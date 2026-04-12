#!/usr/bin/env python3
"""Generate cloud platform weekly operation report markdown files."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


FIELD_ALIASES = {
    "week_start": ["week_start", "周开始", "统计开始"],
    "week_end": ["week_end", "周结束", "统计结束"],
    "title": ["title", "标题", "周报标题"],
    "version_note": ["version_note", "版本说明", "说明"],
    "availability_summary": ["availability_summary", "平台整体可用性"],
    "major_incidents": ["major_incidents", "重大故障记录"],
    "cloud_resources": ["cloud_resources", "云资源运行情况"],
    "traffic_metrics": ["traffic_metrics", "业务流量与接口指标"],
    "ops_release": ["ops_release", "运维与发布情况"],
    "monitoring_security": ["monitoring_security", "监控与安全情况"],
    "reliability_metrics": ["reliability_metrics", "可靠性指标", "SRE指标"],
    "incident_ids": ["incident_ids", "关联事故", "事故编号列表"],
    "exec_summary": ["exec_summary", "周报摘要", "执行摘要"],
    "highlights": ["highlights", "本周亮点", "关键结论"],
    "key_risks": ["key_risks", "重点关注风险", "风险与关注"],
    "next_focus": ["next_focus", "下周重点", "下周重点事项"],
    "decisions_needed": ["decisions_needed", "待决策事项"],
}
WEEKLY_TEMPLATE_MARKER = "<!-- TEMPLATE: WEEKLY_REPORT_V2 -->"
DEFAULT_AVAILABILITY_SCOPES = ["business"]
AVAILABILITY_SCOPE_ALIASES = {
    "infra": ("infra", "基础设施", "基础设施可用率", "infrastructure"),
    "app": ("app", "应用", "应用可用率", "application"),
    "business": ("business", "平台业务", "业务", "平台业务可用率", "business"),
}


def pick_field(payload: dict[str, Any], field_name: str) -> Any:
    for alias in FIELD_ALIASES[field_name]:
        if alias in payload and payload[alias] not in (None, ""):
            return payload[alias]
    return None


def normalize_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_list(value: Any, field_name: str) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return value
    raise ValueError(f"{field_name} 字段必须是数组或逗号分隔字符串")


def normalize_text_list(value: Any, field_name: str) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        parts = [x.strip() for x in re.split(r"[\n;,；]+", value) if x.strip()]
        return parts
    if isinstance(value, list):
        texts = []
        for item in value:
            text = normalize_string(item)
            if text:
                texts.append(text)
        return texts
    raise ValueError(f"{field_name} 字段必须是字符串或字符串数组")


def merge_dict_prefer_existing(base: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in fallback.items():
        if key not in merged or merged[key] in (None, ""):
            merged[key] = value
    return merged


def extract_first_number(value: Any) -> float | None:
    text = normalize_string(value)
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def normalize_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def severity_rank(value: str) -> int:
    text = normalize_string(value).upper()
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
    return order.get(text, 9)


def parse_datetime(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        pass
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法识别的时间格式: {value}")


def parse_date(value: str) -> date:
    return parse_datetime(value).date()


def format_decimal(value: float | None, digits: int = 2) -> str:
    if value is None:
        return ""
    if digits == 0 or abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.{digits}f}"


def format_percent_from_number(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2f}%"


def format_duration_average(seconds: float | None) -> str:
    if seconds is None:
        return ""
    if seconds < 1:
        return f"{seconds * 1000:.2f} ms"
    return f"{seconds:.2f} s"


def format_duration_seconds(seconds: float | None) -> str:
    if seconds is None:
        return ""
    return f"{seconds:.2f} s"


def build_p95_p99_text(p95_seconds: float | None, p99_seconds: float | None) -> str:
    parts = []
    if p95_seconds is not None:
        parts.append(format_duration_seconds(p95_seconds))
    if p99_seconds is not None:
        parts.append(format_duration_seconds(p99_seconds))
    return " / ".join(parts)


def format_minutes_value(minutes: float | None) -> str:
    if minutes is None:
        return "未填写"
    if abs(minutes - round(minutes)) < 1e-6:
        return f"{int(round(minutes))} 分钟"
    return f"{minutes:.1f} 分钟"


def format_percent_value(value: float) -> str:
    if abs(value - 100.0) < 1e-9:
        return "100%"
    digits = 3 if value >= 99.99 else 2
    rendered = f"{value:.{digits}f}"
    if "." not in rendered:
        return f"{rendered}%"
    integer, fraction = rendered.split(".", 1)
    fraction = fraction.rstrip("0")
    if not fraction:
        return f"{integer}.00%"
    if len(fraction) == 1:
        fraction += "0"
    return f"{integer}.{fraction}%"


def period_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    period_start = datetime.combine(start, datetime.min.time())
    period_end = datetime.combine(end + timedelta(days=1), datetime.min.time())
    return period_start, period_end


def overlap_minutes(
    interval_start: datetime,
    interval_end: datetime,
    window_start: datetime,
    window_end: datetime,
) -> float:
    clipped_start = max(interval_start, window_start)
    clipped_end = min(interval_end, window_end)
    if clipped_end <= clipped_start:
        return 0.0
    return (clipped_end - clipped_start).total_seconds() / 60


def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda item: item[0])
    merged: list[tuple[datetime, datetime]] = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def normalize_availability_scopes(value: Any) -> list[str]:
    if value in (None, "", [], ()):
        return DEFAULT_AVAILABILITY_SCOPES.copy()
    if isinstance(value, list):
        scopes: list[str] = []
        for item in value:
            scopes.extend(normalize_availability_scopes(item))
        deduped = []
        seen = set()
        for scope in scopes:
            if scope not in seen:
                deduped.append(scope)
                seen.add(scope)
        return deduped or DEFAULT_AVAILABILITY_SCOPES.copy()

    text = normalize_string(value)
    if not text:
        return DEFAULT_AVAILABILITY_SCOPES.copy()
    if any(token in text.lower() for token in ("all", "全部", "全部可用率")):
        return ["infra", "app", "business"]

    parts = [part.strip() for part in re.split(r"[\s,，/、;；|]+", text) if part.strip()]
    scopes: list[str] = []
    for part in parts:
        lowered = part.lower()
        for scope, aliases in AVAILABILITY_SCOPE_ALIASES.items():
            if any(alias.lower() == lowered or alias.lower() in lowered for alias in aliases):
                scopes.append(scope)
                break

    deduped = []
    seen = set()
    for scope in scopes:
        if scope not in seen:
            deduped.append(scope)
            seen.add(scope)
    return deduped or DEFAULT_AVAILABILITY_SCOPES.copy()


def parse_incident_summary_fields(report_abs_path: Path) -> dict[str, str]:
    fields = {
        "occurred_at": "",
        "resolved_at": "",
        "detection_time": "",
        "first_response_at": "",
        "repair_started_at": "",
        "availability_scope": "",
    }
    if not report_abs_path.exists():
        return fields

    mapping = {
        "- 发生时间：": "occurred_at",
        "- 恢复时间：": "resolved_at",
        "- 检测时间：": "detection_time",
        "- 首次响应时间：": "first_response_at",
        "- 开始修复处理时间：": "repair_started_at",
        "- 可用率归属：": "availability_scope",
        "- 可用率范围：": "availability_scope",
        "- 可用率影响维度：": "availability_scope",
        "- 可用率口径：": "availability_scope",
    }
    for line in report_abs_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        for prefix, key in mapping.items():
            if stripped.startswith(prefix):
                fields[key] = stripped.split("：", 1)[1].strip()
    return fields


def infer_weekly_reliability_from_annual(
    incidents_dir: Path,
    week_start: date,
    week_end: date,
    incident_ids: list[str],
) -> dict[str, Any]:
    rows = collect_annual_rows(incidents_dir, week_start.year, week_end.year)
    if not rows:
        return {"mttd": None, "mtta": None, "severity_counts": {"P0": 0, "P1": 0, "P2": 0}}

    target_ids = set(incident_ids)
    annual_dir = incidents_dir / "annual"
    mttd_minutes: list[float] = []
    mtta_minutes: list[float] = []
    severity_counts = {"P0": 0, "P1": 0, "P2": 0}

    for row in rows:
        if target_ids and row["incident_id"] not in target_ids:
            continue
        try:
            occurred_dt = parse_datetime(row["occurred_at"])
        except ValueError:
            continue
        if not (week_start <= occurred_dt.date() <= week_end):
            continue

        severity = normalize_string(row.get("severity", "")).upper()
        if severity in severity_counts:
            severity_counts[severity] += 1

        report_rel = row.get("report_path", "")
        if not report_rel:
            continue
        report_abs = (annual_dir / report_rel).resolve()
        times = parse_incident_summary_fields(report_abs)

        occurred = times.get("occurred_at")
        detected = times.get("detection_time")
        first_response = times.get("first_response_at")
        if occurred and detected:
            try:
                mttd_minutes.append(float((parse_datetime(detected) - parse_datetime(occurred)).total_seconds() // 60))
            except ValueError:
                pass
        if detected and first_response:
            try:
                mtta_minutes.append(float((parse_datetime(first_response) - parse_datetime(detected)).total_seconds() // 60))
            except ValueError:
                pass

    avg_mttd = sum(mttd_minutes) / len(mttd_minutes) if mttd_minutes else None
    avg_mtta = sum(mtta_minutes) / len(mtta_minutes) if mtta_minutes else None
    return {"mttd": avg_mttd, "mtta": avg_mtta, "severity_counts": severity_counts}


def sanitize_table_cell(value: Any) -> str:
    text = normalize_string(value).replace("\n", " ")
    return text.replace("|", "\\|")


def make_row(item: dict[str, Any], key_map: dict[str, tuple[str, ...]]) -> dict[str, str]:
    row: dict[str, str] = {}
    for canonical_key, aliases in key_map.items():
        row[canonical_key] = ""
        for alias in aliases:
            if alias in item and item[alias] not in (None, ""):
                row[canonical_key] = normalize_string(item[alias])
                break
    return row


def normalize_table_rows(
    value: Any,
    field_name: str,
    key_map: dict[str, tuple[str, ...]],
) -> list[dict[str, str]]:
    rows = normalize_list(value, field_name)
    normalized: list[dict[str, str]] = []
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError(f"{field_name} 每一项必须是对象")
        normalized.append(make_row(item, key_map))
    return normalized


def normalize_availability_summary(value: Any) -> dict[str, dict[str, str]]:
    default_row = {
        "infra": "未填写",
        "app": "未填写",
        "business": "未填写",
        "mttr": "未填写",
        "mtbf": "未填写",
    }
    if not isinstance(value, dict):
        return {"week": default_row.copy(), "month": default_row.copy(), "year": default_row.copy()}

    row_key_map = {
        "infra": ("infra", "基础设施可用率"),
        "app": ("app", "应用可用率"),
        "business": ("business", "平台业务可用率"),
        "mttr": ("mttr", "平均恢复时间", "平均恢复时间（MTTR）"),
        "mtbf": ("mtbf", "平均故障间隔时间", "平均故障间隔时间（MTBF）"),
    }

    def parse_period(period_aliases: tuple[str, ...]) -> dict[str, str]:
        source = None
        for alias in period_aliases:
            if alias in value and isinstance(value[alias], dict):
                source = value[alias]
                break
        if not source:
            return default_row.copy()
        row = make_row(source, row_key_map)
        for key, v in row.items():
            if not v:
                row[key] = "未填写"
        return row

    return {
        "week": parse_period(("week", "本周")),
        "month": parse_period(("month", "本月")),
        "year": parse_period(("year", "全年")),
    }


def parse_annual_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not path.exists():
        return rows

    table_row_pattern = re.compile(r"^\|(.+)\|$")
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

    for line in path.read_text(encoding="utf-8").splitlines():
        match = table_row_pattern.match(line.strip())
        if not match:
            continue
        cells = [cell.strip() for cell in match.group(1).split("|")]
        if not cells:
            continue
        if cells[0] in {"事故编号", "-", "---"}:
            continue
        if all(set(cell) <= {"-"} for cell in cells):
            continue

        report_path = ""
        link_match = link_pattern.search(cells[-1])
        if link_match:
            report_path = link_match.group(1)

        if len(cells) >= 13:
            rows.append(
                {
                    "incident_id": cells[0],
                    "occurred_at": cells[1],
                    "title": cells[2],
                    "severity": cells[3],
                    "system": cells[4],
                    "region": cells[5],
                    "status": cells[6],
                    "mttr": cells[7],
                    "report_path": report_path,
                }
            )
    return rows


def extract_resolved_time(report_abs_path: Path) -> str:
    return parse_incident_summary_fields(report_abs_path).get("resolved_at") or "未填写"


def collect_annual_rows(
    incidents_dir: Path,
    start_year: int,
    end_year: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for year in range(start_year, end_year + 1):
        rows.extend(parse_annual_rows(incidents_dir / "annual" / f"{year}.md"))
    return rows


def load_incident_records(
    incidents_dir: Path,
    period_start: date,
    period_end: date,
    incident_ids: list[str],
) -> list[dict[str, Any]]:
    target_ids = set(incident_ids)
    annual_rows = collect_annual_rows(incidents_dir, period_start.year - 1, period_end.year)
    annual_dir = incidents_dir / "annual"
    records: list[dict[str, Any]] = []

    for row in annual_rows:
        if target_ids and row["incident_id"] not in target_ids:
            continue
        report_rel = row.get("report_path", "")
        report_abs = (annual_dir / report_rel).resolve() if report_rel else Path("")
        fields = parse_incident_summary_fields(report_abs)
        occurred_text = fields.get("occurred_at") or row.get("occurred_at", "")
        resolved_text = fields.get("resolved_at") or ""
        repair_started_text = fields.get("repair_started_at") or ""

        try:
            occurred_dt = parse_datetime(occurred_text)
        except ValueError:
            continue
        try:
            resolved_dt = parse_datetime(resolved_text)
        except ValueError:
            continue
        try:
            repair_started_dt = parse_datetime(repair_started_text)
        except ValueError:
            continue
        if resolved_dt <= repair_started_dt:
            continue

        records.append(
            {
                "incident_id": row["incident_id"],
                "occurred_at": occurred_dt,
                "resolved_at": resolved_dt,
                "repair_started_at": repair_started_dt,
                "severity": normalize_string(row.get("severity")).upper() or "未标注",
                "title": row.get("title", ""),
                "system": row.get("system", ""),
                "region": row.get("region", ""),
                "report_path": report_rel,
                "availability_scopes": normalize_availability_scopes(fields.get("availability_scope")),
            }
        )

    return records


def calculate_availability_metrics(
    incidents_dir: Path,
    week_start: date,
    week_end: date,
    incident_ids: list[str],
) -> dict[str, dict[str, str]]:
    month_start = week_end.replace(day=1)
    year_start = date(week_end.year, 1, 1)
    incident_records = load_incident_records(incidents_dir, year_start, week_end, incident_ids)

    def summarize(period_start: date, period_end: date) -> dict[str, str]:
        window_start, window_end = period_bounds(period_start, period_end)
        total_minutes = (window_end - window_start).total_seconds() / 60
        intervals_by_scope = {"infra": [], "app": [], "business": []}
        incident_durations: list[float] = []

        for record in incident_records:
            overlap = overlap_minutes(
                record["repair_started_at"],
                record["resolved_at"],
                window_start,
                window_end,
            )
            if overlap <= 0:
                continue
            incident_durations.append(overlap)
            clipped_start = max(record["repair_started_at"], window_start)
            clipped_end = min(record["resolved_at"], window_end)
            for scope in record["availability_scopes"]:
                if scope in intervals_by_scope:
                    intervals_by_scope[scope].append((clipped_start, clipped_end))

        summary: dict[str, str] = {}
        for scope in ("infra", "app", "business"):
            merged = merge_intervals(intervals_by_scope[scope])
            downtime = sum((end - start).total_seconds() / 60 for start, end in merged)
            availability = 100.0 if total_minutes <= 0 else max(0.0, (total_minutes - downtime) / total_minutes * 100)
            summary[scope] = format_percent_value(availability)

        if incident_durations:
            avg_mttr = sum(incident_durations) / len(incident_durations)
            summary["mttr"] = format_minutes_value(avg_mttr)
        else:
            summary["mttr"] = "0 分钟"
        summary["mtbf"] = "未填写"
        return summary

    return {
        "week": summarize(week_start, week_end),
        "month": summarize(month_start, week_end),
        "year": summarize(year_start, week_end),
    }


def build_incidents_from_annual(
    incidents_dir: Path,
    week_start: date,
    week_end: date,
    incident_ids: list[str],
) -> tuple[list[dict[str, str]], int]:
    rows = collect_annual_rows(incidents_dir, week_start.year, week_end.year)
    if not rows:
        return [], 0

    target_ids = set(incident_ids)
    selected = []
    for row in rows:
        if target_ids and row["incident_id"] not in target_ids:
            continue
        try:
            occurred = parse_datetime(row["occurred_at"])
        except ValueError:
            continue
        row["occurred_dt"] = occurred
        selected.append(row)

    this_week = [
        row for row in selected if week_start <= row["occurred_dt"].date() <= week_end
    ]
    this_week_count = len(this_week)

    if this_week:
        source_rows = sorted(this_week, key=lambda r: r["occurred_dt"])
    else:
        source_rows = []

    records: list[dict[str, str]] = []
    annual_dir = incidents_dir / "annual"
    for idx, row in enumerate(source_rows, 1):
        occurred_date = row["occurred_dt"].strftime("%Y-%m-%d")
        time_label = occurred_date
        if row["occurred_dt"].date() < week_start:
            time_label = f"（历史）{occurred_date}"

        report_rel = row.get("report_path", "")
        report_abs = (annual_dir / report_rel).resolve() if report_rel else Path("")
        resolved_at = extract_resolved_time(report_abs) if report_rel else "未填写"
        cause = "详见事故报告"
        if report_rel:
            incident_year = row["occurred_dt"].year
            cause = f"[{row['incident_id']}](../../incidents/{incident_year}/{row['incident_id']}.md)"

        records.append(
            {
                "no": str(idx),
                "time": time_label,
                "severity": row.get("severity", "未标注"),
                "description": row["title"],
                "impact_scope": f"{row.get('region', '未知地区')} / {row.get('system', '未知系统')}",
                "recovery_time": resolved_at,
                "cause": cause,
            }
        )
    return records, this_week_count


def build_historical_incidents_from_annual(
    incidents_dir: Path,
    week_start: date,
    incident_ids: list[str],
    limit: int = 5,
) -> list[dict[str, str]]:
    annual_rows = collect_annual_rows(incidents_dir, week_start.year - 1, week_start.year)
    if not annual_rows:
        return []

    target_ids = set(incident_ids)
    selected: list[dict[str, Any]] = []
    for row in annual_rows:
        if target_ids and row["incident_id"] not in target_ids:
            continue
        try:
            occurred = parse_datetime(row["occurred_at"])
        except ValueError:
            continue
        if occurred.date() >= week_start:
            continue
        row["occurred_dt"] = occurred
        selected.append(row)

    source_rows = sorted(selected, key=lambda r: r["occurred_dt"], reverse=True)[:limit]
    records: list[dict[str, str]] = []
    annual_dir = incidents_dir / "annual"
    for idx, row in enumerate(source_rows, 1):
        report_rel = row.get("report_path", "")
        report_abs = (annual_dir / report_rel).resolve() if report_rel else Path("")
        resolved_at = extract_resolved_time(report_abs) if report_rel else "未填写"
        cause = "详见事故报告"
        if report_rel:
            incident_year = row["occurred_dt"].year
            cause = f"[{row['incident_id']}](../../incidents/{incident_year}/{row['incident_id']}.md)"
        records.append(
            {
                "no": str(idx),
                "time": f"（历史）{row['occurred_dt'].strftime('%Y-%m-%d')}",
                "severity": row.get("severity", "未标注"),
                "description": row["title"],
                "impact_scope": f"{row.get('region', '未知地区')} / {row.get('system', '未知系统')}",
                "recovery_time": resolved_at,
                "cause": cause,
            }
        )
    return records


def normalize_major_incidents(
    value: Any,
    incidents_dir: Path,
    week_start: date,
    week_end: date,
    incident_ids: list[str],
) -> tuple[list[dict[str, str]], int]:
    if value in (None, "", []):
        return build_incidents_from_annual(incidents_dir, week_start, week_end, incident_ids)

    key_map = {
        "no": ("no", "序号"),
        "time": ("time", "时间"),
        "severity": ("severity", "等级", "级别"),
        "description": ("description", "故障描述"),
        "impact_scope": ("impact_scope", "影响范围"),
        "recovery_time": ("recovery_time", "恢复时间"),
        "cause": ("cause", "原因"),
    }
    rows = normalize_table_rows(value, "major_incidents", key_map)
    week_count = 0
    for row in rows:
        t = row.get("time", "")
        historical = "历史" in t
        if historical:
            continue
        try:
            d = parse_date(t)
        except ValueError:
            continue
        if week_start <= d <= week_end:
            week_count += 1

    for idx, row in enumerate(rows, 1):
        if not row["no"]:
            row["no"] = str(idx)
        if not row["severity"]:
            row["severity"] = "未标注"
        for key in ("time", "description", "impact_scope", "recovery_time", "cause"):
            if not row[key]:
                row[key] = "未填写"
    return rows, week_count


def normalize_decisions(value: Any) -> list[dict[str, str]]:
    key_map = {
        "item": ("item", "事项", "问题"),
        "impact": ("impact", "影响", "业务影响"),
        "suggestion": ("suggestion", "建议", "建议动作"),
        "owner": ("owner", "负责人", "owner"),
        "due": ("due", "计划完成", "计划完成时间", "期望决策时间"),
    }
    rows = normalize_table_rows(value, "decisions_needed", key_map)
    for row in rows:
        if not row["item"]:
            row["item"] = "未填写"
        if not row["impact"]:
            row["impact"] = "未填写"
        if not row["suggestion"]:
            row["suggestion"] = "未填写"
        if not row["owner"]:
            row["owner"] = "未指定"
        if not row["due"]:
            row["due"] = "未填写"
    return rows


def normalize_reliability_metrics(
    value: Any,
    availability_week: dict[str, str],
    auto_metrics: dict[str, Any],
) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    mttd = normalize_string(
        source.get("mttd")
        or source.get("平均检测时长（MTTD）")
        or source.get("平均检测时长")
    )
    mtta = normalize_string(
        source.get("mtta")
        or source.get("平均响应时长（MTTA）")
        or source.get("平均响应时长")
    )
    mttr = normalize_string(
        source.get("mttr")
        or source.get("平均恢复时长（MTTR）")
        or source.get("平均恢复时长")
        or availability_week.get("mttr")
    )
    mtbf = normalize_string(
        source.get("mtbf")
        or source.get("平均故障间隔时间（MTBF）")
        or source.get("平均故障间隔时间")
        or availability_week.get("mtbf")
    )

    severity_counts = auto_metrics.get("severity_counts", {"P0": 0, "P1": 0, "P2": 0})
    return {
        "mttd": mttd or format_minutes_value(auto_metrics.get("mttd")),
        "mtta": mtta or format_minutes_value(auto_metrics.get("mtta")),
        "mttr": mttr or "未填写",
        "mtbf": mtbf or "未填写",
        "p0_count": str(severity_counts.get("P0", 0)),
        "p1_count": str(severity_counts.get("P1", 0)),
        "p2_count": str(severity_counts.get("P2", 0)),
    }


def fill_severity_counts_from_major(
    reliability_metrics: dict[str, Any],
    major_incidents: list[dict[str, str]],
    week_start: date,
    week_end: date,
) -> None:
    total_existing = sum(
        int(normalize_string(reliability_metrics.get(key)) or "0")
        for key in ("p0_count", "p1_count", "p2_count")
    )
    if total_existing > 0:
        return

    counts = {"P0": 0, "P1": 0, "P2": 0}
    for row in major_incidents:
        t = normalize_string(row.get("time"))
        if "历史" in t:
            continue
        try:
            d = parse_date(t)
        except ValueError:
            continue
        if not (week_start <= d <= week_end):
            continue
        sev = normalize_string(row.get("severity", "")).upper()
        if sev in counts:
            counts[sev] += 1

    reliability_metrics["p0_count"] = str(counts["P0"])
    reliability_metrics["p1_count"] = str(counts["P1"])
    reliability_metrics["p2_count"] = str(counts["P2"])


def normalize_payload(
    raw: dict[str, Any],
    incidents_dir: Path,
    week_start_override: str = "",
    week_end_override: str = "",
    allow_partial_week_override: bool = False,
) -> dict[str, Any]:
    record = {field: pick_field(raw, field) for field in FIELD_ALIASES}

    if week_start_override:
        record["week_start"] = week_start_override
    if week_end_override:
        record["week_end"] = week_end_override

    for required in ("week_start", "week_end"):
        if not record.get(required):
            raise ValueError(f"缺少必填字段: {required}")

    record["week_start"] = normalize_string(record["week_start"])
    record["week_end"] = normalize_string(record["week_end"])
    record["version_note"] = normalize_string(record.get("version_note")) or "当前报告版本不为最终版，后续将不断迭代完善各类运行指标。"
    allow_partial_week = allow_partial_week_override or str(raw.get("allow_partial_week") or "").strip().lower() in {"1", "true", "yes", "y"}
    week_start = parse_date(record["week_start"])
    week_end = parse_date(record["week_end"])
    if week_end < week_start:
        raise ValueError("周结束时间不能早于周开始时间")
    if not allow_partial_week and (week_end - week_start).days != 6:
        raise ValueError("周报统计周期必须为 7 天（起止日期含首尾）")
    if not allow_partial_week and (week_start.weekday() != 5 or week_end.weekday() != 4):
        raise ValueError(
            "周报统计周期必须是“上周六到本周五”（周开始=周六，周结束=周五）"
        )

    if record.get("title"):
        record["title"] = normalize_string(record["title"])
    else:
        record["title"] = f"【{week_start.isoformat()} 至 {week_end.isoformat()}】云平台运行情况报告"

    incident_ids = [
        normalize_string(x).upper()
        for x in normalize_list(record.get("incident_ids"), "incident_ids")
        if normalize_string(x)
    ]

    record["availability_summary"] = calculate_availability_metrics(
        incidents_dir,
        week_start,
        week_end,
        incident_ids,
    )
    record["major_incidents"], record["this_week_incident_count"] = normalize_major_incidents(
        record.get("major_incidents"),
        incidents_dir,
        week_start,
        week_end,
        incident_ids,
    )
    record["historical_incidents"] = build_historical_incidents_from_annual(
        incidents_dir,
        week_start,
        incident_ids,
    )
    traffic = record.get("traffic_metrics") if isinstance(record.get("traffic_metrics"), dict) else {}
    record["traffic_metrics"] = {
        "qps_avg": normalize_string(traffic.get("qps_avg") or traffic.get("API 请求量（QPS）平均值") or traffic.get("api_qps_avg")),
        "qps_peak": normalize_string(traffic.get("qps_peak") or traffic.get("API 请求量（QPS）峰值") or traffic.get("api_qps_peak")),
        "api_success_rate": normalize_string(traffic.get("api_success_rate") or traffic.get("API 成功率")),
        "response_avg": normalize_string(traffic.get("response_avg") or traffic.get("平均响应时间")),
        "response_peak": normalize_string(traffic.get("response_peak") or traffic.get("平均响应时间峰值")),
        "p95_p99": normalize_string(traffic.get("p95_p99") or traffic.get("P95 / P99 响应时间")),
    }
    ops = record.get("ops_release") if isinstance(record.get("ops_release"), dict) else {}
    record["ops_release"] = {
        "release_count": normalize_string(ops.get("release_count") or ops.get("发布次数")),
        "release_success_rate": normalize_string(ops.get("release_success_rate") or ops.get("发布成功率")),
        "rollback_count": normalize_string(ops.get("rollback_count") or ops.get("回滚次数")),
    }
    release_count_num = extract_first_number(record["ops_release"]["release_count"])
    rollback_count_num = extract_first_number(record["ops_release"]["rollback_count"])
    if release_count_num and release_count_num > 0 and rollback_count_num is not None:
        cfr = rollback_count_num / release_count_num * 100
        if abs(cfr - round(cfr)) < 1e-6:
            record["ops_release"]["change_failure_rate"] = f"{int(round(cfr))}%"
        else:
            record["ops_release"]["change_failure_rate"] = f"{cfr:.2f}%"
    else:
        record["ops_release"]["change_failure_rate"] = "未填写"
    monitor = record.get("monitoring_security") if isinstance(record.get("monitoring_security"), dict) else {}
    record["monitoring_security"] = {
        "effective_alerts": normalize_string(monitor.get("effective_alerts") or monitor.get("监控告警数量（有效）")),
        "alert_handle_rate": normalize_string(monitor.get("alert_handle_rate") or monitor.get("监控告警处理率")),
        "cert_expiry": normalize_string(monitor.get("cert_expiry") or monitor.get("证书到期提醒")),
    }
    record["exec_summary"] = normalize_string(record.get("exec_summary"))
    record["highlights"] = normalize_text_list(record.get("highlights"), "highlights")
    record["key_risks"] = normalize_text_list(record.get("key_risks"), "key_risks")
    record["next_focus"] = normalize_text_list(record.get("next_focus"), "next_focus")
    record["decisions_needed"] = normalize_decisions(record.get("decisions_needed"))
    auto_reliability = infer_weekly_reliability_from_annual(
        incidents_dir,
        week_start,
        week_end,
        incident_ids,
    )
    record["reliability_metrics"] = normalize_reliability_metrics(
        record.get("reliability_metrics"),
        record["availability_summary"]["week"],
        auto_reliability,
    )
    fill_severity_counts_from_major(
        record["reliability_metrics"],
        record["major_incidents"],
        week_start,
        week_end,
    )

    record["week_start_date"] = week_start
    record["week_end_date"] = week_end
    record["year"] = week_start.year
    record["iso_week"] = week_start.isocalendar().week
    record["period_key"] = f"{week_start.isoformat()}~{week_end.isoformat()}"
    record["allow_partial_week"] = allow_partial_week
    return record


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        rows = [["未填写"] + ["-"] * (len(headers) - 1)]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(sanitize_table_cell(col) for col in row) + " |")
    return "\n".join(lines)


def render_bullets(items: list[str], empty_text: str) -> str:
    if not items:
        return f"- {empty_text}"
    return "\n".join(f"- {sanitize_table_cell(item)}" for item in items)


def build_summary_reasons(record: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    business = extract_first_number(record["availability_summary"]["week"]["business"])
    incidents = record["this_week_incident_count"]
    api_success = extract_first_number(record["traffic_metrics"]["api_success_rate"])

    if incidents > 0:
        reasons.append(f"本周发生故障 {incidents} 起")
    if business is not None and business < 99.99:
        reasons.append(f"平台业务可用率 {record['availability_summary']['week']['business']}")
    if api_success is not None and api_success < 99.9:
        reasons.append(f"API 成功率 {record['traffic_metrics']['api_success_rate']}")

    return reasons or ["关键运行指标在目标范围内"]


def build_auto_highlights(record: dict[str, Any]) -> list[str]:
    return [
        (
            "本周可用率：基础设施 {infra}，应用 {app}，业务 {business}。".format(
                infra=record["availability_summary"]["week"]["infra"],
                app=record["availability_summary"]["week"]["app"],
                business=record["availability_summary"]["week"]["business"],
            )
        ),
        f"故障与恢复：本周 {record['this_week_incident_count']} 起，MTTR {record['availability_summary']['week']['mttr']}。",
        (
            "交付质量：发布 {release} 次，成功率 {success}，回滚 {rollback} 次。".format(
                release=record["ops_release"]["release_count"] or "未填写",
                success=record["ops_release"]["release_success_rate"] or "未填写",
                rollback=record["ops_release"]["rollback_count"] or "未填写",
            )
        ),
    ]


def build_auto_risks(record: dict[str, Any]) -> list[str]:
    risks = list(record["key_risks"])

    cert_expiry = record["monitoring_security"]["cert_expiry"]
    has_manual_cert_risk = any("证书" in risk for risk in risks)
    if cert_expiry and cert_expiry not in {"未填写", "/"} and "大于15天" not in cert_expiry and not has_manual_cert_risk:
        risks.append(f"证书风险：{cert_expiry.rstrip('。.!')}。")

    api_success = extract_first_number(record["traffic_metrics"]["api_success_rate"])
    if api_success is not None and api_success < 99.9:
        risks.append(f"API 成功率偏低（{record['traffic_metrics']['api_success_rate']}），建议重点排查关键链路。")

    deduped: list[str] = []
    seen = set()
    for risk in risks:
        if risk not in seen:
            deduped.append(risk)
            seen.add(risk)
    return deduped[:6]


def sort_incident_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    def sort_key(row: dict[str, str]) -> tuple[int, int, str]:
        time_text = row.get("time", "")
        is_history = 1 if "历史" in time_text else 0
        return (is_history, severity_rank(row.get("severity", "")), time_text)

    return sorted(rows, key=sort_key)


def extract_max_percent(*values: str) -> float:
    max_value = 0.0
    for value in values:
        for match in re.findall(r"(\d+(?:\.\d+)?)\s*%", normalize_string(value)):
            try:
                max_value = max(max_value, float(match))
            except ValueError:
                continue
    return max_value


def build_resource_hotspots(cloud_resources: list[dict[str, str]]) -> list[list[str]]:
    scored: list[tuple[float, list[str]]] = []
    for row in cloud_resources:
        abnormal = any(keyword in row["status"] for keyword in ("故障", "异常", "降级", "中断"))
        max_percent = extract_max_percent(
            row["cpu"],
            row["memory"],
            row["resource_usage"],
            row["connection_usage"],
        )
        score = max_percent + (1000.0 if abnormal else 0.0)
        note = "状态异常，优先跟踪" if abnormal else ("资源水位偏高" if max_percent >= 80 else "常规观察")
        scored.append(
            (
                score,
                [
                    row["resource_type"],
                    row["status"],
                    row["cpu"] or "/",
                    row["memory"] or "/",
                    row["resource_usage"] or "/",
                    note,
                ],
            )
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    top_rows = [row for _, row in scored[:8]]
    return top_rows or [["未填写", "-", "-", "-", "-", "-"]]


def get_nested(mapping: Any, *keys: str) -> Any:
    current = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def metric_average(metric_block: Any) -> float | None:
    value = get_nested(metric_block, "summary", "point_value_avg")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def metric_average_mbps(metric_block: Any) -> float | None:
    value = get_nested(metric_block, "summary", "point_value_avg_mbps")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def format_number(value: float | None, suffix: str = "", digits: int = 2) -> str:
    if value is None:
        return "/"
    if abs(value - round(value)) < 1e-6:
        rendered = str(int(round(value)))
    else:
        rendered = f"{value:.{digits}f}"
    return f"{rendered}{suffix}"


def markdown_link(target: Path, base_path: Path) -> str:
    rel = os.path.relpath(target, base_path.parent)
    return f"[{target.name}]({rel})"


def collect_appendix_sources(data_root: Path, week_start: str, week_end: str) -> dict[str, list[Path]]:
    week_start_date = parse_date(week_start)
    week_end_date = parse_date(week_end)
    source_root = data_root

    def matching_files(subdir: str, prefix: str) -> list[Path]:
        path = source_root / subdir
        if not path.exists():
            return []
        pattern = f"{prefix}*.{week_start}.{week_end}.json"
        return sorted(path.glob(pattern))

    def snapshot_files_within_week(subdir: str, prefix: str) -> list[Path]:
        path = source_root / subdir
        if not path.exists():
            return []
        matched: list[Path] = []
        for file in sorted(path.glob(f"{prefix}*.json")):
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})(?=\.json$)", file.name)
            if not date_match:
                continue
            try:
                snapshot_date = parse_date(date_match.group(1))
            except ValueError:
                continue
            if week_start_date <= snapshot_date <= week_end_date:
                matched.append(file)
        return matched[-1:] if matched else []

    return {
        "ecs": matching_files("ecs", "ecs-metrics."),
        "rds": matching_files("rds", "rds-metrics."),
        "redis": matching_files("redis", "redis-metrics."),
        "mongodb": matching_files("mongodb", "mongodb-metrics."),
        "slb": snapshot_files_within_week("slb", "slb-metrics."),
        "cdn": matching_files("cdn", "cdn-usage."),
        "eip": snapshot_files_within_week("eip", "eip-load."),
    }


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def load_nginx_traffic_metrics(
    nginx_root: Path,
    week_start: date,
    week_end: date,
) -> dict[str, str]:
    if not nginx_root.exists():
        return {}

    pattern = f"nginx-traffic.{week_start.isoformat()}.{week_end.isoformat()}.snapshot-*.json"
    candidates = sorted(nginx_root.glob(pattern))
    if not candidates:
        return {}

    payload = load_json(candidates[-1])
    metrics = payload.get("traffic_metrics")
    if not isinstance(metrics, dict):
        return {}

    return {
        "qps_avg": format_decimal(normalize_float(metrics.get("qps_avg")), digits=2),
        "qps_peak": format_decimal(normalize_float(metrics.get("qps_peak")), digits=0),
        "api_success_rate": format_percent_from_number(normalize_float(metrics.get("api_success_rate"))),
        "response_avg": format_duration_average(normalize_float(metrics.get("response_avg_seconds"))),
        "response_peak": format_duration_seconds(normalize_float(metrics.get("response_peak_seconds"))),
        "p95_p99": build_p95_p99_text(
            normalize_float(metrics.get("response_p95_seconds")),
            normalize_float(metrics.get("response_p99_seconds")),
        ),
    }


def flatten_texts(value: Any) -> list[str]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(flatten_texts(item))
        return items
    if isinstance(value, dict):
        items: list[str] = []
        for item in value.values():
            items.extend(flatten_texts(item))
        return items
    return [normalize_string(value)]


def filter_report_highlights(value: Any) -> list[str]:
    filtered: list[str] = []
    for item in flatten_texts(value):
        text = normalize_string(item)
        if not text:
            continue
        if (
            "代理本周" in text
            or "快照代理" in text
            or "报告日快照" in text
            or "报告日代理" in text
            or "实时快照数据" in text
            or re.search(r"当天.*实时快照", text)
            or re.search(r"本次以\s+.*当天.*快照", text)
        ):
            continue
        filtered.append(text)
    return filtered


def dedupe_texts(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = normalize_string(item)
        if not text or text in seen:
            continue
        deduped.append(text)
        seen.add(text)
    return deduped


def render_guidance(items: list[str], empty_text: str) -> str:
    return "#### 建议与改进措施\n\n" + render_bullets(dedupe_texts(items)[:6], empty_text)


def render_component_block(
    title: str,
    source_files: list[Path],
    body_parts: list[str],
    report_path: Path,
) -> str:
    parts = [f"### {title}"]
    parts.extend(part for part in body_parts if part)
    return "\n\n".join(parts)


def render_ecs_appendix(files: list[Path], report_path: Path) -> str:
    if not files:
        return render_component_block("5.1 ECS", [], ["- 未找到与当前周报周期对齐的 ECS 监控快照。"], report_path)

    summary_payloads: list[tuple[Path, dict[str, Any]]] = []
    for path in files:
        payload = load_json(path)
        if isinstance(payload.get("items"), list):
            summary_payloads.append((path, payload))

    if summary_payloads:
        source_path, payload = summary_payloads[-1]
        rows: list[list[str]] = []
        observations: list[str] = []
        guidance: list[str] = []
        items = payload.get("items", [])
        running_count = 0
        stopped_count = 0
        for item in items:
            instance_name = normalize_string(item.get("instance_name") or item.get("instanceName")) or "-"
            instance_id = normalize_string(item.get("instance_id") or item.get("instanceId")) or "-"
            region_id = normalize_string(item.get("region_id") or item.get("regionId")) or "-"
            status_text = normalize_string(item.get("status"))
            if status_text.lower() == "running":
                running_count += 1
            elif status_text.lower() == "stopped":
                stopped_count += 1
            metrics = item.get("metrics", {})
            cpu_avg = normalize_float(get_nested(metrics, "cpu", "avg"))
            memory_avg = normalize_float(get_nested(metrics, "memory", "avg"))
            disk_avg = normalize_float(get_nested(metrics, "disk", "avg"))
            connections_avg = normalize_float(get_nested(metrics, "conn", "avg"))
            rows.append(
                [
                    f"{instance_name} / {instance_id}",
                    region_id,
                    normalize_string(item.get("status")) or "-",
                    format_number(cpu_avg, "%"),
                    format_number(memory_avg, "%"),
                    format_number(disk_avg, "%"),
                    format_number(connections_avg),
                ]
            )
            if cpu_avg is not None and cpu_avg >= 70:
                guidance.append(
                    f"注意：{instance_name} 的 CPU 均值约 {format_number(cpu_avg, '%')}，已进入高位区间，建议优先复核该实例的热点进程、计划任务和上下游请求放量情况。"
                )
            if memory_avg is not None and memory_avg >= 80:
                guidance.append(
                    f"注意：{instance_name} 的内存利用率约 {format_number(memory_avg, '%')}，需补充进程级内存画像并预留扩容余量。"
                )
            if disk_avg is not None and disk_avg >= 80:
                guidance.append(
                    f"改进：{instance_name} 的磁盘利用率约 {format_number(disk_avg, '%')}，建议尽快完成日志清理与容量评估。"
                )
            if connections_avg is not None and connections_avg >= 10000:
                guidance.append(
                    f"建议：{instance_name} 的连接数均值约 {format_number(connections_avg)}，属于高连接型入口，建议持续观察连接泄漏、队列积压与公网带宽峰值。"
                )

        total_count = payload.get("total_instances") or len(items)
        observations.append(f"本周期纳入 {total_count} 台 ECS，其中 Running {running_count} 台、Stopped {stopped_count} 台。")
        if stopped_count:
            observations.append(f"当前存在 {stopped_count} 台停机 ECS，建议结合业务用途确认是否为预期停机，避免遗漏历史闲置实例。")
        if items:
            hottest_cpu = max(items, key=lambda item: normalize_float(get_nested(item, 'metrics', 'cpu', 'avg')) or -1)
            hottest_conn = max(items, key=lambda item: normalize_float(get_nested(item, 'metrics', 'conn', 'avg')) or -1)
            hottest_cpu_value = normalize_float(get_nested(hottest_cpu, "metrics", "cpu", "avg"))
            hottest_conn_value = normalize_float(get_nested(hottest_conn, "metrics", "conn", "avg"))
            hottest_cpu_name = normalize_string(hottest_cpu.get("instance_name") or hottest_cpu.get("instanceName")) or "-"
            hottest_conn_name = normalize_string(hottest_conn.get("instance_name") or hottest_conn.get("instanceName")) or "-"
            if hottest_cpu_value is not None:
                observations.append(
                    f"CPU 压力最高的实例为 {hottest_cpu_name}，均值约 {format_number(hottest_cpu_value, '%')}。"
                )
            if hottest_conn_value is not None:
                observations.append(
                    f"连接数最高的实例为 {hottest_conn_name}，均值约 {format_number(hottest_conn_value)}。"
                )

        body_parts = [
            render_table(
                ["实例", "地域", "状态", "CPU 平均", "内存平均", "磁盘平均", "连接数平均"],
                rows,
            ),
            "#### 重点观察\n\n" + render_bullets(observations[:6], "本周期暂无额外 ECS 观察结论。"),
            render_guidance(guidance, "建议持续关注高连接入口、磁盘高水位实例和停机实例清单。"),
        ]
        return render_component_block("5.1 ECS", [source_path], body_parts, report_path)

    rows: list[list[str]] = []
    observations: list[str] = []
    guidance: list[str] = []
    for path in files:
        payload = load_json(path)
        instance = payload.get("instance", {})
        metrics = payload.get("metrics", {})
        supplementary = payload.get("supplementary_metrics", {})
        cpu_avg = metric_average(metrics.get("cpu_utilization_percent"))
        memory_avg = metric_average(metrics.get("memory_utilization_percent"))
        disk_avg = metric_average(metrics.get("disk_usage_percent"))
        connections_avg = metric_average(metrics.get("concurrent_connections"))
        load_1m_avg = metric_average(supplementary.get("load_1m"))
        public_out_avg = metric_average_mbps(supplementary.get("public_internet_out_rate_bps"))
        rows.append(
            [
                f"{instance.get('name', '-') } / {instance.get('id', '-')}",
                normalize_string(instance.get("region_name") or instance.get("region_id")) or "-",
                format_number(cpu_avg, "%"),
                format_number(memory_avg, "%"),
                format_number(disk_avg, "%"),
                format_number(connections_avg),
                format_number(load_1m_avg),
                format_number(public_out_avg, " Mbps"),
            ]
        )
        observations.append(
            f"{instance.get('name', '-') } 在统计周期内 CPU 平均 {format_number(cpu_avg, '%')}，内存平均 {format_number(memory_avg, '%')}，磁盘平均 {format_number(disk_avg, '%')}。"
        )
        if load_1m_avg is not None and instance.get("vcpu") and load_1m_avg > float(instance["vcpu"]):
            observations.append(
                f"{instance.get('name', '-') } 的 1 分钟平均负载约 {format_number(load_1m_avg)}，高于 {instance['vcpu']} vCPU 容量，需重点关注系统负载压力。"
            )
        if disk_avg is not None and disk_avg >= 80:
            observations.append(
                f"{instance.get('name', '-') } 的磁盘使用率平均约 {format_number(disk_avg, '%')}，已处于高水位区间。"
            )
        if public_out_avg is not None:
            observations.append(
                f"{instance.get('name', '-') } 的公网出带宽平均约 {format_number(public_out_avg, ' Mbps')}。"
            )
        if load_1m_avg is not None and instance.get("vcpu") and load_1m_avg > float(instance["vcpu"]):
            guidance.append(
                f"建议：{instance.get('name', '-') } 的平均 1 分钟负载已高于 {instance['vcpu']} vCPU 规格，优先排查 CPU 饱和、I/O 等待与高频定时任务，必要时评估升配或拆分后台任务。"
            )
        if cpu_avg is not None and cpu_avg >= 70:
            guidance.append(
                f"注意：{instance.get('name', '-') } 的 CPU 周均已接近高位，需结合峰值时段检查 Web 进程、数据库连接和批处理任务是否存在集中争抢。"
            )
        if memory_avg is not None and memory_avg >= 75:
            guidance.append(
                f"注意：{instance.get('name', '-') } 的内存利用率已进入高水位，建议补充进程级内存画像，并预留缓存回收或扩容空间。"
            )
        if disk_avg is not None and disk_avg >= 80:
            guidance.append(
                f"改进：{instance.get('name', '-') } 的系统盘使用率已达 {format_number(disk_avg, '%')}，建议本周完成日志、临时文件和历史备份清理，并同步准备磁盘扩容窗口。"
            )
        if (
            load_1m_avg is not None
            and instance.get("vcpu")
            and cpu_avg is not None
            and cpu_avg < 60
            and load_1m_avg > float(instance["vcpu"])
        ):
            guidance.append(
                f"注意：{instance.get('name', '-') } 存在“CPU 均值不高但负载偏高”的特征，更像是 I/O wait 或短时阻塞问题，建议补充 iowait、磁盘队列和进程状态监控。"
            )

    body_parts = [
        render_table(
            ["实例", "地域", "CPU 平均", "内存平均", "磁盘平均", "连接数平均", "1m 负载平均", "公网出带宽平均"],
            rows,
        ),
        "#### 重点观察\n\n" + render_bullets(observations[:6], "本周期暂无额外 ECS 观察结论。"),
        render_guidance(guidance, "建议持续关注主机负载、磁盘水位与进程级资源画像。"),
    ]
    return render_component_block("5.1 ECS", files, body_parts, report_path)


def render_rds_appendix(files: list[Path], report_path: Path) -> str:
    if not files:
        return render_component_block("5.2 RDS MySQL", [], ["- 未找到与当前周报周期对齐的 RDS MySQL 监控快照。"], report_path)

    payload = load_json(files[0])
    rows: list[list[str]] = []
    guidance: list[str] = []
    aggregate_risk = get_nested(payload, "database_risk_metrics", "aggregate") or {}
    aggregate_metrics = payload.get("aggregate_metrics") or {}
    aggregate_conn_usage = metric_average(aggregate_metrics.get("connection_usage_percent"))
    aggregate_slow_queries = metric_average(aggregate_risk.get("slow_queries_per_sec"))
    aggregate_slowlog_size = metric_average(aggregate_risk.get("slowlog_size_mb"))
    aggregate_row_lock_waits = metric_average(aggregate_risk.get("row_lock_waits_per_sec"))
    aggregate_row_lock_time = metric_average(aggregate_risk.get("row_lock_wait_time_avg_ms"))
    aggregate_tmp_disk_tables = metric_average(aggregate_risk.get("tmp_disk_tables_per_sec"))
    risk_by_instance_id = {
        normalize_string(item.get("id")): item.get("metrics", {})
        for item in get_nested(payload, "database_risk_metrics", "instances") or []
    }
    for item in payload.get("instances", []):
        instance = item.get("instance", {})
        metrics = item.get("metrics", {})
        db_risk_metrics = risk_by_instance_id.get(normalize_string(instance.get("id")), {})
        disk_avg = metric_average(metrics.get("disk_usage_percent"))
        conn_usage_avg = metric_average(metrics.get("connection_usage_percent"))
        row_lock_waits = metric_average(db_risk_metrics.get("row_lock_waits_per_sec"))
        row_lock_time = metric_average(db_risk_metrics.get("row_lock_wait_time_avg_ms"))
        rows.append(
            [
                f"{instance.get('name', '-') } / {instance.get('id', '-')}",
                normalize_string(instance.get("role")) or "-",
                format_number(metric_average(metrics.get("cpu_usage_percent")), "%"),
                format_number(metric_average(metrics.get("memory_usage_percent")), "%"),
                format_number(disk_avg, "%"),
                format_number(metric_average(metrics.get("total_session_count"))),
                format_number(metric_average(metrics.get("qps"))),
                format_number(metric_average(metrics.get("tps"))),
            ]
        )
        if disk_avg is not None and disk_avg >= 70:
            guidance.append(
                f"注意：{instance.get('name', '-') } 的磁盘利用率已接近高位，建议提前规划数据清理、归档或存储扩容，避免业务增长后触顶。"
            )
        if conn_usage_avg is not None and conn_usage_avg >= 70:
            guidance.append(
                f"建议：{instance.get('name', '-') } 的连接使用率偏高，需复核连接池上限、空闲连接回收和应用侧重试策略。"
            )
        if row_lock_waits is not None and row_lock_waits > 0.005:
            guidance.append(
                f"改进：{instance.get('name', '-') } 已出现可见的行锁等待，建议重点审查热点更新 SQL、索引命中率和长事务提交顺序。"
            )
        if row_lock_time is not None and row_lock_time >= 100:
            guidance.append(
                f"注意：{instance.get('name', '-') } 的平均行锁等待时长已达到 {format_number(row_lock_time, ' ms')}，需要结合慢 SQL 与事务时长一起排查。"
            )

    if aggregate_slow_queries is not None and aggregate_slow_queries > 0:
        guidance.append("建议：虽然慢查询速率整体较低，但仍建议按周复盘慢日志 Top SQL，避免慢日志空间持续累积。")
    if aggregate_slowlog_size is not None and aggregate_slowlog_size >= 200:
        guidance.append(
            f"改进：当前慢日志累计体量约 {format_number(aggregate_slowlog_size, ' MB')}，建议设置保留周期与清理策略，并沉淀慢 SQL 优化清单。"
        )
    if aggregate_row_lock_waits is not None and aggregate_row_lock_waits > 0.005:
        guidance.append("建议：本周已观察到持续性的 InnoDB 行锁等待，应优先收敛热点行更新、批量事务和锁竞争 SQL。")
    if aggregate_row_lock_time is not None and aggregate_row_lock_time >= 100:
        guidance.append("注意：行锁等待时延已达百毫秒级，若业务高峰继续放大，可能直接反映为接口 RT 抖动。")
    if aggregate_tmp_disk_tables is not None and aggregate_tmp_disk_tables >= 1:
        guidance.append("改进：磁盘临时表生成频率不低，建议针对 ORDER BY、GROUP BY 和大结果集查询补做索引与执行计划优化。")
    if aggregate_conn_usage is not None and aggregate_conn_usage < 20:
        guidance.append("注意：当前连接使用率仍有较大余量，短期不是瓶颈，但建议继续约束应用连接池，避免后续无感膨胀。")

    body_parts = [
        render_table(
            ["实例", "角色", "CPU 平均", "内存平均", "磁盘平均", "会话数平均", "QPS 平均", "TPS 平均"],
            rows,
        ),
        "#### 重点观察\n\n" + render_bullets(filter_report_highlights(payload.get("report_highlights"))[:6], "本周期暂无额外 RDS MySQL 观察结论。"),
        render_guidance(guidance, "建议持续跟踪慢日志、锁等待和临时表落盘情况。"),
    ]
    return render_component_block("5.2 RDS MySQL", files, body_parts, report_path)


def render_redis_appendix(files: list[Path], report_path: Path) -> str:
    if not files:
        return render_component_block("5.3 Redis", [], ["- 未找到与当前周报周期对齐的 Redis 监控快照。"], report_path)

    payload = load_json(files[0])
    rows: list[list[str]] = []
    guidance: list[str] = []
    for item in payload.get("instances", []):
        instance = item.get("instance", {})
        metrics = item.get("metrics", {})
        connected_clients = metric_average(metrics.get("connected_clients"))
        evicted_keys = metric_average(metrics.get("evicted_keys_per_sec"))
        avg_ttl = metric_average(metrics.get("avg_ttl_seconds"))
        rows.append(
            [
                f"{instance.get('name', '-') } / {instance.get('id', '-')}",
                format_number(metric_average(metrics.get("ops_per_sec"))),
                format_number(connected_clients),
                format_number(metric_average(metrics.get("used_memory_bytes")), " MB"),
                format_number(metric_average(metrics.get("total_keys"))),
                format_number(metric_average(metrics.get("expired_keys_per_sec")), "/s", 4),
                format_number(evicted_keys, "/s", 4),
            ]
        )
        if connected_clients is not None and connected_clients >= 1000:
            guidance.append(
                f"注意：{instance.get('name', '-') } 的平均连接数已超过 1000，建议复核应用连接池、长连接复用和无效客户端回收策略。"
            )
        if evicted_keys is not None and evicted_keys > 0:
            guidance.append(
                f"改进：{instance.get('name', '-') } 已出现 key 逐出，建议立即核查 `maxmemory`、热点 key 分布与淘汰策略是否匹配业务预期。"
            )
        if evicted_keys is not None and evicted_keys == 0:
            guidance.append(
                f"建议：{instance.get('name', '-') } 当前未出现逐出，短期内存压力可控，但仍应补充内存碎片率与命中率监控，避免只看已用内存。"
            )
        if avg_ttl is not None and avg_ttl >= 30 * 24 * 3600:
            guidance.append(
                f"注意：{instance.get('name', '-') } 的平均 TTL 已达到长期驻留水平，建议区分永久缓存与短期缓存，定期清理历史业务 key。"
            )

    notes = flatten_texts(payload.get("notes"))
    if any("mem_fragmentation_ratio" in note or "cache_hit_ratio" in note for note in notes):
        guidance.append("改进：当前 Redis 侧尚未拿到碎片率和缓存命中率样本，建议优先补齐这两类指标，避免容量判断失真。")

    body_parts = [
        render_table(
            ["实例", "OPS 平均", "连接数平均", "已用内存平均", "总键数平均", "过期速率平均", "逐出速率平均"],
            rows,
        ),
        "#### 重点观察\n\n" + render_bullets(filter_report_highlights(payload.get("report_highlights"))[:6], "本周期暂无额外 Redis 观察结论。"),
        render_guidance(guidance, "建议持续观察连接数、键数量和淘汰情况，并补齐碎片率与命中率。"),
    ]
    return render_component_block("5.3 Redis", files, body_parts, report_path)


def render_mongodb_appendix(files: list[Path], report_path: Path) -> str:
    if not files:
        return render_component_block("5.4 MongoDB", [], ["- 未找到与当前周报周期对齐的 MongoDB 监控快照。"], report_path)

    payload = load_json(files[0])
    rows: list[list[str]] = []
    guidance: list[str] = []
    for item in payload.get("instances", []):
        instance = item.get("instance", {})
        metrics = item.get("metrics", {})
        current_connections = metric_average(metrics.get("current_connections"))
        page_faults = metric_average(metrics.get("page_faults"))
        query_ops = metric_average(metrics.get("query_ops_per_sec"))
        update_ops = metric_average(metrics.get("update_ops_per_sec"))
        rows.append(
            [
                f"{instance.get('name', '-') } / {instance.get('id', '-')}",
                format_number(query_ops),
                format_number(update_ops),
                format_number(current_connections),
                format_number(metric_average(metrics.get("network_requests"))),
                format_number(page_faults),
            ]
        )
        if current_connections is not None and current_connections >= 80:
            guidance.append(
                f"注意：{instance.get('name', '-') } 的连接数长期维持在较高水平，建议检查连接池复用、空闲连接释放与驱动超时配置。"
            )
        if query_ops is not None and update_ops is not None and update_ops >= query_ops * 0.7:
            guidance.append(
                f"建议：{instance.get('name', '-') } 的写入强度接近读取强度，建议关注主从复制延迟、热点集合与更新索引命中情况。"
            )
        if page_faults is not None and page_faults > 0:
            guidance.append(
                f"改进：{instance.get('name', '-') } 已出现 page faults，需尽快核查工作集是否超出内存，以及磁盘读放大是否增加。"
            )
        if normalize_string(instance.get("role")) == "secondary":
            guidance.append(
                f"注意：当前采样实例 {instance.get('name', '-') } 角色为 secondary，本节更适合作为副本节点负载参考，关键写入瓶颈仍需结合 primary 侧指标复核。"
            )

    notes = flatten_texts(payload.get("notes"))
    if any("mongodb.mem.resident" in note or "mongodb.cursors.totalOpen" in note for note in notes):
        guidance.append("改进：当前 MongoDB 尚缺 resident memory 和 open cursors 样本，建议补齐后再做更稳妥的容量与查询游标评估。")

    body_parts = [
        render_table(
            ["实例", "Query 平均", "Update 平均", "当前连接平均", "网络请求平均", "Page Faults 平均"],
            rows,
        ),
        "#### 重点观察\n\n" + render_bullets(filter_report_highlights(payload.get("report_highlights"))[:6], "本周期暂无额外 MongoDB 观察结论。"),
        render_guidance(guidance, "建议继续关注连接数、读写比例与内存相关指标补齐情况。"),
    ]
    return render_component_block("5.4 MongoDB", files, body_parts, report_path)


def render_slb_appendix(files: list[Path], report_path: Path) -> str:
    if not files:
        return render_component_block("5.5 SLB", [], ["- 未找到 SLB 资源盘点快照。"], report_path)

    payload = load_json(files[0])
    classic = get_nested(payload, "families", "classic_slb") or {}
    nlb = get_nested(payload, "families", "nlb") or {}
    alb = get_nested(payload, "families", "alb") or {}
    guidance: list[str] = []
    family_rows = [
        ["经典型 SLB", normalize_string(classic.get("total_count")) or "/", normalize_string(classic.get("running_count")) or "/", normalize_string(get_nested(payload, "idle_risk", "classic_slb_idle_count")) or "/"],
        ["NLB", normalize_string(nlb.get("total_count")) or "/", normalize_string(nlb.get("running_count")) or "/", "/"],
        ["ALB", normalize_string(alb.get("total_count")) or "/", normalize_string(alb.get("status")) or "/", "/"],
    ]
    region_rows = [
        [
            normalize_string(item.get("region_id")) or "-",
            normalize_string(item.get("instance_count")) or "-",
            normalize_string(item.get("running_count")) or "-",
        ]
        for item in classic.get("regions", [])
    ]
    if normalize_string(classic.get("total_count")) and classic.get("total_count", 0) > 0:
        guidance.append("建议：当前负载均衡仍以经典型 SLB 为主，建议梳理是否有入口适合逐步迁移到 ALB/NLB，以便获得更细粒度的七层治理与弹性能力。")
    if get_nested(payload, "idle_risk", "classic_slb_idle_count") == 0:
        guidance.append("注意：本次未发现闲置 SLB，资源利用率整体健康，但仍建议按季度复核监听、后端服务器组和证书绑定是否与现网一致。")
    if normalize_string(alb.get("status")) == "not_returned_by_overview_api":
        guidance.append("改进：ALB 概览接口本次未返回实例计数，建议后续补一条独立盘点链路，避免 ALB 资源遗漏在周报视图之外。")
    if classic.get("total_count", 0) >= 1 and len(region_rows) > 1:
        guidance.append("注意：当前负载均衡已分布在多个地域，建议同步维护地域到业务的映射关系，避免故障排查时只关注单地域。")

    body_parts = [
        render_table(["负载均衡类型", "总数", "运行中", "闲置数"], family_rows),
        render_table(["地域", "实例数", "运行中"], region_rows),
        "#### 重点观察\n\n" + render_bullets(filter_report_highlights(payload.get("report_highlights"))[:6], "当前暂无额外 SLB 观察结论。"),
        render_guidance(guidance, "建议保持负载均衡资源盘点与监听配置核对的周期性动作。"),
    ]
    return render_component_block("5.5 SLB", files, body_parts, report_path)


def render_cdn_appendix(files: list[Path], report_path: Path) -> str:
    if not files:
        return render_component_block("5.6 CDN", [], ["- 未找到 CDN 资源包与带宽快照。"], report_path)

    payload = load_json(files[0])
    inventory = payload.get("domain_inventory", {})
    usage = payload.get("usage_overview", {})
    guidance: list[str] = []
    domain_rows = [[
        normalize_string(inventory.get("total_count")) or "/",
        normalize_string(inventory.get("online_count")) or "/",
        normalize_string(get_nested(usage, "recent_7d_peak_bandwidth", "value")) or "/",
        normalize_string(get_nested(usage, "recent_7d_peak_bandwidth", "observed_at")) or "/",
    ]]
    package_rows = [
        [
            normalize_string(item.get("package_type")) or "-",
            normalize_string(item.get("region_label")) or "-",
            normalize_string(item.get("package_total")) or "/",
            normalize_string(item.get("current_month_usage")) or "-",
            normalize_string(item.get("package_remaining")) or "/",
            normalize_string(item.get("package_remaining_ratio")) or "/",
            normalize_string(item.get("deductible_package_count")) or "-",
            {
                "resource_package": "资源包抵扣",
                "postpaid": "后付费",
            }.get(normalize_string(item.get("billing_mode")), normalize_string(item.get("billing_mode")) or "-"),
        ]
        for item in usage.get("package_usage_by_region", [])
    ]
    postpaid_regions = [
        normalize_string(item.get("region_label"))
        for item in usage.get("package_usage_by_region", [])
        if normalize_string(item.get("billing_mode")) == "postpaid"
    ]
    if postpaid_regions:
        guidance.append(
            f"注意：{ '、'.join(postpaid_regions) } 当前按后付费计费，建议结合实际访问量评估是否补购资源包，避免跨区流量费用波动。"
        )
    low_remaining_regions = [
        normalize_string(item.get("region_label"))
        for item in usage.get("package_usage_by_region", [])
        if (
            (remaining_ratio := extract_first_number(item.get("package_remaining_ratio"))) is not None
            and remaining_ratio <= 10.0
        )
    ]
    if low_remaining_regions:
        guidance.append(
            f"注意：{ '、'.join(low_remaining_regions) } 的 CDN 资源包剩余占比较低，建议提前核对补购计划或优化跨区流量策略。"
        )
    peak_bandwidth = get_nested(usage, "recent_7d_peak_bandwidth", "value")
    if isinstance(peak_bandwidth, (int, float)) and float(peak_bandwidth) >= 200:
        guidance.append("建议：近 7 天 CDN 带宽峰值已超过 200 Mbps，需同步核对源站带宽、回源限流和热点资源缓存策略。")
    if normalize_string(inventory.get("total_count")) == normalize_string(inventory.get("online_count")):
        guidance.append("注意：当前全部域名在线，说明可用性状态正常，但仍建议按月复核缓存规则、证书有效期和回源地址变更。")
    if any(
        normalize_string(item.get("package_type")).replace(" ", "") == "静态HTTPS请求数"
        and "500" in normalize_string(item.get("current_month_usage"))
        for item in usage.get("package_usage_by_region", [])
    ):
        guidance.append("改进：静态 HTTPS 请求量已接近或超过免费额度，建议评估请求包采购、缓存命中优化以及静态资源合并策略。")

    body_parts = [
        render_table(["域名总数", "在线域名", "近7天带宽峰值(Mbps)", "峰值时间"], domain_rows),
        render_table(["资源类型", "区域", "资源包总量", "当月用量", "剩余量", "剩余占比", "可抵扣资源包", "计费方式"], package_rows),
        "#### 重点观察\n\n" + render_bullets(filter_report_highlights(payload.get("report_highlights"))[:6], "当前暂无额外 CDN 观察结论。"),
        render_guidance(guidance, "建议继续跟踪资源包消耗、带宽峰值与回源策略。"),
    ]
    return render_component_block("5.6 CDN", files, body_parts, report_path)


def render_eip_appendix(files: list[Path], report_path: Path) -> str:
    if not files:
        return render_component_block("5.7 EIP", [], ["- 未找到 EIP 负载快照。"], report_path)

    payload = load_json(files[0])
    aggregate = payload.get("aggregate_metrics", {})
    guidance: list[str] = []
    summary_rows = [[
        normalize_string(aggregate.get("regional_total_count")) or "/",
        normalize_string(aggregate.get("regional_in_use_count")) or "/",
        normalize_string(aggregate.get("regional_idle_count")) or "/",
        normalize_string(aggregate.get("displayed_bandwidth_cap_total_mbps")) or "/",
        normalize_string(aggregate.get("shared_bandwidth_attached_count")) or "/",
    ]]
    instance_rows = [
        [
            f"{normalize_string(item.get('name')) or '-'} / {normalize_string(item.get('ip_address')) or '-'}",
            f"{normalize_string(item.get('bound_instance_type')) or '-'} / {normalize_string(item.get('bound_instance_id')) or '-'}",
            f"{normalize_string(item.get('bandwidth_mbps')) or '-'} Mbps",
            normalize_string(item.get("bandwidth_service")) or "-",
            normalize_string(item.get("status")) or "-",
        ]
        for item in payload.get("instances", [])
    ]
    if aggregate.get("regional_idle_count") == 0:
        guidance.append("建议：当前深圳地域 EIP 全部在用，资源侧没有明显浪费，但建议维护“EIP -> 业务入口 -> 负责人”映射，提升公网故障定位效率。")
    if aggregate.get("shared_bandwidth_attached_count", 0) >= 3:
        guidance.append("注意：多条公网入口共用共享带宽包，需重点关注高峰时段带宽争抢与单点套餐失效带来的连带影响。")
    binding_distribution = aggregate.get("binding_type_distribution") or {}
    if binding_distribution.get("slb_instance", 0) >= 2:
        guidance.append("改进：公网入口主要挂载在 ECS 与 SLB，建议分别梳理直连入口和负载均衡入口的容灾切换预案。")
    global_footprint = aggregate.get("global_resource_footprint") or {}
    if len(global_footprint) > 1:
        guidance.append("注意：当前还存在跨地域 EIP 资源，建议周报与盘点统一纳入口径，避免遗漏青岛等非主地域公网资产。")

    body_parts = [
        render_table(["地域总数", "在用数", "闲置数", "展示带宽总上限(Mbps)", "共享带宽挂载数"], summary_rows),
        render_table(["名称 / IP", "绑定对象", "带宽", "带宽服务", "状态"], instance_rows),
        "#### 重点观察\n\n" + render_bullets(filter_report_highlights(payload.get("report_highlights"))[:6], "当前暂无额外 EIP 观察结论。"),
        render_guidance(guidance, "建议持续跟踪公网入口归属、共享带宽包和跨地域资产分布。"),
    ]
    return render_component_block("5.7 EIP", files, body_parts, report_path)


def render_appendix_sections(record: dict[str, Any], data_root: Path, report_path: Path) -> str:
    sources = collect_appendix_sources(data_root, record["week_start"], record["week_end"])
    sections = [
        render_ecs_appendix(sources["ecs"], report_path),
        render_rds_appendix(sources["rds"], report_path),
        render_redis_appendix(sources["redis"], report_path),
        render_mongodb_appendix(sources["mongodb"], report_path),
        render_slb_appendix(sources["slb"], report_path),
        render_cdn_appendix(sources["cdn"], report_path),
        render_eip_appendix(sources["eip"], report_path),
    ]
    return "\n\n".join(sections)


def render_weekly_markdown(record: dict[str, Any], data_root: Path, report_path: Path) -> str:
    summary_reasons = build_summary_reasons(record)
    exec_summary = record["exec_summary"] or "；".join(summary_reasons) + "。"
    highlights = record["highlights"] or build_auto_highlights(record)
    risks = build_auto_risks(record)
    next_focus = record["next_focus"] or ["持续跟踪核心链路稳定性，确保关键资源无回归。", "推进高风险项闭环并在下周周报更新进展。"]

    incident_rows_sorted = sort_incident_rows(record["major_incidents"])
    major_rows = [
        [
            str(idx),
            row["time"],
            row.get("severity", "未标注"),
            row["description"],
            row["impact_scope"],
            row["recovery_time"],
            row["cause"],
        ]
        for idx, row in enumerate(incident_rows_sorted, 1)
    ]
    if not major_rows:
        major_rows = [["-", "-", "-", "本周无新增故障", "-", "-", "-"]]
    historical_rows = [
        [
            str(idx),
            row["time"],
            row.get("severity", "未标注"),
            row["description"],
            row["impact_scope"],
            row["recovery_time"],
            row["cause"],
        ]
        for idx, row in enumerate(record.get("historical_incidents", []), 1)
    ]

    incident_text = (
        "**结论：本周无新增故障。**"
        if record["this_week_incident_count"] == 0
        else f"**结论：本周发生故障 {record['this_week_incident_count']} 起。**"
    )

    core_availability_rows = [
        [
            "基础设施可用率",
            record["availability_summary"]["week"]["infra"],
            record["availability_summary"]["month"]["infra"],
            record["availability_summary"]["year"]["infra"],
        ],
        [
            "应用可用率",
            record["availability_summary"]["week"]["app"],
            record["availability_summary"]["month"]["app"],
            record["availability_summary"]["year"]["app"],
        ],
        [
            "平台业务可用率",
            record["availability_summary"]["week"]["business"],
            record["availability_summary"]["month"]["business"],
            record["availability_summary"]["year"]["business"],
        ],
    ]

    impact_rows = [
        ["故障总数", str(record["this_week_incident_count"]), "统计周期内发生的事故数量"],
        ["P0/P1/P2 故障数", "{}/{}/{}".format(
            record["reliability_metrics"]["p0_count"],
            record["reliability_metrics"]["p1_count"],
            record["reliability_metrics"]["p2_count"],
        ), "高严重度故障分布"],
        ["有效告警数", record["monitoring_security"]["effective_alerts"] or "未填写", "本周有效告警量"],
    ]

    reliability_rows = [
        ["平均检测时长（MTTD）", record["reliability_metrics"]["mttd"], "从故障发生到被检测的平均时长"],
        ["平均响应时长（MTTA）", record["reliability_metrics"]["mtta"], "从检测到首次响应的平均时长"],
        ["平均恢复时长（MTTR）", record["reliability_metrics"]["mttr"], "从开始修复到恢复的平均时长"],
        ["平均故障间隔时间（MTBF）", record["reliability_metrics"]["mtbf"], "故障之间的平均间隔"],
    ]

    traffic_rows = [
        ["API 请求量（QPS）", record["traffic_metrics"]["qps_avg"] or "未填写", record["traffic_metrics"]["qps_peak"] or "未填写"],
        ["API 成功率", record["traffic_metrics"]["api_success_rate"] or "未填写", "/"],
        ["平均响应时间", record["traffic_metrics"]["response_avg"] or "未填写", record["traffic_metrics"]["response_peak"] or "/"],
        ["P95 / P99 响应时间", record["traffic_metrics"]["p95_p99"] or "未填写", "/"],
    ]

    change_quality_rows = [
        ["发布次数", record["ops_release"]["release_count"] or "未填写", "生产变更总次数"],
        ["发布成功率", record["ops_release"]["release_success_rate"] or "未填写", "交付稳定性"],
        ["回滚次数", record["ops_release"]["rollback_count"] or "未填写", "失败变更回退次数"],
        ["变更失败率（CFR）", record["ops_release"]["change_failure_rate"], "回滚次数 / 发布次数"],
        ["证书到期提醒", record["monitoring_security"]["cert_expiry"] or "未填写", "到期风险预警"],
    ]

    decisions_rows = [
        [row["item"], row["impact"], row["suggestion"], row["owner"], row["due"]]
        for row in record["decisions_needed"]
    ]
    if not decisions_rows:
        decisions_rows = [["无", "-", "-", "-", "-"]]

    return f"""# {record["title"]}

