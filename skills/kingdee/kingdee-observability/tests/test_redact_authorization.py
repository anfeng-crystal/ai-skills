import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from redact import REDACTED, redact_text, redact_value


class AuthorizationRedactionTest(unittest.TestCase):
    def test_unquoted_bearer_preserves_diagnostic_context(self):
        value = "request failed Authorization: Bearer SYNTHETIC_BEARER_SECRET status=401 traceId=trace-demo"
        self.assertEqual(
            f"request failed Authorization: {REDACTED} status=401 traceId=trace-demo",
            redact_text(value),
        )

    def test_basic_case_and_horizontal_spacing(self):
        for value, expected in (
            ("Authorization: Basic U1lOVEhFVElDX0JBU0lD", f"Authorization: {REDACTED}"),
            ("AUTHORIZATION=bAsIc U1lOVEhFVElDX0JBU0lD==; status=403", f"AUTHORIZATION={REDACTED}; status=403"),
            ("authorization\t:\tbeARer\tSYNTHETIC_SECRET, status=401", f"authorization\t:\t{REDACTED}, status=401"),
        ):
            with self.subTest(value=value):
                self.assertEqual(expected, redact_text(value))

    def test_quoted_values_and_json_keys(self):
        for value, expected in (
            ('{"Authorization":"Bearer SYNTHETIC_SECRET","status":401}', f'{{"Authorization":{REDACTED},"status":401}}'),
            ("'authorization'='Basic SYNTHETIC_SECRET' status=401", f"'authorization'={REDACTED} status=401"),
            (r'Authorization: "Bearer SYNTHETIC_\"SECRET" status=401', f"Authorization: {REDACTED} status=401"),
            (r"Authorization: 'Basic SYNTHETIC_\'SECRET' status=401", f"Authorization: {REDACTED} status=401"),
            ('Authorization: Bearer "SYNTHETIC_SECRET" status=401', f"Authorization: {REDACTED} status=401"),
        ):
            with self.subTest(value=value):
                self.assertEqual(expected, redact_text(value))

    def test_single_value_and_repeated_headers(self):
        value = "Authorization=SYNTHETIC_RAW_SECRET; status=401 Authorization: Bearer SYNTHETIC_SECOND_SECRET"
        self.assertEqual(
            f"Authorization={REDACTED}; status=401 Authorization: {REDACTED}",
            redact_text(value),
        )

    def test_matched_quoted_values_retain_multiline_redaction(self):
        for quote in ('"', "'"):
            for newline in ("\n", "\r\n", "\r"):
                with self.subTest(quote=quote, newline=repr(newline)):
                    value = f"Authorization: {quote}Bearer SYNTHETIC_MULTILINE{newline}CONTINUED{quote} status=401"
                    self.assertEqual(f"Authorization: {REDACTED} status=401", redact_text(value))
                    escaped = f"Authorization: {quote}Bearer SYNTHETIC_\\{quote}MULTILINE{newline}CONTINUED{quote} status=401"
                    self.assertEqual(f"Authorization: {REDACTED} status=401", redact_text(escaped))

    def test_header_matching_does_not_cross_line_boundaries(self):
        for newline in ("\n", "\r\n", "\r"):
            with self.subTest(newline=repr(newline)):
                value = f"Authorization: Bearer SYNTHETIC_SECRET{newline}status=401 traceId=trace-demo"
                self.assertEqual(
                    f"Authorization: {REDACTED}{newline}status=401 traceId=trace-demo",
                    redact_text(value),
                )
                empty = f"Authorization: {newline}status=401 traceId=trace-demo"
                self.assertEqual(empty, redact_text(empty))

    def test_empty_header_and_unrelated_context_are_preserved(self):
        for value in ("Authorization:", "authorization checks failed status=401", "traceId=trace-demo status=401"):
            with self.subTest(value=value):
                self.assertEqual(value, redact_text(value))

    def test_recursive_authorization_field_and_message(self):
        result = redact_value({
            "headers": {"aUthOrIzAtIoN": "Bearer SYNTHETIC_FIELD_SECRET"},
            "message": "Authorization: Bearer SYNTHETIC_MESSAGE_SECRET status=401",
            "traceId": "trace-demo",
        })
        self.assertEqual(REDACTED, result["headers"]["aUthOrIzAtIoN"])
        self.assertEqual(f"Authorization: {REDACTED} status=401", result["message"])
        self.assertEqual("trace-demo", result["traceId"])
        self.assertNotIn("SYNTHETIC_", json.dumps(result))

    def test_analyzer_cli_final_artifact_contains_no_authorization_credential(self):
        with tempfile.TemporaryDirectory(prefix="authorization regression ") as temp_name:
            temp = Path(temp_name)
            source = temp / "events.jsonl"
            target = temp / "analysis.json"
            source.write_text(json.dumps({
                "level": "ERROR",
                "traceId": "trace-demo",
                "message": "request failed Authorization: Bearer SYNTHETIC_ANALYZER_SECRET status=401",
            }) + "\n", encoding="utf-8")
            process = subprocess.run(
                [sys.executable, str(SCRIPTS / "analyze_logs.py"), "--input", str(source), "--output", str(target)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, process.returncode, process.stderr)
            payload = target.read_text(encoding="utf-8")
            result = json.loads(payload)
            self.assertNotIn("SYNTHETIC_ANALYZER_SECRET", payload)
            self.assertIn("status=401", result["exceptions"][0]["message"])
            self.assertEqual("trace-demo", result["exceptions"][0]["traceId"])


if __name__ == "__main__":
    unittest.main()
