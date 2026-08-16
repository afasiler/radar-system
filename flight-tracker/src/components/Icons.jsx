import L from 'leaflet';

export const STATUS_COLORS = {
  bekliyor: '#f39c12',
  ucusta:   '#2ecc71',
  indi:     '#95a5a6',
};

export const createPlaneIcon = (bearing, status = 'ucusta') => L.divIcon({
  html: `<div style="
    width: 28px; height: 28px;
    display: flex; align-items: center; justify-content: center;
    transform: rotate(${bearing}deg); cursor: pointer;
  ">
    <svg viewBox="0 0 24 24" width="24" height="24">
      <path fill="${STATUS_COLORS[status]}" stroke="white" stroke-width="1"
        d="M21,16v-2l-8-5V3.5C13,2.67,12.33,2,11.5,2S10,2.67,10,3.5V9l-8,5v2l8-2.5V19l-2,1.5V22l3.5-1l3.5,1v-1.5L13,19v-5.5L21,16z"/>
    </svg>
  </div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
  className: '',
});

export const originDot = L.divIcon({
  html: `<div style="width:12px;height:12px;background:#2ecc71;border:2px solid white;border-radius:50%;"></div>`,
  iconSize: [12, 12], iconAnchor: [6, 6], className: ''
});

export const destDot = L.divIcon({
  html: `<div style="width:12px;height:12px;background:#e74c3c;border:2px solid white;border-radius:50%;"></div>`,
  iconSize: [12, 12], iconAnchor: [6, 6], className: ''
});

export const waypointDot = L.divIcon({
  html: `<div style="width:10px;height:10px;background:#3498db;border:2px solid white;border-radius:2px;transform:rotate(45deg);"></div>`,
  iconSize: [10, 10], iconAnchor: [5, 5], className: ''
});
