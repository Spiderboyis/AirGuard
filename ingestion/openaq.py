import time
from datetime import datetime, timedelta, timezone

import httpx

from common.config import cfg
from common.timeutil import canon_ts

BASE = "https://api.openaq.org/v3"
DELHI_BBOX = "76.80,28.35,77.55,28.95"  # minLon,minLat,maxLon,maxLat
PM25 = 2
MAX_PAGES = 50


def _utc(obj):
    if not obj:
        return None
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return obj.get("utc") or obj.get("local")
    return None


def _is_pm25(sensor):
    parameter = sensor.get("parameter") or {}
    if parameter.get("id") == PM25:
        return True
    name = str(parameter.get("name", "")).lower().replace(".", "").replace("_", "")
    return name in {"pm25", "pm25mass"}


def get(path, **params):
    key = (cfg().get("OPENAQ_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAQ_API_KEY is not set.")
    last = None
    for _ in range(5):
        time.sleep(1.1)  # stay under 60 requests/minute
        try:
            response = httpx.get(BASE + path, params=params, headers={"X-API-Key": key}, timeout=30)
            last = response
            if response.status_code == 429:
                time.sleep(int(response.headers.get("x-ratelimit-reset", 60)) + 1)
                continue
            if response.status_code >= 500 or response.status_code == 408:
                time.sleep(2)
                continue
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as exc:
            print(f"OpenAQ request error: {exc}. Retrying...")
            time.sleep(2)
            continue
    detail = (last.text[:200] if last is not None else "No response")
    raise RuntimeError(f"OpenAQ kept failing. {detail}")


def pm25_stations(active_days=7):
    out, page = [], 1
    while page <= MAX_PAGES:
        payload = get("/locations", bbox=DELHI_BBOX, parameters_id=PM25, limit=1000, page=page)
        results = payload.get("results") or []
        for loc in results:
            sensor = next((s for s in loc.get("sensors") or [] if _is_pm25(s)), None)
            coords = loc.get("coordinates") or {}
            lat, lon = coords.get("latitude"), coords.get("longitude")
            if not sensor or lat is None or lon is None:
                continue
            last = _utc(loc.get("datetimeLast"))
            active = False
            if last:
                try:
                    seen = datetime.fromisoformat(last.replace("Z", "+00:00"))
                    active = seen > datetime.now(timezone.utc) - timedelta(days=active_days)
                except ValueError:
                    active = False
            out.append({
                "id": str(loc["id"]),
                "name": loc.get("name") or str(loc["id"]),
                "lat": lat,
                "lon": lon,
                "sensor_id": sensor.get("id"),
                "last_utc": last,
                "active": active,
            })
        if len(results) < 1000:
            return out
        page += 1
    return out


def hourly_pm25(sensor_id, start_iso, end_iso):
    rows, page = [], 1
    while page <= MAX_PAGES:
        payload = get(
            f"/sensors/{sensor_id}/hours",
            datetime_from=start_iso,
            datetime_to=end_iso,
            limit=1000,
            page=page,
        )
        results = payload.get("results") or []
        for item in results:
            value = item.get("value")
            period = item.get("period") or {}
            start = _utc(period.get("datetimeFrom"))
            if value is None or start is None or not (0 <= value <= 1000):
                continue
            try:
                rows.append({"ts": canon_ts(start), "value": float(value)})
            except ValueError:
                continue
        if len(results) < 1000:
            return rows
        page += 1
    return rows
