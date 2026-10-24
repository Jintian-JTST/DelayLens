# DelayLens — Implementation Plan

> **When should I leave?** Tell DelayLens when you must arrive, as a form or in
> your own words. It shows the probability of arriving on time for each
> departure time and tells you when to leave.

Written 2026-10-24 during OxHack 26. Requirements come from the opening-ceremony
slides and the official schedule. Anything still to confirm is listed in §10.

**Contents:** 0 Tracks & judging · 1 First priority · 2 Scope · 3 Data ·
4 Model · 5 Ask DelayLens (Gemini) · 6 Architecture · 7 Team & ownership ·
**8 Schedule** · 9 Demo · 10 Risks & checklist

---

## 0. What we are entering and how we're judged

### Tracks and prizes

| Target | Asks for | How DelayLens fits |
| --- | --- | --- |
| **HRT — Best use of Data for Predictions & Decision Making** (primary) | Data used to predict and drive a decision | The product: a calibrated prediction (P(on time)) turned into a decision (when to leave) |
| **Tiger Data** (MLH) | Best implementation; $1,000 credits on sign-up | Our self-recorded time-series archive is the core: hypertable, continuous aggregate, compression |
| **Built with Delta** | Team collaboration in Delta from ideation to testing; shared threads | All development in Delta on this repo; one thread per role; links on Devpost |
| **Gemini API** (MLH) | Gemini used *inside* the product | "Ask DelayLens": flexible natural-language questions answered by our model (§5) |
| Vultr (MLH, optional) | Top project on Vultr | The recorder and API run on a Vultr VM, which they must anyway for the overnight gap |

### Judging criteria → design

| Criterion | Weight | What we do |
| --- | --- | --- |
| **Speed & Performance** | **30%** | In-memory cache, vectorised model, advisor and what-if computed in the browser; target < 300 ms API, instant sliders (§6.5) |
| **Technical Implementation** | 25% | Clean module boundaries, typed contract, tests, visible Delta collaboration |
| **Innovation** | 25% | Journey planners give one number; we give a calibrated distribution from data TfL doesn't publish, and you can just ask |
| **Polish & Usability** | 20% | One screen; clear loading/empty/error states; works on a phone |

The organisers asked for projects that are "not a demo": real recorded data,
real live arrivals, no mocked numbers in the final build.

---

## 1. First priority: start recording data

TfL's Unified API gives **live predictions only — there is no archive** of
past arrivals or delays. Every historical sample must be recorded by us, so
every hour without the recorder is data lost for good.

- Recorder writing to Tiger Data by **Sat 15:00**.
- On a Vultr server under a supervisor by **Sat 21:30**, because the team sleeps
  00:00–07:00 and nobody will be watching it.

---

## 2. Product scope

### Core user journey

1. Pick a supported route segment, enter walking times and a **deadline**,
   or type a question: *"I need to be at Oxford Circus around 2, ten minutes
   late is OK."*
2. See the **departure curve**: P(on time) for each departure time in the
   90 minutes before the deadline, with an uncertainty band and sample size.
3. Get the **latest departure** that meets your risk tolerance.
4. **What-if:** +5 / +10 / +15 min shows how the risk changes.
5. **Live panel:** next vehicles at the origin stop now.

### Features and priority

| Feature | What we build | Priority |
| --- | --- | --- |
| Route Selection | Supported segments (ones we have data for), deadline, walk times, tolerance slider | **P0** |
| Live Arrivals | `GET /Line/{ids}/Arrivals`, server-side | **P0** |
| Delay Prediction | Empirical travel-time distribution from recorded data, with uncertainty | **P0** |
| Departure Advisor | Latest departure with P(late) ≤ tolerance | **P0** |
| What-if Simulation | +5/+10/+15 markers and risk deltas | **P0** |
| **Ask DelayLens (Gemini)** | Free-text questions → structured request → our model → plain answer (§5) | **P1, scheduled** |
| Data coverage + calibration | Trips per hour, "low data" badges, reliability chart | **P1, scheduled** |
| Live correction | TfL's own ETA error by horizon, used for the next 30 min | P1 if time |
| Rail mode | National Rail HSP history (e.g. Oxford → Paddington) | P2, only if access arrives |
| Multi-leg journeys, any A→B, accounts | — | Out of scope |

