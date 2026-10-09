"""Request and response models. FastAPI turns these into contracts/openapi.json."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from airguard.geo import in_ncr

Mode = Literal["walk", "cycle", "two_wheeler", "car"]
Sensitivity = Literal["normal", "sensitive", "high"]


class Point(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    name: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def inside_ncr(self):
        if not in_ncr(self.lat, self.lon):
            raise ValueError("AirGuard currently covers Delhi NCR only")
        return self


class TripRequest(BaseModel):
    origin: Point
    destination: Point
    mode: Mode = "cycle"
    sensitivity: Sensitivity = "normal"
    window_h: float = Field(default=4, ge=0, le=6, description="How far ahead to consider leaving (hours)")
    max_extra_min: float = Field(default=15, ge=0, le=90, description="Most extra travel minutes accepted")
    max_wait_min: float = Field(default=120, ge=0, le=360, description="Longest wait before leaving (minutes)")


class RoutesScoreRequest(BaseModel):
    origin: Point
    destination: Point
    mode: Mode = "cycle"
    sensitivity: Sensitivity = "normal"


class Profile(BaseModel):
    name: str | None = Field(default=None, max_length=40)
    sensitivity: Sensitivity = "normal"
    mode: Mode = "cycle"
    max_extra_min: float = Field(default=15, ge=0, le=90)
    max_wait_min: float = Field(default=120, ge=0, le=360)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=600)
    profile: Profile | None = None
    trip_id: str | None = Field(default=None, max_length=64)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)


# --------------------------------------------------------------------------------------------
# Responses
# --------------------------------------------------------------------------------------------
class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class Segment(BaseModel):
    lat: float
    lon: float
    pm25: float
    low: float
    high: float
    minutes: float
    confidence: float
    station_km: float
    line: list[list[float]]


class RouteScore(BaseModel):
    route_id: str
    label: str
    depart_at: str
    duration_min: float
    distance_km: float
    exposure_index: float
    exposure_low: float
    exposure_high: float
    mean_pm25: float
    peak_pm25: float
    risk: str
    risk_label: str
    confidence: float
    max_station_km: float
    segments: list[Segment] = []


class DepartureOption(BaseModel):
    wait_min: int
    depart_at: str
    route_id: str
    label: str
    duration_min: float
    exposure_index: float
    exposure_low: float
    exposure_high: float
    mean_pm25: float
    risk: str
    confidence: float


class DecisionDelta(BaseModel):
    exposure_index_pct: float
    arrival_min: float
    extra_travel_min: float
    wait_min: int


class DecisionRule(BaseModel):
    sensitivity: Sensitivity
    minutes_per_10pct: float
    cost_min: float
    accepted_cost_min: float
    wait_cost_weight: float


class Decision(BaseModel):
    recommended: DepartureOption
    baseline: DepartureOption
    lowest: DepartureOption
    kind: Literal["stay", "route", "wait", "wait_and_route"]
    delta: DecisionDelta
    rule: DecisionRule


class TripPlace(BaseModel):
    lat: float
    lon: float
    name: str | None = None


class TripData(BaseModel):
    forecast_issued_at: str
    model_version: str
    data_age_min: int
    stations: int
    stations_delayed: int
    snapshot: bool


class TripLimits(BaseModel):
    window_h: float
    max_extra_min: float
    max_wait_min: float


class TripResult(BaseModel):
    trip_id: str
    created_at: str
    now: str
    origin: TripPlace
    destination: TripPlace
    mode: Mode
    mode_label: str
    mode_factor: float
    sensitivity: Sensitivity
    limits: TripLimits
    routes: list[RouteScore]
    departures: list[DepartureOption]
    decision: Decision
    recommended_route: RouteScore
    data: TripData


class RoutesScoreResponse(BaseModel):
    routes: list[RouteScore]
    data: TripData


class DepartureResponse(BaseModel):
    departures: list[DepartureOption]
    decision: Decision
    data: TripData


class ForecastPoint(BaseModel):
    lat: float
    lon: float
    target_ts: str
    horizon_h: float
    pm25: float | None
    low: float | None
    high: float | None
    confidence: float | None
    nearest_station_km: float | None
    risk: str | None


class SeriesPoint(BaseModel):
    ts: str
    pm25: float
    low: float
    high: float


class StationSummary(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    provider: str | None
    is_monitor: bool
    pm25_now: float
    pm25_interp_now: float | None
    measured: bool
    obs_age_h: float | None
    series: list[SeriesPoint]


class StationsResponse(BaseModel):
    issued_at: str
    model_version: str
    now: str
    stations: list[StationSummary]


class GeocodeResult(BaseModel):
    name: str
    detail: str
    lat: float
    lon: float
    source: Literal["curated", "osm"]


class EvalRow(BaseModel):
    horizon_h: int
    mode: Literal["normal", "delayed"]
    mae: float
    rmse: float
    baseline_persistence_mae: float | None = None
    baseline_persistence_rmse: float | None = None
    baseline_hourly_mean_mae: float | None = None
    baseline_hourly_mean_rmse: float | None = None
    baseline_cams_mae: float | None = None
    baseline_cams_rmse: float | None = None
    interval_coverage: float | None = None
    interval_width: float | None = None
    n_samples: int


class EvalResponse(BaseModel):
    model_version: str | None
    data_source: str | None
    trained_at: str | None
    train_start: str | None
    train_end: str | None
    test_start: str | None
    test_end: str | None
    n_stations: int | None
    notes: str | None
    metrics: list[EvalRow]


class ToolCall(BaseModel):
    name: str
    input: dict
    output: dict | list | str | None
    ms: int
    ok: bool


class ChatResponse(BaseModel):
    answer: str
    tool_calls: list[ToolCall]
    grounded: bool
    ungrounded_numbers: list[str] = []
    source: Literal["model", "fallback", "cache"]
    model: str | None = None
