"""Ask DelayLens: Gemini maps a question to one validated function call.

Gemini never produces numbers. Our model computes them and the answer sentence
is a template over those numbers (PLAN.md section 5).
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

import httpx
from pydantic import AwareDatetime, BaseModel, BeforeValidator, Field, ValidationError

from app import tfl
from app.schemas import (
    AskResponse,
    DepartureCurveRequest,
    DepartureCurveResponse,
    Interpretation,
    LiveResponse,
    Route,
)

log = logging.getLogger(__name__)

LONDON = ZoneInfo("Europe/London")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_TIMEOUT_S = 4.0
# Tried in order; Google retires and overloads models, so keep a fallback.
DEFAULT_MODELS = ("gemini-3.1-flash-lite", "gemini-3-flash-preview")

CurveFn = Callable[[DepartureCurveRequest], DepartureCurveResponse]
LiveFn = Callable[[Route], LiveResponse]


def _as_london(value: object) -> object:
    """Keep Gemini's wall-clock time but apply London's real UTC offset ourselves.

    Models guess offsets badly around the clock change (it is 02:00 on Sun 25 Oct).
    """
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).replace(tzinfo=LONDON)
        except ValueError:
            return value
    return value


LocalTime = Annotated[AwareDatetime, BeforeValidator(_as_london)]


class GeminiUnavailable(Exception):
    """Gemini could not be reached or returned something unusable."""


_ROUTE_ID = {"type": "string", "description": "A route_id from the supported route list."}
_DEADLINE = {
    "type": "string",
    "description": "Arrival deadline as London local time, ISO 8601 without offset, e.g. 2026-10-25T14:10:00.",
}
_WALK = {"type": "number", "description": "Minutes, default 5."}
_TOLERANCE = {
    "type": "number",
    "description": "Accepted chance of being late, 0.05 to 0.30. Default 0.10; 0.05 for 'I really can't be late'; 0.20 for relaxed.",
}
_DECLARATIONS = [
    {
        "name": "list_routes",
        "description": "List the routes DelayLens supports.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_departure_curve",
        "description": "When should the user leave to arrive by a deadline?",
        "parameters": {
            "type": "object",
            "properties": {
                "route_id": _ROUTE_ID,
                "deadline": _DEADLINE,
                "walk_to_min": _WALK,
                "walk_from_min": _WALK,
                "tolerance": _TOLERANCE,
            },
            "required": ["route_id", "deadline"],
        },
    },
    {
        "name": "compare_departures",
        "description": "Compare the chance of arriving on time for specific departure times.",
        "parameters": {
            "type": "object",
            "properties": {
                "route_id": _ROUTE_ID,
                "deadline": _DEADLINE,
                "departures": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2 to 6 departure times as London local time, ISO 8601 without offset.",
                },
                "walk_to_min": _WALK,
                "walk_from_min": _WALK,
            },
            "required": ["route_id", "deadline", "departures"],
        },
    },
    {
        "name": "get_live",
        "description": "Next vehicles at the route's origin stop right now.",
        "parameters": {
            "type": "object",
            "properties": {"route_id": _ROUTE_ID},
            "required": ["route_id"],
        },
    },
    {
        "name": "unclear",
        "description": "Use when the question is not about travel timing, or lacks a deadline.",
        "parameters": {"type": "object", "properties": {}},
    },
]


class _CurveArgs(BaseModel):
    route_id: str
    deadline: LocalTime
    walk_to_min: float = Field(5, ge=0, le=60)
    walk_from_min: float = Field(5, ge=0, le=60)
    tolerance: float = Field(0.10, gt=0, lt=1)


class _CompareArgs(BaseModel):
    route_id: str
    deadline: LocalTime
    departures: list[LocalTime] = Field(min_length=2, max_length=6)
    walk_to_min: float = Field(5, ge=0, le=60)
    walk_from_min: float = Field(5, ge=0, le=60)


class _LiveArgs(BaseModel):
    route_id: str


def _system_prompt(now: datetime, routes: list[Route]) -> str:
    listing = "\n".join(
        f"- {r.route_id}: {r.origin.name} to {r.destination.name} ({r.mode})" for r in routes
    )
    local = now.astimezone(LONDON)
    return (
        "You turn a traveller's question into exactly one function call. "
        "Never answer in prose and never invent route ids.\n"
        f"Current time: {local.isoformat()} (Europe/London). 'Around 2' means the next 14:00 "
        "after now; 'ten minutes late is OK' moves the deadline 10 minutes later. "
        "'A bit late is fine' with no number keeps the deadline and sets tolerance 0.20. "
        "Send times as London local time without a UTC offset. "
        "Match place names loosely: 'Finsbury Park' or 'Tottenham Court Road' matches a "
        "route whose stop name starts with or contains it. Call list_routes only when the "
        "user asks which routes or places are supported. "
        "If the user names a place that matches none of the supported routes, call "
        "get_departure_curve with route_id 'none'.\n"
        f"Supported routes:\n{listing}"
    )


def _call_gemini(
    question: str,
    now: datetime,
    routes: list[Route],
    *,
    api_key: str,
    models: tuple[str, ...],
    transport: httpx.BaseTransport | None,
) -> tuple[str, dict]:
    if not api_key or api_key == "your-gemini-api-key":
        raise GeminiUnavailable
    body = {
        "systemInstruction": {"parts": [{"text": _system_prompt(now, routes)}]},
        "contents": [{"role": "user", "parts": [{"text": question}]}],
        "tools": [{"functionDeclarations": _DECLARATIONS}],
        "toolConfig": {"functionCallingConfig": {"mode": "ANY"}},
        "generationConfig": {"temperature": 0},
    }
    for model in models:
        try:
            with httpx.Client(timeout=GEMINI_TIMEOUT_S, transport=transport) as client:
                response = client.post(
                    GEMINI_URL.format(model=model),
                    headers={"x-goog-api-key": api_key},
                    json=body,
                )
                response.raise_for_status()
                parts = response.json()["candidates"][0]["content"]["parts"]
            for part in parts:
                call = part.get("functionCall") if isinstance(part, dict) else None
                if call:
                    args = call.get("args") or {}
                    if not isinstance(call["name"], str) or not isinstance(args, dict):
                        raise TypeError
                    return call["name"], args
        except httpx.HTTPStatusError as exc:
            log.warning("Gemini %s failed: HTTP %s", model, exc.response.status_code)
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            # Never log exception text: it can contain the URL or key.
            log.warning("Gemini %s failed: %s", model, type(exc).__name__)
    raise GeminiUnavailable


def _hhmm(dt: datetime) -> str:
    return dt.astimezone(LONDON).strftime("%H:%M")


def _utc_minute(dt: datetime) -> datetime:
    return dt.astimezone(UTC).replace(second=0, microsecond=0)


def _unsupported(routes: list[Route]) -> AskResponse:
    names = "; ".join(f"{r.origin.name} to {r.destination.name}" for r in routes) or "none yet"
    return AskResponse(
        interpretation=Interpretation(),
        curve=None,
        answer=f"I can only answer for the routes I have data for: {names}.",
        status="unsupported_route",
    )


def _unclear() -> AskResponse:
    return AskResponse(
        interpretation=Interpretation(),
        curve=None,
        answer=(
            "I couldn't tell what you need. Try: 'I need to be at the destination by 14:00, "
            "when should I leave?' or use the form."
        ),
        status="unclear",
    )


def answer_question(
    question: str,
    *,
    now: datetime,
    routes: list[Route],
    api_key: str,
    models: tuple[str, ...] = DEFAULT_MODELS,
    compute_curve: CurveFn,
    get_live: LiveFn,
    transport: httpx.BaseTransport | None = None,
) -> AskResponse:
    try:
        name, raw = _call_gemini(
            question, now, routes, api_key=api_key, models=models, transport=transport
        )
    except GeminiUnavailable:
        return AskResponse(
            interpretation=Interpretation(),
            curve=None,
            answer="Ask DelayLens is unavailable right now. Please use the form.",
            status="gemini_unavailable",
        )

    by_id = {r.route_id: r for r in routes}
    try:
        if name == "list_routes":
            return AskResponse(
                interpretation=Interpretation(),
                curve=None,
                answer="I can help with: "
                + "; ".join(f"{r.origin.name} to {r.destination.name}" for r in routes)
                + ".",
                status="ok",
            )
        if name == "get_departure_curve":
            args = _CurveArgs.model_validate(raw)
            if args.route_id not in by_id:
                return _unsupported(routes)
            return _departure_answer(args, compute_curve, by_id[args.route_id], now)
        if name == "compare_departures":
            cmp_args = _CompareArgs.model_validate(raw)
            if cmp_args.route_id not in by_id:
                return _unsupported(routes)
            return _compare_answer(cmp_args, compute_curve, by_id[cmp_args.route_id], now)
        if name == "get_live":
            live_args = _LiveArgs.model_validate(raw)
            if live_args.route_id not in by_id:
                return _unsupported(routes)
            return _live_answer(by_id[live_args.route_id], get_live)
    except ValidationError:
        return _unclear()
    return _unclear()


def _route_context(route: Route, walk_to_min: float, walk_from_min: float) -> str:
    """Name the route and the assumed walks, so a wrong route or default is visible."""
    if walk_to_min == walk_from_min:
        walks = f"{walk_to_min:g}-minute walks at each end"
    else:
        walks = (
            f"a {walk_to_min:g}-minute walk to the stop "
            f"and {walk_from_min:g} minutes from the last stop"
        )
    return (
        f" ({route.mode} {route.line_id}, {route.origin.name} to {route.destination.name}; "
        f"assuming {walks})"
    )


def _past_note(deadline: datetime, now: datetime) -> str:
    if deadline > now:
        return ""
    day = deadline.astimezone(LONDON).strftime("%a %d %b")
    return f" That time has already passed, so this replays recorded data for {day}."


def _departure_answer(
    args: _CurveArgs, compute_curve: CurveFn, route: Route, now: datetime
) -> AskResponse:
    interp = Interpretation(
        route_id=args.route_id,
        deadline=args.deadline,
        walk_to_min=args.walk_to_min,
        walk_from_min=args.walk_from_min,
        tolerance=args.tolerance,
    )
    curve = compute_curve(
        DepartureCurveRequest(
            route_id=args.route_id,
            deadline=args.deadline,
            walk_to_min=args.walk_to_min,
            walk_from_min=args.walk_from_min,
            tolerance=args.tolerance,
        )
    )
    context = _route_context(route, args.walk_to_min, args.walk_from_min)
    past = _past_note(args.deadline, now)
    if curve.data_quality.status == "insufficient_data" or not curve.points:
        answer = (
            f"I don't have enough recorded data to say{context}.{past} "
            f"{curve.data_quality.basis}"
        )
    elif curve.recommended is None:
        answer = (
            f"No departure between {_hhmm(curve.points[0].depart_at)} and "
            f"{_hhmm(curve.points[-1].depart_at)} reaches an estimated "
            f"{round((1 - args.tolerance) * 100)}% chance of arriving by "
            f"{_hhmm(args.deadline)}{context}.{past}"
        )
    else:
        rec = curve.recommended
        trips = next((p.n_trips for p in curve.points if p.depart_at == rec.depart_at), None)
        support = f" (from {trips} recorded trips)" if trips else ""
        answer = (
            f"Leave by {_hhmm(rec.depart_at)} for an estimated {round(rec.p_on_time * 100)}% "
            f"chance{support} of arriving by {_hhmm(args.deadline)}{context}.{past}"
        )
    return AskResponse(interpretation=interp, curve=curve, answer=answer, status="ok")


def _compare_answer(
    args: _CompareArgs, compute_curve: CurveFn, route: Route, now: datetime
) -> AskResponse:
    departures = sorted(args.departures)
    interp = Interpretation(
        route_id=args.route_id,
        deadline=args.deadline,
        walk_to_min=args.walk_to_min,
        walk_from_min=args.walk_from_min,
        compare=departures,
    )
    curve = compute_curve(
        DepartureCurveRequest(
            route_id=args.route_id,
            deadline=args.deadline,
            walk_to_min=args.walk_to_min,
            walk_from_min=args.walk_from_min,
            window_min=240,
        )
    )
    context = _route_context(route, args.walk_to_min, args.walk_from_min)
    past = _past_note(args.deadline, now)
    if curve.data_quality.status == "insufficient_data" or not curve.points:
        return AskResponse(
            interpretation=interp,
            curve=curve,
            answer=(
                f"I don't have enough recorded data to compare{context}.{past} "
                f"{curve.data_quality.basis}"
            ),
            status="ok",
        )
    by_minute = {_utc_minute(p.depart_at): p for p in curve.points}
    found = [(d, by_minute.get(_utc_minute(d))) for d in departures]
    if any(p is None for _, p in found):
        answer = (
            "Some of those departure times are outside the 4 hours before your "
            f"deadline{context}.{past}"
        )
    else:
        scored = [(d, p.p_on_time) for d, p in found if p is not None]
        listing = ", ".join(f"{_hhmm(d)}: {round(p * 100)}%" for d, p in scored)
        best = max(scored, key=lambda item: item[1])
        answer = (
            f"Estimated chance of arriving by {_hhmm(args.deadline)}: {listing}. "
            f"Best: {_hhmm(best[0])}{context}.{past}"
        )
    return AskResponse(interpretation=interp, curve=curve, answer=answer, status="ok")


def _live_answer(route: Route, get_live: LiveFn) -> AskResponse:
    interp = Interpretation(route_id=route.route_id)
    try:
        live = get_live(route)
    except tfl.TflUnavailable:
        return AskResponse(
            interpretation=interp,
            curve=None,
            answer="Live arrivals are unavailable right now.",
            status="unclear",
        )
    if not live.arrivals:
        answer = f"No vehicles are predicted at {route.origin.name} right now."
    else:
        mins = [max(0, round(a.time_to_station_s / 60)) for a in live.arrivals[:3]]
        answer = f"Next at {route.origin.name}: " + ", ".join(f"{m} min" for m in mins) + "."
    return AskResponse(interpretation=interp, curve=None, answer=answer, status="ok")
