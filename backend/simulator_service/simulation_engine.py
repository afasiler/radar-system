"""
simulation_engine.py - Temiz, sıfırdan yazılmış simülatör motoru.

Mimari:
- Her uçuş için ayrı bir thread.
- Geçmişteki zaman aralıklarını hemen (sleep olmadan) DB'ye toplu yazar.
- Gerçek zamana ulaşınca normal 1sn/adım hızına geçer.
- Tüm state thread-safe Lock ile korunur.
"""

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


# ── Yardımcı: Haversine (km) ─────────────────────────────────────

def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    d = math.pi / 180
    dlat = (lat2 - lat1) * d
    dlon = (lon2 - lon1) * d
    a = math.sin(dlat/2)**2 + math.cos(lat1*d)*math.cos(lat2*d)*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0, 1-a)))


# ── Yardımcı: Büyük çember boyunca N nokta üret ──────────────────

def _great_circle_points(lat1, lon1, lat2, lon2, n):
    """origin'den destination'a n+1 eşit aralıklı nokta döndürür."""
    d = math.pi / 180
    lat1r, lon1r, lat2r, lon2r = lat1*d, lon1*d, lat2*d, lon2*d

    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = math.sin(dlat/2)**2 + math.cos(lat1r)*math.cos(lat2r)*math.sin(dlon/2)**2
    dist = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0, 1-a)))

    if dist < 1e-10:
        return [[lat1, lon1]] * (n + 1)

    pts = []
    for i in range(n + 1):
        f = i / n
        A = math.sin((1-f)*dist) / math.sin(dist)
        B = math.sin(f*dist) / math.sin(dist)
        x = A*math.cos(lat1r)*math.cos(lon1r) + B*math.cos(lat2r)*math.cos(lon2r)
        y = A*math.cos(lat1r)*math.sin(lon1r) + B*math.cos(lat2r)*math.sin(lon2r)
        z = A*math.sin(lat1r) + B*math.sin(lat2r)
        pts.append([
            math.degrees(math.atan2(z, math.sqrt(x**2 + y**2))),
            math.degrees(math.atan2(y, x))
        ])
    return pts


STEP_METERS = 500
PLANE_SPEED_KMH = 900

def _build_route(all_points):
    """
    Waypoint'ler dahil tüm rotayı STEP_METERS aralıklı noktalarla döndürür.
    Dönüş: [( [lat, lon], secs_per_step, altitude_ft, speed_kts ), ...]
    """
    raw_steps = []
    for i in range(len(all_points) - 1):
        p1, p2 = all_points[i], all_points[i+1]
        dist_km = _haversine_km(p1[0], p1[1], p2[0], p2[1])

        # Orijinal yüksek frekanslı nokta hesabı (her 500 metrede bir)
        n_steps = max(1, int(dist_km * 1000 / STEP_METERS))
        seg = _great_circle_points(p1[0], p1[1], p2[0], p2[1], n_steps)

        # 900 km/h hızı korumak için bu segmentin adım süresi (yaklaşık 2 saniye)
        total_time_secs = (dist_km / PLANE_SPEED_KMH) * 3600
        secs_per_step = total_time_secs / max(1, n_steps)

        if i < len(all_points) - 2:
            seg = seg[:-1]

        for pt in seg:
            raw_steps.append((pt, secs_per_step))

    M = len(raw_steps)
    if M == 0:
        return []

    CRUISE_ALT = 36000.0  # feet
    CRUISE_SPD = 485.0    # knots
    TAKEOFF_SPD = 150.0   # knots
    LANDING_SPD = 135.0   # knots

    route = []
    for k, (pt, secs_per_step) in enumerate(raw_steps):
        f = k / max(1, M - 1)  # 0.0 -> 1.0

        if f < 0.18:
            # Tırmanma (Climb): 0 -> 36,000 ft
            t = f / 0.18
            alt = round(CRUISE_ALT * math.sin(t * math.pi / 2))
            spd = round(TAKEOFF_SPD + (CRUISE_SPD - TAKEOFF_SPD) * (t ** 0.8))
        elif f <= 0.82:
            # Düz Uçuş (Cruise): 36,000 ft ± 75 ft
            alt = round(CRUISE_ALT + 75.0 * math.sin(k * 0.35))
            spd = round(CRUISE_SPD + 5.0 * math.cos(k * 0.2))
        else:
            # Alçalma (Descent): 36,000 -> 0 ft
            t = (f - 0.82) / 0.18
            alt = round(CRUISE_ALT * math.cos(t * math.pi / 2))
            spd = round(CRUISE_SPD - (CRUISE_SPD - LANDING_SPD) * (t ** 0.8))

        route.append((pt, secs_per_step, max(0.0, float(alt)), max(0.0, float(spd))))
    return route


