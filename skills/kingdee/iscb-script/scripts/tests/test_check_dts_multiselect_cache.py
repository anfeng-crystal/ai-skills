import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "check_dts_multiselect_cache.py"
SPEC = importlib.util.spec_from_file_location("check_dts_multiselect_cache", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class MultiSelectCacheCheckTest(unittest.TestCase):
    def _write_rule(self, *, script: str, iscached: bool) -> Path:
        directory = Path(tempfile.mkdtemp())
        path = directory / "rule.dts"
        value = {
            "$entityname": "isc_value_conver_rule",
            "number": "sampleRule",
            "isc_script_tag": script,
            "iscached": iscached,
        }
        path.write_text(f"({json.dumps(value)})\n", encoding="utf-8")
        return path

    def test_rejects_cached_id_list(self):
        path = self._write_rule(
            script="var ids = []; ids = Collection.addAll(ids, [row.fid]); return ids;",
            iscached=True,
        )
        violations, errors = MODULE.check([path])
        self.assertEqual([], errors)
        self.assertEqual(1, len(violations))

    def test_accepts_uncached_id_list(self):
        path = self._write_rule(
            script="var ids = []; ids = Collection.addAll(ids, [row.fid]); return ids;",
            iscached=False,
        )
        violations, errors = MODULE.check([path])
        self.assertEqual([], errors)
        self.assertEqual([], violations)

    def test_does_not_treat_joined_enum_string_as_id_list(self):
        path = self._write_rule(
            script='var codes = []; return String.join(codes, ",");',
            iscached=True,
        )
        violations, errors = MODULE.check([path])
        self.assertEqual([], errors)
        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
