# 公交29路：联网数据库到浏览器的实际证据

捕获：2026-10-24 **19:57:55.657–19:58:18.744 UTC**，即20:57–20:58 BST。
源码：main `2d7e51cd6c43ef18a12bdc181b1cf49b83b75568`；只给验收脚本增加数据库模式，
没有修改应用、模型、契约或依赖锁文件。Data provided by Transport for London.

## 链路和边界

Tiger Data 的真实已录制预测 → 现有只读数据库缓存 → 原模型/API（8021）→
React/Vite（5182）→ Chrome。没有启用离线快照或合成fixture，也没有拦截成功API响应。
这证明联网数据库的**历史推断行程重放**，不是公网部署、实时到站、实测到站或未来校准。

API读取私有本地配置，数据库连接为只读；配置值没有复制到本包。TfL与Gemini调用禁用，
未启动数据库写入或新采集。浏览器只允许本地同源请求，API在后台读取真实远端数据库。
缓存按现有60秒周期刷新；数据持续增长，之后再次运行的源行程数可能改变。

页面初始因Victoria记录最多而选择该路线；本次通过正常表单选择公交29短段，
切换UTC并填入24日历史截止时间。未修改应用的默认路线策略。

## 实际结果

路段：Mornington Crescent → Tottenham Court Road；前后步行均5分钟，迟到容忍10%。
捕获时API报告53条源行程、7个有记录的UTC小时；不是每个出发点都有53条独立样本。

| 截止时间（UTC） | API/UI结果 | 每个出发点的行程数 |
| --- | --- | --- |
| 16:00 | `ok`，91点；建议15:22，估计准时概率0.9174（页面显示92%） | 17–22 |
| 14:30 | `low_data`，77点，无建议，what-if禁用 | 5–17 |

14:30并非没有数据；其中存在至少15条行程的点，但没有符合90%目标的出发建议。
风险、保守估计和晚5分钟交互均在本地计算，不新增曲线请求；1440/390/320px均无横向
溢出。方法页正确区分Wilson与run-bootstrap区间。10组验收通过，无JS异常或意外HTTP错误。
实时TfL面板的503状态是本次明确禁用后的预期结果，不算实时到站集成成功。

## 可复核文件

- [验收报告](report.json)、[路线和覆盖读回](routes-response.json)。
- [16:00请求](deadline-1600-request.json) / [浏览器完整响应](deadline-1600-response.json)。
- [14:30请求](deadline-1430-request.json) / [浏览器完整响应](deadline-1430-response.json)。
- [实际curl完整响应](curl-1600-response.json) / [响应头](curl-1600-headers.txt)。
- [浏览器/curl逐字段比对](curl-comparison.json)：相同请求、全部业务响应字段一致。
- [桌面建议](recorded-1440.png)、[320px建议](recorded-320.png)、
  [320px低数据](low-data-320.png)、[方法页](methodology-1440.png)。
- [SHA256与字节清单](MANIFEST.json)，用于检测变化，不是外部签名。

curl通过同一前端代理实际执行，HTTP200，单次总耗时0.105815秒；这不是网络p95基准。
curl使用浏览器保存的同一请求文件；响应的全部points、recommended、what_if、
data_quality均一致，只有server_ms运行耗时不参与比较。响应并不回显route或deadline，
这两项从实际请求核验。JSON重排缩进、响应头规范为LF，字段未删减。

从本目录可重复同一请求（需先配置并启动对应API/前端）：

```text
curl --silent --show-error --request POST --header "Content-Type: application/json" --data-binary @deadline-1600-request.json http://127.0.0.1:5182/api/departure-curve
```

[验收脚本](../../../scripts/qa/bus29-browser.cjs)增加可选`QA_DATA_MODE=database`，
同时设置`QA_BASE_URL`、`QA_OUTPUT_DIR`、本机`PUPPETEER_MODULE`和`CHROME_EXECUTABLE`。
未指定模式时仍为原离线快照验收；该默认模式也重新跑过10组检查。
此脚本不会配置数据库、读取密钥、启动服务或更改采集进程。
