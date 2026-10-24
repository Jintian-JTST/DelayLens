# 公交29路：真实离线数据的浏览器验收

采集验收证据时间：2026-10-24 **19:40:19.438–19:40:30.522 UTC**
（20:40 Europe/London，BST）。原始数据不是此时采集；本次使用
[16:55 UTC冻结数据库快照](../bus29-db-snapshot-20261024T1655Z/README.md)。

**这是离线历史重放，不是实时到站、未来预测、实测到站或校准证明。**
Data provided by Transport for London.

## 实际边界与版本

- 源码基线：`134dafb02a33be6a5c3fe7409ed0888dd2b5abb8`，另含
  `Methodology.tsx` 文案修正：`Record TfL predictions`、
  `Capture TfL predictions over time and infer journey samples.`，以及逐点
  Wilson/bootstrap区间与建议门槛说明。没有修改模型或概率计算。
- 实际链路：冻结CSV/JSON → 原模型及API（本地8017）→ React/Vite浏览器页面
  （本地5183），没有拦截或伪造成功API响应，没有启用合成fixture。
- `SNAPSHOT_DIR` 指向上述冻结目录；数据库、TfL密钥与Gemini配置为空，API运行器
  禁止外部socket连接并禁止数据库连接，浏览器仅允许本地同源请求。
- 独立Chrome使用Europe/London时区；表单明确切换UTC，日期为24日。
- API的live/stats返回明确503不可用；这些不是验收中的成功集成。
- 本包只证明本地离线API/UI，不证明公网部署、网络延迟、实机或无人值守采集。

## 实际结果

| 提交的到达截止时间 | 结果 | 支持/建议 |
| --- | --- | --- |
| 2026-10-24 16:00 UTC | `ok`，91个曲线点 | 26条源行程；建议15:25 UTC，估计准时概率0.90；该建议点19条行程 |
| 2026-10-24 14:30 UTC | `low_data`，77个曲线点 | 没有建议，what-if按钮禁用；图表不默认突出某个高概率点 |

此建议来自当前模型；冻结快照README的旧版示例不是这次响应。前后步行均5分钟，
迟到容忍度10%，出发窗口90分钟。完整真实请求与响应保存在本目录，未裁剪响应字段。

风险20%时建议变为15:27 UTC、估计概率0.83。保守估计和晚5分钟操作生效，三类
交互均不新增曲线API请求。1440/390/320px真实建议和低数据状态无横向溢出；
方法页在1440/320px无横向溢出。10组验收全部通过，JS异常、意外HTTP错误和外网请求均为0。

冻结标签在页面清楚显示：

> Offline snapshot frozen 24 Oct 16:55 UTC; not live data.

区间类型逐点取决于可用行程数：5–14条用90% Wilson区间，15条及以上用90%
run-bootstrap区间；少于5条不返回概率或建议。建议仅从该出发时点有至少15条
可用行程的点中选择。整条曲线标记`low_data`不表示每个点均少于15条；本次14:30
响应逐点数量为5–17条。未修改模型或隐藏区间；概率及到站时间均从TfL预测推断，
没有验证校准。

## 可检查文件

- [完整验收报告](report.json)：实际请求、建议、标签与10组检查。
- [16:00请求](deadline-1600-request.json) / [完整响应](deadline-1600-response.json)。
- [14:30请求](deadline-1430-request.json) / [完整响应](deadline-1430-response.json)。
- [桌面真实建议](recorded-1440.png) / [320px真实建议](recorded-320.png)。
- [320px低数据状态](low-data-320.png) / [桌面方法页](methodology-1440.png)。
- [文件清单与SHA256](MANIFEST.json)：检测文件变化，不是外部签名或真实性担保。

验收脚本：[scripts/qa/bus29-browser.cjs](../../../scripts/qa/bus29-browser.cjs)。
运行需先提供隔离的本地离线API/UI，以及已安装的Puppeteer Core和Chrome。
`QA_BASE_URL`指定前端地址；`PUPPETEER_MODULE`和`CHROME_EXECUTABLE`指定本机依赖；
`QA_SOURCE_REV`记录源码版本；`QA_OUTPUT_DIR`指定输出目录。脚本自动保存两组完整
请求/响应、报告和截图。端口5187在验收主机的保留区间内，因此实际使用5183。

Windows本地现有构建与11项前端单元测试也通过；这些检查不替代上述浏览器证据。
