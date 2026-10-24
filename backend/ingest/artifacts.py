"""Inspectable handoff files, independent-trip counts and safe ZIP exports."""

from __future__ import annotations

import calendar
import csv
import gzip
import hashlib
import io
import json
import os
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta, timezone
from itertools import pairwise
from pathlib import Path

from .common import ROOT, atomic_json, iso, stable_id, timestamp
from .derive import METHOD, prediction_id, successful

SEGMENT_FIELDS = [
    "segment_id", "route_id", "route_version", "route_pattern_id", "run_id", "line_id", "direction",
    "vehicle_id", "trip_id", "origin_at", "destination_at", "travel_seconds", "inference_method",
    "confidence", "quality", "source", "origin_event_id", "destination_event_id",
]
LIMITATIONS = [
    "TfL supplies arrival predictions, not independently measured arrival events.",
    "Near-stop inference can still be wrong; confidence is a rule-evidence category, not a probability.",
    "This short weekend recording does not establish calibrated predictions or weekday/general-route performance.",
    "Saturday-to-Sunday transfer is unvalidated; use explicitly dated replay/reference periods.",
    "A data snapshot is not a verified model, API, UI, deployment or database integration.",
    "Trip IDs are required for usable samples in v1; missing or ambiguous identities are excluded.",
    "Only complete identity-stable 120-2400-second segments are usable; excluded or missing trips can bias delay distributions.",
]


def london_features(value: str) -> dict:
    """UK rules from 1996 onward, without relying on a machine's tzdata installation."""
    instant = timestamp(value)
    if not 1996 <= instant.year <= 2099:
        raise ValueError("London feature conversion supports 1996-2099; original UTC remains authoritative")
    transitions = []
    for month in (3, 10):
        last_day = calendar.monthrange(instant.year, month)[1]
        last = datetime(instant.year, month, last_day, 1, tzinfo=UTC)
        transitions.append(last - timedelta(days=(last.weekday() + 1) % 7))
    start, end = transitions
    offset = 3600 if start <= instant < end else 0
    local = instant.astimezone(timezone(timedelta(seconds=offset)))
    return {"local_at": local.isoformat(), "local_date": local.date().isoformat(),
            "weekday": local.weekday(), "utc_offset_seconds": offset,
            "fold": int(end <= instant < end + timedelta(hours=1)), "timezone": "Europe/London"}


