"""Place search: a curated list of common Delhi places first, then Photon (OpenStreetMap, no key).

Photon results are restricted to Delhi NCR and cached in Postgres.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from functools import lru_cache
from pathlib import Path

import httpx

from airguard import db
from airguard.config import settings
from airguard.geo import NCR_BBOX, in_ncr

PLACES_FILE = Path(__file__).resolve().parents[1] / "data" / "places.json"
_lock = threading.Lock()
_last = [0.0]


@lru_cache(maxsize=1)
def curated() -> list[dict]:
    return json.loads(PLACES_FILE.read_text())


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def _curated_matches(q: str) -> list[dict]:
    nq = _norm(q)
    if not nq:
        return []
    out = []
    for p in curated():
        name = _norm(p["name"])
        if name.startswith(nq) or f" {nq}" in f" {name}" or nq in _norm(p["area"]):
            out.append({"name": p["name"], "detail": p["area"], "lat": p["lat"], "lon": p["lon"], "source": "curated"})
    return out


def _photon(q: str, limit: int) -> list[dict]:
    key = hashlib.sha1(f"photon:{q.lower()}:{limit}".encode()).hexdigest()
    try:
        rows = db.query("select response from geocode_cache where key = %s", (key,))
        if rows:
            return rows[0]["response"]
    except db.DatabaseUnavailable:
        pass
    with _lock:  # be gentle with the public instance
        wait = 1.0 - (time.monotonic() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()
    params = {"q": q, "limit": limit, "lat": 28.61, "lon": 77.21, "lang": "en",
              "bbox": ",".join(str(v) for v in NCR_BBOX)}
    r = httpx.get(f"{settings().geocoder_url}/api/", params=params, timeout=10,
                  headers={"User-Agent": settings().user_agent})
    r.raise_for_status()
    out = []
    for f in r.json().get("features", []):
        lon, lat = f["geometry"]["coordinates"]
        if not in_ncr(lat, lon):
            continue
        pr = f["properties"]
        detail = ", ".join(x for x in (pr.get("street"), pr.get("district") or pr.get("locality"), pr.get("city"))
                           if x and x != pr.get("name"))
        out.append({"name": pr.get("name") or detail or q, "detail": detail or "Delhi NCR",
                    "lat": round(lat, 6), "lon": round(lon, 6), "source": "osm"})
    try:
        db.upsert("geocode_cache", [{"key": key, "response": out}], ["key"])
    except db.DatabaseUnavailable:
        pass
    return out


def search(q: str, limit: int = 6) -> list[dict]:
    q = q.strip()[:120]
    if len(q) < 2:
        return []
    results = _curated_matches(q)
    if len(results) < limit:
        try:
            seen = {(round(r["lat"], 3), round(r["lon"], 3)) for r in results}
            for r in _photon(q, limit):
                k = (round(r["lat"], 3), round(r["lon"], 3))
                if k not in seen:
                    results.append(r)
                    seen.add(k)
        except httpx.HTTPError:
            pass  # curated results still work offline
    return results[:limit]
