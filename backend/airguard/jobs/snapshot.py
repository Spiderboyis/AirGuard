"""Freeze the current forecast and compute the headline numbers from it.

    python -m airguard.jobs.snapshot [--trips 30]

Writes
* backend/snapshots/<stamp>.json      the frozen forecast field (set DEMO_SNAPSHOT to serve it)
* docs/headline.json                  demo trip + batch statistics, computed by this script
* frontend/public/demo/trip.json      the demo trip result, for the web app's offline mode

The headline is an estimate under the stated assumptions (see docs/methodology.md), computed by
code from one frozen forecast, never typed by hand.
"""

from __future__ import annotations

import argparse
import itertools
import json
import logging
import os
import random
import statistics
from datetime import datetime, timezone

from airguard.config import REPO_ROOT
from airguard.geo import haversine_km
from airguard.services import forecasts, geocoding, routing, trips

log = logging.getLogger("airguard.snapshot")

DEMO_CANDIDATES = [
    ("Hauz Khas Village", "DU North Campus", "cycle"),
    ("Lajpat Nagar", "Connaught Place", "cycle"),
    ("Mayur Vihar Phase 1", "India Gate", "cycle"),
    ("Jamia Millia Islamia", "Connaught Place", "cycle"),
    ("JNU", "AIIMS", "cycle"),
    ("Dwarka Sector 21", "Janakpuri", "cycle"),
    ("Punjabi Bagh", "Karol Bagh", "walk"),
    ("Nehru Place", "Lodhi Garden", "cycle"),
]
PROFILE = {"sensitivity": "sensitive", "max_extra_min": 15, "max_wait_min": 120, "window_h": 4}


def _place(name: str) -> dict:
    p = next(x for x in geocoding.curated() if x["name"] == name)
    return {"lat": p["lat"], "lon": p["lon"]}


def _summary(t: dict) -> dict:
    d = t["decision"]
    return {
        "trip": f"{t['origin']['name']} → {t['destination']['name']}", "mode": t["mode"], "kind": d["kind"],
        "recommended": {"route": d["recommended"]["label"], "wait_min": d["recommended"]["wait_min"],
                        "depart_at": d["recommended"]["depart_at"]},
        "exposure_change_pct": d["delta"]["exposure_index_pct"], "arrival_change_min": d["delta"]["arrival_min"],
        "extra_travel_min": d["delta"]["extra_travel_min"], "wait_min": d["delta"]["wait_min"],
        "confidence": d["recommended"]["confidence"],
        "lowest_possible_pct": round((d["lowest"]["exposure_index"] / d["baseline"]["exposure_index"] - 1) * 100, 1),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--trips", type=int, default=30, help="random trips between curated places for batch stats")
    p.add_argument("--seed", type=int, default=7)
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # 1. Freeze the live field, with "now" pinned to the moment of the snapshot.
    fld = forecasts.current_field()
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    fld.meta["now"] = now.isoformat()
    stamp = now.strftime("%Y%m%d-%H%M")
    snap_dir = REPO_ROOT / "backend" / "snapshots"
    snap_dir.mkdir(exist_ok=True)
    snap = snap_dir / f"{stamp}.json"
    snap.write_text(json.dumps(fld.to_dict()))
    log.info("snapshot %s (%d stations, model %s)", snap.relative_to(REPO_ROOT), len(fld.stations), fld.model_version)

    # 2. Serve everything below from the frozen field.
    os.environ["DEMO_SNAPSHOT"] = str(snap)
    from airguard.config import settings
    settings.cache_clear()
    forecasts.clear_cache()

    demo = []
    for o, d, mode in DEMO_CANDIDATES:
        try:
            t = trips.analyze(_place(o), _place(d), mode, origin_name=o, destination_name=d, save=False, **PROFILE)
        except (routing.RoutingError, Exception) as e:  # keep going; report what worked
            log.warning("demo %s → %s failed: %s", o, d, e)
            continue
        demo.append(t)
        s = _summary(t)
        log.info("%-40s %-15s %+6.1f%%  %+5.1f min", s["trip"], s["kind"], s["exposure_change_pct"], s["arrival_change_min"])

    # The headline trip: the biggest recommended reduction among the candidates.
    best = min(demo, key=lambda t: t["decision"]["delta"]["exposure_index_pct"]) if demo else None

    # 3. Batch statistics over random trips between curated places (4-20 km apart).
    rng = random.Random(a.seed)
    places = geocoding.curated()
    pairs = [(x, y) for x, y in itertools.permutations(places, 2)
             if 4 <= haversine_km(x["lat"], x["lon"], y["lat"], y["lon"]) <= 20]
    rng.shuffle(pairs)
    batch = []
    for x, y in pairs[: a.trips]:
        try:
            t = trips.analyze({"lat": x["lat"], "lon": x["lon"]}, {"lat": y["lat"], "lon": y["lon"]}, "cycle",
                              origin_name=x["name"], destination_name=y["name"], save=False, **PROFILE)
            batch.append(_summary(t))
        except Exception as e:
            log.warning("batch %s → %s failed: %s", x["name"], y["name"], e)
    improved = [b for b in batch if b["kind"] != "stay"]
    stats = {
        "trips": len(batch),
        "with_cleaner_option": len(improved),
        "median_exposure_change_pct": round(statistics.median(b["exposure_change_pct"] for b in improved), 1) if improved else None,
        "median_arrival_change_min": round(statistics.median(b["arrival_change_min"] for b in improved), 1) if improved else None,
        "median_lowest_possible_pct": round(statistics.median(b["lowest_possible_pct"] for b in batch), 1) if batch else None,
    }
    log.info("batch: %s", stats)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "snapshot": str(snap.relative_to(REPO_ROOT)),
        "forecast_issued_at": fld.issued_at.isoformat(), "frozen_now": now.isoformat(),
        "model_version": fld.model_version, "profile": PROFILE,
        "headline": _summary(best) if best else None,
        "demo_trips": [_summary(t) for t in demo], "batch": stats, "batch_trips": batch,
        "note": "Model estimates under stated assumptions (docs/methodology.md), not measured doses.",
    }
    (REPO_ROOT / "docs").mkdir(exist_ok=True)
    (REPO_ROOT / "docs" / "headline.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    if best:
        demo_dir = REPO_ROOT / "frontend" / "public" / "demo"
        demo_dir.mkdir(parents=True, exist_ok=True)
        (demo_dir / "trip.json").write_text(json.dumps(best, ensure_ascii=False))
        (demo_dir / "stations.json").write_text(json.dumps({
            "issued_at": fld.issued_at.isoformat(), "model_version": fld.model_version, "now": now.isoformat(),
            "stations": forecasts.station_summaries(fld)}, ensure_ascii=False))
    log.info("wrote docs/headline.json; set DEMO_SNAPSHOT=%s to serve this snapshot", snap.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
