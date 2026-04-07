---
name: incident-action-maintenance
description: 事故改进项维护规范。用于更新改进项、负责人、截止时间、状态、复查时间与复发风险，并同步到报告与年汇总。
---

# 事故改进项维护规范

## 1. 目的

通过维护源 JSON 的改进项字段，保证事故报告中的闭环状态和年度汇总中的风险状态准确、可追踪。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为口径补充来源；若不存在，以当前文档为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 一切改进项数据以 `data/incidents/incident-input*.json` 为准。

## 3. 适用场景

- 更新改进项负责人、截止时间、状态、优先级。
- 更新 `复发风险`、`复盘复查时间`。
- 需要同步刷新“未完成改进项数量”。

## 4. 输入与输出

输入：
- 指定事故的 `data/incidents/incident-input*.json`。

输出：
- `reports/incidents/<year>/<incident_id>.md`
- `reports/incidents/annual/<year>.md`

## 5. 操作步骤

1. 定位目标事故输入 JSON。
2. 更新字段（优先结构化字段）：
- `改进项清单`（事项/负责人/截止时间/状态/优先级）
- `长期改进`
- `复发风险`
- `复盘复查时间`

3. 执行生成命令：

```bash
python3 scripts/generate_incident_report.py --input data/incidents/<input-file>.json
```

4. 核对事故报告与年汇总同步更新。

## 6. 状态归一规则

以下状态视为“已完成”：
- `已完成` `完成` `关闭` `closed` `completed` `done`

除上述外均计入“未完成改进项”。

## 7. 必查清单

- 事故报告 `5.2 改进项清单` 与 JSON 一致。
- `未完成改进项数量` 计算正确。
- 年汇总的 `未完成改进项`、`复发风险` 与事故报告一致。

## 8. 禁止事项

- 不允许只改事故报告 Markdown 而不改源 JSON。
- 不允许跳过生成脚本直接改年汇总表格。

## 9. 完成后反馈

至少反馈：
- 更新的 JSON 路径。
- 剩余未完成改进项数量。
- 更新后的事故报告与年汇总路径。
