import threading
import time
import datetime
import math
import requests

PLANNER_URL = "http://localhost:8000"
BULK_BATCH_SIZE = 100          # Kaç konum bir seferde POST edilir
STEP_METERS = 500              # Her adım kaç metre (500m = ~1 sn gerçek hız yaklaşık)
PLANE_SPEED_KMH = 900          # Ortalama yolcu uçağı hızı

_lock = threading.Lock()
_simulations: dict = {}        # flight_id -> SimulationState
_reset_flights: set = set()    # Sıfırlanmış uçuşlar (Sandbox Mode)
_local_sim_positions: dict = {} # flight_id -> [lat, lon] (Sandbox uçuşlar için)

def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    d = math.pi / 180
    dlat = (lat2 - lat1) * d
    dlon = (lon2 - lon1) * d
    a = math.sin(dlat/2)**2 + math.cos(lat1*d)*math.cos(lat2*d)*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0, 1-a)))

def _move_towards(lat1, lon1, lat2, lon2, dist_km):
    """
    Great Circle (Büyük Çember) formülü kullanılarak uçağı mevcut konumundan 
    hedefe doğru dist_km kadar uçurur ve yeni koordinatını döndürür.
    """
    R = 6371.0
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

    # Bearing (Yön açısı)
    y = math.sin(lon2_rad - lon1_rad) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(lon2_rad - lon1_rad)
    brng = math.atan2(y, x)

    # Yeni koordinat hesabı
    d_angular = dist_km / R
    lat3_rad = math.asin(math.sin(lat1_rad) * math.cos(d_angular) +
                         math.cos(lat1_rad) * math.sin(d_angular) * math.cos(brng))
    lon3_rad = lon1_rad + math.atan2(math.sin(brng) * math.sin(d_angular) * math.cos(lat1_rad),
                                     math.cos(d_angular) - math.sin(lat1_rad) * math.sin(lat3_rad))

    return [math.degrees(lat3_rad), math.degrees(lon3_rad)]

def _calculate_total_distance(all_points):
    total = 0.0
    for i in range(len(all_points) - 1):
        p1, p2 = all_points[i], all_points[i+1]
        total += _haversine_km(p1[0], p1[1], p2[0], p2[1])
    return total

def _fetch_flights():
    try:
        r = requests.get(f"{PLANNER_URL}/api/flights", timeout=5)
        return r.json()
    except Exception as e:
        raise RuntimeError(f"Backend'e ulaşılamadı: {e}")

def _fetch_history() -> dict:
    try:
        r = requests.get(f"{PLANNER_URL}/api/flights/history", timeout=5)
        return r.json()
    except Exception:
        return {}

def _resume_base(f: dict, history_map: dict):
    hist_data = history_map.get(f["id"])
    if not hist_data or not hist_data.get("history"):
        return None
    history = hist_data["history"]
    return history[0]["t"], history[-1]["t"]

def _scheduled_base_ts(f: dict) -> float:
    start_str = f.get("startTime", "00:00")
    try:
        h, m = map(int, start_str.split(":"))
    except Exception:
        h, m = 0, 0
    now = datetime.datetime.now()
    base_ts = now.replace(hour=h, minute=m, second=0, microsecond=0).timestamp()
    if base_ts > time.time():
        base_ts -= 24 * 3600
    return base_ts

def _post_bulk(buffer):
    if not buffer:
        return
    try:
        requests.post(f"{PLANNER_URL}/api/simulator/positions", json=buffer, timeout=5)
    except Exception:
        pass

