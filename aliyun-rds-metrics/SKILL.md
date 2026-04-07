---
name: aliyun-rds-metrics
description: 阿里云 RDS MySQL 监控数据拉取规范。用于复用当前已登录的阿里云控制台会话，优先从深圳开始排查并继续覆盖其他地域的 MySQL RDS 周期监控、慢查询与锁等待等指标，并写入项目 data/aliyun/rds 目录。
---

# 阿里云 RDS MySQL 监控数据拉取规范

## 1. 目的

在不离开用户当前真实 Chrome/Aliyun 登录会话的前提下，拉取 MySQL RDS 的周期监控数据与常见数据库风险指标，沉淀为结构化 JSON，供周报或专项分析复用。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为目录与执行口径补充来源；若不存在，以当前文档和同目录模板为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 周报周期优先以 `data/weekly/weekly-input.*.json` 为对齐依据。
- 监控数据最终维护在 `data/aliyun/rds/` 目录下。
- 若资源区分地域，默认先从 `华南1（深圳）/ cn-shenzhen` 开始查找，但必须继续检查其他地域；不允许只查深圳后就停止。

## 3. 适用场景

- 需要为周报补充 MySQL RDS 的 CPU、内存、磁盘、连接数、QPS、TPS 等监控数据。
- 需要补充慢查询、慢日志、元数据锁、行锁等待等数据库常见风险指标。
- 需要保留一份可复用的 MySQL RDS 周期快照，供后续报告、分析或比对。

## 4. 输入与输出

输入：
- 当前已登录阿里云控制台的 Chrome 页面。
- 目标地域、目标统计周期。

输出：
- `data/aliyun/rds/rds-metrics.<region>.<engine>.<start>.<end>.json`

## 5. 操作步骤

1. 复用当前 Chrome DevTools MCP 已接入的真实浏览器会话。
   - 禁止切换到干净浏览器或隔离 profile。
   - 保持阿里云控制台登录态。

2. 确定统计周期。
   - 优先读取现有 `data/weekly/weekly-input.<week_start>.<week_end>.json`。
   - 默认回退顺序：`week_cycle -> recent_7d -> recent_3d -> recent_1d`。

3. 在 DAS 实例监控页定位 MySQL。
   - 页面一般为 `https://hdm.console.aliyun.com/#/dbMonitor/MySQL`。
   - 列表接口：`GetHDMLogicInstances`
   - 指标接口：`GetHDMLogicInstanceMetrics`

4. 优先拉取基础资源指标：
   - `cpu_usage`
   - `mem_usage`
   - `disk_usage`
   - `total_session`
   - `Threads_connected`
   - `conn_usage`
   - `qps`
   - `tps`
   - `active_session`

5. 再补充数据库风险指标：
   - `Slow_queries_ps`
   - `slowlog_size`
   - `mdl_lock_session`
   - `Innodb_row_lock_current_waits`
   - `Innodb_row_lock_waits_ps`
   - `Innodb_row_lock_time_avg`
   - `Created_tmp_disk_tables_ps`

6. 做结果归一化。
   - 无样本：标记为 `no_data`
   - 多实例聚合时：
     - 连接数、QPS、TPS、活跃会话、慢查询等更适合按时间点求和
     - CPU、内存、磁盘、连接使用率、平均锁等待时长更适合按时间点求均值
   - 当前阿里云标准视图未暴露独立 `table_locks_*` 时，可明确说明使用 `mdl_lock_session` 近似观测表锁/元数据锁争用
   - 若本次使用的是报告日采集到的数据，来源时间说明写入 `notes`；`report_highlights` 只能写结果结论，不得出现“快照代理本周”之类的过程性表述

7. 写入结构化 JSON 并校验。
    - **必须严格按照 `templates/rds-metrics.template.json` 模板格式输出**
    - 目标路径：`data/aliyun/rds/rds-metrics.<region>.<engine>.<start>.<end>.json`
    - 写完后执行 `jq empty <file>`
    - 拉取完成后关闭本次为 RDS 打开的相关浏览器标签页；不要关闭用户原本已打开且仍在使用的页签

## 6. 推荐输出结构

- `scope`
- `collection`
- `preferred_period`
- `generated_at`
- `instances`
- `aggregate_metrics`
- `database_risk_metrics`
- `report_compatibility`
- `report_highlights`
- `notes`

## 7. 必查清单

- 已确认使用的是当前真实阿里云登录会话，而不是干净浏览器。
- 周期优先与周报周期对齐。
- `CPU / 内存 / 磁盘 / 连接数 / QPS / TPS / 活跃会话` 已尽量补齐。
- `慢查询 / 慢日志 / 元数据锁 / 行锁等待` 已尽量补齐。
- 对不可用指标使用 `no_data`，不伪造数据。
- 输出文件命名、地域、引擎、起止日期一致。

## 8. 禁止事项

- 不允许只验证“能新开页面”就认定已接入真实会话。
- 不允许跳过周期对齐，直接随意取一个时间段。
- 不允许把当前不可观测的 `table_locks_*` 臆造为已采集指标。
- 不允许通过其他资源（如 ECS、Redis）的接口字段、认证方式、响应结构来推测 RDS 的接口。阿里云不同产品的控制台接口相互独立，ECS 的请求模型、认证机制、返回格式不适用于 RDS。每个资源必须从该资源控制台页面的实际 Network 请求中提取接口规范。

## 9. 数据模板

参考模板文件：`templates/rds-metrics.template.json`

输出 JSON 必须包含的字段：
- `scope`：资源范围（region_id, instance_count 等）
- `preferred_period`：统计周期信息
- `generated_at`：ISO 格式时间戳
- `instances`：每个实例的详细指标数组，每项包含：
  - `instance.id`, `instance.name`, `instance.role`
  - `metrics`：CPU/内存/磁盘/连接数/QPS/TPS等指标，每项包含 `status`/`summary`（含 `sample_count`/`point_value_avg`/`latest_value`）
- `aggregate_metrics`：多实例聚合指标
- `database_risk_metrics`：慢查询、行锁等风险指标
- `report_highlights`：周报可直接引用的摘要结论
- `notes`：数据来源说明

## 10. 常见问题

### 10.1 产品面板 Modal 阻挡问题

**问题描述**：
RDS 控制台页面加载时会弹出"产品与服务"模态框，阻挡页面内容。

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
- 移除 modal 后可访问 `rdsnext.console.aliyun.com` 查看 RDS 概览数据

### 10.2 DAS API 认证问题

**问题描述**：
DAS 页面使用不同的 `hdm-console_zh-cn` config，ECS secToken 无法直接用于 DAS API。

**解决方案**：
直接访问 `rdsnext.console.aliyun.com` 而非 DAS，可获取 RDS 概览数据（实例数量、运行状态等）。

### 10.3 RDS 监控指标获取

**推荐方法**：
通过 DAS 控制台（`hdm.console.aliyun.com`）获取详细监控指标，但需要注意认证配置。

## 11. 完成后反馈

至少反馈：
- 统计的实例数量、实例名称与实例 ID。
- 实际采用的统计周期。
- 输出 JSON 路径。
- 本次值得写入周报的重点观察结论。
