"""OpenAQ v3 client: Delhi PM2.5 stations and their hourly history.

Free tier limits are 60 requests/minute and 2,000/hour, so every call is spaced ~1 s apart and a
429 waits for the window to reset. OpenAQ requires source attribution (shown in the app footer).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import httpx

from airguard.config import settings
from airguard.geo import NCR_BBOX

BASE = "https://api.openaq.org/v3"
PM25 = 2
MIN_INTERVAL_S = 1.05
VALID_RANGE = (0.0, 1000.0)  # drops negatives and sentinel values such as 985/999


class OpenAQError(RuntimeError):
    pass


def _parse_ts(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


class OpenAQ:
    def __init__(self, api_key: str | None = None):
        key = api_key or settings().openaq_api_key
        if not key:
            raise OpenAQError("OPENAQ_API_KEY is not set. Add it to .env.local (see docs/setup.md).")
        self._client = httpx.Client(base_url=BASE, headers={"X-API-Key": key, "User-Agent": settings().user_agent},
                                    timeout=40)
        self._last_call = 0.0
        self.calls = 0

    def get(self, path: str, **params) -> dict:
        for attempt in range(6):
            wait = MIN_INTERVAL_S - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            self.calls += 1
            try:
                r = self._client.get(path, params=params)
            except httpx.TransportError:
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code == 429:
                time.sleep(int(r.headers.get("x-ratelimit-reset", 30)) + 1)
                continue
            if r.status_code >= 500:
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code == 401:
                raise OpenAQError("OpenAQ rejected the API key (401).")
            r.raise_for_status()
            return r.json()
        raise OpenAQError(f"OpenAQ request kept failing: {path}")

    # ------------------------------------------------------------------------------------------
    def pm25_locations(self, active_days: int = 14) -> list[dict]:
        """Fixed PM2.5 locations inside Delhi NCR that reported within `active_days`."""
        bbox = ",".join(str(v) for v in NCR_BBOX)
        cutoff = datetime.now(timezone.utc) - timedelta(days=active_days)
        out, page = [], 1
        while True:
            j = self.get("/locations", bbox=bbox, parameters_id=PM25, limit=1000, page=page)
            for loc in j["results"]:
                if loc.get("isMobile"):
                    continue
                last = _parse_ts((loc.get("datetimeLast") or {}).get("utc"))
                if not last or last < cutoff:
                    continue
                out.append({
                    "id": str(loc["id"]),
                    "name": loc["name"],
                    "lat": loc["coordinates"]["latitude"],
                    "lon": loc["coordinates"]["longitude"],
                    "provider": (loc.get("provider") or {}).get("name"),
                    "is_monitor": bool(loc.get("isMonitor")),
                    "last_seen": last,
                    "sensor_ids": [x["id"] for x in loc.get("sensors", []) if x["parameter"]["id"] == PM25],
                })
            if len(j["results"]) < 1000:
                return out
            page += 1

    def pm25_sensor(self, location_id: str, fallback_ids: list[int] | None = None) -> dict | None:
        """The location's PM2.5 sensor with the most recent data (old CPCB sites carry retired sensors).

        If OpenAQ fails on the sensor listing, fall back to the newest sensor id from /locations.
        """
        try:
            j = self.get(f"/locations/{location_id}/sensors")
        except (OpenAQError, httpx.HTTPError):
            return {"id": max(fallback_ids), "last": None, "first": None} if fallback_ids else None
        best = None
        for s in j["results"]:
            if s["parameter"]["id"] != PM25:
                continue
            last = _parse_ts((s.get("datetimeLast") or {}).get("utc"))
            if last and (best is None or last > best["last"]):
                best = {"id": s["id"], "last": last, "first": _parse_ts((s.get("datetimeFirst") or {}).get("utc"))}
        return best

    def hourly(self, sensor_id: int, start: datetime, end: datetime) -> list[dict]:
        """Hourly PM2.5 averages as [{ts, value}], ts = the UTC hour the average represents.

        CPCB averages run on IST hours (UTC :30), so each period is labelled by its midpoint
        floored to the hour; this puts every provider on the same hourly grid.
        """
        rows, page = [], 1
        while True:
            j = self.get(f"/sensors/{sensor_id}/hours", datetime_from=start.isoformat(),
                         datetime_to=end.isoformat(), limit=1000, page=page)
            for r in j["results"]:
                v = r.get("value")
                if v is None or not (VALID_RANGE[0] <= v <= VALID_RANGE[1]):
                    continue
                t0 = _parse_ts(r["period"]["datetimeFrom"]["utc"])
                t1 = _parse_ts(r["period"]["datetimeTo"]["utc"])
                mid = t0 + (t1 - t0) / 2
                rows.append({"ts": mid.replace(minute=0, second=0, microsecond=0), "value": float(v)})
            if len(j["results"]) < 1000:
                return rows
            page += 1