def quality_report(polls: list[dict], result: dict, metadata: dict) -> dict:
    route = metadata["route"]
    successes = [poll for poll in polls if successful(poll)]
    segments = result["segments"]
    first = metadata.get("started_at") or (polls[0]["polled_at"] if polls else None)
    last = polls[-1]["polled_at"] if polls else None
    expected_slots = []
    successful_slots = set()
    if first and last:
        start_slot = int(timestamp(first).timestamp()) // 30
        end_slot = int(timestamp(last).timestamp()) // 30
        expected_slots = list(range(start_slot, end_slot + 1))
        successful_slots = {int(timestamp(p["polled_at"]).timestamp()) // 30 for p in successes}
    missing = [slot for slot in expected_slots if slot not in successful_slots]
    gaps = []
    for before, after in pairwise(successes):
        seconds = (timestamp(after["polled_at"]) - timestamp(before["polled_at"])).total_seconds()
        if seconds > metadata.get("interval_seconds", 30) * 1.5:
            gaps.append({"from": before["polled_at"], "to": after["polled_at"], "seconds": seconds})
    events = result["events"]
    hours = defaultdict(lambda: {"successful_polls": 0, "usable_segments": 0, "vehicles": set()})
    for poll in successes:
        hour = iso(timestamp(poll["polled_at"]).replace(minute=0, second=0, microsecond=0))
        hours[hour]["successful_polls"] += 1
    for segment in segments:
        hour = iso(timestamp(segment["origin_at"]).replace(minute=0, second=0, microsecond=0))
        hours[hour]["usable_segments"] += 1
        hours[hour]["vehicles"].add(segment["vehicle_id"])
    coverage = [{"hour_utc": hour, "reference_local": london_features(hour),
                 "successful_polls": counts["successful_polls"], "usable_segments": counts["usable_segments"],
                 "distinct_vehicles": len(counts["vehicles"])} for hour, counts in sorted(hours.items())]
    count = len(segments)
    support = "insufficient_data" if count < 5 else "low_data" if count < 15 else "empirical_only_uncalibrated"
    status = metadata.get("status")
    duration = (timestamp(last) - timestamp(first)).total_seconds() if first and last else 0
    window_seconds = ((timestamp(metadata["ended_at"]) - timestamp(first)).total_seconds()
                      if first and metadata.get("ended_at") else duration)
    target_minutes = metadata.get("duration_minutes", 90)
    full_window = status == "completed" and window_seconds >= target_minutes * 60
    return {
        "schema_version": 1, "source": "tfl_live_recording", "route_id": route["route_id"],
        "recording_status": status, "capture_start_utc": first, "last_poll_utc": last,
        "capture_end_utc": metadata.get("ended_at"), "observed_span_seconds": duration,
        "planned_duration_minutes": metadata.get("duration_minutes"), "poll_interval_seconds": 30,
        "validation_window_seconds": window_seconds, "validation_window_complete": full_window,
        "ninety_minute_window_complete": status == "completed" and window_seconds >= 5400,
        "raw_polls": len(polls), "successful_polls": len(successes), "failed_polls": len(polls) - len(successes),
        "empty_successful_polls": sum(not p["payload"] for p in successes),
        "http_failures": dict(Counter(str(p.get("http_status")) for p in polls if not successful(p))),
        "raw_prediction_rows": sum(len(p["payload"]) for p in successes),
        "unique_source_predictions": result["unique_source_predictions"],
        "selected_source_predictions": result["selected_source_predictions"],
        "expected_utc_30_second_slots_through_last_poll": len(expected_slots),
        "successful_utc_30_second_slots": len(successful_slots & set(expected_slots)),
        "poll_slot_completeness": len(successful_slots & set(expected_slots)) / len(expected_slots) if expected_slots else None,
        "missing_successful_slot_starts_utc": [iso(datetime.fromtimestamp(slot * 30, UTC)) for slot in missing],
        "successful_poll_gaps": gaps, "stop_events": len(events),
        "estimated_stop_events": sum(e["quality"] == "estimated" for e in events),
        "uncertain_stop_events": sum(e["quality"] == "uncertain" for e in events),
        "pending_stop_events": sum(str(e["exclusion_reason"]).startswith(("pending_", "awaiting_")) for e in events),
        "uncertain_event_reasons": dict(Counter(e["exclusion_reason"] for e in events if e["exclusion_reason"])),
        "excluded_source_records": result["excluded_source_records"],
        "rejected_segment_reasons": dict(Counter(r["reason"] for r in result["rejected_segments"])),
        "independent_trips": count, "distinct_vehicles": len({s["vehicle_id"] for s in segments}),
        "support_state": support, "calibration_verified": False,
        "data_gate": ("pending" if status == "recording" else "incomplete_recording" if not full_window
                      else "pass" if count >= 5 else "partial" if count else "no_usable_segments"),
        "coverage_hourly": coverage, "limitations": LIMITATIONS,
        "counting_rule": "One canonical complete route segment per matched vehicle/run; never prediction rows or minute replay steps.",
    }


def audit_examples(polls: list[dict], result: dict) -> dict:
    by_prediction = {}
    for poll in polls:
        if successful(poll):
            for row in poll["payload"]:
                if isinstance(row, dict):
                    by_prediction[prediction_id(row)] = {key: row.get(key) for key in (
                        "lineId", "direction", "vehicleId", "tripId", "naptanId", "stationName", "timestamp", "expectedArrival", "timeToStation"
                    )}
    by_event = {event["event_id"]: event for event in result["events"]}
    examples = []
    for segment in result["segments"][:3]:
        endpoints = []
        for field in ("origin_event_id", "destination_event_id"):
            event = by_event[segment[field]]
            endpoints.append({"event": event, "source_predictions": [
                {"prediction_id": pid, "prediction": by_prediction[pid]} for pid in event["prediction_ids"]
            ]})
        examples.append({"segment": segment, "endpoints": endpoints})
    return {"review_status": "source_evidence_for_review", "human_review_claimed": False, "examples": examples,
            "instructions": "Inspect last source predictions, near-stop threshold, two post-ETA absences, matching line/vehicle/trip/direction and stop order. Times are estimates."}


def write_outputs(run: Path, polls: list[dict], result: dict, metadata: dict, recovery: dict, output: Path | None = None) -> dict:
    output = output or run / "derived"
    output.mkdir(parents=True, exist_ok=True)
    report = quality_report(polls, result, metadata)
    report["raw_recovery"] = recovery
    generation = stable_id("generation", metadata["route"]["route_id"], [p["poll_id"] for p in polls])
    report["generation_id"] = generation
    review_path = run / "audit_review.json"
    review = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else {"reviewed_segments": []}
    current = {s["segment_id"]: s for s in result["segments"]}
    reviewed_ids = set()
    for item in review.get("reviewed_segments", []):
        segment = current.get(item.get("segment_id"))
        if (segment and item.get("origin_event_id") == segment["origin_event_id"]
                and item.get("destination_event_id") == segment["destination_event_id"]
                and item.get("outcome") == "consistent_with_rule"):
            reviewed_ids.add(segment["segment_id"])
    report["source_trace_review"] = {
        "review_type": review.get("review_type", "not_reviewed"),
        "reviewed_segment_ids_in_current_generation": sorted(reviewed_ids),
        "reviewed_segment_count": len(reviewed_ids), "required_examples": 3,
        "human_review_claimed": False,
    }
    report["acceptance_gate"] = (report["data_gate"] if report["data_gate"] != "pass"
                                 else "pass" if len(reviewed_ids) >= 3 else "pending_source_trace_review")
    snapshot = {"schema_version": 1, "generation_id": generation, "mode": "recorded_snapshot",
                "source": "tfl_live_recording", "captured_through_utc": report["last_poll_utc"],
                "route": metadata["route"], "inference_method": METHOD, "quality": report,
                "segments": result["segments"], "stop_events": result["events"], "limitations": LIMITATIONS}
    atomic_json(output / "snapshot.json", snapshot)
    atomic_json(output / "quality.json", report)
    atomic_json(output / "stop_events.json", result["events"])
    atomic_json(output / "rejected_segments.json", result["rejected_segments"])
    atomic_json(output / "audit_examples.json", audit_examples(polls, result))
    atomic_json(output / "route.json", metadata["route"])
    atomic_json(output / "audit_review.json", review)
    rows = io.StringIO(newline="")
    writer = csv.DictWriter(rows, fieldnames=SEGMENT_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["segments"])
    temporary = output / "segments.csv.tmp"
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        stream.write(rows.getvalue())
    os.replace(temporary, output / "segments.csv")
    atomic_json(output / "local_time_features.json", [
        {"segment_id": s["segment_id"], "origin": london_features(s["origin_at"]),
         "destination": london_features(s["destination_at"])} for s in result["segments"]
    ])
    if result["segments"] and not (run / "first_snapshot.json").exists():
        atomic_json(run / "first_snapshot.json", snapshot)
    return report


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _write_zip(path: Path, files: dict[str, bytes], kind: str) -> None:
    manifest = {"schema_version": 1, "kind": kind, "files": [
        {"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        for name, content in sorted(files.items())
    ]}
    files = dict(files)
    files["MANIFEST.json"] = _json_bytes(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    with zipfile.ZipFile(temporary) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"ZIP CRC failed: {bad}")
        for entry in manifest["files"]:
            content = archive.read(entry["path"])
            if hashlib.sha256(content).hexdigest() != entry["sha256"]:
                raise ValueError("ZIP readback checksum mismatch")
    os.replace(temporary, path)


def package(run: Path, polls: list[dict], metadata: dict, output: Path | None = None, label: str = "handoff") -> list[Path]:
    derived = output or run / "derived"
    destination = run / "exports"
    files = {path.name: path.read_bytes() for path in sorted(derived.iterdir()) if path.is_file() and path.suffix in (".json", ".csv")}
    raw = b"".join((json.dumps(p, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8") for p in polls)
    files["raw/polls.jsonl.gz"] = gzip.compress(raw, mtime=0)
    files["run.json"] = _json_bytes(metadata)
    validation = run / "route_validation.json"
    if validation.exists():
        files["route_validation.json"] = validation.read_bytes()
    files["README.txt"] = (
        b"DelayLens real TfL data handoff. Start with quality.json, then segments.csv or snapshot.json.\n"
        b"All segment times are inferred, not measured actual arrivals. audit_examples.json links events to raw evidence.\n"
        b"raw/polls.jsonl.gz contains the canonical full captured HTTP payloads through this generation.\n"
        b"MANIFEST.json contains SHA256 checksums. No model, API or UI success is asserted.\n"
    )
    route_id = metadata["route"]["route_id"]
    data_zip = destination / f"delaylens-{route_id}-{label}-data.zip"
    _write_zip(data_zip, files, "real_data_handoff")
    # Positive source allowlist: never traverse .git, .env, local state or environments.
    source_files = {}
    ingest = ROOT / "backend" / "ingest"
    for name in ("__init__.py", "common.py", "poller.py", "derive.py", "artifacts.py", "__main__.py",
                 "README.md", "environment.example", "tests/test_ingestion.py"):
        path = ingest / name
        source_files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    source_files["backend/config/routes.json"] = (ROOT / "backend" / "config" / "routes.json").read_bytes()
    source_files["LICENSE"] = (ROOT / "LICENSE").read_bytes()
    for name in (".gitignore", ".gitattributes", ".editorconfig"):
        path = ROOT / name
        if path.exists():
            source_files[name] = path.read_bytes()
    readme = ingest / "README.md"
    if readme.exists():
        source_files["README.md"] = readme.read_bytes()
    source_zip = destination / f"delaylens-{route_id}-{label}-source.zip"
    _write_zip(source_zip, source_files, "dependency_free_ingestion_source")
    return [data_zip, source_zip]
