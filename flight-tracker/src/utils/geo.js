export function calculateBearing(startLat, startLng, destLat, destLng) {
  const toRad = (deg) => (deg * Math.PI) / 180;
  const toDeg = (rad) => (rad * 180) / Math.PI;
  
  const startLatRad = toRad(startLat);
  const startLngRad = toRad(startLng);
  const destLatRad = toRad(destLat);
  const destLngRad = toRad(destLng);

  const y = Math.sin(destLngRad - startLngRad) * Math.cos(destLatRad);
  const x = Math.cos(startLatRad) * Math.sin(destLatRad) -
            Math.sin(startLatRad) * Math.cos(destLatRad) * Math.cos(destLngRad - startLngRad);
  
  let brng = toDeg(Math.atan2(y, x));
  return (brng + 360) % 360;
}

export function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371.0;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
}

export function greatCirclePoints(lat1_deg, lon1_deg, lat2_deg, lon2_deg, n_steps) {
  const toRad = deg => deg * Math.PI / 180;
  const toDeg = rad => rad * 180 / Math.PI;
  
  const lat1 = toRad(lat1_deg), lon1 = toRad(lon1_deg);
  const lat2 = toRad(lat2_deg), lon2 = toRad(lon2_deg);
  
  const dlat = lat2 - lat1, dlon = lon2 - lon1;
  const a = Math.sin(dlat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dlon / 2) ** 2;
  const d = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
  
  if (d < 1e-10) return Array(n_steps + 1).fill([lat1_deg, lon1_deg]);
  
  const points = [];
  for (let i = 0; i <= n_steps; i++) {
    const f = i / n_steps;
    const A = Math.sin((1 - f) * d) / Math.sin(d);
    const B = Math.sin(f * d) / Math.sin(d);
    const x = A * Math.cos(lat1) * Math.cos(lon1) + B * Math.cos(lat2) * Math.cos(lon2);
    const y = A * Math.cos(lat1) * Math.sin(lon1) + B * Math.cos(lat2) * Math.sin(lon2);
    const z = A * Math.sin(lat1) + B * Math.sin(lat2);
    const lat_out = Math.atan2(z, Math.sqrt(x ** 2 + y ** 2));
    const lon_out = Math.atan2(y, x);
    points.push([toDeg(lat_out), toDeg(lon_out)]);
  }
  return points;
}

export function interpolateSLERP(lat1_deg, lon1_deg, lat2_deg, lon2_deg, f) {
  const toRad = deg => deg * Math.PI / 180;
  const toDeg = rad => rad * 180 / Math.PI;
  
  const lat1 = toRad(lat1_deg), lon1 = toRad(lon1_deg);
  const lat2 = toRad(lat2_deg), lon2 = toRad(lon2_deg);
  
  const dlat = lat2 - lat1, dlon = lon2 - lon1;
  const a = Math.sin(dlat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dlon / 2) ** 2;
  const d = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
  
  if (d < 1e-10) return [lat1_deg, lon1_deg];
  
  const A = Math.sin((1 - f) * d) / Math.sin(d);
  const B = Math.sin(f * d) / Math.sin(d);
  const x = A * Math.cos(lat1) * Math.cos(lon1) + B * Math.cos(lat2) * Math.cos(lon2);
  const y = A * Math.cos(lat1) * Math.sin(lon1) + B * Math.cos(lat2) * Math.sin(lon2);
  const z = A * Math.sin(lat1) + B * Math.sin(lat2);
  return [toDeg(Math.atan2(z, Math.sqrt(x ** 2 + y ** 2))), toDeg(Math.atan2(y, x))];
}

export function coordDist(a, b) {
  return Math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)
}
