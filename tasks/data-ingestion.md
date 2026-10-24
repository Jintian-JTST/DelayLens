# Task: Data ingestion and infrastructure (Code D)

- Task ID: `data-ingestion` / D
- Owner (person / AI tool): Jintian-JTST (D) / Codex
- Branches: `feat/data` (database history); `codex/data-validation-60min` (standalone validation and README)
- Documentation revision branch: `codex/revise-ingestion-plan`
- Status: standalone 60-minute chain verified; four estimated trips; real-data API adapter pending
- Integrator / reviewer: B for API/schema integration; M for usable segment evidence
- Updated: 2026-10-24 (Europe/London)
- Source: [PLAN.md](../PLAN.md), especially sections 1, 3, 4, 6 and 8
- Record structure: [task template](TEMPLATE.md)

## Outcome and acceptance criteria

### Latest checkpoint: completed 60-minute standalone validation

The owner shortened the accepted 90-minute test to 60 minutes while it was
running. Recording stopped at 14:53:10 UTC on 24 October, after **60 minutes
4 seconds**, from 13:53:05 UTC (14:53-15:53 Europe/London).

- **121/121 successful polls**, 24,465 full-line prediction rows, zero failed
  polls or missing UTC capture slots; raw JSONL and closed gzip match exactly.
- **Four independent estimated trips** over 24 inbound Warren Street -> Leicester
  Square. Three examples were traced to both endpoint sequences, source IDs,
  near-stop values and two advancing-source post-ETA absence frames. This is
  agent evidence review, not human signoff or independently measured arrivals.
- The capture window and pipeline execution pass; the original five-trip sample
  gate is only partial. Four usable trips remain `insufficient_data`; no risk
  recommendation or calibrated probability is established. The owner requested
  stopping at 60 minutes, so collection was not extended to reach a count target.
- Complete raw JSONL is durable before derivation. Record/replay/export use the
  standard library, deterministic canonical evidence, one-writer locking and
  traceable categorical quality. Repeated/rewound cached source frames are
  ignored; they neither confirm an absence nor poison otherwise timely new
  confirmation frames. The original 60/90/120-second thresholds are retained.
- First real trip: LTZ1607 / 744402, estimated 13:56:07 -> 14:12:53 UTC,
  **1006 seconds**. Early snapshot and data/source packages were created as soon
  as it completed. Subsequent trips and quality are in the committed CSV below.
- [CSV and dated quality evidence](../docs/evidence/bus24-validation-20261024/README.md)
  are available to M/B. Full raw/provenance, snapshot and SHA256-verified ZIPs
  remain in the ignored `20261024-bus24-validation` run directory and are delivered
  as local artifacts. No secrets or machine-specific paths are committed.
- Real duplicate-backup replay of a 58-poll checkpoint retained identical events
  and segment IDs/counts. A clean extracted two-trip checkpoint reproduced the
  snapshot exactly with network forbidden. Final 121-poll source/data ZIPs also
  passed CRC/SHA256 readback and clean Unicode-path extraction: all 31 tests
  passed and network-forbidden replay reproduced the snapshot exactly. The
  [verification receipt](../docs/evidence/bus24-validation-20261024/export-verification.json)
  records both final archive checksums.
- Current checks: Windows / PowerShell 7.6.5 / Python 3.11.9; **31 standalone
  regression tests**; combined latest-main backend **128 passed, 7 opt-in live-DB
  tests skipped**, one existing Starlette/httpx deprecation warning. Ruff passed.
- Integration preserves the database recorder at `database_poller` and moves its
  unchanged derivation to `database_derive`, updating internal imports/tests.
  The stricter complete-response validator remains at `backend.ingest`; raw
  formats and quality contracts must not be silently mixed. No DB credentials,
  schema, dependencies, running database recorder or production service changed.
