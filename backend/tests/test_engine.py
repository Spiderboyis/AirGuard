"""Unit tests for the exposure engine (pure functions, no network)."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from airguard.engine import assumptions as A
from airguard.engine.departure import decide, evaluate
from airguard.engine.exposure import ForecastUnavailable, RouteInput, prepare, score
from airguard.engine.field import ForecastField, StationSeries
from airguard.engine.segments import split_line
from airguard.geo import haversine_km

T0 = datetime(2026, 10, 9, 2, 0, tzinfo=timezone.utc).timestamp()
H = 3600.0


def station(sid, lat, lon, values, hours=(0, 1, 3, 6, 12, 24), spread=0.0):
    v = np.array(values if np.ndim(values) else [values] * len(hours), dtype=float)
    return StationSeries(station_id=sid, name=sid, lat=lat, lon=lon,
                         times=np.array([T0 + h * H for h in hours]), pred=v,
                         low=v * (1 - spread), high=v * (1 + spread))


def field_of(*stations):
    return ForecastField(stations=list(stations), issued_at=datetime.fromtimestamp(T0, tz=timezone.utc),
                         model_version="test")


def straight_route(rid, lat0, lon0, lat1, lon1, minutes, n=20):
    pts = [[lon0 + (lon1 - lon0) * i / n, lat0 + (lat1 - lat0) * i / n] for i in range(n + 1)]
    return RouteInput(id=rid, geometry=pts, distance_km=haversine_km(lat0, lon0, lat1, lon1), duration_min=minutes)


# A grid of stations around central Delhi with the same value everywhere.
def uniform_field(value=100.0):
    return field_of(*[station(f"s{i}{j}", 28.55 + 0.05 * i, 77.15 + 0.05 * j, value)
                      for i in range(3) for j in range(3)])


# ---------------------------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------------------------
def test_split_line_preserves_length():
    r = straight_route("r", 28.55, 77.20, 28.60, 77.20, 10)
    segs = split_line(r.geometry, 0.2)
    assert sum(s.length_km for s in segs) == pytest.approx(r.distance_km, rel=1e-3)
    assert all(s.length_km <= 0.2 + 1e-9 for s in segs)
    assert segs[-1].length_km <= 0.2


def test_split_line_degenerate():
    assert split_line([[77.2, 28.6]]) == []
    assert split_line([[77.2, 28.6], [77.2, 28.6]]) == []


# ---------------------------------------------------------------------------------------------
# Exposure index
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("mode", list(A.MODE_FACTORS))
def test_uniform_field_gives_concentration_times_time_times_factor(mode):
    fld = uniform_field(100.0)
    r = straight_route("r", 28.58, 77.18, 28.62, 77.22, minutes=30)
    s = score(prepare(r, fld), fld, T0, mode)
    assert s.exposure_index == pytest.approx(100.0 * 0.5 * A.MODE_FACTORS[mode], rel=1e-6)
    assert s.mean_pm25 == pytest.approx(100.0)
    assert s.risk == "poor"  # CPCB band 91-120 µg/m³


def test_hot_station_raises_nearby_route_only():
    background = [station(f"b{i}", lat, lon, 60.0) for i, (lat, lon) in
                  enumerate([(28.50, 77.10), (28.50, 77.30), (28.70, 77.10), (28.70, 77.30)])]
    hot = station("hot", 28.60, 77.15, 300.0)
    fld = field_of(*background, hot)
    west = straight_route("west", 28.56, 77.15, 28.64, 77.15, 30)   # passes the hot station
    east = straight_route("east", 28.56, 77.26, 28.64, 77.26, 30)   # 10 km away from it
    sw, se = (score(prepare(r, fld), fld, T0, "cycle") for r in (west, east))
    assert sw.exposure_index > se.exposure_index * 1.3
    assert sw.peak_pm25 > 200


def test_confidence_falls_with_distance_from_stations():
    fld = field_of(station("a", 28.60, 77.20, 100.0), station("b", 28.61, 77.21, 100.0))
    near = fld.point(28.601, 77.201, T0)
    far = fld.point(28.75, 77.40, T0)
    assert near["confidence"] > 0.9
    assert far["confidence"] < 0.2
    assert far["nearest_station_km"] > 20


def test_confidence_falls_with_interval_width():
    narrow = field_of(station("a", 28.60, 77.20, 100.0, spread=0.05)).point(28.6, 77.2, T0)
    wide = field_of(station("a", 28.60, 77.20, 100.0, spread=0.6)).point(28.6, 77.2, T0)
    assert wide["confidence"] < narrow["confidence"]


def test_time_interpolation_between_horizons():
    fld = field_of(station("a", 28.60, 77.20, [100, 200, 200, 200, 200, 200]))
    assert fld.point(28.6, 77.2, T0 + 0.5 * H)["pm25"] == pytest.approx(150.0)


def test_later_departure_into_cleaner_hours_lowers_exposure():
    # PM2.5 falls from 200 to 80 over the morning, as boundary-layer mixing deepens.
    vals = [200, 180, 120, 80, 80, 80]
    fld = field_of(*[station(f"s{i}", 28.55 + 0.05 * i, 77.20, vals) for i in range(3)])
    r = straight_route("r", 28.57, 77.20, 28.63, 77.20, 30)
    p = prepare(r, fld)
    assert score(p, fld, T0 + 3 * H, "walk").exposure_index < score(p, fld, T0, "walk").exposure_index * 0.7


def test_outside_forecast_window_raises():
    fld = uniform_field()
    r = straight_route("r", 28.58, 77.18, 28.62, 77.22, 30)
    with pytest.raises(ForecastUnavailable):
        score(prepare(r, fld), fld, T0 + 30 * H, "walk")


def test_hand_checked_route():
    """Two stations, a 3-segment route; expected value worked out by hand (docs/methodology.md)."""
    fld = field_of(station("a", 28.600, 77.200, 100.0), station("b", 28.600, 77.230, 200.0))
    # 0.6 km due east from station a, 12 minutes walking.
    lon_end = 77.200 + 0.6 / (111.32 * np.cos(np.radians(28.6)))
    r = RouteInput(id="r", geometry=[[77.200, 28.600], [lon_end, 28.600]], distance_km=0.6, duration_min=12)
    s = score(prepare(r, fld), fld, T0, "walk")
    # Segment midpoints at 0.1, 0.3, 0.5 km east of a; b is ~2.93 km east of a.
    d_b = haversine_km(28.6, 77.2, 28.6, 77.23)
    expected = 0.0
    for x in (0.1, 0.3, 0.5):
        da, db = max(x, A.IDW_MIN_KM), d_b - x
        w_a, w_b = 1 / da ** 2, 1 / db ** 2
        expected += (w_a * 100 + w_b * 200) / (w_a + w_b) * (4 / 60)
    assert s.exposure_index == pytest.approx(expected, rel=1e-3)


# ---------------------------------------------------------------------------------------------
# Departure optimiser and decision layer
# ---------------------------------------------------------------------------------------------
def morning_setup():
    vals = [200, 190, 140, 90, 90, 90]
    fld = field_of(*[station(f"s{i}", 28.55 + 0.05 * i, 77.20, vals) for i in range(3)])
    fast = straight_route("fast", 28.57, 77.20, 28.63, 77.20, 30)
    slow = straight_route("slow", 28.57, 77.19, 28.63, 77.19, 36)
    return fld, [prepare(fast, fld), prepare(slow, fld)]


def test_optimizer_covers_window():
    fld, routes = morning_setup()
    opts = evaluate(routes, fld, T0, "cycle", window_h=4)
    assert {o.wait_min for o in opts} == set(range(0, 241, 15))
    assert len(opts) == 17 * 2


def test_sensitivity_changes_choice_not_estimate():
    fld, routes = morning_setup()
    opts = evaluate(routes, fld, T0, "cycle", window_h=4)
    normal = decide(opts, "normal", max_extra_min=15, max_wait_min=240)
    high = decide(opts, "high", max_extra_min=15, max_wait_min=240)
    # Same options, same numbers...
    assert normal.baseline.exposure_index == high.baseline.exposure_index
    # ...but the more sensitive user accepts at least as much delay for cleaner air.
    assert high.recommended.exposure_index <= normal.recommended.exposure_index
    assert high.wait_min >= normal.wait_min


def test_limits_are_respected():
    fld, routes = morning_setup()
    opts = evaluate(routes, fld, T0, "cycle", window_h=4)
    d = decide(opts, "high", max_extra_min=0, max_wait_min=30)
    assert d.wait_min <= 30
    assert d.recommended.duration_min <= d.baseline.duration_min


def test_flat_air_keeps_fastest_route_now():
    fld = uniform_field(100.0)
    fast = straight_route("fast", 28.58, 77.18, 28.62, 77.22, 30)
    slow = straight_route("slow", 28.58, 77.17, 28.62, 77.21, 40)
    opts = evaluate([prepare(fast, fld), prepare(slow, fld)], fld, T0, "walk")
    d = decide(opts, "high")
    assert d.kind == "stay"
    assert d.recommended.route_id == "fast" and d.wait_min == 0
    assert d.exposure_change_pct == 0.0


def test_unknown_inputs_rejected():
    fld, routes = morning_setup()
    opts = evaluate(routes, fld, T0, "cycle")
    with pytest.raises(ValueError):
        decide(opts, "extreme")
    with pytest.raises(ValueError):
        score(routes[0], fld, T0, "bus")
