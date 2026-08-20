from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "metadata_to_ddl.py"
SPEC = importlib.util.spec_from_file_location("metadata_to_ddl", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "normalized schema.json"


class MetadataToDdlTest(unittest.TestCase):
    def test_postgresql_ddl_is_deterministic(self) -> None:
        schema = MODULE.load_schema(FIXTURE)
        ddl = MODULE.render_ddl(schema, "postgresql")
        self.assertIn("CREATE TABLE T_DEMO_ENTITY", ddl)
        self.assertIn("FNUMBER VARCHAR(80) NOT NULL", ddl)
        self.assertIn("FAMOUNT DECIMAL(18,2)", ddl)
        self.assertIn("CREATE UNIQUE INDEX IDX_DEMO_NUMBER", ddl)
        self.assertNotIn("DROP ", ddl)

    def test_unknown_type_does_not_fall_back_to_varchar(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["columns"][0]["type"] = "mystery"
        with self.assertRaises(MODULE.MetadataError):
            MODULE.normalize_schema(raw)

    def test_missing_string_length_is_rejected(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        del raw["columns"][1]["length"]
        with self.assertRaises(MODULE.MetadataError):
            MODULE.normalize_schema(raw)

    def test_space_path_and_windows_separator_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "folder with spaces" / "schema copy.json"
            target.parent.mkdir()
            target.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            raw = str(target.relative_to(root)).replace("/", "\\")
            self.assertEqual(target.resolve(), MODULE.resolve_user_path(raw, cwd=root))
            self.assertEqual("T_DEMO_ENTITY", MODULE.load_schema(target).table)


if __name__ == "__main__":
    unittest.main()
