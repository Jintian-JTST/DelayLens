"""Synthetic regression fixtures; these are never reported as real TfL samples."""

from __future__ import annotations

import copy
import csv
import gzip
import hashlib
import http.client
import json
import tempfile
import unittest
import urllib.error
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

try:
    from backend.ingest.__main__ import replay
    from backend.ingest.artifacts import london_features, quality_report
    from backend.ingest.common import (
        ROOT,
        atomic_json,
        iso,
        load_route,
        timestamp,
        writer_lock,
    )
    from backend.ingest.derive import derive, read_polls
    from backend.ingest.poller import append_poll, fetch_json, record
    INGEST_PACKAGE = "backend.ingest"
except ModuleNotFoundError as exc:
    if exc.name != "backend":
        raise
    from ingest.__main__ import replay
    from ingest.artifacts import london_features, quality_report
    from ingest.common import ROOT, atomic_json, iso, load_route, timestamp, writer_lock
    from ingest.derive import derive, read_polls
    from ingest.poller import append_poll, fetch_json, record
    INGEST_PACKAGE = "ingest"

BASE = datetime(2026, 10, 24, 16, tzinfo=UTC)
ROUTE = load_route()
O = ROUTE["origin"]["naptan_id"]
D = ROUTE["destination"]["naptan_id"]


def temporary_directory(prefix="test-"):
    # Use an explicitly writable workspace path, including on managed Windows.
    directory = ROOT / ".local" / "test-runs"
    directory.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix=prefix, dir=directory)


def row(at: int, stop: str, arrival: int, vehicle: str = "SYNTHETIC_A", trip: str = "SYNTHETIC_TRIP_1") -> dict:
    return {"lineId": "24", "direction": "inbound", "vehicleId": vehicle, "tripId": trip,
            "naptanId": stop, "timestamp": iso(BASE + timedelta(seconds=at)),
            "expectedArrival": iso(BASE + timedelta(seconds=arrival)), "timeToStation": arrival - at}


def fixture(trips: list[tuple[int, str, str]] | None = None) -> list[dict]:
    trips = trips or [(0, "SYNTHETIC_A", "SYNTHETIC_TRIP_1")]
    polls = []
    for at in range(0, max(t[0] for t in trips) + 691, 30):
        payload = [row(at, "OUTSIDE_SELECTED_SEGMENT", at + 600, "SYNTHETIC_OTHER", "SYNTHETIC_OTHER")]
        for offset, vehicle, trip in trips:
            if at - offset in (0, 30):
                payload.append(row(at, O, offset + 60, vehicle, trip))
            if at - offset in (600, 630):
                payload.append(row(at, D, offset + 660, vehicle, trip))
        polls.append({"poll_id": f"SYNTHETIC_poll_{at}", "collector_id": "SYNTHETIC",
                      "polled_at": iso(BASE + timedelta(seconds=at)), "http_status": 200,
                      "error": None, "payload": payload})
    return polls


def metadata(status="recording") -> dict:
    return {"route": ROUTE, "status": status, "started_at": iso(BASE), "ended_at": None,
            "interval_seconds": 30, "duration_minutes": 90, "source": "synthetic_test_only"}


