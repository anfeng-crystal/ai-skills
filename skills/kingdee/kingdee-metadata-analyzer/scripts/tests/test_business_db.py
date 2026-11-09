import importlib.util
import io
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from business_db import (RoutingError, configured_center, entity_mapping,
                         route_items, select_center, select_schema)


def parse(text):
    return "xml", ET.fromstring(text)


class BusinessDbTest(unittest.TestCase):
    def test_route_formats_use_complete_items(self):
        for value in ('secd', ' pmse, secd ', '["pmse", "secd"]', ['pmse', ' secd ']):
            self.assertIn('secd', route_items(value))
        self.assertNotIn('secd', route_items('secd_archive, pmse'))
        self.assertEqual(set(), route_items(None))
        with self.assertRaises(RoutingError):
            route_items('[broken')

    def test_blank_schema_is_unset_and_unique_actual_schema_wins(self):
        for value in (None, '', ' ', '\t\n'):
            self.assertEqual(('actual', False, True), select_schema(['actual'], value, 'actual'))
        self.assertEqual(('actual', True, True), select_schema(['actual'], 'configured', 'actual'))
        self.assertEqual(('selected', False, False), select_schema(['actual', 'selected'], ' selected ', 'actual'))
        with self.assertRaises(RoutingError):
            select_schema(['one', 'two'], ' ', 'one')

    def test_login_config_is_found_in_submodule_not_other_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / 'code' / 'debug' / 'config'
            config.mkdir(parents=True)
            (config / 'login-prod.properties').write_text('accountId = dc-prod\npassword=unused\n')
            (config / 'login-dev.properties').write_text('accountId=dc-dev\n')
            self.assertEqual(('dc-prod', 'login_config', True), configured_center(root, 'prod'))
            self.assertEqual(('dc-user', 'argument', False), configured_center(root, 'prod', 'dc-user'))
            (root / 'login-prod.properties').write_text('accountId=conflicting\n')
            with self.assertRaisesRegex(RoutingError, 'data_center_config_ambiguous'):
                configured_center(root, 'prod')

    def test_known_center_filters_shared_metadata_database(self):
        self.assertEqual('b', select_center(['a', 'b'], 'b'))
        with self.assertRaisesRegex(RoutingError, 'data_center_metadata_mismatch'):
            select_center(['a'], 'b')
        with self.assertRaisesRegex(RoutingError, 'data_center_required'):
            select_center(['a', 'b'], None)

    def test_main_mapping_ignores_entry_and_preserves_child_override(self):
        child = '<EntityMetadata><ParentId>parent</ParentId><Items><BillEntity><TableName>child_table</TableName><EntryEntity><dbRoute>wrong</dbRoute></EntryEntity></BillEntity></Items></EntityMetadata>'
        parent = '<EntityMetadata><Items><BillEntity><TableName>parent_table</TableName><dbRoute>pmse</dbRoute></BillEntity></Items></EntityMetadata>'
        rows = {('child', False): [('child-id', child)], ('parent', True): [('parent', parent)]}
        result = entity_mapping('child', lambda key, by_id: rows[(key, by_id)], parse)
        self.assertEqual({'entity': 'child', 'route': 'pmse', 'table': 'child_table'}, result)

    def test_main_table_can_differ_from_entity_number(self):
        xml = '<EntityMetadata><Items><BillEntity><TableName>unrelated_table</TableName><dbRoute>secd</dbRoute></BillEntity></Items></EntityMetadata>'
        result = entity_mapping('report', lambda *_: [('id', xml)], parse)
        self.assertEqual('unrelated_table', result['table'])

    def test_inheritance_cycle_does_not_loop_or_return_partial_mapping(self):
        xml = '<EntityMetadata><ParentId>same</ParentId><Items><BillEntity><TableName>partial</TableName></BillEntity></Items></EntityMetadata>'
        with self.assertRaisesRegex(RoutingError, 'entity_inheritance_cycle'):
            entity_mapping('child', lambda *_: [('same', xml)], parse)

    def test_cli_errors_do_not_expose_connection_details(self):
        spec = importlib.util.spec_from_file_location('route_cli', SCRIPTS / 'resolve-business-db.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        output = io.StringIO()
        with patch.object(module, 'resolve', side_effect=RuntimeError('secret host password')), redirect_stdout(output):
            code = module.main(['--config', 'unused', '--environment', 'prod', 'entity'])
        self.assertEqual(1, code)
        self.assertEqual({'status': 'failed', 'error': 'RuntimeError'}, json.loads(output.getvalue()))


if __name__ == '__main__':
    unittest.main()
