#!/usr/bin/env python3
"""
Runs the analyzer against the example files and prints a summary.
"""

import json
import sys
from pathlib import Path

# Ensure the package is importable when run directly from the project root
sys.path.insert(0, str(Path(__file__).parent))

from cloud_iac_analyzer import ResourceAnalyzer  # noqa: E402


def _print_results(report: list) -> None:
    """Print modified and missing resources to stdout."""
    for item in report:
        if item["State"] == "Modified":
            cloud = item["CloudResourceItem"]
            name = cloud.get("name") or cloud.get("id", "?")
            print(f"  {name} — {len(item['ChangeLog'])} change(s):")
            for change in item["ChangeLog"]:
                print(f"    {change['KeyName']}: {change['CloudValue']!r} → {change['IacValue']!r}")

    for item in report:
        if item["State"] == "Missing":
            cloud = item["CloudResourceItem"]
            name = cloud.get("name") or cloud.get("id", "?")
            resource_type = cloud.get("type", "")
            print(f"  Missing: {name} ({resource_type})")


def main() -> int:
    print("Loading example resources...")

    try:
        with open('examples/cloud_resources.json', encoding='utf-8') as f:
            cloud_resources = json.load(f)
        with open('examples/iac_resources.json', encoding='utf-8') as f:
            iac_resources = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Failed to load resources: {e}")
        return 1

    print(f"  cloud: {len(cloud_resources)} resources")
    print(f"  iac:   {len(iac_resources)} resources")

    report = ResourceAnalyzer(cloud_resources, iac_resources).analyze()

    matched = sum(1 for r in report if r["State"] == "Match")
    modified = sum(1 for r in report if r["State"] == "Modified")
    missing = sum(1 for r in report if r["State"] == "Missing")

    print(f"\nResults: {matched} match, {modified} modified, {missing} missing\n")
    _print_results(report)

    output_file = 'output/test_report.json'
    Path(output_file).parent.mkdir(exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print(f"\nFull report written to {output_file}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
