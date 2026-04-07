---
name: aliyun-k8s-release-metrics
description: 阿里云 K8S 发布统计拉取规范。用于复用当前已登录的阿里云控制台真实会话，统计周报所需的发布次数、发布成功率、回滚次数与变更失败率。
---

# 阿里云 K8S 发布统计拉取规范

## 1. 目的

在不离开用户当前真实 Chrome/Aliyun 登录会话的前提下，从阿里云 K8S 控制台统计周报所需的发布相关指标，并沉淀为结构化 JSON，供周报或专项复盘复用。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为目录与执行口径补充来源；若不存在，以当前文档和同目录模板为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 统计结果最终维护在 `data/aliyun/k8s/` 目录下。
- 周报“交付质量与变更风险”中的发布次数、发布成功率、回滚次数、变更失败率（CFR）优先来自阿里云 K8S 控制台。
- 若资源区分地域，默认先从 `华南1（深圳）/ cn-shenzhen` 开始查找，但必须继续检查其他地域；不允许只查深圳后就停止。

## 3. 适用场景

- 需要为周报补充发布次数、发布成功率、回滚次数。
- 需要按统计周期核对变更失败率（CFR）。
- 需要确认某周交付质量是否存在异常波动。

## 4. 输入与输出

输入：
- 当前已登录阿里云控制台的 Chrome 页面。
- 目标统计周期。
- 目标集群、命名空间或应用范围。

输出：
- `data/aliyun/k8s/k8s-release-metrics.<scope>.<start>.<end>.json`

## 5. 操作步骤

1. 复用当前 Chrome DevTools MCP 已接入的真实浏览器会话。
   - 禁止切换到干净浏览器或隔离 profile。
   - 保持阿里云控制台登录态。

2. 打开阿里云容器服务 K8S 控制台。
   - 优先进入与本周报目标环境对应的集群、应用或发布记录页面。
   - 若用户已明确给出环境范围，严格按该范围统计，不要混入其他环境。

3. 按统计周期筛选发布记录。
   - 优先使用当前任务传入的 `week_start/week_end`。
   - 若控制台只支持按自然时间过滤，至少保证覆盖整个统计窗口。

4. 统计周报所需的核心指标。
   - `release_count` / `发布次数`
   - `release_success_rate` / `发布成功率`
   - `rollback_count` / `回滚次数`
   - `change_failure_rate` / `变更失败率（CFR）`
   - 如控制台未直接展示 CFR，按 `回滚次数 / 发布次数` 计算，并在 `notes` 中说明计算口径。

5. 做结果归一化。
   - `scope` 明确记录统计范围，例如 `prod`、`global`、`cn-shenzhen-prod`。
   - 成功率和失败率统一保留百分号字符串，例如 `98.73%`。
   - 若发布次数为 0，则 `change_failure_rate` 统一记为 `0.00%`，避免除零。
   - 若控制台存在“发布失败”与“回滚”两个维度，以回滚作为周报 CFR 口径，除非用户另有要求。

6. 写入结构化 JSON 并校验。
    - **必须严格按照 `templates/k8s-release-metrics.template.json` 模板格式输出**
    - 目标路径：`data/aliyun/k8s/k8s-release-metrics.<scope>.<start>.<end>.json`
    - 写完后执行 `jq empty <file>`
    - 拉取完成后关闭本次为 K8S/ACK 打开的相关浏览器标签页；不要关闭用户原本已打开且仍在使用的页签

7. 如本次任务是周报生成，再把结果同步回填到补充输入。
   - `ops_release.release_count`
   - `ops_release.release_success_rate`
   - `ops_release.rollback_count`
   - `ops_release.change_failure_rate`

## 6. 推荐输出结构

- `scope`
- `collection`
- `generated_at`
- `period`
- `release_metrics`
- `report_compatibility`
- `notes`

## 7. 必查清单

- 已确认统计范围与本周报环境一致。
- 已覆盖完整统计周期。
- 已记录发布次数、发布成功率、回滚次数、变更失败率。
- 若 CFR 为计算值，已在 `notes` 中明确使用 `回滚次数 / 发布次数`。
- 若本次任务是周报，补充输入中的 `ops_release` 已同步更新。

## 8. 禁止事项

- 不允许把其他环境的发布记录混入当前统计范围。
- 不允许只写成功率，不写原始发布次数与回滚次数。
- 不允许在控制台可直接统计时，改用旧周报中的手填值覆盖。
- 不允许通过其他资源（如 ECS、RDS）的接口字段、认证方式、响应结构来推测 K8S 的接口。阿里云不同产品的控制台接口相互独立，ECS 或 RDS 的请求模型、认证机制、返回格式不适用于 K8S。每个资源必须从该资源控制台页面的实际 Network 请求中提取接口规范。

## 9. 数据模板

参考模板文件：`templates/k8s-release-metrics.template.json`

输出 JSON 必须包含的字段：
- `scope`：统计范围（如 `prod`）
- `collection`：数据来源（product, console, cluster_id, cluster_name, region, namespace, source_type）
- `preferred_period` 或 `period`：统计周期信息
- `generated_at`：ISO 格式时间戳
- `release_metrics`：发布指标，包含：
  - `release_count`：发布次数
  - `release_success_rate`：发布成功率（字符串如 "100.00%"）
  - `rollback_count`：回滚次数
  - `change_failure_rate`：变更失败率
  - `failure_rate`：失败率
- `changed_deployments`：每次发布详情数组，每项包含：
  - `name`, `namespace`, `image`, `completed_at`, `status`
- `report_compatibility`：周报兼容信息
- `notes`：数据来源说明

## 10. 常见问题

### 10.1 产品面板 Modal 阻挡问题

**问题描述**：
K8S 控制台页面加载时会弹出"产品与服务"模态框，阻挡页面内容。

**解决方案**：
```javascript
const modal = document.querySelector('[role="dialog"]');
if (modal) {
  modal.remove();
  return 'Modal removed';
}
```

### 10.2 页面加载超时

**问题描述**：
直接使用 `new_page` 打开 K8S 页面时经常超时。

**解决方案**：
使用 `navigate_page` 并设置较长的 timeout（30000ms）。

### 10.4 RAM 权限限制问题

**问题描述**：
RAM 用户可能无法列出目标 namespace 的 deployments，控制台会返回"没有数据"或权限错误。

**解决方案**：
- 需要为 RAM 用户授予 `read` 权限（`AliyunCSReadOnlyAccess` 或更细粒度的策略）
- 或者使用具有集群访问权限的 kubeconfig 通过 kubectl 访问

## 11. 完成后反馈

至少反馈：
- 统计周期。
- 统计范围。
- 发布次数、发布成功率，回滚次数、变更失败率。
- 输出 JSON 路径。
