import pytest

from engine.exposure import Station, best_departure, choose, confidence, score_route

ROUTE_A = [(77.20, 28.60), (77.21, 28.60)]
ROUTE_B = [(77.30, 28.70), (77.31, 28.70)]


def flat(pm, lat=28.60, lon=77.205, sid="s"):
    return Station(sid, lat, lon, [(0, pm, pm * 0.8, pm * 1.2), (24, pm, pm * 0.8, pm * 1.2)])


def test_uniform_field_exposure_index_equals_concentration_times_minutes_times_factor():
    r = score_route(ROUTE_A, 600, "walk", 0, [flat(50)])
    assert r["exposure_index"] == pytest.approx(50 * 10 * 1.0, rel=1e-6)
    assert r["mean_pm25"] == pytest.approx(50)


def test_mode_factor_scales_exposure_index():
    walk = score_route(ROUTE_A, 600, "walk", 0, [flat(50)])["exposure_index"]
    cycle = score_route(ROUTE_A, 600, "cycle", 0, [flat(50)])["exposure_index"]
    assert cycle == pytest.approx(walk * 1.6)


def test_route_near_hot_station_has_higher_exposure_index():
    stations = [flat(150, 28.60, 77.205, "hot"), flat(40, 28.70, 77.305, "cool")]
    a = score_route(ROUTE_A, 600, "walk", 0, stations)
    b = score_route(ROUTE_B, 600, "walk", 0, stations)
    assert a["exposure_index"] > b["exposure_index"]


def test_departure_moves_to_cleaner_hour():
    st = Station("s", 28.60, 77.205, [(0, 200, 160, 240), (1, 40, 30, 50), (24, 40, 30, 50)])
    res = best_departure(
        [{"id": "r1", "coords": ROUTE_A, "duration_s": 600}], "walk", [st],
        window_h=4, max_wait_min=240, sensitivity="high", max_extra_min=120,
    )
    assert res["recommended"]["wait_min"] > 0
    assert res["delta"]["exposure_index_pct"] < 0


def test_segment_count_matches_length():
    r = score_route(ROUTE_A, 600, "walk", 0, [flat(50)])
    assert len(r["segments"]) == 5


def opt(wait, dur, expo):
    return {"wait_min": wait, "duration_min": dur, "exposure_index": expo, "route_id": "r1"}


def test_sensitive_users_accept_more_extra_time_for_the_same_gain():
    options = [opt(0, 20, 100), opt(10, 20, 80)]
    assert choose(options, "normal")["recommended"]["wait_min"] == 0
    assert choose(options, "sensitive")["recommended"]["wait_min"] == 10


def test_limits_are_hard_constraints():
    options = [opt(0, 20, 100), opt(60, 20, 10)]
    assert choose(options, "high", max_extra_min=15)["recommended"]["wait_min"] == 0
    assert choose(options, "high", max_extra_min=90, max_wait_min=30)["recommended"]["wait_min"] == 0


def test_segment_lines_follow_a_bend_in_the_route():
    bent = [(77.20, 28.60), (77.21, 28.60), (77.21, 28.61)]
    r = score_route(bent, 900, "walk", 0, [flat(50)])
    assert all(len(s["line"]) >= 2 for s in r["segments"])
    assert any(len(s["line"]) >= 3 for s in r["segments"])


def test_no_stations_gives_a_clear_error():
    with pytest.raises(ValueError):
        score_route(ROUTE_A, 600, "walk", 0, [])


def test_single_station_still_scores():
    assert score_route(ROUTE_A, 600, "walk", 0, [flat(50)])["exposure_index"] > 0


def test_confidence_falls_as_the_station_gets_farther():
    near = score_route(ROUTE_A, 600, "walk", 0, [flat(50, 28.60, 77.205)])
    far = score_route(ROUTE_A, 600, "walk", 0, [flat(50, 28.90, 77.55)])
    assert near["confidence"] > far["confidence"]
    assert confidence(50, 40, 60, 0.1) > confidence(50, 40, 60, 20)


def test_zero_duration_is_rejected():
    with pytest.raises(ValueError):
        score_route(ROUTE_A, 0, "walk", 0, [flat(50)])
