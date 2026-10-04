#!/usr/bin/env python3
"""Offline file-output contracts; no search backends, credentials or network."""

import contextlib
import errno
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(os.environ.get("MULTI_SEARCH_TEST_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / "scripts" / "cli"))
import main as cli
from errors import CliRuntimeError

WRITER = sys.modules[cli.write_output.__module__]
PRIVATE = "private-content-and-path"


class OutputIOContracts(unittest.TestCase):
    def run_cli(self, *arguments, cwd):
        return subprocess.run(
            [sys.executable, "-B", str(ROOT / "union_search_cli.py"), *arguments],
            cwd=cwd, text=True, capture_output=True, timeout=15,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def write(self, content, path):
        with contextlib.redirect_stdout(io.StringIO()) as stdout, \
             contextlib.redirect_stderr(io.StringIO()) as stderr:
            cli.write_output(content, path)
        return stdout.getvalue(), stderr.getvalue()

    def assert_error(self, result, forbidden):
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(str(forbidden), result.stderr)
        envelope = json.loads(result.stderr)
        self.assertFalse(envelope["success"])
        self.assertEqual(envelope["command"], "error")
        self.assertEqual(envelope["errors"][0]["code"], "CliRuntimeError")
        self.assertRegex(envelope["errors"][0]["detail"], r"^errno=[A-Z0-9]+$")

    def test_directory_target_error_in_all_formats(self):
        for fmt in ("json", "markdown", "text"):
            with self.subTest(fmt=fmt), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / PRIVATE
                target.mkdir()
                neighbor = target.with_suffix(".tmp")
                neighbor.write_text("other-owner", encoding="utf-8")
                before = set(root.iterdir())
                result = self.run_cli("list", "--format", fmt, "-o", str(target), cwd=root)
                self.assert_error(result, PRIVATE)
                self.assertTrue(target.is_dir())
                self.assertEqual(neighbor.read_text(encoding="utf-8"), "other-owner")
                self.assertEqual(set(root.iterdir()), before)

    def test_parent_file_error_preserves_content(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / PRIVATE
            parent.write_text("existing", encoding="utf-8")
            result = self.run_cli("list", "-o", str(parent / "result.json"), cwd=directory)
            self.assert_error(result, PRIVATE)
            self.assertEqual(parent.read_text(encoding="utf-8"), "existing")

    def test_stdout_formats_remain_available(self):
        for fmt, marker in (("json", '"success": true'),
                            ("markdown", "# CLI Result: `list`"), ("text", "success: True")):
            with self.subTest(fmt=fmt), tempfile.TemporaryDirectory() as directory:
                result = self.run_cli("list", "--format", fmt, cwd=directory)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stderr, "")
                self.assertIn(marker, result.stdout)

    def test_relative_file_output_preserves_formats_and_success_path(self):
        for fmt, marker in (("json", '"success": true'),
                            ("markdown", "# CLI Result: `list`"), ("text", "success: True")):
            with self.subTest(fmt=fmt), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "nested" / "output.txt"
                result = self.run_cli("list", "--format", fmt, "-o", "nested/output.txt", cwd=root)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                # macOS may resolve the /var alias in the process working directory.
                self.assertEqual(Path(result.stderr.strip()), target.resolve())
                self.assertIn(marker, target.read_text(encoding="utf-8"))
                self.assertEqual(list(target.parent.iterdir()), [target])

    def test_atomic_replace_preserves_other_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "result.json"
            neighbor = target.with_suffix(".json.tmp")
            target.write_text("old", encoding="utf-8")
            neighbor.write_text("other-owner", encoding="utf-8")
            stdout, stderr = self.write("新内容\n", str(target))
            self.assertEqual(stdout, "")
            self.assertEqual(stderr, str(target) + "\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "新内容\n")
            self.assertEqual(neighbor.read_text(encoding="utf-8"), "other-owner")
            self.assertEqual(set(root.iterdir()), {target, neighbor})

    def test_failed_replace_cleans_only_owned_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "result.json"
            neighbor = target.with_suffix(".json.tmp")
            target.write_text("old", encoding="utf-8")
            neighbor.write_text("other-owner", encoding="utf-8")
            with patch.object(WRITER.os, "replace", side_effect=OSError(errno.EACCES, PRIVATE)) as replace:
                with self.assertRaises(CliRuntimeError) as error:
                    self.write(PRIVATE, str(target))
            temporary, destination = map(Path, replace.call_args.args)
            self.assertEqual(temporary.parent, target.parent)
            self.assertNotEqual(temporary, neighbor)
            self.assertEqual(destination, target)
            self.assertEqual(error.exception.detail, "errno=EACCES")
            self.assertNotIn(PRIVATE, str(error.exception))
            self.assertEqual(target.read_text(encoding="utf-8"), "old")
            self.assertEqual(neighbor.read_text(encoding="utf-8"), "other-owner")
            self.assertEqual(set(root.iterdir()), {target, neighbor})

    def test_directory_creation_failure_is_runtime_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(Path, "mkdir", side_effect=OSError(errno.EACCES, PRIVATE)):
                with self.assertRaises(CliRuntimeError) as error:
                    self.write(PRIVATE, str(Path(directory) / "out"))
            self.assertEqual(error.exception.detail, "errno=EACCES")
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_temporary_creation_failure_is_runtime_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(tempfile, "NamedTemporaryFile", side_effect=OSError(errno.ENOSPC, PRIVATE)):
                with self.assertRaises(CliRuntimeError) as error:
                    self.write(PRIVATE, str(Path(directory) / "out"))
            self.assertEqual(error.exception.detail, "errno=ENOSPC")
            self.assertEqual(list(Path(directory).iterdir()), [])

    def failing_stream(self, error):
        real_open = tempfile.NamedTemporaryFile

        def open_stream(*args, **kwargs):
            stream = real_open(*args, **kwargs)
            stream.write = Mock(side_effect=error)
            return stream

        return patch.object(tempfile, "NamedTemporaryFile", side_effect=open_stream)

    def test_write_failure_cleans_temporary_and_preserves_target(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "out"
            target.write_text("old", encoding="utf-8")
            with self.failing_stream(OSError(errno.ENOSPC, PRIVATE)):
                with self.assertRaises(CliRuntimeError) as error:
                    self.write(PRIVATE, str(target))
            self.assertEqual(error.exception.detail, "errno=ENOSPC")
            self.assertEqual(target.read_text(encoding="utf-8"), "old")
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_cleanup_failure_does_not_replace_primary_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(WRITER.os, "replace", side_effect=OSError(errno.EACCES, PRIVATE)), \
                 patch.object(Path, "unlink", side_effect=OSError(errno.EBUSY, "cleanup-private")):
                with self.assertRaises(CliRuntimeError) as error:
                    self.write(PRIVATE, str(Path(directory) / "out"))
            self.assertEqual(error.exception.detail, "errno=EACCES; cleanup_errno=EBUSY")
            self.assertNotIn(PRIVATE, str(error.exception))
            self.assertNotIn("cleanup-private", str(error.exception))
            leftovers = list(Path(directory).iterdir())
            self.assertEqual(len(leftovers), 1)
            self.assertTrue(leftovers[0].name.startswith(".union-search-"))

    def test_main_reports_cleanup_errno_without_exposing_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / PRIVATE
            with patch.object(sys, "argv", ["cli", "list", "-o", str(target)]), \
                 patch.object(WRITER.os, "replace", side_effect=OSError(errno.ENOSPC, PRIVATE)), \
                 patch.object(Path, "unlink", side_effect=OSError(errno.EACCES, "cleanup-private")), \
                 contextlib.redirect_stdout(io.StringIO()) as stdout, \
                 contextlib.redirect_stderr(io.StringIO()) as stderr:
                status = cli.main()
            self.assertEqual(status, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertNotIn(directory, stderr.getvalue())
            self.assertNotIn(PRIVATE, stderr.getvalue())
            self.assertNotIn("cleanup-private", stderr.getvalue())
            envelope = json.loads(stderr.getvalue())
            self.assertFalse(envelope["success"])
            self.assertEqual(envelope["errors"][0]["code"], "CliRuntimeError")
            self.assertEqual(envelope["errors"][0]["detail"], "errno=ENOSPC; cleanup_errno=EACCES")
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_unknown_errno_is_stable_and_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(WRITER.os, "replace", side_effect=OSError(PRIVATE)):
                with self.assertRaises(CliRuntimeError) as error:
                    self.write(PRIVATE, str(Path(directory) / "out"))
            self.assertEqual(error.exception.detail, "errno=UNKNOWN")
            self.assertNotIn(PRIVATE, str(error.exception))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_non_io_errors_are_not_reclassified(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.failing_stream(ValueError("programming-error")):
                with self.assertRaisesRegex(ValueError, "programming-error"):
                    self.write(PRIVATE, str(Path(directory) / "out"))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_stdout_errors_are_not_file_write_errors(self):
        with patch("builtins.print", side_effect=BrokenPipeError(errno.EPIPE, "pipe-closed")):
            with self.assertRaises(BrokenPipeError):
                cli.write_output("content", None)

    def test_main_error_envelope_contains_only_stable_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / PRIVATE
            with patch.object(sys, "argv", ["cli", "list", "--format", "text", "-o", str(target)]), \
                 patch.object(WRITER.os, "replace", side_effect=OSError(errno.EACCES, PRIVATE, str(target))), \
                 contextlib.redirect_stdout(io.StringIO()) as stdout, \
                 contextlib.redirect_stderr(io.StringIO()) as stderr:
                status = cli.main()
            result = subprocess.CompletedProcess([], status, stdout.getvalue(), stderr.getvalue())
            self.assert_error(result, PRIVATE)
            self.assertNotIn(directory, result.stderr)
            self.assertEqual(json.loads(result.stderr)["errors"][0]["detail"], "errno=EACCES")
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
