#!/usr/bin/env python3
"""Explicit platform selections cannot silently become default/all-platform work."""

import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(os.environ.get("MULTI_SEARCH_TEST_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / "scripts" / "cli"))
sys.path.insert(1, str(ROOT / "scripts"))
import main as cli
from errors import CliUsageError
from validators import validate_platforms

union = importlib.import_module("union_search.union_search")


class PlatformSelection(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("socket.socket", side_effect=AssertionError("network forbidden")))
        self.enterContext(patch("subprocess.run", side_effect=AssertionError("backend forbidden")))
        self.load_env = self.enterContext(patch.object(union, "load_env_file"))

    def invoke(self, *args):
        with patch.object(sys, "argv", ["union_search_cli.py", *args]), \
             contextlib.redirect_stdout(io.StringIO()) as out, \
             contextlib.redirect_stderr(io.StringIO()) as err:
            status = cli.main()
        return status, out.getvalue(), err.getvalue()

    def test_empty_explicit_iterables_fail(self):
        for values in ([], [""], [" "], ["\t", "\n"], ["\u3000"]):
            with self.subTest(values=values), self.assertRaises(CliUsageError):
                validate_platforms(iter(values), ["github"])

    def test_known_platform_normalization_and_order_preserved(self):
        self.assertEqual(validate_platforms([" github ", "", "reddit", "github"],
                                            ["github", "reddit"]),
                         ["github", "reddit", "github"])

    def test_unknown_platform_is_still_rejected(self):
        with self.assertRaisesRegex(CliUsageError, "Unknown platforms"):
            validate_platforms([" ", "unknown"], ["github"])

    def test_blank_search_never_enters_adapter_or_group(self):
        for blank in ("", " ", "\t", "\u3000"):
            for group in ([], ["--group", "all"]):
                with self.subTest(blank=blank, group=group), \
                     patch.object(cli, "run_search", return_value={"summary": {}}) as backend:
                    status, out, err = self.invoke("search", "query", "--platforms", blank, *group)
                    self.assertEqual(status, 1)
                    self.assertEqual(out, "")
                    self.assertFalse(json.loads(err)["success"])
                    self.assertEqual(json.loads(err)["errors"][0]["code"], "CliUsageError")
                    backend.assert_not_called()
                    self.load_env.assert_not_called()

    def test_blank_image_never_enters_adapter(self):
        with patch.object(cli, "run_image", return_value={"summary": {}}) as backend:
            status, out, err = self.invoke("image", "query", "--platforms", " ")
        self.assertEqual(status, 1)
        self.assertEqual(out, "")
        self.assertEqual(json.loads(err)["errors"][0]["code"], "CliUsageError")
        backend.assert_not_called()

    def test_blank_single_platform_has_structured_error(self):
        with patch.object(cli, "run_platform", return_value={"success": True}) as backend:
            status, out, err = self.invoke("platform", " ", "query")
        self.assertEqual(status, 1)
        self.assertEqual(out, "")
        self.assertEqual(json.loads(err)["errors"][0]["code"], "CliUsageError")
        backend.assert_not_called()

    def test_blank_doctor_fails_before_environment_or_dependency_work(self):
        with patch("shutil.which", side_effect=AssertionError("dependency probe forbidden")):
            status, out, err = self.invoke("doctor", "--platforms", " ")
        self.assertEqual(status, 1)
        self.assertEqual(out, "")
        self.assertEqual(json.loads(err)["errors"][0]["code"], "CliUsageError")
        self.load_env.assert_not_called()

    def test_omitted_search_platforms_still_pass_none(self):
        with patch.object(cli, "run_search", return_value={"summary": {}}) as backend:
            status, out, err = self.invoke("search", "query")
        self.assertEqual(status, 0)
        self.assertTrue(json.loads(out)["success"])
        self.assertEqual(err, "")
        self.assertIsNone(backend.call_args.kwargs["platforms"])

    def test_omitted_images_keep_default_and_unlimited_semantics(self):
        with patch.object(cli, "run_image", return_value={"summary": {}}) as backend:
            status, out, err = self.invoke("image", "query", "--limit", "0")
        self.assertEqual(status, 0)
        self.assertTrue(json.loads(out)["success"])
        self.assertEqual(err, "")
        self.assertIsNone(backend.call_args.kwargs["platforms"])
        self.assertEqual(backend.call_args.kwargs["limit"], 0)

    def test_mixed_blanks_valid_platforms_preserve_selection(self):
        with patch.object(cli, "run_search", return_value={"summary": {}}) as backend:
            status, out, err = self.invoke("search", "query", "--platforms", " ", " github ",
                                          "", "reddit", "--group", "all")
        self.assertEqual(status, 0)
        self.assertTrue(json.loads(out)["success"])
        self.assertEqual(err, "")
        self.assertEqual(backend.call_args.kwargs["platforms"], ["github", "reddit"])


if __name__ == "__main__":
    unittest.main()
