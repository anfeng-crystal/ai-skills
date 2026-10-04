#!/usr/bin/env python3
"""Offline worker-count boundary checks with real parsing and thread pools."""

import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(os.environ.get("MULTI_SEARCH_TEST_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / "scripts" / "cli"))
sys.path.insert(1, str(ROOT / "scripts"))
import main as cli

union = importlib.import_module("union_search.union_search")


class NumericWorkers(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch("socket.socket", side_effect=AssertionError("network forbidden")))
        self.enterContext(patch("subprocess.run", side_effect=AssertionError("backend forbidden")))
        self.load_env = self.enterContext(patch.object(union, "load_env_file"))
        self.platform = self.enterContext(patch.object(
            union, "search_platform", return_value=("github", {
                "success": True, "total": 0, "items": [], "platform": "github",
            })))

    def invoke(self, *parts, script=None):
        with patch.object(sys, "argv", ["union_search_cli.py", *parts]), \
             contextlib.redirect_stdout(io.StringIO()) as out, \
             contextlib.redirect_stderr(io.StringIO()) as err:
            if script:
                try:
                    runpy.run_path(str(ROOT / script), run_name="__main__")
                except SystemExit as exc:
                    status = exc.code
            else:
                status = cli.main()
        return status, out.getvalue(), err.getvalue()

    def assert_usage_error(self, result):
        status, out, err = result
        self.assertEqual(status, 1)
        self.assertEqual(out, "")
        envelope = json.loads(err)
        self.assertFalse(envelope["success"])
        self.assertEqual(envelope["command"], "error")
        self.assertEqual(envelope["errors"][0]["code"], "CliUsageError")
        self.assertIn("--max-workers", envelope["errors"][0]["message"])
        self.assertIn("positive integer", envelope["errors"][0]["message"])
        self.assertNotIn("Traceback", err)
        self.load_env.assert_not_called()
        self.platform.assert_not_called()

    def test_nonpositive_workers_fail_before_environment_and_real_pool(self):
        for value in ("0", "-1", "-999"):
            with self.subTest(value=value):
                self.assert_usage_error(self.invoke(
                    "search", "query", "--platforms", "github", "--max-workers", value))

    def test_numeric_spellings_use_the_same_boundary(self):
        for value in ("+0", "-0", "000", "-0001"):
            with self.subTest(value=value), \
                 patch.object(cli, "run_search", return_value={"summary": {}}) as backend:
                self.assert_usage_error(self.invoke("search", "query", f"--max-workers={value}"))
                backend.assert_not_called()

    def test_usage_failure_preserves_output_targets_and_json_error_envelope(self):
        for fmt in ("json", "markdown", "text"):
            for exists in (False, True):
                path = Path(self.temp) / f"{fmt}-{exists}.json"
                if exists:
                    path.write_text("existing output", encoding="utf-8")
                with self.subTest(fmt=fmt, exists=exists), \
                     patch.object(cli, "run_search", return_value={"summary": {}}) as backend:
                    self.assert_usage_error(self.invoke(
                        "search", "query", "--max-workers", "0", "--format", fmt,
                        "--pretty", "--output", str(path)))
                    backend.assert_not_called()
                    self.assertEqual(path.exists(), exists)
                    if exists:
                        self.assertEqual(path.read_text(encoding="utf-8"), "existing output")

    def test_both_script_entrypoints_reject_nonpositive_workers(self):
        for script in ("scripts/cli/main.py", "union_search_cli.py"):
            for value in ("0", "-1"):
                with self.subTest(script=script, value=value):
                    self.assert_usage_error(self.invoke(
                        "search", "query", "--platforms", "github", "--max-workers", value,
                        script=script))

    def test_noninteger_syntax_keeps_argparse_exit_two(self):
        for value in ("bad", "1.5", "", "1e2"):
            with self.subTest(value=value), \
                 contextlib.redirect_stderr(io.StringIO()) as err, \
                 patch.object(sys, "argv", ["cli", "search", "query", "--max-workers", value]):
                with self.assertRaises(SystemExit) as status:
                    cli.parse_args()
                self.assertEqual(status.exception.code, 2)
                self.assertIn("--max-workers", err.getvalue())
                self.assertNotIn("Traceback", err.getvalue())
                self.load_env.assert_not_called()
                self.platform.assert_not_called()

    def test_default_and_positive_workers_reach_adapter_unchanged(self):
        for args, expected in (([], 5), (["--max-workers", "1"], 1),
                               (["--max-workers", "7"], 7), (["--max-workers=+2"], 2),
                               (["--max-workers", "001"], 1)):
            with self.subTest(args=args), \
                 patch.object(union, "union_search", return_value={"summary": {}}) as backend:
                self.load_env.reset_mock()
                status, out, err = self.invoke("search", "query", "--platforms", "github", *args)
                self.assertEqual(status, 0)
                self.assertTrue(json.loads(out)["success"])
                self.assertEqual(err, "")
                self.assertEqual(backend.call_args.kwargs["max_workers"], expected)
                self.assertEqual(backend.call_args.kwargs["platforms"], ["github"])
                self.load_env.assert_called_once_with(".env")

    def test_positive_workers_run_real_pool_with_offline_platform(self):
        for value in ("1", "2"):
            with self.subTest(value=value):
                self.load_env.reset_mock()
                self.platform.reset_mock()
                status, out, err = self.invoke(
                    "search", "query", "--platforms", "github", "--max-workers", value)
                self.assertEqual(status, 0)
                self.assertTrue(json.loads(out)["success"])
                self.assertEqual(json.loads(out)["data"]["summary"]["successful"], 1)
                self.assertEqual(err, "")
                self.load_env.assert_called_once()
                self.platform.assert_called_once()

    def test_last_option_wins_before_semantic_validation(self):
        with patch.object(cli, "run_search", return_value={"summary": {}}) as backend:
            status, out, err = self.invoke(
                "search", "query", "--max-workers", "0", "--max-workers", "2")
            self.assertEqual(status, 0)
            self.assertTrue(json.loads(out)["success"])
            self.assertEqual(err, "")
            self.assertEqual(backend.call_args.kwargs["max_workers"], 2)
            backend.reset_mock()
            self.assert_usage_error(self.invoke(
                "search", "query", "--max-workers", "2", "--max-workers", "0"))
            backend.assert_not_called()

    def test_positive_workers_preserve_successful_file_output(self):
        path = Path(self.temp) / "result.json"
        with patch.object(cli, "run_search", return_value={"summary": {}}):
            status, out, err = self.invoke(
                "search", "query", "--max-workers", "2", "--output", str(path))
        self.assertEqual(status, 0)
        self.assertEqual(out, "")
        self.assertTrue(json.loads(path.read_text(encoding="utf-8"))["success"])
        self.assertEqual(err.strip(), str(path))

    def test_image_and_download_nonpositive_limits_keep_their_contracts(self):
        for command, value in (("image", "0"), ("image", "-1"),
                               ("download", "0"), ("download", "-1")):
            with self.subTest(command=command, value=value), \
                 patch.object(cli, f"run_{command}", return_value={"success": True}) as backend:
                target = "query" if command == "image" else "https://example.invalid/media"
                status, out, err = self.invoke(command, target, "--limit", value)
                self.assertEqual(status, 0)
                self.assertTrue(json.loads(out)["success"])
                self.assertEqual(err, "")
                self.assertEqual(backend.call_args.kwargs["limit"], int(value))

    def test_unrelated_timeout_values_are_not_reinterpreted(self):
        for value in ("0", "-1"):
            with self.subTest(value=value), \
                 patch.object(cli, "run_search", return_value={"summary": {}}) as backend:
                status, out, err = self.invoke("search", "query", "--timeout", value)
                self.assertEqual(status, 0)
                self.assertTrue(json.loads(out)["success"])
                self.assertEqual(err, "")
                self.assertEqual(backend.call_args.kwargs["timeout"], int(value))

    def test_library_nonpositive_limits_remain_outside_cli_policy(self):
        for limit in (None, 0, -1):
            with self.subTest(limit=limit):
                self.platform.reset_mock()
                result = union.union_search("query", ["github"], limit=limit, max_workers=1)
                self.assertEqual(result["summary"]["successful"], 1)
                self.assertEqual(self.platform.call_args.args[2], limit)
                self.load_env.assert_not_called()


if __name__ == "__main__":
    unittest.main()
