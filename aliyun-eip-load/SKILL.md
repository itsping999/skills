---
name: aliyun-eip-load
description: 阿里云 EIP 负载快照拉取规范。用于复用当前已登录的阿里云控制台会话，拉取指定地域 EIP 当前绑定情况、带宽分布、共享带宽占用与闲置风险，并写入项目 data/aliyun/eip 目录。
---

# 阿里云 EIP 负载快照拉取规范

## 1. 目的

在不离开用户当前真实 Chrome/Aliyun 登录会话的前提下，拉取指定地域 EIP 当前绑定情况、带宽分布、共享带宽占用与闲置风险，沉淀为结构化 JSON，供周报附录或公网容量盘点复用。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为目录与执行口径补充来源；若不存在，以当前文档和同目录模板为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 资源快照最终维护在 `data/aliyun/eip/` 目录下。
- 若资源区分地域，默认先从 `华南1（深圳）/ cn-shenzhen` 开始查找，但必须继续检查其他地域；不允许只查深圳后就停止。

## 3. 适用场景

- 需要盘点某个地域当前有哪些 EIP 正在使用。
- 需要识别 EIP 绑定对象的类型分布，例如 ECS、SLB、NAT。
- 需要判断共享带宽包是否集中绑定了多个公网入口。

## 4. 输入与输出

输入：
- 当前已登录阿里云控制台的 Chrome 页面。
- 目标地域。

输出：
- `data/aliyun/eip/eip-load.<region>.<date>.json`

## 5. 操作步骤

1. 复用当前 Chrome DevTools MCP 已接入的真实浏览器会话。
   - 禁止切换到干净浏览器或隔离 profile。
   - 保持阿里云控制台登录态。

2. 打开目标地域的 EIP 列表页。
   - 页面一般为 `https://vpc.console.aliyun.com/eip/<region>/eips`。

3. 优先读取当前表格中可见的字段。
   - EIP ID / 名称 / IP
   - 绑定实例类型与实例 ID
   - IP 状态
   - 带宽
   - 带宽包服务
   - 计费方式
   - 创建时间

4. 如页面中已有资源聚合或闲置结果，一并保留。
   - 地域资源数量
   - 闲置实例数量

5. 做结果归一化。
   - EIP 盘点默认按 `current_state` 记录，不强行对齐周报周期。
   - 共享带宽包要保留 `shared_bandwidth_package_id`，方便识别多入口共用情况。
   - 如果某条 EIP 没有名称，使用 `null`，不要硬填占位文案。

6. 写入结构化 JSON 并校验。
    - **必须严格按照 `templates/eip-load.template.json` 模板格式输出**
    - 目标路径：`data/aliyun/eip/eip-load.<region>.<date>.json`
    - 写完后执行 `jq empty <file>`
    - 拉取完成后关闭本次为 EIP 打开的相关浏览器标签页；不要关闭用户原本已打开且仍在使用的页签

## 6. 推荐输出结构

- `scope`
- `collection`
- `preferred_period`
- `generated_at`
- `aggregate_metrics`
- `instances`
- `report_highlights`
- `notes`

## 7. 必查清单

- 已确认使用的是当前真实阿里云登录会话，而不是干净浏览器。
- 地域总数、在用数量、带宽分布、绑定类型分布已尽量补齐。
- 共享带宽包绑定情况已尽量补齐。

## 8. 禁止事项

- 不允许把当前资源快照误写成周趋势带宽统计。
- 不允许只记录 IP 地址而漏掉绑定对象与带宽包信息。
- 不允许把无名称 EIP 伪造出业务名称。
- 不允许通过其他资源（如 ECS、RDS）的接口字段、认证方式、响应结构来推测 EIP 的接口。阿里云不同产品的控制台接口相互独立，ECS 或 RDS 的请求模型、认证机制、返回格式不适用于 EIP。每个资源必须从该资源控制台页面的实际 Network 请求中提取接口规范。

## 9. 数据模板

参考模板文件：`templates/eip-load.template.json`

输出 JSON 必须包含的字段：
- `scope`：资源范围（resource_type, region_id, region_name）
- `collection`：数据来源（source, snapshot_date, dashboard_view）
- `preferred_period`：统计周期信息
- `generated_at`：ISO 格式时间戳
- `aggregate_metrics`：聚合指标，包含：
  - `regional_total_count`, `regional_in_use_count`, `regional_idle_count`
  - `binding_type_distribution`：绑定类型分布（ecs_instance, slb_instance, nat_gateway）
  - `global_resource_footprint`：各地域资源分布
- `instances`：每个 EIP 实例详情数组，每项包含：
  - `allocation_id`, `name`, `ip_address`
  - `bound_instance_type`, `bound_instance_id`
  - `bandwidth_mbps`, `bandwidth_service`
  - `payment_type`, `billing_mode`, `status`
- `report_highlights`：周报可直接引用的摘要结论
- `notes`：数据来源说明

## 10. 常见问题

### 10.1 产品面板 Modal 阻挡问题

**问题描述**：
EIP 控制台页面加载时会弹出"产品与服务"模态框，阻挡页面内容。

**解决方案**：
```javascript
const modal = document.querySelector('[role="dialog"]');
if (modal) {
  modal.remove();
  return 'Modal removed';
}
```

### 10.2 地域切换

**问题描述**：
默认显示的是杭州地域数据，但实际 EIP 资源在深圳和青岛。

**解决方案**：
通过 URL 直接切换地域：`https://vpc.console.aliyun.com/eip/cn-shenzhen/eips`


## 11. 完成后反馈

至少反馈：
- 地域内 EIP 总数与在用数量。
- 绑定对象类型分布。
- 输出 JSON 路径。
- 本次值得写入周报的重点观察结论。
