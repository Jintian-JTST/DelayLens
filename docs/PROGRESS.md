# DelayLens — Progress and Handoff

Updated: 2026-10-25, Europe/London. Current integration: main `e31bf98` (PR #67),
after the independently reviewed frontend PR #66. Older delivery records below
retain their original test counts and dates. Local tests and recorded-data
browser checks do not establish public deployment or overnight availability.

## Current evidence

| Gate | Verified state and limits |
| --- | --- |
| Frozen bus 29 | Original16:55 UTC snapshot retained (26 short/18 long). Separate20:25:58 UTC handoff snapshot:56 short/48 long inferred segments,8/6 recorded hours,791 poll times. These are database-pipeline counts, not measured arrivals or pooled standalone samples. |
| Morning candidate (not stage default) | PR70 adds the separate 06:07Z snapshot:80 short/70 long database segments. London dates are74 Saturday+6 Sunday short,67 Saturday+3 Sunday long. Manager verified all8 manifest entries and reproduced identical91 Saturday17:00 curve points, including bands. New Brier values0.1276/0.1168 remain preliminary. [Comparison evidence](evidence/bus29-morning-comparison-20261025/README.md); locked20:25Z stage data is unchanged. |
| Independent bus 29 | Earlier90-minute run:7 journeys with separate three-example source review. New180-minute run completed:5 journeys/251 events, low_data, source-trace acceptance pending. The15-run target is explicitly unmet; three usable UTC hours are present. |
| Overnight standalone | PR74 accepted after raw replay: 685 polls, 4 inferred trips, 88 events; all 14 manifest entries and both archive digests/internal manifests pass. Model loads 4/4 rows, no recommendation. Separate from the older 5-trip run and database; target below 15 remains unmet. [Independent comparison](evidence/bus29-morning-comparison-20261025/README.md#independent-overnight-handoff-accepted). |
| Offline data/model/API/UI | Locked 20:25Z snapshot, bus 29 Mornington Crescent, Sat 24 Oct 17:00 London, walks 5/5: leave 16:22, p=0.9174, 56 recorded trips. API and T10 rerun independently reproduce this; Sat 15:30 gives no qualifying advice. This remains historical replay of inferred arrivals. |
| Presentation | Desktop Chrome rendering and Ask/voice cancellation interactions checked for PR #66 with recorded snapshot responses and local health/Ask/SpeechRecognition stubs. Frozen date/source labels remain visible. Real microphone, speech service, Gemini calls, screen readers and physical offline rehearsal remain unverified. Desktop only is the agreed scope. |
| CI | Backend: 247 offline tests passed, 28 live tests deselected; Ruff passed. Frontend: 47 tests and production build passed. Main e31bf98 has [successful push CI](https://github.com/Jintian-JTST/OxHack/actions/runs/40150320031). Check subsequent heads independently; the existing Starlette/httpx deprecation warning remains. |
| Current capture | The frozen 180-minute standalone run finished at 20:21:55 UTC on 24 Oct; its final packages appeared at 20:23:09. Overnight collection has newer agent-reported poll counts, but no new overnight export/source-trace acceptance is established here. No overnight continuity claim is made. |

## Delivery records

- [D delivery checklist](../tasks/chat-d-delivery.md): ownership, integration and remaining gates.
- [Bus 29 source review](../tasks/chat-data-source-review.md): 179 raw polls reproduce all 7 published segments and 162 events; three examples traced to complete raw frames. Agent review is not human signoff.
- [Bus 29 browser acceptance](../tasks/chat-bus29-acceptance.md): actual offline API/browser evidence and corrected prediction/inference wording. The frozen README's older model examples are historical.
- Historical [CI handoff](../tasks/chat-ci-handoff.md): backend **196 passed**, 28 explicitly live tests deselected; frontend **11 passed**, type-check/build and Ruff passed. Current counts are in the CI row above.
- [Final capture/data handoff](../tasks/chat-final-capture.md):354 raw polls,5 standalone journeys, full replay and four ZIP manifests/CRCs verified; final model loader uses all5 rows. Separate refreshed database snapshot is ready for M3.
- [Network-backed browser evidence](evidence/bus29-network-browser-20261024/README.md): actual database/API/UI, screenshots, full requests/responses and curl comparison; PR44 is merged. This remains historical replay, not live arrivals.
- [PR #66](https://github.com/Jintian-JTST/OxHack/pull/66): Ask uses the explicit health flag; optional route stops, voice input and the bus 29 schematic are integrated. The reviewer reproduced and then verified the fix for duplicate Ask requests on voice cancellation: one text submission sends one POST; abort/error/unmount send no additional POSTs. The map says "At stop", not an unsupported boarding-time estimate. Real voice/Gemini calls were not tested.
- [Repeated-hour reporting](../tasks/manager-dst-hour-report.md), [PR #67](https://github.com/Jintian-JTST/OxHack/pull/67): T10 hourly counts include full date, BST/GMT and UTC offset, keeping the two London 01:00 hours separate. Model probabilities and the locked snapshot are unchanged.

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
| Remote CI / integration | PR66/67 and main e31bf98 CI were independently observed successful. The integrator reviews subsequent heads and the new overnight handoff before accepting them. |
| Frontend handoff | T36 is accepted through PR66; F owns subsequent frontend/UI changes. Preserve the recorded-data labels and keyboard interaction. Real microphone/Gemini verification remains a separate gate, not implied by mocked browser tests. |
| Unattended collection / deployment | D supplies timestamped polls over the claimed interval and verifies restart/recovery on the actual host. No overnight or VM success is claimed. |
| Submission / media | M/F confirm rules, final dated scenario, video and submission; this delivery does not publish the app. |

No sample threshold proves calibration. Database and standalone pipelines have
different inference/provenance contracts; their run counts are not pooled.

Clean demo API check (T47/T45 takeover): [local HTTP evidence](evidence/demo-api-smoke-20261025/README.md) on clean main1df3f4b, locked20:25Z, keys/DBempty reproduces16:22/p0.9174. Warm20-request loopback p95 is4.3087ms total/3.54ms server; no public-network, physical-rehearsal or live-microphone/Gemini claim. [Task record](../tasks/manager-clean-demo-api-smoke.md).

Captioned backup recording (T48): [93-second silent actual-UI video](evidence/backup-demo-20261025/README.md) preserves the locked16:22/p0.9174 result and15:30no-advice case, with inferred/preliminary/offline captions. Repository backup only; formal video URL/Delta/eligibility remain unconfirmed. [Task record](../tasks/manager-backup-demo-video.md).

Submission handoff after M offline (T49): [ready-to-copy packet](submission-handoff.md), story, actual video/screenshot and source evidence available. Authenticated submitter, accepted video-host URL, actual Delta links, track selections/eligibility and submission receipt remain unconfirmed. The manager owns repository preparation; no submitted/eligible claim. [Task record](../tasks/manager-submission-takeover.md).
