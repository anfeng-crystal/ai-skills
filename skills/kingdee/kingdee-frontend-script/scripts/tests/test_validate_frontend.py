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

    def test_css_documentation_and_disabled_examples_are_ignored(self) -> None:
        text = """/**
 * 如需使用平台主题色，可以使用'***themeColor***'来代指。
 * 以下写法仅用于说明，不应执行。
@media screen { $.field { color:themeColor; } }
*/
$ { color:'themeColor'; }
"""
        self.assertEqual([], MODULE.validate_css(text, "commented.css"))

    def test_css_findings_keep_original_lines_after_comments(self) -> None:
        text = "/*\n @media screen {}\n*/\n@media screen {}\n$.field {color:themeColor;}"
        findings = MODULE.validate_css(text, "active.css")
        self.assertEqual({("CSS001", 4), ("CSS002", 5), ("CSS003", 5)},
                         {(item.code, item.line) for item in findings})

    def test_comment_delimiters_inside_strings_do_not_hide_live_rules(self) -> None:
        for value in ('"/*"', "'/*'", r'"\"/*"', r"'\'/*'"):
            with self.subTest(value=value):
                text = "$ { content:" + value + "; color:themeColor; } /* real comment */"
                self.assertEqual(["CSS003"], [item.code for item in MODULE.validate_css(text, "quoted.css")])

    def test_unquoted_url_and_escaped_slash_do_not_hide_live_rules(self) -> None:
        values = ("url(/assets/*icon.svg)", "URL(/assets/*icon.svg)",
                  r"u\72l(/assets/*icon.svg)", r"url(/assets/\)/*icon.svg)",
                  r"prefix\/*suffix")
        for value in values:
            with self.subTest(value=value):
                text = "$ { --asset:" + value + "; }\n@media screen {}\n$.field {color:themeColor;}"
                findings = MODULE.validate_css(text, "url-or-escape.css")
                self.assertEqual({("CSS001", 2), ("CSS002", 3), ("CSS003", 3)},
                                 {(item.code, item.line) for item in findings})

    def test_escaped_quote_outside_string_does_not_hide_real_comment(self) -> None:
        text = r'$ .icon\" { color: red; } /* themeColor */' + "\n@media screen {}"
        self.assertEqual([("CSS001", 2)],
                         [(item.code, item.line) for item in MODULE.validate_css(text, "escaped-selector.css")])

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
