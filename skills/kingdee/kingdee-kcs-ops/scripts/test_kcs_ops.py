#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import kcs_ops  # noqa: E402


class MockKcsHandler(BaseHTTPRequestHandler):
    get_count = 0
    post_count = 0
    last_cookie = None
    last_form = None

    def log_message(self, format, *args):
        return

    def write_json(self, value: dict, status: int = 200) -> None:
        payload = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=UTF-8")
        self.send_header("Set-Cookie", "mock-session=must-not-be-logged")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        type(self).get_count += 1
        type(self).last_cookie = self.headers.get("Cookie")
        parsed = urlsplit(self.path)
        if parsed.path == "/kcs/ajax/service/list_by_ids":
            query = parse_qs(parsed.query)
            if not {"zid", "cid", "ids"} <= query.keys():
                self.write_json({"errcode": 400}, status=400)
                return
            self.write_json(
                {
                    "errcode": 0,
                    "data": [
                        {
                            "status": 2,
                            "run_count": 2,
                            "desired_count": 2,
                            "lstime": 200,
                            "access_token": "response-secret",
                        }
                    ],
                }
            )
            return
        if parsed.path == "/kcs/mock/redirect":
            self.send_response(302)
            self.send_header("Location", "/kcs/ajax/service/list_by_ids")
            self.end_headers()
            return
        self.write_json({"errcode": 404}, status=404)

    def do_POST(self):
        type(self).post_count += 1
        type(self).last_cookie = self.headers.get("Cookie")
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        type(self).last_form = parse_qs(body)
        parsed = urlsplit(self.path)
        if parsed.path in {"/kcs/ajax/service/restart", "/kcs/mock/restore"}:
            self.write_json({"errcode": 0, "token": "response-secret"})
            return
        self.write_json({"errcode": 404}, status=404)


class KcsOpsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MockKcsHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        MockKcsHandler.get_count = 0
        MockKcsHandler.post_count = 0
        MockKcsHandler.last_cookie = None
        MockKcsHandler.last_form = None
        self.temp = tempfile.TemporaryDirectory()
        self.task_root = Path(self.temp.name) / "任务 path with spaces"
        self.task_root.mkdir()
        self.draft_path = self.task_root / "kcs draft.json"
        self.plan_path = self.task_root / ".kcs-ops" / "plan.json"
        self.write_draft(self.base_url)

    def tearDown(self):
        self.temp.cleanup()

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

    def test_plan_supports_utf8_and_paths_with_spaces(self):
        digest = self.finalize()
        plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
        self.assertEqual(digest, plan["plan_sha256"])
        self.assertEqual(digest, kcs_ops.plan_digest(plan))
        self.assertEqual("mock KCS target", plan["target"]["label"])

    def test_inspect_uses_memory_only_header_and_redacts_response(self):
        self.finalize()
        secret = "task-cookie-secret"
        with mock.patch.dict(os.environ, {"KCS_TEST_COOKIE": secret}, clear=False):
            code, stdout, stderr = self.run_cli(
                [
                    "inspect",
                    "--plan",
                    str(self.plan_path),
                    "--task-root",
                    str(self.task_root),
                    "--action",
                    "status-before",
                ]
            )
        self.assertEqual(0, code, stderr)
        self.assertEqual(secret, MockKcsHandler.last_cookie)
        self.assertNotIn(secret, stdout + stderr)
        self.assertNotIn("response-secret", stdout + stderr)
        report = json.loads(stdout)
        body = report["completed"][0]["response"]["body"]
        self.assertEqual("<redacted>", body["data"][0]["access_token"])

    def test_apply_rejects_wrong_digest_before_network(self):
        self.finalize()
        with mock.patch.dict(os.environ, {"KCS_TEST_COOKIE": "memory-secret"}, clear=False):
            code, _, _ = self.run_cli(
                [
                    "apply-approved",
                    "--plan",
                    str(self.plan_path),
                    "--task-root",
                    str(self.task_root),
                    "--expected-sha256",
                    "0" * 64,
                    "--approval-id",
                    "approved-task-ref",
                ]
            )
        self.assertEqual(2, code)
        self.assertEqual(0, MockKcsHandler.post_count)

    def test_apply_verify_and_rollback_share_approved_digest(self):
        digest = self.finalize()
        approval = "approved-task-ref"
        common_env = {"KCS_TEST_COOKIE": "memory-secret"}
        with mock.patch.dict(os.environ, common_env, clear=False):
            code, apply_out, apply_err = self.run_cli(
                [
                    "apply-approved",
                    "--plan",
                    str(self.plan_path),
                    "--task-root",
                    str(self.task_root),
                    "--expected-sha256",
                    digest,
                    "--approval-id",
                    approval,
                ]
            )
            self.assertEqual(0, code, apply_err)
            self.assertNotIn(approval, apply_out)
            self.assertEqual(["3"], MockKcsHandler.last_form["id"])

            code, _, verify_err = self.run_cli(
                [
                    "verify",
                    "--plan",
                    str(self.plan_path),
                    "--task-root",
                    str(self.task_root),
                ]
            )
            self.assertEqual(0, code, verify_err)

            code, rollback_out, rollback_err = self.run_cli(
                [
                    "rollback",
                    "--plan",
                    str(self.plan_path),
                    "--task-root",
                    str(self.task_root),
                    "--expected-sha256",
                    digest,
                    "--approval-id",
                    approval,
                ]
            )
            self.assertEqual(0, code, rollback_err)
            self.assertNotIn(approval, rollback_out)
        self.assertEqual(2, MockKcsHandler.post_count)
        self.assertGreaterEqual(MockKcsHandler.get_count, 1)

    def test_missing_credential_fails_before_network(self):
        self.finalize()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("KCS_TEST_COOKIE", None)
            code, _, _ = self.run_cli(
                [
                    "inspect",
                    "--plan",
                    str(self.plan_path),
                    "--task-root",
                    str(self.task_root),
                    "--action",
                    "status-before",
                ]
            )
        self.assertEqual(2, code)
        self.assertEqual(0, MockKcsHandler.get_count)

    def test_non_loopback_plain_http_is_rejected(self):
        self.write_draft("http://example.invalid")
        code, _, _ = self.run_cli(
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
        self.assertEqual(2, code)
        self.assertFalse(self.plan_path.exists())

    def test_plan_rejects_persisted_credentials(self):
        draft = self.draft(self.base_url)
        draft["actions"][1]["body"]["password"] = "must-not-persist"
        self.draft_path.write_text(
            json.dumps(draft, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        code, _, _ = self.run_cli(
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
        self.assertEqual(2, code)
        self.assertFalse(self.plan_path.exists())

    def test_output_cannot_escape_task_root(self):
        code, _, _ = self.run_cli(
            [
                "plan",
                "--draft",
                str(self.draft_path),
                "--output",
                "../outside.json",
                "--task-root",
                str(self.task_root),
            ]
        )
        self.assertEqual(2, code)


if __name__ == "__main__":
    unittest.main()