def catch_up_offline_flights():
    """
    Sistem başlatıldığında çalışır. Dinamik kinematik motoru kullanarak eksik
    geçmişi saniyeler içinde hesaplayıp (fast-forward) yazar.
    """
    history_map = None
    for attempt in range(5):
        try:
            flights = _fetch_flights()
            history_map = _fetch_history()
            break
        except Exception as e:
            print(f"[Catch-Up] Backend henüz hazır değil. Bekleniyor... {e}")
            time.sleep(2)

    if not history_map:
        return

    now_ts = time.time()
    started = 0

    for f in flights:
        fid = f["id"]
        hist_data = history_map.get(fid)

        if not hist_data or not hist_data.get("history"):
            base_timestamp = _scheduled_base_ts(f)
            last_timestamp = base_timestamp
        else:
            history = hist_data["history"]
            base_timestamp = history[0]["t"]
            last_timestamp = history[-1]["t"]

        if now_ts - last_timestamp < 5:
            continue

        all_points = [f["origin"]] + f.get("waypoints", []) + [f["destination"]]
        
        # Sadece eksik süreyi telafi etmesi için thread'i başlat. Thread zaten 
        # sim_t < now olduğu sürece beklemeden (fast-forward) çalışır.
        print(f"[Catch-Up] {fid} için dinamik telafi başlatılıyor...")
        
        with _lock:
            _simulations[fid] = {
                "flight_id": fid,
                "running": True,
                "total_steps": 100, 
                "step": 0,
                "start_time": base_timestamp,
                "status": "running",
                "speed": 1
            }
        t = threading.Thread(target=_run, args=(fid, all_points, 1, base_timestamp, last_timestamp, False), daemon=True)
        t.start()
        started += 1

    print(f"[Catch-Up] Tamamlandı. {started} uçuş dinamik olarak canlandırıldı.")

