# DelayLens: 2-minute stage demo (locked numbers)

This is the stage version of [frontend/docs/demo-script.md](../frontend/docs/demo-script.md).
Every number below comes from the final offline snapshot
`docs/evidence/bus29-db-final-20261024T202558Z`:
- bus 29, Mornington Crescent → Tottenham Court Road;
- ±60-minute window;
- 5-minute walks;
- risk tolerance 10%.

The live database gives the same 17:00 answer. Re-check on the presentation laptop at
the Sunday 10:30 rehearsal.

## Set-up (before judges arrive)

1. Start the offline demo. Leave `DATABASE_URL` unset.
   - **Windows:** `.\scripts\demo.cmd`.
   - **macOS/Linux:** `./scripts/demo.sh`. It opens the browser itself, and Ctrl+C stops
     both servers.
   - **Manual alternative:** from `backend/`, run
     `SNAPSHOT_DIR=docs/evidence/bus29-db-final-20261024T202558Z uv run --locked uvicorn app.main:app --port 8000`.
     Then run `npm run dev` in `frontend/` and open <http://127.0.0.1:5173>.
   - **Without uv:** use `.venv/bin/python -m uvicorn` instead of `uv run --locked uvicorn`.
2. The page opens on **bus 29, Mornington Crescent → Tottenham Court Road**. Press
   **Try a recorded-hour example**. It sets **Sat 24 Oct 17:00**. If it shows anything
   else, type that deadline by hand.
3. Expected on screen:
   - **leave by 16:22, about 92%**, from 18 recorded trips at that departure (up to 22
     across the window);
   - a basis line ending "Offline snapshot frozen 24 Oct 20:25 UTC; not live data."
4. Open a second tab with the same route and deadline **Sat 24 Oct 15:30**. This is the
   no-advice state.
5. Never show the 20:00 or 21:00 deadlines. They read 100% on only a handful of supported
   points, which is an edge effect, not evidence.
6. Fallback order: this laptop → a teammate's laptop with the same commands → the
   backup video.

## Script

| Time | Action | Words |
| --- | --- | --- |
| 0:00–0:15 | Show the form | "Your app says the bus is two minutes away. Eight minutes later you are still waiting. Journey planners give one estimate. We tell you how often it actually holds." |
| 0:15–0:35 | Submit the 17:00 deadline | "I need to be at Tottenham Court Road by 5pm on Saturday 24 October. DelayLens replays every bus we recorded on this route that Saturday." |
| 0:35–1:00 | Point at the curve, then the advice | "Each departure gets an estimated chance of arriving on time. Leave by 16:22 and on our recordings I make it about 92% of the time. This band is our uncertainty, and here is how many recorded trips back it." |
| 1:00–1:15 | Move the risk slider; press +5 min | "Want more certainty? The advice moves instantly. Leave five minutes later and the chance drops, right here." |
| 1:15–1:35 | Switch to the 15:30 tab | "For an earlier deadline no departure reaches our 90% target on the trips we have, so DelayLens gives no recommendation instead of a guess." |
| 1:35–1:50 | Only with network and a Gemini key. Ask: "I need to be at Tottenham Court Road by 5pm on Saturday 24 October, when should I leave Mornington Crescent?" Otherwise skip this row. | "You can also just ask. Gemini only understands the question; our model computes every number, which is why it matches the form." |
| 1:50–2:00 | Methodology tab | "In a held-out backtest on our own recordings, when we said about 92% we were on time about 91% of the time. It is preliminary: one Saturday, and arrivals inferred from TfL predictions." |

**Always say the date.** On Sunday, "by 5pm" means a future 5pm with no recorded data.

## Judge questions

See [judge-qa.md](judge-qa.md) for ten likely questions, who answers each and the evidence
file behind every answer. The short versions:

- *Why not Google Maps?* (M) "Maps gives a best estimate. We show how often it holds,
  and we refuse when the evidence is thin."
- *How fast is it?* (B) A curve takes about 4 ms at p95 on the demo laptop (the smoke
  check makes 20 requests).
