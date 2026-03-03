"""
Comprehensive pytest test suite for cloud_iac_analyzer.

Coverage targets:
  - ResourceAnalyzer: matching by id/name, comparison, report generation
  - Standalone helpers: load_json_file, save_report, generate_analysis_report
  - CLI: validate_input_file, validate_output_path, main() exit codes
  - Edge cases: empty inputs, duplicate ids/names, resources without id/name
  - Type mismatches, deeply nested paths, array bracket notation
  - Report format: all required fields, correct state values, ChangeLog rules

Run with:
    pytest tests/ -v --cov=cloud_iac_analyzer
"""

import argparse
import json
import pytest
from unittest.mock import patch

from cloud_iac_analyzer.analyzer import (
    ResourceAnalyzer,
    load_json_file,
    save_report,
    generate_analysis_report,
)
from cloud_iac_analyzer.cli import validate_input_file, validate_output_path, main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_analyzer(cloud, iac):
    return ResourceAnalyzer(cloud, iac)


def find_item(report, resource_id=None, resource_name=None):
    """Return the first report item whose CloudResourceItem matches id or name."""
    for item in report:
        cloud = item["CloudResourceItem"]
        if resource_id is not None and cloud.get("id") == resource_id:
            return item
        if resource_name is not None and cloud.get("name") == resource_name:
            return item
    return None


def change_keys(report_item):
    """Return the set of KeyName values from a report item's ChangeLog."""
    return {c["KeyName"] for c in report_item["ChangeLog"]}


def find_change(report_item, key_name):
    """Return the ChangeLog entry matching key_name, or None."""
    return next((c for c in report_item["ChangeLog"] if c["KeyName"] == key_name), None)


# ---------------------------------------------------------------------------
# 1.  Resource matching
# ---------------------------------------------------------------------------

class TestResourceMatching:

    def test_match_by_id(self):
        cloud = [{"id": "res-001", "name": "foo", "size": "small"}]
        iac   = [{"id": "res-001", "name": "foo", "size": "small"}]
        report = make_analyzer(cloud, iac).analyze()
        assert report[0]["State"] == "Match"

    def test_match_by_name_when_no_id(self):
        """Resources with no 'id' field match on 'name'."""
        cloud = [{"name": "my-bucket", "region": "us-east-1"}]
        iac   = [{"name": "my-bucket", "region": "us-east-1"}]
        report = make_analyzer(cloud, iac).analyze()
        assert report[0]["State"] == "Match"

    def test_id_takes_priority_over_name(self):
        """Matching is done by id first; name collision with a different id does not match."""
        cloud = [{"id": "res-001", "name": "cloud-name", "size": "small"}]
        iac   = [{"id": "res-001", "name": "iac-name",   "size": "small"}]
        report = make_analyzer(cloud, iac).analyze()
        # id matched → resource found; only 'name' field should differ
        assert report[0]["State"] == "Modified"
        assert any(c["KeyName"] == "name" for c in report[0]["ChangeLog"])

    def test_missing_resource_when_no_id_or_name_match(self):
        cloud = [{"id": "res-999", "name": "ghost"}]
        iac   = [{"id": "res-001", "name": "existing"}]
        report = make_analyzer(cloud, iac).analyze()
        assert report[0]["State"] == "Missing"

    def test_id_namespace_does_not_bleed_into_name_namespace(self):
        """
        A cloud resource that has 'id': 'X' must NOT match an IaC resource
        that only has 'name': 'X' — separate lookup dicts prevent this.
        """
        cloud = [{"id": "X"}]
        iac   = [{"name": "X"}]          # IaC has name='X', no id
        report = make_analyzer(cloud, iac).analyze()
        # cloud looks up by id; 'X' is not in by_id → Missing
        assert report[0]["State"] == "Missing"

    def test_name_fallback_used_when_cloud_has_no_id(self):
        """If the cloud resource has no 'id', fall back to name matching."""
        cloud = [{"name": "shared-sg", "port": 22}]
        iac   = [{"name": "shared-sg", "port": 22}]
        report = make_analyzer(cloud, iac).analyze()
        # cloud has no id → name lookup → identical resources → Match
        assert report[0]["State"] == "Match"

    def test_one_resource_per_cloud_entry(self):
        """Report must have exactly one entry per cloud resource."""
        cloud = [{"id": "r1"}, {"id": "r2"}, {"id": "r3"}]
        iac   = [{"id": "r1"}, {"id": "r2"}]
        report = make_analyzer(cloud, iac).analyze()
        assert len(report) == 3


