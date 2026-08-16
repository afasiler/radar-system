"""
simulator_main.py — Simülatör Servisi (Port 8001)

Bağımsız bir FastAPI uygulaması. Ana backend'den (8000) bağımsız çalışır.
Kontrol paneli: http://localhost:8001
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import simulation_engine as engine

from pathlib import Path
_HERE = Path(__file__).parent
_FRONTEND = _HERE / "sim_frontend"

app = FastAPI(title="Flight Simulator Service", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.mount("/ui", StaticFiles(directory=str(_FRONTEND), html=True), name="frontend")

@app.on_event("startup")
def startup_event():
    import threading
    print("[Simulator] Başlatılıyor... Çevrimdışı telafi yapılıyor.")
    threading.Thread(target=engine.catch_up_offline_flights, daemon=True).start()


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(str(_FRONTEND / "index.html"))


@app.post("/simulations/start")
def start_simulations(speed: int = 1):
    """
    Tüm planlanmış uçuşlar için simülasyon başlatır.
    speed: 1 | 10 | 50
    """
    if speed not in (1, 10, 50):
        raise HTTPException(status_code=400, detail="Geçerli hız değerleri: 1, 10, 50")
    try:
        result = engine.start_all(speed=speed)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ana backend'e ulaşılamadı: {e}")
    return result

@app.post("/simulations/{flight_id}/start")
def start_simulation(flight_id: str, speed: int = 1):
    """Belirli bir uçuşun simülasyonunu başlatır."""
    if speed not in (1, 10, 50):
        raise HTTPException(status_code=400, detail="Geçerli hız değerleri: 1, 10, 50")
    ok = engine.start_one(flight_id, speed)
    if not ok:
        raise HTTPException(status_code=400, detail=f"'{flight_id}' başlatılamadı (Bulunamadı veya zaten çalışıyor).")
    return {"started": flight_id}


@app.post("/simulations/{flight_id}/stop")
def stop_simulation(flight_id: str):
    """Belirli bir uçuşun simülasyonunu durdurur."""
    ok = engine.stop_one(flight_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"'{flight_id}' için aktif simülasyon bulunamadı.")
    return {"stopped": flight_id}

@app.post("/simulations/{flight_id}/speed")
def change_simulation_speed(flight_id: str, speed: int = 1):
    """Belirli bir uçuşun hızını dinamik olarak değiştirir."""
    if speed not in (1, 10, 50):
        raise HTTPException(status_code=400, detail="Geçerli hız değerleri: 1, 10, 50")
    ok = engine.change_speed(flight_id, speed)
    if not ok:
        raise HTTPException(status_code=404, detail=f"'{flight_id}' için hız değiştirilemedi (Aktif değil).")
    return {"speed_changed": flight_id, "new_speed": speed}

@app.post("/simulations/speed")
def change_global_speed(speed: int = 1):
    """Tüm aktif simülasyonların hızını dinamik olarak değiştirir."""
    if speed not in (1, 10, 50):
        raise HTTPException(status_code=400, detail="Geçerli hız değerleri: 1, 10, 50")
    engine.change_all_speed(speed)
    return {"speed_changed": "all", "new_speed": speed}

@app.post("/simulations/reset")
def reset_simulations():
    """
    Tüm uçuşları sıfırlar: durdurur ve simülatörün kendi haritasında origin'e
    döndürür. Veritabanına DOKUNMAZ — ana backend (5173'ün kaynağı) etkilenmez.
    """
    engine.reset_all()
    return {"status": "Tüm simülasyonlar sıfırlandı."}


@app.post("/simulations/{flight_id}/reset")
def reset_simulation(flight_id: str):
    """Tek bir uçuşu sıfırlar (bkz. reset_simulations). DB'ye dokunmaz."""
    engine.reset_one(flight_id)
    return {"status": f"'{flight_id}' sıfırlandı."}


@app.get("/simulations/status")
def get_status():
    """
    Aktif ve yeni inmiş uçuşların durumunu döndürür.
    5 dakika geçmiş (completed) ve durdurulanlar (stopped) dahil edilmez.
    """
    return engine.get_status()


@app.get("/simulations/positions")
def get_render_positions():
    """
    Simülatörün kendi bakış açısından uçuşların konumları. Sıfırlanmış uçuşlar
    burada origin olarak döner; ana backend'deki DB kaydı hiç değişmez. Sim
    frontend'i ana backend'e değil bu uca bakmalı.
    """
    return engine.get_render_positions()
