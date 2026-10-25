# DelayLens captioned backup recording — 25 October 2026 (T48)

[Download / play the93-second WebM](delaylens-backup.webm).
[Poster](poster.png) · [browser/API checks](recording-checks.json).

A silent, English-captioned backup of the actual committed UI and locked recorded
data, made by PROJECT_REVIEWER while the team's formal recording/upload ownership
was unconfirmed. It is a local/repository backup, not a completed Devpost video
upload or a confirmed presentation-computer rehearsal. No voiceover/audio track.

## Content and checks

- Actual frontend and FastAPI on main159433c, with the locked
  `bus29-db-final-20261024T202558Z` snapshot and DB/service keys empty.
- Form: bus29 Mornington Crescent to Tottenham Court Road, Saturday24Oct2026
  17:00 Europe/London, walks5/5. Real API returns leave16:22, p=0.9174.
- Actual browser +5min interaction shows16:27/about75%; no synthetic response.
- Journey map displays whole-trip uncertainty, without claiming stop-level delays.
- Actual15:30 API response has no recommendation; visible UI explains why.
- Methodology and captions disclose historical replay, inferred arrivals,
  preliminary calibration and limited single-Saturday evidence.
- No Gemini or speech request/demonstration; live-arrivals requests are blocked
  by the browser. All displayed journey results come from the local API.
- Recording captions are injected only into this recording browser and labelled
  as added captions. No application source/style/default was changed.
- No browser page errors. API assertions verify both deadline scenarios.
- Encoded video is1440x1000, duration1:33.20,7,281,385bytes. Decoded frames were
  checked at30/50/62/78seconds; visual review included curve, advice, what-if,
  map, no-advice and methodology/captions. The poster is an unedited decoded frame.

The recording is a fallback. The team still needs to confirm an accepted hosting
URL, final submission use, Delta links and prize eligibility/selections. This file
is not evidence of public deployment, measured arrivals, real microphone/live
Gemini testing or physical Wi-Fi-off rehearsal.

## Reproduce

Use a clean checkout with backend/frontend dependencies, Playwright and a browser
installed. Start the API in locked snapshot mode with empty database/service keys,
then start Vite against that API. For this capture, localhost ports8198(API) and
5188(UI) were used. No teammate's server was used or stopped.

Run `node record.cjs` with `DEMO_BASE_URL` pointing to the UI and
`RECORD_OUTPUT_DIR` pointing outside the checkout. If using system Chrome, set
`CHROME_EXECUTABLE` to its executable path; otherwise Playwright's installed
Chromium is used. Node must be able to resolve `playwright`. The script captures
actual browser video, verifies the real API responses, and emits checks/screens.
The captured video is WebM/VP8, playable in Chrome. Host/upload acceptance and any
conversion needed for the team's final submission remain separate checks.
