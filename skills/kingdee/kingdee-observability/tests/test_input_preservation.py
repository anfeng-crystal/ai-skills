import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
CLIS = ("analyze_logs.py", "redact.py", "validate_query_plan.py")


class InputPreservationTest(unittest.TestCase):
    def make_input(self, root, cli):
        source = root / "synthetic input.json"
        if cli == "validate_query_plan.py":
            value = {
                "mode": "dev-query", "scopeId": "scope-synthetic",
                "targetRef": "dev-logs", "queryType": "trace",
                "filters": {"traceId": "trace-synthetic"},
                "maxRecords": 10, "redaction": True,
            }
        else:
            value = {
                "traceId": "trace-synthetic", "level": "ERROR",
                "message": "token=SYNTHETIC_SECRET status=401",
            }
        source.write_text(json.dumps(value) + "\n", encoding="utf-8")
        return source

    def run_cli(self, cli, source, output=None):
        command = [sys.executable, str(SCRIPTS / cli), "--input", str(source)]
        if output is not None:
            command.extend(["--output", str(output)])
        return subprocess.run(command, capture_output=True, text=True, check=False)

    def test_alias_outputs_fail_without_changing_input_bytes(self):
        for cli in CLIS:
            for alias in ("same-path", "resolved-dotdot", "symbolic-link", "hard-link"):
                with self.subTest(cli=cli, alias=alias), tempfile.TemporaryDirectory(prefix="input guard ") as temp:
                    root = Path(temp)
                    source = self.make_input(root, cli)
                    before = source.read_bytes()
                    if alias == "same-path":
                        output = source
                    elif alias == "resolved-dotdot":
                        (root / "nested").mkdir()
                        output = root / "nested" / ".." / source.name
                    else:
                        output = root / "alias.json"
                        try:
                            if alias == "symbolic-link":
                                output.symlink_to(source)
                            else:
                                os.link(source, output)
                        except (OSError, NotImplementedError) as exc:
                            self.skipTest(f"{alias} unavailable: {exc}")
                        self.assertTrue(output.samefile(source))
                    process = self.run_cli(cli, source, output)
                    self.assertEqual(2, process.returncode, process.stderr)
                    self.assertIn("output must not overwrite input", process.stderr)
                    self.assertEqual("", process.stdout)
                    self.assertEqual(before, source.read_bytes())

    def test_distinct_new_and_existing_outputs_keep_report_behavior(self):
        for cli in CLIS:
            for existing in (False, True):
                with self.subTest(cli=cli, existing=existing), tempfile.TemporaryDirectory(prefix="input guard ") as temp:
                    root = Path(temp)
                    source = self.make_input(root, cli)
                    before = source.read_bytes()
                    output = root / "nested output" / "report.json"
                    if existing:
                        output.parent.mkdir()
                        output.write_text("previous report", encoding="utf-8")
                    process = self.run_cli(cli, source, output)
                    self.assertEqual(0, process.returncode, process.stderr)
                    self.assertEqual("", process.stdout)
                    self.assertEqual(before, source.read_bytes())
                    payload = output.read_text(encoding="utf-8")
                    self.assert_expected_report(cli, payload)

    def test_omitted_output_keeps_stdout_json_and_preserves_input(self):
        for cli in CLIS:
            with self.subTest(cli=cli), tempfile.TemporaryDirectory(prefix="input guard ") as temp:
                source = self.make_input(Path(temp), cli)
                before = source.read_bytes()
                process = self.run_cli(cli, source)
                self.assertEqual(0, process.returncode, process.stderr)
                self.assertEqual(before, source.read_bytes())
                self.assert_expected_report(cli, process.stdout)

    def assert_expected_report(self, cli, payload):
        result = json.loads(payload)
        self.assertNotIn("SYNTHETIC_SECRET", payload)
        if cli == "analyze_logs.py":
            self.assertEqual(1, result["summary"]["eventCount"])
            self.assertEqual(1, result["summary"]["exceptionCount"])
        elif cli == "redact.py":
            self.assertEqual("token=[REDACTED] status=401", result["message"])
        else:
            self.assertTrue(result["valid"])
            self.assertEqual("trace-synthetic", result["plan"]["filters"]["traceId"])


if __name__ == "__main__":
    unittest.main()