# ---------------------------------------------------------------------------
# 2.  Simple and nested property comparison
# ---------------------------------------------------------------------------

class TestPropertyComparison:

    def test_identical_resources_produce_match_and_empty_changelog(self):
        resource = {"id": "r1", "name": "vpc", "cidr": "10.0.0.0/8"}
        report = make_analyzer([resource], [resource.copy()]).analyze()
        assert report[0]["State"] == "Match"
        assert report[0]["ChangeLog"] == []

    def test_single_primitive_property_diff(self):
        cloud = [{"id": "r1", "version": "1.0"}]
        iac   = [{"id": "r1", "version": "2.0"}]
        report = make_analyzer(cloud, iac).analyze()
        assert report[0]["State"] == "Modified"
        changelog = report[0]["ChangeLog"]
        assert len(changelog) == 1
        assert changelog[0] == {
            "KeyName": "version",
            "CloudValue": "1.0",
            "IacValue": "2.0",
        }

    def test_nested_object_diff_uses_dot_notation(self):
        cloud = [{"id": "r1", "tags": {"Env": "prod",    "Owner": "Alice"}}]
        iac   = [{"id": "r1", "tags": {"Env": "staging", "Owner": "Alice"}}]
        report = make_analyzer(cloud, iac).analyze()
        assert report[0]["State"] == "Modified"
        assert "tags.Env" in change_keys(report[0])

    def test_deeply_nested_diff_three_levels(self):
        """encryption.kms.key_id — three levels of nesting."""
        cloud = [{"id": "r1", "encryption": {"kms": {"key_id": "old-key", "region": "us-east-1"}}}]
        iac   = [{"id": "r1", "encryption": {"kms": {"key_id": "new-key", "region": "us-east-1"}}}]
        report = make_analyzer(cloud, iac).analyze()
        assert "encryption.kms.key_id" in change_keys(report[0])
        assert "encryption.kms.region" not in change_keys(report[0])

    def test_cloud_only_key_has_none_iac_value(self):
        """Key present in cloud but absent in IaC → IacValue must be None."""
        cloud = [{"id": "r1", "extra_tag": "value"}]
        iac   = [{"id": "r1"}]
        report = make_analyzer(cloud, iac).analyze()
        entry = find_change(report[0], "extra_tag")
        assert entry is not None
        assert entry["CloudValue"] == "value"
        assert entry["IacValue"] is None

    def test_iac_only_key_has_none_cloud_value(self):
        """Key present in IaC but absent in cloud → CloudValue must be None."""
        cloud = [{"id": "r1"}]
        iac   = [{"id": "r1", "managed_by": "terraform"}]
        report = make_analyzer(cloud, iac).analyze()
        entry = find_change(report[0], "managed_by")
        assert entry is not None
        assert entry["CloudValue"] is None
        assert entry["IacValue"] == "terraform"

    def test_boolean_vs_string_type_mismatch_detected(self):
        """'true' (str) vs True (bool) must be reported as a change."""
        cloud = [{"id": "r1", "enabled": "true"}]
        iac   = [{"id": "r1", "enabled": True}]
        report = make_analyzer(cloud, iac).analyze()
        assert report[0]["State"] == "Modified"
        entry = find_change(report[0], "enabled")
        assert entry["CloudValue"] == "true"
        assert entry["IacValue"] is True

    def test_integer_vs_string_type_mismatch_detected(self):
        """80 (int) vs '80' (str) must be reported as a change."""
        cloud = [{"id": "r1", "port": 80}]
        iac   = [{"id": "r1", "port": "80"}]
        report = make_analyzer(cloud, iac).analyze()
        assert report[0]["State"] == "Modified"
        entry = find_change(report[0], "port")
        assert entry["CloudValue"] == 80
        assert entry["IacValue"] == "80"

    def test_multiple_diffs_all_reported(self):
        cloud = [{"id": "r1", "version": "1.0", "class": "small", "zone": "us-east-1a"}]
        iac   = [{"id": "r1", "version": "2.0", "class": "xlarge", "zone": "us-east-1a"}]
        report = make_analyzer(cloud, iac).analyze()
        keys = change_keys(report[0])
        assert "version" in keys
        assert "class" in keys
        assert "zone" not in keys


