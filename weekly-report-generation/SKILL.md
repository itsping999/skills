---
name: weekly-report-generation
description: 周报生成与索引维护规范。用于按周期直出周报、拉取组件源数据、按需补充人工字段并同步维护周报索引。
---

# 周报生成与索引维护规范

## 1. 目的

基于统计周期、事故报告与组件源数据生成标准化周报 Markdown，并同步维护周报索引，保证周期、指标与事故信息一致。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为口径补充来源；若不存在，以当前文档和同目录模板为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 周报结构与字段以 `templates/weekly-report-template.md` 为准。
- 事故相关数据优先从 `reports/incidents/annual/<year>.md` 自动提取。
- 周报统计周期固定为：`上周六 -> 本周五`（7 天，含首尾）。
- 附录资源明细优先从 `data/aliyun/ecs`、`data/aliyun/rds`、`data/aliyun/redis`、`data/aliyun/mongodb`、`data/aliyun/slb`、`data/aliyun/cdn`、`data/aliyun/eip` 自动生成，并补充组件级建议与改进措施。
- ECS 当前优先消费 `data/aliyun/ecs/ecs-metrics.summary.<week_start>.<week_end>.json` 汇总文件；若存在该文件，周报附录会直接展示全量实例，而不是单实例样本。
- `4.1 接口与流量` 当前可以通过 `nginx-log-analysis` skill 从用户提供的 Nginx access log 直接回填，不要求日志文件放在仓库内。
- `3. 交付质量与变更风险` 中的发布次数、发布成功率、回滚次数、CFR 当前优先通过 `aliyun-k8s-release-metrics` skill 从阿里云 K8S 控制台统计。
- `3. 交付质量与变更风险` 中的 `证书到期提醒` 当前优先通过 `aliyun-certificate-expiry` skill 从阿里云数字证书管理服务获取。
- 拉取阿里云资源时，若资源区分地域，默认先从 `华南1（深圳）/ cn-shenzhen` 开始查找，但必须继续检查其他地域；不允许只查深圳后就停止。

## 3. 适用场景

- 新增某周运行周报。
- 修正周报周期（起止日期）或指标值后重生成。
- 周报索引存在重复周期、旧周期残留或链接错误时清理。

## 4. 输入与输出

输入：
- 必填周期：`--week-start <YYYY-MM-DD>` + `--week-end <YYYY-MM-DD>`
- 可选补充输入：`data/weekly/weekly-input.<week_start>.<week_end>.json`

说明：
- 周报脚本现在可以直接按周期生成，不再要求 `weekly-input` 作为主输入。
- `data/weekly/weekly-input.<week_start>.<week_end>.json` 仅作为可选补充输入，用于填充暂未自动采集的数据，例如发布流水、告警事件、接口 SLA、摘要说明、风险与下周重点等。
- 如果已经完成阿里云 K8S 发布统计与证书到期扫描，这些结果也应同步写入补充输入，而不是继续手工改周报正文。
- 当已完成 Nginx 日志分析时，`4.1` 对应的 `traffic_metrics` 也应通过这份补充输入回填。
- 核心可用率默认根据事故报告中的 `开始修复处理时间 -> 恢复时间` 自动计算；若未专门声明影响层级，默认仅计入“平台业务可用率”。
- 当用户明确要求“用生成周报当天的组件数据当作本周数据”时，可以接受使用报告日采集到的组件数据生成当周组件文件，但相关来源说明只能写在对应组件 JSON 的 `notes` 中，不能进入周报正文、`report_highlights` 或补充输入摘要。

输出：
- `reports/weekly/<year>/<year>-W<week>.md`
- `reports/weekly/index.md`

## 5. 操作步骤

