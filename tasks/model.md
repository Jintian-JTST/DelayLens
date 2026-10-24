# Task: Model and submission (role M)

- Task ID: model / M
- Owner (person / AI tool): Olivia Guo (M) / Claude Code
- Branch: `docs/model-readme` (model code is on `main` via PRs #6, #13, #24)
- Status: model complete on `main`; README model section ready for review; submission pending
- Integrator / reviewer: B merges; PROJECT_REVIEWER checks evidence wording
- Plan / contract reference: [PLAN.md](../PLAN.md) §3.5, §3.6, §4, §8, §9 at `134dafb`

## Outcome and acceptance criteria

`backend/app/model.py` turns usable inferred segments into a departure curve
(PLAN.md §4). It replays every recorded minute within ±60 minutes of the London
local time on the query's own date. It boards the first run at least 1 minute
later and adds both walks. It reports `p_on_time`, `arrive_p50/p90`, a 90%
run-bootstrap band (`ok` rows only) and counts of distinct runs, vehicles, replay
steps and censored steps. Recording gaps, the recording edge and origin departures
without a usable segment are censored, never counted as late.

| Usable runs | Status | Output |
| --- | --- | --- |
| 0–4 | `insufficient_data` | Counts only |
| 5–14 | `low_data` | Estimate; no band, no recommendation |
| 15+ | `ok` | Estimate, band, `recommend()` and `what_if()` |

A curve takes about 8.5 ms (PLAN target 50 ms). `n_boot=0` skips the band for
backtests.

## Ownership and dependencies

- Owned files: `backend/app/model.py`, `backend/tests/test_model.py`,
  `backend/conftest.py`, this file, README model section, Devpost write-up
- Consumers: B's `curves.py` (live API, ±60 window via `curves.TOD_WINDOW_MIN`,
  PR #20) and `calibration.py` (blocked hold-out, `n_boot=0`, PR #25)
- Inputs: D's handoff folders (`load_handoff`) and the database snapshot

## Handoff

- **Decisions:** ±60-minute window (PR #20), because ±30 never reached 15 runs on bus
  29. The 15-run threshold is unchanged. Demo mode is the offline snapshot (PR #36),
  so the numbers stay fixed.
- **Verified demo numbers** (main `134dafb`, snapshot mode, by M):
  - Sat 24 Oct 17:00 London, 5/5 walks: leave **16:25**, 0.90, `ok`, up to 20 runs.
  - The 15:30 deadline gives `low_data` and no recommendation.
  - Live DB mode (reported by B and D): 16:22, 0.92.
- **Calibration** (B's backtest): snapshot status preliminary, Brier 0.1165,
  448 outcomes, 22 runs, top bin 0.932 → 0.924. Live DB #47: Brier 0.125,
  0.936 → 0.914. Scored against inferred events only.
- **Bus 29 standalone 90-min handoff** (`docs/evidence/bus29-short-20261024`):
  - 7 usable runs and 20 origin events. 8 departures inside coverage had no usable
    segment and are censored; 5 come after the recording end.
  - At ±60, up to 6 runs per departure, so no advice from this run alone.
- **Checks run** (macOS, `uv run --locked`):
  - backend suite on `main`: 196 passed, 28 opt-in skipped;
  - ruff clean;
  - frontend: 11 tests, build OK.
- **Unverified by M:** live database mode and Ask on this machine (no keys).
- **Next (M):**
  - Sun 07:00: recheck support and calibration on the overnight data.
  - Sun 08:30: lock the demo scenario.
  - Confirm submission rules with the organisers.
  - Sun 09:30–10:30: Devpost draft; submit 11:00–11:15.
