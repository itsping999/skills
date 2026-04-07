---
name: aliyun-email-usage
description: 阿里云邮件推送用量拉取规范。用于复用当前已登录的阿里云控制台会话，拉取可查询窗口内的发送统计、账户额度、按官方单价估算的费用与权限受限项，并写入项目 data/aliyun/email 目录。
---

# 阿里云邮件推送用量拉取规范

## 1. 目的

在不离开用户当前真实 Chrome/Aliyun 登录会话的前提下，拉取邮件推送当前可查询窗口内的发送量、成功率、额度、关键资源概览与估算费用，沉淀为结构化 JSON，供周报或投递质量分析复用。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为目录与执行口径补充来源；若不存在，以当前文档和同目录模板为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 使用结果最终维护在 `data/aliyun/email/` 目录下。
- 若资源区分地域，默认先从 `华南1（深圳）/ cn-shenzhen` 开始查找，但必须继续检查其他地域；不允许只查深圳后就停止。

## 3. 适用场景

- 需要补充邮件推送发信量、成功率与无效地址率。
- 需要补充账户额度、域名数、发信地址数、模板数。
- 需要按官方基础单价估算当前查询窗口或分段汇总后的邮件费用。
- 需要保留 RAM 权限受限导致无法读取的项目。

## 4. 输入与输出

输入：
- 当前已登录阿里云控制台的 Chrome 页面。

输出：
- `data/aliyun/email/email-usage.<region>.<start>.<end>.json`

## 5. 操作步骤

1. 复用当前 Chrome DevTools MCP 已接入的真实浏览器会话。
   - 禁止切换到干净浏览器或隔离 profile。
   - 保持阿里云控制台登录态。

2. 打开邮件推送控制台。
   - 页面一般为 `https://dm.console.aliyun.com/`。
   - 常用地域为 `cn-hangzhou`。

3. 先拉取概览接口，再进入“发送数据”页签。
   - 概览接口：
     - `descAccount.json`
     - `getValidationQuota.json`
     - `getSendifyInfo.json`
   - 页面读取：
     - 日额度、月额度
     - 发信域名数、发信地址数、模板数、标签数
     - Sendify 是否开通
   - 发送数据页读取：
     - 每日总数、成功、失败、无效地址
     - 页面查询时间范围

4. 查询官方定价并估算费用。
   - 优先使用官方定价文档中的按量单价，不要求必须进入账单中心。
   - 当前默认按量口径可记录为：
     - `2.00 元 / 千封`
     - `0.002 元 / 封`
   - 估算公式：
     - `estimated_cost_cny = chargeable_mail_count / 1000 * unit_price_cny_per_1000_mails`
   - 若当前仍有免费额度余量，应在估算前先扣减可用免费量。
   - 若需要近似“当月费用”，但发送数据窗口受限，可按多段时间窗口分别拉取后汇总估算。

5. 做结果归一化。
   - 邮件推送当前控制台通常只提供自定义时间窗口，不直接区分国内/国外。
   - 若独立 IP 等接口返回 `NoPermission`，必须写入 `permission_gaps`，不要写成 0。
   - 若查询窗口不是周报周期，保留真实查询区间，并在兼容说明中注明。
   - 费用字段必须明确标注为 `estimated`，不要伪装成账单实付金额。

6. 写入结构化 JSON 并校验。
    - **必须严格按照 `templates/email-usage.template.json` 模板格式输出**
    - 目标路径：`data/aliyun/email/email-usage.<region>.<start>.<end>.json`
    - 写完后执行 `jq empty <file>`
    - 拉取完成后关闭本次为 Email 打开的相关浏览器标签页；不要关闭用户原本已打开且仍在使用的页签

## 6. 推荐输出结构

- `scope`
- `collection`
- `preferred_period`
- `generated_at`
- `account_overview`
- `send_statistics`
- `cost_estimate`
- `permission_gaps`
- `report_compatibility`
- `report_highlights`
- `notes`

## 7. 必查清单

- 已确认使用的是当前真实阿里云登录会话，而不是干净浏览器。
- 已记录发信统计窗口、总量、成功、失败、无效地址。
- 已记录账户额度与资源概览。
- 已记录单价来源、估算公式与估算费用。
- 已把权限受限项写入 `permission_gaps`。

## 8. 禁止事项

- 不允许把权限不足的指标写成 0。
- 不允许把发送统计窗口误写成整月数据。
- 不允许强行杜撰国内/国外拆分。
- 不允许把估算费用写成"账单实付金额"。
- 不允许通过其他资源（如 ECS、RDS）的接口字段、认证方式、响应结构来推测 Email 的接口。阿里云不同产品的控制台接口相互独立，ECS 或 RDS 的请求模型、认证机制、返回格式不适用于 Email。每个资源必须从该资源控制台页面的实际 Network 请求中提取接口规范。

## 9. 完成后反馈

至少反馈：
- 查询窗口与总发信量。
- 成功率与无效地址情况。
- 当前采用的基础单价与估算费用。
- 当前账户日/月额度。
- 是否存在权限受限项。
- 输出 JSON 路径。

## 10. 数据模板

参考模板文件：`templates/email-usage.template.json`

输出 JSON 必须包含的字段：
- `scope`：地域范围，如 `cn-hangzhou`
- `generated_at`：ISO 格式时间戳
- `preferred_period`：周期对象，包含 `type`、`start`、`end`、`source`
- `account_overview`：账户概览，包含 `user_status`、`quota_level`、`daily_quota`、`month_quota`、`domains`、`mail_addresses`、`templates`、`tags`
- `send_statistics`：发送统计，包含 `daily` 数组和 `summary` 对象
- `permission_gaps`：权限受限项数组（如有）
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
- Email 页面移除 modal 后可能仍有权限弹窗，需额外处理

### 11.2 RAM 权限受限

**问题描述**：
部分接口（如独立 IP 相关接口）可能因 RAM 权限不足返回 `NoPermission`。

**解决方案**：
必须将权限受限项写入 `permission_gaps`，不要写成 0 或忽略不计。
