from app.journeys import SUBROUTE_PREFIX
from ingest.settings import load_routes
from ingest.store import _with_subroutes


def test_sync_adds_stop_pair_subroutes_for_the_database_view():
    configured = load_routes()
    synced = _with_subroutes(configured)
    subs = [r for r in synced if r["route_id"].startswith(SUBROUTE_PREFIX)]
    assert synced[: len(configured)] == configured
    assert subs and len(synced) == len(configured) + len(subs)
    assert len({r["route_id"] for r in synced}) == len(synced)
    for r in subs:  # every column sync_routes writes is present
        assert r["line_id"] and r["direction"] in {"inbound", "outbound"} and r["mode"]
        assert r["origin"]["naptan_id"] != r["destination"]["naptan_id"]
