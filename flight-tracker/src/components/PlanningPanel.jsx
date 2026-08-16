import React, { useState } from 'react';
import { COMMERCIAL_AIRPORTS, AIRLINES } from '../data/airports';

export default function PlanningPanel({ 
  onClose, 
  onFlightAdd, 
  secimModu, 
  setSecimModu, 
  kalkisLat, setKalkisLat,
  kalkisLng, setKalkisLng,
  varisLat, setVarisLat,
  varisLng, setVarisLng,
  waypoints, setWaypoints 
}) {
  const [flightType, setFlightType] = useState('commercial'); // 'commercial' | 'custom'
  const [selectedAirline, setSelectedAirline] = useState(AIRLINES[0].prefix);
  const [ucusNo, setUcusNo] = useState(String(Math.floor(1000 + Math.random() * 9000)));
  const [customUcusId, setCustomUcusId] = useState('');
  
  const [originAirport, setOriginAirport] = useState(COMMERCIAL_AIRPORTS[0].code);
  const [destAirport, setDestAirport] = useState(COMMERCIAL_AIRPORTS[2].code); // ESB default
  
  const [originName, setOriginName] = useState('');
  const [destName, setDestName] = useState('');
  const [kalkisSaati, setKalkisSaati] = useState('');

  const addWaypoint = () => setWaypoints(prev => [...prev, { lat: '', lng: '' }]);
  const removeWaypoint = (i) => setWaypoints(prev => prev.filter((_, idx) => idx !== i));
  const updateWaypoint = (i, field, val) => setWaypoints(prev =>
    prev.map((wp, idx) => idx === i ? { ...wp, [field]: val } : wp)
  );

  const getCurrentTime = () => {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    return `${hours}:${minutes}`;
  };

  const handleCommercialOriginChange = (code) => {
    setOriginAirport(code);
    const ap = COMMERCIAL_AIRPORTS.find(a => a.code === code);
    if (ap) {
      setKalkisLat(String(ap.lat));
      setKalkisLng(String(ap.lng));
    }
  };

  const handleCommercialDestChange = (code) => {
    setDestAirport(code);
    const ap = COMMERCIAL_AIRPORTS.find(a => a.code === code);
    if (ap) {
      setVarisLat(String(ap.lat));
      setVarisLng(String(ap.lng));
    }
  };

  const ucusEkle = async (e) => {
    e.preventDefault();
    const finalStartTime = kalkisSaati.trim() !== '' ? kalkisSaati : getCurrentTime();

    let id, finalOriginName, finalDestName, finalOrigin, finalDestination;

    if (flightType === 'commercial') {
      const orig = COMMERCIAL_AIRPORTS.find(a => a.code === originAirport) || COMMERCIAL_AIRPORTS[0];
      const dest = COMMERCIAL_AIRPORTS.find(a => a.code === destAirport) || COMMERCIAL_AIRPORTS[2];
      
      id = `${selectedAirline}${ucusNo}`;
      finalOriginName = `${orig.code} - ${orig.city}`;
      finalDestName = `${dest.code} - ${dest.city}`;
      finalOrigin = [orig.lat, orig.lng];
      finalDestination = [dest.lat, dest.lng];
    } else {
      id = customUcusId.trim();
      finalOriginName = originName.trim() || 'Özel Kalkış';
      finalDestName = destName.trim() || 'Özel Varış';
      finalOrigin = [parseFloat(kalkisLat), parseFloat(kalkisLng)];
      finalDestination = [parseFloat(varisLat), parseFloat(varisLng)];
    }

    const yeniUcus = {
      id: id,
      originName: finalOriginName,
      destName: finalDestName,
      origin: finalOrigin,
      destination: finalDestination,
      position: finalOrigin,
      startTime: finalStartTime,
      waypoints: waypoints
        .filter(wp => wp.lat !== '' && wp.lng !== '')
        .map(wp => [parseFloat(wp.lat), parseFloat(wp.lng)]),
    };

    const success = await onFlightAdd(yeniUcus);
    if (success) {
      setCustomUcusId(''); setOriginName(''); setDestName('');
      setKalkisLat(''); setKalkisLng('');
      setVarisLat(''); setVarisLng('');
      setKalkisSaati(''); setWaypoints([]);
      setSecimModu(null);
      setUcusNo(String(Math.floor(1000 + Math.random() * 9000)));
    }
  };

  return (
    <div className="planning-panel" style={{
      maxHeight: '90vh',
      overflowY: 'auto',
      zIndex: 1001
    }}>
      <div className="planning-panel-header">
        <h3>Uçuş Planlama Merkezi</h3>
        <button onClick={() => { onClose(); setSecimModu(null); }}>✕</button>
      </div>

      {/* Uçuş Türü Seçimi (Ticari vs Özel) */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
        <button 
          type="button"
          onClick={() => setFlightType('commercial')}
          style={{
            flex: 1, padding: '8px 4px', borderRadius: 8, border: 'none',
            fontSize: 12, fontWeight: 700, cursor: 'pointer',
            background: flightType === 'commercial' ? '#3b82f6' : '#2d3148',
            color: flightType === 'commercial' ? 'white' : '#94a3b8',
            transition: 'all 0.2s'
          }}>
          🏢 Ticari (Commercial)
        </button>
        <button 
          type="button"
          onClick={() => setFlightType('custom')}
          style={{
            flex: 1, padding: '8px 4px', borderRadius: 8, border: 'none',
            fontSize: 12, fontWeight: 700, cursor: 'pointer',
            background: flightType === 'custom' ? '#8b5cf6' : '#2d3148',
            color: flightType === 'custom' ? 'white' : '#94a3b8',
            transition: 'all 0.2s'
          }}>
          🛩️ Özel / Serbest
        </button>
      </div>
      
      <form onSubmit={ucusEkle}>
        {/* TİCARİ UÇUŞ FORMU */}
        {flightType === 'commercial' ? (
          <>
            <label>Havayolu & Uçuş No</label>
            <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
              <select 
                value={selectedAirline} 
                onChange={(e) => setSelectedAirline(e.target.value)}
                style={{ flex: 1.4, padding: 8, background: '#252836', color: 'white', border: '1px solid #2d3148', borderRadius: 6 }}>
                {AIRLINES.map(al => (
                  <option key={al.prefix} value={al.prefix}>{al.logo} {al.prefix} ({al.name})</option>
                ))}
              </select>
              <input 
                type="text" 
                value={ucusNo} 
                onChange={(e) => setUcusNo(e.target.value)} 
                placeholder="1989" 
                required 
                style={{ flex: 1, padding: 8, background: '#252836', color: 'white', border: '1px solid #2d3148', borderRadius: 6 }} 
              />
            </div>

            <label>Kalkış Havalimanı (Origin IATA)</label>
            <select 
              value={originAirport} 
              onChange={(e) => handleCommercialOriginChange(e.target.value)}
              style={{ width: '100%', padding: 8, background: '#252836', color: 'white', border: '1px solid #2d3148', borderRadius: 6, marginBottom: 10 }}>
              {COMMERCIAL_AIRPORTS.map(ap => (
                <option key={ap.code} value={ap.code}>
                  ✈️ {ap.code} - {ap.name} ({ap.city}, {ap.country})
                </option>
              ))}
            </select>

            <label>Varış Havalimanı (Destination IATA)</label>
            <select 
              value={destAirport} 
              onChange={(e) => handleCommercialDestChange(e.target.value)}
              style={{ width: '100%', padding: 8, background: '#252836', color: 'white', border: '1px solid #2d3148', borderRadius: 6, marginBottom: 10 }}>
              {COMMERCIAL_AIRPORTS.filter(a => a.code !== originAirport).map(ap => (
                <option key={ap.code} value={ap.code}>
                  🎯 {ap.code} - {ap.name} ({ap.city}, {ap.country})
                </option>
              ))}
            </select>
          </>
        ) : (
          /* ÖZEL / SERBEST UÇUŞ FORMU */
          <>
            <label>Uçuş ID</label>
            <input value={customUcusId} onChange={(e) => setCustomUcusId(e.target.value)} required placeholder="Örn: TC-JFK" />

            <label>Kalkış Noktası</label>
            <input value={originName} onChange={(e) => setOriginName(e.target.value)} placeholder="Şehir / Pist Adı" />
            <button type="button" className={`map-btn ${secimModu === 'kalkis' ? 'active' : ''}`} onClick={() => setSecimModu(secimModu === 'kalkis' ? null : 'kalkis')}>
              {secimModu === 'kalkis' ? 'Haritadan Seçiliyor...' : '📍 Haritadan Koordinat Seç'}
            </button>
            <div style={{ display: 'flex', gap: '5px' }}>
              <input placeholder="Lat" value={kalkisLat} onChange={(e) => setKalkisLat(e.target.value)} required />
              <input placeholder="Lng" value={kalkisLng} onChange={(e) => setKalkisLng(e.target.value)} required />
            </div>

            <label>Varış Noktası</label>
            <input value={destName} onChange={(e) => setDestName(e.target.value)} placeholder="Şehir / Pist Adı" />
            <button type="button" className={`map-btn ${secimModu === 'varis' ? 'active' : ''}`} onClick={() => setSecimModu(secimModu === 'varis' ? null : 'varis')}>
              {secimModu === 'varis' ? 'Haritadan Seçiliyor...' : '📍 Haritadan Koordinat Seç'}
            </button>
            <div style={{ display: 'flex', gap: '5px' }}>
              <input placeholder="Lat" value={varisLat} onChange={(e) => setVarisLat(e.target.value)} required />
              <input placeholder="Lng" value={varisLng} onChange={(e) => setVarisLng(e.target.value)} required />
            </div>
          </>
        )}

        <label style={{ marginTop: 8 }}>Kalkış Saati (İsteğe bağlı - boşsa şu an)</label>
        <input type="time" value={kalkisSaati} onChange={(e) => setKalkisSaati(e.target.value)} />

        {/* WAYPOINTLER */}
        {waypoints.map((wp, i) => (
          <div key={i} style={{ borderLeft: '3px solid #3498db', paddingLeft: 8, marginBottom: 8, marginTop: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label style={{ fontSize: 12, color: '#3498db', fontWeight: 600 }}>◆ Durak {i + 1}</label>
              <button type="button" onClick={() => removeWaypoint(i)}
                style={{ background: 'none', border: 'none', color: '#e74c3c', cursor: 'pointer', fontSize: 16 }}>✕</button>
            </div>
            <button type="button" className={`map-btn ${secimModu === `waypoint-${i}` ? 'active' : ''}`}
              onClick={() => setSecimModu(secimModu === `waypoint-${i}` ? null : `waypoint-${i}`)}>
              {secimModu === `waypoint-${i}` ? 'Haritadan Seçiliyor...' : '📍 Haritadan Seç'}
            </button>
            <div style={{ display: 'flex', gap: '5px' }}>
              <input placeholder="Lat" value={wp.lat} onChange={(e) => updateWaypoint(i, 'lat', e.target.value)} />
              <input placeholder="Lng" value={wp.lng} onChange={(e) => updateWaypoint(i, 'lng', e.target.value)} />
            </div>
          </div>
        ))}

        <button type="button" onClick={addWaypoint}
          style={{ background: '#2980b9', color: 'white', border: 'none', padding: '7px', borderRadius: 6, cursor: 'pointer', fontSize: 12, marginTop: 8, marginBottom: 12, width: '100%' }}>
          + Ara Durak (Waypoint) Ekle
        </button>

        <button type="submit" className="submit-btn" style={{
          background: 'linear-gradient(135deg, #22c55e, #16a34a)',
          color: 'white', fontWeight: 800, padding: 12, borderRadius: 8, width: '100%', border: 'none', cursor: 'pointer'
        }}>
          🚀 Uçuş Planını Kaydet & Başlat
        </button>
      </form>
    </div>
  );
}
