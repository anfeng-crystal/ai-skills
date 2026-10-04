import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
POST_LINT = SKILL_ROOT / "scripts" / "cosmic-post-lint.py"


class ExceptionRecommendationTest(unittest.TestCase):
    def check_source(self, source):
        with tempfile.TemporaryDirectory(prefix="cosmic exception contract ") as name:
            target = Path(name) / "Demo.java"
            target.write_text(source, encoding="utf-8")
            env = os.environ.copy()
            env.pop("OK_COSMIC_KNOWLEDGE_DB", None)
            result = subprocess.run(
                [sys.executable, str(POST_LINT), str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            return result, json.loads(result.stdout)

    def test_jdk_exception_spellings_remain_nonblocking_recommendations(self):
        for prefix in ("", "java.lang."):
            for exception in ("RuntimeException", "IllegalArgumentException", "IllegalStateException"):
                with self.subTest(exception=prefix + exception):
                    result, report = self.check_source(
                        "public class Demo {\n"
                        "    void reject() {\n"
                        f'        throw new {prefix}{exception}("invalid argument");\n'
                        "    }\n}\n"
                    )
                    findings = [i for i in report["issues"] if i["rule_id"] == "STYLE-018"]
                    self.assertEqual(1, len(findings))
                    self.assertEqual("WARNING", findings[0]["severity"])
                    self.assertEqual("B", findings[0]["layer"])
                    self.assertIn("cause", findings[0]["fix_hint"])
                    self.assertIn("既有合同", findings[0]["fix_hint"])
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertTrue(report["summary"]["passed"])

    def test_platform_wrapping_and_noncode_mentions_do_not_match(self):
        result, report = self.check_source(
            "import kd.bos.exception.KDBizException;\n"
            "import kd.bos.exception.KDException;\n"
            "import kd.bos.exception.ErrorCode;\n"
            "public class Demo {\n"
            '    String text = "throw new IllegalArgumentException()";\n'
            "    // throw new RuntimeException();\n"
            "    void business(Throwable cause) {\n"
            '        throw new KDBizException(cause, new ErrorCode("demo.biz", "业务拒绝"));\n'
            "    }\n"
            "    void system(Throwable cause) {\n"
            '        throw new KDException(cause, new ErrorCode("demo.system", "系统错误"));\n'
            "    }\n}\n"
        )
        self.assertEqual([], [i for i in report["issues"] if i["rule_id"] == "STYLE-018"])
        self.assertEqual(0, result.returncode, result.stderr)

    def test_other_a_layer_gate_still_blocks_with_exception_recommendation(self):
        result, report = self.check_source(
            "public class Demo {\n"
            "    void fail(Exception cause) {\n"
            "        cause.printStackTrace();\n"
            '        throw new IllegalArgumentException("invalid argument", cause);\n'
            "    }\n}\n"
        )
        issues = {i["rule_id"]: i for i in report["issues"]}
        self.assertEqual(("A", "ERROR"), (issues["STYLE-009"]["layer"], issues["STYLE-009"]["severity"]))
        self.assertEqual(("B", "WARNING"), (issues["STYLE-018"]["layer"], issues["STYLE-018"]["severity"]))
        self.assertEqual(1, report["summary"]["errors"])
        self.assertFalse(report["summary"]["passed"])
        self.assertNotEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()
