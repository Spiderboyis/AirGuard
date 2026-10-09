# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
