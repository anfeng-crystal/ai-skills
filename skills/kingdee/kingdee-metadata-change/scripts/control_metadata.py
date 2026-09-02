#!/usr/bin/env python3
"""Derive observed control contracts for metadata authoring."""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from typing import Any, Iterable
from xml.etree import ElementTree as ET


CATALOG_VERSION = 2
IDENTITY_PROPERTIES = {"Id", "oid", "Key", "ParentId", "PkId"}
BINDING_PROPERTIES = {
    "EntityId",
    "FieldId",
    "FieldKey",
    "FieldName",
    "ListFieldId",
    "OperationKey",
    "ReferenceId",
}
POSITION_PROPERTIES = {"Index", "Order", "Position", "SeqColumnType"}
STYLE_PROPERTIES = {
    "AlignContent",
    "AlignItems",
    "BackColor",
    "Border",
    "Color",
    "Direction",
    "Display",
    "FlexBasis",
    "Font",
    "Grow",
    "Height",
    "JustifyContent",
    "LayoutStyle",
    "Margin",
    "Padding",
    "Shrink",
    "Visible",
    "Width",
    "Wrap",
}
STATE_PROPERTIES = {"Lock", "LockStyle", "Required", "MustInput", "Enabled", "Readonly"}


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def scalar_properties(element: ET.Element) -> dict[str, str]:
    return {
        local_tag(child.tag): (child.text or "").strip()
        for child in list(element)
        if len(child) == 0
    }


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


def property_category(name: str) -> str:
    if name in IDENTITY_PROPERTIES:
        return "identity"
    if name in BINDING_PROPERTIES or name.endswith("FieldId") or name.endswith("FieldName"):
        return "binding"
    if name in POSITION_PROPERTIES:
        return "position"
    if name in STYLE_PROPERTIES or any(token in name.lower() for token in ("color", "style", "height", "width", "margin", "padding")):
        return "style"
    if name in STATE_PROPERTIES or name in {"Visible", "Lock"}:
        return "state"
    if name in {"Name", "Title", "SubTitle", "Placeholder", "Tips", "BusyTip"}:
        return "text"
    return "behavior"


def control_family(control_type: str) -> str:
    if "ListColumn" in control_type or control_type in {"OperationColumnAp", "VoucherNoListColumnAp"}:
        return "list-column"
    if "Filter" in control_type:
        return "filter"
    if control_type in {"ToolbarAp", "MToolbarAp", "AdvConToolbarAp"} or "BarItem" in control_type or control_type in {"ButtonAp", "FloatMenuItemAp"}:
        return "toolbar-action"
    if control_type in {"FieldAp", "EntryFieldAp", "FlatFieldAp", "CardEntryFieldAp", "EntryFieldGroupAp"}:
        return "field"
    if control_type in {"EntryAp", "CardEntryAp", "SubCardEntryAp"}:
        return "entry"
    if control_type.endswith("PanelAp") or control_type in {"FlexPanelAp", "TabAp", "TabPageAp", "SplitContainerAp", "LayoutFlexAp", "GridContainerAp"}:
        return "container"
    if "FormAp" in control_type or control_type in {"BillListAp", "ReportListAp", "ListFormAp"}:
        return "page-root"
    if control_type.startswith(("M", "Mob", "Mobile")):
        return "mobile"
    if control_type.endswith("ViewAp") or control_type in {"TreeViewAp", "QingViewAp", "QingAnalysisAp"}:
        return "view"
    if control_type in {"LabelAp", "ImageAp", "VectorAp", "HtmlAp", "MarkdownAp", "RichTextEditorAp", "QRCodeAp", "ProgressBarAp"}:
        return "display"
    if control_type in {"CustomControlAp", "SpreadAp", "CodeEditAp"}:
        return "custom"
    return "other"


def attribute_value(element: ET.Element, name: str) -> str:
    for key, value in element.attrib.items():
        if local_tag(key) == name:
            return str(value)
    return ""


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _profile_key(host_model_type: str, page_model_type: str, parent_type: str) -> tuple[str, str, str]:
    return host_model_type, page_model_type, parent_type


