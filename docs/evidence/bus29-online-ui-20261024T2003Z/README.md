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

Not covered: the default form is not bus 29, so it shows no advice. Bus 29 online numbers are
in `../bus29-online-api-20261024T2000Z/` (curl only), and bus 29 offline UI screenshots in
`../bus29-browser-20261024/`. No online-UI screenshot of bus 29 advice was saved: the browser
tool here cannot write screenshots of a clicked state to disk. Recorded TfL predictions replayed;
arrivals estimated, not measured; not yet calibrated.
