# Task: Verify and display the bus-feed source credit

- Related task: T43 submission preflight
- Owner: PROJECT_REVIEWER (manager implementation follow-up)
- Branch: `docs/bus-feed-attribution`
- Status: local checks passed; remote CI pending

## Outcome and scope

The preflight incorrectly treated the existing bus-feed attribution as invalid.
TfL's official open-data page explicitly lists it in the live bus arrivals
instant and stream branding sections. Keep that notice in the draft, link the
specific primary source, and add the notice to the app footer while preserving
its existing general open-data credit. No branding or endorsement is introduced.

The general transport-data terms page returned HTTP403 during this check;
this is a feed-guidance verification, not a claim of complete terms compliance.

## Ownership and validation

- Files: app footer copy, the draft attribution item and this record.
- M/F were notified of the limited footer/documentation ownership before edits.
- Frontend production build passed; existing relative Markdown targets and
  `git diff --check` passed. Copy only; no new tests were needed.
- Next: review the diff and exact-head CI before merging.
