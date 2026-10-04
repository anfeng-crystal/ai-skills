import json
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from validate_ksql import normalize_sql, tokenize_preserve_strings, validate


class KsqlLexicalTest(unittest.TestCase):
    def test_comment_markers_inside_literals_do_not_hide_sql(self):
        for literal in ("'-- marker'", "'/*marker*/'", "'https://example.invalid'",
                        "'can''t -- /*x*/ //  x'"):
            with self.subTest(literal=literal):
                sql = f"SELECT {literal} value FROM t_sample LIMIT 1"
                result = validate(sql)
                self.assertFalse(result['valid'])
                self.assertTrue(any('LIMIT' in e for e in result['errors']))
                tokens, _ = tokenize_preserve_strings(normalize_sql(sql))
                self.assertIn(literal, tokens)

    def test_literal_whitespace_is_preserved(self):
        sql = " SELECT\t' a  b\n c ' value FROM t_sample "
        self.assertEqual(normalize_sql(sql), "SELECT ' a  b\n c ' value FROM t_sample")

    def test_quoted_identifiers_keep_comment_markers(self):
        for identifier in ('"a--b"', '"a""/*b*/"', '[a//b]', '[a]]--b]'):
            with self.subTest(identifier=identifier):
                tokens, _ = tokenize_preserve_strings(normalize_sql(
                    f'SELECT {identifier} FROM t_sample'))
                self.assertIn(identifier, tokens)

    def test_all_supported_comments_are_ignored(self):
        for comment in ('-- LIMIT 1\n', '// LIMIT 1\n', '// LIMIT 1\r\n',
                        '/* LIMIT 1\n */'):
            with self.subTest(comment=comment):
                self.assertTrue(validate(comment + 'SELECT fid FROM t_sample')['valid'])
                self.assertTrue(validate('SELECT fid FROM t_sample ' + comment)['valid'])

    def test_bare_cr_does_not_end_line_comments(self):
        # The verified 7.0 Lexer ends both comment forms at LF, not bare CR.
        for marker in ('--', '//'):
            with self.subTest(marker=marker):
                sql = f'SELECT fid FROM t_sample {marker} note\rLIMIT 1'
                self.assertTrue(validate(sql)['valid'])
                self.assertEqual(normalize_sql(sql), 'SELECT fid FROM t_sample')
                self.assertEqual(validate(f'{marker} note\rSELECT fid FROM t_sample')
                                 ['statement_type'], 'EMPTY')

    def test_line_comments_end_at_lf_or_eof(self):
        for marker in ('--', '//'):
            for newline in ('\n', '\r\n'):
                with self.subTest(marker=marker, newline=newline):
                    sql = f'SELECT fid FROM t_sample {marker} note{newline}LIMIT 1'
                    self.assertTrue(any('LIMIT' in e for e in validate(sql)['errors']))
            with self.subTest(marker=marker, newline='EOF'):
                self.assertTrue(validate(f'SELECT fid FROM t_sample {marker} LIMIT 1')
                                ['valid'])
                self.assertEqual(validate(f'{marker} LIMIT 1')['statement_type'], 'EMPTY')

    def test_comment_only_input_is_empty(self):
        result = validate('// SELECT fid\n/* FROM t */ -- end')
        self.assertFalse(result['valid'])
        self.assertEqual(result['statement_type'], 'EMPTY')

    def test_comment_between_tokens_does_not_join_them(self):
        result = validate('SELECT/* note */fid FROM/* note */t_sample LIMIT 1')
        self.assertEqual(result['statement_type'], 'SELECT')
        self.assertFalse(result['valid'])

    def test_unclosed_lexemes_are_reported(self):
        for sql in ("SELECT 'value", 'SELECT "field', 'SELECT [field',
                    'SELECT fid FROM t_sample /* note'):
            with self.subTest(sql=sql):
                result = validate(sql)
                self.assertFalse(result['valid'])
                self.assertTrue(any('未闭合' in e for e in result['errors']))

    def test_existing_statement_checks_remain_active(self):
        for sql in ('SELECT fid FROM t_sample LIMIT 1', 'UPDATE t_sample t SET fid=1',
                    'MERGE INTO t_sample', 'INSERT t_sample VALUES (1)'):
            with self.subTest(sql=sql):
                self.assertFalse(validate(sql)['valid'])
        self.assertTrue(validate('SELECT TOP 10 fid FROM t_sample')['valid'])

    def test_stdin_cli_preserves_json_contract(self):
        run = subprocess.run([sys.executable, str(SCRIPTS / 'validate_ksql.py'), '-'],
                             input='// note\nSELECT fid FROM t_sample', text=True,
                             capture_output=True, check=True)
        result = json.loads(run.stdout)
        self.assertEqual(set(result), {'valid', 'statement_type', 'errors', 'warnings'})
        self.assertTrue(result['valid'])


if __name__ == '__main__':
    unittest.main()
