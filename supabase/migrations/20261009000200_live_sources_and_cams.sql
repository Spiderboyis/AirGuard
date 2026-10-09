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
