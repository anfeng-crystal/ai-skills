"""Offline response checks: synthetic fixtures, real check_session and CLI."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "cosmic_login.py"
spec = importlib.util.spec_from_file_location("session_under_test", SCRIPT_PATH)
cosmic_login = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cosmic_login)

BASE_URL = "https://example.invalid/ierp"
# Shape derived from the local 7.0 getUserLanguage method; values are synthetic.
LANGUAGE = {"language": "zh_CN", "defaultLang": "zh_CN",
            "accountId": "fixture-dc", "direction": {"zh_CN": "ltr"}}
IDENTITY = dict(LANGUAGE, userId="fixture-dc_fixture-user")
# IDENTITY is an existing-branch compatibility control, not authentication proof.
CASES = [
    ("language-only", 200, "application/json", json.dumps(LANGUAGE), False),
    ("empty-object", 200, "application/json", "{}", False),
    ("synthetic-denial", 200, "application/json",
     '{"success":false,"errorCode":"SESSION_EXPIRED"}', False),
    ("maintenance-html", 200, "text/html", "<html>maintenance</html>", False),
    ("parse-failure", 200, "application/json", "{invalid", False),
    ("unauthorized", 401, "application/json", "{}", False),
    ("login-html", 200, "text/html", "<html>login</html>", False),
    ("identity-compatibility", 200, "application/json", json.dumps(IDENTITY), True),
]


class Response:
    def __init__(self, status, content_type, body):
        self.status_code = status
        self.headers = {"content-type": content_type}
        self.text = body

    def json(self):
        return json.loads(self.text)


class SessionResponseTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(cosmic_login.requests.sessions.Session, "request",
                             side_effect=AssertionError("network forbidden"))
        self.network = guard.start()
        self.addCleanup(guard.stop)
        self.addCleanup(self.network.assert_not_called)

    def test_response_matrix(self):
        for name, status, content_type, body, expected in CASES:
            with self.subTest(case=name):
                with patch.object(cosmic_login.requests, "post",
                                  return_value=Response(status, content_type, body)) as post:
                    actual = cosmic_login.check_session(BASE_URL, "")
                self.assertIs(actual, expected)
                post.assert_called_once_with(
                    BASE_URL + "/api/login/getUserLanguage.do",
                    headers={"Cookie": "", "ajax": "true"}, timeout=8)

    def test_non_object_json_does_not_confirm_session(self):
        for body in ('[]', 'null', '"language"', '42', 'true'):
            with self.subTest(body=body):
                with patch.object(cosmic_login.requests, "post",
                                  return_value=Response(200, "application/json", body)):
                    self.assertIs(cosmic_login.check_session(BASE_URL, ""), False)

    def test_http_error_with_identity_does_not_confirm_session(self):
        with patch.object(cosmic_login.requests, "post",
                          return_value=Response(403, "application/json", json.dumps(IDENTITY))):
            self.assertIs(cosmic_login.check_session(BASE_URL, ""), False)

    def test_request_failure_does_not_confirm_session_or_retry(self):
        for error in (cosmic_login.requests.Timeout, cosmic_login.requests.ConnectionError):
            with self.subTest(error=error.__name__):
                with patch.object(cosmic_login.requests, "post", side_effect=error) as post:
                    self.assertIs(cosmic_login.check_session(BASE_URL, ""), False)
                post.assert_called_once()

    def test_request_arguments_and_existing_identity_branch_are_preserved(self):
        with patch.object(cosmic_login.requests, "post", return_value=Response(
                200, "application/json; charset=utf-8", json.dumps(IDENTITY))) as post:
            actual = cosmic_login.check_session(
                BASE_URL + "/", "fixture-cookie", "fixture-csrf", timeout=3)
        self.assertIs(actual, True)
        post.assert_called_once_with(
            BASE_URL + "/api/login/getUserLanguage.do",
            headers={"Cookie": "fixture-cookie", "ajax": "true",
                     "kd-csrf-token": "fixture-csrf"}, timeout=3)


class SessionCliTests(unittest.TestCase):
    def test_real_check_session_cli_matrix(self):
        for name, status, content_type, body, expected in CASES:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as workdir:
                source = textwrap.dedent(f"""
                    import importlib.util
                    import json
                    import sys
                    from types import SimpleNamespace
                    from unittest.mock import patch
                    spec = importlib.util.spec_from_file_location('login_cli', {str(SCRIPT_PATH)!r})
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    response = SimpleNamespace(status_code={status!r},
                        headers={{'content-type': {content_type!r}}}, text={body!r},
                        json=lambda: json.loads({body!r}))
                    sys.argv = ['cosmic_login.py', '--check', {BASE_URL!r}, 'fixture-cli-cookie']
                    with patch.object(module.requests.sessions.Session, 'request',
                                      side_effect=AssertionError('network forbidden')) as network:
                        with patch.object(module.requests, 'post', return_value=response) as post:
                            try:
                                module.main()
                            except SystemExit as exc:
                                code = exc.code
                        network.assert_not_called()
                        post.assert_called_once_with(
                            {BASE_URL + '/api/login/getUserLanguage.do'!r},
                            headers={{'Cookie': 'fixture-cli-cookie', 'ajax': 'true'}}, timeout=8)
                    sys.exit(code)
                """)
                completed = subprocess.run([sys.executable, "-B", "-c", source],
                                           cwd=workdir, capture_output=True, text=True,
                                           check=False, timeout=15)
                self.assertEqual(completed.returncode, 0 if expected else 1,
                                 completed.stdout + completed.stderr)
                self.assertEqual(completed.stdout, f"SESSION_VALID={expected}\n")
                self.assertEqual(completed.stderr, "")
                self.assertNotIn("fixture-cli-cookie", completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
