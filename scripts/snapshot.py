import hashlib
import json
import os
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.explain import explain_saved
from api import service
from common import db
from engine.exposure import level_config

TRIPS = [{"name": "Hauz Khas to DU North Campus", "mode": "cycle", "o": "hauz khas", "d": "du north campus"}]
QUESTIONS = [
    "I cycle from Hauz Khas to DU North Campus. Which route should I take, and when should I leave?",
]


def pt(place):
    lat, lon = service.geocode(place)
    return {"lat": lat, "lon": lon}


def freeze_stations():
    stations, age = service.load_stations()
    if not stations:
        raise SystemExit("No fresh stations to freeze. Check /health first.")
    snap = [{"id": s.id, "lat": s.lat, "lon": s.lon, "series": [list(p) for p in s.series]} for s in stations]
    db.upsert("route_cache", [{
        "key": "snapshot:stations",
        "response": {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "data_age_at_capture_min": age,
            "stations": snap,
        },
    }], "key")
    print(f"froze {len(snap)} stations; data was {age} minutes old")


def headline(t):
    o, d = pt(t["o"]), pt(t["d"])
    res = service.score_trip(o, d, t["mode"], 0.0, demo=True)
    fast = next(r for r in res["routes"] if r["is_fastest"])
    clean = next(r for r in res["routes"] if r["is_cleanest"])
    dep = service.departure(o, d, t["mode"], 0.0, 4.0, 120, demo=True, sensitivity="sensitive")
    reduction = 0.0
    if fast["exposure_index"]:
        reduction = round(100 * (fast["exposure_index"] - clean["exposure_index"]) / fast["exposure_index"], 1)
    return {
        "trip": t["name"],
        "routes": len(res["routes"]),
        "cleanest_vs_fastest": {"extra_min": round(clean["duration_min"] - fast["duration_min"], 1), "exposure_reduction_pct": reduction},
        "departure": dep["delta"],
        "recommended_wait_min": dep["recommended"]["wait_min"],
        "reliability": clean["confidence"],
    }


def offline_files(t, saved):
    o, d = pt(t["o"]), pt(t["d"])
    body = {
        "trip": t["name"],
        "request": {
            "from": "Hauz Khas", "to": "DU North Campus", "mode": t["mode"],
            "sensitivity": "sensitive", "max_extra_min": 15, "max_wait_min": 120,
        },
        "snapshot": service.snapshot_info(),
        "levels": level_config(),
        "chat": saved,
        "routes": service.score_trip(o, d, t["mode"], 0.0, demo=True),
        "departure": service.departure(o, d, t["mode"], 0.0, 4.0, 120, demo=True, sensitivity="sensitive"),
    }
    path = ROOT / "frontend" / "public" / "demo" / "trip1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body))
    print("wrote", path)


def cache_answers():
    saved = []
    for q in QUESTIONS:
        try:
            from agent.agent import chat
            out = chat(q, {"sensitivity": "sensitive", "mode": "cycle", "max_extra_min": 15, "max_wait_min": 120}, [], demo=True)
        except Exception as exc:
            print("agent unavailable, writing a deterministic answer from the saved trip:", exc)
            o, d = pt("hauz khas"), pt("du north campus")
            analyzed = service.analyze_trip(o, d, "cycle", True, 4.0, 120, "sensitive", 15)
            summary = db.select("route_cache", select="response", key=f"eq.trip:{analyzed['trip_id']}")[0]["response"]
            out = {
                "answer": explain_saved(summary),
                "tool_calls": [{"name": "get_trip_result", "input": {"trip_id": analyzed["trip_id"]}, "output": json.dumps(summary)[:2000]}],
                "cached": True,
            }
        key = "agent:" + hashlib.sha1(q.strip().lower().encode()).hexdigest()
        db.upsert("route_cache", [{"key": key, "response": out}], "key")
        print("cached answer for:", q)
        saved.append({"question": q, **out})
    return saved


def batch_stats(mode="cycle", n=30, seed=1):
    random.seed(seed)
    stations, _ = service.load_stations(demo=True)
    if len(stations) < 2:
        return {"n": 0, "median_extra_min": None, "median_reduction_pct": None}
    out = []
    attempts = 0
    while len(out) < n and attempts < n * 3:
        attempts += 1
        a, b = random.sample(stations, 2)
        if haversine_pair(a, b) < 1:
            continue
        try:
            res = service.score_trip({"lat": a.lat, "lon": a.lon}, {"lat": b.lat, "lon": b.lon}, mode, 0.0, demo=True)
        except Exception as exc:
            print("batch trip skipped:", exc)
            continue
        fast = next(r for r in res["routes"] if r["is_fastest"])
        clean = next(r for r in res["routes"] if r["is_cleanest"])
        base = fast["exposure_index"] or 1
        out.append((clean["duration_min"] - fast["duration_min"], 100 * (fast["exposure_index"] - clean["exposure_index"]) / base))
    if not out:
        return {"n": 0, "median_extra_min": None, "median_reduction_pct": None}
    return {
        "n": len(out),
        "median_extra_min": round(statistics.median(x for x, _ in out), 1),
        "median_reduction_pct": round(statistics.median(y for _, y in out), 1),
        "note": "Trips are between station locations in this snapshot, not a random sample of Delhi trips.",
    }


def haversine_pair(a, b):
    from common.geo import haversine_km
    return haversine_km(a.lat, a.lon, b.lat, b.lon)


if __name__ == "__main__":
    os.chdir(ROOT)
    freeze_stations()
    summary = {"trips": [headline(t) for t in TRIPS], "batch": batch_stats()}
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "headline.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    saved = cache_answers()
    for t in TRIPS:
        offline_files(t, saved)
