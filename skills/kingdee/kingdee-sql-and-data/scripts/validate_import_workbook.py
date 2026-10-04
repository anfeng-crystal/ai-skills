#!/usr/bin/env python3
"""Read-only preflight for filling a platform-exported XLSX import template."""
import argparse
from collections import defaultdict
import copy
import json
from pathlib import Path
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def workbook(path):
    with zipfile.ZipFile(path) as archive:
        if len(archive.namelist()) != len(set(archive.namelist())):
            raise ValueError('duplicate_zip_member')
        members = {name: archive.read(name) for name in archive.namelist()}
    root = ET.fromstring(members['xl/workbook.xml'])
    relations = ET.fromstring(members['xl/_rels/workbook.xml.rels'])
    targets = {x.get('Id'): x.get('Target') for x in relations}
    sheets = {}
    for sheet in root.find(NS + 'sheets'):
        target = targets[sheet.get(REL + 'id')]
        part = posixpath.normpath(target.lstrip('/') if target.startswith('/')
                                 else posixpath.join('xl', target))
        sheets[sheet.get('name')] = part
    strings = []
    if 'xl/sharedStrings.xml' in members:
        strings = [''.join(n.itertext()) for n in ET.fromstring(members['xl/sharedStrings.xml'])]
    return members, sheets, strings


def cells(root, strings):
    result = {}
    for cell in root.findall('.//' + NS + 'sheetData/' + NS + 'row/' + NS + 'c'):
        address = cell.get('r')
        if not address or address in result or not re.fullmatch(r'[A-Z]+[1-9][0-9]*', address):
            raise ValueError('invalid_or_duplicate_cell_address')
        kind = cell.get('t', 'n')
        raw = cell.findtext(NS + 'v', '')
        if kind == 's':
            index = int(raw)
            if index < 0 or index >= len(strings):
                raise ValueError('invalid_shared_string_index')
            value = strings[index]
        elif kind == 'inlineStr':
            value = ''.join(cell.find(NS + 'is').itertext())
        else:
            value = raw
        result[address] = (value, kind, cell.get('s'), cell.find(NS + 'f') is not None)
    return result


def outside_data(root):
    root = copy.deepcopy(root)
    for child in list(root):
        if child.tag in (NS + 'sheetData', NS + 'dimension'):
            root.remove(child)
    return ET.tostring(root)