### Success criteria

- A recommendation from **real recorded data** in under 2 seconds via the form,
  with sample size shown.
- A judge can type a question their own way and get a correct, grounded answer.
- Limitations are visible in the UI, not only in the pitch.

---

## 3. Data strategy

### 3.1 What we record

- Poll `GET https://api.tfl.gov.uk/Line/{lineIds}/Arrivals?app_key=…` every
  **30 s**. One call covers all listed lines. Confirm the keyed rate limit on
  the TfL API portal.
- Keep only predictions for stops on the chosen segments (≈10–20 stops):
  `vehicleId`, `naptanId`, `lineId`, `direction`, `timeToStation`,
  `expectedArrival`, `timestamp`.
- Tiger Data account via `mlh.link/tigerdata` (credits); standard service,
  European region if offered.
- Every poll is also appended to a gzipped JSONL backup, so a database outage
  never loses data.
- **Everything in UTC.** UK clocks go back at 02:00 on Sun 25 Oct while we
  sleep, so 01:00–02:00 local time happens twice.

### 3.2 From predictions to observed trips

- **Observed arrival** for a `(vehicleId, naptanId)` episode = the last
  `expectedArrival` seen while `timeToStation ≤ 60 s`, or else the last poll
  in which the prediction appeared.
- The same vehicle at the same stop more than 20 min later = a new episode.
- **Trip segment** = same vehicle at origin O (`t_O`), then destination D in
  the same direction (`t_D > t_O`). Ride time = `t_D − t_O`.

### 3.3 Choosing routes (D decides at kickoff)

- **Main: one bus segment of ~30–45 min through traffic.** Real variance and
  reliable `vehicleId`s. Find IDs with `GET /Line/Mode/bus` and stop order with
  `GET /Line/{id}/Route/Sequence/{direction}`.
- **Contrast: one Tube segment.** Low variance, which shows the model says
  "either is fine" when that's true.
- Avoid lines with closures this weekend (`GET /Line/{ids}/Status`).

### 3.4 Honest time coverage

- We'll have data from Sat ~15:00 onwards, weekend only. **Demo deadlines must
  fall inside recorded hours.** `/api/routes` returns `hours_covered`.
- Every result is labelled, e.g. "based on 38 trips observed Sat 24 – Sun 25
  Oct (weekend)".

### 3.5 Optional: National Rail HSP (P2)

Historical actual-vs-scheduled times for station pairs, via POST `serviceMetrics`
and `serviceDetails`. Needs a National Rail Data Portal account with HSP ticked.
D submits the sign-up at kickoff; we only build this if access arrives by
Saturday evening.

---

## 4. Model

Plain NumPy. The goal is **calibrated probabilities with honest uncertainty**.

### 4.1 Empirical replay

For departure `d`, walking times `w₁` and `w₂`, and deadline `T`:

1. The user reaches the stop at `s = d + w₁`.
2. Take every recorded instant `s'` at the same time of day (± 30 min, 1-min
   steps).
3. For each `s'`, take the first vehicle leaving O at or after `s'` + 1 min, and
   its arrival at D. Then `TT(s') = t_D − s' + w₂`. This captures waiting,
   headway gaps and ride time together, with no parametric assumptions.
4. `P(on time | d) = mean(1[d + w₁ + TT ≤ T])`.

Output per departure: `p_on_time`, `arrive_p50`, `arrive_p90`, and `n_trips`
(distinct vehicles, not replay steps).

### 4.2 Uncertainty

- Bootstrap over distinct trips (200 resamples, vectorised) gives a 90% band.
- If `n_trips < 15`, widen to ± 60 min and flag `low_data`. If still below 15,
  return `insufficient_data`. **Never fabricate a probability.**

### 4.3 Advisor and what-if

- The curve runs from `T − 90 min` to `T` at 1-min resolution.
- The recommendation is the latest `d` with P(late) ≤ tolerance (default 10%).
  The "conservative" option uses the band's lower edge.
- What-if reads the curve at `+5 / +10 / +15`.

### 4.4 Calibration (P1)

