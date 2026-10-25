# 公交29：2026-10-25 06:07Z 只读数据库快照（T17，候选，非默认）

读回时间 **2026-10-25T06:07:32Z**，经 `python -m tools.refresh_snapshot` 只读 Tiger Data（`app.db.load_snapshot`），未改库、未覆盖旧目录。
Data provided by Transport for London.

| 路段 | 行程 | 起点事件 | 有记录UTC小时 |
| --- | --- | --- | --- |
| Mornington Crescent→Tottenham Court Road | 80 | 93 | 13至23时 |
| Finsbury Park→Tottenham Court Road | 70 | 98 | 14至23时 |

轮询1903次，2026-10-24T13:49:34Z–2026-10-25T06:07:09Z。最后一个行程起点为23:56:39Z，之后无新增行程（见 summary.json，原因未核查）。

**周六17:00伦敦（16:00Z）对比**：`--compare-only` 得到 16:22 离开、92%（p=0.9174），与演示数字 **UNCHANGED**。

**默认演示快照仍是** [bus29-db-final-20261024T202558Z](../bus29-db-final-20261024T202558Z/)（56趟）。本目录是历史预测推断数据，不是实测或校准证明；不要与独立录制的趟数合并计数。[MANIFEST.json](MANIFEST.json)含逐文件SHA256。
