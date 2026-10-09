import math
import os
from datetime import datetime, timedelta, timezone

import numpy as np

from common.geo import haversine_km

HORIZONS = [int(h) for h in os.environ.get("HORIZONS", "1,3,6,12,24").split(",") if h.strip()]
FEATURES = [
    "now", "lag1", "lag3", "lag6", "lag24", "mean6", "mean24",
    "hod_sin", "hod_cos", "dow",
    "temp", "rh", "wind", "wind_u", "wind_v", "blh", "fires_upwind",
    "nbr_mean",
]
NAN = float("nan")
IST = timezone(timedelta(hours=5, minutes=30))


def hour(ts: str) -> datetime:
    """UTC ISO string -> naive datetime floored to the hour. All inputs must be UTC."""
    d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    if d.tzinfo is not None:
        d = d.astimezone(timezone.utc).replace(tzinfo=None)
    return d.replace(minute=0, second=0, microsecond=0)


def local_dt(t: datetime) -> datetime:
    """Naive UTC hour -> India Standard Time. Delhi's diurnal cycle is local, not UTC."""
    aware = t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t
    return aware.astimezone(IST)


def neighbors(stations, k=3):
    out = {}
    for s in stations:
        ranked = sorted(
            (haversine_km(s["lat"], s["lon"], o["lat"], o["lon"]), o["id"])
            for o in stations if o["id"] != s["id"]
        )
        out[s["id"]] = [i for _, i in ranked[:k]]
    return out


def interval(p, q10, q90):
    """Forecast range with the guarantee 0 <= low <= p <= high."""
    return max(0.0, min(p, p + q10)), max(p, p + q90)


def _uv(speed, deg):
    if speed is None or deg is None:
        return NAN, NAN
    r = math.radians(deg)  # wind blows FROM deg; u/v point where it blows toward
    return -speed * math.sin(r), -speed * math.cos(r)


def _f(x):
    return NAN if x is None else float(x)


def row(sid, t, h, pm, wx, nbrs):
    """Feature vector for station sid at issue time t. None when the current value or weather is missing.

    h is accepted so train and serve call the same function. The horizon is not a column:
    each horizon has its own model. Hour-of-day is the issue hour in IST.
    """
    del h  # horizon-specific models, not a feature
    s = pm.get(sid) or {}
    now = s.get(t)
    w = (wx.get(sid) or {}).get(t)
    if now is None or w is None:
        return None
    lag = lambda k: s.get(t - timedelta(hours=k), NAN)
    last6 = [v for k in range(6) if (v := s.get(t - timedelta(hours=k))) is not None]
    last24 = [v for k in range(24) if (v := s.get(t - timedelta(hours=k))) is not None]
    nb = [v for n in nbrs.get(sid, []) if (v := (pm.get(n) or {}).get(t)) is not None]
    u, v_ = _uv(w.get("wind_speed"), w.get("wind_dir"))
    local = local_dt(t)
    return [
        now, lag(1), lag(3), lag(6), lag(24),
        sum(last6) / len(last6) if len(last6) >= 4 else NAN,
        sum(last24) / len(last24) if len(last24) >= 16 else NAN,
        math.sin(2 * math.pi * local.hour / 24), math.cos(2 * math.pi * local.hour / 24), float(local.weekday()),
        _f(w.get("temp")), _f(w.get("humidity")), _f(w.get("wind_speed")), u, v_, _f(w.get("blh")), _f(w.get("fires_upwind")),
        sum(nb) / len(nb) if nb else NAN,
    ]


def build_dataset(stations, pm, wx, issue_times, h):
    nbrs = neighbors(stations)
    X, y, meta = [], [], []
    for st in stations:
        sid = st["id"]
        for t in issue_times:
            target = (pm.get(sid) or {}).get(t + timedelta(hours=h))
            if target is None:
                continue
            x = row(sid, t, h, pm, wx, nbrs)
            if x is not None:
                X.append(x)
                y.append(target)
                meta.append((sid, t))
    return np.array(X, dtype=float).reshape(-1, len(FEATURES)), np.array(y, dtype=float), meta
