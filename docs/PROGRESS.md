# DelayLens — Progress and Handoff

Updated: 2026-10-24 (Europe/London).

## Current milestone

Branch integration is prepared on `codex/integrate-branches` for owner review.
Main is not advanced by this task. A branch merge and passing unit tests do not
establish the real-data end-to-end demo.

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
- UTF-8/JSON/conflict-marker/path/whitespace and 44 exact-case local Markdown
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
| Frontend / demo | No frontend branch/source found; real data -> model -> API -> UI remains unverified |
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
