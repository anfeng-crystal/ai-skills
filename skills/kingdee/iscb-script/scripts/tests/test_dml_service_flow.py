from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "dml_service_flow.py"
SPEC = importlib.util.spec_from_file_location("dml_service_flow", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class DmlServiceFlowTest(unittest.TestCase):
    def args(self) -> Namespace:
        return Namespace(
            baseline=str(FIXTURES / "current baseline.dts"),
            sql_file=str(FIXTURES / "write.sql"),
            precheck_sql_file=str(FIXTURES / "precheck.sql"),
            parameters_file=str(FIXTURES / "parameters.json"),
            contract_file=str(FIXTURES / "contract.json"),
        )

    def test_prepare_generates_parameterized_script(self) -> None:
        dml, precheck, _, contract, script = MODULE.prepare(self.args(), require_approved=True)
        self.assertEqual("UPDATE", dml.verb)
        self.assertEqual("SELECT", precheck.verb)
        self.assertEqual(1, contract["max_rows"])
        self.assertIn("query_value(DB1", script)
        self.assertIn("execute_update(DB1", script)
        self.assertNotIn("fixture-approval", script)

    def test_patch_preserves_other_records_and_nodes(self) -> None:
        _, _, _, contract, script = MODULE.prepare(self.args(), require_approved=True)
        baseline = MODULE.read_text(FIXTURES / "current baseline.dts")
        patched = MODULE.patch_dts(baseline, contract, script)
        self.assertIn('"$entityname":"isc_data_source"', patched)
        self.assertIn("execute_update(DB1", patched)
        records = [MODULE.unwrap_json(line)[0] for line in patched.splitlines() if line.strip()]
        flow = next(record for record in records if record.get("$entityname") == "isc_service_flow")
        definition = MODULE.unwrap_json(flow["define_json_tag"])[0]
        self.assertEqual({"id": "9", "type": "End"}, definition["nodes"]["9"])

    def test_update_without_where_is_rejected(self) -> None:
        with self.assertRaises(MODULE.ContractError):
            MODULE.parse_dml("UPDATE t_demo SET fstatus = ?")

    def test_space_path_and_windows_separator_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "folder with spaces" / "contract copy.json"
            target.parent.mkdir()
            target.write_text(json.dumps({"value": 1}), encoding="utf-8")
            raw = str(target.relative_to(root)).replace("/", "\\")
            self.assertEqual(target.resolve(), MODULE.resolve_user_path(raw, cwd=root))


if __name__ == "__main__":
    unittest.main()
