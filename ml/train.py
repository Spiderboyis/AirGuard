import json
import os
from datetime import timedelta

import numpy as np
import xgboost as xgb
from xgboost.callback import EarlyStopping

from common import db
from ml.features import FEATURES, HORIZONS, build_dataset, hour, local_dt, neighbors

VERSION = os.environ.get("MODEL_VERSION", "v1")
DROP = set(filter(None, os.environ.get("DROP_FEATURES", "").split(",")))


def active_features(drop=None):
    """Column order after an ablation. `now` is the persistence baseline and is never dropped."""
    skipped = set(drop if drop is not None else DROP) - {"now"}
    return [f for f in FEATURES if f not in skipped]


def paged(table, page=1000, **params):
    return db.select_all(table, page=page, **params)


def load():
    stations = db.select("stations", select="id,name,lat,lon,sensor_id")
    pm, wx = {}, {}
    for s in stations:
        sid = s["id"]
        rows = paged("measurements", station_id=f"eq.{sid}", pollutant="eq.pm25", select="ts,value", order="ts.asc")
        pm[sid] = {hour(r["ts"]): r["value"] for r in rows}
        w = paged("weather", station_id=f"eq.{sid}", select="ts,temp,humidity,wind_speed,wind_dir,blh,fires_upwind", order="ts.asc")
        wx[sid] = {hour(r["ts"]): r for r in w}
    return stations, pm, wx


def mae(a, b):
    return float(np.mean(np.abs(a - b)))


def rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


def main():
    stations, pm, wx = load()
    stations = [s for s in stations if len(pm.get(s["id"], {})) > 24 * 60]
    print(f"{len(stations)} stations have more than 60 days of hourly PM2.5")
    if len(stations) < 3:
        raise SystemExit("Too few stations with enough history. Check the backfill, narrow the area, or lower the 60-day rule.")
    hours = sorted({t for s in stations for t in pm[s["id"]]})
    end = hours[-1]
    test_start = end - timedelta(days=14)
    val_start = test_start - timedelta(days=14)
    os.makedirs(f"models/{VERSION}", exist_ok=True)
    names = active_features()
    cols = [FEATURES.index(f) for f in names]
    now_idx = names.index("now")
    trees = int(os.environ.get("MODEL_TREES", "600"))
    residual_q, rows_out = {}, []
    for h in HORIZONS:
        X, y, meta = build_dataset(stations, pm, wx, hours, h)
        if len(y) == 0:
            print(f"+{h}h: no usable rows (missing history or weather). Skipping it.")
            continue
        X = X[:, cols]
        tgt = [t + timedelta(hours=h) for _, t in meta]
        tr = np.array([a < val_start for a in tgt])
        va = np.array([t >= val_start and a < test_start for (_, t), a in zip(meta, tgt)])
        te = np.array([t >= test_start for _, t in meta])
        n_tr, n_va, n_te = int(tr.sum()), int(va.sum()), int(te.sum())
        print(f"+{h}h: {n_tr} train, {n_va} validation, {n_te} test rows")
        if min(n_tr, n_va, n_te) < 200:
            print(f"  skipping +{h}h: need at least 200 rows in each split. Remove it from HORIZONS.")
            continue
        # XGBoost 3 takes early stopping as a callback. save_best keeps the best iteration.
        model = xgb.XGBRegressor(
            n_estimators=trees, learning_rate=0.05, max_depth=6, subsample=0.8,
            colsample_bytree=0.8, min_child_weight=5, tree_method="hist", n_jobs=-1, random_state=0,
            callbacks=[EarlyStopping(rounds=30, save_best=True)],
        )
        model.fit(X[tr], y[tr], eval_set=[(X[va], y[va])], verbose=False)
        res = y[va] - np.maximum(0.0, model.predict(X[va]))
        residual_q[str(h)] = [float(np.quantile(res, 0.1)), float(np.quantile(res, 0.9))]
        print({"horizon_h": h, "val_mae": round(float(np.mean(np.abs(res))), 2)})
        hod = {}
        for i in np.where(tr)[0]:
            sid, t = meta[i]
            hod.setdefault((sid, local_dt(t + timedelta(hours=h)).hour), []).append(y[i])
        hod = {k: float(np.mean(v)) for k, v in hod.items()}
        gm = float(np.mean(y[tr]))
        idx = np.where(te)[0]
        p_hod = np.array([hod.get((meta[i][0], local_dt(meta[i][1] + timedelta(hours=h)).hour), gm) for i in idx])
        p_model, p_pers, yt = np.maximum(0.0, model.predict(X[te])), X[te][:, now_idx], y[te]
        q10, q90 = residual_q[str(h)]
        lo = np.maximum(0.0, np.minimum(p_model, p_model + q10))
        hi = np.maximum(p_model, p_model + q90)
        cov, wid = float(np.mean((yt >= lo) & (yt <= hi))), float(np.mean(hi - lo))
        rows_out.append({
            "model_version": VERSION, "horizon_h": h,
            "mae": round(mae(yt, p_model), 2), "rmse": round(rmse(yt, p_model), 2),
            "baseline_persistence_mae": round(mae(yt, p_pers), 2),
            "baseline_hourly_mean_mae": round(mae(yt, p_hod), 2),
            "baseline_persistence_rmse": round(rmse(yt, p_pers), 2),
            "baseline_hourly_mean_rmse": round(rmse(yt, p_hod), 2),
            "interval_coverage": round(cov, 3), "interval_width": round(wid, 2), "n_samples": int(te.sum()),
        })
        print(rows_out[-1])
        model.save_model(f"models/{VERSION}/h{h}.json")
    if not residual_q:
        raise SystemExit("No horizon had enough data. Fix the data first.")
    meta_out = {
        "version": VERSION,
        "features": names,
        "horizons": sorted(int(h) for h in residual_q),
        "residual_q": residual_q,
        "stations": stations,
        "neighbors": neighbors(stations),
        "trained_through": str(end),
        "test_start": str(test_start),
        "clock": "Asia/Kolkata",
    }
    with open(f"models/{VERSION}/meta.json", "w") as fh:
        json.dump(meta_out, fh)
    db.upsert("eval_metrics", rows_out, "model_version,horizon_h")
    return rows_out


if __name__ == "__main__":
    main()
