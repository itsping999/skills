---
name: aliyun-voice-usage
description: 阿里云语音服务用量拉取规范。用于复用当前已登录的阿里云控制台会话，拉取账单月内的计费用量、当月已产生费用与国内/国外可见口径，并写入项目 data/aliyun/voice 目录。
---

# 阿里云语音服务用量拉取规范

## 1. 目的

在不离开用户当前真实 Chrome/Aliyun 登录会话的前提下，拉取语音服务当前账单月内的计费用量、当月已产生费用与商品口径，沉淀为结构化 JSON，供周报或成本分析复用。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为目录与执行口径补充来源；若不存在，以当前文档和同目录模板为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 使用结果最终维护在 `data/aliyun/voice/` 目录下。
- 若资源区分地域，默认先从 `华南1（深圳）/ cn-shenzhen` 开始查找，但必须继续检查其他地域；不允许只查深圳后就停止。

## 3. 适用场景

- 需要补充语音通知、语音推送等用量与当月账单金额。
- 需要判断当前账单是国内还是国际商品口径。
- 需要为周报附录增加一条语音服务资源说明。

## 4. 输入与输出

输入：
- 当前已登录阿里云控制台的 Chrome 页面。

输出：
- `data/aliyun/voice/voice-usage.<region>.<start>.<end>.json`

## 5. 操作步骤

1. 复用当前 Chrome DevTools MCP 已接入的真实浏览器会话。
   - 禁止切换到干净浏览器或隔离 profile。
   - 保持阿里云控制台登录态。

2. 打开语音服务费用统计页。
   - 页面一般为 `https://dyvms.console.aliyun.com/statistic/newcost/overview`。

3. 拉取账单主接口并读取页面当前可见账单。
   - `GetUserBill`
   - `ListCustomBillTab`
   - 页面读取：
     - 账期
     - 产品名称、商品名称、费用项名称
     - 原价、账单金额、优惠金额

4. 做结果归一化。
   - 优先保留账单月累计用量与当月已产生费用。
   - 若商品码带 `public_cn` 等明显国内标识，应写出当前口径为国内。
   - 若当前未观察到国际商品，标注为 `not_observed`，不要写成国际用量 0。
   - 若同月存在多条商品账单项，应合并汇总并保留明细项数组。

5. 写入结构化 JSON 并校验。
    - **必须严格按照 `templates/voice-usage.template.json` 模板格式输出**
    - 目标路径：`data/aliyun/voice/voice-usage.<region>.<start>.<end>.json`
    - 写完后执行 `jq empty <file>`
    - 拉取完成后关闭本次为 Voice 打开的相关浏览器标签页；不要关闭用户原本已打开且仍在使用的页签

## 6. 推荐输出结构

- `scope`
- `collection`
- `preferred_period`
- `generated_at`
- `usage_overview`
- `international_split`
- `report_compatibility`
- `report_highlights`
- `notes`

## 7. 必查清单

- 已确认使用的是当前真实阿里云登录会话，而不是干净浏览器。
- 已记录账单月、计费用量与当月账单金额。
- 已说明当前商品是否属于国内口径。
- 若页面存在权限弹窗，但接口能返回数据，已在备注中说明。

## 8. 禁止事项

- 不允许把月度账单累计误写成精确周数据。
- 不允许在未观察到国际商品时写成国际用量 0。
- 不允许只写金额不写计费用量。
- 不允许通过其他资源（如 ECS、RDS）的接口字段、认证方式、响应结构来推测 Voice 的接口。阿里云不同产品的控制台接口相互独立，ECS 或 RDS 的请求模型、认证机制、返回格式不适用于 Voice。每个资源必须从该资源控制台页面的实际 Network 请求中提取接口规范。

## 9. 完成后反馈

至少反馈：
- 账单月与计费用量。
- 本月已产生费用。
- 当前商品是否为国内口径。
- 输出 JSON 路径。

## 10. 数据模板

参考模板文件：`templates/voice-usage.template.json`

输出 JSON 必须包含的字段：
- `scope`：地域范围，如 `cn-hangzhou`
- `generated_at`：ISO 格式时间戳
- `preferred_period`：周期对象，包含 `type`、`bill_month`、`start`、`end`、`source`
- `usage_overview`：用量概览，包含 `payable_bill_total_amount`、`original_total_amount`、`discount_total_amount`、`items` 数组
- `international_split`：国际拆分对象，包含 `status`（`not_observed` 或 `observed`）和 `reason`
- `report_compatibility`：报告兼容性对象
- `report_highlights`：周报摘要数组
- `notes`：数据来源说明

## 11. 常见问题

### 11.1 产品面板 Modal 阻挡问题

**问题描述**：
阿里云控制台大部分页面加载时会弹出"产品与服务"模态框（modal dialog），阻挡页面内容，导致无法通过 UI 获取数据。

**解决方案**：
```javascript
const modal = document.querySelector('[role="dialog"]');
if (modal) {
  modal.remove();
  return 'Modal removed';
}
```

**注意事项**：
- 每次页面刷新后 modal 会重新出现，需要重新执行移除操作
- Voice 页面移除 modal 后可能仍有权限弹窗，需额外处理

### 11.2 页面直接打开超时问题

**问题描述**：
直接使用 `new_page` 打开 Voice 费用统计页经常超时。

**解决方案**：
改用 `navigate_page` 并设置较长 timeout（如 60000ms）。