Hold out the latest hours, predict for synthetic deadlines, and compare with
what happened. This gives reliability bins and a Brier score, shown on the
Methodology tab ("when we say 80%, we were on time x% of the time").

### 4.5 Live correction (P1 if time)

Measure TfL's prediction error (actual − predicted) by horizon. For departures
in the next 30 min, use the live ETA plus a sampled error instead of history.

---

## 5. Ask DelayLens (Gemini API)

**Why:** the form is fast but rigid. People ask questions with slack in them:
*"around 2"*, *"I really can't be late"*, *"is 13:10 or 13:20 better?"*,
*"what's the latest I can leave?"*. Gemini turns these into a precise request.
**Our model always produces the numbers.**

### How it works

1. `POST /api/ask` sends the question plus the current time to Gemini with
   **function declarations** that mirror our API:

   | Function | Parameters | Covers questions like |
   | --- | --- | --- |
   | `list_routes()` | — | "Which routes can you do?" |
   | `get_departure_curve` | `route_id, deadline, walk_to_min, walk_from_min, tolerance` | "When should I leave to be there by 2?" |
   | `compare_departures` | `route_id, deadline, departures[]` | "13:10 or 13:20?" |
   | `get_live` | `route_id` | "When's the next bus?" |

2. Gemini maps vague language to parameters:

   | The user says | Gemini sets |
   | --- | --- |
   | "around 2, ten minutes late is OK" | deadline 14:10 |
   | "I really can't be late" | tolerance 0.05 |
   | "a bit relaxed" | tolerance 0.20 |

   Free-text places are matched to supported routes only.

3. The backend validates the arguments against `routes.json` and runs **our
   model**.
4. The answer sentence is built from a template using the computed numbers.
   An optional Gemini rephrasing is used only if every number in it matches
   the result; otherwise we fall back to the template.
5. The UI shows the **interpretation as editable chips** (route, deadline,
   tolerance) above the normal curve, so the user can see and fix what was
   understood.

### Guardrails

- Unsupported place or route → a helpful reply listing the routes we cover.
  Never a guess.
- 3-second timeout; on failure, the form opens prefilled with whatever was
  parsed. **The form always works without Gemini.**
- The key lives server-side only (`GEMINI_API_KEY`). Use a fast Gemini Flash
  model; confirm the current model ID in Google AI Studio.
- A test set of ~20 phrasings (vague times, comparisons, off-topic,
  unsupported places) is run before freeze.

---

## 6. Architecture

```
  TfL Unified API ──30 s──► ingest/poller ──► JSONL backup
                                │
                                ▼
          Tiger Data: arrival_predictions (hypertable) → stop_events → trip segments
                      coverage_hourly (continuous aggregate), compression
                                │  (cached in memory, refreshed every minute)
                                ▼
   Gemini API ◄── /api/ask ── FastAPI backend + model.py ── /api/live ──► TfL
                                │
                                ▼
         React (Vite + TS): Ask box · form · curve · advisor · what-if · live · methodology
```

All of it runs on one Vultr VM, with the recorder under `systemd` (auto-restart).

### 6.1 Repository layout and owners

```
backend/
  ingest/poller.py, ingest/derive.py      D
  sql/001_schema.sql                      D
  config/routes.json                      D
  app/model.py, tests/test_model.py       M
  app/main.py, app/schemas.py             B   (the contract)
  app/tfl.py, app/db.py, app/ask.py       B   (ask.py = Gemini)
  tests/test_api.py, tests/ask_cases.json B
  fixtures/                               B
  pyproject.toml, uv.lock                 B
frontend/                                 F
deploy/ (systemd units, scripts)          D
README.md additions                       M
.env.example                              B
```

### 6.2 Tiger Data schema (sketch; verify syntax against current Tiger docs)

