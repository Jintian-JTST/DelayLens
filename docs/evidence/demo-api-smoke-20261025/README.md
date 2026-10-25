# Clean locked-snapshot API smoke and latency check — T47 (T45 takeover)

The manager checked B's checkpoint and actual checkout: it remained on e31bf98
with uncommitted work; B's listener explicitly reported no execution capability.
No files in that checkout were changed. This run used clean main
`1df3f4bbf43f1c1e26ec61ec382cd40b32e06b44` before adding these evidence files.
The exact actual Git SHA is recorded in [result.json](result.json).

## Result and measurement boundary

- Locked `bus29-db-final-20261024T202558Z`, all database/service keys explicitly
  empty; health returns `status=ok`, `ask_available=false`.
- Bus29 Mornington Crescent to Tottenham Court Road, Saturday24Oct17:00 London,
  walks5/5: leave16:22, p=0.9174, identical for every measured request.
- Uvicorn bound only to an ephemeral loopback port in a separate thread;
  urllib sends real local HTTP requests. Three warmups, then20 samples.
- Warm p95 total **4.3087ms**, API-reported server p95 **3.54ms**.
  Nearest-rank percentile: nineteenth sorted observation of20.
- First curve request after startup and health: **23.2415ms** total,
  **22.08ms** server-reported. This excludes process/server startup time.
- Environment: macOS/Darwin arm64, Python3.14.7; exact OS/runtime/package versions
  and all20 observations are in the result file. One machine and one run only.

This is not public-network latency, an in-process-only handler benchmark, a
load test, physical Wi-Fi-off rehearsal, browser test, real microphone or live
Gemini validation. Background load and hardware affect these measurements.
No external service request was needed; no database write, credential read or
application/default change was made by the measurement script.

## Reproduce

From a clean repository checkout with backend dependencies installed:

```text
python docs/evidence/demo-api-smoke-20261025/reproduce.py --repo . --out ../demo-smoke-result.json
```

The output path should be outside the checkout so a subsequent run still passes
the clean-checkout gate. The script forces the locked snapshot and empties service
credentials in its own process without modifying environment files. It starts and
stops its own isolated HTTP server; it does not use or stop teammates' servers.
The imported application can load dotenv, but explicitly empty variables take
precedence and no credential values are read or emitted by this script.
