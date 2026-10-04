import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
from lint import style_check
from lint.base import Severity


class StyleContractTest(unittest.TestCase):
    def findings(self, source, rule):
        return [x for x in style_check.check("Demo.java", source.splitlines())
                if x.rule_id == rule]

    def test_positive_and_range_checks_are_not_empty_pk_checks(self):
        for comparison in ("pk <= 0", "id < 1", "billId < 0L", "recordPk <= 1", "id == 1"):
            with self.subTest(comparison=comparison):
                self.assertEqual([], self.findings("boolean invalid = " + comparison + ";", "STYLE-026"))

    def test_pk_hint_preserves_type_missing_and_positive_contracts(self):
        for code in ('return billId == null;', 'return billPk != null;',
                     'return id == 0L;', 'return row.get("id") == null;',
                     'Integer id = null; boolean missing = id == null;'):
            with self.subTest(code=code):
                findings = self.findings(code, "STYLE-026")
                self.assertEqual(1, len(findings))
                issue = findings[0]
                self.assertEqual(Severity.INFO, issue.severity)
                self.assertIn("类型", issue.fix_hint)
                self.assertIn("查询未命中", issue.fix_hint)
                self.assertIn("正数", issue.fix_hint)
                self.assertNotIn("主键默认值为 0L", issue.message)

    def test_existing_pk_helper_remains_excluded(self):
        self.assertEqual([], self.findings('return EntityUtils.isEmptyPk(pk);', "STYLE-026"))

    def test_decimal_null_and_rounding_contracts_are_not_replaced(self):
        cases = ['return amount != null && amount.compareTo(BigDecimal.ZERO) > 0;',
                 'return amount.divide(total, 2, RoundingMode.HALF_UP);',
                 'return amount.add(BigDecimal.ONE);']
        for code in cases:
            with self.subTest(code=code):
                issue, = self.findings(code, "STYLE-027")
                self.assertEqual(Severity.INFO, issue.severity)
                for contract in ("null", "scale", "RoundingMode", "比较"):
                    self.assertIn(contract, issue.fix_hint)
                self.assertIn("不自动", issue.fix_hint)

    def test_existing_decimal_helper_remains_excluded(self):
        self.assertEqual([], self.findings('return BigDecimalUtils.add(a, b);', "STYLE-027"))

    def test_qfilter_literal_is_advice_not_runtime_failure(self):
        for operator in ("=", "<>", "like", "not in", "unknown_operator"):
            with self.subTest(operator=operator):
                code = 'return new QFilter("status", "' + operator + '", value);'
                issue, = self.findings(code, "STYLE-024")
                self.assertEqual(Severity.INFO, issue.severity)
                self.assertIn("String", issue.fix_hint)
                self.assertIn("目标", issue.fix_hint)
                self.assertNotIn("枚举", issue.message + issue.fix_hint)
                self.assertNotIn("崩溃", issue.message + issue.fix_hint)

    def test_qcp_constant_does_not_require_literal_advice(self):
        self.assertEqual([], self.findings('return new QFilter("status", QCP.equals, value);', "STYLE-024"))

    def test_comments_and_text_are_not_contract_calls(self):
        source = r'''class Demo {
    // new QFilter("status", "=", value); id == null; amount.add(BigDecimal.ONE);
    String text = "new QFilter(field, \"=\", value)";
    String decimal = "amount.add(BigDecimal.ONE)";
    /* id == null; */ int marker = 1;
}'''
        for rule in ("STYLE-024", "STYLE-026", "STYLE-027"):
            with self.subTest(rule=rule):
                self.assertEqual([], self.findings(source, rule))

    def test_literals_alongside_real_code_do_not_hide_or_create_advice(self):
        source = r'''String text = "new QFilter(field, \"=\", value)"; QFilter f = new QFilter("x", QCP.equals, 1);'''
        self.assertEqual([], self.findings(source, "STYLE-024"))
        self.assertEqual(1, len(self.findings('/* hint */ QFilter f = new QFilter("x", "=", 1);', "STYLE-024")))

    def test_cli_keeps_advice_nonblocking_and_other_error_gate(self):
        with tempfile.TemporaryDirectory(prefix="style contract ") as name:
            path = Path(name) / "Demo.java"
            path.write_text('class Demo { Object f() { return new QFilter("x", "=", 1); } }')
            env = os.environ.copy(); env.pop("OK_COSMIC_KNOWLEDGE_DB", None)
            cmd = [sys.executable, str(SKILL_ROOT / "scripts" / "cosmic-post-lint.py"), str(path), "--json"]
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            report = json.loads(result.stdout)
            self.assertEqual(0, result.returncode, result.stderr)
            issue, = [x for x in report["issues"] if x["rule_id"] == "STYLE-024"]
            self.assertEqual("INFO", issue["severity"])
            path.write_text('class Demo { void f(Exception e) { e.printStackTrace(); } }')
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            self.assertNotEqual(0, result.returncode)
            report = json.loads(result.stdout)
            self.assertTrue(any(x["rule_id"] == "STYLE-009" and x["severity"] == "ERROR" for x in report["issues"]))


if __name__ == "__main__":
    unittest.main()
