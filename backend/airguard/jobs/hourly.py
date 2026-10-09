"""Hourly refresh: new readings, weather and CAMS, then a new forecast.

    python -m airguard.jobs.hourly          # run once
    python -m airguard.jobs.hourly --loop   # run now, then at five past every hour (local mode)

On AWS the same `run()` is invoked by an EventBridge schedule.
"""

from __future__ import annotations

import argparse
import logging
import time
import traceback
from datetime import datetime, timedelta, timezone

from airguard.ingestion import sync
from airguard.ingestion.openaq import OpenAQ
from airguard.ml import predict

log = logging.getLogger("airguard.hourly")


def run(refresh_stations: bool = False) -> dict:
    started = datetime.now(timezone.utc)
    details: dict = {}
    try:
        oaq = OpenAQ()
        stations = sync.sync_stations(oaq) if refresh_stations else sync.active_stations()
        if not stations:
            stations = sync.sync_stations(oaq)
        details["measurement_rows"] = sync.sync_measurements(oaq, stations, started - timedelta(days=3))
        details["weather_rows"] = sync.sync_weather(stations, (started - timedelta(days=3)).date(), history=False)
        details.update(predict.run())
        sync.record_run("hourly", "ok", details, started)
    except Exception as e:  # recorded for /health, then re-raised
        details["error"] = repr(e)
        sync.record_run("hourly", "error", details, started)
        raise
    return details


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--loop", action="store_true", help="keep running every hour")
    p.add_argument("--forecast-only", action="store_true", help="skip ingestion, just re-issue the forecast")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if a.forecast_only:
        predict.run()
        return
    runs = 0
    while True:
        try:
            log.info("hourly run: %s", run(refresh_stations=(runs % 24 == 0)))
        except Exception:
            traceback.print_exc()
        runs += 1
        if not a.loop:
            return
        now = datetime.now(timezone.utc)
        nxt = (now + timedelta(hours=1)).replace(minute=5, second=0, microsecond=0)
        time.sleep(max(60.0, (nxt - now).total_seconds()))


if __name__ == "__main__":
    main()
