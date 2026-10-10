"""AirGuard HTTP API.

    uvicorn airguard.api.main:app --reload --port 8000     (from backend/)

Every error uses the same shape: {"error": {"code": "...", "message": "..."}}.
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from airguard import __version__, db
from airguard.api import schemas as S
from airguard.config import settings
from airguard.engine import assumptions as A
from airguard.engine.departure import decide, evaluate
from airguard.engine.exposure import ForecastUnavailable, prepare, score
from airguard.services import forecasts, geocoding, routing, trips

log = logging.getLogger("airguard.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

app = FastAPI(
    title="AirGuard API",
    version=__version__,
    description="Route and departure-time advice for Delhi commuters, from a validated PM2.5 forecast.",
)
app.add_middleware(CORSMiddleware, allow_origins=settings().origins, allow_methods=["GET", "POST"],
                   allow_headers=["*"])

ERRORS = {code: {"model": S.ErrorResponse} for code in (422, 429, 502, 503)}


# --------------------------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------------------------
class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(ApiError)
async def _api_error(_: Request, e: ApiError):
    return _err(e.status, e.code, e.message)


@app.exception_handler(RequestValidationError)
async def _validation(_: Request, e: RequestValidationError):
    first = e.errors()[0] if e.errors() else {}
    loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
    msg = str(first.get("msg", "invalid request")).removeprefix("Value error, ")
    return _err(422, "invalid_request", f"{loc}: {msg}" if loc else msg)


@app.exception_handler(StarletteHTTPException)
async def _http(_: Request, e: StarletteHTTPException):
    return _err(e.status_code, "not_found" if e.status_code == 404 else "http_error", str(e.detail))


@app.exception_handler(routing.RoutingError)
async def _routing(_: Request, e: routing.RoutingError):
    return _err(502, "routing_failed", f"Couldn't get routes: {e}")


@app.exception_handler(ForecastUnavailable)
async def _forecast(_: Request, e: ForecastUnavailable):
    return _err(503, "forecast_unavailable", f"The forecast doesn't cover this trip ({e}).")


@app.exception_handler(forecasts.NoForecast)
async def _noforecast(_: Request, e: forecasts.NoForecast):
    return _err(503, "forecast_unavailable", str(e))


@app.exception_handler(db.DatabaseUnavailable)
async def _db(_: Request, e: db.DatabaseUnavailable):
    return _err(503, "database_unavailable", "The database is unreachable. Is Supabase running?")


@app.exception_handler(Exception)
async def _unhandled(_: Request, e: Exception):
    log.exception("unhandled error")
    return _err(500, "internal_error", "Something went wrong on our side.")


# --------------------------------------------------------------------------------------------
# Rate limiting for the agent (per client IP, sliding one-minute window)
# --------------------------------------------------------------------------------------------
_hits: dict[str, deque] = defaultdict(deque)


def _rate_limit(request: Request) -> None:
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?")
    q, now = _hits[ip], time.monotonic()
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= settings().agent_rate_limit_per_min:
        raise ApiError(429, "rate_limited", "Too many questions in a minute. Please wait a moment.")
    q.append(now)


# --------------------------------------------------------------------------------------------
# Meta and health
# --------------------------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
def health():
    out = {"status": "ok", "version": __version__, "time": datetime.now(timezone.utc).isoformat(),
           "database": db.ping(), "snapshot": forecasts.snapshot_mode(),
           "llm": {"backend": settings().llm_backend,
                   "model": settings().ollama_model if settings().llm_backend == "ollama" else settings().bedrock_model_id}}
    try:
        fld = forecasts.current_field()
        now = forecasts.reference_now(fld)
        delayed = sum(1 for s in fld.stations if s.obs_age_h is None or s.obs_age_h > 3)
        out["data"] = {"stations": len(fld.stations), "stations_delayed": delayed,
                       "forecast_issued_at": fld.issued_at.isoformat(), "model_version": fld.model_version,
                       "data_age_min": round((now - fld.issued_at).total_seconds() / 60)}
    except (forecasts.NoForecast, db.DatabaseUnavailable) as e:
        out["status"] = "degraded"
        out["data"] = {"error": str(e)}
    if out["database"]:
        runs = db.query("select kind, status, finished_at from pipeline_runs order by started_at desc limit 1")
        out["last_pipeline_run"] = runs[0] if runs else None
    return out


@app.get("/meta", tags=["meta"])
def meta():
    """Every modelling assumption, verbatim from engine/assumptions.py, plus data attributions."""
    return {
        "version": __version__,
        "assumptions": A.as_dict(),
        "attributions": [
            {"name": "OpenAQ", "url": "https://openaq.org", "use": "Station PM2.5 (CPCB, DPCC, IMD, AirNow, AirGradient)"},
            {"name": "Open-Meteo", "url": "https://open-meteo.com", "use": "Weather and CAMS air-quality data"},
            {"name": "Copernicus CAMS", "url": "https://atmosphere.copernicus.eu", "use": "Global PM2.5 model"},
            {"name": "NASA FIRMS", "url": "https://firms.modaps.eosdis.nasa.gov", "use": "Active fire detections"},
            {"name": "OpenStreetMap contributors", "url": "https://www.openstreetmap.org/copyright", "use": "Map data, routing and geocoding"},
            {"name": "OSRM / FOSSGIS", "url": "https://routing.openstreetmap.de", "use": "Routing"},
            {"name": "Photon by Komoot", "url": "https://photon.komoot.io", "use": "Place search"},
            {"name": "OpenFreeMap", "url": "https://openfreemap.org", "use": "Map tiles"},
        ],
    }


# --------------------------------------------------------------------------------------------
# Air data
# --------------------------------------------------------------------------------------------
@app.get("/stations", response_model=S.StationsResponse, tags=["air"])
def stations():
    """Every station's current value and its forecast for the next 24 hours."""
    fld = forecasts.current_field()
    return {"issued_at": fld.issued_at.isoformat(), "model_version": fld.model_version,
            "now": forecasts.reference_now(fld).isoformat(), "stations": forecasts.station_summaries(fld)}


