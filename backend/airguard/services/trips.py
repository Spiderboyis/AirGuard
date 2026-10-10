"""Trip analysis: routes + departure options + recommendation in one call, saved for the agent."""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone

from airguard import db
from airguard.engine import assumptions as A
from airguard.engine.departure import decide, evaluate
from airguard.engine.exposure import ForecastUnavailable, prepare, score
from airguard.services import forecasts, routing

log = logging.getLogger("airguard.trips")

_memory: dict[str, dict] = {}   # fallback store if the database is unavailable


def analyze(origin: dict, destination: dict, mode: str, sensitivity: str = "normal", window_h: float = 4,
            max_extra_min: float = 15, max_wait_min: float = 120, origin_name: str | None = None,
            destination_name: str | None = None, save: bool = True) -> dict:
    fld = forecasts.current_field()
    now = forecasts.reference_now(fld)
    now_ts = now.timestamp()
    routes = routing.get_routes((origin["lat"], origin["lon"]), (destination["lat"], destination["lon"]), mode)
    prepared = [prepare(r, fld) for r in routes]

    scores_now = [score(p, fld, now_ts, mode) for p in prepared]
    options = evaluate(prepared, fld, now_ts, mode, window_h=window_h)
    decision = decide(options, sensitivity, max_extra_min=max_extra_min, max_wait_min=max_wait_min)
    rec = decision.recommended
    rec_prepared = next(p for p in prepared if p.route.id == rec.route_id)
    rec_score = score(rec_prepared, fld, rec.depart_ts, mode)

    delayed = [s for s in fld.stations if s.obs_age_h is None or s.obs_age_h > 3]
    result = {
        "trip_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "now": now.isoformat(),
        "origin": {**origin, "name": origin_name},
        "destination": {**destination, "name": destination_name},
        "mode": mode, "mode_label": A.MODE_LABELS[mode], "mode_factor": A.MODE_FACTORS[mode],
        "sensitivity": sensitivity,
        "limits": {"window_h": window_h, "max_extra_min": max_extra_min, "max_wait_min": max_wait_min},
        "routes": [s.to_dict() for s in scores_now],
        "departures": [o.to_dict() for o in options],
        "decision": decision.to_dict(),
        "recommended_route": rec_score.to_dict(),
        "data": {
            "forecast_issued_at": fld.issued_at.isoformat(),
            "model_version": fld.model_version,
            "data_age_min": round((now - fld.issued_at).total_seconds() / 60),
            "stations": len(fld.stations),
            "stations_delayed": len(delayed),
            "snapshot": forecasts.snapshot_mode(),
        },
    }
    if save:
        _save(result, {"origin": origin, "destination": destination, "mode": mode, "sensitivity": sensitivity,
                       "window_h": window_h, "max_extra_min": max_extra_min, "max_wait_min": max_wait_min})
    return result


def _save(result: dict, request: dict) -> None:
    _memory[result["trip_id"]] = result
    if len(_memory) > 200:
        _memory.pop(next(iter(_memory)))
    try:
        db.execute("insert into trips (id, request, result) values (%s, %s, %s)",
                   (result["trip_id"], db.Jsonb(request), db.Jsonb(result)))
    except db.DatabaseUnavailable:
        log.warning("trip %s kept in memory only", result["trip_id"])


def get(trip_id: str) -> dict | None:
    if trip_id in _memory:
        return _memory[trip_id]
    try:
        uuid.UUID(trip_id)
        rows = db.query("select result from trips where id = %s", (trip_id,))
    except (ValueError, db.DatabaseUnavailable):
        return None
    return rows[0]["result"] if rows else None


# ------------------------------------------------------------------------------------------------
# Preview: an unsaved analysis plus a departure strip chart (used by the landing page)
# ------------------------------------------------------------------------------------------------
_preview_cache: dict[str, tuple[float, dict]] = {}
PREVIEW_TTL_S = 300
STRIP_STEP_MIN = 15


def departure_strips(origin: dict, destination: dict, mode: str, route_id: str, window_h: float = 4) -> dict:
    """PM2.5 along one route for every departure on the 15-minute grid: one row per departure,
    one value per 200 m segment. This is the engine's own scenario grid, drawn as a picture."""
    fld = forecasts.current_field()
    now_ts = forecasts.reference_now(fld).timestamp()
    routes = routing.get_routes((origin["lat"], origin["lon"]), (destination["lat"], destination["lon"]), mode)
    route = next((r for r in routes if r.id == route_id), routes[0])
    p = prepare(route, fld)
    rows = []
    for wait in range(0, int(window_h * 60) + 1, STRIP_STEP_MIN):
        t = now_ts + wait * 60
        try:
            s = score(p, fld, t, mode)
        except ForecastUnavailable:
            break
        rows.append({
            "wait_min": wait,
            "depart_at": datetime.fromtimestamp(t, tz=timezone.utc).isoformat(),
            "exposure_index": s.exposure_index, "mean_pm25": s.mean_pm25, "confidence": s.confidence,
            "pm25": [seg["pm25"] for seg in s.segments],
            "minutes": [seg["minutes"] for seg in s.segments],
        })
    return {"route_id": route.id, "label": route.label, "distance_km": round(route.distance_km, 2),
            "duration_min": round(route.duration_min, 1), "rows": rows}


def preview(origin: dict, destination: dict, mode: str, sensitivity: str, window_h: float, max_extra_min: float,
            max_wait_min: float, origin_name: str | None, destination_name: str | None) -> dict:
    fld = forecasts.current_field()
    key = json.dumps([origin, destination, mode, sensitivity, window_h, max_extra_min, max_wait_min,
                      fld.issued_at.isoformat()], sort_keys=True, default=str)
    hit = _preview_cache.get(key)
    if hit and time.monotonic() - hit[0] < PREVIEW_TTL_S:
        return hit[1]
    trip = analyze(origin, destination, mode, sensitivity, window_h, max_extra_min, max_wait_min,
                   origin_name, destination_name, save=False)
    strips = departure_strips(origin, destination, mode, trip["decision"]["recommended"]["route_id"], window_h)
    out = {"trip": trip, "strips": strips}
    _preview_cache[key] = (time.monotonic(), out)
    if len(_preview_cache) > 50:
        _preview_cache.pop(next(iter(_preview_cache)))
    return out
