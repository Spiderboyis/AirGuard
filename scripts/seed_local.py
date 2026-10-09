"""Build a local SQLite database, a small model, and the offline demo file.

The measurements are synthetic. They exist so the app can run before OpenAQ,
OpenRouteService, and Supabase keys are filled in. The model version is
`synthetic-v1`. Do not quote its error numbers as a Delhi backtest.
"""

import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)
os.environ["LOCAL"] = "1"
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_KEY"] = ""
os.environ["MODEL_VERSION"] = "synthetic-v1"
os.environ["MODEL_DIR"] = str(ROOT / "models" / "synthetic-v1")
os.environ.setdefault("MODEL_TREES", "160")
os.environ.setdefault("AIRGUARD_DB", str(ROOT / "data" / "local.db"))
os.environ["AIRGUARD_OFFLINE_INGEST"] = "1"

from agent.explain import explain_saved
from api import service
from common import db
from common.config import cfg
from engine.exposure import level_config
from ingestion.handler import lambda_handler, reset_models
from ml.train import main as train_main

cfg.cache_clear()

STATIONS = [
    {"id": "s-hauz", "name": "Hauz Khas", "lat": 28.5494, "lon": 77.2001, "sensor_id": 1},
    {"id": "s-aiims", "name": "AIIMS", "lat": 28.5672, "lon": 77.2100, "sensor_id": 2},
    {"id": "s-lodhi", "name": "Lodhi Garden", "lat": 28.5931, "lon": 77.2197, "sensor_id": 3},
    {"id": "s-india", "name": "India Gate", "lat": 28.6129, "lon": 77.2295, "sensor_id": 4},
    {"id": "s-cp", "name": "Connaught Place", "lat": 28.6315, "lon": 77.2167, "sensor_id": 5},
    {"id": "s-du", "name": "DU North Campus", "lat": 28.6889, "lon": 77.2100, "sensor_id": 6},
    {"id": "s-dwarka", "name": "Dwarka", "lat": 28.5921, "lon": 77.0460, "sensor_id": 7},
    {"id": "s-noida", "name": "Noida", "lat": 28.5355, "lon": 77.3910, "sensor_id": 8},
]
QUESTION = "I cycle from Hauz Khas to DU North Campus. Which route should I take, and when should I leave?"


def pm_value(lat, lon, stamp, peak_hour):
    """High at the seed's latest hour, then a sharp drop over the next hour.

    The same shape repeats every day, so the horizon models can learn it. East of
    the corridor is dirtier than west, which gives alternative routes something to separate.
    """
    ist = stamp + timedelta(hours=5, minutes=30)
    dh = (ist.hour - peak_hour) % 24
    if dh <= 1:
        wave = 120 * (1 - 0.8 * dh)
    elif dh <= 5:
        wave = 18
    else:
        wave = 35
    base = 25 + 80 * max(0.0, lon - 77.08)
    return round(max(8.0, base + wave), 2)


def weather_row(station, stamp):
    ist_hour = (stamp + timedelta(hours=5, minutes=30)).hour
    return {
        "station_id": station["id"],
        "ts": stamp.replace(tzinfo=timezone.utc).isoformat(),
        "temp": round(22 + 8 * math.sin((ist_hour - 9) / 24 * 2 * math.pi), 2),
        "humidity": round(48 + 15 * math.cos((ist_hour - 6) / 24 * 2 * math.pi), 2),
        "wind_speed": 2.4,
        "wind_dir": 320.0,
        "blh": round(300 + 900 * max(0.0, math.sin((ist_hour - 6) / 24 * 2 * math.pi)), 1),
        "fires_upwind": 0,
    }


def write_history(days=100):
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    peak_hour = (end + timedelta(hours=5, minutes=30)).hour
    db.upsert("stations", [{**s, "source": "synthetic", "last_seen": end.isoformat()} for s in STATIONS], "id")
    measurements, weather = [], []
    stamp = start
    while stamp <= end:
        for station in STATIONS:
            measurements.append({
                "station_id": station["id"], "pollutant": "pm25", "unit": "µg/m³",
                "value": pm_value(station["lat"], station["lon"], stamp, peak_hour),
                "ts": stamp.replace(tzinfo=timezone.utc).isoformat(),
            })
            weather.append(weather_row(station, stamp))
        stamp += timedelta(hours=1)
    db.upsert("measurements", measurements, "station_id,pollutant,ts")
    db.upsert("weather", weather, "station_id,ts")
    print(f"wrote {len(measurements)} synthetic hourly measurements")


