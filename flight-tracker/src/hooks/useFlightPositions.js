import { useState, useEffect } from 'react';
import { interpolateSLERP, calculateBearing, coordDist } from '../utils/geo';

export default function useFlightPositions(flights, flightHistory, sliderValue, sliderTargetId) {
  const [positions, setPositions] = useState({});

  useEffect(() => {
    const newPositions = {};

    flights.forEach(f => {
      const timeToUse = (sliderTargetId !== 'ALL' && f.id !== sliderTargetId)
                        ? ((Date.now() / 1000) - 4)
                        : sliderValue;

      const fData = flightHistory[f.id];
      const firstTarget = (f.waypoints && f.waypoints.length > 0) ? f.waypoints[0] : f.destination;
      let initialBearing = 0;
      if (f.origin && firstTarget) {
         initialBearing = calculateBearing(f.origin[0], f.origin[1], firstTarget[0], firstTarget[1]);
      }

      if (!fData || !fData.history || fData.history.length === 0) {
        newPositions[f.id] = { position: f.origin, bearing: initialBearing, altitude: 0, speed_kts: 0, status: 'bekliyor' };
        return;
      }

      const hist = fData.history;

      // Before takeoff
      if (timeToUse <= hist[0].t) {
        newPositions[f.id] = { position: hist[0].p, bearing: initialBearing, altitude: 0, speed_kts: 0, status: 'bekliyor' };
        return;
      }

      // Flight finished or waiting for next telemetry (live mode latency)
      if (timeToUse >= hist[hist.length - 1].t) {
        const last = hist[hist.length - 1];

        let finalBearing = 0;
        // Find the last actual movement to determine bearing
        for (let i = hist.length - 2; i >= 0; i--) {
           if (hist[i].p[0] !== last.p[0] || hist[i].p[1] !== last.p[1]) {
               finalBearing = calculateBearing(hist[i].p[0], hist[i].p[1], last.p[0], last.p[1]);
               break;
           }
        }

        // If no past movement found (e.g. still at origin), look towards the first target
        if (finalBearing === 0) {
            finalBearing = initialBearing;
        }

        // Calculate if actually landed based on geographic distance
        const isLanded = (coordDist(last.p, f.destination) < 0.02);

        newPositions[f.id] = { 
          position: last.p, 
          bearing: finalBearing, 
          altitude: isLanded ? 0 : Math.round(last.alt ?? 0),
          speed_kts: isLanded ? 0 : Math.round(last.spd ?? 0),
          status: isLanded ? 'indi' : 'ucusta' 
        };
        return;
      }

      // Interpolate during flight
      let pt1, pt2;
      let index = 0;
      for (let i = 0; i < hist.length - 1; i++) {
        if (timeToUse >= hist[i].t && timeToUse < hist[i+1].t) {
          pt1 = hist[i];
          pt2 = hist[i+1];
          index = i;
          break;
        }
      }

      if (pt1 && pt2) {
        const timeDiff = pt2.t - pt1.t;
        const f_ratio = timeDiff > 0 ? (timeToUse - pt1.t) / timeDiff : 0;

        let exactPos;
        let computedBearing = 0;

        const alt1 = pt1.alt ?? 0;
        const alt2 = pt2.alt ?? 0;
        const exactAlt = Math.round(alt1 + (alt2 - alt1) * f_ratio);

        const spd1 = pt1.spd ?? 0;
        const spd2 = pt2.spd ?? 0;
        const exactSpd = Math.round(spd1 + (spd2 - spd1) * f_ratio);

        // Waiting at origin or waypoint
        if (pt1.p[0] === pt2.p[0] && pt1.p[1] === pt2.p[1]) {
           exactPos = pt1.p;

           let searchIdx = index + 1;
           let nextP = hist[searchIdx].p;
           while (searchIdx < hist.length - 1 && nextP[0] === exactPos[0] && nextP[1] === exactPos[1]) {
              searchIdx++;
              nextP = hist[searchIdx].p;
           }

           if (nextP[0] !== exactPos[0] || nextP[1] !== exactPos[1]) {
              computedBearing = calculateBearing(exactPos[0], exactPos[1], nextP[0], nextP[1]);
           } else {
              let backtrackIdx = index - 1;
              while (backtrackIdx >= 0 && hist[backtrackIdx].p[0] === exactPos[0] && hist[backtrackIdx].p[1] === exactPos[1]) {
                 backtrackIdx--;
              }
              if (backtrackIdx >= 0) {
                 const prevP = hist[backtrackIdx].p;
                 computedBearing = calculateBearing(prevP[0], prevP[1], exactPos[0], exactPos[1]);
              } else {
                 computedBearing = initialBearing;
              }
           }
        } else {
           // Moving
           exactPos = interpolateSLERP(pt1.p[0], pt1.p[1], pt2.p[0], pt2.p[1], f_ratio);
           computedBearing = calculateBearing(pt1.p[0], pt1.p[1], pt2.p[0], pt2.p[1]);
        }

        newPositions[f.id] = { 
          position: exactPos, 
          bearing: computedBearing, 
          altitude: exactAlt,
          speed_kts: exactSpd,
          status: 'ucusta' 
        };
      } else {
         newPositions[f.id] = { position: f.origin, bearing: 0, altitude: 0, speed_kts: 0, status: 'bekliyor' };
      }
    });

    setPositions(newPositions);
  }, [sliderValue, flightHistory, flights, sliderTargetId]);

  return positions;
}
