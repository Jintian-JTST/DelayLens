"""Export a fresh read-only bus 29 snapshot and compare it with the demo numbers.

From backend/:
    python -m tools.refresh_snapshot --out ../docs/evidence/bus29-db-<UTC time>
    python -m tools.refresh_snapshot --compare-only ../docs/evidence/bus29-db-final-20261024T202558Z

The export reads Tiger Data through DATABASE_URL (backend/.env) and writes only the new
folder; it never overwrites an existing one. The comparison loads the folder as an offline
snapshot (no database, no network) and asks /api/departure-curve for Saturday 17:00 London
(16:00 UTC), the demo case, then prints whether it still gives 16:22 at 92%.
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROUTE = "bus-29-outbound-mornington-crescent-tottenham-court-road"
DEADLINE = "2026-10-24T16:00:00Z"  # Saturday 17:00 London (BST)
EXPECTED = ("16:22", 92)


def compare(folder: Path) -> bool:
    os.environ["SNAPSHOT_DIR"] = str(folder.resolve())
    os.environ.pop("DATABASE_URL", None)
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        routes = {r["route_id"]: r for r in client.get("/api/routes").json()}
        curve = client.post(
            "/api/departure-curve",
            json={
                "route_id": ROUTE,
                "deadline": DEADLINE,
                "walk_to_min": 5,
                "walk_from_min": 5,
                "tolerance": 0.1,
            },
        ).json()
    quality = curve["data_quality"]
    rec = curve["recommended"]
    print(f"snapshot {folder.name}")
    print(f"  trips on route: {routes[ROUTE].get('trips_observed')}")
    print(f"  status: {quality['status']}; basis: {quality['basis']}")
    if rec is None:
        print("  recommended: none")
        return False
    leave = datetime.fromisoformat(rec["depart_at"])
    got = (leave.astimezone(ZoneInfo("Europe/London")).strftime("%H:%M"), round(rec["p_on_time"] * 100))
    print(f"  17:00 London deadline -> leave {got[0]}, {got[1]}% (p={rec['p_on_time']})")
    same = got == EXPECTED
    print(f"  demo numbers {EXPECTED[0]} / {EXPECTED[1]}%: {'UNCHANGED' if same else 'DIFFERENT'}")
    return same


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--out", type=Path, help="new folder to export into (must not exist)")
    group.add_argument("--compare-only", type=Path, help="existing snapshot folder to compare")
    args = parser.parse_args(argv)
    if args.out is not None:
        if args.out.exists():
            print(f"{args.out} already exists; refusing to overwrite", file=sys.stderr)
            return 2
        from tools import export_db_snapshot

        code = export_db_snapshot.main(["--out", str(args.out), "--route-filter", "bus-29"])
        if code:
            return code
        folder = args.out
    else:
        folder = args.compare_only
    return 0 if compare(folder) else 1


if __name__ == "__main__":
    raise SystemExit(main())
