# Bus 29 database snapshot: 24 October 2026, 16:55 UTC

A frozen, read-only copy of what the API saw in Tiger Data at 16:55:34 UTC
(17:55 BST), so the bus 29 demo numbers can be reproduced after the live database
keeps growing. Recorded public TfL predictions; arrivals are inferred, not measured.

- Written by [`backend/tools/export_db_snapshot.py`](../../../backend/tools/export_db_snapshot.py)
  through `app.db.load_snapshot`, the same loader as the API cache. No credentials.
- 373 database polls, 13:49:34-16:55:25 UTC (shared by all configured routes).
- `bus-29-outbound-mornington-crescent-tottenham-court-road`: 26 usable segments,
  31 origin events, origins 13:49-16:32 UTC.
- `bus-29-outbound-finsbury-park-tottenham-court-road`: 18 usable segments,
  32 origin events, origins 14:06-16:00 UTC.

Per route: `segments.csv` (the `get_segments` view), `origin_events.csv` (every
origin departure, usable or not) and `coverage.json`. Shared: `poll_times.csv`
(the poll ledger the model uses for coverage) and `summary.json`.

## Time-of-day window check (in sample)

Mornington Crescent -> Tottenham Court Road. Loaded with `curves.to_segments`,
then `model.departure_curve` (90-minute window, 200 bootstraps) and
`model.recommend` with default tolerance. Same data, so not calibration.

| Deadline (UTC) | ±30 min: runs per departure / ok points | ±60 min: runs per departure / ok points | ±60 advice (conservative) |
| --- | --- | --- | --- |
| 14:30 | 0-9 / 0 | 1-15 / 1 | none meets tolerance |
| 15:00 | 1-10 / 0 | 6-20 / 31 | 14:34, p=0.93 (14:32) |
| 15:30 | 6-13 / 0 | 9-20 / 61 | 15:05, p=0.91 (15:02) |
| 16:00 | 7-13 / 0 | 15-20 / 91 | 15:34, p=0.92 (15:32) |
| 16:30 | 4-13 / 0 | 10-20 / 71 | 16:09, p=0.93 (16:07) |

With ±30 there is never any advice. The live API after this snapshot (more trips)
gave 15:32 UTC, p=0.917 for the 16:00 deadline. Data provided by Transport for London.