# ---------------------------------------------------------------------------
# 3.  Array comparison
# ---------------------------------------------------------------------------

class TestArrayComparison:

    def test_array_bracket_notation_for_missing_element(self):
        """security_groups[0].ingress_rules[1] — bracket notation in path."""
        cloud = [{"id": "r1", "security_groups": [
            {"ingress_rules": [{"port": 80}]}
        ]}]
        iac = [{"id": "r1", "security_groups": [
            {"ingress_rules": [{"port": 80}, {"port": 443}]}
        ]}]
        report = make_analyzer(cloud, iac).analyze()
        assert report[0]["State"] == "Modified"
        assert "security_groups[0].ingress_rules[1]" in change_keys(report[0])

    def test_array_element_value_diff_includes_index(self):
        cloud = [{"id": "r1", "ports": [80, 443, 8080]}]
        iac   = [{"id": "r1", "ports": [80, 444, 8080]}]
        report = make_analyzer(cloud, iac).analyze()
        assert "ports[1]" in change_keys(report[0])
        assert "ports[0]" not in change_keys(report[0])
        assert "ports[2]" not in change_keys(report[0])

    def test_cloud_array_longer_than_iac_reports_none_iac_value(self):
        """Extra cloud elements appear with IacValue: None."""
        cloud = [{"id": "r1", "ports": [80, 443, 8080]}]
        iac   = [{"id": "r1", "ports": [80, 443]}]
        report = make_analyzer(cloud, iac).analyze()
        entry = find_change(report[0], "ports[2]")
        assert entry is not None
        assert entry["CloudValue"] == 8080
        assert entry["IacValue"] is None

    def test_iac_array_longer_than_cloud_reports_none_cloud_value(self):
        """Extra IaC elements appear with CloudValue: None."""
        cloud = [{"id": "r1", "ports": [80]}]
        iac   = [{"id": "r1", "ports": [80, 443]}]
        report = make_analyzer(cloud, iac).analyze()
        entry = find_change(report[0], "ports[1]")
        assert entry is not None
        assert entry["CloudValue"] is None
        assert entry["IacValue"] == 443

    def test_nested_array_bracket_path_multi_level(self):
        """subnets[1].cidr and subnets[1].tags.Tier — mixed bracket and dot."""
        cloud = [{"id": "r1", "subnets": [
            {"cidr": "10.0.1.0/24"},
            {"cidr": "10.0.2.0/24", "tags": {"Type": "Private"}},
        ]}]
        iac = [{"id": "r1", "subnets": [
            {"cidr": "10.0.1.0/24"},
            {"cidr": "10.0.3.0/24", "tags": {"Type": "Private", "Tier": "DB"}},
        ]}]
        report = make_analyzer(cloud, iac).analyze()
        keys = change_keys(report[0])
        assert "subnets[1].cidr" in keys
        assert "subnets[1].tags.Tier" in keys
        assert "subnets[0].cidr" not in keys

    def test_identical_arrays_produce_no_changes(self):
        cloud = [{"id": "r1", "cidrs": ["10.0.0.0/8", "192.168.0.0/16"]}]
        iac   = [{"id": "r1", "cidrs": ["10.0.0.0/8", "192.168.0.0/16"]}]
        report = make_analyzer(cloud, iac).analyze()
        assert report[0]["State"] == "Match"
        assert report[0]["ChangeLog"] == []

    def test_deeply_nested_array_path(self):
        """security_groups[0].rules[1].port — three segments with two brackets."""
        cloud = [{"id": "r1", "security_groups": [
            {"rules": [{"port": 80}]}
        ]}]
        iac = [{"id": "r1", "security_groups": [
            {"rules": [{"port": 80}, {"port": 443}]}
        ]}]
        report = make_analyzer(cloud, iac).analyze()
        assert "security_groups[0].rules[1]" in change_keys(report[0])