- Reviewed the human README and accompanying AGENTS/PROJECT patch supplied from
  Claude Code. Team demo route is **bus 29**, awaiting a short ordered subsegment;
  this completed **bus 24** validation is separate evidence of pipeline viability.
  Current commands, sample support, model/API wiring and frontend state are explicit.

Run/format contract: [ingestion README](../backend/ingest/README.md).
Remaining: B's snapshot/DB adapter, M's real-data evaluation and bus 29 selection,
then the API/UI demonstration. Historical database checks and route evidence below
are preserved and are not claimed as rerun by this standalone validation.

Deliver a small, traceable set of credible inferred London bus segments to M/B
before spending time on additional infrastructure. TfL supplies predictions;
inferred stop times are not independent measurements of actual arrival.

### P0 — start collecting and prove the samples

- [ ] Start one bus line's complete TfL -> JSONL recording at 30-second cadence;
  database/account/migration setup is not a prerequisite for raw capture.
- [ ] Check five consecutive polls for stable vehicle identity and progression.
  Select one **10-20-minute segment over 4-8 consecutive stops**, one direction
  and a verified route pattern; record route/config versions and IDs.
- [ ] Assign `poll_id`/collector identity, record UTC collection time separately
  from source timestamps, and durably append complete raw results before any
  retryable database import. Detect incomplete tails and disk-write failures.
- [ ] Start Tiger Data import after raw capture works. An unavailable DB must
  leave a recoverable archive. Deduplicate source predictions as well as polls.
- [ ] Derive only plausible near-stop events: a qualifying prediction sequence,
  `timeToStation <= 60 s`, timestamps and stop order checked. The initial
  two-distinct-source-prediction heuristic needs D/M inspection of raw examples.
- [ ] Early disappearance or ambiguous identity becomes uncertain/rejected
  evidence, not a usable inferred arrival. Preserve exclusion reasons/counts.
- [ ] Store `inference_method`, categorical `confidence`, `last_seen_at`,
  `prediction_count`, inferred time and raw provenance on stop events.
- [ ] Match `line_id + vehicle_id + direction + route_pattern_id` within one
  canonical run, with increasing `stop_sequence` and plausible positive ride
  duration. A 20-minute episode gap alone is not sufficient identity evidence.
- [ ] Manually trace the first O->D samples to raw records, then deliver CSV,
  ordinary SQL/query contract, quality metadata and a **first real-data snapshot
  immediately**. M reads the CSV; B verifies DB-independent snapshot loading.

**Cut rule:** after about **90 minutes of continuous recording** without a
manually checkable O->D segment, shorten the segment or change route. Preserve raw
records and record the new route version; do not keep debugging a 30-45-minute
segment indefinitely.

### P1 — keep the proven path running

- [ ] Deploy the recorder/derivation to Vultr under `systemd` before unattended
  overnight operation. Use one active canonical derivation/DB writer; laptop
  backup records raw data only after handover.
- [ ] Verify the three essential recovery cases: unexpected process exit restarts
  collection; DB outage still saves raw data; backup replay/overlap does not
  duplicate canonical events or segments.
- [ ] Publish separate polling completeness and unique usable-journey coverage,
  initially with ordinary SQL. Add continuous aggregates/Hypercore only after
  the real-data handoff, checking the actual instance version and migration.
- [ ] Deploy B's API and F's build and verify the real UI journey with them.
  Record deployed revision; latency targets follow correctness and are measured,
  not prerequisites for first samples.
- [ ] Inspect overnight gaps and the repeated local 01:00 hour, recover available
  records, refresh the snapshot and support the final demo rehearsal.

### P2 — only after the core works

Tube contrast, longer routes, HSP sign-up/integration, full compression benchmarks,
complex fault drills and extended backup-network exercises are optional. Prepare
a simple hotspot fallback if time; these items cannot block the single-bus MVP.

## Ownership and dependencies

### Owned paths and deliverables

Application paths below are the planned ownership contract, not evidence that
these files or services have been implemented.

