"""Feature construction shared by training and hourly prediction (one code path, no skew).

Rows are (station, issue hour t0, horizon h); the target is PM2.5 at t0 + h. All inputs are
"wide" hourly frames indexed by UTC hour with one column per station.

Feed-delay mode
---------------
CPCB feeds on OpenAQ sometimes arrive many hours late. When a station's newest observation is
older than STALE_AFTER_H, its own lag features are blanked and the model leans on CAMS, weather and
any neighbours that are still reporting. Training blanks the same features on a random share of
rows, so the model has learned exactly this situation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from airguard.geo import haversine_matrix

HORIZONS = [0, 1, 3, 6, 12, 24]
STALE_AFTER_H = 3
NEIGHBOUR_KM = 30.0

OWN_FEATURES = ["lag0", "lag1", "lag2", "lag3", "lag6", "lag12", "lag24", "roll3", "roll24", "delta3",
                "cams_bias72"]
NEIGHBOUR_FEATURES = ["nbr_idw", "nbr_nearest_km", "nbr_n15"]
FEATURES = OWN_FEATURES + NEIGHBOUR_FEATURES + [
    "cams_t0", "cams_target", "cams_target_max3",
    "blh_t0", "blh_target", "wind_t0", "wind_target", "wind_u_target", "wind_v_target",
    "rh_target", "temp_target", "fires_upwind",
    "hour_sin", "hour_cos", "dow", "horizon_h", "lat", "lon", "is_monitor",
]


@dataclass
class Inputs:
    """Hourly wide frames over a common index (past and up to two days ahead for covariates)."""
    pm25: pd.DataFrame
    cams: pd.DataFrame
    blh: pd.DataFrame
    wind_speed: pd.DataFrame
    wind_dir: pd.DataFrame
    humidity: pd.DataFrame
    temp: pd.DataFrame
    fires: pd.DataFrame
    stations: pd.DataFrame          # index = station id; columns lat, lon, is_monitor


def build_inputs(stations: list[dict], measurements: list[dict], weather: list[dict],
                 index: pd.DatetimeIndex | None = None) -> Inputs:
    st = pd.DataFrame(stations).set_index("id")[["lat", "lon", "is_monitor"]]
    ids = list(st.index)
    m = pd.DataFrame(measurements)
    w = pd.DataFrame(weather)
    if index is None:
        lo = min(m["ts"].min(), w["ts"].min())
        hi = max(m["ts"].max(), w["ts"].max())
        index = pd.date_range(pd.Timestamp(lo).floor("h"), pd.Timestamp(hi).floor("h"), freq="h", tz="UTC")

    def wide(df: pd.DataFrame, col: str) -> pd.DataFrame:
        if df.empty or col not in df:
            return pd.DataFrame(np.nan, index=index, columns=ids)
        p = df.pivot_table(index="ts", columns="station_id", values=col, aggfunc="mean")
        p.index = pd.DatetimeIndex(p.index).tz_convert("UTC") if p.index.tz is not None else \
            pd.DatetimeIndex(p.index).tz_localize("UTC")
        return p.reindex(index=index, columns=ids).astype("float32")

    return Inputs(
        pm25=wide(m, "value"), cams=wide(w, "cams_pm25"), blh=wide(w, "blh"), wind_speed=wide(w, "wind_speed"),
        wind_dir=wide(w, "wind_dir"), humidity=wide(w, "humidity"), temp=wide(w, "temp"),
        fires=wide(w, "fires_upwind"), stations=st,
    )


def _neighbour_weights(st: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    d = haversine_matrix(st["lat"], st["lon"], st["lat"], st["lon"])
    np.fill_diagonal(d, np.inf)
    w = np.where(d <= NEIGHBOUR_KM, 1.0 / np.maximum(d, 0.3) ** 2, 0.0)
    return w, d


def _neighbours(pm: pd.DataFrame, st: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """IDW of other stations' current value, distance to nearest reporting one, count within 15 km."""
    w, d = _neighbour_weights(st)
    vals = pm.to_numpy(dtype=float)
    have = ~np.isnan(vals)
    num = np.nan_to_num(vals) @ w.T
    den = have.astype(float) @ w.T
    idw = np.where(den > 0, num / np.where(den > 0, den, 1), np.nan)
    # Nearest reporting neighbour and neighbours within 15 km, one station at a time to bound memory.
    nearest = np.full(vals.shape, np.nan)
    n15 = np.zeros(vals.shape)
    for j in range(vals.shape[1]):
        dj = np.where(have, d[j][None, :], np.inf)                # (hours, other stations)
        mn = dj.min(axis=1)
        nearest[:, j] = np.where(np.isfinite(mn), mn, np.nan)
        n15[:, j] = (dj <= 15.0).sum(axis=1)
    mk = lambda a: pd.DataFrame(a, index=pm.index, columns=pm.columns).astype("float32")  # noqa: E731
    return mk(idw), mk(nearest), mk(n15)


