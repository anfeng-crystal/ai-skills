from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "validate_frontend.py"
SPEC = importlib.util.spec_from_file_location("validate_frontend", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class FrontendValidatorTest(unittest.TestCase):
    def test_valid_fixtures_pass(self) -> None:
        self.assertEqual([], MODULE.validate_path(FIXTURES / "lifecycle-valid.js"))
        self.assertEqual([], MODULE.validate_path(FIXTURES / "style-valid.css"))

    def test_invalid_javascript_reports_lifecycle_findings(self) -> None:
        codes = {issue.code for issue in MODULE.validate_path(FIXTURES / "lifecycle-invalid.js")}
        self.assertEqual({"JS001", "JS002", "JS004"}, codes)

    def test_invalid_css_reports_all_contract_findings(self) -> None:
        codes = {issue.code for issue in MODULE.validate_path(FIXTURES / "style-invalid.css")}
        self.assertEqual({"CSS001", "CSS002", "CSS003"}, codes)

    def test_space_path_and_windows_separator_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "folder with spaces" / "page script.js"
            target.parent.mkdir()
            target.write_text((FIXTURES / "lifecycle-valid.js").read_text(encoding="utf-8"), encoding="utf-8")
            relative_windows = str(target.relative_to(root)).replace("/", "\\")
            resolved = MODULE.resolve_user_path(relative_windows, cwd=root)
            self.assertEqual(target.resolve(), resolved)
            self.assertEqual([], MODULE.validate_path(resolved))


if __name__ == "__main__":
    unittest.main()
