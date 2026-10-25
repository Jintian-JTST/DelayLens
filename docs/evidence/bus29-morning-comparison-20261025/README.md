# Morning database comparison — 25 October 2026 (T42, database part)

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

D's new overnight standalone handoff has not been delivered at this checkpoint.
Its reported four trips are not independently accepted, and are not pooled with
these counts or the older five-trip standalone package. T42 therefore remains
partial until that source handoff can be verified.

## Reproduce

From `backend/` on main containing PR67 and PR70, without database or API keys:

```text
python -m tools.rerun_t10 docs/evidence/bus29-db-final-20261024T202558Z docs/evidence/bus29-db-20261025T0607Z
```

The API comparison used separate FastAPI TestClient processes with each folder
as `SNAPSHOT_DIR`, querying the short bus29 route with deadline
`2026-10-24T17:00:00+01:00`, walks5/5 and tolerance0.1. No network or external model call was made.
