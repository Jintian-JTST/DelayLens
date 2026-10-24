# 公交29：最终交接用只读数据库快照

冻结于2026-10-24 **20:25:58.575884 UTC**（21:25:58 BST），用于M3后续复核。
使用现有`backend/tools/export_db_snapshot.py`和API相同的`app.db.load_snapshot`，
只读Tiger Data，没有改写数据库或启动采集。Data provided by Transport for London.

| 路段 | 推断行程 | 起点事件 | 有记录UTC小时 | 行程起点范围（UTC） |
| --- | --- | --- | --- | --- |
| Mornington Crescent→Tottenham Court Road | 56 | 63 | 8（13至20时） | 13:49:20–20:02:12 |
| Finsbury Park→Tottenham Court Road | 48 | 65 | 6（14至19时） | 14:06:14–19:42:58 |

共享791条轮询时间，13:49:34–20:25:30 UTC。两条路线按数据库现有口径均超过
15条和3个小时；这个计数不证明逐点支持、推断正确或校准成立。
不要与[独立180分钟录制的5条](../bus29-standalone-180m-20261024T1721Z/README.md)合并计数。

每条路线含`segments.csv`、`origin_events.csv`和`coverage.json`；共享
[summary.json](summary.json)与[poll_times.csv](poll_times.csv)。现有离线加载器已实读，
行程数/覆盖计数一致，episode键唯一，每条时长及起点事件链接通过，轮询时间无重复；
见[verification.json](verification.json)。[MANIFEST.json](MANIFEST.json)提供逐文件SHA256。

M可将`SNAPSHOT_DIR`设置为本目录，再运行现有API/回测；比较时明确路段、截止时间、
步行、±60分钟窗、旧/新数据日期和校准状态。此目录是历史预测推断数据，不是实时到站、
实测或校准证明。未改原16:55 UTC快照，未把新数据的数字冒充既有演示结果。
