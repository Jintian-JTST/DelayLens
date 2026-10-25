"""API contract for DelayLens. Owned by B; frozen at Sat 17:00 (see PLAN.md §6.3)."""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

DataStatus = Literal["ok", "low_data", "insufficient_data"]
AskStatus = Literal["ok", "unsupported_route", "unclear", "gemini_unavailable"]


class Stop(BaseModel):
    naptan_id: str
    name: str


class Route(BaseModel):
    route_id: str
    line_id: str
    mode: Literal["bus", "tube"]
    origin: Stop
    destination: Stop
    trips_observed: int
    hours_covered: list[datetime]
    # Optional, additive: the configured stop sequence (origin first) when known.
    stops: list[Stop] | None = None


class DepartureCurveRequest(BaseModel):
    route_id: str
    deadline: AwareDatetime
    walk_to_min: float = Field(5, ge=0, le=60)
    walk_from_min: float = Field(5, ge=0, le=60)
    tolerance: float = Field(0.10, gt=0, lt=1)
    window_min: int = Field(90, ge=10, le=240)


class CurvePoint(BaseModel):
    depart_at: datetime
    p_on_time: float = Field(ge=0, le=1)
    ci: tuple[float, float]
    arrive_p50: datetime
    arrive_p90: datetime
    n_trips: int


class Recommended(BaseModel):
    depart_at: datetime
    p_on_time: float


class WhatIf(BaseModel):
    delay_min: int
    p_on_time: float
    delta: float


class DataQuality(BaseModel):
    status: DataStatus
    basis: str


class DepartureCurveResponse(BaseModel):
    points: list[CurvePoint]
    recommended: Recommended | None
    what_if: list[WhatIf]
    data_quality: DataQuality
    server_ms: float


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class Interpretation(BaseModel):
    route_id: str | None = None
    deadline: datetime | None = None
    walk_to_min: float | None = None
    walk_from_min: float | None = None
    tolerance: float | None = None
    compare: list[datetime] | None = None


class AskResponse(BaseModel):
    interpretation: Interpretation
    curve: DepartureCurveResponse | None
    answer: str
    status: AskStatus


class LiveArrival(BaseModel):
    vehicle_id: str
    line_id: str
    destination_name: str | None = None
    time_to_station_s: int
    expected_arrival: datetime


class LiveResponse(BaseModel):
    route_id: str
    arrivals: list[LiveArrival]
    fetched_at: datetime


class LiveError(BaseModel):
    error: Literal["tfl_unavailable"]


class Stats(BaseModel):
    rows: int
    chunks: int
    compression_ratio: float | None
    first_polled_at: datetime | None
    last_polled_at: datetime | None


class ReliabilityBin(BaseModel):
    predicted: float
    observed: float
    n: int


class Calibration(BaseModel):
    bins: list[ReliabilityBin]
    brier_score: float | None
    # Added after the freeze (B approved): never claims validated calibration.
    calibration_status: Literal["not_validated", "preliminary"] = "not_validated"
    n_outcomes: int = 0
    n_runs: int = 0
    basis: str = ""
