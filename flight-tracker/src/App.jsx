import React, { useState, useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, useMapEvents } from 'react-leaflet';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
import 'leaflet/dist/leaflet.css';

import FlightLayer from './components/FlightLayer';
import InfoPanel from './components/InfoPanel';
import PlanningPanel from './components/PlanningPanel';
import useFlightPositions from './hooks/useFlightPositions';

const MAP_THEMES = {
  dark: {
    id: 'dark',
    name: 'Gece Modu',
    icon: '🌑',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; CartoDB Dark Matter'
  },
  satellite: {
    id: 'satellite',
    name: 'Uydu',
    icon: '🛰️',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri World Imagery'
  },
  standard: {
    id: 'standard',
    name: 'Standart',
    icon: '🗺️',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap'
  },
  aviation: {
    id: 'aviation',
    name: 'Havacılık / Topo',
    icon: '🧭',
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenTopoMap'
  }
};

function MapClickHandler({ secimModu, onKoordinatSec }) {
  useMapEvents({
    click(event) {
      if (secimModu) {
        onKoordinatSec(event.latlng.lat, event.latlng.lng);
      }
    }
  });
  return null;
}

export default function App() {
  const [selectedFlight, setSelectedFlight] = useState(null);
  const [flights, setFlights] = useState([]);
  const [flightHistory, setFlightHistory] = useState({});
  const [historyLoaded, setHistoryLoaded] = useState(false);
  
  // Harita Teması State'i (Koyu, Uydu, Standart, Havacılık)
  const [activeTheme, setActiveTheme] = useState('standard');

  // Canlı Hava Durumu / Yağış Radarı State'leri
  const [showRadar, setShowRadar] = useState(false);
  const [radarOpacity, setRadarOpacity] = useState(0.7);
  const [radarTilePath, setRadarTilePath] = useState(null);

  // Slider (Zaman Makinesi) State'leri
  const getTodayAt = (h, m) => {
    const d = new Date(); d.setHours(h, m, 0, 0); return Math.floor(d.getTime() / 1000);
  };
  const [sliderMin] = useState(() => getTodayAt(0, 0));
  const [sliderMax, setSliderMax] = useState(Date.now() / 1000);
  const [sliderValue, setSliderValue] = useState(Date.now() / 1000);
  const [isLive, setIsLive] = useState(true);
  const [sliderTargetId, setSliderTargetId] = useState('ALL');

  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [secimModu, setSecimModu] = useState(null);

  // Form State'leri (PlanningPanel'e prop olarak geçilecek)
  const [kalkisLat, setKalkisLat] = useState('41.2753');
  const [kalkisLng, setKalkisLng] = useState('28.7519');
  const [varisLat, setVarisLat] = useState('40.1281');
  const [varisLng, setVarisLng] = useState('32.9951');
  const [waypoints, setWaypoints] = useState([]);

  // RainViewer Canlı Radar Harita Katmanı Verisini Çekme
  useEffect(() => {
    fetch('https://api.rainviewer.com/public/weather-maps.json')
      .then(res => res.json())
      .then(data => {
        if (data && data.radar && data.radar.past && data.radar.past.length > 0) {
          const latest = data.radar.past[data.radar.past.length - 1];
          setRadarTilePath(latest.path);
        }
      })
      .catch(err => console.log('Radar API çevrimdışı:', err));
  }, []);

  // Veri Çekme (Planlanan Uçuşlar)
  useEffect(() => {
    fetch('http://localhost:8000/api/flights')
      .then(res => res.json())
      .then(data => setFlights(data))
      .catch(err => console.error("Sunucudan uçuşlar alınamadı:", err));
  }, []);

  // Geçmiş (History) Verisini Çekme (Her 2 saniyede bir)
  useEffect(() => {
    const fetchHistory = () => {
      fetch('http://localhost:8000/api/flights/history')
        .then(res => res.json())
        .then(data => {
            setFlightHistory(data);
            setHistoryLoaded(true);
        })
        .catch(err => console.error("Geçmiş veriler alınamadı:", err));
    };
    
    fetchHistory();
    const interval = setInterval(fetchHistory, 2000);
    return () => clearInterval(interval);
  }, []);

  // Zaman Akışı (Saniyede 60 FPS slider güncellemesi)
  useEffect(() => {
    let lastTime = Date.now();
    let animationFrameId;

    const loop = () => {
      const now = Date.now();
      const deltaSec = (now - lastTime) / 1000;
      lastTime = now;
      
      setSliderMax(now / 1000);
      
      if (isLive) {
        setSliderValue((now / 1000) - 4);
      } else {
        setSliderValue(prev => prev + deltaSec);
      }
      
      animationFrameId = requestAnimationFrame(loop);
    };
    
    animationFrameId = requestAnimationFrame(loop);
    
    return () => cancelAnimationFrame(animationFrameId);
  }, [isLive]);

  // Tüm uçakların anlık pozisyon, irtifa, hız ve açısını hesaplama
  const positions = useFlightPositions(flights, flightHistory, sliderValue, sliderTargetId);

  // Uçuş Ekleme Handler'ı
  const handleFlightAdd = async (yeniUcus) => {
    try {
      const response = await fetch('http://localhost:8000/api/flights', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(yeniUcus)
      });

      if (response.ok) {
        const savedFlight = await response.json();
        setFlights([...flights, savedFlight]);
        
        fetch(`http://localhost:8001/simulations/${savedFlight.id}/start?speed=50`, { method: 'POST' })
          .catch(err => console.log('Simülatör otomatik başlatılamadı:', err));
          
        setIsPanelOpen(false);
        return true;
      } else {
        const errorData = await response.json();
        alert('Hata: ' + errorData.detail);
        return false;
      }
    } catch (err) {
      console.error(err);
      alert("Sunucuya ulaşılamadı. Backend açık mı?");
      return false;
    }
  };

  const handleHaritadanKoordinatGirdi = (lat, lng) => {
    const kisaLat = lat.toFixed(4);
    const kisaLng = lng.toFixed(4);
    
    if (secimModu === 'kalkis') {
      setKalkisLat(kisaLat); setKalkisLng(kisaLng);
    } else if (secimModu === 'varis') {
      setVarisLat(kisaLat); setVarisLng(kisaLng);
    } else if (secimModu?.startsWith('waypoint-')) {
      const idx = parseInt(secimModu.split('-')[1]);
      setWaypoints(prev => prev.map((wp, i) => i === idx ? { ...wp, lat: kisaLat, lng: kisaLng } : wp));
    }
    setSecimModu(null);
  };

  const handleDeleteFlight = async (flightId) => {
    try {
      const response = await fetch(`http://localhost:8000/api/flights/${flightId}`, {
        method: 'DELETE',
      });
      if (response.ok) {
        setFlights(flights.filter(f => f.id !== flightId));
        if (selectedFlight && selectedFlight.id === flightId) {
          setSelectedFlight(null);
        }
      } else {
        console.error('Silme başarısız:', await response.text());
      }
    } catch (error) {
      console.error('Uçuş silinemedi:', error);
    }
  };

  const generateRandomFlight = async () => {
    const randomLat = () => 36.5 + Math.random() * 5.5;
    const randomLng = () => 27.0 + Math.random() * 16.0;
    
    const now = new Date();
    const startTime = now.toTimeString().slice(0, 5);

    const flightId = "TK" + Math.floor(Math.random() * 9000 + 1000);
    const flightData = {
      id: flightId,
      originName: "İstanbul (IST)",
      destName: "Antalya (AYT)",
      origin: [41.2753, 28.7519],
      destination: [36.8987, 30.8005],
      waypoints: [],
      startTime: startTime,
    };
    
    if (Math.random() > 0.5) {
      flightData.waypoints.push([randomLat(), randomLng()]);
    }

    try {
      const response = await fetch('http://localhost:8000/api/flights', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(flightData),
      });
      
      if (response.ok) {
        const result = await response.json();
        setFlights([...flights, result]);
        
        try {
          await fetch(`http://localhost:8001/simulations/${flightId}/start?speed=1`, { method: 'POST' });
        } catch (simError) {
          console.warn("Simülatör başlatılamadı:", simError);
        }
      } else {
        const errText = await response.text();
        alert("Rastgele uçuş oluşturulamadı: " + errText);
      }
    } catch (error) {
      console.error('Rastgele uçuş hatası:', error);
      alert("Bağlantı hatası: " + error.message);
    }
  };

  const currentTheme = MAP_THEMES[activeTheme] || MAP_THEMES.dark;

  return (
    <div style={{ position: 'relative', width: '100vw', height: '100vh', fontFamily: 'sans-serif' }}>

      {/* Üst Sağ Kontrol Barı (Harita Teması, Radar & Planlama) */}
      <div style={{ position: 'absolute', top: '20px', right: '20px', zIndex: 1000, display: 'flex', gap: '10px', alignItems: 'center' }}>
        
        {/* Harita Tema Seçici */}
        <div style={{
          background: 'rgba(20, 24, 36, 0.88)',
          backdropFilter: 'blur(14px)',
          border: '1px solid rgba(255, 255, 255, 0.15)',
          borderRadius: '12px',
          padding: '4px',
          display: 'flex',
          gap: '3px',
          boxShadow: '0 6px 24px rgba(0,0,0,0.35)'
        }}>
          {Object.values(MAP_THEMES).map(th => (
            <button
              key={th.id}
              onClick={() => setActiveTheme(th.id)}
              style={{
                background: activeTheme === th.id ? 'linear-gradient(135deg, #3b82f6, #1d4ed8)' : 'transparent',
                color: activeTheme === th.id ? 'white' : '#94a3b8',
                border: 'none',
                padding: '6px 10px',
                borderRadius: '8px',
                fontWeight: 700,
                fontSize: '11px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                transition: 'all 0.15s ease'
              }}
              title={th.name}>
              <span>{th.icon}</span>
              <span>{th.name}</span>
            </button>
          ))}
        </div>

        {/* Hava Durumu Radarı Aç/Kapa Butonu */}
        <div style={{
          background: 'rgba(20, 24, 36, 0.88)',
          backdropFilter: 'blur(14px)',
          border: '1px solid rgba(255, 255, 255, 0.15)',
          borderRadius: '12px',
          padding: '4px 10px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          boxShadow: '0 6px 24px rgba(0,0,0,0.35)'
        }}>
          <button
            onClick={() => setShowRadar(!showRadar)}
            style={{
              background: showRadar ? 'linear-gradient(135deg, #0ea5e9, #2563eb)' : 'rgba(255,255,255,0.08)',
              color: 'white',
              border: 'none',
              padding: '6px 10px',
              borderRadius: '8px',
              fontWeight: 700,
              fontSize: '11px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.2s ease'
            }}>
            <span>🌧️</span>
            <span>{showRadar ? 'Radar: AÇIK' : 'Radar: KAPALI'}</span>
          </button>
          {showRadar && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '10px', color: '#94a3b8' }}>
              <input 
                type="range" 
                min="0.2" 
                max="1.0" 
                step="0.05"
                value={radarOpacity} 
                onChange={(e) => setRadarOpacity(parseFloat(e.target.value))}
                style={{ width: '50px', cursor: 'pointer' }}
              />
            </div>
          )}
        </div>

        {!isPanelOpen ? (
          <>
            <button 
              className="open-panel-btn" 
              style={{ position: 'relative', top: '0', left: '0' }} 
              onClick={() => setIsPanelOpen(true)}
              title="Uçuş Planlama Merkezi"
            >
              +
            </button>
            <button 
              className="open-panel-btn" 
              style={{ position: 'relative', top: '0', left: '0', backgroundColor: '#9b59b6', fontSize: '24px' }} 
              onClick={generateRandomFlight}
              title="Rastgele Uçuş Üret"
            >
              🎲
            </button>
          </>
        ) : null}
      </div>

      {/* Planlama Paneli */}
      {isPanelOpen && (
        <PlanningPanel 
          onClose={() => setIsPanelOpen(false)}
          onFlightAdd={handleFlightAdd}
          secimModu={secimModu}
          setSecimModu={setSecimModu}
          kalkisLat={kalkisLat} setKalkisLat={setKalkisLat}
          kalkisLng={kalkisLng} setKalkisLng={setKalkisLng}
          varisLat={varisLat} setVarisLat={setVarisLat}
          varisLng={varisLng} setVarisLng={setVarisLng}
          waypoints={waypoints} setWaypoints={setWaypoints}
        />
      )}

      {/* Canlı Uçuş & Kokpit Telemetri Bilgi Paneli */}
      {selectedFlight && (
        <InfoPanel 
          flight={{
            ...selectedFlight, 
            status: positions[selectedFlight.id]?.status || 'bekliyor',
            altitude: positions[selectedFlight.id]?.altitude ?? 0,
            speed_kts: positions[selectedFlight.id]?.speed_kts ?? 0,
            bearing: positions[selectedFlight.id]?.bearing ?? 0
          }} 
          onClose={() => setSelectedFlight(null)} 
          onDelete={handleDeleteFlight} 
        />
      )}

      {/* Harita */}
      <MapContainer center={[39.92, 32.85]} zoom={6} maxZoom={19} style={{ width: '100%', height: '100%', cursor: secimModu ? 'crosshair' : 'grab' }}>
        
        {/* Seçilen Ana Harita Katmanı (Dark, Satellite, Standard, Topo) */}
        <TileLayer 
          key={currentTheme.id}
          url={currentTheme.url} 
          maxZoom={19}
          attribution={currentTheme.attribution} 
        />
        
        {/* Canlı Yağış ve Bulut Radarı Katmanı */}
        {showRadar && radarTilePath && (
          <TileLayer 
            key={radarTilePath}
            url={`https://tilecache.rainviewer.com${radarTilePath}/256/{z}/{x}/{y}/2/1_1.png`} 
            opacity={radarOpacity}
            zIndex={400}
            maxNativeZoom={7}
            maxZoom={19}
            tileSize={256}
            attribution='&copy; RainViewer Global Weather Radar'
          />
        )}

        <MapClickHandler secimModu={secimModu} onKoordinatSec={handleHaritadanKoordinatGirdi} />
        {historyLoaded && flights.map(f => (
          <FlightLayer 
            key={f.id} 
            flight={f} 
            onSelect={setSelectedFlight} 
            currentPosition={positions[f.id]} 
          />
        ))}
      </MapContainer>

      {/* Zaman Kaydırıcısı (Slider) ve Mod Kontrolü */}
      <div style={{
        position: 'absolute', bottom: '30px', left: '50%', transform: 'translateX(-50%)',
        backgroundColor: 'rgba(17, 21, 33, 0.92)', padding: '15px 30px', borderRadius: '20px',
        zIndex: 1000, color: 'white', display: 'flex', alignItems: 'center', gap: '25px',
        boxShadow: '0 12px 36px rgba(0,0,0,0.6)', backdropFilter: 'blur(16px)', border: '1px solid rgba(255,255,255,0.12)'
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
          <span style={{ fontSize: '11px', color: '#aaa', fontWeight: 'bold', letterSpacing: '1px' }}>MOD</span>
          <button 
            onClick={() => setIsLive(!isLive)}
            style={{ 
              backgroundColor: isLive ? '#e74c3c' : '#3498db', color: 'white', 
              border: 'none', padding: '10px 15px', borderRadius: '10px', cursor: 'pointer', 
              fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px', transition: 'all 0.3s ease'
            }}>
            {isLive ? (
              <><span style={{ width: '8px', height: '8px', backgroundColor: 'white', borderRadius: '50%', animation: 'blink 1s infinite' }}></span> CANLI (LIVE)</>
            ) : (
              <>⏪ GEÇMİŞ</>
            )}
          </button>
        </div>

        {/* ── ZAMAN KAYDIRICISI (SLIDER) ── */}
        <div style={{ width: '400px', padding: '0 10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#ddd', fontWeight: 'bold' }}>
            <span>{new Date(sliderMin * 1000).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}</span>
            <span style={{ color: '#f1c40f', fontSize: '14px' }}>
              {new Date(sliderValue * 1000).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
            <span>Şu An</span>
          </div>
          <Slider
            min={sliderMin}
            max={sliderMax}
            value={sliderValue}
            onChange={(val) => {
              setIsLive(false);
              setSliderValue(val);
            }}
            disabled={isLive}
            trackStyle={{ backgroundColor: '#e74c3c', height: 6 }}
            handleStyle={{
              borderColor: '#e74c3c', height: 18, width: 18, marginTop: -6, backgroundColor: '#fff',
              boxShadow: '0 0 10px rgba(231, 76, 60, 0.8)'
            }}
            railStyle={{ backgroundColor: 'rgba(255,255,255,0.2)', height: 6 }}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
          <span style={{ fontSize: '11px', color: '#aaa', fontWeight: 'bold', letterSpacing: '1px' }}>HEDEF UÇUŞ</span>
          <select 
            value={sliderTargetId} 
            onChange={(e) => setSliderTargetId(e.target.value)}
            style={{ 
              backgroundColor: 'rgba(50, 50, 50, 0.8)', color: 'white', border: '1px solid rgba(255,255,255,0.2)', 
              padding: '9px 12px', borderRadius: '10px', outline: 'none', fontWeight: 'bold', cursor: 'pointer', fontSize: '14px' 
            }}>
            <option value="ALL">Tümü (Eşzamanlı)</option>
            {flights.map(f => (
              <option key={f.id} value={f.id}>{f.id} ({f.originName} - {f.destName})</option>
            ))}
          </select>
        </div>
      </div>

    </div>
  );
}
