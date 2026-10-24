# DelayLens — Progress and Handoff

Updated: 2026-10-24 (Europe/London).

## Current milestone

Product and intended stack are selected in [PLAN.md](../PLAN.md) and
[PROJECT.md](PROJECT.md). Next is **G0: durable real TfL recording**, then manually
traceable short-bus segments and the first CSV/snapshot handoff. A written plan
is not a running recorder.

## Verified repository state

- Shared AI instructions, onboarding and initial project documents exist.
- Initial implementation PLAN: `73006fa`.
- D task: `2ae4394`, merged to main in PR #1 at `e09ab18`.
- This revision rewrites PLAN/D task after the owner-supplied review, synchronises
  product/ownership summaries and standardises `tasks/` paths.
- Main baseline `e09ab18` has no application source, manifests or lockfiles.
  Other-branch work is not assumed complete/integrated/tested from its branch
  name or commit title.
- Concurrent remote `feat/data` commit `ee055d6` adds bus 29/Victoria route
  configuration and a legacy D record reporting live route/status checks. That
  evidence was inspected, not rerun. The revised short-route/five-poll gate,
  sustained recording and credible segments are still unverified here.

## Verification for this revision

- Remote fetched; clean `feat/data` fast-forwarded to `e09ab18`.
- After detecting concurrent D development, this documentation revision moved to
  `codex/revise-ingestion-plan`; the remote implementation branch is preserved.
- Official TfL feed/API and Tiger Data aggregate/Hypercore references consulted;
  source links and scope are in PLAN section 10.
- Shared-review page retrieval failed; the complete pasted review was used.
- Passed: one-off Python validation of eight final files for UTF-8/LF,
  whitespace/personal paths; 39 exact-case links across 11 Markdown files;
  canonical template, PLAN sections, scope invariants and matching valid JSON
  examples with the correct 870-second duration.
- Passed: `git diff --check` and a whitespace check of the new task template.
- No live TfL call, recorder, migration, inferred segment, recovery check,
  application test, build or deployment verified by this revision.

Historical scaffold checks (including Windows clone/line-ending checks) were
recorded before this rewrite; they are not current application verification.

## Gates and next actions

| Gate | Owner | Exit check | Current evidence |
| --- | --- | --- | --- |
| G0 raw capture | D | Durable consecutive polls independent of DB; short route verified | Not verified |
| G1 credible segment | D/M | Raw-linked O->D; shorten/change route after 90 minutes without one | Not verified |
| G2 first handoff | D -> M/B | Readable CSV/query/quality contract; first snapshot works without DB | Not verified |
| Contract reconciliation | B with M/F | Revised tiers/nullability/evidence fields in schemas/fixtures | Pending implementation |
| Core real-data journey | All, B integrates | Data -> model -> API -> UI, honest labels/counts | Not verified |
| Overnight readiness | D | One supervised writer; restart, DB-down raw saving and replay checks | Not verified |
| Submission/demo | M/F with B/D | Covered reference scenario, snapshot/video and actual submission confirmation | Not verified |

If original Saturday targets have passed, start G0 immediately. Preserve Sunday's
fixed deadline; use elapsed capture time for the 90-minute route cut. Tube, HSP,
full benchmarks and complex drills are P2.

## Active handoffs

Task records and [the template](../tasks/TEMPLATE.md) are canonical under `tasks/`.
M/B/F names are not recorded here; role definitions do not prove acceptance.

| Role / task | Owner | Status | Next action |
| --- | --- | --- | --- |
| [D: data-ingestion](../tasks/data-ingestion.md) | Jintian-JTST / Codex | Claimed; review-driven plan revision | Start G0; deliver real sample evidence/CSV/snapshot |
| M: `tasks/model.md` | Person not recorded | Role defined; task file absent in inspected main | Create record; reconcile tiers and independent-run resampling |
| B: `tasks/backend-api.md` | Person not recorded | Role defined; task file absent in inspected main | Integrate docs; publish revised contract/fixtures |
| F: `tasks/frontend-demo.md` | Person not recorded | Role defined; task file absent in inspected main | Create record; implement quality states and pick covered demo time with M |

B owns later shared summaries and D -> M -> B -> F integration. This requested
documentation change does not claim teammates' app files were edited or external
messages sent.

B/D consolidate the concurrent legacy task record into `tasks/data-ingestion.md`
on integration, preserving its route-check evidence and reconciling the new P0.
