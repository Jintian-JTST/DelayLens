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
- Needed from B (`numpy` is now in `pyproject.toml`): map NaN or
  `insufficient_data` to the contract's status with no probability, and expose
  `calibration_status: not_validated`.

## Handoff

- Changes (uncommitted, on `feat/model`):
  - **Unconfirmed departures:** a bus seen leaving O with no usable segment now
    censors replay instants that would board it, instead of skipping to the next
    usable run (which overstated waits).
  - **`load_handoff(folder)`:** reads D's export (segments.csv, stop_events.json,
    quality.json, route.json). Coverage is the capture window, split at each
    `successful_poll_gaps` entry (`from`/`to`, format read from D's exporter).
  - **90% band:** Poisson bootstrap over whole runs (200 resamples), `ok` rows only.
  - **Advisor and what-if:** `recommend()` returns the latest departure with
    P(late) <= tolerance (ok rows only, plus a conservative variant from the band
    edge) or a reason (`too_few_runs`, `no_departure_meets_tolerance`).
    `what_if()` returns +5/+10/+15 min results, with None where unsupported.
- Real data (D's bus 24 checkpoint, 14:53–15:23 BST Sat 24 Oct): 62/62 polls,
  2 usable runs, 3 unconfirmed origin departures (1 inside coverage) →
  `insufficient_data` and `too_few_runs` everywhere, as expected.
- Checks run (macOS, `uv run --locked`): `pytest`: 139 passed, 7 skipped
  (opt-in DB tests); `ruff check` on model files: clean. Curve + band +
  advisor on 630 synthetic runs: median 8.5 ms (budget 50 ms).
- B's `app/curves.py` maps `Curve` onto the API (insufficient points are
  omitted, with a provisional Wilson `ci`). The run-bootstrap band
  (`Curve.ci_low/ci_high`, `ok` rows only) and `recommend()`/`what_if()` are
  ready for B to switch to.
- Real data on `main` (60-min bus 24 evidence, 4 runs): `insufficient_data`
  everywhere. That evidence has no `stop_events.json`, so unconfirmed departures
  can't be censored: ask D to include it in handoffs.
- Next action (M): re-run on D's next handoff (5+ runs for `low_data`); ask B to use
  the bootstrap band and `recommend()` in `curves.py`.
