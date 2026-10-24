# Recorder operations

D owns this directory. No server has been provisioned by these files. Use an
existing authorized Vultr Linux VM, or keep the laptop awake until one is ready.
Do not create paid resources without authorization. No public inbound port is
needed for this recorder; outbound HTTPS and the database connection are needed.

## Local recorder (Windows, macOS, Linux)

This document operates `ingest.database_poller`, the imported database pipeline.
Main's separate `backend.ingest.poller` retains complete HTTP responses for short
bus recording. That raw archive is not accepted by `ingest.admin replay`; their
formats and derivation paths are different. Keep one canonical database writer.
The imported SQL inference has not yet been reconciled with the revised PLAN's
canonical identity, quality and provenance requirements. Do not treat its view
rows as approved model evidence merely because this branch has been integrated.

Python >=3.11. From `backend/`, use B's uv environment with the separate D driver:

```text
uv sync --locked
```

Or create a dedicated environment with `python -m venv .venv`, activate it using
the platform's normal procedure, and `python -m pip install -r ingest/requirements.txt`.
This alternative does not require B's branch or change the backend lockfile.

Copy `.env.example` to `.env` locally if it does not exist; preserve existing
values. Set `TFL_APP_KEY` and `DATABASE_URL` there. Do not copy secrets into shell
commands, source files or chat. The recorder reads `backend/.env` regardless of
the launching directory. Relative `RAW_BACKUP_DIR` resolves from the repo root.

Run from `backend/`, using the configured environment's Python:

```text
python -m ingest.admin init
python -m ingest.admin replay
python -m ingest.database_poller
```

`--once` records one poll for a smoke check. `--backup-only` explicitly skips the
database. Without `DATABASE_URL`, backups continue and a warning is logged.
After changing credentials, restart the process. Only one recorder should own a
backup directory. Do not run `admin replay` concurrently with that recorder.
The database ledger makes retries idempotent; it is not a multi-worker queue.

## Linux server, user systemd

Check out the reviewed integrated commit on the VM. In `backend/`, create a
virtual environment and install the recorder dependency as above. Configure
`backend/.env` privately on the VM; on Linux, set file permissions to owner-only:

```sh
chmod 600 backend/.env
```

That command is from the repository root. Initialize and replay first, then render
the service from the repository root (this step does not install it):

```sh
python deploy/render_service.py
```

It detects this checkout's paths and writes an ignored `.local/` unit. To use a
different environment, pass `--python /path/to/python` (quote paths with spaces).
After reviewing the generated unit, install it for the current Linux user:

```sh
mkdir -p "$HOME/.config/systemd/user"
cp .local/delaylens-recorder.service "$HOME/.config/systemd/user/delaylens-recorder.service"
systemctl --user daemon-reload
systemctl --user enable --now delaylens-recorder
systemctl --user status delaylens-recorder
journalctl --user -u delaylens-recorder --since '5 minutes ago'
```

Ask the VM administrator to enable lingering for this user (`loginctl enable-linger`)
so the user service survives logout. Verify it after logout and a reconnect, and
verify a controlled process restart. A unit file alone does not prove overnight
operation. Logs intentionally contain counts/error classes, never URLs or secrets.

## Public web: API service and Caddy (prepared, not installed)

B prepared these files; nothing here has been installed, started or provisioned, and
no server was touched. A VM, open ports 80 and 443, and any DNS name need the team's
authorization (David and Jintian) before use. D owns this directory: review before use.

The shape: the FastAPI app listens on `127.0.0.1:8000` only; Caddy serves the built
frontend (`frontend/dist`) and proxies `/api/*` to it. The frontend calls `/api/...` on
its own origin, so no CORS or `VITE_API_BASE_URL` is needed.

On the VM, from the reviewed integrated commit:

```sh
cd backend && uv sync --locked                                          # creates backend/.venv from uv.lock
cd ../frontend && npm ci && npm run build                                   # writes frontend/dist
cd .. && python deploy/render_web.py --site <ip-with-dashes>.sslip.io       # writes .local/delaylens-api.service and .local/Caddyfile
```

