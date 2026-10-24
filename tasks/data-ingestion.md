# Task: Data ingestion and infrastructure (Code D)

- Task ID: `data-ingestion` / D
- Owner (person / AI tool): Jintian-JTST (D) / Codex
- Branch: `feat/data`
- Status: claimed; task record prepared; implementation not started
- Integrator / reviewer: B (backend, API contract and branch integration); M reviews segment usability
- Updated: 2026-10-24 (Europe/London)
- Source: [PLAN.md](../PLAN.md), sections 1, 3, 6, 7 and 8, at commit `73006fa`
- Record structure: [task template](../docs/tasks/TEMPLATE.md)

## Outcome and acceptance criteria

Deliver real TfL recordings and usable trip segments to M and B, then keep the
recorder and demo running through the overnight gap. Recorder first: time spent
without collecting cannot be recovered from TfL's live API.

### P0: collection and usable data

- [ ] Select one bus segment of roughly 30-45 minutes and one Tube contrast
  segment; verify line status, stop order, direction and TfL identifiers. Record
  the supported segments in `backend/config/routes.json`.
- [ ] Poll `/Line/{lineIds}/Arrivals` every 30 seconds, filtering to the selected
  stops. Preserve `vehicleId`, `naptanId`, `lineId`, `direction`,
  `timeToStation`, `expectedArrival` and the source `timestamp`; record collection
  time separately as `polled_at`.
- [ ] Save every fetched poll to a gzipped JSONL backup and insert predictions
  into Tiger Data. A database outage must leave the raw backup recoverable.
- [ ] Handle 429, 5xx, timeouts, malformed responses and network loss with
  explicit logs and bounded backoff; resume recording after recovery.
- [ ] Store all timestamps in UTC. The repeated local 01:00 hour on Sunday
  25 October must remain distinct, ordered and recoverable.
- [ ] Run derivation every minute. Produce stop events and same-direction
  origin-to-destination segments with positive, plausible ride times.
- [ ] Hand M a real segment CSV and B the segment query and coverage SQL.
  Counts must reflect real recordings; incomplete coverage stays visible.

### Infrastructure and demo readiness

- [ ] Run the recorder and derivation on Vultr under `systemd` with automatic
  restart; keep the laptop recorder as the planned backup.
- [ ] Verify a forced recorder termination restarts collection and that a
  network/database interruption can be recovered from JSONL without duplicate
  derived trips.
- [ ] Provide `coverage_hourly`, compression configuration and stats SQL to B;
  target the planned SQL checks below 100 ms and report actual measurements.
- [ ] Deploy the API package from B and production frontend build from F;
  verify the core journey at the public URL with B.
- [ ] Show overnight row counts and gaps, including the clock change; recover
  available missing data from JSONL before other morning work.
- [ ] Produce a fallback snapshot of real recorded data and verify B's API can
  serve it without Tiger Data. Identify its capture time and coverage clearly.
- [ ] Measure deployed API latency against the plan's p95 < 300 ms target,
  prepare the hotspot backup and complete the final VM/recorder/snapshot check.

### Optional work and scope limits

- [ ] Submit the National Rail HSP access request. Build rail support only if
  access arrives by Saturday evening and the core pipeline is working (P2).

M owns modelling and calibration; B owns API endpoints, caching and Gemini; F
owns the frontend. Multi-leg routing, arbitrary A-to-B journeys and accounts are
outside the MVP. Do not expand into another role's files without coordination.

## Ownership and dependencies

### Owned files and deliverables

These application paths are planned in `PLAN.md`; they do not exist yet at task
creation.

| Path / deliverable | D's responsibility |
| --- | --- |
| `backend/ingest/poller.py` | TfL polling, stop filtering, JSONL durability, database writes and recovery |
| `backend/ingest/derive.py` | Prediction episodes, inferred stop events, trip segments and repeatable derivation |
| `backend/sql/001_schema.sql` | Prediction hypertable, indexes, stop events, coverage aggregate and compression |
| `backend/config/routes.json` | Verified route IDs, modes, directions, endpoints and supported stop IDs |
| `deploy/` | VM setup instructions, service units, deployment and recovery procedures |
| `tasks/data-ingestion.md` | D's status, decisions, evidence and handoff |
| Data handoff | Segment CSV, segment/coverage/stats SQL and a real-data fallback snapshot; artifact locations agreed with M/B |

D also owns TfL, Tiger Data and Vultr setup, the HSP request, and hotspot backup
preparation. Keep credentials in local environment files or the server's secret
configuration; never put credentials or personal machine paths in this record.

### Shared interfaces and decisions to agree

`PLAN.md` provides the initial contract and schema sketch. B owns the final API
contract and freezes it at Saturday 17:00; subsequent changes require B's approval.

| Interface | Required handoff / decision |
| --- | --- |
| `routes.json` -> B/M | Agree the file shape and stable `route_id` values. Match the planned API route fields; B supplies dynamic trip counts and `hours_covered` from real data. |
| Predictions -> stop events | Use the last `expectedArrival` seen with `timeToStation <= 60 s`, otherwise the last poll in which the prediction appeared. A return to the same stop more than 20 minutes later starts a new episode. Preserve the distinction between inferred events and independently measured arrivals. |
| Stop events -> segments -> M | Match the same vehicle and direction from origin to destination with `t_D > t_O`. Agree segment table/CSV fields, UTC timestamp representation and sample identity before M consumes them. |
| Segment storage -> B | Supply the `get_segments` query, coverage SQL and stats SQL. B implements `backend/app/db.py`, the minute-refreshed cache and API responses. |
| Raw backups and laptop/VM overlap | Agree duplicate identity, replay rules and treatment of still-active prediction episodes. Re-running derivation or importing overlapping backups must not inflate trip counts. |
| Fallback snapshot -> B | Agree the snapshot format and loading interface; B owns API-side loading. Keep source, capture time and supported hours visible. |
| Deployment -> B/F | Receive their runnable API package and production frontend build; coordinate environment variables, service commands and public smoke tests. |

