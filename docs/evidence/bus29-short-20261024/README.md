# Bus 29 standalone recording: 24 October 2026

Recorded public TfL predictions from the standalone recorder (no database), route
`bus-29-outbound-mornington-crescent-tottenham-court-road`: eight consecutive stops,
Mornington Crescent Station -> Tottenham Court Road Station, towards Trafalgar Square.

- Capture 15:46:18-17:16:30 UTC (16:46-18:16 BST), the full planned 90 minutes.
- 179/179 polls succeeded, 77,419 raw prediction rows; 179 of 181 30-second slots,
  with one 47-second gap (17:13:23-17:14:10 UTC) recorded in `quality.json`.
- 7 independent estimated trips from 7 vehicles, 608-1049 s end to end;
  162 stop events (91 estimated, 71 uncertain). Support state `low_data`.
- `data_gate` pass. `acceptance_gate` is `pending_source_trace_review`: no trip has
  been source-traced yet (`audit_review.json` is empty). Arrivals are inferred from
  predictions, not measured; no calibration is claimed.

Files follow the bus 24 handoff layout, so `model.load_handoff` reads this folder
directly (checked: 7 rows, 7 used, 3 unconfirmed origin departures):
[segments.csv](segments.csv), [quality.json](quality.json), [route.json](route.json),
[stop_events.json](stop_events.json) and [audit_review.json](audit_review.json).
Raw polls and source ZIPs stay in the recording checkout's ignored run directory.

The demo uses the database path instead, which has more trips on the same segment:
see [the 16:55 UTC database snapshot](../bus29-db-snapshot-20261024T1655Z/README.md).

Data provided by Transport for London.