```sql
CREATE TABLE arrival_predictions (
  polled_at timestamptz NOT NULL, line_id text NOT NULL, direction text,
  vehicle_id text NOT NULL, naptan_id text NOT NULL, destination_name text,
  time_to_station integer NOT NULL, expected_arrival timestamptz NOT NULL
);
SELECT create_hypertable('arrival_predictions', by_range('polled_at', INTERVAL '1 hour'));
CREATE INDEX ON arrival_predictions (vehicle_id, naptan_id, polled_at DESC);

CREATE TABLE stop_events (
  line_id text, direction text, vehicle_id text, naptan_id text,
  observed_at timestamptz NOT NULL,
  PRIMARY KEY (vehicle_id, naptan_id, observed_at)
);

CREATE MATERIALIZED VIEW coverage_hourly WITH (timescaledb.continuous) AS
SELECT time_bucket('1 hour', polled_at) AS hour, line_id, naptan_id,
       count(DISTINCT vehicle_id) AS vehicles
FROM arrival_predictions GROUP BY 1, 2, 3;
```

Percentiles are computed in Python. Compression is enabled on older chunks,
and its ratio is shown on the Methodology tab.

### 6.3 API contract (B owns it; frozen at Sat 17:00)

`GET /api/routes`
```json
[{"route_id": "bus-XX-outbound-A-B", "line_id": "XX", "mode": "bus",
  "origin": {"naptan_id": "…", "name": "…"}, "destination": {"naptan_id": "…", "name": "…"},
  "trips_observed": 412, "hours_covered": ["2026-10-24T14:00Z", "…"]}]
```

`POST /api/departure-curve`
```json
// request
{"route_id": "…", "deadline": "2026-10-25T11:00:00Z",
 "walk_to_min": 6, "walk_from_min": 4, "tolerance": 0.10, "window_min": 90}
// response
{"points": [{"depart_at": "…", "p_on_time": 0.94, "ci": [0.89, 0.97],
             "arrive_p50": "…", "arrive_p90": "…", "n_trips": 38}],
 "recommended": {"depart_at": "…", "p_on_time": 0.91},
 "what_if": [{"delay_min": 5, "p_on_time": 0.84, "delta": -0.07}],
 "data_quality": {"status": "ok | low_data | insufficient_data",
                  "basis": "38 trips observed Sat 24 – Sun 25 Oct (weekend)"},
 "server_ms": 23}
```

`POST /api/ask`
```json
// request
{"question": "I need to be at Oxford Circus around 2, ten minutes late is fine"}
// response
{"interpretation": {"route_id": "…", "deadline": "…", "walk_to_min": 5,
                    "walk_from_min": 5, "tolerance": 0.10, "compare": null},
 "curve": { /* same shape as /api/departure-curve */ },
 "answer": "Leave by 13:12 for a 90% chance of arriving by 14:10.",
 "status": "ok | unsupported_route | unclear | gemini_unavailable"}
```

`GET /api/live?route_id=…` returns next arrivals, or `{"error": "tfl_unavailable"}`.
`GET /api/stats` returns row count, chunks, compression ratio and coverage.
`GET /api/calibration` returns reliability bins and the Brier score.

### 6.4 Configuration (`.env.example`, names only)

```
TFL_APP_KEY=your-tfl-app-key
DATABASE_URL=postgres://user:password@host:port/tsdb?sslmode=require
GEMINI_API_KEY=your-gemini-api-key
POLL_LINE_IDS=XX,victoria
POLL_STOP_IDS=490000000A,940GZZLUXXX
POLL_INTERVAL_SECONDS=30
RAW_BACKUP_DIR=.local/raw
FRONTEND_ORIGIN=http://localhost:5173
```

Python ≥ 3.11 with `uv`; Node ≥ 20 with `npm`. API on port 8000, frontend on 5173.

### 6.5 Performance (30% of the score)

- No database call on the hot path: segments are cached per route and
  refreshed each minute, and common deadlines are precomputed.
- The model is vectorised (`searchsorted`); budget < 50 ms per curve including
  the bootstrap.
- One request returns the whole curve. The advisor slider and what-if run in
  the browser.
- The frontend uses a single SVG component with no chart library, skeleton
  loaders, and prefetches routes and the default curve.
- The Ask flow shows the interpretation chips as soon as parsing returns.
- "Computed in N ms" appears on screen.

---

## 7. Team and ownership

Four roles, referred to by code. Each file, account and deliverable has
**exactly one owner**. Others review or request changes; only the owner edits.

