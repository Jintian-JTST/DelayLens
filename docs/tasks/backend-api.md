# Task: Backend API, Gemini and integration (role B)

- Task ID: backend-api
- Owner (person / AI tool): B (David) / Claude Code
- Branch: feat/api
- Status: in progress
- Integrator / reviewer: B merges in order D → M → B → F

## Outcome and acceptance criteria

FastAPI backend serving the contract in PLAN.md §6.3: `/api/routes`,
`/api/departure-curve`, `/api/ask`, `/api/live`, `/api/stats`, `/api/calibration`.
Real data replaces fixtures at the Sat 18:30 gate; failures are explicit, never faked.

## Ownership and dependencies

- Owned files: `backend/app/main.py`, `schemas.py`, `tfl.py`, `db.py`, `ask.py`,
  `backend/tests/test_api.py`, `backend/tests/ask_cases.json`, `backend/fixtures/`,
  `backend/pyproject.toml`, `backend/uv.lock`, `backend/.env.example`
- Shared interfaces: `backend/app/schemas.py` (frozen Sat 17:00)
- Dependencies: D (schema, `routes.json`, segments SQL), M (`model.py`)
- Required local configuration names: `TFL_APP_KEY`, `DATABASE_URL`,
  `GEMINI_API_KEY`, `FRONTEND_ORIGIN`

## Handoff

- Changes: uv project, schemas, fixture-backed `/api/departure-curve`, stubs that fail honestly
- Checks run (macOS, Python 3.14, uv 0.13.5): `uv run pytest` 7 passed; `uv run ruff check`
- Unverified: real TfL, Tiger Data and Gemini integration (not built yet)
- Next action (B): `tfl.py` + real `/api/live`, `/api/routes` from D's `routes.json`
