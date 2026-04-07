---
name: aliyun-ecs-metrics
description: 阿里云 ECS 监控数据拉取规范。复用当前已登录的阿里云控制台真实会话，优先批量拉取全量 ECS，并产出可直接供周报消费的汇总 JSON。
---

# 阿里云 ECS 监控数据拉取规范

## 1. 目的

在不离开用户当前真实 Chrome/Aliyun 登录会话的前提下，按统计周期拉取 ECS 监控数据，沉淀为结构化 JSON，供周报或专项分析复用。

本技能支持两种模式：
- `batch_all`（默认）：拉取目标范围内全部 ECS 实例（例如 26 台）。
- `single_instance`：只拉取指定实例。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为目录与执行口径补充来源；若不存在，以当前文档和同目录模板为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 周报周期优先以当前任务传入的 `week_start/week_end` 为准；`weekly-input.*.json` 只作为可选补充输入，不再是周期主来源。
- 监控数据最终维护在 `data/aliyun/ecs/` 目录下。
- 当前周报优先消费 `ecs-metrics.summary.<start>.<end>.json`。
- 若资源区分地域，默认先从 `华南1（深圳）/ cn-shenzhen` 开始查找，但必须继续检查其他地域；不允许只查深圳后就停止。

## 3. 适用场景

- 需要为周报补充全量 ECS（例如 26 台）的 CPU、内存、磁盘、连接数、系统负载等监控数据。
- 需要对某个地域或某组实例进行批量监控快照归档。
- 需要单实例排障时，临时切换为 `single_instance`。

## 4. 输入与输出

输入：
- 当前已登录阿里云控制台的 Chrome 页面。
- 目标统计周期。
- 目标范围（默认全量；可指定地域/实例 ID 列表）。

输出：
- 每实例文件：
  - `data/aliyun/ecs/ecs-metrics.<region>.<instance-slug>.<start>.<end>.json`
- 批量汇总文件：
  - `data/aliyun/ecs/ecs-metrics.summary.<start>.<end>.json`

补充说明：
- ECS 与 DAS 类产品不同，当前项目内尚未沉淀出一个“已验证可直接复用”的纯脚本请求模板。
- 但当前项目已经沉淀出一个稳定的执行路径：
  1. 先用 `data/aliyun/ecs/ecs-instances.inventory.new` 作为实例源。
  2. 再在真实 ECS 控制台会话里复用前端监控模型批量调用 `DescribeMetricListFromProxy`。
- 默认直接信任 `ecs-instances.inventory.new`，不再判断它是否“最新”。
- 只有当这个文件缺失或用户明确要求实时实例范围时，才回退到“先抓实例列表，再抓监控请求样例”的路径。
- 当前项目里，若任务目标是“生成周报”，则汇总文件是主产物；单实例文件不是必需品。
- 当前项目里，若任务目标是“生成周报”，ECS 默认要求是“全量拉取所有实例”；`single_instance` 只用于单机排障或临时验证，不能替代周报所需的全量视图。
- 当用户明确要求“只需要生成周报当天的组件源数据当作本周数据”时，可以按该来源时间落盘，并在 `notes` 中写清楚数据来源时间。
- 这类来源说明只允许保留在 JSON 的 `notes` 中；`report_highlights` 和周报正文必须只写观察结果，不写“快照代理本周”之类的过程性表述。

## 5. 操作步骤

1. 复用当前 Chrome DevTools MCP 已接入的真实浏览器会话。
   - 禁止切换到干净浏览器或隔离 profile。
   - 保持阿里云控制台登录态。
   - 默认入口页优先使用这条固定监控页：
     - `https://ecs.console.aliyun.com/server/i-wz92y59yk0wty1by6wsu/monitor?regionId=cn-shenzhen&startTime=1774321320000&endTime=1774926120000&range=168#/`
   - 这条入口页已经验证可作为前端监控模型锚点；除非页面失效，否则优先从这里启动。
   - 注意：该入口 URL 自带的 `startTime`、`endTime`、`range` 只是页面默认筛选条件，只用于打开锚点页，不能直接当作本次统计周期。

2. 确定统计周期。
   - 优先以当前任务给定的 `week_start/week_end` 为准。
   - 如果用户要求“用周报生成当天的数据当作本周数据”，则请求时间窗口可以缩到报告日 `00:00:00 -> 23:59:59`，但输出文件名仍应对齐周报周期。
   - 无论锚点页 URL 上带什么默认时间参数，最终请求都必须按本次任务要求重新覆盖时间范围。