| Code | Role | Owns | Accounts | Task file |
| --- | --- | --- | --- | --- |
| **D** | Data & infra | Recorder, `derive.py`, schema, `routes.json`, Vultr deploy, fallback snapshot, hotspot backup | TfL key, Tiger Data, Vultr, HSP sign-up | [tasks/data-ingestion.md](tasks/data-ingestion.md) |
| **M** | Model & submission | `model.py`, model tests, calibration, demo scenario, README, Devpost write-up and submission | Devpost | [tasks/model.md](tasks/model.md) |
| **B** | Backend, Gemini & integration | API contract, all endpoints, `ask.py` (Gemini), caching/performance, API tests, merging branches | Gemini API key | [tasks/backend-api.md](tasks/backend-api.md) |
| **F** | Frontend & pitch | Whole `frontend/` incl. Ask box, Methodology tab, Devpost images, backup video, table script, lead presenter | — | [tasks/frontend-demo.md](tasks/frontend-demo.md) |

**Working rules**

- One branch per role: `feat/data`, `feat/model`, `feat/api`, `feat/frontend`.
  B merges in the order D → M → B → F.
- After 17:00 the contract changes only with B's approval, announced to all.
- M and F build against B's fixtures until real data flows. Fixtures are
  labelled and removed before judging.
- Finished early? Take your next row in §8 or ask B. Never start in someone
  else's area.
- Blocked for more than 20 minutes? Post in your Delta thread and tell B.
- **Delta:** threads `D · data`, `M · model`, `B · api`, `F · frontend`, plus a
  team thread `ideation & contract`. Review each other's agent output
  in-thread. M collects the best thread links for Devpost.

---

## 8. Schedule

Official fixed points:

| Time | Event |
| --- | --- |
| Sat 12:00 | Hacking began |
| Sat 18:00–19:00 | Dinner |
| Sun 00:00 | Pizza |
| Sun 08:00–09:00 | Breakfast |
| Sun 09:00–10:00 | Devpost workshop |
| **Sun 12:00** | **Hacking ends** |
| **Sun 13:00–15:45** | **Judging at our table** |
| Sun 16:00 | Closing ceremony |

**The team sleeps 00:00–07:00**, so the recorder must run unattended on the
server from 23:45. Clocks go back at 02:00; data is UTC, so nothing to do.
Talks and workshops are skipped except the Devpost workshop, which M attends.

★ rows are **all-team gates**: everyone stops, meets for 5–15 minutes, and
leaves with the exit check met or the stated cut made.

### Saturday 24 Oct

