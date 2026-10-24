# DelayLens — Project Brief

Updated: 2026-10-24 (Europe/London). Product and intended stack are selected in
[PLAN.md](../PLAN.md). This brief records decisions; implementation and actual
verification belong in [PROGRESS.md](PROGRESS.md) and the role task records.

## Product and scope

| Item | Decision |
| --- | --- |
| Name | DelayLens |
| Users/problem | Travellers choosing when to leave when journey time is uncertain |
| Data geography | London TfL bus predictions; Oxford BODS is outside this MVP |
| First route | One verified 10-20-minute bus segment over 4-8 consecutive stops; D selects exact IDs from live evidence |
| Core journey | Supported route/time + deadline/walks -> empirical distribution/evidence -> eligible departure choices/what-if; separate live predictions |
| P0 | Raw-first collection, traceable inference, CSV/query/snapshot handoff, form/API/model/UI and honest sample-support states |
| P1 | Supervised overnight VM, public demo, essential recovery; then Gemini, coverage UI and Tiger Data optimisation |
| P2 | Tube, HSP, longer routes, full benchmarks and complex drills |
| Out of scope | Arbitrary A-to-B, multi-leg journeys, accounts and unqualified calibrated-probability claims |

Success requires a real-data journey with usable evidence and visible limitations.
Targets: form result under two seconds, model <50 ms and API p95 <300 ms after
correctness. These are not current measurements. Fewer than five usable runs
support only samples/insufficient output; that does not meet the probability goal.

## Data and evidence contract

- Durable 30-second TfL -> JSONL collection precedes database setup/writes.
- Select the route after five consecutive polls demonstrate usable identity/order.
  After 90 minutes of capture without an inspectable segment, shorten/change it.
- Stop events are inferred from plausible near-stop sequences. Early disappearance
  stays uncertain. Store method, categorical confidence, last-seen time,
  prediction count and raw provenance; never call forecasts measured arrivals.
- Match line, vehicle, direction, pattern and ordered stops within one run.
  Stable identities, one canonical writer and overlap/replay checks prevent
  duplicate samples. Count canonical usable run segments, not minute steps.
- 0-4 usable runs: `insufficient_data`; 5-14: `low_data` / Preliminary estimate,
  no risk-based recommendation; 15+: empirical estimate, with justified sampling
  uncertainty. No count threshold establishes calibration.
- Store UTC and retain Europe/London date/weekday/offset/fold. Disclose reference
  hours/cross-day assumptions; distinguish the two local 01:00 hours.
- Export the first snapshot at the first usable-segment handoff and refresh
  before freeze. B owns loading; F labels snapshot/availability states.

PLAN sections 3/6 define the minimum segment and pending API reconciliation.
B owns schemas/fixtures; M owns model implementation. Intended behaviour is not
a claim that application schemas already implement this revision.

Concurrent D commit `ee055d6` provides bus 29/Victoria candidates and records
route/status checks. B/D retain that work while selecting a short bus subsegment
and verifying five consecutive polls; Victoria remains optional P2.

## Technology and architecture

| Area | Selected direction / owner |
| --- | --- |
| Frontend | React, Vite, TypeScript; Node >=20/npm; F |
| Backend | Python >=3.11, FastAPI, NumPy; uv; B manifests/lockfile, M model |
| Ingestion | TfL poller, recoverable JSONL/gzip, retryable importer, canonical derivation; D |
| Storage | Tiger Data/PostgreSQL raw predictions, inferred events and segments; ordinary coverage SQL first; D |
| Later optimisation | Version-tested hypertables, continuous aggregates and Hypercore/columnstore after core handoff |
| Optional language input | Gemini API, server-side key; B/F |
| Hosting | Vultr Linux VM/systemd for overnight collection; D with B/F |
| Fallback | Real-data snapshot through B's API without Tiger Data |
| Interfaces | B publishes nullable evidence states and route/segment fixtures before freeze |

## Reproducible setup status

Application source, manifests and lockfiles are absent from the inspected main
baseline `e09ab18`. Do not present proposed app commands as tested setup. B/F add
actual install/run/test/build commands when code lands.

| Item | Shared contract / remaining action |
| --- | --- |
| Versions | Python >=3.11; Node >=20; exact supported/package-manager versions pinned by B/F when code lands |
| Package managers | uv backend; npm frontend; commit generated lockfiles |
| Services | TfL access; Tiger Data after capture begins; Vultr overnight; Gemini optional |
| Local ports | API 8000; frontend 5173; isolate concurrent instance ports/data roots |
| Config names | TFL_APP_KEY, DATABASE_URL, GEMINI_API_KEY, POLL_LINE_IDS, POLL_STOP_IDS, POLL_INTERVAL_SECONDS, RAW_BACKUP_DIR, FRONTEND_ORIGIN |
| Environment examples | B owns `.env.example`; no real credentials in shared files |
| Platforms | Portable Windows/macOS/Linux local paths; systemd deployment Linux-only |
| Verified here | Documentation/Git only; no application setup, service call or deployment verified |

Use repository-relative paths and each teammate's local credentials. Follow
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Event constraints and demo

The initial PLAN records opening-slide/schedule notes: hacking Sat 24 October
12:00 to Sun 25 October 12:00; judging 13:00-15:45; teams <=4; HRT/Tiger
Data/Delta/Gemini/Vultr tracks and judging weights. This revision does not
independently reverify those notes. M confirms exact Devpost fields/cut-off,
prize combinations, pre-existing-code/AI-use rules and attribution.

M/F select a supported recorded scenario early. Prefer explicitly dated replay;
a Saturday-to-Sunday forecast is an unvalidated transfer assumption. Fallback:
refreshed real snapshot, then video. B verifies the public form/API; F verifies
phone/keyboard/evidence states.

## Team and ownership

| Code | Owner / scope | Task record |
| --- | --- | --- |
| D | Jintian-JTST; collection, inference, schema/routes, snapshot and infra | [data-ingestion](../tasks/data-ingestion.md) |
| M | Person not recorded; model, evaluation, README/submission | `tasks/model.md` — owner to create |
| B | Person not recorded; backend/Gemini/contracts, integration/shared docs | `tasks/backend-api.md` — owner to create |
| F | Person not recorded; frontend, pitch, screenshots/video | `tasks/frontend-demo.md` — owner to create |

Use [tasks/TEMPLATE.md](../tasks/TEMPLATE.md). Defining roles does not establish
that unnamed people have accepted them or completed work. Integrate D -> M -> B
-> F; B approves contract changes after freeze.

## Decision log

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-10-23 | Canonical AGENTS.md and thin client entry points | One portable rule set; preserve original README/MIT licence |
| 2026-10-24 | DelayLens/London TfL and the stack above | Initial PLAN direction replaces preparation-stage TBDs |
| 2026-10-24 | Raw-first short route, conservative inference, 90-minute cut, early snapshot | Owner accepted review; usable samples are the critical dependency |
| 2026-10-24 | Tiered support, unvalidated calibration by default | Expose what independent-run evidence can support |
| 2026-10-24 | Canonical task records/template under tasks/ | Match existing role paths; B integrates shared contract changes |
