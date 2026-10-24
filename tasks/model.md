# Task: Model and submission (role M)

- Task ID: model / M
- Owner (person / AI tool): Olivia Guo (M) / Claude Code
- Branch: feat/model
- Status: in progress
- Integrator / reviewer: B merges in order D → M → B → F

## Outcome and acceptance criteria

`backend/app/model.py` turns recorded trip segments into the departure curve in
PLAN.md §4: `p_on_time`, 90% band, `arrive_p50/p90`, `n_trips`, recommendation and
what-if. It returns `low_data` / `insufficient_data` and never invents a
probability. The budget is < 50 ms per curve. Calibration JSON and Devpost submission
come later (PLAN.md §8).

## Ownership and dependencies

- Owned files: `backend/app/model.py`, `backend/tests/test_model.py`, this file,
  README additions, Devpost write-up
- Interface proposed to D and B: `Segments(vehicle_id, t_origin, t_dest)` with
  NumPy arrays and times as int64 UTC epoch seconds, sorted by `t_origin`. D's
  segment CSV should provide these three columns, with timestamps in ISO 8601 UTC.
- Dependencies: D (segment CSV, Sat 18:30), B (contract and fixtures, Sat 17:00)
- Dependency request to B: add `numpy` to `backend/pyproject.toml`

## Handoff

- Changes: synthetic timetable generator (`synthetic_segments`), `Segments`
  container, vectorised empirical replay (`replay_curve`, `departure_curve`,
  `p_on_time`) returning `p_on_time`, `arrive_p50/p90` and `n_trips` per departure.
  If no recorded vehicle covers a departure, the result is NaN with
  `n_trips = 0`, never 0%.
- Checks run (macOS, Python 3.14.6, numpy 2.5.4, pytest 9.1.1, via local venv;
  `uv` not installed): `pytest tests/test_model.py` from `backend/`: 13 passed.
  These include hand-checked step, ramp and walking cases, distinct-trip counts,
  end of data and multi-day replay. Curve over 2 days of synthetic data (615
  trips, 91 departures): median 1.5 ms (budget 50 ms)
- Next action (M): 90% bootstrap band; `low_data` / `insufficient_data`
  thresholds (Sat 16:30–18:00); match the frozen contract at 17:00