{WEEKLY_TEMPLATE_MARKER}

> _{record["version_note"]}_

---

## 一、本周结论与业务影响

- 统计周期：{record["week_start"]} 至 {record["week_end"]}
- 执行摘要：{sanitize_table_cell(exec_summary)}

### 1.1 关键结论

{render_bullets(highlights, "本周暂无补充结论。")}

### 1.2 核心可用率（本周 / 本月 / 本年度）

{render_table(["指标", "本周", "本月", "本年度"], core_availability_rows)}

### 1.3 业务影响概览

{render_table(["指标", "本周", "说明"], impact_rows)}

---

## 二、可靠性与故障治理

### 2.1 本周故障明细

{incident_text}

{render_table(["序号", "时间", "等级", "故障描述", "影响范围", "恢复时间", "根因/详情"], major_rows)}

#### 历史故障回顾

{render_table(["序号", "时间", "等级", "故障描述", "影响范围", "恢复时间", "根因/详情"], historical_rows)}

### 2.2 可靠性效率指标

{render_table(["指标", "本周", "说明"], reliability_rows)}

### 2.3 风险与待决策

#### 风险与关注项

{render_bullets(risks, "本周未识别到需要上升汇报的新增风险。")}

#### 待决策事项

{render_table(["事项", "业务影响", "建议动作", "负责人", "计划完成时间"], decisions_rows)}

