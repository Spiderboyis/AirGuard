"""Access to the current forecast field (database, or a frozen snapshot for demos)."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from airguard import db
from airguard.config import REPO_ROOT, settings
from airguard.engine.field import ForecastField

CACHE_S = 60.0
_lock = threading.Lock()
_cached: dict = {}


class NoForecast(RuntimeError):
    pass


def _snapshot_path() -> Path | None:
    s = settings().demo_snapshot
    if not s:
        return None
    p = Path(s)
    return p if p.is_absolute() else REPO_ROOT / p


def snapshot_mode() -> bool:
    return _snapshot_path() is not None


def _load_db() -> ForecastField:
    stations = db.query("select id, name, lat, lon, provider, is_monitor from stations where active")
    rows = db.query("select station_id, horizon_h, target_ts, issued_at, pm25_pred, pm25_low, pm25_high, "
                    "model_version, obs_age_h from forecasts_latest")
    if not rows:
        raise NoForecast("no forecast has been issued yet; run `make forecast`")
    fld = ForecastField.from_rows(stations, rows)
    fld.meta["now"] = None
    return fld


def current_field() -> ForecastField:
    with _lock:
        if _cached.get("at") and time.monotonic() - _cached["at"] < CACHE_S:
            return _cached["field"]
        path = _snapshot_path()
        if path:
            fld = ForecastField.from_dict(json.loads(path.read_text()))
        else:
            fld = _load_db()
        _cached.update(at=time.monotonic(), field=fld)
        return fld


def clear_cache() -> None:
    with _lock:
        _cached.clear()


def reference_now(fld: ForecastField) -> datetime:
    """The 'now' trips are planned from: real time, or the frozen time stored in a snapshot."""
    frozen = fld.meta.get("now")
    if frozen:
        return datetime.fromisoformat(frozen)
    cov_start, cov_end = fld.coverage
    real_now = datetime.now(timezone.utc)
    if fld.stations and cov_end > cov_start:
        real_ts = real_now.timestamp()
        if real_ts < cov_start or real_ts > cov_end - 3600:
            return datetime.fromtimestamp(cov_start, tz=timezone.utc)
    return real_now


def station_summaries(fld: ForecastField) -> list[dict]:
    """Current value and next-24h outlook for every station (for the map layer)."""
    now = reference_now(fld).timestamp()
    out = []
    for s in fld.stations:
        pts = [{"ts": datetime.fromtimestamp(t, tz=timezone.utc).isoformat(), "pm25": round(float(p), 1),
                "low": round(float(lo), 1), "high": round(float(hi), 1)}
               for t, p, lo, hi in zip(s.times, s.pred, s.low, s.high)]
        cur = fld.point(s.lat, s.lon, now) if s.times[0] - 3600 <= now <= s.times[-1] else None
        measured = s.obs_age_h is not None and s.obs_age_h <= 3
        out.append({
            "id": s.station_id, "name": s.name, "lat": s.lat, "lon": s.lon, "provider": s.provider,
            "is_monitor": s.is_monitor, "pm25_now": round(float(s.pred[0]), 1),
            "pm25_interp_now": round(cur["pm25"], 1) if cur and cur["pm25"] is not None else None,
            "measured": measured, "obs_age_h": s.obs_age_h, "series": pts,
        })
    return out
