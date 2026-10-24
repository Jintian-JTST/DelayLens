# Task: Frozen bus 29 browser acceptance

- Task ID: chat-bus29-acceptance
- Owner (person / AI tool): Jintian-JTST / Codex subagent
- Branch: `codex/chat-bus29-acceptance`
- Status: implementation and acceptance verified; not committed or integrated
- Integrator / reviewer: D-CodeX
- Plan / contract reference: PLAN sections 3, 6 and 9; AGENTS delivery-boundary checks

## Outcome and acceptance criteria

Verify the frozen real bus 29 data through its real model/API and the current
browser interface. This is dated offline replay, not live arrivals or calibrated
future forecasting. Exercise the 24 October 2026 UTC 16:00 recommendation,
UTC 14:30 no-advice state, risk/conservative/what-if controls and 390/320px layouts.

## Ownership and dependencies

- Owned: this record, `scripts/qa/bus29-browser.cjs`, and two explicitly authorised
  source-wording corrections plus the authorised per-departure interval/support
  explanation in `frontend/src/components/Methodology.tsx`, and the new evidence
  package `docs/evidence/bus29-browser-20261024/`.
- No API, model, schema, shared progress or lockfile changes.
- Isolated checkout based on `134dafb`; API 8017 and frontend 5183.
- Planned port 5187 is inside this Windows host's TCP reserved range 5184-5283;
  `listen EACCES` and `netsh` confirmed it. No system port settings were changed.
- Reuse locally installed dependencies; no installation or secret loading.
- API uses `SNAPSHOT_DIR=docs/evidence/bus29-db-snapshot-20261024T1655Z`.
- Disable database, TfL and Gemini configuration; permit loopback traffic only.
- Browser runner accepts `PUPPETEER_MODULE`, `CHROME_EXECUTABLE`, `QA_BASE_URL`
  and `QA_OUTPUT_DIR`; all machine-specific paths remain local environment values.

## Handoff

- Changes and relevant commits: no commit or push requested.
- Windows / PowerShell, Node 24.13.0, Python 3.11.9, installed Chrome.
- Existing `npm run build`: TypeScript and Vite production build passed.
- Existing `npm test`: all 11 tests passed.
- Browser acceptance runner: 10 grouped checks passed through the actual API/model,
  without intercepting any successful API payload or enabling labelled fixtures.
- UTC deadline `2026-10-24T16:00:00Z`: bus 29 short route, 91 curve points, 26
  source journeys, recommendation `15:25Z`, estimated probability 0.90. This is the
  current model output; the frozen data README contains older in-sample examples.
- UTC deadline `14:30Z`: `low_data`, 77 points, no recommendation and disabled
  what-if buttons. The chart has no default focus that could imply advice.
- Risk 10% -> 20% changes advice locally (`15:27Z`, 0.83); conservative and +5 min
  controls also work without additional curve requests.
- 1440/390/320px: real recommendation, source counts and frozen source label render;
  low-data state at those widths and Methodology at 1440/320px have no overflow.
- Browser exceptions, unexpected HTTP errors and external requests: zero. Expected
  `/api/live` and `/api/stats` 503 states remain explicit. `/api/calibration` returned
  actual offline preliminary evaluation, with its not-validated/inferred labels.
- Frozen basis is visible: `Offline snapshot frozen 24 Oct 16:55 UTC; not live data.`
- Corrected misleading Methodology strings to `Record TfL predictions` and
  `Capture TfL predictions over time and infer journey samples.`; verified rendered
  page also says arrival times are inferred, not measured.
- Clarified the current per-point policy: 5-14 usable trips use a 90% Wilson
  interval, 15+ use a 90% run-bootstrap interval, fewer than 5 show no probability
  or advice; recommendations require 15+ for the chosen departure. An overall
  `low_data` curve can contain 15+ points. No model, band or advisor change.
- Refreshed final browser evidence at 19:40:19.438-19:40:30.522 UTC. The new
  committed-candidate evidence package contains four screenshots, the full report,
  two actual complete API requests/responses, README and SHA256 manifest. The
  runner saves complete requests/responses and UTC capture times automatically.
- Final screenshots/report are ignored under `.local/qa/chat-bus29/`:
  `recorded-{1440,390,320}.png`, `low-data-{1440,390,320}.png`,
  `methodology-{1440,320}.png`, and `report.json`.
- Final `git diff --check` and `node --check scripts/qa/bus29-browser.cjs`: passed.
- Reviewed final desktop recommendation, mobile recommendation/low-data and
  desktop Methodology screenshots. No behavior defect was found beyond the
  two corrected source-wording issues.
- Unverified behavior or blockers: public deployment, live arrivals, Gemini,
  independent arrival measurement, physical devices and overnight services.
- Next action: D-CodeX reviews this scoped patch and integrates only when authorised.
  No commit, push, publication, recorder restart or database mutation was performed.