@app.get("/forecast", response_model=S.ForecastPoint, tags=["air"], responses=ERRORS)
def forecast(lat: float = Query(ge=28.35, le=28.95), lon: float = Query(ge=76.80, le=77.55),
             horizon_h: float = Query(default=0, ge=0, le=24)):
    """PM2.5 at any point in Delhi NCR, now or up to 24 h ahead (interpolated between stations)."""
    fld = forecasts.current_field()
    t = forecasts.reference_now(fld) + timedelta(hours=horizon_h)
    p = fld.point(lat, lon, t.timestamp())
    return {"lat": lat, "lon": lon, "target_ts": t.isoformat(), "horizon_h": horizon_h, **p,
            "risk": A.risk_band(p["pm25"])[0] if p["pm25"] is not None else None}


@app.get("/eval", response_model=S.EvalResponse, tags=["air"])
def eval_metrics():
    """Backtest of the current forecast model against persistence, hour-of-day mean and raw CAMS."""
    fld_version = None
    try:
        fld_version = forecasts.current_field().model_version
    except (forecasts.NoForecast, db.DatabaseUnavailable):
        pass
    models = db.query("select * from models where model_version = %s", (fld_version,)) if fld_version else []
    if not models:
        models = db.query("select * from models order by trained_at desc limit 1")
    if not models:
        return {"model_version": None, "data_source": None, "trained_at": None, "train_start": None,
                "train_end": None, "test_start": None, "test_end": None, "n_stations": None, "notes": None,
                "metrics": []}
    m = models[0]
    rows = db.query("select * from eval_metrics where model_version = %s order by mode, horizon_h",
                    (m["model_version"],))
    iso = lambda v: v.isoformat() if v else None  # noqa: E731
    return {"model_version": m["model_version"], "data_source": m["data_source"], "trained_at": iso(m["trained_at"]),
            "train_start": iso(m["train_start"]), "train_end": iso(m["train_end"]),
            "test_start": iso(m["test_start"]), "test_end": iso(m["test_end"]), "n_stations": m["n_stations"],
            "notes": m["notes"], "metrics": rows}


@app.get("/geocode", response_model=list[S.GeocodeResult], tags=["places"])
def geocode(q: str = Query(min_length=2, max_length=120)):
    """Search Delhi NCR places (curated list first, then OpenStreetMap via Photon)."""
    return geocoding.search(q)


# --------------------------------------------------------------------------------------------
# Trips
# --------------------------------------------------------------------------------------------
def _trip_data(fld) -> dict:
    now = forecasts.reference_now(fld)
    return {"forecast_issued_at": fld.issued_at.isoformat(), "model_version": fld.model_version,
            "data_age_min": round((now - fld.issued_at).total_seconds() / 60), "stations": len(fld.stations),
            "stations_delayed": sum(1 for s in fld.stations if s.obs_age_h is None or s.obs_age_h > 3),
            "snapshot": forecasts.snapshot_mode()}


