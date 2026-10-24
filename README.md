# DelayLens

**Language / 语言:** [English](#english) · [中文使用手册](#chinese)

<a id="english"></a>

**When should I leave?** DelayLens records live London bus predictions from TfL,
infers traceable journey samples, and is being built to help you choose a departure
time from an empirical journey-time distribution with visible data-support limits.

Built by a team at OxHack 2026, University of Oxford.

## Demo user guide

### Start here

| What you want | What to run | Requirements |
| --- | --- | --- |
| Explore the interactive UI | Frontend only, then click **Try demo** | Node.js/npm; no API keys or database |
| Use recorded journeys and the real API | Frontend + backend, then **Real routes** | Python/uv and a configured database with recorded segments |
| See current TfL predictions | Real mode's **Next to arrive** panel | Backend, network access and `TFL_APP_KEY` |
| Ask in natural language | **Ask DelayLens** in real mode | Backend and `GEMINI_API_KEY`; optional |

**Quickest preview:** from the repository root, run the following and keep the
terminal open. Use Node.js **20.19+ within 20.x, or 22.12+** and npm.

```text
cd frontend
npm ci
npm run dev
```

Open [the demo](http://127.0.0.1:5173), then click **Try demo** in the top
navigation. If the backend is offline, **Try labelled demo** in the connection
panel does the same thing. This explicitly selects synthetic data; the page
keeps an **Interactive demo / Fixture data** label. Ask is disabled and live
vehicles are not simulated. Click **Real routes** to return to the API.

For the full local app, also start the backend in a **second terminal**, following
[Run the API](#run-the-api). The frontend proxies `/api` to port 8000. A working
health endpoint does not establish that recorded data is available.

### What you can choose

| Control | How to use it |
| --- | --- |
| **Your route** | Select a configured origin/destination pair; arbitrary A-to-B and transfers are outside this MVP. Demo mode has one synthetic Camden Town → Oxford Circus route. |
| **I need to arrive by** | Set the arrival date and time at your final destination, including the walk after the stop. |
| **Time zone** | Browser time zone by default, or UTC. Switching preserves the selected instant. |
| **Walk to stop / Walk from stop** | Walking minutes before and after the ride, each 0–60; both default to 5. |
| **Find my departure / Update my journey** | Submit after changing route, deadline or walking times. |
| **Chance of being late** | Your acceptable risk, initially 10% (target: at least 90% on time). Lower values are stricter. The advisor updates locally. |
| **Use a conservative estimate** | Choose using the lower uncertainty bound. This does not guarantee arrival. |
| **On plan / +5 / +10 / +15 min** | Compare leaving later than an eligible recommended departure; unavailable outside the returned curve or without a recommendation. |
| **View departure data** | Expand the chart's exact values and supporting trip counts. The chart also supports pointer and arrow-key exploration. |
| **Our methodology** | Inspect data coverage, provenance and available statistics/calibration. Missing services have explicit states. |

**Try it:** in labelled demo mode, keep both walks at 5 minutes, submit a deadline,
move the late-risk slider, toggle the conservative option, then compare **+5 min**.
The curve plots departure time horizontally and on-time probability vertically;
the shaded region is the displayed uncertainty band. These demo values and counts
are synthetic.

### Recorded data and optional features

Real mode currently lists bus **29** (Finsbury Park or Mornington Crescent →
Tottenham Court Road), bus **24** (Warren Street → Leicester Square or Tottenham
Court Road), and **Victoria** (Brixton → Oxford Circus). Bus 29 remains the agreed
main demo route; the presence of another option does not prove sample coverage.
The frontend initially selects the route with the most reported trips.

If a route reports coverage, click **Try a recorded-hour example**, then
**Find my departure / Update my journey**. This fills a historical deadline;
it does not turn recorded Saturday data into a future forecast. A deadline outside
coverage may return no curve. Fewer than 5 usable runs means `insufficient_data`;
5–14 means **Preliminary estimate**, with no recommendation; a departure needs at
least 15 usable runs for advice. Counts alone do not prove calibration.

**Ask DelayLens** accepts a journey question in real mode, displays its
interpretation, and lets you edit the form. Without Gemini, use the form directly.
**Next to arrive** is a separate live-prediction panel, refreshing every 30 seconds;
it is not a measured arrival or the historical probability curve.

### Troubleshooting

| Symptom | Next step |
| --- | --- |
| Service offline / cannot load routes | Start the backend on port 8000 and retry, or explicitly choose **Try demo**. |
| Connected but no curve | Check recorded coverage, try the recorded-hour example and submit; check database configuration. Insufficient data is a valid result. |
| Curve but no recommended time | Check sample counts and risk target; sparse data or no qualifying departure can suppress advice. |
| Ask or live arrivals unavailable | Configure the relevant backend key/network; the regular form and labelled demo remain available. |
| Port 5173 occupied | Use `npm run dev -- --port 5174`, then open port 5174. |
| Backend on another port | Copy `frontend/.env.example` to `frontend/.env`, change `API_TARGET`, and restart Vite. |

Stop a foreground local server with **Ctrl+C** in its terminal. Frontend checks
and build commands are in [frontend/README.md](frontend/README.md).

## Main route: London bus 29

The team has agreed to build the demo around **London bus route 29**. The
configured route is outbound from Finsbury Park (Blackstock Road) towards
Tottenham Court Road Station (`bus-29-outbound-finsbury-park-tottenham-court-road`
in [backend/config/routes.json](backend/config/routes.json)).

The configuration also includes a short bus 29 subsegment, Mornington Crescent
to Tottenham Court Road. Its presence does not establish usable sample coverage
or manual validation. The **bus 24 validation segment** is already verified;
the Victoria line remains optional. A working bus 24 pipeline does not establish
bus 29 sample coverage.

## How it works

1. **Record** - a poller asks the TfL API for arrival predictions every 30 seconds
   and saves raw responses before downstream processing.
2. **Infer** - the standalone validator infers stop events from near-stop
   prediction sequences and advancing source frames. Unsupported disappearance
   stays uncertain. TfL supplies predictions, not measured actual arrivals.
3. **Model** - completed bus runs can feed the NumPy empirical replay model for
   a given reference time. The API adapter reads recorded segments through its
   database cache when configured.
4. **Answer** - the API exposes departure choices with evidence counts. Fewer
   than 5 usable runs is `insufficient_data`; 5-14 is preliminary; 15+ supports
   an empirical estimate. No sample-count threshold proves calibration.
5. **Ask (optional)** - Gemini turns a plain-English question into a form request;
   the normal form remains available without it.

### How the model works

DelayLens answers "if I leave at time *d*, how likely am I to arrive by my
deadline?" by **replaying recorded trips**, with no fitted formula or timetable.

1. You reach the origin stop at *d* plus your walk to the stop.
2. Every recorded minute within **±60 minutes** of that London local time, on the
   same date, is replayed. Combining dates, such as Saturday with Sunday, must be
   requested explicitly and is never done silently. With ±30 minutes, bus 29 never
   reached the 15 trips needed for advice (see the
   [bus 29 window check](docs/evidence/bus29-db-snapshot-20261024T1655Z/README.md)).
3. Each replayed minute boards the first recorded bus leaving at least 1 minute
   later, and its inferred arrival plus your walk from the stop gives one outcome.
4. The share of outcomes arriving by the deadline is the estimated chance of
   being on time; median and 90th-percentile arrivals are reported too.

**Unknown stays unknown.** A replayed minute is set aside (censored), not counted
as late, when it falls in a recording gap, after the recording ends, or when the
next bus was seen leaving the origin but its trip could not be confirmed.

**Evidence tiers** count distinct bus runs, not replayed minutes or prediction rows:

| Usable runs | Shown |
| --- | --- |
| 0-4 | Counts only: no probability, band or recommendation |
| 5-14 | Preliminary estimate with a wider 90% Wilson interval; no recommendation |
| 15+ | Estimate, 90% run-bootstrap band and a "leave by" recommendation |

For 15+ runs the 90% band resamples whole runs (200 bootstrap resamples), so it
describes sampling variability in our inferred data. For 5-14 runs the API shows a
wider 90% Wilson interval over distinct runs instead
([backend/app/curves.py](backend/app/curves.py)). The recommendation is the latest
departure whose estimated chance of being late is within your tolerance
(default 10%); the conservative option uses the band's lower edge.

**Limitations.**

- **Arrivals are inferred, not measured.** Stop events are inferred from TfL
  arrival predictions; no actual arrival times were measured.
- **One Saturday afternoon.** The usable data covers Sat 24 Oct 2026, roughly
  14:50-18:00 London time, so it says nothing about weekdays or peak hours.
- **Thin data gets no answer.** Below 15 runs there is no recommendation, and
  below 5 runs only sample counts are shown.
- **Calibration is preliminary.** The `/api/calibration` blocked hold-out scores
  the model against the same inferred events, not measured arrivals; its status
  is never "validated".

Evidence: [bus 24 validation](docs/evidence/bus24-validation-20261024/README.md)
and the [bus 29 snapshot](docs/evidence/bus29-db-snapshot-20261024T1655Z/README.md).
Code: [backend/app/model.py](backend/app/model.py), with hand-checked tests in
[backend/tests/test_model.py](backend/tests/test_model.py).

## Status

| Part | State |
| --- | --- |
| Data validation | Bus 24: 60-minute capture completed, 121 successful polls, 4 traceable inferred trips; CSV and snapshots exported |
| Database recorder | Separate recorder and SQL tooling retained; its archive/derivation contract differs from the standalone validator |
| Backend API | FastAPI health, routes, departure-curve and Ask endpoints |
| Model | Replay with censoring, evidence tiers, run-bootstrap band and advisor, served by `/api/departure-curve` with a ±60-minute window (PR #20) |
| Frontend | React/Vite planner; checked locally against real bus 29 data and the offline snapshot on Sat 24 Oct (Sat 17:00 deadline: about 16:22, 92% live; 16:25, 90% snapshot) |

The bus 24 validation ran on **24 October 2026, 14:53-15:53 Europe/London**
(13:53-14:53 UTC), stopping after 60 minutes at the owner's request. Three
examples were traced to their source predictions; this is agent evidence review,
not independent arrival measurement or human signoff. Four usable trips still
mean `insufficient_data` for probability output.

Real routes return `insufficient_data` when recorded data is not connected or
the requested period lacks enough usable runs. Current progress and verification live in
[docs/PROGRESS.md](docs/PROGRESS.md); data handoff details are in
[backend/ingest/README.md](backend/ingest/README.md).

The recorded [sample CSV and quality report](docs/evidence/bus24-validation-20261024/README.md)
are included for M/B to inspect and load. Complete raw/source ZIPs are delivered
separately; credentials and local recording archives are not committed.

Frontend setup and its own checks are documented in
[frontend/README.md](frontend/README.md). This data validation does not claim a
verified browser journey through the model and live API.

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

**Offline snapshot mode** (no database or network needed for curves) serves the
frozen bus 29 data; a relative path is resolved from the repository root:

```text
# macOS / Linux (bash, zsh)
SNAPSHOT_DIR=docs/evidence/bus29-db-snapshot-20261024T1655Z uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000

# Windows PowerShell
$env:SNAPSHOT_DIR = "docs/evidence/bus29-db-snapshot-20261024T1655Z"
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Without uv, use the backend virtual environment's Python:
`.venv/bin/python -m uvicorn app.main:app --port 8000` (Windows:
`.venv\Scripts\python.exe`). The basis text then ends with "Offline snapshot
frozen 24 Oct 16:55 UTC; not live data"; `/api/stats` is unavailable, and live
arrivals and Ask still need the network.

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
available. The validator defaults to bus 24; other configured routes require an
explicit `--route-id`. Full instructions: [data validation](backend/ingest/README.md).

## Repository layout

| Path | Contents |
| --- | --- |
| `backend/app/` | FastAPI app, model and Gemini Ask handler |
| `backend/ingest/` | Standalone validator and separate database recording/derivation tools |
| `backend/config/routes.json` | Configured routes and ordered validation stops |
| `backend/sql/` | Database schema and queries |
| `frontend/` | React/Vite interface, presentation assets and frontend tests |
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

---

<a id="chinese"></a>

## 中文使用手册

**语言：** [English / 返回英文](#english) · [中文](#chinese)

DelayLens 帮你回答「为了准时到达，我应该几点出门？」。输入路线、到达时间、
前后两段步行时间，再选择能接受的迟到风险，即可查看有数据支持的出发时间曲线。
这是 OxHack 2026 项目，数据来自伦敦交通局 TfL。TfL 提供的是到站预测，
我们从预测序列推断行程，不能把它当成实测到站时间或准时保证。

**只想先体验：看下面的「只运行前端」。想接入真实录制数据：再启动后端。**
本页同时保留中英文，默认从上方英文开始阅读；顶部「中文使用手册」会跳到这里。

### 1. 先选你想运行的模式

| 模式 | 可以体验什么 | 需要什么 |
| --- | --- | --- |
| **Try demo：交互演示** | 表单、概率曲线、风险滑块、保守估计、晚出发对比 | 只启动前端；不需要后端、数据库或密钥 |
| **Real routes：真实数据** | API 提供的路线、录制时段和历史行程曲线 | 前端 + 后端；数据库里有对应路线、时段的可用行程 |
| **Next to arrive：实时到站预测** | 起点站下一班车的 TfL 预测 | 后端、网络和 `TFL_APP_KEY`；独立于历史曲线 |
| **Ask DelayLens：自然语言输入** | 用一句话描述行程，再检查和修改识别结果 | 后端和 `GEMINI_API_KEY`；可选功能 |

演示模式始终显示 **Interactive demo / Fixture data**，概率和样本数是合成示例。
它不模拟实时车辆，Ask 也会禁用。接入失败时不会自动换成假数据，需要你主动点击演示按钮。

### 2. 只运行前端，先把 demo 玩起来

准备好 Git、Node.js 和 npm。Node 支持 **20.x 中的 20.19 及以上，或 22.12 及以上**。
已有仓库就打开项目根目录；没有的话先执行：

```text
git clone https://github.com/Jintian-JTST/OxHack.git
cd OxHack
```

在项目根目录打开终端，逐行执行。以下命令适用于 PowerShell、bash 和 zsh：

```text
cd frontend
npm ci
npm run dev
```

终端保持打开。在浏览器访问 [本地 demo](http://127.0.0.1:5173)，点击顶部
**Try demo**。如果先看到连接失败提示，也可以点 **Try labelled demo**。
出现演示标识和曲线后，就能操作下面介绍的控件。

推荐第一次这样试：保持两段步行时间各 5 分钟 → 选一个到达日期和时间 →
点 **Find my departure** → 拖动迟到风险滑块 → 勾选保守估计 → 点 **+5 min**
比较晚五分钟出发的结果。点击 **Real routes** 可以切回真实 API。

### 3. 启动完整本地应用：前端 + 后端

前端继续运行。在**第二个终端**打开项目根目录，需要 Python **3.11 及以上**和
[uv](https://docs.astral.sh/uv/)，然后执行：

```text
cd backend
uv sync --locked
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000
```

可打开 [健康检查](http://127.0.0.1:8000/api/health) 和
[API 交互文档](http://127.0.0.1:8000/docs)。网页仍访问
[前端 5173](http://127.0.0.1:5173)，前端会把 `/api` 请求代理到后端 8000。
回到网页点击 **Real routes**；如果已经在真实模式，刷新路线或页面即可。

**后端启动成功，只代表服务可访问。真实曲线还需要数据库连接和足够的录制数据。**
当前代码已有数据库缓存到模型的适配器；没有接上数据或所选时段样本不足时，
显示 `insufficient_data` 是正常结果。

需要外部服务时，把 `backend/.env.example` 复制为同目录的 `.env`，填写自己的配置，
然后重启后端。PowerShell 可以用 `Copy-Item .env.example .env`；bash/zsh 用
`cp .env.example .env`，均在 `backend/` 中执行且确认目标文件尚不存在，避免覆盖已有配置。

| 配置项 | 用途 |
| --- | --- |
| `DATABASE_URL` | 连接已有 Tiger Data / PostgreSQL，读取录制行程；交互演示不需要 |
| `TFL_APP_KEY` | 网页实时到站预测、带认证采集；低频独立验证曾不带 key 运行，不代表网页实时面板也不需要 |
| `GEMINI_API_KEY` | 可选的 Ask 输入；没填时直接使用普通表单 |
| `FRONTEND_ORIGIN` | 前后端直接跨域访问时配置允许的前端地址；默认开发流程通过代理访问 |

`.env` 已被 Git 忽略。密钥和数据库连接串只放后端本地配置，向队友索取共享配置请走私下渠道。
`frontend/.env` 只需要代理等公开配置；`VITE_` 开头的变量会进入浏览器，不能放密钥。

### 4. 页面里能选什么

| 页面英文 | 中文说明 / 操作方式 |
| --- | --- |
| **Journey planner** | 行程规划主页面 |
| **Your route** | 选择预设起终点路段；暂不支持任意地址、换乘或多段行程 |
| **I need to arrive by** | 最终目的地的到达截止日期和时间，包含下车后的步行 |
| **Time zone** | 默认浏览器时区，也可选 UTC；切换会保留同一个绝对时刻 |
| **Walk to stop** | 出门走到起点站的分钟数，0–60，默认 5 |
| **Walk from stop** | 下车走到最终目的地的分钟数，0–60，默认 5 |
| **Find my departure / Update my journey** | 提交计算；改路线、到达时间或步行时间后，需要再点一次 |
| **Chance of being late** | 可接受的迟到风险，默认 10%，即目标为至少 90% 准时；越低越严格，滑动后本地即时更新建议 |
| **Use a conservative estimate** | 按不确定区间下界选择出发时间，比使用中心估计更保守 |
| **On plan / +5 / +10 / +15 min** | 以符合条件的建议出发时间为基准，比较晚出发 5、10、15 分钟；没有建议或超出曲线范围时不可用 |
| **View departure data** | 展开每个出发时间的概率、不确定区间和支持行程数；曲线也可以用鼠标或方向键查看 |
| **Our methodology** | 查看数据覆盖、来源和可用的统计、校准信息；缺失时显示不可用状态 |
| **Next to arrive** | 起点站实时到站预测，面板打开时每 30 秒刷新，也可手动刷新 |

曲线**横轴是出发时间，纵轴是准时到达概率**；阴影表示显示的不确定区间，
目标线对应你选择的风险要求。合成演示中的阴影也是示例，不能用于真实出行判断。

真实模式目前配置了以下选项，**出现在菜单里不等于已经有足够数据**：

| 线路 | 起点 → 终点 | 用途 |
| --- | --- | --- |
| 巴士 29 | Finsbury Park / Blackstock Road → Tottenham Court Road Station | 团队确认的主线路 |
| 巴士 29 短路段 | Mornington Crescent Station → Tottenham Court Road Station | 已配置的短路段，需检查其数据覆盖 |
| 巴士 24 | Warren Street Station / Euston Road → Leicester Square Station | 已完成独立采集验证的路段 |
| 巴士 24 短路段 | Warren Street Station / Euston Road → Tottenham Court Road Station | 备用短路段 |
| Victoria 地铁线 | Brixton Underground Station → Oxford Circus Underground Station | 已配置的可选线路，主 MVP 仍以巴士 29 为准 |

交互演示模式只有一条 **Camden Town → Oxford Circus** 合成路线。真实模式初始优先选
API 报告行程数最多的路线，不一定是巴士 29。

### 5. 怎么查看真实数据，以及为什么没有曲线

先选路线，查看表单里的 **recorded hours** 和最近录制时间。如果出现
**Try a recorded-hour example**，点它填入历史截止时间，再点
**Find my departure / Update my journey** 提交。这比随意填一个未来时间更容易落在录制范围内，
但仍可能因为样本不足而没有结果。

| 状态 | 意思 / 可以期待的结果 |
| --- | --- |
| `insufficient_data`，0–4 个可用行程 | 数据不足，不显示概率和出发建议 |
| `low_data` / **Preliminary estimate**，5–14 个 | 初步估计，可探索有支持的曲线；这些出发点不提供建议 |
| 某出发点有 15 个及以上可用行程 | 才有资格参与出发建议；还需满足所选风险目标，不保证一定有建议 |

样本数按独立可用行程算，不能拿预测记录行数或每分钟重放点数充数。样本数量达到门槛
也不代表模型已校准。曲线中断表示该时段缺少支持，不能自行补齐。

数据日期和时段要与查询对应：周六录制的历史回放不能直接说成周日预测。
2026 年 10 月 25 日英国换冬令时，本地 01:00 会出现两次；如需明确区分，使用 UTC。

项目保留的巴士 24 验证记录来自 **2026 年 10 月 24 日伦敦时间 14:53–15:53**：
121 次成功采集、4 个可追溯的推断行程，仍不足以输出概率。原始预测追溯不等于独立实测到站。
可查看[样本 CSV 和质量报告](docs/evidence/bus24-validation-20261024/README.md)，
这份导出也不会因为后端启动就自动加载为 API 数据。

### 6. Ask 和实时面板怎么用

在真实模式的 **Ask DelayLens** 输入一句行程描述，例如：
`I need to get to Tottenham Court Road by 6 pm, with 5 minutes of walking at each end.`
检查返回的路线、日期、时间和风险，点击识别结果旁的 **Edit** 修改对应表单项。
解析不完整时补齐字段再提交；Ask 不可用时直接填表，不影响普通操作。

**Next to arrive** 是另一个独立面板：显示 TfL 当前预测，不是历史曲线，也不是车辆实测到站。
演示模式不会编造车辆；真实模式缺少 key、网络失败或没有班次时会显示相应状态。

### 7. 常见问题与停止运行

| 遇到的情况 | 怎么处理 |
| --- | --- |
| `npm`、`python` 或 `uv` 找不到 | 安装对应运行时/工具后重新打开终端；uv 安装见上方官方链接 |
| 网页显示 **Service offline** / 连接不上 | 确认后端终端仍在运行，检查 8000 的健康接口；只体验界面可点 **Try demo** |
| 已连接但没有曲线 | 检查数据库、录制覆盖和样本数，试录制时段示例后提交；连接成功不代表数据足够 |
| 有曲线但没有出发建议 | 检查可用行程数和风险目标；数据不足不能靠调整滑块绕过 |
| Ask / 实时到站不可用 | 检查对应后端配置和网络；可以继续使用普通表单或合成演示 |
| 5173 端口占用 | 前端执行 `npm run dev -- --port 5174`，浏览器改访问 5174 |
| 后端用了另一个端口 | 复制 `frontend/.env.example` 为 `.env`，改 `API_TARGET` 后重启前端；后端用匹配的 `--port` 启动 |
| 想关闭本地 demo | 在前端、后端各自终端按 **Ctrl+C**；无需停止其他采集任务 |

### 8. 可选：采集数据和运行检查

**单纯体验网页不用启动采集器。** 需要录制数据时，先确认没有另一个规范数据库写入器运行。
独立验证器与数据库采集器格式不同，不能把一方的原始文件直接喂给另一方，也不能直接合并样本。

独立验证器只用 Python 标准库，不依赖数据库。在项目根目录执行；选择一个新的运行目录，
默认录制巴士 24，`--minutes` 是录制分钟数：

```text
python -m backend.ingest record --run .local/runs/my-run --minutes 60
python -m backend.ingest replay --run .local/runs/my-run
python -m backend.ingest export --run .local/runs/my-run
```

`record` 需要访问 TfL；后两条是离线重放和导出。其他已配置路线通过 `--route-id` 显式选择。
独立验证器不会自动读取 `backend/.env`，本地配置需按其手册用 `--env-file` 指定。
数据库采集器的初始化和启动见[英文采集说明](#run-a-recorder)及
[采集器详细手册](backend/ingest/README.md)；Linux 服务见[部署说明](deploy/README.md)。

需要检查代码时，分别在对应目录执行：

```text
# frontend/：前端测试和生产构建
npm test
npm run build
npm run preview
```

```text
# backend/：后端测试
uv run --locked pytest -q
```

`npm run preview` 在构建后预览产物，默认端口为 4173；它不会启动后端。
第一次完整体验使用上方 `npm run dev` 流程。
普通后端测试无需凭据或网络，真实数据库等集成检查需显式配置。
这些是使用命令，不代表本次文档修改已经执行了所有测试或部署。

### 9. 继续阅读

| 文件 | 内容 |
| --- | --- |
| [前端说明](frontend/README.md) | 前端启动、配置、测试、构建与当前集成限制 |
| [实现计划](PLAN.md) / [项目约定](docs/PROJECT.md) | MVP 范围、数据规则、架构和分工 |
| [项目进度](docs/PROGRESS.md) / [任务记录](tasks/) | 已执行验证、待办和交接；分支状态可能不同 |
| [协作流程](CONTRIBUTING.md) | 队友本地配置、独立工作区和 PR 流程 |

团队：D 数据 / Jintian，M 模型 / Olivia，B 后端 / David，F 前端人员待确认。
数据由 Transport for London 提供，见
[TfL 官方开放数据说明](https://tfl.gov.uk/info-for/open-data-users/our-open-data)。
项目采用 [MIT 许可证](LICENSE)。

[返回顶部 / Back to top](#delaylens) · [English](#english)
