---
name: incident-management
description: 事故数据与报告管理规范。用于维护事故输入、生成事故报告、刷新年度汇总并校验模板一致性。
---

# 事故数据与报告管理规范

## 1. 目的

统一管理事故相关数据与文档，覆盖以下能力：

- 原始事故信息整理与标准化
- 事故报告生成
- 年度汇总维护
- 改进项字段更新后的同步刷新
- 事故模板一致性校验

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为口径补充来源；若不存在，以当前文档和同目录模板为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 事故等级定义见 `templates/incident-severity-levels.md`，仅支持：`P0` `P1` `P2` `P3` `P4`。
- 事故编号格式定义见 `templates/incident-id-format.md`，格式：`INC-YYYYMMDD-SYSTEM-ISSUE`。
- 事故报告模板见 `templates/incident-postmortem-template.md`。
- MTTR 口径：`开始修复处理时间 -> 恢复时间`。

## 3. 适用场景

- 用户提供事故文字材料，要求整理为标准 JSON 并生成事故报告。
- 新增事故、补录历史事故或修正既有事故字段。
- 年度汇总需要同步刷新、去重、修复链接或调整排序。
- 改进项、负责人、截止时间、状态、复发风险、复查时间发生变化。
- 需要校验事故模板结构是否完整一致。

## 4. 输入与输出

输入：
- 原始事故信息（文本、表格或已有文档）。
- 目标输入文件：`data/incidents/incident-input.<yyyy-mm-dd>.<topic>.json`

输出：
- `reports/incidents/<year>/<incident_id>.md`
- `reports/incidents/annual/<year>.md`

可选后续发布：
- 当用户要求同步到钉钉文档时，更适合在本地 Markdown 生成成功后，再调用通用 `dingtalk-docs` skill 上传对应 `.md` 文件。
- 具体上传到哪个目录，不由本 skill 固化；目录选择由当前业务场景决定，例如按年份上传到某个事故记录目录。
- 事故场景下，调用 `dingtalk-docs` 时更适合显式传入目标目录名，例如年度事故目录 `云平台故障记录（2026）`。

## 5. 常用入口

以下命令默认在当前 skills 仓库根目录执行。

如需生成或刷新事故报告与年度汇总，可使用：

```bash
python3 incident-management/scripts/generate_incident_report.py --input data/incidents/<input-file>.json
```

如需校验事故模板一致性，可使用：

```bash
python3 incident-management/scripts/validate_incident_templates.py --scope incident
```

若同一年内涉及多条事故调整，更适合按时间顺序逐条处理，便于核对年度汇总变化。

如需同步到钉钉文档，更适合在上述本地生成完成后，再调用 `dingtalk-docs` 执行上传，而不是在本 skill 内直接操作钉钉页面。

## 6. 建议核对项

- 事故编号日期与发生时间日期一致。
- 报告采用 V2 结构（见 `templates/incident-postmortem-template.md`）。
- 报告中的 MTTR 与口径一致（开始修复处理时间到恢复时间）。
- 时效指标表已包含 MTTD、MTTA、缓解时长、MTTR、全量恢复总时长。
- 年度汇总包含该事故，且报告标识与事故编号一致。
- 复发风险、改进项未完成数量与 JSON 一致。
- 每个事故编号在 annual 中仅出现一次。
- `5.2 改进项清单` 与源 JSON 中的结构化字段一致。

## 7. 约束与边界

- 一般不建议直接手改 `reports/incidents/annual/<year>.md` 来修正数据。
- 一般不建议绕过 `data/incidents/*.json`，直接把事故报告正文视作最终数据源。
- 一般不建议只改 Markdown 而不更新源 JSON。
- 本 skill 负责事故数据与本地 Markdown 产物，不负责固化钉钉目录名。
- 若需要同步钉钉，通常由本 skill 先产出本地 `.md`，再把“上传哪个文件到哪个目录”的决定交给调用方或后续发布步骤。

## 8. 完成后反馈

反馈中通常可包含：
- 更新的输入 JSON 路径。
- 生成或刷新的事故报告路径与年度汇总路径。
- 本次使用的 MTTR 起算时间与计算结果。
- 剩余未完成改进项数量（若本次涉及改进项维护）。
