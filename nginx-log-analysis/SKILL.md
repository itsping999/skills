---
name: nginx-log-analysis
description: Nginx access log 分析规范。用于从用户提供的日志路径独立生成结构化流量指标数据。
---

# Nginx Access Log 分析规范

## 1. 目的

从用户提供的 Nginx access log 中提取接口与流量相关指标，独立输出结构化 JSON。

## 2. 标准来源

- 若仓库根目录存在 `README.md`，以其为目录与执行口径补充来源；若不存在，以当前文档为准。
- 本执行流程以当前文档为准，不依赖外部全局 skill 目录。
- 当前脚本入口为：`.codex/skills/nginx-log-analysis/scripts/analyze_nginx_traffic.py`
- 日志原文件可以位于仓库外，通常可直接从用户提供的绝对路径读取。

## 3. 适用场景

- 需要根据 Nginx access log 生成结构化流量指标数据。
- 需要复盘某个时间窗口内的 QPS、成功率、平均响应时间、P95/P99。
- 需要对现有统计口径做调整，例如排除 WebSocket、排除下载接口、只统计成功请求响应时间。
- 需要定位异常峰值请求，并判断它是否属于 4.1 应统计的业务接口。

## 4. 输入与输出

输入：
- 用户提供的 access log 绝对路径，可以在仓库外。
- 目标统计周期。
- 当前统计口径。
- 输出目录，由调用方显式传入，例如 `<nginx_root>`。

输出：
- 结构化分析结果：
  - `<nginx_root>/nginx-traffic.<week_start>.<week_end>.snapshot-<report_day>.json`

常用命令：

```bash
python3 .codex/skills/nginx-log-analysis/scripts/analyze_nginx_traffic.py \
  --log-path /absolute/path/to/access.log \
  --week-start 2026-04-04 \
  --week-end 2026-04-10 \
  --output-dir <nginx_root>
```

## 5. 当前默认口径

当前默认使用下面这套口径：

1. 先排除不应纳入接口统计的请求。
   - WebSocket 升级请求：
     - 状态码 `101`
     - 或路径包含 `/socket.io/`
     - 或路径包含 `transport=websocket`
   - 下载类接口：
     - 当前按 `/download` 前缀排除
   - 若确认某类更新包、静态资源、历史兼容接口不属于 4.1 业务 API，可继续通过前缀扩展排除规则，而不是保留在峰值样本中。

2. 成功率口径：
   - `4xx` 不算失败
   - `501` 不算失败
   - `503` 不算失败
   - 其他 `5xx` 算失败

3. 响应时间口径：
   - 只统计成功请求的 `rt`
   - `QPS` 与成功率使用“排除 WebSocket/下载后的全部请求”
   - `平均响应时间 / 峰值 / P95 / P99` 只使用成功请求
   - 若峰值样本虽满足“非失败状态”，但业务上不属于接口性能统计范围，仍应通过排除前缀移出统计样本后再重算

4. 百分位算法：
   - 使用 nearest-rank
   - `P95 = ceil(N * 0.95)` 对应位置
   - `P99 = ceil(N * 0.99)` 对应位置

## 6. 参考步骤

1. 可先读取日志样例。
   - 至少检查首尾几行，确认是否包含：
     - 时间戳
     - 请求行
     - 状态码
     - `rt=...`

2. 再判断日志是否足够支撑目标指标计算。
   - 若存在 `rt`，可统计：
     - `QPS 平均`
     - `QPS 峰值`
     - `API 成功率`
     - `平均响应时间`
     - `P95 / P99`
     - `响应时间峰值`
   - 若不存在 `rt`，通常只能统计流量与成功率，并说明响应时间暂不可计算。

3. 大文件更适合直接原地分析。
   - 通常不需要先把日志复制到仓库。
   - 更适合直接读取用户提供的绝对路径。
   - 若日志很大，可优先用 Python 流式逐行统计，而不是整文件读入内存。

4. 统计前可先固化过滤规则。
   - 明确哪些请求要排除。
   - 明确哪些状态码算失败。
   - 明确响应时间采用“全部请求”还是“只成功请求”。
   - 若已发现异常峰值，先定位原始日志行和请求路径，再决定是否扩展 `--exclude-download-prefix` 或 `--exclude-static-prefix`。

5. 可输出结构化 JSON。
   - 至少包含：
     - `source`
     - `preferred_period`
     - `observed_window`
     - `request_summary`
     - `traffic_metrics`
     - `notes`

6. 结构化结果生成后，可再由后续流程按目录约定读取对应周期文件。
   - 当前文件命名建议为：
     - `<output_dir>/nginx-traffic.<week_start>.<week_end>.snapshot-*.json`
   - 其中 `traffic_metrics` 可直接作为后续分析或展示的输入。

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

## 8. 建议核对项

- 已明确日志文件路径，不要求日志放进仓库。
- 已确认日志里存在 `rt` 字段，或明确说明为什么无法算响应时间。
- 已明确本次是否排除 WebSocket 请求。
- 已明确本次是否排除下载类接口。
- 已明确本次是否需要排除静态资源、更新包或其他不属于业务 API 的请求前缀。
- 已明确响应时间是否只按成功请求统计。
- `P95/P99` 算法在反馈中保持一致，不要这一周 nearest-rank、下一周又改插值。
- 输出结果中的口径说明与本次统计规则一致，尤其是异常峰值是否已被排除。
- 若发现异常峰值，最好保留对应原始日志行到 `notes` 或终端反馈中。

## 9. 约束与边界

- 一般不需要要求用户先把日志复制到仓库再分析。
- 该 skill 可以独立运行，不依赖周报脚本、补充输入或其他外部步骤才能产出结果。
- 输出目录更适合由调用方显式传入，而不是由 skill 内部固定。
- WebSocket 长连接的 `rt` 通常不宜直接作为普通接口响应时间峰值。
- 若口径发生变化，更适合在结果中说明，例如是否排除下载接口、是否只统计成功请求。
- 若异常峰值来自不应计入 4.1 的接口，更适合调整排除规则后重算，而不是直接接受该峰值进入周报。
- 状态码口径更适合明确记录在 `notes` 中，而不是只依赖隐含约定。

## 10. 完成后反馈

反馈中通常可包含：
- 使用的日志路径。
- 本次采用的过滤与成功率口径。
- 生成的数据文件路径。
- 对应周期的核心指标值。
