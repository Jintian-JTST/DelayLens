# Task: Keep repeated London hours separate in T10 reports

- Task ID: T39 (project chat)
- Owner: David / PROJECT_REVIEWER (Codex manager)
- Branch: `fix/t10-dst-hour-report`
- Status: local validation passed; PR/remote CI pending
- Integrator / reviewer: PROJECT_REVIEWER
- Plan / contract reference: AGENTS.md data provenance and local-clock assumptions

## Outcome and acceptance criteria

The overnight export crosses the 25 October clock change. The T10 report must
show the repeated London 01:00 hours separately as BST (+0100) and GMT (+0000).
Distinct dates must also remain separate. Only report labels/grouping change;
snapshot contents, model probability calculations and inference stay unchanged.

## Ownership and dependencies

- Files: `backend/tools/rerun_t10.py`, `backend/tests/test_rerun_t10.py`, this record.
- No API/schema change, credentials or external services required.
- Supports the scheduled T16 model/data comparison and T14 export handoff.

## Handoff

- Regression cases cover both repeated 01:00 hours and separate dates sharing
  the same weekday/hour.
- macOS/Python 3.14: offline pytest 247 passed, 28 live tests deselected; Ruff
  passed for app/tests/ingest, the report tool and deploy tooling. The existing
  Starlette/httpx deprecation warning remains.
- Reran `python -m tools.rerun_t10 docs/evidence/bus29-db-final-20261024T202558Z`
  from `backend/`: Brier 0.1296/0.1318, leave 16:22, p=0.9174 and the 15:30
  no-advice contrast are unchanged. Snapshot/model files were untouched.
- Next: run checks, inspect diff, publish PR and verify exact-head CI.
