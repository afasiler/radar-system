import time
import requests
import math
from datetime import datetime

BASE_URL = "http://localhost:8000/api"

# ── Bugün 17:40'ta başla ──────────────────────────────────────
def get_flight_start_ts():
    """Bugünün 17:40'ını Unix timestamp olarak döndürür (yerel saat)."""
    now = datetime.now()
    start = now.replace(hour=17, minute=40, second=0, microsecond=0)
    return int(start.timestamp())

FLIGHT_START_TS = get_flight_start_ts()

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def get_segmented_line(lat1, lng1, lat2, lng2, num_segments):
    if num_segments <= 0:
        return [[lat2, lng2]]
    points = []
    for i in range(num_segments + 1):
        f = i / num_segments
        points.append([lat1 + (lat2 - lat1) * f, lng1 + (lng2 - lng1) * f])
    return points

def run_simulator():
    start_str = datetime.fromtimestamp(FLIGHT_START_TS).strftime('%H:%M')
    print(f"Simülatör hazır. Uçuşlar {start_str}'da başlayacak.")

    # Uçuşları backend'den çek
    while True:
        try:
            resp = requests.get(f"{BASE_URL}/flights")
            if resp.status_code == 200:
                flights = resp.json()
                if not flights:
                    print("Hiç uçuş yok. Bekleniyor...")
                    time.sleep(5)
                    continue
                break
        except Exception:
            print("Backend kapalı, bekleniyor...")
            time.sleep(5)

    # Her uçuş için rota hesapla (900 km/s gerçekçi hız)
    flight_routes = {}
    for f in flights:
        dist_km = haversine(f['origin'][0], f['origin'][1], f['destination'][0], f['destination'][1])
        duration_sec = max(1, int(dist_km / 0.25))  # 900 km/h = 0.25 km/s
        route = get_segmented_line(
            f['origin'][0], f['origin'][1],
            f['destination'][0], f['destination'][1],
            duration_sec
        )
        flight_routes[f['id']] = {'route': route, 'duration': duration_sec}
        print(f"  [{f['id']}] {int(dist_km)} km → {duration_sec // 60} dk {duration_sec % 60} sn")

    print(f"\nTelemetri döngüsü başladı. Şu an: {datetime.now().strftime('%H:%M:%S')}")

    # --- Fast Forward Logic ---
    now_ts = int(time.time())

    # Fetch history
    try:
        hist_resp = requests.get(f"{BASE_URL}/flights/history")
        hist_data = hist_resp.json() if hist_resp.status_code == 200 else []
    except Exception:
        hist_data = []

    last_ts_per_flight = {}
    for h in hist_data:
        fid = h.get('flight_id')
        ts = h.get('timestamp')
        if ts:
            if fid not in last_ts_per_flight or ts > last_ts_per_flight[fid]:
                last_ts_per_flight[fid] = ts

    missing_positions = []

    if now_ts > FLIGHT_START_TS:
        for f in flights:
            fid = f['id']
            last_ts = last_ts_per_flight.get(fid, FLIGHT_START_TS)

            state = flight_routes[fid]
            route = state['route']

            for t in range(last_ts + 1, now_ts + 1):
                step = min(t - FLIGHT_START_TS, len(route) - 1)
                if step < 0:
                    continue
                missing_positions.append({
                    "flight_id": fid,
                    "timestamp": t,
                    "position": route[step]
                })

    # Send missing positions in chunks of 100
    if missing_positions:
        print(f"Fast-forwarding {len(missing_positions)} missed positions...")
        chunk_size = 100
        for i in range(0, len(missing_positions), chunk_size):
            chunk = missing_positions[i:i + chunk_size]
            try:
                requests.post(f"{BASE_URL}/simulator/positions", json=chunk)
            except Exception as e:
                print("Fast-forward Hata:", e)
        print("Fast-forward complete.")

    while True:
        now_ts = int(time.time())

        # 17:40'tan önce ise, başlangıç noktasında beklet (kayıt gönderme)
        if now_ts < FLIGHT_START_TS:
            remaining = FLIGHT_START_TS - now_ts
            print(f"Kalkışa {remaining} saniye kaldı...", end='\r')
            time.sleep(1)
            continue

        # Kaç saniye geçti 17:40'tan beri?
        elapsed = now_ts - FLIGHT_START_TS

        positions_to_send = []
        for f in flights:
            state = flight_routes[f['id']]
            route = state['route']
            # Geçen süreye göre adım belirle (sınırı aşma)
            step = min(elapsed, len(route) - 1)
            current_pos = route[step]
            positions_to_send.append({
                "flight_id": f['id'],
                "timestamp": now_ts,
                "position": current_pos
            })

        if positions_to_send:
            try:
                requests.post(f"{BASE_URL}/simulator/positions", json=positions_to_send)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {len(positions_to_send)} uçuş güncellendi (elapsed: {elapsed}s)")
            except Exception as e:
                print("Hata:", e)

        time.sleep(1)

if __name__ == "__main__":
    run_simulator()
