"""Open-Meteo: hourly weather and the CAMS PM2.5 model at each station (no API key).

* Weather history comes from the ERA5 archive (about a 5-day delay); the recent past and the next
  two days come from the forecast endpoint.
* CAMS PM2.5 comes from the air-quality endpoint (global CAMS, ~45 km over India). It is coarse,
  so AirGuard uses it only as a model input and as a baseline, never as station truth.

Open-Meteo is free for non-commercial use and must be credited (with CAMS) in the app.
Responses are cached on disk so repeated backfills don't re-download.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

from airguard.config import BACKEND_ROOT, settings

WEATHER_VARS = "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,boundary_layer_height"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
CACHE = BACKEND_ROOT / "data" / "cache" / "openmeteo"
BATCH = 10  # coordinates per request

_FIELDS = {
    "temperature_2m": "temp",
    "relative_humidity_2m": "humidity",
    "wind_speed_10m": "wind_speed",
    "wind_direction_10m": "wind_dir",
    "boundary_layer_height": "blh",
    "pm2_5": "cams_pm25",
}


def _get(url: str, params: dict, cache: bool) -> list[dict]:
    key = hashlib.sha1((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    path = CACHE / f"{key}.json"
    if cache and path.exists():
        return json.loads(path.read_text())
    for attempt in range(4):
        try:
            r = httpx.get(url, params=params, timeout=120, headers={"User-Agent": settings().user_agent})
        except httpx.TransportError:
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        j = r.json()
        items = j if isinstance(j, list) else [j]
        if cache:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(items))
        return items
    raise RuntimeError(f"Open-Meteo request kept failing: {url}")


def _rows(items: list[dict], stations: list[dict]) -> list[dict]:
    rows = []
    for s, item in zip(stations, items):
        h = item["hourly"]
        for i, t in enumerate(h["time"]):
            row = {"station_id": s["id"], "ts": datetime.fromisoformat(t).replace(tzinfo=timezone.utc)}
            for src, dst in _FIELDS.items():
                if src in h:
                    row[dst] = h[src][i]
            rows.append(row)
    return rows


def _batched(stations: list[dict], url: str, extra: dict, cache: bool) -> list[dict]:
    out = []
    for i in range(0, len(stations), BATCH):
        batch = stations[i:i + BATCH]
        params = {
            "latitude": ",".join(f"{s['lat']:.5f}" for s in batch),
            "longitude": ",".join(f"{s['lon']:.5f}" for s in batch),
            "timezone": "UTC",
            **extra,
        }
        out += _rows(_get(url, params, cache), batch)
    return out


def _windows(start: date, end: date, days: int = 92):
    d = start
    while d <= end:
        e = min(end, d + timedelta(days=days - 1))
        yield d, e
        d = e + timedelta(days=1)


def weather_history(stations: list[dict], start: date, end: date) -> list[dict]:
    rows = []
    for a, b in _windows(start, end):
        rows += _batched(stations, ARCHIVE_URL, {"hourly": WEATHER_VARS, "wind_speed_unit": "ms",
                                                 "start_date": str(a), "end_date": str(b)}, cache=True)
    return rows


def weather_recent(stations: list[dict], past_days: int = 7, forecast_days: int = 2) -> list[dict]:
    return _batched(stations, FORECAST_URL, {"hourly": WEATHER_VARS, "wind_speed_unit": "ms",
                                             "past_days": past_days, "forecast_days": forecast_days}, cache=False)


def cams_history(stations: list[dict], start: date, end: date) -> list[dict]:
    rows = []
    for a, b in _windows(start, end):
        rows += _batched(stations, AQ_URL, {"hourly": "pm2_5", "start_date": str(a), "end_date": str(b)},
                         cache=True)
    return rows


def cams_recent(stations: list[dict], past_days: int = 7, forecast_days: int = 2) -> list[dict]:
    return _batched(stations, AQ_URL, {"hourly": "pm2_5", "past_days": past_days, "forecast_days": forecast_days},
                    cache=False)


def merge(*row_sets: list[dict]) -> list[dict]:
    """Merge rows from several sources on (station_id, ts); later sets fill only missing fields."""
    merged: dict[tuple, dict] = {}
    for rows in row_sets:
        for r in rows:
            k = (r["station_id"], r["ts"])
            cur = merged.setdefault(k, {"station_id": r["station_id"], "ts": r["ts"]})
            for f, v in r.items():
                if v is not None and cur.get(f) is None:
                    cur[f] = v
    return list(merged.values())


def archive_end() -> date:
    """Newest day the ERA5 archive reliably covers."""
    return (datetime.now(timezone.utc) - timedelta(days=6)).date()


def cache_dir() -> Path:
    return CACHE
