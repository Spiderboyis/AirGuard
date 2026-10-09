import math
from dataclasses import dataclass

from common.geo import haversine_km

MODES = {
    "walk": {"factor": 1.0, "ors_profile": "foot-walking", "osrm_profile": "foot"},
    "cycle": {"factor": 1.6, "ors_profile": "cycling-regular", "osrm_profile": "bike"},
    "car": {"factor": 0.5, "ors_profile": "driving-car", "osrm_profile": "driving"},
}
# Illustrative AirGuard levels for the mean forecast PM2.5 on a route, not official AQI categories.
# CPCB's PM2.5 categories are defined on 24-hour averages, so they are not applied to a trip.
RISK_BANDS = [(30, "low"), (60, "moderate"), (90, "elevated"), (120, "high"), (250, "very_high"), (float("inf"), "extreme")]
LEVEL_COLORS = {
    "low": "#2e7d32",
    "moderate": "#9e9d24",
    "elevated": "#f9a825",
    "high": "#e65100",
    "very_high": "#b71c1c",
    "extreme": "#4a148c",
}
PREFERENCES = {  # extra minutes accepted per 10% reduction in exposure (illustrative)
    "normal": 4.0,
    "sensitive": 7.0,
    "high": 10.0,
}


@dataclass
class Station:
    id: str
    lat: float
    lon: float
    series: list  # [(hours_from_now, pm25, low, high), ...] sorted by hours_from_now


def at_hour(series, h):
    """Linear interpolation in time; held flat outside the series."""
    if not series:
        raise ValueError("Station has no forecast series.")
    if h <= series[0][0]:
        return tuple(series[0][1:])
    for (h0, *v0), (h1, *v1) in zip(series, series[1:]):
        if h1 <= h0:
            continue
        if h <= h1:
            w = (h - h0) / (h1 - h0)
            return tuple(a + w * (b - a) for a, b in zip(v0, v1))
    return tuple(series[-1][1:])


def idw(lat, lon, stations, h, k=4, power=2.0):
    if not stations:
        raise ValueError("No usable air-quality stations right now.")
    ranked = sorted(((haversine_km(lat, lon, s.lat, s.lon), s) for s in stations), key=lambda x: x[0])[:k]
    nearest_km = ranked[0][0]
    if nearest_km < 0.05:
        pm, lo, hi = at_hour(ranked[0][1].series, h)
        return pm, lo, hi, nearest_km
    wts = [1 / d ** power for d, _ in ranked]
    vals = [at_hour(s.series, h) for _, s in ranked]
    tot = sum(wts)
    pm, lo, hi = (sum(w * v[i] for w, v in zip(wts, vals)) / tot for i in range(3))
    return pm, lo, hi, nearest_km


def _cumulative(coords):
    pts = [(lat, lon) for lon, lat in coords]
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + haversine_km(a[0], a[1], b[0], b[1]) * 1000)
    return pts, cum


def resample(coords, step_m=200):
    """coords: [(lon, lat), ...] -> ([(lat, lon, length_m), ...] segment midpoints, total_m)."""
    if not coords:
        raise ValueError("Route geometry is missing.")
    pts, cum = _cumulative(coords)
    total = cum[-1]
    if total == 0 or len(pts) < 2:
        return [(pts[0][0], pts[0][1], 0.0)], 0.0
    n = max(1, round(total / step_m))
    out, j = [], 0
    for i in range(n):
        target = (i + 0.5) * total / n
        while j < len(cum) - 2 and cum[j + 1] < target:
            j += 1
        seg = cum[j + 1] - cum[j]
        f = 0.0 if seg == 0 else (target - cum[j]) / seg
        out.append((pts[j][0] + f * (pts[j + 1][0] - pts[j][0]), pts[j][1] + f * (pts[j + 1][1] - pts[j][1]), total / n))
    return out, total


def segment_lines(coords, n):
    """Split the route into n equal-length pieces and return each piece's own points as [[lon, lat], ...]."""
    if not coords:
        return []
    pts, cum = _cumulative(coords)
    total = cum[-1]
    if total == 0 or len(pts) < 2 or n < 1:
        return [[[coords[0][0], coords[0][1]]] for _ in range(max(n, 1))]

    def at(d):
        j = 0
        while j < len(cum) - 2 and cum[j + 1] < d:
            j += 1
        seg = cum[j + 1] - cum[j]
        f = 0.0 if seg == 0 else min(1.0, max(0.0, (d - cum[j]) / seg))
        return [pts[j][1] + f * (pts[j + 1][1] - pts[j][1]), pts[j][0] + f * (pts[j + 1][0] - pts[j][0])]

    lines = []
    for i in range(n):
        d0, d1 = i * total / n, (i + 1) * total / n
        # Include a vertex on the cut in the piece that ends there, so a corner is not dropped.
        inner = [[pts[k][1], pts[k][0]] for k in range(1, len(pts) - 1) if d0 < cum[k] <= d1]
        line = [at(d0)] + inner + [at(d1)]
        deduped = [line[0]]
        for point in line[1:]:
            if point != deduped[-1]:
                deduped.append(point)
        lines.append(deduped)
    return lines