| Path / deliverable | Responsibility |
| --- | --- |
| `backend/ingest/poller.py` | Raw-first polling, durable recording, explicit failures and retryable import boundary |
| `backend/ingest/derive.py` | Canonical episodes, inference quality, ordered matching, replay and traceability |
| `backend/sql/001_schema.sql` | P0 raw/prediction/event/segment storage, provenance and unique keys; later version-tested optimisation |
| `backend/config/routes.json` | One verified London bus pattern, stop order/endpoints and route version |
| `deploy/` | VM/service/deployment and essential recovery instructions |
| `tasks/data-ingestion.md` | D's decisions, real checks and handoffs |
| CSV / snapshot / query handoff | Real canonical segments, provenance and quality/coverage manifest; location agreed with B/M |

B owns `backend/app/db.py`, API schemas/endpoints, `.env.example`, dependency
manifests and lockfiles. M owns model thresholds/implementation; F owns UI labels.
D requests changes there instead of editing another role's application files.
The owner explicitly requested this shared documentation revision; B maintains
project summaries/contracts after integration.

### Minimum segment interface

The following is a **format example, not a collected sample**:

```json
{
  "segment_id": "stable-unique-id",
  "route_id": "bus-example-A-B",
  "vehicle_id": "vehicle-123",
  "origin_at": "2026-10-24T17:10:00Z",
  "destination_at": "2026-10-24T17:24:30Z",
  "travel_seconds": 870,
  "inference_method": "near_stop_prediction",
  "quality": "estimated",
  "source": "tfl_live_recording"
}
```

Keep the CSV's minimum fields identical. Full records additionally carry route
version/pattern, line/direction, canonical run ID, endpoint event IDs, categorical
confidence and a lookup from `segment_id` to raw predictions. `origin_at` and
`destination_at` remain inferred UTC timestamps; never call them `actualArrival`.
Only deduplicated estimated segments passing the agreed endpoint checks go to M.

### Decisions and handoffs to B/M

| Interface | Agreement needed before use |
| --- | --- |
| Route configuration | Verified IDs, direction/pattern, stop sequence, route version and duration bounds |
| Event/segment identity | Stable canonical episode/endpoint-based keys and `ON CONFLICT`; `poll_id` alone does not deduplicate independent collectors |
| Backup recovery | Merge/deduplicate source evidence through one derivation writer; prove the same unique segment counts on overlapping replay |
| M's model support | Count distinct usable run segments, not rows/replay minutes. 0-4: insufficient; 5-14: preliminary; 15+: empirical estimate, not automatically calibrated. M owns implementation and further policy changes. |
| B's API | Retain `ok` / `low_data` / `insufficient_data` names where possible; B updates nullable recommendation/interval behaviour and fixtures before contract freeze |
| B's queries | Supply `get_segments`, ordinary coverage and stats SQL against the agreed schema; B implements the database adapter/cache |
| Coverage | Separate expected/successful polls/gaps from usable segments, distinct vehicles and exclusions |
| Snapshot | First handoff includes real segments, capture/reference times, route version, quality and provenance; B loads without Tiger Data and labels snapshot mode |
| Demo time | M/F pick a genuinely recorded period early; any Saturday-to-Sunday transfer is explicit and unvalidated |

Use UTC storage plus Europe/London local date, weekday and offset/fold for
features. Keep the two local 01:00 hours distinct; do not silently pool Saturday
and Sunday or shift recordings to a fictional date.

### Configuration and prerequisites

Use `TFL_APP_KEY`, `DATABASE_URL`, `POLL_LINE_IDS`, `POLL_STOP_IDS`,
`POLL_INTERVAL_SECONDS` (30) and `RAW_BACKUP_DIR` (planned `.local/raw`). B owns
safe `.env.example` values. Secrets and personal paths stay local. Python >=3.11
with uv is planned; systemd is Linux-specific. Record exact install/run/service
commands when the code exists and the commands have been exercised.

