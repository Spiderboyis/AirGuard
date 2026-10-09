"""Small geodesy helpers shared by ingestion, the forecast features and the exposure engine."""

from __future__ import annotations

import math

import numpy as np

R_KM = 6371.0088

# Delhi NCR, approximate: (min_lon, min_lat, max_lon, max_lat). Trips must start and end inside it.
NCR_BBOX = (76.80, 28.35, 77.55, 28.95)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_KM * math.asin(math.sqrt(a))


def haversine_matrix(lat_a, lon_a, lat_b, lon_b) -> np.ndarray:
    """Pairwise distances in km between points A (n) and B (m), as an (n, m) array."""
    la = np.radians(np.asarray(lat_a, dtype=float))[:, None]
    oa = np.radians(np.asarray(lon_a, dtype=float))[:, None]
    lb = np.radians(np.asarray(lat_b, dtype=float))[None, :]
    ob = np.radians(np.asarray(lon_b, dtype=float))[None, :]
    a = np.sin((lb - la) / 2) ** 2 + np.cos(la) * np.cos(lb) * np.sin((ob - oa) / 2) ** 2
    return 2 * R_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def in_ncr(lat: float, lon: float) -> bool:
    min_lon, min_lat, max_lon, max_lat = NCR_BBOX
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon
