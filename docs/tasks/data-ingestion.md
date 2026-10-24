# Task: DelayLens data ingestion

- Task ID: data-ingestion
- Owner (person / AI tool): D / Codex
- Branch: feat/data (independent clone)
- Status: delivered; live recorder writing to Tiger Data locally; VM deployment pending
- Integrator / reviewer: B; model consumer M

## Outcome and acceptance criteria

Record real TfL predictions every 30 seconds, back up each successful poll to
gzip JSONL, persist into Tiger Data, derive estimated stop events and matched
trip segments without inventing observations. All timestamps are UTC.

## Ownership and dependencies

- Owned files: backend/ingest/, backend/sql/, backend/config/routes.json, deploy/.
- Explicit requested shared edits: backend/.env.example and this task file.
- No backend/app/ or B-owned dependency/lockfile changes.
- B merges D before M. B must add psycopg[binary] to the backend dependencies.
- Local configuration: TFL_APP_KEY, DATABASE_URL, POLL_LINE_IDS, POLL_STOP_IDS,
  POLL_INTERVAL_SECONDS, RAW_BACKUP_DIR; secrets only in ignored backend/.env.

## Interface decisions

Routes (public identifiers):

| route_id | line_id | direction | origin naptan_id | destination naptan_id |
| --- | --- | --- | --- | --- |
| bus-29-outbound-finsbury-park-tottenham-court-road | 29 | outbound | 490015078M | 490000235GX |
| tube-victoria-outbound-brixton-oxford-circus | victoria | outbound | 940GZZLUBXN | 940GZZLUOXC |

Stop order verified with the official TfL Line/29/Route/Sequence/outbound and
Line/victoria/Route/Sequence/outbound endpoints on 2026-10-24 at approximately
13:46 UTC. Weekend status queried for 2026-10-24T00:00:00Z through
2026-10-25T23:59:59Z: both lines report Good Service. Recheck before demo.
Rejected line 24 (Victoria northbound stop closure) and 73 (planned truncation).

The final bus origin is **Finsbury Park / Blackstock Road**, not the inactive
Finsbury Park Station stop `490000083S`: the latter appears in the route sequence
but both StopPoint and Line arrivals returned empty arrays throughout sampling.
The corrected origin has real outbound predictions and its official timetable
to Tottenham Court Road gives **33 minutes**. The first routes-only commit was
`ee055d6`; consumers should use the latest feat/data route file, including this fix.

Polled public IDs are in `backend/ingest/polling.json` and `backend/.env.example`:
lines `29,victoria`; bus stops `490015078M,490008298R,490004679X,490000036S,490000152C,490015042U,490000235GX`;
tube stops `940GZZLUBXN,940GZZLUSKW,940GZZLUVXL,940GZZLUPCO,940GZZLUVIC,940GZZLUGPK,940GZZLUOXC`.
All intermediate IDs were checked against the same route sequence.

### Exact SQL contract for B and M

`get_segments` is a **view**, not a function. Query it with a bound parameter:

```sql
SET TIME ZONE 'UTC';
SELECT route_id, vehicle_id, origin_observed_at, destination_observed_at,
       ride_seconds, origin_method, destination_method
FROM get_segments WHERE route_id = $1 ORDER BY origin_observed_at;
SELECT route_id, trips_observed, hours_covered FROM route_coverage;
```

With psycopg, use `%s` in place of `$1` and pass `(route_id,)` separately.

| View | Exact column | PostgreSQL type / meaning |
| --- | --- | --- |
| get_segments | route_id | text |
| get_segments | vehicle_id | text; reused IDs distinguish trips using origin_episode_started_at |
| get_segments | origin_observed_at | timestamptz; inferred arrival/departure estimate at origin |
| get_segments | destination_observed_at | timestamptz; inferred arrival estimate at destination |
| get_segments | line_id | text |
| get_segments | direction | text; inbound or outbound |
| get_segments | origin_episode_started_at | timestamptz; stable origin episode identifier |
| get_segments | destination_episode_started_at | timestamptz; stable destination episode identifier |
| get_segments | origin_method | text; near_stop_prediction or last_poll |
| get_segments | destination_method | text; near_stop_prediction or last_poll |
| get_segments | ride_seconds | double precision; positive, <=7200 |
| route_coverage | route_id | text; includes active routes with zero trips |
| route_coverage | trips_observed | bigint; number of matched trips, not distinct vehicle IDs |
| route_coverage | hours_covered | timestamptz[]; sorted distinct UTC origin hours with >=1 matched trip; empty array if none |
| coverage_hourly | hour | timestamptz; UTC hourly bucket of raw predictions |
| coverage_hourly | line_id | text |
| coverage_hourly | direction | text |
| coverage_hourly | naptan_id | text |
| coverage_hourly | vehicles | bigint; distinct vehicle IDs seen in this bucket |
| coverage_hourly | predictions | bigint; raw prediction row count |

The stable trip key is `(route_id, vehicle_id, origin_episode_started_at)`.
Do not count a vehicle with multiple runs as one independent trip in M's bootstrap.
Do not call a prediction-covered hour a matched-trip-covered hour. Hour coverage
means at least one matched trip, not a complete hour of continuous recording.
`hours_covered` uses UTC absolute dates, including both distinct hours across the
2026-10-25 UK clock change. B should serialize timezone-aware values as ISO 8601.

Stop events follow PLAN 3.2: latest ETA while <=60 seconds from the stop, otherwise
last observed poll. Disappearance-based events finalize after >=90 seconds of
absence measured against successful polls; an explicit trip-ID change can close
the preceding episode sooner. IDs, line and direction scope episodes; >20-minute gaps or
explicit trip-ID changes start another episode. Unknown vehicle IDs, missing
directions, stale/invalid timestamps and negative horizons are rejected for SQL
but kept in the filtered raw backup. Missing directions are never guessed.
Same-direction pairing chooses the first later destination, rejects crossing a
new origin episode, matches known trip IDs, caps ride time at two hours and never
reuses a destination event. A vanished prediction >120 seconds from either endpoint
is excluded from model trips while its stop event remains inspectable.

**These are prediction-derived estimates, not measured ground-truth arrivals.**
M and the methodology UI must preserve that limitation. Low sample counts must
continue to yield insufficient_data. Additional platform changes/short workings
can still invalidate inference; these heuristics do not prove ground truth.

### Setup and recovery

From `backend/` in a Python >=3.11 environment:

```text
python -m pip install -r ingest/requirements.txt
python -m ingest.admin init
python -m ingest.admin replay
python -m ingest.poller
python -m ingest.admin health
```

B: add `psycopg[binary]>=3.2,<4` to your owned `pyproject.toml` and update `uv.lock`
before integrating `app/db.py`. D did not edit either file or backend/app/.
`backend/.env.example` retains public polling defaults and placeholders for secrets;
this is an explicitly requested exception to the normal B ownership of that file.
Do not copy real local credentials into the example or the integration commit.

The recorder backs up first, commits predictions plus a batch ledger atomically,
then moves the backup into its retained archive. Failed writes retry automatically.
`admin replay --include-archive` restores a new database; ingestion is idempotent.
Derivation checkpoints and stop-event upserts commit atomically. Older backfilled
data invalidate the checkpoint and trigger a reproducible rebuild. Keep one
recorder per backup directory and stop it before manual replay.

Portable Linux systemd rendering and operations are in `deploy/README.md`.

### Documentation checked

