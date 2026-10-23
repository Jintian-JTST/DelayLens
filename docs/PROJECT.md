# OxHack 2026 — Project Brief

Status: repository preparation. Fill in the product brief with the team before
generating application code or choosing dependencies. `TBD` means undecided.

## Product and scope

| Item | Team decision |
| --- | --- |
| Project name | TBD |
| Target users | TBD |
| Problem and user value | TBD |
| Core user journey | TBD |
| Must-have MVP features | TBD |
| Explicitly out of scope | TBD |
| Optional features after the MVP works | TBD |
| Success criteria | TBD |

## Event constraints

Record the current rules from the organizers, including permitted preparation,
existing code and AI use, sponsor requirements, attribution and submission format.
Add the source and verification date; do not assume these requirements.

| Constraint | Confirmed requirement and source |
| --- | --- |
| Coding and preparation window | TBD |
| Existing code, AI tools and attribution | TBD |
| Challenge or sponsor track | TBD |
| Submission deadline and deliverables | TBD |

## Technology and architecture

| Area | Decision and reason |
| --- | --- |
| Frontend and interface | TBD |
| Backend and runtime | TBD |
| Data model and storage | TBD |
| External APIs and authentication | TBD |
| Hosting and deployment | TBD |
| Package manager and lockfile | TBD |
| Component boundaries and API contracts | TBD |

Document required environment variable **names** and safe example values when an
integration is selected. Real credentials belong in ignored local files or the
selected platform's secret store.

## Reproducible setup (complete when the stack is selected)

| Item | Shared contract |
| --- | --- |
| Supported OS, shell and runtime versions | TBD; record platform-specific exceptions |
| Package manager version and dependency install command | TBD |
| Development, test, lint and build commands | TBD |
| Required services and local initialization | TBD |
| Environment variable names and safe example file | TBD |
| Concurrent instance configuration (ports, databases, outputs) | TBD |

Use repository-relative paths and explicit working directories. Specify supported
version ranges and exact commands, and label shell-specific alternatives. Personal
paths and credentials stay on each machine; follow [CONTRIBUTING.md](../CONTRIBUTING.md).

## Acceptance and demo plan

- [ ] Define the user's starting state, core action and observable successful result.
- [ ] Define important failure cases and the expected recovery behavior.
- [ ] Record real run, test and build commands after the stack is chosen.
- [ ] Prepare the demo sequence, data provenance, prerequisites and fallback plan.
- [ ] Verify submission links, repository access and required attribution.

## Team and ownership

| Responsibility | Owner | Files or interface |
| --- | --- | --- |
| Product and demo | TBD | TBD |
| Implementation and integrations | TBD | TBD |
| Verification and submission | TBD | TBD |
| Integration and shared documentation | TBD | TBD |

Track independently owned tasks using [the task template](tasks/TEMPLATE.md).

## Decision log

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-10-23 | Use root `AGENTS.md` with thin tool-specific entry points | Share one set of coding rules across AI tools. |
| 2026-10-23 | Preserve the existing MIT license and original repository content | Extend the existing repository. |
| 2026-10-23 | Leave the product idea and technology stack undecided | Prepare collaboration documents before the team chooses what to build. |
| 2026-10-23 | Use portable shared settings and independent task workspaces | Support different computers and concurrent human/AI contributions. |

Keep implementation status and handoffs in [PROGRESS.md](PROGRESS.md).
