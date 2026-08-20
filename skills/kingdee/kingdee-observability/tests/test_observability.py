import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


REDACT = load_module("observability_redact", SCRIPTS / "redact.py")
ANALYZE = load_module("observability_analyze", SCRIPTS / "analyze_logs.py")
QUERY = load_module("observability_query", SCRIPTS / "validate_query_plan.py")
FIXTURE = ROOT / "tests" / "fixtures" / "synthetic_trace.jsonl"


class RedactionTest(unittest.TestCase):
    def test_recursive_redaction_and_sql_normalization(self):
        value = {
            "tenantId": "tenant-demo",
            "account": "account-demo",
            "message": "userId=7 clientIp=192.0.2.4 token=abc",
            "sql": "select * from t where id=42 and name='Alice'",
            "params": [42, "Alice"],
            "ip": "203.0.113.9",
            "host": "internal.example.invalid",
        }
        result = REDACT.redact_value(value)
        serialized = json.dumps(result)
        for secret in (
            "tenant-demo",
            "account-demo",
            "192.0.2.4",
            "203.0.113.9",
            "internal.example.invalid",
            "abc",
            "Alice",
            "42",
        ):
            self.assertNotIn(secret, serialized)
        self.assertEqual("[REDACTED]", result["params"])
        self.assertIn("id=?", result["sql"])
        sql_message = REDACT.redact_text("slow SQL select * from t where id=42 and name='Alice'")
        self.assertNotIn("42", sql_message)
        self.assertNotIn("Alice", sql_message)
        self.assertEqual("03:04:05", REDACT.redact_text("03:04:05"))
        self.assertEqual("[REDACTED_IP]", REDACT.redact_text("2001:db8::1"))
        quoted = REDACT.redact_text('{"token":"abc","userId":42,"params":[1,2]}')
        self.assertNotIn("abc", quoted)
        self.assertNotIn("42", quoted)
        self.assertNotIn("[1,2]", quoted)


class AnalyzerTest(unittest.TestCase):
    def test_classifies_trace_sql_n_plus_one_thread_gc_and_exception(self):
        events, warnings = ANALYZE.load_events(FIXTURE)
        result = ANALYZE.analyze(
            events, slow_sql_ms=1000, n_plus_one_threshold=3, warnings=warnings
        )
        self.assertEqual(7, result["summary"]["eventCount"])
        self.assertEqual(1, result["summary"]["traceCount"])
        self.assertEqual(1, result["summary"]["slowSqlCount"])
        self.assertEqual(1, result["summary"]["possibleNPlusOneCount"])
        self.assertEqual(1, result["summary"]["threadEvidenceCount"])
        self.assertEqual(1, result["summary"]["gcEvidenceCount"])
        self.assertGreaterEqual(result["summary"]["exceptionCount"], 1)
        serialized = json.dumps(result, ensure_ascii=False)
        for secret in ("tenant-demo", "account-demo", "not-a-real-secret", "192.0.2.10", "Alice", "Bob", "Carol"):
            self.assertNotIn(secret, serialized)

    def test_cli_accepts_paths_with_spaces_and_does_not_overwrite_input(self):
        with tempfile.TemporaryDirectory(prefix="observability path ") as temp_name:
            temp = Path(temp_name)
            input_path = temp / "trace input.jsonl"
            output_path = temp / "report output.json"
            input_path.write_bytes(FIXTURE.read_bytes())
            process = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "analyze_logs.py"),
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, process.returncode, process.stderr)
            self.assertTrue(output_path.exists())
            self.assertEqual(FIXTURE.read_bytes(), input_path.read_bytes())

    def test_n_plus_one_requires_trace_identity(self):
        events = [
            {"sql": "select * from t where id=1"},
            {"sql": "select * from t where id=2"},
            {"sql": "select * from t where id=3"},
        ]
        result = ANALYZE.analyze(events, slow_sql_ms=1000, n_plus_one_threshold=3)
        self.assertEqual(0, result["summary"]["possibleNPlusOneCount"])


class QueryPlanTest(unittest.TestCase):
    def test_prod_plan_is_bounded_and_credential_free(self):
        result = QUERY.validate_plan(
            {
                "mode": "prod-readonly",
                "scopeId": "task-42",
                "targetRef": "prod-a",
                "queryType": "time-window",
                "filters": {
                    "start": "2026-01-02T03:00:00+08:00",
                    "end": "2026-01-02T03:10:00+08:00",
                    "service": "order-service",
                },
                "maxRecords": 500,
                "approvalRef": "approval-42",
                "redaction": True,
            }
        )
        self.assertTrue(result["valid"])
        self.assertEqual(64, len(result["contractDigest"]))

    def test_rejects_credentials_and_unapproved_production(self):
        with self.assertRaisesRegex(ValueError, "credential/session"):
            QUERY.validate_plan(
                {
                    "mode": "prod-readonly",
                    "scopeId": "task-43",
                    "targetRef": "prod-a",
                    "queryType": "trace",
                    "filters": {"traceId": "trace-demo"},
                    "maxRecords": 10,
                    "redaction": True,
                    "token": "forbidden",
                }
            )


if __name__ == "__main__":
    unittest.main()
