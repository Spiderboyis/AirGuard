import hashlib
import json
import os
import statistics
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from common import db
from common.config import cfg
from common.geo import haversine_km
from engine.exposure import MODES, Station, best_departure, idw, score_route

ORS = "https://api.openrouteservice.org/v2/directions"
OSRM = "https://router.project-osrm.org/route/v1"
MAX_OBS_AGE_MIN = 360
PLACES = {
    "connaught place": (28.6315, 77.2167),
    "india gate": (28.6129, 77.2295),
    "hauz khas": (28.5494, 77.2001),
    "du north campus": (28.6889, 77.2100),
    "lodhi garden": (28.5931, 77.2197),
    "nehru place": (28.5491, 77.2519),
}
_CACHE = {}
_LAST_GEO = [0.0]
_GEO_LOCK = threading.Lock()
_FIXTURES = None


def route_cache_key(mode, o_lat, o_lon, d_lat, d_lon) -> str:
    return hashlib.sha1(f"{mode}:{o_lat:.4f},{o_lon:.4f}>{d_lat:.4f},{d_lon:.4f}".encode()).hexdigest()


def _place_key(mode, o_lat, o_lon, d_lat, d_lon) -> str:
    return f"{mode}:{o_lat:.4f},{o_lon:.4f}>{d_lat:.4f},{d_lon:.4f}"


def _cached(key, fn, ttl=300):
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    value = fn()
    _CACHE[key] = (time.time(), value)
    return value


def _ts(value):
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _same_run(a, b) -> bool:
    if a == b:
        return True
    try:
        return abs((_ts(a) - _ts(b)).total_seconds()) <= 2
    except Exception:
        return False


def _stations_from_rows(names, rows):
    now = datetime.now(timezone.utc)
    by_station = {}
    for row in rows:
        by_station.setdefault(row["station_id"], []).append(row)
    stations, ages = [], []
    for sid, group in by_station.items():
        obs = next((row for row in group if row["horizon_h"] == 0), None)
        if obs is None or sid not in names or names[sid].get("lat") is None:
            continue
        obs_age = max(0.0, (now - _ts(obs["target_ts"])).total_seconds() / 60)
        if obs_age > MAX_OBS_AGE_MIN:
            continue
        # An older hourly run must not fill in horizons this run did not write.
        run = [row for row in group if _same_run(row.get("generated_at"), obs.get("generated_at"))]
        series = sorted(
            ((_ts(row["target_ts"]) - now).total_seconds() / 3600, row["pm25_pred"], row["pm25_low"], row["pm25_high"])
            for row in run
        )
        if len(series) >= 2:
            stations.append(Station(sid, names[sid]["lat"], names[sid]["lon"], series))
            ages.append(obs_age)
    return stations, (round(statistics.median(ages)) if ages else None)


def load_stations(demo=False):
    """Return ([Station], median age in minutes of the latest real readings).

    demo=True reads the frozen snapshot. Its hour offsets stay relative to the capture time.
    """
    if demo:
        hit = db.select("route_cache", select="response", key="eq.snapshot:stations")
        if not hit:
            raise ValueError("Demo snapshot is missing. Run python scripts/snapshot.py or python scripts/seed_local.py first.")
        snap = hit[0]["response"]
        return [Station(s["id"], s["lat"], s["lon"], [tuple(p) for p in s["series"]]) for s in snap["stations"]], None

    def fetch():
        names = {s["id"]: s for s in db.select_all("stations", select="id,lat,lon")}
        rows = db.select_all(
            "forecasts_latest",
            select="station_id,horizon_h,target_ts,pm25_pred,pm25_low,pm25_high,generated_at",
        )
        return _stations_from_rows(names, rows)

    return _cached("stations", fetch)


def forecast_age_min():
    rows = db.select("forecasts_latest", select="generated_at", order="generated_at.desc", limit=1)
    if not rows or not rows[0].get("generated_at"):
        return None
    return round((datetime.now(timezone.utc) - _ts(rows[0]["generated_at"])).total_seconds() / 60)


