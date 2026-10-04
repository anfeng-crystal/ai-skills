import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

SPEC = importlib.util.spec_from_file_location(
    'preflight', Path(__file__).resolve().parents[1] / 'validate_import_workbook.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
CONTRACT = {
    'sheet': 'sheet1', 'header_row': 3, 'data_start_row': 5,
    'key_field': 'number', 'parent_field': 'parent.number',
    'fields': {'number': {'required': True, 'text': True, 'max_length': 8},
               'status': {'required': True, 'choices': ['已审核']}}
}


def cell(address, value, kind='inlineStr'):
    payload = '<is><t>' + value + '</t></is>' if kind == 'inlineStr' else '<v>' + value + '</v>'
    return '<c r="' + address + '" t="' + kind + '">' + payload + '</c>'


def make_book(path, rows=(), extra=None, header='number', prefix=False):
    data = '<row r="3">' + cell('A3', header) + cell('B3', 'status') + cell('C3', 'parent.number') + '</row>'
    for index, values in enumerate(rows, 5):
        data += '<row r="' + str(index) + '">'
        data += ''.join(cell(column + str(index), value) for column, value in zip('ABC', values))
        data += '</row>'
    worksheet = '<worksheet xmlns="' + NS + '"><sheetData>' + data + '</sheetData></worksheet>'
    if prefix:
        worksheet = worksheet.replace('<worksheet xmlns=', '<m:worksheet xmlns:m=').replace('</worksheet>', '</m:worksheet>')
        # The default namespace keeps child nodes valid while the root prefix changes.
        worksheet = worksheet.replace('xmlns:m="' + NS + '"', 'xmlns:m="' + NS + '" xmlns="' + NS + '"')
    parts = {
        'xl/workbook.xml': '<workbook xmlns="' + NS + '" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="sheet1" sheetId="1" r:id="rId1"/><sheet name="dropdown" sheetId="2" state="hidden" r:id="rId2"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': worksheet,
        'xl/worksheets/sheet2.xml': '<worksheet xmlns="' + NS + '"><sheetData/></worksheet>',
    }
    parts.update(extra or {})
    with zipfile.ZipFile(path, 'w') as out:
        for name, content in parts.items():
            out.writestr(name, content)


class ImportPreflightTests(unittest.TestCase):
    def run_case(self, rows, contract=None, **options):
        with tempfile.TemporaryDirectory(prefix='import template ') as directory:
            template, candidate = Path(directory) / '原模板.xlsx', Path(directory) / '候选.xlsx'
            make_book(template)
            make_book(candidate, rows, **options)
            before = (template.read_bytes(), candidate.read_bytes())
            result = MODULE.validate(template, candidate, contract or CONTRACT)
            self.assertEqual(before, (template.read_bytes(), candidate.read_bytes()))
            self.assertEqual(result['platform_parse'], 'not_executed')
            return result

    @staticmethod
    def codes(result):
        return {finding['code'] for finding in result['findings']}

    def test_root_and_existing_parent_are_valid_without_writes(self):
        contract = dict(CONTRACT, existing_keys=['001'])
        result = self.run_case([('002', '已审核', '001')], contract)
        self.assertEqual(result['status'], 'static_passed')
        self.assertEqual(result['data_rows'], 1)

    def test_missing_status_and_bad_status(self):
        result = self.run_case([('001', '', ''), ('002', '暂存', '')])
        self.assertTrue({'required_value_missing', 'value_outside_choices'} <= self.codes(result))

    def test_parent_order_does_not_prove_same_batch_import(self):
        result = self.run_case([('001', '已审核', ''), ('002', '已审核', '001')])
        self.assertEqual(result['status'], 'review_required')
        self.assertIn('same_batch_parent_requires_platform_evidence', self.codes(result))

    def test_explicit_same_batch_evidence_removes_only_that_warning(self):
        result = self.run_case([('001', '已审核', ''), ('002', '已审核', '001')],
                               dict(CONTRACT, allow_same_batch_parent=True))
        self.assertEqual(result['status'], 'static_passed')

    def test_missing_parent_cycle_existing_and_duplicate_keys(self):
        result = self.run_case([('001', '已审核', '002'), ('002', '已审核', '001'),
                                ('003', '已审核', '999'), ('003', '已审核', '')],
                               dict(CONTRACT, existing_keys=['003']))
        self.assertTrue({'parent_cycle', 'parent_missing', 'duplicate_or_existing_key'} <= self.codes(result))

    def test_changed_technical_header_blocks(self):
        result = self.run_case([('001', '已审核', '')], header='wrong')
        self.assertIn('template_header_changed', self.codes(result))

    def test_package_and_prefix_changes_need_review(self):
        result = self.run_case([('001', '已审核', '')], prefix=True,
                               extra={'xl/worksheets/sheet2.xml': '<changed/>'})
        self.assertTrue({'unreviewed_package_change', 'worksheet_prefix_changed'} <= self.codes(result))

    def test_length_is_checked_without_exposing_value(self):
        result = self.run_case([('PRIVATE-LONG-IDENTIFIER', '已审核', '')])
        self.assertIn('input_field_too_long', self.codes(result))
        self.assertNotIn('PRIVATE-LONG-IDENTIFIER', str(result))

    def test_unknown_contract_rule_rejected(self):
        contract = copy.deepcopy(CONTRACT)
        contract['fields']['number']['maxLength'] = 4
        with self.assertRaisesRegex(ValueError, 'unknown_field_rule'):
            self.run_case([('001', '已审核', '')], contract)

    def test_uncached_formula_is_reviewed_even_outside_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            template, candidate = Path(directory) / 't.xlsx', Path(directory) / 'c.xlsx'
            make_book(template)
            make_book(candidate, [('001', '已审核', '')])
            with zipfile.ZipFile(candidate) as z:
                parts = {n: z.read(n) for n in z.namelist()}
            part = 'xl/worksheets/sheet1.xml'
            parts[part] = parts[part].replace(b'</row></sheetData>',
                b'</row><row r="6"><c r="B6"><f>1+1</f></c><c r="D6"><f>1+1</f></c></row></sheetData>')
            with zipfile.ZipFile(candidate, 'w') as z:
                for n, data in parts.items():
                    z.writestr(n, data)
            result = MODULE.validate(template, candidate, CONTRACT)
            self.assertTrue({'formula_requires_value_review', 'data_outside_template_columns'} <= self.codes(result))

    def test_invalid_data_style_index_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            template, candidate = Path(directory) / 't.xlsx', Path(directory) / 'c.xlsx'
            make_book(template)
            make_book(candidate, [('001', '已审核', '')])
            with zipfile.ZipFile(candidate) as z:
                parts = {n: z.read(n) for n in z.namelist()}
            parts['xl/worksheets/sheet1.xml'] = parts['xl/worksheets/sheet1.xml'].replace(b'r="A5"', b'r="A5" s="999"')
            parts['xl/styles.xml'] = ('<styleSheet xmlns="' + NS + '"><cellXfs count="1"><xf/></cellXfs></styleSheet>')
            with zipfile.ZipFile(candidate, 'w') as z:
                for n, data in parts.items():
                    z.writestr(n, data)
            self.assertIn('invalid_style_index', self.codes(MODULE.validate(template, candidate, CONTRACT)))

    def test_data_string_encoding_change_requires_review(self):
        with tempfile.TemporaryDirectory() as directory:
            template, candidate = Path(directory) / 't.xlsx', Path(directory) / 'c.xlsx'
            make_book(template)
            make_book(candidate, [('001', '已审核', '')])
            with zipfile.ZipFile(candidate) as z:
                parts = {n: z.read(n) for n in z.namelist()}
            part = 'xl/worksheets/sheet1.xml'
            parts[part] = parts[part].replace(cell('A5', '001').encode(), cell('A5', '001', 'str').encode())
            with zipfile.ZipFile(candidate, 'w') as z:
                for n, data in parts.items():
                    z.writestr(n, data)
            result = MODULE.validate(template, candidate, CONTRACT)
            self.assertEqual(result['status'], 'review_required')
            self.assertIn('string_encoding_changed', self.codes(result))

    def test_broken_shared_string_reference_blocks(self):
        with self.assertRaisesRegex(ValueError, 'invalid_shared_string_index'):
            MODULE.cells(MODULE.ET.fromstring('<worksheet xmlns="' + NS + '"><sheetData>'
                '<row r="5"><c r="A5" t="s"><v>999</v></c></row></sheetData></worksheet>'), ['only'])


if __name__ == '__main__':
    unittest.main()
