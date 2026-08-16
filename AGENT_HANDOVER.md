# AGENT HANDOVER DOCUMENT

## Project Overview (Flight Tracker & Simulator)
This project consists of three main components:
1. **Main Backend (Port 8000)**: A FastAPI server (`backend/main.py`) using SQLite (`flights.db`). It handles flight plans, stores positional history, and serves the main React frontend.
2. **Simulator Service (Port 8001)**: A secondary FastAPI server (`backend/simulator_service/simulator_main.py`). It runs background threads (`simulation_engine.py`) for each flight, simulating their movement along a great circle route. It pushes new positions to the Main Backend.
3. **Main Frontend (Port 5173)**: A React application (`flight-tracker/`) using Leaflet. It fetches flight history from the Main Backend and interpolates plane positions for smooth animation, including a timeline slider for time travel.

## Important Directories & Files
- `/backend/main.py` - Core API (CRUD for flights, accepting simulator telemetry).
- `/backend/simulator_service/simulation_engine.py` - The core engine that calculates routes and runs `threading.Thread` instances to simulate flights. **Handle with extreme care.**
- `/backend/simulator_service/sim_frontend/index.html` - A secondary, vanilla JS frontend specifically for controlling the simulator (Play, Pause, Speed). Available at `http://localhost:8001/ui`.
- `/flight-tracker/src/App.jsx` & `useFlightPositions.js` - React UI and logic for drawing planes and handling the timeline.

## How to Start the Services
The project uses a Python virtual environment located at `/backend/venv/`.
```bash
# 1. Start Main Backend
cd backend && ./venv/bin/uvicorn main:app --port 8000 --reload

# 2. Start Simulator Service
cd backend/simulator_service && ../venv/bin/uvicorn simulator_main:app --port 8001 --reload

# 3. Start React Frontend
cd flight-tracker && npm run dev
```

## Critical User Preferences & Warnings (MUST READ)
1. **Database History is Sacred to the Frontend**: The React frontend heavily relies on the database's `FlightPosition` history array to draw flight paths (orange lines) and power the time-travel slider.
2. **The "Reset" Bug Sensitivity**: If you modify the simulator's "Reset" or "Start" functionality, **DO NOT randomly delete the flight history from the database** unless explicitly requested. I previously made a change that deleted the history to make planes "jump back to the start", and the user was absolutely furious because it broke the React frontend.
3. **Isolation**: The user wants the Simulator UI (port 8001) to act independently. Clicking "Reset" in the Simulator should ideally snap the planes to the origin *on the simulator map only*, without wiping the actual DB history that the React app uses.
4. **Current Simulator Engine State**: I completely reverted `simulation_engine.py` to the user's original logic because they were unhappy with my autonomous bug fixes. Currently, `start_all` and `start_one` **do** issue `DELETE` requests to the history (as was in the original code), but `reset_all` only stops the threads. 
5. **Simulator UI Aesthetics**: I added ETA calculation and global speed controls (1x, 10x, 50x) to `sim_frontend/index.html`. These should be preserved.

## Pending Issues
- **"Start All" Duplication**: If the simulator is paused and restarted, the original engine logic will sometimes push duplicate points or fast-forward incorrectly. The user previously complained that "Start All" doesn't work right and that F5 causes a millisecond flicker of planes at the origin on the React frontend. 
- *Note:* I wrote an Implementation Plan to fix this using a `skip_until` parameter, but the user rejected it in favor of keeping the original logic. If the user asks you to fix "Start All" or the "F5 Flicker", be very cautious about touching the DB history.

Good luck! Listen carefully to the user's instructions regarding how the Simulator should interact with the Frontend.
