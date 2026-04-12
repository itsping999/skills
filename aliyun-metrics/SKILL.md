---
name: aliyun-metrics
description: 阿里云统一数据拉取 skill。复用当前已登录控制台会话，按调用参数显式传入地域、时间范围和输出目录，拉取 ECS/RDS/Redis/MongoDB/K8S/SLB/CDN/EIP/SMS/Voice/Email/Certificate 数据。
---

# 云平台（默认阿里云）统一数据拉取规范

## 1. 目的

这个 skill 的目标是：
- 单一 skill 即可独立完成云资源数据拉取。
- 调用方显式传入地域范围、时间范围与输出目录，skill 不做默认推断。
- 在权限允许范围内尽量扩大指标覆盖（`metric_scope=all`）。
- 输出到调用方指定目录，供后续分析流程复用。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其目录口径补充来源；若不存在，以当前文档与 `templates/` 为准。
- 默认云厂商为阿里云；若调用方指定其他厂商，保持同一流程并替换控制台入口、指标命名和输出目录中的 `provider`。
- 复用当前已登录的真实控制台会话，不切换到干净浏览器 profile。
- 地域范围由调用方通过 `region_scope` 显式指定；skill 不做默认地域推断。

## 3. 调用参数契约

建议由调用方显式提供：

```json
{
  "provider": "aliyun",
  "services": [
    "ecs",
    "rds",
    "redis",
    "mongodb",
    "k8s",
    "slb",
    "cdn",
    "eip",
    "sms",
    "voice",
    "email",
    "certificates"
  ],
  "time_window": {
    "start": "YYYY-MM-DD HH:MM:SS",
    "end": "YYYY-MM-DD HH:MM:SS",
    "timezone": "Asia/Shanghai",
    "snapshot_date": "YYYY-MM-DD"
  },
  "region_scope": {
    "regions": ["cn-shenzhen", "cn-hangzhou"],
    "cross_region": true
  },
  "output": {
    "root_dir": "<data_root>"
  },
  "metric_scope": "all",
  "metric_profile": {
    "default_level": "all",
    "service_overrides": {
      "ecs": "all",
      "rds": "extended"
    }
  },
  "aggregation_policy": {
    "priority": ["Average", "Value", "Maximum", "Minimum"]
  },
  "failure_policy": {
    "mode": "partial_success",
    "continue_on_service_error": true
  }
}
```

参数建议：
- `time_window.start/end/timezone` 通常应明确提供。
- `time_window.snapshot_date` 更适合在快照型任务中提供。
- `region_scope.regions` 建议至少包含一个明确地域。
- `output.root_dir` 建议由调用方显式指定。
- `metric_scope` 支持 `core|extended|all`，默认 `all`。
- `metric_profile` 由调用方指定，用于覆盖服务级指标档位（可选）。
- `aggregation_policy.priority` 由调用方指定聚合优先级（可选）。
- `failure_policy` 由调用方指定失败处理策略（可选）。
- `services` 通常至少包含一个服务。

最小调用样例（单服务）：

```json
{
  "provider": "aliyun",
  "services": ["ecs"],
  "time_window": {
    "start": "2026-04-04 00:00:00",
    "end": "2026-04-10 23:59:59",
    "timezone": "Asia/Shanghai"
  },
  "region_scope": {
    "regions": ["cn-shenzhen"],
    "cross_region": false
  },
  "output": {
    "root_dir": "<data_root>"
  },
  "metric_scope": "all",
  "metric_profile": {
    "default_level": "all"
  },
  "aggregation_policy": {
    "priority": ["Average", "Value", "Maximum", "Minimum"]
  },
  "failure_policy": {
    "mode": "partial_success",
    "continue_on_service_error": true
  }
}
```

多服务调用样例：

```json
{
  "provider": "aliyun",
  "services": ["ecs","rds","redis","mongodb","slb","cdn","eip","k8s","certificates"],
  "time_window": {
    "start": "2026-04-04 00:00:00",
    "end": "2026-04-10 23:59:59",
    "timezone": "Asia/Shanghai"
  },
  "region_scope": {
    "regions": ["cn-shenzhen", "cn-hangzhou"],
    "cross_region": true
  },
  "output": {
    "root_dir": "<data_root>"
  },
  "metric_scope": "all",
  "metric_profile": {
    "default_level": "all"
  },
  "aggregation_policy": {
    "priority": ["Average", "Value", "Maximum", "Minimum"]
  },
  "failure_policy": {
    "mode": "partial_success",
    "continue_on_service_error": true
  }
}
```

## 4. 服务路由与输出

统一 skill 通过 `services` 路由到对应服务执行步骤，并套用对应模板：

- `ecs`
  - 模板：`templates/ecs-metrics.summary.template.json`
  - 输出：`<data_root>/ecs/ecs-metrics.summary.<start>.<end>.json`
- `rds`
  - 模板：`templates/rds-metrics.template.json`
  - 输出：`<data_root>/rds/rds-metrics.<region>.<engine>.<start>.<end>.json`
