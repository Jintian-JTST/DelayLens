"""Sub-routes and one-change journeys built from the configured routes.

Plain dicts (the routes.json shape) so the recorder's route sync can use the
same expansion without importing the API. A sub-route is an ordered stop pair
inside a configured stop sequence; the database derives its trips from stop
events it already records (get_segments pairs any origin and destination).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

Route = Mapping[str, Any]

SUBROUTE_PREFIX = "sub--"


def subroute_id(parent_route_id: str, origin_id: str, destination_id: str) -> str:
    return f"{SUBROUTE_PREFIX}{parent_route_id}--{origin_id}--{destination_id}"


def _key(route: Route) -> tuple[str, str, str, str]:
    return (
        route["line_id"],
        route.get("direction", ""),
        route["origin"]["naptan_id"],
        route["destination"]["naptan_id"],
    )


def expand_subroutes(routes: Iterable[Route]) -> list[dict[str, Any]]:
    """Every ordered stop pair of each route's `stops` that no route already
    covers (same line, direction, origin and destination), first come first kept.
    """
    routes = list(routes)
    seen = {_key(r) for r in routes}
    extra: list[dict[str, Any]] = []
    for parent in routes:
        stops = parent.get("stops") or []
        for i in range(len(stops)):
            for j in range(i + 1, len(stops)):
                sub = {
                    "route_id": subroute_id(
                        parent["route_id"], stops[i]["naptan_id"], stops[j]["naptan_id"]
                    ),
                    "line_id": parent["line_id"],
                    "direction": parent.get("direction"),
                    "mode": parent["mode"],
                    "origin": dict(stops[i]),
                    "destination": dict(stops[j]),
                    "stops": [dict(s) for s in stops[i : j + 1]],
                    "parent_route_id": parent["route_id"],
                }
                if _key(sub) not in seen:
                    seen.add(_key(sub))
                    extra.append(sub)
    return extra


def find_journeys(
    origin_id: str, destination_id: str, routes: Iterable[Route]
) -> list[list[Route]]:
    """Direct routes first, then one change at a shared stop on another line.

    Each journey is its legs in order. Routes include sub-routes, so a change
    can happen at any configured stop, not only at route ends.
    """
    routes = list(routes)
    direct = [
        [r]
        for r in routes
        if r["origin"]["naptan_id"] == origin_id
        and r["destination"]["naptan_id"] == destination_id
    ]
    starts = [r for r in routes if r["origin"]["naptan_id"] == origin_id]
    ends = [r for r in routes if r["destination"]["naptan_id"] == destination_id]
    changes = [
        [a, b]
        for a in starts
        for b in ends
        if a["destination"]["naptan_id"] == b["origin"]["naptan_id"]
        and a["destination"]["naptan_id"] not in (origin_id, destination_id)
        and a["line_id"] != b["line_id"]
    ]
    return direct + changes


def stop_catalogue(routes: Iterable[Route]) -> list[dict[str, str]]:
    """Distinct stops named by any route, in first-seen order."""
    seen: dict[str, dict[str, str]] = {}
    for r in routes:
        for stop in [r["origin"], *(r.get("stops") or []), r["destination"]]:
            seen.setdefault(
                stop["naptan_id"],
                {"naptan_id": stop["naptan_id"], "name": stop["name"]},
            )
    return list(seen.values())


def journey_options(
    origin_id: str, destination_id: str, routes: Iterable[Route]
) -> list[list[list[Route]]]:
    """find_journeys grouped for riding: each option is its legs, and each leg
    the routes that serve it (take whichever comes first). All direct routes form
    one option; transfers form one option per interchange stop.
    """
    direct: list[Route] = []
    by_change: dict[str, tuple[list[Route], list[Route]]] = {}
    for legs in find_journeys(origin_id, destination_id, routes):
        if len(legs) == 1:
            direct.append(legs[0])
            continue
        first, second = by_change.setdefault(
            legs[0]["destination"]["naptan_id"], ([], [])
        )
        if legs[0] not in first:
            first.append(legs[0])
        if legs[1] not in second:
            second.append(legs[1])
    options = [[direct]] if direct else []
    return options + [[first, second] for first, second in by_change.values()]
