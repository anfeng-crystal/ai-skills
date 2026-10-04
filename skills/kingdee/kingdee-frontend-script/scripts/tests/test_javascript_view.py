from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'validate_frontend.py'
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location('frontend_view_tests', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class JavascriptViewTests(unittest.TestCase):
    def codes(self, source):
        return {item.code for item in MODULE.validate_javascript(source, 'synthetic.js')}

    def cli(self, source, output_format='json'):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'page with spaces.js'
            path.write_text(source, encoding='utf-8')
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = MODULE.main([str(path), '--format', output_format])
            return code, stdout.getvalue(), stderr.getvalue()

    def test_comments_and_strings_cannot_supply_cleanup_or_origin(self):
        cases = [
            ("node.addEventListener('message', handler);\n// node.removeEventListener('message', handler); event.origin", {'JS001', 'JS004'}),
            ("node.addEventListener('message', handler);\nconst s=\"node.removeEventListener('message', handler); event.origin\";", {'JS001', 'JS004'}),
            ('setInterval(tick,1000); /* clearInterval(timer) */', {'JS002'}),
            ('node.appendChild(child); const note="node.remove()";', {'JS003'}),
        ]
        for source, expected in cases:
            with self.subTest(source=source): self.assertEqual(expected, self.codes(source))

    def test_documentation_text_does_not_create_resources(self):
        source = '''// node.addEventListener('message', handler)
const note="setInterval(tick,1000); node.appendChild(child)";
const template=`node.addEventListener('message', handler)`;
'''
        self.assertEqual(set(), self.codes(source))

    def test_event_names_remain_data_not_executable_text(self):
        source = '''node.addEventListener('setInterval(', handler);
node.removeEventListener('setInterval(', handler);'''
        self.assertEqual(set(), self.codes(source))
        self.assertEqual({'JS001'}, self.codes("node.addEventListener(/* event */ 'click', handler);"))

    def test_real_cleanup_and_message_origin_are_preserved(self):
        source = '''node.addEventListener('message', handler);
node.removeEventListener('message', handler);
const allowed=event.origin;
const timer=setInterval(tick,1000); clearInterval(timer);
node.appendChild(child); node.removeChild(child);'''
        self.assertEqual(set(), self.codes(source))

    def test_template_raw_text_does_not_clear_timer(self):
        self.assertEqual({'JS002'}, self.codes('setInterval(tick,1000); const raw=`clearInterval(timer)`;'))

    def test_template_expression_and_nested_expression_keep_real_calls(self):
        for source in ('const view=`${setInterval(tick,1000)}`;',
                       'const view=`raw ${`nested ${setInterval(tick,1000)}`}`;',
                       'const view=`${({nested:{value:setInterval(tick,1000)}}).nested.value}`;'):
            with self.subTest(source=source): self.assertEqual({'JS002'}, self.codes(source))
        self.assertEqual(set(), self.codes('setInterval(tick,1000); const view=`${clearInterval(timer)}`;'))

    def test_template_boundaries_do_not_invent_cleanup_call(self):
        self.assertEqual({'JS002'}, self.codes('setInterval(tick,1000); const view=`${clearInterval}`(timer);'))

    def test_escaped_quotes_and_comment_markers_do_not_hide_following_code(self):
        source = r'''const quoted="\\\"/* clearInterval(timer) //";'''+ '\nsetInterval(tick,1000);'
        self.assertEqual({'JS002'}, self.codes(source))

    def test_regex_text_does_not_clear_timer(self):
        for pattern in ('/clearInterval(timer)/', r'/[/*]clearInterval(timer)\//g'):
            with self.subTest(pattern=pattern):
                self.assertEqual({'JS002'}, self.codes('setInterval(tick,1000); const pattern='+pattern+';'))

    def test_regex_after_control_parentheses_is_not_division(self):
        self.assertEqual({'JS002'}, self.codes('setInterval(tick,1000); if (ready) /clearInterval(timer)/.test(text);'))

    def test_division_and_comparison_are_not_rejected_or_partial(self):
        code, output, _ = self.cli('const ratio=total / count; const smaller=ratio < limit; const shifted=total << 1;')
        result = json.loads(output)
        self.assertEqual(0, code)
        self.assertEqual('pass', result['status'])
        self.assertNotEqual('partial', result.get('analysis'))

    def test_keyword_property_before_division_does_not_hide_live_call(self):
        for property_name in ('return', 'throw', 'yield', 'await'):
            with self.subTest(property_name=property_name):
                self.assertEqual({'JS002'}, self.codes(f'const ratio=obj.{property_name} / setInterval(tick,1000) / 2;'))

    def test_original_line_numbers_survive_comments_strings_and_templates(self):
        source = '/* fake\nclearInterval(timer) */\nconst raw=`fake\nclearInterval(timer)`;\nsetInterval(tick,1000);'
        for text in (source, source.replace('\n', '\r\n')):
            issues = MODULE.validate_javascript(text, 'line.js')
            self.assertEqual([('JS002', 5)], [(item.code,item.line) for item in issues])

    def test_unknown_syntax_is_partial_and_keeps_resource_clues(self):
        for source in ('setInterval(tick,1000); const view=<div>clearInterval(timer)</div>;',
                       'setInterval(tick,1000); if(ready){} /clearInterval(timer)/.test(text);'):
            with self.subTest(source=source):
                code, output, _ = self.cli(source)
                result = json.loads(output)
                self.assertEqual(1, code)
                self.assertEqual('partial', result['analysis'])
                self.assertTrue(result['warnings'])
                self.assertIn('JS002', {item['code'] for item in result['issues']})

    def test_partial_without_findings_is_not_silent_pass(self):
        code, output, _ = self.cli('const view=<div/>;')
        result=json.loads(output)
        self.assertEqual(0, code)
        self.assertEqual('partial', result['status'])
        self.assertEqual('partial', result['analysis'])
        code, output, _ = self.cli('const view=<div/>;', 'text')
        self.assertEqual(0, code)
        self.assertIn('PARTIAL', output)
        self.assertNotIn('PASS:', output)

    def test_template_depth_boundary_is_partial_not_recursion_error(self):
        for depth in (32, 33, 80):
            with self.subTest(depth=depth):
                source='setInterval(tick,1000); const deep='+'`${'*depth+'0'+'}`'*depth+';'
                code, output, _ = self.cli(source)
                result=json.loads(output)
                self.assertEqual(1, code)
                if depth <= 32:
                    self.assertNotEqual('partial', result.get('analysis'))
                else:
                    self.assertEqual('partial', result['analysis'])
                    self.assertTrue(any('depth' in item['reason'].lower() for item in result['warnings']))

    def test_contextual_keyword_division_preserves_live_call_clues(self):
        for word in ('of', 'await', 'yield'):
            for call, code in (("setInterval(tick,1000)", 'JS002'),
                               ("node.appendChild(child)", 'JS003'),
                               ("node.addEventListener('message',handler)", 'JS001')):
                with self.subTest(word=word, call=call):
                    _, output, _ = self.cli(f'const {word}=8; {word} / {call} / 2;')
                    result=json.loads(output)
                    self.assertEqual('partial', result['analysis'])
                    self.assertIn(code, {item['code'] for item in result['issues']})

    def test_unclosed_or_mismatched_code_delimiters_are_partial(self):
        for source in ('function sample(){', 'const value=(1;', 'const value=[1;',
                       'const value=(1];', 'const value=`${(1}`;'):
            with self.subTest(source=source):
                _, output, _ = self.cli(source)
                self.assertEqual('partial', json.loads(output)['analysis'])

    def test_unclosed_literal_reports_partial(self):
        for source in ('const value="unfinished', 'const value=`unfinished', '/* unfinished'):
            with self.subTest(source=source):
                _, output, _ = self.cli(source)
                self.assertEqual('partial', json.loads(output)['analysis'])


if __name__ == '__main__':
    unittest.main()
