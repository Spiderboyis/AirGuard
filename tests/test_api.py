from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.service import get_routes, route_cache_key
from common.db import upsert

client = TestClient(app)


def test_geocode_known_place_returns_lat_lon():
    response = client.get("/geocode", params={"q": "hauz khas"})
    assert response.status_code == 200
    assert set(response.json()) == {"lat", "lon"}


def test_geocode_rejects_a_too_short_query():
    assert client.get("/geocode", params={"q": "a"}).status_code == 422


def test_health_reports_no_data_on_an_empty_database():
    body = client.get("/health").json()
    assert body["status"] == "no_data"
    assert body["stations"] == 0


def test_config_serves_levels_and_mode_factors():
    body = client.get("/config").json()
    assert body["mode_factors"]["cycle"] == 1.6
    assert body["levels"][0]["name"] == "low"
    assert body["preferences"]["sensitive"] == 7.0


def test_invalid_mode_and_far_away_window_are_rejected():
    payload = {
        "origin": {"lat": 28.55, "lon": 77.20},
        "destination": {"lat": 28.68, "lon": 77.21},
        "mode": "bus",
    }
    assert client.post("/routes/score", json=payload).status_code == 422
    payload["mode"] = "cycle"
    payload["window_h"] = 20
    assert client.post("/departure/best", json=payload).status_code == 422
    assert client.get("/forecast", params={"lat": 19.0, "lon": 72.8, "horizon_h": 1}).status_code == 422


def test_missing_stations_return_the_error_shape():
    response = client.post("/routes/score", json={
        "origin": {"lat": 28.55, "lon": 77.20},
        "destination": {"lat": 28.68, "lon": 77.21},
        "mode": "cycle",
    })
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "no_data"


def _seed_station_and_route(now_pm=80, later_pm=80):
    now = datetime.now(timezone.utc)
    later = now + timedelta(hours=1)
    generated = now.isoformat()
    upsert("stations", [{"id": "s", "name": "Test", "lat": 28.60, "lon": 77.205, "sensor_id": 1}], "id")
    upsert("forecasts_latest", [
        {"station_id": "s", "horizon_h": 0, "target_ts": now.isoformat(), "pm25_pred": now_pm, "pm25_low": now_pm * 0.8, "pm25_high": now_pm * 1.2,
         "model_version": "test", "generated_at": generated},
        {"station_id": "s", "horizon_h": 1, "target_ts": later.isoformat(), "pm25_pred": later_pm, "pm25_low": later_pm * 0.8, "pm25_high": later_pm * 1.2,
         "model_version": "test", "generated_at": generated},
    ], "station_id,horizon_h")
    origin, dest = (28.60, 77.20), (28.60, 77.21)
    upsert("route_cache", [{
        "key": route_cache_key("walk", origin[0], origin[1], dest[0], dest[1]),
        "response": [{
            "id": "r1",
            "coords": [[77.20, 28.60], [77.21, 28.60]],
            "duration_s": 600,
            "distance_m": 1000,
        }],
    }], "key")
    return {"origin": {"lat": origin[0], "lon": origin[1]}, "destination": {"lat": dest[0], "lon": dest[1]}, "mode": "walk"}


def test_a_partial_forecast_run_does_not_reuse_stale_horizons():
    now = datetime.now(timezone.utc)
    old = (now - timedelta(hours=5)).isoformat()
    upsert("stations", [{"id": "s", "name": "Test", "lat": 28.60, "lon": 77.205, "sensor_id": 1}], "id")
    upsert("forecasts_latest", [
        {"station_id": "s", "horizon_h": 0, "target_ts": now.isoformat(), "pm25_pred": 80, "pm25_low": 70, "pm25_high": 90,
         "model_version": "test", "generated_at": now.isoformat()},
        {"station_id": "s", "horizon_h": 1, "target_ts": (now + timedelta(hours=1)).isoformat(), "pm25_pred": 400,
         "pm25_low": 300, "pm25_high": 500, "model_version": "test", "generated_at": old},
    ], "station_id,horizon_h")
    response = client.post("/routes/score", json={
        "origin": {"lat": 28.60, "lon": 77.20},
        "destination": {"lat": 28.60, "lon": 77.21},
        "mode": "walk",
    })
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "no_data"


