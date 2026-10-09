"""Issue a forecast for every active station at the current hour.

Horizon 0 is "now": the station's own reading if it reported within STALE_AFTER_H hours, otherwise
the nowcast model's estimate (flagged by obs_age_h). Horizons 1-24 come from the per-horizon models.
If no model has been trained yet, a transparent fallback is used (last reading, else CAMS scaled
by the station's recent bias) so the app still works on a fresh install.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import xgboost as xgb

from airguard import db
from airguard.ml import data
from airguard.ml.features import FEATURES, HORIZONS, STALE_AFTER_H, build_frame
from airguard.ml.train import latest_model_dir

log = logging.getLogger("airguard.predict")

MEASUREMENT_UNCERTAINTY = 0.10   # ±10% band shown around a direct reading
FALLBACK_SPREAD = 0.35           # ±35% band for the no-model fallback

_cache: dict = {}


def load_models() -> tuple[dict, dict] | None:
    d = latest_model_dir()
    if d is None:
        return None
    if _cache.get("dir") == d:
        return _cache["meta"], _cache["models"]
    meta = json.loads((d / "meta.json").read_text())
    models = {}
    for h in meta["horizons"]:
        m = xgb.XGBRegressor()
        m.load_model(d / f"h{h}.json")
        models[int(h)] = m
    _cache.update(dir=d, meta=meta, models=models)
    return meta, models


def issue_hour(now: datetime) -> pd.Timestamp:
    """Forecasts are issued from the newest hour that has readings (OpenAQ delivers even live
    sensors about two hours late), so features look exactly like they did in the backtest. The
    API interpolates "now" between that hour and the following horizons."""
    floor = pd.Timestamp(now).tz_convert("UTC").floor("h")
    newest = db.query("select max(ts) as ts from measurements where pollutant = 'pm25' and ts > %s",
                      ((floor - pd.Timedelta(hours=6)).to_pydatetime(),))[0]["ts"]
    return min(floor, pd.Timestamp(newest).tz_convert("UTC")) if newest else floor


def forecast(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    t0 = issue_hour(now)
    x = data.load_inputs((t0 - pd.Timedelta(hours=100)).to_pydatetime(), (t0 + pd.Timedelta(hours=26)).to_pydatetime())
    loaded = load_models()
    version = loaded[0]["version"] if loaded else "fallback"
    issued = t0.to_pydatetime()
    rows = []
    last_fresh = x.pm25.ffill(limit=STALE_AFTER_H).loc[t0]

    for h in HORIZONS:
        f = build_frame(x, pd.DatetimeIndex([t0]), h, with_target=False)
        delayed = f["feed_delayed"].to_numpy()
        if loaded and h in loaded[1]:
            meta, models = loaded
            pred = np.expm1(models[h].predict(f[FEATURES])).clip(min=0)
            q = meta["quantiles"].get(str(h), {})
            qn, qd = q.get("normal", q.get("delayed")), q.get("delayed")
            lo = np.where(delayed, pred * qd[0], pred * qn[0])
            hi = np.where(delayed, pred * qd[1], pred * qn[1])
        else:
            bias = f["cams_bias72"].to_numpy(dtype=float)
            cams = f["cams_target"].to_numpy(dtype=float)
            pred = np.where(~np.isnan(f["lag0"]), f["lag0"], np.where(np.isnan(bias), cams, cams * bias))
            lo, hi = pred * (1 - FALLBACK_SPREAD), pred * (1 + FALLBACK_SPREAD)

        for i, sid in enumerate(f["station_id"]):
            p, low, high = float(pred[i]), float(lo[i]), float(hi[i])
            if h == 0 and not delayed[i] and not np.isnan(last_fresh[sid]):
                p = float(last_fresh[sid])
                low, high = p * (1 - MEASUREMENT_UNCERTAINTY), p * (1 + MEASUREMENT_UNCERTAINTY)
            if np.isnan(p):
                continue
            age = f["obs_age_h"].iloc[i]
            rows.append({"station_id": sid, "horizon_h": h, "target_ts": issued + timedelta(hours=h),
                         "issued_at": issued, "pm25_pred": round(p, 2), "pm25_low": round(low, 2),
                         "pm25_high": round(high, 2), "model_version": version,
                         "obs_age_h": None if np.isnan(age) else float(age)})
    return rows


def write(rows: list[dict]) -> None:
    if not rows:
        return
    db.upsert("forecasts", rows, ["station_id", "horizon_h", "target_ts", "model_version"])
    db.execute("delete from forecasts_latest")
    db.upsert("forecasts_latest", rows, ["station_id", "horizon_h"])


def run(now: datetime | None = None) -> dict:
    rows = forecast(now)
    write(rows)
    stations = {r["station_id"] for r in rows}
    delayed = {r["station_id"] for r in rows if r["horizon_h"] == 0 and (r["obs_age_h"] is None or r["obs_age_h"] > STALE_AFTER_H)}
    summary = {"rows": len(rows), "stations": len(stations), "delayed_feeds": len(delayed),
               "model_version": rows[0]["model_version"] if rows else None}
    log.info("forecast: %s", summary)
    return summary
