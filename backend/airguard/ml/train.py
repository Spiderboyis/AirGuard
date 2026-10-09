"""Train one global XGBoost model per horizon and backtest it on held-out weeks.

    python -m airguard.ml.train [--test-days 14] [--calib-days 7]

Split by time, never randomly:  [ train ......... | 24 h gap | calibration | test ]
* train        fits the models (log-PM2.5 target, early stopping on calibration)
* calibration  sets the prediction intervals: the 10th/90th percentiles of y / y_hat (split conformal)
* test         is reported, in two modes:
    normal   the station's own feed is current; compared with persistence, the station's
             hour-of-day mean and the raw CAMS forecast
    delayed  the station's own feed is blanked (as in a CPCB outage); compared with hour-of-day
             mean and raw CAMS

Outputs models/<version>/h{h}.json + meta.json, and rows in `models` and `eval_metrics`.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from airguard import db
from airguard.config import settings
from airguard.ml import data
from airguard.ml.features import FEATURES, HORIZONS, Inputs, build_frame

log = logging.getLogger("airguard.train")

DELAY_SHARE = 0.25     # share of training rows with the station's own feed blanked
SAMPLE_EVERY_H = 2     # training issue times are thinned to keep memory modest
QUANTILES = (0.1, 0.9)
XGB_PARAMS = dict(n_estimators=1500, learning_rate=0.04, max_depth=7, min_child_weight=10, subsample=0.8,
                  colsample_bytree=0.8, reg_lambda=1.0, tree_method="hist", n_jobs=8,
                  early_stopping_rounds=60, eval_metric="mae")


def _metrics(y: np.ndarray, p: np.ndarray) -> tuple[float, float]:
    e = p - y
    return float(np.mean(np.abs(e))), float(np.sqrt(np.mean(e ** 2)))


def _hourly_mean_table(x: Inputs, train_end: pd.Timestamp) -> pd.DataFrame:
    pm = x.pm25.loc[:train_end]
    ist_hour = ((pm.index.hour + 5) + (pm.index.minute + 30) // 60) % 24
    return pm.groupby(ist_hour).mean()          # rows: IST hour, columns: station


def _hourly_mean(tab: pd.DataFrame, frame: pd.DataFrame, horizon: int) -> np.ndarray:
    target = pd.DatetimeIndex(frame["t0"]).tz_localize("UTC") + pd.Timedelta(hours=horizon) \
        if pd.DatetimeIndex(frame["t0"]).tz is None else pd.DatetimeIndex(frame["t0"]) + pd.Timedelta(hours=horizon)
    hours = ((target.hour + 5) + (target.minute + 30) // 60) % 24
    stacked = tab.stack()
    keys = pd.MultiIndex.from_arrays([hours, frame["station_id"].to_numpy()])
    return stacked.reindex(keys).to_numpy(dtype=float)


def _frames(x: Inputs, t0s: pd.DatetimeIndex, h: int, delayed: bool | float, seed: int) -> pd.DataFrame:
    n = len(t0s) * x.pm25.shape[1]
    if delayed is True:
        mask = np.ones(n, dtype=bool)
    elif delayed is False:
        mask = None
    else:
        mask = np.random.default_rng(seed).random(n) < delayed
    f = build_frame(x, t0s, h, mask=mask)
    return f[f["y"].notna()].reset_index(drop=True)


def train(test_days: int = 14, calib_days: int = 7, history_days: int = 365) -> dict:
    t_start = time.monotonic()
    rng_end = db.query("select max(ts) as ts from measurements where pollutant = 'pm25'")[0]["ts"]
    if rng_end is None:
        raise SystemExit("No measurements yet; run `make backfill` first.")
    end = pd.Timestamp(rng_end).tz_convert("UTC")
    start = end - pd.Timedelta(days=history_days)
    x = data.load_inputs(start.to_pydatetime(), (end + pd.Timedelta(hours=25)).to_pydatetime())
    idx = x.pm25.index
    test_start = end - pd.Timedelta(days=test_days)
    calib_start = test_start - pd.Timedelta(days=calib_days)
    train_end = calib_start - pd.Timedelta(hours=24)
    version = "v" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    out_dir = settings().model_path / version
    out_dir.mkdir(parents=True, exist_ok=True)
    hm_table = _hourly_mean_table(x, train_end)
    log.info("data %s .. %s | stations %d | train < %s | calib %s | test %s .. %s", idx[0], idx[-1],
             x.pm25.shape[1], train_end, calib_start, test_start, end)

    meta = {"version": version, "horizons": HORIZONS, "features": FEATURES, "log_target": True,
            "quantiles": {}, "data_source": "openaq", "trained_at": datetime.now(timezone.utc).isoformat(),
            "train_start": str(idx[0]), "train_end": str(train_end), "test_start": str(test_start),
            "test_end": str(end), "n_stations": int(x.pm25.shape[1]), "delay_share": DELAY_SHARE}
    eval_rows = []

    for h in HORIZONS:
        t_train = idx[(idx < train_end - pd.Timedelta(hours=h))][h % SAMPLE_EVERY_H::SAMPLE_EVERY_H]
        t_cal = idx[(idx >= calib_start) & (idx < test_start - pd.Timedelta(hours=h))]
        t_test = idx[(idx >= test_start) & (idx <= end - pd.Timedelta(hours=h))]
        # Horizon 0 is a nowcast: it only exists for stations whose feed is delayed.
        share = 1.0 if h == 0 else DELAY_SHARE
        tr = _frames(x, t_train, h, True if h == 0 else share, seed=h)
        cal_n = None if h == 0 else _frames(x, t_cal, h, False, seed=100 + h)
        cal_d = _frames(x, t_cal, h, True, seed=200 + h)
        te_n = None if h == 0 else _frames(x, t_test, h, False, seed=300 + h)
        te_d = _frames(x, t_test, h, True, seed=400 + h)
        cal = pd.concat([f for f in (cal_n, cal_d) if f is not None], ignore_index=True)

        model = xgb.XGBRegressor(**XGB_PARAMS, random_state=h)
        model.fit(tr[FEATURES], np.log1p(tr["y"]), eval_set=[(cal[FEATURES], np.log1p(cal["y"]))], verbose=False)
        model.save_model(out_dir / f"h{h}.json")

        def predict(f, model=model):
            return np.expm1(model.predict(f[FEATURES])).clip(min=0)

        q = {}
        for mode, cf in (("normal", cal_n), ("delayed", cal_d)):
            if cf is None or cf.empty:
                continue
            ratio = cf["y"].to_numpy() / np.maximum(predict(cf), 1.0)
            q[mode] = [float(np.quantile(ratio, QUANTILES[0])), float(np.quantile(ratio, QUANTILES[1]))]
        meta["quantiles"][str(h)] = q

        for mode, tf in (("normal", te_n), ("delayed", te_d)):
            if tf is None or tf.empty:
                continue
            p = predict(tf)
            y = tf["y"].to_numpy(dtype=float)
            hm = _hourly_mean(hm_table, tf, h)
            cams = tf["cams_target"].to_numpy(dtype=float)
            pers = tf["lag0"].to_numpy(dtype=float)
            keep = ~np.isnan(hm) & ~np.isnan(cams)
            if mode == "normal":
                keep &= ~np.isnan(pers)
            y, p, hm, cams, pers = y[keep], p[keep], hm[keep], cams[keep], pers[keep]
            lo, hi = p * q[mode][0], p * q[mode][1]
            row = {"model_version": version, "horizon_h": h, "mode": mode, "n_samples": int(keep.sum()),
                   "interval_coverage": float(np.mean((y >= lo) & (y <= hi))),
                   "interval_width": float(np.mean(hi - lo))}
            row["mae"], row["rmse"] = _metrics(y, p)
            row["baseline_hourly_mean_mae"], row["baseline_hourly_mean_rmse"] = _metrics(y, hm)
            row["baseline_cams_mae"], row["baseline_cams_rmse"] = _metrics(y, cams)
            if mode == "normal":
                row["baseline_persistence_mae"], row["baseline_persistence_rmse"] = _metrics(y, pers)
            eval_rows.append(row)
            log.info("h=%-2d %-7s n=%-6d MAE %.1f | persistence %s | hourly-mean %.1f | CAMS %.1f | "
                     "coverage %.0f%% | trees %d", h, mode, row["n_samples"], row["mae"],
                     f"{row['baseline_persistence_mae']:.1f}" if mode == "normal" else "  -  ",
                     row["baseline_hourly_mean_mae"], row["baseline_cams_mae"], 100 * row["interval_coverage"],
                     model.best_iteration + 1)

    meta["metrics"] = eval_rows
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    db.upsert("models", [{
        "model_version": version, "data_source": "openaq", "horizons": HORIZONS, "features": FEATURES,
        "train_start": idx[0].to_pydatetime(), "train_end": train_end.to_pydatetime(),
        "test_start": test_start.to_pydatetime(), "test_end": end.to_pydatetime(),
        "n_stations": int(x.pm25.shape[1]),
        "notes": f"XGBoost per horizon, log target, {int(DELAY_SHARE * 100)}% of rows trained with a delayed feed",
        "summary": {"quantiles": meta["quantiles"]},
    }], ["model_version"])
    db.upsert("eval_metrics", eval_rows, ["model_version", "horizon_h", "mode"])
    log.info("saved %s in %.1f min", out_dir, (time.monotonic() - t_start) / 60)
    return meta


def latest_model_dir() -> Path | None:
    root = settings().model_path
    if settings().model_version:
        d = root / settings().model_version
        return d if (d / "meta.json").exists() else None
    dirs = sorted(d for d in root.glob("v*") if (d / "meta.json").exists())
    return dirs[-1] if dirs else None


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--test-days", type=int, default=14)
    p.add_argument("--calib-days", type=int, default=7)
    p.add_argument("--history-days", type=int, default=365)
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    train(a.test_days, a.calib_days, a.history_days)


if __name__ == "__main__":
    main()