def test_routing_prefers_ors_then_a_saved_geometry_then_osrm(monkeypatch):
    from common.config import cfg

    calls = []
    monkeypatch.setenv("ORS_API_KEY", "test-key")
    cfg.cache_clear()

    def ors(*_args):
        calls.append("ors")
        return [{"id": "ors1", "coords": [[77.2, 28.6], [77.21, 28.6]], "duration_s": 600, "distance_m": 1000}]

    def osrm(*_args):
        calls.append("osrm")
        raise AssertionError("OSRM should not run when an earlier source returned a route")

    monkeypatch.setattr("api.service._ors_routes", ors)
    monkeypatch.setattr("api.service._osrm_routes", osrm)
    monkeypatch.setattr("api.service._fixtures", lambda: {
        "cycle:28.6000,77.2000>28.6000,77.2100": [{"id": "fix"}],
    })
    got = get_routes(28.6, 77.2, 28.6, 77.21, "cycle")
    assert calls == ["ors"]
    assert got[0]["id"] == "ors1"

    calls.clear()

    def ors_down(*_args):
        calls.append("ors")
        raise httpx.HTTPError("down")

    monkeypatch.setattr("api.service._ors_routes", ors_down)
    monkeypatch.setattr("api.service._fixtures", lambda: {
        "cycle:28.6100,77.2000>28.6100,77.2100": [
            {"id": "fix1", "coords": [[77.2, 28.61], [77.21, 28.61]], "duration_s": 600, "distance_m": 1000},
        ],
    })
    got = get_routes(28.61, 77.2, 28.61, 77.21, "cycle")
    assert calls == ["ors"]
    assert got[0]["id"] == "fix1"

    monkeypatch.setenv("ORS_API_KEY", "")
    cfg.cache_clear()
    calls.clear()

    def osrm_ok(*_args):
        calls.append("osrm")
        return [{"id": "o1", "coords": [[77.2, 28.62], [77.21, 28.62]], "duration_s": 500, "distance_m": 900}]

    monkeypatch.setattr("api.service._osrm_routes", osrm_ok)
    monkeypatch.setattr("api.service._fixtures", lambda: {})
    got = get_routes(28.62, 77.2, 28.62, 77.21, "cycle")
    assert calls == ["osrm"]
    assert got[0]["id"] == "o1"

    def osrm_down(*_args):
        raise httpx.HTTPError("down")

    monkeypatch.setattr("api.service._osrm_routes", osrm_down)
    monkeypatch.setenv("AIRGUARD_STRAIGHT_ROUTES", "")
    with pytest.raises(ValueError, match="No route"):
        get_routes(28.63, 77.2, 28.63, 77.21, "cycle")
    monkeypatch.setenv("AIRGUARD_STRAIGHT_ROUTES", "1")
    got = get_routes(28.63, 77.2, 28.63, 77.21, "cycle")
    assert len(got) == 2


def test_cached_route_is_scored_from_forecasts():
    payload = _seed_station_and_route()
    response = client.post("/routes/score", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["routes"][0]["exposure_index"] == pytest_approx(80 * 10 * 1.0, rel=0.02)
    assert body["routes"][0]["is_fastest"] is True
    assert "error" not in body


def test_departure_prefers_the_cleaner_hour_for_a_sensitive_user():
    payload = _seed_station_and_route(now_pm=200, later_pm=40)
    payload.update({"sensitivity": "high", "max_extra_min": 120, "max_wait_min": 180, "window_h": 2})
    response = client.post("/departure/best", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["recommended"]["wait_min"] > 0
    assert body["delta"]["exposure_index_pct"] < 0


def test_analyze_stores_a_trip_the_reader_can_load():
    payload = _seed_station_and_route()
    response = client.post("/trips/analyze", json=payload)
    assert response.status_code == 200, response.text
    trip_id = response.json()["trip_id"]
    from common.db import select
    stored = select("route_cache", select="response", key=f"eq.trip:{trip_id}")
    assert stored and stored[0]["response"]["recommended"]["route_id"] == "r1"


def pytest_approx(value, rel=0.02):
    import pytest
    return pytest.approx(value, rel=rel)