3. 确定实例范围（默认批量全量）。
   - 默认模式：`batch_all`。
   - 若用户明确传入 `instance_ids`，切换为 `single_instance` 或定向批量。
   - 如果任务目标是周报，不允许因为方便而静默降级为 `single_instance`。
   - 默认读取 `data/aliyun/ecs/ecs-instances.inventory.new` 作为实例源。
   - 该文件由用户主动维护；执行时直接信任其内容，无需再判断是否为最新。
   - 若 `ecs-instances.inventory.new` 缺失，或用户明确要求实时实例范围，再回到页面上下文拉取实例清单（优先当前账号可见范围，必要时分页）。
   - 每个实例至少记录：`instanceId`、`instanceName`、`regionId`、`zoneId`、`instanceType`、`vcpu`、`memory`、`osName`、`publicIp/eip`。

4. 在真实 ECS 控制台中复用前端监控模型，而不是手写裸请求。
   - 建议页面：任意已登录的 ECS 实例详情监控页，例如：
     - `https://ecs.console.aliyun.com/server/<instanceId>/monitor?...`
   - 当前默认锚点页：
     - `https://ecs.console.aliyun.com/server/i-wz92y59yk0wty1by6wsu/monitor?regionId=cn-shenzhen&startTime=1774321320000&endTime=1774926120000&range=168#/`
   - 在页面上下文内注入 webpack runtime：
     - `window.aliEcsCorewebpackJsonp.push([[Math.random()], {}, function (r) { req = r; }])`
   - 当前项目已验证可用的模块入口：
     - `req(33657).Nd('DescribeMetricListFromProxy', 'metrics20180308')`
   - 这条路径本质上仍然是复用真实控制台请求模型，只是不用再手工抄完整 network body。
   - 如果该模块入口失效，再回退到 Network 面板抓一条成功样例。

5. 按已验证请求模型做批量请求建模。
   - 已知目标接口动作：`DescribeMetricListFromProxy`
   - 已知命名空间：`acs_ecs_dashboard`
   - 已验证时间参数格式：
     - `startTime: 'YYYY-MM-DD 00:00:00'`
     - `endTime: 'YYYY-MM-DD 23:59:59'`
   - 这里的 `startTime` / `endTime` 必须以当前任务要求为准，不得复用入口页 URL 里的默认毫秒时间戳。
   - 已验证周期参数：
     - `Period: '60'`
   - 已验证上下文字段：
     - `consolePageRequestContextUrl: '/'`
   - 已验证 payload 建议同时带两套字段，避免前端模型差异：
     - 大写字段：`StartTime` `EndTime` `Namespace` `MetricName` `Period` `Dimensions`
     - 小写字段：`startTime` `endTime` `namespace` `metricName` `dimensions`
   - `Dimensions` 的已验证格式：
     - 常规指标：`[{ instanceId: '<instanceId>' }]`
     - 磁盘指标：`[{ instanceId: '<instanceId>', mountpoint: '/' }]`
   - 当前项目已验证这 4 个指标可以稳定返回：
     - `CPUUtilization`
     - `vm.MemoryUtilization`
     - `vm.DiskUtilization`
     - `concurrentConnections`
   - 推荐直接把 `ecs-instances.inventory.new` 中的实例列表喂给这套请求模型做批量循环。

6. 在批量模式下按实例循环拉取核心指标。
   - 推荐每次只改实例维度与时间范围，不改其余结构字段。
   - 如果 `ecs-instances.inventory.new` 中已有 26 台实例，就直接对这 26 台循环，不必依赖页面当前是否加载出实例列表。
   - 若某些指标需要额外维度（例如磁盘挂载点 `/`），优先沿用已验证格式。
   - 批量执行时，先用 1 台实例完成端到端验证，再扩到全量实例。

7. 优先拉取核心指标（每个实例）：
   - `CPUUtilization`
   - `vm.MemoryUtilization`
   - `vm.DiskUtilization`（`mountpoint: "/"`）
   - `concurrentConnections`

8. 再补充建议指标（每个实例）：
   - `ConnectionUtilization`
   - `memory_usedutilization`
   - `load_1m`
   - `load_5m`
   - `load_15m`
   - `vm.ProcessCount`
   - `IntranetInRate`
   - `IntranetOutRate`
   - `VPC_PublicIP_InternetInRate`
   - `VPC_PublicIP_InternetOutRate`
   - `networkcredit_limit_overflow_errorpackets`

9. 做结果归一化。
   - 无样本：标记为 `no_data`
   - 样本存在但值全为 `-1`：标记为 `unavailable`
   - 取值优先级建议：`Average -> Value -> Maximum -> Minimum`
   - 带宽指标同时保留 `bit/s` 原值，必要时补充 Mbps 摘要字段
   - 对 `1 vCPU` 实例，若 `load_1m/5m/15m` 长期在 `3` 左右，应在摘要中明确标注负载压力

