# DelayLens — Progress and Handoff

Updated: 2026-10-24 (Europe/London).

## Current milestone

The standalone bus 24 data chain has completed a real 60-minute validation:
capture -> conservative inference -> CSV/snapshot -> independent offline replay.
There are four usable estimated trips, so probability output remains insufficient.
The next product gate is B's real-data adapter; the API/UI demo is not yet proven.

## 60-minute validation and README checkpoint

- The owner shortened the running 90-minute recording to 60 minutes. Capture
  13:53:05-14:53:10 UTC / 14:53-15:53 BST on 24 October: 121 successful polls,
  24,465 prediction rows, zero failed polls or missing capture slots, four complete
  independent estimated trips. Three examples were source-traced by the agent;
  no human signoff or independent actual-arrival measurement is claimed.
- CSV, snapshot, event provenance, quality report and separate SHA256-verified
  data/source ZIPs were generated. [Evidence and CSV](evidence/bus24-validation-20261024/README.md)
  are committed for M/B; complete raw/local archives remain outside Git.
- Added the dependency-free record/replay/export CLI, durable raw-first handling,
  canonical replay, inference quality, one-writer locking and portable exports.
  The database pipeline is preserved separately as `database_poller` /
  `database_derive`; their archive/quality contracts are not interchangeable.
- Reviewed the README and documentation patch supplied from Claude Code. Retained
  bus 29 as the team demo route, labelled bus 24 as the completed validation,
  corrected commands/current status and moved AI-entry references into AGENTS.md.
- Checks: 31 standalone regression tests; combined backend **128 passed, 7
  explicitly opt-in database tests skipped**; Ruff passed. The existing
  Starlette/httpx deprecation warning remains. Final source/data archive readback
  and clean offline reproduction are recorded in the D task handoff.

The historical branch-integration checks below describe their own earlier
revision. PRs #5/#6/#7 are already in the inspected main baseline `a42fb30`.

## Repository integration

- Main baseline `4da089c` already contains PRs #1/#2, the revised PLAN and the
  complete-response bus 24 raw recorder. Preserve that recorder and short routes.
- `feat/api` at `ab9012c` includes `feat/data` at `82ae093`; import that history
  once, retain the corrected bus 29 origin and all four configured routes.
- `feat/model` at `f12e4de` contributes NumPy replay and its synthetic tests.
  Add its requested NumPy dependency and update the existing uv lockfile.
- Keep the imported database pipeline at `ingest.database_poller`, updating its
  imports and service template. It uses a different archive from main's raw
  recorder. No interchange/replay bridge is implemented.
- Consolidate D/B records under `tasks/`, preserving D's historical live evidence
  and distinguishing it from checks actually rerun for this integration.
- Source branches and existing checkouts remain intact. Full inventory and
  conflict decisions: [branch integration](../tasks/branch-integration.md).

## Verification for this integration

Windows / PowerShell 7.6.5 / Python 3.11.9; isolated uv environment and lockfile.

- `uv sync --project backend --locked --group dev`: passed.
- From `backend/`, `python -m pytest -q --strict-markers`: **93 passed, 7 skipped**.
  All seven skips are explicitly opt-in real-database tests; no credentials used.
  One existing Starlette/httpx deprecation warning remains.
- Ruff over `backend/app`, `backend/tests`, `backend/ingest`, `deploy`: passed.
- Added regression coverage for merged route/poll defaults, complete raw saving
  without a database, both recorder imports and actual-config API responses with
  no synthetic probabilities.
- UTF-8/JSON/conflict-marker/path/whitespace and 45 exact-case local Markdown
  links passed across 54 versioned/new files. Git whitespace checks passed.
- First restricted test invocation stalled; stopped only that integration test
  process and reran with normal process access and a 55-second bound. The complete
  suite passed in 2.32 seconds. This is not a live integration/service check.

## Remaining product gates

| Gate | Status / next action |
| --- | --- |
| Raw collection | Main recorder preserved; no live collection started or restarted in this task |
| Credible bus segments / snapshot | D's historical evidence retained; revised canonical identity/quality/provenance still needs reconciliation |
| Model evidence policy | M implements 0-4 / 5-14 / 15+ handling, uncertainty and explicit local-date/clock-change/pooling assumptions |
| Real API data wiring | B implements DB/snapshot adapter and connects the model; configured routes currently return insufficient_data |
| Stats / calibration | Explicit 503 responses remain; no fabricated results |
| Frontend / demo | PR #8 added React/Vite source; the real data -> model -> API -> UI journey remains unverified by this data validation |
| VM / submission | No deployment or submission performed; existing live services not changed |

## Active handoffs

| Task | Owner recorded by source task | Next action |
| --- | --- | --- |
| [Branch integration](../tasks/branch-integration.md) | Jintian-JTST / Codex | Owner reviews PR targeting main |
| [D: data-ingestion](../tasks/data-ingestion.md) | Jintian-JTST / Codex | Reconcile revised P0 and produce raw-linked bus evidence |
| [M: model](../tasks/model.md) | Olivia Guo / Claude Code | Revised evidence policy and B adapter contract |
| [B: backend-api](../tasks/backend-api.md) | David / Codex | DB/snapshot cache and model adapter |
| F: frontend-demo | Not recorded | Create task/branch and implement core evidence UI |

Earlier setup/docs verification is retained in Git history and the source task
records. D/B's external-service results are dated source reports, not new checks
of live collection, Tiger Data, Gemini or TfL during this integration.
