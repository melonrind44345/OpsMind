#!/usr/bin/env python3
"""Analyse coverage data and identify high-impact test gaps.

Prints a ranked list of modules by "ROI" — modules with many uncovered lines
that would most improve overall coverage if tested.

Usage:  python scripts/analyse_coverage.py [coverage.json|coverage.xml]
"""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ModuleGap:
    path: str
    statements: int
    covered: int
    missing: int
    coverage_pct: float
    # What fraction of total missing lines this module accounts for
    pct_of_total_missing: float = 0.0


def parse_coverage_json(path: str) -> list[ModuleGap]:
    with open(path) as f:
        data: dict[str, Any] = json.load(f)

    totals = data["totals"]
    total_missing = totals["missing_lines"]

    gaps: list[ModuleGap] = []
    for file_path, file_data in data.get("files", {}).items():
        summary = file_data["summary"]
        stmts = summary["num_statements"]
        miss = summary["missing_lines"]
        cov = summary["covered_lines"]
        pct = summary["percent_covered"]
        gaps.append(
            ModuleGap(
                path=file_path,
                statements=stmts,
                covered=cov,
                missing=miss,
                coverage_pct=pct,
                pct_of_total_missing=(miss / total_missing * 100) if total_missing > 0 else 0,
            )
        )

    return gaps


def parse_coverage_xml(path: str) -> list[ModuleGap]:
    tree = ET.parse(path)
    root = tree.getroot()

    total_missing_lines = 0
    raw_packages: list[dict[str, Any]] = []

    for pkg in root.findall(".//package"):
        for cls in pkg.findall("classes/class"):
            filename = cls.attrib.get("filename", cls.attrib.get("name", "unknown"))
            lines = cls.findall("lines/line")
            total_lines = len(lines)
            missing = sum(1 for ln in lines if ln.attrib.get("hits", "1") == "0")
            total_missing_lines += missing
            raw_packages.append({
                "filename": filename,
                "lines": total_lines,
                "missing": missing,
            })

    gaps: list[ModuleGap] = []
    for rp in raw_packages:
        stmts = rp["lines"]
        miss = rp["missing"]
        cov = stmts - miss
        pct = (cov / stmts * 100) if stmts > 0 else 100.0
        gaps.append(
            ModuleGap(
                path=rp["filename"],
                statements=stmts,
                covered=cov,
                missing=miss,
                coverage_pct=pct,
                pct_of_total_missing=(miss / total_missing_lines * 100) if total_missing_lines > 0 else 0,
            )
        )

    return gaps


def main() -> None:
    # Find coverage data
    json_path = Path("coverage.json")
    xml_path = Path("coverage.xml")

    if json_path.exists():
        gaps = parse_coverage_json(str(json_path))
    elif xml_path.exists():
        gaps = parse_coverage_xml(str(xml_path))
    else:
        print("ERROR: No coverage.json or coverage.xml found. Run tests with --cov first.")
        sys.exit(1)

    if not gaps:
        print("No coverage data found.")
        return

    # Sort by missing lines descending (highest ROI first)
    gaps.sort(key=lambda g: g.missing, reverse=True)

    total_stmts = sum(g.statements for g in gaps)
    total_cov = sum(g.covered for g in gaps)
    total_miss = sum(g.missing for g in gaps)
    overall_pct = (total_cov / total_stmts * 100) if total_stmts > 0 else 0

    print("=" * 80)
    print("  OpsMind Coverage Gap Analysis")
    print("=" * 80)
    print(f"  Overall: {overall_pct:.1f}% ({total_cov}/{total_stmts} statements)")
    print(f"  Missing: {total_miss} statements across {len(gaps)} modules")
    print()

    # Top-3 quick wins
    print("  🔴 Top-3 modules by uncovered lines (biggest wins):")
    print(f"  {'Rank':<6} {'Missing':<9} {'%ofTotal':<10} {'Module'}")
    print(f"  {'-'*6} {'-'*9} {'-'*10} {'-'*40}")
    for i, g in enumerate(gaps[:10], 1):
        bar = "█" * min(int(g.pct_of_total_missing / 2), 30)
        print(f"  {i:<6} {g.missing:<9} {g.pct_of_total_missing:<10.1f}% {g.path}  {bar}")
    print()

    # Modules with 0% coverage
    zero_cov = [g for g in gaps if g.coverage_pct == 0.0]
    if zero_cov:
        print(f"  ⚪ Modules with 0% coverage ({len(zero_cov)}):")
        for g in zero_cov:
            print(f"     - {g.path} ({g.statements} statements)")
        print()

    # Suggested test strategy
    print("  📋 Suggested test-writing priority:")
    print(f"  {'Priority':<10} {'Module'}")
    print(f"  {'-'*10} {'-'*40}")
    priority = 1
    covered_modules = {"schemas", "__init__"}  # Already well-tested
    for g in gaps:
        if g.coverage_pct == 100:
            continue
        # Skip modules that already have test files
        mod_name = Path(g.path).stem
        test_name = f"test_{mod_name}.py"
        if Path("tests/unit").exists() and any(
            (Path("tests") / d / test_name).exists()
            for d in ("unit", "integration")
        ):
            tag = " (needs expansion)"
        else:
            tag = " (new test file)"
        if g.missing >= 30:  # High-impact
            print(f"  {priority:<10} {g.path}{tag}")
            priority += 1
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