def _run(flight_id: str, all_points: list, initial_speed: int, base_timestamp: float, skip_until: float = 0, sandbox_mode: bool = False):
    """
    Dinamik Kinematik Fizik Motoru (True Kinematic Engine):
    Rotayı önceden statik olarak hesaplamaz. Her adımda "Şu an neredeyim, hedefe ne kadar kaldı?"
    diyerek vektörel (ileriye dönük) hesaplama yapar.
    """
    total_distance_km = _calculate_total_distance(all_points)
    current_wp_idx = 0
    current_pos = all_points[0]
    
    CRUISE_ALT = 36000.0  
    CRUISE_SPD = 485.0    
    TAKEOFF_SPD = 150.0   
    LANDING_SPD = 135.0   
    
    covered_distance_km = 0.0
    sim_t = base_timestamp
    buffer = []
    step_idx = 0 
    
    # Hedef son waypoint olana kadar devam et
    while current_wp_idx < len(all_points) - 1:
        target_wp = all_points[current_wp_idx + 1]
        dist_to_target = _haversine_km(current_pos[0], current_pos[1], target_wp[0], target_wp[1])
        
        # Uçak saatte 900km hızla uçuyor. 1 saniyede 0.25 km gider.
        # Biz 2 saniyelik adımlar atıyoruz, yani step_dist_km = 0.5 km (500 metre)
        secs_per_step = 2.0
        step_dist_km = 0.5
        
        # Eğer hedefe (waypoint) ulaşmaya çok az kaldıysa tam üstüne in ve sonraki waypoint'e geç
        if dist_to_target <= step_dist_km:
            current_pos = target_wp
            covered_distance_km += dist_to_target
            current_wp_idx += 1
            secs_per_step = (dist_to_target / PLANE_SPEED_KMH) * 3600
        else:
            # Hedefe doğru vektörel 500m (0.5 km) ilerle (True Kinematics)
            current_pos = _move_towards(current_pos[0], current_pos[1], target_wp[0], target_wp[1], step_dist_km)
            covered_distance_km += step_dist_km
            
        step_idx += 1
        sim_t += secs_per_step
        
        # Daha önceden DB'ye yazılmış kısmı hesaplıyorsak (Catch-up sırasında), DB'ye post etmeden geç
        if sim_t <= skip_until:
            continue
            
        # VNAV (Dikey İrtifa/Hız) Hesaplaması: Uçuşun % kaçı bittiğine göre dinamik belirlenir
        f = covered_distance_km / max(0.1, total_distance_km)
        f = min(1.0, max(0.0, f))
        
        if f < 0.18:
            t = f / 0.18
            alt = round(CRUISE_ALT * math.sin(t * math.pi / 2))
            spd = round(TAKEOFF_SPD + (CRUISE_SPD - TAKEOFF_SPD) * (t ** 0.8))
        elif f <= 0.82:
            alt = round(CRUISE_ALT + 75.0 * math.sin(step_idx * 0.35))
            spd = round(CRUISE_SPD + 5.0 * math.cos(step_idx * 0.2))
        else:
            t = (f - 0.82) / 0.18
            alt = round(CRUISE_ALT * math.cos(t * math.pi / 2))
            spd = round(CRUISE_SPD - (CRUISE_SPD - LANDING_SPD) * (t ** 0.8))
            
        payload = {
            "flight_id": flight_id,
            "timestamp": sim_t,
            "position": current_pos,
            "altitude": max(0.0, float(alt)),
            "speed_kts": max(0.0, float(spd))
        }
        
        with _lock:
            state = _simulations.get(flight_id)
            if not state or not state.get("running"):
                return
            current_speed = state.get("speed", initial_speed)
            state["step"] = int(f * 100) # Progress'i step üzerinden % olarak tutalım UI için
            state["total_steps"] = 100
            
        sleep_interval = secs_per_step / max(1, current_speed)
        
        with _lock:
            _local_sim_positions[flight_id] = current_pos
            
        if not sandbox_mode:
            if sim_t < time.time():
                # Uçak geçmişte kalmış, beklemeden "Fast-Forward" (Hızlı ileri sarma) yap
                buffer.append(payload)
                if len(buffer) >= BULK_BATCH_SIZE:
                    _post_bulk(buffer)
                    buffer = []
            else:
                # Uçak günümüze yetişti, gerçek zamanlı uyuyarak (Live) devam et
                if buffer:
                    _post_bulk(buffer)
                    buffer = []
                _post_bulk([payload])
                time.sleep(sleep_interval)
        else:
            # Sandbox (Offline test) modu: DB'ye veri atma, sadece zamanı gelince RAM'i güncelle
            if sim_t >= time.time():
                time.sleep(sleep_interval)

    # Uçuş Bitti: Hedefe (Destination) Ulaşıldı
    if not sandbox_mode:
        _post_bulk(buffer)
        
    with _lock:
        if flight_id in _simulations:
            _simulations[flight_id]["running"] = False
            _simulations[flight_id]["status"] = "landed"

def start_all(speed: int = 1) -> dict:
    flights = _fetch_flights()
    history_map = _fetch_history()
    started, skipped = [], []

    for f in flights:
        fid = f["id"]
        with _lock:
            existing = _simulations.get(fid)
            if existing and existing.get("running"):
                skipped.append(fid)
                continue
            is_reset = fid in _reset_flights

        all_points = [f["origin"]] + f.get("waypoints", []) + [f["destination"]]

        skip_until = 0
        sandbox = False
        if is_reset:
            base_ts = time.time()
            sandbox = True
        else:
            resume = _resume_base(f, history_map)
            if resume:
                base_ts, skip_until = resume
            else:
                base_ts = _scheduled_base_ts(f)

        with _lock:
            _simulations[fid] = {
                "flight_id": fid,
                "running": True,
                "total_steps": 100,
                "step": 0,
                "start_time": time.time(),
                "status": "running",
                "speed": speed
            }
            if not sandbox:
                _reset_flights.discard(fid)
                if fid in _local_sim_positions:
                    del _local_sim_positions[fid]

        t = threading.Thread(target=_run, args=(fid, all_points, speed, base_ts, skip_until, sandbox), daemon=True)
        t.start()
        started.append(fid)

    return {"started": started, "skipped": skipped}

