"""A space-time PM2.5 field built from per-station forecasts.

Each station has a short series of forecast points (horizon 0 = latest value, then +1h ... +24h).
`ForecastField.sample` answers "what is PM2.5 at these points at these times?" by
1. linearly interpolating each station's series in time, then
2. inverse-distance weighting the nearest stations in space,
and attaches a confidence in [0, 1] from the distance to the nearest station and the width of the
forecast interval. Pure numpy, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from airguard.engine import assumptions as A
from airguard.geo import haversine_matrix

TIME_TOLERANCE_S = 3600.0  # allow sampling up to an hour beyond a station's first/last point


@dataclass
class StationSeries:
    station_id: str
    name: str
    lat: float
    lon: float
    times: np.ndarray            # epoch seconds, ascending
    pred: np.ndarray
    low: np.ndarray
    high: np.ndarray
    obs_age_h: float | None = None
    provider: str | None = None
    is_monitor: bool = True


@dataclass
class Sample:
    pm25: np.ndarray
    low: np.ndarray
    high: np.ndarray
    nearest_km: np.ndarray
    confidence: np.ndarray


@dataclass
class ForecastField:
    stations: list[StationSeries]
    issued_at: datetime
    model_version: str = "unknown"
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        self.stations = [s for s in self.stations if len(s.times) > 0]
        self._lat = np.array([s.lat for s in self.stations], dtype=float)
        self._lon = np.array([s.lon for s in self.stations], dtype=float)

    # ------------------------------------------------------------------------------------------
    @property
    def coverage(self) -> tuple[float, float]:
        """Epoch-second range covered by at least one station."""
        if not self.stations:
            return (0.0, 0.0)
        return (min(float(s.times[0]) for s in self.stations), max(float(s.times[-1]) for s in self.stations))

    def distances(self, lats, lons) -> np.ndarray:
        return haversine_matrix(lats, lons, self._lat, self._lon)

    def values_at(self, times) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Station values at each time: three (n_times, n_stations) arrays; NaN outside coverage."""
        t = np.asarray(times, dtype=float)
        n, m = t.shape[0], len(self.stations)
        P, L, H = (np.full((n, m), np.nan) for _ in range(3))
        for j, s in enumerate(self.stations):
            ok = (t >= s.times[0] - TIME_TOLERANCE_S) & (t <= s.times[-1] + TIME_TOLERANCE_S)
            if not ok.any():
                continue
            P[ok, j] = np.interp(t[ok], s.times, s.pred)
            L[ok, j] = np.interp(t[ok], s.times, s.low)
            H[ok, j] = np.interp(t[ok], s.times, s.high)
        return P, L, H

    def sample(self, lats, lons, times, dist: np.ndarray | None = None) -> Sample:
        lats = np.atleast_1d(np.asarray(lats, dtype=float))
        lons = np.atleast_1d(np.asarray(lons, dtype=float))
        times = np.broadcast_to(np.asarray(times, dtype=float), lats.shape)
        n = lats.shape[0]
        if not self.stations:
            nan = np.full(n, np.nan)
            return Sample(nan, nan, nan, nan, np.zeros(n))

        D = self.distances(lats, lons) if dist is None else dist
        P, L, H = self.values_at(times)
        valid = ~np.isnan(P)
        Dm = np.where(valid, np.maximum(D, A.IDW_MIN_KM), np.inf)

        k = min(A.IDW_NEIGHBOURS, Dm.shape[1])
        idx = np.argsort(Dm, axis=1)[:, :k]
        d_k = np.take_along_axis(Dm, idx, axis=1)
        use = d_k <= A.IDW_MAX_KM
        no_near = ~use.any(axis=1)                       # nothing within range: fall back to the k nearest
        use[no_near] = np.isfinite(d_k[no_near])
        w = np.where(use, 1.0 / np.power(np.where(use, d_k, 1.0), A.IDW_POWER), 0.0)
        wsum = w.sum(axis=1)

        def blend(V):
            v = np.take_along_axis(V, idx, axis=1)
            num = np.where(w > 0, w * np.nan_to_num(v), 0.0).sum(axis=1)
            return np.where(wsum > 0, num / np.where(wsum > 0, wsum, 1.0), np.nan)

        pm, lo, hi = blend(P), blend(L), blend(H)
        nearest = np.where(valid, D, np.inf).min(axis=1)
        nearest = np.where(np.isfinite(nearest), nearest, np.nan)

        spatial = 1.0 / (1.0 + (np.nan_to_num(nearest, nan=1e6) / A.SPATIAL_HALF_KM) ** 2)
        rel_width = np.clip((hi - lo) / np.maximum(pm, 1.0), 0.0, None)
        interval = 1.0 / (1.0 + np.nan_to_num(rel_width, nan=10.0))
        conf = np.sqrt(spatial * interval)
        conf = np.where(np.isnan(pm), 0.0, conf)
        return Sample(pm25=pm, low=lo, high=hi, nearest_km=nearest, confidence=conf)

    def point(self, lat: float, lon: float, ts: float) -> dict:
        s = self.sample([lat], [lon], [ts])
        return {"pm25": _f(s.pm25[0]), "low": _f(s.low[0]), "high": _f(s.high[0]),
                "nearest_station_km": _f(s.nearest_km[0]), "confidence": _f(s.confidence[0])}

    # ------------------------------------------------------------------------------------------
    @classmethod
    def from_rows(cls, stations: list[dict], forecasts: list[dict], issued_at: datetime | None = None,
                  model_version: str | None = None) -> ForecastField:
        """Build from `stations` rows and `forecasts_latest` rows (any horizon order)."""
        by_station: dict[str, list[dict]] = {}
        for r in forecasts:
            by_station.setdefault(r["station_id"], []).append(r)
        series = []
        for s in stations:
            rows = sorted(by_station.get(s["id"], []), key=lambda r: r["target_ts"])
            rows = [r for r in rows if r.get("pm25_pred") is not None]
            if not rows:
                continue
            pred = np.array([r["pm25_pred"] for r in rows], dtype=float)
            series.append(StationSeries(
                station_id=s["id"], name=s["name"], lat=float(s["lat"]), lon=float(s["lon"]),
                times=np.array([_epoch(r["target_ts"]) for r in rows], dtype=float),
                pred=pred,
                low=np.array([r.get("pm25_low") if r.get("pm25_low") is not None else p
                              for r, p in zip(rows, pred)], dtype=float),
                high=np.array([r.get("pm25_high") if r.get("pm25_high") is not None else p
                               for r, p in zip(rows, pred)], dtype=float),
                obs_age_h=next((r.get("obs_age_h") for r in rows if r.get("horizon_h") == 0), None),
                provider=s.get("provider"), is_monitor=bool(s.get("is_monitor", True)),
            ))
        issued = issued_at or max((r["issued_at"] for r in forecasts), default=datetime.now(timezone.utc))
        version = model_version or (forecasts[0]["model_version"] if forecasts else "none")
        return cls(stations=series, issued_at=issued, model_version=version)

    def to_dict(self) -> dict:
        return {
            "issued_at": self.issued_at.isoformat(), "model_version": self.model_version, "meta": self.meta,
            "stations": [{
                "station_id": s.station_id, "name": s.name, "lat": s.lat, "lon": s.lon,
                "times": s.times.tolist(), "pred": s.pred.tolist(), "low": s.low.tolist(), "high": s.high.tolist(),
                "obs_age_h": s.obs_age_h, "provider": s.provider, "is_monitor": s.is_monitor,
            } for s in self.stations],
        }

    @classmethod
    def from_dict(cls, d: dict) -> ForecastField:
        return cls(
            stations=[StationSeries(
                station_id=s["station_id"], name=s["name"], lat=s["lat"], lon=s["lon"],
                times=np.array(s["times"], dtype=float), pred=np.array(s["pred"], dtype=float),
                low=np.array(s["low"], dtype=float), high=np.array(s["high"], dtype=float),
                obs_age_h=s.get("obs_age_h"), provider=s.get("provider"), is_monitor=s.get("is_monitor", True),
            ) for s in d["stations"]],
            issued_at=datetime.fromisoformat(d["issued_at"]), model_version=d.get("model_version", "unknown"),
            meta=d.get("meta", {}),
        )


def _epoch(ts) -> float:
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.timestamp()


def _f(x) -> float | None:
    x = float(x)
    return None if np.isnan(x) else x