def build_frame(x: Inputs, t0s: pd.DatetimeIndex, horizon: int, mask: np.ndarray | None = None,
                with_target: bool = True) -> pd.DataFrame:
    """Long frame of features (and target) for every station at each issue time in `t0s`.

    `mask` (bool per output row) blanks own-station features to simulate a delayed feed; it is
    also applied automatically wherever a station's newest observation is older than STALE_AFTER_H.
    """
    pm = x.pm25
    ids = list(pm.columns)
    feats: dict[str, pd.DataFrame] = {}
    for k in (0, 1, 2, 3, 6, 12, 24):
        feats[f"lag{k}"] = pm.shift(k)
    feats["roll3"] = pm.rolling(3, min_periods=1).mean()
    feats["roll24"] = pm.rolling(24, min_periods=6).mean()
    feats["delta3"] = pm - pm.shift(3)
    cams_where_obs = x.cams.where(pm.notna())
    feats["cams_bias72"] = pm.rolling(72, min_periods=12).mean() / cams_where_obs.rolling(72, min_periods=12).mean()

    # Hours since each station last reported (for the staleness rule).
    last_seen = pm.notna().astype(float).replace(0.0, np.nan)
    last_seen = last_seen.mul(np.arange(len(pm))[:, None]).ffill()
    age = pd.DataFrame(np.arange(len(pm))[:, None] - last_seen.to_numpy(), index=pm.index, columns=ids)

    fresh = pm.where(age <= STALE_AFTER_H)
    idw, nearest, n15 = _neighbours(fresh, x.stations)
    feats["nbr_idw"], feats["nbr_nearest_km"], feats["nbr_n15"] = idw, nearest, n15

    feats["cams_t0"] = x.cams
    feats["cams_target"] = x.cams.shift(-horizon)
    feats["cams_target_max3"] = x.cams.shift(-horizon).rolling(3, min_periods=1, center=True).max()
    feats["blh_t0"] = x.blh
    feats["blh_target"] = x.blh.shift(-horizon)
    feats["wind_t0"] = x.wind_speed
    feats["wind_target"] = x.wind_speed.shift(-horizon)
    rad = np.radians(x.wind_dir.shift(-horizon))
    feats["wind_u_target"] = -x.wind_speed.shift(-horizon) * np.sin(rad)
    feats["wind_v_target"] = -x.wind_speed.shift(-horizon) * np.cos(rad)
    feats["rh_target"] = x.humidity.shift(-horizon)
    feats["temp_target"] = x.temp.shift(-horizon)
    feats["fires_upwind"] = x.fires

    sel = {k: v.reindex(t0s).to_numpy(dtype="float32").reshape(-1) for k, v in feats.items()}
    n_t, n_s = len(t0s), len(ids)
    out = pd.DataFrame(sel)
    out["station_id"] = np.tile(np.array(ids, dtype=object), n_t)
    out["t0"] = np.repeat(t0s.values, n_s)
    target_time = t0s + pd.Timedelta(hours=horizon)
    ist_hour = (target_time.hour + target_time.minute / 60 + 5.5) % 24
    out["hour_sin"] = np.repeat(np.sin(2 * np.pi * ist_hour / 24), n_s).astype("float32")
    out["hour_cos"] = np.repeat(np.cos(2 * np.pi * ist_hour / 24), n_s).astype("float32")
    out["dow"] = np.repeat(((target_time + pd.Timedelta(hours=5.5)).dayofweek).values, n_s).astype("float32")
    out["horizon_h"] = np.float32(horizon)
    out["lat"] = np.tile(x.stations["lat"].to_numpy(dtype="float32"), n_t)
    out["lon"] = np.tile(x.stations["lon"].to_numpy(dtype="float32"), n_t)
    out["is_monitor"] = np.tile(x.stations["is_monitor"].to_numpy(dtype="float32"), n_t)
    out["obs_age_h"] = age.reindex(t0s).to_numpy(dtype="float32").reshape(-1)

    stale = ~(out["obs_age_h"] <= STALE_AFTER_H).to_numpy()
    blank = stale if mask is None else (stale | mask)
    out.loc[blank, OWN_FEATURES] = np.nan
    out["feed_delayed"] = blank
    if with_target:
        out["y"] = pm.shift(-horizon).reindex(t0s).to_numpy(dtype="float32").reshape(-1)
    return out
