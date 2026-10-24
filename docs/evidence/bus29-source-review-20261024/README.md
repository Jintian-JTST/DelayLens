# 公交 29 路：三例原始来源审计

2026-10-24，代理来源追溯审查，`human_review_claimed: false`。
这是对已记录 TfL **预测**的来源审查，不是人工签字、独立实测到站或校准验证。
Data provided by Transport for London.

## 审查范围与结果

对应[独立录制交接](../bus29-short-20261024/README.md)，不是数据库快照。
原始记录覆盖 15:46:18–17:16:30 UTC / 16:46–18:16 Europe/London。
179 次原始轮询可离线重放出完全相同的 7 条行程和 162 个事件；原始 JSONL
与解压后的 GZIP 内容一致。原始 JSONL SHA256：

```text
fb08165b9bf0b49295c76e8774c376abac610c4f4bef4c8d75c04d953f2016fc
```

| 车辆 / trip | 推断行程 UTC | 耗时 | 起点/终点最后倒计时 |
| --- | --- | --- | --- |
| LK66GCV / 603050 | 15:53:39 → 16:03:47 | 608 秒 | 21 / 30 秒 |
| LK66HCV / 603101 | 16:26:11 → 16:38:55 | 764 秒 | 23 / 6 秒 |
| LK66HDG / 603119 | 16:32:32 → 16:44:48 | 736 秒 | 14 / 28 秒 |

三例均从完整原始轮询检查：线路、方向、车辆、trip 一致；八站有序；末两次来源
时间间隔不超过 90 秒、ETA 调整不超过 120 秒；来源时钟新鲜且最后倒计时不超过
60 秒；每个端点均有 ETA 后两个成功、健康、不同的确认帧，相隔至少 20 秒且来源
时间递增，完整帧中没有该端点行程记录。

这符合既有 `near_stop_prediction_v1` 规则。消失本身不构成到站证据。
全部 7 条行程的支持状态仍是 `low_data`，不能据此给出风险建议或校准保证。

## 文件与复核

- [audit_review.json](audit_review.json)：沿用既有 exporter 的 agent 审核格式，列出三条
  segment 及其两端 event ID。
- [source_excerpt.json](source_excerpt.json)：每端末两次来源预测、确认帧标识及时间。
  这是精简摘录；仅凭摘录不能独立证明完整帧中缺席，必须用原始记录复核。
- [verify_source_review.py](verify_source_review.py)：从完整原始轮询重新推导并核验上述
  证据、公开交接一致性和文件哈希；只使用标准库及仓库已有 ingestion 代码。
- [MANIFEST.json](MANIFEST.json)：本目录其他文件的 SHA256；它用于检测内容变化，
  不构成外部签名或证据真实性保证。

在仓库根目录运行，将占位路径换成原始 run 目录；命令适用于 Windows/macOS/Linux，
Python 3.11+，无需数据库、网络或密钥：

```text
python -B docs/evidence/bus29-source-review-20261024/verify_source_review.py --run <run-directory> --verify-exporter
```

复核使用 Python 断言；脚本会明确拒绝 `python -O`、`-OO` 或开启
`PYTHONOPTIMIZE` 的运行，避免优化模式跳过证据检查后误报通过。

原始 run 需包含 `run.json` 与 `polls.jsonl` 或 `polls.jsonl.gz`；数据 ZIP 解压目录的
`raw/` 布局也可使用。原始大文件不在 Git 中，须由数据负责人另行提供。
不带 `--verify-exporter` 时仅作读取；带该参数时，在仓库忽略的
`.local/source-review-check/` 下创建并自动移除临时副本，用既有 `write_outputs`
验证三条审查可产生 `acceptance_gate=pass`，且仍保留 `low_data`。

本审计包不会修改原始录制、既有 standalone 交接或已冻结数据库快照。
旧交接的 `pending_source_trace_review` 保留为其当时状态；这里单独补充来源审查证据。

## 交付边界

此次审计只证明原始预测与三条推断样例之间的可追溯关系。它不证明所有推断均正确，
不填补采集缺口，也不验证数据库推导、API、UI、部署、未来日期或跨日预测。
