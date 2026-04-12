#!/usr/bin/env python3
"""Analyze nginx access logs and emit structured traffic metrics."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


LOG_RE = re.compile(
    r'\[(?P<timestamp>[^\]]+)\]\s+"(?P<method>[A-Z]+)\s+(?P<target>\S+)(?:\s+HTTP/[^"]+)?"\s+(?P<status>\d{3})\s+\S+(?P<tail>.*)$'
)
RT_RE = re.compile(r"\brt=(?P<rt>\d+(?:\.\d+)?)")


@dataclass
class ParsedLine:
    observed_at: datetime
    target: str
    status: int
    rt_seconds: float | None
    raw_line: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="分析 Nginx access log 并生成结构化指标")
    parser.add_argument("--log-path", required=True, help="access log 文件绝对路径")
    parser.add_argument("--week-start", required=True, help="统计开始日期（YYYY-MM-DD）")
    parser.add_argument("--week-end", required=True, help="统计结束日期（YYYY-MM-DD）")
    parser.add_argument("--report-day", help="快照标记日期（YYYY-MM-DD），默认使用 week_end")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="结构化结果输出目录，由调用方显式传入",
    )
    parser.add_argument(
        "--timezone",
        default="Asia/Shanghai",
        help="时区标记（默认: Asia/Shanghai）",
    )
    parser.add_argument(
        "--exclude-download-prefix",
        action="append",
        default=None,
        help="按前缀排除下载类接口，可多次传入；默认包含 /download",
    )
    parser.add_argument(
        "--exclude-static-prefix",
        action="append",
        default=[],
        help="按前缀排除静态资源请求，可多次传入",
    )
    return parser.parse_args()


def parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_log_line(line: str) -> ParsedLine | None:
    match = LOG_RE.search(line)
    if not match:
        return None
    try:
        observed_at = datetime.strptime(match.group("timestamp"), "%d/%b/%Y:%H:%M:%S %z")
    except ValueError:
        return None
    rt_match = RT_RE.search(match.group("tail"))
    rt_seconds = float(rt_match.group("rt")) if rt_match else None
    return ParsedLine(
        observed_at=observed_at,
        target=match.group("target"),
        status=int(match.group("status")),
        rt_seconds=rt_seconds,
        raw_line=line.rstrip("\n"),
    )


def is_websocket_request(target: str, status: int) -> bool:
    lowered = target.lower()
    return status == 101 or "/socket.io/" in lowered or "transport=websocket" in lowered


def is_failed_status(status: int) -> bool:
    if 400 <= status < 500:
        return False
    if status in {501, 503}:
        return False
    return 500 <= status < 600


def nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(1, math.ceil(len(ordered) * percentile)) - 1
    return ordered[index]


def main() -> None:
    args = parse_args()

    log_path = Path(args.log_path)
    if not log_path.exists():
        raise FileNotFoundError(f"日志文件不存在: {log_path}")

    week_start = parse_day(args.week_start)
    week_end = parse_day(args.week_end)
    if week_end < week_start:
        raise ValueError("week_end 不能早于 week_start")

    report_day = args.report_day or args.week_end
    download_prefixes = args.exclude_download_prefix or ["/download"]
    static_prefixes = args.exclude_static_prefix or []

    observed_start: datetime | None = None
    observed_end: datetime | None = None
    total_requests = 0
    included_requests = 0
    failed_requests = 0
    excluded_websocket_requests = 0
    excluded_download_requests = 0
    excluded_static_asset_requests = 0
    successful_requests_for_latency = 0
    status_counts: Counter[int] = Counter()
    included_per_second: Counter[str] = Counter()
    latency_values: list[float] = []
    peak_latency_seconds: float | None = None
    peak_latency_at: str | None = None
    peak_latency_line: str | None = None

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            parsed = parse_log_line(raw_line)
            if not parsed:
                continue
            if not (week_start <= parsed.observed_at.date() <= week_end):
                continue

            total_requests += 1
            status_counts[parsed.status] += 1
            observed_start = parsed.observed_at if observed_start is None else min(observed_start, parsed.observed_at)
            observed_end = parsed.observed_at if observed_end is None else max(observed_end, parsed.observed_at)

            if is_websocket_request(parsed.target, parsed.status):
                excluded_websocket_requests += 1
                continue
            if any(parsed.target.startswith(prefix) for prefix in download_prefixes):
                excluded_download_requests += 1
                continue
            if any(parsed.target.startswith(prefix) for prefix in static_prefixes):
                excluded_static_asset_requests += 1
                continue

            included_requests += 1
            included_per_second[parsed.observed_at.strftime("%Y-%m-%dT%H:%M:%S%z")] += 1

            if is_failed_status(parsed.status):
                failed_requests += 1
                continue
            if parsed.rt_seconds is None:
                continue

            successful_requests_for_latency += 1
            latency_values.append(parsed.rt_seconds)
            if peak_latency_seconds is None or parsed.rt_seconds > peak_latency_seconds:
                peak_latency_seconds = parsed.rt_seconds
                peak_latency_at = parsed.observed_at.isoformat()
                peak_latency_line = parsed.raw_line

    if observed_start is None or observed_end is None:
        raise ValueError("在指定周期内未解析到可用日志记录")

    observed_seconds = max(1.0, (observed_end - observed_start).total_seconds())
    qps_avg = included_requests / observed_seconds
    qps_peak_at = None
    qps_peak = 0
    if included_per_second:
        qps_peak_at, qps_peak = max(included_per_second.items(), key=lambda item: (item[1], item[0]))

    api_success_rate = None
    if included_requests > 0:
        api_success_rate = (included_requests - failed_requests) / included_requests * 100

    status_counts_top20 = dict(sorted(status_counts.items(), key=lambda item: (-item[1], item[0]))[:20])
    payload: dict[str, Any] = {
        "source": {
            "log_path": str(log_path.resolve()),
            "log_type": "nginx_access_log",
        },
        "preferred_period": {
            "start": week_start.isoformat(),
            "end": week_end.isoformat(),
            "report_day": report_day,
            "timezone": args.timezone,
        },
        "observed_window": {
            "start": observed_start.isoformat(),
            "end": observed_end.isoformat(),
        },
        "request_summary": {
            "total_requests": total_requests,
            "included_requests": included_requests,
            "failed_requests": failed_requests,
            "excluded_websocket_requests": excluded_websocket_requests,
            "excluded_download_requests": excluded_download_requests,
            "excluded_static_asset_requests": excluded_static_asset_requests,
            "successful_requests_for_latency": successful_requests_for_latency,
            "failure_rule": "4xx 不算失败，501/503 不算失败，其余 5xx 算失败。",
            "status_counts_top20": {str(code): count for code, count in status_counts_top20.items()},
        },
        "traffic_metrics": {
            "qps_avg": round(qps_avg, 2),
            "qps_peak": qps_peak,
            "qps_peak_at": qps_peak_at,
            "api_success_rate": round(api_success_rate, 2) if api_success_rate is not None else None,
            "response_avg_seconds": round(sum(latency_values) / len(latency_values), 3) if latency_values else None,
            "response_peak_seconds": round(peak_latency_seconds, 3) if peak_latency_seconds is not None else None,
            "response_peak_at": peak_latency_at,
            "response_p95_seconds": round(nearest_rank(latency_values, 0.95), 3) if latency_values else None,
            "response_p99_seconds": round(nearest_rank(latency_values, 0.99), 3) if latency_values else None,
        },
        "notes": [
            "已从统计中排除 WebSocket 升级请求，排除规则为状态码 101 或请求路径包含 /socket.io/ 或 transport=websocket。",
            f"已从 4.1 统计中排除下载类接口请求，当前前缀为: {', '.join(download_prefixes)}。",
            (
                f"已从 4.1 统计中排除静态资源请求，当前前缀为: {', '.join(static_prefixes)}。"
                if static_prefixes
                else "当前未额外配置静态资源前缀排除。"
            ),
            "成功率口径为：4xx 不算失败，501/503 不算失败，其余 5xx 算失败。",
            "平均响应时间、峰值、P95、P99 仅基于成功请求的 rt 计算，百分位算法使用 nearest-rank。",
        ],
    }
    if peak_latency_seconds is not None:
        payload["peak_latency_sample"] = {
            "rt_seconds": round(peak_latency_seconds, 3),
            "at": peak_latency_at,
            "raw_line": peak_latency_line,
        }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (
        f"nginx-traffic.{week_start.isoformat()}.{week_end.isoformat()}.snapshot-{report_day}.json"
    )
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已生成 Nginx 结构化数据: {output_path}")


if __name__ == "__main__":
    main()