# ── Backend'den uçuş planlarını çek ─────────────────────────────

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
    """
    Bir uçuşun DB'deki (REST ile çekilen) geçmişine bakarak "gerçekte nerede
    kaldıysa oradan devam" noktasını bulur. Simülatörün amacı artık origin'den
    sıfırdan uçurmak değil — havadaysa kaldığı yerden, indiyse indiği haliyle
    göstermek.

    Dönüş:
      None                          → geçmiş yok (yepyeni uçuş, origin'den başlar)
      (base_timestamp, skip_until)  → bu noktadan devam edilmeli
                                        (skip_until'a kadarki adımlar DB'de zaten
                                        var, tekrar postalanmaz; skip_until ==
                                        rotanın sonuna eşit/yakınsa uçuş zaten
                                        inmiş demektir, _run() hemen "landed"
                                        durumuna geçer — bu da doğru davranıştır)
    """
    hist_data = history_map.get(f["id"])
    if not hist_data or not hist_data.get("history"):
        return None
    history = hist_data["history"]
    return history[0]["t"], history[-1]["t"]


def _scheduled_base_ts(f: dict) -> float:
    """Uçuşun planlanan kalkış saatini bugünün gerçek timestamp'ine çevirir."""
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


# ── Toplu POST ───────────────────────────────────────────────────

def _post_bulk(buffer):
    if not buffer:
        return
    try:
        requests.post(f"{PLANNER_URL}/api/simulator/positions", json=buffer, timeout=5)
    except Exception:
        pass  # Ağ hatası olursa sessizce geç

# ── Çevrimdışı Telafi (Offline Catch-Up) ─────────────────────────

def catch_up_offline_flights():
    """
    Sistem başlatıldığında çalışır. Sunucu kapalıyken yarıda kalan uçuşların
    geçen zamandaki hareketlerini hesaplayıp tek seferde veritabanına yazar.
    Uçuş hala bitmediyse kaldığı yerden (canlı) devam ettirir.
    """
    # Ana backend'in uyanmasını bekle (start_all ile aynı anda başlatıldığında hazır olmayabilir)
    history_map = None
    for attempt in range(5):
        try:
            flights = _fetch_flights()
            r = requests.get(f"{PLANNER_URL}/api/flights/history", timeout=5)
            history_map = r.json()
            break
        except Exception as e:
            print(f"[Catch-Up] Backend henüz hazır değil (Deneme {attempt+1}/5). 2sn bekleniyor... Hata: {e}")
            time.sleep(2)

    if not history_map:
        print(f"[Catch-Up] Backend'e ulaşılamadı. İptal ediliyor.")
        return

    now_ts = time.time()
    started = 0

    for f in flights:
        fid = f["id"]
        hist_data = history_map.get(fid)

        if not hist_data or not hist_data.get("history"):
            start_str = f.get("startTime", "00:00")
            try:
                h, m = map(int, start_str.split(":"))
            except Exception:
                h, m = 0, 0
            now = datetime.datetime.now()
            base_timestamp = now.replace(hour=h, minute=m, second=0, microsecond=0).timestamp()
            if base_timestamp > time.time():
                base_timestamp -= 24 * 3600
            last_timestamp = base_timestamp
        else:
            history = hist_data["history"]
            base_timestamp = history[0]["t"]
            last_timestamp = history[-1]["t"]

        if now_ts - last_timestamp < 5:
            continue

        all_points = [f["origin"]] + f.get("waypoints", []) + [f["destination"]]
        route = _build_route(all_points)

        sim_t = base_timestamp
        missing_points = []

        for pt, secs_per_step, altitude, speed_kts in route:
            if sim_t > last_timestamp and sim_t <= now_ts:
                missing_points.append({
                    "flight_id": fid,
                    "timestamp": sim_t,
                    "position": [pt[0], pt[1]],
                    "altitude": altitude,
                    "speed_kts": speed_kts
                })
            sim_t += secs_per_step

        if missing_points:
            print(f"[Catch-Up] {fid} için {len(missing_points)} eksik konum tamamlandı.")
            for i in range(0, len(missing_points), BULK_BATCH_SIZE):
                _post_bulk(missing_points[i:i+BULK_BATCH_SIZE])

        if sim_t > now_ts:
            print(f"[Catch-Up] {fid} havada, canlı simülasyon devam ettiriliyor...")
            with _lock:
                _simulations[fid] = {
                    "flight_id": fid,
                    "running": True,
                    "total_steps": len(route),
                    "step": 0,
                    "start_time": base_timestamp,
                    "status": "running",
                    "speed": 1
                }
            t = threading.Thread(target=_run, args=(fid, route, 1, base_timestamp, last_timestamp, False), daemon=True)
            t.start()
            started += 1

    print(f"[Catch-Up] Tamamlandı. {started} uçuş tekrar canlandırıldı.")