`render_web.py` only renders into the ignored `.local/` directory and checks that `--site` is
a plain hostname. Review both files, then (needs authorization) install the unit as a user
service like the recorder (`systemctl --user enable --now delaylens-api`, plus lingering)
and give Caddy the Caddyfile (Caddy needs permission to bind ports 80 and 443).

Firewall: allow inbound 80 and 443 (the cloud provider's firewall group, and `ufw` if it
is enabled). Port 8000 stays closed to the outside; only Caddy reaches it on loopback.

Caddy usually runs as its own `caddy` user. If `frontend/dist` sits under a home directory
whose mode is 700, Caddy cannot read it and static files return 403. Either copy the build
to a shared path and render with it:

```sh
sudo mkdir -p /srv/delaylens && sudo cp -r frontend/dist /srv/delaylens/dist
python deploy/render_web.py --site <site> --dist /srv/delaylens/dist
```

or give the path's directories `o+x` (search only, not listing). Copy again after each rebuild.

`backend/.env` on the VM must be created privately (`chmod 600`) and set `DATABASE_URL`,
`TFL_APP_KEY`, `GEMINI_API_KEY` and `ASK_ACCESS_CODE`. **Set `ASK_ACCESS_CODE`: when it is
unset, `/api/ask` is open to anyone and spends the Gemini key.** Never put these values in
chat, commands or committed files.

Redeploying a change (needs the same authorization as the first deploy). Per PLAN section 8,
feature freeze is Sunday 09:30, after which role B (David) approves and announces changes, and
from 11:15 only B-approved, demo-breaking redeploys are made:

```sh
git pull --ff-only
cd backend && uv sync --locked
cd ../frontend && npm ci && npm run build   # then copy dist again if serving from /srv/delaylens
systemctl --user restart delaylens-api
```

Checks after it is up (run from outside the VM):

```sh
curl -s https://<site>/api/health                  # {"status":"ok"}
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://<site>/api/ask \
  -H 'content-type: application/json' -d '{"question":"hello"}'   # 401 without the passcode
```

Or run all of this at once from any machine (standard library only; see the script's docstring
for flags, and note it measures latency from that machine over that network):

```sh
python deploy/smoke_check.py https://<site>
```

Then open `https://<site>/` on mobile data and confirm the bus 29 form shows the expected
advice. If uv is not available, create `backend/.venv` and install the dependencies listed in
`backend/pyproject.toml` by hand (the project has no build backend, so `pip install -e .`
is not supported). Not verified: Caddy and systemd syntax were not run (neither is installed on the
machine that wrote these files); the uvicorn command was smoke-tested locally only.

## Local demo checklist (offline snapshot)

For presenting from one laptop with no database, no TfL key and no network. The API
reads the frozen bus 29 snapshot (24 Oct 2026, 16:55 UTC); the UI labels it as a
frozen, not live, copy. Run from the repository root.

