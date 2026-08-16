import time as time_module
import requests
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from database import engine, Base, get_db
import models
import schemas
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape

# Tabloları oluştur, yeni kolonları migrate et
models.Base.metadata.create_all(bind=engine)
try:
    from sqlalchemy import text
    with engine.connect() as _conn:
        _conn.execute(text("ALTER TABLE flights ADD COLUMN IF NOT EXISTS waypoints_json TEXT DEFAULT '[]'"))
        _conn.execute(text("ALTER TABLE flight_positions ADD COLUMN IF NOT EXISTS altitude FLOAT DEFAULT 0.0"))
        _conn.execute(text("ALTER TABLE flight_positions ADD COLUMN IF NOT EXISTS speed_kts FLOAT DEFAULT 0.0"))
        _conn.commit()
except Exception:
    pass  # DB yoksa veya kolon zaten varsa sessizce geç

app = FastAPI(title="Flight Tracker Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Yardımcı Fonksiyonlar ────────────────────────────────────────

import json as json_module

def create_route_linestring(all_points: list, segments_per_leg: int = 10) -> str:
    """
    Verilen noktalar listesi (origin + waypoints + destination) arasında
    her bacak için segmentlere bölünmüş LINESTRING oluşturur.
    """
    coords = []
    for i in range(len(all_points) - 1):
        lat1, lng1 = all_points[i]
        lat2, lng2 = all_points[i + 1]
        for j in range(segments_per_leg + (1 if i == len(all_points) - 2 else 0)):
            frac = j / segments_per_leg
            lat = lat1 + (lat2 - lat1) * frac
            lng = lng1 + (lng2 - lng1) * frac
            coords.append(f"{lng} {lat}")
    return f"LINESTRING({', '.join(coords)})"


def validate_coords(position: list, label: str = "Koordinat"):
    """Lat/Lng değerlerinin geçerli aralıkta olduğunu kontrol eder."""
    if len(position) != 2:
        raise HTTPException(status_code=422, detail=f"{label}: [lat, lng] formatında 2 değer olmalı")
    lat, lng = position
    if not (-90 <= lat <= 90):
        raise HTTPException(status_code=422, detail=f"{label} Latitude {lat} geçersiz. -90 ile 90 arasında olmalı.")
    if not (-180 <= lng <= 180):
        raise HTTPException(status_code=422, detail=f"{label} Longitude {lng} geçersiz. -180 ile 180 arasında olmalı.")


def validate_timestamp(ts: int):
    """Timestamp'in makul bir zaman diliminde olduğunu kontrol eder."""
    now = int(time_module.time())
    one_week_ago = now - 7 * 24 * 3600   # 1 haftadan eski olmasın
    one_day_future = now + 24 * 3600     # 1 günden fazla gelecekte olmasın
    if not (one_week_ago <= ts <= one_day_future):
        raise HTTPException(
            status_code=422,
            detail=f"Timestamp {ts} geçersiz aralıkta. (1 hafta önce – 1 gün sonrası kabul edilir)"
        )


def validate_flight_id(flight_id: str):
    """Flight ID'nin temiz bir string olduğunu kontrol eder."""
    if not flight_id or not flight_id.strip():
        raise HTTPException(status_code=422, detail="Flight ID boş olamaz.")
    if len(flight_id) > 20:
        raise HTTPException(status_code=422, detail="Flight ID en fazla 20 karakter olabilir.")
    # Sadece harf, rakam, tire ve alt çizgiye izin ver
    import re
    if not re.match(r'^[A-Za-z0-9\-_]+$', flight_id):
        raise HTTPException(status_code=422, detail="Flight ID yalnızca harf, rakam, - ve _ içerebilir.")


# ── Periyodik Temizleme: 24 saatten eski flight_positions kayıtlarını sil ────
def cleanup_old_positions():
    """Her saat çalışır, 24 saatten eski telemetri kayıtlarını siler."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        cutoff = int(time_module.time()) - 24 * 3600
        deleted = db.query(models.FlightPosition).filter(
            models.FlightPosition.timestamp < cutoff
        ).delete()
        db.commit()
        if deleted > 0:
            print(f"[Temizlik] {deleted} eski konum kaydı silindi.")
    except Exception as e:
        print(f"[Temizlik Hatası] {e}")
    finally:
        db.close()

# Uygulama başladığında scheduler'ı başlat
scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_old_positions, 'interval', hours=1, id='cleanup')
scheduler.start()


# ── API Uçları ────────────────────────────────────────────────────

@app.post("/api/flights", response_model=schemas.FlightResponse)
def create_flight(flight: schemas.FlightCreate, db: Session = Depends(get_db)):
    # 1. Flight ID doğrulama
    validate_flight_id(flight.id)

    # 2. Koordinat doğrulama
    validate_coords(flight.origin, "Kalkış koordinatı")
    validate_coords(flight.destination, "Varış koordinatı")

    # 3. Kalkış ve varış aynı nokta mı?
    if flight.origin == flight.destination:
        raise HTTPException(status_code=422, detail="Kalkış ve varış noktaları aynı olamaz.")

    # 4. Mükerrer ID kontrolü
    existing = db.query(models.Flight).filter(models.Flight.id == flight.id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"'{flight.id}' ID'li uçuş zaten mevcut.")

    # Waypoint koordinat validasyonu
    for wp in (flight.waypoints or []):
        validate_coords(wp, f"Durak koordinatı")

    # Tüm rotayı oluştur: origin → waypoints → destination
    all_points = [flight.origin] + (flight.waypoints or []) + [flight.destination]
    origin_wkt = f"POINT({flight.origin[1]} {flight.origin[0]})"
    dest_wkt   = f"POINT({flight.destination[1]} {flight.destination[0]})"
    route_wkt  = create_route_linestring(all_points)

    db_flight = models.Flight(
        id=flight.id,
        origin_name=flight.originName,
        dest_name=flight.destName,
        start_time=flight.startTime,
        waypoints_json=json_module.dumps(flight.waypoints or []),
        origin_geom=WKTElement(origin_wkt, srid=4326),
        dest_geom=WKTElement(dest_wkt, srid=4326),
        route_geom=WKTElement(route_wkt, srid=4326)
    )

    db.add(db_flight)
    db.commit()
    db.refresh(db_flight)

    return schemas.FlightResponse(
        id=db_flight.id,
        originName=db_flight.origin_name,
        destName=db_flight.dest_name,
        startTime=db_flight.start_time,
        waypoints=flight.waypoints or [],
        origin=flight.origin,
        destination=flight.destination,
        position=flight.origin
    )


@app.delete("/api/flights/{flight_id}")
def delete_flight(flight_id: str, db: Session = Depends(get_db)):
    f = db.query(models.Flight).filter(models.Flight.id == flight_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Uçuş bulunamadı")

    # 1. Simülatörü durdurmaya çalış
    try:
        requests.post(f"http://localhost:8001/simulations/{flight_id}/stop", timeout=2)
    except Exception:
        pass # Simülatör ayakta değilse veya uçuş çalışmıyorsa umursama

    # 2. Geçmiş konumları sil
    db.query(models.FlightPosition).filter(models.FlightPosition.flight_id == flight_id).delete()

    # 3. Uçuşu sil
    db.delete(f)
    db.commit()

    return {"status": "ok", "message": f"Uçuş {flight_id} silindi."}


@app.get("/api/flights", response_model=list[schemas.FlightResponse])
def get_flights(db: Session = Depends(get_db)):
    flights = db.query(models.Flight).all()
    result = []
    for f in flights:
        orig_pt = to_shape(f.origin_geom)
        dest_pt = to_shape(f.dest_geom)
        result.append(schemas.FlightResponse(
            id=f.id,
            originName=f.origin_name,
            destName=f.dest_name,
            startTime=f.start_time,
            waypoints=json_module.loads(f.waypoints_json or '[]'),
            origin=[orig_pt.y, orig_pt.x],
            destination=[dest_pt.y, dest_pt.x],
            position=[orig_pt.y, orig_pt.x]
        ))
    return result


@app.post("/api/simulator/positions")
def receive_positions(positions: list[schemas.FlightPositionCreate], db: Session = Depends(get_db)):
    if len(positions) > 100:
        raise HTTPException(status_code=422, detail="Tek seferde en fazla 100 konum gönderilebilir.")

    valid_flight_ids = {f.id for f in db.query(models.Flight.id).all()}

    saved = 0
    for pos in positions:
        # Bilinmeyen uçuş ID'si → sessizce atla (simülatör henüz senkronize olmamış olabilir)
        if pos.flight_id not in valid_flight_ids:
            continue

        # Koordinat ve timestamp doğrulama
        validate_coords(pos.position, f"[{pos.flight_id}] Konum")
        validate_timestamp(pos.timestamp)

        pos_wkt = f"POINT({pos.position[1]} {pos.position[0]})"
        db_pos = models.FlightPosition(
            flight_id=pos.flight_id,
            timestamp=pos.timestamp,
            position_geom=WKTElement(pos_wkt, srid=4326),
            altitude=getattr(pos, 'altitude', 0.0) or 0.0,
            speed_kts=getattr(pos, 'speed_kts', 0.0) or 0.0
        )
        db.add(db_pos)
        saved += 1

    db.commit()
    return {"status": "ok", "saved_count": saved}


@app.delete("/api/flights/{flight_id}/positions")
def delete_flight_positions(flight_id: str, db: Session = Depends(get_db)):
    """Simülasyon yeniden başlatıldığında eski konum geçmişini siler."""
    db.query(models.FlightPosition).filter(models.FlightPosition.flight_id == flight_id).delete()
    db.commit()
    return {"status": "ok"}


@app.get("/api/flights/positions")
def get_flight_positions(time: int = Query(None), flight_id: str = Query(None), db: Session = Depends(get_db)):
    # Eğer time parametresi geldiyse doğrula
    if time is not None:
        validate_timestamp(time)

    flights = db.query(models.Flight).all()
    result = []

    for f in flights:
        query = db.query(models.FlightPosition).filter(models.FlightPosition.flight_id == f.id)

        use_time = time
        if flight_id and flight_id != "ALL" and f.id != flight_id:
            use_time = None

        if use_time is not None:
            pos = query.filter(models.FlightPosition.timestamp <= use_time).order_by(
                models.FlightPosition.timestamp.desc()
            ).first()
        else:
            pos = query.order_by(models.FlightPosition.timestamp.desc()).first()

        if pos:
            pt = to_shape(pos.position_geom)
            result.append({"flight_id": f.id, "position": [pt.y, pt.x]})
        else:
            orig_pt = to_shape(f.origin_geom)
            result.append({"flight_id": f.id, "position": [orig_pt.y, orig_pt.x]})

    return result

@app.get("/api/flights/history")
def get_flight_history(db: Session = Depends(get_db)):
    """Tüm uçuşların kaydedilmiş bütün konum geçmişini döndürür."""
    flights = db.query(models.Flight).all()
    result = {}

    for f in flights:
        positions = db.query(models.FlightPosition)\
                      .filter(models.FlightPosition.flight_id == f.id)\
                      .order_by(models.FlightPosition.timestamp.asc())\
                      .all()

        history = []
        for p in positions:
            pt = to_shape(p.position_geom)
            history.append({
                "t": p.timestamp,
                "p": [pt.y, pt.x],
                "alt": getattr(p, 'altitude', 0.0) or 0.0,
                "spd": getattr(p, 'speed_kts', 0.0) or 0.0
            })

        orig_pt = to_shape(f.origin_geom)
        result[f.id] = {
            "origin": [orig_pt.y, orig_pt.x],
            "history": history
        }

    return result


@app.get("/api/flights/{flight_id}", response_model=schemas.FlightResponse)
def get_flight(flight_id: str, db: Session = Depends(get_db)):
    f = db.query(models.Flight).filter(models.Flight.id == flight_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Uçuş bulunamadı")

    return schemas.FlightResponse(
        id=f.id,
        originName=f.origin_name,
        destName=f.dest_name,
        startTime=f.start_time,
        waypoints=json_module.loads(f.waypoints_json),
        origin=[to_shape(f.origin_geom).y, to_shape(f.origin_geom).x] if f.origin_geom else [0,0],
        destination=[to_shape(f.dest_geom).y, to_shape(f.dest_geom).x] if f.dest_geom else [0,0],
        position=[to_shape(f.origin_geom).y, to_shape(f.origin_geom).x] if f.origin_geom else [0,0]
    )
