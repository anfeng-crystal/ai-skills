"""Synthetic-only fixtures shared by the offline KCS CLI tests."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import kcs_ops  # noqa: E402


class MockResponse:
    def __init__(self, value, status=200, content_type="application/json"):
        self.raw = value if isinstance(value, bytes) else json.dumps(value).encode("utf-8")
        self.status = status
        self.headers = {"Content-Type": content_type}

    def read(self, limit):
        return self.raw[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


class MockKcsOpener:
    """No fallback transport: unconfigured destinations fail immediately."""

    def __init__(self):
        self.get_count = 0
        self.post_count = 0
        self.last_cookie = None
        self.last_form = None
        self.responses = []
        self.requests = []

    def open(self, request, timeout):
        parsed = urlsplit(request.full_url)
        if parsed.scheme != "https" or parsed.netloc != "kcs.example.invalid":
            raise AssertionError("unconfigured mock destination")
        self.requests.append(request)
        self.last_cookie = request.get_header("Cookie")
        method = request.get_method()
        if method == "GET":
            self.get_count += 1
        elif method == "POST":
            self.post_count += 1
            self.last_form = parse_qs(request.data.decode("utf-8"))
        else:
            raise AssertionError("unconfigured mock method")
        if self.responses:
            return self.responses.pop(0)
        if method == "GET" and parsed.path == "/kcs/ajax/service/list_by_ids":
            if not {"zid", "cid", "ids"} <= parse_qs(parsed.query).keys():
                return MockResponse({"errcode": 400}, status=400)
            return MockResponse({"errcode": 0, "data": [{
                "status": 2, "run_count": 2, "desired_count": 2,
                "lstime": 200, "access_token": "response-secret",
            }]})
        if method == "POST" and parsed.path in {
            "/kcs/ajax/service/restart", "/kcs/mock/restore",
        }:
            return MockResponse({"errcode": 0, "token": "response-secret"})
        raise AssertionError("unconfigured mock endpoint")


class OfflineKcsCase(unittest.TestCase):
    base_url = "https://kcs.example.invalid"

    def setUp(self):
        self.environment = {"KCS_TEST_COOKIE": "synthetic-default-cookie"}
        # Replace the mapping itself: never read or merge the host environment.
        self.env_patch = mock.patch.object(os, "environ", self.environment)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.blocked_sockets = []
        for target in ("socket.create_connection", "socket.socket.connect"):
            patcher = mock.patch(target, side_effect=AssertionError("network forbidden"))
            self.blocked_sockets.append(patcher.start())
            self.addCleanup(patcher.stop)
        self.opener = MockKcsOpener()
        patcher = mock.patch.object(kcs_ops, "build_opener", return_value=self.opener)
        self.build_opener = patcher.start()
        self.addCleanup(patcher.stop)
        self.temp = tempfile.TemporaryDirectory(prefix="kcs-synthetic-tests-")
        self.addCleanup(self.temp.cleanup)
        self.task_root = Path(self.temp.name) / "任务 path with spaces"
        self.task_root.mkdir()
        self.draft_path = self.task_root / "kcs draft.json"
        self.plan_path = self.task_root / ".kcs-ops" / "plan.json"
        self.write_draft(self.base_url)

    def tearDown(self):
        for blocked_socket in self.blocked_sockets:
            blocked_socket.assert_not_called()

    def draft(self, base_url: str) -> dict:
        auth = {"Cookie": "KCS_TEST_COOKIE"}
        status_query = {"zid": "zone-a", "cid": "cluster-a", "ids": "[3]"}
        return {
            "schema_version": 1,
            "target": {
                "label": "mock KCS target",
                "base_url": base_url,
                "environment": "test",
            },
            "contract_evidence": {
                "kind": "local-observed",
                "reference": "mock-test-contract",
                "verified_at": "2026-07-26T00:00:00Z",
            },
            "actions": [
                {
                    "id": "status-before",
                    "phase": "inspect",
                    "risk": "read-only",
                    "method": "GET",
                    "path": "/kcs/ajax/service/list_by_ids",
                    "query": status_query,
                    "headers_from_env": auth,
                    "expect": {
                        "http_status": [200],
                        "json_equals": {"errcode": 0},
                    },
                    "response_policy": "sanitized-json",
                },
                {
                    "id": "restart",
                    "phase": "apply",
                    "risk": "write",
                    "method": "POST",
                    "path": "/kcs/ajax/service/restart",
                    "headers_from_env": auth,
                    "encoding": "form",
                    "body": {
                        "id": "3",
                        "name": "mservice",
                        "zid": "zone-a",
                        "strategy": "verified",
                    },
                    "expect": {
                        "http_status": [200],
                        "json_equals": {"errcode": 0},
                    },
                    "verify_actions": ["verify-running"],
                    "rollback_action": "restore",
                    "response_policy": "summary",
                },
                {
                    "id": "verify-running",
                    "phase": "verify",
                    "risk": "read-only",
                    "method": "GET",
                    "path": "/kcs/ajax/service/list_by_ids",
                    "query": status_query,
                    "headers_from_env": auth,
                    "expect": {
                        "http_status": [200],
                        "json_equals": {
                            "errcode": 0,
                            "data.0.status": 2,
                        },
                        "json_relations": [
                            {
                                "left": "data.0.run_count",
                                "op": ">=",
                                "right_path": "data.0.desired_count",
                            },
                            {
                                "left": "data.0.desired_count",
                                "op": ">",
                                "right": 0,
                            },
                        ],
                    },
                    "response_policy": "sanitized-json",
                },
                {
                    "id": "restore",
                    "phase": "rollback",
                    "risk": "write",
                    "method": "POST",
                    "path": "/kcs/mock/restore",
                    "headers_from_env": auth,
                    "encoding": "form",
                    "body": {"id": "3"},
                    "expect": {
                        "http_status": [200],
                        "json_equals": {"errcode": 0},
                    },
                    "verify_actions": ["verify-running"],
                    "response_policy": "summary",
                },
            ],
        }

    def write_draft(self, base_url: str) -> None:
        self.draft_path.write_text(
            json.dumps(self.draft(base_url), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = kcs_ops.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def finalize(self) -> str:
        code, stdout, stderr = self.run_cli(
            [
                "plan",
                "--draft",
                str(self.draft_path),
                "--output",
                str(self.plan_path),
                "--task-root",
                str(self.task_root),
            ]
        )
        self.assertEqual(0, code, stderr)
        report = json.loads(stdout)
        return report["plan_sha256"]
