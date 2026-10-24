# DelayLens

**When should I leave?** DelayLens records live London bus predictions from TfL,
turns them into an empirical journey-time distribution, and helps you pick a
departure time, while showing honestly how much data supports the answer.

Built by a team at OxHack 2026, University of Oxford.

## Main route: London bus 29

The team has agreed to build the demo around **London bus route 29**. The
configured route is outbound from Finsbury Park (Blackstock Road) towards
Tottenham Court Road Station (`bus-29-outbound-finsbury-park-tottenham-court-road`
in [backend/config/routes.json](backend/config/routes.json)).

Still to do: choose a short bus 29 subsegment (roughly 10-20 minutes, 4-8
consecutive stops) with an explicit ordered stop list, so its journeys can be
checked by hand. The other configured routes (bus 24 and the Victoria line) are
kept as fallbacks and optional extras.

## How it works

1. **Record** – a poller asks the TfL API for arrival predictions every 30
   seconds and saves the raw responses before anything else touches them.
2. **Infer** – from those predictions we infer when a bus passed each stop, and
   keep how confident that inference is. TfL gives predictions, not measured
   arrivals, so a bus disappearing from the feed is treated as uncertain.
3. **Model** – completed bus runs over the segment become an empirical
   journey-time distribution for a given time of day.
4. **Answer** – the API returns departure choices for a deadline, with the
   number of runs behind the estimate. With fewer than 5 usable runs it says
   `insufficient_data`; 5-14 runs give a preliminary estimate; 15+ give an
   empirical estimate.
5. **Ask (optional)** – Gemini turns a plain-English question into a form
   request; the normal form still works without it.

## Status

| Part | State |
| --- | --- |
| Data recording | Two recorders on `main` (see below); live capture in progress |
| Backend API | FastAPI app with health, routes, departure curve and Ask endpoints |
| Model | NumPy replay model; not yet connected to real recorded data |
| Frontend | Not started in this repository yet |

Real routes return `insufficient_data` until the recorded data is wired into the
API. Up-to-date progress and verification live in
[docs/PROGRESS.md](docs/PROGRESS.md).

## Getting started

You need Git, Python 3.11 or newer, and [uv](https://docs.astral.sh/uv/). The
commands below work in PowerShell, bash and zsh.

```text
git clone https://github.com/Jintian-JTST/OxHack.git
cd OxHack/backend
uv sync --locked
uv run --locked pytest -q
```

The tests need no credentials or network access.

### Configuration and secrets

Copy `backend/.env.example` to `backend/.env` and fill in your own values:

| Variable | Needed for |
| --- | --- |
| `TFL_APP_KEY` | Calling the TfL API (recorders, live predictions) |
| `DATABASE_URL` | Writing to and reading from the shared Tiger Data / PostgreSQL database |
| `GEMINI_API_KEY` | The optional Ask feature |

`backend/.env` is git-ignored. **Never commit it, and never paste keys or the
`DATABASE_URL` into code, commit messages, issues or chat.** Ask a teammate
for the shared database URL privately. Only `.env.example`, with placeholders,
belongs in the repository.

### Run the API

From `backend/`:

```text
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then open <http://127.0.0.1:8000/api/health> or <http://127.0.0.1:8000/docs>.

### Run a recorder

There are two recorders. Their archive formats are different, so do not feed one
recorder's files into the other, and run only one database recorder at a time.

**Database recorder** (polls bus 29, bus 24 and the Victoria line, writes raw
backups and the database). From `backend/`:

```text
uv run --locked python -m ingest.admin init
uv run --locked python -m ingest.database_poller
```

Add `--once` for a single test poll. Server setup (Linux systemd) is described
in [deploy/README.md](deploy/README.md).

**Short raw recorder** (saves complete TfL responses for one segment). From the
repository root:

```text
cd backend
uv run --locked python -m ingest.poller --run ../.local/runs/my-run --minutes 90
```

It currently records the bus 24 segment by default (`--route-id` picks another
configured route). It will support bus 29 once the bus 29 subsegment has its
ordered stop list.

## Repository layout

| Path | Contents |
| --- | --- |
| `backend/app/` | FastAPI app, model and Gemini Ask handler |
| `backend/ingest/` | TfL recorders, derivation and database tooling |
| `backend/config/routes.json` | Configured routes and stops |
| `backend/sql/` | Database schema and queries |
| `deploy/` | Recorder service files for a Linux VM |
| `PLAN.md` | Full product and implementation plan |
| `docs/PROJECT.md` | Agreed decisions, stack and ownership |
| `docs/PROGRESS.md` | What is done and verified |
| `tasks/` | One handoff file per task or role |

## Team

| Role | Person | Focus |
| --- | --- | --- |
| D – Data | Jintian | Recording, inference, database, server |
| M – Model | Olivia | Model, evaluation, submission |
| B – Backend | David | API, Gemini, contracts, integration |
| F – Frontend | To be confirmed | UI, pitch, demo video |

## Contributing

Work on short feature branches and open a pull request into `main`. See
[CONTRIBUTING.md](CONTRIBUTING.md) for setup and workflow.

If you use an AI coding assistant (Codex, Claude Code, Copilot, Gemini CLI,
Cursor), its rules live in [AGENTS.md](AGENTS.md), not in this README.

## License

[MIT](LICENSE)
