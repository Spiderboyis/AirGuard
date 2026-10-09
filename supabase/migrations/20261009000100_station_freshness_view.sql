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
