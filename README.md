# DelayLens

**When should I leave?** DelayLens records live London bus predictions from TfL,
infers traceable journey samples, and is being built to help you choose a departure
time from an empirical journey-time distribution with visible data-support limits.

Built by a team at OxHack 2026, University of Oxford.

## Main route: London bus 29

The team has agreed to build the demo around **London bus route 29**. The
configured route is outbound from Finsbury Park (Blackstock Road) towards
Tottenham Court Road Station (`bus-29-outbound-finsbury-park-tottenham-court-road`
in [backend/config/routes.json](backend/config/routes.json)).

Still to do: choose a short bus 29 subsegment (roughly 10-20 minutes, 4-8
consecutive stops) with an explicit ordered stop list, so its journeys can be
checked by hand. The **bus 24 validation segment** is already verified; the
Victoria line remains optional. A working bus 24 pipeline does not establish
bus 29 sample coverage.

## How it works

1. **Record** - a poller asks the TfL API for arrival predictions every 30 seconds
   and saves raw responses before downstream processing.
2. **Infer** - the standalone validator infers stop events from near-stop
   prediction sequences and advancing source frames. Unsupported disappearance
   stays uncertain. TfL supplies predictions, not measured actual arrivals.
3. **Model** - completed bus runs can feed the NumPy empirical replay model for
   a given reference time. The real-data API adapter is still pending.
4. **Answer** - the API exposes departure choices with evidence counts. Fewer
   than 5 usable runs is `insufficient_data`; 5-14 is preliminary; 15+ supports
   an empirical estimate. No sample-count threshold proves calibration.
5. **Ask (optional)** - Gemini turns a plain-English question into a form request;
   the normal form remains available without it.

## Status

| Part | State |
| --- | --- |
| Data validation | Bus 24: 60-minute capture completed, 121 successful polls, 4 traceable inferred trips; CSV and snapshots exported |
| Database recorder | Separate recorder and SQL tooling retained; its archive/derivation contract differs from the standalone validator |
| Backend API | FastAPI health, routes, departure-curve and Ask endpoints |
| Model | NumPy replay model; not yet connected to the real-data API adapter |
| Frontend | Not present in this repository at this checkpoint |

The bus 24 validation ran on **24 October 2026, 14:53-15:53 Europe/London**
(13:53-14:53 UTC), stopping after 60 minutes at the owner's request. Three
examples were traced to their source predictions; this is agent evidence review,
not independent arrival measurement or human signoff. Four usable trips still
mean `insufficient_data` for probability output.

Real routes return `insufficient_data` until recorded data is connected to the
API. Current progress and verification live in
[docs/PROGRESS.md](docs/PROGRESS.md); data handoff details are in
[backend/ingest/README.md](backend/ingest/README.md).

The recorded [sample CSV and quality report](docs/evidence/bus24-validation-20261024/README.md)
are included for M/B to inspect and load. Complete raw/source ZIPs are delivered
separately; credentials and local recording archives are not committed.

## Getting started

You need Git, Python 3.11 or newer, and [uv](https://docs.astral.sh/uv/) for the
full backend. The standalone data validator uses only Python's standard library.
These commands work in PowerShell, bash and zsh:

```text
git clone https://github.com/Jintian-JTST/OxHack.git
cd OxHack/backend
uv sync --locked
uv run --locked pytest -q
```

Ordinary tests need no credentials or network access. Real database integration
checks are opt-in and skipped without explicit configuration.

### Configuration and secrets

Copy `backend/.env.example` to `backend/.env` and fill in your own values:

| Variable | Needed for |
| --- | --- |
| `TFL_APP_KEY` | API live panel and authenticated polling; the low-frequency standalone validation worked without a key |
| `DATABASE_URL` | Shared Tiger Data / PostgreSQL database recorder and database operations |
| `GEMINI_API_KEY` | Optional Ask feature |

`backend/.env` is git-ignored. **Never commit it, and never paste keys or the
`DATABASE_URL` into code, commit messages, issues or chat.** Obtain shared
credentials through the team's private channel. Only placeholder examples belong
in the repository. The standalone validator accepts its explicit local config
via `--env-file`; it does not load the backend's `.env` implicitly.

### Run the API

From `backend/`:

```text
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/api/health> or <http://127.0.0.1:8000/docs>.

### Run a recorder

The recorders have different archive and derivation contracts. Do not feed one
recorder's files into the other, pool their samples without reconciling quality
fields, or start multiple canonical database writers.

**Database recorder**: from `backend/`, initialise the configured database and
start the recorder. Its default lines are bus 29, bus 24 and Victoria:

```text
uv run --locked python -m ingest.admin init
uv run --locked python -m ingest.database_poller
```

Add `--once` for a single poll. Database derivation remains in
`ingest.database_derive`. Linux service setup is in
[deploy/README.md](deploy/README.md).

**Standalone raw-first validator**: from the repository root, choose a new run
folder. The default segment is bus 24; `--minutes` sets the recording duration:

```text
python -m backend.ingest record --run .local/runs/my-run --minutes 60
python -m backend.ingest replay --run .local/runs/my-run
python -m backend.ingest export --run .local/runs/my-run
python -m unittest discover -s backend/ingest/tests -p test_ingestion.py -v
```

It saves complete TfL responses, infers conservative events, exports CSV and a
snapshot, and creates separate data/source ZIPs with SHA256 manifests. The first
usable segment triggers an early snapshot. Replay and export need no network,
API key or database. The low-level `backend.ingest.poller` entry point remains
available. Bus 29 needs its ordered short-stop configuration before this validator
can record that route. Full instructions: [data validation](backend/ingest/README.md).

## Repository layout

| Path | Contents |
| --- | --- |
| `backend/app/` | FastAPI app, model and Gemini Ask handler |
| `backend/ingest/` | Standalone validator and separate database recording/derivation tools |
| `backend/config/routes.json` | Configured routes and ordered validation stops |
| `backend/sql/` | Database schema and queries |
| `deploy/` | Recorder service files for Linux |
| `PLAN.md` | Product and implementation plan |
| `docs/PROJECT.md` | Agreed decisions, stack and ownership |
| `docs/PROGRESS.md` | Completed work, verification and remaining gates |
| `tasks/` | One handoff file per task or role |

## Team

| Role | Person | Focus |
| --- | --- | --- |
| D - Data | Jintian | Recording, inference, database, server |
| M - Model | Olivia | Model, evaluation, submission |
| B - Backend | David | API, Gemini, contracts, integration |
| F - Frontend | To be confirmed | UI, pitch, demo video |

## Contributing

Use short feature branches and open a pull request into `main`. See
[CONTRIBUTING.md](CONTRIBUTING.md) for setup and workflow.

AI-assistant instructions and tool-entry links live in [AGENTS.md](AGENTS.md).

## Data attribution

Data provided by Transport for London.
[Official data information](https://tfl.gov.uk/info-for/open-data-users/our-open-data).

## License

[MIT](LICENSE)
