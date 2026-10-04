import json
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import analyze_logs


class ExceptionEvidenceTest(unittest.TestCase):
    def analyze(self, event):
        return analyze_logs.analyze(
            [event], slow_sql_ms=1000, n_plus_one_threshold=3
        )

    def test_explicit_stack_aliases_survive_nonempty_message_and_are_redacted(self):
        stack = (
            "java.lang.IllegalStateException: synthetic failure token=synthetic-secret\n"
            "\tat example.DiagnosticTarget.execute(DiagnosticTarget.java:42)"
        )
        for alias in ("exception", "throwable", "stackTrace", "error"):
            with self.subTest(alias=alias):
                result = self.analyze({"message": "Request failed", alias: stack})
                item = result["exceptions"][0]
                self.assertEqual("Request failed", item["message"])
                self.assertIn("java.lang.IllegalStateException", item["exception"])
                self.assertIn("DiagnosticTarget.java:42", item["exception"])
                self.assertIn("token=[REDACTED]", item["exception"])
                self.assertNotIn("synthetic-secret", json.dumps(result))

    def test_structured_exception_preserves_evidence_without_sensitive_values(self):
        result = self.analyze({
            "message": "Request failed",
            "exception": {
                "type": "java.lang.IllegalStateException",
                "message": "synthetic failure",
                "stackTrace": "at example.DiagnosticTarget.execute(DiagnosticTarget.java:42)",
                "context": {"token": "synthetic-token", "userId": "synthetic-user"},
            },
        })
        exception = result["exceptions"][0]["exception"]
        self.assertEqual("java.lang.IllegalStateException", exception["type"])
        self.assertEqual("synthetic failure", exception["message"])
        self.assertIn("DiagnosticTarget.java:42", exception["stackTrace"])
        self.assertEqual({"token": "[REDACTED]", "userId": "[REDACTED]"}, exception["context"])
        for sensitive in ("synthetic-token", "synthetic-user"):
            self.assertNotIn(sensitive, json.dumps(result))

    def test_error_level_without_explicit_exception_does_not_fabricate_one(self):
        result = self.analyze({"level": "ERROR", "message": "Request failed"})
        self.assertEqual(1, result["summary"]["exceptionCount"])
        item = result["exceptions"][0]
        self.assertEqual("ERROR", item["level"])
        self.assertEqual("Request failed", item["message"])
        self.assertNotIn("exception", item)


if __name__ == "__main__":
    unittest.main()
