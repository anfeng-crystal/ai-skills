import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import analyze_logs as ANALYZE


class DurationContractTest(unittest.TestCase):
    def test_preserves_numeric_millisecond_and_second_forms(self):
        for value, expected in (
            (0, 0.0), (0.0, 0.0), (1200, 1200.0), (12.5, 12.5),
            ("1200", 1200.0), ("12.5MS", 12.5), ("1.25 s", 1250.0),
            (" 1200 ms ", 1200.0),
        ):
            with self.subTest(value=value):
                self.assertEqual(expected, ANALYZE.parse_duration(value, ""))

    def test_rejects_negative_partial_nonfinite_and_overflow_values(self):
        for value in (
            -1, -1.5, "-1200ms", "prefix 1200ms trailing", "1200msfoo",
            "1e3", "1.2.3ms", float("nan"), float("inf"), float("-inf"),
            "NaN", "Infinity", 10**1000, "9" * 309 + "ms",
            "9" * 306 + "s", True, False,
        ):
            with self.subTest(value=repr(value)):
                self.assertIsNone(ANALYZE.parse_duration(value, ""))

    def test_preserves_explicit_message_markers(self):
        for message, expected in (
            ("query duration=1200ms", 1200.0), ("elapsed: 1.25 s", 1250.0),
            ("cost 0ms", 0.0), ("request took 2s", 2000.0),
        ):
            with self.subTest(message=message):
                self.assertEqual(expected, ANALYZE.parse_duration(None, message))

    def test_message_does_not_accept_malformed_or_overflow_duration(self):
        for message in (
            "duration=-1200ms", "duration=2msfoo", "duration=2seconds",
            "duration=1.2.3ms", "duration=NaNms", "duration=Infinitys",
            "duration=" + "9" * 306 + "s",
        ):
            with self.subTest(message=message):
                self.assertIsNone(ANALYZE.parse_duration(None, message))

    def test_invalid_field_can_fall_back_to_explicit_message_duration(self):
        for value in (-1, "-1200ms", "prefix1200ms", float("nan"), float("inf"), 10**1000, True):
            with self.subTest(value=repr(value)):
                self.assertEqual(250.0, ANALYZE.parse_duration(value, "query took 0.25s"))

    def test_valid_field_retains_precedence_over_message(self):
        self.assertEqual(0.0, ANALYZE.parse_duration(0, "query took 2s"))
        self.assertEqual(200.0, ANALYZE.parse_duration("200ms", "query took 2s"))

    def test_invalid_duration_does_not_create_slow_sql_or_nonstandard_json(self):
        values = ["-1200ms", "prefix1200ms", float("nan"), float("inf"), 10**1000, "9" * 306 + "s", True]
        events = [
            {"traceId": "synthetic-trace", "spanId": str(index), "durationMs": value,
             "sql": "select * from synthetic", "level": "ERROR"}
            for index, value in enumerate(values)
        ]
        result = ANALYZE.analyze(events, slow_sql_ms=1000, n_plus_one_threshold=3)
        self.assertEqual(0, result["summary"]["slowSqlCount"])
        self.assertTrue(all(item["durationMs"] is None for item in result["exceptions"]))
        json.dumps(result, allow_nan=False)

    def test_explicit_slow_sql_marker_survives_unknown_duration(self):
        result = ANALYZE.analyze(
            [{"durationMs": "invalid", "sql": "select * from synthetic", "message": "slow SQL"}],
            slow_sql_ms=1000, n_plus_one_threshold=3,
        )
        self.assertEqual(1, result["summary"]["slowSqlCount"])
        self.assertIsNone(result["slowSql"][0]["durationMs"])

    def test_cli_rejects_nonfinite_or_negative_threshold_before_writing(self):
        with tempfile.TemporaryDirectory(prefix="duration threshold ") as temp_name:
            temp = Path(temp_name)
            source = temp / "input.json"
            output = temp / "output.json"
            original = '[{"sql":"select * from synthetic","durationMs":2000}]'
            source.write_text(original, encoding="utf-8")
            for threshold in ("-1", "nan", "inf", "-inf", "1e309"):
                with self.subTest(threshold=threshold):
                    output.write_text("existing output", encoding="utf-8")
                    process = subprocess.run(
                        [sys.executable, str(SCRIPTS / "analyze_logs.py"), "--input", str(source),
                         "--output", str(output), "--slow-sql-ms=" + threshold],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(2, process.returncode, process.stderr)
                    self.assertIn("threshold", process.stderr)
                    self.assertEqual("", process.stdout)
                    self.assertEqual("existing output", output.read_text(encoding="utf-8"))
                    self.assertEqual(original, source.read_text(encoding="utf-8"))

    def test_cli_preserves_zero_and_finite_thresholds(self):
        with tempfile.TemporaryDirectory(prefix="duration finite threshold ") as temp_name:
            source = Path(temp_name) / "input.json"
            source.write_text('[{"sql":"select * from synthetic","durationMs":1000}]', encoding="utf-8")
            for threshold, expected in (("0", 1), ("1000", 1), ("1000.1", 0)):
                with self.subTest(threshold=threshold):
                    process = subprocess.run(
                        [sys.executable, str(SCRIPTS / "analyze_logs.py"), "--input", str(source),
                         "--slow-sql-ms=" + threshold],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(0, process.returncode, process.stderr)
                    result = json.loads(process.stdout)
                    self.assertEqual(expected, result["summary"]["slowSqlCount"])
                    self.assertEqual(float(threshold), result["thresholds"]["slowSqlMs"])


if __name__ == "__main__":
    unittest.main()
