import React from 'react';
import AltitudeChart from './AltitudeChart';

const STATUS_LABELS = {
  bekliyor: { icon: '⏳', text: 'Kalkış Bekliyor', color: '#f39c12', bg: 'rgba(243, 156, 18, 0.15)' },
  tirmanis: { icon: '🛫', text: 'Tırmanışta',       color: '#3498db', bg: 'rgba(52, 152, 219, 0.15)' },
  seyir:    { icon: '✈️', text: 'Düz Uçuş (FL360)', color: '#2ecc71', bg: 'rgba(46, 204, 113, 0.15)' },
  alcalis:  { icon: '🛬', text: 'Alçalıyor',       color: '#9b59b6', bg: 'rgba(155, 89, 182, 0.15)' },
  indi:     { icon: '✅', text: 'Varışa İndi',      color: '#95a5a6', bg: 'rgba(149, 165, 166, 0.15)' },
};

function getCompassDirection(deg) {
  const directions = ['K (N)', 'KD (NE)', 'D (E)', 'GD (SE)', 'G (S)', 'GB (SW)', 'B (W)', 'KB (NW)'];
  const index = Math.round(((deg % 360) / 45)) % 8;
  return directions[index];
}

export default function InfoPanel({ flight, onClose, onDelete }) {
  const altitude = flight.altitude ?? 0;
  const speedKts = flight.speed_kts ?? 0;
  const speedKmh = Math.round(speedKts * 1.852);
  const bearing = Math.round(flight.bearing ?? 0);

  let flightPhase = 'bekliyor';
  if (flight.status === 'indi') {
    flightPhase = 'indi';
  } else if (flight.status === 'bekliyor') {
    flightPhase = 'bekliyor';
  } else if (altitude < 25000 && speedKts < 400 && speedKts > 50) {
    flightPhase = 'tirmanis';
  } else if (altitude > 28000) {
    flightPhase = 'seyir';
  } else {
    flightPhase = 'alcalis';
  }

  const statusInfo = STATUS_LABELS[flightPhase] || STATUS_LABELS['seyir'];
  const altPercent = Math.min(100, Math.round((altitude / 38000) * 100));

  return (
    <div style={{
      position: 'absolute', top: 20, right: 20, zIndex: 1000,
      background: 'rgba(17, 21, 33, 0.94)',
      backdropFilter: 'blur(18px)',
      border: '1px solid rgba(255, 255, 255, 0.12)',
      borderRadius: 16,
      padding: '18px 20px',
      boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
      width: 320,
      color: '#f8fafc',
      fontFamily: 'Inter, system-ui, sans-serif'
    }}>
      {/* Üst Başlık & Kontroller */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 22 }}>✈️</span>
          <div>
            <div style={{ fontWeight: 800, fontSize: 18, letterSpacing: 0.5 }}>{flight.id}</div>
            <div style={{ fontSize: 11, color: '#94a3b8' }}>Canlı Kokpit & Telemetri</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button 
            onClick={() => { if(window.confirm(`${flight.id} uçuşunu silmek istediğinize emin misiniz?`)) onDelete(flight.id); }} 
            style={{
              background: 'rgba(239, 68, 68, 0.2)',
              color: '#ef4444',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              borderRadius: 8,
              padding: '5px 10px',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}>
            Sil
          </button>
          <button 
            onClick={onClose} 
            style={{
              background: 'rgba(255, 255, 255, 0.08)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              borderRadius: 8,
              width: 28,
              height: 28,
              color: '#94a3b8',
              fontSize: 14,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
            ✕
          </button>
        </div>
      </div>

      {/* Faz / Durum Rozeti */}
      <div style={{
        background: statusInfo.bg,
        border: `1px solid ${statusInfo.color}`,
        borderRadius: 10,
        padding: '7px 12px',
        marginBottom: 12,
        fontWeight: 700,
        color: statusInfo.color,
        fontSize: 13,
        display: 'flex',
        alignItems: 'center',
        gap: 8
      }}>
        <span>{statusInfo.icon}</span>
        <span>{statusInfo.text}</span>
      </div>

      {/* Rota Özeti */}
      <div style={{
        background: 'rgba(255, 255, 255, 0.04)',
        borderRadius: 12,
        padding: '10px 14px',
        marginBottom: 12,
        display: 'flex',
        flexDirection: 'column',
        gap: 6
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Kalkış</div>
            <div style={{ fontWeight: 700, fontSize: 13, color: '#22c55e' }}>🟢 {flight.originName}</div>
          </div>
          <div style={{ color: '#64748b', fontSize: 16 }}>➔</div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Varış</div>
            <div style={{ fontWeight: 700, fontSize: 13, color: '#ef4444' }}>🔴 {flight.destName}</div>
          </div>
        </div>
        <div style={{ fontSize: 11, color: '#94a3b8', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 6 }}>
          🕒 Planlanan Kalkış: <strong>{flight.startTime}</strong>
        </div>
      </div>

      {/* Uçuş Göstergeleri (Avionics Telemetry Grid) */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        
        {/* İrtifa (Altitude) */}
        <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 10, padding: '8px 10px', border: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ fontSize: 9, color: '#94a3b8', textTransform: 'uppercase', fontWeight: 700, marginBottom: 2 }}>
            🏔️ İrtifa (ALT)
          </div>
          <div style={{ fontSize: 15, fontWeight: 800, color: '#38bdf8' }}>
            {altitude.toLocaleString('tr-TR')} <span style={{ fontSize: 10, fontWeight: 500 }}>ft</span>
          </div>
          <div style={{ width: '100%', height: 3, background: 'rgba(255,255,255,0.1)', borderRadius: 4, marginTop: 4, overflow: 'hidden' }}>
            <div style={{ width: `${altPercent}%`, height: '100%', background: 'linear-gradient(90deg, #38bdf8, #818cf8)', transition: 'width 0.5s ease' }} />
          </div>
        </div>

        {/* Yer Hızı (Speed) */}
        <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 10, padding: '8px 10px', border: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ fontSize: 9, color: '#94a3b8', textTransform: 'uppercase', fontWeight: 700, marginBottom: 2 }}>
            ⚡ Yer Hızı (SPD)
          </div>
          <div style={{ fontSize: 15, fontWeight: 800, color: '#f59e0b' }}>
            {speedKts} <span style={{ fontSize: 10, fontWeight: 500 }}>kts</span>
          </div>
          <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>
            ≈ {speedKmh} km/h
          </div>
        </div>

        {/* Yönelim (Heading / Bearing) */}
        <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 10, padding: '8px 10px', border: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ fontSize: 9, color: '#94a3b8', textTransform: 'uppercase', fontWeight: 700, marginBottom: 2 }}>
            🧭 Yön (HDG)
          </div>
          <div style={{ fontSize: 14, fontWeight: 800, color: '#a78bfa' }}>
            {bearing}°
          </div>
          <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>
            {getCompassDirection(bearing)}
          </div>
        </div>

        {/* Uçuş Seviyesi (Flight Level) */}
        <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 10, padding: '8px 10px', border: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ fontSize: 9, color: '#94a3b8', textTransform: 'uppercase', fontWeight: 700, marginBottom: 2 }}>
            📡 Seviye (FL)
          </div>
          <div style={{ fontSize: 14, fontWeight: 800, color: '#34d399' }}>
            FL{Math.round(altitude / 100).toString().padStart(3, '0')}
          </div>
          <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>
            {altitude > 10000 ? 'RVSM Sahası' : 'Terminal Sahası'}
          </div>
        </div>

      </div>

      {/* Dikey İrtifa Profil Grafiği (Altitude Profile HUD) */}
      <AltitudeChart 
        currentAltitude={altitude} 
        currentSpeed={speedKts} 
        status={flight.status} 
      />
    </div>
  );
}
