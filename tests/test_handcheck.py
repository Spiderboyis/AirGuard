import pytest

from common.geo import haversine_km
from engine.exposure import Station, idw


def test_idw_matches_a_spreadsheet_check():
    """Two stations equally far from the point, so the weights cancel.

    Point (28.6, 77.21). Station A is 0.01 degrees west at PM2.5 100.
    Station B is 0.01 degrees east at PM2.5 40. The inverse-distance average is 70,
    the low bound is 55, and the high bound is 85.
    """
    west = Station("a", 28.6, 77.20, [(0, 100, 80, 120), (24, 100, 80, 120)])
    east = Station("b", 28.6, 77.22, [(0, 40, 30, 50), (24, 40, 30, 50)])
    lat, lon = 28.6, 77.21
    d_west = haversine_km(lat, lon, west.lat, west.lon)
    d_east = haversine_km(lat, lon, east.lat, east.lon)
    assert d_west == pytest.approx(d_east, rel=1e-6)
    assert d_west > 0.05
    pm, lo, hi, nearest = idw(lat, lon, [west, east], 0)
    assert pm == pytest.approx(70)
    assert lo == pytest.approx(55)
    assert hi == pytest.approx(85)
    assert nearest == pytest.approx(d_west)
