"""Exposure index for a route at a given departure time.

    exposure index = sum_i  C_i * t_i * m

C_i is the interpolated PM2.5 (µg/m³) on segment i at the time the traveller reaches it, t_i the
hours spent on it, and m the mode factor (see assumptions.MODE_FACTORS). The result is an index in
µg·h/m³, a model estimate under stated assumptions, not a measured dose.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import numpy as np

from airguard.engine import assumptions as A
from airguard.engine.field import ForecastField
from airguard.engine.segments import Segment, split_line


class ForecastUnavailable(RuntimeError):
    """No forecast covers part of the trip (outside the forecast window, or no stations)."""


@dataclass
class RouteInput:
    id: str
    geometry: list[list[float]]   # [[lon, lat], ...]
    distance_km: float
    duration_min: float
    label: str = ""


@dataclass
class PreparedRoute:
    """A route split into segments, with station distances precomputed (reused across departures)."""
    route: RouteInput
    segments: list[Segment]
    seg_minutes: np.ndarray
    mid_offset_min: np.ndarray    # minutes from departure to each segment's midpoint
    dist: np.ndarray              # (n_segments, n_stations) km


@dataclass
class RouteScore:
    route_id: str
    label: str
    depart_ts: float
    duration_min: float
    distance_km: float
    exposure_index: float
    exposure_low: float
    exposure_high: float
    mean_pm25: float
    peak_pm25: float
    risk: str
    risk_label: str
    confidence: float
    max_station_km: float
    segments: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["depart_at"] = datetime.fromtimestamp(self.depart_ts, tz=timezone.utc).isoformat()
        return d


def prepare(route: RouteInput, fld: ForecastField) -> PreparedRoute:
    segs = split_line(route.geometry, A.SEGMENT_KM)
    if not segs:
        raise ValueError(f"route {route.id} has no usable geometry")
    lengths = np.array([s.length_km for s in segs])
    total = lengths.sum()
    # Time on each segment is proportional to its share of the route distance.
    minutes = lengths / total * route.duration_min
    mids = np.cumsum(minutes) - minutes / 2
    dist = fld.distances([s.lat for s in segs], [s.lon for s in segs])
    return PreparedRoute(route=route, segments=segs, seg_minutes=minutes, mid_offset_min=mids, dist=dist)


def score(p: PreparedRoute, fld: ForecastField, depart_ts: float, mode: str, with_segments: bool = True) -> RouteScore:
    if mode not in A.MODE_FACTORS:
        raise ValueError(f"unknown mode {mode!r}")
    m = A.MODE_FACTORS[mode]
    times = depart_ts + p.mid_offset_min * 60.0
    s = fld.sample([g.lat for g in p.segments], [g.lon for g in p.segments], times, dist=p.dist)
    if np.isnan(s.pm25).any():
        bad = datetime.fromtimestamp(float(times[np.isnan(s.pm25)][0]), tz=timezone.utc)
        raise ForecastUnavailable(f"no forecast covers {bad.isoformat()}")

    hours = p.seg_minutes / 60.0
    exposure = float(np.sum(s.pm25 * hours) * m)
    exp_low = float(np.sum(s.low * hours) * m)
    exp_high = float(np.sum(s.high * hours) * m)
    total_h = float(hours.sum())
    mean_pm = exposure / (total_h * m) if total_h > 0 else 0.0
    risk, risk_label = A.risk_band(mean_pm)
    conf = float(np.sum(s.confidence * p.seg_minutes) / p.seg_minutes.sum())

    segments = []
    if with_segments:
        for g, pm, lo, hi, mins, c, near in zip(p.segments, s.pm25, s.low, s.high, p.seg_minutes,
                                                s.confidence, s.nearest_km):
            segments.append({"lat": round(g.lat, 6), "lon": round(g.lon, 6), "pm25": round(float(pm), 1),
                             "low": round(float(lo), 1), "high": round(float(hi), 1),
                             "minutes": round(float(mins), 2), "confidence": round(float(c), 3),
                             "station_km": round(float(near), 2), "line": g.line})

    return RouteScore(
        route_id=p.route.id, label=p.route.label, depart_ts=float(depart_ts),
        duration_min=round(float(p.route.duration_min), 1), distance_km=round(float(p.route.distance_km), 2),
        exposure_index=round(exposure, 2), exposure_low=round(exp_low, 2), exposure_high=round(exp_high, 2),
        mean_pm25=round(mean_pm, 1), peak_pm25=round(float(np.max(s.pm25)), 1),
        risk=risk, risk_label=risk_label, confidence=round(conf, 3),
        max_station_km=round(float(np.nanmax(s.nearest_km)), 2), segments=segments,
    )
