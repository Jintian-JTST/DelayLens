# Task: Independent frontend acceptance (T52)

- Owner: PROJECT_REVIEWER
- Branch: fix/reviewed-map-cleanup
- Status: source review/browser/unit/build complete; exact-head CI gates merge
- Scope: D's T51 implementation; own cancelled T50 prototype is not merged

JTST merged the originalPR83 before its review correction. Manager independently
reproduced the initial503 recovery defect, verified D's6c21857 fix with61tests
and fault/race Chrome checks, then integrated it throughPR84. Valid edits after
initial/manual503 recover; delayed old responses cannot replace new results;
rapid typing sends one debounced request; invalid walks send none.

D's50f06a3 removes unmodelled map context and renders real endpoint fallback for
Finsbury. Manager fixes its inherited7px text-stroke selector regression on an
isolated branch, preserving D's commits/worktree.62tests/build pass; both route
maps and their label bounds/styles are checked against the actual locked API.
[Evidence](../docs/evidence/selected-map-review-20261025/README.md).

Locked16:22/p0.9174,15:30no-advice and source labels remain. Backend/model/default
files are unchanged. Real microphone/Gemini and physical rehearsal are not accepted
by these checks. OptionalPR82 remains separate pending sources/style integration.
