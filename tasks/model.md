# Task: Model and submission (role M)

- Task ID: model / M
- Owner (person / AI tool): Olivia Guo (M) / Claude Code
- Branch: `docs/t10-final-snapshot` (model code is on `main` via PRs #6, #13, #24)
- Status: model complete on `main`; README model section merged (PR #42); T10/M3 rerun on the final data accepted by the reviewer; submission pending
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
| 5–14 | `low_data` | Estimate; no model band (API adds a 90% Wilson interval); no recommendation |
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

- **Decisions:**
  - ±60-minute window (PR #20), because ±30 never reached 15 runs on bus 29. The
    15-run threshold is unchanged.
  - Demo mode is the offline snapshot (PR #36), so the numbers stay fixed.
  - The stage demo uses the final snapshot `bus29-db-final-20261024T202558Z` (PR #46),
    Sat 17:00 deadline only (David, chat #209). Do not show the 20:00 or 21:00 deadlines.
- **Verified demo numbers** (main `b62c0af`, final snapshot, by M):
  - Sat 24 Oct 17:00 London, 5/5 walks: leave **16:22**, p=0.9174, 91/91 points `ok`,
    up to 22 runs. This matches live DB mode (B and D).
  - The 15:30 deadline: 6 `ok`, 71 `low_data` and 14 `insufficient_data` points, up to
    17 runs, `no_departure_meets_tolerance`.
  - The old 16:55Z snapshot still gives 16:25, 0.90.
- **T10/M3: rerun on the final data** (main `b62c0af`, by M; the reviewer accepted
  it in chat #208 without rerunning it):
  - Method: the API's loaders, `calibration.backtest`, ±60 and `n_boot=0`, applied to
    both snapshots.
  - Reproduce it with one command, run from `backend/`. Pass the old folder first;
    paths are relative to the repo root:

    ```text
    uv run --locked python -m tools.rerun_t10 docs/evidence/bus29-db-final-20261024T202558Z [NEW_FOLDER] --standalone docs/evidence/<standalone handoff>
    ```

    On the 20:25Z snapshot it prints:
    - Brier 0.1296 for Mornington Crescent (1104 outcomes, 49 runs);
    - Brier 0.1318 for Finsbury Park (760 outcomes, 42 runs);
    - Sat 17:00 → leave 16:22, p=0.9174;
    - Sat 15:30 → `no_departure_meets_tolerance`.

    Checked by dry run on main `7895e83` (T29).
  - All data is from Saturday 24 Oct. Standalone recording counts and database
    counts are reported separately.

  | Route (database snapshot) | Runs 16:55Z → 20:25Z | Brier | Outcomes (runs) | Top bin, predicted → observed |
  | --- | --- | --- | --- | --- |
  | Mornington Crescent → TCR (short) | 26 → 56 | 0.1165 → 0.1296 | 448 (22) → 1104 (49) | 0.932 → 0.924, then 0.918 → 0.908 |
  | Finsbury Park → TCR (long) | 18 → 48 | 0.1683 → 0.1318 | 296 (16) → 760 (42) | 0.941 → 0.854, then 0.934 → 0.949 |

  - Short segment, final snapshot: the middle bins are slightly conservative
    (0.695 → 0.768). On the long segment the earlier overconfidence is gone.
  - Advice on the final snapshot, by deadline:
    - 18:00 → 17:24 (0.92);
    - 19:00 → 18:19 (0.92);
    - 20:00 and 21:00 → p=1.00 on only 12/91 and 2/91 `ok` points. This is an edge
      effect, not evidence.
  - Status stays preliminary: one Saturday, scored against inferred events.
  - PR #46 checks:
    - both `MANIFEST.json` files: SHA256 and byte counts recomputed, 10/10 each;
    - standalone 180-min recording: `load_handoff` used 5/5 rows (London 18, 20 and
      21 h). At most 4 runs per departure, so `too_few_runs` and no advice. Task 1's
      15-run gate is still not met.
- **T16: morning rerun** (main `f57eb65`, by M with `tools.rerun_t10`; it matches the
  manager's independent T42 comparison in
  `docs/evidence/bus29-morning-comparison-20261025`):

  | Route (database snapshot) | Runs 20:25Z → 06:07Z | Brier | Outcomes (runs) | Top bin, predicted → observed |
  | --- | --- | --- | --- | --- |
  | Mornington Crescent → TCR (short) | 56 → 80 (74 Sat + 6 Sun) | 0.1296 → 0.1276 | 1104 (49) → 1584 (67) | 0.918 → 0.908, then 0.929 → 0.924 |
  | Finsbury Park → TCR (long) | 48 → 70 (67 Sat + 3 Sun) | 0.1318 → 0.1168 | 760 (42) → 1128 (56) | 0.934 → 0.949, then 0.931 → 0.960 |

  - New runs are Saturday evening and Sunday 00:00–01:00 BST. Inferred runs stop
    before 01:00 BST, so the clock change at 02:00 BST is not exercised by this data.
  - Same local date only: with the 06:07Z data, Sat 17:00 still gives leave 16:22,
    p=0.9174, and Sat 15:30 still gives no recommendation. Earlier checks agree:
    adding a synthetic Sunday copy left the Saturday curve unchanged, and
    `test_dates_are_not_pooled_unless_requested` covers this.
  - New snapshot `MANIFEST.json`: 8/8 SHA256 match.
  - The demo stays on the locked 20:25Z snapshot, because its numbers are unchanged.
  - Status stays preliminary: scored against inferred events, mostly one Saturday.
  - No new standalone export was available at 07:03 GMT, so task 1's standalone
    count was not rechecked.
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
  - Sun 07:00: recheck support and calibration only if new data is exported after
    20:25Z.
  - Sun 08:30: lock the demo scenario (final snapshot, Sat 17:00). Check at rehearsal
    that the example button lands on 17:00 after D-claude's default-route PR.
  - Confirm submission rules with the organisers.
  - Sun 09:30–10:30: Devpost draft; submit 11:00–11:15.
