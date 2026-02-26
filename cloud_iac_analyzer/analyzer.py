"""
Compares deployed cloud resources against IaC declarations to produce a drift report.
"""

import json
from typing import Any, Dict, List, Optional, Tuple


class ResourceAnalyzer:
    """
    Matches each cloud resource to its IaC counterpart and diffs their properties.

    Matching tries 'id' first, then 'name'. The two fields use separate lookup dicts
    so a resource's name can't accidentally collide with a different resource's id.
    """

    def __init__(self, cloud_resources: List[Dict], iac_resources: List[Dict]):
        self.cloud_resources = cloud_resources
        self.iac_resources = iac_resources
        self.analysis_report: List[Dict] = []
        self.by_id, self.by_name = self._build_iac_lookup()

    def _build_iac_lookup(self) -> Tuple[Dict[str, Dict], Dict[str, Dict]]:
        """
        Index IaC resources by 'id' and 'name' in separate namespaces.

        Using separate dicts prevents a resource's 'name' value from clobbering
        a different resource's 'id' entry (and vice versa) in a shared namespace.
        Resources with neither field are indexed by position as a fallback.
        """
        by_id: Dict[str, Dict] = {}
        by_name: Dict[str, Dict] = {}

        for idx, resource in enumerate(self.iac_resources):
            indexed = False

            if 'id' in resource:
                key = resource['id']
                if key in by_id:
                    print(f"[WARNING] Duplicate IaC resource id '{key}' — later entry overwrites earlier one")
                by_id[key] = resource
                indexed = True

            if 'name' in resource:
                key = resource['name']
                if key in by_name:
                    print(f"[WARNING] Duplicate IaC resource name '{key}' — later entry overwrites earlier one")
                by_name[key] = resource
                indexed = True

            if not indexed:
                by_id[f"_index_{idx}"] = resource

        return by_id, by_name

    def _find_matching_iac_resource(self, cloud_resource: Dict) -> Optional[Dict]:
        """Try 'id' first, fall back to 'name'."""
        if 'id' in cloud_resource:
            match = self.by_id.get(cloud_resource['id'])
            if match is not None:
                return match

        if 'name' in cloud_resource:
            return self.by_name.get(cloud_resource['name'])

        return None

    def _compare_values(self, cloud_val: Any, iac_val: Any, path: str = "") -> List[Dict]:
        """
        Recursively diff two values and return changelog entries for every difference.

        Dicts are compared key-by-key (union of both keysets). Arrays are compared
        element-by-element by index — order matters. Keys or elements present on only
        one side are reported with None on the other.
        """
        changes = []

        if isinstance(cloud_val, dict) and isinstance(iac_val, dict):
            for key in cloud_val.keys() | iac_val.keys():
                child_path = f"{path}.{key}" if path else key
                if key not in cloud_val:
                    changes.append({"KeyName": child_path, "CloudValue": None, "IacValue": iac_val[key]})
                elif key not in iac_val:
                    changes.append({"KeyName": child_path, "CloudValue": cloud_val[key], "IacValue": None})
                else:
                    changes.extend(self._compare_values(cloud_val[key], iac_val[key], child_path))

        elif isinstance(cloud_val, list) and isinstance(iac_val, list):
            for i in range(max(len(cloud_val), len(iac_val))):
                child_path = f"{path}[{i}]"
                if i >= len(cloud_val):
                    changes.append({"KeyName": child_path, "CloudValue": None, "IacValue": iac_val[i]})
                elif i >= len(iac_val):
                    changes.append({"KeyName": child_path, "CloudValue": cloud_val[i], "IacValue": None})
                else:
                    changes.extend(self._compare_values(cloud_val[i], iac_val[i], child_path))

        else:
            if cloud_val != iac_val:
                changes.append({"KeyName": path, "CloudValue": cloud_val, "IacValue": iac_val})

        return changes

    def _compare_resources(self, cloud: Dict, iac: Dict) -> Tuple[str, List[Dict]]:
        changes = self._compare_values(cloud, iac)
        return ("Match", []) if not changes else ("Modified", changes)

    def analyze(self) -> List[Dict]:
        """Run the full analysis and return one report item per cloud resource."""
        self.analysis_report = []

        for cloud_resource in self.cloud_resources:
            item: Dict = {
                "CloudResourceItem": cloud_resource,
                "IacResourceItem": {},
                "State": "Missing",
                "ChangeLog": [],
            }

            iac_resource = self._find_matching_iac_resource(cloud_resource)
            if iac_resource is not None:
                item["IacResourceItem"] = iac_resource
                item["State"], item["ChangeLog"] = self._compare_resources(cloud_resource, iac_resource)

            self.analysis_report.append(item)

        return self.analysis_report


def load_json_file(file_path: str) -> List[Dict]:
    """Load a JSON file that must contain a top-level array."""
    try:
        with open(file_path, encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"Expected a JSON array in {file_path}, got {type(data).__name__}")
        return data
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in {file_path}: {e.msg}", e.doc, e.pos)


def save_report(report: List[Dict], output_path: str) -> None:
    """Write the report to a JSON file."""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to: {output_path}")
    except IOError as e:
        raise IOError(f"Failed to write report to {output_path}: {e}")


def generate_analysis_report(cloud_file: str, iac_file: str, output_file: str) -> List[Dict]:
    """Load both resource files, run the analysis, save the report, and return it."""
    cloud_resources = load_json_file(cloud_file)
    iac_resources = load_json_file(iac_file)

    report = ResourceAnalyzer(cloud_resources, iac_resources).analyze()
    save_report(report, output_file)

    matched = sum(1 for r in report if r["State"] == "Match")
    modified = sum(1 for r in report if r["State"] == "Modified")
    missing = sum(1 for r in report if r["State"] == "Missing")
    print(f"Analyzed {len(report)} resources — {matched} match, {modified} modified, {missing} missing")

    return report
