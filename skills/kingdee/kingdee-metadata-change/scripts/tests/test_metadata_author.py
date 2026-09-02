import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import metadata_author as author


KNOWLEDGE_DIR = SCRIPT_DIR.parents[0] / "knowledge" / "prod-current"


class MetadataAuthorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.knowledge = author.Knowledge(KNOWLEDGE_DIR)
        record = next(
            row
            for row in cls.knowledge.standard["form"]
            if row.get("scope") == "template" and row.get("fnumber") == "bos_billtpl"
        )
        cls.bill_xml = str(record["fdata"]).encode("utf-8")
        cls.bill_fid = str(record["fid"])
        entity_record = next(
            row
            for row in cls.knowledge.standard["entity"]
            if row.get("scope") == "template" and row.get("fnumber") == "bos_billtpl"
        )
        cls.bill_entity_xml = str(entity_record["fdata"]).encode("utf-8")
        base_record = next(
            row
            for row in cls.knowledge.standard["form"]
            if row.get("scope") == "template" and row.get("fnumber") == "bos_basetpl"
        )
        cls.base_xml = str(base_record["fdata"]).encode("utf-8")

    @staticmethod
    def contract(artifact, changes, classification="repository-canonical"):
        return {
            "contract_version": author.CONTRACT_VERSION,
            "environment": "prod",
            "baseline_sha256": author.sha256_bytes(artifact.raw),
            "baseline_provenance": {
                "classification": classification,
                "evidence": "unittest immutable fixture",
            },
            "changes": changes,
        }

    @staticmethod
    def write(path, data):
        path.write_bytes(data)
        return author.Artifact.load(path)

    def test_modify_is_token_preserving_and_rollback_is_byte_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = self.write(root / "bos_billtpl.xml", self.bill_xml)
            contract = self.contract(
                baseline,
                [
                    {
                        "action": "modify",
                        "target": {
                            "kind": "form",
                            "number": "bos_billtpl",
                            "node_type": "BarItemAp",
                            "locator": {"key": "bar_print"},
                        },
                        "set": {"Visible": "init,edit"},
                    }
                ],
            )
            resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
            candidate, applied = author.apply_resolved(baseline, resolved)
            changed_lines = [
                (before, after)
                for before, after in zip(self.bill_xml.splitlines(), candidate.splitlines())
                if before != after
            ]
            self.assertEqual(
                [(b"      <Visible>init,edit,view,submit,audit</Visible>", b"      <Visible>init,edit</Visible>")],
                changed_lines,
            )
            bundle = author.rollback_bundle(baseline, candidate, contract, applied)
            with zipfile.ZipFile(io.BytesIO(bundle), "r") as archive:
                self.assertEqual(self.bill_xml, archive.read("baseline.bin"))

    def test_ai_derived_baseline_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "bos_billtpl.xml", self.bill_xml)
            contract = self.contract(
                baseline,
                [{"action": "modify", "target": {"kind": "form"}, "set": {"Name": "x"}}],
                classification="ai-derived",
            )
            with self.assertRaisesRegex(author.ContractError, "基线血缘"):
                author.validate_contract(contract, baseline, self.knowledge)

    def test_change_spec_version_is_filled_by_the_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "change.json"
            path.write_text("{}", encoding="utf-8")
            spec = author.read_change_spec(path)
            self.assertEqual(author.CONTRACT_VERSION, spec["contract_version"])

    def test_unknown_property_and_identity_edit_are_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "bos_billtpl.xml", self.bill_xml)
            base_target = {
                "kind": "form",
                "number": "bos_billtpl",
                "node_type": "BarItemAp",
                "locator": {"key": "bar_print"},
            }
            for property_name in ("InventedByAgent", "Key"):
                contract = self.contract(
                    baseline,
                    [{"action": "modify", "target": base_target, "set": {property_name: "bad"}}],
                )
                resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
                self.assertEqual("invalid", resolved[0]["status"])

    def test_observed_boolean_shape_is_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "bos_billtpl.xml", self.bill_xml)
            contract = self.contract(
                baseline,
                [
                    {
                        "action": "modify",
                        "target": {
                            "kind": "form",
                            "number": "bos_billtpl",
                            "node_type": "BillFormAp",
                            "locator": {"key": "bos_billtpl"},
                        },
                        "set": {"Wrap": "not-a-boolean"},
                    }
                ],
            )
            resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
            self.assertEqual("invalid", resolved[0]["status"])
            self.assertTrue(any("值形态" in issue for issue in resolved[0]["issues"]))

    def test_add_requires_exact_control_profile_and_verified_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "bos_billtpl.xml", self.bill_xml)
            contract = self.contract(
                baseline,
                [
                    {
                        "action": "add",
                        "target": {
                            "kind": "form",
                            "number": "bos_billtpl",
                            "node_type": "BarItemAp",
                            "parent_type": "Items",
                            "page_model_type": "BillFormModel",
                            "semantic_parent_type": "FieldAp",
                        },
                    }
                ],
            )
            resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
            self.assertEqual("blocked", resolved[0]["status"])
            self.assertTrue(any("父容器组合" in issue for issue in resolved[0]["issues"]))
            self.assertTrue(any("身份合同" in issue for issue in resolved[0]["issues"]))

    def test_bill_only_root_control_is_not_authorized_for_base_model(self):
        self.assertIsNotNone(
            self.knowledge.control_profile("BillFormAp", "BillFormModel", "BillFormModel", "none")
        )
        self.assertIsNone(
            self.knowledge.control_profile("BillFormAp", "BaseFormModel", "BaseFormModel", "none")
        )
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "bos_basetpl.xml", self.base_xml)
            contract = self.contract(
                baseline,
                [
                    {
                        "action": "add",
                        "target": {
                            "kind": "form",
                            "number": "bos_basetpl",
                            "node_type": "BillFormAp",
                            "parent_type": "Items",
                            "page_model_type": "BaseFormModel",
                            "semantic_parent_type": "none",
                        },
                    }
                ],
            )
            resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
            self.assertEqual("blocked", resolved[0]["status"])
            self.assertTrue(any("父容器组合" in issue for issue in resolved[0]["issues"]))

    def test_control_binding_to_unknown_field_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "bos_billtpl.xml", self.bill_xml)
            contract = self.contract(
                baseline,
                [
                    {
                        "action": "modify",
                        "target": {
                            "kind": "form",
                            "number": "bos_billtpl",
                            "node_type": "ListColumnAp",
                            "locator": {"key": "colbillno"},
                        },
                        "set": {"ListFieldId": "field_that_does_not_exist"},
                    }
                ],
            )
            resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
            self.assertEqual("invalid", resolved[0]["status"])
            self.assertTrue(any("无法解析到同业务对象字段" in issue for issue in resolved[0]["issues"]))

    def test_platform_created_addition_can_be_verified_without_copying_standard_identity(self):
        root = ET.fromstring(self.bill_xml)
        parents = author.parent_map(root)
        existing = next(
            node
            for node in root.iter()
            if author.local_tag(node.tag) == "BarItemAp"
            and author.direct_properties(node).get("Key") == "bar_print"
        )
        items = parents[id(existing)]
        existing_props = author.direct_properties(existing)
        values = {
            "Id": "platform-generated-id",
            "PkId": "platform-generated-pkid",
            "Key": "platform_new_button",
            "ParentId": existing_props["ParentId"],
            "MasterId": "platform-generated-master",
            "OperationKey": "submit",
        }
        generic_profile = self.knowledge.generic_profile(
            "form", "BarItemAp", "BillFormModel", "Items"
        )
        control_profile = self.knowledge.control_profile(
            "BarItemAp", "BillFormModel", "BillFormModel", "ToolbarAp"
        )
        required = set(generic_profile["observed_common_properties"]) | set(
            control_profile["observed_common_properties"]
        )
        property_contracts = self.knowledge.form_types["node_types"]["BarItemAp"]["properties"]
        for name in required:
            if name not in values:
                values[name] = (property_contracts[name].get("examples") or [""])[0]
        added = ET.Element("BarItemAp")
        ordered = [name for name in generic_profile["observed_child_order"] if name in required]
        ordered.extend(sorted(required - set(ordered)))
        for name in ordered:
            child = ET.SubElement(added, name)
            child.text = values[name]
        items.append(added)
        candidate_xml = ET.tostring(root, encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            baseline = self.write(tmp_root / "baseline.xml", self.bill_xml)
            candidate = self.write(tmp_root / "candidate.xml", candidate_xml)
            contract = self.contract(
                baseline,
                [
                    {
                        "action": "add",
                        "target": {
                            "kind": "form",
                            "number": "bos_billtpl",
                            "node_type": "BarItemAp",
                            "locator": {"key": "platform_new_button"},
                        },
                    }
                ],
            )
            contract["candidate_sha256"] = author.sha256_bytes(candidate.raw)
            contract["candidate_provenance"] = {
                "classification": "platform-exported",
                "evidence": "unittest platform-created fixture",
            }
            resolved, issues = author.verify_platform_candidate(
                self.knowledge, baseline, candidate, contract
            )
            self.assertEqual([], issues)
            self.assertEqual("ready", resolved[0]["status"])

    def test_operation_key_must_bind_to_actual_entity_operation_or_standard_form_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "bos_billtpl.xml", self.bill_xml)
            target = {
                "kind": "form",
                "number": "bos_billtpl",
                "node_type": "BarItemAp",
                "locator": {"key": "bar_print"},
            }
            valid = self.contract(
                baseline,
                [{"action": "modify", "target": target, "set": {"OperationKey": "submit"}}],
            )
            resolved, _ = author.resolve_contract(self.knowledge, baseline, valid)
            self.assertEqual("ready", resolved[0]["status"])

            invalid = self.contract(
                baseline,
                [{"action": "modify", "target": target, "set": {"OperationKey": "invented_operation"}}],
            )
            resolved, _ = author.resolve_contract(self.knowledge, baseline, invalid)
            self.assertEqual("invalid", resolved[0]["status"])
            self.assertTrue(any("既不是同业务对象实体操作" in issue for issue in resolved[0]["issues"]))

    def test_dropdown_operation_key_is_checked_as_an_operation_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "bos_billtpl.xml", self.bill_xml)
            contract = self.contract(
                baseline,
                [
                    {
                        "action": "modify",
                        "target": {
                            "kind": "form",
                            "number": "bos_billtpl",
                            "node_type": "DropdownItem",
                            "locator": {"key": "bar_unsubmit"},
                        },
                        "set": {"OperationKey": "invented_dropdown_operation"},
                    }
                ],
            )
            resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
            self.assertEqual("invalid", resolved[0]["status"])
            self.assertTrue(any("OperationKey=" in issue for issue in resolved[0]["issues"]))

    def test_platform_created_text_field_addition_uses_actual_entity_contract(self):
        root = ET.fromstring(self.bill_entity_xml)
        items = next(child for child in list(root) if author.local_tag(child.tag) == "Items")
        profile = self.knowledge.generic_profile(
            "entity", "TextField", "BillFormModel", "Items"
        )
        self.assertIsNotNone(profile)
        required = set(profile["observed_common_properties"])
        property_contracts = self.knowledge.entity_types["node_types"]["TextField"]["properties"]
        values = {
            "Id": "platform-generated-field-id",
            "PkId": "platform-generated-field-pkid",
            "Key": "platform_new_text",
            "ParentId": author.direct_properties(root).get("Id", ""),
            "MasterId": "platform-generated-field-master",
            "FieldName": "fplatformnewtext",
            "Name": "平台新文本字段",
        }
        for name in required:
            if name not in values:
                values[name] = (property_contracts[name].get("examples") or [""])[0]
        added = ET.Element("TextField")
        ordered = [name for name in profile["observed_child_order"] if name in required]
        ordered.extend(sorted(required - set(ordered)))
        for name in ordered:
            child = ET.SubElement(added, name)
            child.text = values[name]
        items.append(added)
        candidate_xml = ET.tostring(root, encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            baseline = self.write(tmp_root / "entity-baseline.xml", self.bill_entity_xml)
            candidate = self.write(tmp_root / "entity-candidate.xml", candidate_xml)
            contract = self.contract(
                baseline,
                [
                    {
                        "action": "add",
                        "target": {
                            "kind": "entity",
                            "node_type": "TextField",
                            "locator": {"key": "platform_new_text"},
                        },
                    }
                ],
            )
            contract["candidate_sha256"] = author.sha256_bytes(candidate.raw)
            contract["candidate_provenance"] = {
                "classification": "platform-exported",
                "evidence": "unittest platform-created field fixture",
            }
            resolved, issues = author.verify_platform_candidate(
                self.knowledge, baseline, candidate, contract
            )
            self.assertEqual([], issues)
            self.assertEqual("TextField", author.local_tag(resolved[0]["node"].tag))

    def test_inherited_delta_resolves_control_key_and_parent_from_standard(self):
        standard_root = ET.fromstring(self.bill_xml)
        standard_control = next(
            node
            for node in standard_root.iter()
            if author.local_tag(node.tag) == "BarItemAp"
            and author.direct_properties(node).get("Key") == "bar_print"
        )
        control_props = author.direct_properties(standard_control)
        control_oid = control_props.get("PkId") or control_props["Id"]
        page_oid = author.direct_properties(standard_root).get("PkId") or author.direct_properties(standard_root)["Id"]
        delta = (
            f'<FormMetadata action="edit" oid="{page_oid}">'
            "<Key>demo_bill</Key><ModelType>BillFormModel</ModelType>"
            f"<ParentId>{self.bill_fid}</ParentId><InheritPath>{self.bill_fid}</InheritPath>"
            f'<Items><BarItemAp action="edit" oid="{control_oid}"><Visible/></BarItemAp></Items>'
            "</FormMetadata>"
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "delta.xml", delta)
            contract = self.contract(
                baseline,
                [
                    {
                        "action": "modify",
                        "target": {
                            "kind": "form",
                            "number": "demo_bill",
                            "node_type": "BarItemAp",
                            "locator": {"key": "bar_print"},
                        },
                        "set": {"Visible": "init"},
                    }
                ],
            )
            resolved, public = author.resolve_contract(self.knowledge, baseline, contract)
            self.assertEqual("ready", resolved[0]["status"])
            self.assertEqual("ToolbarAp", resolved[0]["semantic_parent_type"])
            self.assertEqual("bos_billtpl", public[0]["standard_template"])

    def test_delete_is_blocked_when_parent_is_still_referenced(self):
        xml = b"""<FormMetadata><Id>page</Id><Key>demo</Key><ModelType>BillFormModel</ModelType><Items>
<FlexPanelAp><Id>panel</Id><Key>panel</Key><ParentId>page</ParentId></FlexPanelAp>
<ButtonAp><Id>child</Id><Key>child</Key><ParentId>panel</ParentId></ButtonAp>
</Items></FormMetadata>"""
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "demo.xml", xml)
            contract = self.contract(
                baseline,
                [
                    {
                        "action": "delete",
                        "target": {
                            "kind": "form",
                            "number": "demo",
                            "node_type": "FlexPanelAp",
                            "locator": {"key": "panel"},
                        },
                    }
                ],
            )
            resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
            self.assertEqual("invalid", resolved[0]["status"])
            self.assertEqual(1, len(resolved[0]["references"]))

    def test_move_to_unobserved_parent_combination_is_blocked(self):
        xml = b"""<FormMetadata><Id>page</Id><Key>demo</Key><ModelType>BillFormModel</ModelType><Items>
<FieldAp><Id>field-parent</Id><Key>field-parent</Key><ParentId>page</ParentId></FieldAp>
<BarItemAp><Id>button</Id><Key>button</Key><ParentId>page</ParentId></BarItemAp>
</Items></FormMetadata>"""
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "demo.xml", xml)
            contract = self.contract(
                baseline,
                [
                    {
                        "action": "move",
                        "target": {
                            "kind": "form",
                            "number": "demo",
                            "node_type": "BarItemAp",
                            "locator": {"key": "button"},
                        },
                        "new_parent_id": "field-parent",
                    }
                ],
            )
            resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
            self.assertEqual("invalid", resolved[0]["status"])
            self.assertTrue(any("移动后的控件" in issue for issue in resolved[0]["issues"]))

    def test_localization_existing_name_can_be_modified_without_inventing_row_identity(self):
        xml = b"""<DeployMetadata><DesignMetas>
<DesignFormMeta><Number>demo</Number><ModelType>BillFormModel</ModelType><DataXml><FormMetadata><Id>page</Id><Key>demo</Key><ModelType>BillFormModel</ModelType></FormMetadata></DataXml></DesignFormMeta>
<DesignFormMetaL><Number>demo</Number><PkId>locale-row</PkId><DataXml><FormMetadata/></DataXml><Name>Old</Name><Id>master</Id><LocaleId>zh_CN</LocaleId></DesignFormMetaL>
</DesignMetas></DeployMetadata>"""
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "demo.dymx", xml)
            contract = self.contract(
                baseline,
                [
                    {
                        "action": "modify",
                        "target": {
                            "kind": "form_l",
                            "number": "demo",
                            "node_type": "DesignFormMetaL",
                            "locator": {"id": "master"},
                        },
                        "set": {"Name": "New"},
                    }
                ],
            )
            resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
            self.assertEqual("ready", resolved[0]["status"])
            candidate, _ = author.apply_resolved(baseline, resolved)
            self.assertIn(b"<Name>New</Name>", candidate)
            self.assertNotIn(b"<Name>Old</Name>", candidate)

    def test_plugin_attachment_requires_analyzer_evidence_and_class_name_locator(self):
        selected = None
        for record in self.knowledge.standard["form"]:
            if record.get("scope") != "template":
                continue
            root = ET.fromstring(str(record["fdata"]))
            if not author.metadata_value(root, "ModelType"):
                continue
            plugins = [
                node
                for node in root.iter()
                if author.local_tag(node.tag) == "Plugin"
                and author.direct_properties(node).get("ClassName")
                and author.direct_properties(node).get("Enabled")
            ]
            for plugin in plugins:
                props = author.direct_properties(plugin)
                if sum(
                    author.direct_properties(item).get("ClassName") == props["ClassName"]
                    for item in plugins
                ) == 1:
                    selected = record, props
                    break
            if selected:
                break
        self.assertIsNotNone(selected, "生产模板知识中应存在可定位插件节点")
        record, props = selected
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "plugin.xml", str(record["fdata"]).encode("utf-8"))
            unit = author.all_document_units(baseline)[0]
            target = {
                "kind": "form",
                "number": author.unit_number(unit),
                "node_type": "Plugin",
                "locator": {"class_name": props["ClassName"]},
            }
            next_enabled = "false" if props["Enabled"].lower() == "true" else "true"
            missing = self.contract(
                baseline,
                [{"action": "modify", "target": target, "set": {"Enabled": next_enabled}}],
            )
            resolved, _ = author.resolve_contract(self.knowledge, baseline, missing)
            self.assertEqual("invalid", resolved[0]["status"])
            self.assertTrue(any("metadata-analyzer" in issue for issue in resolved[0]["issues"]))

            verified = self.contract(
                baseline,
                [
                    {
                        "action": "modify",
                        "target": target,
                        "set": {"Enabled": next_enabled},
                        "plugin_evidence": {
                            "source": "kingdee-metadata-analyzer",
                            "reference": "unittest-plugin-evidence",
                        },
                    }
                ],
            )
            resolved, _ = author.resolve_contract(self.knowledge, baseline, verified)
            self.assertEqual("ready", resolved[0]["status"])

    def test_zip_rebuild_preserves_non_metadata_member_and_metadata_member_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_path = root / "baseline.zip"
            metadata_info = zipfile.ZipInfo("metadata/bos_billtpl.dym", date_time=(2024, 1, 2, 3, 4, 6))
            metadata_info.compress_type = zipfile.ZIP_DEFLATED
            note_info = zipfile.ZipInfo("README.txt", date_time=(2023, 2, 3, 4, 5, 6))
            note_info.compress_type = zipfile.ZIP_STORED
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr(metadata_info, self.bill_xml)
                archive.writestr(note_info, b"keep-me")
            baseline = author.Artifact.load(zip_path)
            contract = self.contract(
                baseline,
                [
                    {
                        "action": "modify",
                        "target": {
                            "kind": "form",
                            "number": "bos_billtpl",
                            "node_type": "BarItemAp",
                            "locator": {"key": "bar_print"},
                        },
                        "set": {"Visible": "init"},
                    }
                ],
            )
            resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
            candidate, _ = author.apply_resolved(baseline, resolved)
            with zipfile.ZipFile(io.BytesIO(candidate), "r") as archive:
                self.assertEqual(b"keep-me", archive.read("README.txt"))
                rebuilt = archive.getinfo("metadata/bos_billtpl.dym")
                self.assertEqual(metadata_info.date_time, rebuilt.date_time)
                self.assertEqual(metadata_info.compress_type, rebuilt.compress_type)


if __name__ == "__main__":
    unittest.main()
