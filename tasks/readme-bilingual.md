# Task: Bilingual README and demo user guide

- Task ID: readme-bilingual
- Owner (person / AI tool): Jintian-JTST / Codex
- Branch: `codex/d-live-ops` (current checkout; no branch switch or commit)
- Status: documentation complete; local checks passed
- Integrator / reviewer: repository maintainer
- Plan / contract reference: owner-requested bilingual usage manual; existing PLAN scope

## Outcome and acceptance criteria

Keep English first in README.md and add explicit English/Chinese anchor links.
Provide runnable frontend/backend instructions, actual UI controls, configured
route choices, optional services, data-support limits and troubleshooting in
both languages. Preserve existing project, evidence, attribution and licence text.

## Ownership and dependencies

- Owned files: `README.md`, this task record.
- No application, API, schema, lockfile or shared progress changes.
- Sources: current frontend source/package/config, backend source/config and
  project/role documents. Historical reports are not new external-service checks.
- Local configuration: existing backend and frontend environment examples only.

## Handoff

- English remains the default first section; Chinese lives in the same README.
- Added labelled-demo and full-app walkthroughs, control descriptions, recorded-hour
  selection, optional Ask/live services, evidence states and troubleshooting.
- Corrected stale README claims about the absent model adapter and missing short
  bus 29 configuration using current source. No new data coverage is asserted.
- Checks actually run: Python documentation validation passed for 29 local
  links/anchors, English-first section order, UTF-8, paired code fences, trailing
  whitespace, npm script names, actual UI labels and all five configured route
  endpoints. `git diff --check` passed. Reviewed the README diff; original
  project/evidence/attribution/licence sections are retained.
- Environment: Windows / PowerShell 7.6.5 / Python 3.11.9 / Node 24.13.0.
- Unverified: app/browser interaction, external services, deployment; no recorder
  was started. `uv` is unavailable on PATH in this session.
- Next action: maintainer reviews documentation alongside the integrated build.
