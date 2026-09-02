import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "metadata_knowledge.py"
SPEC = importlib.util.spec_from_file_location("metadata_knowledge", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MetadataKnowledgeTests(unittest.TestCase):
    @staticmethod
    def form_record(number, model_type, item_xml):
        xml = (
            f"<FormMetadata><Id>page-id</Id><Key>{number}</Key><ModelType>{model_type}</ModelType>"
            f"<Items>{item_xml}</Items></FormMetadata>"
        )
        return {
            "scope": "template",
            "fnumber": number,
            "fmodeltype": model_type,
            "fdata": xml,
            "fdata_summary": {"sha256": MODULE.sha256_bytes(xml.encode("utf-8"))},
        }

    def test_referenced_ids_collects_parent_and_inherit_path(self):
        records = [{"fparentid": "parent", "finheritpath": "root, middle, parent"}]
        self.assertEqual({"root", "middle", "parent"}, MODULE.referenced_ids(records))

    def test_xml_summary_is_deterministic(self):
        summary = MODULE.xml_summary("<FormMetadata><Key>abc</Key></FormMetadata>")
        self.assertEqual("xml", summary["format"])
        self.assertEqual("FormMetadata", summary["root"])
        self.assertEqual(2, summary["nodes"])
        self.assertEqual(64, len(summary["sha256"]))

    def test_xml_summary_marks_invalid_xml(self):
        self.assertEqual("invalid-xml", MODULE.xml_summary("<broken>")["format"])

    def test_normalize_distinguishes_template_and_ancestor(self):
        templates = [{"fid": "t", "fdata": "<EntityMetadata />"}]
        ancestors = [{"fid": "a", "fdata": "<EntityMetadata />"}]
        records = MODULE.normalize_records(templates, ancestors, {}, {})
        self.assertEqual(["template", "ancestor_context"], [record["scope"] for record in records])

    def test_catalog_uses_zh_cn_name_and_hash(self):
        records = MODULE.normalize_records(
            [{"fid": "t", "fnumber": "bos_tpl", "fdata": "<FormMetadata />"}],
            [],
            {"t": [{"flocaleid": "zh_CN", "fname": "模板"}]},
            {},
        )
        item = MODULE.compact_catalog("form", records)[0]
        self.assertEqual("模板", item["fname_zh_CN"])
        self.assertEqual("FormMetadata", item["xml_root"])

    def test_knowledge_bundle_contains_actual_side_table_and_mainentity_contracts(self):
        entity_xml = (
            "<EntityMetadata><Id>entity</Id><Key>bill</Key><ModelType>BillFormModel</ModelType>"
            "<Fields><TextField><Id>field</Id><Key>name</Key><Name>Name</Name></TextField></Fields>"
            "<Operations><Operation><Id>submit-operation</Id><Key>submit</Key><Name>提交</Name></Operation></Operations>"
            "</EntityMetadata>"
        )
        entity = {
            "scope": "template",
            "fid": "entity",
            "fnumber": "bill",
            "fmodeltype": "BillFormModel",
            "fdata": entity_xml,
            "fdata_summary": {"sha256": MODULE.sha256_bytes(entity_xml.encode())},
            "locales": [{"fid": "entity", "flocaleid": "zh_CN", "fname": "单据"}],
            "terms": [{"fid": "entity", "flocaleid": "zh_CN", "fterm": "术语"}],
        }
        form = self.form_record(
            "bill",
            "BillFormModel",
            "<FieldAp><Id>control</Id><Key>name</Key><ParentId>page-id</ParentId><FieldId>name</FieldId></FieldAp>"
            "<BarItemAp><Id>submit-control</Id><Key>submit</Key><ParentId>page-id</ParentId><OperationKey>submit</OperationKey></BarItemAp>"
            "<ButtonAp><Id>close-control</Id><Key>close</Key><ParentId>page-id</ParentId><OperationKey>close</OperationKey></ButtonAp>",
        )
        form.update(
            {
                "fid": "form",
                "locales": [{"fid": "form", "flocaleid": "zh_CN", "fname": "单据"}],
                "terms": [{"fid": "form", "flocaleid": "zh_CN", "fterm": "术语"}],
            }
        )
        control_catalog = MODULE.build_control_catalog([form])
        bundle = MODULE.build_knowledge_bundle(
            [entity],
            [form],
            [{"fid": "main", "fmodeltype": "BillFormModel", "fistemplate": "1"}],
            control_catalog,
            {"environment": "test"},
        )
        payloads = bundle["payloads"]
        self.assertEqual(4, len(payloads["localization-term-contracts.json"]["contracts"]))
        self.assertIn("fmodeltype", payloads["mainentity-contract.json"]["columns"])
        expected_entity_profiles = sum(
            len(info["profiles"])
            for info in payloads["entity-types.json"]["node_types"].values()
        )
        self.assertEqual(
            expected_entity_profiles,
            payloads["model-matrix.json"]["models"]["BillFormModel"]["entity_profiles"],
        )
        binding_matrix = payloads["binding-matrix.json"]
        self.assertEqual(1, binding_matrix["summary"]["operation_binding_combinations"])
        self.assertEqual("Operation", binding_matrix["operation_bindings"][0]["operation_type"])
        self.assertEqual("close", binding_matrix["form_action_bindings"][0]["operation_key"])
        self.assertEqual([], MODULE.validate_knowledge_bundle(bundle["manifest"], payloads))

    def test_resolve_reference_chain_returns_exact_hash(self):
        catalog = [{"kind": "form", "fid": "p", "fnumber": "bos_tpl", "fmodeltype": "BillFormModel", "scope": "template", "fdata_sha256": "abc"}]
        result = MODULE.resolve_reference_chain(catalog, "form", "p", None)
        self.assertEqual("abc", result["matched"][0]["fdata_sha256"])
        self.assertEqual([], result["unmatched"])

    def test_candidate_documents_rejects_zip_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.zip"
            import zipfile
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../bad.dym", "<EntityMetadata />")
            with self.assertRaises(MODULE.ContractError):
                MODULE.candidate_documents(path)

    def test_metadata_units_unwraps_deploy_metadata(self):
        text = """<DeployMetadata><DesignMetas><DesignFormMeta><ModelType>BillFormModel</ModelType><Number>demo</Number><DataXml><FormMetadata><ParentId>p</ParentId></FormMetadata></DataXml></DesignFormMeta></DesignMetas></DeployMetadata>"""
        units = MODULE.metadata_units({"source": "demo.dym", "text": text})
        self.assertEqual("form", units[0]["kind"])
        self.assertEqual("demo", MODULE.metadata_value(units[0]["header"], "Number"))
        self.assertEqual("FormMetadata", MODULE.local_tag(units[0]["xml_root"].tag))

    def test_control_catalog_keeps_model_and_parent_compatibility(self):
        base = self.form_record(
            "base",
            "BaseFormModel",
            "<FlexPanelAp><Id>panel</Id><Key>panel</Key></FlexPanelAp>"
            "<FieldAp><Id>field</Id><Key>name</Key><ParentId>panel</ParentId><FieldId>name-id</FieldId></FieldAp>",
        )
        bill = self.form_record(
            "bill",
            "BillFormModel",
            "<ButtonAp><Id>button</Id><Key>submit</Key><ParentId>page-id</ParentId><Visible>default</Visible></ButtonAp>",
        )
        catalog = MODULE.build_control_catalog([base, bill])
        self.assertEqual(3, catalog["summary"]["control_types"])
        field = catalog["control_types"]["FieldAp"]
        profiles = MODULE.filter_control_profiles(field, "BaseFormModel", "BaseFormModel", "FlexPanelAp")
        self.assertEqual(1, len(profiles))
        self.assertEqual([], MODULE.filter_control_profiles(field, "BillFormModel", None, None))
        self.assertEqual([], MODULE.validate_control_catalog(catalog))

    def test_control_catalog_keeps_value_shapes_and_child_order(self):
        record = self.form_record(
            "bill",
            "BillFormModel",
            "<ButtonAp><Id>button</Id><Key>submit</Key><ParentId>page-id</ParentId>"
            "<Visible>true</Visible><Width>120</Width></ButtonAp>",
        )
        profile = MODULE.build_control_catalog([record])["control_types"]["ButtonAp"]["profiles"][0]
        self.assertEqual({"boolean": 1}, profile["observed_property_shapes"]["Visible"])
        self.assertEqual(["Id", "Key", "ParentId", "Visible", "Width"], profile["observed_child_order"])


if __name__ == "__main__":
    unittest.main()
