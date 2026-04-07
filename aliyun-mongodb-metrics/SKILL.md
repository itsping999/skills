---
name: aliyun-mongodb-metrics
description: 阿里云 MongoDB 监控数据拉取规范。用于复用当前已登录的阿里云控制台会话，拉取 MongoDB 周期监控与操作行为指标，并写入项目 data/aliyun/mongodb 目录。
---

# 阿里云 MongoDB 监控数据拉取规范

## 1. 目的

在不离开用户当前真实 Chrome/Aliyun 登录会话的前提下，拉取 MongoDB 的周期监控数据与操作行为指标，沉淀为结构化 JSON，供周报或专项分析复用。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为目录与执行口径补充来源；若不存在，以当前文档和同目录模板为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 周报周期优先以 `data/weekly/weekly-input.*.json` 为对齐依据。
- 监控数据最终维护在 `data/aliyun/mongodb/` 目录下。
- 若资源区分地域，默认先从 `华南1（深圳）/ cn-shenzhen` 开始查找，但必须继续检查其他地域；不允许只查深圳后就停止。

## 3. 适用场景

- 需要为周报补充 MongoDB 的 query/insert/update/delete/getmore/command 等操作数据。
- 需要观察当前连接数、网络流量、网络请求、asserts、page faults 等指标。
- 需要保留一份可复用的 MongoDB 周期快照，供后续报告、分析或比对。

## 4. 输入与输出

输入：
- 当前已登录阿里云控制台的 Chrome 页面。
- 目标地域、目标实例、目标统计周期。

输出：
- `data/aliyun/mongodb/mongodb-metrics.<region>.<instance-slug>.<start>.<end>.json`

## 5. 操作步骤

1. 复用当前 Chrome DevTools MCP 已接入的真实浏览器会话。
   - 禁止切换到干净浏览器或隔离 profile。
   - 保持阿里云控制台登录态。

2. 确定统计周期。
   - 优先读取现有 `data/weekly/weekly-input.<week_start>.<week_end>.json`。
   - 默认回退顺序：`week_cycle -> recent_7d -> recent_3d -> recent_1d`。

3. 在 DAS 实例监控页定位 MongoDB。
   - 页面一般为 `https://hdm.console.aliyun.com/#/dbMonitor/MySQL` 中的 `MongoDB` tab。
   - 列表接口：`GetHDMLogicInstances`
   - 指标接口：`GetHDMLogicInstanceMetrics`

4. 优先拉取已验证可用的核心指标：
   - `mongodb.opcounters.query`
   - `mongodb.opcounters.insert`
   - `mongodb.opcounters.update`
   - `mongodb.opcounters.delete`
   - `mongodb.opcounters.getmore`
   - `mongodb.opcounters.command`
   - `mongodb.connections.current`

5. 再补充行为与稳定性指标：
   - `mongodb.network.bytesIn`
   - `mongodb.network.bytesOut`
   - `mongodb.network.numRequests`
   - `mongodb.asserts.regular`
   - `mongodb.asserts.warning`
   - `mongodb.asserts.msg`
   - `mongodb.asserts.user`
   - `mongodb.page_faults`

6. 做结果归一化。
   - 无样本：标记为 `no_data`
   - `opcounters`、`network.numRequests` 更适合直接按时间点统计均值、峰值和最后值
   - `page_faults` 为 0 也应保留，便于说明当前内存页故障压力不高
   - 如果当前实例在界面展示为副本集视角，指标值仍以 DAS 返回结果为准
   - 若本次使用的是报告日采集到的数据，来源时间说明写入 `notes`；`report_highlights` 只能写结果结论，不得出现“快照代理本周”之类的过程性表述

7. 写入结构化 JSON 并校验。
    - **必须严格按照 `templates/mongodb-metrics.template.json` 模板格式输出**
    - 目标路径：`data/aliyun/mongodb/mongodb-metrics.<region>.<instance-slug>.<start>.<end>.json`
    - 写完后执行 `jq empty <file>`
    - 拉取完成后关闭本次为 MongoDB 打开的相关浏览器标签页；不要关闭用户原本已打开且仍在使用的页签

## 6. 推荐输出结构

- `scope`
- `collection`
- `preferred_period`
- `generated_at`
- `instances`
- `aggregate_metrics`
- `report_compatibility`
- `report_highlights`
- `notes`

## 7. 必查清单

- 已确认使用的是当前真实阿里云登录会话，而不是干净浏览器。
- 周期优先与周报周期对齐。
- `opcounters / 当前连接 / 网络请求 / asserts / page faults` 已尽量补齐。
- 对不可用指标使用 `no_data`，不伪造数据。
- 输出文件命名、地域、实例名、起止日期一致。

## 8. 禁止事项

- 不允许只验证“能新开页面”就认定已接入真实会话。
- 不允许跳过周期对齐，直接随意取一个时间段。
- 不允许把当前无样本的内存或 cursor 指标当成已经成功采集。
- 不允许通过其他资源（如 ECS、RDS、Redis）的接口字段、认证方式、响应结构来推测 MongoDB 的接口。阿里云不同产品的控制台接口相互独立，ECS 或 RDS 的请求模型、认证机制、返回格式不适用于 MongoDB。每个资源必须从该资源控制台页面的实际 Network 请求中提取接口规范。

## 9. 完成后反馈

至少反馈：
- 使用的实例名称与实例 ID。
- 实际采用的统计周期。
- 输出 JSON 路径。
- 本次值得写入周报的重点观察结论。

## 10. 数据模板

参考模板文件：`templates/mongodb-metrics.template.json`

输出 JSON 必须包含的字段：
- `scope.resource_type`：资源类型，固定为 `RDS MongoDB`
- `scope.region_id`：地域 ID，如 `cn-shenzhen`
- `scope.instance_count`：实例数量
- `preferred_period.window`：时间窗口类型
- `preferred_period.start/end`：统计周期起止日期
- `generated_at`：ISO 格式时间戳
- `instances`：实例数组，每项包含：
  - `instance.id/name/role`：实例 ID、名称、角色
  - `metrics`：指标对象，每项包含 `status`、`metric_name`、`summary`（含 `sample_count`、`point_value_avg`、`latest_value`）
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
- 部分页面移除 modal 后可能仍有权限弹窗，需额外处理

### 11.2 DAS/RDS API 认证问题

**问题描述**：
DAS 页面使用不同的 `hdm-console_zh-cn` config，ECS secToken 无法直接用于 DAS API。

**解决方案**：
通过阿里云控制台页面直接访问 `rdsnext.console.aliyun.com` 而非 DAS，页面会展示 RDS 概览数据。

### 11.3 MongoDB 特有指标不可用问题

**问题描述**：
DAS API 返回的是通用数据库监控指标，而非 MongoDB 特有的指标（如 `mongodb.opcounters.query`、`mongodb.opcounters.update`、`mongodb.connections.current`、`mongodb.page_faults`）。

**解决方案**：
- 对于 DAS API 没有返回的 MongoDB 特有指标，统一标记为 `no_data`
- 可用的通用指标（如 `num_requests`）可代理为 `network_requests`
- 模板要求的是结构正确，数据可以是 `no_data`
- 如需获取完整的 MongoDB 特有指标，可能需要直接连接 MongoDB 实例执行 `serverStatus` 或 `opcounters` 命令
