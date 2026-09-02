#!/usr/bin/env python3
"""Build a machine-queryable authoring schema from captured Cosmic metadata."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from typing import Any, Iterable
from xml.etree import ElementTree as ET


SCHEMA_VERSION = 2
IDENTITY_PROPERTIES = {"Id", "PkId", "Key", "ParentId", "MasterId"}
BINDING_PROPERTIES = {
    "FieldId",
    "ListFieldId",
    "FieldName",
    "EntityId",
    "BaseEntityId",
    "OperationKey",
}
SENSITIVE_SAMPLE_PROPERTIES = {
    "Id",
    "PkId",
    "ParentId",
    "MasterId",
    "BizappId",
    "EntityId",
    "BaseEntityId",
    "ItemId",
    "IsvSign",
}


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def direct_scalar_properties(element: ET.Element) -> dict[str, str]:
    return {
        local_tag(child.tag): (child.text or "").strip()
        for child in list(element)
        if len(child) == 0
    }


def element_action(element: ET.Element) -> str:
    for name, value in element.attrib.items():
        if local_tag(name) == "action":
            return str(value)
    return ""


def value_shape(value: str) -> str:
    if value == "":
        return "empty"
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return "boolean"
    if re.fullmatch(r"-?\d+", value):
        return "integer"
    if re.fullmatch(r"-?\d+\.\d+", value):
        return "decimal"
    if re.fullmatch(r"#[0-9A-Fa-f]{3,8}", value):
        return "color"
    if re.fullmatch(r"-?\d+(?:\.\d+)?(?:px|%|em|rem|vh|vw)", value):
        return "dimension"
    if re.fullmatch(r"[0-9a-fA-F]{16,64}", value):
        return "hex-identifier"
    if re.fullmatch(r"[A-Za-z0-9_+/=\-]{8,64}", value):
        return "identifier-like"
    return "text"


def safe_example_properties(properties: dict[str, str]) -> dict[str, str]:
    return {
        name: value
        for name, value in properties.items()
        if name not in SENSITIVE_SAMPLE_PROPERTIES and len(value) <= 120
    }


def _profile_key(model_type: str, parent_type: str) -> tuple[str, str]:
    return model_type or "<unknown>", parent_type or "none"


def _new_profile() -> dict[str, Any]:
    return {
        "occurrences": 0,
        "full_definition_nodes": 0,
        "actions": Counter(),
        "properties": Counter(),
        "full_property_sets": [],
        "nested_sections": Counter(),
        "attributes": Counter(),
        "child_orders": Counter(),
        "examples": [],
    }


def _record_example(
    profile: dict[str, Any],
    record: dict[str, Any],
    path: str,
    properties: dict[str, str],
) -> None:
    if len(profile["examples"]) >= 3:
        return
    summary = record.get("fdata_summary") or {}
    profile["examples"].append(
        {
            "template_number": record.get("fnumber"),
            "template_fdata_sha256": summary.get("sha256"),
            "xml_path": path,
            "key": properties.get("Key", ""),
            "name": properties.get("Name", ""),
            "sample_properties": safe_example_properties(properties),
        }
    )


def build_node_catalog(kind: str, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "occurrences": 0,
            "full_definition_nodes": 0,
            "model_types": Counter(),
            "parent_types": Counter(),
            "actions": Counter(),
            "identity_properties": Counter(),
            "binding_properties": Counter(),
            "properties": defaultdict(lambda: {"occurrences": 0, "value_shapes": Counter(), "examples": []}),
            "profiles": defaultdict(_new_profile),
        }
    )
    templates = 0
    invalid_xml = []

    for record in records:
        if record.get("scope") != "template":
            continue
        templates += 1
        raw = str(record.get("fdata") or "")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            invalid_xml.append(record.get("fnumber"))
            continue
        model_type = str(record.get("fmodeltype") or direct_scalar_properties(root).get("ModelType") or "")

        def visit(element: ET.Element, parent_type: str, path: str) -> None:
            if len(element) == 0:
                return
            node_type = local_tag(element.tag)
            properties = direct_scalar_properties(element)
            action = element_action(element) or "full"
            attributes = [local_tag(name) for name in element.attrib]
            nested = [local_tag(child.tag) for child in list(element) if len(child) > 0]
            child_order = tuple(local_tag(child.tag) for child in list(element))
            info = nodes[node_type]
            info["occurrences"] += 1
            info["model_types"][model_type or "<unknown>"] += 1
            info["parent_types"][parent_type or "none"] += 1
            info["actions"][action] += 1
            if action == "full":
                info["full_definition_nodes"] += 1
            for name in IDENTITY_PROPERTIES:
                if name in properties:
                    info["identity_properties"][name] += 1
            for name in BINDING_PROPERTIES:
                if name in properties:
                    info["binding_properties"][name] += 1
            for name, value in properties.items():
                prop = info["properties"][name]
                prop["occurrences"] += 1
                prop["value_shapes"][value_shape(value)] += 1
                if name not in SENSITIVE_SAMPLE_PROPERTIES and value not in prop["examples"] and len(prop["examples"]) < 5:
                    prop["examples"].append(value[:120])

            profile = info["profiles"][_profile_key(model_type, parent_type)]
            profile["occurrences"] += 1
            profile["actions"][action] += 1
            profile["properties"].update(properties.keys())
            profile["nested_sections"].update(nested)
            profile["attributes"].update(attributes)
            profile["child_orders"][child_order] += 1
            if action == "full":
                profile["full_definition_nodes"] += 1
                profile["full_property_sets"].append(set(properties))
                _record_example(profile, record, path, properties)

            tag_counts: Counter[str] = Counter()
            for child in list(element):
                if len(child) == 0:
                    continue
                child_tag = local_tag(child.tag)
                ordinal = tag_counts[child_tag]
                tag_counts[child_tag] += 1
                visit(child, node_type, f"{path}/{child_tag}[{ordinal}]")

        visit(root, "none", f"/{local_tag(root.tag)}[0]")

    finalized = {}
    for node_type, info in sorted(nodes.items()):
        profiles = []
        for (model_type, parent_type), profile in sorted(info["profiles"].items()):
            common = (
                sorted(set.intersection(*profile["full_property_sets"]))
                if profile["full_property_sets"]
                else []
            )
            child_order = []
            if profile["child_orders"]:
                child_order = list(profile["child_orders"].most_common(1)[0][0])
            profiles.append(
                {
                    "model_type": model_type,
                    "parent_type": parent_type,
                    "occurrences": profile["occurrences"],
                    "full_definition_nodes": profile["full_definition_nodes"],
                    "actions": dict(sorted(profile["actions"].items())),
                    "observed_properties": sorted(profile["properties"]),
                    "observed_common_properties": common,
                    "observed_nested_sections": dict(sorted(profile["nested_sections"].items())),
                    "observed_attributes": sorted(profile["attributes"]),
                    "observed_child_order": child_order,
                    "authoring": {
                        "modify": "observed" if profile["occurrences"] else "unsupported",
                        "add": "observed-not-roundtrip-verified" if profile["full_definition_nodes"] else "unsupported",
                        "delete": "observed-not-roundtrip-verified" if profile["actions"].get("delete") else "unsupported",
                        "reset": "observed-not-roundtrip-verified" if profile["actions"].get("reset") else "unsupported",
                    },
                    "examples": profile["examples"],
                }
            )
        finalized[node_type] = {
            "occurrences": info["occurrences"],
            "full_definition_nodes": info["full_definition_nodes"],
            "model_types": dict(sorted(info["model_types"].items())),
            "parent_types": dict(sorted(info["parent_types"].items())),
            "actions": dict(sorted(info["actions"].items())),
            "identity_properties": dict(sorted(info["identity_properties"].items())),
            "binding_properties": dict(sorted(info["binding_properties"].items())),
            "properties": {
                name: {
                    "occurrences": value["occurrences"],
                    "value_shapes": dict(sorted(value["value_shapes"].items())),
                    "examples": value["examples"],
                }
                for name, value in sorted(info["properties"].items())
            },
            "profiles": profiles,
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "source": {"scope": "standard-template-database", "evidence": "observed-not-roundtrip-verified"},
        "summary": {"templates": templates, "node_types": len(finalized), "invalid_xml": len(invalid_xml)},
        "invalid_xml_templates": invalid_xml,
        "node_types": finalized,
    }


def build_model_matrix(entity_catalog: dict[str, Any], form_catalog: dict[str, Any]) -> dict[str, Any]:
    matrix: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"entity_node_types": set(), "form_node_types": set(), "entity_profiles": 0, "form_profiles": 0}
    )
    for kind, catalog, key in (
        ("entity", entity_catalog, "entity_node_types"),
        ("form", form_catalog, "form_node_types"),
    ):
        profile_key = f"{kind}_profiles"
        for node_type, info in catalog["node_types"].items():
            for profile in info["profiles"]:
                model_type = profile["model_type"]
                if profile["full_definition_nodes"]:
                    matrix[model_type][key].add(node_type)
                matrix[model_type][profile_key] += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "models": {
            model: {
                "entity_node_types": sorted(value["entity_node_types"]),
                "form_node_types": sorted(value["form_node_types"]),
                "entity_profiles": value["entity_profiles"],
                "form_profiles": value["form_profiles"],
            }
            for model, value in sorted(matrix.items())
        },
    }


def structured_nodes(root: ET.Element) -> list[ET.Element]:
    return [element for element in root.iter() if len(element) > 0]


def _record_reference_ids(record: dict[str, Any]) -> list[str]:
    result: list[str] = []
    raw_values = [record.get("finheritpath"), record.get("fparentid")]
    try:
        root = ET.fromstring(str(record.get("fdata") or ""))
    except ET.ParseError:
        root = None
    if root is not None:
        properties = direct_scalar_properties(root)
        raw_values.extend((properties.get("InheritPath"), properties.get("ParentId")))
    for raw in raw_values:
        for identity in str(raw or "").split(","):
            identity = identity.strip()
            if identity and identity not in result:
                result.append(identity)
    return result


def _lineage_roots(
    record: dict[str, Any],
    records_by_id: dict[str, dict[str, Any]],
    root_cache: dict[str, ET.Element | None],
) -> list[ET.Element]:
    ordered: list[dict[str, Any]] = []
    visited: set[str] = set()

    def visit(item: dict[str, Any]) -> None:
        identity = str(item.get("fid") or "")
        token = identity or f"anonymous:{id(item)}"
        if token in visited:
            return
        visited.add(token)
        for parent_id in _record_reference_ids(item):
            parent = records_by_id.get(parent_id)
            if parent is not None:
                visit(parent)
        ordered.append(item)

    visit(record)
    roots: list[ET.Element] = []
    for item in ordered:
        identity = str(item.get("fid") or f"anonymous:{id(item)}")
        if identity not in root_cache:
            try:
                root_cache[identity] = ET.fromstring(str(item.get("fdata") or ""))
            except ET.ParseError:
                root_cache[identity] = None
        root = root_cache[identity]
        if root is not None:
            roots.append(root)
    return roots


def _entity_fields(roots: Iterable[ET.Element]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for root in roots:
        for node in structured_nodes(root):
            node_type = local_tag(node.tag)
            properties = direct_scalar_properties(node)
            if not node_type.endswith("Field") or not properties.get("Key"):
                continue
            for identity in (
                properties.get("Key"),
                properties.get("Id"),
                properties.get("FieldName"),
            ):
                if identity:
                    fields[identity] = node_type
    return fields


def _entity_operations(roots: Iterable[ET.Element]) -> dict[str, str]:
    """Return actual operation definitions stored below the entity Operations node."""
    operations: dict[str, str] = {}
    for root in roots:
        parents = {id(child): parent for parent in root.iter() for child in list(parent)}
        for node in structured_nodes(root):
            parent = parents.get(id(node))
            properties = direct_scalar_properties(node)
            if (
                parent is not None
                and local_tag(parent.tag) == "Operations"
                and properties.get("Key")
            ):
                operations[properties["Key"]] = local_tag(node.tag)
    return operations


def build_binding_matrix(
    entity_records: Iterable[dict[str, Any]],
    form_records: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    entity_records = list(entity_records)
    form_records = list(form_records)
    entity_by_id = {str(record.get("fid")): record for record in entity_records if record.get("fid")}
    form_by_id = {str(record.get("fid")): record for record in form_records if record.get("fid")}
    entity_by_number = {
        str(record.get("fnumber")): record
        for record in entity_records
        if record.get("scope") == "template"
    }
    field_combinations: Counter[tuple[str, str, str, str]] = Counter()
    field_examples: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    operation_combinations: Counter[tuple[str, str, str, str]] = Counter()
    operation_examples: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    form_action_combinations: Counter[tuple[str, str, str, str]] = Counter()
    form_action_examples: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    entity_root_cache: dict[str, ET.Element | None] = {}
    form_root_cache: dict[str, ET.Element | None] = {}
    paired_templates = 0
    resolved_bindings = 0
    unresolved_bindings = 0
    resolved_operation_bindings = 0
    observed_form_actions = 0
    for form_record in form_records:
        if form_record.get("scope") != "template":
            continue
        number = str(form_record.get("fnumber"))
        entity_id = str(form_record.get("fentityid") or "").strip()
        entity_record = entity_by_id.get(entity_id) or entity_by_number.get(number)
        if not entity_record:
            continue
        entity_roots = _lineage_roots(entity_record, entity_by_id, entity_root_cache)
        form_roots = _lineage_roots(form_record, form_by_id, form_root_cache)
        if not entity_roots or not form_roots:
            continue
        paired_templates += 1
        fields = _entity_fields(entity_roots)
        operations = _entity_operations(entity_roots)
        model_type = str(form_record.get("fmodeltype") or "")
        if not model_type:
            model_type = direct_scalar_properties(form_roots[-1]).get("ModelType", "")
        for form_root in form_roots:
            for node in structured_nodes(form_root):
                control_type = local_tag(node.tag)
                props = direct_scalar_properties(node)
                for binding_property in ("FieldId", "ListFieldId", "FieldName"):
                    value = props.get(binding_property)
                    if not value:
                        continue
                    field_type = fields.get(value)
                    if not field_type:
                        unresolved_bindings += 1
                        continue
                    resolved_bindings += 1
                    key = (model_type, field_type, control_type, binding_property)
                    field_combinations[key] += 1
                    if len(field_examples[key]) < 3:
                        field_examples[key].append(
                            {
                                "template_number": number,
                                "entity_fdata_sha256": (entity_record.get("fdata_summary") or {}).get("sha256"),
                                "form_fdata_sha256": (form_record.get("fdata_summary") or {}).get("sha256"),
                                "field_key": value,
                                "control_key": props.get("Key", ""),
                            }
                        )
                operation_key = props.get("OperationKey")
                if not operation_key:
                    continue
                operation_type = operations.get(operation_key)
                if operation_type:
                    resolved_operation_bindings += 1
                    key = (model_type, operation_type, control_type, "OperationKey")
                    operation_combinations[key] += 1
                    if len(operation_examples[key]) < 3:
                        operation_examples[key].append(
                            {
                                "template_number": number,
                                "entity_fdata_sha256": (entity_record.get("fdata_summary") or {}).get("sha256"),
                                "form_fdata_sha256": (form_record.get("fdata_summary") or {}).get("sha256"),
                                "operation_key": operation_key,
                                "control_key": props.get("Key", ""),
                            }
                        )
                else:
                    observed_form_actions += 1
                    key = (model_type, control_type, "OperationKey", operation_key)
                    form_action_combinations[key] += 1
                    if len(form_action_examples[key]) < 3:
                        form_action_examples[key].append(
                            {
                                "template_number": number,
                                "form_fdata_sha256": (form_record.get("fdata_summary") or {}).get("sha256"),
                                "operation_key": operation_key,
                                "control_key": props.get("Key", ""),
                            }
                        )
    field_rows = [
        {
            "model_type": key[0],
            "field_type": key[1],
            "control_type": key[2],
            "binding_property": key[3],
            "occurrences": count,
            "examples": field_examples[key],
        }
        for key, count in sorted(field_combinations.items())
    ]
    operation_rows = [
        {
            "model_type": key[0],
            "operation_type": key[1],
            "control_type": key[2],
            "binding_property": key[3],
            "occurrences": count,
            "examples": operation_examples[key],
        }
        for key, count in sorted(operation_combinations.items())
    ]
    form_action_rows = [
        {
            "model_type": key[0],
            "control_type": key[1],
            "binding_property": key[2],
            "operation_key": key[3],
            "occurrences": count,
            "examples": form_action_examples[key],
        }
        for key, count in sorted(form_action_combinations.items())
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "join": "form fentityid -> entity fid with exact inherited standard chains",
            "operation_definition": "entity child below Operations with a direct Key",
            "evidence": "observed-not-roundtrip-verified",
        },
        "summary": {
            "paired_templates": paired_templates,
            "resolved_bindings": resolved_bindings,
            "unresolved_bindings": unresolved_bindings,
            "combinations": len(field_rows),
            "resolved_operation_bindings": resolved_operation_bindings,
            "observed_form_actions": observed_form_actions,
            "operation_binding_combinations": len(operation_rows),
            "form_action_binding_combinations": len(form_action_rows),
        },
        "bindings": field_rows,
        "operation_bindings": operation_rows,
        "form_action_bindings": form_action_rows,
    }


def build_identity_contracts(entity_catalog: dict[str, Any], form_catalog: dict[str, Any]) -> dict[str, Any]:
    contracts = {}
    for kind, catalog in (("entity", entity_catalog), ("form", form_catalog)):
        for node_type, info in catalog["node_types"].items():
            if not info["identity_properties"] and not info["actions"]:
                continue
            contracts[f"{kind}:{node_type}"] = {
                "kind": kind,
                "node_type": node_type,
                "observed_identity_properties": info["identity_properties"],
                "observed_actions": info["actions"],
                "profiles": [
                    {
                        "model_type": profile["model_type"],
                        "parent_type": profile["parent_type"],
                        "full_definition_nodes": profile["full_definition_nodes"],
                        "observed_identity_properties": sorted(
                            set(profile["observed_properties"]) & IDENTITY_PROPERTIES
                        ),
                        "observed_common_identity_properties": sorted(
                            set(profile["observed_common_properties"]) & IDENTITY_PROPERTIES
                        ),
                    }
                    for profile in info["profiles"]
                    if profile["full_definition_nodes"]
                ],
                "generation": {
                    "status": "unverified",
                    "mechanism": None,
                    "reason": "数据库终态样本不能单独证明平台身份生成算法；需同版本 DEV 创建并回导验证",
                },
            }
    return {
        "schema_version": SCHEMA_VERSION,
        "contracts": contracts,
    }


def build_related_contracts(
    entity_records: Iterable[dict[str, Any]],
    form_records: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Describe actual locale/term side-table shapes captured with standard templates."""

    contracts: dict[str, Any] = {}
    for kind, records in (("entity", entity_records), ("form", form_records)):
        materialized = list(records)
        for collection, suffix in (("locales", "l"), ("terms", "term")):
            rows = [
                row
                for record in materialized
                if record.get("scope") == "template"
                for row in (record.get(collection) or [])
            ]
            columns: dict[str, dict[str, Any]] = {}
            for name in sorted({str(column) for row in rows for column in row}):
                values = ["" if row.get(name) is None else str(row.get(name)) for row in rows if name in row]
                columns[name] = {
                    "present": len(values),
                    "nonempty": sum(bool(value) for value in values),
                    "value_shapes": dict(sorted(Counter(value_shape(value) for value in values).items())),
                }
            contracts[f"{kind}_{suffix}"] = {
                "kind": kind,
                "collection": collection,
                "table": f"t_meta_{kind}design_{suffix}",
                "rows": len(rows),
                "columns": columns,
                "locale_ids": sorted(
                    {str(row.get("flocaleid")) for row in rows if row.get("flocaleid")}
                ),
                "authoring": {
                    "modify_existing": "observed",
                    "add_or_delete_row": "observed-not-roundtrip-verified",
                    "serialization": "baseline-node-only",
                },
            }
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "tables": [
                "t_meta_entitydesign_l",
                "t_meta_entitydesign_term",
                "t_meta_formdesign_l",
                "t_meta_formdesign_term",
            ],
            "scope": "rows belonging to fistemplate='1' design records",
        },
        "contracts": contracts,
    }


