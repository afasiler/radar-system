"""
great_circle.py — Coğrafi Yay (Great Circle) Hesaplama

KARAR: Düz lat/lng interpolasyonu yerine great circle kullanıyoruz.
Gerekçe: Düz interpolasyon haritada düz görünse de yeryüzünde
daha uzun bir yol demektir. Hocanın "coğrafi düz ile geometrik
düzün farkını dikkate al" uyarısı bunu işaret ediyor.

Yöntem: Spherical Linear Interpolation (SLERP)
  Kaynak: https://en.wikipedia.org/wiki/Great-circle_navigation
"""
import math


def great_circle_points(lat1_deg: float, lon1_deg: float,
                        lat2_deg: float, lon2_deg: float,
                        n_steps: int) -> list[list[float]]:
    """
    İki koordinat arasında great circle üzerinde n_steps+1 nokta döndürür.
    Her nokta [lat, lng] formatında.
    """
    lat1 = math.radians(lat1_deg)
    lon1 = math.radians(lon1_deg)
    lat2 = math.radians(lat2_deg)
    lon2 = math.radians(lon2_deg)

    # İki nokta arasındaki açısal mesafe (radyan)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    d = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))

    # Aynı nokta — sonsuz döngüden koru
    if d < 1e-10:
        return [[lat1_deg, lon1_deg]] * (n_steps + 1)

    points = []
    for i in range(n_steps + 1):
        f = i / n_steps  # 0.0 → 1.0 arası kesir

        # SLERP formülü
        A = math.sin((1 - f) * d) / math.sin(d)
        B = math.sin(f * d) / math.sin(d)

        x = A * math.cos(lat1) * math.cos(lon1) + B * math.cos(lat2) * math.cos(lon2)
        y = A * math.cos(lat1) * math.sin(lon1) + B * math.cos(lat2) * math.sin(lon2)
        z = A * math.sin(lat1) + B * math.sin(lat2)

        lat_out = math.atan2(z, math.sqrt(x ** 2 + y ** 2))
        lon_out = math.atan2(y, x)

        points.append([math.degrees(lat_out), math.degrees(lon_out)])

    return points


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """İki koordinat arasındaki kuş uçuşu mesafesi (km)."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))
