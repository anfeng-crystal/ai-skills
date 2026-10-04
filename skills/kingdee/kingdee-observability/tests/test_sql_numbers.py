import json
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import analyze_logs
import redact


class SqlNumberTest(unittest.TestCase):
    def test_decimal_and_exponent_literals_are_redacted(self):
        for literal in ("42", "42.5", ".5", "1.", "1e3", "1E+3", "1E-3", ".5e+2", "1.e-2"):
            with self.subTest(literal=literal):
                self.assertEqual("SELECT ?", redact.sanitize_sql("SELECT " + literal))

    def test_unary_signs_keep_positive_and_negative_literal_signatures_together(self):
        for literal in ("42", "-42", "+42", "-.5", "+.5", "-1E3", "+1E-3"):
            with self.subTest(literal=literal):
                self.assertEqual("SELECT * FROM t WHERE id=?", redact.sanitize_sql(
                    "SELECT * FROM t WHERE id=" + literal))
                self.assertEqual("SELECT ?", redact.sanitize_sql("SELECT " + literal))
                self.assertEqual("SELECT f(?)", redact.sanitize_sql("SELECT f(" + literal + ")"))

    def test_binary_arithmetic_keeps_operators(self):
        cases = {
            "SELECT amount-42": "SELECT amount-?",
            "SELECT amount -42": "SELECT amount -?",
            "SELECT amount - 42": "SELECT amount - ?",
            "SELECT amount+42": "SELECT amount+?",
            "SELECT amount +42": "SELECT amount +?",
            "SELECT 42-7": "SELECT ?-?",
            "SELECT 42 -7": "SELECT ? -?",
            "SELECT (amount)-42": "SELECT (amount)-?",
            "SELECT :1-42, $1 -42, ?1 -42": "SELECT :1-?, $1 -?, ?1 -?",
            "SELECT 1E-3-2E-3": "SELECT ?-?",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(expected, redact.sanitize_sql(source))

    def test_plain_identifiers_parameters_and_existing_quote_handling(self):
        source = "SELECT column1, t2.amount3, $1, :1, ?1, @p1, :value2 FROM table9"
        self.assertEqual(source, redact.sanitize_sql(source))
        self.assertEqual("SELECT ?", redact.sanitize_sql("SELECT 'O''Brien 42'"))
        # No target SQL mode is known: do not newly exempt double-quoted text.
        self.assertEqual('SELECT "?"', redact.sanitize_sql('SELECT "42"'))

    def test_equivalent_numeric_forms_group_in_one_trace_without_literal_leak(self):
        events = [
            {"traceId": "synthetic-sql", "durationMs": 1500,
             "sql": "SELECT * FROM t WHERE amount=" + literal}
            for literal in ("1e3", "-.5", "1.")
        ]
        result = analyze_logs.analyze(events, slow_sql_ms=1000, n_plus_one_threshold=3)
        self.assertEqual(3, result["summary"]["slowSqlCount"])
        self.assertEqual(1, result["summary"]["possibleNPlusOneCount"])
        candidate = result["possibleNPlusOne"][0]
        self.assertEqual("SELECT * FROM t WHERE amount=?", candidate["sqlSignature"])
        self.assertEqual(3, candidate["count"])
        self.assertEqual("hypothesis", candidate["confidence"])
        for literal in ("1e3", "-.5", "1."):
            self.assertNotIn(literal, json.dumps(result))


if __name__ == "__main__":
    unittest.main()
