-- =============================================================================================
-- AirGuard: full database setup for a fresh Supabase project.
--
-- GENERATED FILE. Do not edit by hand. Source: supabase/migrations/*.sql
-- Regenerate with: make setup-sql
--
-- How to use: open your project's SQL editor in the Supabase dashboard, paste this whole file,
-- and run it. It is idempotent, so running it again on an existing project is safe.
-- Migrations included (in order):
--   20261009000000_init.sql
--   20261009000100_station_freshness_view.sql
--   20261009000200_live_sources_and_cams.sql
--   20261009000300_eval_modes_and_cams_baseline.sql
-- =============================================================================================

-- ---- 20261009000000_init.sql ---------------------------------------------------------------
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

-- ---- 20261009000100_station_freshness_view.sql ---------------------------------------------
-- Hours of PM2.5 history per station, used by the data-coverage checks and /health.

create or replace view public.station_coverage
with (security_invoker = true) as
select
  s.id,
  s.name,
  s.source,
  s.active,
  count(m.ts)  as n_hours,
  min(m.ts)    as first_ts,
  max(m.ts)    as last_ts
from public.stations s
left join public.measurements m
  on m.station_id = s.id and m.pollutant = 'pm25'
group by s.id, s.name, s.source, s.active;

comment on view public.station_coverage is 'PM2.5 history depth and recency per station.';

-- ---- 20261009000200_live_sources_and_cams.sql ----------------------------------------------
-- Support mixed station feeds and the CAMS model covariate.
--
-- * stations.provider / is_monitor: CPCB reference monitors and low-cost sensors (AirGradient,
--   AirNow) report with different delays and accuracy; the app labels them differently.
-- * weather.cams_pm25: Open-Meteo's CAMS PM2.5 at the station location. It is always current, so
--   the forecast can still estimate a station whose own feed is delayed.

alter table public.stations
  add column if not exists provider   text,
  add column if not exists is_monitor boolean not null default true;

alter table public.weather
  add column if not exists cams_pm25 double precision;

-- Forecast rows record how old the station's newest observation was when the forecast was issued.
alter table public.forecasts
  add column if not exists obs_age_h double precision;
alter table public.forecasts_latest
  add column if not exists obs_age_h double precision;

comment on column public.forecasts_latest.obs_age_h is
  'Hours between the station''s newest observation and issue time. Large values mean the feed is delayed and the value is a model estimate.';

-- ---- 20261009000300_eval_modes_and_cams_baseline.sql ---------------------------------------
-- Backtest metrics per evaluation mode, plus the raw CAMS forecast as a third baseline.
--
-- mode = 'normal': the station's own feed is current (the usual case).
-- mode = 'delayed': the station's own feed is blanked, as during a CPCB feed outage; the model
--                   relies on CAMS, weather and neighbouring stations.

alter table public.eval_metrics
  add column if not exists mode text not null default 'normal',
  add column if not exists baseline_cams_mae  double precision,
  add column if not exists baseline_cams_rmse double precision;

alter table public.eval_metrics drop constraint if exists eval_metrics_pkey;
alter table public.eval_metrics add constraint eval_metrics_pkey primary key (model_version, horizon_h, mode);

alter table public.models
  add column if not exists summary jsonb not null default '{}'::jsonb;
