"""Portable paths, UTC timestamps and deterministic content identities."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROUTES = ROOT / "backend" / "config" / "routes.json"
DEFAULT_ROUTE_ID = "bus-24-inbound-warren-leicester"
USER_AGENT = "DelayLens-OxHack/0.1 (public transport research)"


def utc_now() -> str:
    return iso(datetime.now(timezone.utc))


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("UTC offset required")
    return result.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def stable_id(kind: str, *parts: Any) -> str:
    encoded = json.dumps(parts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return kind + "_" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:32]


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def load_route(route_id: str = DEFAULT_ROUTE_ID, config: Path = DEFAULT_ROUTES) -> dict:
    routes = json.loads(config.read_text(encoding="utf-8"))
    route = next((item for item in routes if item["route_id"] == route_id), None)
    if route is None:
        raise ValueError(f"Unknown route_id: {route_id}")
    stops = route.get("stops", [])
    ids = [stop["naptan_id"] for stop in stops]
    if len(ids) < 2 or len(ids) != len(set(ids)):
        raise ValueError("Recording requires an explicit non-repeating stop sequence")
    if ids[0] != route["origin"]["naptan_id"] or ids[-1] != route["destination"]["naptan_id"]:
        raise ValueError("Route endpoints must match its ordered stops")
    if route["mode"] != "bus":
        raise ValueError("This recorder currently supports verified bus segments only")
    return route
