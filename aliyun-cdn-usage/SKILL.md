---
name: aliyun-cdn-usage
description: 阿里云 CDN 资源包用量拉取规范。用于复用当前已登录的阿里云控制台会话，拉取各地域资源包总量、已用量、剩余量、域名概览与近 7 天带宽峰值，并写入项目 data/aliyun/cdn 目录。
---

# 阿里云 CDN 资源包用量拉取规范

## 1. 目的

在不离开用户当前真实 Chrome/Aliyun 登录会话的前提下，拉取 CDN 各地域资源包总量、当月已用量、剩余量、域名概览与近 7 天带宽峰值，沉淀为结构化 JSON，供周报或成本分析复用。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为目录与执行口径补充来源；若不存在，以当前文档和同目录模板为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 使用结果最终维护在 `data/aliyun/cdn/` 目录下。
- 若资源区分地域，默认先从 `华南1（深圳）/ cn-shenzhen` 开始查找，但必须继续检查其他地域；不允许只查深圳后就停止。

## 3. 适用场景

- 需要补充各地域 CDN 资源包总量、当月消耗与剩余量。
- 需要知道当前 CDN 域名总数与在线情况。
- 需要为周报补一条 CDN 近 7 天带宽峰值。

## 4. 输入与输出

输入：
- 当前已登录阿里云控制台的 Chrome 页面。

输出：
- `data/aliyun/cdn/cdn-usage.<scope>.<start>.<end>.json`

## 5. 操作步骤

1. 复用当前 Chrome DevTools MCP 已接入的真实浏览器会话。
   - 禁止切换到干净浏览器或隔离 profile。
   - 保持阿里云控制台登录态。

2. 打开 CDN 概览页。
   - 页面一般为 `https://cdn.console.aliyun.com/overview`。

3. 拉取域名列表接口并读取页面当前可见的资源包看板。
   - 域名接口：`DescribeUserDomains`
   - 概览页直接读取：
     - 域名总数与在线数量
     - 近 7 天带宽峰值
     - 各地域资源包总量
     - 各地域资源包当月用量
     - 各地域资源包剩余量
     - 各地域资源包剩余占比
     - 静态 HTTPS 请求数当月用量

4. 做结果归一化。
   - 资源包用量默认按 `current_month_to_date` 记录，不强行对齐周报周期。
   - 带宽峰值作为单独的 `recent_7d_peak_bandwidth` 保留。
   - 如果控制台直接展示资源包总量、剩余量或剩余比例，优先保留 UI 原值，不自行换算覆盖。
   - 若只拿到总量与已用量，也可以补算 `package_remaining`，但必须在 `notes` 中说明是推导值。
   - 没有可抵扣资源包的地域，明确标记为 `postpaid`。

5. 写入结构化 JSON 并校验。
    - **必须严格按照 `templates/cdn-usage.template.json` 模板格式输出**
    - 目标路径：`data/aliyun/cdn/cdn-usage.<scope>.<start>.<end>.json`
    - 写完后执行 `jq empty <file>`
    - 拉取完成后关闭本次为 CDN 打开的相关浏览器标签页；不要关闭用户原本已打开且仍在使用的页签

## 6. 推荐输出结构

- `scope`
- `collection`
- `preferred_period`
- `generated_at`
- `domain_inventory`
- `usage_overview`
- `report_compatibility`
- `report_highlights`
- `notes`

## 7. 必查清单

- 已确认使用的是当前真实阿里云登录会话，而不是干净浏览器。
- 域名总数、资源包总量、当月用量、剩余量、近 7 天带宽峰值已尽量补齐。
- 明确区分“月累计用量”和“近 7 天峰值”这两个不同统计窗口。

## 8. 禁止事项

- 不允许把 CDN 月累计资源包用量硬写成周报精确周期数据。
- 不允许忽略“无可抵扣，后付费”的地域状态。
- 不允许只记录带宽峰值而漏掉各地域资源包总量、用量或剩余量。
- 不允许通过其他资源（如 ECS、RDS）的接口字段、认证方式、响应结构来推测 CDN 的接口。阿里云不同产品的控制台接口相互独立，ECS 或 RDS 的请求模型、认证机制、返回格式不适用于 CDN。每个资源必须从该资源控制台页面的实际 Network 请求中提取接口规范。

## 9. 数据模板

参考模板文件：`templates/cdn-usage.template.json`

输出 JSON 必须包含的字段：
- `scope`：资源范围（resource_type, scope_type, selection_basis）
- `collection`：数据来源（source, dashboard_view, apis_observed, secondary_signals）
- `preferred_period`：统计周期信息（primary_window, secondary_window）
- `generated_at`：ISO 格式时间戳
- `domain_inventory`：域名清单（total_count, online_count, domains 数组）
- `usage_overview`：用量概览，包含：
  - `recent_7d_peak_bandwidth`：近 7 天带宽峰值
  - `package_usage_by_region`：各地域资源包用量数组
- `report_compatibility`：周报兼容性说明
- `report_highlights`：周报可直接引用的摘要结论
- `notes`：数据来源说明

## 10. 常见问题

### 10.1 产品面板 Modal 阻挡问题

**问题描述**：
CDN 控制台页面加载时会弹出"产品与服务"模态框，阻挡页面内容。

**解决方案**：
```javascript
const modal = document.querySelector('[role="dialog"]');
if (modal) {
  modal.remove();
  return 'Modal removed';
}
```

### 10.2 CDN API 认证问题

**问题描述**：
CDN API endpoint 不同于 ECS，`https://cdn.console.aliyun.com/data/api.json` 返回 `ApiNotFound`。

**解决方案**：
通过 CDN 控制台 UI 直接读取页面数据，不需要调用 API。

### 10.3 控制台读取优先

CDN 控制台概览页通常可直接读取：
- 域名总数与在线数量
- 近 7 天带宽峰值
- 各地域资源包总量/当月用量/剩余量

## 11. 完成后反馈

至少反馈：
- 域名总数与在线数量。
- 主要消耗地域、低剩余资源包地域与无资源包地域。
- 输出 JSON 路径。
- 本次值得写入周报的重点观察结论。
