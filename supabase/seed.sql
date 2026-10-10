-- Local development seed. Runs after migrations on `supabase db reset`.
--
-- Intentionally empty: station data is loaded by `make data` (synthetic) or `make backfill`
-- (OpenAQ), because it depends on which data source you use.
select 1;
