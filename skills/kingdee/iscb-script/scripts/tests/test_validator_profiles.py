import importlib.util
import json
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = SKILL_ROOT / "scripts" / "iscb_skill_validator.py"
SPEC = importlib.util.spec_from_file_location("iscb_skill_validator", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


class ValidatorProfileTests(unittest.TestCase):
    def test_mapping_direct_macro(self):
        payload = validator.check_mapping_expression("#{new_int_id()}")
        self.assertEqual("pass", payload["status"])

    def test_mapping_aggregation_chain(self):
        payload = validator.check_mapping_expression(
            "split(;)::rtrim(省,市,自治区)::join(,)"
        )
        self.assertEqual("pass", payload["status"])

    def test_mapping_zero_selector_is_rejected(self):
        payload = validator.check_mapping_expression("[0]")
        self.assertEqual("fail", payload["status"])
        self.assertEqual("zero-mapping-selector", payload["findings"][0]["code"])

    def test_engine_profile_rejects_mapping_expression(self):
        payload = validator.check_script("#{new_uuid()}", "engine")
        self.assertEqual("fail", payload["status"])
        self.assertIn(
            "mapping-expression-profile",
            {finding["code"] for finding in payload["findings"]},
        )

    def test_engine_profile_rejects_unknown_global(self):
        payload = validator.check_script("return inventedFunction(1);", "engine")
        self.assertEqual("fail", payload["status"])
        self.assertIn(
            "unknown-global",
            {finding["code"] for finding in payload["findings"]},
        )

    def test_platform_catalog_is_case_sensitive(self):
        payload = validator.check_script(
            "return getpersonbyposition(positionId);", "platform"
        )
        self.assertEqual("fail", payload["status"])
        self.assertIn(
            "case-mismatch",
            {finding["code"] for finding in payload["findings"]},
        )

    def test_platform_profile_accepts_official_catalog_as_reference_only(self):
        script = "var ids = GetPersonByPosition(positionId); return PrivacyTool.convertValue(ids);"
        payload = validator.check_script(script, "platform")
        self.assertEqual("warn", payload["status"])
        self.assertIn(
            "platform-reference-only",
            {finding["code"] for finding in payload["findings"]},
        )

    def test_deprecated_platform_api_is_recognized_and_warned(self):
        payload = validator.check_script("return invokeOpenApi(api, data);", "platform")
        self.assertEqual("warn", payload["status"])
        self.assertIn(
            "deprecated-platform-api",
            {finding["code"] for finding in payload["findings"]},
        )

    def test_unavailable_resource_status_is_version_scoped(self):
        payload = validator.check_script("return MetaSchemaResource;", "platform")
        self.assertEqual("warn", payload["status"])
        self.assertIn(
            "platform-resource-unavailable",
            {finding["code"] for finding in payload["findings"]},
        )

    def test_arraylist_is_platform_reference_not_engine_runtime(self):
        script = "var batch = new java.util.ArrayList(); return batch;"
        self.assertEqual("fail", validator.check_script(script, "engine")["status"])
        self.assertEqual("warn", validator.check_script(script, "platform")["status"])

    def test_platform_sql_concat_is_a_scoped_default_warning(self):
        payload = validator.check_script(
            'var querySQL = "SELECT 1 " + "FROM dual"; return querySQL;', "platform"
        )
        self.assertEqual("warn", payload["status"])
        self.assertIn(
            "platform-sql-concat",
            {finding["code"] for finding in payload["findings"]},
        )

    def test_bizquery_string_connection_stays_blocked(self):
        payload = validator.check_script(
            "return bizQuery('ierp', entity, requires, filters);", "platform"
        )
        self.assertEqual("fail", payload["status"])
        self.assertIn(
            "bizquery-string-connection",
            {finding["code"] for finding in payload["findings"]},
        )

    def test_official_platform_reference_is_complete(self):
        payload = validator.audit_skill()
        self.assertEqual(0, payload["missing_platform_token_count"])

    def test_new_id_manifest_matches_runtime_name(self):
        manifest = json.loads(
            (SKILL_ROOT / "scripts" / "engine_api_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn("NEW_ID", manifest["globals"])
        self.assertNotIn("NewID", manifest["globals"])

    def test_failed_bundle_returns_nonzero(self):
        self.assertEqual(1, validator.result_exit_code({"status": "fail"}, "audit-bundle"))

    def test_passed_bundle_returns_zero(self):
        self.assertEqual(0, validator.result_exit_code({"status": "pass"}, "audit-bundle"))

    def test_metadata_snapshot_is_not_bundled(self):
        self.assertFalse((SKILL_ROOT / "references" / "metas").exists())
        self.assertFalse((SKILL_ROOT / "references" / "all_metadata_basic.json").exists())


if __name__ == "__main__":
    unittest.main()
