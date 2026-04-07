---
name: incident-annual-maintenance
description: 年度事故汇总维护规范。用于新增、删除、迁移、重命名事故后，保证 annual 汇总完整且可追溯。
---

# 年度事故汇总维护规范

## 1. 目的

确保 `reports/incidents/annual/<year>.md` 与当年事故报告、源数据保持一致，避免漏项、重项和失效链接。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为口径补充来源；若不存在，以当前文档为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 年度汇总数据来自 `data/incidents/incident-input*.json` + 生成脚本结果，不手工造数。

## 3. 适用场景

- 新增或补录事故后需要更新年汇总。
- 事故编号、标题、地区或时间发生改动。
- 删除历史事故后需要清理年汇总残留行。

## 4. 输入与输出

输入：
- 当年所有 `data/incidents/incident-input*.json`。

输出：
- `reports/incidents/annual/<year>.md`

## 5. 操作步骤

1. 收集目标年份的事故输入 JSON 清单。
2. 逐个顺序执行（禁止并行）：

```bash
python3 scripts/generate_incident_report.py --input data/incidents/<incident-a>.json
python3 scripts/generate_incident_report.py --input data/incidents/<incident-b>.json
```

3. 生成后核对年度汇总排序、字段完整性、链接有效性。

## 6. 必查清单

- 每个事故编号仅出现一次。
- 按 `发生时间` 升序排列。
- `查看报告` 链接可打开且路径正确。
- `恢复时长`、`复发风险`、`未完成改进项` 不为空。
- 与对应事故报告中的关键字段一致。

## 7. 禁止事项

- 不允许人工直接编辑 annual 表格内容来代替重生成。
- 不允许并发执行同一年的多次生成（会覆盖导致不一致）。

## 8. 完成后反馈

至少反馈：
- 维护的年份。
- 年汇总行数变化（若有）。
- 发现并修复的问题（如重复行、坏链接、旧编号残留）。