def save_fixture(mode, origin, dest):
    routes = service.get_routes(origin["lat"], origin["lon"], dest["lat"], dest["lon"], mode)
    path = ROOT / "fixtures" / "demo_routes.json"
    path.parent.mkdir(exist_ok=True)
    existing = json.loads(path.read_text()) if path.exists() else {}
    existing[service._place_key(mode, origin["lat"], origin["lon"], dest["lat"], dest["lon"])] = routes
    path.write_text(json.dumps(existing))
    service._FIXTURES = existing
    return routes


def freeze_and_demo():
    stations, age = service.load_stations()
    snap = [{"id": s.id, "lat": s.lat, "lon": s.lon, "series": [list(p) for p in s.series]} for s in stations]
    captured = datetime.now(timezone.utc).isoformat()
    db.upsert("route_cache", [{
        "key": "snapshot:stations",
        "response": {"captured_at": captured, "data_age_at_capture_min": age, "stations": snap},
    }], "key")
    origin, dest = {"lat": 28.5494, "lon": 77.2001}, {"lat": 28.6889, "lon": 77.2100}
    try:
        save_fixture("cycle", origin, dest)
    except Exception as exc:
        print("routing services failed, using straight-line stand-ins:", exc)
        os.environ["AIRGUARD_STRAIGHT_ROUTES"] = "1"
        save_fixture("cycle", origin, dest)
    service._CACHE.clear()
    analyzed = service.analyze_trip(origin, dest, "cycle", True, 4.0, 120, "sensitive", 30)
    summary = db.select("route_cache", select="response", key=f"eq.trip:{analyzed['trip_id']}")[0]["response"]
    answer = explain_saved(summary)
    saved = [{
        "question": QUESTION,
        "answer": answer,
        "tool_calls": [{
            "name": "get_trip_result",
            "input": {"trip_id": analyzed["trip_id"]},
            "output": json.dumps(summary)[:2000],
        }],
        "cached": True,
    }]
    import hashlib
    db.upsert("route_cache", [{
        "key": "agent:" + hashlib.sha1(QUESTION.strip().lower().encode()).hexdigest(),
        "response": {"answer": answer, "tool_calls": saved[0]["tool_calls"], "cached": True},
    }], "key")
    body = {
        "trip": "Hauz Khas to DU North Campus",
        "request": {
            "from": "Hauz Khas", "to": "DU North Campus", "mode": "cycle",
            "sensitivity": "sensitive", "max_extra_min": 30, "max_wait_min": 120,
        },
        "snapshot": service.snapshot_info(),
        "levels": level_config(),
        "chat": saved,
        "routes": analyzed["routes"],
        "departure": analyzed["departure"],
    }
    demo = ROOT / "frontend" / "public" / "demo" / "trip1.json"
    demo.parent.mkdir(parents=True, exist_ok=True)
    demo.write_text(json.dumps(body))
    headline = {
        "label": "synthetic local seed, not a Delhi measurement",
        "trip": body["trip"],
        "routes": len(analyzed["routes"]["routes"]),
        "departure": analyzed["departure"]["delta"],
        "recommended_wait_min": analyzed["departure"]["recommended"]["wait_min"],
        "recommended_route": analyzed["departure"]["recommended"]["route_id"],
        "reliability": analyzed["departure"]["recommended"].get("confidence"),
    }
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "headline.json").write_text(json.dumps(headline, indent=2))
    print(json.dumps(headline, indent=2))
    print("wrote", demo)


def main():
    db.reset_connection()
    db_path = Path(os.environ["AIRGUARD_DB"])
    if db_path.exists():
        db_path.unlink()
    fixture = ROOT / "fixtures" / "demo_routes.json"
    if fixture.exists():
        fixture.unlink()
    service._FIXTURES = {}
    write_history()
    print("training synthetic-v1")
    train_main()
    reset_models()
    print(lambda_handler({}, None))
    service._CACHE.clear()
    freeze_and_demo()


if __name__ == "__main__":
    main()
