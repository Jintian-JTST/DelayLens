# Task: Branch inventory and reviewable integration

- Task ID: branch-integration
- Owner (person / AI tool): Jintian-JTST / Codex
- Branch: `codex/integrate-branches`
- Status: verified; ready for owner PR review
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
- Checks actually run: Windows, PowerShell 7.6.5, Python 3.11.9, Node 24.13.0.
  Locked uv install passed; pytest: 93 passed, 7 opt-in live-DB tests skipped,
  one Starlette/httpx warning. Ruff passed after small lint-only fixes (imports,
  UTC aliases, literals, explicit subprocess check and equivalent gzip contexts).
  Added three integration regressions. UTF-8/JSON/paths/conflicts/whitespace and
  45 exact-case Markdown links across 54 files passed; Git whitespace passed.
  No live service/database/recorder/deployment checks were performed.
- Next action: finish integration, verify, commit and push the integration branch,
  then create the review PR. Preserve main and all source branches.

## Branch inventory at review baseline

| Branch/ref | Captured tip | Disposition |
| --- | --- | --- |
| `origin/main` | `4da089c` | PR base; left unchanged |
| `origin/codex/revise-ingestion-plan` | `dd762e8` | Already merged by PR #2; no duplicate merge |
| `origin/feat/data` | `82ae093` | Included by API merge; full ancestry retained |
| `origin/feat/api` | `ab9012c` | Integrated with conflicts resolved |
| `origin/feat/model` | `f12e4de` | Integrated; declared NumPy dependency supplied |
| local `main` | `73006fa` | Older ancestor of remote main; preserved |
| local `feat/data` | `ee055d6` | Older ancestor of remote data; active worktree preserved |
| local `codex/revise-ingestion-plan` | `dd762e8` | Root checkout preserved |

No frontend branch was exposed by Git fetch/GitHub inventory. No branch deletion,
force push, main update, production deployment or automatic PR merge is part of
this task. Review the imported inference limitations before approving model use.

Final refetch showed unchanged source tips. Ancestry checks confirmed all seven
local/remote source refs in the table are included in the integration HEAD.
Final tracked-file validation: 54 files, 45 exact-case local Markdown links,
valid JSON/UTF-8, no conflict markers, machine paths or credential signatures.
