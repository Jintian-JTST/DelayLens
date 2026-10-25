# Morning source comparison — 25 October 2026 (T42)

Data provided by Transport for London.

The manager independently checked the locked [20:25Z snapshot](../bus29-db-final-20261024T202558Z/)
and the new [06:07Z candidate](../bus29-db-20261025T0607Z/) from PR70 head
`79b87d30837cbc024cb5cceef42e84d18475d5f8`. This is a read-only comparison of
inferred database segments. It is not a standalone recording or measured-arrival validation.

## Verified results

| Item | Locked 20:25Z | Candidate 06:07Z |
| --- | --- | --- |
| Short / long database segments | 56 / 48 | 80 / 70 |
| Short segments by London date | 56 Saturday | 74 Saturday + 6 Sunday |
| Long segments by London date | 48 Saturday | 67 Saturday + 3 Sunday |
| Short Brier (outcomes / scored runs) | 0.1296 (1104 / 49) | 0.1276 (1584 / 67) |
| Long Brier (outcomes / scored runs) | 0.1318 (760 / 42) | 0.1168 (1128 / 56) |
| Sat 24 Oct 17:00 London, walks 5/5 | Leave 16:22, p=0.9174 | Leave 16:22, p=0.9174 |
| Sat 24 Oct 15:30 London | No qualifying recommendation | No qualifying recommendation |

The Saturday 17:00 API responses have identical 91 curve points, including
confidence bands. Their provenance text differs because the snapshots differ.
All eight candidate manifest file sizes/hashes and the separately reported
manifest digest were verified. The locked snapshot's Git tree is unchanged.
[verification.json](verification.json) records these checks; [t10-output.txt](t10-output.txt)
contains the full date/BST/GMT/offset hourly breakdown and preliminary calibration bins.

The candidate includes a few Sunday-local-date runs: UTC Saturday timestamps
must not all be described as Saturday London samples. The Saturday 17:00 answer
was checked directly; no broader cross-date pooling or calibration claim is made.
Both Brier results score inferred events and remain preliminary.

## Decision and remaining evidence

Keep the locked 20:25Z stage default. PR70 is accepted as a separate candidate;
no demo launcher or default was changed. Larger database counts do not replace
independent samples or prove calibration.

## Independent overnight handoff accepted

PR74 head `7faef4631991c7a542b4a81825e06357ea20e1d2` supplies the separate
[overnight package](../bus29-independent-20261025T0545Z/). The manager verified
all 14 outer manifest entries, both ZIP digests and internal manifests/CRCs, then
replayed all 685 raw polls using the reviewed repository derivation code (identical
to the archived source). The replay exactly reproduces four CSV segments and 88
stop events. Counts recomputed from raw polls: 683 successful, two failed,
442 empty successes and 48,819 prediction rows. Empty responses do not establish
why predictions were absent.

The run spans 24 Oct 22:33:21Z to 25 Oct 04:59:21Z. Inferred origin-hour bins are
24 Oct 23:00 BST: two; 25 Oct 00:00 BST: two. The model loads all four rows;
these support no recommendation and remain below 15. They are separate from
both the older five-trip standalone run and all database counts. No pooling,
measured-arrival validation or calibration improvement is claimed.

[standalone-verification.json](standalone-verification.json) records the independent
checks; [standalone-t10-output.txt](standalone-t10-output.txt) records model loading
and the unchanged locked-snapshot baseline. T42's source comparison is complete;
the independent sample target remains unmet. The recorded pre-run gap
22:11–22:33Z is producer-reported, not independently reconstructed from this run.

## Reproduce

From `backend/` on main containing PR67 and PR70, without database or API keys:

```text
python -m tools.rerun_t10 docs/evidence/bus29-db-final-20261024T202558Z docs/evidence/bus29-db-20261025T0607Z
```

The API comparison used separate FastAPI TestClient processes with each folder
as `SNAPSHOT_DIR`, querying the short bus29 route with deadline
`2026-10-24T17:00:00+01:00`, walks5/5 and tolerance0.1. No network or external model call was made.
