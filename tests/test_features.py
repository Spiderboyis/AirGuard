import math
from datetime import datetime, timedelta

from ml.features import FEATURES, hour, local_dt, row
from ml.train import active_features


def test_hour_of_day_uses_india_local_time():
    # 02:00 UTC is 07:30 IST, so the local hour is 7.
    t = datetime(2026, 1, 15, 2, 0)
    assert local_dt(t).hour == 7
    pm = {"s": {t: 40.0, t - timedelta(hours=1): 40.0}}
    wx = {"s": {t: {"temp": 20, "humidity": 50, "wind_speed": 2, "wind_dir": 0, "blh": 400, "fires_upwind": 0}}}
    vector = row("s", t, 1, pm, wx, {})
    assert vector[FEATURES.index("hod_sin")] == pytest_approx(math.sin(2 * math.pi * 7 / 24))
    assert hour("2026-01-15T02:30:00Z") == datetime(2026, 1, 15, 2, 0)


def pytest_approx(value):
    import pytest
    return pytest.approx(value)


def test_now_feature_cannot_be_dropped():
    names = active_features({"now", "blh"})
    assert names[0] == "now"
    assert "blh" not in names
