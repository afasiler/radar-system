# Flight Tracking System — Technical Specification

> **Context for the implementing AI:** This is an assignment given to a CS student (2nd year) by a
> defense-software company (Endorfyn). The student knows Python, C, and has just learned Leaflet +
> Firebase (basic full-stack). They do NOT know React, FastAPI, or REST backend design yet.
> **Your role:** generate working code, but ensure the student understands each part — the company
> explicitly requires that the student can explain the architecture and logic (AI-assisted coding is
> permitted, blind copy-paste is not). Work in phases, verify each phase runs before moving on, and
> explain the "why" behind each piece. Do not dump the whole system at once.

---

## 1. Assignment Requirements (verbatim intent)

Build a web-based flight tracking application. Three tiers: **frontend (React)**, **backend (REST)**, **database**.

### Frontend
- A map (Leaflet or similar hosted map).
- A panel for planning flights.
- A time slider to set the currently displayed time on the map.
- Flights rendered on the map as: an **aircraft icon**, **start/end markers** (points), and a **dashed polyline** for the route.
- Multiple flights displayed simultaneously.
- Clicking an aircraft icon opens an info panel showing that flight's details (start time, ID, origin, destination).
- Visual polish is left to the implementer.

### Backend
- Planned flights (from frontend) are written to the database.
- Frontend fetches flight data from the database on demand.
- An **independent external simulator** connects to the backend:
  - It **queries planned flights** via one REST endpoint.
  - It **posts position data** for those flights to another REST endpoint.
  - The backend writes these positions to the database.
  - The frontend then updates the displayed flights using these positions.

### Time logic (hardest part)
- When the slider shows a **past** time, the simulator may still be streaming data.
- Incoming data is still written to the DB, but if it does not belong to the currently displayed time, it must **not** be shown on the map.
- Suggested approach: a **Live Mode / Replay Mode** distinction (implementation left open).

---

## 2. Tech Stack (decided)

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | React (Vite) + `react-leaflet` | React requested. Student knows Leaflet; react-leaflet wraps it. |
| Backend | Python + FastAPI + Uvicorn | Student knows Python. FastAPI = minimal boilerplate REST, auto-docs (`/docs`), async-ready. |
| Database | SQLite (start) → PostgreSQL/PostGIS if needed | SQLite is zero-config, file-based. Migrate to Postgres only if geospatial queries or concurrency demand it. |
| Real-time transport | Polling first, WebSocket later | Start with simple interval polling; upgrade to WebSocket in Phase 7 if latency matters. |
| Dev env | VS Code | Multi-file project. |

**Open decision to confirm with company:** the simulator's expected REST contract (endpoint paths, request/response schemas). If unspecified, design a clean contract and document it. This blocks Phase 6 — resolve before implementing simulator endpoints.

---

## 3. Data Model

### `flights` table
| Column | Type | Notes |
|---|---|---|
| `id` | TEXT (PK) | Flight ID (user-assigned or generated) |
| `origin_lat` | REAL | Start point latitude |
| `origin_lng` | REAL | Start point longitude |
| `dest_lat` | REAL | End point latitude |
| `dest_lng` | REAL | End point longitude |
| `start_time` | INTEGER | Unix epoch (ms) — flight scheduled start |
| `route` | TEXT (JSON) | Optional: GeoJSON LineString of planned route, or computed straight line |
| `created_at` | INTEGER | Unix epoch (ms) |

### `positions` table
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER (PK, autoincrement) | |
| `flight_id` | TEXT (FK → flights.id) | Which flight this position belongs to |
| `lat` | REAL | Aircraft latitude at this timestamp |
| `lng` | REAL | Aircraft longitude at this timestamp |
| `timestamp` | INTEGER | Unix epoch (ms) — when the aircraft was at this position |
| `heading` | REAL | Optional: bearing in degrees, for icon rotation |

**Key design point:** positions are timestamped. Replay Mode = query positions `WHERE timestamp <= sliderTime` and take the latest per flight. Live Mode = take the newest position per flight. This timestamping is what enables the time-slider feature.

---

## 4. REST API Contract