def validate(template, candidate, contract):
    findings = defaultdict(list)

    def add(severity, code, location=''):
        findings[(severity, code)].append(location)

    allowed = {'sheet', 'header_row', 'data_start_row', 'key_field', 'parent_field',
               'existing_keys', 'allow_same_batch_parent', 'fields'}
    if set(contract) - allowed:
        raise ValueError('unknown_contract_key')
    header, start = contract['header_row'], contract['data_start_row']
    if type(header) is not int or type(start) is not int or not 0 < header < start:
        raise ValueError('invalid_header_or_data_row')
    if type(contract.get('allow_same_batch_parent', False)) is not bool:
        raise ValueError('invalid_same_batch_policy')
    existing_list = contract.get('existing_keys', [])
    if not isinstance(existing_list, list) or any(not isinstance(x, str) for x in existing_list):
        raise ValueError('invalid_existing_keys')
    rules = contract.get('fields', {})
    for rule in rules.values():
        if set(rule) - {'required', 'max_length', 'choices', 'text'}:
            raise ValueError('unknown_field_rule')
        for name in ('required', 'text'):
            if name in rule and type(rule[name]) is not bool:
                raise ValueError('invalid_boolean_rule')
        if 'max_length' in rule and (type(rule['max_length']) is not int or rule['max_length'] < 1):
            raise ValueError('invalid_max_length')
        if 'choices' in rule and (not isinstance(rule['choices'], list) or
                                  any(not isinstance(x, str) for x in rule['choices'])):
            raise ValueError('invalid_choices')
    tm, ts, tv = workbook(template)
    cm, cs, cv = workbook(candidate)
    sheet = contract['sheet']
    if ts != cs or sheet not in ts:
        raise ValueError('sheet_structure_changed')
    part = ts[sheet]
    for member in set(tm) | set(cm):
        if member not in {part, 'xl/sharedStrings.xml'} and tm.get(member) != cm.get(member):
            add('warning', 'unreviewed_package_change', member)
    if cv[:len(tv)] != tv:
        add('warning', 'existing_shared_strings_changed')
    tr, cr = ET.fromstring(tm[part]), ET.fromstring(cm[part])
    tc, cc = cells(tr, tv), cells(cr, cv)
    styles = ET.fromstring(cm['xl/styles.xml']).find(NS + 'cellXfs') if 'xl/styles.xml' in cm else None
    style_count = len(styles) if styles is not None else 0
    for address, cell in cc.items():
        style = cell[2]
        if style is not None and (not style.isdecimal() or int(style) >= style_count):
            add('error', 'invalid_style_index', address)
    if outside_data(tr) != outside_data(cr):
        add('warning', 'sheet_metadata_changed')
    prefix = rb'<((?:[A-Za-z_][\w.-]*:)?worksheet)\b'
    if re.search(prefix, tm[part]).group(1) != re.search(prefix, cm[part]).group(1):
        add('warning', 'worksheet_prefix_changed')
    def row_number(address):
        return int(re.search(r'\d+$', address).group())
    def before_data(all_cells):
        return {a: v for a, v in all_cells.items() if row_number(a) < start}
    if before_data(tc) != before_data(cc):
        add('error', 'template_header_changed')
    fields = {re.sub(r'\d+$', '', a): v[0] for a, v in tc.items()
              if row_number(a) == header and v[0]}
    if len(set(fields.values())) != len(fields):
        raise ValueError('duplicate_technical_header')
    key, parent = contract['key_field'], contract.get('parent_field')
    if any(x not in fields.values() for x in [key] + ([parent] if parent else []) + list(rules)):
        raise ValueError('contract_field_missing_in_template')
    rows = defaultdict(dict)
    baseline_string_types = {v[1] for v in tc.values() if v[1] in ('s', 'str', 'inlineStr')}
    for address, cell in cc.items():
        row = row_number(address)
        if row < start or (not cell[0] and not cell[3]):
            continue
        field = fields.get(re.sub(r'\d+$', '', address))
        if field is None:
            add('error', 'data_outside_template_columns', address)
            continue
        rows[row][field] = cell
        if cell[3]:
            add('warning', 'formula_requires_value_review', address)
        if baseline_string_types and cell[1] in ('s', 'str', 'inlineStr') and cell[1] not in baseline_string_types:
            add('warning', 'string_encoding_changed', address)
    existing = set(existing_list)
    keyed = {}
    for row, data in rows.items():
        identifier = data.get(key, ('',))[0]
        if not identifier:
            add('error', 'key_required', str(row))
        elif identifier in keyed or identifier in existing:
            add('error', 'duplicate_or_existing_key', str(row))
        keyed[identifier] = row
        for field, rule in rules.items():
            value, kind, _, _ = data.get(field, ('', '', None, False))
            if rule.get('required') and not value.strip():
                add('error', 'required_value_missing', str(row) + ':' + field)
            if value and rule.get('text') and kind not in ('s', 'str', 'inlineStr'):
                add('error', 'code_not_stored_as_text', str(row) + ':' + field)
            if value and 'choices' in rule and value not in rule['choices']:
                add('error', 'value_outside_choices', str(row) + ':' + field)
            if 'max_length' in rule and len(value) > rule['max_length']:
                add('error', 'input_field_too_long', str(row) + ':' + field)
    parents = {}
    if parent:
        for row, data in rows.items():
            identifier, ancestor = data.get(key, ('',))[0], data.get(parent, ('',))[0]
            parents[identifier] = ancestor
            if not ancestor or ancestor in existing:
                continue
            if ancestor not in keyed:
                add('error', 'parent_missing', str(row))
            elif not contract.get('allow_same_batch_parent', False):
                add('warning', 'same_batch_parent_requires_platform_evidence', str(row))
        for identifier in parents:
            visited, current = set(), identifier
            while current in parents and current:
                if current in visited:
                    add('error', 'parent_cycle', str(keyed[identifier]))
                    break
                visited.add(current)
                current = parents[current]
    if not rows:
        add('error', 'no_data_rows')
    details = [{'severity': s, 'code': c, 'count': len(v), 'locations': v[:5]}
               for (s, c), v in sorted(findings.items())]
    status = 'failed' if any(x['severity'] == 'error' for x in details) else (
        'review_required' if details else 'static_passed')
    return {'status': status, 'data_rows': len(rows), 'findings': details,
            'platform_parse': 'not_executed', 'derived_field_limits': 'not_checked'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--contract', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(args.template, args.candidate, json.loads(args.contract.read_text(encoding='utf-8')))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, ET.ParseError, zipfile.BadZipFile) as exc:
        # Exception text can contain source cell values or local paths.
        result = {'status': 'failed', 'error': type(exc).__name__, 'code': 'invalid_input_or_contract',
                  'platform_parse': 'not_executed'}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return {'static_passed': 0, 'failed': 1, 'review_required': 2}[result['status']]


if __name__ == '__main__':
    raise SystemExit(main())
