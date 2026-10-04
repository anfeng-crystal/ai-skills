#!/usr/bin/env python3
"""Offline regressions for stable search-result selection during downloads."""
import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(os.environ.get("MULTI_SEARCH_TEST_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / "scripts" / "cli"))
sys.path.insert(1, str(ROOT / "scripts"))
import main as cli
from downloader import yt_dlp_downloader as downloader
union = importlib.import_module("union_search.union_search")


def candidates():
    return [
        {"index": 1, "platform": "bilibili", "title": "Bili", "url": "https://example.invalid/b1"},
        {"index": 2, "platform": "youtube", "title": "Chosen", "url": "https://example.invalid/y2"},
        {"index": 3, "platform": "youtube", "title": "Other", "url": "https://example.invalid/y3"},
    ]


def raw_results():
    return {"results": {
        "bilibili": {"items": [{"title": "Bili", "url": "https://example.invalid/b1"}]},
        "youtube": {"items": [{"title": "Chosen", "url": "https://example.invalid/y2"},
                               {"title": "Other", "url": "https://example.invalid/y3"}]},
    }}


class CandidateSelection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.enterContext(patch("socket.socket", side_effect=AssertionError("network forbidden")))
        self.enterContext(patch("subprocess.run", side_effect=AssertionError("backend forbidden")))
        self.env = self.enterContext(patch.object(downloader, "load_env_file"))

    def test_saved_indices_select_same_url_after_platform_filter(self):
        original = candidates()
        for wrapped in (False, True):
            payload = {"download_candidates": original}
            if wrapped:
                payload = {"data": payload}
            with self.subTest(wrapped=wrapped):
                selected = downloader.build_download_candidates(payload, platforms=["youtube"], select="2")
                self.assertEqual(selected, [original[1]])
        self.assertEqual(original, candidates())

    def test_platform_filter_keeps_displayed_indices_without_selection(self):
        original = candidates()
        selected = downloader.build_download_candidates(
            {"download_candidates": original}, platforms=["youtube"])
        self.assertEqual(selected, original[1:])

    def test_existing_noncontiguous_indices_survive_round_trip(self):
        original = candidates()[1:]
        original[0]["index"] = 7
        original[1]["index"] = 11
        self.assertEqual(downloader.build_download_candidates(
            {"download_candidates": original}, select="11"), [original[1]])
        self.assertEqual(downloader.build_download_candidates(
            {"download_candidates": original}), original)

    def test_missing_indices_use_unfiltered_unique_url_order(self):
        original = candidates()
        payload = {"download_candidates": [{k: v for k, v in item.items() if k != "index"}
                                           for item in original]}
        self.assertEqual(downloader.build_download_candidates(payload), original)
        self.assertEqual(downloader.build_download_candidates(
            payload, platforms=["youtube"], select="2"), [original[1]])

    def test_raw_results_have_same_selection_as_generated_search_candidates(self):
        original = candidates()
        for wrapped in (False, True):
            payload = raw_results()
            if wrapped:
                payload = {"data": payload}
            with self.subTest(wrapped=wrapped):
                self.assertEqual(downloader.build_download_candidates(payload), original)
                self.assertEqual(downloader.build_download_candidates(
                    payload, platforms=["youtube"], select="2"), [original[1]])

    def test_final_items_keep_global_indices_and_platform_url_fallbacks(self):
        payload = {"final_items": [
            {"platform": "bilibili", "data": {"bvid": "BVfixture", "title": "Bili"}},
            {"platform": "youtube", "data": {"video_id": "fixture", "title": "Chosen"}},
            {"platform": "douyin", "data": {"video_info": {"aweme_id": "123", "title": "Video"}}},
        ]}
        all_items = downloader.build_download_candidates(payload)
        self.assertEqual([c["url"] for c in all_items], [
            "https://www.bilibili.com/video/BVfixture",
            "https://www.youtube.com/watch?v=fixture", "https://www.douyin.com/video/123"])
        self.assertEqual(downloader.build_download_candidates(
            payload, platforms=["youtube"], select="2"), [all_items[1]])

    def test_filter_selection_and_limit_do_not_renumber_or_expand_scope(self):
        original = candidates()
        payload = {"download_candidates": original}
        self.assertEqual(downloader.build_download_candidates(
            payload, platforms=["youtube"], select="1"), [])
        for limit in (None, 0, -1):
            with self.subTest(limit=limit):
                self.assertEqual(downloader.build_download_candidates(
                    payload, platforms=["youtube"], select="3,2,3", limit=limit), original[1:])
        self.assertEqual(downloader.build_download_candidates(
            payload, platforms=["youtube"], select="3,2", limit=1), [original[1]])

    def test_normalization_and_filtered_duplicate_url_remain_supported(self):
        raw = {"results": {
            "bilibili": {"items": [{"url": "https://example.invalid/shared", "title": "Bili"}]},
            "youtube": {"items": [{"url": " https://example.invalid/shared ", "title": " YouTube "},
                                   {"url": "https://example.invalid/shared", "title": "Duplicate"},
                                   {"url": "", "title": "Empty"}]}}}
        for payload in (raw, {"download_candidates": [
                {"platform": "bilibili", "url": "https://example.invalid/shared", "title": "Bili"},
                {"platform": "youtube", "url": " https://example.invalid/shared ", "title": " YouTube "},
                {"platform": "youtube", "url": "https://example.invalid/shared", "title": "Duplicate"},
                {"platform": "youtube", "url": "", "title": "Empty"}]}):
            with self.subTest(payload=payload):
                selected = downloader.build_download_candidates(payload, platforms=["youtube"])
                self.assertEqual(selected, [{"index": 1, "platform": "youtube", "title": "YouTube",
                                             "url": "https://example.invalid/shared"}])

    def test_invalid_selection_keeps_existing_validation(self):
        for select in ("0", "-1", "two", "1.5"):
            with self.subTest(select=select), self.assertRaises(ValueError):
                downloader.build_download_candidates({"download_candidates": candidates()}, select=select)
        self.assertEqual(downloader.build_download_candidates(
            {"download_candidates": candidates()}, select=" , "), [])

    def test_utf8_bom_file_preserves_saved_candidate_indices(self):
        path = Path(self.temp.name) / "search.json"
        payload = {"data": {"download_candidates": candidates()}}
        path.write_text(json.dumps(payload), encoding="utf-8-sig")
        self.assertEqual(downloader.collect_urls_from_search_output(
            str(path), platforms=["youtube"], select="2"), [candidates()[1]])
        self.assertEqual(json.loads(path.read_text(encoding="utf-8-sig")), payload)

    def test_cli_search_to_download_selects_displayed_candidate(self):
        path = Path(self.temp.name) / "search.json"
        result = {**raw_results(), "summary": {"failed": 0}, "platforms": ["bilibili", "youtube"]}
        with patch.object(union, "load_env_file"), \
             patch.object(union, "union_search", return_value=result), \
             patch.object(sys, "argv", ["union_search_cli.py", "search", "fixture", "--platforms",
                                       "bilibili", "youtube", "-o", str(path)]), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(), 0)
        displayed = json.loads(path.read_text())["data"]["download_candidates"]
        self.assertEqual(displayed, candidates())
        with patch.object(downloader, "run_yt_dlp_download", return_value={"success": True}) as backend, \
             patch.object(sys, "argv", ["union_search_cli.py", "download", "--from-file", str(path),
                                       "--platforms", "youtube", "--select", "2", "--dry-run"]), \
             contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(), 0)
        envelope = json.loads(stdout.getvalue())
        self.assertTrue(envelope["success"])
        self.assertEqual(envelope["data"]["candidates"], [displayed[1]])
        self.assertEqual(envelope["data"]["resolved_urls"], [displayed[1]["url"]])
        self.assertEqual(backend.call_args.kwargs["urls"], [displayed[1]["url"]])
        self.assertIs(backend.call_args.kwargs["dry_run"], True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