1. 校验统计周期满足“周开始=周六、周结束=周五”；若生成阶段性快照，明确使用 `--allow-partial-week`。
2. 生成周报前，先拉取并刷新本周期内依赖的最新 data 数据。
   - **推荐使用多个子代理并行同步拉取**：阿里云各服务（ECS、RDS、Redis、MongoDB、SLB、CDN、EIP、K8S、Voice、Email、Certificate）数据拉取相互独立，推荐使用 Task tool 启动多个 general 子代理并行执行，每个子代理负责一个服务的完整拉取流程，可大幅缩短总执行时间。
   - 涉及附录资源明细时，必须同步拉取对应组件在该统计周期内的最新 JSON，不允许直接复用过期快照。
   - 如果发现同周期数据文件已存在，也要先确认其内容已覆盖到本次周报统计结束日，确保周期内数据是最新的。
   - 事故报告必须已生成并写入 `reports/incidents/annual/<year>.md`，因为周报中的故障明细、严重度分布和核心可用率都会依赖事故报告。
   - 核心可用率按事故报告中的 `开始修复处理时间 -> 恢复时间` 自动计算；若事故报告未专门声明影响层级，默认仅扣减“平台业务可用率”。
   - ECS 必须优先拉全量实例，而不是只拉单台样本；如果已经拿到全量监控结果，应输出 `ecs-metrics.summary.<week_start>.<week_end>.json`，供周报直接使用。
   - 如果本周只允许使用“周报生成当天”的组件数据作为周数据，则各组件文件可以按该口径生成，但需要在 `notes` 里明确说明数据来源时间；周报正文只写结果，不写“快照代理本周”之类的过程性表述。
   - 如果要回填 `4.1`，优先用 `nginx-log-analysis` 从用户提供的日志路径生成 `data/nginx/*.json`，再把 `traffic_metrics` 写入补充输入。
   - 如果要补 `3. 交付质量与变更风险`，优先从阿里云 K8S 控制台统计发布次数、发布成功率、回滚次数、CFR，再写入补充输入的 `ops_release`。
   - 如果要补 `证书到期提醒`，优先从阿里云数字证书管理服务拉取证书剩余天数，再写入补充输入的 `monitoring_security.cert_expiry`。
   - 如果仍有发布、告警、接口 SLA 或周报摘要未自动化，再更新对应的补充 JSON。
3. 执行生成命令：

```bash
python3 scripts/generate_weekly_report.py --week-start 2026-03-21 --week-end 2026-03-27
```

如需补充人工字段：

```bash
python3 scripts/generate_weekly_report.py --week-start 2026-03-21 --week-end 2026-03-27 --input data/weekly/<input-file>.json
```

阶段性快照命令：

```bash
python3 scripts/generate_weekly_report.py --week-start 2026-03-28 --week-end 2026-03-31 --allow-partial-week
```

4. 若同一年多周数据有变更，按时间顺序逐个重生成。
5. 校验周报正文与索引同步更新。
   - 尤其检查附录是否已经按组件生成，而不是继续沿用手工汇总表。
   - 正文不再维护“云资源运行情况”汇总表和“资源热点”聚合区块；资源观察应以下沉后的组件章节为准。
   - 同时检查每个组件是否已输出“重点观察”和“建议与改进措施”。
   - 周报成文中不展示源数据文件路径；数据文件路径只在执行反馈或排障场景中说明。
6. 优先校验本次新生成的周报文件；如需全量校验，再额外执行全仓校验。

当前项目里仍存在历史旧结构周报，因此：
- 对本次新周报，至少应做单文件模板校验。
- `python3 scripts/validate_report_templates.py --scope weekly` 可能因为历史报告尚未迁移而失败，这不应阻塞本次新周报交付，但要在反馈中说明原因。

单文件校验示例：

```bash
python3 - <<'PY'
from pathlib import Path
from scripts.validate_report_templates import validate_file, WEEKLY_TEMPLATE_MARKER, WEEKLY_HEADINGS
path = Path('reports/weekly/2026/2026-W13.md')
errors = validate_file(path, WEEKLY_TEMPLATE_MARKER, WEEKLY_HEADINGS)
print('OK' if not errors else '\\n'.join(errors))
PY
```

全量校验命令：

```bash
python3 scripts/validate_report_templates.py --scope weekly
```

## 6. 必查清单