def snapshot_info():
    hit = db.select("route_cache", select="response", key="eq.snapshot:stations")
    if not hit:
        raise ValueError("Demo snapshot is missing. Run python scripts/snapshot.py or python scripts/seed_local.py first.")
    snap = hit[0]["response"]
    return {"captured_at": snap["captured_at"], "data_age_at_capture_min": snap.get("data_age_at_capture_min")}


def geocode(q):
    key = q.strip().lower()
    if key in PLACES:
        return PLACES[key]
    hit = db.select("route_cache", select="response", key=f"eq.geo:{key}")
    if hit:
        return tuple(hit[0]["response"])
    with _GEO_LOCK:
        wait = 1.1 - (time.time() - _LAST_GEO[0])
        if wait > 0:
            time.sleep(wait)
        _LAST_GEO[0] = time.time()
        email = cfg().get("CONTACT_EMAIL") or "airguard-local@example.com"
        response = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            timeout=6,
            params={"q": q + ", Delhi", "format": "jsonv2", "limit": 1, "countrycodes": "in"},
            headers={"User-Agent": f"AirGuard-hackathon/0.1 ({email})"},
        )
    response.raise_for_status()
    if not response.json():
        raise ValueError(f"Could not find '{q}'")
    point = [float(response.json()[0]["lat"]), float(response.json()[0]["lon"])]
    db.upsert("route_cache", [{"key": f"geo:{key}", "response": point}], "key")
    return tuple(point)


def _fixtures():
    global _FIXTURES
    if _FIXTURES is None:
        path = Path(__file__).resolve().parents[1] / "fixtures" / "demo_routes.json"
        _FIXTURES = json.loads(path.read_text()) if path.exists() else {}
    return _FIXTURES


def _ors_routes(o_lat, o_lon, d_lat, d_lon, mode):
    body = {
        "coordinates": [[o_lon, o_lat], [d_lon, d_lat]],
        "instructions": False,
        "alternative_routes": {"target_count": 3, "share_factor": 0.6, "weight_factor": 1.6},
    }
    url = f"{ORS}/{MODES[mode]['ors_profile']}/geojson"
    headers = {"Authorization": cfg()["ORS_API_KEY"]}
    response = httpx.post(url, json=body, headers=headers, timeout=8)
    if response.status_code == 400:
        body.pop("alternative_routes")
        response = httpx.post(url, json=body, headers=headers, timeout=8)
    response.raise_for_status()
    return _pack_features(response.json().get("features") or [])