- `redis`
  - 模板：`templates/redis-metrics.template.json`
  - 输出：`<data_root>/redis/redis-metrics.<region>.<instance-slug>.<start>.<end>.json`
- `mongodb`
  - 模板：`templates/mongodb-metrics.template.json`
  - 输出：`<data_root>/mongodb/mongodb-metrics.<region>.<instance-slug>.<start>.<end>.json`
- `k8s`
  - 模板：`templates/k8s-release-metrics.template.json`
  - 输出：`<data_root>/k8s/k8s-release-metrics.<scope>.<start>.<end>.json`
- `slb`
  - 模板：`templates/slb-metrics.template.json`
  - 输出：`<data_root>/slb/slb-metrics.<scope>.<date>.json`
- `cdn`
  - 模板：`templates/cdn-usage.template.json`
  - 输出：`<data_root>/cdn/cdn-usage.<scope>.<start>.<end>.json`
- `eip`
  - 模板：`templates/eip-load.template.json`
  - 输出：`<data_root>/eip/eip-load.<region>.<date>.json`
- `sms`
  - 模板：`templates/sms-usage.template.json`
  - 输出：`<data_root>/sms/sms-usage.<scope>.<start>.<end>.json`
- `voice`
  - 模板：`templates/voice-usage.template.json`
  - 输出：`<data_root>/voice/voice-usage.<region>.<start>.<end>.json`
- `email`
  - 模板：`templates/email-usage.template.json`
  - 输出：`<data_root>/email/email-usage.<region>.<start>.<end>.json`
- `certificates`
  - 模板：`templates/certificate-expiry.template.json`
  - 输出：`<data_root>/certificates/certificate-expiry.<scope>.<date>.json`

## 5. 执行流程

1. 校验调用参数完整性。
   - 若存在缺失项，优先反馈缺失内容，而不是自行补全时间范围、地域范围或输出目录。

2. 复用当前控制台会话，按 `services` 逐项执行。
   - 若运行环境支持并行，可并行拉取服务。
   - 若不支持并行，可按如下顺序处理：`ecs -> rds -> redis -> mongodb -> k8s -> slb -> cdn -> eip -> sms -> voice -> email -> certificates`。
   - 每个服务拉取完成并确认 JSON 落盘后，可关闭该服务对应的浏览器标签页，再进入下一个服务，以减少标签页堆积和会话混淆。

3. 每个服务都遵循同一覆盖策略。
   - 默认使用 `metric_scope`，若定义了 `metric_profile.service_overrides` 则按服务覆盖。
   - `core`：只拉核心指标。
   - `extended`：核心 + 常用扩展指标。
   - `all`：核心 + 扩展 + 当前页面/API 可见的其余可访问指标，并在 `metric_coverage.extended_metrics_unavailable` 标注不可用项。

4. 结果归一化。
   - 无样本：`no_data`
   - 不支持或权限受限：`unavailable`
   - 聚合优先级由 `aggregation_policy.priority` 指定；未指定时再使用 `Average -> Value -> Maximum -> Minimum`。

5. 写入 JSON 并校验格式。
   - 优先执行 `jq empty <file>`；若无 `jq`，使用等价 JSON 解析校验。

6. 结果交付。
   - 返回已拉取服务清单、输出文件列表、覆盖情况摘要、失败项与原因。
   - 失败处理遵循 `failure_policy`（例如 `partial_success` 或 `fail_fast`）。

### 结果判定参考

- `services` 中每个服务都至少有一个对应输出文件。
- 每个输出文件都可被 JSON 解析。
- 若 `metric_scope=all`，输出中包含 `metric_coverage` 并标注可用/不可用指标。
- 若部分服务失败，结果中宜包含失败服务列表与原因，而不是静默跳过。

## 6. 数据准备场景约束

- 在统一统计窗口场景中，通常会显式传入一致的 `time_window`，例如：
  - `time_window.start = <week_start> 00:00:00`
  - `time_window.end = <week_end> 23:59:59`
  - `time_window.timezone = Asia/Shanghai`
- `k8s` 与 `certificates` 结果更适合作为结构化数据产物落盘，供后续流程按需消费。

## 7. 建议核对项

- `time_window` 来自调用参数，而不是页面默认值。
- `region_scope` 来自调用参数，而不是 skill 默认值或页面默认地域。
- 输出目录来自调用参数 `output.root_dir`，而不是 skill 内的固定路径。
- `services` 包含 `ecs` 时，更适合按账号可见范围进行全量拉取（跨地域、跨分页、全实例），以保持与调用目标一致。
- `metric_scope=all` 时，结果中已尽量扩大指标范围并记录不可用指标。
- 指标覆盖档位与调用方给定的 `metric_profile` 保持一致（如有覆盖规则）。
- 聚合顺序与调用方给定的 `aggregation_policy` 保持一致。
- 失败处理方式与调用方给定的 `failure_policy` 保持一致。
- 地域型资源已适度覆盖首选地域之外的可见地域。
- 输出路径与服务路由一致，JSON 可以通过结构校验。
- K8S 与证书数据已落盘并可作为后续处理输入。
- 每个服务执行结束后，如已不再使用，可关闭对应标签页，仅保留必要页面。

