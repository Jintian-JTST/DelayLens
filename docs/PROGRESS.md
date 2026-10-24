# DelayLens — Progress and Handoff

Updated: 2026-10-24, Europe/London. Prepared against main `134dafb` (PR #38).
Local checks below describe isolated task checkouts; they do not establish
remote CI, public deployment or overnight availability.

## Current evidence

| Gate | Verified state and limits |
| --- | --- |
| Frozen bus 29 | Original16:55 UTC snapshot retained (26 short/18 long). Separate20:25:58 UTC handoff snapshot:56 short/48 long inferred segments,8/6 recorded hours,791 poll times. These are database-pipeline counts, not measured arrivals or pooled standalone samples. |
| Independent bus 29 | Earlier90-minute run:7 journeys with separate three-example source review. New180-minute run completed:5 journeys/251 events, low_data, source-trace acceptance pending. The15-run target is explicitly unmet; three usable UTC hours are present. |
| Offline data/model/API/UI | Actual frozen data through API and Chrome: UTC 16:00 deadline, walks 5/5, 91 points, recommendation 15:25 UTC with estimated probability 0.90. UTC 14:30: 77 points and no qualifying advice. No synthetic successful API payload was substituted. |
| Presentation | Desktop and 390/320px states, risk/conservative/what-if controls and methodology checked. Frozen date/source labels remain visible. Physical devices remain unverified. |
| CI | Offline backend tests/Ruff and frontend tests/build passed locally and in GitHub PR/main runs. Main b8d6f0a (PR #47, after default-route 459ac72) has [successful push CI](https://github.com/Jintian-JTST/OxHack/actions/runs/40131596242); frontend now has 16 tests. Inspect actual checks for subsequent heads. |
| Current capture | The180-minute standalone recorder normally finished20:21:55 UTC; final packages appeared20:23:09 and its process exited. Database/area recorders were left untouched. No overnight continuity claim is made. |

## Delivery records

- [D delivery checklist](../tasks/chat-d-delivery.md): ownership, integration and remaining gates.
- [Bus 29 source review](../tasks/chat-data-source-review.md): 179 raw polls reproduce all 7 published segments and 162 events; three examples traced to complete raw frames. Agent review is not human signoff.
- [Bus 29 browser acceptance](../tasks/chat-bus29-acceptance.md): actual offline API/browser evidence and corrected prediction/inference wording. The frozen README's older model examples are historical.
- [CI handoff](../tasks/chat-ci-handoff.md): backend **196 passed**, 28 explicitly live tests deselected; frontend **11 passed**, type-check/build and Ruff passed. The existing Starlette/httpx deprecation warning remains.
- [Final capture/data handoff](../tasks/chat-final-capture.md):354 raw polls,5 standalone journeys, full replay and four ZIP manifests/CRCs verified; final model loader uses all5 rows. Separate refreshed database snapshot is ready for M3.
- [Network-backed browser evidence](evidence/bus29-network-browser-20261024/README.md): actual database/API/UI, screenshots, full requests/responses and curl comparison; PR44 is merged. This remains historical replay, not live arrivals.

Historical implementation and external-service results remain in
[D](../tasks/data-ingestion.md), [B](../tasks/backend-api.md),
[M](../tasks/model.md), [F](../tasks/frontend-demo.md) and
[the earlier integration record](../tasks/branch-integration.md).
They are dated reports, not newly rerun external checks.

## Remaining gates and owners

| Gate | Next action / owner |
| --- | --- |
| 180-minute export | Final archives and SHA256 are verified in the new dated handoff. Standalone5<15 remains below target; separate database56/48 counts must not replace it. |
| Refreshed model/backtest | **Done (T10/M3, reviewer-checked, chat #280).** Final snapshot `bus29-db-final-20261024T202558Z`: Mornington Brier 0.1296 (1104 outcomes, 49 runs), Finsbury Park 0.1318; Sat 17:00 → 16:22, p=0.9174. Standalone 5 runs give no advice. Preliminary: one Saturday, scored against inferred events. See [tasks/model.md](../tasks/model.md). |
| Network-backed demo / recovery | Network UI evidence is on main (PR44); B's local recovery checklist is recorded separately. Physical disconnection and overnight survival are not implied. |
| Backend input hardening | **Done (T25/T28).** 44 bad requests found 3 HTTP 500 (naive deadline, `1e400`, deeply nested JSON); fixed in #57 (merged `5cfe07b`) with regression tests; pytest 199 passed / 28 skipped, no 5xx on snapshot or live DB. Valid Ask not tested. Details: [B](../tasks/backend-api.md). |
| Remote CI / integration | PR39/44 and their main CI were observed successful; integrator checks the current head and reviews final data handoff changes. |
| Unattended collection / deployment | D supplies timestamped polls over the claimed interval and verifies restart/recovery on the actual host. No overnight or VM success is claimed. |
| Submission / media | M/F confirm rules, final dated scenario, video and submission; this delivery does not publish the app. |

No sample threshold proves calibration. Database and standalone pipelines have
different inference/provenance contracts; their run counts are not pooled.
