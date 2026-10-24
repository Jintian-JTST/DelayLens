# DelayLens frontend (role F)

React + TypeScript + Vite, consuming the API contract in `backend/app/schemas.py`
and `PLAN.md` §6.3. The frontend owns no provider credentials or backend logic.

## Run locally

Use Node.js 20.19+ or 22.12+ and npm. These commands work in PowerShell, bash and
zsh, from the repository root:

```text
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. The development server proxies `/api` to
`http://127.0.0.1:8000`. In a second terminal, start the backend from its checkout:

```text
cd backend
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

When working in separate role worktrees, use B's backend checkout to preview its
latest integration; do not copy or overwrite another role's uncommitted changes.
No real credentials are needed to use the backend's clearly labelled fixtures.
If the backend is offline, select **Try labelled demo** explicitly to explore
the interface. Offline failures never automatically become synthetic success.

For another backend port, copy `.env.example` to `.env` and change `API_TARGET`.
For concurrent frontends, use `npm run dev -- --port 5174` and configure the
backend's `FRONTEND_ORIGIN` if requesting it directly across origins.

## Checks and build

```text
npm test
npm run build
npm run preview
```

Tests cover advisor thresholds, conservative advice, out-of-window what-if
results and the UK's repeated hour on 25 October. Tests compile before running
with Node's test runner; generated test files live in ignored `.local/tests/`.
The production build includes a strict TypeScript check and writes to `dist/`.

For deployment, D serves `dist/` and proxies `/api` to FastAPI on the same origin.
Alternatively, set public `VITE_API_BASE_URL` before building and configure the
backend's allowed frontend origin. Variables prefixed `VITE_` are public:
never put TfL, Gemini or database secrets there. Ports and proxy targets are
configuration, not hard-coded deployment assumptions.

## Interaction and data rules

- The complete departure curve comes from one API response. Moving the risk
  slider, choosing the lower uncertainty bound, or selecting +5/+10/+15 minutes
  recalculates advice locally without network calls.
- Route, deadline and walking edits require submission; a visible pending-change
  notice distinguishes the last result from the edited form.
- The SVG chart resizes without shrinking its text. Pointer and arrow-key
  exploration show exact values; an expandable data table is also available.
- Fixture curves are labelled at the page, chart and provenance levels. The
  optional local demo is explicitly chosen and never simulates live vehicles.
- `insufficient_data` suppresses probabilities and advice. Live service failures,
  empty arrivals, unavailable statistics and missing calibration have explicit
  states. Live arrivals refresh every 30 seconds while their panel is mounted.
- Ask uses the existing `/api/ask` contract. Its returned numbers are displayed;
  the frontend never invents natural-language travel predictions. Interpretation
  chips focus editable form fields. Partial parsing pre-fills usable fields;
  newer form edits cancel pending Ask requests.
- All API timestamps are absolute ISO 8601 instants. Display defaults to the
  browser's labelled time zone. Switch to UTC to specify either occurrence of
  the repeated UK hour unambiguously. Changing the display zone preserves the
  deadline instant.
- Methodology displays real route-hour coverage, database statistics and
  calibration only when the corresponding backend results are available.

## Current integration limits

The existing backend provides fixture curves; real route definitions, recorded
trips, the model, Gemini, statistics and calibration are still dependencies on
the other roles. Frontend success does not verify those services or deployment.
Chrome desktop and phone-sized layouts have been checked; physical-device,
Safari, Firefox and screen-reader verification remain outstanding.

See `docs/demo-script.md` for the table presentation and fixture precautions.
