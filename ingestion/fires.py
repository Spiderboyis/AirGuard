import csv
import io
import math
from datetime import date, timedelta

import httpx
import numpy as np

from common.config import cfg

FIRMS = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
REGION = "73.5,28.0,78.0,32.5"  # west,south,east,north: Punjab, Haryana, Delhi NCR


def fetch(day_range, start=None, source="VIIRS_SNPP_NRT"):
    key = (cfg().get("FIRMS_MAP_KEY") or "").strip()
    if not key:
        return []
    url = f"{FIRMS}/{key}/{source}/{REGION}/{day_range}" + (f"/{start}" if start else "")
    response = httpx.get(url, timeout=90)
    response.raise_for_status()
    if not response.text.startswith("latitude"):
        if response.text.strip() == "":
            return []
        raise RuntimeError(response.text[:200])
    return [
        {"lat": float(row["latitude"]), "lon": float(row["longitude"]), "day": date.fromisoformat(row["acq_date"])}
        for row in csv.DictReader(io.StringIO(response.text))
        if row.get("latitude") and row.get("acq_date")
    ]


def fetch_range(start: date, end: date, window=5):
    if not (cfg().get("FIRMS_MAP_KEY") or "").strip():
        print("FIRMS_MAP_KEY is not set; fire counts stay zero.")
        return []
    out, day = [], start
    while day <= end:
        rows = []
        for source in ("VIIRS_SNPP_SP", "VIIRS_SNPP_NRT"):
            try:
                rows = fetch(window, day, source)
            except Exception as exc:
                print(f"FIRMS {source} failed for {day}: {exc}")
                rows = []
            if rows:
                break
        out += rows
        day += timedelta(days=window)
    return out


def sector_table(stations, fires, start: date, end: date, min_km=20, max_km=400):
    """{station_id: array[n_days, 8]} of fires from the two complete days before each day.

    Sector 0 is north. Empty fire lists return zeros instead of failing the forecast job.
    """
    n = (end - start).days + 1
    if n < 1:
        return {s["id"]: np.zeros((0, 8)) for s in stations}
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
        dist = 2 * 6371.0088 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
        y = np.sin(dl) * np.cos(f_lat)
        x = np.cos(lat1) * np.sin(f_lat) - np.sin(lat1) * np.cos(f_lat) * np.cos(dl)
        brg = (np.degrees(np.arctan2(y, x)) + 360) % 360
        keep = (dist >= min_km) & (dist <= max_km) & (f_day >= 0) & (f_day < n)
        sector = (((brg[keep] + 22.5) // 45) % 8).astype(int)
        daily = np.zeros((n, 8))
        if keep.any():
            np.add.at(daily, (f_day[keep], sector), 1)
        prev2 = np.zeros_like(daily)
        prev2[1:] += daily[:-1]
        prev2[2:] += daily[:-2]
        out[s["id"]] = prev2
    return out


def upwind_count(table, station_id, start: date, ts, wind_from_deg):
    arr = table.get(station_id)
    if hasattr(ts, "date"):
        day = (ts.date() - start).days
    else:
        return 0
    if arr is None or wind_from_deg is None or not (0 <= day < len(arr)):
        return 0
    return int(arr[day][int(((wind_from_deg + 22.5) // 45) % 8)])
