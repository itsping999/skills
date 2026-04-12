#!/usr/bin/env python3
"""Generate incident postmortem markdown and yearly summary files."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


FIELD_ALIASES = {
    "incident_id": ["incident_id", "事故编号", "id"],
    "title": ["title", "标题", "事故标题"],
    "occurred_at": ["occurred_at", "发生时间", "开始时间"],
    "resolved_at": ["resolved_at", "恢复时间", "结束时间"],
    "severity": ["severity", "级别", "故障级别"],
    "system": ["system", "系统", "影响系统"],
    "region": ["region", "地区", "区域", "region_name"],
    "status": ["status", "状态"],
    "owner": ["owner", "负责人", "责任人"],
    "incident_commander": ["incident_commander", "事故指挥官", "值班负责人"],
    "responders": ["responders", "协同团队", "参与团队"],
    "summary": ["summary", "事故概述", "概述"],
    "trigger": ["trigger", "触发条件", "触发原因"],
    "detection_source": ["detection_source", "发现方式", "检测来源"],
    "detection_time": ["detection_time", "发现时间", "检测时间"],
    "first_response_at": ["first_response_at", "首次响应时间"],
    "repair_started_at": ["repair_started_at", "开始修复处理时间", "开始修复时间", "修复开始时间"],
    "mitigated_at": ["mitigated_at", "缓解时间", "止血时间"],
    "impact_scope": ["impact_scope", "影响范围"],
    "customer_impact": ["customer_impact", "客户影响"],
    "business_impact": ["business_impact", "业务影响"],
    "impact_sla": ["impact_sla", "SLA影响", "SLO影响"],
    "impact_users": ["impact_users", "影响用户数"],
    "impact_customers": ["impact_customers", "影响客户数"],
    "impact_revenue": ["impact_revenue", "直接经济影响"],
    "communication_internal": ["communication_internal", "内部通报"],
    "communication_external": ["communication_external", "外部通报", "客户通报"],
    "root_cause": ["root_cause", "根因分析", "根因"],
    "contributing_factors": ["contributing_factors", "促成因素"],
    "five_whys": ["five_whys", "三个为什么", "3 whys", "3 why", "五个为什么", "5 whys"],
    "actions_taken": ["actions_taken", "临时措施", "处置过程"],
    "preventive_actions": ["preventive_actions", "长期改进", "改进措施"],
    "action_items": ["action_items", "改进项清单"],
    "what_went_well": ["what_went_well", "做得好的地方"],
    "what_went_poorly": ["what_went_poorly", "待改进项"],
    "where_lucky": ["where_lucky", "运气因素", "险些发生点"],
    "lessons_learned": ["lessons_learned", "经验总结"],
    "recurrence_risk": ["recurrence_risk", "复发风险"],
    "followup_review_at": ["followup_review_at", "复盘复查时间"],
    "references": ["references", "参考资料", "关联链接"],
    "tags": ["tags", "标签"],
    "timeline": ["timeline", "时间线"],
}

REQUIRED_FIELDS = [
    "incident_id",
    "title",
    "occurred_at",
    "severity",
    "system",
    "region",
    "status",
    "owner",
    "summary",
]

LIST_FIELDS = [
    "tags",
    "responders",
    "contributing_factors",
    "five_whys",
    "what_went_well",
    "what_went_poorly",
    "where_lucky",
    "lessons_learned",
    "references",
    "timeline",
]

SEVERITY_DEFINITIONS = {
    "P0": "灾难级事故。核心业务全面不可用或存在重大安全/数据风险，需要立即全员响应。",
    "P1": "严重事故。核心链路部分不可用，影响大量用户或关键交易，需要最高优先级处理。",
    "P2": "高优先级事故。功能受损但存在可替代路径，影响中等范围用户，需当日修复。",
    "P3": "一般事故。局部功能异常或体验下降，影响可控，可按计划窗口修复。",
    "P4": "低优先级问题。轻微缺陷或告警噪音，对业务无明显影响，纳入常规优化。",
}

RECURRENCE_RISK_LABELS = {
    "LOW": "低",
    "MEDIUM": "中",
    "HIGH": "高",
}

DONE_STATUSES = {"done", "closed", "completed", "已完成", "完成", "关闭"}

INCIDENT_ID_PATTERN = re.compile(
    r"^INC-(?P<date>\d{8})-[A-Z0-9]+(?:-[A-Z0-9]+)+$"
)
URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)
REPAIR_START_EVENT_PATTERNS = (
    re.compile(r"开始.*修复"),
    re.compile(r"开始.*处理"),
    re.compile(r"定位.*开始.*修复"),
    re.compile(r"定位.*开始.*处理"),
    re.compile(r"实施.*修复"),
)
INCIDENT_TEMPLATE_MARKER = "<!-- TEMPLATE: INCIDENT_REPORT_V2 -->"


def pick_field(payload: dict[str, Any], field_name: str) -> Any:
    for alias in FIELD_ALIASES[field_name]:
        if alias in payload and payload[alias] not in (None, ""):
            return payload[alias]
    return None


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


def normalize_action_items(value: Any) -> list[dict[str, str]]:
    items = normalize_list(value, "action_items")
    normalized_items: list[dict[str, str]] = []
    for item in items:
        if isinstance(item, str):
            normalized_items.append(
                {
                    "item": item.strip(),
                    "owner": "",
                    "due_date": "",
                    "status": "待开始",
                    "priority": "",
                }
            )
            continue
        if not isinstance(item, dict):
            raise ValueError("改进项清单的每一项必须是对象或字符串")
        normalized_items.append(
            {
                "item": normalize_string(item.get("事项") or item.get("item")),
                "owner": normalize_string(item.get("负责人") or item.get("owner")),
                "due_date": normalize_string(
                    item.get("截止时间") or item.get("due_date")
                ),
                "status": normalize_string(item.get("状态") or item.get("status"))
                or "待开始",
                "priority": normalize_string(
                    item.get("优先级") or item.get("priority")
                ),
            }
        )
    return normalized_items


def count_open_action_items(action_items: list[dict[str, str]]) -> int:
    open_count = 0
    for item in action_items:
        status = item.get("status", "").strip().lower()
        if status not in DONE_STATUSES:
            open_count += 1
    return open_count


def get_duration_minutes(start_at: str, resolved_at: str) -> int | None:
    if not resolved_at:
        return None
    started = parse_datetime(start_at)
    resolved = parse_datetime(resolved_at)
    delta = resolved - started
    minutes = int(delta.total_seconds() // 60)
    return max(minutes, 0)


def get_optional_duration_minutes(start_at: str, end_at: str) -> int | None:
    if not start_at or not end_at:
        return None
    try:
        return get_duration_minutes(start_at, end_at)
    except ValueError:
        return None


def infer_repair_started_at_from_timeline(timeline: list[Any]) -> str:
    candidates: list[tuple[datetime, str]] = []
    for item in timeline:
        if not isinstance(item, dict):
            continue
        event = normalize_string(item.get("事件") or item.get("event"))
        event_time = normalize_string(
            item.get("时间") or item.get("time") or item.get("timestamp")
        )
        if not event or not event_time:
            continue
        if not any(pattern.search(event) for pattern in REPAIR_START_EVENT_PATTERNS):
            continue
        try:
            parsed = parse_datetime(event_time)
        except ValueError:
            continue
        candidates.append((parsed, event_time))

    if not candidates:
        return ""
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def format_duration(minutes: int | None) -> str:
    if minutes is None:
        return "未恢复"
    if minutes < 60:
        return f"{minutes} 分钟"
    hours = minutes // 60
    remain = minutes % 60
    if remain == 0:
        return f"{hours} 小时"
    return f"{hours} 小时 {remain} 分钟"


def normalize_payload(raw: dict[str, Any]) -> dict[str, Any]:
    normalized = {field: pick_field(raw, field) for field in FIELD_ALIASES}
    missing = [name for name in REQUIRED_FIELDS if not normalized.get(name)]
    if missing:
        raise ValueError(f"缺少必填字段: {', '.join(missing)}")

    normalized["incident_id"] = normalize_string(normalized["incident_id"]).upper()
    normalized["title"] = normalize_string(normalized["title"])
    normalized["occurred_at"] = normalize_string(normalized["occurred_at"])
    normalized["resolved_at"] = normalize_string(normalized.get("resolved_at"))
    normalized["severity"] = normalize_string(normalized["severity"]).upper()
    normalized["system"] = normalize_string(normalized["system"])
    normalized["region"] = normalize_string(normalized["region"])
    normalized["status"] = normalize_string(normalized["status"])
    normalized["owner"] = normalize_string(normalized["owner"])
    normalized["summary"] = normalize_string(normalized["summary"])
    normalized["incident_commander"] = normalize_string(
        normalized.get("incident_commander")
    )
    normalized["trigger"] = normalize_string(normalized.get("trigger"))
    normalized["detection_source"] = normalize_string(normalized.get("detection_source"))
    normalized["detection_time"] = normalize_string(normalized.get("detection_time"))
    normalized["first_response_at"] = normalize_string(
        normalized.get("first_response_at")
    )
    normalized["repair_started_at"] = normalize_string(
        normalized.get("repair_started_at")
    )
    normalized["mitigated_at"] = normalize_string(normalized.get("mitigated_at"))
    normalized["impact_scope"] = normalize_string(normalized.get("impact_scope"))
    normalized["customer_impact"] = normalize_string(normalized.get("customer_impact"))
    normalized["business_impact"] = normalize_string(normalized.get("business_impact"))
    normalized["impact_sla"] = normalize_string(normalized.get("impact_sla"))
    normalized["impact_users"] = normalize_string(normalized.get("impact_users"))
    normalized["impact_customers"] = normalize_string(normalized.get("impact_customers"))
    normalized["impact_revenue"] = normalize_string(normalized.get("impact_revenue"))
    normalized["communication_internal"] = normalize_string(
        normalized.get("communication_internal")
    )
    normalized["communication_external"] = normalize_string(
        normalized.get("communication_external")
    )
    normalized["root_cause"] = normalize_string(normalized.get("root_cause"))
    normalized["actions_taken"] = normalize_string(normalized.get("actions_taken"))
    normalized["preventive_actions"] = normalize_string(
        normalized.get("preventive_actions")
    )
    normalized["followup_review_at"] = normalize_string(
        normalized.get("followup_review_at")
    )

    recurrence_risk = normalize_string(normalized.get("recurrence_risk")).upper()
    if recurrence_risk and recurrence_risk not in RECURRENCE_RISK_LABELS:
        raise ValueError("复发风险仅支持: LOW, MEDIUM, HIGH")
    normalized["recurrence_risk"] = recurrence_risk

    for field in LIST_FIELDS:
        normalized[field] = normalize_list(normalized.get(field), field)
    if len(normalized["five_whys"]) > 3:
        normalized["five_whys"] = normalized["five_whys"][:3]
    normalized["action_items"] = normalize_action_items(normalized.get("action_items"))

    occurred = parse_datetime(normalized["occurred_at"])
    normalized["year"] = occurred.year
    if normalized["resolved_at"]:
        parse_datetime(normalized["resolved_at"])
    for field in (
        "detection_time",
        "first_response_at",
        "repair_started_at",
        "mitigated_at",
        "followup_review_at",
    ):
        if normalized[field]:
            parse_datetime(normalized[field])

    if normalized["severity"] not in SEVERITY_DEFINITIONS:
        supported = ", ".join(SEVERITY_DEFINITIONS.keys())
        raise ValueError(f"无效的事故等级: {normalized['severity']}，支持: {supported}")

    match = INCIDENT_ID_PATTERN.match(normalized["incident_id"])
    if not match:
        raise ValueError(
            "无效的事故编号格式: {incident_id}。要求: INC-YYYYMMDD-SYSTEM-ISSUE "
            "(使用大写字母/数字和连字符)".format(
                incident_id=normalized["incident_id"]
            )
        )
    incident_date = match.group("date")
    occurred_date = occurred.strftime("%Y%m%d")
    if incident_date != occurred_date:
        raise ValueError(
            "事故编号日期({incident_date})与发生时间({occurred_date})不一致".format(
                incident_date=incident_date,
                occurred_date=occurred_date,
            )
        )

    if not normalized["repair_started_at"]:
        normalized["repair_started_at"] = infer_repair_started_at_from_timeline(
            normalized["timeline"]
        )

    if normalized["repair_started_at"]:
        normalized["mttr_start_at"] = normalized["repair_started_at"]
        normalized["mttr_basis"] = "开始修复处理时间 -> 恢复时间"
    elif normalized["mitigated_at"]:
        normalized["mttr_start_at"] = normalized["mitigated_at"]
        normalized["mttr_basis"] = "缓解时间 -> 恢复时间（缺少开始修复处理时间时回退）"
    else:
        normalized["mttr_start_at"] = normalized["occurred_at"]
        normalized["mttr_basis"] = "发生时间 -> 恢复时间（缺少开始修复处理时间时回退）"

    normalized["duration_minutes"] = get_duration_minutes(
        normalized["mttr_start_at"],
        normalized["resolved_at"],
    )
    normalized["full_duration_minutes"] = get_optional_duration_minutes(
        normalized["occurred_at"],
        normalized["resolved_at"],
    )
    normalized["mttd_minutes"] = get_optional_duration_minutes(
        normalized["occurred_at"],
        normalized["detection_time"],
    )
    normalized["mtta_minutes"] = get_optional_duration_minutes(
        normalized["detection_time"],
        normalized["first_response_at"],
    )
    normalized["mitigation_minutes"] = get_optional_duration_minutes(
        normalized["first_response_at"],
        normalized["mitigated_at"],
    )
    normalized["open_action_items"] = count_open_action_items(
        normalized["action_items"]
    )
    return normalized


def format_bullets(items: list[Any], default_text: str = "未填写") -> str:
    if not items:
        return f"- {default_text}"
    lines = []
    for item in items:
        lines.append(f"- {normalize_string(item)}")
    return "\n".join(lines)


def format_timeline(timeline: list[Any]) -> str:
    if not timeline:
        return "- 暂无记录"

    lines = []
    for item in timeline:
        if isinstance(item, dict):
            event_time = normalize_string(
                item.get("时间") or item.get("time") or item.get("timestamp")
            ) or "未知时间"
            event = normalize_string(item.get("事件") or item.get("event")) or "无事件描述"
            actor = normalize_string(item.get("执行人") or item.get("actor"))
            if actor:
                lines.append(f"- {event_time}：{event}（执行：{actor}）")
            else:
                lines.append(f"- {event_time}：{event}")
        else:
            lines.append(f"- {normalize_string(item)}")
    return "\n".join(lines)


def format_action_items_table(action_items: list[dict[str, str]]) -> str:
    if not action_items:
        return "| 改进事项 | 负责人 | 截止时间 | 状态 | 优先级 |\n| --- | --- | --- | --- | --- |\n| 未填写 | - | - | - | - |"

    lines = [
        "| 改进事项 | 负责人 | 截止时间 | 状态 | 优先级 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in action_items:
        lines.append(
            "| {item} | {owner} | {due_date} | {status} | {priority} |".format(
                item=sanitize_table_cell(item.get("item") or "未填写"),
                owner=sanitize_table_cell(item.get("owner") or "-"),
                due_date=sanitize_table_cell(item.get("due_date") or "-"),
                status=sanitize_table_cell(item.get("status") or "-"),
                priority=sanitize_table_cell(item.get("priority") or "-"),
            )
        )
    return "\n".join(lines)


def format_references(references: list[Any]) -> str:
    if not references:
        return "- 未填写"

    lines = []
    for item in references:
        if isinstance(item, dict):
            name = normalize_string(item.get("名称") or item.get("name")) or "参考链接"
            url = normalize_string(item.get("链接") or item.get("url"))
            if url:
                lines.append(f"- [{name}]({url})")
            else:
                lines.append(f"- {name}")
        else:
            text = normalize_string(item)
            if URL_PATTERN.match(text):
                lines.append(f"- [链接]({text})")
            else:
                lines.append(f"- {text}")
    return "\n".join(lines)


def format_metric_duration(minutes: int | None) -> str:
    if minutes is None:
        return "未填写"
    return format_duration(minutes)


def render_incident_markdown(record: dict[str, Any]) -> str:
    tags = "、".join(record["tags"]) if record["tags"] else "无"
    responders = "、".join(record["responders"]) if record["responders"] else "未填写"
    recurrence_risk = (
        RECURRENCE_RISK_LABELS.get(record["recurrence_risk"], "未评估")
        if record["recurrence_risk"]
        else "未评估"
    )

    return f"""# 事故复盘报告：{record["title"]}