# ── Thread gövdesi ───────────────────────────────────────────────

def _run(flight_id: str, route: list, initial_speed: int, base_timestamp: float, skip_until: float = 0, sandbox_mode: bool = False):
    """
    Her adım:
    - simulated_time < now  → sleep yok, bulk buffer'a ekle (fast-forward)
    - simulated_time >= now → normal hızda uyu (live)
    - simulated_time <= skip_until → zaten işlenmiş, atla
    - sandbox_mode == True → Veritabanına ASLA YAZMA, sadece RAM'de tut
    """
    sim_t = base_timestamp
    buffer = []

    for item in route:
        pt, secs_per_step, altitude, speed_kts = item

        if sim_t <= skip_until:
            sim_t += secs_per_step
            continue

        # Dışarıdan durduruldu mu veya hız değişti mi?
        with _lock:
            state = _simulations.get(flight_id)
            if not state or not state.get("running"):
                return
            current_speed = state.get("speed", initial_speed)
            state["step"] += 1

        sleep_interval = secs_per_step / max(1, current_speed)
        payload = {
            "flight_id": flight_id,
            "timestamp": sim_t,
            "position": [pt[0], pt[1]],
            "altitude": altitude,
            "speed_kts": speed_kts
        }

        # Sandbox modu da olsa 8001 ekranı görsün diye RAM'e kaydet
        with _lock:
            _local_sim_positions[flight_id] = [pt[0], pt[1]]

        if not sandbox_mode:
            if sim_t < time.time():
                # Fast-forward: beklemeden buffer'a yaz
                buffer.append(payload)
                if len(buffer) >= BULK_BATCH_SIZE:
                    _post_bulk(buffer)
                    buffer = []
            else:
                # Önce kalan buffer'ı temizle
                if buffer:
                    _post_bulk(buffer)
                    buffer = []
                # Tek tek gönder ve uyu
                _post_bulk([payload])
                time.sleep(sleep_interval)
        else:
            # Sandbox modundaysa sadece uyu (DB'ye yazma)
            if sim_t >= time.time():
                time.sleep(sleep_interval)

        sim_t += secs_per_step

    # Rota bitti: kalan buffer'ı gönder
    if not sandbox_mode:
        _post_bulk(buffer)

    with _lock:
        if flight_id in _simulations:
            _simulations[flight_id]["running"] = False
            _simulations[flight_id]["status"] = "landed"


# ── Public API ───────────────────────────────────────────────────

def start_all(speed: int = 1) -> dict:
    """
    DB'deki tüm uçuşlar için simülasyon başlatır. Zaten çalışanları atlar.

    - SIFIRLANMIŞ bir uçuş (kullanıcı Reset'e bastıysa): her zaman origin'den,
      şimdi itibarıyla TAZE başlar. Reset'in niyeti "tekrar baştan uçur"tur —
      DB'de eskiden (belki tamamlanmış) bir geçmiş olması bunu değiştirmez.
    - Sıfırlanmamış bir uçuş: DB'deki GERÇEK durumundan (havadaysa kaldığı
      yerden, inmişse indiği haliyle) devam eder — ör. servis yeniden
      başladığı için hafızası kaybolmuş ama uçuş gerçekte hâlâ havadaysa.
    - Hiç geçmişi yoksa (yepyeni uçuş): origin'den/planlanan saatten başlar.
    """
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

        # NOT: DB geçmişi burada asla silinmez — hem React frontend'in geçmişi/slider'ı
        # buna bağımlı, hem de "kaldığı yerden devam" mantığının kendisi buna dayanıyor.
        waypoints = f.get("waypoints") or []
        all_points = [f["origin"]] + waypoints + [f["destination"]]
        route = _build_route(all_points)

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
                "total_steps": len(route),
                "step": 0,
                "start_time": time.time(),
                "status": "running",
                "speed": speed
            }
            # Eğer uçak artık normal çalışacaksa reset listesinden çıkar (Sandbox'tan çıkar)
            if not sandbox:
                _reset_flights.discard(fid)
                if fid in _local_sim_positions:
                    del _local_sim_positions[fid]

        t = threading.Thread(target=_run, args=(fid, route, speed, base_ts, skip_until, sandbox), daemon=True)
        t.start()
        started.append(fid)

    return {"started": started, "skipped": skipped}


