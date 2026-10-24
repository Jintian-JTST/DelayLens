# Task: Read-only final capture verification and data handoff

- Task ID: chat-final-capture
- Owner (person / AI tool): Jintian-JTST / D-CodeX
- Branch: `codex/chat-final-capture`
- Status: final capture, archives, replay and model-loading verified; PR/handoff pending
- Integrator / reviewer: repository maintainer; M consumes final samples
- Plan / contract reference: PLAN sections 3 and 9; chat T13 coordination

## Outcome and acceptance criteria

Verify and hand off the existing 180-minute standalone bus29 capture after its
own recorder finishes. Keep all raw originals and distinguish archive delivery
from unmet usable-run/time-support targets. Report actual counts; never pool
database segments into standalone counts or infer measured arrivals.

## Ownership and dependencies

- New dated handoff/evidence, this task and evidence-backed progress update.
  No API/model/schema changes.
- Isolated base main `a976b0d`; source run is `bus29-short-20261024T1721Z`.
- The original CLI owns raw saving, derivation and final ZIP generation. This
  task reads completed outputs and performs independent in-memory replay and
  archive verification; it does not invoke export against the source run.
- Chat T13 named jtst-claude. D-CodeX told the coordinator it would only inspect
  automatic outputs, preserving that handoff and avoiding concurrent writes.
- No recorder stops/restarts, original review changes or database writes.

## Handoff

- Latest check at20:14 UTC: recorder PID3748 was live, metadata status recording,
  raw polls342 (341 successful/1 failed), four independent inferred journeys.
  These are provisional and not the final result.
- Expected duration ends near20:22 UTC on24 October; completion and final archives
  must be observed rather than inferred from this schedule.
- Normal completion observed20:21:55 UTC; both final ZIPs appeared20:23:09 and
  recorder PID3748 exited. Existing database and area recorders were left alone.
- Final354 polls,353 successful/1 failed,5 inferred independent journeys and251 events.
  Data gate passes; source-trace acceptance remains pending; global support low_data.
- Usable journey hours17/19/20 UTC meet3-hour count, but5<15: the independent-run
  target is explicitly unmet. No database/standalone pooling was performed.
- Read-only replay reproduces all CSV/events, raw JSONL/GZIP hashes agree, four ZIP
  CRCs/manifests pass, final canonical archived raw polls match original records.
- Actual model loader:5 rows,5 used,0 excluded. Ruff passes; optimisation preserves
  explicit failure checks. No notebook or archived source was executed.
- Separately froze database snapshot20:25:58 UTC: short56 segments/8 hours, long48/6,
  791 poll times. Existing loader, counts, unique episodes, positive durations and
  origin links verified. These are that pipeline's counts, not measured arrivals.
- Both new evidence folders retain original historical snapshots and contain SHA256.
- Next: review/integrate this PR, notify M to rerun M3/T10, then clear T13 only after
  the files are available to the team. New calibration is M's work, not claimed here.