| Time | Owner | Task | Tools | Exit check |
| --- | --- | --- | --- | --- |
| **14:00–14:15** | **all** | **★ Kickoff:** confirm who is D/M/B/F; D picks routes (others advise); B reads the API contract aloud; create Delta threads; share secrets privately (never in repo or public chat) | Delta | Routes listed; contract agreed |
| 14:15–15:00 | D | TfL key; Tiger Data via `mlh.link/tigerdata` + service; `001_schema.sql` (UTC hypertable); minimal `poller.py` + JSONL backup | TfL Unified API, Tiger Data, psycopg | Rows land every 30 s |
| 14:15–15:00 | M | Synthetic timetable generator; hand-checked tests (bus every 10 min, fixed 20-min ride → step-shaped curve) | NumPy, pytest | Tests written |
| 14:15–15:00 | B | `uv` + FastAPI skeleton; `schemas.py`; `/api/departure-curve` serving a fixture; `.env.example` | FastAPI, Pydantic, uv | F can call the fixture |
| 14:15–15:00 | F | Vite + React + TS scaffold; layout and tokens; route form (route, deadline, walk times, tolerance) | Vite, React, TypeScript | Form renders, keyboard-usable |
| **15:00** | **all** | **★ Recorder gate:** rows arriving every 30 s. **If not, M stops and helps D** until they are | — | — |
| 15:00–16:30 | D | Harden poller: backoff on 429/5xx/timeouts, restart loop, logging; stop IDs both directions; submit National Rail HSP sign-up | TfL `Route/Sequence` | Survives a Wi-Fi drop |
| 15:00–16:30 | M | Vectorised empirical replay: `p_on_time`, `arrive_p50/p90`, `n_trips` | NumPy (`searchsorted`) | Synthetic tests pass |
| 15:00–16:30 | B | `tfl.py` (timeouts, explicit errors); real `/api/live`; `/api/routes` from `routes.json`; add `/api/ask` shape to the contract | httpx, FastAPI | Real live arrivals returned |
| 15:00–16:30 | F | `DepartureCurve` SVG on the fixture: curve, band, recommended marker | SVG | Fixture renders correctly |
| 16:30–18:00 | D | `derive.py`: stop events + trip segments every minute; sanity-check ride times | SQL, TimescaleDB | Plausible ride times per route |
| 16:30–18:00 | M | Bootstrap 90% band; `low_data` / `insufficient_data` thresholds; benchmark | NumPy | < 50 ms per curve |
| 16:30–17:00 | B | Finalise contract + fixtures (curve, ask, live, stats, calibration) on `main` | Pydantic | Merged |
| 16:30–17:00 | F | `api.ts` typed client mirroring `schemas.py` | TypeScript | Compiles against fixtures |
| **17:00** | **all** | **★ Contract freeze:** later changes need B's approval and are announced | — | — |
| 17:00–18:00 | B | `db.py` pool + in-memory segment cache refreshed each minute | psycopg | Cache refreshes |
| 17:00–18:00 | F | Client-side advisor (tolerance slider) + what-if chips | React | Sliders never call the API |
| 18:00–18:30 | all | Dinner | — | — |
| 18:30 | D | **Hand-off:** segment CSV → M; `get_segments` + coverage SQL → B | — | — |
| 18:30–19:30 | D | Provision Vultr VM (`mlh.link/vultr`); install runtime | Vultr | SSH works |
| 18:30–19:15 | M | Run the model on real segments; sanity-check; merge `model.py` → B by 19:15 | — | Numbers make sense to a commuter |
| 18:30–19:30 | B | Wire D's SQL and M's model into the curve endpoint | — | Curve from real data |
| 18:30–19:30 | F | `LivePanel`; switch from fixture to the real API | — | Real curve on screen |
| **19:30** | **all** | **★ End-to-end gate:** real data → model → API → screen. **If not, cut Gemini and calibration;** everyone closes the gap on the bus route only | — | — |
| 19:30–21:30 | D | Recorder + `derive.py` on the VM under `systemd`; laptop recorder keeps running as backup | Vultr, systemd | VM and laptop row counts match |
| 19:30–21:30 | M | Time-of-day window in UTC; edge cases (no next vehicle, end of data, repeated 01:00 hour); tests | pytest | Edge-case tests pass |
| 19:30–21:30 | B | `ask.py`: Gemini function calling (`list_routes`, `get_departure_curve`, `compare_departures`, `get_live`), argument validation, 3 s timeout, templated answer | Gemini API | 10 sample questions parse correctly |
| 19:30–21:30 | F | Loading, empty and error states; `low_data` badge; phone layout; focus styles | CSS | Every state reachable |
| 21:30–22:30 | D | `coverage_hourly` continuous aggregate; compression policy; `stats` SQL → B | TimescaleDB | Queries < 100 ms |
| 21:30–23:00 | M | Calibration backtest v1 on ~8 h of data → JSON | NumPy | Calibration JSON committed |
| 21:30–22:30 | B | `/api/stats`, `/api/calibration`; precompute common deadlines; `server_ms`; API tests; package the API → D | FastAPI, pytest | p95 < 300 ms locally |
| 21:30–22:30 | F | **Ask box:** free text → editable interpretation chips → curve; "computed in N ms"; "Powered by TfL Open Data" footer; production build → D | React | Ask flow works on the dev server |
| 22:30–23:00 | D | Deploy API + frontend build to the VM | Vultr | Public URL works |
| 22:30–23:00 | B | Merge branches D → M → B → F; smoke-test the public URL with D | git | `main` = deployed build |
| 22:30–23:00 | F | Table demo script v1 (2-minute core) | — | Script in repo |
| **23:00** | **all** | **★ P0 + deploy gate:** five core features + Ask work on the public URL. **If Ask is flaky, hide it behind the form;** the form stays the main path | — | — |
| 23:00–23:45 | D | Overnight readiness: kill the recorder and confirm `systemd` restarts it; check disk space; laptop backup plugged in with sleep disabled | systemd | Recorder survives a forced kill |
| 23:00–23:45 | M | Shortlist demo scenarios inside recorded hours; methodology notes | — | Shortlist in PROGRESS.md |
| 23:00–23:45 | B | Ask test set (`ask_cases.json`, ~20 phrasings) written; handover notes in PROGRESS.md | pytest | Test set committed |
| 23:00–23:45 | F | Devpost screenshots + architecture diagram | — | Images in repo |
| **23:45** | **all** | **★ Overnight gate:** recorder confirmed on the server; laptops plugged in; everyone logs off by 00:00 | — | — |
| 00:00–07:00 | all | **Sleep.** Grab pizza on the way if you want it | — | — |

