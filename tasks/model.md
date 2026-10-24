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
  container, `p_on_time` signature (stub), and hand-checked tests: a step curve
  with exact time of day, a ramp with a ±30 min window, and walking-time shifts
- Checks run (macOS, Python 3.14.6, numpy 2.5.4, pytest 9.1.1, via local venv;
  `uv` not installed): `python -m pytest tests/test_model.py` from `backend/`:
  5 passed, 3 xfailed (strict; the replay tests wait on the next task)
- Next action (M): vectorised empirical replay (Sat 15:00–16:30) until the 3
  xfail tests pass
