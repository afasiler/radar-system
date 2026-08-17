import math

def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    d = math.pi / 180
    dlat = (lat2 - lat1) * d
    dlon = (lon2 - lon1) * d
    a = math.sin(dlat/2)**2 + math.cos(lat1*d)*math.cos(lat2*d)*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0, 1-a)))

def _move_towards(lat1, lon1, lat2, lon2, dist_km):
    R = 6371.0
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

    # Calculate bearing
    y = math.sin(lon2_rad - lon1_rad) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(lon2_rad - lon1_rad)
    brng = math.atan2(y, x)

    # Calculate destination
    d_angular = dist_km / R
    lat3_rad = math.asin(math.sin(lat1_rad) * math.cos(d_angular) +
                         math.cos(lat1_rad) * math.sin(d_angular) * math.cos(brng))
    lon3_rad = lon1_rad + math.atan2(math.sin(brng) * math.sin(d_angular) * math.cos(lat1_rad),
                                     math.cos(d_angular) - math.sin(lat1_rad) * math.sin(lat3_rad))

    return math.degrees(lat3_rad), math.degrees(lon3_rad)

p1 = [41.0082, 28.9784] # IST
p2 = [36.8969, 30.7133] # AYT

d = _haversine_km(p1[0], p1[1], p2[0], p2[1])
print(f"Total distance: {d} km")

p_curr = p1
steps = 0
while _haversine_km(p_curr[0], p_curr[1], p2[0], p2[1]) > 0.5:
    p_curr = _move_towards(p_curr[0], p_curr[1], p2[0], p2[1], 0.5)
    steps += 1

print(f"Reached AYT in {steps} steps. Final pos: {p_curr}")
