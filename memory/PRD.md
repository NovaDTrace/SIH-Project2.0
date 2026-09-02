# ISRO Intelligent Dead-Reckoning Dashboard — PRD

## Original problem
> "I will give u dataset as well. make me a FULL WEB APP WITH ML TRAINING AND EVERYTHING. I WANT MY SHIT TO WORK."

Context: ISRO's *AI/ML Based Intelligent Dead Reckoning System for Seamless Navigation* problem statement. Dataset: IO-VNBD (smartphone IMU log `S-S1.csv` + vehicle telemetry `V-S1.csv`) — Coventry drive.

## Personas
- **Hackathon / proposal reviewer** — needs a demonstrable, honest pipeline showing measurable drift reduction.
- **Aerospace-navigation engineer** — wants to see the sensor flow, ML model quality, and Kalman-filter behaviour on real data.

## Architecture (implemented 2026-02-03)
- **Backend** — FastAPI (`/app/backend/server.py`) + numpy/pandas/scikit-learn pipeline (`/app/backend/pipeline.py`).
  - `POST /api/dataset/load-preset` → loads bundled `S-S1.csv` (first ~600 s at native 10 Hz).
  - `POST /api/dataset/upload` → user CSV in the same schema.
  - `POST /api/pipeline/train` → RandomForest velocity regressor from 21 IMU-window features (gravity-subtracted linear-accel stats, gyro stats, pitch/roll, jerk).
  - `POST /api/pipeline/simulate` → runs the ENU dead-reckoning + EKF fusion, with phone-to-vehicle alignment (δ learned from GPS-heading vs device-yaw) and non-holonomic constraint. Returns GT / INS-raw / fused trajectories, drift %, RMSE, blackout distance (true GPS path length).
  - `POST /api/ai/summary` → Claude Sonnet 4.5 via `emergentintegrations` + `EMERGENT_LLM_KEY`.
- **Frontend** — React 19 + Tailwind + shadcn/ui + Leaflet + Recharts + Sonner.
  - Single dashboard page (`/app/frontend/src/pages/Dashboard.jsx`) with 4 stages: Dataset, ML Training, Blackout Simulation, Trajectory Map + Metrics + AI report.
  - Dark tactical/aerospace aesthetic (Exo 2 / IBM Plex Sans / JetBrains Mono, cyan/orange/purple accents).
- **State** — in-memory session dict on backend (fine for MVP demo).
- **Data-testid** coverage on every interactive control + key metric.

## What's implemented
- Full CSV → preprocess → ML train → EKF-fusion simulation → map + metrics → LLM report loop, exercised end-to-end.
- Native 10 Hz resolution preserved (no downsampling drift).
- Velocity signal derived from smoothed GPS positions (`GPS SPEED` column was saturated in the sample data).
- Fused drift on 120-150 s blackout: **13.9 %** vs INS baseline **248.9 %** — ~18× improvement.
- 16/16 backend pytest cases passing. Frontend e2e verified via testing agent (~90 %).

## Backlog / next
- **P1** — meet the 10 % ISRO drift target. Requires: better phone-mount calibration (learn a proper 3D rotation, not just yaw δ), Savitzky–Golay velocity target, LSTM head over IMU windows, map-matching to OSM road graph.
- **P1** — persist sessions to Mongo so backend restart doesn't 404 the UI.
- **P2** — live 10 Hz playback marker along the fused trajectory.
- **P2** — support the vehicle CSV (`V-S1.csv`) as extra ground-truth channel (wheel-speed, brake, yaw-rate).
- **P2** — Android app export (TensorFlow Lite model).
