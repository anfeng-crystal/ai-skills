import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
import metadata_author as author
from metadata_references import external_references


class MetadataReferenceTests(unittest.TestCase):
    def scan(self, xml, target_path):
        root = ET.fromstring(xml)
        return external_references([("demo", "form", root)], root.find(target_path))

    def test_rule_field_id_reference_blocks_deletion(self):
        xml = '''<FormMetadata><Items><FieldAp><Id>field</Id><Key>name</Key></FieldAp></Items>
          <FormRules><FormRule><Actions><HideFieldAction><Fields>
          <FieldId><Id>field</Id></FieldId></Fields></HideFieldAction></Actions>
          </FormRule></FormRules></FormMetadata>'''
        refs = self.scan(xml, "./Items/FieldAp")
        self.assertEqual(["FieldId.Id"], [r["property"] for r in refs])

    def test_descendant_identity_is_checked(self):
        xml = '''<FormMetadata><Items><FlexPanelAp><Id>panel</Id><Items>
          <FieldAp><Id>child</Id></FieldAp></Items></FlexPanelAp></Items>
          <FieldAp><FieldId>child</FieldId></FieldAp></FormMetadata>'''
        self.assertEqual(1, len(self.scan(xml, "./Items/FlexPanelAp")))

    def test_internal_reference_is_removed_with_subtree(self):
        xml = '''<FormMetadata><Items><FlexPanelAp><Id>panel</Id><Items>
          <FieldAp><Id>child</Id><ParentId>panel</ParentId></FieldAp>
          </Items></FlexPanelAp></Items></FormMetadata>'''
        self.assertEqual([], self.scan(xml, "./Items/FlexPanelAp"))

    def test_reference_holder_is_not_a_removed_identity(self):
        xml = '''<FormMetadata><FormRules><FormRule><Id>rule</Id><Actions>
          <HideFieldAction><Fields><FieldId><Id>shared</Id></FieldId></Fields>
          </HideFieldAction></Actions></FormRule></FormRules>
          <FieldAp><FieldId>shared</FieldId></FieldAp></FormMetadata>'''
        self.assertEqual([], self.scan(xml, "./FormRules/FormRule"))

    def test_scalar_reference_and_namespace_are_preserved(self):
        xml = '''<FormMetadata xmlns="urn:test"><Items><FieldAp><Id>field</Id></FieldAp>
          <FieldAp><ListFieldId>field</ListFieldId></FieldAp></Items></FormMetadata>'''
        refs = self.scan(xml, "./{urn:test}Items/{urn:test}FieldAp")
        self.assertEqual(["ListFieldId"], [r["property"] for r in refs])

    def test_unrelated_nested_id_is_not_a_reference(self):
        xml = '''<FormMetadata><Items><FieldAp><Id>field</Id></FieldAp></Items>
          <Other><Id>field</Id></Other></FormMetadata>'''
        self.assertEqual([], self.scan(xml, "./Items/FieldAp"))

    def test_real_standard_rule_reference_and_authoring_gate(self):
        knowledge = author.Knowledge(SCRIPT_DIR.parent / "knowledge" / "prod-current")
        record = next(r for r in knowledge.standard["form"] if r.get("fnumber") == "adm_approve")
        root = ET.fromstring(str(record["fdata"]))
        rule = next(n for n in root.iter() if n.tag == "HideFieldAction")
        identity = rule.find("./Fields/FieldId/Id").text
        # The snapshot stores deployment headers separately from fdata.
        package = ET.Element("DeployMetadata")
        design = ET.SubElement(package, "DesignFormMeta")
        for tag, key in (("Number", "fnumber"), ("ModelType", "fmodeltype"),
                         ("ParentId", "fparentid"), ("InheritPath", "finheritpath")):
            ET.SubElement(design, tag).text = str(record.get(key) or "")
        ET.SubElement(design, "DataXml").append(root)
        xml = ET.tostring(package)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "template.xml"
            path.write_bytes(xml)
            baseline = author.Artifact.load(path)
            resolved = author.resolve_change(knowledge, baseline, author.all_document_units(baseline), {
                "action": "delete", "target": {"kind": "form", "number": "adm_approve",
                "node_type": "FieldAp", "locator": {"id": identity}},
            })
            self.assertEqual("invalid", resolved["status"])
            self.assertTrue(any(r["property"] == "FieldId.Id" for r in resolved["references"]))
            with self.assertRaisesRegex(author.ContractError, "未就绪"):
                author.apply_resolved(baseline, [resolved])


if __name__ == "__main__":
    unittest.main()
