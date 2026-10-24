# Task: Backend API, Gemini and integration (role B)

- Task ID: backend-api
- Owner (person / AI tool): B (David) / Codex (continuing the Claude Code scaffold)
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

Updated: 2026-10-24 (Europe/London).

- Existing scaffold: uv project, schemas, labelled fixture-backed departure curve,
  and explicit unavailable responses for integrations that are not connected.
- Added `tfl.py` and wired `/api/live`: three-second HTTP timeouts, validation,
  origin/line/direction filtering, UTC timestamps and sorted arrivals. Failures
  return HTTP 503 with `{"error":"tfl_unavailable"}` as specified in PLAN.md;
  provider errors and API keys are never forwarded to callers. An empty valid
  provider list remains a successful response.
- `/api/routes` loads D's `backend/config/routes.json` once present. It expects a
  JSON array with the route/stop fields in PLAN.md; `direction` can be `inbound`
  or `outbound` and is required for Tube live calls. Until the DB coverage is
  wired, missing `trips_observed` and `hours_covered` default to `0` and `[]`.
  Invalid configuration returns 503 instead of silently loading fixtures.
- The existing fixture route remains available while the real configuration is
  absent. Once real routes are configured, departure curves return
  `insufficient_data` with no probabilities until M's model is connected.
- Checked the arrivals endpoint and field names against the
  [official TfL API schema](https://api.tfl.gov.uk/swagger/docs/v1).
- Checks run on macOS/zsh with the existing Python 3.14.7 environment (commands
  from `backend/`): `.venv/bin/python -m pytest -q` — **34 passed**;
  `.venv/bin/ruff check app tests` — passed;
  `.venv/bin/ruff format --check app/main.py app/tfl.py tests/test_api.py` — passed;
  `git diff --check` — passed. Windows uses `.venv/Scripts/python.exe` and
  `.venv/Scripts/ruff.exe` for the equivalent commands. No dependencies changed.
- Existing check limitations: pytest emits a Starlette/httpx deprecation warning;
  a broader formatting check also flags unchanged `app/fixtures.py`.
- Unverified: a real TfL request. This checkout has neither `TFL_APP_KEY` nor
  D's route configuration; tests use HTTPX's mock transport. Tiger Data, the
  recorded-trip model and Gemini remain unconnected.
- Next actions: D supplies the route configuration and local TfL credentials;
  B verifies live arrivals against those routes. Then implement `db.py`'s pool
  and minute-refreshed segment cache against D's SQL contract and connect M's
  model. Do not invent the missing database or model interfaces.

## Update: Ask DelayLens (Gemini)

- Added `backend/app/ask.py` and wired `POST /api/ask`. Gemini only chooses one function call
  (`list_routes`, `get_departure_curve`, `compare_departures`, `get_live`, `unclear`); arguments are
  validated, and every number and the answer sentence come from our model and templates.
- Times from Gemini are treated as London wall-clock time and given the real UTC offset by us
  (clocks change at 02:00 on Sun 25 Oct and models guess the offset wrongly).
- Models tried in order: `gemini-3.1-flash-lite`, `gemini-3-flash-preview` (4 s each; `GEMINI_MODEL`
  overrides the first). `gemini-2.5-*` is no longer available to new keys.
- Failures return status `gemini_unavailable` and never leak the key.
- Checks run (macOS, Python 3.14): `.venv/bin/python -m pytest -q` 54 passed; `.venv/bin/ruff check app tests`.
  Real Gemini, fixture route only: curve, compare, relaxed-deadline, off-topic and unsupported-place
  questions behaved correctly. Latency measured 0.8 s to 6 s (Gemini load varies).
- Unverified: Ask against real routes and real model output (waiting for D's routes.json and M's model);
  the plan's 20-phrasing test set is not written yet.
