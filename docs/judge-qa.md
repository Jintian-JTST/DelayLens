# DelayLens: judge questions and answers

Ten questions judges are likely to ask, each answered in at most three sentences, with
the file on `main` that supports the answer. Numbers come from the final offline
snapshot `bus29-db-final-20261024T202558Z` (bus 29, Mornington Crescent → Tottenham
Court Road, Sat 24 Oct 2026) unless stated otherwise. Who answers: M (model), B (API
and Gemini) or D (data).

## 1. Where does the data come from? (D)

A recorder polls TfL's live arrival predictions every 30 seconds, saves the raw
responses first and then writes them to Tiger Data (TimescaleDB). Bus 29 has 56 usable
runs on the short segment and 48 on the longer Finsbury Park segment. The demo uses a
frozen read-only copy of the database, taken at 20:25 UTC.

Evidence: [README "How it works"](../README.md#how-it-works),
[snapshot README](evidence/bus29-db-final-20261024T202558Z/README.md),
[snapshot summary](evidence/bus29-db-final-20261024T202558Z/summary.json).

## 2. Are these real arrival times? (D/M)

No. TfL publishes predictions, not measured arrivals, so we infer stop events from the
sequence of predictions near each stop. When a bus simply disappears from the feed, it
is left uncertain and never treated as an arrival.

Evidence: [README "How it works"](../README.md#how-it-works),
[bus 29 source review](evidence/bus29-source-review-20261024/README.md).

## 3. How do you compute the chance of being on time? (M)

We replay every recorded minute within ±60 minutes of your departure, on the same date.
Each minute boards the first recorded bus at least 1 minute later, and we add both
walks. The share of those replays that arrive by your deadline is the estimated chance.
There is no fitted formula and no timetable.

Evidence: [README "How the model works"](../README.md#how-the-model-works),
[backend/app/model.py](../backend/app/model.py),
[backend/tests/test_model.py](../backend/tests/test_model.py).

## 4. Why do you need 15 trips before giving advice? (M)

The thresholds count distinct bus runs, not replayed minutes. 0–4 runs show counts
only; 5–14 show a preliminary estimate with no recommendation; 15+ show an estimate, a
band and a "leave by" time. With a ±30-minute window bus 29 never reached 15 runs, so
we widened it to ±60 and disclose that.

Evidence: [README evidence tiers](../README.md#how-the-model-works),
[16:55Z window check](evidence/bus29-db-snapshot-20261024T1655Z/README.md),
[tasks/model.md](../tasks/model.md).

## 5. Is it calibrated? (M/B)

Only preliminarily. In a blocked hold-out backtest, departures where we predicted about
92% arrived on time about 91% of the time. That was a Brier score of 0.130 over 1,104
overlapping outcomes from 49 runs. It is scored against the same inferred events, not
measured arrivals, so we never call it validated.

Evidence: [tasks/model.md (T10 table)](../tasks/model.md),
[backend/app/calibration.py](../backend/app/calibration.py),
[docs/PROGRESS.md](PROGRESS.md).

## 6. Why only one Saturday? (D/M)

We recorded live during the hackathon. The locked demo snapshot (20:25Z) is all Sat
24 Oct 2026, about 14:50–21:00 London, and the later 06:07Z candidate adds Saturday
evening plus 6 and 3 runs from the first hour of Sunday. The model never pools dates
silently, so a Saturday 17:00 query replays only Saturday data and gives 16:22 on both
snapshots; neither says anything about weekdays or rush hours.

Evidence: [README limitations](../README.md#how-the-model-works),
[test_dates_are_not_pooled_unless_requested](../backend/tests/test_model.py),
[morning comparison](evidence/bus29-morning-comparison-20261025/README.md),
[tasks/model.md](../tasks/model.md).

## 7. What is the offline snapshot, and is the demo live? (B)

The demo reads a frozen copy of our database (`SNAPSHOT_DIR`), so its numbers stay
fixed: a Saturday 17:00 deadline gives leave by 16:22, about 92%, and the live
database gives the same answer. The page labels it "Offline snapshot frozen 24 Oct
20:25 UTC; not live data". Live arrivals need the network, and Ask is enabled only when
`/api/health` reports a Gemini key (`ask_available`).

Evidence: [README "Run the API"](../README.md#run-the-api),
[deploy/README.md](../deploy/README.md),
[backend/app/snapshot_files.py](../backend/app/snapshot_files.py).

## 8. What do the bands mean: Wilson or bootstrap? (M/B)

With 15+ runs the 90% band resamples whole bus runs 200 times, so it shows sampling
variability in our inferred data. With 5–14 runs the API shows a wider 90% Wilson
interval over distinct runs instead. Neither band covers error in the inference itself.

Evidence: [README "How the model works"](../README.md#how-the-model-works),
[backend/app/curves.py](../backend/app/curves.py) (`_wilson`),
[backend/app/model.py](../backend/app/model.py).

## 9. How reliable is Ask? Can Gemini make up numbers? (B)

Gemini only turns a typed or spoken question into one validated function call. Our
model computes every number into a fixed template, and each call has a 4-second
timeout, a fallback model and, on the public site, a team passcode. Voice uses the
browser's speech recognition (Chrome sends audio to Google); voice and live Gemini
were tested only with mocks, and the form works without either.

Evidence: [backend/app/ask.py](../backend/app/ask.py),
[backend/app/main.py](../backend/app/main.py) (`ASK_ACCESS_CODE`, `ask_available`),
[frontend/src/speech.ts](../frontend/src/speech.ts).

## 10. What are the main limitations, and what would you do next? (M)

The main limitations:
- arrivals are inferred, not measured;
- the locked demo snapshot covers one Saturday, and the 06:07Z candidate adds only a
  few runs from the first hour of Sunday;
- below 15 runs there is no advice;
- our backup standalone recorder collected only 5 usable trips, so it can't
  independently confirm the database counts;
- the journey map cannot locate delays at individual stops, because trips are recorded
  origin to destination only.

Next: record weekdays and peaks, add measured arrivals for true validation, cover more
routes and support multi-leg journeys.

Evidence: [README limitations](../README.md#how-the-model-works),
[standalone 180-minute recording](evidence/bus29-standalone-180m-20261024T1721Z/README.md),
[frontend/src/components/RouteMap.tsx](../frontend/src/components/RouteMap.tsx),
[docs/PROGRESS.md](PROGRESS.md).