def build_control_catalog(form_records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build an observed control/type/property matrix from standard form templates."""
    types: dict[str, dict[str, Any]] = {}
    templates = 0
    pages = 0
    controls = 0

    for record in form_records:
        if record.get("scope") != "template":
            continue
        templates += 1
        raw = str(record.get("fdata") or "")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            continue
        template_number = str(record.get("fnumber") or "")
        template_hash = str((record.get("fdata_summary") or {}).get("sha256") or hashlib.sha256(raw.encode("utf-8")).hexdigest())
        host_model_type = str(record.get("fmodeltype") or "")

        for page_ordinal, page in enumerate(element for element in root.iter() if local_tag(element.tag) == "FormMetadata"):
            page_props = scalar_properties(page)
            page_model_type = page_props.get("ModelType") or host_model_type
            page_key = page_props.get("Key", "")
            page_id = page_props.get("Id", "")
            items = next((child for child in list(page) if local_tag(child.tag) == "Items"), None)
            if items is None:
                continue
            pages += 1
            id_types = {page_id: "FormMetadata"} if page_id else {}
            item_props = []
            for item in list(items):
                props = scalar_properties(item)
                item_props.append((item, props))
                if props.get("Id"):
                    id_types[props["Id"]] = local_tag(item.tag)

            for item_index, (item, props) in enumerate(item_props):
                controls += 1
                control_type = local_tag(item.tag)
                action = attribute_value(item, "action")
                parent_id = props.get("ParentId", "")
                parent_type = "none" if not parent_id else id_types.get(parent_id, "FormMetadata" if parent_id == page_id else "unresolved")
                full_definition = bool(props.get("Id") and props.get("Key") and action not in {"edit", "delete"})
                info = types.setdefault(
                    control_type,
                    {
                        "family": control_family(control_type),
                        "occurrences": 0,
                        "full_definition_nodes": 0,
                        "override_or_partial_nodes": 0,
                        "host_model_types": Counter(),
                        "page_model_types": Counter(),
                        "parent_types": Counter(),
                        "actions": Counter(),
                        "properties": defaultdict(
                            lambda: {
                                "present": 0,
                                "nonempty": 0,
                                "category": "",
                                "value_shapes": Counter(),
                                "examples": [],
                            }
                        ),
                        "nested_sections": Counter(),
                        "profiles": defaultdict(
                            lambda: {
                                "occurrences": 0,
                                "full_definition_nodes": 0,
                                "property_counts": Counter(),
                                "property_shapes": defaultdict(Counter),
                                "nested_sections": Counter(),
                                "child_orders": Counter(),
                                "examples": [],
                            }
                        ),
                    },
                )
                info["occurrences"] += 1
                info["full_definition_nodes" if full_definition else "override_or_partial_nodes"] += 1
                info["host_model_types"][host_model_type] += 1
                info["page_model_types"][page_model_type] += 1
                info["parent_types"][parent_type] += 1
                info["actions"][action or "full"] += 1
                for name, value in props.items():
                    stat = info["properties"][name]
                    stat["present"] += 1
                    stat["nonempty"] += bool(value)
                    stat["category"] = property_category(name)
                    stat["value_shapes"][value_shape(value)] += 1
                    if value not in stat["examples"] and len(stat["examples"]) < 5:
                        stat["examples"].append(value[:120])
                nested = [local_tag(child.tag) for child in list(item) if len(child) > 0]
                child_order = tuple(local_tag(child.tag) for child in list(item))
                info["nested_sections"].update(nested)

                profile = info["profiles"][_profile_key(host_model_type, page_model_type, parent_type)]
                profile["occurrences"] += 1
                profile["full_definition_nodes"] += int(full_definition)
                if full_definition:
                    profile["property_counts"].update(props.keys())
                    for name, value in props.items():
                        profile["property_shapes"][name][value_shape(value)] += 1
                    profile["child_orders"][child_order] += 1
                profile["nested_sections"].update(nested)
                if full_definition and len(profile["examples"]) < 3:
                    profile["examples"].append(
                        {
                            "template_number": template_number,
                            "template_fdata_sha256": template_hash,
                            "page_key": page_key,
                            "page_ordinal": page_ordinal,
                            "item_index": item_index,
                            "control_key": props.get("Key", ""),
                            "control_name": props.get("Name", ""),
                        }
                    )

    normalized_types: dict[str, Any] = {}
    families: dict[str, list[str]] = defaultdict(list)
    for control_type in sorted(types):
        info = types[control_type]
        profiles = []
        for (host_model_type, page_model_type, parent_type), profile in sorted(info["profiles"].items()):
            full_count = profile["full_definition_nodes"]
            common = sorted(name for name, count in profile["property_counts"].items() if full_count and count == full_count)
            child_order = list(profile["child_orders"].most_common(1)[0][0]) if profile["child_orders"] else []
            profiles.append(
                {
                    "host_model_type": host_model_type,
                    "page_model_type": page_model_type,
                    "parent_type": parent_type,
                    "occurrences": profile["occurrences"],
                    "full_definition_nodes": full_count,
                    "observed_properties": sorted(profile["property_counts"]),
                    "observed_common_properties": common,
                    "observed_property_shapes": {
                        name: _counter_dict(shapes)
                        for name, shapes in sorted(profile["property_shapes"].items())
                    },
                    "observed_child_order": child_order,
                    "nested_sections": _counter_dict(profile["nested_sections"]),
                    "examples": profile["examples"],
                }
            )
        family = info["family"]
        families[family].append(control_type)
        normalized_types[control_type] = {
            "family": family,
            "occurrences": info["occurrences"],
            "full_definition_nodes": info["full_definition_nodes"],
            "override_or_partial_nodes": info["override_or_partial_nodes"],
            "host_model_types": _counter_dict(info["host_model_types"]),
            "page_model_types": _counter_dict(info["page_model_types"]),
            "parent_types": _counter_dict(info["parent_types"]),
            "actions": _counter_dict(info["actions"]),
            "properties": {
                name: {
                    "present": info["properties"][name]["present"],
                    "nonempty": info["properties"][name]["nonempty"],
                    "category": info["properties"][name]["category"],
                    "value_shapes": _counter_dict(info["properties"][name]["value_shapes"]),
                    "examples": info["properties"][name]["examples"],
                }
                for name in sorted(info["properties"])
            },
            "nested_sections": _counter_dict(info["nested_sections"]),
            "binding_properties": sorted(name for name in info["properties"] if property_category(name) == "binding"),
            "profiles": profiles,
        }

    return {
        "catalog_version": CATALOG_VERSION,
        "source": {
            "table": "t_meta_formdesign",
            "scope": "fistemplate='1'",
            "evidence": "observed-not-universal-schema",
        },
        "summary": {
            "templates": templates,
            "form_pages": pages,
            "control_nodes": controls,
            "control_types": len(normalized_types),
        },
        "families": {family: sorted(names) for family, names in sorted(families.items())},
        "control_types": normalized_types,
    }


def validate_control_catalog(catalog: dict[str, Any]) -> list[str]:
    errors = []
    control_types = catalog.get("control_types") or {}
    summary = catalog.get("summary") or {}
    if catalog.get("catalog_version") != CATALOG_VERSION:
        errors.append("控件目录版本不支持")
    if summary.get("control_types") != len(control_types):
        errors.append("控件类型计数不一致")
    occurrence_total = sum(int(item.get("occurrences", 0)) for item in control_types.values())
    if summary.get("control_nodes") != occurrence_total:
        errors.append("控件节点计数不一致")
    for control_type, info in control_types.items():
        if not info.get("profiles"):
            errors.append(f"{control_type} 缺少模型/父容器证据")
        if int(info.get("full_definition_nodes", 0)) + int(info.get("override_or_partial_nodes", 0)) != int(info.get("occurrences", 0)):
            errors.append(f"{control_type} 定义与覆盖节点计数不一致")
    return errors


def control_catalog_markdown(catalog: dict[str, Any]) -> str:
    summary = catalog.get("summary", {})
    lines = [
        "# 苍穹标准模板控件目录",
        "",
        "> 本文件由目标环境元数据库快照自动生成；类型和兼容性是当前环境观测事实，不是可复制的控件身份。",
        "",
        f"- 标准表单模板：{summary.get('templates', 0)}",
        f"- FormMetadata 页面：{summary.get('form_pages', 0)}",
        f"- 控件节点：{summary.get('control_nodes', 0)}",
        f"- 控件类型：{summary.get('control_types', 0)}",
        "",
        "| 控件类型 | 功能族 | 节点数 | 完整定义 | 宿主 ModelType（出现次数） |",
        "|---|---:|---:|---:|---|",
    ]
    for control_type, info in catalog.get("control_types", {}).items():
        models = "、".join(f"{name}({count})" for name, count in info.get("host_model_types", {}).items())
        lines.append(
            f"| `{control_type}` | {info.get('family', '')} | {info.get('occurrences', 0)} | "
            f"{info.get('full_definition_nodes', 0)} | {models} |"
        )
    host_types: dict[str, list[str]] = defaultdict(list)
    for control_type, info in catalog.get("control_types", {}).items():
        for profile in info.get("profiles", []):
            if profile.get("full_definition_nodes", 0) > 0:
                host_types[profile.get("host_model_type", "")].append(control_type)
    lines.extend(["", "## 宿主 ModelType 的实际可新增类型", ""])
    for model_type in sorted(host_types):
        names = sorted(set(host_types[model_type]))
        lines.extend([f"### `{model_type}`（{len(names)}种）", "", "、".join(f"`{name}`" for name in names), ""])
    lines.extend(
        [
            "",
            "精确新增兼容性必须继续按宿主 ModelType、嵌套页面 ModelType 和父容器查询 `control-catalog.json`；本表不能单独授权新增。",
            "",
        ]
    )
    return "\n".join(lines)


def filter_control_profiles(
    info: dict[str, Any],
    host_model_type: str | None = None,
    page_model_type: str | None = None,
    parent_type: str | None = None,
) -> list[dict[str, Any]]:
    return [
        profile
        for profile in info.get("profiles", [])
        if (not host_model_type or profile.get("host_model_type") == host_model_type)
        and (not page_model_type or profile.get("page_model_type") == page_model_type)
        and (not parent_type or profile.get("parent_type") == parent_type)
    ]