---

## 三、交付质量与变更风险

{render_table(["指标", "本周", "说明"], change_quality_rows)}

---

## 四、性能与容量表现

### 4.1 接口与流量

{render_table(["指标", "平均值", "峰值"], traffic_rows)}

### 4.2 下周重点

{render_bullets(next_focus, "下周重点待补充。")}

---

## 五、附录（按组件资源明细）

{render_appendix_sections(record, data_root, report_path)}

---
"""


def parse_weekly_index(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not path.exists():
        return rows
    pattern = re.compile(r"^\|(.+)\|$")
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        cells = [cell.strip() for cell in match.group(1).split("|")]
        if not cells:
            continue
        if cells[0] in {"周期", "-", "---"}:
            continue
        if all(set(cell) <= {"-"} for cell in cells):
            continue
        if len(cells) < 8:
            continue
        report_path = ""
        link_match = link_pattern.search(cells[7])
        if link_match:
            report_path = link_match.group(1)
        rows.append(
            {
                "period": cells[0],
                "infra": cells[1],
                "app": cells[2],
                "business": cells[3],
                "incident_count": cells[4],
                "mttr": cells[5],
                "note": cells[6],
                "report_path": report_path,
            }
        )
    return rows


def upsert_weekly_index(path: Path, row: dict[str, str]) -> list[dict[str, str]]:
    rows = parse_weekly_index(path)

    # Keep one row per weekly report file path so period corrections do not leave stale records.
    filtered_rows = [
        existing
        for existing in rows
        if existing["period"] != row["period"] and existing["report_path"] != row["report_path"]
    ]
    filtered_rows.append(row)

    def sort_key(item: dict[str, str]) -> date:
        start = item["period"].split("~")[0]
        try:
            return parse_date(start)
        except ValueError:
            return date.min

    filtered_rows.sort(key=sort_key, reverse=True)
    return filtered_rows


def render_weekly_index(rows: list[dict[str, str]]) -> str:
    header = (
        "# 云平台周报索引\n\n"
        "| 周期 | 基础设施可用率 | 应用可用率 | 平台业务可用率 | 故障数 | 平均恢复时间（MTTR） | 备注 | 报告 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
    )
    lines: list[str] = []
    for row in rows:
        lines.append(
            "| {period} | {infra} | {app} | {business} | {incident_count} | {mttr} | {note} | [查看报告]({report_path}) |".format(
                period=sanitize_table_cell(row["period"]),
                infra=sanitize_table_cell(row["infra"]),
                app=sanitize_table_cell(row["app"]),
                business=sanitize_table_cell(row["business"]),
                incident_count=sanitize_table_cell(row["incident_count"]),
                mttr=sanitize_table_cell(row["mttr"]),
                note=sanitize_table_cell(row["note"]),
                report_path=row["report_path"],
            )
        )
    if not lines:
        lines.append("| - | - | - | - | - | - | - | - |")
    return header + "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="生成云平台运行周报")
    parser.add_argument(
        "--input",
        help="可选的周报补充 JSON 文件路径；若提供，可补充发布、告警、接口指标和摘要说明等人工字段",
    )
    parser.add_argument("--week-start", help="统计开始日期（YYYY-MM-DD）")
    parser.add_argument("--week-end", help="统计结束日期（YYYY-MM-DD）")
    parser.add_argument(
        "--allow-partial-week",
        action="store_true",
        help="允许生成非标准 7 天窗口的阶段性快照",
    )
    parser.add_argument(
        "--reports-dir",
        default="reports/weekly",
        help="周报输出目录（默认: reports/weekly）",
    )
    parser.add_argument(
        "--incidents-dir",
        default="reports/incidents",
        help="事故报告目录（默认: reports/incidents）",
    )
    parser.add_argument(
        "--data-root",
        default="data/aliyun",
        help="组件指标数据根目录（默认: data/aliyun）",
    )
    parser.add_argument(
        "--nginx-root",
        default="data/nginx",
        help="Nginx 结构化指标目录（默认: data/nginx）",
    )
    args = parser.parse_args()

    if not args.input and (not args.week_start or not args.week_end):
        parser.error("未提供 --input 时，必须同时传入 --week-start 和 --week-end")

    input_path = Path(args.input) if args.input else None
    reports_dir = Path(args.reports_dir)
    incidents_dir = Path(args.incidents_dir)

    raw: dict[str, Any] = {}
    if input_path:
        with input_path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
    week_start_text = normalize_string(args.week_start) or normalize_string(pick_field(raw, "week_start"))
    week_end_text = normalize_string(args.week_end) or normalize_string(pick_field(raw, "week_end"))
    if week_start_text and week_end_text:
        nginx_metrics = load_nginx_traffic_metrics(
            Path(args.nginx_root),
            parse_date(week_start_text),
            parse_date(week_end_text),
        )
        if nginx_metrics:
            existing_traffic = raw.get("traffic_metrics") if isinstance(raw.get("traffic_metrics"), dict) else {}
            raw["traffic_metrics"] = merge_dict_prefer_existing(existing_traffic, nginx_metrics)
    record = normalize_payload(
        raw,
        incidents_dir,
        week_start_override=normalize_string(args.week_start),
        week_end_override=normalize_string(args.week_end),
        allow_partial_week_override=args.allow_partial_week,
    )

    weekly_year_dir = reports_dir / str(record["year"])
    weekly_year_dir.mkdir(parents=True, exist_ok=True)
    if record["allow_partial_week"]:
        weekly_report_path = weekly_year_dir / f"{record['week_start']}-to-{record['week_end']}-stage.md"
    else:
        weekly_report_path = weekly_year_dir / f"{record['year']}-W{record['iso_week']:02d}.md"
    data_root = Path(args.data_root)
    weekly_report_path.write_text(
        render_weekly_markdown(record, data_root, weekly_report_path),
        encoding="utf-8",
    )

    weekly_index_path = reports_dir / "index.md"
    if not record["allow_partial_week"]:
        index_row = {
            "period": record["period_key"],
            "infra": record["availability_summary"]["week"]["infra"],
            "app": record["availability_summary"]["week"]["app"],
            "business": record["availability_summary"]["week"]["business"],
            "incident_count": str(record["this_week_incident_count"]),
            "mttr": record["availability_summary"]["week"]["mttr"],
            "note": (
                "本周无故障发生"
                if record["this_week_incident_count"] == 0
                else f"本周故障 {record['this_week_incident_count']} 起"
            ),
            "report_path": f"./{record['year']}/{record['year']}-W{record['iso_week']:02d}.md",
        }
        index_rows = upsert_weekly_index(weekly_index_path, index_row)
        weekly_index_path.write_text(render_weekly_index(index_rows), encoding="utf-8")

    print(f"已生成周报: {weekly_report_path}")
    if record["allow_partial_week"]:
        print("本次为阶段性快照，未更新周报索引。")
    else:
        print(f"已更新索引: {weekly_index_path}")
    print(f"本周故障数: {record['this_week_incident_count']}")


if __name__ == "__main__":
    main()