10. 写入结构化 JSON 并校验。
    - **必须严格按照 `templates/ecs-metrics.summary.template.json`（汇总）或 `templates/ecs-metrics.template.json`（单实例）模板格式输出**
    - 若任务目标是周报，优先生成汇总文件。
    - 单实例文件按需生成；如果只为周报附录服务，可以只写汇总文件。
    - 对周报任务，最终交付物至少要包含全量汇总文件；没有汇总文件就不算完成 ECS 周报数据准备。
    - 汇总文件至少包含：
     - `generated_at`
     - `period.start / period.end / period.timezone`
     - `period.snapshot_date`（若使用报告日代理周口径）
     - `total_instances`
     - `metric_scope`
     - `items`
     - `notes`
    - 优先执行 `jq empty <file>`；若本机无 `jq`，使用等价 JSON 解析校验（如 `ConvertFrom-Json`）。
    - 拉取完成后关闭本次为 ECS 打开的相关浏览器标签页；不要关闭用户原本已打开且仍在使用的页签

## 6. 已验证事实与请求诊断

### 6.1 本项目当前已验证事实

- `data/aliyun/ecs/ecs-instances.inventory.new` 是默认且唯一优先使用的实例清单来源，由用户主动维护。
- 当前真实浏览器会话中的 ECS 页面可读到 `window.ALIYUN_CONSOLE_CONFIG.SEC_TOKEN`，说明登录态和会话上下文本身是可用的。
- 单纯拿 `SEC_TOKEN` 手写裸 `POST` 仍然不稳，但复用页面内 webpack 模块 `req(33657).Nd('DescribeMetricListFromProxy', 'metrics20180308')` 已验证可成功返回数据。
- 已验证 `inventory -> 前端监控模型 -> 批量拉取` 这条链路可以在 `2026-04-03` 报告日快照口径下成功覆盖 26 台实例，并生成 `ecs-metrics.summary.2026-03-28.2026-04-03.json`。
- 已验证固定入口页 `i-wz92y59yk0wty1by6wsu` 可稳定作为监控页锚点，后续批量抓取应优先复用该页面。
- 已验证返回体中的 `Datapoints` 可能是 JSON 字符串，也可能已经是数组；落盘前必须统一解析。
- 已验证部分实例会出现：
  - `memory=no_data`
  - `disk=no_data`
  - `Stopped` 实例四项核心指标全部 `no_data`
  这些都应视为真实状态，不应当作失败。

### 6.2 常见失败信号

- `PostonlyOrTokenError`
  - 常见原因：
    - 请求方法不对
    - token 已过期
    - 页面刚切换或停留过久，前端 token 未刷新
  - 建议动作：
    - 先 reload 当前 ECS 页面
    - 重新触发一次真实监控加载
    - 再从最新 Network 记录里取请求

- `Bind`
  - 常见原因：
    - 直接跳过前端模型，手写 body
    - 缺少前端调用路径中的包装方式
    - `Dimensions` / 时间参数 / 指标参数格式错误
  - 建议动作：
    - 不要继续猜字段
    - 优先回到页面内 webpack 模块调用路径
    - 只有当模块路径失效时，才回到 Network 成功样例逐字段对照

- `InvalidAction.NotFound`
  - 常见原因：
    - 请求被包错层
    - 把 `action` 与 `__action`、`params` 等字段混用了
  - 建议动作：
    - 以浏览器真实成功请求或页面内前端模型为准，不要自己重新拼 action 层级

- HTTP 200 但返回空样本
  - 常见原因：
    - 时间格式不对
    - 维度字段不对
    - 当前指标对该实例不可用
  - 建议动作：
    - 先用同一台实例、同一指标、同一时间窗复现页面中的成功请求
    - 确认该指标是否本就为空

### 6.3 推荐抓包顺序

1. 先读取 `ecs-instances.inventory.new`。
2. 优先打开固定锚点页 `i-wz92y59yk0wty1by6wsu`；若该页失效，再选另一台有监控图表数据的实例。
3. 刷新页面，保证 token 与页面模块都是最新的。
4. 先尝试页面内 webpack 模块调用 `DescribeMetricListFromProxy`。
5. 若模块调用失败，再在 Network 里找成功请求样例。
6. 单实例脚本化成功后，再对 `ecs-instances.inventory.new` 中的实例列表做批量化。

## 7. 推荐输出结构

每实例 JSON：
- `instance`
- `intended_use`
- `preferred_period`
- `generated_at`
- `report_highlights`
- `metrics`
- `supplementary_metrics`
- `notes`

汇总 JSON：
- `generated_at`
- `period`
- `total_instances`
- `metric_scope`
- `items`
- `notes`

## 8. 必查清单