def start_one(flight_id: str, speed: int = 1):
    """Bkz. start_all() docstring'i — aynı 'kaldığı yerden devam' mantığı burada da geçerli."""
    flights = _fetch_flights()
    f = next((fl for fl in flights if fl["id"] == flight_id), None)
    if not f:
        return False

    with _lock:
        if flight_id in _simulations and _simulations[flight_id]["running"]:
            return False # zaten çalışıyor
        is_reset = flight_id in _reset_flights

    # NOT: DB geçmişi burada asla silinmez — bkz. start_all() içindeki aynı not.
    all_points = [f["origin"]] + f.get("waypoints", []) + [f["destination"]]
    route = _build_route(all_points)

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
            "total_steps": len(route),
            "step": 0,
            "start_time": time.time(),
            "status": "running",
            "speed": speed
        }
        if not sandbox:
            _reset_flights.discard(flight_id)
            if flight_id in _local_sim_positions:
                del _local_sim_positions[flight_id]

    t = threading.Thread(target=_run, args=(flight_id, route, speed, base_timestamp, skip_until, sandbox), daemon=True)
    t.start()
    return True


def stop_one(flight_id: str) -> bool:
    with _lock:
        if flight_id not in _simulations:
            return False
        _simulations[flight_id]["running"] = False
    return True


def reset_one(flight_id: str) -> bool:
    """
    Tek bir uçuşu sıfırlar: simülasyonu durdurur ve _reset_flights'e ekler.
    Veritabanına DOKUNMAZ — bu state tamamen bu servisin kendi belleğinde yaşar,
    5173'teki ana frontend'in DB geçmişi hiç etkilenmez. get_render_positions()
    bu uçuş için origin döndürecek şekilde bunu kullanır.
    """
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
    """Bilinen tüm uçuşları sıfırlar (bkz. reset_one) — hepsi origin'e döner, DB'ye dokunulmaz."""
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
                progress = int((step / total) * 100)
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
    """
    Simülatörün kendi haritasında (8001) gösterilecek pozisyonlar. Sıfırlanmış
    uçuşlar için ana backend'den gelen gerçek DB pozisyonu YOKSAYILIR, o uçuşun
    origin'i döndürülür — DB'ye hiç yazılmaz/silinmez, sadece bu servisin cevabı
    değişir. 5173'teki ana frontend bu uca hiç bakmaz, dolayısıyla etkilenmez.
    """
    try:
        flights = _fetch_flights()
    except Exception:
        return []
    origin_map = {f["id"]: f["origin"] for f in flights}

    # ÖNEMLİ: reset_ids, pozisyonları ÇEKMEDEN ÖNCE alınmalı. Aksi halde iki ayrı ağ
    # isteği (bu ve start_one/start_all) arasındaki sıralama yüzünden şu senaryo
    # oluşabilir: pozisyon isteği DELETE'ten (start_one/start_all) ÖNCE gönderilip
    # eski/gerçek veriyi döndürür, ama cevap gelene kadar geçen sürede start_one
    # zaten _reset_flights.discard() yapmış olur — override artık uygulanmaz ve tek
    # bir kare boyunca eski (yanlış) konum sızar. reset_ids'i önce almak, "şüpheye
    # düşünce origin göster" yönünde güvenli tarafta kalmayı garanti eder.
    with _lock:
        reset_ids = set(_reset_flights)

    # ÖNEMLİ: time=<gerçek şimdi> parametresi olmadan bu uç "ne zaman olursa olsun
    # en son kaydı" döndürür. Yüksek hızda (10x/50x) kaydedilen gerçekçi zaman
    # çizelgesi (sim_t) TASARIM GEREĞİ gerçek saatten ileride olabilir — bu yüzden
    # eski (ör. tamamlanmış) bir koşunun kaydı, taze başlatılan yeni bir koşunun
    # gerçek-zamanlı kayıtlarından "daha yeni" görünmeye devam eder ve uçak yanlışlıkla
    # eski (ör. varış) konumunda gösterilir. Gerçek zamana kadar olanı istemek bunu
    # kayıt hızından bağımsız, "şu an gerçekten nerede" ile tutarlı kılar.
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
            # Sandbox modundaysa RAM'den oku, yoksa origin'i ver
            with _lock:
                pos = _local_sim_positions.get(fid, origin_map[fid])
            result.append({"flight_id": fid, "position": pos})
        else:
            result.append(p)

    for fid, origin in origin_map.items():
        if fid not in seen:
            result.append({"flight_id": fid, "position": origin})

    return result
