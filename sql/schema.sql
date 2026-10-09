-- AirGuard schema for Supabase. Enable PostGIS, then run this once in the SQL editor.
-- The local SQLite fallback in common/db.py mirrors these tables without PostGIS or row-level security.
-- The service role key bypasses row-level security. The anon key has no policies, so it cannot read the tables.

create extension if not exists postgis;

create table if not exists stations (
  id text primary key,
  name text,
  geom geography(Point, 4326),
  lat double precision,
  lon double precision,
  sensor_id bigint,
  last_seen timestamptz,
  source text default 'openaq'
);

create table if not exists measurements (
  station_id text references stations(id),
  pollutant text not null,
  value double precision,
  unit text,
  ts timestamptz not null,
  primary key (station_id, pollutant, ts)
);
create index if not exists measurements_ts on measurements (ts desc);

create table if not exists weather (
  ts timestamptz not null,
  station_id text references stations(id),
  wind_speed double precision,
  wind_dir double precision,
  humidity double precision,
  temp double precision,
  blh double precision,
  fires_upwind integer,
  primary key (station_id, ts)
);

create table if not exists forecasts (
  station_id text references stations(id),
  horizon_h integer not null,
  target_ts timestamptz not null,
  pm25_pred double precision,
  pm25_low double precision,
  pm25_high double precision,
  model_version text,
  generated_at timestamptz default now(),
  primary key (station_id, horizon_h, target_ts, model_version)
);

create table if not exists forecasts_latest (
  station_id text references stations(id),
  horizon_h integer not null,
  target_ts timestamptz not null,
  pm25_pred double precision,
  pm25_low double precision,
  pm25_high double precision,
  model_version text,
  generated_at timestamptz default now(),
  primary key (station_id, horizon_h)
);

create table if not exists eval_metrics (
  model_version text,
  horizon_h integer,
  mae double precision,
  rmse double precision,
  baseline_persistence_mae double precision,
  baseline_hourly_mean_mae double precision,
  baseline_persistence_rmse double precision,
  baseline_hourly_mean_rmse double precision,
  interval_coverage double precision,
  interval_width double precision,
  n_samples integer,
  primary key (model_version, horizon_h)
);

create table if not exists route_cache (
  key text primary key,
  response jsonb not null,
  created_at timestamptz default now()
);

do $$ declare t text; begin
  foreach t in array array['stations','measurements','weather','forecasts','forecasts_latest',
                           'eval_metrics','route_cache'] loop
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;
