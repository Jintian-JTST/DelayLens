"""Record complete HTTP results before invoking any downstream processing."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from .common import DEFAULT_ROUTE_ID, ROOT, USER_AGENT, atomic_json, load_route, utc_now


def fetch_json(path: str, key: str = "", timeout: float = 10) -> dict:
    url = "https://api.tfl.gov.uk" + path
    if key:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"app_key": key})
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    result = {"requested_at": utc_now(), "http_status": None, "payload": None, "error": None}
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            result.update(http_status=response.status, server_date=response.headers.get("Date"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        result.update(http_status=exc.code, error=f"http_{exc.code}", retry_after=exc.headers.get("Retry-After"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        body = ""
        result["error"] = type(exc).__name__
    # No request URL, credentials, or unrestricted response headers are archived.
    if key:
        body = body.replace(key, "[REDACTED]").replace(urllib.parse.quote(key, safe=""), "[REDACTED]")
    result["received_at"] = utc_now()
    try:
        result["payload"] = json.loads(body)
    except (ValueError, TypeError):
        result["response_text"] = body
        if result["error"] is None:
            result["error"] = "malformed_json"
    return result


def append_poll(stream, poll: dict) -> None:
    stream.write(json.dumps(poll, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def process_run(run_dir: Path, final: bool = False) -> None:
    # Separate interpreter loads new derivation code while an early recorder is running.
    # This lets raw collection start before downstream implementation is finished.
    if not (ROOT / "backend" / "ingest" / "__main__.py").exists():
        print(json.dumps({"event": "raw_saved", "derivation": "not_installed_yet"}), flush=True)
        return
    args = [sys.executable, "-m", "backend.ingest", "replay", "--run", str(run_dir)]
    if final:
        args.append("--package")
    try:
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=45)
        print(json.dumps({"event": "derivation", "exit_code": result.returncode, "result": result.stdout[-2500:], "error": result.stderr[-1500:]}), flush=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"event": "derivation_failed", "error": type(exc).__name__}), flush=True)


def record(run_dir: Path, minutes: float = 90, interval: float = 30, key: str = "", route_id: str = DEFAULT_ROUTE_ID) -> int:
    if minutes <= 0 or interval < 30:
        raise ValueError("Positive duration and an interval of at least 30 seconds required")
    route = load_route(route_id)
    run_dir.mkdir(parents=True, exist_ok=False)
    collector_id = str(uuid.uuid4())
    metadata = {"schema_version": 1, "collector_id": collector_id, "created_at": utc_now(), "route": route,
                "duration_minutes": minutes, "interval_seconds": interval, "started_at": None, "ended_at": None,
                "status": "preflight", "source": "tfl_live_recording", "user_agent": USER_AGENT,
                "rules_confirmation": "Owner confirmed onsite that AI-assisted coding and public APIs are allowed, 2026-10-24."}
    atomic_json(run_dir / "run.json", metadata)
    # Persist public validation evidence; reject changed route patterns before recording.
    sequence = fetch_json(f"/Line/{route['line_id']}/Route/Sequence/{route['direction']}", key)
    status = fetch_json(f"/Line/{route['line_id']}/Status", key)
    atomic_json(run_dir / "route_validation.json", {"sequence": sequence, "status": status})
    wanted = [stop["naptan_id"] for stop in route["stops"]]
    patterns = []
    if isinstance(sequence["payload"], dict):
        patterns = [[p["id"] for p in branch.get("stopPoint", [])] for branch in sequence["payload"].get("stopPointSequences", [])]
    matches = [p for p in patterns if any(p[i:i + len(wanted)] == wanted for i in range(len(p)))]
    good_status = isinstance(status["payload"], list) and any(
        s.get("statusSeverityDescription") == "Good Service"
        for line in status["payload"] for s in line.get("lineStatuses", [])
    )
    if not matches or sequence["http_status"] != 200 or status["http_status"] != 200 or not good_status:
        metadata.update(status="preflight_failed", ended_at=utc_now())
        atomic_json(run_dir / "run.json", metadata)
        print(json.dumps({"event": "preflight_failed", "run": str(run_dir)}), flush=True)
        return 2
    raw_path = run_dir / "polls.jsonl"
    started = None
    first_attempt = time.monotonic()
    next_at = first_attempt
    failures = 0
    exit_code = 0
    metadata["status"] = "recording"
    atomic_json(run_dir / "run.json", metadata)
    try:
        with raw_path.open("x", encoding="utf-8", newline="\n") as stream:
            while started is None or time.monotonic() < started + minutes * 60:
                if started is None and time.monotonic() - first_attempt > 600:
                    metadata["status"] = "no_successful_poll"
                    exit_code = 2
                    break
                delay = next_at - time.monotonic()
                if delay > 0:
                    deadline = started + minutes * 60 if started is not None else next_at
                    time.sleep(max(0, min(delay, deadline - time.monotonic())))
                if started is not None and time.monotonic() >= started + minutes * 60:
                    break
                attempted_at = time.monotonic()
                poll = fetch_json(f"/Line/{route['line_id']}/Arrivals", key)
                poll.update(schema_version=1, poll_id=str(uuid.uuid4()), collector_id=collector_id,
                            line_id=route["line_id"], polled_at=poll["received_at"])
                if poll["error"] is None and not isinstance(poll["payload"], list):
                    poll["error"] = "unexpected_payload_shape"
                append_poll(stream, poll)
                successful = poll["http_status"] == 200 and poll["error"] is None
                if successful and started is None:
                    started = time.monotonic()
                    metadata["started_at"] = poll["polled_at"]
                    atomic_json(run_dir / "run.json", metadata)
                print(json.dumps({"event": "poll_saved", "poll_id": poll["poll_id"], "at": poll["polled_at"],
                                  "success": successful, "http_status": poll["http_status"],
                                  "predictions": len(poll["payload"]) if isinstance(poll["payload"], list) else 0,
                                  "error": poll["error"]}), flush=True)
                failures = 0 if successful else failures + 1
                if poll["http_status"] in (401, 403):
                    metadata["status"] = "access_denied"
                    exit_code = 2
                    break
                retry_delay = min(120, interval * 2 ** min(failures, 2)) if failures else interval
                try:
                    retry_delay = max(retry_delay, min(120, float(poll.get("retry_after") or 0)))
                except ValueError:
                    pass
                next_at = attempted_at + retry_delay
                if successful:
                    process_run(run_dir)
    except KeyboardInterrupt:
        metadata["status"] = "interrupted"
        exit_code = 130
    except OSError:
        metadata["status"] = "disk_error"
        exit_code = 2
        raise
    finally:
        metadata["ended_at"] = utc_now()
        if metadata["status"] == "recording":
            metadata["status"] = "completed"
        atomic_json(run_dir / "run.json", metadata)
        if raw_path.exists():
            compressed = raw_path.with_suffix(".jsonl.gz")
            with raw_path.open("rb") as source, compressed.with_suffix(".gz.tmp").open("wb") as target:
                with gzip.GzipFile(fileobj=target, mode="wb", mtime=0) as archive:
                    shutil.copyfileobj(source, archive)
            os.replace(compressed.with_suffix(".gz.tmp"), compressed)
            process_run(run_dir, final=True)
        print(json.dumps({"event": "recording_finished", "status": metadata["status"], "run": str(run_dir)}), flush=True)
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--minutes", type=float, default=90)
    parser.add_argument("--route-id", default=DEFAULT_ROUTE_ID)
    args = parser.parse_args()
    return record(args.run.resolve(), args.minutes, key=os.environ.get("TFL_APP_KEY", ""), route_id=args.route_id)


if __name__ == "__main__":
    raise SystemExit(main())
