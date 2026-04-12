#!/usr/bin/env python3
"""Validate generated weekly report template consistency."""

from __future__ import annotations

import argparse
from pathlib import Path


WEEKLY_TEMPLATE_MARKER = "<!-- TEMPLATE: WEEKLY_REPORT_V2 -->"
WEEKLY_HEADINGS = [
    "## 一、本周结论与业务影响",
    "### 1.1 关键结论",
    "### 1.2 核心可用率（本周 / 本月 / 本年度）",
    "### 1.3 业务影响概览",
    "## 二、可靠性与故障治理",
    "### 2.1 本周故障明细",
    "### 2.2 可靠性效率指标",
    "#### 风险与关注项",
    "#### 待决策事项",
    "## 三、交付质量与变更风险",
    "## 四、性能与容量表现",
    "### 4.1 接口与流量",
    "### 4.2 下周重点",
    "## 五、附录（按组件资源明细）",
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
    if WEEKLY_TEMPLATE_MARKER not in text:
        errors.append(f"缺少模板标识: {WEEKLY_TEMPLATE_MARKER}")

    missing = missing_or_out_of_order(text, WEEKLY_HEADINGS)
    if missing:
        errors.append("缺少或顺序不符合预期的章节: " + "；".join(missing))
    return errors


def collect_weekly_reports(reports_root: Path) -> list[Path]:
    weekly_root = reports_root / "weekly"
    if not weekly_root.exists():
        return []

    files: list[Path] = []
    for path in weekly_root.rglob("*.md"):
        if path.name == "index.md":
            continue
        files.append(path)
    return sorted(files)


def main() -> None:
    parser = argparse.ArgumentParser(description="校验已生成周报的模板一致性")
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="报告目录（默认: reports）",
    )
    parser.add_argument(
        "--scope",
        choices=["weekly"],
        default="weekly",
        help="校验范围（固定: weekly）",
    )
    args = parser.parse_args()

    reports_root = Path(args.reports_dir)
    weekly_files = collect_weekly_reports(reports_root)
    print(f"周报待校验: {len(weekly_files)}")

    failed = False
    for path in weekly_files:
        errors = validate_file(path)
        if errors:
            failed = True
            print(f"[FAIL] {path}")
            for err in errors:
                print(f"  - {err}")

    if failed:
        raise SystemExit(1)

    print("周报模板一致性校验通过")


if __name__ == "__main__":
    main()
