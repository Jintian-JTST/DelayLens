# Task: Network-backed bus 29 browser evidence

- Task ID: chat-network-acceptance
- Owner (person / AI tool): Jintian-JTST / D-CodeX
- Branch: `codex/chat-network-acceptance`
- Status: actual network and snapshot-regression checks passed; PR/integration pending
- Integrator / reviewer: B / repository maintainer
- Plan / contract reference: PLAN sections 6 and 9; chat T6 coordination

## Outcome and acceptance criteria

Verify existing Tiger Data recorded journeys through the actual API/model and
browser; preserve full requests/responses and screenshots. This is historical
replay of inferred arrivals, not current measured arrival or future validation.

## Ownership and dependencies

- New evidence directory, optional database mode in the existing QA runner, and
  this task only; no API/model/schema/lock or product behavior changes.
- Isolated worktree from main `2d7e51c`; API 8021 and frontend 5182.
- Reuse private local database configuration without displaying or copying its
  values. API cache connections are read-only. No recorder or database writer starts.
- Disable TfL/Gemini calls for this check; B retains the local demo checklist.
- Original frozen evidence in PR #39 remains unchanged.

## Handoff

- Capture 2026-10-24 19:57:55.657–19:58:18.744 UTC on Windows/Chrome/Node24.13.0.
- Read-only database reports 53 short-route source journeys and 7 recorded hours.
  UTC16:00: 91 points, advice15:22Z, estimated probability0.9174; UTC14:30: 77 points,
  low_data/no advice. Counts are dated and not independent evidence of calibration.
- Actual network API/browser: 10 grouped checks passed, including form/result
  agreement, local controls, mobile widths, source wording and no fixture fallback.
- Actual curl through the same frontend proxy returned200; all point, advice and
  data-quality fields matched the browser response. One loopback call was105.815ms,
  not a network latency benchmark.
- Existing offline default mode: 10 grouped checks passed again. Node syntax passed.
- Initial default route is Victoria (most reported trips); bus29 was explicitly
  selected through the normal form. No claim that bus29 is the default route.
- Network evidence is under docs/evidence/bus29-network-browser-20261024; existing
  frozen evidence from PR39 stays unchanged. Review/CI and integration remain pending.
- B accepted this ownership split in chat and continues the separate T7 checklist.
- No deployment, power-policy changes or source-data mutation authorised by this task.
