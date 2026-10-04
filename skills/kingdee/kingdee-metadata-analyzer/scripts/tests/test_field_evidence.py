"""Offline regressions for design-layer field evidence, not platform merging."""

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    # quick-query configures UTF-8 streams only when a .buffer exists.
    with patch.object(sys, "stdout", io.StringIO()), patch.object(sys, "stderr", io.StringIO()):
        spec.loader.exec_module(module)
    return module


quick = load_module("quick_query_test", "quick-query.py")
contract = load_module("metadata_contract_test", "metadata_contract.py")


def entity(number, fields="", parent=None, extra=""):
    ref = f"<ParentId>{parent}</ParentId>" if parent else ""
    return (number, number, f"<EntityMetadata>{ref}{extra}<Fields>{fields}</Fields></EntityMetadata>", "")


FIELD = "<TextField><Id>field-1</Id><Key>test_field</Key><Name>parent label</Name></TextField>"


class FieldEvidenceTest(unittest.TestCase):
    def query(self, row, ancestors=None, inherit=True):
        ancestors = ancestors or {}
        saved = {}
        connection, cursor = Mock(), Mock()
        connection.cursor.return_value = cursor
        lookups = []

        def parent_query(_cursor, root):
            lookups.append(root.findtext("ParentId"))
            if len(lookups) > 40:
                self.fail("inheritance traversal did not stop")
            return ancestors.get(root.findtext("ParentId"))

        output, errors = io.StringIO(), io.StringIO()
        with patch.object(quick, "load_config", return_value={}), \
             patch.object(quick, "get_conn", return_value=connection), \
             patch.object(quick, "query_entity", return_value=row), \
             patch.object(quick, "query_parent_entity", side_effect=parent_query), \
             patch.object(quick, "CACHE_DIR", Path("unused")), \
             patch.object(quick, "save_cache", side_effect=lambda _, data: saved.update(data)), \
             redirect_stdout(output), redirect_stderr(errors):
            result = quick.command_fields(SimpleNamespace(config="unused", entityNumber=row[1], inherit=inherit))
        cursor.close.assert_called_once()
        connection.close.assert_called_once()
        self.assertEqual(0, result)
        return saved, output.getvalue() + errors.getvalue(), lookups

    def test_remove_delta_retains_candidates_but_warns(self):
        child = entity("child", '<TextField action="remove" oid="field-1"/>', "parent")
        data, output, _ = self.query(child, {"parent": entity("parent", FIELD)})
        self.assertTrue(data.get("warnings"), "removed ancestor field must not appear without incomplete-evidence warning")
        self.assertIn("WARNING", output)
        self.assertIn("设计候选", output)
        self.assertEqual(["test_field"], [field["fieldKey"] for field in data["fields"]])
        self.assertFalse(data["fieldEvidence"]["effectiveFieldsResolved"])
        self.assertEqual("remove", data["fieldEvidence"]["unresolvedDeltas"][0]["action"])
        self.assertEqual("parent", data["fields"][0]["sourceEntity"])

    def test_edit_delta_without_key_remains_unresolved(self):
        child = entity("child", '<TextField action="edit" oid="field-1"><Name>child label</Name></TextField>', "parent")
        data, _, _ = self.query(child, {"parent": entity("parent", FIELD)})
        self.assertTrue(data["warnings"])
        delta = data["fieldEvidence"]["unresolvedDeltas"][0]
        self.assertIsNone(delta["fieldKey"])
        self.assertEqual("field-1", delta["oid"])
        self.assertEqual("parent label", data["fields"][0]["name"])

    def test_same_key_keeps_layer_provenance_without_merging(self):
        child = entity("child", FIELD.replace("parent label", "child label"), "parent")
        data, _, _ = self.query(child, {"parent": entity("parent", FIELD)})
        self.assertEqual(["child", "parent"], [field["sourceEntity"] for field in data["fields"]])
        self.assertTrue(data["warnings"])

    def test_simple_field_preserves_existing_values(self):
        data, _, lookups = self.query(entity("plain", FIELD), inherit=False)
        self.assertEqual([], data["warnings"])
        self.assertEqual([], lookups)
        self.assertEqual("test_field", data["fields"][0]["fieldKey"])
        self.assertEqual("TextField", data["fields"][0]["type"])
        self.assertTrue(data["fieldEvidence"]["chainComplete"])

    def test_without_inherit_does_not_hide_unread_parent(self):
        data, _, lookups = self.query(entity("child", FIELD, "parent"), inherit=False)
        self.assertFalse(data["fieldEvidence"]["chainComplete"])
        self.assertTrue(data["warnings"])
        self.assertEqual([], lookups)

    def test_missing_parent_is_incomplete(self):
        data, _, _ = self.query(entity("child", FIELD, "missing"))
        self.assertFalse(data["fieldEvidence"]["chainComplete"])
        self.assertIn("ancestor_not_found", data["warnings"])

    def test_cycle_stops_without_duplicate_layers(self):
        child = entity("child", FIELD, "parent")
        data, _, lookups = self.query(child, {"parent": entity("parent", FIELD, "child"), "child": child})
        self.assertIn("inheritance_cycle", data["warnings"])
        self.assertFalse(data["fieldEvidence"]["chainComplete"])
        self.assertEqual(2, len(data["fieldEvidence"]["sources"]))
        self.assertEqual(2, len(lookups))

    def test_long_chain_is_bounded_and_marked_truncated(self):
        ancestors = {str(i): entity(str(i), FIELD, str(i + 1)) for i in range(1, 36)}
        data, _, lookups = self.query(entity("0", FIELD, "1"), ancestors)
        self.assertIn("inheritance_depth_limit", data["warnings"])
        self.assertFalse(data["fieldEvidence"]["chainComplete"])
        self.assertLessEqual(len(lookups), 32)

    def test_invalid_target_or_parent_xml_is_incomplete(self):
        for row, ancestors in [(("bad", "bad", "<broken>", ""), {}),
                               (entity("child", FIELD, "parent"), {"parent": ("parent", "parent", "<broken>", "")})]:
            with self.subTest(row=row[1]):
                data, _, _ = self.query(row, ancestors)
                self.assertFalse(data["fieldEvidence"]["chainComplete"])
                self.assertIn("entity_xml_unreadable", data["warnings"])

    def test_inherit_path_without_resolvable_parent_is_not_complete(self):
        data, _, _ = self.query(entity("child", FIELD, extra="<InheritPath>ancestor</InheritPath>"))
        self.assertFalse(data["fieldEvidence"]["chainComplete"])
        self.assertIn("ancestor_reference_unresolved", data["warnings"])


