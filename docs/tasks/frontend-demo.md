# Task: Frontend and pitch (role F)

- Task ID: frontend-demo
- Owner (person / AI tool): F / Codex
- Branch: feat/frontend
- Status: visual refinement and real Victoria curves verified; ready for integration review
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

### Preview follow-up (2026-10-24)

- Restarted the local frontend/backend preview after the user reported an empty
  website. The API now lists real bus and Tube routes, but their departure
  responses report that the prediction model is not connected yet.
- Added a navigation-level **Try demo** control so the labelled interactive curve
  can be explored even while the API is reachable but cannot predict. **Real
  routes** returns to the actual service; data is never silently substituted.
- Passed the production build and all seven unit tests. Targeted Chrome checks
  passed for the real-route empty state, explicit 91-point demo, switching back,
  390px/320px layouts and absence of uncaught browser errors.

### Real Victoria curves and low-data design (2026-10-24)

- Updated against B's integrated model on `feat/api` (`568844b` at verification).
  No shared API schema changes were needed. The initial route now prefers the
  most recorded trips, which selects Victoria over the currently empty bus route.
- Prominent preliminary-estimate notices accompany the chart and advice. The
  inspected point shows its trip count. The frontend mirrors B/M's policy that
  only departure points with at least 15 trips are recommendation-eligible;
  changing tolerance or the conservative setting cannot bypass that rule.
  Coordinate updates to this eligibility threshold with B and M.
- API-omitted minutes leave gaps in both probability and uncertainty paths.
  The complete requested time axis stays visible and a coverage note explains
  missing points. Isolated points retain their uncertainty whisker.
- The form shows reported coverage and offers an explicitly historical
  recorded-hour example. The user submits it; future deadlines are not silently
  replaced. Results also show their calendar date.
- Actual API/browser verification: Victoria, deadline `2026-10-24T14:30:00Z`,
  `low_data`, 66 returned points, 5–14 trips per point, no recommendation.
  Desktop and phone widths rendered without overflow or browser errors. Actual
  screenshots are saved in ignored `.local/qa/low-data-real*.png`.
- Passed `npm run build` and **11 unit tests**. Intercepted browser cases also
  verified all-low-data and mixed-data eligibility, disconnected SVG segments,
  risk/conservative controls, and 390px/320px layouts. These intercepted cases
  supplement the real-API check; they do not represent additional real journeys.
- Next: B integrates F; D deploys the combined build. Rehearse the recorded-hour
  real-data flow and capture a stable demo/video after integration. Keep recording
  data and verify additional endpoints/calibration as those integrations mature.

### Visual refinement (2026-10-24)

- Preserved the page order, interaction flow and cream/orange/purple identity.
  Consolidated duplicate base selectors and breakpoint sections in the stylesheet;
  shared tokens now control body/helper/metadata sizes, card padding, field gaps,
  section gaps and control sizes instead of a trailing layer of corrective rules.
- Body text is 14px, helper text 12px and essential metadata at least 11px.
  Phone text inputs and selects use 16px; chart axes and legends use 12px.
  Route names wrap in the route summary, and chart readouts/legends wrap on narrow
  screens. Chart geometry, missing-data gaps and probability logic are unchanged.
- Buttons, navigation, selects, slider hit areas, the checkbox label and the
  departure-data disclosure have at least 44px targets. The checkbox itself remains
  a conventional 20px visual control inside its larger clickable label.
- Kept low-data/provenance notices visible and aligned the loading, offline,
  insufficient-data and demo states with the same typography and spacing system.
  Checked normal text contrast at 4.5:1 and large text at 3:1 in rendered states;
  retained visible keyboard focus and reduced-motion behavior.
- Passed `npm run build`, all **11 existing unit tests**, `git diff --check`,
  and **9 grouped browser acceptance checks**: five viewport widths (1440, 1024,
  768, 390, 320), long route names, control sizes, contrast, keyboard chart
  exploration/tab order, normal/low/insufficient/offline/loading/demo states,
  methodology, and reduced motion. Risk, what-if and conservative interactions
  still issue no additional curve requests. No uncaught browser errors occurred.
- Verified 200% zoom-equivalent reflow using 720 CSS pixels and device scale 2
  for a 1440px-wide display, including chart keyboard control and no horizontal
  overflow. Native headless Chrome zoom controls were unavailable; manual native
  browser zoom and physical-device verification remain outstanding.
- Refreshed actual API-backed screenshots at
  `frontend/.local/qa/polished-final-{1440,768,390,320}.png`, plus state and
  zoom-equivalent QA screenshots. These artifacts and the temporary QA runner
  are ignored. Only the stylesheet and this handoff changed; there are no API,
  model, recommendation-threshold or dependency changes.
