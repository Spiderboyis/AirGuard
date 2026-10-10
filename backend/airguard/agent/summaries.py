"""Compact, model-friendly views of engine results (small local models have small contexts)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def ist(ts: str | float | datetime) -> str:
    if isinstance(ts, (int, float)):
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    elif isinstance(ts, str):
        dt = datetime.fromisoformat(ts)
    else:
        dt = ts
    return dt.astimezone(IST).strftime("%H:%M")


def _route_line(r: dict) -> dict:
    return {"route": f"{r['route_id']} {r['label']}".strip(), "duration_min": round(r["duration_min"]),
            "distance_km": round(r["distance_km"], 1), "exposure_index": round(r["exposure_index"], 1),
            "avg_pm25": round(r["mean_pm25"]), "air_level": r["risk_label"],
            "confidence": round(r["confidence"], 2)}


def _option(o: dict) -> dict:
    return {"route": f"{o['route_id']} {o['label']}".strip(), "leave_at_ist": ist(o["depart_at"]),
            "wait_min": o["wait_min"], "duration_min": round(o["duration_min"]),
            "exposure_index": round(o["exposure_index"], 1),
            "exposure_range": [round(o["exposure_low"], 1), round(o["exposure_high"], 1)],
            "avg_pm25": round(o["mean_pm25"]), "confidence": round(o["confidence"], 2)}


KIND_TEXT = {
    "stay": "Leave now on the fastest route; no alternative cuts exposure enough to be worth the extra time.",
    "route": "Leave now but take a different route.",
    "wait": "Take the same route but leave later.",
    "wait_and_route": "Leave later and take a different route.",
}


def trip_summary(t: dict) -> dict:
    d = t["decision"]
    o, dest = t["origin"].get("name") or "origin", t["destination"].get("name") or "destination"
    return {
        "trip": f"{o} to {dest}, {t['mode_label'].lower()}",
        "planned_from_ist": ist(t["now"]),
        "advice": KIND_TEXT[d["kind"]],
        "recommended": _option(d["recommended"]),
        "fastest_leaving_now": _option(d["baseline"]),
        "change_vs_fastest_now": {"exposure_pct": d["delta"]["exposure_index_pct"],
                                  "arrival_later_min": d["delta"]["arrival_min"],
                                  "wait_min": d["delta"]["wait_min"],
                                  "extra_travel_min": d["delta"]["extra_travel_min"]},
        "lowest_possible_in_window": _option(d["lowest"]),
        "routes_if_leaving_now": [_route_line(r) for r in t["routes"]],
        "sensitivity": t["sensitivity"],
        "decision_rule": (f"{d['rule']['minutes_per_10pct']:g} extra minutes accepted per 10% less exposure; "
                          f"waiting counts at {d['rule']['wait_cost_weight']:g}x"),
        "data": {"stations": t["data"]["stations"], "stations_with_delayed_feed": t["data"]["stations_delayed"],
                 "forecast_issued_ist": ist(t["data"]["forecast_issued_at"])},
    }
