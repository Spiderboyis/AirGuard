-- AirGuard: initial schema.
--
-- Every statement is idempotent (`if not exists`, `or replace`), so this file can be re-run safely
-- and concatenated into supabase/setup.sql for a fresh hosted project.
--
-- Access model: row-level security is enabled on every table and no policies are defined, so the
-- public `anon` key can read nothing. The backend uses the service-role key, which bypasses RLS.

-- ---------------------------------------------------------------------------------------------
-- Monitoring stations (OpenAQ locations)
-- ---------------------------------------------------------------------------------------------
create table if not exists public.stations (
  id          text primary key,
  name        text not null,
  lat         double precision not null check (lat between -90 and 90),
  lon         double precision not null check (lon between -180 and 180),
  sensor_id   bigint,
  source      text not null default 'openaq',
  active      boolean not null default true,
  last_seen   timestamptz,
  created_at  timestamptz not null default now()
);
comment on table public.stations is 'Air quality monitoring stations used by the forecast and the exposure engine.';

-- ---------------------------------------------------------------------------------------------
-- Hourly observations
-- ---------------------------------------------------------------------------------------------
create table if not exists public.measurements (
  station_id  text not null references public.stations(id) on delete cascade,
  pollutant   text not null,
  value       double precision not null,
  unit        text not null default 'µg/m³',
  ts          timestamptz not null,
  primary key (station_id, pollutant, ts)
);
create index if not exists measurements_ts_idx on public.measurements (ts desc);
comment on column public.measurements.ts is 'Start of the hourly averaging period, UTC.';

-- Hourly weather at each station (Open-Meteo), plus upwind fire detections (NASA FIRMS).
create table if not exists public.weather (
  station_id    text not null references public.stations(id) on delete cascade,
  ts            timestamptz not null,
  temp          double precision,
  humidity      double precision,
  wind_speed    double precision,
  wind_dir      double precision,
  blh           double precision,
  fires_upwind  integer,
  primary key (station_id, ts)
);
create index if not exists weather_ts_idx on public.weather (ts desc);

-- ---------------------------------------------------------------------------------------------
-- Forecasts
-- ---------------------------------------------------------------------------------------------
-- Full history of issued forecasts (used to evaluate the live pipeline after the fact).
create table if not exists public.forecasts (
  station_id     text not null references public.stations(id) on delete cascade,
  horizon_h      integer not null check (horizon_h between 0 and 48),
  target_ts      timestamptz not null,
  issued_at      timestamptz not null,
  pm25_pred      double precision not null,
  pm25_low       double precision,
  pm25_high      double precision,
  model_version  text not null,
  generated_at   timestamptz not null default now(),
  primary key (station_id, horizon_h, target_ts, model_version)
);
create index if not exists forecasts_target_idx on public.forecasts (target_ts desc);

-- Newest forecast per station and horizon. Horizon 0 is the latest observation.
-- The API reads only this table on the request path, so it stays small and fast.
create table if not exists public.forecasts_latest (
  station_id     text not null references public.stations(id) on delete cascade,
  horizon_h      integer not null check (horizon_h between 0 and 48),
  target_ts      timestamptz not null,
  issued_at      timestamptz not null,
  pm25_pred      double precision not null,
  pm25_low       double precision,
  pm25_high      double precision,
  model_version  text not null,
  generated_at   timestamptz not null default now(),
  primary key (station_id, horizon_h)
);

-- ---------------------------------------------------------------------------------------------
-- Model registry and backtest metrics
-- ---------------------------------------------------------------------------------------------
create table if not exists public.models (
  model_version  text primary key,
  data_source    text not null,
  horizons       integer[] not null,
  features       jsonb not null default '[]'::jsonb,
  train_start    timestamptz,
  train_end      timestamptz,
  test_start     timestamptz,
  test_end       timestamptz,
  n_stations     integer,
  notes          text,
  trained_at     timestamptz not null default now()
);

create table if not exists public.eval_metrics (
  model_version                text not null,
  horizon_h                    integer not null,
  mae                          double precision,
  rmse                         double precision,
  baseline_persistence_mae     double precision,
  baseline_persistence_rmse    double precision,
  baseline_hourly_mean_mae     double precision,
  baseline_hourly_mean_rmse    double precision,
  interval_coverage            double precision,
  interval_width               double precision,
  n_samples                    integer,
  created_at                   timestamptz not null default now(),
  primary key (model_version, horizon_h)
);

-- ---------------------------------------------------------------------------------------------
-- Caches and request artefacts
-- ---------------------------------------------------------------------------------------------
create table if not exists public.route_cache (
  key         text primary key,
  response    jsonb not null,
  created_at  timestamptz not null default now()
);

create table if not exists public.geocode_cache (
  key         text primary key,
  response    jsonb not null,
  created_at  timestamptz not null default now()
);

-- A saved trip analysis. The agent reads it back instead of recomputing the trip.
create table if not exists public.trips (
  id          uuid primary key default gen_random_uuid(),
  request     jsonb not null,
  result      jsonb not null,
  created_at  timestamptz not null default now()
);
create index if not exists trips_created_idx on public.trips (created_at desc);

-- One row per ingestion / forecast run; /health reports data freshness from here.
create table if not exists public.pipeline_runs (
  id           bigint generated always as identity primary key,
  kind         text not null,
  status       text not null check (status in ('running', 'ok', 'error')),
  started_at   timestamptz not null default now(),
  finished_at  timestamptz,
  details      jsonb not null default '{}'::jsonb
);
create index if not exists pipeline_runs_started_idx on public.pipeline_runs (started_at desc);

-- ---------------------------------------------------------------------------------------------
-- Row-level security: deny everything to anon/authenticated; the service role bypasses RLS.
-- ---------------------------------------------------------------------------------------------
alter table public.stations          enable row level security;
alter table public.measurements      enable row level security;
alter table public.weather           enable row level security;
alter table public.forecasts         enable row level security;
alter table public.forecasts_latest  enable row level security;
alter table public.models            enable row level security;
alter table public.eval_metrics      enable row level security;
alter table public.route_cache       enable row level security;
alter table public.geocode_cache     enable row level security;
alter table public.trips             enable row level security;
alter table public.pipeline_runs     enable row level security;
