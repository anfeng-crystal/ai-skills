import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "sdk_search.py"
SPEC = importlib.util.spec_from_file_location("sdk_search", SCRIPT)
sdk_search = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sdk_search)


def sdk_fixture():
    return {
        "metadata": {
            "version": "Cosmic\u00a0V8.0.1",
            "source_url": "https://example.invalid/sdk/Cosmic-V8.0.1",
            "crawl_time": "2026-04-15T10:12:08",
        },
        "classes": [
            {
                "name": name,
                "full_name": "kd.fixture." + name,
                "type": "class",
                "comment": "Sharedbehavior. " + ("distinctkeyword" if name == "AlphaWidget" else ""),
                "methods": [{
                    "name": "read",
                    "returnType": "String",
                    "modifiers": "public",
                    "paramNames": ["key"],
                    "paramTypes": ["String"],
                    "comment": "Read a value.",
                }],
            }
            for name in ("AlphaWidget", "BetaWidget", "GammaWidget")
        ],
    }


class SdkSearchTests(unittest.TestCase):
    def assert_evidence(self, output, target="7.0", comparison="different-version"):
        self.assertEqual(output.count("## SDK evidence"), 1)
        for field in ("Index version:", "Index source:", "Index crawl time:"):
            self.assertIn(field, output)
        self.assertIn(f"Requested target version: {target}", output)
        self.assertIn(f"Version comparison: {comparison}", output)
        self.assertIn("Project compatibility: unverified", output)
        self.assertIn("index-candidate; not confirmed-project", output)
        self.assertIn("target project's resolved JARs", output)

    def test_every_search_branch_keeps_evidence_and_existing_results(self):
        sdk = sdk_fixture()
        cases = (
            ("AlphaWidget", 10, "# Class: kd.fixture.AlphaWidget"),
            ("kd.fixture.AlphaWidget", 10, "# Class: kd.fixture.AlphaWidget"),
            ("Beta", 10, "# Class: kd.fixture.BetaWidget"),
            ("Widget", 10, "Found 3 classes:"),
            ("Widget", 1, "Found 3 matching classes."),
            ("sharedbehavior", 10, "Found 'sharedbehavior' in 3 classes:"),
            ("sharedbehavior", 1, "Found 3 classes containing 'sharedbehavior'."),
            ("distinctkeyword", 10, "Found 'distinctkeyword' in 1 classes:"),
            ("not-present", 10, "No results found for 'not-present'."),
        )
        for query, limit, expected in cases:
            with self.subTest(query=query, limit=limit):
                output = sdk_search.search(sdk, query, limit, target_version="7.0")
                self.assert_evidence(output)
                self.assertIn(expected, output)
        detailed = sdk_search.search(sdk, "AlphaWidget", target_version="7.0")
        self.assertIn("public String read(String key)", detailed)
        self.assertIn("Read a value.", detailed)

    def test_legacy_python_call_keeps_limit_position_and_marks_target_missing(self):
        output = sdk_search.search(sdk_fixture(), "Widget", 1)
        self.assert_evidence(output, "not provided", "target-not-specified")
        self.assertIn("Top 1:", output)
        self.assertNotIn("- kd.fixture.BetaWidget", output)

    def test_version_comparison_never_fills_missing_components(self):
        cases = (
            ("Cosmic V8.0.1", "7.0", "different-version"),
            ("Cosmic V7.0.13", "7.0", "incomplete-version"),
            ("Cosmic V7.0", "7.0", "incomplete-version"),
            ("Cosmic V7.0.13", "V7.0.13", "same-version"),
            ("Cosmic V7.0.13", "7.0.12", "different-version"),
            ("Cosmic V7.0.13.2", "7.0.13", "incomplete-version"),
            ("Cosmic V7.0.13", "latest", "unknown"),
            (None, "7.0", "unknown"),
            ("unversioned", "7.0", "unknown"),
            ("Cosmic V8.0.1", None, "target-not-specified"),
        )
        for indexed, target, comparison in cases:
            with self.subTest(indexed=indexed, target=target):
                sdk = sdk_fixture()
                sdk["metadata"]["version"] = indexed
                output = sdk_search.search(sdk, "AlphaWidget", target_version=target)
                self.assert_evidence(output, target or "not provided", comparison)
                self.assertIn("# Class: kd.fixture.AlphaWidget", output)
                self.assertNotIn("Project compatibility: confirmed", output)

    def test_unknown_metadata_is_not_replaced_by_index_schema_version(self):
        for metadata in ({}, None, "not-an-object", {"sdk_version": "1.0"}):
            with self.subTest(metadata=metadata):
                sdk = sdk_fixture()
                sdk["metadata"] = metadata
                output = sdk_search.search(sdk, "AlphaWidget", target_version="7.0")
                self.assert_evidence(output, comparison="unknown")
                self.assertIn("Index version: unknown", output)
                self.assertIn("Index source: unknown", output)
                self.assertIn("Index crawl time: unknown", output)

    def test_search_does_not_mutate_index_or_target(self):
        sdk = sdk_fixture()
        original = copy.deepcopy(sdk)
        sdk_search.search(sdk, "AlphaWidget", target_version="7.0")
        self.assertEqual(sdk, original)


class SdkSearchCliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="sdk search ")
        self.index = Path(self.temp_dir.name) / "目标 索引.json"
        self.index.write_text(json.dumps(sdk_fixture(), ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cli(self, *args, environment=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            capture_output=True, text=True, encoding="utf-8", env=environment, check=False,
        )

    def test_custom_index_supports_pathlib_string_and_cli_paths_with_spaces(self):
        self.assertEqual(sdk_search.load_sdk(self.index), sdk_fixture())
        self.assertEqual(sdk_search.load_sdk(str(self.index)), sdk_fixture())
        completed = self.run_cli("AlphaWidget", "--sdk-path", self.index, "--target-version", "7.0")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Index version: Cosmic\u00a0V8.0.1", completed.stdout)
        self.assertIn("Index source: https://example.invalid/", completed.stdout)
        self.assertIn("Index crawl time: 2026-04-15T10:12:08", completed.stdout)
        self.assertIn("Version comparison: different-version", completed.stdout)
        self.assertIn("# Class: kd.fixture.AlphaWidget", completed.stdout)

    def test_cli_without_target_keeps_querying_custom_index(self):
        completed = self.run_cli("AlphaWidget", "--sdk-path", self.index)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Requested target version: not provided", completed.stdout)
        self.assertIn("Project compatibility: unverified", completed.stdout)
        self.assertIn("# Class: kd.fixture.AlphaWidget", completed.stdout)

    def test_legacy_cli_uses_bundled_index_without_new_flags(self):
        completed = self.run_cli("__sdk_version_audit_missing_class__")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Index version:", completed.stdout)
        self.assertIn("Requested target version: not provided", completed.stdout)
        self.assertIn("Project compatibility: unverified", completed.stdout)
        self.assertIn("No results found", completed.stdout)

    def test_cli_load_failure_keeps_unknown_evidence_and_target(self):
        self.index.write_text("{invalid", encoding="utf-8")
        completed = self.run_cli("AlphaWidget", "--sdk-path", self.index, "--target-version", "7.0")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("Index version: unknown", completed.stdout)
        self.assertIn("Requested target version: 7.0", completed.stdout)
        self.assertIn("Project compatibility: unverified", completed.stdout)
        self.assertIn("Error:", completed.stdout)

    def test_cli_ascii_stdout_does_not_fail_on_new_unicode_metadata(self):
        environment = dict(os.environ, PYTHONIOENCODING="ascii")
        completed = self.run_cli("AlphaWidget", "--sdk-path", self.index, "--target-version", "7.0", environment=environment)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Index version: Cosmic\\xa0V8.0.1", completed.stdout)
        self.assertIn("Project compatibility: unverified", completed.stdout)
        self.assertIn("# Class: kd.fixture.AlphaWidget", completed.stdout)


if __name__ == "__main__":
    unittest.main()
