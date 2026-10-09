import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import db
from ingestion import fires, openaq, weather


def chunks(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def main(days=365):
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    stations = [s for s in openaq.pm25_stations() if s["active"]]
    print("active PM2.5 stations:", len(stations))
    if not stations:
        raise SystemExit("No active Delhi PM2.5 stations. Check OPENAQ_API_KEY and the bbox.")
    db.upsert("stations", [{
        "id": s["id"], "name": s["name"], "lat": s["lat"], "lon": s["lon"],
        "sensor_id": s["sensor_id"], "last_seen": s["last_utc"], "source": "openaq",
    } for s in stations], "id")
    for s in stations:
        try:
            if db.select("measurements", select="ts", station_id=f"eq.{s['id']}", limit=1):
                print(f"Skipping {s['name']}, already in DB")
                continue
            rows = openaq.hourly_pm25(s["sensor_id"], start.isoformat(), end.isoformat())
            if rows:
                db.upsert(
                    "measurements",
                    [{"station_id": s["id"], "pollutant": "pm25", "unit": "µg/m³", **r} for r in rows],
                    "station_id,pollutant,ts",
                )
            print(s["name"], len(rows), "hourly values")
        except Exception as exc:
            print(f"Skipping {s['name']} due to error: {exc}")
    fire_list = fires.fetch_range(start.date(), end.date())
    table = fires.sector_table(stations, fire_list, start.date(), end.date())
    archive_end = (end - timedelta(days=8)).date()
    for batch in chunks(stations, 10):
        wx = weather.fetch_recent(batch, past_days=14, forecast_days=0)
        if archive_end >= start.date():
            wx += weather.fetch_archive(batch, start.date(), archive_end)
        for w in wx:
            stamp = datetime.fromisoformat(w["ts"])
            w["fires_upwind"] = fires.upwind_count(table, w["station_id"], start.date(), stamp, w.get("wind_dir"))
        if wx:
            db.upsert("weather", wx, "station_id,ts")


if __name__ == "__main__":
    main()
