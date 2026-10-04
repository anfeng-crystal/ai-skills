import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import analyze_logs


class MessageStackTest(unittest.TestCase):
    def analyze(self, events):
        return analyze_logs.analyze(
            events, slow_sql_ms=1000, n_plus_one_threshold=3
        )

    def test_warn_java_exception_header_and_frame_are_evidence(self):
        messages = [
            "java.lang.NullPointerException: Cannot invoke save\n"
            " at demo.SavePlugin.run(SavePlugin.java:18)",
            "java.lang.IllegalArgumentException\n"
            "\tat demo.SavePlugin.run(Unknown Source)",
            "java.lang.AssertionError: synthetic failure\r\n"
            "\tat java.base/java.lang.Thread.run(Thread.java:840)",
            "demo.Outer$OperationException: synthetic failure\n"
            "\tat app//demo.Outer$Operation.run(Native Method)",
        ]
        for message in messages:
            with self.subTest(message=message):
                result = self.analyze([{"level": "WARN", "message": message}])
                self.assertEqual(1, result["summary"]["exceptionCount"])
                item = result["exceptions"][0]
                self.assertEqual("WARN", item["level"])
                self.assertEqual(message, item["message"])
                self.assertNotIn("exception", item)

    def test_mentions_and_incomplete_stacks_do_not_add_exception_evidence(self):
        messages = [
            "validation completed",
            "Registered java.lang.NullPointerException handler",
            "NullPointerException counter is zero",
            "java.lang.NullPointerException: configured class name",
            "\tat demo.SavePlugin.run(SavePlugin.java:18)",
            "java.lang.NullPointerException: configured class name\nvalidation completed\n"
            "\tat demo.SavePlugin.run(SavePlugin.java:18)",
            "demo.ExceptionMapper: initialized\n\tat demo.SavePlugin.run(SavePlugin.java:18)",
            "java.lang.NullPointerException: synthetic failure\n at some location",
        ]
        for message in messages:
            with self.subTest(message=message):
                result = self.analyze([{"level": "WARN", "message": message}])
                self.assertEqual([], result["exceptions"])

    def test_error_levels_and_structured_exception_keep_source_evidence(self):
        events = [{"level": level, "message": "save rejected by validation"}
                  for level in ("ERROR", "FATAL", "SEVERE")]
        events.append({"level": "WARN", "message": "load failed", "exception": {
            "type": "java.lang.IllegalStateException",
            "context": {"token": "synthetic-secret", "userId": "synthetic-user"},
        }})
        result = self.analyze(events)
        self.assertEqual(4, result["summary"]["exceptionCount"])
        for event, item in zip(events[:3], result["exceptions"][:3]):
            self.assertEqual(event["level"], item["level"])
            self.assertEqual(event["message"], item["message"])
            self.assertNotIn("exception", item)
        exception = result["exceptions"][3]["exception"]
        self.assertEqual("java.lang.IllegalStateException", exception["type"])
        self.assertEqual({"token": "[REDACTED]", "userId": "[REDACTED]"}, exception["context"])

    def test_new_stack_evidence_is_redacted_and_traces_remain_separate(self):
        message = ("java.lang.NullPointerException: token=synthetic-secret\n"
                   "\tat demo.SavePlugin.run(SavePlugin.java:18)")
        events = [{"level": "WARN", "message": message, "traceId": trace}
                  for trace in ("trace-alpha", "trace-beta", "")]
        result = self.analyze(events)
        self.assertEqual(3, result["summary"]["eventCount"])
        self.assertEqual(3, result["summary"]["exceptionCount"])
        self.assertEqual(["trace-alpha", "trace-beta", ""],
                         [item["traceId"] for item in result["exceptions"]])
        self.assertEqual([1, 1], [tree["eventCount"] for tree in result["traceTrees"]])
        self.assertNotIn("synthetic-secret", json.dumps(result))
        self.assertIn("token=[REDACTED]", result["exceptions"][0]["message"])

    def test_text_lines_without_trace_are_not_joined(self):
        text = ("java.lang.NullPointerException: Cannot invoke save\n"
                "\tat demo.SavePlugin.run(SavePlugin.java:18)\n")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.txt"
            path.write_text(text, encoding="utf-8")
            events, warnings = analyze_logs.load_events(path)
            self.assertEqual(2, len(events))
            self.assertEqual([], warnings)
            result = self.analyze(events)
            self.assertEqual([], result["exceptions"])
            self.assertEqual([], result["traceTrees"])
            self.assertEqual(text, path.read_text(encoding="utf-8"))

    def test_classification_reasons_retain_all_applicable_rules(self):
        message = ("java.lang.NullPointerException: synthetic failure\n"
                   "\tat demo.SavePlugin.run(SavePlugin.java:18)")
        events = [
            {"level": "INFO", "message": message},
            {"level": "ERROR", "message": "save rejected by validation"},
            {"level": "WARN", "message": "load failed", "exception": {"type": "demo.CustomFailure"}},
            {"level": "INFO", "message": "error counter is zero"},
            {"level": "ERROR", "message": message, "exception": "java.lang.NullPointerException"},
        ]
        result = self.analyze(events)
        self.assertEqual([
            ["java_stack"], ["error_level"], ["exception_field"], ["text_marker"],
            ["error_level", "exception_field", "java_stack"],
        ], [item["classificationReasons"] for item in result["exceptions"]])
        self.assertEqual("INFO", result["exceptions"][0]["level"])
        self.assertNotIn("exception", result["exceptions"][0])

    def test_adjacent_json_records_do_not_form_a_stack(self):
        for trace in ("", "trace-alpha"):
            with self.subTest(trace=trace):
                events = [{"level": "WARN", "traceId": trace, "message": message}
                          for message in ("java.lang.NullPointerException: synthetic failure",
                                          "\tat demo.SavePlugin.run(SavePlugin.java:18)")]
                result = self.analyze(events)
                self.assertEqual(2, result["summary"]["eventCount"])
                self.assertEqual([], result["exceptions"])

    def test_summary_counts_all_stack_events_beyond_evidence_limit(self):
        event = {"level": "WARN", "message": (
            "java.lang.NullPointerException: synthetic failure\n"
            "\tat demo.SavePlugin.run(SavePlugin.java:18)")}
        result = self.analyze([event.copy() for _ in range(105)])
        self.assertEqual(105, result["summary"]["eventCount"])
        self.assertEqual(105, result["summary"]["exceptionCount"])
        self.assertEqual(100, len(result["exceptions"]))

    def test_stack_classification_survives_sql_message_redaction(self):
        message = ("java.sql.SQLException: select * from demo_table where code='synthetic-literal'\n"
                   "\tat demo.Target.execute(Target.java:12)")
        result = self.analyze([{"level": "WARN", "message": message}])
        self.assertEqual(1, result["summary"]["exceptionCount"])
        item = result["exceptions"][0]
        self.assertEqual(["java_stack"], item["classificationReasons"])
        self.assertEqual("WARN", item["level"])
        self.assertNotIn("exception", item)
        self.assertIn("java.sql.SQLException", item["message"])
        self.assertIn("code=?", item["message"])
        self.assertNotIn("synthetic-literal", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
