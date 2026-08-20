from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "validate_change_contract.py"


class ValidateChangeContractTest(unittest.TestCase):
    def run_contract(self, contract: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "contract.json"
            path.write_text(json.dumps(contract), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), "--contract", str(path)],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_accepts_safe_plan_contract(self) -> None:
        result = self.run_contract(safe_contract())
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)["status"], "pass")

    def test_rejects_null_for_not_null_stale_count_and_missing_recompute(self) -> None:
        contract = safe_contract()
        contract["scope"] = {"where_sql": "fid in stage", "expected_rows": 56, "max_rows": 55}
        contract["assignments"][0]["mapping_missing"] = "set_null"
        contract["failure_recovery"]["recompute_scope"] = False
        result = self.run_contract(contract)
        self.assertEqual(result.returncode, 1, result.stdout)
        codes = {item["code"] for item in json.loads(result.stdout)["errors"]}
        self.assertIn("exceeds_max_rows", codes)
        self.assertIn("not_null_assignment_can_be_null", codes)
        self.assertIn("recompute_required", codes)

    def test_execute_mode_requires_approval_reference(self) -> None:
        contract = safe_contract()
        contract["mode"] = "execute-approved"
        result = self.run_contract(contract)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("missing_approval", {item["code"] for item in json.loads(result.stdout)["errors"]})

    def test_special_change_kinds_require_extra_evidence(self) -> None:
        expected = {
            "relationship-remap": "relationship_evidence_required",
            "entity-migration": "storage_topology_required",
            "symptom-repair": "causal_target_required",
        }
        for change_kind, expected_code in expected.items():
            with self.subTest(change_kind=change_kind):
                contract = safe_contract()
                contract["change_kind"] = change_kind
                result = self.run_contract(contract)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(expected_code, {item["code"] for item in json.loads(result.stdout)["errors"]})

    def test_entity_migration_rejects_empty_self_certified_topology(self) -> None:
        contract = safe_contract()
        contract["change_kind"] = "entity-migration"
        contract["storage_topology"] = {
            "enumerated": True,
            "multilingual_tables": [],
            "entry_tables": [],
            "relation_tables": [],
            "reference_strategy": "unknown",
            "import_order": "unknown",
            "orphan_check": True,
        }
        result = self.run_contract(contract)
        self.assertEqual(result.returncode, 1, result.stdout)
        codes = {item["code"] for item in json.loads(result.stdout)["errors"]}
        self.assertIn("table_classes_required", codes)
        self.assertIn("reference_strategy_required", codes)
        self.assertIn("import_order_required", codes)

    def test_entity_migration_accepts_evidenced_absent_table_classes(self) -> None:
        contract = safe_contract()
        contract["change_kind"] = "entity-migration"
        contract["storage_topology"] = safe_storage_topology()
        result = self.run_contract(contract)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)["status"], "pass")


def safe_contract() -> dict:
    return {
        "version": 1,
        "mode": "plan-only",
        "change_kind": "direct",
        "environment": "prod",
        "target": {"database": "db", "schema": "public", "table": "target", "key_columns": ["fid"]},
        "scope": {"where_sql": "fid in stage", "expected_rows": 10, "max_rows": 10},
        "stage": {"enabled": True, "unique_key": ["fid"], "rejects_unmapped": True},
        "assignments": [{"column": "fk_target_org", "nullable": False, "mapping_missing": "preserve_old"}],
        "transaction": True,
        "before_image": {"enabled": True},
        "concurrency": {"compare_old_values": True},
        "rollback": {"compare_before_restore": True},
        "verification": {"exact_affected_rows": True, "postcheck": True},
        "failure_recovery": {"rollback": True, "recompute_scope": True},
    }


def safe_storage_topology() -> dict:
    return {
        "enumerated": True,
        "classes": {
            "main": {"status": "present", "tables": ["t_main"], "evidence_ref": "metadata entity table mapping"},
            "multilingual": {"status": "confirmed_absent", "tables": [], "evidence_ref": "metadata field storage audit"},
            "entries": {"status": "confirmed_absent", "tables": [], "evidence_ref": "entry metadata audit"},
            "relations": {"status": "confirmed_absent", "tables": [], "evidence_ref": "relation metadata audit"},
        },
        "reference_strategy": "reuse verified target references",
        "import_order": ["t_main"],
        "parent_keys": {"t_main": "root table; primary key fid"},
        "id_mapping": {"t_main": "old fid to new fid mapping"},
        "row_count_checks": {"t_main": {"before": "bounded source count", "after": "exact target count"}},
        "orphan_check": True,
    }


if __name__ == "__main__":
    unittest.main()
