# Task: 公交 29 路独立录制来源审计

- Task ID: chat-data-source-review
- Owner (person / AI tool): Jintian-JTST / D-CodeX raw_trace_audit
- Branch: `codex/chat-data-source-review`
- Status: 审计包与离线核验完成，待主代理复核集成
- Integrator / reviewer: D-CodeX 主代理 / 仓库维护者
- Plan / contract reference: PLAN 3.3–3.5；AGENTS 数据证据边界；聊天室授权的 D 未完项

## Outcome and acceptance criteria

为既有公交 29 路 7 条独立录制行程补三例代理来源审计。公开最小来源摘录、审核
JSON、便携复核脚本和文件哈希；从完整原始轮询重放验证，再通过既有 exporter 的
三例审查门槛。不声称人工签字、实测到站或概率校准。

## Ownership and dependencies

- 仅新增 `docs/evidence/bus29-source-review-20261024/` 和本任务文件。
- 原始 raw run、既有 standalone 交接与冻结数据库快照均保持原样。
- 不修改模型、API、schema、依赖、数据库或其他人的分支/索引。
- 复核依赖 Python 3.11+、仓库 ingestion 源码和数据负责人提供的原始 run；无需密钥。
- exporter 门槛检查只在本工作区忽略的 `.local/source-review-check/` 临时目录写入。

## Handoff

- Changes and relevant commits: 新增独立来源审计包，尚未提交或推送。
- Checks actually run, OS/runtime and results: Windows / PowerShell / Python 3.11.9。
  - 本目录 `verify_source_review.py --run <original-run> --verify-exporter`：三例原始证据
    匹配、179 轮重放、7 条公开行程和 162 个事件一致；既有 exporter 临时副本给出
    `acceptance_gate=pass`、`reviewed_segment_count=3`，仍为 `low_data`。
  - 原始 JSONL 与解压 GZIP 的 SHA256 一致；原 run 四个 ZIP 的 CRC 全通过。
  - `python -B -m unittest discover -s backend/ingest/tests -p test_ingestion.py -q`：31 项通过。
  - 审计脚本 Ruff、公开文件 UTF-8/JSON/尾随空白/本地链接和凭据路径模式检查通过。
  - 复核脚本拒绝 Python 优化模式，避免断言被禁用；所有证据文本固定 LF，按实际
    暂存 Git blob 的字节独立核对 manifest 哈希和大小，防止行尾规范化破坏摘要。
  - 原始审查 JSON 仍为空、原公开质量门槛仍为 pending；冻结证据目录无 Git 变更。
- Unverified behavior or blockers: 不验证实际到站、校准、API/UI/部署；7 条仍为 `low_data`。
- Next action and responsible owner: 主代理复核产物、决定是否集成；旧证据原件不覆盖。
