# Task: Offline pull request checks

- Task ID: chat-ci-handoff
- Owner (person / AI tool): Jintian-JTST / Codex CI subagent
- Branch: `codex/chat-ci-handoff`
- Status: implementation and local checks complete; awaiting integrator review
- Integrator / reviewer: D-CodeX with B
- Plan / contract reference: PLAN sections 6.4 and 7; AGENTS testing and handoff rules

## Outcome and acceptance criteria

Run the existing backend tests and Ruff, and frontend tests and production build,
on pushes and pull requests. Use committed dependency locks. Do not require live
services, credentials, deployment rights or an application change.

## Ownership and dependencies

- Owned files: `.github/workflows/ci.yml` and this task record only.
- No API, model, data, package manifest or lockfile changes.
- Ubuntu jobs use Python 3.11, uv 0.13.5 and Node 24. Existing real-database and
  real-Gemini tests remain explicit opt-in tests and are excluded from this
  offline workflow; the workflow supplies neither service credentials nor opt-in.
- Checkout credentials are not persisted; workflow permissions are `contents: read`.
- Shared progress updates belong to the integrator; this branch does not edit them.

## Handoff

- Base: `134dafb`; no commit or push performed by this subagent.
- Official action tags and full commit IDs checked on 24 October 2026:
  [checkout](https://github.com/actions/checkout/releases),
  [setup-node](https://github.com/actions/setup-node),
  [setup-uv](https://github.com/astral-sh/setup-uv).
  Commands follow [Astral's GitHub Actions guide](https://docs.astral.sh/uv/guides/integration/github/).
- Checks actually run on Windows / PowerShell 7.6.5 / Python 3.11.9 /
  Node 24.13.0 / uv 0.13.5, from this isolated worktree:
  - `uv sync --locked --group dev --offline`: passed from the existing local
    cache, creating only this worktree's backend virtual environment.
  - `python -m pytest -q --strict-markers -m "not live_db and not live_gemini"`
    from `backend/`, using the already-installed project Python: **196 passed,
    28 live-service tests deselected, 6 subtests passed** in 78.50 seconds.
    One existing Starlette/httpx deprecation warning remains.
  - `ruff check app tests ingest ../deploy` from `backend/`: passed.
  - `npm test` from `frontend/`: **11 passed**.
  - `npm run build` from `frontend/`: TypeScript and Vite production build passed.
    Frontend checks reused a private copy of the existing local `node_modules`;
    they do not prove a clean Ubuntu `npm ci` installation.
  - Parsed YAML and checked both triggers, read-only permission, two bounded
    Ubuntu jobs, full action SHA pins and absence of secret references or
    privileged PR triggers. `git diff --check` passed; both lockfiles unchanged.
- Unverified: GitHub runner execution, fresh Ubuntu dependency installation and
  repository branch-protection requirements. A workflow file is not a green run.
- Next action: integrator reviews and opens a PR; inspect the actual GitHub
  checks before treating CI as verified.
