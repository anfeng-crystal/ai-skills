import io
import contextlib
import json
import sys
import tempfile
import unittest
from unittest import mock
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

    def test_add_requires_exact_control_profile_but_not_platform_generated_identity(self):
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
            self.assertFalse(any("身份合同" in issue for issue in resolved[0]["issues"]))
            contract["changes"][0]["target"]["semantic_parent_type"] = "ToolbarAp"
            resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
            self.assertEqual("candidate-required", resolved[0]["status"])
            self.assertEqual([], resolved[0]["issues"])
            self.assertEqual("unverified", resolved[0]["identity_generation"]["status"])
            with self.assertRaisesRegex(author.ContractError, "verify-candidate"):
                author.apply_resolved(baseline, resolved)

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

            # A locally authored node must take the same structural checks without
            # claiming that its identifiers were first allocated by a designer.
            contract["candidate_provenance"] = {
                "classification": "local-authored",
                "evidence": "unittest same-model template with new local identities",
            }
            resolved, issues = author.verify_candidate(self.knowledge, baseline, candidate, contract)
            self.assertEqual([], issues)
            with self.assertRaises(author.ContractError):
                author.verify_platform_candidate(self.knowledge, baseline, candidate, contract)

            for name in ("Id",):
                with self.subTest(collision=name):
                    changed = ET.fromstring(candidate_xml)
                    node = next(n for n in changed.iter() if author.direct_properties(n).get("Key") == "platform_new_button")
                    node.find(name).text = existing_props[name]
                    invalid = self.write(tmp_root / "collision.xml", ET.tostring(changed))
                    contract["candidate_sha256"] = author.sha256_bytes(invalid.raw)
                    _, issues = author.verify_candidate(self.knowledge, baseline, invalid, contract)
                    self.assertTrue(any(f"{name}=" in issue and "冲突" in issue for issue in issues), issues)

            # Unrelated edits and unresolved operation bindings remain invalid.
            for property_name, value, expected in (("OperationKey", "unknown_operation", "OperationKey"), ("ParentId", "missing_parent", "父容器")):
                with self.subTest(property=property_name):
                    changed = ET.fromstring(candidate_xml)
                    node = next(n for n in changed.iter() if author.direct_properties(n).get("Key") == "platform_new_button")
                    prop = node.find(property_name)
                    if prop is None:
                        prop = ET.SubElement(node, property_name)
                    prop.text = value
                    invalid = self.write(tmp_root / "binding.xml", ET.tostring(changed))
                    contract["candidate_sha256"] = author.sha256_bytes(invalid.raw)
                    _, issues = author.verify_candidate(self.knowledge, baseline, invalid, contract)
                    self.assertTrue(any(expected in issue for issue in issues), issues)

            changed = ET.fromstring(candidate_xml)
            node = next(n for n in changed.iter() if author.direct_properties(n).get("Key") == "bar_print")
            node.find("Name").text = "unauthorized change"
            invalid = self.write(tmp_root / "extra.xml", ET.tostring(changed))
            contract["candidate_sha256"] = author.sha256_bytes(invalid.raw)
            _, issues = author.verify_candidate(self.knowledge, baseline, invalid, contract)
            self.assertTrue(any("其他结构差异" in issue for issue in issues), issues)

            contract["candidate_sha256"] = author.sha256_bytes(candidate.raw)
            contract["baseline_provenance"]["classification"] = "ai-derived"
            with self.assertRaisesRegex(author.ContractError, "基线血缘"):
                author.verify_candidate(self.knowledge, baseline, candidate, contract)

    def test_local_text_field_cli_and_parent_reference_validation(self):
        root = ET.fromstring(self.bill_entity_xml)
        profile = self.knowledge.generic_profile("entity", "TextField", "BillFormModel", "Items")
        required = set(profile["observed_common_properties"])
        properties = self.knowledge.entity_types["node_types"]["TextField"]["properties"]
        values = {"Id": "local-field-id", "Key": "local_added_text"}
        added = ET.Element("TextField")
        for name in required:
            ET.SubElement(added, name).text = values.get(name, (properties[name].get("examples") or [""])[0])
        field = next(n for n in root.iter() if author.local_tag(n.tag) == "BillNoField")
        author.parent_map(root)[id(field)].append(added)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            baseline = self.write(tmp_root / "baseline.xml", self.bill_entity_xml)
            candidate = self.write(tmp_root / "candidate.xml", ET.tostring(root))
            contract = self.contract(baseline, [{
                "action": "add", "target": {"kind": "entity", "node_type": "TextField", "locator": {"key": "local_added_text"}},
            }])
            contract["candidate_sha256"] = author.sha256_bytes(candidate.raw)
            contract["candidate_provenance"] = {"classification": "local-authored", "evidence": "same-model TextField fixture; local identifiers"}
            spec = tmp_root / "contract.json"
            spec.write_text(json.dumps(contract))
            args = author.parser().parse_args(["verify-candidate", str(KNOWLEDGE_DIR), str(baseline.path), str(candidate.path), "--contract", str(spec)])
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(0, args.func(args))
            self.assertEqual("candidate-structurally-ready", json.loads(output.getvalue())["status"])

            added.find("Key").text = "billno"
            collision = self.write(tmp_root / "collision.xml", ET.tostring(root))
            contract["changes"][0]["target"]["locator"] = {"id": values["Id"]}
            contract["candidate_sha256"] = author.sha256_bytes(collision.raw)
            _, issues = author.verify_candidate(self.knowledge, baseline, collision, contract)
            self.assertTrue(any("Key=billno" in issue and "冲突" in issue for issue in issues), issues)
            added.find("Key").text = values["Key"]

            parent = ET.SubElement(added, "ParentId")
            for parent_value in ("nonexistent_parent", values["Id"]):
                with self.subTest(parent=parent_value):
                    parent.text = parent_value
                    invalid = self.write(tmp_root / "invalid.xml", ET.tostring(root))
                    contract["candidate_sha256"] = author.sha256_bytes(invalid.raw)
                    _, issues = author.verify_candidate(self.knowledge, baseline, invalid, contract)
                    self.assertTrue(any("ParentId" in issue for issue in issues), issues)

    def test_common_behavior_properties_are_not_required_for_new_checkbox(self):
        root = ET.fromstring(self.bill_entity_xml)
        items = next(child for child in root if author.local_tag(child.tag) == "Items")
        added = ET.SubElement(items, "CheckBoxField")
        ET.SubElement(added, "Id").text = "local-checkbox-id"
        ET.SubElement(added, "Key").text = "local_checkbox"
        profile = self.knowledge.generic_profile("entity", "CheckBoxField", "BillFormModel", "Items")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            baseline = self.write(tmp_root / "baseline.xml", self.bill_entity_xml)
            candidate = self.write(tmp_root / "candidate.xml", ET.tostring(root))
            contract = self.contract(baseline, [{"action": "add", "target": {
                "kind": "entity", "node_type": "CheckBoxField", "locator": {"key": "local_checkbox"},
            }}])
            contract["candidate_provenance"] = {"classification": "local-authored", "evidence": "test checkbox fixture"}
            contract["candidate_sha256"] = author.sha256_bytes(candidate.raw)
            # Even if every sampled node has these behavior settings, omission
            # must remain valid; a snapshot does not make them required.
            with mock.patch.dict(profile, {"observed_common_properties": ["Id", "Key", "MustInput", "Lock"]}):
                _, issues = author.verify_candidate(self.knowledge, baseline, candidate, contract)
                self.assertEqual([], issues)
                self.assertIsNone(added.find("MustInput"))
                self.assertNotIn(b"<Lock", ET.tostring(added))

                added.remove(added.find("Id"))
                invalid = self.write(tmp_root / "missing-id.xml", ET.tostring(root))
                contract["candidate_sha256"] = author.sha256_bytes(invalid.raw)
                _, issues = author.verify_candidate(self.knowledge, baseline, invalid, contract)
                self.assertTrue(any("身份" in issue for issue in issues), issues)

            ET.SubElement(added, "Id").text = "local-checkbox-id"
            ET.SubElement(added, "Lock").text = "view"
            invalid = self.write(tmp_root / "unsupported-lock.xml", ET.tostring(root))
            contract["candidate_sha256"] = author.sha256_bytes(invalid.raw)
            _, issues = author.verify_candidate(self.knowledge, baseline, invalid, contract)
            self.assertTrue(any("未观察到的属性: Lock" in issue for issue in issues), issues)

    def test_lock_state_list_rejects_boolean_even_when_empty_is_observed(self):
        contract = self.knowledge.property_contract("form", "FieldAp", "Lock")
        for value in (True, False, "true", "false", 1):
            with self.subTest(value=value):
                self.assertIn("状态列表", author.property_shape_issue(contract, "Lock", value))
        self.assertIsNone(author.property_shape_issue(contract, "Lock", ""))
        self.assertIsNone(author.property_shape_issue(contract, "Lock", "new,edit"))
        # Boolean false is still a valid boolean value, not an empty value.
        self.assertIsNone(author.property_shape_issue({"value_shapes": {"boolean": 1}}, "DefValue", False))

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

    def test_restore_requires_supported_delta_and_resolved_ancestor(self):
        standard_root = ET.fromstring(self.bill_xml)
        standard_control = next(
            node for node in standard_root.iter()
            if author.local_tag(node.tag) == "BarItemAp"
            and author.direct_properties(node).get("Key") == "bar_print"
        )
        props = author.direct_properties(standard_control)
        oid = props.get("PkId") or props["Id"]
        cases = [
            ("edit", oid, "ready"),
            ("reset", oid, "ready"),
            ("delete", oid, "ready"),
            ("edit", "missing-ancestor-identity", "invalid"),
            ("edit", "", "invalid"),
            ("add", oid, "invalid"),
            ("", oid, "invalid"),
        ]
        for delta_action, delta_oid, expected_status in cases:
            with self.subTest(action=delta_action, oid=delta_oid), tempfile.TemporaryDirectory() as tmp:
                xml = (
                    '<FormMetadata><Id>test-page</Id><Key>demo_restore</Key>'
                    '<ModelType>BillFormModel</ModelType>'
                    f'<ParentId>{self.bill_fid}</ParentId><InheritPath>{self.bill_fid}</InheritPath>'
                    f'<Items><BarItemAp action="{delta_action}" oid="{delta_oid}">'
                    '<Key>local_key</Key><Visible/></BarItemAp></Items></FormMetadata>'
                ).encode("utf-8")
                baseline = self.write(Path(tmp) / "restore.xml", xml)
                contract = self.contract(baseline, [{
                    "action": "restore",
                    "target": {
                        "kind": "form", "number": "demo_restore", "node_type": "BarItemAp",
                        "locator": {"key": "local_key"},
                    },
                }])
                resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
                self.assertEqual(expected_status, resolved[0]["status"])
                if expected_status == "ready":
                    candidate, _ = author.apply_resolved(baseline, resolved)
                    self.assertNotIn(b"BarItemAp", candidate)
                    self.assertIn(f"<ParentId>{self.bill_fid}</ParentId>".encode(), candidate)
                    self.assertEqual(xml, baseline.raw)
                else:
                    with self.assertRaisesRegex(author.ContractError, "未就绪"):
                        author.apply_resolved(baseline, resolved)

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

    def test_move_parent_is_resolved_only_in_the_selected_design_page(self):
        root = ET.fromstring(self.bill_xml)
        toolbar = next(node for node in root.find("Items") if author.local_tag(node.tag) == "ToolbarAp")
        toolbar_id = author.direct_properties(toolbar)["Id"]
        mobile_page = next(node for node in root.iter("FormMetadata")
                           if author.direct_properties(node).get("ModelType") == "MobileBillFormModel")
        mobile_parent = next(node for node in mobile_page.find("Items")
                             if author.local_tag(node.tag) == "MToolbarAp")
        cases = [(toolbar_id, "ready"), ("_toolbar_", "invalid"),
                 (author.direct_properties(mobile_parent)["Id"], "invalid"),
                 ("missing-parent", "invalid")]
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "bos_billtpl.xml", self.bill_xml)
            for parent_id, status in cases:
                with self.subTest(parent_id=parent_id):
                    contract = self.contract(baseline, [{
                        "action": "move", "target": {"kind": "form", "number": "bos_billtpl",
                        "node_type": "BarItemAp", "locator": {"key": "bar_print"}},
                        "new_parent_id": parent_id,
                    }])
                    resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
                    self.assertEqual(status, resolved[0]["status"])
                    if status == "ready":
                        author.apply_resolved(baseline, resolved)
                    else:
                        self.assertIn("unresolved", resolved[0]["semantic_parent_type"])
                        self.assertTrue(any("当前页面" in issue for issue in resolved[0]["issues"]))
                        with self.assertRaisesRegex(author.ContractError, "未就绪"):
                            author.apply_resolved(baseline, resolved)
            content_panel = next(node for node in root.find("Items")
                                 if author.direct_properties(node).get("Key") == "contentpanelflex")
            new_parent = author.direct_properties(content_panel)["Id"]
            contract = self.contract(baseline, [{
                "action": "move", "target": {"kind": "form", "number": "bos_billtpl",
                "node_type": "ToolbarAp", "locator": {"key": "tbmain"}},
                "new_parent_id": new_parent,
            }])
            resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
            self.assertEqual("ready", resolved[0]["status"])
            candidate, _ = author.apply_resolved(baseline, resolved)
            old_parent = author.direct_properties(toolbar)["ParentId"]
            old_token = f"<ParentId>{old_parent}</ParentId>".encode()
            new_token = f"<ParentId>{new_parent}</ParentId>".encode()
            self.assertNotEqual(baseline.raw, candidate)
            self.assertEqual(baseline.raw.replace(old_token, new_token, 1), candidate)

    def test_nested_page_duplicate_id_does_not_override_local_parent_or_cycle(self):
        xml = b"""<FormMetadata><Id>page</Id><Key>demo</Key><ModelType>BillFormModel</ModelType><Items>
<FlexPanelAp><Id>panel</Id><Key>panel</Key></FlexPanelAp>
<FlexPanelAp><Id>other</Id><Key>other</Key><ParentId>panel</ParentId></FlexPanelAp>
<ToolbarAp><Id>toolbar</Id><Key>toolbar</Key><ParentId>other</ParentId></ToolbarAp>
<BarItemAp><Id>button</Id><Key>button</Key><ParentId>toolbar</ParentId></BarItemAp>
<BillFormAp><Id>form</Id><Key>form</Key><MobMeta><FormMetadata><Id>page</Id>
<Key>mobile</Key><ModelType>MobileBillFormModel</ModelType><Items>
<FieldAp><Id>toolbar</Id><Key>mobile_field</Key><ParentId>button</ParentId></FieldAp>
<FlexPanelAp><Id>other</Id><Key>mobile_other</Key></FlexPanelAp>
</Items></FormMetadata></MobMeta></BillFormAp></Items></FormMetadata>"""
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "demo.xml", xml)
            for key, kind, parent_id, expected in [
                ("button", "BarItemAp", "toolbar", "ready"),
                ("panel", "FlexPanelAp", "other", "invalid"),
            ]:
                with self.subTest(key=key):
                    contract = self.contract(baseline, [{
                        "action": "move", "target": {"kind": "form", "number": "demo",
                        "node_type": kind, "locator": {"key": key}}, "new_parent_id": parent_id,
                    }])
                    resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
                    self.assertEqual(expected, resolved[0]["status"])
                    if expected == "invalid":
                        self.assertTrue(any("循环" in issue for issue in resolved[0]["issues"]))

    def test_move_inherited_parent_keeps_its_page_scope_when_page_ids_repeat(self):
        root = ET.fromstring(self.bill_xml)
        props = author.direct_properties(next(node for node in root.find("Items")
                if author.local_tag(node.tag) == "BarItemAp" and author.direct_properties(node).get("Key") == "bar_print"))
        oid = props.get("PkId") or props["Id"]
        xml = (f'<FormMetadata action="edit" oid="{self.bill_fid}"><Key>demo_bill</Key>'
               f'<ModelType>BillFormModel</ModelType><ParentId>{self.bill_fid}</ParentId>'
               f'<InheritPath>{self.bill_fid}</InheritPath><Items><BarItemAp action="edit" oid="{oid}">'
               '<Visible/></BarItemAp></Items></FormMetadata>').encode()
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "delta.xml", xml)
            for parent_id, expected in [(props["ParentId"], "ready"), ("_toolbar_", "invalid")]:
                with self.subTest(parent_id=parent_id):
                    contract = self.contract(baseline, [{
                        "action": "move", "target": {"kind": "form", "number": "demo_bill",
                        "node_type": "BarItemAp", "locator": {"key": "bar_print"}},
                        "new_parent_id": parent_id,
                    }])
                    resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
                    self.assertEqual(expected, resolved[0]["status"])
                    if expected == "ready":
                        self.assertEqual("BillFormModel", resolved[0]["page_model_type"])
                        candidate, _ = author.apply_resolved(baseline, resolved)
                        self.assertIn(f'<ParentId>{parent_id}</ParentId>'.encode(), candidate)

    def test_move_cycle_uses_current_oid_only_inherited_parent_override(self):
        root = ET.fromstring(self.bill_xml)
        panels = {author.direct_properties(node).get("Key"): author.direct_properties(node)
                  for node in root.find("Items") if author.local_tag(node.tag) == "FlexPanelAp"}
        first, second = panels["titlepanelflex"], panels["contentpanelflex"]
        xml = (f'<FormMetadata action="edit" oid="{self.bill_fid}"><Key>demo_cycle</Key>'
               f'<ModelType>BillFormModel</ModelType><ParentId>{self.bill_fid}</ParentId>'
               f'<InheritPath>{self.bill_fid}</InheritPath><Items>'
               f'<FlexPanelAp action="edit" oid="{first["Id"]}"><Visible/></FlexPanelAp>'
               f'<FlexPanelAp action="edit" oid="{second["Id"]}"><ParentId>{first["Id"]}</ParentId></FlexPanelAp>'
               '</Items></FormMetadata>').encode()
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self.write(Path(tmp) / "delta.xml", xml)
            contract = self.contract(baseline, [{
                "action": "move", "target": {"kind": "form", "number": "demo_cycle",
                "node_type": "FlexPanelAp", "locator": {"key": "titlepanelflex"}},
                "new_parent_id": second["Id"],
            }])
            resolved, _ = author.resolve_contract(self.knowledge, baseline, contract)
            self.assertEqual("invalid", resolved[0]["status"])
            self.assertTrue(any("循环" in issue for issue in resolved[0]["issues"]))
            with self.assertRaisesRegex(author.ContractError, "未就绪"):
                author.apply_resolved(baseline, resolved)

    def test_scalar_insertion_preserves_compact_and_multiline_xml_tokens(self):
        cases = [
            (b'<m:BarItemAp xmlns:m="urn:test"><!--keep--><m:Visible/></m:BarItemAp>',
             b'<m:ParentId>toolbar</m:ParentId>'),
            (b'<m:BarItemAp xmlns:m="urn:test">\r\n  <!--keep-->\r\n  <m:Visible/>\r\n</m:BarItemAp>',
             b'  <m:ParentId>toolbar</m:ParentId>\r\n'),
            (b'<BarItemAp xmlns="urn:test"><!--keep--><Visible/></BarItemAp>',
             b'<ParentId>toolbar</ParentId>'),
        ]
        for raw, inserted in cases:
            with self.subTest(raw=raw):
                node, _ = author.span_tree(raw)
                patch = author.set_scalar_patch(raw, node, "ParentId", "toolbar", ["ParentId", "Visible"])
                candidate = author.apply_patches(raw, [patch])
                self.assertEqual("toolbar", ET.fromstring(candidate).find("{urn:test}ParentId").text)
                self.assertEqual(1, candidate.count(inserted))
                self.assertEqual(raw, candidate.replace(inserted, b"", 1))
        raw = b'<m:BarItemAp xmlns:m="urn:test" action="edit" oid="button"/>'
        node, _ = author.span_tree(raw)
        candidate = author.apply_patches(raw, [author.set_scalar_patch(raw, node, "ParentId", "toolbar", [])])
        self.assertEqual(raw[:-2] + b'><m:ParentId>toolbar</m:ParentId></m:BarItemAp>', candidate)
        self.assertEqual("toolbar", ET.fromstring(candidate).find("{urn:test}ParentId").text)

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
