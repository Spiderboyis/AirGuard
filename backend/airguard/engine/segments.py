"""Split a route polyline into equal-length segments."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from airguard.geo import haversine_km


@dataclass(frozen=True)
class Segment:
    lat: float            # midpoint
    lon: float
    start_km: float       # distance from the route start to the segment start
    length_km: float
    line: list[list[float]]  # [[lon, lat], ...] including both ends


def split_line(coords: list[list[float]], step_km: float = 0.2) -> list[Segment]:
    """Cut a [[lon, lat], ...] polyline into pieces of `step_km` (the last one may be shorter).

    Cut points are linearly interpolated in lon/lat, which is accurate to well under a metre over
    a few hundred metres at Delhi's latitude.
    """
    pts = [(float(p[0]), float(p[1])) for p in coords]
    pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
    if len(pts) < 2:
        return []
    seg_len = [haversine_km(a[1], a[0], b[1], b[0]) for a, b in zip(pts, pts[1:])]
    total = float(sum(seg_len))
    if total <= 0:
        return []

    cum = np.concatenate([[0.0], np.cumsum(seg_len)])

    def point_at(d: float) -> tuple[float, float]:
        i = int(np.searchsorted(cum, d, side="right") - 1)
        i = min(max(i, 0), len(seg_len) - 1)
        f = 0.0 if seg_len[i] == 0 else (d - cum[i]) / seg_len[i]
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        return x0 + f * (x1 - x0), y0 + f * (y1 - y0)

    n = max(1, int(np.ceil(total / step_km - 1e-9)))
    out = []
    for k in range(n):
        a, b = k * step_km, min((k + 1) * step_km, total)
        if b - a <= 1e-9:
            continue
        inner = [pts[j + 1] for j in range(len(seg_len)) if a < cum[j + 1] < b]
        line = [point_at(a), *inner, point_at(b)]
        mx, my = point_at((a + b) / 2)
        out.append(Segment(lat=my, lon=mx, start_km=a, length_km=b - a,
                           line=[[round(x, 6), round(y, 6)] for x, y in line]))
    return out
