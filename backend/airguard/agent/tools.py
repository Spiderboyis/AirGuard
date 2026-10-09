"""Agent tools. Each is a thin, traced wrapper over the same functions the API uses."""

from __future__ import annotations

from datetime import timedelta

from strands import tool

from airguard.agent.summaries import IST, _option, _route_line, ist, trip_summary
from airguard.agent.trace import traced
from airguard.engine import assumptions as A
from airguard.engine.departure import decide, evaluate
from airguard.engine.exposure import prepare, score
from airguard.geo import in_ncr
from airguard.services import forecasts, geocoding, routing, trips


def _check(lat: float, lon: float) -> None:
    if not in_ncr(lat, lon):
        raise ValueError("location is outside Delhi NCR, which is all AirGuard covers")


@tool
@traced
def now_ist() -> dict:
    """Current date and time in India (IST). Use it to turn 'in 30 minutes' into a clock time."""
    now = forecasts.reference_now(forecasts.current_field())
    return {"now_ist": now.astimezone(IST).strftime("%A %d %b %Y, %H:%M")}


@tool
@traced
def geocode(place: str) -> dict:
    """Find coordinates for a place name in Delhi NCR. Returns up to 3 matches."""
    res = geocoding.search(place, limit=3)
    if not res:
        raise ValueError(f"no place called {place!r} found in Delhi NCR")
    return {"matches": [{"name": r["name"], "detail": r["detail"], "lat": r["lat"], "lon": r["lon"]} for r in res]}


@tool
@traced
def get_trip_result(trip_id: str) -> dict:
    """The saved analysis of the trip the user is looking at: recommended route and departure time,
    the fastest option leaving now, every route's exposure, confidence, and the decision rule used."""
    t = trips.get(trip_id)
    if t is None:
        raise ValueError("trip not found; ask the user to plan the trip first")
    return trip_summary(t)


@tool
@traced
def get_forecast(lat: float, lon: float, hours_ahead: float = 0) -> dict:
    """PM2.5 forecast (µg/m³) at a point, now or up to 24 hours ahead, with a range and confidence."""
    _check(lat, lon)
    hours_ahead = min(max(float(hours_ahead), 0.0), 24.0)
    fld = forecasts.current_field()
    t = forecasts.reference_now(fld) + timedelta(hours=hours_ahead)
    p = fld.point(lat, lon, t.timestamp())
    if p["pm25"] is None:
        raise ValueError("no forecast covers that time")
    key, label = A.risk_band(p["pm25"])
    return {"time_ist": ist(t), "pm25": round(p["pm25"]), "range": [round(p["low"]), round(p["high"])],
            "air_level": label, "confidence": round(p["confidence"], 2),
            "nearest_station_km": round(p["nearest_station_km"], 1)}


@tool
@traced
def score_routes(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float, mode: str = "cycle") -> dict:
    """Candidate routes leaving now with duration, exposure index, average PM2.5 and confidence.
    mode is one of: walk, cycle, two_wheeler, car."""
    _check(origin_lat, origin_lon)
    _check(dest_lat, dest_lon)
    if mode not in A.MODE_FACTORS:
        raise ValueError("mode must be walk, cycle, two_wheeler or car")
    fld = forecasts.current_field()
    now = forecasts.reference_now(fld).timestamp()
    routes = routing.get_routes((origin_lat, origin_lon), (dest_lat, dest_lon), mode)
    return {"routes": [_route_line(score(prepare(r, fld), fld, now, mode, with_segments=False).to_dict())
                       for r in routes]}


@tool
@traced
def best_departure_time(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float,
                        mode: str = "cycle", sensitivity: str = "normal", window_h: float = 4,
                        max_extra_min: float = 15, max_wait_min: float = 120) -> dict:
    """Best time to leave within the next window_h hours (max 6), checked every 15 minutes, using the
    user's sensitivity (normal, sensitive, high) and time limits. Returns the recommendation and the
    trade-off against the fastest route leaving now."""
    _check(origin_lat, origin_lon)
    _check(dest_lat, dest_lon)
    if mode not in A.MODE_FACTORS:
        raise ValueError("mode must be walk, cycle, two_wheeler or car")
    if sensitivity not in A.MINUTES_PER_10PCT:
        sensitivity = "normal"
    fld = forecasts.current_field()
    now = forecasts.reference_now(fld).timestamp()
    prepared = [prepare(r, fld) for r in routing.get_routes((origin_lat, origin_lon), (dest_lat, dest_lon), mode)]
    d = decide(evaluate(prepared, fld, now, mode, window_h=window_h), sensitivity, max_extra_min, max_wait_min).to_dict()
    return {"recommended": _option(d["recommended"]), "fastest_leaving_now": _option(d["baseline"]),
            "change_vs_fastest_now": d["delta"], "kind": d["kind"]}


ALL_TOOLS = [now_ist, geocode, get_trip_result, get_forecast, score_routes, best_departure_time]
