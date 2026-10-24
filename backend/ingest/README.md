# DelayLens: real TfL data validation

Python 3.11+ standard library only. Run commands from the repository root on
Windows, macOS or Linux. No package installation, database, model or server is
required for this data-only slice. TfL network access is required for recording;
replay and export are fully offline.

## Record, replay and export

Choose a new run directory. Existing directories are refused to preserve evidence.

```text
python -m backend.ingest record --run .local/runs/bus24-validation --minutes 90
python -m backend.ingest replay --run .local/runs/bus24-validation
python -m backend.ingest export --run .local/runs/bus24-validation
python -m unittest discover -s backend/ingest/tests -p test_ingestion.py -v
```

Optional credentials: copy `backend/ingest/environment.example` to an ignored
file such as `.local/tfl.env`, fill it locally, and pass
`--env-file .local/tfl.env` to `record`. Existing environment variables win. The
only supported settings are `TFL_APP_KEY` and `POLL_INTERVAL_SECONDS` (minimum 30).
The low-frequency unkeyed public endpoint worked during the 24 October preflight;
this is not a guarantee of future unkeyed access. Registration information:
<https://api-portal.tfl.gov.uk/>. Keys never enter request logs, raw request URLs,
route snapshots or export packages.

Recording validates current service and the exact contiguous stop pattern before
starting. The 90-minute clock starts after the first successful raw append and
fsync. Each full-line response is saved before derivation, including failures.
One line is one poll envelope with UUID poll/collector IDs, UTC request/receive
times, HTTP status, payload or malformed response text, and a typed error.
Frames and source predictions have separate deterministic identities.

The active file is `polls.jsonl`; it is flushed and fsynced every round. On close,
the recorder additionally writes `polls.jsonl.gz`, preserving the original. A disk
failure stops collection visibly. 401/403 stop retries; 429/timeouts/5xx use
bounded 60/120-second backoff (respecting numeric Retry-After up to 120 seconds).
Raw collection continues if derivation fails. Any missed slots appear in quality
reports. The recorder prints status, never the secret-bearing request URL.

Every successful poll invokes offline replay in a separate interpreter. This
allows an early raw-only recorder to pick up completed downstream code without
restarting or losing data. An OS lock permits one canonical replay writer per
run. The first usable segment produces an immutable first-sample handoff; the
final export refreshes both ZIPs. A short recording does not pass the 90-minute
validation just because the command succeeds.

## Route and evidence rules

Default: `bus-24-inbound-warren-leicester`, 24 inbound towards Pimlico:
Warren Street, Capper Street, Goodge Street, Stephen Street, Tottenham Court Road,
Cambridge Circus, Leicester Square. Exact IDs and route version are in
`backend/config/routes.json`. Existing bus 29/Victoria entries are retained as
legacy candidates; they lack the required ordered-stop contract for this recorder.

- Keep line, direction, vehicle, trip ID, stop, source timestamp, time to station
  and expected arrival. Missing vehicle/trip identity is excluded in v1.
- At least two distinct source timestamps; last two no more than 90 seconds
  apart and expected-arrival adjustment no more than 120 seconds. The last valid
  prediction must be within 60 seconds of the stop.
- Source timestamps must be fresh within 90 seconds (allowing 30 seconds of
  forward clock skew). Conflicting countdown/source clocks are excluded.
- Two healthy, changed frames at least 20 seconds apart after the final ETA must
  lack the episode and advance the latest source timestamp. Repeated/rewound
  cached responses are ignored. They cannot add confirmations or poison two
  otherwise valid confirmations. A gap over 90 seconds between usable changed
  source frames, an empty response or a failed poll keeps the event uncertain.
- Match the same line/vehicle/trip/direction over ordered stops. Accept only
  120-2400-second complete segments with unambiguous endpoints and no observed
  reverse stop order. Split same-key stop episodes after a 20-minute gap; that
  gap alone never supplies a usable run identity.