### Sunday 25 Oct

| Time | Owner | Task | Tools | Exit check |
| --- | --- | --- | --- | --- |
| **07:00–07:15** | **all** | **★ Wake-up gate:** D shows overnight rows and gaps across the clock change. **If gaps, D reloads from the JSONL backup** before anything else | — | — |
| 07:15–08:30 | D | Data QA across the clock change; build the demo **fallback snapshot** (API serves without Tiger Data) | — | Snapshot serves offline |
| 07:15–08:30 | M | Re-run calibration with overnight data; live correction (P1), dropped at 08:15 if unconvincing | NumPy | Merged, or written up as future work |
| 07:15–08:30 | B | Run and fix the Ask test set: vague times, "a bit late is fine", comparisons, off-topic, unsupported places; overnight bugs | Gemini API, pytest | ≥ 18/20 cases pass; failures handled gracefully |
| 07:15–08:30 | F | Methodology tab: coverage heatmap, calibration chart, Tiger stats | SVG | Works on the deployed build |
| **08:30–08:45** | **all** | **★ Morning sync (at breakfast):** P1s in or out; demo scenario fixed | — | — |
| 08:45–09:30 | D | Load-test the deployed API; set up phone hotspot as network backup | — | p95 < 300 ms on the VM |
| 08:45–09:00 | M | Lock the demo scenario; final threshold check | — | Recorded in PROGRESS.md |
| 08:45–09:30 | B | Merge M's P1 work; redeploy with D | git | Stable deployed build |
| 08:45–09:30 | F | UI polish from team feedback; check first load on a phone | — | Feels instant on a phone |
| 09:00–09:45 | M | **Devpost workshop:** exact cut-off and required fields | Devpost | Requirements noted |
| **09:30** | **all** | **★ Feature freeze** (M is told in the team thread): bug fixes only; the deployed build is the demo build | — | — |
| 09:30–10:00 | D | Write the data/infra section → M | — | Sent |
| 09:30–10:00 | B | Write the backend + Gemini section → M | — | Sent |
| 09:30–10:00 | F | Record the backup demo video → M | — | Video with M |
| 09:45–10:30 | M | Assemble Devpost + README (what, how to run, architecture, TfL attribution, Delta links) | Devpost | Draft complete |
| 10:00–10:30 | D | Final infra checklist: VM, recorder, snapshot, hotspot | — | All ticked |
| 10:00–10:30 | B | Regression check of every endpoint on the VM, incl. Ask | — | All pass |
| 10:00–10:30 | F | Final table script + speaking parts (F hook + demo; M data story; B Ask; D pipeline) | — | Script in repo |
| **10:30–11:00** | **all** | **★ Dress rehearsal:** timed table demo + mock Q&A on the deployed site; fixes assigned to owners | — | Under 3 min |
| 11:00–11:15 | M | **Submit on Devpost** | Devpost | Confirmation received |
| **11:15** | **all** | **★ Submitted** | — | — |
| 11:15–12:00 | B | Approves demo-breaking fixes only; D redeploys if approved | — | — |
| 11:15–12:00 | M | Judge Q&A cheat sheet (why empirical replay, calibration, limits, next steps) | — | One page |
| 11:15–12:00 | F | Backup video and fallback ready on a second device | — | — |
| **12:00** | **all** | **★ Hacking ends:** hands off keyboards | — | — |
| 12:00–13:00 | all | Lunch; set up the table; two timed rehearsals | — | — |
| **13:00–15:45** | **all** | **★ Judging at our table** (rota below) | — | — |