# ---------------------------------------------------------------------------
# 4.  Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_both_empty_produces_empty_report(self):
        report = make_analyzer([], []).analyze()
        assert report == []

    def test_empty_cloud_resources_produces_empty_report(self):
        iac = [{"id": "r1"}]
        report = make_analyzer([], iac).analyze()
        assert report == []

    def test_empty_iac_resources_all_cloud_are_missing(self):
        cloud = [{"id": "r1", "name": "vpc"}, {"id": "r2"}]
        report = make_analyzer(cloud, []).analyze()
        assert len(report) == 2
        assert all(item["State"] == "Missing" for item in report)

    def test_duplicate_ids_in_iac_emits_warning_and_last_wins(self, capsys):
        cloud = [{"id": "r1", "version": "1.0"}]
        iac   = [
            {"id": "r1", "version": "first"},
            {"id": "r1", "version": "last"},
        ]
        report = make_analyzer(cloud, iac).analyze()
        captured = capsys.readouterr()
        assert "Duplicate IaC resource id 'r1'" in captured.out
        entry = find_change(report[0], "version")
        assert entry["IacValue"] == "last"

    def test_duplicate_names_in_iac_emits_warning_and_last_wins(self, capsys):
        cloud = [{"name": "bucket", "versioning": True}]
        iac   = [
            {"name": "bucket", "versioning": True},
            {"name": "bucket", "versioning": False},
        ]
        report = make_analyzer(cloud, iac).analyze()
        captured = capsys.readouterr()
        assert "Duplicate IaC resource name 'bucket'" in captured.out
        # last IaC entry has versioning=False, cloud has True → Modified
        assert report[0]["State"] == "Modified"

    def test_resources_without_id_or_name_are_not_matched(self):
        """
        Resources with neither 'id' nor 'name' are indexed positionally in IaC
        but cannot be found by a cloud resource lookup (cloud has no id/name either).
        """
        cloud = [{"size": "large", "region": "us-west-2"}]
        iac   = [{"size": "large", "region": "us-west-2"}]
        report = make_analyzer(cloud, iac).analyze()
        assert len(report) == 1
        # cloud resource has no id/name → _find_matching_iac_resource returns None
        assert report[0]["State"] == "Missing"

    def test_multiple_resources_mixed_states(self):
        cloud = [
            {"id": "r1", "size": "small"},   # Match
            {"id": "r2", "size": "small"},   # Modified
            {"id": "r3", "size": "large"},   # Missing
        ]
        iac = [
            {"id": "r1", "size": "small"},
            {"id": "r2", "size": "xlarge"},
        ]
        report = make_analyzer(cloud, iac).analyze()
        states = {item["CloudResourceItem"]["id"]: item["State"] for item in report}
        assert states["r1"] == "Match"
        assert states["r2"] == "Modified"
        assert states["r3"] == "Missing"

    def test_analyze_resets_report_on_each_call(self):
        """Calling analyze() twice on the same instance does not accumulate results."""
        cloud = [{"id": "r1"}]
        iac   = [{"id": "r1"}]
        analyzer = make_analyzer(cloud, iac)
        analyzer.analyze()
        report = analyzer.analyze()
        assert len(report) == 1


# ---------------------------------------------------------------------------
# 5.  Report format validation (Fix #3)
# ---------------------------------------------------------------------------

