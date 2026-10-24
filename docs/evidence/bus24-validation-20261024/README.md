# Real TfL bus 24 validation: 24 October 2026

This is recorded public TfL evidence, not synthetic demo data. The owner shortened
this run from 90 to 60 minutes. Capture: 13:53:05-14:53:10 UTC (14:53-15:53 BST).

- 121/121 HTTP polls succeeded; 24,465 raw prediction rows; no polling gaps.
- Four complete independent estimated trips over seven ordered stops, Warren
  Street -> Leicester Square, 24 inbound towards Pimlico.
- Three examples were checked against captured endpoint prediction sequences
  and advancing-source post-ETA absence frames; agent review, not human signoff.
- Four trips remain `insufficient_data`. No calibrated probability, actual-arrival
  measurement, bus 29 coverage or real-data API/UI integration is established.

[segments.csv](segments.csv) is the M/B handoff: one inferred journey per row.
[quality.json](quality.json) records coverage, exclusion reasons and count units.
[stop_events.json](stop_events.json) lists every inferred stop event (any quality)
and [route.json](route.json) the stop pattern; `model.load_handoff` needs both to
censor origin departures without a usable segment.
[audit_review.json](audit_review.json) identifies the reviewed source-derived IDs.
[export-verification.json](export-verification.json) records final ZIP checksums,
31 passing checks in a clean source extraction and an identical offline replay.
The complete raw JSONL/gzip, event provenance, snapshot and source ZIPs are retained
in the recording checkout's ignored run directory and delivered separately. Raw
archives, secrets and local machine configuration are not committed here.

Inference and independent offline replay instructions:
[ingestion README](../../../backend/ingest/README.md).

Data provided by Transport for London.
[Official data information](https://tfl.gov.uk/info-for/open-data-users/our-open-data).
