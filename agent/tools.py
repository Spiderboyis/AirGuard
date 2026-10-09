import json
import os
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone

from strands import tool

from api import service
from common import db
from engine.exposure import MODES

_demo: ContextVar[bool] = ContextVar("airguard_demo", default=False)
IST = timezone(timedelta(hours=5, minutes=30))


def set_demo(value: bool):
    return _demo.set(bool(value))


def reset_demo(token):
    _demo.reset(token)


def _j(value):
    return json.dumps(value, separators=(",", ":"), default=str)


def _check(lat, lon, mode="walk"):
    try:
        flat = float(lat)
        flon = float(lon)
    except (ValueError, TypeError):
        raise ValueError("Latitude and longitude must be numbers.")
    if not (28.2 <= flat <= 29.0 and 76.7 <= flon <= 77.7):
        raise ValueError("Only Delhi NCR is supported.")
    m = str(mode).lower()
    if m not in MODES:
        raise ValueError("Mode must be walk, cycle or car.")
    return flat, flon, m


@tool
def now_ist() -> str:
    """Get the current date and time in India Standard Time, to say which clock time a recommended wait corresponds to."""
    if _demo.get():
        captured = service.snapshot_info()["captured_at"]
        t = datetime.fromisoformat(captured).astimezone(IST)
        return _j({"now": t.isoformat(timespec="minutes"), "weekday": t.strftime("%A"), "note": "frozen demo snapshot"})
    n = datetime.now(IST)
    return _j({"now": n.isoformat(timespec="minutes"), "weekday": n.strftime("%A")})


@tool
def geocode(place: str) -> str:
    """Find the latitude and longitude of a place in Delhi NCR.

    Args:
        place: A landmark, neighbourhood or address, for example 'Hauz Khas'.
    """
    try:
        lat, lon = service.geocode(place)
        return _j({"place": place, "lat": lat, "lon": lon})
    except Exception as exc:
        return _j({"error": str(exc)})


@tool
def get_forecast(lat: float, lon: float, hours_ahead: float = 1.0) -> str:
    """Forecast PM2.5 in micrograms per cubic metre at a point, with a low-high range and the distance to the nearest station.

    Args:
        lat: Latitude.
        lon: Longitude.
        hours_ahead: Hours from now, between 0 and 24.
    """
    try:
        flat, flon, _ = _check(lat, lon)
        ha = float(hours_ahead)
        return _j(service.forecast_at(flat, flon, min(max(ha, 0), 24), _demo.get()))
    except Exception as exc:
        return _j({"error": str(exc)})


@tool
def score_routes(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float, mode: str = "walk") -> str:
    """Compare alternative routes for a trip by estimated pollution exposure.

    Args:
        origin_lat: Origin latitude.
        origin_lon: Origin longitude.
        dest_lat: Destination latitude.
        dest_lon: Destination longitude.
        mode: One of walk, cycle, car.
    """
    try:
        olat, olon, mode_val = _check(origin_lat, origin_lon, mode)
        dlat, dlon, _ = _check(dest_lat, dest_lon, mode_val)
        res = service.score_trip(
            {"lat": olat, "lon": olon},
            {"lat": dlat, "lon": dlon},
            mode_val, 0.0, _demo.get(),
        )
        keep = ("id", "duration_min", "distance_km", "exposure_index", "mean_pm25", "risk", "confidence", "is_cleanest", "is_fastest")
        return _j({
            "routes": [{k: r[k] for k in keep} for r in res["routes"]],
            "data_age_min": res["data_age_min"],
            "note": "exposure_index is a relative index for comparing options, not a measured dose",
        })
    except Exception as exc:
        return _j({"error": str(exc)})


@tool
def best_departure_time(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float,
                        mode: str = "walk", window_hours: float = 4.0, max_wait_minutes: int = 120,
                        sensitivity: str = "normal", max_extra_minutes: int = 15) -> str:
    """Find the departure time that minimises estimated exposure, within the user's limits.

    Args:
        origin_lat: Origin latitude.
        origin_lon: Origin longitude.
        dest_lat: Destination latitude.
        dest_lon: Destination longitude.
        mode: One of walk, cycle, car.
        window_hours: How many hours ahead to search, up to 6.
        max_wait_minutes: The longest the user is willing to wait before leaving.
        sensitivity: One of normal, sensitive, high, from the profile line.
        max_extra_minutes: The most extra total minutes the user will accept.
    """
    try:
        olat, olon, mode_val = _check(origin_lat, origin_lon, mode)
        dlat, dlon, _ = _check(dest_lat, dest_lon, mode_val)
        sens_str = str(sensitivity).lower()
        if sens_str not in ("normal", "sensitive", "high"):
            sens_str = "normal"
        wh = float(window_hours)
        mwm = int(float(max_wait_minutes))
        mem = int(float(max_extra_minutes))
        res = service.departure(
            {"lat": olat, "lon": olon},
            {"lat": dlat, "lon": dlon},
            mode_val, 0.0, min(max(wh, 0.25), 6),
            max(0, min(mwm, 720)),
            _demo.get(), sens_str, max(0, min(mem, 120)),
        )
        return _j({
            "baseline": res["baseline"],
            "recommended": res["recommended"],
            "delta": res["delta"],
            "preference": res["preference"],
            "best_by_wait": _best_by_wait(res["options"]),
            "data_age_min": res["data_age_min"],
        })
    except Exception as exc:
        return _j({"error": str(exc)})


def _best_by_wait(options):
    by_wait = {}
    for opt in options:
        if opt["wait_min"] % 30 == 0 and (opt["wait_min"] not in by_wait or opt["exposure_index"] < by_wait[opt["wait_min"]]["exposure_index"]):
            by_wait[opt["wait_min"]] = opt
    return list(by_wait.values())


