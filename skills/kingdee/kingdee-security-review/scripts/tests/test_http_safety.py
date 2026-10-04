"""Offline checks of request plans and HTTP summaries; no remote service is used."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import network_probe
import poc_runner
import scope_check


SECRET_HEADERS = {
    name: f"sentinel-secret-{index}"
    for index, name in enumerate((
        "Authorization", "Proxy-Authorization", "Cookie", "Set-Cookie", "X-API-Key",
        "access_token", "AccessToken", "appToken", "cosmic_mcp_token",
        "kd-csrf-token", "X-CSRF-Token", "client_secret", "erpAccountId",
    ))
}


class Response(io.BytesIO):
    status = 200
    headers = {**SECRET_HEADERS, "Content-Type": "application/json"}


class HttpRedactionTest(unittest.TestCase):
    def test_redirect_location_is_redacted_without_mutating_headers(self):
        headers = {"Location": "https://other.invalid/?custom=secret-in-query#secret-in-fragment",
                   "Content-Location": "https://user:secret-in-url@other.invalid/",
                   "X-Request-Id": "safe-request-id"}
        before = dict(headers)
        result = scope_check.redact_headers(headers)
        self.assertEqual(before, headers)
        self.assertEqual("<redacted>", result["Location"])
        self.assertEqual("<redacted>", result["Content-Location"])
        self.assertEqual("safe-request-id", result["X-Request-Id"])

    def assert_redacted(self, result):
        rendered = json.dumps(result)
        for value in SECRET_HEADERS.values():
            self.assertNotIn(value, rendered)
        self.assertIn("application/json", rendered)

    def test_dry_run_plan_redacts_auth_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "poc.json"
            spec.write_text(json.dumps({"path": "api/check", "headers": {
                **SECRET_HEADERS, "Content-Type": "application/json",
            }}))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = poc_runner.main([
                    "--mode", "verify", "--target-url", "https://dev.example.invalid/ierp",
                    "--scope", "dev", "--poc-file", str(spec),
                ])
            self.assertEqual(0, code)
            result = json.loads(output.getvalue())
            self.assertEqual("DRY_RUN_ONLY", result["result"])
            self.assert_redacted(result)

    def test_poc_success_summary_redacts_response_headers(self):
        with patch("poc_runner.open_once", return_value=Response(b"{}")):
            result = poc_runner.run_request(urllib.request.Request("https://dev.example.invalid"), 1)
        self.assertTrue(result["ok"])
        self.assert_redacted(result)

    def test_poc_http_error_summary_redacts_response_headers(self):
        error = urllib.error.HTTPError("https://dev.example.invalid", 403, "denied",
                                      Response.headers, io.BytesIO(b"{}"))
        with patch("poc_runner.open_once", side_effect=error):
            result = poc_runner.run_request(urllib.request.Request("https://dev.example.invalid"), 1)
        self.assertEqual(403, result["status"])
        self.assert_redacted(result)

    def test_error_body_read_failure_preserves_status_and_closes_response(self):
        class BrokenBody(io.BytesIO):
            def read(self, *args):
                raise OSError("synthetic-read-secret")

        body = BrokenBody()
        error = urllib.error.HTTPError("https://dev.example.invalid", 503, "unavailable",
                                      {}, body)
        with patch("poc_runner.open_once", side_effect=error):
            result = poc_runner.run_request(urllib.request.Request("https://dev.example.invalid"), 1)
        self.assertEqual(503, result["status"])
        self.assertTrue(result["body_read_failed"])
        self.assertTrue(body.closed)
        self.assertNotIn("synthetic-read-secret", json.dumps(result))

    def test_probe_summary_redacts_response_headers(self):
        with patch("network_probe.socket.getaddrinfo", return_value=[]), \
                patch("network_probe.open_once", return_value=Response(b"")):
            result = network_probe.probe("https://dev.example.invalid", 1)
        self.assertTrue(result["ok"])
        self.assert_redacted(result)


if __name__ == "__main__":
    unittest.main()