class TestReportFormat:

    REQUIRED_FIELDS = {"CloudResourceItem", "IacResourceItem", "State", "ChangeLog"}
    VALID_STATES    = {"Match", "Modified", "Missing"}

    def _mixed_report(self):
        cloud = [
            {"id": "r1", "v": 1},  # Match
            {"id": "r2", "v": 1},  # Modified
            {"id": "r3"},          # Missing
        ]
        iac = [
            {"id": "r1", "v": 1},
            {"id": "r2", "v": 2},
        ]
        return make_analyzer(cloud, iac).analyze()

    def test_all_required_fields_present_in_every_item(self):
        for item in self._mixed_report():
            assert self.REQUIRED_FIELDS.issubset(item.keys()), \
                f"Missing fields in: {set(item.keys())}"

    def test_state_is_always_a_valid_value(self):
        for item in self._mixed_report():
            assert item["State"] in self.VALID_STATES

    def test_changelog_is_always_a_list(self):
        for item in self._mixed_report():
            assert isinstance(item["ChangeLog"], list)

    def test_changelog_empty_for_match_state(self):
        cloud = [{"id": "r1", "v": 1}]
        iac   = [{"id": "r1", "v": 1}]
        report = make_analyzer(cloud, iac).analyze()
        assert report[0]["State"] == "Match"
        assert report[0]["ChangeLog"] == []

    def test_changelog_empty_for_missing_state(self):
        cloud = [{"id": "r1"}]
        report = make_analyzer(cloud, []).analyze()
        assert report[0]["State"] == "Missing"
        assert report[0]["ChangeLog"] == []

    def test_iac_resource_item_is_exactly_empty_dict_for_missing(self):
        """Fix #3: IacResourceItem must be {} (not None, not absent) for Missing state."""
        cloud = [{"id": "r1", "name": "vpc"}]
        report = make_analyzer(cloud, []).analyze()
        item = report[0]
        assert item["State"] == "Missing"
        assert item["IacResourceItem"] == {}
        assert isinstance(item["IacResourceItem"], dict)

    def test_iac_resource_item_is_not_none_for_missing(self):
        """IacResourceItem must never be None — always {} for Missing."""
        cloud = [{"id": "x"}]
        report = make_analyzer(cloud, []).analyze()
        assert report[0]["IacResourceItem"] is not None

    def test_changelog_entries_have_exactly_three_keys(self):
        cloud = [{"id": "r1", "v": 1}]
        iac   = [{"id": "r1", "v": 2}]
        report = make_analyzer(cloud, iac).analyze()
        for entry in report[0]["ChangeLog"]:
            assert set(entry.keys()) == {"KeyName", "CloudValue", "IacValue"}

    def test_cloud_resource_item_references_original_object(self):
        """CloudResourceItem should be the original dict, not a copy."""
        resource = {"id": "r1", "data": "original"}
        report = make_analyzer([resource], []).analyze()
        assert report[0]["CloudResourceItem"] is resource

    def test_iac_resource_item_references_original_iac_object(self):
        """IacResourceItem for a matched resource should be the original IaC dict."""
        iac_resource = {"id": "r1", "data": "iac"}
        cloud = [{"id": "r1", "data": "cloud"}]
        report = make_analyzer(cloud, [iac_resource]).analyze()
        assert report[0]["IacResourceItem"] is iac_resource

    def test_report_length_equals_cloud_resource_count(self):
        cloud = [{"id": "r1"}, {"id": "r2"}, {"id": "r3"}]
        iac   = [{"id": "r1"}]
        report = make_analyzer(cloud, iac).analyze()
        assert len(report) == len(cloud)


# ---------------------------------------------------------------------------
# 6.  load_json_file
# ---------------------------------------------------------------------------

