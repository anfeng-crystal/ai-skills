#!/usr/bin/env python3
"""Offline CLI contracts; never load credentials, spawn backends, or use network."""
import contextlib
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(os.environ.get("MULTI_SEARCH_TEST_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / "scripts" / "cli"))
sys.path.insert(1, str(ROOT / "scripts"))
import adapters
import main as cli
import registry
import validators
from errors import CliUsageError
from output import render_output
from downloader.yt_dlp_downloader import build_download_candidates
union = importlib.import_module("union_search.union_search")


class Contracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        old_cwd = Path.cwd()
        os.chdir(self.temp.name)
        self.addCleanup(os.chdir, old_cwd)
        self.enterContext(patch.dict(os.environ, {"HOME": self.temp.name, "USERPROFILE": self.temp.name}, clear=True))
        self.enterContext(patch("socket.socket", side_effect=AssertionError("network forbidden")))
        self.enterContext(patch("subprocess.run", side_effect=AssertionError("backend forbidden")))
        self.load_env = self.enterContext(patch.object(union, "load_env_file"))

    def args(self, *parts):
        with patch.object(sys, "argv", ["union_search_cli.py", *parts]):
            return cli.parse_args()

    def search(self, platforms=None, group=None, limit=None):
        return adapters.run_search("query", platforms, group, limit, 2, 30, False, "missing.env")

    def image_module(self):
        # pyimagedl is never imported: only the coordinator's selection logic runs.
        fake = types.ModuleType("imagedl")
        fake.imagedl = object()
        with patch.dict(sys.modules, {"imagedl": fake}):
            spec = importlib.util.spec_from_file_location(
                "offline_images", ROOT / "scripts/union_image_search/multi_platform_image_search.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod

    def test_text_nonpositive_limits_rejected_before_backend(self):
        commands = [("search", "query"), ("platform", "github", "query"),
                    ("github", "query"), ("gsearch", "query"), ("bsearch", "query")]
        with patch.object(union, "union_search", return_value={"summary": {}}) as aggregate, \
             patch.object(union, "search_platform", return_value=("github", {"success": True})) as single:
            for command in commands:
                for limit in ("0", "-1"):
                    with self.subTest(command=command, limit=limit):
                        with self.assertRaises(CliUsageError):
                            cli.dispatch(self.args(*command, "--limit", limit))
            aggregate.assert_not_called()
            single.assert_not_called()
            self.load_env.assert_not_called()

    def test_limit_precedence_and_presets_preserved(self):
        self.assertIsNone(validators.resolve_limit(None, None))
        for preset, count in {"small": 3, "medium": 5, "large": 10, "extra": 20}.items():
            self.assertEqual(validators.resolve_limit(None, preset), count)
        self.assertEqual(validators.resolve_limit(7, "small"), 7)

    def test_search_default_uses_free_group(self):
        with patch.object(union, "union_search", return_value={"summary": {}}) as backend:
            self.search()
        self.assertEqual(backend.call_args.kwargs["platforms"], union.PLATFORM_GROUPS["no_api_key_fast"])

    def test_explicit_search_groups_and_platforms_preserved(self):
        for group in union.PLATFORM_GROUPS:
            with self.subTest(group=group), \
                 patch.object(union, "union_search", return_value={"summary": {}}) as backend:
                self.search(group=group, limit=5)
                self.assertEqual(backend.call_args.kwargs["platforms"], union.PLATFORM_GROUPS[group])
                self.assertEqual(backend.call_args.kwargs["limit"], 5)
        with patch.object(union, "union_search", return_value={"summary": {}}) as backend:
            self.search(platforms=["tavily"], group="no_api_key_fast")
        self.assertEqual(backend.call_args.kwargs["platforms"], ["tavily"])

    def legacy_search(self, *parts):
        result = {"summary": {"successful": 0, "failed": 0, "total_platforms": 0,
                              "total_items": 0}, "results": {}, "final_items": []}
        with patch.object(sys, "argv", ["union_search.py", "query", "--json", *parts]), \
             patch.object(union, "SearchLogger"), \
             patch.object(union, "union_search", return_value=result) as backend, \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(union.main(), 0)
        return backend.call_args.kwargs

    def test_legacy_invalid_numeric_arguments_fail_before_side_effects(self):
        result = {"summary": {"successful": 0, "failed": 0, "total_platforms": 0,
                              "total_items": 0}, "results": {}, "final_items": []}
        for option in ("--limit", "--max-workers", "--timeout", "--read-timeout"):
            command = ["--read-url", "https://example.invalid"] if option == "--read-timeout" else ["query"]
            for value in ("0", "-1", "bad", "1.5"):
                self.load_env.reset_mock()
                with self.subTest(option=option, value=value), \
                     patch.object(sys, "argv", ["union_search.py", *command, option, value, "--json"]), \
                     patch.object(union, "SearchLogger") as logger, \
                     patch.object(union, "union_search", return_value=result) as backend, \
                     patch.dict(sys.modules, {"url_to_markdown": None}), \
                     contextlib.redirect_stdout(io.StringIO()) as stdout, \
                     contextlib.redirect_stderr(io.StringIO()) as stderr:
                    with self.assertRaises(SystemExit) as status:
                        union.main()
                    self.assertEqual(status.exception.code, 2)
                    self.assertIn(option, stderr.getvalue())
                    self.assertNotIn("Traceback", stderr.getvalue())
                    self.assertEqual(stdout.getvalue(), "")
                    logger.assert_not_called()
                    backend.assert_not_called()
                    self.load_env.assert_not_called()

    def test_legacy_positive_numeric_values_and_defaults_preserved(self):
        with patch.object(sys, "argv", ["union_search.py", "query"]):
            args = union.parse_args()
        self.assertIsNone(args.limit)
        self.assertEqual((args.max_workers, args.timeout, args.read_timeout), (5, 60, 30))
        with patch.object(sys, "argv", ["union_search.py", "query", "--limit", "1",
                                        "--max-workers", "2", "--timeout", "3", "--read-timeout", "4"]):
            args = union.parse_args()
        self.assertEqual((args.limit, args.max_workers, args.timeout, args.read_timeout), (1, 2, 3, 4))
        actual = self.legacy_search("--limit", "1", "--max-workers", "2", "--timeout", "3")
        self.assertEqual((actual["limit"], actual["max_workers"], actual["timeout"]), (1, 2, 3))

    def test_legacy_direct_script_rejects_nonpositive_limit(self):
        status, stdout, stderr = self.run_direct("query", "--limit", "0")
        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn("--limit", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_legacy_default_uses_free_group(self):
        actual = self.legacy_search()
        self.assertEqual(actual["platforms"], union.PLATFORM_GROUPS["no_api_key_fast"])
        self.assertIsNone(actual["limit"])

    def test_legacy_explicit_sources_preserve_all_and_platform_priority(self):
        for group, platforms in union.PLATFORM_GROUPS.items():
            with self.subTest(group=group):
                actual = self.legacy_search("--group", group, "--limit", "3")
                self.assertEqual(actual["platforms"], platforms)
                self.assertEqual(actual["limit"], 3)
        actual = self.legacy_search("--platforms", "tavily", "--group", "no_api_key_fast")
        self.assertEqual(actual["platforms"], ["tavily"])

    def test_legacy_direct_help_starts_without_backend_or_credentials(self):
        script = ROOT / "scripts/union_search/union_search.py"
        # run_path does not add the script directory like `python script.py` does.
        with patch.object(sys, "path", [str(script.parent), *sys.path]), \
             patch.object(sys, "argv", [str(script), "--help"]), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as status:
                runpy.run_path(str(script), run_name="__main__")
        self.assertEqual(status.exception.code, 0)
        self.assertIn("no_api_key_fast", output.getvalue())
        self.load_env.assert_not_called()

    def test_legacy_nonsearch_commands_do_not_initialize_logs_or_environment(self):
        for command, expected in ((["--list-platforms"], 0), ([], 1),
                                  (["query", "--platforms", "missing"], 1)):
            self.load_env.reset_mock()
            with self.subTest(command=command), \
                 patch.object(sys, "argv", ["union_search.py", *command]), \
                 patch.object(union, "SearchLogger", side_effect=PermissionError("private")) as log, \
                 patch.object(union, "union_search") as backend, \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(union.main(), expected)
                log.assert_not_called()
                backend.assert_not_called()
                self.load_env.assert_not_called()

    def test_legacy_log_io_failure_preserves_json_and_file_results(self):
        result = {"summary": {"successful": 1, "failed": 0, "total_platforms": 1,
                              "total_items": 1}, "results": {},
                  "final_items": [{"title": "Offline", "url": "https://example.invalid"}]}
        for stage in ("init", "write"):
            for save in (False, True):
                output_path = Path(self.temp.name) / "result.json"
                args = ["query", "--json", *(["-o", str(output_path)] if save else [])]
                with self.subTest(stage=stage, save=save), \
                     patch.object(sys, "argv", ["union_search.py", *args]), \
                     patch.object(union, "SearchLogger") as log, \
                     patch.object(union, "union_search", return_value=result) as backend, \
                     contextlib.redirect_stdout(io.StringIO()) as stdout, \
                     contextlib.redirect_stderr(io.StringIO()) as stderr:
                    if stage == "init":
                        log.side_effect = PermissionError(13, "private-log-detail")
                    else:
                        log.return_value.log_union_search.side_effect = OSError(28, "private-log-detail")
                    self.assertEqual(union.main(), 0)
                    backend.assert_called_once()
                    content = output_path.read_text() if save else stdout.getvalue()
                    self.assertEqual(json.loads(content), result)
                    if save:
                        self.assertEqual(stdout.getvalue(), "")
                    self.assertIn("搜索日志未保存", stderr.getvalue())
                    self.assertNotIn("private-log-detail", stderr.getvalue())

    def test_legacy_environment_failure_stops_before_backend_and_hides_values(self):
        for error in (PermissionError(13, "private-value"), UnicodeError("private-value"),
                      ValueError("private-value")):
            with self.subTest(error=type(error).__name__), \
                 patch.object(sys, "argv", ["union_search.py", "query", "--json"]), \
                 patch.object(union, "load_env_file", side_effect=error), \
                 patch.object(union, "SearchLogger") as log, \
                 patch.object(union, "union_search") as backend, \
                 contextlib.redirect_stdout(io.StringIO()) as stdout, \
                 contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(union.main(), 1)
                backend.assert_not_called()
                log.assert_not_called()
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn(type(error).__name__, stderr.getvalue())
                self.assertNotIn("private-value", stderr.getvalue())

    def test_legacy_url_environment_failure_never_creates_reader_or_logs(self):
        module = types.ModuleType("url_to_markdown")
        module.UrlToMarkdown = unittest.mock.MagicMock()
        with patch.dict(sys.modules, {"url_to_markdown": module}), \
             patch.object(sys, "argv", ["union_search.py", "--read-url", "https://example.invalid"]), \
             patch.object(union, "load_env_file", side_effect=UnicodeError("private-value")), \
             patch.object(union, "SearchLogger") as log, \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(union.main(), 1)
        module.UrlToMarkdown.assert_not_called()
        log.assert_not_called()

    def test_legacy_url_import_configuration_failure_is_controlled_and_redacted(self):
        import builtins
        original_import = builtins.__import__

        def guarded(name, *args, **kwargs):
            if name == "url_to_markdown":
                raise UnicodeDecodeError("utf-8", b"private-value", 0, 1, "private-value")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=guarded), \
             patch.object(sys, "argv", ["union_search.py", "--read-url", "https://example.invalid"]), \
             patch.object(union, "SearchLogger") as log, \
             contextlib.redirect_stdout(io.StringIO()) as stdout, \
             contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(union.main(), 1)
        log.assert_not_called()
        self.load_env.assert_not_called()
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("URL读取模块初始化失败", stderr.getvalue())
        self.assertIn("UnicodeDecodeError", stderr.getvalue())
        self.assertNotIn("private-value", stderr.getvalue())

    def test_legacy_successful_log_preserves_query_results_and_metadata(self):
        result = {"summary": {"successful": 1, "failed": 0, "total_platforms": 1,
                              "total_items": 1}, "results": {"github": {"success": True,
                              "total": 1, "timing_ms": 3}}, "final_items": [{"title": "Offline"}]}
        with patch.object(sys, "argv", ["union_search.py", "query", "--json"]), \
             patch.object(union, "SearchLogger") as log, \
             patch.object(union, "union_search", return_value=result), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(union.main(), 0)
        log.assert_called_once_with(verbose=False)
        payload = log.return_value.log_union_search.call_args.kwargs
        self.assertEqual(payload["query"], "query")
        self.assertEqual(payload["results"], result["final_items"])
        self.assertEqual(payload["metadata"]["status"], "success")
        self.assertEqual(payload["metadata"]["platform_details"], [{"platform": "github",
                         "status": "success", "items": 1, "timing_ms": 3, "error": None}])

    def test_failed_default_sources_never_fall_back_to_paid_platform(self):
        platforms = union.PLATFORM_GROUPS["no_api_key_fast"]
        with patch.object(union, "_run_platform_json_command", side_effect=RuntimeError("offline blocked")) as command:
            for platform in platforms:
                with self.subTest(platform=platform):
                    _, result = union.search_platform(platform, "query", 3)
                    self.assertFalse(result["success"])
                    self.assertEqual(result["error"], "offline blocked")
                    call = command.call_args
                    self.assertEqual(call.kwargs["platform"], platform)
                    self.assertEqual(Path(call.args[0][1]).name, union.DIRECT_NO_API_SCRIPT_MAP[platform][1])
        self.assertEqual(command.call_count, len(platforms))

    def run_direct(self, *args):
        script = ROOT / "scripts/union_search/union_search.py"
        empty_env = Path(self.temp.name) / "isolated.env"
        empty_env.write_text("", encoding="utf-8")
        log_module = types.ModuleType("search_logger")
        log_module.SearchLogger = lambda **kwargs: types.SimpleNamespace(
            log_union_search=lambda **kwargs: "offline-log")
        with patch.object(sys, "path", [str(script.parent), *sys.path]), \
             patch.object(sys, "argv", [str(script), *args, "--env-file", str(empty_env)]), \
             patch.dict(sys.modules, {"search_logger": log_module}), \
             contextlib.redirect_stdout(io.StringIO()) as stdout, \
             contextlib.redirect_stderr(io.StringIO()) as stderr:
            with self.assertRaises(SystemExit) as status:
                runpy.run_path(str(script), run_name="__main__")
        return status.exception.code, stdout.getvalue(), stderr.getvalue()

    def test_direct_read_url_loads_optional_client_and_preserves_output(self):
        module = types.ModuleType("url_to_markdown")
        calls = []

        class FakeReader:
            def __init__(self, timeout):
                calls.append(timeout)

            def fetch(self, url):
                calls.append(url)
                return {"url": url, "title": "Offline", "content": "fixture"}

        module.UrlToMarkdown = FakeReader
        with patch.dict(sys.modules, {"url_to_markdown": module}):
            status, stdout, _ = self.run_direct("--read-url", "https://example.invalid", "--read-timeout", "9", "--json")
        self.assertEqual(status, 0)
        self.assertEqual(calls, [9, "https://example.invalid"])
        self.assertEqual(json.loads(stdout), {"url": "https://example.invalid", "title": "Offline", "content": "fixture"})

    def test_direct_read_url_missing_optional_module_reports_failure(self):
        with patch.dict(sys.modules, {"url_to_markdown": None}):
            status, stdout, stderr = self.run_direct("--read-url", "https://example.invalid")
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertIn("url_to_markdown", stderr)

    def test_direct_help_does_not_import_optional_reader(self):
        import builtins
        original = builtins.__import__

        def guarded(name, *args, **kwargs):
            if name == "url_to_markdown":
                self.fail("help must not import optional reader or load its environment")
            return original(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=guarded):
            status, stdout, _ = self.run_direct("--help")
        self.assertEqual(status, 0)
        self.assertIn("no_api_key_fast", stdout)

    def test_image_default_excludes_paid_api_and_metadata_matches(self):
        reply = types.SimpleNamespace(returncode=0, stdout='{"summary":{"failed":0}}', stderr="")
        with patch.object(adapters.subprocess, "run", return_value=reply) as process:
            result = cli.dispatch(self.args("image", "cats"))
        cmd = process.call_args.args[0]
        self.assertIn("--platforms", cmd)
        selected = cmd[cmd.index("--platforms") + 1:]
        self.assertEqual(selected, [p for p in registry.IMAGE_PLATFORMS if p != "volcengine"])
        self.assertEqual(result["meta"]["selected_image_platforms"], selected)

    def test_image_nonpositive_limits_and_explicit_paid_route_preserved(self):
        reply = types.SimpleNamespace(returncode=0, stdout='{"summary":{"failed":0}}', stderr="")
        for limit in ("0", "-1", "5"):
            with self.subTest(limit=limit), patch.object(adapters.subprocess, "run", return_value=reply) as process:
                cli.dispatch(self.args("image", "cats", "--limit", limit, "--platforms", "volcengine"))
                cmd = process.call_args.args[0]
                self.assertEqual(cmd[cmd.index("--num") + 1], limit)
                self.assertEqual(cmd[cmd.index("--platforms") + 1:], ["volcengine"])

    def test_standalone_image_default_and_explicit_selection(self):
        mod = self.image_module()
        for selected in (None, ["volcengine"]):
            with self.subTest(selected=selected), \
                 patch.object(mod, "search_platform", return_value={}) as backend, \
                 contextlib.redirect_stdout(io.StringIO()):
                mod.search_all_platforms("cats", 0, selected, self.temp.name, 1, False, 0)
                actual = [call.args[0] for call in backend.call_args_list]
                expected = selected or [p for p in registry.IMAGE_PLATFORMS if p != "volcengine"]
                self.assertEqual(actual, expected)

    def test_registry_paid_api_requirements(self):
        caps = {cap.name: cap for cap in registry.load_capabilities()}
        self.assertEqual(caps["exa"].required_env, ("EXA_API_KEY",))
        self.assertEqual(caps["serper"].required_env, ("SERPER_API_KEY",))
        for platform in union.PLATFORM_GROUPS["no_api_key"]:
            self.assertEqual(caps[platform].required_env, (), platform)

    def test_doctor_warns_for_missing_paid_credentials_without_reading_values(self):
        fake_deps = {name: types.ModuleType(name) for name in (
            "requests", "dotenv", "lxml", "pygments", "feedparser", "loguru", "pydantic", "firecrawl", "imagedl")}
        with patch.dict(sys.modules, fake_deps), patch("shutil.which", return_value=None):
            result = cli.dispatch(self.args("doctor", "--platforms", "exa", "serper", "--env-file", "missing.env"))
        checks = {item["platform"]: item for item in result["data"]["platforms"]}
        self.assertEqual(set(checks), {"exa", "serper"})
        self.assertEqual(checks["exa"]["status"], "warn")
        self.assertIn("EXA_API_KEY", checks["exa"]["message"])
        self.assertEqual(checks["serper"]["status"], "warn")
        self.assertIn("SERPER_API_KEY", checks["serper"]["message"])

    def test_single_platform_positive_limit_and_passthrough_preserved(self):
        with patch.object(union, "search_platform", return_value=("google", {"success": True})) as backend:
            result = cli.dispatch(self.args("gsearch", "old", "--query", "new", "--limit", "3",
                                            "--param", "lang=zh", "--param", "safe=true"))
        self.assertTrue(result["success"])
        self.assertEqual(backend.call_args.kwargs["keyword"], "new")
        self.assertEqual(backend.call_args.kwargs["limit"], 3)
        self.assertEqual(backend.call_args.kwargs["lang"], "zh")
        self.assertIs(backend.call_args.kwargs["safe"], True)

    def test_download_nonpositive_limit_contract_preserved(self):
        data = {"download_candidates": [
            {"platform": "youtube", "url": "https://example.test/a", "index": 1},
            {"platform": "youtube", "url": "https://example.test/b", "index": 2}]}
        for limit in (None, 0, -1):
            self.assertEqual(len(build_download_candidates(data, limit=limit)), 2)
        self.assertEqual(len(build_download_candidates(data, limit=1)), 1)

    def test_defuddle_explicit_url_overrides_positional_and_preserves_single_inputs(self):
        old_url = "https://old.example.invalid/original"
        new_url = "https://new.example.invalid/replacement"
        cases = [([old_url], old_url), (["--url", new_url], new_url),
                 ([old_url, "--url", new_url], new_url),
                 (["--url", new_url, old_url], new_url)]
        module = types.ModuleType("url_to_markdown.engines.defuddle_engine")
        for arguments, expected in cases:
            for json_output in (False, True):
                module.DefuddleEngine = unittest.mock.MagicMock()
                module.DefuddleEngine.return_value.fetch.return_value = {"content": "offline"}
                extra = ["--json"] if json_output else []
                with self.subTest(arguments=arguments, json_output=json_output), \
                     patch.dict(sys.modules, {module.__name__: module}), \
                     patch.object(sys, "argv", ["union_search_cli.py", "defuddle", *arguments,
                                               "--timeout", "7", *extra]), \
                     contextlib.redirect_stdout(io.StringIO()) as stdout, \
                     contextlib.redirect_stderr(io.StringIO()) as stderr:
                    self.assertEqual(cli.main(), 0)
                    result = json.loads(stdout.getvalue())
                    module.DefuddleEngine.assert_called_once_with(timeout=7)
                    module.DefuddleEngine.return_value.fetch.assert_called_once_with(
                        url=expected, markdown=True, json_output=json_output, timeout=7)
                    self.assertEqual((result["query"], result["meta"]["url"]), (expected, expected))
                    self.assertTrue(result["success"])
                    self.assertEqual(result["command"], "defuddle")
                    self.assertEqual(result["data"]["content"], "offline")
                    self.assertEqual(stderr.getvalue(), "")
        self.load_env.assert_not_called()

    def test_list_formats_and_direct_aliases_preserved(self):
        for fmt in ("json", "markdown", "text"):
            args = self.args("list", "--format", fmt)
            data = cli.dispatch(args)
            self.assertTrue(data["success"])
            self.assertEqual(args.format, fmt)
            rendered = render_output({"command": "list", **data}, fmt=fmt, pretty=False)
            self.assertIsInstance(rendered, str)
            self.assertIn("list", rendered)
            if fmt == "json":
                self.assertTrue(json.loads(rendered)["success"])
        for command, platform in (("gsearch", "google"), ("bsearch", "bing")):
            self.assertEqual(self.args(command, "query").platform_command, platform)


if __name__ == "__main__":
    unittest.main(verbosity=2)
