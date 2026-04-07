---
name: aliyun-certificate-expiry
description: 阿里云证书到期时间拉取规范。用于复用当前已登录的阿里云控制台会话，拉取 SSL 证书列表、到期时间、剩余天数与提醒状态，并写入项目 data/aliyun/certificates 目录。
---

# 阿里云证书到期时间拉取规范

## 1. 目的

在不离开用户当前真实 Chrome/Aliyun 登录会话的前提下，拉取证书管理控制台中的 SSL 证书列表、剩余天数、到期日期和提醒状态，沉淀为结构化 JSON，供周报或风险巡检复用。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为目录与执行口径补充来源；若不存在，以当前文档和同目录模板为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 使用结果最终维护在 `data/aliyun/certificates/` 目录下。
- 周报“交付质量与变更风险”中的 `证书到期提醒` 优先来自阿里云数字证书管理服务。
- 若资源区分地域，默认先从 `华南1（深圳）/ cn-shenzhen` 开始查找，但必须继续检查其他地域；不允许只查深圳后就停止。

## 3. 适用场景

- 需要补充证书到期时间和剩余天数。
- 需要识别 30 天内到期的证书风险。
- 需要确认到期提醒是否已开启、证书是否已部署。
- 需要为周报回填 `证书到期提醒` 字段。

## 4. 输入与输出

输入：
- 当前已登录阿里云控制台的 Chrome 页面。

输出：
- `data/aliyun/certificates/certificate-expiry.<scope>.<date>.json`

## 5. 操作步骤

1. 复用当前 Chrome DevTools MCP 已接入的真实浏览器会话。
   - 禁止切换到干净浏览器或隔离 profile。
   - 保持阿里云控制台登录态。

2. 打开数字证书管理服务控制台。
   - 页面一般为 `https://yundun.console.aliyun.com/?p=cas#/instance/upload/cn-hangzhou`。
   - 优先查看 `SSL证书管理 V2.0 -> 上传证书` 页签。

3. 读取页面当前可见证书列表。
   - 每条证书至少记录：
     - 证书名称
     - 资源 ID
     - CertIdentifier
     - 品牌 / 算法
     - 状态
     - 绑定域名
     - 剩余天数
     - 到期日期
     - 是否已部署
   - 同时记录顶部总览：
     - 总数量
     - 未开启到期提醒
     - 未部署云产品
     - 证书待续费

4. 做结果归一化。
   - 证书通常按账号全局资源统计，建议使用 `global` scope。
   - 剩余天数优先保留控制台 UI 展示值，不自行重算覆盖。
   - 若多域名绑定到一张证书，应作为数组保存。

5. 写入结构化 JSON 并校验。
    - **必须严格按照 `templates/certificate-expiry.template.json` 模板格式输出**
    - 目标路径：`data/aliyun/certificates/certificate-expiry.<scope>.<date>.json`
    - 写完后执行 `jq empty <file>`
    - 拉取完成后关闭本次为证书管理打开的相关浏览器标签页；不要关闭用户原本已打开且仍在使用的页签

## 6. 推荐输出结构

- `scope`
- `collection`
- `generated_at`
- `overview`
- `certificates`
- `report_compatibility`
- `report_highlights`
- `notes`

## 7. 必查清单

- 已确认使用的是当前真实阿里云登录会话，而不是干净浏览器。
- 已记录每张证书的到期日期和剩余天数。
- 已记录未开启提醒数量。
- 已明确哪些证书落入 30 天内到期窗口。
- 若本次任务是周报，`monitoring_security.cert_expiry` 已同步更新。

## 8. 禁止事项

- 不允许自己重算后覆盖控制台展示的剩余天数字段。
- 不允许只写总数，不写单证书明细。
- 不允许把提醒未开启写成"无风险"。
- 不允许通过其他资源（如 ECS、RDS）的接口字段、认证方式、响应结构来推测 Certificate 的接口。阿里云不同产品的控制台接口相互独立，ECS 或 RDS 的请求模型、认证机制、返回格式不适用于 Certificate。每个资源必须从该资源控制台页面的实际 Network 请求中提取接口规范。

## 9. 完成后反馈

至少反馈：
- 证书总数。
- 最早到期日期和对应证书。
- 30 天内到期证书数量。
- 未开启提醒数量。
- 输出 JSON 路径。

## 10. 数据模板

参考模板文件：`templates/certificate-expiry.template.json`

输出 JSON 必须包含的字段：
- `scope`：资源范围，固定为 `global`
- `generated_at`：ISO 格式时间戳
- `overview`：总览对象，包含 `certificate_total`、`reminder_not_enabled`、`undeployed_cloud_products`、`pending_renewal`
- `certificates`：证书数组，每项包含：
  - `name`、`resource_id`、`cert_identifier`
  - `brand`、`algorithm`、`status`
  - `bound_domains`：绑定域名数组
  - `remaining_days_ui`：UI 显示的剩余天数
  - `expires_on`：到期日期
  - `deployed`：是否已部署
- `report_compatibility`：报告兼容性对象
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
- Certificate 页面移除 modal 后可能仍有权限弹窗，需额外处理

### 11.2 剩余天数以 UI 为准

**问题描述**：
自行重算的剩余天数可能与控制台展示不一致。

**解决方案**：
优先保留控制台 UI 展示值 `remaining_days_ui`，不自行重算覆盖。
