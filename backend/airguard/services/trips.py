"""Trip analysis: routes + departure options + recommendation in one call, saved for the agent."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from airguard import db
from airguard.engine import assumptions as A
from airguard.engine.departure import decide, evaluate
from airguard.engine.exposure import prepare, score
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
