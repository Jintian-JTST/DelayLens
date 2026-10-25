# DelayLens: Devpost submission draft

Owner: M (Olivia). Fill in the ___ blanks on Sunday 09:30–10:30 and submit 11:00–11:15.
Every number below comes from the final snapshot `bus29-db-final-20261024T202558Z`
(verified on main; see [tasks/model.md](../tasks/model.md)) unless marked. Judge answers
with evidence links: [judge-qa.md](judge-qa.md).

**Tagline:** When should I leave? A journey planner that tells you how often it's right,
and says so when it doesn't know.

## Inspiration

Countdown boards and journey planners tell you when the bus *should* come. Everyone has
seen "2 min" turn into eight. We wanted to answer a different question: if I need to be
there by 5pm, when should I leave, and how sure can I be?

## What it does

Pick a London bus route, your deadline and your walking times. For every departure in
the 90 minutes before your deadline, DelayLens estimates your chance of arriving on
time from trips we actually recorded, and recommends the latest departure that meets
your risk tolerance (default: at most 10% late).

On bus 29 (Mornington Crescent → Tottenham Court Road) with a 5pm Saturday deadline, it
says **leave by 16:22 for an estimated 92% chance** (frozen snapshot of our recording; the live database gives the same).
You can also just ask in plain English, by typing or by voice. Gemini interprets the
question; our model computes every number. A schematic journey map shows the
recommended walk, wait and ride, and marks where the uncertainty is: the wait at the
stop and the ride as a whole. We do not claim delays at individual stops.

When the evidence is thin, it says so:

- fewer than 5 recorded trips: no estimate, only counts;
- 5–14 trips: a preliminary estimate and no recommendation;
- 15+ trips: an estimate, a 90% band and a "leave by" time.

## How we built it

- **Data (D):**
  - A recorder polls TfL's live arrival predictions every 30 s into Tiger Data
    (TimescaleDB hypertable, a real-time continuous aggregate for hourly coverage,
    and a columnstore policy that converts chunks after 2 hours; we claim no
    compression ratio), with raw JSONL backups.
  - Stop events are inferred conservatively from near-stop predictions, and paired
    into origin → destination trips with quality labels.
  - ___ D's data/infra paragraph: D-claude supplies the verified poll totals, UTC
    start and end, and backup location after its export check. Keep the reported
    22-minute recorder gap (22:11–22:33Z). Do not fill in estimates. ___
- **Model (M):**
  - Empirical replay in NumPy. Every recorded minute within ±60 min of your departure
    boards the first recorded bus and adds your walks.
  - Minutes that fall in recording gaps, or behind a bus whose trip we couldn't
    confirm, are set aside instead of counted as late.
  - A bootstrap over whole bus runs gives the 90% band. A curve takes about 8.5 ms.
- **Backend and Gemini (B):** A FastAPI service reads Tiger Data into an in-memory
  snapshot of recorded bus trips, refreshed every 60 s; a failed refresh keeps serving
  the last good snapshot. Gemini is used only for Ask: it maps a question to one
  validated function call, with a 4 s timeout and a fallback model. It never produces
  numbers; the answer is a template filled from our model. An offline snapshot mode
  runs the whole demo without a database. On the demo laptop, /api/departure-curve
  takes about 4 ms at p95 (smoke check, 20 requests; re-measure Sun 08:30).
- **Frontend:** React + TypeScript + Vite. The curve is a hand-built SVG with keyboard
  exploration and a data table. Risk and "+5/+10/+15 min" update instantly in the browser.
  - The journey map is our own SVG of bus 29's 8 stops. It is not TfL artwork.
  - Ask is enabled only when the server reports a Gemini key (`/api/health`
    `ask_available`).
  - Voice input uses the browser's Web Speech API. In Chrome, audio is sent to
    Google's speech service.

## Challenges

- TfL gives predictions, not arrivals, so arrival times have to be inferred.
- Separating "the bus was late" from "we stopped seeing it".
- UK clocks went back at 02:00 on Sunday 25 Oct, so everything is stored in UTC.
- A ±30-minute window never gathered enough trips for advice; widening to ±60 had to
  be disclosed.