## Milestones and handoff order

Times are **targets**, in Europe/London; no unchecked row claims completion.
Start immediately if the original Saturday timetable has slipped.

| Gate | Exit condition / recipient |
| --- | --- |
| G0 immediately; original Sat 15:00 target | Continuous durable real polls without waiting for DB; route identity checked |
| First 90 minutes of capture | Manually inspect credible O->D samples; otherwise shorten/change route |
| First usable samples (G2) | CSV -> M; query/schema/quality contract and snapshot -> B; snapshot mode tested immediately |
| Sat 17:00 contract gate | B reconciles quality/nullable states with M/F; identity rules explicit |
| Sat 18:30 handoff | Real samples, ordinary coverage SQL and refreshed snapshot consumable by M/B |
| Sat 19:30 core gate | Real data -> model -> API -> UI; cut optional work if absent |
| Evening, target Sat 21:30 | Supervised VM; one active writer; three essential recovery checks |
| Sat 23:45 overnight gate | Restart, disk/raw backup and snapshot checked before team absence |
| Sun 07:00-08:30 | Gaps/clock-change QA/recovery; snapshot refreshed, not first created |
| Sun 09:30 freeze | Covered demo reference locked; performance measurement/redeploy support |
| Sun 10:00 / 10:30 | Data/infra notes -> M; final infra/rehearsal support |

B integrates D -> M -> B -> F. After freeze, bug fixes only; after submission,
B approves demo-breaking redeploys. D explains the evidence/inference pipeline.

## Verification plan

- Inspect real polling durability/source freshness and route identity.
- Check disappearance, stale/jumping predictions, branch mismatch, reused IDs,
  insufficient evidence, incomplete trips and the repeated local hour.
- Trace accepted/excluded examples to raw records; verify count units.
- Exercise restart, DB-down raw saving and idempotent overlapping replay.
- M reads CSV; B reads the same snapshot/query results. Verify real UI behaviour
  and DB-independent snapshot mode, rather than inferring success from a build.
- For this documentation revision: UTF-8/LF, exact-case local links, canonical
  paths/template, JSON examples, scope invariants and Git whitespace.

## Handoff

- Changes: short-bus/raw-first P0, 90-minute cut, conservative inference,
  provenance/identity contract, early snapshot and deferred extras; shared
  plan/project/progress/instructions reconciled in the same revision.
- Checks actually run: Windows / PowerShell 7.6.5 / Python 3.11.9; remote fetched
  and clean branch fast-forwarded to main `e09ab18`. One-off Python documentation
  validation passed: eight final files checked for UTF-8/LF, whitespace and
  personal paths; 39 exact-case local links across 11 Markdown files; canonical
  template, PLAN sections, scope invariants and matching segment JSON checked.
  The example's timestamps correctly differ by 870 seconds. `git diff --check`
  and the new-template whitespace check passed. No application checks ran.
- Unverified: no live collection, selected route, DB migration, inferred sample,
  recovery check, model integration or deployment verified by this revision.
  Planned app checks are not passed tests.
- Concurrent handoff: remote `feat/data` commit `ee055d6` adds bus 29/Victoria
  configuration and reports route/status checks in a legacy task record. Keep
  that evidence on integration; short-route/five-poll suitability still needs
  checking against this revision. Victoria is P2. B/D consolidate the record
  under this canonical path; this docs branch does not overwrite their code.
- Next action: B reviews/integrates plan and contract changes; D begins G0 raw
  capture/route evidence, then delivers the first inspectable segments.

## Imported feat/data evidence (historical handoff)

The following branch record is retained verbatim except for the recorder module
name and template link. Its live checks were reported by D, not rerun during branch integration.
The revised P0 requirements above still apply; SQL estimates are not approved model inputs.

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
python -m ingest.database_poller
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
