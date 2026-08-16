import React, { useMemo } from 'react';
import { Marker, Polyline } from 'react-leaflet';
import { originDot, destDot, waypointDot, createPlaneIcon } from './Icons';
import { coordDist, greatCirclePoints } from '../utils/geo';

export default function FlightLayer({ flight, onSelect, currentPosition }) {
  const activePosition = currentPosition?.position || flight.origin;
  const activeBearing = currentPosition?.bearing ?? 0;
  const waypoints = flight.waypoints || [];

  // Calculate status
  const distToOrigin = coordDist(activePosition, flight.origin);
  const distToDest = coordDist(activePosition, flight.destination);
  let status = 'ucusta';
  if (distToOrigin < 0.01) status = 'bekliyor';
  else if (distToDest < 0.01) status = 'indi';

  // Round bearing to nearest degree — icon only recreates when bearing changes by >=1 degree
  const roundedBearing = Math.round(activeBearing);

  const planeIcon = useMemo(
    () => createPlaneIcon(roundedBearing, status),
    [roundedBearing, status]
  );

  // Memoize the full route so it doesn't recalculate every frame
  const fullRoute = useMemo(() => {
    const allPoints = [flight.origin, ...waypoints, flight.destination];
    const route = [];
    for (let i = 0; i < allPoints.length - 1; i++) {
      const seg = greatCirclePoints(allPoints[i][0], allPoints[i][1], allPoints[i+1][0], allPoints[i+1][1], 50);
      route.push(...(i < allPoints.length - 2 ? seg.slice(0, -1) : seg));
    }
    return route;
  }, [flight.origin, flight.destination, waypoints]);

  const { pastRoute, futureRoute } = useMemo(() => {
    if (status === 'bekliyor') return { pastRoute: [], futureRoute: fullRoute };
    if (status === 'indi') return { pastRoute: fullRoute, futureRoute: [] };

    let closestIdx = 0;
    let minDist = Infinity;
    for (let i = 0; i < fullRoute.length; i++) {
      const d = coordDist(activePosition, fullRoute[i]);
      if (d < minDist) {
        minDist = d;
        closestIdx = i;
      }
    }

    // Smooth transition exactly at activePosition
    const past = [...fullRoute.slice(0, closestIdx), activePosition];
    const future = [activePosition, ...fullRoute.slice(closestIdx + 1)];

    return { pastRoute: past, futureRoute: future };
  }, [fullRoute, activePosition, status]);

  return (
    <>
      {pastRoute.length > 0 && (
        <Polyline positions={pastRoute} pathOptions={{ color: '#f39c12', weight: 2, opacity: 0.8 }} />
      )}
      {futureRoute.length > 0 && (
        <Polyline positions={futureRoute} pathOptions={{ color: '#3498db', weight: 2, dashArray: '6 8', opacity: 0.5 }} />
      )}

      <Marker position={flight.origin} icon={originDot} />
      {waypoints.map((wp, i) => (
        <Marker key={i} position={wp} icon={waypointDot} />
      ))}
      <Marker position={flight.destination} icon={destDot} />
      <Marker
        position={activePosition}
        icon={planeIcon}
        eventHandlers={{ click: () => onSelect({ ...flight, status }) }}
      />
    </>
  );
}
