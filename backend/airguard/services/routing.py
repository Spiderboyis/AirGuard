"""Candidate routes from OSRM (FOSSGIS public servers: foot, bike and car profiles, no key).

OSRM often returns a single route, or near-duplicates. When that happens AirGuard asks for routes
through a point offset to either side of the straight line, keeps those that differ meaningfully
and aren't much longer, and labels each by its main roads. Every response is cached in Postgres,
so a demo trip never depends on the public server being up.
"""

from __future__ import annotations

import hashlib
import logging
import math
import threading
import time

import httpx
import numpy as np

from airguard import db
from airguard.config import settings
from airguard.engine.assumptions import MODE_PROFILE
from airguard.engine.exposure import RouteInput
from airguard.geo import haversine_km, haversine_matrix

log = logging.getLogger("airguard.routing")

PROFILE_PATH = {"foot": "routed-foot", "bike": "routed-bike", "car": "routed-car"}
MAX_ROUTES = 3
MAX_DETOUR = 1.6          # alternatives may take at most 60% longer than the fastest
MIN_DIFFERENT_SHARE = 0.25  # at least 25% of an alternative must be >80 m from every other route
MAX_TRIP_KM = 60

_lock = threading.Lock()
_last = [0.0]


class RoutingError(RuntimeError):
    pass


def _osrm(profile: str, coords: list[tuple[float, float]], alternatives: bool) -> list[dict]:
    path = PROFILE_PATH[profile]
    loc = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in coords)
    url = f"{settings().osrm_base_url}/{path}/route/v1/driving/{loc}"
    params = {"overview": "full", "geometries": "geojson", "steps": "true",
              "alternatives": "3" if alternatives else "false"}
    with _lock:  # the public servers ask for at most ~1 request per second
        wait = 1.0 - (time.monotonic() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()
    try:
        r = httpx.get(url, params=params, timeout=30, headers={"User-Agent": settings().user_agent})
    except httpx.HTTPError as e:
        raise RoutingError(f"routing service unreachable: {e}") from e
    if r.status_code != 200:
        raise RoutingError(f"routing service returned {r.status_code}")
    j = r.json()
    if j.get("code") != "Ok":
        raise RoutingError(j.get("message") or j.get("code") or "no route")
    out = []
    for rt in j["routes"]:
        roads = []
        for leg in rt["legs"]:
            for st in leg.get("steps", []):
                name = (st.get("ref") or st.get("name") or "").strip()
                if name and st.get("distance", 0) > 400 and name not in roads:
                    roads.append(name)
        out.append({"geometry": rt["geometry"]["coordinates"], "distance_km": rt["distance"] / 1000,
                    "duration_min": rt["duration"] / 60, "roads": roads,
                    "main_roads": _main_roads(rt)})
    return out


def _main_roads(rt: dict) -> list[str]:
    totals: dict[str, float] = {}
    for leg in rt["legs"]:
        for st in leg.get("steps", []):
            name = (st.get("name") or st.get("ref") or "").strip()
            if name:
                totals[name] = totals.get(name, 0.0) + st.get("distance", 0.0)
    return [n for n, _ in sorted(totals.items(), key=lambda kv: -kv[1])[:2]]


def _different_share(a: list, others: list[list]) -> float:
    """Share of route a's points lying more than 80 m from every point of the other routes."""
    if not others:
        return 1.0
    pa = np.array(a[:: max(1, len(a) // 150)])
    far = np.ones(len(pa), dtype=bool)
    for o in others:
        po = np.array(o[:: max(1, len(o) // 300)])
        d = haversine_matrix(pa[:, 1], pa[:, 0], po[:, 1], po[:, 0]).min(axis=1)
        far &= d > 0.08
    return float(far.mean())


def _via_points(o: tuple[float, float], d: tuple[float, float]) -> list[tuple[float, float]]:
    lat_m, lon_m = (o[0] + d[0]) / 2, (o[1] + d[1]) / 2
    dist = haversine_km(*o, *d)
    off = min(max(0.12 * dist, 0.8), 3.0)                     # km to either side of the midpoint
    dy, dx = d[0] - o[0], (d[1] - o[1]) * math.cos(math.radians(lat_m))
    n = math.hypot(dx, dy) or 1.0
    px, py = -dy / n, dx / n                                   # unit perpendicular (x = east, y = north)
    deg = off / 111.32
    return [(lat_m + s * py * deg, lon_m + s * px * deg / math.cos(math.radians(lat_m))) for s in (1, -1)]


def _cache_key(profile: str, o, d) -> str:
    raw = f"osrm:{profile}:{o[0]:.5f},{o[1]:.5f}:{d[0]:.5f},{d[1]:.5f}"
    return hashlib.sha1(raw.encode()).hexdigest()


def get_routes(origin: tuple[float, float], dest: tuple[float, float], mode: str) -> list[RouteInput]:
    """Up to three distinct candidate routes, fastest first."""
    if haversine_km(*origin, *dest) > MAX_TRIP_KM:
        raise RoutingError(f"trips longer than {MAX_TRIP_KM} km are not supported")
    if haversine_km(*origin, *dest) < 0.3:
        raise RoutingError("origin and destination are too close together")
    profile = MODE_PROFILE[mode]
    key = _cache_key(profile, origin, dest)
    cached = _read_cache(key)
    if cached is None:
        routes = _osrm(profile, [origin, dest], alternatives=True)
        kept: list[dict] = []
        for r in sorted(routes, key=lambda r: r["duration_min"]):
            if _different_share(r["geometry"], [k["geometry"] for k in kept]) >= MIN_DIFFERENT_SHARE or not kept:
                kept.append(r)
        if len(kept) < MAX_ROUTES:
            for via in _via_points(origin, dest):
                if len(kept) >= MAX_ROUTES:
                    break
                try:
                    alt = _osrm(profile, [origin, via, dest], alternatives=False)[0]
                except RoutingError:
                    continue
                if alt["duration_min"] > kept[0]["duration_min"] * MAX_DETOUR:
                    continue
                if _different_share(alt["geometry"], [k["geometry"] for k in kept]) >= MIN_DIFFERENT_SHARE:
                    kept.append(alt)
        cached = sorted(kept, key=lambda r: r["duration_min"])[:MAX_ROUTES]
        _write_cache(key, cached)

    out = []
    for i, r in enumerate(cached):
        roads = r.get("main_roads") or r.get("roads") or []
        label = "via " + " & ".join(roads[:2]) if roads else ("Fastest route" if i == 0 else f"Alternative {i}")
        out.append(RouteInput(id=f"r{i + 1}", geometry=r["geometry"], distance_km=r["distance_km"],
                              duration_min=r["duration_min"], label=label))
    return out


def _read_cache(key: str):
    try:
        rows = db.query("select response from route_cache where key = %s", (key,))
    except db.DatabaseUnavailable:
        return None
    return rows[0]["response"] if rows else None


def _write_cache(key: str, value) -> None:
    try:
        db.upsert("route_cache", [{"key": key, "response": value}], ["key"])
    except db.DatabaseUnavailable:
        log.warning("route cache unavailable")
