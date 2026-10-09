import httpx

from common.timeutil import canon_ts

HOURLY_BASE = "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m"
HOURLY = HOURLY_BASE + ",boundary_layer_height"


def _get(url, params, timeout):
    response = httpx.get(url, params=params, timeout=timeout)
    if response.status_code == 400 and "boundary_layer_height" in str(params.get("hourly", "")):
        response = httpx.get(url, params={**params, "hourly": HOURLY_BASE}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _rows(payload, stations):
    items = payload if isinstance(payload, list) else [payload]
    if len(items) != len(stations):
        raise RuntimeError(f"Open-Meteo returned {len(items)} locations for {len(stations)} stations.")
    rows = []
    for station, item in zip(stations, items):
        hourly = item.get("hourly") or {}
        times = hourly.get("time") or []
        for i, stamp in enumerate(times):
            blh = hourly.get("boundary_layer_height")
            rows.append({
                "station_id": station["id"],
                "ts": canon_ts(stamp),
                "temp": _at(hourly.get("temperature_2m"), i),
                "humidity": _at(hourly.get("relative_humidity_2m"), i),
                "wind_speed": _at(hourly.get("wind_speed_10m"), i),
                "wind_dir": _at(hourly.get("wind_direction_10m"), i),
                "blh": _at(blh, i) if blh is not None else None,
            })
    return rows


def _at(values, index):
    if not values or index >= len(values):
        return None
    return values[index]


def _common(stations):
    return {
        "latitude": ",".join(str(s["lat"]) for s in stations),
        "longitude": ",".join(str(s["lon"]) for s in stations),
        "hourly": HOURLY,
        "wind_speed_unit": "ms",
        "timezone": "UTC",
    }


def fetch_recent(stations, past_days=3, forecast_days=2):
    if not stations:
        return []
    payload = _get(
        "https://api.open-meteo.com/v1/forecast",
        {**_common(stations), "past_days": past_days, "forecast_days": forecast_days},
        60,
    )
    return _rows(payload, stations)


def fetch_archive(stations, start, end):
    if not stations or end < start:
        return []
    payload = _get(
        "https://archive-api.open-meteo.com/v1/archive",
        {**_common(stations), "start_date": str(start), "end_date": str(end)},
        120,
    )
    return _rows(payload, stations)
