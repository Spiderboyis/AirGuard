"""One-time history load: stations, hourly PM2.5, weather, CAMS and fires.

    python -m airguard.jobs.backfill --days 365

Safe to re-run: every step is incremental and idempotent. Takes ~15 minutes for a year of
history across ~75 stations, mostly waiting on OpenAQ's rate limit.
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta, timezone

from airguard.ingestion import sync
from airguard.ingestion.openaq import OpenAQ


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--days", type=int, default=365, help="days of history to load (default 365)")
    p.add_argument("--skip-measurements", action="store_true")
    p.add_argument("--skip-weather", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    started = datetime.now(timezone.utc)
    start = started.replace(minute=0, second=0, microsecond=0) - timedelta(days=args.days)
    t0 = time.monotonic()
    oaq = OpenAQ()
    stations = sync.sync_stations(oaq)
    details = {"days": args.days, "stations": len(stations)}
    if not args.skip_weather:
        details["weather_rows"] = sync.sync_weather(stations, start.date(), history=True)
    if not args.skip_measurements:
        details["measurement_rows"] = sync.sync_measurements(oaq, stations, start)
    details["openaq_calls"] = oaq.calls
    sync.record_run("backfill", "ok", details, started)
    logging.info("backfill done in %.1f min: %s", (time.monotonic() - t0) / 60, details)


if __name__ == "__main__":
    main()
