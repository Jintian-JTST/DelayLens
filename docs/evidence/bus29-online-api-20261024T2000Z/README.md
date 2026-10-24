# Bus 29: online API curl evidence (24 Oct 2026, ~20:00 UTC)

Captured at the time in `captured_at_utc.txt` by B-claude on a macOS laptop, main `2d7e51c`.
API: `uvicorn app.main:app` on `127.0.0.1:8000` with `DATABASE_URL` from the ignored
`backend/.env` (live Tiger Data views, read-only). No `SNAPSHOT_DIR`. No keys or connection
strings appear in these files.

- `health.json`, `routes.json`: `/api/health`, `/api/routes`.
- `departure-curve-1600Z.json`: `POST /api/departure-curve`, bus 29 Mornington Crescent ->
  Tottenham Court Road, deadline 2026-10-24T16:00:00Z, walk 5+5 min, tolerance 0.10.

Result: status `ok`, 54 recorded trips (14:49-20:48 London time), recommended depart
15:22 UTC, p_on_time 0.9174. This matches the 15:22Z / 0.9174 reported by B and D earlier.

Recorded TfL predictions replayed; arrivals are estimated, not measured; not yet calibrated.
Not covered: browser screenshots of the online UI (offline-snapshot screenshots are in
`../bus29-browser-20261024/`), `/api/ask`, public deployment.
