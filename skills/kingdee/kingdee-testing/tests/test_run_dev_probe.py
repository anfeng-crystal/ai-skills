import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_dev_probe.py"
SPEC = importlib.util.spec_from_file_location("run_dev_probe", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class RuntimeContractTest(unittest.TestCase):
    def test_local_rejects_non_loopback(self):
        with self.assertRaisesRegex(ValueError, "loopback"):
            MODULE.validate_contract(
                url="https://example.invalid/ping",
                mode="local",
                method="GET",
                scope_id="task-1",
                target_alias="local",
                approval_ref=None,
                rollback_ref=None,
                expected_evidence="status 200",
                allowed_path_prefixes=[],
                request_limit=1,
                has_payload=False,
            )

    def test_prod_readonly_requires_approval(self):
        with self.assertRaisesRegex(ValueError, "approval"):
            MODULE.validate_contract(
                url="https://example.invalid/ping",
                mode="prod-readonly",
                method="GET",
                scope_id="task-2",
                target_alias="prod-a",
                approval_ref=None,
                rollback_ref=None,
                expected_evidence="status 200",
                allowed_path_prefixes=[],
                request_limit=1,
                has_payload=False,
            )

    def test_dev_test_readonly_contract(self):
        contract = MODULE.validate_contract(
            url="https://example.invalid/health",
            mode="dev-test",
            method="HEAD",
            scope_id="task-dev",
            target_alias="dev-a",
            approval_ref=None,
            rollback_ref=None,
            expected_evidence="health header exists",
            allowed_path_prefixes=[],
            request_limit=1,
            has_payload=False,
        )
        self.assertTrue(contract["valid"])
        self.assertEqual("dev-test", contract["mode"])

    def test_approved_write_is_path_scoped(self):
        contract = MODULE.validate_contract(
            url="https://example.invalid/api/test-records/42",
            mode="approved-write",
            method="DELETE",
            scope_id="task-3",
            target_alias="dev-a",
            approval_ref="approval-7",
            rollback_ref="rollback-7",
            expected_evidence="record absent after delete",
            allowed_path_prefixes=["/api/test-records/"],
            request_limit=1,
            has_payload=False,
        )
        self.assertTrue(contract["valid"])
        self.assertEqual("https://[REDACTED_HOST]/api/test-records/42", contract["target"])

    def test_sensitive_headers_use_environment_without_output(self):
        headers = MODULE.parse_env_headers(
            ["Authorization=TASK_TEST_TOKEN"], {"TASK_TEST_TOKEN": "secret-value"}
        )
        self.assertEqual("secret-value", headers["Authorization"])
        self.assertEqual("[REDACTED]", MODULE.redact_headers(headers)["Authorization"])
        self.assertNotIn(
            "secret-value",
            MODULE.redact_text("server reflected secret-value", ("secret-value",)),
        )
        sql_preview = MODULE.redact_text("select * from t where id=42 and name='Alice'")
        self.assertNotIn("42", sql_preview)
        self.assertNotIn("Alice", sql_preview)
        quoted = MODULE.redact_text('{"token":"abc","userId":42,"params":[1,2]}')
        self.assertNotIn("abc", quoted)
        self.assertNotIn("42", quoted)
        self.assertNotIn("[1,2]", quoted)
        with self.assertRaisesRegex(ValueError, "header-env"):
            MODULE.parse_headers(["Authorization: secret-value"])

    def test_cli_dry_run_with_path_spaces(self):
        process = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--mode",
                "local",
                "--scope-id",
                "path space",
                "--target-alias",
                "local",
                "--url",
                "http://127.0.0.1/path%20with%20spaces",
                "--expected-evidence",
                "status 200",
                "--dry-run",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertIn("[REDACTED_HOST]", process.stdout)


if __name__ == "__main__":
    unittest.main()
