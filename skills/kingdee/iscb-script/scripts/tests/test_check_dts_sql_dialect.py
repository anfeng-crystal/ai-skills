from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "check_dts_sql_dialect.py"
SPEC = importlib.util.spec_from_file_location("check_dts_sql_dialect", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CheckDtsSqlDialectTest(unittest.TestCase):
    def write_dts(self, record: dict) -> Path:
        directory = Path(tempfile.mkdtemp())
        path = directory / "flow.dts"
        path.write_text(f"({json.dumps(record, ensure_ascii=False)})\n", encoding="utf-8")
        return path

    def test_finds_bare_trim_in_nested_service_flow_json(self) -> None:
        definition = {"nodes": {"3": {"script": "var sql = 'SELECT TRIM(name) FROM t';"}}}
        path = self.write_dts({"$entityname": "isc_service_flow", "define_json_tag": f"({json.dumps(definition)})"})
        violations, errors = MODULE.check([path], "sqlserver-legacy")
        self.assertFalse(errors)
        self.assertEqual([item["code"] for item in violations], ["SQLSERVER_LEGACY_TRIM"])

    def test_scans_standalone_rule_but_ignores_dsl_string_trim(self) -> None:
        bad = self.write_dts({"$entityname": "isc_value_conver_rule", "isc_script_tag": "return query_value(cn, 'SELECT TRIM(name) FROM t');"})
        good = self.write_dts({"$entityname": "isc_value_conver_rule", "isc_script_tag": "return String.trim(value);"})
        violations, errors = MODULE.check([bad, good], "sqlserver-legacy")
        self.assertFalse(errors)
        self.assertEqual(len(violations), 1)


if __name__ == "__main__":
    unittest.main()