{INCIDENT_TEMPLATE_MARKER}

## 1. 事故概览

- 事故编号：{record["incident_id"]}
- 发生时间：{record["occurred_at"]}
- 恢复时间：{record["resolved_at"] or "未填写"}
- 故障级别：{record["severity"]}
- 等级定义：{SEVERITY_DEFINITIONS[record["severity"]]}
- 当前状态：{record["status"]}
- 事故指挥：{record["incident_commander"] or "未填写"}
- 负责人：{record["owner"]}
- 协同团队：{responders}
- 影响系统：{record["system"]}
- 影响地区：{record["region"]}
- 标签：{tags}
- 事件摘要：{record["summary"] or "未填写"}

## 2. 影响评估

- 用户影响范围：{record["impact_scope"] or "未填写"}
- 客户影响：{record["customer_impact"] or "未填写"}
- 业务影响：{record["business_impact"] or "未填写"}
- SLA/SLO 影响：{record["impact_sla"] or "未填写"}
- 影响用户数：{record["impact_users"] or "未填写"}
- 影响客户数：{record["impact_customers"] or "未填写"}
- 直接经济影响：{record["impact_revenue"] or "未填写"}

## 3. 处置过程与时效

### 3.1 触发与检测

{record["trigger"] or "未填写"}

### 3.2 关键时效指标

