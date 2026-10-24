"""Run with python -m backend.ingest {record,replay,export}."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .artifacts import package, write_outputs
from .common import DEFAULT_ROUTE_ID, atomic_json, load_route, writer_lock
from .derive import derive, raw_paths, read_polls
from .poller import record


def load_environment(path: Path) -> None:
    """Explicit local file only; no shell expansion, execution or credential logging."""
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or key.strip() not in {"TFL_APP_KEY", "POLL_INTERVAL_SECONDS"}:
            raise ValueError("Local config accepts TFL_APP_KEY and POLL_INTERVAL_SECONDS only")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def replay(run: Path, route_id: str | None = None, make_package: bool = False) -> dict:
    with writer_lock(run / ".derivation.lock"):
        metadata = json.loads((run / "run.json").read_text(encoding="utf-8"))
        original_route = metadata["route"]["route_id"]
        if route_id and route_id != original_route:
            metadata["route"] = load_route(route_id)
        alternate = metadata["route"]["route_id"] != original_route
        output = run / "fallback" if alternate else run / "derived"
        polls, recovery = read_polls(raw_paths(run))
        if not polls:
            raise ValueError("No complete raw polls to replay")
        result = derive(polls, metadata["route"])
        report = write_outputs(run, polls, result, metadata, recovery, output)
        exports = []
        first_zip = run / "exports" / f"delaylens-{metadata['route']['route_id']}-first-sample-data.zip"
        if result["segments"] and not first_zip.exists():
            exports.extend(package(run, polls, metadata, output, "first-sample"))
        if make_package:
            label = "final" if metadata.get("status") == "completed" else "checkpoint"
            exports.extend(package(run, polls, metadata, output, label))
        summary = {"route_id": metadata["route"]["route_id"], "polls": report["raw_polls"],
                   "failed_polls": report["failed_polls"], "estimated_stop_events": report["estimated_stop_events"],
                   "independent_trips": report["independent_trips"], "distinct_vehicles": report["distinct_vehicles"],
                   "support_state": report["support_state"], "data_gate": report["data_gate"],
                   "acceptance_gate": report["acceptance_gate"],
                   "exports": [p.relative_to(run).as_posix() for p in exports]}
        atomic_json(output / "status.json", summary)
    # Keep primary outputs intact, derive the explicit shorter route only after the cut.
    if (make_package and report["validation_window_complete"] and not alternate
            and not result["segments"] and original_route == DEFAULT_ROUTE_ID):
        summary["fallback"] = replay(run, "bus-24-inbound-warren-tottenham", True)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("record", "replay", "export"):
        item = commands.add_parser(command)
        item.add_argument("--run", type=Path, required=True, help="Unique run directory; local data must stay outside Git")
        item.add_argument("--route-id", default=DEFAULT_ROUTE_ID if command == "record" else None)
        if command == "record":
            item.add_argument("--minutes", type=float, default=90)
            item.add_argument("--env-file", type=Path)
        elif command == "replay":
            item.add_argument("--package", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "record":
            if args.env_file:
                load_environment(args.env_file)
            return record(args.run.resolve(), args.minutes, float(os.environ.get("POLL_INTERVAL_SECONDS", "30")),
                          os.environ.get("TFL_APP_KEY", ""), args.route_id)
        summary = replay(args.run.resolve(), args.route_id, args.command == "export" or args.package)
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except (OSError, EOFError, ValueError, KeyError) as exc:
        # Values can include paths but never interpolate configured credentials.
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
