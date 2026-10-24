"""Read-only source review; optional exporter verification writes only ignored scratch."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path

if not __debug__:
    raise RuntimeError("Source review requires assertions; do not use Python -O or PYTHONOPTIMIZE")

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
HANDOFF = ROOT / "docs" / "evidence" / "bus29-short-20261024"
sys.path.insert(0, str(ROOT))

from backend.ingest.artifacts import SEGMENT_FIELDS, write_outputs
from backend.ingest.common import timestamp
from backend.ingest.derive import (
    _frames,
    derive,
    prediction_id,
    raw_paths,
    read_polls,
    successful,
)


def digest(path: Path, *, compressed: bool = False) -> str:
    hasher = hashlib.sha256()
    opener = gzip.open if compressed else open
    with opener(path, "rb") as stream:
        while chunk := stream.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def source_review(run: Path, review: dict) -> tuple[dict, list, dict, dict, dict]:
    """Re-derive all samples and inspect each reviewed endpoint against complete raw polls."""
    paths = raw_paths(run)
    if not paths:
        raise ValueError("No raw polls found in the supplied run")
    polls, recovery = read_polls(paths)
    route = json.loads((HANDOFF / "route.json").read_text(encoding="utf-8"))
    metadata = json.loads((run / "run.json").read_text(encoding="utf-8"))
    assert metadata["route"] == route, "Source run route differs from the published handoff"
    result = derive(polls, route)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=SEGMENT_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["segments"])
    assert output.getvalue() == (HANDOFF / "segments.csv").read_text(encoding="utf-8"), "Replayed segments differ"
    assert result["events"] == json.loads((HANDOFF / "stop_events.json").read_text(encoding="utf-8")), "Replayed stop events differ"

    by_poll = {poll["poll_id"]: poll for poll in polls}
    by_prediction = {
        prediction_id(row): row
        for poll in polls if successful(poll)
        for row in poll["payload"] if isinstance(row, dict)
    }
    frames = {frame["poll"]["poll_id"]: frame for frame in _frames(polls)}
    events = {event["event_id"]: event for event in result["events"]}
    segments = {segment["segment_id"]: segment for segment in result["segments"]}
    examples = []
    assert review["review_type"] == "agent_source_trace" and review["human_review_claimed"] is False
    reviewed = review["reviewed_segments"]
    assert len(reviewed) == len({item["segment_id"] for item in reviewed}) == 3
    for item in reviewed:
        segment = segments[item["segment_id"]]
        assert item["outcome"] == "consistent_with_rule"
        endpoints = []
        for name in ("origin_event_id", "destination_event_id"):
            assert item[name] == segment[name]
            event = events[item[name]]
            assert event["quality"] == "estimated"
            predictions = [by_prediction[pid] for pid in event["prediction_ids"]]
            predictions.sort(key=lambda row: timestamp(row["timestamp"]))
            assert len({row["timestamp"] for row in predictions}) >= 2
            for row in predictions:
                assert str(row["lineId"]) == segment["line_id"]
                assert row["direction"] == segment["direction"]
                assert str(row["vehicleId"]) == segment["vehicle_id"]
                assert str(row["tripId"]) == segment["trip_id"]
                assert row["naptanId"] == event["naptan_id"]
            referenced = {
                prediction_id(row)
                for pid in event["poll_ids"]
                for row in by_poll[pid]["payload"] if isinstance(row, dict)
            }
            assert set(event["prediction_ids"]) <= referenced
            last = by_prediction[event["selected_prediction_id"]]
            assert 0 <= int(last["timeToStation"]) <= 60
            assert timestamp(last["expectedArrival"]) == timestamp(event["inferred_at"])
            assert -30 <= (timestamp(event["last_seen_at"]) - timestamp(last["timestamp"])).total_seconds() <= 90
            source_gap = (timestamp(predictions[-1]["timestamp"]) - timestamp(predictions[-2]["timestamp"])).total_seconds()
            adjustment = abs((timestamp(predictions[-1]["expectedArrival"]) - timestamp(predictions[-2]["expectedArrival"])).total_seconds())
            assert 0 < source_gap <= 90 and adjustment <= 120
            confirmations = event["absence_confirmations"]
            assert len(confirmations) >= 2
            for confirmation in confirmations:
                poll = by_poll[confirmation["poll_id"]]
                frame = frames[confirmation["poll_id"]]
                assert successful(poll) and frame["healthy"]
                assert timestamp(poll["polled_at"]) > timestamp(event["inferred_at"])
                assert confirmation["frame_id"] == frame["id"]
                assert timestamp(confirmation["source_at"]) == frame["source_at"]
                assert not any(
                    isinstance(row, dict)
                    and str(row.get("lineId")) == segment["line_id"]
                    and row.get("direction") == segment["direction"]
                    and str(row.get("vehicleId")) == segment["vehicle_id"]
                    and str(row.get("tripId")) == segment["trip_id"]
                    and row.get("naptanId") == event["naptan_id"]
                    for row in poll["payload"]
                )
            assert (timestamp(confirmations[1]["at"]) - timestamp(confirmations[0]["at"])).total_seconds() >= 20
            assert confirmations[0]["frame_id"] != confirmations[1]["frame_id"]
            assert timestamp(confirmations[1]["source_at"]) > timestamp(confirmations[0]["source_at"])
            fields = ("lineId", "direction", "vehicleId", "tripId", "naptanId", "timestamp", "expectedArrival", "timeToStation")
            endpoints.append({
                "endpoint": name,
                "event_id": event["event_id"],
                "stop_sequence": event["stop_sequence"],
                "naptan_id": event["naptan_id"],
                "inferred_at": event["inferred_at"],
                "selected_prediction_id": event["selected_prediction_id"],
                "source_prediction_count": len(predictions),
                "last_source_gap_seconds": source_gap,
                "last_eta_adjustment_seconds": adjustment,
                "last_predictions": [
                    {"prediction_id": prediction_id(row), "prediction": {key: row[key] for key in fields}}
                    for row in predictions[-2:]
                ],
                "absence_confirmations": confirmations,
            })
        assert endpoints[0]["stop_sequence"] == 0 and endpoints[1]["stop_sequence"] == 7
        assert float(segment["travel_seconds"]) == (timestamp(segment["destination_at"]) - timestamp(segment["origin_at"])).total_seconds()
        examples.append({"segment": segment, "endpoints": endpoints})
    source_hash = digest(paths[0], compressed=paths[0].suffix == ".gz")
    if (run / "polls.jsonl").exists() and (run / "polls.jsonl.gz").exists():
        assert digest(run / "polls.jsonl") == digest(run / "polls.jsonl.gz", compressed=True)
    excerpt = {
        "schema_version": 1,
        "review_type": "agent_source_trace",
        "human_review_claimed": False,
        "raw_uncompressed_sha256": source_hash,
        "raw_poll_count": len(polls),
        "replayed_segment_count": len(result["segments"]),
        "replayed_event_count": len(result["events"]),
        "examples": examples,
        "limitation": "Compact excerpts do not independently prove absence; verification reads each complete original poll. All arrival times remain inferred predictions.",
    }
    return excerpt, polls, result, metadata, recovery


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="Original run or extracted data ZIP with run.json")
    parser.add_argument("--verify-exporter", action="store_true", help="Verify the existing exporter gate in ignored temporary output")
    args = parser.parse_args()
    review = json.loads((EVIDENCE / "audit_review.json").read_text(encoding="utf-8"))
    excerpt, polls, result, metadata, recovery = source_review(args.run.resolve(), review)
    assert excerpt == json.loads((EVIDENCE / "source_excerpt.json").read_text(encoding="utf-8")), "Published excerpts differ from raw evidence"
    manifest = json.loads((EVIDENCE / "MANIFEST.json").read_text(encoding="utf-8"))
    for record in manifest["files"]:
        file = EVIDENCE / record["path"]
        assert file.is_file() and digest(file) == record["sha256"], "Evidence manifest mismatch"
    gate = "not_requested"
    if args.verify_exporter:
        scratch = ROOT / ".local" / "source-review-check"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="bus29-", dir=scratch) as temporary:
            output = Path(temporary)
            (output / "audit_review.json").write_text(json.dumps(review), encoding="utf-8")
            report = write_outputs(output, polls, result, metadata, recovery)
            assert report["source_trace_review"]["reviewed_segment_count"] == 3
            assert report["source_trace_review"]["human_review_claimed"] is False
            assert report["acceptance_gate"] == "pass" and report["support_state"] == "low_data"
            gate = report["acceptance_gate"]
    print(json.dumps({"reviewed_examples": 3, "raw_polls": len(polls), "segments": len(result["segments"]), "exporter_gate": gate, "human_review_claimed": False}))


if __name__ == "__main__":
    main()
