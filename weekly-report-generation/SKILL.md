---
name: weekly-report-generation
description: 周报生成与索引维护规范。用于在依赖数据准备完成后，按周期生成周报并维护索引。
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
- 附录资源明细优先从 `<data_root>/ecs`、`<data_root>/rds`、`<data_root>/redis`、`<data_root>/mongodb`、`<data_root>/slb`、`<data_root>/cdn`、`<data_root>/eip` 自动生成，并补充组件级建议与改进措施。
- ECS 优先消费 `<data_root>/ecs/ecs-metrics.summary.<week_start>.<week_end>.json` 汇总文件；若存在该文件，周报附录直接展示全量实例，而不是单实例样本。
- `4.1 接口与流量` 优先从 `<nginx_root>/nginx-traffic.<week_start>.<week_end>.snapshot-*.json` 读取。
- `3. 交付质量与变更风险` 中的发布与证书字段，可优先从 `<data_root>/k8s`、`<data_root>/certificates` 对应结果中提取。

## 3. 适用场景

- 新增某周运行周报。
- 修正周报周期（起止日期）或指标值后重生成。
- 周报索引存在重复周期、旧周期残留或链接错误时清理。

## 4. 输入与输出

输入：
- 必填周期：`--week-start <YYYY-MM-DD>` + `--week-end <YYYY-MM-DD>`
- 可选补充输入：`data/weekly/weekly-input.<week_start>.<week_end>.json`
- 可选云厂商：`provider`（默认 `aliyun`）

说明：
- 周报脚本可直接按周期生成；但更适合先准备好本周期依赖数据，再进入生成阶段。
- 组件指标目录通过 `--data-root` 显式指定，可抽象记为 `<data_root>`。
- Nginx 结构化指标目录通过 `--nginx-root` 显式指定，可抽象记为 `<nginx_root>`。
- `data/weekly/weekly-input.<week_start>.<week_end>.json` 仅作为可选补充输入，用于填充暂未自动采集的数据，例如告警事件、摘要说明、风险与下周重点等。
- 若补充输入与目录内结构化结果同时存在，显式提供的字段优先，缺失字段再由目录结果补齐。
- 核心可用率默认根据事故报告中的 `开始修复处理时间 -> 恢复时间` 自动计算；若未专门声明影响层级，默认仅计入“平台业务可用率”。
- 当用户明确要求“用生成周报当天的组件数据当作本周数据”时，可以接受使用报告日采集到的组件数据生成当周组件文件，但相关来源说明只能写在对应组件 JSON 的 `notes` 中，不能进入周报正文、`report_highlights` 或补充输入摘要。

输出：
- `reports/weekly/<year>/<year>-W<week>.md`
- `reports/weekly/index.md`

可选后续发布：
- 当用户要求同步到钉钉文档时，更适合在本地 Markdown 与索引更新完成后，再调用通用 `dingtalk-docs` skill 上传对应 `.md` 文件。
- 具体上传到哪个目录，不由本 skill 固化；目录选择由当前业务场景决定。

## 5. 参考步骤

1. 可先确认统计周期是否满足“周开始=周六、周结束=周五”；若生成阶段性快照，可结合 `--allow-partial-week` 使用。
2. 生成周报前，更适合先确认本周期依赖数据已经准备完成。
   - 事故数据：`reports/incidents/annual/<year>.md`
   - 组件指标：`<data_root>/ecs`、`<data_root>/rds`、`<data_root>/redis`、`<data_root>/mongodb`、`<data_root>/slb`、`<data_root>/cdn`、`<data_root>/eip`
   - 交付与证书：`<data_root>/k8s`、`<data_root>/certificates`
   - 流量指标：`<nginx_root>/nginx-traffic.<week_start>.<week_end>.snapshot-*.json`
   - 补充输入：`data/weekly/weekly-input.<week_start>.<week_end>.json`
3. 执行生成命令：

   以下命令默认在当前 skills 仓库根目录执行。

```bash
python3 weekly-report-generation/scripts/generate_weekly_report.py --week-start 2026-03-21 --week-end 2026-03-27 --data-root <data_root> --nginx-root <nginx_root>
```

如需补充人工字段：

```bash
python3 weekly-report-generation/scripts/generate_weekly_report.py --week-start 2026-03-21 --week-end 2026-03-27 --input data/weekly/<input-file>.json --data-root <data_root> --nginx-root <nginx_root>
```

阶段性快照命令：

```bash
python3 weekly-report-generation/scripts/generate_weekly_report.py --week-start 2026-03-28 --week-end 2026-03-31 --allow-partial-week --data-root <data_root> --nginx-root <nginx_root>
```