def _osrm_call(profile, points):
    path = ";".join(f"{lon},{lat}" for lon, lat in points)
    response = httpx.get(
        f"{OSRM}/{profile}/{path}",
        params={"overview": "full", "geometries": "geojson", "alternatives": "true"},
        timeout=8,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != "Ok":
        return []
    packed = []
    for route in (payload.get("routes") or [])[:3]:
        coords = [[round(x, 5), round(y, 5)] for x, y in route["geometry"]["coordinates"]]
        if len(coords) < 2:
            continue
        packed.append({"coords": coords, "duration_s": route["duration"], "distance_m": route["distance"]})
    return packed


def _osrm_routes(o_lat, o_lon, d_lat, d_lon, mode):
    profile = MODES[mode]["osrm_profile"]
    found = _osrm_call(profile, [(o_lon, o_lat), (d_lon, d_lat)])
    # One corridor is a weak demo. Ask for a road via a point east of the middle, then west of it.
    if len(found) < 2:
        mid_lat = (o_lat + d_lat) / 2
        mid_lon = (o_lon + d_lon) / 2
        for dlon, dlat in ((0.035, 0.0), (-0.035, 0.01)):
            try:
                via = _osrm_call(profile, [(o_lon, o_lat), (mid_lon + dlon, mid_lat + dlat), (d_lon, d_lat)])
            except httpx.HTTPError:
                continue
            if not via:
                continue
            candidate = via[0]
            if any(abs(candidate["distance_m"] - item["distance_m"]) < 400 for item in found):
                continue
            found.append(candidate)
            if len(found) >= 3:
                break
    return [{"id": f"r{i + 1}", **route} for i, route in enumerate(found[:3])]


def _pack_features(features):
    routes = []
    for i, feature in enumerate(features):
        summary = (feature.get("properties") or {}).get("summary") or {}
        coords = [[round(x, 5), round(y, 5)] for x, y in feature["geometry"]["coordinates"]]
        routes.append({
            "id": f"r{i + 1}",
            "coords": coords,
            "duration_s": summary["duration"],
            "distance_m": summary["distance"],
        })
    return routes


def get_routes(o_lat, o_lon, d_lat, d_lon, mode):
    if mode not in MODES:
        raise ValueError("Mode must be walk, cycle or car.")
    key = route_cache_key(mode, o_lat, o_lon, d_lat, d_lon)
    hit = db.select("route_cache", select="response", key=f"eq.{key}")
    if hit:
        return hit[0]["response"]
    # A configured key should win over a frozen file. The file still covers an ORS outage,
    # and straight-line stand-ins stay opt-in so they are not mistaken for roads.
    routes = []
    if (cfg().get("ORS_API_KEY") or "").strip():
        try:
            routes = _ors_routes(o_lat, o_lon, d_lat, d_lon, mode)
        except httpx.HTTPError as exc:
            print("OpenRouteService failed, trying the next source:", exc)
            routes = []
    if not routes:
        place = _place_key(mode, o_lat, o_lon, d_lat, d_lon)
        routes = _fixtures().get(place) or []
    if not routes:
        try:
            routes = _osrm_routes(o_lat, o_lon, d_lat, d_lon, mode)
        except httpx.HTTPError as exc:
            print("OSRM fallback failed:", exc)
            routes = []
    if not routes and os.environ.get("AIRGUARD_STRAIGHT_ROUTES") == "1":
        routes = _straight_routes(o_lat, o_lon, d_lat, d_lon, mode)
    if not routes:
        raise ValueError("No route found between those places.")
    db.upsert("route_cache", [{"key": key, "response": routes}], "key")
    return routes


def _straight_routes(o_lat, o_lon, d_lat, d_lon, mode):
    """Two corridor stand-ins used only when every routing service fails.

    Speeds are city assumptions so the engine can still compare a direct path with a bowed one.
    """
    speeds = {"walk": 4.8, "cycle": 15.0, "car": 22.0}

    def line(bow):
        pts = []
        for i in range(24):
            f = i / 23
            lat = o_lat + (d_lat - o_lat) * f + bow * math_sin(f)
            lon = o_lon + (d_lon - o_lon) * f + bow * math_sin(f)
            pts.append([round(lon, 5), round(lat, 5)])
        return pts

    out = []
    for i, bow in enumerate((0.0, 0.015)):
        coords = line(bow)
        km = 0.0
        for a, b in zip(coords, coords[1:]):
            km += haversine_km(a[1], a[0], b[1], b[0])
        if km <= 0:
            continue
        out.append({
            "id": f"r{i + 1}",
            "coords": coords,
            "duration_s": km / speeds[mode] * 3600,
            "distance_m": km * 1000,
        })
    if out:
        print("routing: using straight-line stand-ins because no routing service responded")
    return out


def math_sin(f):
    import math
    return math.sin(math.pi * f)


def _score_routes(routes, mode, depart_in_h, stations):
    scored = []
    for route in routes:
        scored.append({
            "id": route["id"],
            **score_route(route["coords"], route["duration_s"], mode, depart_in_h, stations),
            "geometry": route["coords"],
        })
    if not scored:
        raise ValueError("No route found between those places.")
    cleanest = min(scored, key=lambda item: item["exposure_index"])["id"]
    fastest = min(scored, key=lambda item: item["duration_min"])["id"]
    for item in scored:
        item["is_cleanest"] = item["id"] == cleanest
        item["is_fastest"] = item["id"] == fastest
    return scored


def _require_stations(demo):
    stations, age = load_stations(demo)
    if not stations:
        raise ValueError("No usable air-quality stations right now. Run the hourly job or seed local data.")
    return stations, age


def score_trip(o, d, mode, depart_in_h=0.0, demo=False):
    stations, age = _require_stations(demo)
    routes = get_routes(o["lat"], o["lon"], d["lat"], d["lon"], mode)
    return {
        "routes": _score_routes(routes, mode, depart_in_h, stations),
        "data_age_min": age,
        "mode_factor": MODES[mode]["factor"],
    }


def departure(o, d, mode, earliest_in_h=0.0, window_h=4.0, max_wait_min=120, demo=False,
              sensitivity="normal", max_extra_min=15):
    stations, age = _require_stations(demo)
    routes = get_routes(o["lat"], o["lon"], d["lat"], d["lon"], mode)
    result = best_departure(
        routes, mode, stations, earliest_in_h, window_h, max_wait_min,
        sensitivity=sensitivity, max_extra_min=max_extra_min,
    )
    result["data_age_min"] = age
    return result


def _best_by_wait(options):
    by_wait = {}
    for opt in options:
        wait = opt["wait_min"]
        if wait % 30 == 0 and (wait not in by_wait or opt["exposure_index"] < by_wait[wait]["exposure_index"]):
            by_wait[wait] = opt
    return list(by_wait.values())


def analyze_trip(o, d, mode, demo=False, window_h=4.0, max_wait_min=120, sensitivity="normal", max_extra_min=15):
    """Routes plus departure advice. Stores a compact summary the agent can explain without recomputing."""
    res = score_trip(o, d, mode, 0.0, demo)
    dep = departure(o, d, mode, 0.0, window_h, max_wait_min, demo, sensitivity, max_extra_min)
    keep = ("id", "duration_min", "distance_km", "exposure_index", "mean_pm25", "risk", "confidence", "is_cleanest", "is_fastest")
    summary = {
        "mode": mode,
        "demo": demo,
        "routes": [{k: r[k] for k in keep} for r in res["routes"]],
        "baseline": dep["baseline"],
        "recommended": dep["recommended"],
        "delta": dep["delta"],
        "best_by_wait": _best_by_wait(dep["options"]),
        "data_age_min": res["data_age_min"],
        "preference": dep["preference"],
        "snapshot": snapshot_info() if demo else None,
    }
    stamp = round(time.time() / 3600)
    identity = [_round_point(o), _round_point(d), mode, bool(demo), sensitivity, int(max_extra_min), int(max_wait_min), round(float(window_h), 2), stamp]
    trip_id = hashlib.sha1(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
    db.upsert("route_cache", [{"key": f"trip:{trip_id}", "response": summary}], "key")
    return {"trip_id": trip_id, "routes": res, "departure": dep, "snapshot": summary["snapshot"]}


def _round_point(point):
    return {"lat": round(float(point["lat"]), 5), "lon": round(float(point["lon"]), 5)}


def forecast_at(lat, lon, horizon_h, demo=False):
    stations, age = load_stations(demo)
    pm, lo, hi, dist = idw(lat, lon, stations, horizon_h)
    from engine.exposure import confidence
    return {
        "pm25": round(pm, 1),
        "low": round(lo, 1),
        "high": round(hi, 1),
        "nearest_station_km": round(dist, 1),
        "confidence": round(confidence(pm, lo, hi, dist), 2),
        "data_age_min": age,
    }


def eval_metrics():
    version = (cfg().get("MODEL_VERSION") or "").strip() or "v1"
    rows = db.select("eval_metrics", select="*", model_version=f"eq.{version}", order="horizon_h.asc")
    if rows:
        return rows
    return db.select("eval_metrics", select="*", order="horizon_h.asc")