def start_one(flight_id: str, speed: int = 1):
    flights = _fetch_flights()
    f = next((fl for fl in flights if fl["id"] == flight_id), None)
    if not f:
        return False

    with _lock:
        if flight_id in _simulations and _simulations[flight_id]["running"]:
            return False 
        is_reset = flight_id in _reset_flights

    all_points = [f["origin"]] + f.get("waypoints", []) + [f["destination"]]

    skip_until = 0
    sandbox = False
    if is_reset:
        base_timestamp = time.time()
        sandbox = True
    else:
        resume = _resume_base(f, _fetch_history())
        if resume:
            base_timestamp, skip_until = resume
        else:
            base_timestamp = time.time()

    with _lock:
        _simulations[flight_id] = {
            "flight_id": flight_id,
            "running": True,
            "total_steps": 100,
            "step": 0,
            "start_time": time.time(),
            "status": "running",
            "speed": speed
        }
        if not sandbox:
            _reset_flights.discard(flight_id)
            if flight_id in _local_sim_positions:
                del _local_sim_positions[flight_id]

    t = threading.Thread(target=_run, args=(flight_id, all_points, speed, base_timestamp, skip_until, sandbox), daemon=True)
    t.start()
    return True

def stop_one(flight_id: str) -> bool:
    with _lock:
        if flight_id not in _simulations:
            return False
        _simulations[flight_id]["running"] = False
    return True

def reset_one(flight_id: str) -> bool:
    with _lock:
        if flight_id in _simulations:
            _simulations[flight_id]["running"] = False
            del _simulations[flight_id]
        _reset_flights.add(flight_id)
        if flight_id in _local_sim_positions:
            del _local_sim_positions[flight_id]
    return True

def change_speed(flight_id: str, speed: int) -> bool:
    with _lock:
        state = _simulations.get(flight_id)
        if state and state.get("running"):
            state["speed"] = speed
            return True
    return False

def change_all_speed(speed: int):
    with _lock:
        for s in _simulations.values():
            if s.get("running"):
                s["speed"] = speed

def reset_all():
    try:
        flights = _fetch_flights()
        all_ids = [f["id"] for f in flights]
    except Exception:
        all_ids = []

    with _lock:
        for s in _simulations.values():
            s["running"] = False
        _simulations.clear()
        _reset_flights.update(all_ids)
        _local_sim_positions.clear()

def get_status() -> list:
    result = []
    with _lock:
        now = time.time()
        for fid, s in _simulations.items():
            if s.get("running") or s.get("status") == "running":
                step = s.get("step", 0)
                total = max(s.get("total_steps", 1), 1)
                progress = step # Already calculated as percentage 0-100
                start_time = s.get("start_time", now)
                elapsed = int(now - start_time)
                result.append({
                    "flight_id": fid, 
                    "status": s.get("status", "running"), 
                    "speed": s.get("speed", 1),
                    "step": step,
                    "total_steps": total,
                    "progress": progress,
                    "elapsed_sec": elapsed
                })
    return result

def get_render_positions() -> list:
    try:
        flights = _fetch_flights()
    except Exception:
        return []
    origin_map = {f["id"]: f["origin"] for f in flights}

    with _lock:
        reset_ids = set(_reset_flights)

    try:
        now_ts = int(time.time())
        r = requests.get(f"{PLANNER_URL}/api/flights/positions", params={"time": now_ts}, timeout=5)
        positions = r.json()
    except Exception:
        positions = []

    result = []
    seen = set()
    for p in positions:
        fid = p.get("flight_id")
        seen.add(fid)
        if fid in reset_ids and fid in origin_map:
            with _lock:
                pos = _local_sim_positions.get(fid, origin_map[fid])
            result.append({"flight_id": fid, "position": pos})
        else:
            result.append(p)

    for fid, origin in origin_map.items():
        if fid not in seen:
            result.append({"flight_id": fid, "position": origin})

    return result
