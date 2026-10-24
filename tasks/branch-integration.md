# Task: Branch inventory and reviewable integration

- Task ID: branch-integration
- Owner (person / AI tool): Jintian-JTST / Codex
- Branch: `codex/integrate-branches`
- Status: integrating; checks pending
- Integrator / reviewer: Codex prepares; repository owner reviews PR to main
- Plan / contract reference: PLAN.md sections 3, 4, 6; AGENTS.md

## Outcome and acceptance criteria

Inventory every local and remote branch, retain existing work and histories,
resolve compatible integration conflicts, run available checks, and open a PR
targeting main. Do not merge the PR or delete source branches before review.

## Ownership and dependencies

- Owned files: merge conflicts, integration configuration/tests, dependency
  manifest/lockfile, this record and shared progress/setup summaries.
- Main baseline: `4da089c`; includes `codex/revise-ingestion-plan` at `dd762e8`.
- Integrate `feat/data` at `82ae093` via `feat/api` at `ab9012c`, then
  `feat/model` at `f12e4de`. These are captured tips, not live branch locks.
- Existing root checkout and D's data-validation worktree stay untouched.
- No credentials, live database mutation, recorder launch or deployment required.

## Handoff

- Keep main's complete-response raw recorder as `ingest.poller`; preserve D's
  database-backed recorder as `ingest.database_poller`. Update imports and the
  service template together. Their raw formats are different; no automatic
  interchange/replay compatibility is claimed. Only one canonical DB writer.
- Retain main's bus 24 short routes and D's corrected bus 29 origin. Expand the
  database poll defaults so every configured endpoint remains included.
- Consolidate D's historical evidence under `tasks/data-ingestion.md`, explicitly
  distinguishing branch-reported live checks from this integration's checks.
  Move B's record to canonical `tasks/backend-api.md`.
- Model/API data wiring and the revised evidence/calibration policy remain
  incomplete upstream; a branch merge does not establish a working real-data demo.
- Checks actually run: Windows, PowerShell 7.6.5, Python 3.11.9, Node 24.13.0;
  Git branch/history inspection. Test environment being prepared.
- Next action: finish integration, verify, commit and push the integration branch,
  then create the review PR. Preserve main and all source branches.
