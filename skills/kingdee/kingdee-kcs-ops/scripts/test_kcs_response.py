#!/usr/bin/env python3
"""Response regression through the CLI, with no credentials or network access."""
from __future__ import annotations

import copy
import json
import unittest
from unittest import mock

from kcs_test_support import MockResponse, OfflineKcsCase, kcs_ops


COOKIE = "KCS_ECHO_6f74f53c_never_a_real_credential"
AUTH = "KCS_AUTH_b487a2c1_synthetic_opaque_value"


class KcsResponseTests(OfflineKcsCase):
    def inspect_plan(self, policy="sanitized-json", count=1):
        draft = self.draft(self.base_url)
        first = draft["actions"][0]
        first["response_policy"] = policy
        first["headers_from_env"]["Authorization"] = "KCS_TEST_AUTH"
        draft["actions"] = []
        for number in range(count):
            action = copy.deepcopy(first)
            action["id"] = f"inspect-{number + 1}"
            draft["actions"].append(action)
        self.draft_path.write_text(json.dumps(draft), encoding="utf-8")
        self.environment.update(KCS_TEST_COOKIE=COOKIE, KCS_TEST_AUTH=AUTH)
        return self.finalize()

    def run_inspect(self):
        result_path = self.task_root / "inspect result.json"
        result_path.unlink(missing_ok=True)
        code, stdout, stderr = self.run_cli([
            "inspect", "--plan", str(self.plan_path),
            "--task-root", str(self.task_root), "--result", str(result_path),
        ])
        self.assertTrue(result_path.exists(), stderr)
        result_text = result_path.read_text(encoding="utf-8")
        report = json.loads(result_text)
        return code, stdout, stderr, result_text, report

    def assert_no_credentials(self, stdout, stderr, result_text):
        for output in (stdout, stderr, result_text):
            for secret in (COOKIE, AUTH):
                self.assertNotIn(secret, output)
                # A value straddling the truncation boundary must not leak a prefix.
                self.assertNotIn(secret[:16], output)
        self.assertNotIn(COOKIE, self.plan_path.read_text(encoding="utf-8"))
        self.assertNotIn(AUTH, self.plan_path.read_text(encoding="utf-8"))

    def assert_failed_after_first(self, outcome):
        code, stdout, stderr, result_text, report = outcome
        self.assertEqual(2, code)
        self.assertEqual("", stdout)
        self.assertEqual("failed", report["status"])
        self.assertEqual(["inspect-1"], [r["action_id"] for r in report["completed"]])
        self.assertEqual(report, json.loads(stderr))
        self.assert_no_credentials(stdout, stderr, result_text)
        self.assertNotIn("Traceback", stderr)
        self.assertNotIn("RAW_RESPONSE_MARKER", stderr + result_text)

    @staticmethod
    def echo_payload():
        return {
            "errcode": 0,
            "message": COOKIE,
            "nested": {"items": ["prefix " + COOKIE + " suffix", {"value": AUTH}]},
            "long_early": COOKIE + "x" * 4200,
            "long_crossing": "x" * 4090 + COOKIE + "y" * 20,
            "long_late": "x" * 4200 + COOKIE,
            "safe": "normal service message",
        }

    def test_runtime_credentials_redacted_in_full_console_and_result(self):
        self.inspect_plan()
        self.opener.responses = [MockResponse(self.echo_payload())]
        code, stdout, stderr, result_text, report = self.run_inspect()
        self.assertEqual(0, code, stderr)
        self.assertEqual(COOKIE, self.opener.last_cookie)
        self.assertEqual(AUTH, self.opener.requests[0].get_header("Authorization"))
        self.assert_no_credentials(stdout, stderr, result_text)
        self.assertEqual(report, json.loads(stdout))
        body = report["completed"][0]["response"]["body"]
        self.assertEqual("<redacted>", body["message"])
        self.assertEqual("normal service message", body["safe"])
        self.assertEqual("passed", report["status"])

    def test_summary_preserves_hash_and_bytes_without_echo_body(self):
        import hashlib

        self.inspect_plan(policy="summary")
        response = MockResponse(self.echo_payload())
        self.opener.responses = [response]
        code, stdout, stderr, result_text, report = self.run_inspect()
        self.assertEqual(0, code, stderr)
        self.assert_no_credentials(stdout, stderr, result_text)
        self.assertEqual({
            "type": "summary", "bytes": len(response.raw),
            "sha256": hashlib.sha256(response.raw).hexdigest(),
        }, report["completed"][0]["response"])

    def test_existing_sensitive_keys_patterns_and_safe_truncation_preserved(self):
        self.inspect_plan()
        payload = {
            "errcode": 0, "access_token": "key-only-synthetic-secret",
            "nested": {"client-secret": "nested-key-synthetic-secret"},
            "bearer": "prefix Bearer synthetic-bearer suffix",
            "basic": "Basic synthetic-basic", "assignment": "cookie=synthetic-value",
            "token_assignment": "token=synthetic-value", "plain": "healthy",
            "long_plain": "a" * 4200,
        }
        self.opener.responses = [MockResponse(payload)]
        code, stdout, stderr, result_text, report = self.run_inspect()
        self.assertEqual(0, code, stderr)
        body = report["completed"][0]["response"]["body"]
        for name in ("access_token", "bearer", "basic", "assignment", "token_assignment"):
            self.assertEqual("<redacted>", body[name])
        self.assertEqual("<redacted>", body["nested"]["client-secret"])
        self.assertEqual("healthy", body["plain"])
        self.assertEqual("a" * 4096 + "<truncated>", body["long_plain"])
        for value in ("key-only-synthetic-secret", "nested-key-synthetic-secret",
                      "synthetic-bearer", "synthetic-basic", "synthetic-value"):
            self.assertNotIn(value, stdout + stderr + result_text)

    def test_1100_array_response_retains_completed_for_both_policies(self):
        raw = b'{"errcode":0,"data":' + b"[" * 1100 + b"0" + b"]" * 1100 + b"}"
        self.assertEqual(2222, len(raw))
        for policy in ("sanitized-json", "summary"):
            with self.subTest(policy=policy):
                self.inspect_plan(policy=policy, count=2)
                self.opener.responses = [MockResponse({"errcode": 0}), MockResponse(raw)]
                self.assert_failed_after_first(self.run_inspect())

    def test_parser_success_over_depth_limit_is_controlled_for_both_policies(self):
        # 101 containers including the root object: json.loads itself succeeds.
        raw = (b'{"errcode":0,"data":' + b"[" * 100
               + b'"RAW_RESPONSE_MARKER"' + b"]" * 100 + b"}")
        self.assertEqual(0, json.loads(raw)["errcode"])
        for policy in ("sanitized-json", "summary"):
            with self.subTest(policy=policy):
                self.inspect_plan(policy=policy, count=2)
                self.opener.responses = [MockResponse({"errcode": 0}), MockResponse(raw)]
                self.assert_failed_after_first(self.run_inspect())

    def test_depth_limit_allows_100_containers_for_both_policies(self):
        raw = b'{"errcode":0,"data":' + b"[" * 99 + b'"healthy"' + b"]" * 99 + b"}"
        for policy in ("sanitized-json", "summary"):
            with self.subTest(policy=policy):
                self.inspect_plan(policy=policy)
                self.opener.responses = [MockResponse(raw)]
                code, stdout, stderr, result_text, report = self.run_inspect()
                self.assertEqual(0, code, stderr)
                self.assertEqual("passed", report["status"])
                self.assertEqual(1, len(report["completed"]))
                self.assert_no_credentials(stdout, stderr, result_text)
                if policy == "sanitized-json":
                    self.assertEqual(json.loads(raw), report["completed"][0]["response"]["body"])

    def test_later_conversion_recursion_error_retains_completed(self):
        self.inspect_plan(count=2)
        self.opener.responses = [MockResponse({"errcode": 0}), MockResponse({"errcode": 0})]
        real_view = kcs_ops.response_view
        calls = 0

        def conversion(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RecursionError("RAW_RESPONSE_MARKER " + COOKIE)
            return real_view(*args, **kwargs)

        with mock.patch.object(kcs_ops, "response_view", side_effect=conversion):
            self.assert_failed_after_first(self.run_inspect())
        self.assertEqual(2, calls)

    def test_ordinary_expect_failure_still_retains_completed(self):
        self.inspect_plan(count=2)
        self.opener.responses = [MockResponse({"errcode": 0}), MockResponse({"errcode": 7})]
        self.assert_failed_after_first(self.run_inspect())

    def test_5000_digit_integer_failure_retains_completed_for_both_policies(self):
        raw = b'{"errcode":0,"data":' + b"9" * 5000 + b"}"
        for policy in ("sanitized-json", "summary"):
            with self.subTest(policy=policy):
                self.inspect_plan(policy=policy, count=2)
                self.opener.responses = [MockResponse({"errcode": 0}), MockResponse(raw)]
                self.assert_failed_after_first(self.run_inspect())

    def test_lone_surrogate_fails_sanitized_output_but_allows_summary(self):
        raw = b'{"errcode":0,"label":"\\ud800"}'
        self.inspect_plan(count=2)
        self.opener.responses = [MockResponse({"errcode": 0}), MockResponse(raw)]
        self.assert_failed_after_first(self.run_inspect())
        self.inspect_plan(policy="summary", count=2)
        self.opener.responses = [MockResponse({"errcode": 0}), MockResponse(raw)]
        code, stdout, stderr, result_text, report = self.run_inspect()
        self.assertEqual(0, code, stderr)
        self.assertEqual("passed", report["status"])
        self.assertEqual(2, len(report["completed"]))
        self.assertEqual("summary", report["completed"][1]["response"]["type"])
        self.assertNotIn("body", report["completed"][1]["response"])
        self.assertNotIn("\\ud800", stdout + stderr + result_text)

    def test_exact_numeric_runtime_credential_is_redacted_without_numeric_coercion(self):
        self.inspect_plan()
        self.environment["KCS_TEST_COOKIE"] = "739182645"
        self.opener.responses = [MockResponse({"errcode": 0, "message": 739182645})]
        code, stdout, stderr, result_text, report = self.run_inspect()
        self.assertEqual(0, code, stderr)
        self.assertEqual("739182645", self.opener.last_cookie)
        self.assertNotIn("739182645", stdout + stderr + result_text)
        self.assertEqual("<redacted>", report["completed"][0]["response"]["body"]["message"])
        # Only exact scalar text matches are secrets; don't infer numeric variants.
        controls = {"errcode": 0, "decimal": 739182645.0, "nearby": 739182646}
        self.opener.responses = [MockResponse(controls)]
        code, _, stderr, _, report = self.run_inspect()
        self.assertEqual(0, code, stderr)
        self.assertEqual(controls, report["completed"][0]["response"]["body"])

    def test_credential_patterns_in_response_keys_are_redacted(self):
        self.inspect_plan()
        payload = {"errcode": 0, "data": {
            "Bearer synthetic-bearer-key": "safe",
            "Basic synthetic-basic-key": "safe",
            "token=synthetic-token-key": "safe",
        }}
        self.opener.responses = [MockResponse(payload)]
        code, stdout, stderr, result_text, report = self.run_inspect()
        self.assertEqual(0, code, stderr)
        for secret in ("synthetic-bearer-key", "synthetic-basic-key", "synthetic-token-key"):
            self.assertNotIn(secret, stdout + stderr + result_text)
        self.assertIn("<redacted>", report["completed"][0]["response"]["body"]["data"])


if __name__ == "__main__":
    unittest.main()