These are conservative heuristics, not proof of a measured arrival. All accepted
times remain `estimated`; confidence `supported_by_rule` is categorical, not a
statistical probability. Pending, early-disappearing and invalid evidence is
reported separately. Source prediction IDs hash their identifying source fields,
not local poll IDs. Event/segment IDs are deterministic for the canonical union
of evidence. New source evidence may revise provisional IDs; consumers replace a
snapshot generation instead of appending rows from successive snapshots.

Independent samples are canonical complete vehicle-run segments, not raw rows,
minute query points or unique vehicles. 0-4 is `insufficient_data`; 5-14 is
`low_data`; 15+ is still an uncalibrated empirical sample. Model/API policy belongs
to M/B. Local time features retain UTC, London date/weekday/offset and fold; the
repeated October 01:00 hours remain separate. The dependency-free London feature
converter supports the post-1996 UK rules through 2099, subject to rule changes.

## Recovery and inspection

Replay ignores and reports an incomplete final line, retaining it in the original
file. A malformed complete line, conflicting poll ID or corrupt gzip is an error.
To combine overlapping recordings, put copied `.jsonl`/`.jsonl.gz` files in the
run's `imports/` directory and replay. This reads the canonical union through one
writer; duplicate poll IDs and source evidence do not multiply samples. All output
files are regenerated, never appended. To restart after a recorder crash, start a
new run and import the preserved earlier raw file; do not overwrite old runs.

Open `derived/quality.json` first. It separates HTTP success, UTC 30-second slot
coverage, prediction volume, uncertain events and independent journeys. Coverage
ends at the last captured poll; `capture_end_utc` records process completion.
`audit_examples.json` traces up to three accepted segments to both endpoint
events, all relevant predictions/poll IDs and the two absence confirmations.
It is evidence for review, not a claim that a human has reviewed the data.

After the configured run (90 minutes by default), fewer than five samples means partial/insufficient
support. With zero segments, export automatically derives the separate five-stop
Warren Street -> Tottenham Court Road fallback from the same raw recording.
Primary outputs are retained. Explicit fallback replay:

```text
python -m backend.ingest export --run .local/runs/bus24-validation --route-id bus-24-inbound-warren-tottenham
```

If both routes have zero usable segments, inspect exclusions and change route;
do not lower quality rules just to obtain a successful count.

## Delivery

- `derived/segments.csv`: one estimated journey per row, UTC endpoints in seconds.
- `derived/snapshot.json`: versioned recorded snapshot with route, events,
  segments, source times, quality, support state and limitations.
- `derived/stop_events.json`: accepted and uncertain endpoint/intermediate events.
- `derived/audit_examples.json`: inspectable source lineage for the first samples.
- `derived/local_time_features.json`: London date, weekday, UTC offset and fold.
- `exports/*-data.zip`: canonical raw gzip, inference/quality/route/audit files.
- `exports/*-source.zip`: allowlisted portable ingestion source, tests, safe example
  and MIT licence; excludes credentials, Git history and local environments.

Each ZIP contains `MANIFEST.json` with SHA256 and size per file; CRC and hash
readback are verified before publishing the completed ZIP. The package's snapshot
is the authoritative generation; active output files may be refreshed sequentially.
Give M the CSV and B the snapshot/quality contract. Database adapters, SQL schema,
model, API and UI integration are subsequent role-owned work.

For independent offline verification, extract the source ZIP into a clean folder,
extract the data ZIP into `.local/received-data` inside it, then run:

```text
python -m backend.ingest replay --run .local/received-data
```

The exported `raw/polls.jsonl.gz` layout is accepted directly. No network or keys
are needed. `acceptance_gate` additionally requires three source-traced examples;
`audit_review.json` identifies agent-reviewed evidence without claiming human
signoff or independent actual-arrival measurements.

Data attribution: Data provided by Transport for London.
<https://tfl.gov.uk/info-for/open-data-users/our-open-data>
