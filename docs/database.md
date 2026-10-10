# Database

AirGuard uses Postgres through Supabase: a local stack for development, a hosted project for
deployment. The schema is defined by migrations in [`supabase/migrations/`](../supabase/migrations).

## Two files, one source of truth

| File | Use it for |
| --- | --- |
| `supabase/migrations/*.sql` | The schema history. Applied in order by the Supabase CLI. **Edit here.** |
| `supabase/setup.sql` | Generated from the migrations. Paste it into the SQL editor of a **fresh hosted project** to create everything at once. |

Every statement is idempotent (`if not exists`, `or replace`, `add column if not exists`), so
`setup.sql` is safe to run again on a project that already has some of it.

## Adding a change

1. Create a new file named `supabase/migrations/<YYYYMMDDHHMMSS>_<what>.sql`. Never edit an applied migration.
2. Write idempotent SQL.
3. Apply it locally: `make db-migrate`.
4. Regenerate the paste-ready file: `make setup-sql` (CI fails if you forget: `make check`).
5. On a hosted project, paste **only the new migration** into the SQL editor (or the whole
   `setup.sql`; it's idempotent).

## Setting up a hosted Supabase project

1. Create a project (pick a region close to where the API will run).
2. SQL editor → paste `supabase/setup.sql` → Run.
3. Project Settings → Database → Connection string → **Session pooler** URI. Put it in `.env.local` as
   `DATABASE_URL=...` (keep the password secret).
4. Run `make backfill`, `make train`, `make forecast` against it.

Free hosted projects pause after a week without activity. Open the dashboard before a demo.

## Access model

Row-level security is **enabled on every table with no policies**, so the public `anon` key can read
nothing through the REST API. The backend connects directly to Postgres with the database password (or
the service role) and is the only reader and writer. The web app never talks to the database.

## Tables

| Table | Written by | Purpose |
| --- | --- | --- |
| `stations` | ingestion | Active PM2.5 locations, provider, monitor vs low-cost |
| `measurements` | ingestion | Hourly PM2.5 per station |
| `weather` | ingestion | Hourly weather, CAMS PM2.5 and upwind fires per station |
| `forecasts` | hourly job | Every forecast issued (for later evaluation) |
| `forecasts_latest` | hourly job | The current forecast per station and horizon (what the API reads) |
| `models` | training | Model registry: data window, features, notes |
| `eval_metrics` | training | Backtest per model, horizon and mode |
| `route_cache`, `geocode_cache` | API | Cached public-service responses |
| `trips` | API | Saved trip analyses the assistant reads back |
| `pipeline_runs` | jobs | Run history for `/health` |
| `station_coverage` (view) | — | Hours of history per station |

## Useful queries

```sql
-- History depth per station
select * from station_coverage order by n_hours desc;

-- Stations whose feed is delayed right now
select s.name, f.obs_age_h from forecasts_latest f join stations s on s.id = f.station_id
where f.horizon_h = 0 and (f.obs_age_h is null or f.obs_age_h > 3) order by f.obs_age_h desc nulls first;

-- Latest backtest
select horizon_h, mode, round(mae::numeric, 1) mae, round(baseline_persistence_mae::numeric, 1) persistence,
       round(baseline_cams_mae::numeric, 1) cams
from eval_metrics where model_version = (select model_version from models order by trained_at desc limit 1)
order by mode, horizon_h;
```