- 周报文件名周期、命令行周期、正文标题周期一致。
- 周期为 7 天，且满足“上周六到本周五”。
- 生成前已重新拉取周报周期内的最新 data，各组件 JSON 已覆盖到本次统计结束日。
- 若 ECS 已拉全量数据，周报附录应优先消费 `ecs-metrics.summary.<week_start>.<week_end>.json`，并展示全量实例。
- 若 `4.1` 已用日志分析回填，必须明确该统计口径，例如是否排除 WebSocket、下载类接口，以及响应时间是否只统计成功请求。
- 可用率已按事故报告中的 `开始修复处理时间 -> 恢复时间` 自动计算，并正确裁剪到周 / 月 / 年统计窗口。
- 如果同一时段内存在多个事故，已按时间区间合并后再扣减可用率，避免重复计算不可用时长。
- 若使用补充 JSON，其中的发布、告警、接口 SLA 等字段已按最新源数据同步更新，没有沿用旧周报或旧快照中的历史值。
- 若 `ops_release` 已更新，其来源应优先是阿里云 K8S 控制台统计结果，而不是人工回忆或旧周报复用。
- 若 `monitoring_security.cert_expiry` 已更新，其来源应优先是阿里云数字证书管理服务中的最新证书有效期信息。
- “核心可用率”已体现本周、本月、本年度三个维度。
- 可靠性效率指标包含 MTTD、MTTA、MTTR、MTBF（允许未填写，但结构需存在）。
- 交付质量与变更风险包含发布次数、发布成功率、回滚次数、CFR。
- 索引中同一周报文件仅保留一条有效周期记录。
- 同一指标不在多个主模块重复展示（附录仅保留明细）。
- 附录中的 ECS、RDS、Redis、MongoDB、SLB、CDN、EIP 组件分段应优先来自 `data/` 下已拉取的 JSON。
- 周报正文和附录中不应出现 `data/...` 源文件路径。
- 如果组件文件使用报告日数据作为本周来源，对应 JSON 里必须留下明确 `notes` 说明，但这些来源说明不得直接进入周报正文。
- 不允许使用统计周期之外的旧数据或未刷新数据生成当周周报。
- 附录中的组件建议应尽量由真实指标触发，不要写成固定套话。
- 故障数、MTTR 与当周输入数据口径一致。
- 事故明细链接可打开（若存在）。

## 7. 当前流程总结

当前周报流程已经调整为：

1. 先准备源数据与事故报告。
2. **推荐使用子代理并行拉取**：启动多个 general 子代理同步执行阿里云各服务数据拉取，每个子代理负责一个服务的完整流程（包括移除 modal、访问控制台、读取数据、按模板生成 JSON、验证格式、写入文件）。
3. ECS 拉全量实例并优先产出汇总文件，其他组件各自产出当前周或报告日代理周的 JSON。
3. 若需要回填 `4.1`，直接从用户提供的 Nginx 日志路径做分析，并将结果落到 `data/nginx/` 与可选补充输入。
4. 若需要回填 `3. 交付质量与变更风险`，优先从阿里云 K8S 控制台和数字证书管理服务生成结构化数据，再同步写入可选补充输入。
5. 再按统计周期直接生成周报。
6. 若部分字段暂时没有自动来源，再通过可选补充 JSON 补告警、接口 SLA、摘要等内容。

换句话说，`weekly-input` 现在是“补充输入”，不是“主输入”。


**并行拉取示例（伪代码）**：
```
并行启动 12 个子代理：
- 子代理1：ECS metrics（移除modal → 访问ECS控制台 → 拉取全量实例 → 按模板生成JSON → 验证写入）
- 子代理2：RDS metrics
- 子代理3：Redis metrics
- 子代理4：MongoDB metrics
- 子代理5：SLB metrics
- 子代理6：CDN usage
- 子代理7：EIP load
- 子代理8：K8S release metrics
- 子代理9：SMS usage
- 子代理10：Voice usage
- 子代理11：Email usage
- 子代理12：Certificate expiry
等待所有子代理完成后，汇总验证所有JSON文件，再进入周报生成步骤。
```
## 8. 禁止事项

- 不允许手工直接编辑 `reports/weekly/index.md` 修数据。
- 不允许绕过源数据直接修改周报正文作为最终来源。

## 9. 完成后反馈

至少反馈：
- 使用的统计周期。
- 更新的补充输入文件路径（若有）。
- 生成的周报路径与索引路径。
- 本次修正的周期或指标项（若有）。