- 已确认使用的是当前真实阿里云登录会话，而不是干净浏览器。
- 周期优先与周报周期对齐。
- 如果任务要求使用报告日数据作为当周来源，文件名仍必须对齐周报周期，且 `notes` 中必须写清来源时间口径。
- 批量模式下，实例清单总数与预期一致（例如应为 26 台时，不得只产出 1 台）。
- 周报场景下必须明确反馈“本次共拉取多少台 ECS”，不能只说“已验证单台成功”。
- 已确认实例源来自 `ecs-instances.inventory.new`，或明确说明为什么回退到实时页面清单。
- 已至少拿到 1 条成功的 `DescribeMetricListFromProxy` 调用路径，并确认不是靠手工猜测构造出来的。
- 若页面 reload 后 token 变化，已使用 reload 之后的最新请求样例，而不是沿用旧样例。
- 每台实例的 `CPU / 内存 / 磁盘使用率 / 连接数` 已尽量补齐；若系统负载未拉取，也应明确标为缺失，而不是阻塞汇总文件产出。
- 对不可用指标使用 `no_data` 或 `unavailable`，不伪造数据。
- 输出文件命名、地域、实例名、起止日期一致。
- 若任务目标是周报，最终必须确认周报实际读取的是 ECS 汇总文件，而不是残留的单实例样本。
- 若周报附录里仍只显示单台 ECS，说明流程没有真正切到全量汇总视图，必须继续修正。

## 9. 禁止事项

- 不允许只验证“能新开页面”就认定已接入真实会话。
- 不允许跳过周期对齐，直接随意取一个时间段。
- 不允许直接把固定入口 URL 上的默认时间筛选当成本次统计周期。
- 不允许只因为读到了 `SEC_TOKEN` 就认定请求模型已经明确。
- 如果 `ecs-instances.inventory.new` 已可用，不允许重复把“实例列表怎么拿”当作主阻塞点。
- 不允许在没有成功样例的前提下，持续手工猜 `Dimensions`、时间格式、包裹字段并把失败结果当成接口不可用。
- 不允许把全为 `-1` 的监控返回值当作真实指标写进报告。
- 在批量任务中，不允许静默降级为单实例而不明确告知。
- 不允许通过 ECS 成功请求的接口字段、认证方式、响应结构来推测其他资源的接口。阿里云不同产品的控制台接口相互独立，ECS 的请求模型（如 `DescribeMetricListFromProxy`）、认证机制（如 `SEC_TOKEN`）、返回格式（如 `Datapoints` 结构）不适用于其他产品（如 RDS、Redis、SLB）。每个资源必须从该资源控制台页面的实际 Network 请求中提取接口规范。

## 10. 数据模板

参考模板文件：`templates/ecs-metrics.summary.template.json`

汇总 JSON 必须包含的字段：
- `generated_at`：ISO 格式时间戳
- `period.start/end/timezone`：统计周期
- `total_instances`：实例总数
- `metric_scope`：本次拉取的指标范围
- `items`：每实例指标数组，每项包含：
  - `instance_id`, `instance_name`, `region_id`, `zone_id`, `status`
  - `cpu_cores`, `memory_mib`
  - `metrics`：CPU/内存/磁盘/连接数指标，每项包含 `status`/`samples`/`avg`/`latest`
- `notes`：数据来源说明

## 11. 常见问题

### 11.1 产品面板 Modal 阻挡问题

**问题描述**：
阿里云控制台大部分页面（ECS、RDS、Redis、MongoDB、CDN、SLB、EIP、K8S、Email、Voice、SSL等）加载时会弹出"产品与服务"模态框（modal dialog），阻挡页面内容，导致无法通过 UI 获取数据。

**解决方案**：
```javascript
// 在目标页面执行以下 JavaScript 代码移除 modal
const modal = document.querySelector('[role="dialog"]');
if (modal) {
  modal.remove();
  return 'Modal removed';
}
```

**注意事项**：
- 每次页面刷新后 modal 会重新出现，需要重新执行移除操作
- 该方法适用于所有被 modal 阻挡的阿里云控制台页面
- 部分页面（如 Voice）移除 modal 后可能仍有权限弹窗，需额外处理

### 11.2 ECS API 认证问题

**问题描述**：
ECS secToken 无法直接用于裸 API 请求，会返回 `PostonlyOrTokenError`。

**解决方案**：
复用前端 webpack 模块调用 `DescribeMetricListFromProxy`，而不是手写裸请求。参考 SKILL.md 第 5 步操作步骤。

## 12. 完成后反馈

至少反馈：
- 实际模式（`batch_all` 或 `single_instance`）。
- 实例总数，成功数、失败数。
- 实际采用的统计周期。
- 本次是否已经沉淀出可复用的成功请求样例；如果没有，要明确卡在哪个请求字段或哪类校验错误。
- 输出 JSON 路径（每实例 + 汇总）。
- 本次值得写入周报的重点观察结论（全局 + 高风险实例）。