@app.post("/routes/score", response_model=S.RoutesScoreResponse, tags=["trips"], responses=ERRORS)
def routes_score(req: S.RoutesScoreRequest):
    """Candidate routes leaving now, each with exposure index, risk level and confidence."""
    fld = forecasts.current_field()
    now = forecasts.reference_now(fld).timestamp()
    rs = routing.get_routes((req.origin.lat, req.origin.lon), (req.destination.lat, req.destination.lon), req.mode)
    return {"routes": [score(prepare(r, fld), fld, now, req.mode).to_dict() for r in rs], "data": _trip_data(fld)}


@app.post("/departure/best", response_model=S.DepartureResponse, tags=["trips"], responses=ERRORS)
def departure_best(req: S.TripRequest):
    """Every (route, departure) option on a 15-minute grid and the recommended one."""
    fld = forecasts.current_field()
    now = forecasts.reference_now(fld).timestamp()
    rs = routing.get_routes((req.origin.lat, req.origin.lon), (req.destination.lat, req.destination.lon), req.mode)
    opts = evaluate([prepare(r, fld) for r in rs], fld, now, req.mode, window_h=req.window_h)
    d = decide(opts, req.sensitivity, req.max_extra_min, req.max_wait_min)
    return {"departures": [o.to_dict() for o in opts], "decision": d.to_dict(), "data": _trip_data(fld)}


@app.post("/trips/analyze", response_model=S.TripResult, tags=["trips"], responses=ERRORS)
def trips_analyze(req: S.TripRequest):
    """Routes, departure options and the recommendation in one call. The result is saved and gets
    a trip_id the assistant can read back."""
    return trips.analyze(
        origin={"lat": req.origin.lat, "lon": req.origin.lon}, destination={"lat": req.destination.lat,
                                                                           "lon": req.destination.lon},
        mode=req.mode, sensitivity=req.sensitivity, window_h=req.window_h, max_extra_min=req.max_extra_min,
        max_wait_min=req.max_wait_min, origin_name=req.origin.name, destination_name=req.destination.name)


@app.post("/trips/preview", response_model=S.TripPreview, tags=["trips"], responses=ERRORS)
def trips_preview(req: S.TripRequest):
    """An analysis that isn't saved, plus PM2.5 along the recommended route for every 15-minute
    departure (the 'departure strips' on the landing page). Cached for five minutes."""
    return trips.preview(
        origin={"lat": req.origin.lat, "lon": req.origin.lon}, destination={"lat": req.destination.lat,
                                                                           "lon": req.destination.lon},
        mode=req.mode, sensitivity=req.sensitivity, window_h=req.window_h, max_extra_min=req.max_extra_min,
        max_wait_min=req.max_wait_min, origin_name=req.origin.name, destination_name=req.destination.name)


@app.get("/trips/{trip_id}", response_model=S.TripResult, tags=["trips"], responses={404: {"model": S.ErrorResponse}})
def trip_get(trip_id: str):
    t = trips.get(trip_id)
    if t is None:
        raise ApiError(404, "not_found", "No trip with that id.")
    return t


# --------------------------------------------------------------------------------------------
# Assistant
# --------------------------------------------------------------------------------------------
@app.post("/agent/chat", response_model=S.ChatResponse, tags=["assistant"], responses=ERRORS)
async def agent_chat(req: S.ChatRequest, request: Request):
    """Ask the assistant. Returns the answer and every tool call it made."""
    _rate_limit(request)
    from airguard.agent.agent import chat

    return await chat(req.message, req.profile.model_dump() if req.profile else None, req.trip_id,
                      [h.model_dump() for h in req.history])


@app.post("/agent/stream", tags=["assistant"], responses=ERRORS)
async def agent_stream(req: S.ChatRequest, request: Request):
    """Same as /agent/chat, streamed as Server-Sent Events: tool_start, tool_end, token, reset, done."""
    _rate_limit(request)
    from airguard.agent.agent import stream

    async def events():
        async for ev in stream(req.message, req.profile.model_dump() if req.profile else None, req.trip_id,
                               [h.model_dump() for h in req.history]):
            yield f"event: {ev['type']}\ndata: {json.dumps(ev, default=str)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
