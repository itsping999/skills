---
name: aliyun-slb-metrics
description: 阿里云 SLB 资源盘点拉取规范。用于复用当前已登录的阿里云控制台会话，拉取负载均衡全局概览、闲置风险与关键配额，并写入项目 data/aliyun/slb 目录。
---

# 阿里云 SLB 资源盘点拉取规范

## 1. 目的

在不离开用户当前真实 Chrome/Aliyun 登录会话的前提下，拉取阿里云负载均衡的全局资源概览、闲置风险与关键配额，沉淀为结构化 JSON，供周报附录或专项容量盘点复用。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为目录与执行口径补充来源；若不存在，以当前文档和同目录模板为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 资源盘点结果最终维护在 `data/aliyun/slb/` 目录下。
- 若资源区分地域，默认先从 `华南1（深圳）/ cn-shenzhen` 开始查找，但必须继续检查其他地域；不允许只查深圳后就停止。

## 3. 适用场景

- 需要补充当前账号下 SLB/NLB 的资源数量与地域分布。
- 需要检查是否存在闲置负载均衡实例。
- 需要给周报补充当前负载均衡配额使用情况。

## 4. 输入与输出

输入：
- 当前已登录阿里云控制台的 Chrome 页面。

输出：
- `data/aliyun/slb/slb-metrics.<scope>.<date>.json`

## 5. 操作步骤

1. 复用当前 Chrome DevTools MCP 已接入的真实浏览器会话。
   - 禁止切换到干净浏览器或隔离 profile。
   - 保持阿里云控制台登录态。

2. 打开 SLB 概览页。
   - 页面一般为 `https://slb.console.aliyun.com/overview`。

3. 拉取已验证可用的概览接口。
   - `DescribeLoadBalancerSummaryForGlobal`
   - `GetGlobalLoadBalancerSummary`
   - `DescribeIdleInstancesForGlobal`
   - `DescribeSlbQuotas`

4. 优先保留以下结果：
   - 经典型 SLB 总数、运行数、地域分布
   - NLB 总数
   - ALB 概览返回情况
   - 闲置实例数量
   - `slbs-per-user` 配额

5. 做结果归一化。
   - 资源盘点默认按 `current_state` 记录，不强行对齐周报周期。
   - 如果某类概览接口未返回实例计数字段，使用 `null` 并在 `notes` 中说明，不伪造 0。

6. 写入结构化 JSON 并校验。
    - **必须严格按照 `templates/slb-metrics.template.json` 模板格式输出**
    - 目标路径：`data/aliyun/slb/slb-metrics.<scope>.<date>.json`
    - 写完后执行 `jq empty <file>`
    - 拉取完成后关闭本次为 SLB 打开的相关浏览器标签页；不要关闭用户原本已打开且仍在使用的页签

## 6. 推荐输出结构

- `scope`
- `collection`
- `preferred_period`
- `generated_at`
- `families`
- `idle_risk`
- `quota`
- `report_highlights`
- `notes`

## 7. 必查清单

- 已确认使用的是当前真实阿里云登录会话，而不是干净浏览器。
- 经典型 SLB、NLB、闲置实例、关键配额已尽量补齐。
- 输出文件明确标注为当前资源快照，而不是趋势统计。

## 8. 禁止事项

- 不允许只验证“能新开页面”就认定已接入真实会话。
- 不允许把未返回的 ALB 计数臆造为已采集成功。
- 不允许把当前快照误写成周趋势结论。
- 不允许通过其他资源（如 ECS、RDS）的接口字段、认证方式、响应结构来推测 SLB 的接口。阿里云不同产品的控制台接口相互独立，ECS 或 RDS 的请求模型、认证机制、返回格式不适用于 SLB。每个资源必须从该资源控制台页面的实际 Network 请求中提取接口规范。

## 9. 数据模板

参考模板文件：`templates/slb-metrics.template.json`

输出 JSON 必须包含的字段：
- `scope`：资源范围（scope_type, selection_basis）
- `collection`：数据来源（source, snapshot_date, dashboard_view）
- `preferred_period`：统计周期信息
- `generated_at`：ISO 格式时间戳
- `families`：各类型 SLB 统计（classic_slb, nlb, alb），每项包含 total_count, running_count, regions
- `idle_risk`：闲置实例风险信息
- `report_highlights`：周报可直接引用的摘要结论
- `notes`：数据来源说明

## 10. 常见问题

### 10.1 产品面板 Modal 阻挡问题

**问题描述**：
SLB 控制台页面加载时会弹出"产品与服务"模态框，阻挡页面内容。

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
- 移除 modal 后可访问 `slb.console.aliyun.com/overview` 获取 SLB 概览数据

### 10.2 页面首次加载超时

**问题描述**：
直接使用 `new_page` 打开 SLB 页面时经常超时。

**解决方案**：
使用 `navigate_page` 并设置较长的 timeout（30000ms）。

## 11. 完成后反馈

至少反馈：
- 资源总数与地域分布。
- 是否发现闲置实例。
- 输出 JSON 路径。
- 本次值得写入周报的重点观察结论。
