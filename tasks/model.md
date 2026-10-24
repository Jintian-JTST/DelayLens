# Task: Model and submission (role M)

- Task ID: model / M
- Owner (person / AI tool): Olivia Guo (M) / Claude Code
- Branch: feat/model
- Status: in progress
- Integrator / reviewer: B merges in order D → M → B → F
- Plan / contract reference: [PLAN.md](../PLAN.md) §3.5, §3.6 and §4 at `4da089c`

## Outcome and acceptance criteria

`backend/app/model.py` turns D's usable inferred segments into the departure
curve (PLAN.md §4). Per departure it returns `p_on_time`, `arrive_p50/p90`, and
counts: distinct runs (`n_trips`), vehicles, eligible replay steps and censored
steps. It also returns an evidence status:

| Usable runs | Status | Model output |
| --- | --- | --- |
| 0–4 | `insufficient_data` | Counts only; probability and arrivals are NaN |
| 5–14 | `low_data` | Descriptive probability; no recommendation (advisor, next task) |
| 15+ | `ok` | Probability; band and recommendation (next task) |

Replay uses London local time on explicit reference dates (default: the query's
own date only, so Saturday and Sunday are not pooled). The boarding buffer is
1 min. Recording edges and capture gaps are censored, never counted as late.
Budget < 50 ms per curve.

## Ownership and dependencies

- Owned files: `backend/app/model.py`, `backend/tests/test_model.py`,
  `backend/conftest.py`, this file, calibration outputs, README and Devpost
- Input from D: the §3.5 CSV (`segment_id, route_id, vehicle_id, origin_at,
  destination_at, travel_seconds, inference_method, quality, source`).
  `load_segments_csv` keeps `quality == estimated` rows for one route, dedupes on
  `segment_id`, checks durations and reports each exclusion by reason.
- Needed from D: complete-recording intervals per route (start/end UTC) for
  censoring. Without them, coverage defaults to first..last departure, so
  mid-recording gaps would be missed.
- Needed from B: add `numpy` to `backend/pyproject.toml`; map NaN or
  `insufficient_data` to the contract's status with no probability, and expose
  `calibration_status: not_validated`.

## Handoff

- Changes: merged `main` (revised plan) into `feat/model`. Added the §3.5 CSV
  loader with an exclusion report, local-time reference dates (repeated 01:00 hour
  kept distinct), coverage-based censoring, the 0–4 / 5–14 / 15+ evidence status,
  and separate run, vehicle, step and censored counts.
- Checks run (macOS, Python 3.14.6, numpy 2.5.4, pytest 9.1.1, local venv; `uv`
  not installed): `pytest tests/test_model.py` from `backend/`: 17 passed.
  These include hand-checked step, ramp, walking, gap-censoring (37 eligible / 24
  censored) and end-of-recording cases. Curve over 2 days of noisy synthetic data
  (630 runs, 91 departures, 2 reference dates): median 1.6 ms.
- Unverified: no real segment CSV yet; all results use labelled synthetic data.
- Next action (M): bootstrap 90% band by resampling runs, and an advisor that
  suppresses recommendations below 15 runs (Sat 16:30–18:00)
