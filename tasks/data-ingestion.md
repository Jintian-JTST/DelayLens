# Task: Data ingestion and infrastructure (Code D)

- Task ID: `data-ingestion` / D
- Owner (person / AI tool): Jintian-JTST (D) / Codex
- Branch: `feat/data`
- Documentation revision branch: `codex/revise-ingestion-plan`
- Status: claimed; plan revised after review; implementation not verified
- Integrator / reviewer: B for API/schema integration; M for usable segment evidence
- Updated: 2026-10-24 (Europe/London)
- Source: [PLAN.md](../PLAN.md), especially sections 1, 3, 4, 6 and 8
- Record structure: [task template](TEMPLATE.md)

## Outcome and acceptance criteria

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
