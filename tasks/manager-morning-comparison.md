# Task: Morning source comparison (T16 takeover)

- Task ID: T42, linked to M's T16
- Owner: PROJECT_REVIEWER (Codex manager)
- Branch: `docs/accepted-overnight-comparison`
- Status: complete; database and standalone sources independently verified
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

## Standalone acceptance and limits

PR74 supplied both raw-data and source ZIPs. The manager checked 14 outer hashes,
both archive digests/internal manifests and CRCs, scanned decompressed contents
for secrets, and replayed 685 polls with reviewed derive.py. Four segments and
88 events exactly match the export; the model uses four of four rows and gives
no recommendation. London-hour bins: Saturday 23:00 BST two, Sunday 00:00 BST two.
The old locked snapshot tree and demo defaults are unchanged.

The public comparison records raw checks and rerun output. Documentation links,
manifest integrity and whitespace checks pass; exact-head CI gates the PR merge.
The 15-trip target remains unmet. Human video/Delta/track selections and real
microphone/Gemini acceptance remain separate pending work.