Verify TfL rate limits and current Tiger Data schema/compression syntax against
official documentation during implementation. The SQL in `PLAN.md` is a sketch,
not a migration already verified against a live service.

### Local configuration and prerequisites

Configuration names from `PLAN.md` relevant to D:

| Name | Purpose |
| --- | --- |
| `TFL_APP_KEY` | Server-side TfL access |
| `DATABASE_URL` | Tiger Data PostgreSQL connection |
| `POLL_LINE_IDS` | Selected bus and Tube line IDs |
| `POLL_STOP_IDS` | Selected NaPTAN stop IDs |
| `POLL_INTERVAL_SECONDS` | Poll interval; planned value `30` |
| `RAW_BACKUP_DIR` | Local raw archive directory; planned value `.local/raw` |

B owns `.env.example`, `backend/pyproject.toml` and `backend/uv.lock`; request
needed dependencies or configuration changes through B. The plan selects Python
>= 3.11 with `uv`. D's `systemd` deployment is Linux-specific; local setup and
shared instructions must remain portable. No dependencies are installed by this
task-file preparation step.

## Milestones and handoffs

Times below are targets from `PLAN.md`, in **Europe/London**. Checkboxes indicate
completion evidence, not simply that the scheduled time has passed.

| Target | D deliverable / exit check | Recipient |
| --- | --- | --- |
| Sat 24 Oct, kickoff | Supported routes selected; identifiers and contract questions recorded | B, M |
| Sat 15:00 | Real rows every 30 seconds; JSONL backup; schema and `routes.json` available. If blocked, M helps D at the recorder gate. | M, B |
| Sat 16:30 | Recovery/backoff exercised, stop IDs checked and HSP request submitted | B |
| Sat 18:30 | Plausible derived segments, segment CSV, `get_segments` and coverage SQL | CSV -> M; SQL -> B |
| Sat 19:30 | Support the real data -> model -> API -> screen gate; follow the team's bus-only cut if needed | All |
| Sat 21:30 | Recorder and derivation supervised on the VM; compare laptop/VM collection coverage and row counts | B |
| Sat 22:30 | Coverage aggregate, compression and stats SQL ready; receive API/frontend builds | SQL -> B; builds <- B/F |
| Sat 23:00 | Public deployment works; smoke-tested with B, with deployed revision recorded | B, F |
| Sat 23:45 | Forced-kill restart proven; disk and laptop backup readiness checked | All |
| Sun 25 Oct, 07:00-07:15 | Overnight rows/gaps shown across the clock change; JSONL recovery first if needed | All |
| Sun 08:30 | Data QA complete and snapshot-backed API verified without Tiger Data | B, M |
| Sun 09:30 | Deployed latency measured, hotspot prepared, redeploy coordinated with B; feature freeze | B, F |
| Sun 10:00 | Data/infra description and evidence ready for the submission | M |
| Sun 10:30 | Final VM, recorder, snapshot and hotspot checks; dress rehearsal | All |

B integrates branches in order **D -> M -> B -> F**. After the feature freeze,
coordinate bug fixes with B; after submission, only B-approved demo-breaking fixes
are redeployed. D covers the pipeline portion of the table demo.

## Verification plan

Record actual commands, inputs and results here as implementation lands. Planned
checks are not completed tests.

- Collection: inspect successive real polls and database rows at the configured
  cadence; compare retained records with the raw archive.
- Failure and replay: exercise 429/5xx/timeouts, Wi-Fi loss, database loss, JSONL
  recovery and overlapping laptop/VM recordings.
- Derivation: check episode boundaries, missing/vanishing predictions, direction,
  repeated vehicle IDs, incomplete trips, replay idempotency and plausible ride
  times. Include the repeated local hour with distinct UTC instants.
- Handoff: M reads the real CSV; B runs the segment, coverage and stats queries
  against the agreed schema. Check counts and covered hours against source data.
- Deployment: prove service restart, public UI behaviour, snapshot operation
  without the database and the backup network path; record latency measurements.
- Documentation: check UTF-8/LF, exact-case local links and Git whitespace.

## Handoff

- Changes and relevant commits: local checkout fast-forwarded to `73006fa`
  (`Initialise PLAN.md`); `feat/data` created from that revision; this task record
  added at the path assigned to D in `PLAN.md`.
- Checks actually run, OS/runtime and results: Windows, PowerShell 7.6.5,
  Git 2.52.0.windows.1 and Python 3.11.9 detected; clean starting worktree verified;
  remote fetch, fast-forward and branch creation succeeded. One-off Python
  documentation checks passed: UTF-8 without BOM, LF, final newline, no trailing
  whitespace, three exact-case local links, template sections, owner and branch.
  `git diff --check` passed; the new file also passed
  `git diff --no-index --check -- NUL tasks/data-ingestion.md` (Windows empty-file
  comparison; exit 1 indicates the new content differs, with no whitespace errors).
- Unverified behaviour or blockers: implementation has not started. Route choices,
  service/account access, API/schema details, recovery, latency and deployment are
  unverified; no application tests, service setup or external sign-ups have run.
- Next action: D selects and verifies the bus/Tube segments, agrees the data
  interfaces with B/M, then starts the minimal recorder plus JSONL backup. B, as
  integrator, adds this task to [docs/PROGRESS.md](../docs/PROGRESS.md) and reconciles
  the preparation-stage project summary with `PLAN.md`.
