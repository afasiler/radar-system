from pydantic import BaseModel
from typing import List, Optional

class FlightCreate(BaseModel):
    id: str
    originName: str
    destName: str
    origin: List[float]
    destination: List[float]
    startTime: str
    waypoints: Optional[List[List[float]]] = []   # [[lat,lng], ...]

class FlightResponse(BaseModel):
    id: str
    originName: str
    destName: str
    origin: List[float]
    destination: List[float]
    startTime: str
    waypoints: Optional[List[List[float]]] = []
    position: Optional[List[float]] = None

# Simülatörden gelecek olan veri şeması
class FlightPositionCreate(BaseModel):
    flight_id: str
    timestamp: float
    position: List[float] # [Lat, Lng]
    altitude: Optional[float] = 0.0 # feet
    speed_kts: Optional[float] = 0.0 # knots

class FlightPositionResponse(BaseModel):
    flight_id: str
    timestamp: float
    position: List[float]
    altitude: Optional[float] = 0.0
    speed_kts: Optional[float] = 0.0

    class Config:
        orm_mode = True