class ContractEvidenceTest(unittest.TestCase):
    def build(self, cache, inventory=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cache.json").write_text(json.dumps(cache), encoding="utf-8")
            if inventory is not None:
                (root / "inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
            return contract.build_contract(SimpleNamespace(quick_cache=str(root / "cache.json"),
                inventory=str(root / "inventory.json") if inventory is not None else None,
                entity_number=None, environment="dev"))

    def test_input_warnings_are_not_discarded_or_reinterpreted(self):
        warnings = ["inheritance_delta_unresolved", {"kind": "partial", "details": [1, 2]}]
        result = self.build({"entityNumber": "child", "fields": [{"fieldKey": "test_field"}], "warnings": warnings})
        for warning in warnings:
            self.assertIn(warning, result["warnings"])

    def test_false_completeness_and_provenance_survive(self):
        status = {"chainComplete": False, "effectiveFieldsResolved": False, "unresolvedDeltas": [{"oid": "field-1"}]}
        result = self.build({"entityNumber": "child", "complete": False, "fieldEvidence": status,
            "fields": [{"fieldKey": "test_field", "sourceEntity": "parent", "sourceDepth": 1, "action": "edit", "oid": "field-1"}]})
        self.assertIs(False, result["sourceEvidence"]["quickCache"]["complete"])
        self.assertEqual(status, result["sourceEvidence"]["quickCache"]["fieldEvidence"])
        self.assertEqual("parent", result["fields"][0]["sourceEntity"])
        self.assertEqual("field-1", result["fields"][0]["oid"])
        self.assertTrue(result["warnings"])

    def test_legacy_fields_have_unknown_evidence_status(self):
        result = self.build({"fields": [{"fieldKey": "test_field"}]})
        self.assertIn("quickCache:field_evidence_status_unknown", result["warnings"])

    def test_plugin_contract_is_preserved_with_input_warning(self):
        inventory = {"entity": {"fnumber": "child"}, "warnings": "source_warning",
            "plugins": [{"className": "example.Plugin", "formPage": "MobileBillFormAp", "pageElement": "form"}]}
        result = self.build({"fields": []}, inventory)
        self.assertIn("source_warning", result["warnings"])
        self.assertEqual("mobile-bill", result["forms"][0]["pageType"])
        self.assertEqual("example.Plugin", result["forms"][0]["plugins"][0]["className"])


if __name__ == "__main__":
    unittest.main()