class InferenceTests(unittest.TestCase):
    def test_complete_segment_has_traceable_estimated_endpoints(self):
        polls = fixture()
        result = derive(polls, ROUTE)
        self.assertEqual(len(result["segments"]), 1)
        segment = result["segments"][0]
        self.assertEqual(segment["travel_seconds"], 600)
        self.assertEqual(segment["quality"], "estimated")
        self.assertNotIn("actualArrival", segment)
        events = {e["event_id"]: e for e in result["events"]}
        for key in ("origin_event_id", "destination_event_id"):
            event = events[segment[key]]
            self.assertEqual(event["source_timestamp_count"], 2)
            self.assertEqual(len(event["absence_confirmations"]), 2)
            self.assertTrue(all(timestamp(c["at"]) >= timestamp(event["inferred_at"])
                                for c in event["absence_confirmations"]))
            self.assertTrue(event["prediction_ids"])
            self.assertTrue(event["poll_ids"])

    def test_early_disappearance_is_not_an_arrival(self):
        polls = fixture()
        for poll in polls[:2]:
            for item in poll["payload"]:
                if item["naptanId"] == O:
                    item["expectedArrival"] = iso(BASE + timedelta(seconds=180))
                    item["timeToStation"] += 120
        result = derive(polls, ROUTE)
        self.assertEqual(result["segments"], [])
        self.assertIn("disappeared_before_near_stop", [e["exclusion_reason"] for e in result["events"]])

    def test_repeated_cached_prediction_is_one_source_timestamp(self):
        polls = fixture()
        polls[1]["payload"][-1] = copy.deepcopy(polls[0]["payload"][-1])
        result = derive(polls, ROUTE)
        self.assertEqual(result["segments"], [])
        origin = next(e for e in result["events"] if e["naptan_id"] == O)
        self.assertEqual(origin["source_timestamp_count"], 1)

    def test_failed_poll_blocks_disappearance_confirmation(self):
        polls = fixture()
        polls[2].update(http_status=503, error="http_503", payload=None)
        result = derive(polls, ROUTE)
        self.assertEqual(result["segments"], [])
        self.assertIn("capture_interruption", [e["exclusion_reason"] for e in result["events"]])

    def test_empty_response_is_not_absence_confirmation(self):
        polls = fixture()
        polls[2]["payload"] = []
        result = derive(polls, ROUTE)
        self.assertEqual(result["segments"], [])

    def test_jump_near_stop_is_uncertain(self):
        polls = fixture()
        polls[0]["payload"][-1] = row(0, O, 240)
        result = derive(polls, ROUTE)
        self.assertEqual(result["segments"], [])
        self.assertIn("prediction_time_jump", [e["exclusion_reason"] for e in result["events"]])

    def test_different_vehicle_or_trip_or_direction_cannot_pair(self):
        for field, value in (("vehicleId", "SYNTHETIC_B"), ("tripId", "SYNTHETIC_TRIP_2"), ("direction", "outbound")):
            with self.subTest(field=field):
                polls = fixture()
                for poll in polls:
                    for item in poll["payload"]:
                        if item["naptanId"] == D:
                            item[field] = value
                self.assertEqual(derive(polls, ROUTE)["segments"], [])

    def test_missing_identity_is_excluded(self):
        polls = fixture()
        for poll in polls:
            for item in poll["payload"]:
                if item["naptanId"] == O:
                    item.pop("tripId")
        result = derive(polls, ROUTE)
        self.assertEqual(result["segments"], [])
        self.assertEqual(result["excluded_source_records"]["missing_trip_id"], 2)

    def test_reused_vehicle_is_two_independent_runs(self):
        polls = fixture([(0, "SYNTHETIC_A", "SYNTHETIC_TRIP_1"), (900, "SYNTHETIC_A", "SYNTHETIC_TRIP_2")])
        result = derive(polls, ROUTE)
        self.assertEqual(len(result["segments"]), 2)
        report = quality_report(polls, result, metadata())
        self.assertEqual(report["independent_trips"], 2)
        self.assertEqual(report["distinct_vehicles"], 1)

    def test_two_collectors_and_replay_do_not_multiply_samples(self):
        polls = fixture()
        other = copy.deepcopy(polls)
        for poll in other:
            poll["poll_id"] += "_collector2"
            poll["collector_id"] = "SYNTHETIC_COLLECTOR2"
            poll["polled_at"] = iso(timestamp(poll["polled_at"]) + timedelta(seconds=1))
        merged = sorted(polls + other, key=lambda p: (p["polled_at"], p["poll_id"]))
        first = derive(polls, ROUTE)
        combined = derive(merged, ROUTE)
        self.assertEqual(first["segments"], combined["segments"])
        self.assertEqual(combined, derive(merged, ROUTE))
        self.assertEqual(combined["events"][0]["source_timestamp_count"], 2)

    def test_stale_feed_cannot_confirm_an_arrival(self):
        polls = fixture()
        for poll in polls[2:5]:
            poll["payload"] = copy.deepcopy(polls[0]["payload"][:1])
        self.assertEqual(derive(polls, ROUTE)["segments"], [])

    def test_stale_entity_in_fresh_feed_still_counts_as_present(self):
        polls = fixture()
        near = copy.deepcopy(polls[1]["payload"][-1])
        for poll in polls[2:9]:
            poll["payload"].append(copy.deepcopy(near))
        result = derive(polls, ROUTE)
        self.assertEqual(result["segments"], [])
        origin = next(e for e in result["events"] if e["naptan_id"] == O)
        self.assertEqual(origin["exclusion_reason"], "stale_prediction_at_last_sighting")

    def test_pending_approach_is_distinct_from_early_disappearance(self):
        polls = fixture()[:2]
        for poll in polls:
            poll["payload"][-1] = row(int((timestamp(poll["polled_at"]) - BASE).total_seconds()), O, 600)
        event = derive(polls, ROUTE)["events"][0]
        self.assertEqual(event["exclusion_reason"], "pending_approach")

    def test_reverse_intermediate_stop_order_is_rejected(self):
        polls = fixture()
        for at, stop_index, arrival in ((180, 3, 240), (210, 3, 240), (300, 2, 360), (330, 2, 360)):
            polls[at // 30]["payload"].append(row(at, ROUTE["stops"][stop_index]["naptan_id"], arrival))
        result = derive(polls, ROUTE)
        self.assertEqual(result["segments"], [])
        self.assertIn("stop_order_conflict", [r["reason"] for r in result["rejected_segments"]])

    def test_source_clock_disagreement_does_not_become_a_valid_event(self):
        polls = fixture()
        for poll in polls[:2]:
            poll["payload"][-1]["timeToStation"] = 999
        result = derive(polls, ROUTE)
        self.assertEqual(result["segments"], [])
        self.assertEqual(result["excluded_source_records"]["inconsistent_prediction_clock"], 2)

    def test_cached_duplicate_between_valid_confirmations_is_neutral(self):
        original = fixture()
        polls = copy.deepcopy(original[:5] + original[7:])
        # Source age: first absence 60.4s, identical cached response 90.4s,
        # second new absence 60.8s. The two usable frames are only 60.4s apart.
        polls[1]["polled_at"] = iso(BASE + timedelta(seconds=60.8))
        polls[2]["polled_at"] = iso(BASE + timedelta(seconds=120.4))
        polls[3]["polled_at"] = iso(BASE + timedelta(seconds=150.4))
        polls[3]["payload"] = copy.deepcopy(polls[2]["payload"])
        polls[4]["polled_at"] = iso(BASE + timedelta(seconds=180.8))
        polls[4]["payload"] = [row(120, "OUTSIDE_SELECTED_SEGMENT", 720, "SYNTHETIC_OTHER", "SYNTHETIC_OTHER")]
        result = derive(polls, ROUTE)
        self.assertEqual(len(result["segments"]), 1)
        without_cache = polls[:3] + polls[4:]
        self.assertEqual(result["segments"], derive(without_cache, ROUTE)["segments"])
        origin = next(e for e in result["events"] if e["naptan_id"] == O)
        self.assertEqual(len(origin["absence_confirmations"]), 2)
        self.assertLessEqual((timestamp(origin["absence_confirmations"][1]["at"])
                              - timestamp(origin["absence_confirmations"][0]["at"])).total_seconds(), 90)

    def test_rewound_source_frame_cannot_count_as_new_absence(self):
        polls = fixture()[:4]
        polls[2]["payload"] = [row(0, "OUTSIDE_SELECTED_SEGMENT", 600, "SYNTHETIC_OTHER", "SYNTHETIC_OTHER")]
        polls[3]["payload"] = [row(10, "OUTSIDE_SELECTED_SEGMENT", 610, "SYNTHETIC_OTHER", "SYNTHETIC_OTHER")]
        origin = next(e for e in derive(polls, ROUTE)["events"] if e["naptan_id"] == O)
        self.assertEqual(origin["quality"], "uncertain")
        self.assertEqual(origin["absence_confirmations"], [])


class DurabilityAndExportTests(unittest.TestCase):
    def test_access_denied_is_durable_and_stops_without_retry(self):
        sequence = {"http_status": 200, "payload": {"stopPointSequences": [{"stopPoint": [
            {"id": stop["naptan_id"]} for stop in ROUTE["stops"]
        ]}]}}
        status = {"http_status": 200, "payload": [{"lineStatuses": [{"statusSeverityDescription": "Good Service"}]}]}
        denied = {"http_status": 403, "payload": None, "error": "http_403", "received_at": iso(BASE)}
        with temporary_directory() as temporary:
            run = Path(temporary) / "new-run"
            with (patch(f"{INGEST_PACKAGE}.poller.fetch_json", side_effect=[sequence, status, denied]) as fetch,
                  patch(f"{INGEST_PACKAGE}.poller.process_run"), patch("builtins.print")):
                exit_code = record(run)
            self.assertEqual(exit_code, 2)
            self.assertEqual(fetch.call_count, 3)
            polls, _ = read_polls([run / "polls.jsonl"])
            self.assertEqual(polls[0]["http_status"], 403)
            state = json.loads((run / "run.json").read_text())
            self.assertIsNone(state["started_at"])
            self.assertEqual(state["status"], "access_denied")
            self.assertTrue((run / "polls.jsonl.gz").exists())

    def test_changed_route_is_rejected_before_recording(self):
        sequence = {"http_status": 200, "payload": {"stopPointSequences": []}}
        status = {"http_status": 200, "payload": []}
        with temporary_directory() as temporary:
            run = Path(temporary) / "new-run"
            with (patch(f"{INGEST_PACKAGE}.poller.fetch_json", side_effect=[sequence, status]),
                  patch("builtins.print")):
                self.assertEqual(record(run), 2)
            self.assertFalse((run / "polls.jsonl").exists())
            self.assertEqual(json.loads((run / "run.json").read_text())["status"], "preflight_failed")

    def test_raw_fsync_precedes_downstream_work_and_database_is_optional(self):
        sequence = {"http_status": 200, "payload": {"stopPointSequences": [{"stopPoint": [
            {"id": stop["naptan_id"]} for stop in ROUTE["stops"]
        ]}]}}
        status = {"http_status": 200, "payload": [{"lineStatuses": [{"statusSeverityDescription": "Good Service"}]}]}
        captured = dict(fixture()[0], received_at=iso(BASE))
        with temporary_directory() as temporary:
            run = Path(temporary) / "new-run"
            checkpoints = []

            def downstream(path, final=False):
                data, _ = read_polls([path / "polls.jsonl"])
                checkpoints.append((len(data), final))
                if not final:
                    raise KeyboardInterrupt

            with (patch(f"{INGEST_PACKAGE}.poller.fetch_json", side_effect=[sequence, status, captured]),
                  patch(f"{INGEST_PACKAGE}.poller.process_run", side_effect=downstream),
                  patch.dict("os.environ", {"DATABASE_URL": "invalid-unavailable-database"}),
                  patch("builtins.print")):
                self.assertEqual(record(run), 130)
            self.assertEqual(checkpoints, [(1, False), (1, True)])
            self.assertEqual(json.loads((run / "run.json").read_text())["status"], "interrupted")

    def test_raw_tail_recovery_and_duplicate_poll_identity(self):
        with temporary_directory() as temporary:
            first = Path(temporary) / "a.jsonl"
            second = Path(temporary) / "b.jsonl"
            content = json.dumps(fixture()[0]).encode() + b"\n"
            first.write_bytes(content + b'{"poll_id":')
            second.write_bytes(content)
            polls, recovery = read_polls([first, second])
            self.assertEqual(len(polls), 1)
            self.assertEqual(recovery["duplicate_poll_records"], 1)
            self.assertEqual(len(recovery["incomplete_tails"]), 1)
            self.assertTrue(first.read_bytes().endswith(b'{"poll_id":'))

    def test_corrupt_complete_line_and_conflicting_poll_are_errors(self):
        with temporary_directory() as temporary:
            path = Path(temporary) / "bad.jsonl"
            path.write_bytes(b"{bad}\n")
            with self.assertRaises(ValueError):
                read_polls([path])
            poll = fixture()[0]
            altered = dict(poll, error="different")
            path.write_text(json.dumps(poll) + "\n" + json.dumps(altered) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_polls([path])

    def test_gzip_round_trip_and_crash_flush(self):
        with temporary_directory() as temporary:
            path = Path(temporary) / "a.jsonl"
            with path.open("w", encoding="utf-8") as stream:
                append_poll(stream, fixture()[0])
                self.assertTrue(path.read_bytes().endswith(b"\n"))
            compressed = path.with_suffix(".jsonl.gz")
            compressed.write_bytes(gzip.compress(path.read_bytes()))
            self.assertEqual(read_polls([path])[0], read_polls([compressed])[0])

    def test_zip_manifest_csv_snapshot_and_offline_replay(self):
        with temporary_directory() as temporary:
            run = Path(temporary)
            polls = fixture()
            atomic_json(run / "run.json", metadata())
            (run / "polls.jsonl").write_text("".join(json.dumps(p) + "\n" for p in polls), encoding="utf-8")
            with patch("urllib.request.urlopen", side_effect=AssertionError("Offline replay must not access network")):
                summary = replay(run, make_package=True)
            self.assertEqual(summary["independent_trips"], 1)
            with (run / "derived" / "segments.csv").open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(float(rows[0]["travel_seconds"]), 600)
            before = (run / "derived" / "snapshot.json").read_bytes()
            replay(run)
            self.assertEqual(before, (run / "derived" / "snapshot.json").read_bytes())
            zips = list((run / "exports").glob("*.zip"))
            self.assertEqual(len(zips), 4)
            for path in zips:
                with zipfile.ZipFile(path) as archive:
                    self.assertIsNone(archive.testzip())
                    manifest = json.loads(archive.read("MANIFEST.json"))
                    for item in manifest["files"]:
                        self.assertEqual(hashlib.sha256(archive.read(item["path"])).hexdigest(), item["sha256"])
                    self.assertFalse(any(".env" in name or ".git/" in name or ".local/" in name or "__pycache__" in name for name in archive.namelist()))
            received = run / "received-data"
            received.mkdir()
            data_zip = next(path for path in zips if path.name.endswith("checkpoint-data.zip"))
            with zipfile.ZipFile(data_zip) as archive:
                for name in archive.namelist():
                    self.assertTrue((received / name).resolve().is_relative_to(received.resolve()))
                archive.extractall(received)
            with patch("urllib.request.urlopen", side_effect=AssertionError("Exported replay must stay offline")):
                replayed = replay(received)
            self.assertEqual(replayed["independent_trips"], 1)
            received_snapshot = json.loads((received / "derived" / "snapshot.json").read_text())
            self.assertEqual(json.loads(before)["segments"], received_snapshot["segments"])

    def test_short_recording_cannot_pass_ninety_minute_gate(self):
        polls = fixture([(i * 900, f"SYNTHETIC_{i}", f"SYNTHETIC_TRIP_{i}") for i in range(5)])
        meta = metadata("completed")
        meta["ended_at"] = polls[-1]["polled_at"]
        result = derive(polls, ROUTE)
        self.assertEqual(len(result["segments"]), 5)
        self.assertEqual(quality_report(polls, result, meta)["data_gate"], "incomplete_recording")
        meta["ended_at"] = iso(BASE + timedelta(minutes=90))
        self.assertEqual(quality_report(polls, result, meta)["data_gate"], "pass")

    def test_repeated_london_hour_retains_offset_and_fold(self):
        earlier = london_features("2026-10-25T00:30:00Z")
        later = london_features("2026-10-25T01:30:00Z")
        self.assertEqual(earlier["local_at"][:19], later["local_at"][:19])
        self.assertEqual((earlier["utc_offset_seconds"], earlier["fold"]), (3600, 0))
        self.assertEqual((later["utc_offset_seconds"], later["fold"]), (0, 1))
        self.assertEqual(later["weekday"], 6)

    def test_owner_requested_sixty_minute_window_is_reported_honestly(self):
        polls = fixture()
        meta = metadata("completed")
        meta.update(duration_minutes=60, original_duration_minutes=90, ended_at=iso(BASE + timedelta(minutes=60)))
        report = quality_report(polls, derive(polls, ROUTE), meta)
        self.assertTrue(report["validation_window_complete"])
        self.assertFalse(report["ninety_minute_window_complete"])
        self.assertEqual(report["planned_duration_minutes"], 60)
        self.assertEqual(report["data_gate"], "partial")

    def test_explicit_paths_and_os_lock(self):
        with temporary_directory(prefix="DelayLens Unicode 路径 ") as temporary:
            path = Path(temporary) / ".writer.lock"
            with writer_lock(path), self.assertRaises(OSError), writer_lock(path):
                self.fail("Second writer acquired exclusive lock")
            with writer_lock(path):
                pass

    def test_http_key_is_redacted_even_when_reflected(self):
        fake_key = "SYNTHETIC_TEST_KEY"
        error = urllib.error.HTTPError("https://api.tfl.gov.uk/", 403, "Forbidden", {}, io_bytes(fake_key))
        with patch("urllib.request.urlopen", side_effect=error):
            response = fetch_json("/Line/24/Arrivals", fake_key)
        self.assertEqual(response["http_status"], 403)
        self.assertNotIn(fake_key, json.dumps(response))

    def test_malformed_and_nonfinite_json_remain_recoverable_failures(self):
        for body in (b"not-json", b'{"invalid": NaN}', b'[Infinity]'):
            with self.subTest(body=body):
                response = MagicMock()
                response.__enter__.return_value = response
                response.status = 200
                response.headers = {}
                response.read.return_value = body
                with patch("urllib.request.urlopen", return_value=response):
                    captured = fetch_json("/Line/24/Arrivals")
                self.assertEqual(captured["error"], "malformed_json")
                self.assertEqual(captured["response_text"], body.decode())
                json.dumps(captured, allow_nan=False)

    def test_timeout_rate_limit_and_partial_response_are_explicit(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError()):
            self.assertEqual(fetch_json("/Line/24/Arrivals")["error"], "TimeoutError")
        error = urllib.error.HTTPError("https://api.tfl.gov.uk/", 429, "Rate limited", {"Retry-After": "60"}, io_bytes("wait"))
        with patch("urllib.request.urlopen", side_effect=error):
            captured = fetch_json("/Line/24/Arrivals")
        self.assertEqual((captured["http_status"], captured["retry_after"]), (429, "60"))
        with patch("urllib.request.urlopen", side_effect=http.client.IncompleteRead(b'{"partial":', 20)):
            captured = fetch_json("/Line/24/Arrivals")
        self.assertEqual(captured["error"], "incomplete_response")
        self.assertEqual(captured["response_text"], '{"partial":')


def io_bytes(value: str):
    import io
    return io.BytesIO(value.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
