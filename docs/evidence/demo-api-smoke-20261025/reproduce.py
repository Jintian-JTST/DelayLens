"""Measure an isolated locked-snapshot API over loopback HTTP, without service keys.

Run from any directory: python reproduce.py --repo /path/to/OxHack --out result.json
The API runs in this process in a separate server thread. Results include local
HTTP/client overhead; they are neither an in-process handler benchmark nor public
network latency. No application source or environment file is changed.
"""
import argparse
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = args.repo.resolve()
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
clean = not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo, text=True).strip()
if not clean:
    raise SystemExit('Use a clean checkout for this measurement.')
snapshot = 'docs/evidence/bus29-db-final-20261024T202558Z'
for name in ('DATABASE_URL', 'GEMINI_API_KEY', 'TFL_APP_KEY', 'ASK_ACCESS_CODE'):
    os.environ[name] = ''
os.environ['SNAPSHOT_DIR'] = str(repo / snapshot)
sys.path.insert(0, str(repo / 'backend'))
import uvicorn
from app.main import app

sock = socket.socket()
sock.bind(('127.0.0.1', 0))
base = f'http://127.0.0.1:{sock.getsockname()[1]}'
server = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False, lifespan='on'))
thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
thread.start()
end = time.monotonic() + 15
while not server.started:
    if not thread.is_alive() or time.monotonic() > end:
        raise RuntimeError('Isolated API did not start.')
    time.sleep(.01)
body = {'route_id': 'bus-29-outbound-mornington-crescent-tottenham-court-road',
        'deadline': '2026-10-24T17:00:00+01:00', 'walk_to_min': 5,
        'walk_from_min': 5, 'tolerance': .1, 'window_min': 90}

def curve():
    request = urllib.request.Request(base + '/api/departure-curve',
        data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=10) as response:
        result = json.load(response)
        assert response.status == 200
    elapsed = (time.perf_counter() - start) * 1000
    assert result['recommended'] == {'depart_at': '2026-10-24T15:22:00Z', 'p_on_time': .9174}
    assert 'Offline snapshot frozen 24 Oct 20:25 UTC' in result['data_quality']['basis']
    return {'total_ms': round(elapsed, 4), 'server_ms': result['server_ms']}

try:
    with urllib.request.urlopen(base + '/api/health', timeout=10) as response:
        health = json.load(response)
    assert health == {'status': 'ok', 'ask_available': False}
    first = curve()
    warmups = [curve() for _ in range(3)]
    samples = [curve() for _ in range(20)]
    # Nearest rank: ceil(.95 * 20), the nineteenth sorted observation.
    p95 = {key: sorted(row[key] for row in samples)[math.ceil(.95 * len(samples)) - 1]
           for key in ('total_ms', 'server_ms')}
    output = {'measured_at_utc': datetime.now(timezone.utc).isoformat(),
        'git_head': head, 'checkout_clean_before_measurement': clean,
        'snapshot': snapshot, 'service_keys_and_database_empty': True,
        'environment': {'os': platform.system(), 'os_release': platform.release(),
            'machine': platform.machine(), 'python': platform.python_version(),
            'packages': {name: importlib.metadata.version(name)
                         for name in ('fastapi', 'uvicorn', 'numpy')}},
        'transport': 'loopback HTTP via urllib to uvicorn in a separate thread',
        'health': health, 'request': body,
        'recommended': {'depart_at': '2026-10-24T15:22:00Z', 'p_on_time': .9174},
        'first_curve_request': first, 'warmup_count': len(warmups),
        'sample_count': len(samples), 'samples': samples, 'p95_ms': p95,
        'percentile_method': 'nearest rank ceil(0.95*n), nineteen of twenty',
        'limits': ['Single local machine; not public network latency or load test.',
            'Not a physical Wi-Fi-off rehearsal, browser UI, microphone or live Gemini test.',
            'First request follows API startup and health check; not cold process startup.',
            'Measurements depend on this machine and background load.']}
    args.out.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'health': health, 'recommended': output['recommended'],
                      'first_curve_request': first, 'p95_ms': p95}, indent=2))
finally:
    server.should_exit = True
    thread.join(timeout=10)
    sock.close()
