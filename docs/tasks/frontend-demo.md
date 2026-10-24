# Task: Frontend and pitch (role F)

- Task ID: frontend-demo
- Owner (person / AI tool): F / Codex
- Branch: feat/frontend
- Status: frontend implemented; awaiting real-data integration
- Integrator / reviewer: B; integration order D → M → B → F

## Outcome and acceptance criteria

Implement the React, Vite and TypeScript interface in PLAN.md: journey form,
departure curve with uncertainty, local advisor and what-if controls, live arrivals,
Ask interpretation, methodology, accessible states and a responsive phone layout.
No fixture result can be presented as real observations or live data.

## Ownership and dependencies

- Owned files: `frontend/` and this task record.
- Shared contract: consume `backend/app/schemas.py` and PLAN.md §6.3; F does not
  edit the backend contract or other roles' files.
- Dependencies: B's API; D's configured routes and observed trips; M's departure
  model and calibration. Use clearly labelled fixture data while those land.
- Configuration names: `API_TARGET` (development proxy), `VITE_API_BASE_URL`
  (optional public API origin). All provider secrets stay on the backend.

## Handoff

Updated: 2026-10-24 (Europe/London).

- Implemented the responsive React/Vite/TypeScript interface, typed API client,
  route/deadline/walk form, resizable SVG curve and uncertainty band, local risk
  and conservative advisor, and +5/+10/+15-minute what-if controls. Exact chart
  values are available through pointer/keyboard exploration and a data table.
- Added live-arrival polling and refresh, loading/empty/error/low-data states,
  Ask interpretation chips that focus editable form fields, and cancellation
  so late responses cannot overwrite newer form edits.
- Added methodology with binary route/hour coverage, database statistics and
  calibration display. Missing services remain explicitly unavailable.
- Fixture data is labelled prominently; the optional offline demo requires an
  explicit selection and never simulates live arrivals. Insufficient data
  suppresses both probabilities and recommendations.
- Added a two-minute presentation script, real-data rehearsal/recording checklist,
  and an SVG architecture diagram under `frontend/docs/`. The diagram describes
  PLAN.md; it does not assert that the pipeline is deployed.
- Added `frontend/README.md`, safe environment examples and npm's lockfile.
  No changes to backend files or the shared API schema were required.

### Verification

macOS/zsh, Node 24.22.1, npm 12.2.1, Chrome 151.0.7922.172:

- From `frontend/`: `npm run build` — passed strict TypeScript and production
  bundling; `npm test` — **7 passed**, including advisor edge cases and absolute
  time arithmetic across the UK clock change.
- Headless browser verification using the installed Playwright runtime:
  **14 checks passed**. The actual local backend supplied fixture routes/curves
  and its unavailable Ask response. Intercepted API payloads exercised offline,
  empty, insufficient/low-data, unavailable live arrivals, successful Ask,
  interpretation editing, stale-response cancellation and missing methodology
  services. Intercepted data does not verify those real integrations.
- Confirmed risk, conservative and what-if changes issue no curve requests;
  invalid walking times prevent submission; switching to UTC preserves the
  deadline instant. Desktop, 390px and 320px layouts have no horizontal overflow.
- `npm run preview` — compiled production page returned HTTP 200, loaded the
  backend's fixture curve, rendered desktop/mobile layouts and had no uncaught
  browser errors. Final chart text remains readable at phone widths.
- Validated architecture SVG XML, UTF-8, trailing whitespace and absence of
  personal absolute paths in the 25 intended source/documentation files.
- QA screenshots and the temporary browser runner are in ignored
  `frontend/.local/qa/`. They are labelled fixture previews, not submission
  evidence of real predictions. Generated `dist/` and test output are ignored.

### Remaining dependencies and next actions

- B integrates the frontend after D and M, following PLAN.md's branch order.
  Development proxy defaults to port 8000; D serves `frontend/dist/` and `/api`
  on one production origin or configures `VITE_API_BASE_URL` plus backend CORS.
- D supplies routes/coverage and real observations; M supplies the model and
  calibration; B connects the real curve, Gemini, statistics and live endpoints.
  Live external services and the deployed site remain unverified by F.
- F runs the real-data end-to-end check, rehearses the script, records the backup
  video and captures Devpost screenshots once the real-data gate passes.
- Physical phones, Safari, Firefox and screen readers remain unverified.
