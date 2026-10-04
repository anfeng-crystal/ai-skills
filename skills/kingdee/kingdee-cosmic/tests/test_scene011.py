"""SCENE-011 syntactic scope regressions; no SDK or Java platform execution."""
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
from lint.base import parse_java
from lint.scene_check import check


class MissingSuperScopeTest(unittest.TestCase):
    def findings(self, body, declaration="class Demo extends AbstractFormPlugin"):
        source = (declaration + " {\n"
                  "    @Override\n"
                  "    public void initialize() {\n" + body + "\n"
                  "    }\n}\n")
        return self.check_source(source)

    def check_source(self, source):
        lines = source.splitlines()
        tree, _ = parse_java(lines)
        self.assertFalse(tree.root_node.has_error, source)
        return [issue for issue in check("Synthetic.java", lines)
                if issue.rule_id == "SCENE-011"]

    def assert_missing(self, body):
        issues = self.findings(body)
        self.assertEqual([3], [issue.line for issue in issues])
        self.assertEqual("WARNING", issues[0].severity.value)
        return issues[0]

    def test_missing_call_remains_a_review_warning(self):
        self.assert_missing("        int business = 1;")

    def test_fix_hint_requires_parent_contract_not_first_statement(self):
        issue = self.assert_missing("")
        self.assertNotIn("首行", issue.fix_hint)
        self.assertIn("父实现", issue.fix_hint)
        self.assertIn("位置", issue.fix_hint)
        self.assertIn("空实现", issue.fix_hint)

    def test_direct_call_preserved_at_any_statement_position(self):
        for body in ("super.initialize();", "int x = 1; super.initialize();",
                     "{ super.initialize(); }", "super /* comment */ . initialize ();",
                     "super.\ninitialize();"):
            with self.subTest(body=body):
                self.assertEqual([], self.findings(body))

    def test_comment_and_literal_text_cannot_supply_a_call(self):
        for body in ("// super.initialize();", "/* super.initialize(); */",
                     "/*\nsuper.initialize();\n*/",
                     'String note = "super.initialize();";',
                     'String note = """\nsuper.initialize();\n""";'):
            with self.subTest(body=body):
                self.assert_missing(body)

    def test_anonymous_class_call_does_not_satisfy_outer_method(self):
        self.assert_missing("""Object child = new Parent() {
            @Override public void initialize() { super.initialize(); }
        };""")

    def test_local_class_call_does_not_satisfy_outer_method(self):
        self.assert_missing("""class Local extends Parent {
            @Override public void initialize() { super.initialize(); }
        }""")

    def test_deferred_lambda_does_not_satisfy_outer_method(self):
        self.assert_missing("Runnable deferred = () -> super.initialize();")

    def test_direct_outer_call_survives_nested_scopes(self):
        self.assertEqual([], self.findings("""Object child = new Parent() {
            @Override public void initialize() { }
        };
        super.initialize();"""))

    def test_other_super_method_does_not_satisfy_override(self):
        self.assert_missing("super.registerListener();")

    def test_interface_only_plugins_do_not_require_class_super(self):
        for declaration in ("class Demo implements IWorkflowPlugin",
                            "class Demo implements IOperationServicePlugIn"):
            with self.subTest(declaration=declaration):
                self.assertEqual([], self.findings("", declaration))

    def test_nested_recognized_plugin_is_reviewed_in_its_own_scope(self):
        source = """class Outer extends AbstractFormPlugin {
    @Override public void initialize() {
        class Inner extends AbstractFormPlugin {
            @Override public void initialize() { }
        }
        super.initialize();
    }
}
"""
        self.assertEqual([4], [i.line for i in self.check_source(source)])

    def test_conditional_call_is_presence_not_all_paths_proof(self):
        # Intentional boundary: no control-flow or interprocedural verification.
        self.assertEqual([], self.findings("if (ready) super.initialize();"))


if __name__ == "__main__":
    unittest.main()
