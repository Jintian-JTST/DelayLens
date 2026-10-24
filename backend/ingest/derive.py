"""Deterministic replay; forecasts remain estimates, never actual arrivals."""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

from .common import iso, stable_id, timestamp

SOURCE_FIELDS = ("lineId", "direction", "vehicleId", "tripId", "naptanId", "timestamp", "expectedArrival", "timeToStation")
METHOD = "near_stop_prediction_v1"


def prediction_id(row: dict) -> str:
    # Poll/collector IDs are deliberately absent: overlapping recorders share evidence.
    return stable_id("prediction", *(row.get(field) for field in SOURCE_FIELDS))


def read_polls(paths: list[Path]) -> tuple[list[dict], dict]:
    """Recover complete lines, reporting (and retaining) only an incomplete final line."""
    polls: dict[str, dict] = {}
    tails = []
    duplicate_polls = 0
    for path in sorted(set(paths)):
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rb") as stream:
            for number, line in enumerate(stream, 1):
                if not line.endswith(b"\n"):
                    tails.append({"file": path.name, "line": number, "sha256": hashlib.sha256(line).hexdigest(),
                                  "bytes": len(line), "reason": "incomplete_final_line", "retained_in_original": True})
                    continue
                try:
                    poll = json.loads(line)
                    timestamp(poll["polled_at"])
                    poll_id = poll["poll_id"]
                except (ValueError, KeyError, TypeError) as exc:
                    raise ValueError(f"Invalid complete raw record: {path.name}:{number}") from exc
                if poll_id in polls:
                    if poll != polls[poll_id]:
                        raise ValueError(f"Conflicting raw poll_id: {poll_id}")
                    duplicate_polls += 1
                else:
                    polls[poll_id] = poll
    ordered = sorted(polls.values(), key=lambda p: (timestamp(p["polled_at"]), p["poll_id"]))
    return ordered, {"duplicate_poll_records": duplicate_polls, "incomplete_tails": tails}


def raw_paths(run: Path) -> list[Path]:
    # Prefer the original, and preserve explicit overlap files in imports/.
    main = run / "polls.jsonl"
    paths = [main] if main.exists() else list(run.glob("polls.jsonl.gz"))
    if not paths and (run / "raw").exists():
        # A data ZIP is a self-contained replay input after extraction.
        paths.extend((run / "raw").glob("*.jsonl"))
        paths.extend((run / "raw").glob("*.jsonl.gz"))
    imports = run / "imports"
    if imports.exists():
        paths.extend(imports.glob("*.jsonl"))
        paths.extend(imports.glob("*.jsonl.gz"))
    return paths


def successful(poll: dict) -> bool:
    return poll.get("http_status") == 200 and not poll.get("error") and isinstance(poll.get("payload"), list)


def _frames(polls: list[dict]) -> list[dict]:
    """One successful observation per UTC 30s slot; collectors do not multiply evidence."""
    slots: dict[int, dict] = {}
    for poll in polls:
        instant = timestamp(poll["polled_at"])
        slot = int(instant.timestamp()) // 30
        payload = poll.get("payload") if successful(poll) else []
        row_ids = sorted(prediction_id(row) for row in payload if isinstance(row, dict))
        fresh = False
        source_times = []
        for row in payload:
            try:
                source_time = timestamp(row["timestamp"])
                age = (instant - source_time).total_seconds()
                if age >= -30:
                    source_times.append(source_time)
                fresh = fresh or -30 <= age <= 90
            except (ValueError, KeyError, TypeError, AttributeError):
                pass
        frame = {"at": instant, "poll": poll, "id": stable_id("frame", row_ids),
                 "healthy": successful(poll) and bool(payload) and fresh, "rows": payload,
                 "source_at": max(source_times) if source_times else None}
        previous = slots.get(slot)
        # A successful collector can cover another collector's outage in the same slot.
        if previous is None or (frame["healthy"], instant, poll["poll_id"]) > (
            previous["healthy"], previous["at"], previous["poll"]["poll_id"]
        ):
            slots[slot] = frame
    return [slots[key] for key in sorted(slots)]


