# Task: Clean locked-snapshot API measurement (T47, linked T45)

- Owner: PROJECT_REVIEWER
- Branch: docs/clean-demo-api-smoke
- Status: measured and locally verified; exact-head CI/merge pending
- Scope: evidence-only takeover, preserving B's dirty worktree and locked default

B's checkpoint and local branch e31bf98 were inspected; the listener confirmed
it cannot execute. The manager ran the isolated script on clean main1df3f4b.
Health and all24 curve requests (first+3warmups+20samples) preserve the locked
16:22/p0.9174 result without DB or service keys. Local HTTP p95 is4.3087ms,
server p95 is3.54ms; first curve request23.2415ms excludes process startup.

[Evidence and reproduction](../docs/evidence/demo-api-smoke-20261025/README.md)
contain all samples, method and environment. This does not accept any physical
rehearsal, public network, live Gemini or microphone claim. M updates PR76 from
these verified results after this evidence handoff; T45 remains B's task to close.
