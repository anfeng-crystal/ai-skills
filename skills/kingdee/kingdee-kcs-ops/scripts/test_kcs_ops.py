#!/usr/bin/env python3
"""CLI contract regression; every request is a strict in-memory opener mock."""
from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from kcs_test_support import OfflineKcsCase, kcs_ops


class KcsOpsTests(OfflineKcsCase):
    def test_plan_supports_utf8_and_paths_with_spaces(self):
        digest = self.finalize()
        plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
        self.assertEqual(digest, plan["plan_sha256"])
        self.assertEqual(digest, kcs_ops.plan_digest(plan))
        self.assertEqual("mock KCS target", plan["target"]["label"])

    def test_inspect_uses_memory_only_header_and_redacts_response(self):
        self.finalize()
        secret = "task-cookie-secret"
        with mock.patch.dict(os.environ, {"KCS_TEST_COOKIE": secret}, clear=True):
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
        self.assertEqual(secret, self.opener.last_cookie)
        self.assertNotIn(secret, stdout + stderr)
        self.assertNotIn("response-secret", stdout + stderr)
        report = json.loads(stdout)
        body = report["completed"][0]["response"]["body"]
        self.assertEqual("<redacted>", body["data"][0]["access_token"])

    def test_apply_rejects_wrong_digest_before_network(self):
        self.finalize()
        with mock.patch.dict(os.environ, {"KCS_TEST_COOKIE": "memory-secret"}, clear=True):
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
        self.assertEqual(0, self.opener.post_count)

    def test_apply_verify_and_rollback_share_approved_digest(self):
        digest = self.finalize()
        approval = "approved-task-ref"
        common_env = {"KCS_TEST_COOKIE": "memory-secret"}
        with mock.patch.dict(os.environ, common_env, clear=True):
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
            self.assertEqual(["3"], self.opener.last_form["id"])

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
        self.assertEqual(2, self.opener.post_count)
        self.assertGreaterEqual(self.opener.get_count, 1)

    def test_missing_credential_fails_before_network(self):
        self.finalize()
        with mock.patch.dict(os.environ, {}, clear=True):
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
        self.assertEqual(0, self.opener.get_count)

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
