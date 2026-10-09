"""Bring the database up to date with the external sources.

Used by both the one-time backfill and the hourly job. Every step is incremental: measurements are
fetched from each station's newest stored hour onward, so re-running is cheap and safe.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from airguard import db
from airguard.ingestion import firms, openmeteo
from airguard.ingestion.openaq import OpenAQ

log = logging.getLogger("airguard.ingestion")


def _now_hour() -> datetime:
    return datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)


def sync_stations(oaq: OpenAQ, active_days: int = 14) -> list[dict]:
    """Discover active PM2.5 locations, pick each one's live sensor, and upsert them."""
    known = {r["id"]: r for r in db.query("select id, sensor_id from stations")}
    stations = []
    for loc in oaq.pm25_locations(active_days=active_days):
        sensor_id = (known.get(loc["id"]) or {}).get("sensor_id")
        if sensor_id is None:
            sensor = oaq.pm25_sensor(loc["id"], loc.get("sensor_ids"))
            if not sensor:
                continue
            sensor_id = sensor["id"]
        row = {k: v for k, v in loc.items() if k != "sensor_ids"}
        stations.append({**row, "sensor_id": sensor_id, "source": "openaq", "active": True})
    db.upsert("stations", stations, ["id"])
    db.execute("update stations set active = false where id <> all(%s)", ([s["id"] for s in stations],))
    log.info("stations: %d active PM2.5 locations", len(stations))
    return stations


def active_stations() -> list[dict]:
    return db.query("select id, name, lat, lon, sensor_id, provider, is_monitor from stations "
                    "where active order by id")


def sync_measurements(oaq: OpenAQ, stations: list[dict], default_start: datetime) -> int:
    newest = {r["station_id"]: r["ts"] for r in db.query(
        "select station_id, max(ts) as ts from measurements where pollutant = 'pm25' group by 1")}
    end = _now_hour() + timedelta(hours=1)
    total = 0
    for i, s in enumerate(stations, 1):
        since = newest.get(s["id"])
        start = max(default_start, since - timedelta(hours=3)) if since else default_start
        try:
            rows = oaq.hourly(s["sensor_id"], start, end)
        except Exception as e:  # one bad station must not stop the run
            log.warning("[%d/%d] %s: skipped (%s)", i, len(stations), s["name"], e)
            continue
        db.upsert("measurements", [{"station_id": s["id"], "pollutant": "pm25", "unit": "µg/m³",
                                    "ts": r["ts"], "value": r["value"]} for r in rows],
                  ["station_id", "pollutant", "ts"])
        total += len(rows)
        log.info("[%d/%d] %s: %d hours from %s", i, len(stations), s["name"], len(rows), start.date())
    return total


def sync_weather(stations: list[dict], start: date, history: bool) -> int:
    """Weather, CAMS PM2.5 and upwind fires per station-hour, from `start` to two days ahead."""
    sets = []
    cutoff = openmeteo.archive_end()
    if history and start <= cutoff:
        sets.append(openmeteo.weather_history(stations, start, cutoff))
        sets.append(openmeteo.cams_history(stations, start, cutoff))
    sets.append(openmeteo.weather_recent(stations, past_days=8, forecast_days=2))
    sets.append(openmeteo.cams_recent(stations, past_days=8, forecast_days=2))
    rows = openmeteo.merge(*sets)
    rows = [r for r in rows if r["ts"].date() >= start]

    fire_start = start - timedelta(days=2)
    fire_end = (_now_hour() + timedelta(days=2)).date()
    detections = firms.fetch_range(fire_start, _now_hour().date())
    table = firms.sector_table(stations, detections, fire_start, fire_end)
    for r in rows:
        r["fires_upwind"] = firms.upwind_count(table, r["station_id"], fire_start, r["ts"], r.get("wind_dir"))
    cols = ["station_id", "ts", "temp", "humidity", "wind_speed", "wind_dir", "blh", "cams_pm25", "fires_upwind"]
    db.upsert("weather", [{c: r.get(c) for c in cols} for r in rows], ["station_id", "ts"])
    log.info("weather: %d station-hours (%d fire detections)", len(rows), len(detections))
    return len(rows)


def record_run(kind: str, status: str, details: dict, started_at: datetime) -> None:
    db.execute("insert into pipeline_runs (kind, status, started_at, finished_at, details) "
               "values (%s, %s, %s, now(), %s)", (kind, status, started_at, db.Jsonb(details)))