def _format_trip_summary(raw: dict) -> dict:
    if not isinstance(raw, dict):
        return raw

    routes = raw.get("routes", [])
    cleanest = next((r for r in routes if r.get("is_cleanest")), routes[0] if routes else None)
    fastest = next((r for r in routes if r.get("is_fastest")), routes[0] if routes else None)
    cleanest_exp = cleanest["exposure_index"] if cleanest and cleanest.get("exposure_index") else 1.0

    routes_summary = []
    for r in routes:
        diff_pct = round(((r["exposure_index"] - cleanest_exp) / max(cleanest_exp, 1.0)) * 100, 1)
        routes_summary.append({
            "route_id": r["id"],
            "duration_min": round(r["duration_min"], 1),
            "distance_km": round(r["distance_km"], 1),
            "mean_pm25": round(r["mean_pm25"], 1),
            "risk_level": r["risk"],
            "is_cleanest": r.get("is_cleanest", False),
            "is_fastest": r.get("is_fastest", False),
            "relative_exposure": "0.0% (Cleanest)" if r.get("is_cleanest") else f"+{diff_pct}% exposure vs cleanest",
        })

    rec = raw.get("recommended", {})
    wait_min = rec.get("wait_min", 0)
    exp_change_pct = rec.get("exposure_change_pct", 0.0)

    bbw = raw.get("best_by_wait", [])
    if len(bbw) >= 2:
        pm_now = bbw[0]["mean_pm25"]
        pm_later = bbw[-1]["mean_pm25"]
        hours = max(round(len(bbw) * 0.5), 1)
        if pm_later > pm_now + 1:
            trend = f"PM2.5 is forecast to rise from {round(pm_now, 1)} to {round(pm_later, 1)} µg/m³ over the coming {hours}h. Departing immediately avoids worsening air."
        elif pm_later < pm_now - 1:
            trend = f"PM2.5 is forecast to decrease from {round(pm_now, 1)} to {round(pm_later, 1)} µg/m³."
        else:
            trend = f"PM2.5 levels remain steady around {round(pm_now, 1)} µg/m³."
    else:
        trend = "PM2.5 forecasts remain stable."

    if wait_min == 0:
        dep_guidance = {
            "verdict": "Depart now",
            "wait_min": 0,
            "reason": f"Immediate departure offers the lowest inhalation exposure. {trend}",
            "exposure_saving_pct": 0.0,
        }
    else:
        dep_guidance = {
            "verdict": f"Wait {wait_min} minutes",
            "wait_min": wait_min,
            "reason": f"Waiting {wait_min} minutes reduces estimated exposure by {abs(round(exp_change_pct, 1))}%. {trend}",
            "exposure_saving_pct": abs(round(exp_change_pct, 1)),
            "extra_travel_min": round(rec.get("extra_min", wait_min), 1),
        }

    return {
        **raw,
        "cleanest_route": cleanest["id"] if cleanest else "r1",
        "fastest_route": fastest["id"] if fastest else "r1",
        "routes_breakdown": routes_summary,
        "departure_guidance": dep_guidance,
    }


@tool
def get_trip_result(trip_id: str) -> str:
    """Read the saved result for the trip the user is looking at.

    Args:
        trip_id: The id from the '[Current trip id: ...]' line at the start of the message.
    """
    try:
        hit = db.select("route_cache", select="response", key=f"eq.trip:{trip_id}")
    except Exception as exc:
        return _j({"error": str(exc)})
    if not hit:
        return _j({"error": "Trip result not found. Ask the user to run Compare routes again."})
    return _j(_format_trip_summary(hit[0]["response"]))


@tool
def evaluate_trip(from_place: str, to_place: str, mode: str = "walk", sensitivity: str = "normal") -> str:
    """Evaluate routes and departure timing between two places in Delhi NCR in a single call.

    Args:
        from_place: Starting location or landmark in Delhi NCR (e.g. 'Dwarka Sector 21').
        to_place: Destination location or landmark in Delhi NCR (e.g. 'Connaught Place').
        mode: Mode of travel: 'walk', 'cycle', or 'car'.
        sensitivity: User exposure sensitivity: 'normal', 'sensitive', or 'high'.
    """
    try:
        o_lat, o_lon = service.geocode(from_place)
        d_lat, d_lon = service.geocode(to_place)
        mode_val = mode.lower() if mode and mode.lower() in MODES else "walk"
        sens_val = sensitivity.lower() if sensitivity and sensitivity.lower() in ("normal", "sensitive", "high") else "normal"
        analyzed = service.analyze_trip(
            {"lat": o_lat, "lon": o_lon},
            {"lat": d_lat, "lon": d_lon},
            mode=mode_val,
            demo=_demo.get(),
            sensitivity=sens_val,
        )
        return get_trip_result(analyzed["trip_id"])
    except Exception as exc:
        return _j({"error": str(exc)})


TOOLS = [now_ist, get_trip_result, evaluate_trip, geocode, get_forecast, score_routes, best_departure_time]

if os.environ.get("ALERT_TOPIC_ARN"):
    @tool
    def send_email_summary(subject: str, body: str) -> str:
        """Email the user a short summary of the recommendation.

        Args:
            subject: Email subject, under 80 characters.
            body: Plain-text body, under 800 characters.
        """
        import boto3
        boto3.client("sns").publish(TopicArn=os.environ["ALERT_TOPIC_ARN"], Subject=subject[:99], Message=body[:2000])
        return _j({"sent": True})

    TOOLS.append(send_email_summary)
