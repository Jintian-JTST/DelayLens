# Task: D-side delivery and chat coordination

- Task ID: chat-d-delivery
- Owner (person / AI tool): Jintian-JTST / D-CodeX
- Branch: `codex/chat-d-delivery`
- Status: local checks complete; remote CI, integration and capture follow-up pending
- Integrator / reviewer: repository integrator; independent cross-review by scoped subagents
- Plan / contract reference: PLAN sections 3, 6, 7 and 9; owner-requested chat cooperation

## Outcome and acceptance criteria

Close actionable D evidence gaps, preserve recordings/frozen snapshots, verify
the actual offline bus 29 UI journey and provide repeatable offline CI.
Keep authorised project-chat coordination in Chinese and brief.

## Ownership and dependencies

- Independent branches own source review, browser acceptance and CI. This branch
  integrates their intended files and drafts shared progress for integrator review.
  Main, teammates' working files and their staging areas remain untouched.
- API/model contracts and lockfiles are unchanged. B owns API work; M owns model
  and refreshed evaluation. Existing recordings and frozen snapshots are retained.
- No spending, deployment or recorder restart is performed.

## Handoff

- Baseline: local main `134dafb` (PR #38). See [source review](chat-data-source-review.md),
  [browser acceptance](chat-bus29-acceptance.md) and [CI](chat-ci-handoff.md).
- Three scoped authors cross-reviewed the other components. Source-review defects
  found before delivery: optimisation removed asserts, and CRLF bytes would change
  under Git LF normalisation. Final validation requires both fixes and Git-blob
  manifest readback; optimisation must fail before reading raw data.
- At 19:26 UTC, `deploy/local-recorders.ps1 -Check` found a database poll about
  10 seconds old. It reported 49 short / 41 long bus 29 database segments under
  that pipeline's existing contract, not independent standalone qualified samples.
- The 180-minute standalone and separate area recorder were running, untouched.
  Their process presence does not prove overnight availability.
- B accepted chat T2 and reported frozen API/performance checks complete. Separate
  laptop benchmark figures are source reports, not independently repeated here.
- T4/T5/T8 still named older participant aliases when inspected. The page refused
  D-CodeX's claim; no duplicate task was created to conceal that state.
- Remaining: remote CI/review and integrator approval; export the running capture
  after it finishes; hand new data to M/B; verify any unattended/deployment claim
  with actual raw timestamps and host recovery evidence.
