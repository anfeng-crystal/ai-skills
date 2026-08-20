import importlib.util
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SKILL_ROOT / "cosmic_login.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("cosmic_login_under_test", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cosmic_login = _load_module()


class LoginOutputUnitTests(unittest.TestCase):
    def test_success_output_reports_availability_without_secret_values(self):
        result = {
            "success": True,
            "cookie": "KERPSESSIONID=raw-cookie-value",
            "csrf_token": "raw-csrf-value",
            "account_id": "1565321489509515264",
            "user_id": "12345",
        }

        output = "\n".join(cosmic_login._login_output_lines(result))

        self.assertIn("LOGIN_SUCCESS", output)
        self.assertIn("COOKIE_AVAILABLE=True", output)
        self.assertIn("CSRF_TOKEN_AVAILABLE=True", output)
        self.assertIn(f"ACCOUNT_ID={result['account_id']}", output)
        self.assertIn(f"USER_ID={result['user_id']}", output)
        self.assertNotRegex(output, r"(?m)^COOKIE=")
        self.assertNotRegex(output, r"(?m)^CSRF_TOKEN=")
        self.assertNotIn(result["cookie"], output)
        self.assertNotIn(result["csrf_token"], output)

    def test_failure_output_keeps_diagnostics_without_session_material(self):
        result = {
            "success": False,
            "cookie": "raw-cookie-value",
            "csrf_token": "raw-csrf-value",
            "error": "用户名或密码错误",
            "datacenters": [
                {"id": "100001", "name": "测试中心"},
            ],
        }

        output = "\n".join(cosmic_login._login_output_lines(result))

        self.assertIn("LOGIN_FAILED: 用户名或密码错误", output)
        self.assertIn("DATACENTERS_COUNT=1", output)
        for secret in (result["cookie"], result["csrf_token"]):
            self.assertNotIn(secret, output)


class LoginCliSubprocessTests(unittest.TestCase):
    def _run_mocked_cli(self, argv, patch_source):
        source = textwrap.dedent(
            f"""
            import importlib.util
            import sys

            script_path = {str(SCRIPT_PATH)!r}
            spec = importlib.util.spec_from_file_location("cosmic_login_subprocess", script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            {patch_source}
            sys.argv = [script_path] + {argv!r}
            module.main()
            """
        )
        return subprocess.run(
            [sys.executable, "-c", source],
            cwd=SKILL_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_success_subprocess_never_prints_returned_session_material(self):
        cookie = "KERPSESSIONID=subprocess-cookie-secret"
        csrf = "subprocess-csrf-secret"
        account_id = "1565321489509515264"
        user_id = "987654321"
        result = {
            "success": True,
            "cookie": cookie,
            "csrf_token": csrf,
            "error": "",
            "account_id": account_id,
            "user_id": user_id,
        }

        completed = self._run_mocked_cli(
            ["https://example.invalid/ierp", "secret-user", "secret-password", account_id],
            f"module.auto_login = lambda *args, **kwargs: {result!r}",
        )
        combined = completed.stdout + completed.stderr

        self.assertEqual(0, completed.returncode, combined)
        self.assertIn("LOGIN_SUCCESS", completed.stdout)
        self.assertIn("COOKIE_AVAILABLE=True", completed.stdout)
        self.assertIn("CSRF_TOKEN_AVAILABLE=True", completed.stdout)
        self.assertIn(f"ACCOUNT_ID={account_id}", completed.stdout)
        self.assertIn(f"USER_ID={user_id}", completed.stdout)
        self.assertNotRegex(completed.stdout, r"(?m)^COOKIE=")
        self.assertNotRegex(completed.stdout, r"(?m)^CSRF_TOKEN=")
        for secret in (cookie, csrf, "secret-user", "secret-password"):
            self.assertNotIn(secret, combined)

    def test_failure_subprocess_keeps_status_without_session_material(self):
        cookie = "KERPSESSIONID=failure-cookie-secret"
        csrf = "failure-csrf-secret"
        result = {
            "success": False,
            "cookie": cookie,
            "csrf_token": csrf,
            "error": "用户名或密码错误",
            "account_id": "",
            "datacenters": [],
        }

        completed = self._run_mocked_cli(
            ["https://example.invalid/ierp", "secret-user", "secret-password"],
            f"module.auto_login = lambda *args, **kwargs: {result!r}",
        )
        combined = completed.stdout + completed.stderr

        self.assertEqual(1, completed.returncode, combined)
        self.assertIn("LOGIN_FAILED: 用户名或密码错误", completed.stdout)
        for secret in (cookie, csrf, "secret-user", "secret-password"):
            self.assertNotIn(secret, combined)

    def test_check_mode_keeps_compatible_status_without_echoing_cookie(self):
        cookie = "KERPSESSIONID=existing-cookie-secret"
        completed = self._run_mocked_cli(
            ["--check", "https://example.invalid/ierp", cookie],
            "module.check_session = lambda *args, **kwargs: True",
        )
        combined = completed.stdout + completed.stderr

        self.assertEqual(0, completed.returncode, combined)
        self.assertEqual("SESSION_VALID=True\n", completed.stdout)
        self.assertNotIn(cookie, combined)

    def test_usage_describes_safe_output_without_network_access(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            cwd=SKILL_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(1, completed.returncode, completed.stderr)
        self.assertIn("CLI 不输出 Cookie 或 CSRF 原值", completed.stdout)
        self.assertIn("auto_login()", completed.stdout)


if __name__ == "__main__":
    unittest.main()
