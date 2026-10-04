"""Regression for bundled-JAR-proven static false positives; no business execution."""
import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("iscb_lexical_validator", SCRIPTS / "iscb_skill_validator.py")
validator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = validator
spec.loader.exec_module(validator)


class LexicalValidationTests(unittest.TestCase):
    def check(self, script, mode="engine"):
        return validator.check_script(script, mode)

    def codes(self, script, mode="engine"):
        return {finding["code"] for finding in self.check(script, mode)["findings"]}

    def test_comment_contents_do_not_become_code(self):
        self.assertEqual("pass", self.check('// "inventedFunction() ( $src\nreturn 3;')["status"])

    def test_string_contents_do_not_become_calls_or_resources(self):
        for script in ['return "inventedFunction()";', 'return "$src";', 'return "Hash.HmacSHA256(\\"a\\", \\"b\\")";']:
            with self.subTest(script=script):
                self.assertEqual("pass", self.check(script)["status"])

    def test_escaped_quotes_and_comment_markers_stay_in_string(self):
        self.assertEqual("pass", self.check('return "a\\"// inventedFunction()";')["status"])

    def test_actual_unclosed_string_or_delimiter_is_rejected(self):
        self.assertIn("unterminated-string", self.codes('return "missing;'))
        self.assertIn("unbalanced-delimiter", self.codes('return (1 + 2;'))

    def test_local_stream_calls_are_independent_of_whitespace(self):
        for receiver in ["values.each", "values\n.each", "values . each"]:
            with self.subTest(receiver=receiver):
                self.assertEqual("pass", self.check('var values=[1,2]; return ' + receiver + '($ + 1);')["status"])
        self.assertEqual("pass", self.check('var values=[1,2]; return values.filter($ > 1);')["status"])

    def test_local_property_stream_receivers_use_the_bound_root(self):
        for script in [
            'var obj={values:[1,2]}; return obj.values.each($ + 1);',
            'var obj={nested:{values:[1,2,3]}}; return obj.nested.values.filter($ > 1).each($ + 1);',
            'var obj={values:[1,2]}; return obj \n . values \n . each ($ + 1);',
            'var obj={values:[1,2]}; return obj.// between properties\nvalues.each($ + 1);',
            'var obj={String:[1,2]}; return obj.String.each($ + 1);',
            'function transform(obj) { return obj.values.each($ + 1); } var input={values:[1,2]}; return transform(input);',
        ]:
            with self.subTest(script=script):
                self.assertEqual("pass", self.check(script)["status"])

    def test_property_chain_cannot_borrow_a_leaf_binding_or_toolbox(self):
        for script in [
            'var values=[1,2]; return missing.values.each($ + 1);',
            'return missing.String.trim(" x ");',
        ]:
            with self.subTest(script=script):
                self.assertIn("unknown-namespace", self.codes(script))

    def test_local_property_method_still_requires_evidence(self):
        for script in [
            'var obj={values:[1,2]}; return obj.values.invented();',
            'var obj={String:" x "}; return obj.String.trim();',
        ]:
            with self.subTest(script=script):
                self.assertIn("unverified-member-method", self.codes(script))

    def test_partial_property_path_cannot_borrow_a_local_root(self):
        for script in [
            'var obj={values:[1]}; return (missing).obj.values.each($);',
            'var obj={values:[1]}; return missing[0].obj.values.each($);',
        ]:
            with self.subTest(script=script):
                self.assertIn("unverified-member-method", self.codes(script))

    def test_function_and_lambda_parameters_are_local_receivers(self):
        for script in [
            'function transform(values) { return values.each($ + 1); } var items=[1,2]; return transform(items);',
            'var transform = values -> values.each($ + 1); var items=[1,2]; return transform(items);',
            'var transform = (values, unused) -> values.each($ + 1); var items=[1,2]; return transform(items, 0);',
        ]:
            with self.subTest(script=script):
                self.assertEqual("pass", self.check(script)["status"])

    def test_local_bindings_do_not_leak_outside_their_scope(self):
        for script in [
            'function f(values) { return values.each($); } return values.each($);',
            'var f = values -> values.each($); return values.each($);',
            '{ var values=[1]; } return values.each($);',
            'function f(obj) { return obj.values.each($); } return obj.values.each($);',
            'var f = obj -> obj.values.each($); return obj.values.each($);',
        ]:
            with self.subTest(script=script):
                self.assertIn("unknown-namespace", self.codes(script))

    def test_unknown_local_member_is_unverified(self):
        self.assertIn("unverified-member-method", self.codes('var values=[1]; return values.invented();'))
        self.assertNotEqual("pass", self.check('var values=[1]; return values.invented();')["status"])

    def test_local_namespace_shadow_is_not_a_toolbox_call(self):
        self.assertEqual("pass", self.check('var String=[1,2]; return String.each($ + 1);')["status"])
        self.assertIn("unknown-method", self.codes('return String.invented();'))

    def test_real_unknown_calls_and_case_errors_still_fail(self):
        self.assertIn("unknown-global", self.codes('return inventedFunction();'))
        self.assertIn("unknown-namespace", self.codes('return Invented.function();'))
        self.assertIn("case-mismatch", self.codes('return Number.parseint("1");'))

    def test_bare_parse_warning_uses_call_kind_across_whitespace(self):
        self.assertIn("bare-parse", self.codes('return parseInt("12");'))
        for script in ['return Number.parseInt("12");', 'return Number \n . parseInt ("12");']:
            with self.subTest(script=script):
                self.assertEqual("pass", self.check(script)["status"])
                self.assertNotIn("bare-parse", self.codes(script))

    def test_real_literal_argument_checks_are_preserved(self):
        self.assertIn("bizquery-string-connection", self.codes("return bizQuery('ierp', entity, requires, filters);", "platform"))
        self.assertIn("hmac-string-args", self.codes('return Hash.HmacSHA256("a", "b");'))
        self.assertIn("platform-sql-concat", self.codes('var querySQL="SELECT 1 " + "FROM dual"; return querySQL;', "platform"))

    def test_literal_or_comment_imitation_does_not_trigger_argument_checks(self):
        for script in [
            "// bizQuery('ierp', entity, requires, filters);\nreturn 3;",
            'return "bizQuery(\'ierp\', entity, requires, filters)";',
            '// Hash.HmacSHA256("a", "b");\nreturn 3;',
            '// var querySQL="SELECT 1 " + "FROM dual";\nreturn 3;',
        ]:
            with self.subTest(script=script):
                self.assertEqual("pass", self.check(script, "platform")["status"])

    def test_real_platform_resource_remains_reference_only(self):
        self.assertIn("external-resource", self.codes('return $src;'))
        self.assertIn("platform-reference-only", self.codes('return $src;', "platform"))

    def test_mapping_route_is_preserved(self):
        self.assertEqual("pass", self.check('#{new_int_id()}', "mapping")["status"])
        self.assertIn("mapping-expression-profile", self.codes('#{new_int_id()}'))


if __name__ == "__main__":
    unittest.main()
