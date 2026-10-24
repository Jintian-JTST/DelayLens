import json
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import Field, TypeAdapter, ValidationError

from app import ask as ask_module
from app import curves, db, fixtures, model, tfl
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


_cache: db.SegmentCache | None = None


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    return "" if "user:password@host" in url else url


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _cache
    if url := _database_url():
        _cache = db.SegmentCache(url)
        _cache.start()
    yield
    if _cache is not None:
        _cache.stop()


app = FastAPI(title="DelayLens API", lifespan=_lifespan)
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


def _snapshot() -> db.Snapshot | None:
    return _cache.snapshot if _cache is not None else None


@app.get("/api/routes", response_model=list[Route])
def routes() -> list[Route]:
    result = _load_routes()
    if snapshot := _snapshot():
        for route in result:
            if cov := snapshot.coverage.get(route.route_id):
                route.trips_observed = cov.trips_observed
                route.hours_covered = cov.hours_covered
    return result


_segments_memo: dict[tuple[datetime, str], model.Segments] = {}


def _segments_for(snapshot: db.Snapshot, route_id: str) -> model.Segments:
    key = (snapshot.refreshed_at, route_id)
    if key not in _segments_memo:
        _segments_memo.clear()  # keep only the current snapshot's conversions
        _segments_memo[key] = curves.to_segments(snapshot.segments.get(route_id, []))
    return _segments_memo[key]


def _compute_curve(req: DepartureCurveRequest) -> DepartureCurveResponse:
    started = time.perf_counter()
    if ROUTES_PATH.exists():
        snapshot = _snapshot()
        if snapshot is None:
            result = DepartureCurveResponse(
                points=[],
                recommended=None,
                what_if=[],
                server_ms=0,
                data_quality=DataQuality(
                    status="insufficient_data",
                    basis="Recorded-trip data not connected; no probability available.",
                ),
            )
        else:
            segments = _segments_for(snapshot, req.route_id)
            curve = model.departure_curve(
                segments,
                req.deadline,
                walk_to_min=req.walk_to_min,
                walk_from_min=req.walk_from_min,
                window_min=req.window_min,
            )
            result = curves.build_response(curve, req, segments)
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
    if snapshot := _snapshot():
        return snapshot.stats
    raise HTTPException(status_code=503, detail="database_not_connected")


@app.get("/api/calibration", response_model=Calibration)
def calibration() -> Calibration:
    raise HTTPException(status_code=503, detail="calibration_not_available")
