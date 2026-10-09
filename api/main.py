import os
import threading
import time
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from pydantic import BaseModel, Field

from api import service

app = FastAPI(title="AirGuard API", version="0.1")
_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
_origins = [item.strip() for item in os.environ.get("ALLOWED_ORIGINS", _default_origins).split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or _default_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
Mode = Literal["walk", "cycle", "car"]
Sensitivity = Literal["normal", "sensitive", "high"]
_rate_hits: dict[str, list[float]] = {}
_rate_lock = threading.Lock()


def allow_chat(ip: str, limit: int = 10, window: float = 60) -> bool:
    now = time.time()
    with _rate_lock:
        if len(_rate_hits) > 200:
            expired_ips = [k for k, stamps in _rate_hits.items() if not stamps or now - stamps[-1] >= window]
            for k in expired_ips:
                del _rate_hits[k]
        recent = [stamp for stamp in _rate_hits.get(ip, []) if now - stamp < window]
        if len(recent) >= limit:
            _rate_hits[ip] = recent
            return False
        recent.append(now)
        _rate_hits[ip] = recent
        return True


def reset_rate_limit():
    with _rate_lock:
        _rate_hits.clear()


class Point(BaseModel):
    lat: float = Field(ge=28.2, le=29.0)
    lon: float = Field(ge=76.7, le=77.7)


class TripRequest(BaseModel):
    origin: Point
    destination: Point
    mode: Mode = "walk"
    window_h: float = Field(4.0, gt=0, le=6)
    max_extra_min: int = Field(15, ge=0, le=120)
    max_wait_min: int = Field(120, ge=0, le=720)
    sensitivity: Sensitivity = "normal"
    demo: bool = False


class DepartureRequest(BaseModel):
    origin: Point
    destination: Point
    mode: Mode = "walk"
    window_h: float = Field(4.0, gt=0, le=6)
    max_wait_min: int = Field(120, ge=0, le=720)
    max_extra_min: int = Field(15, ge=0, le=120)
    sensitivity: Sensitivity = "normal"
    demo: bool = False


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    profile: dict | None = None
    trip_id: str | None = None
    from_place: str | None = None
    to_place: str | None = None
    history: list[dict] = []
    demo: bool = False


class Segment(BaseModel):
    lat: float
    lon: float
    pm25: float
    minutes: float
    line: list[list[float]]


class RouteOut(BaseModel):
    id: str
    duration_min: float
    distance_km: float
    exposure_index: float
    mean_pm25: float
    risk: str
    confidence: float
    segments: list[Segment]
    geometry: list[list[float]]
    is_cleanest: bool
    is_fastest: bool


class TripResponse(BaseModel):
    routes: list[RouteOut]
    data_age_min: int | None
    mode_factor: float


def err(status, code, message):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(RequestValidationError)
async def _validation(_, exc):
    message = exc.errors()[0]["msg"] if exc.errors() else "Invalid input."
    return err(422, "invalid_input", str(message))


@app.exception_handler(HTTPException)
async def _http(_, exc):
    return err(exc.status_code, "error", str(exc.detail))


@app.exception_handler(ValueError)
async def _no_data(_, exc):
    return err(503, "no_data", str(exc))


@app.exception_handler(httpx.HTTPError)
async def _upstream(_, exc):
    print("upstream failed:", repr(exc))
    return err(502, "upstream_unavailable", "A data provider is not responding. Try again shortly.")


@app.get("/health")
def health():
    try:
        stations, age = service.load_stations()
        return {
            "status": "ok" if stations else "no_data",
            "stations": len(stations),
            "observation_age_min": age,
            "forecast_age_min": service.forecast_age_min(),
        }
    except Exception as exc:
        print("health failed:", repr(exc))
        return {"status": "no_data", "stations": 0, "observation_age_min": None, "forecast_age_min": None}


@app.get("/geocode")
def geocode(q: str = Query(min_length=2, max_length=80)):
    try:
        lat, lon = service.geocode(q)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    if not (28.2 <= lat <= 29.0 and 76.7 <= lon <= 77.7):
        raise HTTPException(422, "That place is outside Delhi NCR, the only area supported.")
    return {"lat": lat, "lon": lon}


@app.get("/places/search")
def search_places(q: str = Query(min_length=2, max_length=80)):
    try:
        results = service.search_places(q)
        return {"results": results}
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc



@app.get("/forecast")
def forecast(lat: float = Query(ge=28.2, le=29.0), lon: float = Query(ge=76.7, le=77.7),
             horizon_h: float = Query(1, ge=0, le=24), demo: bool = False):
    return service.forecast_at(lat, lon, horizon_h, demo)


@app.post("/routes/score", response_model=TripResponse)
def routes_score(req: TripRequest):
    return service.score_trip(req.origin.model_dump(), req.destination.model_dump(), req.mode, 0.0, req.demo)


@app.post("/trips/analyze")
def trips_analyze(req: TripRequest):
    return service.analyze_trip(
        req.origin.model_dump(), req.destination.model_dump(), req.mode, req.demo,
        window_h=req.window_h, max_wait_min=req.max_wait_min,
        sensitivity=req.sensitivity, max_extra_min=req.max_extra_min,
    )


@app.post("/departure/best")
def departure_best(req: DepartureRequest):
    return service.departure(
        req.origin.model_dump(), req.destination.model_dump(), req.mode,
        0.0, req.window_h, req.max_wait_min, req.demo, req.sensitivity, req.max_extra_min,
    )


@app.get("/config")
def config():
    from engine.exposure import MODES, PREFERENCES, level_config
    return {
        "levels": level_config(),
        "mode_factors": {k: v["factor"] for k, v in MODES.items()},
        "preferences": PREFERENCES,
        "notes": {
            "levels": "AirGuard levels for mean forecast PM2.5 on a route. Not official AQI categories.",
            "mode_factors": "Illustrative relative intake per minute. Compare options within one mode.",
            "preferences": "Extra minutes the decision rule will accept per 10% exposure reduction.",
            "confidence": "0.6 x distance term + 0.4 x forecast-interval term. A heuristic, not a probability.",
            "departure_steps": "Forecasts at +1, +3, +6, +12 and +24 hours, interpolated to 15-minute scenario steps.",
        },
    }


@app.get("/eval")
def eval_():
    return service.eval_metrics()


@app.post("/agent/chat")
def agent_chat(req: ChatRequest, request: Request):
    """Local chat route. Deployed API Gateway sends this path to the agent Lambda instead."""
    ip = request.client.host if request.client else "local"
    if not allow_chat(ip):
        return err(429, "rate_limited", "Too many assistant requests. Wait a minute and try again.")
    from agent.agent import chat
    from agent.handler import _cached, _history

    history = req.history if isinstance(req.history, list) else []
    try:
        return chat(
            req.message,
            req.profile,
            _history(history[-6:]),
            req.demo,
            req.trip_id,
            from_place=req.from_place,
            to_place=req.to_place,
        )
    except Exception as exc:
        print("agent failed:", repr(exc))
        hit = _cached(req.message) if req.demo else None
        if hit:
            return {**hit, "cached": True}
        raise HTTPException(503, "The assistant is unavailable right now. The route and departure results still work.") from exc


handler = Mangum(app, lifespan="off")
