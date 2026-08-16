import React from 'react';

export default function AltitudeChart({ currentAltitude = 0, currentSpeed = 0, status = 'ucusta' }) {
  // 0% -> 100% rota boyunca tipik uçuş profil eğrisi noktaları (SVG koordinatları)
  // Genişlik: 280, Yükseklik: 90
  const width = 280;
  const height = 80;
  const padding = 10;

  // Max irtifa 40,000 ft
  const maxAlt = 40000;
  const altToY = (alt) => height - padding - ((alt / maxAlt) * (height - 2 * padding));

  // Örnek ideal profil yol çizgisi
  // 0% -> 0 ft, 20% -> 36,000 ft, 80% -> 36,000 ft, 100% -> 0 ft
  const p0 = `${padding},${altToY(0)}`;
  const p1 = `${padding + (width - 2 * padding) * 0.2},${altToY(36000)}`;
  const p2 = `${padding + (width - 2 * padding) * 0.8},${altToY(36000)}`;
  const p3 = `${width - padding},${altToY(0)}`;

  const pathD = `M ${p0} Q ${padding + 25},${altToY(25000)} ${p1} L ${p2} Q ${width - padding - 25},${altToY(25000)} ${p3}`;
  const areaD = `${pathD} L ${width - padding},${height - padding} L ${padding},${height - padding} Z`;

  // Mevcut uçağın konumu
  let progressRatio = 0.5;
  if (status === 'bekliyor') progressRatio = 0.02;
  else if (status === 'indi') progressRatio = 0.98;
  else if (currentAltitude < 30000 && currentSpeed < 380) progressRatio = Math.max(0.05, (currentAltitude / 36000) * 0.2);
  else if (currentAltitude > 30000) progressRatio = 0.5;
  else progressRatio = 0.85;

  const currentX = padding + (width - 2 * padding) * progressRatio;
  const currentY = altToY(currentAltitude);

  return (
    <div style={{
      background: 'rgba(0, 0, 0, 0.4)',
      borderRadius: 12,
      padding: '12px',
      border: '1px solid rgba(255, 255, 255, 0.08)',
      marginTop: 12
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase', fontWeight: 700, letterSpacing: 0.5 }}>
          📊 Dikey İrtifa Profili (VNAV HUD)
        </span>
        <span style={{ fontSize: 11, color: '#38bdf8', fontWeight: 700 }}>
          {currentAltitude.toLocaleString('tr-TR')} ft
        </span>
      </div>

      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} style={{ overflow: 'visible' }}>
        <defs>
          <linearGradient id="altGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* FL360 Referans Çizgisi */}
        <line
          x1={padding}
          y1={altToY(36000)}
          x2={width - padding}
          y2={altToY(36000)}
          stroke="rgba(255,255,255,0.15)"
          strokeDasharray="3,3"
        />
        <text x={width - padding + 2} y={altToY(36000) + 3} fill="#64748b" fontSize="8" fontFamily="sans-serif">
          FL360
        </text>

        {/* Taban Çizgisi (0 ft) */}
        <line
          x1={padding}
          y1={height - padding}
          x2={width - padding}
          y2={height - padding}
          stroke="rgba(255,255,255,0.12)"
        />

        {/* Profil Alanı & Çizgisi */}
        <path d={areaD} fill="url(#altGrad)" />
        <path d={pathD} fill="none" stroke="#38bdf8" strokeWidth="2" strokeLinecap="round" />

        {/* Anlık Konum Çubuğu */}
        <line
          x1={currentX}
          y1={padding}
          x2={currentX}
          y2={height - padding}
          stroke="#f59e0b"
          strokeWidth="1.5"
          strokeDasharray="2,2"
        />

        {/* Anlık Uçak Noktası (Glow Noktası) */}
        <circle cx={currentX} cy={currentY} r="5" fill="#f59e0b" stroke="#ffffff" strokeWidth="1.5">
          <animate attributeName="r" values="4;6;4" dur="1.5s" repeatCount="indefinite" />
        </circle>
      </svg>

      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#64748b', marginTop: 4 }}>
        <span>🛫 Kalkış (TOC)</span>
        <span>✈️ Seyir (CRZ)</span>
        <span>🛬 Alçalış (TOD)</span>
      </div>
    </div>
  );
}
