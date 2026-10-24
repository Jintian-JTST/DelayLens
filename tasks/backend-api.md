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

## Update: D integrated

- Merged `feat/data` (D) into `feat/api`; resolved `backend/.env.example` (kept D's polling IDs, plus optional `GEMINI_MODEL`).
- Added `psycopg[binary]>=3.2,<4` to `pyproject.toml` / `uv.lock`, as D requested.
- Verified with the real TfL key: `/api/routes` loads D's two routes; `/api/live` returns real arrivals for
  both (bus 29 outbound, Victoria outbound); `/api/ask` picks the right real route and answers
  "not enough recorded data" for curves (honest: M's model is not connected). 54 API tests + 23 ingest tests pass
  (7 ingest tests need a database and skipped).
- Still unverified: `app/db.py` against real Tiger Data; `/api/stats`, `/api/calibration` are still 503 stubs.
- Next (B): `db.py` pool + minute cache using D's `get_segments` / `route_coverage` views, then M's `model.py`.

## Update: Tiger Data cache (db.py)

- Added `backend/app/db.py`: read-only connection, loads D's `get_segments` and `route_coverage`
  views plus row/chunk/compression stats into an in-memory snapshot every 60 s in a background
  thread (started by the FastAPI lifespan when `DATABASE_URL` is set). A failed refresh keeps the
  last good snapshot and logs only the error type.
- `/api/routes` now fills `trips_observed` and `hours_covered` from the database; `/api/stats` is real;
  real-route curves stay `insufficient_data` but report the recorded trip count until M's model lands.
  `SegmentCache.segments(route_id)` is the hook for M's model.
- Checks (macOS, Python 3.14): `pytest -q` 62 passed; `ruff check app tests` passed. Against real
  Tiger Data at ~14:34 UTC: cache loaded with no error; routes 11 ms (bus 29: 0 trips, Victoria: 14
  trips over 2 hours); stats 2 ms (10,674 rows, 2 chunks, no compression yet).
- Open: bus 29 has 0 matched trips so far (D to check); `/api/calibration` still a 503 stub.

## Update: M's model connected

- Merged `feat/model` (which already contains `main` and PR #5) into `feat/api`; no conflicts. `uv sync` added numpy.
- Added `backend/app/curves.py`: D's segments -> `model.Segments` (deduplicated on vehicle + origin episode),
  `model.departure_curve` -> contract. NaN/`insufficient_data` rows are omitted; overall status is
  `insufficient_data` (no points), `low_data` (any low row) or `ok`. Recommendation and what-if only from `ok`
  rows (M's advisor policy). `ci` is a provisional 90% Wilson interval over distinct runs until M's bootstrap.
- `db.py` now also reads `origin_episode_started_at` (D's stable trip key).
- Checks (macOS, Python 3.14): `pytest -q` 111 passed, 7 skipped (live DB); `ruff check app tests` passed.
  Real Tiger Data, Victoria Brixton -> Oxford Circus, 15 trips: `low_data`, 62 points, P falls 1.00 -> 0.81 -> 0.00
  as departure moves later; server 40 ms. All three bus routes: 0 trips.
- For M: (1) replay uses only the deadline's date +/- 30 min, so a 10-min bus shows ~7 runs and can never reach `ok`
  (no recommendation) - see `tests/test_curves.py`; (2) bootstrap band to replace the Wilson placeholder;
  (3) coverage intervals still default to first..last departure (needs D).
- For D: bus 29 and both bus 24 routes have 0 matched trips; the bus is the core demo route.

## Update: Ask test set (21 phrasings)

- `backend/tests/ask_cases.json` + `tests/test_ask_cases.py`: vague times, tolerance words, comparisons, walking,
  live, route list, off-topic, unsupported places, missing deadline, slang and Chinese, against a fixed
  "now" (Sat 24 Oct 15:00 London). Structure check always runs; Gemini checks are opt-in:
  `DELAYLENS_RUN_GEMINI_TESTS=1 uv run pytest tests/test_ask_cases.py` (paced 5 s per case; costs quota).
- Prompt fix: "a bit late is fine" without a number now relaxes tolerance instead of moving the deadline.
- Results (real Gemini, 2026-10-24): best run 17/21. After the prompt fix no case returned a wrong
  interpretation; every failure was `gemini_unavailable`. 19 cases are confirmed passing; `walk-time` and
  `no-deadline` are unconfirmed (Gemini unavailable in the runs where they were identified). Logged causes:
  `gemini-3.1-flash-lite` ReadTimeout (>4 s) and `gemini-3-flash-preview` HTTP 429 (free-tier rate limit
  exhausted by repeated test runs). Ask now logs model + HTTP status/error type on failure (never the key).
- Risk for the demo: free-tier Gemini quota and latency. Consider a paid/credit key and avoid bulk test runs before judging.

## Update: /api/calibration (rolling-origin backtest)

- `backend/app/calibration.py` (B, built at the user's request; M owns calibration policy and may take it over):
  forecast origins every 30 min; the model sees only runs that had arrived by the origin (coverage ends
  before the first unfinished run), and is scored on departures in the next disjoint 30-min block against
  the first recorded catchable run. Deadlines = training median ride + (-2..12) min. 5 reliability bins
  and a Brier score; uses only M's public `model.replay_curve`.
- Waits over 4x the training median headway are censored as suspected capture gaps (unknown, not late)
  and counted in `basis`; placeholder until D supplies coverage intervals.
- Contract change (B-approved, additive with defaults): `Calibration` gains `calibration_status`
  (`not_validated` | `preliminary`; never "validated"), `n_outcomes`, `n_runs`, `basis`.
  `GET /api/calibration?route_id=` optional; 503 without the database; memoised per cache refresh.
- Checks: `pytest -q` 120 passed, 28 skipped. Real data at ~15:10 UTC: 23 ms; `not_validated` with 0 scored
  outcomes, because the only held-out block fell on a 16.7-min hole in recorded Victoria runs
  (35 outcomes censored). Before censoring, that hole produced a misleading Brier score of 0.63.
- For D: Victoria has a 16.7-min gap between recorded departures (trains run every 2-3 min) - likely
  unmatched runs; coverage intervals would let the model and backtest handle this properly.

## Update: M's bootstrap band and advisor

- `curves.py` now uses M's `model.recommend()` and `model.what_if()` (B's duplicate advisor removed), and
  M's 90% run bootstrap (`ci_low`/`ci_high`) for `ok` rows. The model gives no band for `low_data` rows;
  because `CurvePoint.ci` is required by the contract and the frontend chart, those rows keep a wider 90%
  Wilson interval over distinct runs. Contract unchanged.
- Checks: `pytest -q` 162 passed, 28 skipped; `ruff check app tests` passed. Real Tiger Data (~16:20 UTC):
  Victoria 51 trips: first real recommendation (leave 15:43 UTC, P=0.913; +5 min -> 0.049), 23 ms. Bus 29
  segments 14 and 22 trips: `low_data`, no recommendation, 4-10 ms. Calibration 24 ms, 21 outcomes, Brier 0.042,
  `not_validated`.
- Not checked in the browser (the running localhost servers are another checkout's).

## Update: M's calibration feedback (blocked hold-out, coverage, unconfirmed departures)

- Live curves now pass M's `coverage` and `unconfirmed_departures` to the model (previously dropped).
  `db.py` loads every origin `stop_events` row per active route and the `poll_runs` ledger;
  `curves.poll_coverage` splits recording at polls > 1.5x the median interval (D's exporter rule) and clips
  each route's coverage to its first origin event. Origin events without a usable run are unconfirmed.
- `calibration.py` is now a blocked hold-out (M's proposal, PLAN section 4): each 30-min block is held out
  and the model is trained on runs, coverage and unconfirmed departures outside it. An outcome is scored
  only if the caught run is inside the block, in coverage, and no unconfirmed bus came first; others are set
  aside and counted. The `SUSPECT_GAP_FACTOR` placeholder is removed.
- Checks: `pytest -q` 165 passed, 28 skipped. New tests: bus timetable (8-min headway, 18-min ride: 568
  outcomes, previously 0), disjoint held-out training, gap set aside, unconfirmed bus makes outcome unknown,
  poll-gap coverage and unconfirmed detection.
- Real Tiger Data (~16:25 UTC): bus 29 Finsbury Park 15 runs + 11 unconfirmed; calibration per route 25-36 ms;
  all routes 69 ms, 744 outcomes, 52 runs, 5 blocks, Brier 0.144, `preliminary`. Top bin predicted 0.96 vs
  observed 0.83 (overconfident at the top). Curves 2-12 ms; Victoria recommendation 15:48 UTC.

## Update: +/-60 min window (PR #20) and Devpost backend draft

- PR #20 (merged): `curves.TOD_WINDOW_MIN = 60`, passed as `tod_window_min` to `model.departure_curve`
  (`main.py`) and `model.replay_curve` (`calibration.py`), so the API, Ask and the backtest score the same
  model. `_known_outcome` now uses `<=` for an unconfirmed departure at the run's origin time, matching
  `model.py`. `curves._basis` states the window and `test_basis_discloses_the_time_of_day_window` pins it
  (PLAN section 4 allows +/-60 only with disclosed coverage). The 15-run threshold is unchanged.
- Why: at +/-30 min bus 29 has about 7-13 runs per departure and never reaches 15, so it gives no advice;
  at +/-60 it does (M's synthetic check, then D's DB check).
- Checks on `main` after #20, live Tiger Data snapshot, bus 29 Mornington Crescent -> Tottenham Court Road
  (28 trips): deadline 16:00Z `ok`, 91 points, recommended leave 15:32Z P=0.9174; deadline 14:30Z `low_data`,
  `recommended=null`. `/api/calibration` with +/-60: Brier 0.1251, `preliminary`, 504 outcomes from 24 runs,
  216 set aside; top bin 0.936 predicted vs 0.914 observed (was 0.96 vs 0.83 at +/-30). Arrivals are
  inferred from TfL predictions and outcomes overlap, so these are not independent samples.
- Latency, in-process (TestClient on one laptop, so no network or TLS), 240 warm requests to
  `/api/departure-curve`: total p50 3.5 ms, p95 4.1 ms, max 5.4 ms; `server_ms` p95 3.2 ms; first cold call
  45 ms. Calibration first call 45 ms, then 1 ms memoised. PLAN target p95 < 300 ms. Say "in-process" if quoted.
- Not checked: Ask against Gemini, the UI, and latency over the network.
- Open: use `n_boot=0` in `calibration.backtest` once M's `feat/model-nboot` is on `main`.

### Devpost draft: backend and Gemini (about 150 words, for M's submission)

> A FastAPI service reads Tiger Data (PostgreSQL) into an in-memory snapshot of recorded bus trips, refreshed
> every 60 s; a failed refresh keeps serving the last good snapshot. A curves adapter turns the snapshot into
> model inputs and the model's output into the API response, with a data-quality status and a plain-language
> basis line. Gemini is used only for Ask: it maps a question to one validated function call, with a 4 s
> timeout and a fallback model. It never produces numbers; every figure comes from our empirical-replay model
> and the answer is a template. Public Ask is passcode-gated. Calibration is a blocked hold-out: six
> 30-minute blocks, each scored by a model trained on the other blocks, against arrivals inferred from TfL
> predictions (Brier 0.125, preliminary). In-process, a warm /api/departure-curve takes p95 4 ms (server time
> 3 ms); a cold first call takes 45 ms.

Caveats for the submission: the passcode sentence holds only when `ASK_ACCESS_CODE` is set on the deployed
server (unset leaves Ask open); the Brier score and status will move as recording continues.
