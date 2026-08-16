from sqlalchemy import Column, String, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from database import Base

class Flight(Base):
    __tablename__ = "flights"

    id = Column(String, primary_key=True, index=True)
    origin_name = Column(String)
    dest_name = Column(String)

    # 4326: WGS 84 Koordinat sistemi
    origin_geom = Column(Geometry(geometry_type='POINT', srid=4326))
    dest_geom = Column(Geometry(geometry_type='POINT', srid=4326))
    route_geom = Column(Geometry(geometry_type='LINESTRING', srid=4326))

    start_time = Column(String) # "HH:MM"
    waypoints_json = Column(String, default='[]') # [[lat,lng], ...] JSON string

    # One-to-Many ilişkisi (Bir uçuşun birden fazla konum geçmişi olur)
    positions = relationship("FlightPosition", back_populates="flight")

class FlightPosition(Base):
    __tablename__ = "flight_positions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    flight_id = Column(String, ForeignKey("flights.id"))
    timestamp = Column(Float) # Unix Timestamp (Saniye cinsinden kesirli zaman)
    position_geom = Column(Geometry(geometry_type='POINT', srid=4326))
    altitude = Column(Float, default=0.0) # İrtifa (feet)
    speed_kts = Column(Float, default=0.0) # Hız (knots)

    flight = relationship("Flight", back_populates="positions")
