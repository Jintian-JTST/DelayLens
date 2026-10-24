"""Portable paths and strict, secret-safe local configuration."""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PROJECT = BACKEND.parent


def load_env(path: Path = BACKEND / ".env") -> None:
    """Read literal KEY=value entries; never evaluate or interpolate secrets."""
    if not path.exists():
        return
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            raise ValueError(f"Invalid environment entry on line {number}")
        if value[:1] in {"'", '"'}:
            if value[-1:] != value[:1] or len(value) < 2:
                raise ValueError(f"Unclosed quoted value on line {number}")
            value = value[1:-1]
        os.environ.setdefault(name, value)


def load_routes(path: Path = BACKEND / "config" / "routes.json") -> list[dict]:
    routes = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(routes, list) or not routes:
        raise ValueError("routes.json must contain a nonempty array")
    identifiers = set()
    for route in routes:
        if (not isinstance(route, dict) or not route.get("route_id")
                or route["route_id"] in identifiers
                or route.get("direction") not in {"inbound", "outbound"}
                or route.get("mode") not in {"bus", "tube"}
                or not route.get("line_id")):
            raise ValueError("Invalid or duplicate route configuration")
        for endpoint in ("origin", "destination"):
            if not route.get(endpoint, {}).get("naptan_id") or not route[endpoint].get("name"):
                raise ValueError("Invalid route endpoint")
        if route["origin"]["naptan_id"] == route["destination"]["naptan_id"]:
            raise ValueError("Route endpoints must differ")
        identifiers.add(route["route_id"])
    return routes


@dataclass(frozen=True)
class Settings:
    line_ids: tuple[str, ...]
    stop_ids: frozenset[str]
    interval: float
    backup_dir: Path

    @classmethod
    def read(cls) -> "Settings":
        config = json.loads((BACKEND / "ingest" / "polling.json").read_text())
        lines = tuple(x.strip() for x in os.getenv("POLL_LINE_IDS", ",".join(config["line_ids"])).split(",") if x.strip())
        stops = frozenset(x.strip() for x in os.getenv("POLL_STOP_IDS", ",".join(config["stop_ids"])).split(",") if x.strip())
        if not lines or not stops or any(not re.fullmatch(r"[A-Za-z0-9-]+", x) for x in (*lines, *stops)):
            raise ValueError("Invalid polling identifiers")
        interval = float(os.getenv("POLL_INTERVAL_SECONDS", "30"))
        if not 5 <= interval <= 3600:
            raise ValueError("POLL_INTERVAL_SECONDS must be between 5 and 3600")
        backup = Path(os.getenv("RAW_BACKUP_DIR", ".local/raw"))
        if not backup.is_absolute():
            backup = PROJECT / backup
        for route in load_routes():
            if route["line_id"] not in lines or not {route["origin"]["naptan_id"], route["destination"]["naptan_id"]} <= stops:
                raise ValueError("Polling must include every configured route endpoint")
        return cls(lines, stops, interval, backup)