## 8. 约束与边界

- 不建议在 skill 内部推断或硬编码统计周期。
- 不建议在 skill 内部推断或硬编码地域范围。
- 不建议在 skill 内部固定输出目录。
- 单实例样本通常不宜直接等同于全量视图。
- 在 `services=["ecs"]` 场景下，若仅拿到验证样本，更适合作为部分结果而非完整成功结果。
- 输出结果宜尽量贴近模板结构，而不是临时文本摘要。

## 9. 服务级覆盖矩阵（实测口径）

以下为当前控制台会话下可稳定拉取的指标范围（`metric_scope=all`）：

- `ecs`
  - 核心：CPU、内存、磁盘、网络（按实例聚合与汇总）。
  - 扩展：实例维度热点、可用区/规格补充信息。
- `rds`
  - 核心：连接数、CPU、IOPS、延迟、存储空间。
  - 扩展：实例状态、引擎版本、规格与区域信息。
- `redis`
  - 核心：QPS、连接数、CPU、内存使用、水位变化。
  - 扩展：实例状态、规格、节点信息（可见时）。
- `mongodb`
  - 核心：连接、CPU、内存、慢查询与吞吐相关指标。
  - 扩展：分片/副本集拓扑字段（可见时）。
- `k8s`
  - 核心：集群状态、任务/事件、发布统计（可访问时）。
  - 扩展：命名空间与 Deployment 明细（受 RBAC 影响）。
- `slb`
  - 核心：SLB/ALB/NLB 总量、空闲实例、配额。
  - 扩展：跨地域分布与实例类型细分。
- `cdn`
  - 核心：流量、带宽、HTTP 状态码分布、域名总览。
  - 扩展：套餐、证书/CNAME 配置状态、源站状态码分层。
- `eip`
  - 核心：总量、已绑定/未绑定、带宽总额、绑定类型分布。
  - 扩展：多地域明细（不只单地域）。
- `sms`
  - 核心：总发送、成功/失败、日趋势。
  - 扩展：资质状态、账号开通状态、套餐字段（可见时）。
- `voice`
  - 核心：账单金额、计费项、用量。
  - 扩展：商品目录与费用项目录；按周精确序列通常不可直接得到。
- `email`
  - 核心：总发送、成功/失败、无效地址、日趋势。
  - 扩展：发送详情样本、退订/垃圾举报名单、账号配额、验证额度。
  - 权限敏感：`ConfigSet`、`DedicatedIpPool` 常见 `NoPermission`。
- `certificates`
  - 核心：订单总量、过期数量、套餐使用量。
  - 扩展：逐证书剩余天数与部署明细（页面/API可见时）。

### 9.1 优先接口清单（按服务）

为保证 `metric_scope=all` 下稳定复现，建议优先观察以下控制台接口（接口名可随前端版本变化，但语义应一致）：

- `sms`：`QuerySmsStatisticsNew`、`QuerySmsBaseScreenNew`、`QueryPackageSummary`、`QuerySmsQualificationRecord`
- `voice`：`GetUserBill`、`ListCustomBillTab`、`GetSearchTreeData`、`GetBillViewDescription`
- `email`：`listStatistics`、`listStatisticsDetail`、`listBlockSending`、`descAccount`、`getValidationQuota`、`listMailAddress`
- `certificates`：`getCertificateOrderCount`、`getCertificatePackageCount`、`listCertificateOrder`
- `eip`：`DescribeResourceAggregations`、`DescribeEipAddresses`
- `slb`：`DescribeLoadBalancerSummary`、`DescribeIdleInstances`、`DescribeSlbQuotas`、`GetAlbGlobalSummary`、`GetNlbGlobalSummary`
- `cdn`：`DescribeDomainUsageData`、`DescribeDomainHttpCodeDataByLayer`、`DescribeDomainSrcHttpCodeData`、`DescribeCdnUserResourcePackage`
- `k8s`：`DescribeClusters`、`DescribeTasks`、`DescribeEvents`、`DescribeClusterNamespaces`、`Deployments 列表接口`

## 10. 权限降级与兜底规范

- 当接口返回 `NoPermission/403/forbidden`：
  - 可以继续保留该服务的部分输出。
  - 可在 `metric_coverage.extended_metrics_unavailable` 标注缺失项。
  - 可在 `permission_findings` 或 `notes` 记录接口名、错误码、RequestId。
- 当页面有数据但无 API 明细：
  - 可先保留“快照级”聚合结果。
  - 可在 `report_compatibility` 标注其与目标统计口径的一致程度。
- 当样本为空：
  - 更适合使用 `no_data` 或空数组，而不是伪造 0 值序列。

## 11. 建议执行顺序（全量覆盖）

当目标是“尽可能全面覆盖”且包含通信扩展视角时，建议顺序：

`ecs -> rds -> redis -> mongodb -> k8s -> slb -> cdn -> eip -> certificates -> sms -> voice -> email`

说明：
- 先拉基础资源稳定面（计算/数据库/网络），再拉通信与费用面。
- `email` 放在后段，便于在同一次会话中补采发送详情、退订、举报等扩展数据。