def derive(polls: list[dict], route: dict) -> dict:
    frames = _frames(polls)
    stops = {item["naptan_id"]: i for i, item in enumerate(route["stops"])}
    episodes: dict[tuple, list[dict]] = defaultdict(list)
    presence: dict[tuple, list[tuple[int, Any]]] = defaultdict(list)
    excluded = Counter()
    source_refs: dict[str, set[str]] = defaultdict(set)
    # Retain every contributing raw poll even when its duplicate observation is collapsed.
    for poll in polls:
        if successful(poll):
            for row in poll["payload"]:
                if isinstance(row, dict):
                    source_refs[prediction_id(row)].add(poll["poll_id"])
    seen_invalid = set()
    selected_prediction_ids = set()
    for frame_index, frame in enumerate(frames):
        for row in frame["rows"]:
            if not isinstance(row, dict) or row.get("lineId") != route["line_id"] or row.get("naptanId") not in stops:
                continue
            if row.get("direction") != route["direction"]:
                continue
            pid = prediction_id(row)
            selected_prediction_ids.add(pid)
            if row.get("vehicleId") and row.get("tripId"):
                raw_key = (row["lineId"], row["direction"], str(row["vehicleId"]), str(row["tripId"]), row["naptanId"])
                presence[raw_key].append((frame_index, frame["at"]))
            reason = None
            if not row.get("vehicleId") or str(row.get("vehicleId")).lower() in ("0", "000", "unknown"):
                reason = "missing_vehicle_id"
            elif not row.get("tripId") or str(row.get("tripId")).lower() in ("0", "unknown"):
                reason = "missing_trip_id"
            try:
                source_at = timestamp(row["timestamp"])
                expected_at = timestamp(row["expectedArrival"])
                tts = row["timeToStation"]
                if not isinstance(tts, int) or isinstance(tts, bool) or not 0 <= tts <= 7200:
                    reason = reason or "invalid_time_to_station"
                age = (frame["at"] - source_at).total_seconds()
                if not -30 <= age <= 90:
                    reason = reason or "stale_source_prediction"
                if abs((expected_at - source_at).total_seconds() - tts) > 120:
                    reason = reason or "inconsistent_prediction_clock"
            except (KeyError, ValueError, TypeError):
                reason = reason or "invalid_prediction_timestamp"
            if reason:
                if pid not in seen_invalid:
                    excluded[reason] += 1
                    seen_invalid.add(pid)
                continue
            key = (row["lineId"], row["direction"], str(row["vehicleId"]), str(row["tripId"]), row["naptanId"])
            candidates = episodes[key]
            if not candidates or (frame["at"] - candidates[-1]["last_seen"]).total_seconds() > 1200:
                candidates.append({"observations": {}, "last_seen": frame["at"], "last_frame": frame_index,
                                   "first_frame": frame_index})
            episode = candidates[-1]
            episode["last_seen"] = frame["at"]
            episode["last_frame"] = frame_index
            if pid not in episode["observations"]:
                episode["observations"][pid] = {
                    "prediction_id": pid, "source_at": source_at, "expected_at": expected_at,
                    "time_to_station": tts, "first_seen": frame["at"], "frame_index": frame_index,
                }
    events = []
    for key, groups in sorted(episodes.items()):
        for group_index, episode in enumerate(groups):
            next_start = groups[group_index + 1]["first_frame"] if group_index + 1 < len(groups) else len(frames)
            # A stale/malformed prediction still shows presence; dropping it must not
            # manufacture the two absences needed for an inferred arrival.
            sightings = [(index, at) for index, at in presence[key]
                         if episode["first_frame"] <= index < next_start]
            if sightings:
                episode["last_frame"], episode["last_seen"] = sightings[-1]
            observations = sorted(episode["observations"].values(), key=lambda o: (o["source_at"], o["prediction_id"]))
            last = observations[-1]
            reason = None
            confirmations = []
            if len({o["source_at"] for o in observations}) < 2:
                reason = "fewer_than_two_source_timestamps"
            elif (episode["last_seen"] - last["source_at"]).total_seconds() > 90:
                reason = "stale_prediction_at_last_sighting"
            elif len({(o["expected_at"], o["time_to_station"]) for o in observations if o["source_at"] == last["source_at"]}) > 1:
                reason = "conflicting_source_timestamp"
            elif last["time_to_station"] > 60:
                reason = "pending_approach" if episode["last_frame"] == len(frames) - 1 else "disappeared_before_near_stop"
            else:
                previous = next(o for o in reversed(observations[:-1]) if o["source_at"] != last["source_at"])
                if (last["source_at"] - previous["source_at"]).total_seconds() > 90:
                    reason = "source_prediction_gap"
                elif abs((last["expected_at"] - previous["expected_at"]).total_seconds()) > 120:
                    reason = "prediction_time_jump"
            previous_at = episode["last_seen"]
            previous_frame_id = frames[episode["last_frame"]]["id"]
            previous_source_at = frames[episode["last_frame"]]["source_at"] or last["source_at"]
            if reason is None:
                for frame in frames[episode["last_frame"] + 1:]:
                    if not successful(frame["poll"]) or not frame["rows"]:
                        reason = "capture_interruption"
                        break
                    # Repeated or rewound cached source views neither confirm an
                    # absence nor interrupt otherwise timely independent evidence.
                    if (frame["id"] == previous_frame_id or frame["source_at"] is None
                            or frame["source_at"] <= previous_source_at):
                        continue
                    if (frame["at"] - previous_at).total_seconds() > 90:
                        reason = "capture_interruption"
                        break
                    if not frame["healthy"]:
                        continue
                    previous_at = frame["at"]
                    previous_frame_id = frame["id"]
                    previous_source_at = frame["source_at"]
                    if frame["at"] < last["expected_at"]:
                        continue
                    if confirmations and (frame["at"] - timestamp(confirmations[-1]["at"])).total_seconds() < 20:
                        continue
                    confirmations.append({"poll_id": frame["poll"]["poll_id"], "at": iso(frame["at"]),
                                          "frame_id": frame["id"], "source_at": iso(frame["source_at"])})
                    if len(confirmations) == 2:
                        break
                if reason is None and len(confirmations) < 2:
                    reason = "awaiting_two_post_eta_absences"
            evidence_ids = [o["prediction_id"] for o in observations]
            event_id = stable_id("event", *key, last["prediction_id"])
            event = {
                "event_id": event_id, "route_pattern_id": route["route_pattern_id"], "line_id": key[0],
                "direction": key[1], "vehicle_id": key[2], "trip_id": key[3], "naptan_id": key[4],
                "stop_sequence": stops[key[4]], "inferred_at": iso(last["expected_at"]),
                "inference_method": METHOD, "quality": "estimated" if reason is None else "uncertain",
                "confidence": "supported_by_rule" if reason is None else "insufficient_evidence",
                "exclusion_reason": reason, "first_seen_at": iso(min(o["first_seen"] for o in observations)),
                "last_seen_at": iso(episode["last_seen"]), "prediction_count": len(observations),
                "source_timestamp_count": len({o["source_at"] for o in observations}),
                "last_time_to_station": last["time_to_station"], "selected_prediction_id": last["prediction_id"],
                "prediction_ids": evidence_ids,
                "poll_ids": sorted({p for pid in evidence_ids for p in source_refs[pid]}),
                "absence_confirmations": confirmations,
            }
            events.append(event)
    events.sort(key=lambda event: (event["inferred_at"], event["event_id"]))
    by_run = defaultdict(list)
    for event in events:
        if event["quality"] == "estimated":
            by_run[(event["line_id"], event["direction"], event["vehicle_id"], event["trip_id"])].append(event)
    segments = []
    rejected_segments = []
    for key, run_events in sorted(by_run.items()):
        origins = [e for e in run_events if e["stop_sequence"] == 0]
        destinations = [e for e in run_events if e["stop_sequence"] == len(stops) - 1]
        for origin in origins:
            options = [destination for destination in destinations if 0 < (
                timestamp(destination["inferred_at"]) - timestamp(origin["inferred_at"])
            ).total_seconds() <= route["max_travel_seconds"]]
            if not options:
                if destinations:
                    rejected_segments.append({"origin_event_id": origin["event_id"], "reason": "no_positive_duration_within_bounds"})
                continue
            if len(options) != 1:
                rejected_segments.append({"origin_event_id": origin["event_id"], "reason": "ambiguous_destination"})
                continue
            destination = options[0]
            start, end = timestamp(origin["inferred_at"]), timestamp(destination["inferred_at"])
            seconds = (end - start).total_seconds()
            if seconds < route["min_travel_seconds"]:
                rejected_segments.append({"origin_event_id": origin["event_id"], "reason": "duration_out_of_bounds"})
                continue
            competitors = [o for o in origins if timestamp(o["inferred_at"]) < end and 0 < (
                end - timestamp(o["inferred_at"])
            ).total_seconds() <= route["max_travel_seconds"]]
            if len(competitors) != 1:
                rejected_segments.append({"origin_event_id": origin["event_id"], "reason": "ambiguous_origin"})
                continue
            nearby_intermediates = [e for e in run_events if 0 < e["stop_sequence"] < len(stops) - 1
                                    and start - timedelta(seconds=120) <= timestamp(e["inferred_at"]) <= end + timedelta(seconds=120)]
            if any(not start < timestamp(e["inferred_at"]) < end for e in nearby_intermediates):
                rejected_segments.append({"origin_event_id": origin["event_id"], "reason": "intermediate_time_outside_endpoints"})
                continue
            between = [e for e in run_events if start <= timestamp(e["inferred_at"]) <= end]
            ordered = sorted(between, key=lambda e: timestamp(e["inferred_at"]))
            if any(a["stop_sequence"] >= b["stop_sequence"] for a, b in pairwise(ordered)):
                rejected_segments.append({"origin_event_id": origin["event_id"], "reason": "stop_order_conflict"})
                continue
            run_id = stable_id("run", route["route_pattern_id"], *key, origin["event_id"])
            segments.append({
                "segment_id": stable_id("segment", route["route_id"], origin["event_id"], destination["event_id"]),
                "route_id": route["route_id"], "route_version": route["route_version"],
                "route_pattern_id": route["route_pattern_id"], "run_id": run_id,
                "line_id": key[0], "direction": key[1], "vehicle_id": key[2], "trip_id": key[3],
                "origin_at": origin["inferred_at"], "destination_at": destination["inferred_at"],
                "travel_seconds": seconds, "inference_method": METHOD, "confidence": "supported_by_rule",
                "quality": "estimated", "source": "tfl_live_recording",
                "origin_event_id": origin["event_id"], "destination_event_id": destination["event_id"],
            })
    segments.sort(key=lambda segment: (segment["origin_at"], segment["segment_id"]))
    return {"events": events, "segments": segments, "rejected_segments": rejected_segments,
            "excluded_source_records": dict(sorted(excluded.items())),
            "unique_source_predictions": len(source_refs),
            "selected_source_predictions": len(selected_prediction_ids), "canonical_poll_slots": len(frames)}
