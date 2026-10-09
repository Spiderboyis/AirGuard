# Decisions and fixes

The implementation follows the AirGuard guide. These are the places the starter code was wrong or would not run, and what the code does instead.

## Local database

Supabase is still used when `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are both set. With both empty, the same `select` / `upsert` calls use SQLite at `AIRGUARD_DB` (default `data/local.db`). Row-level security and PostGIS exist only in `sql/schema.sql`. The engine uses latitude and longitude in Python, which is what the guide already switched to.

## Forecast clock

Hour-of-day and day-of-week features, and the hour-of-day baseline, use India Standard Time. The guide's starter code used the UTC hour, so a Delhi morning peak would have been labelled as the previous evening. Train and serve both call `ml.features.local_dt`, so they stay aligned.

## XGBoost 3

`early_stopping_rounds` is no longer a constructor or `fit` argument. Training passes `EarlyStopping(rounds=30, save_best=True)` as a callback. The persistence baseline reads the `now` column by name, and that column cannot be dropped in an ablation.

## Routing

OpenRouteService is used when `ORS_API_KEY` is set. Known demo geometries in `fixtures/demo_routes.json` are next. The public OSRM demo server is the fallback so a laptop without an ORS key can still score a trip. Straight-line stand-ins are used only when `AIRGUARD_STRAIGHT_ROUTES=1` and every routing service failed. They are not roads.

## Offline demo

The planner page in the guide declared offline state but never loaded `/demo/trip1.json`. The page now does that when the URL contains `?offline=1`, and it restores the saved mode, sensitivity, and limits so the cards match the frozen trip. The map selects the recommended route, not only the cleanest leave-now route.

## Agent

`/agent/chat` is served by the local FastAPI app (Appendix M). On Lambda the same path is the agent function, which also answers CORS preflight `OPTIONS` requests. The demo flag lives in a `contextvar`, so two overlapping chats cannot flip each other's snapshot mode. The profile line includes `max_extra_min` and `max_wait_min`. If the model is down, demo mode can still return a cached scripted answer. The offline file's answer is filled only from the engine's saved numbers.

## Ingestion

Missing `OPENAQ_API_KEY` makes the hourly job forecast from rows already in the database instead of failing. `AIRGUARD_OFFLINE_INGEST=1` forces that path, which is how the synthetic seed trains and then writes `forecasts_latest` without calling OpenAQ. A missing FIRMS key stores zero fires. Timestamps are floored to a single UTC-hour spelling so OpenAQ's `Z` suffix and Open-Meteo's shorter strings do not insert the same hour twice.

## Frontend build

Next.js 16 turns on `cacheComponents`, which enables Partial Prerendering. That cannot be combined with `output: "export"`, so the frontend config keeps the static export and leaves `cacheComponents` off. MapLibre's current package has no default export, so the map imports `Map`, `NavigationControl`, and `LngLatBounds` by name.

## What is still out of scope

Scheduled departures such as "tomorrow 8 AM" are not supported. Metro is not a mode. Email alerts stay off unless `ALERT_TOPIC_ARN` is set. AWS deploy files are in `infra/` and are not required to run locally.