## Accomplishments

- A real pipeline from live TfL data to an on-screen decision.
- A model that refuses to guess.
- A held-out backtest. In it, when we said about 92% we were on time about 91% of the
  time (bus 29 from Mornington Crescent: Brier 0.130, 1,104 overlapping outcomes, 49 runs;
  preliminary). On the longer branch from Finsbury Park: 93% predicted, 95% observed.

## Limitations (please read)

- Arrival times are inferred from TfL's live predictions; we did not measure actual
  arrivals.
- The demo snapshot covers one Saturday afternoon and evening on bus 29 (24 Oct 2026,
  about 14:50–21:00 London).
- A later snapshot (06:07Z) adds Saturday evening plus 6 and 3 runs from the first hour
  of Sunday. It is not used for the demo.
- Neither snapshot says anything about weekdays or rush hours.
- Below 15 recorded trips there is no recommendation; below 5, only counts.
- The calibration check scores the model against the same inferred events, not
  measured arrivals, and is reported as preliminary.
- Our backup standalone recorder collected only 5 usable bus 29 trips (below our
  15-trip target), so it cannot independently confirm the database counts.
- The journey map cannot locate delays at individual stops. Our trips are recorded
  origin to destination only.
- Voice input and Gemini answers were tested only with mocks and a local stub, with no
  real microphone or live Gemini call. ___ Update this line if the rehearsal tests
  them live. ___

## What's next

Longer recordings across weekdays and peaks, more routes, measured arrivals for real
validation, and multi-leg journeys.

## Built with

Python, NumPy, FastAPI, Tiger Data (TimescaleDB), Gemini API, React, TypeScript, Vite,
Web Speech API, TfL Unified API.

## Links and tracks

- Repo: https://github.com/Jintian-JTST/OxHack
- Demo video: ___ (backup video, owner ___)
- Try it: none (no public deployment; local demo, see README "Run the API")
- Tracks to tick: HRT (Data for Predictions & Decision Making), Tiger Data, Gemini API,
  Built with Delta. ___ Check that each is selected on Devpost and needs no separate form.
- Delta thread links: ___
- Data attribution: "Data provided by Transport for London." This is the notice
  listed in TfL's [live bus arrivals branding guidance](https://tfl.gov.uk/info-for/open-data-users/our-open-data)
  (instant and stream sections; checked 25 Oct 2026). The app also retains its
  existing general open-data credit. This source check does not establish full
  compliance with every term or permission to use TfL logos or imply endorsement.

## Before submitting: open items and owners

Checked against main `f57eb65` on Sun 25 Oct by M (T43). Fill these in by hand. Do not
guess links or numbers.

| Item | Owner | Status |
| --- | --- | --- |
| Demo video link | Olivia names who records it; the team records it | Not recorded yet |
| Delta thread links | Olivia, from the team's Delta threads | Not collected |
| Devpost track selections (HRT, Tiger Data, Gemini API, Built with Delta) | Olivia, confirmed with the organisers | Not confirmed |
| D's data/infra paragraph and verified totals | D-claude, after the export check | Waiting for the export |
| Live Gemini Ask test (needs `GEMINI_API_KEY` in `backend/.env`) | Olivia at the 10:30 rehearsal | Not tested |
| Real-microphone test (one `/api/ask` POST only) | Olivia at the 10:30 rehearsal | Not tested |
| Latency re-measure on the demo laptop | B-claude, 08:30 | 4 ms p95 from the earlier smoke check |
| Standalone count for task 1 (≥15 trips) | D-claude | Last verified: 5 trips |

The demo stays on the locked 20:25Z snapshot.
- The 06:07Z candidate snapshot (80 and 70 runs, including 6 and 3 Sunday runs) leaves
  Sat 17:00 unchanged (16:22, p=0.9174). See `docs/evidence/bus29-morning-comparison-20261025`.
- Keep the limitations above when copying into Devpost.
