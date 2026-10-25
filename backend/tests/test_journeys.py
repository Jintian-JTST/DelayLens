"""Sub-routes, journey search, line merging and the journey endpoint."""

import json
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import db, journeys, main, model
from app.main import app
from app.schemas import Stats

client = TestClient(app)


def stop(i: str) -> dict:
    return {"naptan_id": i, "name": f"Stop {i}"}


def route(route_id: str, line: str, stops: list[str]) -> dict:
    return {
        "route_id": route_id,
        "line_id": line,
        "direction": "inbound",
        "mode": "bus",
        "origin": stop(stops[0]),
        "destination": stop(stops[-1]),
        "stops": [stop(s) for s in stops],
    }


# A-B-C-D on line 1, B-C-E on line 2: B->C is served by both lines.
LINE1 = route("one", "1", ["A", "B", "C", "D"])
LINE2 = route("two", "2", ["B", "C", "E"])


def test_subroutes_cover_every_ordered_stop_pair_once() -> None:
    subs = journeys.expand_subroutes([LINE1, LINE2])
    pairs = {
        (s["line_id"], s["origin"]["naptan_id"], s["destination"]["naptan_id"])
        for s in subs
    }
    # 6 pairs on line 1 minus the configured A->D, 3 on line 2 minus B->E.
    assert len(subs) == 7
    assert ("1", "A", "D") not in pairs and ("2", "B", "E") not in pairs
    assert ("1", "B", "C") in pairs and ("2", "B", "C") in pairs
    sub = next(
        s for s in subs if s["route_id"] == journeys.subroute_id("one", "B", "D")
    )
    assert [s["naptan_id"] for s in sub["stops"]] == ["B", "C", "D"]
    assert sub["parent_route_id"] == "one"


def test_journeys_are_direct_then_one_change_on_another_line() -> None:
    routes = [LINE1, LINE2, *journeys.expand_subroutes([LINE1, LINE2])]
    found = journeys.find_journeys("A", "E", routes)
    assert all(len(j) == 2 for j in found)
    changes = {j[0]["destination"]["naptan_id"] for j in found}
    assert changes == {"B", "C"}
    assert all(j[0]["line_id"] == "1" and j[1]["line_id"] == "2" for j in found)

    options = journeys.journey_options("B", "C", routes)
    assert len(options) == 1 and len(options[0]) == 1  # one direct option...
    assert {r["line_id"] for r in options[0][0]} == {
        "1",
        "2",
    }  # ...served by both lines
    assert journeys.find_journeys("D", "A", routes) == []


def test_merged_lines_board_whichever_comes_first() -> None:
    start = datetime(2026, 10, 24, 12, tzinfo=UTC)
    end = start + timedelta(hours=4)
    a = model.synthetic_segments(start, end, headway_min=20, ride_min=10)
    b = model.synthetic_segments(
        start + timedelta(minutes=10), end, headway_min=20, ride_min=10
    )
    merged = model.merge_segments([a, b])
    assert len(merged) == len(a) + len(b)
    assert np.all(np.diff(merged.t_origin) >= 0)
    assert np.diff(merged.t_origin[:4]).tolist() == [
        600,
        600,
        600,
    ]  # 10-min combined headway
    np.testing.assert_array_equal(
        merged.coverage,
        [[model.to_epoch(start + timedelta(minutes=10)), model.to_epoch(end)]],
    )


# --- endpoint -----------------------------------------------------------------

START = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
END = datetime(2026, 10, 24, 20, 0, tzinfo=UTC)


def _rows(origin_offset_min: float, ride_min: float, headway_min: float = 4):
    syn = model.synthetic_segments(
        START + timedelta(minutes=origin_offset_min),
        END,
        headway_min=headway_min,
        ride_min=ride_min,
    )
    return [
        db.Segment(
            vehicle_id=f"v{v}",
            origin_observed_at=datetime.fromtimestamp(int(o), UTC),
            destination_observed_at=datetime.fromtimestamp(int(d), UTC),
            ride_seconds=float(d - o),
            origin_episode_started_at=datetime.fromtimestamp(int(o), UTC),
        )
        for v, o, d in zip(syn.vehicle_id, syn.t_origin, syn.t_dest, strict=True)
    ]


@pytest.fixture
def network(monkeypatch, tmp_path):
    """Line 1 A->D recorded A-B; line 2 B->E recorded B-E (a change at B)."""
    path = tmp_path / "routes.json"
    path.write_text(json.dumps([LINE1, LINE2]), encoding="utf-8")
    monkeypatch.setattr(main, "ROUTES_PATH", path)
    segments = {
        journeys.subroute_id("one", "A", "B"): _rows(0, 10),
        "two": _rows(2, 15),
    }
    snapshot = db.Snapshot(
        segments=segments,
        coverage={k: db.Coverage(len(v), []) for k, v in segments.items()},
        origin_events={},
        poll_times=[],
        stats=Stats(
            rows=0,
            chunks=0,
            compression_ratio=None,
            first_polled_at=None,
            last_polled_at=None,
        ),
        refreshed_at=START,
    )
    cache = db.SegmentCache("postgres://unused", loader=lambda url: snapshot)
    cache.refresh()
    monkeypatch.setattr(main, "_cache", cache)
    main._segments_memo.clear()


def test_journey_endpoint_plans_a_change(network) -> None:
    response = client.post(
        "/api/journey-curve",
        json={
            "origin_naptan_id": "A",
            "destination_naptan_id": "E",
            "deadline": "2026-10-24T17:00:00Z",
            "walk_to_min": 0,
            "walk_from_min": 0,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert [
        (leg["origin"]["naptan_id"], leg["destination"]["naptan_id"])
        for leg in data["legs"]
    ] == [("A", "B"), ("B", "E")]
    assert data["recommended"] is not None
    assert data["data_quality"]["basis"].startswith(
        "One change: bus 1 Stop A to Stop B"
    )
    # 10-min ride, change, 15-min ride: never faster than 25 min door to door.
    for p in data["points"]:
        assert datetime.fromisoformat(p["arrive_p50"]) - datetime.fromisoformat(
            p["depart_at"]
        ) >= timedelta(minutes=25)


def test_journey_endpoint_rejects_unconnected_stops(network) -> None:
    response = client.post(
        "/api/journey-curve",
        json={
            "origin_naptan_id": "D",
            "destination_naptan_id": "A",
            "deadline": "2026-10-24T17:00:00Z",
        },
    )
    assert response.status_code == 404


def test_subroutes_are_listed_only_on_request(network) -> None:
    assert len(client.get("/api/routes").json()) == 2
    assert len(client.get("/api/routes?include_subroutes=true").json()) == 9
    assert {s["naptan_id"] for s in client.get("/api/stops").json()} == set("ABCDE")