### Frontend ↔ Backend
| Method | Path | Purpose | Body / Response |
|---|---|---|---|
| `POST` | `/flights` | Create a planned flight | Body: flight object → returns created flight |
| `GET` | `/flights` | List all flights | Returns array of flights |
| `GET` | `/flights/{id}` | Single flight detail | Returns flight object |
| `GET` | `/positions?at={timestamp}` | Positions at/before a given time (Replay) | Returns latest position per flight ≤ timestamp |
| `GET` | `/positions/live` | Latest position per flight (Live) | Returns newest position per flight |

### Simulator ↔ Backend
| Method | Path | Purpose | Body / Response |
|---|---|---|---|
| `GET` | `/sim/flights` | Simulator queries planned flights | Returns array of flights to simulate |
| `POST` | `/sim/positions` | Simulator posts position updates | Body: `[{flight_id, lat, lng, timestamp, heading}]` → writes to `positions` |

> **NOTE:** These simulator paths/schemas are a *proposal*. If the company provides a contract, override these to match exactly. Mismatched contract = simulator can't connect.

---

## 5. Frontend Architecture (React)

### Component tree
```
App
├── MapView                 (react-leaflet MapContainer + TileLayer)
│   ├── FlightLayer[]       (one per flight: aircraft Marker + start/end Markers + dashed Polyline)
├── PlanningPanel           (form: origin, dest, ID, start_time → POST /flights)
├── InfoPanel               (shows selected flight details; visible when a flight is selected)
└── TimeSlider              (controls displayed time + Live/Replay mode toggle)
```

### Key React state (lives in `App`, passed via props)
| State | Type | Purpose |
|---|---|---|
| `flights` | array | All flights (from `GET /flights`) |
| `positions` | object `{flightId: {lat,lng,heading}}` | Current displayed positions |
| `selectedFlightId` | string \| null | Which flight's info panel is open |
| `displayTime` | number (epoch ms) | Time the slider currently shows |
| `mode` | `'live'` \| `'replay'` | Determines which position endpoint to poll |

### Rendering rules
- **Aircraft icon:** custom `L.divIcon` or `L.icon`; rotate by `heading` if available.
- **Route:** `<Polyline>` with `dashArray="8"` (dashed).
- **Start/end:** `<Marker>` (or `<CircleMarker>`) at origin/dest.
- **Multiple flights:** map over `flights` array, render a `FlightLayer` per flight.
- **Click → info:** aircraft Marker `eventHandlers={{ click: () => setSelectedFlightId(id) }}`.
- **Time filtering:** in Replay mode, only render flights that have a position ≤ `displayTime`; hide the rest.

---

## 6. Time Logic (Live vs Replay) — the hard part

**The core problem:** the simulator streams positions continuously, tagged with timestamps. The map must show only positions relevant to `displayTime`, while still persisting everything.

**Model:**
- Simulator always POSTs positions → always written to `positions` table (regardless of what the map shows).
- **Live Mode:** `displayTime` tracks "now" (auto-advances). Frontend polls `/positions/live`, renders newest position per flight.
- **Replay Mode:** `displayTime` is a past instant set by the slider. Frontend polls/fetches `/positions?at={displayTime}`, renders the latest position per flight *at or before* that instant. New incoming data (with timestamps after `displayTime`) is saved to DB but not shown.

**Mode switch:** a toggle. Dragging the slider into the past → Replay. Snapping to "now" / pressing Live → Live. `mode` state drives which endpoint is polled.

**Implementation note:** the "latest position per flight ≤ T" query is the crux. In SQL: for each `flight_id`, select the row with `MAX(timestamp)` where `timestamp <= T`. This one query powers Replay.

---

## 7. Phased Build Plan

> Each phase produces a **running, verifiable artifact**. Do not proceed to the next phase until the
> current one runs. Explain each new concept as it's introduced (React, FastAPI, SQL).

### Phase 0 — Scaffold
- Verify Node (`node --version`, `npm --version`); install if missing.
- `npm create vite@latest flight-tracker -- --template react`
- `cd flight-tracker && npm install && npm run dev` → default page at `:5173`.
- `npm install leaflet react-leaflet`
- **Artifact:** empty React app running.

### Phase 1 — Map
- Render `<MapContainer>` + `<TileLayer>` (OpenStreetMap), centered on Turkey/Ankara.
- **Artifact:** working map in React.
- **Concept:** react-leaflet, first component, `import 'leaflet/dist/leaflet.css'`.

### Phase 2 — Static flight rendering
- Hardcode 1–2 flight objects.
- Render per flight: start/end markers, dashed `<Polyline>`, aircraft `<Marker>` with custom icon.
- **Artifact:** static flights on map (icon + route + endpoints), multiple at once.
- **Concept:** custom icons, dashArray, mapping arrays to components.

