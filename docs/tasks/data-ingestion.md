# Task: DelayLens data ingestion

- Task ID: data-ingestion
- Owner (person / AI tool): D / Codex
- Branch: feat/data (independent clone)
- Status: routes verified; recorder and SQL in progress
- Integrator / reviewer: B; model consumer M

## Outcome and acceptance criteria

Record real TfL predictions every 30 seconds, back up each successful poll to
gzip JSONL, persist into Tiger Data, derive estimated stop events and matched
trip segments without inventing observations. All timestamps are UTC.

## Ownership and dependencies

- Owned files: backend/ingest/, backend/sql/, backend/config/routes.json, deploy/.
- Explicit requested shared edits: backend/.env.example and this task file.
- No backend/app/ or B-owned dependency/lockfile changes.
- B merges D before M. B must add psycopg[binary] to the backend dependencies.
- Local configuration: TFL_APP_KEY, DATABASE_URL, POLL_LINE_IDS, POLL_STOP_IDS,
  POLL_INTERVAL_SECONDS, RAW_BACKUP_DIR; secrets only in ignored backend/.env.

## Interface decisions

Routes (public identifiers):

| route_id | line_id | direction | origin naptan_id | destination naptan_id |
| --- | --- | --- | --- | --- |
| bus-29-outbound-finsbury-park-tottenham-court-road | 29 | outbound | 490000083S | 490000235GX |
| tube-victoria-outbound-brixton-oxford-circus | victoria | outbound | 940GZZLUBXN | 940GZZLUOXC |

Stop order verified with the official TfL Line/29/Route/Sequence/outbound and
Line/victoria/Route/Sequence/outbound endpoints on 2026-10-24 at approximately
13:46 UTC. Weekend status queried for 2026-10-24T00:00:00Z through
2026-10-25T23:59:59Z: both lines report Good Service. Recheck before demo.
Rejected line 24 (Victoria northbound stop closure) and 73 (planned truncation).

## Handoff

- Changes and relevant commits: first delivery is routes.json and polling IDs.
- Checks actually run: Windows / PowerShell 7.6.5 / Python 3.11.9; official TfL
  route-sequence, live arrivals and weekend-status requests succeeded.
- Unverified: database connection, server deployment, sustained recording, segment
  counts and runtime SQL execution. Tiger Data DATABASE_URL not configured yet.
- Next action: D implements SQL, poller, recovery and derivation; B can test the
  real route configuration immediately after the first push.