def confidence(pm, lo, hi, nearest_km):
    """Heuristic data-reliability score, not a probability."""
    c_dist = math.exp(-nearest_km / 8.0)  # 1.0 at a station, about 0.37 at 8 km
    c_width = 1.0 / (1.0 + (hi - lo) / max(pm, 10.0))
    return 0.6 * c_dist + 0.4 * c_width


def level_config():
    """Single source of truth for levels, cutoffs and map colours. Served at /config."""
    return [{"name": n, "max": None if c == float("inf") else c, "color": LEVEL_COLORS[n]} for c, n in RISK_BANDS]


def risk_label(mean_pm):
    return next(name for cutoff, name in RISK_BANDS if mean_pm <= cutoff)


def score_route(coords, duration_s, mode, depart_in_h, stations, step_m=200):
    if mode not in MODES:
        raise ValueError("Mode must be walk, cycle or car.")
    if duration_s <= 0:
        raise ValueError("Route duration must be positive.")
    segs, total_m = resample(coords, step_m)
    if not segs:
        raise ValueError("Route geometry is missing.")
    lines = segment_lines(coords, len(segs))
    seg_s = duration_s / len(segs)
    factor = MODES[mode]["factor"]
    exposure_index = pm_minutes = conf_sum = 0.0
    out = []
    for i, (lat, lon, _) in enumerate(segs):
        t_h = depart_in_h + (i + 0.5) * seg_s / 3600
        pm, lo, hi, d_km = idw(lat, lon, stations, t_h)
        minutes = seg_s / 60
        exposure_index += pm * minutes * factor
        pm_minutes += pm * minutes
        conf_sum += confidence(pm, lo, hi, d_km)
        out.append({
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "pm25": round(pm, 1),
            "minutes": round(minutes, 2),
            "line": [[round(x, 5), round(y, 5)] for x, y in lines[i]],
        })
    mean_pm = pm_minutes / (duration_s / 60)
    return {
        "duration_min": round(duration_s / 60, 1),
        "distance_km": round(total_m / 1000, 2),
        "exposure_index": round(exposure_index, 1),
        "mean_pm25": round(mean_pm, 1),
        "risk": risk_label(mean_pm),
        "confidence": round(conf_sum / len(segs), 2),
        "segments": out,
    }


def choose(options, sensitivity="normal", max_extra_min=15, max_wait_min=120):
    """Pick the lowest-exposure option whose extra time is justified.

    Sensitivity changes only this decision rule, never the exposure estimate.
    The fastest leave-now option always qualifies, so there is always a recommendation.
    """
    if not options:
        raise ValueError("No departure options to compare.")
    leave_now = [o for o in options if o["wait_min"] == 0]
    if not leave_now:
        raise ValueError("The departure search has no leave-now option to compare against.")
    base = min(leave_now, key=lambda o: o["duration_min"])
    k = PREFERENCES.get(sensitivity, PREFERENCES["normal"])
    acceptable = []
    for o in options:
        extra = o["wait_min"] + o["duration_min"] - base["duration_min"]
        gain = 100 * (base["exposure_index"] - o["exposure_index"]) / base["exposure_index"] if base["exposure_index"] else 0.0
        if o["wait_min"] <= max_wait_min and extra <= max_extra_min and extra <= k * gain / 10:
            acceptable.append({**o, "extra_min": round(extra, 1), "exposure_change_pct": round(-gain, 1)})
    if not acceptable:
        acceptable = [{**base, "extra_min": 0.0, "exposure_change_pct": 0.0}]
    chosen = min(acceptable, key=lambda o: (o["exposure_index"], o["extra_min"]))
    return {
        "options": options,
        "baseline": base,
        "recommended": chosen,
        "delta": {"exposure_index_pct": chosen["exposure_change_pct"], "arrival_min": chosen["extra_min"]},
        "preference": {
            "sensitivity": sensitivity if sensitivity in PREFERENCES else "normal",
            "minutes_per_10pct": k,
            "max_extra_min": max_extra_min,
            "max_wait_min": max_wait_min,
        },
    }


def best_departure(routes, mode, stations, earliest_in_h=0.0, window_h=4.0, max_wait_min=120, step_min=15,
                   sensitivity="normal", max_extra_min=15):
    """routes: [{'id', 'coords', 'duration_s'}]. Evaluates every route at each 15-minute step."""
    if not routes:
        raise ValueError("No route found between those places.")
    window_h = min(float(window_h), 6.0)
    options, t = [], float(earliest_in_h)
    end = earliest_in_h + window_h
    while t <= end + 1e-9:
        for r in routes:
            s = score_route(r["coords"], r["duration_s"], mode, t, stations)
            options.append({
                "depart_in_h": round(t, 3),
                "wait_min": int(round((t - earliest_in_h) * 60)),
                "route_id": r["id"],
                **{k: s[k] for k in ("duration_min", "exposure_index", "mean_pm25", "risk", "confidence")},
            })
        t += step_min / 60
    return choose(options, sensitivity, max_extra_min, max_wait_min)
