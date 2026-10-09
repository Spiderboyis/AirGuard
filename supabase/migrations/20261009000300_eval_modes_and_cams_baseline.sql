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