- [TfL API reference](https://api.tfl.gov.uk/) and direct Route/Sequence, Timetable,
  Arrivals, current and date-window Status requests.
- [Tiger Data hypertable creation](https://www.tigerdata.com/docs/learn/hypertables/creating-and-configuring-hypertables): explicit by_range partitioning.
- [Continuous aggregates](https://www.tigerdata.com/docs/learn/continuous-aggregates): DISTINCT aggregates supported; real-time mode explicitly enabled.
- [Refresh policy](https://www.tigerdata.com/docs/reference/timescaledb/continuous-aggregates/add_continuous_aggregate_policy): closed-hour materialization and seven-day replay window.
- [Columnstore policy](https://www.tigerdata.com/docs/api/latest/hypercore/add_columnstore_policy/): enable columnstore and CALL policy after two hours.
- [Psycopg installation](https://www.psycopg.org/psycopg3/docs/basic/install.html).
- [Official event page](https://26.oxhack.net/) checked; detailed AI/reuse/submission
  rules are supplied by PLAN's ceremony notes, not independently published there.
  M must confirm those remaining event-rule details before submission.

## Handoff

- Changes and relevant commits: `ee055d6` first route delivery; subsequent delivery
  adds SQL, recorder, event derivation, recovery, tests and deployment instructions.
- Checks actually run: Windows / PowerShell 7.6.5 / Python 3.11.9; direct official
  TfL requests succeeded. Unified ingest test run: **27 passed**, including all
  7 real-database rollback tests. After additional malformed-ID handling, focused
  recorder tests: **23 passed** (three new cases); unchanged DB tests retain their
  successful result. Ruff and Git whitespace checks passed. A secret/ownership
  scan passed for all 19 intended delivery files; secret values were never printed.
- SQL actually executed successfully on Tiger Data TimescaleDB **2.31.0**:
  hypertable, continuous aggregate (real-time mode), refresh and columnstore
  policies, route configuration and both consumer views. Pglast parsed 18 statements.
- Re-running schema initialization succeeded without duplicating policies. Readback
  confirmed the real-time aggregate, refresh/compression jobs and columnstore
  statistics query. Compression reports zero converted chunks at this early stage.
- B's untouched origin/feat/api snapshot: **34 API tests passed** in D's isolated
  validation directory. Real D config smoke test: `/api/routes` returned HTTP 200
  with two routes, both `/api/live` requests returned HTTP 200 (bus 3 arrivals,
  tube 0 at that instant), both real-route curves returned insufficient_data with
  zero points. One dependency deprecation warning; no test failure. The first
  restricted-environment API test invocation hung; a bounded rerun with normal
  process access completed in 1.72 seconds. Dependencies were installed in D's
  local virtual environment, not using B's uv lock, which remains untouched.
- Systemd template rendered with detected local paths; Linux unit execution is
  not proven by this check. A credential-free fallback snapshot was exported and
  read successfully, containing two real inferred tube trips at 14:08 UTC.
- Live evidence: recorder started **2026-10-24T13:49:34Z**; at 14:00:51Z,
  2,892 prediction rows matched 24 readable compressed backups and 75 inferred
  events. At approximately 14:03Z, the first real Tube segment matched vehicle
  217 from 13:49:35Z to 14:01:29Z (**714 seconds**). Counts continue increasing.
- At 14:08:29Z: **4,886 predictions**, 130 stop events and two matched tube trips;
  bus sampling at the corrected origin began at approximately **14:03:59Z**.
  Credentials exist only in ignored local configuration. The recorder is a local
  background process on this machine; the checkout or process configuration alone
  is not an overnight availability guarantee.
- Unverified: Vultr provisioning/deployment, Linux/macOS execution, overnight
  survival, scheduled compression after chunks age and a full bus trip. No
  compression ratio is claimed before any chunks actually convert.
- Next action: B integrates the latest routes, driver and SQL views; M consumes
  inferred segments and checks sample independence/coverage. D continues collecting
  locally; move the recorder to an authorized VM before the laptop sleeps.

### Follow-up audit, 2026-10-24 14:17 UTC

- Continued with the existing database and independent feat/data checkout; no new
  database or service was created. Implementation commit: `36838c2`.
- Exactly one recorder process tree was found: the Windows virtual-environment
  launcher and its child Python process. Updated that tree to the latest tested
  code; the first new poll at 14:16:53Z backed up and committed successfully.
- At 14:14:29Z, live readback showed **6,310 arrival_predictions, 174 stop_events,
  5 get_segments rows**. Route coverage: bus 0; tube 5 with UTC origin hours 13:00
  and 14:00. Counts are a dated snapshot and continue changing.
- Queried information_schema.columns: every documented get_segments and
  route_coverage column and type matches the deployed views. Corrected wording
  above to distinguish disappearance finalization from explicit trip-ID changes.
- Latest complete ingest suite: **30 passed in 11.58 seconds**, including seven
  real-database rollback tests. Ruff passed; PostgreSQL parser accepted all 26
  statements across the two SQL files. No committed test rows remained.
- All 35 tracked files and both implementation branch-only commits were checked
  against actual local credentials: **zero matches**. `.env` and raw backups are
  ignored; only the safe `.env.example` is tracked. No secret values were printed.
- No application code or other branch was changed. Server deployment remains
  optional until these local checks are complete; prioritize one small existing
  authorized Linux VM and the supplied systemd template over extra infrastructure.
