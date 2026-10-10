"""Load training / prediction inputs from the database."""

from __future__ import annotations

from datetime import datetime

from airguard import db
from airguard.ml.features import Inputs, build_inputs


def stations() -> list[dict]:
    return db.query("select id, name, lat, lon, is_monitor, provider from stations where active order by id")


def load_inputs(start: datetime, end: datetime) -> Inputs:
    st = stations()
    m = db.query("select station_id, ts, value from measurements where pollutant = 'pm25' and ts >= %s and ts <= %s",
                 (start, end))
    w = db.query("select station_id, ts, temp, humidity, wind_speed, wind_dir, blh, cams_pm25, fires_upwind "
                 "from weather where ts >= %s and ts <= %s", (start, end))
    import pandas as pd

    index = pd.date_range(pd.Timestamp(start).floor("h"), pd.Timestamp(end).floor("h"), freq="h")
    if index.tz is None:
        index = index.tz_localize("UTC")
    return build_inputs(st, m, w, index=index)
