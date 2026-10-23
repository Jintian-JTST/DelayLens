# OxHack 2026 — Progress and Handoff

Updated: 2026-10-23 (Europe/London).

## Current milestone

Repository preparation. Product requirements and technology decisions await the
team's brief in [PROJECT.md](PROJECT.md).

## Completed

- Initialized the repository with shared AI instructions and project documents.
- Added canonical AI coding rules in root `AGENTS.md` and thin entry points for
  Copilot, Claude Code, Gemini CLI and Cursor.
- Added a project brief, decision log and this progress/handoff document.
- Extended the README and inherited Python `.gitignore`; preserved `LICENSE`.
- Added cross-platform onboarding, local/shared configuration boundaries, independent
  task workspaces, a per-task handoff template and shared text-file conventions.
- Corrected inherited ignore rules that hid library source directories.

## Verification

- Passed: expected file inventory, UTF-8 content, local Markdown links and imports,
  and Cursor rule frontmatter.
- Passed at initialization: original README and Python ignore rules retained; MIT
  license unchanged. The later portability update removes broad library ignores.
- Passed: ignore checks for 13 local credential/generated paths and retention checks
  for 17 example, lockfile and project paths.
- Passed: `git diff --check`.

There is no application tooling yet; application tests, lint and builds are not
configured. Instruction files were checked structurally against the linked official
formats; individual AI clients have not been launched to test automatic loading.

Portability review completed:

- Passed: 14 intended files, UTF-8, exact-case local links/imports and no personal
  absolute paths in shared files.
- Passed: 12 local/generated paths ignored; 30 source, template, portable configuration
  and lockfile paths retained, including nested `src/lib/` directories.
- Passed: fresh offline clones in paths containing spaces and Unicode, with both
  `core.autocrlf=true` and `false`; LF text/shell scripts, CRLF Windows command
  scripts and unchanged binary fixture bytes.
- Passed: documented worktree commands and isolation of task working files/staging.

These checks ran on Windows. macOS/Linux execution and each AI client's automatic
rule loading remain unverified; use the explicit `AGENTS.md` reading fallback.

## Open decisions and next actions

1. Confirm organizer rules for preparation, existing code, AI use and submission.
2. Agree on target users, the problem and one core user journey in `PROJECT.md`.
3. Select the minimum stack and define component boundaries and file ownership.
4. Implement and verify one complete MVP journey, then prepare the demo.

## Active handoffs

No implementation task is assigned yet. Create a separate file per task using
[tasks/TEMPLATE.md](tasks/TEMPLATE.md); the integrator lists those files here and
maintains the milestone summary after integration.

| Task record | Owner | Status | Next action |
| --- | --- | --- | --- |
| Not assigned | TBD | Awaiting product brief | Agree on an MVP and task ownership |
