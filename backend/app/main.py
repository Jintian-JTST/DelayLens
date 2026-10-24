import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import fixtures
from app.schemas import (
    AskRequest,
    AskResponse,
    Calibration,
    DepartureCurveRequest,
    DepartureCurveResponse,
    Interpretation,
    LiveResponse,
    Route,
    Stats,
)

load_dotenv()

app = FastAPI(title="DelayLens API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _route_or_404(route_id: str) -> Route:
    for route in fixtures.load_routes():
        if route.route_id == route_id:
            return route
    raise HTTPException(status_code=404, detail=f"Unknown route_id: {route_id}")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/routes", response_model=list[Route])
def routes() -> list[Route]:
    return fixtures.load_routes()


@app.post("/api/departure-curve", response_model=DepartureCurveResponse)
def departure_curve(req: DepartureCurveRequest) -> DepartureCurveResponse:
    _route_or_404(req.route_id)
    started = time.perf_counter()
    result = fixtures.fixture_curve(req)
    result.server_ms = round((time.perf_counter() - started) * 1000, 2)
    return result


@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    # Gemini wiring lands in app/ask.py (Sat 19:30). Until then say so explicitly.
    return AskResponse(
        interpretation=Interpretation(),
        curve=None,
        answer="Ask DelayLens is not connected yet. Please use the form.",
        status="gemini_unavailable",
    )


@app.get("/api/live", response_model=LiveResponse)
def live(route_id: str) -> LiveResponse:
    _route_or_404(route_id)
    # Real TfL arrivals arrive with app/tfl.py; never fake live data.
    raise HTTPException(status_code=503, detail="tfl_unavailable")


@app.get("/api/stats", response_model=Stats)
def stats() -> Stats:
    raise HTTPException(status_code=503, detail="database_not_connected")


@app.get("/api/calibration", response_model=Calibration)
def calibration() -> Calibration:
    raise HTTPException(status_code=503, detail="calibration_not_available")