def build_mainentity_contract(main_records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(main_records)
    columns = {}
    for name in sorted({str(column) for row in rows for column in row}):
        values = ["" if row.get(name) is None else str(row.get(name)) for row in rows if name in row]
        columns[name] = {
            "present": len(values),
            "nonempty": sum(bool(value) for value in values),
            "value_shapes": dict(sorted(Counter(value_shape(value) for value in values).items())),
        }
    models: dict[str, dict[str, Any]] = {}
    for model_type in sorted({str(row.get("fmodeltype") or "<unknown>") for row in rows}):
        model_rows = [row for row in rows if str(row.get("fmodeltype") or "<unknown>") == model_type]
        models[model_type] = {
            "rows": len(model_rows),
            "observed_columns": sorted({str(name) for row in model_rows for name in row}),
            "nonempty_columns": sorted(
                {
                    str(name)
                    for row in model_rows
                    for name, value in row.items()
                    if value not in (None, "")
                }
            ),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {"table": "t_meta_mainentityinfo", "scope": "fistemplate='1'"},
        "records": len(rows),
        "columns": columns,
        "models": models,
        "authoring": "observed-not-roundtrip-verified",
    }


def build_knowledge_bundle(
    entity_records: list[dict[str, Any]],
    form_records: list[dict[str, Any]],
    main_records: list[dict[str, Any]],
    control_catalog: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    entity_catalog = build_node_catalog("entity", entity_records)
    form_catalog = build_node_catalog("form", form_records)
    model_matrix = build_model_matrix(entity_catalog, form_catalog)
    binding_matrix = build_binding_matrix(entity_records, form_records)
    identity_contracts = build_identity_contracts(entity_catalog, form_catalog)
    related_contracts = build_related_contracts(entity_records, form_records)
    mainentity_contract = build_mainentity_contract(main_records)
    manifest = {
        "knowledge_version": SCHEMA_VERSION,
        "source": source,
        "status": "observed",
        "authoring_verified_contracts": 0,
        "counts": {
            "entity_node_types": entity_catalog["summary"]["node_types"],
            "form_node_types": form_catalog["summary"]["node_types"],
            "control_types": control_catalog["summary"]["control_types"],
            "models": len(model_matrix["models"]),
            "binding_combinations": binding_matrix["summary"]["combinations"],
            "operation_binding_combinations": binding_matrix["summary"]["operation_binding_combinations"],
            "form_action_binding_combinations": binding_matrix["summary"]["form_action_binding_combinations"],
            "identity_contracts": len(identity_contracts["contracts"]),
            "localization_term_contracts": len(related_contracts["contracts"]),
            "mainentity_columns": len(mainentity_contract["columns"]),
        },
    }
    payloads = {
        "entity-types.json": entity_catalog,
        "form-types.json": form_catalog,
        "control-types.json": control_catalog,
        "model-matrix.json": model_matrix,
        "binding-matrix.json": binding_matrix,
        "identity-contracts.json": identity_contracts,
        "localization-term-contracts.json": related_contracts,
        "mainentity-contract.json": mainentity_contract,
    }
    manifest["payload_sha256"] = {
        name: sha256_text(canonical_json(payload)) for name, payload in payloads.items()
    }
    return {"manifest": manifest, "payloads": payloads}


def validate_knowledge_bundle(
    manifest: dict[str, Any],
    payloads: dict[str, Any],
    required_version: int | None = SCHEMA_VERSION,
) -> list[str]:
    errors = []
    version = manifest.get("knowledge_version")
    if required_version is not None and version != required_version:
        errors.append("knowledge_version 不匹配")
    elif required_version is None and version not in {1, SCHEMA_VERSION}:
        errors.append("knowledge_version 不受支持")
    for name, expected in (manifest.get("payload_sha256") or {}).items():
        payload = payloads.get(name)
        if payload is None:
            errors.append(f"缺少知识库文件: {name}")
            continue
        actual = sha256_text(canonical_json(payload))
        if actual != expected:
            errors.append(f"知识库文件哈希不匹配: {name}")
    return errors