### Judging rota

At least two of us at the table at all times. F presents; a technical answerer
backs them up.

| Time | At the table | Free |
| --- | --- | --- |
| 13:00–13:45 | All four | — |
| 13:45–14:30 | F, M, D | B |
| 14:30–15:15 | F, M, B | D |
| 15:15–15:45 | All four | — |

### Hand-offs at a glance

| Time | From → To | What |
| --- | --- | --- |
| Sat 15:00 | D → M, B | Schema + `routes.json` |
| Sat 17:00 | B → M, F | Frozen contract + fixtures |
| Sat 18:30 | D → M / B | Segment CSV / `get_segments` + coverage SQL |
| Sat 19:15 | M → B | `model.py` merged |
| Sat 22:30 | B, F → D | API package, frontend build |
| Sat 22:30 | D → B | `stats` SQL |
| Sat 23:00 | M → B | Calibration JSON |
| Sun 10:00 | D, B, F → M | Devpost sections and backup video |

---

## 9. Table demo (2-minute core, repeatable)

1. **Hook (15 s):** "You must be there by 2. Leave at 1:10 or 1:20? Journey
   planners give one number; reality is a distribution."
2. **Ask (25 s):** type *"I need to be at [stop] around 2, I can't be late"*.
   The interpretation chips appear, then the curve.
3. **Curve (40 s):** P(on time) falls as departure gets later; the band and
   "N trips" show how sure we are. "1:10 gives 93%, 1:20 gives 71%."
4. **Advisor + what-if (20 s):** tolerance slider gives "leave by 1:13"; tap
   +5/+10/+15. Note the "computed in N ms".
5. **Extended (if asked):** Tube contrast (flat curve, "either is fine"); data
   story (TfL has no archive, so we built one in Tiger Data since Saturday,
   with N rows, compression and coverage); the calibration chart; limitations
   (weekend data, single-leg routes).

Close: *"Data turned into a prediction, turned into a decision."*
**Fallback:** the snapshot-backed API, then the backup video on a second device.

---

## 10. Risks and checklist

### Risks

| Risk | Mitigation |
| --- | --- |
| **Recorder dies overnight while we sleep** | `systemd` auto-restart on the VM, tested by a forced kill at 23:00; laptop backup recorder; JSONL backup; first thing at 07:00 is the gap check |
| Not enough history | Recorder first; dense routes only; `n_trips` shown; `insufficient_data` instead of guesses |
| Gemini misreads a question | Editable interpretation chips; argument validation; 20-case test set; the form always works |
| Gemini slow or down | 3 s timeout; prefilled form fallback; Ask is never the only path |
| UI feels slow | Cache + client-side advisor; measure `server_ms` from the first slice |
| `vehicleId` noise (Tube) | Lead with the bus; Tube is the contrast only |
| TfL outage | Backoff; UI error state; never fake live data |
| Demo deadline outside recorded hours | Choose from `hours_covered` (M locks it at 08:45) |

### Hackathon checklist

Confirmed (opening slides and official schedule, read 2026-10-24):

- [x] Hacking Sat 12:00 → **Sun 12:00**; Devpost submission; judging 13:00–15:45 at tables; closing 16:00.
- [x] Teams ≤ 4; MLH + Hackathons UK codes of conduct.
- [x] Judging: Speed & Performance 30%, Technical 25%, Innovation 25%, Polish 20%.
- [x] Tracks: HRT data track; Tiger Data, Gemini API and Vultr (MLH); Built with Delta.

To confirm (M at the Sun 09:00 Devpost workshop, or on Discord):

- [ ] Exact Devpost cut-off and required fields (video? track selection?).
- [ ] Whether one project can enter several sponsor prizes.
- [ ] Rules on pre-existing code and AI tools. The repo scaffold (docs only)
      pre-dates the event.
- [ ] TfL attribution ("Powered by TfL Open Data") in the UI and README.