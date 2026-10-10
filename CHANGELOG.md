# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] - 2026-10-10

### Added
- Landing page rebuilt around live data: a ride-window chart (forecast along the demo route with the ride
  as a window you can slide to other departures), an annotated route figure, a "won't do" list, a
  computed evidence sentence, and a CPCB-coloured scroll progress bar.
- `POST /trips/preview`: unsaved analysis plus corridor forecast and per-departure exposure.
- Assistant: "New chat" button; a new trip starts a fresh conversation.
- `make start` and `make stop`; `backend/requirements.lock` for reproducible installs.

### Changed
- Planner tabs sit at the top of the panel; the assistant view pins the message box and collapses the
  trip form to a summary.
- Map limited to Delhi NCR; basemap tile failures are logged as warnings.
- Pointer cursor on every clickable control.
- The number guard accepts values from the user's own profile; explanations distinguish "outside your
  limits" from "not worth the time".
- Licence aligned with the repository (Apache-2.0).

## [0.1.0] - 2026-10-09

### Added
- Exposure engine: space-time PM2.5 field (time interpolation + inverse-distance weighting), 200 m route
  segments, exposure index with range and confidence, 15-minute departure grid and a sensitivity-aware
  decision rule.
- Forecast: XGBoost per horizon (now, +1, +3, +6, +12, +24 h) on a year of OpenAQ data with weather,
  CAMS and upwind fires; time-based backtest against persistence, hour-of-day mean and raw CAMS; a
  delayed-feed mode for late CPCB data.
- Ingestion from OpenAQ, Open-Meteo and NASA FIRMS with incremental sync and an hourly job.
- FastAPI service with trip analysis, routes, departures, stations, forecast, evaluation and metadata.
- Strands Agents SDK assistant with traced tools, a number guard and a deterministic fallback.
- Next.js web app: landing page, onboarding, trip planner with map and assistant, evidence and method pages.
- Local Supabase with migrations and a generated `setup.sql`.
