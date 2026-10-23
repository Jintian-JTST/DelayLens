# OxHack 2026 — Progress and Handoff

Updated: 2026-10-23 (Europe/London).

## Current milestone

Repository preparation. Product requirements and technology decisions await the
team's brief in [PROJECT.md](PROJECT.md).

## Completed

- Cloned `Jintian-JTST/OxHack` into the requested local folder with `origin` and
  tracking branch `main`.
- Added canonical AI coding rules in root `AGENTS.md` and thin entry points for
  Copilot, Claude Code, Gemini CLI and Cursor.
- Added a project brief, decision log and this progress/handoff document.
- Extended the README and inherited Python `.gitignore`; preserved `LICENSE`.

## Verification

- Passed: expected file inventory, UTF-8 content, local Markdown links and imports,
  and Cursor rule frontmatter.
- Passed: original README and Python ignore rules retained; MIT license unchanged.
- Passed: ignore checks for 13 local credential/generated paths and retention checks
  for 17 example, lockfile and project paths.
- Passed: `git diff --check`.

There is no application tooling yet; application tests, lint and builds are not
configured. Instruction files were checked structurally against the linked official
formats; individual AI clients have not been launched to test automatic loading.

## Open decisions and next actions

1. Confirm organizer rules for preparation, existing code, AI use and submission.
2. Agree on target users, the problem and one core user journey in `PROJECT.md`.
3. Select the minimum stack and define component boundaries and file ownership.
4. Implement and verify one complete MVP journey, then prepare the demo.

## Active handoffs

No implementation task is assigned yet. Replace the placeholders when handing off
substantial work; mark completed handoffs and remove stale entries.

| Task | Owner | Files and interfaces | Checks and result | Blocker or next action |
| --- | --- | --- | --- | --- |
| TBD | TBD | TBD | TBD | TBD |