class TestLoadJsonFile:

    def test_loads_valid_json_array(self, tmp_path):
        data = [{"id": "r1"}, {"id": "r2"}]
        f = tmp_path / "resources.json"
        f.write_text(json.dumps(data))
        assert load_json_file(str(f)) == data

    def test_raises_value_error_for_json_object(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text(json.dumps({"key": "value"}))
        with pytest.raises(ValueError, match="Expected a JSON array"):
            load_json_file(str(f))

    def test_raises_value_error_for_json_scalar(self, tmp_path):
        f = tmp_path / "scalar.json"
        f.write_text("42")
        with pytest.raises(ValueError, match="Expected a JSON array"):
            load_json_file(str(f))

    def test_raises_json_decode_error_for_invalid_json(self, tmp_path):
        f = tmp_path / "broken.json"
        f.write_text("{not valid json")
        with pytest.raises(json.JSONDecodeError):
            load_json_file(str(f))

    def test_loads_empty_array(self, tmp_path):
        f = tmp_path / "empty.json"
        f.write_text("[]")
        assert load_json_file(str(f)) == []


# ---------------------------------------------------------------------------
# 7.  save_report
# ---------------------------------------------------------------------------

class TestSaveReport:

    def test_saves_report_as_indented_json(self, tmp_path):
        report = [
            {
                "CloudResourceItem": {"id": "r1"},
                "IacResourceItem": {"id": "r1"},
                "State": "Match",
                "ChangeLog": [],
            }
        ]
        out = tmp_path / "report.json"
        save_report(report, str(out))
        loaded = json.loads(out.read_text())
        assert loaded == report

    def test_raises_io_error_for_unwritable_path(self, tmp_path):
        bad_path = str(tmp_path / "no_such_dir" / "report.json")
        with pytest.raises(IOError):
            save_report([], bad_path)


# ---------------------------------------------------------------------------
# 8.  generate_analysis_report (end-to-end)
# ---------------------------------------------------------------------------

class TestGenerateAnalysisReport:

    def test_end_to_end_match(self, tmp_path):
        cloud = [{"id": "r1", "size": "small"}]
        iac   = [{"id": "r1", "size": "small"}]
        cloud_f = tmp_path / "cloud.json"
        iac_f   = tmp_path / "iac.json"
        out_f   = tmp_path / "report.json"
        cloud_f.write_text(json.dumps(cloud))
        iac_f.write_text(json.dumps(iac))

        result = generate_analysis_report(str(cloud_f), str(iac_f), str(out_f))

        assert len(result) == 1
        assert result[0]["State"] == "Match"
        assert out_f.exists()

    def test_end_to_end_creates_output_file(self, tmp_path):
        cloud = [{"id": "r1"}]
        iac   = []
        cloud_f = tmp_path / "cloud.json"
        iac_f   = tmp_path / "iac.json"
        out_f   = tmp_path / "report.json"
        cloud_f.write_text(json.dumps(cloud))
        iac_f.write_text(json.dumps(iac))

        generate_analysis_report(str(cloud_f), str(iac_f), str(out_f))
        assert out_f.exists()
        loaded = json.loads(out_f.read_text())
        assert loaded[0]["State"] == "Missing"

    def test_end_to_end_prints_summary(self, tmp_path, capsys):
        cloud = [
            {"id": "r1", "v": 1},
            {"id": "r2", "v": 1},
            {"id": "r3"},
        ]
        iac = [
            {"id": "r1", "v": 1},
            {"id": "r2", "v": 2},
        ]
        cloud_f = tmp_path / "cloud.json"
        iac_f   = tmp_path / "iac.json"
        out_f   = tmp_path / "report.json"
        cloud_f.write_text(json.dumps(cloud))
        iac_f.write_text(json.dumps(iac))

        generate_analysis_report(str(cloud_f), str(iac_f), str(out_f))
        captured = capsys.readouterr()
        assert "1 match" in captured.out
        assert "1 modified" in captured.out
        assert "1 missing" in captured.out


# ---------------------------------------------------------------------------
# 9.  CLI — validate_input_file, validate_output_path, main()
# ---------------------------------------------------------------------------

class TestCLIValidators:

    def test_validate_input_file_returns_absolute_path(self, tmp_path):
        f = tmp_path / "cloud.json"
        f.write_text("[]")
        result = validate_input_file(str(f))
        assert result == str(f.absolute())

    def test_validate_input_file_raises_for_missing_file(self, tmp_path):
        with pytest.raises(argparse.ArgumentTypeError, match="File not found"):
            validate_input_file(str(tmp_path / "ghost.json"))

    def test_validate_input_file_raises_for_directory(self, tmp_path):
        with pytest.raises(argparse.ArgumentTypeError, match="Not a file"):
            validate_input_file(str(tmp_path))

    def test_validate_input_file_raises_for_wrong_extension(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_text("[]")
        with pytest.raises(argparse.ArgumentTypeError, match="File must be JSON"):
            validate_input_file(str(f))

    def test_validate_output_path_returns_absolute_path(self, tmp_path):
        out = tmp_path / "report.json"
        result = validate_output_path(str(out))
        assert result == str(out.absolute())

    def test_validate_output_path_creates_missing_parent(self, tmp_path):
        out = tmp_path / "new_dir" / "report.json"
        result = validate_output_path(str(out))
        assert (tmp_path / "new_dir").is_dir()
        assert result == str(out.absolute())

    def test_validate_output_path_raises_when_parent_is_a_file(self, tmp_path):
        # Create a file where the parent dir should be
        blocker = tmp_path / "blocker"
        blocker.write_text("x")
        out = str(blocker / "report.json")
        with pytest.raises(argparse.ArgumentTypeError):
            validate_output_path(out)


class TestCLIMain:

    def _write_json(self, path, data):
        path.write_text(json.dumps(data))

    def test_main_returns_0_on_success(self, tmp_path):
        cloud_f = tmp_path / "cloud.json"
        iac_f   = tmp_path / "iac.json"
        out_f   = tmp_path / "report.json"
        self._write_json(cloud_f, [{"id": "r1"}])
        self._write_json(iac_f, [{"id": "r1"}])

        with patch("sys.argv", ["cli", str(cloud_f), str(iac_f), str(out_f)]):
            assert main() == 0

    def test_main_returns_1_on_value_error(self, tmp_path):
        cloud_f = tmp_path / "cloud.json"
        iac_f   = tmp_path / "iac.json"
        out_f   = tmp_path / "report.json"
        # IaC file contains a JSON object, not an array → ValueError
        cloud_f.write_text("[]")
        iac_f.write_text('{"key": "value"}')

        with patch("sys.argv", ["cli", str(cloud_f), str(iac_f), str(out_f)]):
            assert main() == 1

    def test_main_returns_1_on_generic_exception(self, tmp_path):
        cloud_f = tmp_path / "cloud.json"
        iac_f   = tmp_path / "iac.json"
        out_f   = tmp_path / "report.json"
        self._write_json(cloud_f, [{"id": "r1"}])
        self._write_json(iac_f, [{"id": "r1"}])

        with patch("sys.argv", ["cli", str(cloud_f), str(iac_f), str(out_f)]):
            with patch(
                "cloud_iac_analyzer.cli.generate_analysis_report",
                side_effect=RuntimeError("unexpected"),
            ):
                assert main() == 1

    def test_main_output_file_created(self, tmp_path):
        cloud_f = tmp_path / "cloud.json"
        iac_f   = tmp_path / "iac.json"
        out_f   = tmp_path / "report.json"
        self._write_json(cloud_f, [{"id": "r1", "v": 1}])
        self._write_json(iac_f,   [{"id": "r1", "v": 2}])

        with patch("sys.argv", ["cli", str(cloud_f), str(iac_f), str(out_f)]):
            main()

        assert out_f.exists()
        report = json.loads(out_f.read_text())
        assert report[0]["State"] == "Modified"

    def test_main_returns_1_on_file_not_found(self, tmp_path):
        cloud_f = tmp_path / "cloud.json"
        iac_f   = tmp_path / "iac.json"
        out_f   = tmp_path / "report.json"
        self._write_json(cloud_f, [{"id": "r1"}])
        self._write_json(iac_f, [{"id": "r1"}])

        with patch("sys.argv", ["cli", str(cloud_f), str(iac_f), str(out_f)]):
            with patch(
                "cloud_iac_analyzer.cli.generate_analysis_report",
                side_effect=FileNotFoundError("file gone"),
            ):
                assert main() == 1

    def test_validate_output_path_raises_for_unwritable_directory(self, tmp_path):
        out = tmp_path / "report.json"
        with patch("os.access", return_value=False):
            with pytest.raises(argparse.ArgumentTypeError, match="not writable"):
                validate_output_path(str(out))
