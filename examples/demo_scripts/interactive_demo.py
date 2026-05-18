#!/usr/bin/env python3
"""OpsMind Interactive Demo - showcases all CLI features step by step."""

import subprocess
import sys
import time


def run_step(step_num: int, title: str, command: str) -> None:
    """Run a demo step with header."""
    separator = "━" * 60
    print(f"\n{separator}")
    print(f"  Step {step_num}: {title}")
    print(separator)
    print(f"  $ {command}\n")

    result = subprocess.run(command, shell=True, capture_output=False, text=True)
    if result.returncode != 0:
        print(f"\n  ⚠ Command exited with code {result.returncode}")
    time.sleep(1)


def main() -> None:
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║         OpsMind Interactive Demo - v0.1.0               ║")
    print("║   Ansible-Driven Modernization Assessment Platform       ║")
    print("╚" + "═" * 58 + "╝")
    print("\nThis demo walks through OpsMind's core capabilities.")
    print("Press Ctrl+C at any time to exit.\n")
    print("Starting in 3 seconds...")
    time.sleep(2)

    steps = [
        (1, "System Validation", "opsmind validate"),
        (2, "Legacy System Discovery", "opsmind discover legacy-centos --method mock"),
        (3, "Modern System Discovery", "opsmind discover modern-ubuntu --method mock"),
        (4, "Containerization Assessment", "opsmind assess --report-format markdown"),
        (5, "Generate Docker Artifacts", "opsmind generate docker --output-dir opsmind_demo_artifacts"),
        (6, "Generate Migration Plan", "opsmind generate migration-plan --output-dir opsmind_demo_artifacts"),
        (7, "HTML Report Export", "opsmind report export --format html --output opsmind_demo_report.html"),
        (8, "JSON Report Export", "opsmind report export --format json --output opsmind_demo_report.json"),
    ]

    for step_num, title, command in steps:
        run_step(step_num, title, command)

    print("\n" + "═" * 60)
    print("  Demo Complete!")
    print("═" * 60)
    print("\nGenerated artifacts:")
    print("  📄 opsmind_demo_report.html")
    print("  📄 opsmind_demo_report.json")
    print("  📁 opsmind_demo_artifacts/")
    print("\nRun 'opsmind --help' for all commands.")
    print("Run 'opsmind pipeline <target>' for the full automated workflow.\n")


if __name__ == "__main__":
    main()
