# Online mode: default form vs `/api/departure-curve` (24 Oct 2026, ~20:03 UTC)

Captured by B-claude on a macOS laptop, main `cb5af53`. API: `uvicorn` on `127.0.0.1:8000`
with `DATABASE_URL` from the ignored `backend/.env` (live Tiger Data, read-only, no
`SNAPSHOT_DIR`); frontend: `npm run dev` on `127.0.0.1:5173` (proxies `/api`). No keys in
these files. No DEMO label appears on the page (checked in the DOM: "DEMO" absent).

- `online-default-1280.png`, `online-default-390.png`: headless Chrome screenshots of the
  untouched page, "Service connected".
- `default-form-departure-curve.json`: the same request the form sends (route, deadline,
  walk 5+5, tolerance 0.10) replayed with curl.

The default form is the first route, Victoria line Brixton -> Oxford Circus (Tube), arrive by
2026-10-24 23:00 Europe/London (22:00 UTC). UI: "Insufficient data", "120 trips recorded
(Sat 24 Oct 14:49 - 20:47, London time)", no recommendation. curl: `insufficient_data`,
0 points, no recommendation, same 120-trip basis. They agree.

## Read-back times

Default-form screenshots and curl: about 20:03 UTC (`captured_at_utc.txt`; Brixton 120 trips).
Bus 29 UI screenshot and its curl: about 20:06 UTC (page footer "Updated 21:06" BST); 54 trips,
last trip 20:48 London. A different reader at a different moment (D-CodeX: 53 trips at 19:58 UTC)
will see a different count because recording continues.

## Bus 29, online UI (added ~20:06 UTC, live data had grown to 54 trips)

Driven in headless Chrome over DevTools on the real page: route set to Mornington Crescent ->
Tottenham Court Road (bus 29), "Try a recorded-hour example" clicked (fills arrive by
2026-10-24 20:00 Europe/London = 19:00 UTC), "Update my journey" clicked. Files:
`online-bus29-recorded-example-1280.png` and `bus29-recorded-example-departure-curve.json`
(the same request replayed with curl).

UI and API agree: "Low data", 54 trips (14:49-20:48 London), advice "Aim to leave by 18:53,
100%" (curl: 17:53 UTC = 18:53 BST, p_on_time 1). "Low data" because some departures have
fewer than 15 trips; the page says the estimate is preliminary. No DEMO label (DOM checked).
The live "Next to arrive" panel on the page is a real-time TfL feed, not part of the curve.

Not covered: `/api/ask`, public deployment, the 90%-tolerance advice for 16:00 UTC on the UI
(that figure is in `../bus29-online-api-20261024T2000Z/` as curl). Recorded TfL predictions
replayed; arrivals estimated, not measured; not yet calibrated.
