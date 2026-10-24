import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import Field, TypeAdapter, ValidationError

from app import ask as ask_module
from app import fixtures, tfl
from app.schemas import (
    AskRequest,
    AskResponse,
    Calibration,
    DataQuality,
    DepartureCurveRequest,
    DepartureCurveResponse,
    LiveError,
    LiveResponse,
    Route,
    Stats,
)

load_dotenv()

ROUTES_PATH = Path(__file__).resolve().parent.parent / "config" / "routes.json"


class _ConfiguredRoute(Route):
    """Data-team configuration; observation coverage is populated by the DB later."""

    direction: Literal["inbound", "outbound"] | None = None
    trips_observed: int = Field(default=0, ge=0)
    hours_covered: list[datetime] = Field(default_factory=list)


def _load_routes() -> list[_ConfiguredRoute]:
    if not ROUTES_PATH.exists():
        return [
            _ConfiguredRoute.model_validate(r.model_dump())
            for r in fixtures.load_routes()
        ]
    try:
        result = TypeAdapter(list[_ConfiguredRoute]).validate_python(
            json.loads(ROUTES_PATH.read_text(encoding="utf-8"))
        )
        if len({r.route_id for r in result}) != len(result):
            raise ValueError("Duplicate route IDs")
        return result
    except (OSError, ValueError, ValidationError):
        raise HTTPException(
            status_code=503, detail="route_config_unavailable"
        ) from None


app = FastAPI(title="DelayLens API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _route_or_404(route_id: str) -> _ConfiguredRoute:
    for route in _load_routes():
        if route.route_id == route_id:
            return route
    raise HTTPException(status_code=404, detail=f"Unknown route_id: {route_id}")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/routes", response_model=list[Route])
def routes() -> list[Route]:
    return _load_routes()


def _compute_curve(req: DepartureCurveRequest) -> DepartureCurveResponse:
    started = time.perf_counter()
    if ROUTES_PATH.exists():
        result = DepartureCurveResponse(
            points=[],
            recommended=None,
            what_if=[],
            server_ms=0,
            data_quality=DataQuality(
                status="insufficient_data",
                basis="Recorded-trip model not connected; no probability available.",
            ),
        )
    else:
        result = fixtures.fixture_curve(req)
    result.server_ms = round((time.perf_counter() - started) * 1000, 2)
    return result


@app.post("/api/departure-curve", response_model=DepartureCurveResponse)
def departure_curve(req: DepartureCurveRequest) -> DepartureCurveResponse:
    _route_or_404(req.route_id)
    return _compute_curve(req)


def _gemini_models() -> tuple[str, ...]:
    override = os.getenv("GEMINI_MODEL", "").strip()
    return (override, *ask_module.DEFAULT_MODELS) if override else ask_module.DEFAULT_MODELS


@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    app_key = os.getenv("TFL_APP_KEY", "")
    return ask_module.answer_question(
        req.question,
        now=datetime.now(UTC),
        routes=_load_routes(),
        api_key=os.getenv("GEMINI_API_KEY", ""),
        models=_gemini_models(),
        compute_curve=_compute_curve,
        get_live=lambda r: tfl.get_live(
            r, app_key=app_key, direction=getattr(r, "direction", None)
        ),
    )


@app.get(
    "/api/live", response_model=LiveResponse, responses={503: {"model": LiveError}}
)
def live(route_id: str) -> LiveResponse | JSONResponse:
    route = _route_or_404(route_id)
    try:
        return tfl.get_live(
            route, app_key=os.getenv("TFL_APP_KEY", ""), direction=route.direction
        )
    except tfl.TflUnavailable:
        return JSONResponse(status_code=503, content={"error": "tfl_unavailable"})


@app.get("/api/stats", response_model=Stats)
def stats() -> Stats:
    raise HTTPException(status_code=503, detail="database_not_connected")


@app.get("/api/calibration", response_model=Calibration)
def calibration() -> Calibration:
    raise HTTPException(status_code=503, detail="calibration_not_available")