### Phase 3 — Click → info panel
- Aircraft Marker click sets `selectedFlightId`.
- `InfoPanel` renders selected flight's details (ID, start time, origin, destination).
- **Artifact:** clickable aircraft + info panel.
- **Concept:** React state, event handlers, conditional rendering, lifting state up.

### Phase 4 — Planning panel
- `PlanningPanel` form: origin, dest, ID, start_time.
- On submit, add flight to `flights` state (frontend-only for now).
- **Artifact:** user can plan flights that appear on the map.
- **Concept:** controlled inputs, updating state arrays.

### Phase 5 — Backend + DB
- `pip install fastapi uvicorn`; run with `uvicorn main:app --reload`.
- SQLite (`sqlite3` stdlib or SQLAlchemy). Create `flights` table.
- Implement `POST /flights`, `GET /flights`, `GET /flights/{id}`.
- Enable CORS (frontend on `:5173`, backend on `:8000`).
- Wire frontend: planning → `POST`, load → `GET` (via `fetch`).
- **Artifact:** flights persist in DB, round-trip through frontend.
- **Concept:** FastAPI routes, Pydantic models, SQLite, CORS, `fetch`.

### Phase 6 — Simulator endpoints
- **Resolve contract with company first** (or design + document).
- `GET /sim/flights` → return planned flights.
- `POST /sim/positions` → write positions to `positions` table.
- Create `positions` table.
- **Artifact:** simulator can query flights and post positions.
- **Concept:** REST API design, external integration, request validation.

### Phase 7 — Real-time position updates
- Frontend polls `/positions/live` on an interval (e.g. every 1–2s), updates aircraft markers.
- (Optional upgrade: WebSocket for push instead of poll.)
- **Artifact:** aircraft move on the map as positions arrive.
- **Concept:** polling with `setInterval`/`useEffect`, updating marker positions, cleanup.

### Phase 8 — Time slider + Live/Replay
- `TimeSlider` sets `displayTime`; toggle for Live/Replay `mode`.
- Live: poll `/positions/live`. Replay: fetch `/positions?at={displayTime}`.
- Implement "latest position per flight ≤ T" query in backend.
- Positions always persist; only those matching `displayTime` render.
- **Artifact:** time control with two modes.
- **Concept:** time-based filtering, SQL MAX-per-group, mode state machine.

---

## 8. Architecture Diagram

```
┌──────────────┐    REST (fetch)     ┌──────────────┐     SQL      ┌──────────┐
│   Frontend   │ ◄─────────────────► │   Backend    │ ◄──────────► │ Database │
│ React +      │  POST /flights      │  FastAPI     │              │ SQLite   │
│ react-leaflet│  GET  /flights      │              │              │          │
│              │  GET  /positions    │              │              │          │
└──────────────┘                     └──────────────┘              └──────────┘
       ▲                                    ▲
       │ renders aircraft/routes            │ REST
       │ from positions                     │
       │                              ┌──────────────┐
       └── time slider selects        │  Simulator   │ (independent, external)
           which instant to show      │  GET /sim/flights   → queries planned flights
                                       │  POST /sim/positions → streams positions
                                       └──────────────┘
```

---

## 9. Constraints & Reminders

- **No deadline given** — but scope is large; sequence strictly by phase.
- **Simulator contract is the critical unknown** — confirm before Phase 6.
- **Student must understand each part** — explain concepts, don't just emit code. Company will quiz on architecture.
- **Domain mapping (defense context):** aircraft position = point, route = LineString, flight metadata = properties. This mirrors target-tracking / command-and-control visualization — the same geo→data→display chain the student already learned with Leaflet/GeoJSON.
- **Half the domain is known:** Leaflet, GeoJSON, geometry types, marker/popup, DB read/write m\
  (from Firebase). New: React, FastAPI, REST design, real-time updates, time-mode logic.
- **Quality floor:** responsive, keyboard-accessible controls, clean state management, CORS handled, error states in UI.

---

## 10. First Actions

1. Confirm simulator REST contract with the company (needed by Phase 6; ask now).
2. `node --version` — verify toolchain.
3. Phase 0 — scaffold React project.
4. Proceed phase by phase, verifying each runs and explaining each concept before moving on.