4. 若同一年多周数据有变更，可按时间顺序逐个重生成。
5. 可再核对周报正文与索引是否同步更新。
   - 尤其检查附录是否已经按组件生成，而不是继续沿用手工汇总表。
   - 正文不维护“云资源运行情况”汇总表和“资源热点”聚合区块；资源观察以下沉后的组件章节为准。
   - 同时检查每个组件是否已输出“重点观察”和“建议与改进措施”。
   - 周报成文中不展示源数据文件路径；数据文件路径只在执行反馈或排障场景中说明。
6. 校验时可优先关注本次新生成的周报文件；如需全量校验，再扩展到全仓范围。

模板校验要求：
- 对本次新周报，可优先做单文件模板校验。
- 若执行 `python3 weekly-report-generation/scripts/validate_weekly_templates.py --scope weekly` 失败，仍可继续分析本次结果，但更适合在反馈中说明原因。

单文件校验示例：

```bash
python3 weekly-report-generation/scripts/validate_weekly_templates.py --scope weekly --reports-dir reports
```

全量校验命令：

```bash
python3 weekly-report-generation/scripts/validate_weekly_templates.py --scope weekly
```

## 6. 建议核对项

- 周报文件名周期、命令行周期、正文标题周期一致。
- 周期为 7 天，且满足“上周六到本周五”。
- 生成前已尽量刷新周报周期内的 data，各组件 JSON 较好地覆盖到本次统计结束日。
- `services` 含 `ecs` 时，更适合采用全量实例口径（跨地域、跨分页、全实例）；若仅有单实例样本，可在反馈中说明其适用范围。
- 若 ECS 已拉全量数据，周报附录通常会优先消费 `ecs-metrics.summary.<week_start>.<week_end>.json`，并展示全量实例。
- 若 `4.1` 已读取 `<nginx_root>` 下的结构化结果，更适合明确该统计口径，例如是否排除 WebSocket、下载类接口，以及响应时间是否只统计成功请求。
- 可用率已按事故报告中的 `开始修复处理时间 -> 恢复时间` 自动计算，并正确裁剪到周 / 月 / 年统计窗口。
- 如果同一时段内存在多个事故，已按时间区间合并后再扣减可用率，避免重复计算不可用时长。
- 若使用补充 JSON，其中的发布、告警、接口 SLA 等字段已按本周期最新源数据同步更新。
- 若 `ops_release` 已更新，其来源更适合参考阿里云 K8S 控制台统计结果，而不是人工回忆。
- 若 `monitoring_security.cert_expiry` 已更新，其来源更适合参考阿里云数字证书管理服务中的较新证书有效期信息。
- “核心可用率”已体现本周、本月、本年度三个维度。
- 可靠性效率指标包含 MTTD、MTTA、MTTR、MTBF（允许未填写，但结构需存在）。
- 交付质量与变更风险包含发布次数、发布成功率、回滚次数、CFR。
- 索引中同一周报文件仅保留一条有效周期记录。
- 同一指标不在多个主模块重复展示（附录仅保留明细）。
- 附录中的 ECS、RDS、Redis、MongoDB、SLB、CDN、EIP 组件分段，通常会来自 `--data-root` 指定目录下已拉取的 JSON。
- 周报正文和附录中不应出现 `data/...` 源文件路径。
- 如果组件文件使用报告日数据作为本周来源，更适合在对应 JSON 中留下明确 `notes` 说明，而这些来源说明通常不直接进入周报正文。
- 统计周期之外的旧数据或未刷新数据，更适合作为补充说明而不是直接当作当周正式口径。
- 附录中的组件建议更适合由真实指标触发，而不是固定套话。
- 故障数、MTTR 与当周输入数据口径一致。
- 事故明细中的事故编号与本地事故报告一致。

## 8. 约束与边界

- 一般不建议手工直接编辑 `reports/weekly/index.md` 来修正数据。
- 一般不建议绕过源数据，直接把周报正文作为最终来源。
- 若 ECS 只有样本数据而非全量视图，更适合作为阶段性结果，而不是正式周报交付口径。
- 本 skill 负责周报本地 Markdown 与索引产物，不负责固化钉钉目录名。
- 若需要同步钉钉，更适合在本地周报生成成功后，再把“上传哪个文件到哪个目录”的决定交给调用方或后续发布步骤。

## 9. 完成后反馈

至少反馈：
- 使用的统计周期。
- 更新的补充输入文件路径（若有）。
- 生成的周报路径与索引路径。
- 本次修正的周期或指标项（若有）。
