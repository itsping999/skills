#!/usr/bin/env python3
"""Validate generated incident report template consistency."""

from __future__ import annotations

import argparse
from pathlib import Path


INCIDENT_TEMPLATE_MARKER = "<!-- TEMPLATE: INCIDENT_REPORT_V2 -->"
INCIDENT_HEADINGS = [
    "## 1. 事故概览",
    "## 2. 影响评估",
    "## 3. 处置过程与时效",
    "### 3.1 触发与检测",
    "### 3.2 关键时效指标",
    "### 3.3 处置动作与恢复",
    "### 3.4 事件时间线",
    "## 4. 根因与机制分析",
    "### 4.1 促成因素",
    "### 4.2 3 Whys",
    "## 5. 改进计划与风险跟踪",
    "### 5.1 长期改进方向",
    "### 5.2 改进项清单",
    "### 5.3 沟通记录",
    "## 6. 复盘结论与参考",
    "### 6.1 做得好的地方",
    "### 6.2 待改进项",
    "### 6.3 运气因素 / 险些发生点",
    "### 6.4 经验总结",
    "### 6.5 参考资料",
]


def missing_or_out_of_order(text: str, headings: list[str]) -> list[str]:
    missing: list[str] = []
    cursor = -1
    for heading in headings:
        index = text.find(heading, cursor + 1)
        if index == -1:
            missing.append(heading)
            continue
        cursor = index
    return missing


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    if INCIDENT_TEMPLATE_MARKER not in text:
        errors.append(f"缺少模板标识: {INCIDENT_TEMPLATE_MARKER}")

    missing = missing_or_out_of_order(text, INCIDENT_HEADINGS)
    if missing:
        errors.append("缺少或顺序不符合预期的章节: " + "；".join(missing))
    return errors


def collect_incident_reports(reports_root: Path) -> list[Path]:
    incident_root = reports_root / "incidents"
    if not incident_root.exists():
        return []

    files: list[Path] = []
    for path in incident_root.rglob("*.md"):
        if path.parent.name == "annual":
            continue
        files.append(path)
    return sorted(files)


def main() -> None:
    parser = argparse.ArgumentParser(description="校验已生成事故报告的模板一致性")
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="报告目录（默认: reports）",
    )
    parser.add_argument(
        "--scope",
        choices=["incident"],
        default="incident",
        help="校验范围（固定: incident）",
    )
    args = parser.parse_args()

    reports_root = Path(args.reports_dir)
    incident_files = collect_incident_reports(reports_root)
    print(f"事故报告待校验: {len(incident_files)}")

    failed = False
    for path in incident_files:
        errors = validate_file(path)
        if errors:
            failed = True
            print(f"[FAIL] {path}")
            for err in errors:
                print(f"  - {err}")

    if failed:
        raise SystemExit(1)

    print("事故报告模板一致性校验通过")


if __name__ == "__main__":
    main()
