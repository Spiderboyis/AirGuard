import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

import numpy as np
import xgboost as xgb

from common import db
from common.config import cfg
from ingestion import fires, openaq, weather
from ml.features import FEATURES, hour, interval, row

_M = {}


def load_models():
    if _M:
        return _M
    version = os.environ.get("MODEL_VERSION", "v1")
    directory = os.environ.get("MODEL_DIR")
    if not directory:
        local = os.path.join("models", version)
        if os.path.exists(os.path.join(local, "meta.json")) and not os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            directory = local
    if not directory:
        import boto3

        s3, directory = boto3.client("s3"), tempfile.mkdtemp()
        bucket = cfg()["MODEL_BUCKET"]
        s3.download_file(bucket, f"models/{version}/meta.json", f"{directory}/meta.json")
        meta = json.load(open(f"{directory}/meta.json"))
        for h in meta["horizons"]:
            s3.download_file(bucket, f"models/{version}/h{h}.json", f"{directory}/h{h}.json")
    if not os.path.exists(os.path.join(directory, "meta.json")):
        raise FileNotFoundError(f"No model metadata in {directory}. Train first or set MODEL_DIR.")
    meta = json.load(open(os.path.join(directory, "meta.json")))
    models = {}
    for h in meta["horizons"]:
        model = xgb.XGBRegressor()
        model.load_model(os.path.join(directory, f"h{h}.json"))
        models[int(h)] = model
    _M.clear()
    _M.update(meta=meta, models=models, version=meta.get("version", version))
    return _M


def _stored_frames(stations, now_h):
    cutoff = now_h - timedelta(hours=36)
    pm = {s["id"]: {} for s in stations}
    for s in stations:
        rows = db.select_all(
            "measurements", select="ts,value", station_id=f"eq.{s['id']}",
            pollutant="eq.pm25", order="ts.asc",
        )
        pm[s["id"]] = {hour(r["ts"]): r["value"] for r in rows if hour(r["ts"]) >= cutoff}
    wx = {s["id"]: {} for s in stations}
    weather_cutoff = now_h - timedelta(hours=48)
    for w in db.select_all("weather", select="station_id,ts,temp,humidity,wind_speed,wind_dir,blh,fires_upwind", order="ts.asc"):
        if w["station_id"] not in wx:
            continue
        t = hour(w["ts"])
        if weather_cutoff <= t <= now_h:
            wx[w["station_id"]][t] = w
    return pm, wx


def _refresh(stations, now, now_h):
    pm = {}
    for s in stations:
        rows = openaq.hourly_pm25(s["sensor_id"], (now - timedelta(hours=36)).isoformat(), now.isoformat())
        pm[s["id"]] = {hour(r["ts"]): r["value"] for r in rows}
        if rows:
            db.upsert(
                "measurements",
                [{"station_id": s["id"], "pollutant": "pm25", "unit": "µg/m³", **r} for r in rows],
                "station_id,pollutant,ts",
            )
    wrows = weather.fetch_recent(stations, past_days=2, forecast_days=1)
    start_d, end_d = (now_h - timedelta(days=4)).date(), now_h.date()
    try:
        fire_rows = fires.fetch(5) if (cfg().get("FIRMS_MAP_KEY") or "").strip() else []
        table = fires.sector_table(stations, fire_rows, start_d, end_d)
    except Exception as exc:
        print("fire refresh skipped:", exc)
        table = fires.sector_table(stations, [], start_d, end_d)
    wx = {s["id"]: {} for s in stations}
    stored = []
    for w in wrows:
        t = hour(w["ts"])
        w["fires_upwind"] = fires.upwind_count(table, w["station_id"], start_d, t, w.get("wind_dir"))
        wx[w["station_id"]][t] = w
        if t <= now_h:
            stored.append(w)
    if stored:
        db.upsert("weather", stored, "station_id,ts")
    return pm, wx


def _predict(meta, models, version, stations, nbrs, pm, wx, now):
    out, gen = [], now.isoformat()
    now_h = now.replace(tzinfo=None, minute=0, second=0, microsecond=0)
    for s in stations:
        sid = s["id"]
        if not pm.get(sid):
            continue
        t0 = max(pm[sid])
        if now_h - t0 > timedelta(hours=6):
            continue
        base = {"station_id": sid, "model_version": version, "generated_at": gen}
        observed = float(pm[sid][t0])
        out.append({
            **base, "horizon_h": 0, "target_ts": t0.replace(tzinfo=timezone.utc).isoformat(),
            "pm25_pred": observed, "pm25_low": observed, "pm25_high": observed,
        })
        for h in meta["horizons"]:
            h = int(h)
            vector = row(sid, t0, h, pm, wx, nbrs)
            if vector is None:
                continue
            try:
                vector = [vector[FEATURES.index(f)] for f in meta["features"]]
            except ValueError:
                continue
            if h not in models:
                continue
            pred = max(0.0, float(models[h].predict(np.array([vector]))[0]))
            q10, q90 = meta["residual_q"][str(h)]
            low, high = interval(pred, q10, q90)
            out.append({
                **base, "horizon_h": h,
                "target_ts": (t0 + timedelta(hours=h)).replace(tzinfo=timezone.utc).isoformat(),
                "pm25_pred": pred, "pm25_low": low, "pm25_high": high,
            })
    return out


def lambda_handler(event, context):
    del event, context
    bundle = load_models()
    meta, models = bundle["meta"], bundle["models"]
    stations, nbrs = meta["stations"], meta["neighbors"]
    now = datetime.now(timezone.utc)
    now_h = now.replace(tzinfo=None, minute=0, second=0, microsecond=0)
    offline = os.environ.get("AIRGUARD_OFFLINE_INGEST") == "1" or not (cfg().get("OPENAQ_API_KEY") or "").strip()
    if offline:
        print("ingestion: using measurements and weather already in the database")
        pm, wx = _stored_frames(stations, now_h)
    else:
        pm, wx = _refresh(stations, now, now_h)
    out = _predict(meta, models, bundle["version"], stations, nbrs, pm, wx, now)
    if out:
        db.upsert("forecasts_latest", out, "station_id,horizon_h")
        db.upsert("forecasts", out, "station_id,horizon_h,target_ts,model_version")
    return {"stations": len({o["station_id"] for o in out}), "rows": len(out), "offline": offline}


def reset_models():
    _M.clear()
