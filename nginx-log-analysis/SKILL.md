---
name: nginx-log-analysis
description: Nginx access log 分析规范。用于从用户提供的日志路径直接统计 4.1 接口与流量指标，并生成可供周报复用的结构化数据。
---

# Nginx Access Log 分析规范

## 1. 目的

从用户提供的 Nginx access log 中提取 `4.1 接口与流量` 所需指标，输出结构化 JSON，并按需回填周报补充输入。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为目录与执行口径补充来源；若不存在，以当前文档为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 周报中的 `4.1 接口与流量` 最终由 `scripts/generate_weekly_report.py` 消费 `traffic_metrics`。
- 日志原文件不要求放在仓库内，可以直接从用户提供的绝对路径读取。

## 3. 适用场景

- 需要根据 Nginx access log 回填周报 `4.1`。
- 需要复盘某个时间窗口内的 QPS、成功率、平均响应时间、P95/P99。
- 需要对现有 4.1 的口径做调整，例如排除 WebSocket、排除下载接口、只统计成功请求响应时间。

## 4. 输入与输出

输入：
- 用户提供的 access log 绝对路径，可以在仓库外。
- 目标统计周期。
- 当前统计口径。

输出：
- 结构化分析结果：
  - `data/nginx/nginx-traffic.<week_start>.<week_end>.snapshot-<report_day>.json`
- 如需回填周报：
  - `data/weekly/weekly-input.<week_start>.<week_end>.json`

## 5. 当前默认口径

当前项目里，`4.1` 使用下面这套口径：

1. 先排除不应纳入接口统计的请求。
   - WebSocket 升级请求：
     - 状态码 `101`
     - 或路径包含 `/socket.io/`
     - 或路径包含 `transport=websocket`
   - 下载类接口：
     - 当前按 `/download` 前缀排除

2. 成功率口径：
   - `4xx` 不算失败
   - `501` 不算失败
   - `503` 不算失败
   - 其他 `5xx` 算失败

3. 响应时间口径：
   - 只统计成功请求的 `rt`
   - `QPS` 与成功率使用“排除 WebSocket/下载后的全部请求”
   - `平均响应时间 / 峰值 / P95 / P99` 只使用成功请求

4. 百分位算法：
   - 使用 nearest-rank
   - `P95 = ceil(N * 0.95)` 对应位置
   - `P99 = ceil(N * 0.99)` 对应位置

## 6. 操作步骤

1. 先读取日志样例。
   - 至少检查首尾几行，确认是否包含：
     - 时间戳
     - 请求行
     - 状态码
     - `rt=...`

2. 先确认日志是否足够支撑 4.1。
   - 若存在 `rt`，可统计：
     - `QPS 平均`
     - `QPS 峰值`
     - `API 成功率`
     - `平均响应时间`
     - `P95 / P99`
     - `响应时间峰值`
   - 若不存在 `rt`，只能统计流量与成功率，必须明确说明响应时间无法计算。

3. 大文件直接原地分析。
   - 不要要求用户先把日志复制到仓库。
   - 优先直接读取用户提供的绝对路径。
   - 若日志很大，优先用 Python 流式逐行统计，不要整文件读入内存。

4. 统计前先固化过滤规则。
   - 明确哪些请求要排除。
   - 明确哪些状态码算失败。
   - 明确响应时间是“全部请求”还是“只成功请求”。

5. 输出结构化 JSON。
   - 至少包含：
     - `source`
     - `preferred_period`
     - `observed_window`
     - `request_summary`
     - `traffic_metrics`
     - `notes`

6. 如需周报回填，再写补充输入。
   - 当前 `traffic_metrics` 至少建议回填：
     - `qps_avg`
     - `qps_peak`
     - `api_success_rate`
     - `response_avg`
     - `response_peak`
     - `p95_p99`

## 7. 推荐输出字段

`request_summary`：
- `total_requests`
- `failed_requests`
- `excluded_websocket_requests`
- `excluded_download_requests`
- `successful_requests_for_latency`
- `failure_rule`
- `status_counts_top20`

`traffic_metrics`：
- `qps_avg`
- `qps_peak`
- `qps_peak_at`
- `api_success_rate`
- `response_avg_seconds`
- `response_peak_seconds`
- `response_peak_at`
- `response_p95_seconds`
- `response_p99_seconds`

## 8. 必查清单

- 已明确日志文件路径，不要求日志放进仓库。
- 已确认日志里存在 `rt` 字段，或明确说明为什么无法算响应时间。
- 已明确本次是否排除 WebSocket 请求。
- 已明确本次是否排除下载类接口。
- 已明确响应时间是否只按成功请求统计。
- `P95/P99` 算法在反馈中保持一致，不要这一周 nearest-rank、下一周又改插值。
- 周报补充输入与结构化分析结果口径一致。
- 若发现异常峰值，最好保留对应原始日志行到 `notes` 或终端反馈中。

## 9. 禁止事项

- 不允许要求用户先把日志复制到仓库再分析。
- 不允许把 WebSocket 长连接的 `rt` 直接当普通接口响应时间峰值。
- 不允许在未说明口径变化的情况下，随意切换“是否排除下载接口”或“是否只统计成功请求”。
- 不允许把状态码口径写在脑子里，不落到 `notes`。

## 10. 完成后反馈

至少反馈：
- 使用的日志路径。
- 本次采用的过滤与成功率口径。
- 生成的数据文件路径。
- 是否已回填周报补充输入。
- `4.1` 的最终指标值。