1. Start the API (terminal 1). Leave `DATABASE_URL`, `TFL_APP_KEY` and `GEMINI_API_KEY`
   unset so nothing can reach the network:

   ```text
   cd backend
   SNAPSHOT_DIR="$(cd ../docs/evidence/bus29-db-snapshot-20261024T1655Z && pwd)" \
     uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

2. Start the frontend (terminal 2): `cd frontend && npm run dev`, then open
   <http://127.0.0.1:5173/>. The dev server proxies `/api` to port 8000.
3. Check the offline numbers (turn Wi-Fi off first): bus 29, Saturday 24 Oct, deadline
   17:00 London gives leave 16:25 at 90%; deadline 15:30 is `low_data` (data exists, but
   no departure time reaches 90%), so there is no recommendation. `/api/ask` needs a Gemini key and is not available offline; do not
   demo it without network.
4. Run the smoke check from the demo computer and keep the output:

   ```text
   python3 deploy/smoke_check.py http://127.0.0.1:8000 --skip-ask --skip-port-check
   ```

   Expected: `ALL CHECKS PASSED`, bus 29 with 26 trips, 16:25 / p=0.9, `low_data`
   at 15:30. Latency is measured from that machine only.
5. Recording laptop: plug in the charger and stop sleep, for example on macOS
   `caffeinate -dimsu` in a spare terminal (or System Settings > Battery, Lock Screen),
   on Windows `powercfg /change standby-timeout-ac 0`. Confirm AC power with
   `pmset -g batt`. Do not stop the recorder or run `admin replay` while it records.

Verified 24 Oct 2026 on a macOS laptop (main `2d7e51c`): steps 1, 2 and 4 passed with
the snapshot and no database or key set (`ALL CHECKS PASSED`; 20 requests, p50 4 ms,
p95 4 ms). Not verified: the actual Wi-Fi-off check (step 3) and the Windows demo
computer; repeat both there. The sleep setting was not changed by this checklist.

## Recovery, inspection and handoff

From `backend/`, with the recorder stopped for replay:

```text
python -m ingest.admin verify-backups
python -m ingest.admin replay
python -m ingest.admin derive
python -m ingest.admin health
python -m ingest.admin snapshot
```

Each successful poll is one complete gzipped JSONL batch, written to a temporary
file, fsynced and atomically renamed into `.local/raw/pending/`. Only after the
database transaction commits does it move to `archive/YYYY-MM-DD/`. Archive files
are retained as the fallback. A crash between commit and move causes a harmless
ledger-deduplicated retry. Corrupt files cause a visible error and remain retained;
inspect them before moving them aside. `.tmp` files are incomplete interrupted
writes and are never replayed automatically. Do not delete retained backups.

`snapshot` exports route configuration, inferred segments, coverage, generation
time and an explicit provenance label to ignored `.local/delaylens-snapshot.json.gz`.
It contains no credentials. Its database reads use one consistent snapshot. Regenerate
it before demo; it is a dated fallback, not a substitute for live data.

To rebuild a new database, apply `init` and use `replay --include-archive`. Imported
out-of-order batches invalidate the inference checkpoint and rebuild events from
retained raw database rows. No raw-data retention policy deletes this archive.
Refresh old continuous-aggregate buckets manually if replaying data older than
the seven-day automatic refresh window. For this hackathon all data fits inside it.

Read `tasks/data-ingestion.md` for the exact SQL contract. Run checks from
the repository root using an environment with `pytest` and `ruff` installed:

```text
python -m pytest -c backend/ingest/pytest.ini -q
python -m ruff check backend/ingest deploy
git diff --check
```

Database tests require explicit `INGEST_RUN_DB_TESTS=1` and a configured database;
all their sample rows and state changes are transactionally rolled back. Set that
environment variable in the shell appropriate to your OS. Ordinary tests make
no network calls. Linux/macOS execution and systemd deployment must be verified
on the actual VM; Windows checks do not prove either.

## Existing local recorders (Windows PowerShell 5.1)

From the repository root, inspect without starting anything (also the default):

```powershell
.\deploy\local-recorders.ps1 -Check
.\deploy\local-recorders.ps1 -Start
.\deploy\local-recorders.ps1 -Start -StartBus29Minutes 60
```

Use `-SystemPython` to override the independent recorder's default
`D:\Python311\python.exe`. All workspace paths resolve from the script's repository
root. The database
workspace is `.local/data-workspace/backend`, using Python at
`.local/data-workspace/.local/venv/Scripts/python.exe` and its old `ingest.poller`
module name. Starts use hidden windows and UTC-stamped stdout/stderr files in
that workspace's `.local/logs/`. An existing database recorder (including the
renamed `ingest.database_poller`) prevents another database launch. Concurrent
helper starts are serialized; manual starts must respect the same writer rule.

The optional independent recording runs `backend.ingest record` in
`.local/worktrees/bus29-short` for route
`bus-29-outbound-mornington-crescent-tottenham-court-road`. Each invocation starts
a recorder that creates a new `.local/runs/bus29-short-<UTC timestamp>/` there; the
recorder refuses an existing directory, so stdout/stderr go to the sibling
`bus29-short-<UTC timestamp>.log` and `.err`, as for runs started by hand. A running
independent recorder blocks another bus 29 launch; it can start even when the
database recorder is already running.
Existing environments/configuration must already be prepared. `-Check` shows
processes, selected database health counts and the latest run status/counts from
the last log line (also reading a `recorder.log` left inside a run by the earlier
helper layout). Missing data or
failed health checks are reported as unavailable with error details hidden.
No environment-file contents or connection strings are printed. The helper never
stops processes or deletes files. A launch PID alone does not prove collection;
run `-Check` again and inspect the logs before claiming success.