| 指标 | 口径 | 本次结果 |
| --- | --- | --- |
| 平均检测时长（MTTD） | 发生时间 -> 检测时间 | {format_metric_duration(record["mttd_minutes"])} |
| 平均响应时长（MTTA） | 检测时间 -> 首次响应时间 | {format_metric_duration(record["mtta_minutes"])} |
| 缓解时长 | 首次响应时间 -> 缓解完成时间 | {format_metric_duration(record["mitigation_minutes"])} |
| 恢复时长（MTTR） | {record["mttr_basis"]} | {format_duration(record["duration_minutes"])} |
| 全量恢复总时长 | 发生时间 -> 恢复时间 | {format_duration(record["full_duration_minutes"])} |

- 检测来源：{record["detection_source"] or "未填写"}
- 检测时间：{record["detection_time"] or "未填写"}
- 首次响应时间：{record["first_response_at"] or "未填写"}
- 开始修复处理时间：{record["mttr_start_at"] or "未填写"}
- 缓解完成时间：{record["mitigated_at"] or "未填写"}

### 3.3 处置动作与恢复

{record["actions_taken"] or "未填写"}

### 3.4 事件时间线

{format_timeline(record["timeline"])}

## 4. 根因与机制分析

{record["root_cause"] or "未填写"}

