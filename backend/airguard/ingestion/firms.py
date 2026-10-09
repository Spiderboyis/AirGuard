"""NASA FIRMS active-fire detections, reduced to an "upwind fires" count per station and hour.

Fires are counted per 45-degree sector around each station on the two complete days before each
day, so nothing from the current day leaks into a forecast issued that morning. A fire is upwind
when its bearing from the station falls in the sector the wind is blowing from.
"""

from __future__ import annotations

import csv
import io
import math
from datetime import date, datetime, timedelta

import httpx
import numpy as np

from airguard.config import settings

FIRMS = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
REGION = "73.5,28.0,78.0,32.5"  # west,south,east,north: Punjab, Haryana and Delhi NCR (approx.)
WINDOW_DAYS = 5


def _fetch(day_range: int, start: date | None, source: str) -> list[dict]:
    key = settings().firms_map_key
    url = f"{FIRMS}/{key}/{source}/{REGION}/{day_range}" + (f"/{start}" if start else "")
    r = httpx.get(url, timeout=90)
    r.raise_for_status()
    text = r.text.strip()
    if not text:
        return []
    if not text.startswith("latitude"):
        raise RuntimeError(f"FIRMS: {text[:200]}")
    return [{"lat": float(x["latitude"]), "lon": float(x["longitude"]), "day": date.fromisoformat(x["acq_date"])}
            for x in csv.DictReader(io.StringIO(text))]


def fetch_range(start: date, end: date) -> list[dict]:
    """All VIIRS detections between start and end (standard product, falling back to near-real-time)."""
    if not settings().firms_map_key:
        return []
    out, d = [], start
    while d <= end:
        rows = []
        for source in ("VIIRS_SNPP_SP", "VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT"):
            try:
                rows = _fetch(WINDOW_DAYS, d, source)
            except (httpx.HTTPError, RuntimeError):
                rows = []
            if rows:
                break
        out += rows
        d += timedelta(days=WINDOW_DAYS)
    return out


def sector_table(stations: list[dict], fires: list[dict], start: date, end: date,
                 min_km: float = 20, max_km: float = 400) -> dict[str, np.ndarray]:
    """{station_id: array[n_days, 8]} of detections on days d-1 and d-2 per sector (0 = north)."""
    n = (end - start).days + 1
    if not fires:
        return {s["id"]: np.zeros((n, 8)) for s in stations}
    f_lat = np.radians(np.array([f["lat"] for f in fires], dtype=float))
    f_lon = np.radians(np.array([f["lon"] for f in fires], dtype=float))
    f_day = np.array([(f["day"] - start).days for f in fires], dtype=int)
    out = {}
    for s in stations:
        lat1, lon1 = math.radians(s["lat"]), math.radians(s["lon"])
        dl = f_lon - lon1
        a = np.sin((f_lat - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(f_lat) * np.sin(dl / 2) ** 2
        dist = 2 * 6371.0088 * np.arcsin(np.sqrt(a))
        y = np.sin(dl) * np.cos(f_lat)
        x = np.cos(lat1) * np.sin(f_lat) - np.sin(lat1) * np.cos(f_lat) * np.cos(dl)
        brg = (np.degrees(np.arctan2(y, x)) + 360) % 360
        keep = (dist >= min_km) & (dist <= max_km) & (f_day >= 0) & (f_day < n)
        sector = (((brg[keep] + 22.5) // 45) % 8).astype(int)
        daily = np.zeros((n, 8))
        np.add.at(daily, (f_day[keep], sector), 1)
        prev2 = np.zeros_like(daily)
        prev2[1:] += daily[:-1]
        prev2[2:] += daily[:-2]
        out[s["id"]] = prev2
    return out


def upwind_count(table: dict[str, np.ndarray], station_id: str, start: date, ts: datetime,
                 wind_from_deg: float | None) -> int | None:
    arr = table.get(station_id)
    if arr is None or wind_from_deg is None:
        return None
    d = (ts.date() - start).days
    if not 0 <= d < len(arr):
        return None
    return int(arr[d][int(((wind_from_deg + 22.5) // 45) % 8)])
