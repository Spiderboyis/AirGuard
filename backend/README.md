# AirGuard backend

Python package `airguard`: forecast pipeline, exposure engine, FastAPI service and the Strands agent.
See the [project README](../README.md) and [docs/](../docs) for the full picture.

```bash
pip install -r backend/requirements.lock && pip install --no-deps -e backend   # from the repo root
cd backend && pytest               # unit tests
uvicorn airguard.api.main:app --reload --port 8000
```

| Package | Contents |
| --- | --- |
| `airguard.engine` | Pure exposure maths and every modelling assumption |
| `airguard.ml` | Features, training with a time-based backtest, hourly prediction |
| `airguard.ingestion` | OpenAQ, Open-Meteo and NASA FIRMS clients; incremental sync |
| `airguard.services` | Routing, geocoding, forecast access, trip analysis |
| `airguard.agent` | Strands agent, traced tools, number guard, fallback explanations |
| `airguard.api` | FastAPI app and request/response schemas |
| `airguard.jobs` | Backfill, hourly refresh and snapshot commands |
