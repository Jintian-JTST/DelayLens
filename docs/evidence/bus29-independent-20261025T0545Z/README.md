# Independent recording export: bus29-short-20261024T2233205052870Z

Generated 2026-10-25T05:45:50.819657+00:00 from a finished independent bus 29 recording (status completed).
Data provided by Transport for London. TfL arrivals are predictions; the segments here are inferred
from them and are not measured actual arrivals.

- Capture UTC window: 2026-10-24T22:33:21.448657Z to 2026-10-25T04:59:21.643123Z (386.0 min planned).
- Polls: 685 raw, 683 successful, 2 failed.
- Empty successful polls: 442; HTTP failures: {"None": 2}.
  Why polls were empty (for example few night buses) is an inference, not measured; raw responses are kept unchanged in the final data package and the original run directory.
- Independent usable trips: **4**; the 15-trip minimum is NOT met.
- Independent trips by London hour: {"2026-10-24 23:00 BST": 2, "2026-10-25 00:00 BST": 2}.
- Database read-only export: {"snapshot_refreshed_at_utc": "2026-10-25T05:25:19.387302+00:00", "poll_count": 1819, "first_poll_utc": "2026-10-24T13:49:34.840394+00:00", "last_poll_utc": "2026-10-25T05:24:52.778379+00:00"}.
- Database snapshot counts (by London hour in export-report.json) are a different pipeline and are never added to the independent count:
  {"db-short-mornington": 80, "db-long-finsbury": 70}.
- Replay check of the final packages: {"performed": true, "ok": true, "result": {"identical_segments": true, "identical_events": true, "segments": 4, "events": 88, "polls": 685}}.
- Time assumption: UTC in files; London local = BST (UTC+1) until the clock change at 02:00 BST on 25 Oct 2026, GMT after.
  Hour bins above are London natural hours.
- This run is separate from earlier runs (for example 20261024T1721Z and 20261024T2032Z) and from the keyed/night runs started by other sessions; samples are not pooled.
- The data level is not raised by this export; support state is reported as computed (insufficient_data).
- The final data and source zip packages are committed under `packages/` so the replay can be reproduced independently (SHA256 also in `export-report.json` and `MANIFEST.json`).

## Capture gap and scope notes

- This run started at 22:33:21Z after a deliberate stop of all recorders at 22:11:18-22:11:41Z (the recording machine was moved). Gap before this run: independent 22:11:18Z to 22:33:21Z; database poller 22:11:02Z to 22:33:20Z. The earlier independent run 20261024T2032Z was not finalised and is not included here.
- Independent trips fall in London hours 23:00 and 00:00 BST on 24-25 Oct; none fall in the repeated hour created by the clock change (01:00Z = 02:00 BST back to 01:00 GMT), so no hour label is ambiguous.
- Database trips by London hour (separate pipeline, read-only export at the refresh time above):
  - db-short-mornington: 80 trips; by hour: {"2026-10-24 14:00 BST": 1, "2026-10-24 15:00 BST": 9, "2026-10-24 16:00 BST": 12, "2026-10-24 17:00 BST": 8, "2026-10-24 18:00 BST": 10, "2026-10-24 19:00 BST": 6, "2026-10-24 20:00 BST": 9, "2026-10-24 21:00 BST": 6, "2026-10-24 22:00 BST": 10, "2026-10-24 23:00 BST": 3, "2026-10-25 00:00 BST": 6}
  - db-long-finsbury: 70 trips; by hour: {"2026-10-24 15:00 BST": 8, "2026-10-24 16:00 BST": 9, "2026-10-24 17:00 BST": 10, "2026-10-24 18:00 BST": 8, "2026-10-24 19:00 BST": 7, "2026-10-24 20:00 BST": 8, "2026-10-24 21:00 BST": 7, "2026-10-24 22:00 BST": 6, "2026-10-24 23:00 BST": 4, "2026-10-25 00:00 BST": 3}

No reviewer acceptance is implied by this folder; verify MANIFEST.json hashes and re-run the replay with verify_capture.py from the 20261024T1721Z evidence folder if needed.
