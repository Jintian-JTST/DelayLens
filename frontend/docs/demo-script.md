# DelayLens — table demo (role F)

Target: 2 minutes, with F presenting and a technical teammate available.
This script is ready for rehearsal; the live-data gate is not yet met.

## Before showing it to judges

1. M chooses a route and deadline inside the recorded coverage hours. D confirms
   data recording, the deployed URL and the fallback snapshot. B verifies the
   API, including Ask. F checks the page on the presentation device and a phone.
2. Confirm fixture banners are absent because the result uses real recorded
   observations. Do not hide a banner to make synthetic output look real.
3. Choose a route with enough journeys and rehearse its actual recommendation.
   The example percentages below are deliberately omitted: read the live result.
4. If Ask is unavailable, start with the form. If the API is unavailable, use
   D's verified recorded-data snapshot, then the backup video of that real flow.
   The local labelled demo is for interface review, not proof of prediction quality.

## The two-minute story

| Time      | Speaker and action                                           | Words                                                                                                                                           |
| --------- | ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| 0:00–0:15 | F: show the deadline                                         | “You need to be there by a certain time. A journey planner gives you one estimate. But how much confidence should you put in it?”               |
| 0:15–0:35 | F: enter the chosen route and deadline; optionally use Ask   | “DelayLens starts with your deadline and how much risk you are comfortable with.”                                                               |
| 0:35–1:05 | F: point to the curve, uncertainty band and source label     | “Every departure gets a probability of arriving on time. This band shows uncertainty. Here is how many distinct journeys support the estimate.” |
| 1:05–1:25 | F: change the risk slider, then select +5 minutes            | “Here is the latest departure that meets my target. If I leave five minutes later, this is what happens to my odds. Those changes are instant.” |
| 1:25–1:45 | F/B: show editable Ask chips if the service passed its check | “You can ask in your own words. You can see and edit what was understood. Our journey model, not the language model, provides the numbers.”     |
| 1:45–2:00 | F: briefly show methodology                                  | “We show our data coverage and limitations alongside the decision. Data becomes a prediction, then a time to leave.”                            |

## Questions to hand off

- **M:** empirical replay, distinct-trip bootstrap, calibration and small samples.
- **D:** TfL recording, Tiger Data, UTC timestamps, overnight reliability and backup.
- **B:** API latency, integration boundaries, Gemini validation and honest failures.
- **F:** accessible interaction, mobile layout, local risk controls and error recovery.

## Recording checklist (when the real-data gate passes)

- Capture the deployed real journey, sample count and provenance, then the slider
  and what-if interaction. Record Ask only when it is reliably available.
- Show the methodology coverage and relevant limitations. Keep the core under
  two minutes and keep a copy on the second presentation device.
- Capture Devpost desktop and phone screenshots from the same verified build.
  Current fixture QA screenshots must not be represented as real predictions.
- Use `architecture.svg` as the implementation-plan graphic; confirm each
  integration before describing the whole pipeline as deployed.
