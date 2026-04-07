---
name: aliyun-sms-usage
description: 阿里云短信服务用量拉取规范。用于复用当前已登录的阿里云控制台会话，拉取国内短信发送量、套餐包余量、国际短信状态与当月已产生费用，并写入项目 data/aliyun/sms 目录。
---

# 阿里云短信服务用量拉取规范

## 1. 目的

在不离开用户当前真实 Chrome/Aliyun 登录会话的前提下，拉取短信服务当前可见的发送量、套餐包余量、国际短信启用状态与当月已产生费用，沉淀为结构化 JSON，供周报或容量预警复用。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为目录与执行口径补充来源；若不存在，以当前文档和同目录模板为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 使用结果最终维护在 `data/aliyun/sms/` 目录下。
- 若资源区分地域，默认先从 `华南1（深圳）/ cn-shenzhen` 开始查找，但必须继续检查其他地域；不允许只查深圳后就停止。

## 3. 适用场景

- 需要补充短信发送量、成功率与套餐余量。
- 需要确认国际短信能力是否已启用。
- 需要体现短信服务当月已产生费用，并区分可见的国内/国际账单项。
- 需要为周报增加一条短信资源与容量观察。

## 4. 输入与输出

输入：
- 当前已登录阿里云控制台的 Chrome 页面。

输出：
- `data/aliyun/sms/sms-usage.<scope>.<start>.<end>.json`

## 5. 操作步骤

1. 复用当前 Chrome DevTools MCP 已接入的真实浏览器会话。
   - 禁止切换到干净浏览器或隔离 profile。
   - 保持阿里云控制台登录态。

2. 打开短信服务概览页。
   - 页面一般为 `https://dysms.console.aliyun.com/overview`。

3. 拉取概览页核心接口并读取页面当前可见看板。
   - `QuerySmsStatisticsNew`
   - `QueryPackageSummary`
   - `QuerySmsBaseScreenNew`
   - 页面直接读取：
     - 发送总量、成功、未成功
     - 国内短信套餐包余量
     - 是否存在国际短信入口

4. 进入费用统计页并拉取当月账单金额。
   - 页面一般为 `https://dysms.console.aliyun.com/expense/overview`。
   - 优先使用账单接口：
     - `GetUserBill`
   - 至少保留：
     - 账单月
     - 应付金额、原价金额、优惠金额
     - 费用项名称、商品码、计费用量
   - 若可观察到国际短信账单项，应与国内短信账单项分开记录。
   - 若国际短信未启用或无账单项，必须明确标注为 `not_enabled` 或 `not_observed`，不要伪造为 0。

5. 做结果归一化。
   - 概览页默认优先按“本月”统计。
   - 国际短信若未启用，必须写成 `not_enabled`，不要伪造为 0。
   - 若需要兼容周报，可额外从日序列中裁剪出周报周期摘要。
   - 费用字段优先保留账单实值，而不是估算值。

6. 写入结构化 JSON 并校验。
    - **必须严格按照 `templates/sms-usage.template.json` 模板格式输出**
    - 目标路径：`data/aliyun/sms/sms-usage.<scope>.<start>.<end>.json`
    - 写完后执行 `jq empty <file>`
    - 拉取完成后关闭本次为 SMS 打开的相关浏览器标签页；不要关闭用户原本已打开且仍在使用的页签

## 6. 推荐输出结构

- `scope`
- `collection`
- `preferred_period`
- `generated_at`
- `usage_overview`
- `billing_overview`
- `daily_series`
- `report_compatibility`
- `report_highlights`
- `notes`

## 7. 必查清单

- 已确认使用的是当前真实阿里云登录会话，而不是干净浏览器。
- 已记录国内发送量、套餐包余量与国际短信启用状态。
- 已记录当月账单金额与至少一组短信费用项明细。
- 若国际短信未启用，已明确标注为 `not_enabled`。
- 若补了周报口径，已说明其来自月度日序列裁剪。

## 8. 禁止事项

- 不允许把国际短信未开通写成“国际发送量 0”。
- 不允许只记录发送总量而漏掉套餐包余量。
- 不允许漏记当月费用。
- 不允许脱离当前真实登录会话去启动新浏览器。
- 不允许通过其他资源（如 ECS、RDS）的接口字段、认证方式、响应结构来推测 SMS 的接口。阿里云不同产品的控制台接口相互独立，ECS 或 RDS 的请求模型、认证机制、返回格式不适用于 SMS。每个资源必须从该资源控制台页面的实际 Network 请求中提取接口规范。

## 9. 完成后反馈

至少反馈：
- 本月国内短信发送总量与成功量。
- 当前套餐包余量。
- 本月已产生费用。
- 国际短信是否启用。
- 输出 JSON 路径。

## 10. 数据模板

参考模板文件：`templates/sms-usage.template.json`

输出 JSON 必须包含的字段：
- `dateRange`：日期范围，如 `YYYY-MM-DD to YYYY-MM-DD`
- `period`：账单周期，如 `Month YYYY-MM (current month)`
- `totalSent`：发送总量
- `successCount`：成功量
- `failedCount`：失败量
- `successRate`：成功率（小数形式，如 0.99）
- `dataSource`：数据来源，固定为 `Aliyun SMS Console dysms.console.aliyun.com`
- `fetchDate`：拉取日期

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
- 部分页面移除 modal 后可能仍有权限弹窗，需额外处理

### 11.2 账单接口差异

**问题描述**：
短信服务账单接口 `GetUserBill` 返回的字段结构可能与 Voice 服务不同。

**解决方案**：
优先使用短信服务控制台页面直接读取当前可见的账单数据，而不是跨服务复制接口调用模式。
