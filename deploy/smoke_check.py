"""Smoke-test a running DelayLens site from the outside; read-only, standard library only.

  python deploy/smoke_check.py https://203-0-113-7.sslip.io
  python deploy/smoke_check.py http://127.0.0.1:8000 --skip-ask --skip-port-check

Checks health, routes, the two demo states (bus 29, Sat 24 Oct), that /api/ask is
passcode-gated, that port 8000 is not publicly reachable, and request latency measured
from THIS machine over THIS network (say so when quoting it). It never sends a passcode
or any key. Without --skip-ask it sends one question to /api/ask; if the site is wrongly
open that spends one Gemini call and the check fails. Exit status 1 if any check fails.
"""

import argparse
import json
import socket
import statistics
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

ROUTE = "bus-29-outbound-mornington-crescent-tottenham-court-road"
CURVE = {"route_id": ROUTE, "walk_to_min": 5, "walk_from_min": 5, "tolerance": 0.1}
failures = 0


def report(ok: bool, name: str, detail: str = "") -> None:
    global failures
    failures += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


def call(base: str, path: str, body: dict | None = None, timeout: float = 15.0):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, method="POST" if body is not None else "GET")
    if data is not None:
        request.add_header("content-type", "application/json")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status, text = response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        status, text = error.code, error.read().decode()
    except (urllib.error.URLError, OSError):  # includes timeouts: report, do not crash
        return None, None, (time.perf_counter() - started) * 1000
    ms = (time.perf_counter() - started) * 1000
    try:
        payload = json.loads(text)
    except ValueError:
        payload = None
    return status, payload, ms


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url", help="site root, e.g. https://203-0-113-7.sslip.io")
    parser.add_argument("--requests", type=int, default=20, help="latency samples (default 20)")
    parser.add_argument("--skip-ask", action="store_true", help="do not send anything to /api/ask")
    parser.add_argument("--skip-port-check", action="store_true", help="do not probe port 8000")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        parser.error("url must start with http:// or https://")

    status, payload, _ = call(base, "/api/health")
    if status is None:
        report(False, "site reachable", "no response (connection error or timeout)")
        return 1
    report(status == 200 and isinstance(payload, dict) and payload.get("status") == "ok", "/api/health", f"status {status}")
    if parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost"):
        report(False, "HTTPS", "the public site is served over plain http")

    status, routes, _ = call(base, "/api/routes")
    route_list = routes if isinstance(routes, list) else []
    bus29 = next((r for r in route_list if isinstance(r, dict) and r.get("route_id") == ROUTE), None)
    report(status == 200 and bool(bus29 and bus29.get("trips_observed")), "/api/routes lists bus 29 with trips",
           f"trips_observed {bus29.get('trips_observed') if bus29 else 'missing'}")

    status, advice, _ = call(base, "/api/departure-curve", {**CURVE, "deadline": "2026-10-24T16:00:00Z"})
    rec = (advice or {}).get("recommended")
    quality = ((advice or {}).get("data_quality") or {}).get("status")
    report(status == 200 and quality == "ok" and bool(rec), "demo state: 5pm Sat gives advice",
           f"status {quality}, recommended {rec['depart_at'] + ' p=' + str(rec['p_on_time']) if rec else None}")
    status, none, _ = call(base, "/api/departure-curve", {**CURVE, "deadline": "2026-10-24T14:30:00Z"})
    report(status == 200 and (none or {}).get("recommended") is None, "demo state: 3:30pm Sat gives no advice",
           f"status {((none or {}).get('data_quality') or {}).get('status')}")

    if args.skip_ask:
        print("SKIP  /api/ask passcode check (--skip-ask)")
    else:
        status, _, _ = call(base, "/api/ask", {"question": "smoke check, no passcode"})
        report(status == 401, "/api/ask requires the passcode", f"status {status}; 200 means it is open to anyone")

    if args.skip_port_check:
        print("SKIP  port 8000 check (--skip-port-check)")
    else:
        try:
            socket.create_connection((parsed.hostname, 8000), timeout=3).close()
            report(False, "port 8000 is not publicly reachable", "it accepted a connection; close it")
        except OSError:
            report(True, "port 8000 is not publicly reachable")

    results = [call(base, "/api/departure-curve", {**CURVE, "deadline": "2026-10-24T16:00:00Z"})
               for _ in range(args.requests)]
    failed = sum(1 for status, _, _ in results if status != 200)
    report(failed == 0, f"{len(results)} latency requests all returned 200", f"{failed} failed")
    samples = [ms for status, _, ms in results if status == 200]
    if not samples:
        print("FAILED", f"({failures} failing)")
        return 1
    ordered = sorted(samples)
    p95 = ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]
    print(f"INFO  latency of /api/departure-curve from this machine over this network, {len(samples)} requests: "
          f"p50 {statistics.median(samples):.0f} ms, p95 {p95:.0f} ms, max {max(samples):.0f} ms")
    print("FAILED" if failures else "ALL CHECKS PASSED", f"({failures} failing)" if failures else "")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
