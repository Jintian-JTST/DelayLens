# DelayLens — Progress and Handoff

Updated: 2026-10-24, Europe/London. Prepared against main `134dafb` (PR #38).
Local checks below describe isolated task checkouts; they do not establish
remote CI, public deployment or overnight availability.

## Current evidence

| Gate | Verified state and limits |
| --- | --- |
| Frozen bus 29 | Unchanged 16:55 UTC database snapshot: 26 short-route / 18 long-route inferred segments, origin events and 373 poll times. Arrivals are not measured. |
| Independent bus 29 | Completed 90-minute run: 7 independent inferred journeys and 162 events. A separate three-example agent source review preserves the original handoff. Support remains low_data. |
| Offline data/model/API/UI | Actual frozen data through API and Chrome: UTC 16:00 deadline, walks 5/5, 91 points, recommendation 15:25 UTC with estimated probability 0.90. UTC 14:30: 77 points and no qualifying advice. No synthetic successful API payload was substituted. |
| Presentation | Desktop and 390/320px states, risk/conservative/what-if controls and methodology checked. Frozen date/source labels remain visible. Physical devices remain unverified. |
| CI | PR/push workflow added for offline backend tests/Ruff and frontend tests/type-check/build. Local equivalents passed; a green GitHub run and green main still require observation. |
| Current capture | Read-only inspection at 19:26 UTC found a database poll about 10 seconds old, the active 180-minute standalone run and a separate area recorder. Existing processes were untouched. This proves freshness then, not overnight continuity. |

## Delivery records

- [D delivery checklist](../tasks/chat-d-delivery.md): ownership, integration and remaining gates.
- [Bus 29 source review](../tasks/chat-data-source-review.md): 179 raw polls reproduce all 7 published segments and 162 events; three examples traced to complete raw frames. Agent review is not human signoff.
- [Bus 29 browser acceptance](../tasks/chat-bus29-acceptance.md): actual offline API/browser evidence and corrected prediction/inference wording. The frozen README's older model examples are historical.
- [CI handoff](../tasks/chat-ci-handoff.md): backend **196 passed**, 28 explicitly live tests deselected; frontend **11 passed**, type-check/build and Ruff passed. The existing Starlette/httpx deprecation warning remains.

Historical implementation and external-service results remain in
[D](../tasks/data-ingestion.md), [B](../tasks/backend-api.md),
[M](../tasks/model.md), [F](../tasks/frontend-demo.md) and
[the earlier integration record](../tasks/branch-integration.md).
They are dated reports, not newly rerun external checks.

## Remaining gates and owners

| Gate | Next action / owner |
| --- | --- |
| 180-minute export | D waits for the existing run to finish, exports to a new dated location, verifies SHA256/replay and reports actual route/time support. No target count is assumed achieved. |
| Refreshed model/backtest | M reruns against the new handoff; inferred outcomes are not independent measured arrivals. |
| Network-backed demo / recovery | B records live-database browser/API evidence and local smoke checks separately from the frozen-data evidence. |
| Remote CI / integration | Integrator reviews this proposal and observes actual GitHub checks before claiming main is green. |
| Unattended collection / deployment | D supplies timestamped polls over the claimed interval and verifies restart/recovery on the actual host. No overnight or VM success is claimed. |
| Submission / media | M/F confirm rules, final dated scenario, video and submission; this delivery does not publish the app. |

No sample threshold proves calibration. Database and standalone pipelines have
different inference/provenance contracts; their run counts are not pooled.
