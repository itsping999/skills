---
name: incident-postmortem-intake
description: 事故录入与复盘文档生成规范。用于把原始事故信息整理为标准 JSON，并生成事故报告与年度汇总。
---

# 事故录入与复盘文档生成规范

## 1. 目的

将原始事故描述统一转换为项目标准数据，并生成一致的 Markdown 事故报告与年度汇总条目。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为口径补充来源；若不存在，以当前文档和同目录模板为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 事故等级定义见 `templates/incident-severity-levels.md`，仅支持：`P0` `P1` `P2` `P3` `P4`。
- 事故编号格式定义见 `templates/incident-id-format.md`，格式：`INC-YYYYMMDD-SYSTEM-ISSUE`。
- 事故报告模板见 `templates/incident-postmortem-template.md`。
- MTTR 口径：`开始修复处理时间 -> 恢复时间`。

## 3. 适用场景

- 用户提供事故文字材料，要求落库并生成标准报告。
- 新增事故或补录历史事故。
- 需要校验事故编号、等级、时间字段合法性。

## 4. 输入与输出

输入：
- 原始事故信息（文本、表格或已有文档）。
- 目标输入文件：`data/incidents/incident-input.<yyyy-mm-dd>.<topic>.json`。

输出：
- `reports/incidents/<year>/<incident_id>.md`
- `reports/incidents/annual/<year>.md`

## 5. 操作步骤

1. 定位项目根目录（含 `data/`、`reports/`、`scripts/`）。
2. 抽取并标准化字段，优先保留原始明确值。
3. 校验关键治理字段（事故编号、等级、时间格式）。
4. 写入或更新 `data/incidents/incident-input.*.json`。
5. 执行生成命令：

```bash
python3 scripts/generate_incident_report.py --input data/<input-file>.json
```

6. 校验输出文件已更新且内容一致。
7. 执行模板一致性校验：

```bash
python3 scripts/validate_report_templates.py --scope incident
```

## 6. 必查清单

- 事故编号日期与发生时间日期一致。
- 报告采用 V2 结构（见 `templates/incident-postmortem-template.md`）。
- 报告中的 MTTR 与口径一致（开始修复处理时间到恢复时间）。
- 时效指标表已包含 MTTD、MTTA、缓解时长、MTTR、全量恢复总时长。
- 年度汇总包含该事故且链接可打开。
- 复发风险、改进项未完成数量与 JSON 一致。

## 7. 禁止事项

- 不允许直接手改 `reports/incidents/annual/<year>.md` 来“修数据”。
- 不允许绕过 `data/incidents/*.json` 直接改事故报告正文当作最终数据源。

## 8. 完成后反馈

至少反馈：
- 更新的输入 JSON 路径。
- 生成的事故报告路径与年度汇总路径。
- 本次使用的 MTTR 起算时间与计算结果。
