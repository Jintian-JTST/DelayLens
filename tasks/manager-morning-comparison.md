# Task: Morning source comparison (T16 takeover)

- Task ID: T42, linked to M's T16
- Owner: PROJECT_REVIEWER (Codex manager)
- Branch: `docs/morning-db-comparison`
- Status: database comparison verified; new standalone handoff pending
- Contract: separate database/standalone provenance; preserve locked stage data

## Scope and evidence

Verified PR70's candidate manifest and all eight listed file sizes/hashes,
confirmed only a new folder was added, and checked the old snapshot tree stayed
unchanged. Reran the old/new T10 comparison and separate offline API processes.
All 91 Saturday 17:00 curve points, including bands, agree; advice remains
16:22/p=0.9174. Current source dates and preliminary Brier differences are in the
[comparison package](../docs/evidence/bus29-morning-comparison-20261025/README.md).

No external API call or database write was made during the model/API comparison.
The separate candidate export was supplied by B and independently checked here.

## Remaining work

The new D standalone package is not delivered. Do not mark T42 fully complete,
pool its reported counts with database runs, or replace the old standalone source
with a status message. Verify the new source/hashes and add its separately dated
results when it arrives. Keep the 20:25Z default and its existing demo claims.
