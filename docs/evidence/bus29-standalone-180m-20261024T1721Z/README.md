# 公交29短段：180分钟独立录制最终交接

2026-10-24，17:21:48–20:21:55 UTC（18:21–21:21 BST）。原CLI正常完成并自动打包，
没有提前停止或重启采集。Data provided by Transport for London.

- 354次轮询，353次成功、1次失败；5条独立推断行程、251个事件。
- `data_gate=pass`；`support_state=low_data`；`acceptance_gate=pending_source_trace_review`。
- 4个有成功轮询的UTC小时；有可用行程的小时为17、19、20，共3个。
- 15条行程目标未达；不能用数据库56条替代或合并这5条。5条总数也不保证任一
  出发时点的时间窗有5条支持。无风险建议、实测到站、人工签字或校准保证。

## 交接文件

[segments.csv](segments.csv)、[quality.json](quality.json)、[route.json](route.json)、
[stop_events.json](stop_events.json)、[audit_review.json](audit_review.json)、
[local_time_features.json](local_time_features.json)保留原生成内容。
M的`model.load_handoff`实际读取5行、使用5行、排除0行，见[载入报告](model-load-report.json)。

[verification.json](verification.json)记录：全部原始轮询在内存重放，与5条CSV和251个事件
完全一致；原始JSONL与GZIP解压SHA256一致；4个ZIP均通过CRC和包内清单校验；
最终数据ZIP的全部canonical raw轮询与原始恢复后的轮询逐条一致。
验证未改写原run、原review、原ZIP或数据库。

最终数据ZIP（7,446,496字节）SHA256：

```text
a2387081646e5f835941250bbb8ca1af48d006396d056c59149e2bc8cb768371
```

最终源码ZIP（37,724字节）SHA256：

```text
3d8558b7eea9c26d2ba87a4fe7b97948e2713b7254b76f1808a9d18880423c69
```

完整raw和ZIP保留于录制机器原run的`exports/`，不入Git。原run名
`bus29-short-20261024T1721Z`，需要完整包时由数据负责人提供。
公开可复核脚本只读取原run，不执行包内源码，不产生新导出：

```text
python -B docs/evidence/bus29-standalone-180m-20261024T1721Z/verify_capture.py --run <original-run-directory>
```

脚本使用显式异常校验，Python优化模式下也不会跳过检查。
[MANIFEST.json](MANIFEST.json)记录本目录文件SHA256；它不是外部真实性签名。

## M3使用的新数据库快照

另见[20:25:58 UTC的新数据库冻结快照](../bus29-db-final-20261024T202558Z/README.md)：
短段56条/8个小时，长段48条/6个小时；这是另一个推断管线的口径，单独交付供模型复核。
原16:55 UTC演示快照不变，新快照不会自动替换演示数字。