### 4.1 促成因素

{format_bullets(record["contributing_factors"])}

### 4.2 3 Whys

{format_bullets(record["five_whys"])}

## 5. 改进计划与风险跟踪

### 5.1 长期改进方向

{record["preventive_actions"] or "未填写"}

### 5.2 改进项清单

{format_action_items_table(record["action_items"])}

- 未完成改进项数量：{record["open_action_items"]}
- 复盘复查时间：{record["followup_review_at"] or "未填写"}
- 复发风险：{recurrence_risk}

### 5.3 沟通记录

- 内部通报：{record["communication_internal"] or "未填写"}
- 外部通报：{record["communication_external"] or "未填写"}

## 6. 复盘结论与参考

### 6.1 做得好的地方

{format_bullets(record["what_went_well"])}

### 6.2 待改进项

{format_bullets(record["what_went_poorly"])}

### 6.3 运气因素 / 险些发生点

{format_bullets(record["where_lucky"])}

### 6.4 经验总结

{format_bullets(record["lessons_learned"])}

### 6.5 参考资料

{format_references(record["references"])}
"""


def sanitize_table_cell(text: Any) -> str:
    value = normalize_string(text).replace("\n", " ")
    return value.replace("|", "\\|")


def summarize_user_impact(record: dict[str, Any]) -> str:
    if record["impact_users"]:
        return f"{record['impact_users']} 用户"
    if record["customer_impact"]:
        return record["customer_impact"][:40]
    if record["impact_scope"]:
        return record["impact_scope"][:40]
    return "未填写"


def parse_annual_markdown_rows(md_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not md_path.exists():
        return rows

    table_row_pattern = re.compile(r"^\|(.+)\|$")
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

    for line in md_path.read_text(encoding="utf-8").splitlines():
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

        if len(cells) == 8:
            rows.append(
                {
                    "incident_id": cells[0],
                    "occurred_at": cells[1],
                    "title": cells[2],
                    "severity": cells[3],
                    "system": cells[4],
                    "region": "",
                    "status": cells[5],
                    "owner": cells[6],
                    "mttr": "",
                    "user_impact": "",
                    "recurrence_risk": "",
                    "open_action_items": "",
                    "report_path": report_path,
                }
            )
        elif len(cells) >= 12:
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
                        "user_impact": cells[8],
                        "recurrence_risk": cells[9],
                        "open_action_items": cells[10],
                        "owner": cells[11],
                        "report_path": report_path,
                    }
                )
                continue
            rows.append(
                {
                    "incident_id": cells[0],
                    "occurred_at": cells[1],
                    "title": cells[2],
                    "severity": cells[3],
                    "system": cells[4],
                    "region": "",
                    "status": cells[5],
                    "mttr": cells[6],
                    "user_impact": cells[7],
                    "recurrence_risk": cells[8],
                    "open_action_items": cells[9],
                    "owner": cells[10],
                    "report_path": report_path,
                }
            )
    return rows


def upsert_annual_rows(annual_md_path: Path, row: dict[str, str]) -> list[dict[str, str]]:
    rows = parse_annual_markdown_rows(annual_md_path)

    replaced = False
    for idx, existing in enumerate(rows):
        if existing["incident_id"] == row["incident_id"]:
            rows[idx] = row
            replaced = True
            break
    if not replaced:
        rows.append(row)

    def sort_key(item: dict[str, str]):
        try:
            return parse_datetime(item["occurred_at"])
        except ValueError:
            return datetime.max

    rows.sort(key=sort_key)
    return rows


def render_annual_markdown(year: int, rows: list[dict[str, str]]) -> str:
    header = (
        f"# {year} 年故障汇总表\n\n"
        "| 事故编号 | 发生时间 | 标题 | 级别 | 系统 | 地区 | 状态 | 恢复时长 | 用户影响 | 复发风险 | 未完成改进项 | 负责人 | 报告 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    )

    body_lines = []
    for row in rows:
        report_rel = row["report_path"] or f"../{year}/{row['incident_id']}.md"
        body_lines.append(
            "| {incident_id} | {occurred_at} | {title} | {severity} | {system} | {region} | {status} | "
            "{mttr} | {user_impact} | {recurrence_risk} | {open_action_items} | {owner} | "
            "[查看报告]({report_rel}) |".format(
                incident_id=sanitize_table_cell(row.get("incident_id", "")),
                occurred_at=sanitize_table_cell(row.get("occurred_at", "")),
                title=sanitize_table_cell(row.get("title", "")),
                severity=sanitize_table_cell(row.get("severity", "")),
                system=sanitize_table_cell(row.get("system", "")),
                region=sanitize_table_cell(row.get("region", "") or "未填写"),
                status=sanitize_table_cell(row.get("status", "")),
                mttr=sanitize_table_cell(row.get("mttr", "") or "未填写"),
                user_impact=sanitize_table_cell(row.get("user_impact", "") or "未填写"),
                recurrence_risk=sanitize_table_cell(
                    row.get("recurrence_risk", "") or "未评估"
                ),
                open_action_items=sanitize_table_cell(
                    row.get("open_action_items", "") or "0"
                ),
                owner=sanitize_table_cell(row.get("owner", "")),
                report_rel=report_rel,
            )
        )
    if not body_lines:
        body_lines.append(
            "| - | - | - | - | - | - | - | - | - | - | - | - | - |"
        )
    return header + "\n".join(body_lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="生成事故报告和年度汇总")
    parser.add_argument("--input", required=True, help="事故输入 JSON 文件路径")
    parser.add_argument(
        "--reports-dir",
        default="reports/incidents",
        help="事故报告输出目录（默认: reports/incidents）",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    reports_dir = Path(args.reports_dir)

    with input_path.open("r", encoding="utf-8") as file:
        raw_data = json.load(file)
    record = normalize_payload(raw_data)

    year_dir = reports_dir / str(record["year"])
    annual_dir = reports_dir / "annual"
    incident_report_path = year_dir / f"{record['incident_id']}.md"
    annual_md_path = annual_dir / f"{record['year']}.md"

    year_dir.mkdir(parents=True, exist_ok=True)
    annual_dir.mkdir(parents=True, exist_ok=True)

    incident_report_path.write_text(
        render_incident_markdown(record),
        encoding="utf-8",
    )

    annual_row = {
        "incident_id": record["incident_id"],
        "occurred_at": record["occurred_at"],
        "title": record["title"],
        "severity": record["severity"],
        "system": record["system"],
        "region": record["region"],
        "status": record["status"],
        "mttr": format_duration(record["duration_minutes"]),
        "user_impact": summarize_user_impact(record),
        "recurrence_risk": RECURRENCE_RISK_LABELS.get(
            record["recurrence_risk"], "未评估"
        ),
        "open_action_items": str(record["open_action_items"]),
        "owner": record["owner"],
        "report_path": f"../{record['year']}/{record['incident_id']}.md",
    }
    all_rows = upsert_annual_rows(annual_md_path, annual_row)
    annual_md_path.write_text(
        render_annual_markdown(record["year"], all_rows),
        encoding="utf-8",
    )

    print(f"已生成事故报告: {incident_report_path}")
    print(f"已更新年度汇总: {annual_md_path}")


if __name__ == "__main__":
    main()
