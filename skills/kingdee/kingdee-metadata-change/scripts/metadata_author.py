#!/usr/bin/env python3
"""Plan, apply, validate and roll back evidence-bound Cosmic metadata changes."""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import io
import json
import posixpath
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET
from xml.parsers import expat
from xml.sax.saxutils import escape


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from metadata_knowledge import (  # noqa: E402
    ContractError,
    direct_properties,
    element_action,
    element_oid,
    local_tag,
    metadata_value,
)
from metadata_schema import SCHEMA_VERSION, value_shape  # noqa: E402


CONTRACT_VERSION = 2
TEXT_SUFFIXES = {".dym", ".dymx", ".xml"}
LOCATOR_FIELDS = {
    "key": "Key",
    "id": "Id",
    "oid": "oid",
    "operation_key": "OperationKey",
    "class_name": "ClassName",
}
SUPPORTED_KINDS = {"entity", "form", "entity_l", "form_l", "entity_term", "form_term"}
BASE_KIND = {
    "entity": "entity",
    "form": "form",
    "entity_l": "entity",
    "form_l": "form",
    "entity_term": "entity",
    "form_term": "form",
}
SAFE_BASELINE_CLASSES = {"platform-exported", "user-confirmed-original", "repository-canonical"}
IDENTITY_PROPERTIES = {"Id", "PkId", "Key", "MasterId", "oid"}
BINDING_PROPERTIES = {"FieldId", "ListFieldId", "FieldName"}
REFERENCE_PROPERTIES = {
    "ParentId",
    "FieldId",
    "ListFieldId",
    "FieldName",
    "EntityId",
    "BaseEntityId",
    "MasterId",
    "ReferenceId",
    "ItemId",
    "OperationKey",
}
PLUGIN_NODE_TYPES = {"Plugin", "Plugins", "JsPlugins"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def safe_member(name: str) -> bool:
    normalized = posixpath.normpath(name)
    return not name.startswith("/") and normalized != ".." and not normalized.startswith("../") and "\\" not in name


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"JSON 不可读: {path}: {exc}") from exc


def read_change_spec(path: Path) -> dict[str, Any]:
    spec = read_json(path)
    spec.setdefault("contract_version", CONTRACT_VERSION)
    return spec


def read_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


@dataclass
class Artifact:
    path: Path
    raw: bytes
    is_zip: bool
    documents: dict[str, bytes]
    infos: list[zipfile.ZipInfo] = field(default_factory=list)
    comment: bytes = b""

    @classmethod
    def load(cls, path: Path) -> "Artifact":
        path = path.expanduser().resolve()
        if not path.is_file():
            raise ContractError(f"元数据文件不存在: {path}")
        raw = path.read_bytes()
        if path.suffix.lower() != ".zip":
            if path.suffix.lower() not in TEXT_SUFFIXES:
                raise ContractError("只支持 ZIP、DYM、DYMX 或 XML")
            ET.fromstring(raw)
            return cls(path, raw, False, {path.name: raw})
        try:
            with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
                documents = {}
                infos = archive.infolist()
                for info in infos:
                    if not safe_member(info.filename):
                        raise ContractError(f"ZIP 包含不安全成员: {info.filename}")
                    if info.is_dir() or Path(info.filename).suffix.lower() not in TEXT_SUFFIXES:
                        continue
                    data = archive.read(info)
                    ET.fromstring(data)
                    documents[info.filename] = data
                if not documents:
                    raise ContractError("ZIP 中没有可编辑元数据 XML")
                return cls(path, raw, True, documents, infos, archive.comment)
        except zipfile.BadZipFile as exc:
            raise ContractError("ZIP 无法解析") from exc

    def build(self, changed_documents: dict[str, bytes]) -> bytes:
        if not self.is_zip:
            if len(changed_documents) != 1:
                raise ContractError("单文件候选只能包含一个文档")
            return next(iter(changed_documents.values()))
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.raw), "r") as source, zipfile.ZipFile(output, "w") as target:
            target.comment = self.comment
            for info in self.infos:
                data = changed_documents.get(info.filename)
                if data is None:
                    data = source.read(info) if not info.is_dir() else b""
                target.writestr(copy.copy(info), data)
        return output.getvalue()


def first_descendant(root: ET.Element | None, name: str) -> ET.Element | None:
    if root is None:
        return None
    for element in root.iter():
        if local_tag(element.tag) == name:
            return element
    return None


def expand_units(root: ET.Element, source: str) -> list[dict[str, Any]]:
    root_name = local_tag(root.tag)
    kind = {"EntityMetadata": "entity", "FormMetadata": "form"}.get(root_name)
    if kind:
        return [{"source": source, "kind": kind, "header": root, "xml_root": root}]
    if root_name != "DeployMetadata":
        return []
    tags = {
        "DesignEntityMeta": ("entity", "EntityMetadata"),
        "DesignFormMeta": ("form", "FormMetadata"),
        "DesignEntityMetaL": ("entity_l", "EntityMetadata"),
        "DesignFormMetaL": ("form_l", "FormMetadata"),
        "DesignEntityMetaTerm": ("entity_term", "EntityMetadata"),
        "DesignFormMetaTerm": ("form_term", "FormMetadata"),
    }
    units = []
    for element in root.iter():
        mapping = tags.get(local_tag(element.tag))
        if not mapping:
            continue
        unit_kind, inner_tag = mapping
        data_xml = next((child for child in list(element) if local_tag(child.tag) == "DataXml"), None)
        inner = first_descendant(data_xml, inner_tag)
        units.append({"source": source, "kind": unit_kind, "header": element, "xml_root": inner})
    return units


def unit_number(unit: dict[str, Any]) -> str:
    header = unit["header"]
    root = editable_root(unit)
    return metadata_value(header, "Number") or (metadata_value(root, "Key") if root is not None else "")


def unit_model_type(unit: dict[str, Any]) -> str:
    header = unit["header"]
    root = editable_root(unit)
    return metadata_value(header, "ModelType") or (metadata_value(root, "ModelType") if root is not None else "")


def editable_root(unit: dict[str, Any]) -> ET.Element:
    if unit["kind"] in {"entity", "form"}:
        root = unit.get("xml_root")
        if root is None:
            raise ContractError("目标元数据单元没有 XML 根")
        return root
    return unit["header"]


def effective_unit_model_type(units: list[dict[str, Any]], unit: dict[str, Any]) -> str:
    direct = unit_model_type(unit)
    if direct:
        return direct
    base_kind = BASE_KIND.get(unit["kind"])
    number = unit_number(unit)
    matches = [
        candidate
        for candidate in units
        if candidate["kind"] == base_kind and unit_number(candidate) == number and unit_model_type(candidate)
    ]
    return unit_model_type(matches[0]) if len(matches) == 1 else ""


def all_document_units(artifact: Artifact) -> list[dict[str, Any]]:
    units = []
    for source, raw in artifact.documents.items():
        root = ET.fromstring(raw)
        for unit in expand_units(root, source):
            unit["document_root"] = root
            units.append(unit)
    return units


@dataclass
class SpanNode:
    tag: str
    attrs: dict[str, str]
    path: str
    start: int
    start_tag_end: int
    end_start: int = 0
    end: int = 0
    children: list["SpanNode"] = field(default_factory=list)


def find_tag_end(raw: bytes, start: int) -> int:
    quote = None
    index = start
    while index < len(raw):
        value = raw[index]
        if quote is not None:
            if value == quote:
                quote = None
        elif value in (34, 39):
            quote = value
        elif value == 62:
            return index
        index += 1
    raise ContractError("XML 标签未闭合")


def span_tree(raw: bytes) -> tuple[SpanNode, dict[str, SpanNode]]:
    parser = expat.ParserCreate()
    stack: list[tuple[SpanNode, Counter[str]]] = []
    paths: dict[str, SpanNode] = {}
    root_node: SpanNode | None = None

    def start(name: str, attrs: dict[str, str]) -> None:
        nonlocal root_node
        tag = name.rsplit(":", 1)[-1]
        byte_index = parser.CurrentByteIndex
        start_end = find_tag_end(raw, byte_index)
        if stack:
            parent, counters = stack[-1]
            ordinal = counters[tag]
            counters[tag] += 1
            path = f"{parent.path}/{tag}[{ordinal}]"
        else:
            path = f"/{tag}[0]"
        node = SpanNode(tag, dict(attrs), path, byte_index, start_end)
        paths[path] = node
        if stack:
            stack[-1][0].children.append(node)
        else:
            root_node = node
        stack.append((node, Counter()))

    def end(_name: str) -> None:
        node, _ = stack.pop()
        current = parser.CurrentByteIndex
        opening = raw[node.start : node.start_tag_end + 1].rstrip()
        if opening.endswith(b"/>"):
            node.end_start = node.start_tag_end - 1
            node.end = node.start_tag_end + 1
            return
        node.end_start = current
        node.end = find_tag_end(raw, current) + 1

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    try:
        parser.Parse(raw, True)
    except expat.ExpatError as exc:
        raise ContractError(f"XML 位置解析失败: {exc}") from exc
    if root_node is None:
        raise ContractError("XML 没有根节点")
    return root_node, paths


def element_paths(root: ET.Element) -> dict[int, str]:
    result: dict[int, str] = {}

    def visit(element: ET.Element, path: str) -> None:
        result[id(element)] = path
        counters: Counter[str] = Counter()
        for child in list(element):
            tag = local_tag(child.tag)
            ordinal = counters[tag]
            counters[tag] += 1
            visit(child, f"{path}/{tag}[{ordinal}]")

    visit(root, f"/{local_tag(root.tag)}[0]")
    return result


def parent_map(root: ET.Element) -> dict[int, ET.Element]:
    return {id(child): parent for parent in root.iter() for child in list(parent)}


def effective_properties(node: ET.Element, standard_node: ET.Element | None) -> dict[str, str]:
    result = direct_properties(standard_node) if standard_node is not None else {}
    result.update(direct_properties(node))
    return result


class Knowledge:
    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.manifest = read_json(self.root / "manifest.json")
        if self.manifest.get("knowledge_version") != SCHEMA_VERSION:
            raise ContractError(
                f"知识库版本不是当前执行器要求的 {SCHEMA_VERSION}，必须从已验证快照重新固化"
            )
        self.entity_types = read_json(self.root / "entity-types.json")
        self.form_types = read_json(self.root / "form-types.json")
        self.control_types = read_json(self.root / "control-types.json")
        self.model_matrix = read_json(self.root / "model-matrix.json")
        self.binding_matrix = read_json(self.root / "binding-matrix.json")
        self.identity_contracts = read_json(self.root / "identity-contracts.json")
        self.localization_term_contracts = read_json(self.root / "localization-term-contracts.json")
        self.mainentity_contract = read_json(self.root / "mainentity-contract.json")
        expected = self.manifest.get("payload_sha256") or {}
        for name, digest in expected.items():
            data = read_json(self.root / name)
            if sha256_bytes(canonical_json(data).encode("utf-8")) != digest:
                raise ContractError(f"知识库哈希不匹配: {name}")
        for name, contract in (self.manifest.get("standard_record_files") or {}).items():
            path = self.root / name
            if not path.is_file() or sha256_bytes(path.read_bytes()) != contract.get("sha256"):
                raise ContractError(f"标准记录文件哈希不匹配: {name}")
        self.standard = {
            "entity": read_jsonl_gz(self.root / "standard-entity.jsonl.gz"),
            "form": read_jsonl_gz(self.root / "standard-form.jsonl.gz"),
        }
        self._standard_by_id = {
            kind: {str(row.get("fid")): row for row in rows if row.get("fid")}
            for kind, rows in self.standard.items()
        }
        self._standard_templates_by_number = {
            kind: {
                str(row.get("fnumber")): row
                for row in rows
                if row.get("scope") == "template" and row.get("fnumber")
            }
            for kind, rows in self.standard.items()
        }

    @property
    def environment(self) -> str:
        return str((self.manifest.get("source") or {}).get("environment") or "")

    def resolve_standard(self, unit: dict[str, Any]) -> tuple[ET.Element | None, dict[str, Any] | None]:
        chain = self.resolve_standard_chain(unit)
        return chain[-1] if chain else (None, None)

    def resolve_standard_chain(self, unit: dict[str, Any]) -> list[tuple[ET.Element, dict[str, Any]]]:
        root = unit.get("xml_root")
        if root is None or unit["kind"] not in {"entity", "form"}:
            return []
        inherit_path = metadata_value(root, "InheritPath") or metadata_value(unit["header"], "InheritPath")
        ids = [item.strip() for item in inherit_path.split(",") if item.strip()]
        parent_id = metadata_value(root, "ParentId") or metadata_value(unit["header"], "ParentId")
        if parent_id and parent_id not in ids:
            ids.append(parent_id)
        records = self._standard_by_id[unit["kind"]]
        chain: list[tuple[ET.Element, dict[str, Any]]] = []
        seen: set[str] = set()
        for identity in ids:
            record = records.get(identity)
            if not record:
                continue
            for root, item in self.resolve_record_chain(unit["kind"], record):
                item_id = str(item.get("fid") or "")
                if item_id in seen:
                    continue
                seen.add(item_id)
                chain.append((root, item))
        return chain

    def standard_record_by_number(self, kind: str, number: str) -> dict[str, Any] | None:
        return self._standard_templates_by_number.get(kind, {}).get(number)

    def standard_record_by_id(self, kind: str, identity: str) -> dict[str, Any] | None:
        return self._standard_by_id.get(kind, {}).get(identity)

    def resolve_record_chain(
        self,
        kind: str,
        record: dict[str, Any],
    ) -> list[tuple[ET.Element, dict[str, Any]]]:
        records = self._standard_by_id[kind]
        ordered: list[dict[str, Any]] = []
        visited: set[str] = set()

        def reference_ids(item: dict[str, Any]) -> list[str]:
            raw_values = [item.get("finheritpath"), item.get("fparentid")]
            try:
                root = ET.fromstring(str(item.get("fdata") or ""))
            except ET.ParseError:
                root = None
            if root is not None:
                raw_values.extend((metadata_value(root, "InheritPath"), metadata_value(root, "ParentId")))
            result: list[str] = []
            for raw in raw_values:
                for identity in str(raw or "").split(","):
                    identity = identity.strip()
                    if identity and identity not in result:
                        result.append(identity)
            return result

        def visit(item: dict[str, Any]) -> None:
            identity = str(item.get("fid") or "")
            token = identity or f"anonymous:{id(item)}"
            if token in visited:
                return
            visited.add(token)
            for parent_id in reference_ids(item):
                parent = records.get(parent_id)
                if parent is not None:
                    visit(parent)
            ordered.append(item)

        visit(record)
        result = []
        for item in ordered:
            try:
                result.append((ET.fromstring(str(item.get("fdata") or "")), item))
            except ET.ParseError:
                continue
        return result

    def entity_record_for_form(self, number: str, entity_id: str = "") -> dict[str, Any] | None:
        if entity_id:
            matched = self.standard_record_by_id("entity", entity_id)
            if matched is not None:
                return matched
        form_record = self.standard_record_by_number("form", number)
        if form_record is not None:
            mapped = self.standard_record_by_id("entity", str(form_record.get("fentityid") or "").strip())
            if mapped is not None:
                return mapped
        return self.standard_record_by_number("entity", number)

    def is_control_type(self, node_type: str) -> bool:
        return node_type in self.control_types.get("control_types", {})

    def property_contract(self, kind: str, node_type: str, property_name: str) -> dict[str, Any] | None:
        catalog = self.entity_types if BASE_KIND.get(kind) == "entity" else self.form_types
        return ((catalog.get("node_types") or {}).get(node_type, {}).get("properties") or {}).get(property_name)

    def binding_observed(
        self,
        model_type: str,
        field_type: str,
        control_type: str,
        binding_property: str,
    ) -> bool:
        return any(
            row.get("model_type") == model_type
            and row.get("field_type") == field_type
            and row.get("control_type") == control_type
            and row.get("binding_property") == binding_property
            and int(row.get("occurrences", 0)) > 0
            for row in self.binding_matrix.get("bindings", [])
        )

    def operation_binding_observed(
        self,
        model_type: str,
        operation_type: str,
        control_type: str,
    ) -> bool:
        return any(
            row.get("model_type") == model_type
            and row.get("operation_type") == operation_type
            and row.get("control_type") == control_type
            and row.get("binding_property") == "OperationKey"
            and int(row.get("occurrences", 0)) > 0
            for row in self.binding_matrix.get("operation_bindings", [])
        )

    def form_action_observed(
        self,
        model_type: str,
        control_type: str,
        operation_key: str,
    ) -> bool:
        return any(
            row.get("model_type") == model_type
            and row.get("control_type") == control_type
            and row.get("binding_property") == "OperationKey"
            and row.get("operation_key") == operation_key
            and int(row.get("occurrences", 0)) > 0
            for row in self.binding_matrix.get("form_action_bindings", [])
        )

    def generic_profile(self, kind: str, node_type: str, model_type: str, parent_type: str) -> dict[str, Any] | None:
        catalog = self.entity_types if kind == "entity" else self.form_types
        info = catalog["node_types"].get(node_type)
        if not info:
            return None
        exact = [
            profile
            for profile in info["profiles"]
            if profile["model_type"] == (model_type or "<unknown>") and profile["parent_type"] == parent_type
        ]
        return exact[0] if len(exact) == 1 else None

    def control_profile(
        self,
        node_type: str,
        host_model: str,
        page_model: str,
        semantic_parent: str,
    ) -> dict[str, Any] | None:
        info = self.control_types["control_types"].get(node_type)
        if not info:
            return None
        exact = [
            profile
            for profile in info["profiles"]
            if profile["host_model_type"] == host_model
            and profile["page_model_type"] == page_model
            and profile["parent_type"] == semantic_parent
            and profile["full_definition_nodes"] > 0
        ]
        return exact[0] if len(exact) == 1 else None


def standard_identity_index(root: ET.Element | None) -> dict[str, ET.Element]:
    result = {}
    if root is None:
        return result
    for node in root.iter():
        props = direct_properties(node)
        for value in (props.get("Id"), props.get("PkId"), props.get("Key"), element_oid(node)):
            if value:
                result[value] = node
    return result


def standard_identity_index_many(roots: Iterable[ET.Element]) -> dict[str, ET.Element]:
    result: dict[str, ET.Element] = {}
    for root in roots:
        result.update(standard_identity_index(root))
    return result


def nearest_ancestor(node: ET.Element, parents: dict[int, ET.Element], tag: str) -> ET.Element | None:
    current = node
    while id(current) in parents:
        current = parents[id(current)]
        if local_tag(current.tag) == tag:
            return current
    return None


def semantic_parent_type(
    node: ET.Element,
    page: ET.Element | None,
    standard_node: ET.Element | None,
    standard_page: ET.Element | None,
    standard_index: dict[str, ET.Element],
) -> str:
    props = effective_properties(node, standard_node)
    return semantic_parent_type_for_id(
        props.get("ParentId", ""), page, standard_page, standard_index
    )


def semantic_parent_type_for_id(
    parent_id: str,
    page: ET.Element | None,
    standard_page: ET.Element | None,
    standard_index: dict[str, ET.Element],
) -> str:
    if not parent_id:
        return "none"
    page_props = effective_properties(page, standard_page) if page is not None else {}
    if page is not None and parent_id in {page_props.get("Id"), page_props.get("PkId")}:
        return "FormMetadata"
    if page is not None:
        for candidate in page.iter():
            candidate_props = direct_properties(candidate)
            if parent_id in {candidate_props.get("Id"), candidate_props.get("PkId")}:
                return local_tag(candidate.tag)
    standard_parent = standard_index.get(parent_id)
    if standard_parent is not None:
        return local_tag(standard_parent.tag)
    return "unresolved"


def semantic_parent_index(
    page: ET.Element | None,
    standard_page: ET.Element | None,
    standard_index: dict[str, ET.Element],
) -> dict[str, ET.Element]:
    result = dict(standard_index)
    for source in (standard_page, page):
        if source is None:
            continue
        for candidate in source.iter():
            props = direct_properties(candidate)
            for name in ("Id", "PkId", "Key"):
                if props.get(name):
                    result[props[name]] = candidate
    return result


def would_create_parent_cycle(
    node: ET.Element,
    standard_node: ET.Element | None,
    new_parent_id: str,
    page: ET.Element | None,
    standard_page: ET.Element | None,
    standard_index: dict[str, ET.Element],
    current_root: ET.Element | None = None,
) -> bool:
    node_ids = {
        value
        for value in (
            effective_properties(node, standard_node).get("Id"),
            effective_properties(node, standard_node).get("PkId"),
        )
        if value
    }
    if new_parent_id in node_ids:
        return True
    index = semantic_parent_index(page, standard_page, standard_index)
    if current_root is not None:
        index.update(standard_identity_index(current_root))
    seen = set()
    current = new_parent_id
    while current and current not in seen:
        if current in node_ids:
            return True
        seen.add(current)
        parent = index.get(current)
        if parent is None:
            return False
        parent_standard = standard_index.get(element_oid(parent))
        current = effective_properties(parent, parent_standard).get("ParentId", "")
    return False


def select_unit(units: list[dict[str, Any]], target: dict[str, Any]) -> dict[str, Any]:
    matches = [unit for unit in units if unit["kind"] == target.get("kind")]
    if target.get("document"):
        matches = [unit for unit in matches if unit["source"] == target["document"]]
    if target.get("number"):
        matches = [unit for unit in matches if unit_number(unit) == target["number"]]
    if len(matches) != 1:
        raise ContractError(f"目标元数据单元必须唯一，实际匹配 {len(matches)} 个")
    if matches[0]["kind"] in {"entity", "form"} and matches[0].get("xml_root") is None:
        raise ContractError("目标元数据单元没有 XML 根")
    return matches[0]


def locator_value(node: ET.Element, standard_node: ET.Element | None, field_name: str) -> str:
    if field_name == "oid":
        return element_oid(node)
    return effective_properties(node, standard_node).get(field_name, "")


def matching_target_nodes(
    unit: dict[str, Any],
    target: dict[str, Any],
    standard_roots: Iterable[ET.Element],
) -> list[tuple[ET.Element, ET.Element | None]]:
    locator = target.get("locator") or {}
    present = [(name, value) for name, value in locator.items() if name in LOCATOR_FIELDS and value]
    if len(present) != 1:
        raise ContractError("target.locator 必须且只能提供 key/id/oid/operation_key/class_name 之一")
    locator_name, expected = present[0]
    field_name = LOCATOR_FIELDS[locator_name]
    standard_index = standard_identity_index_many(standard_roots)
    root = editable_root(unit)
    parents = parent_map(root)
    matches = []
    for node in root.iter():
        if target.get("node_type") and local_tag(node.tag) != target["node_type"]:
            continue
        standard_node = standard_index.get(element_oid(node))
        if locator_value(node, standard_node, field_name) != str(expected):
            continue
        if target.get("page_key") and unit["kind"] == "form":
            page = node if local_tag(node.tag) == "FormMetadata" else nearest_ancestor(node, parents, "FormMetadata")
            standard_page = standard_index.get(element_oid(page)) if page is not None else None
            page_key = effective_properties(page, standard_page).get("Key", "") if page is not None else ""
            if page_key != target["page_key"]:
                continue
        matches.append((node, standard_node))
    return matches


def select_target_node(
    unit: dict[str, Any],
    target: dict[str, Any],
    standard_roots: Iterable[ET.Element],
) -> tuple[ET.Element, ET.Element | None]:
    matches = matching_target_nodes(unit, target, standard_roots)
    if len(matches) != 1:
        raise ContractError(f"目标节点必须唯一，实际匹配 {len(matches)} 个")
    return matches[0]


def normalized_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def property_shape_issue(contract: dict[str, Any] | None, property_name: str, value: Any) -> str | None:
    if contract is None:
        return None
    observed = set((contract.get("value_shapes") or {}).keys())
    actual = value_shape(normalized_scalar(value))
    strict = {"boolean", "color", "dimension"}
    numeric = {"integer", "decimal"}
    if observed and observed <= strict and actual not in observed:
        return f"{property_name} 值形态为 {actual}，实际标准只观察到 {','.join(sorted(observed))}"
    if observed and observed <= numeric and actual not in numeric:
        return f"{property_name} 值形态为 {actual}，实际标准只观察到数值"
    return None


def plugin_evidence_issue(change: dict[str, Any], node_type: str, parent_type: str) -> str | None:
    """Require business-object evidence for plugin attachment changes.

    Standard templates prove XML shape, not that a business plugin, page, or
    operation is the intended attachment target.
    """
    if node_type not in PLUGIN_NODE_TYPES and parent_type not in PLUGIN_NODE_TYPES:
        return None
    evidence = change.get("plugin_evidence")
    if not isinstance(evidence, dict):
        return "插件挂载变更缺少 kingdee-metadata-analyzer 取证"
    if evidence.get("source") != "kingdee-metadata-analyzer":
        return "插件挂载取证来源必须是 kingdee-metadata-analyzer"
    if not str(evidence.get("reference") or "").strip():
        return "插件挂载取证缺少可追溯 reference"
    return None


def entity_context_roots(
    knowledge: Knowledge,
    units: list[dict[str, Any]],
    form_unit: dict[str, Any],
) -> list[ET.Element]:
    form_header = direct_properties(form_unit["header"])
    form_root = direct_properties(editable_root(form_unit))
    entity_id = form_header.get("EntityId") or form_root.get("EntityId") or ""
    entity_units = [unit for unit in units if unit["kind"] == "entity"]
    exact = []
    if entity_id:
        for unit in entity_units:
            identities = {
                value
                for source in (direct_properties(unit["header"]), direct_properties(editable_root(unit)))
                for name, value in source.items()
                if name in {"Id", "PkId", "MasterId"} and value
            }
            if entity_id in identities:
                exact.append(unit)
    if not exact:
        number = unit_number(form_unit)
        exact = [unit for unit in entity_units if unit_number(unit) == number]
    if len(exact) == 1:
        entity_unit = exact[0]
        roots = [root for root, _ in knowledge.resolve_standard_chain(entity_unit)]
        roots.append(editable_root(entity_unit))
        return roots
    record = knowledge.entity_record_for_form(unit_number(form_unit), entity_id)
    if record is None:
        return []
    return [root for root, _ in knowledge.resolve_record_chain("entity", record)]


def field_type_index(
    knowledge: Knowledge,
    units: list[dict[str, Any]],
    form_unit: dict[str, Any],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for root in entity_context_roots(knowledge, units, form_unit):
        for node in root.iter():
            node_type = local_tag(node.tag)
            props = direct_properties(node)
            if not node_type.endswith("Field") or not props.get("Key"):
                continue
            for identity in (props.get("Key"), props.get("Id"), props.get("FieldName")):
                if identity:
                    result[identity] = node_type
    return result


def operation_type_index(
    knowledge: Knowledge,
    units: list[dict[str, Any]],
    form_unit: dict[str, Any],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for root in entity_context_roots(knowledge, units, form_unit):
        parents = parent_map(root)
        for node in root.iter():
            parent = parents.get(id(node))
            props = direct_properties(node)
            if (
                parent is not None
                and local_tag(parent.tag) == "Operations"
                and props.get("Key")
            ):
                result[props["Key"]] = local_tag(node.tag)
    return result


def operation_binding_issues(
    knowledge: Knowledge,
    units: list[dict[str, Any]],
    form_unit: dict[str, Any],
    model_type: str,
    node_type: str,
    operation_key: str,
) -> list[str]:
    if not operation_key:
        return []
    operation_type = operation_type_index(knowledge, units, form_unit).get(operation_key)
    if operation_type:
        if knowledge.operation_binding_observed(model_type, operation_type, node_type):
            return []
        return [f"未观察到 {model_type}/{operation_type}/{node_type}/OperationKey 操作绑定组合"]
    if knowledge.form_action_observed(model_type, node_type, operation_key):
        return []
    return [f"OperationKey={operation_key} 既不是同业务对象实体操作，也不是该模型/控件的实际标准表单动作"]


def external_references(units: list[dict[str, Any]], node: ET.Element, standard_node: ET.Element | None) -> list[dict[str, str]]:
    identities = {
        value
        for name, value in effective_properties(node, standard_node).items()
        if name in {"Id", "PkId", "Key"} and value
    }
    if not identities:
        return []
    references = []
    for unit in units:
        for candidate in editable_root(unit).iter():
            if candidate is node:
                continue
            for property_name, value in direct_properties(candidate).items():
                if property_name not in REFERENCE_PROPERTIES or value not in identities:
                    continue
                references.append(
                    {
                        "unit": unit_number(unit),
                        "kind": unit["kind"],
                        "node_type": local_tag(candidate.tag),
                        "node_key": direct_properties(candidate).get("Key", ""),
                        "property": property_name,
                    }
                )
    return references


def resolve_change(
    knowledge: Knowledge,
    artifact: Artifact,
    units: list[dict[str, Any]],
    change: dict[str, Any],
) -> dict[str, Any]:
    action = change.get("action")
    if action not in {"modify", "move", "delete", "restore", "add"}:
        raise ContractError(f"不支持的 action: {action}")
    target = change.get("target") or {}
    if target.get("kind") not in SUPPORTED_KINDS:
        raise ContractError("target.kind 不是支持的实体、表单、多语言或术语层")
    unit = select_unit(units, target)
    model_type = effective_unit_model_type(units, unit)
    if not model_type:
        raise ContractError("无法识别目标 ModelType")
    standard_chain = knowledge.resolve_standard_chain(unit)
    standard_roots = [root for root, _ in standard_chain]
    standard_root, standard_record = standard_chain[-1] if standard_chain else (None, None)
    standard_index = standard_identity_index_many(standard_roots)
    if action == "add":
        node_type = target.get("node_type")
        parent_type = target.get("parent_type")
        if not node_type or not parent_type:
            raise ContractError("新增必须指定实际 node_type 和 parent_type")
        base_kind = BASE_KIND[target["kind"]]
        generic_profile = knowledge.generic_profile(base_kind, node_type, model_type, parent_type)
        control_profile = None
        issues = []
        plugin_issue = plugin_evidence_issue(change, node_type, parent_type)
        if plugin_issue:
            issues.append(plugin_issue)
        if target["kind"] not in {"entity", "form"}:
            issues.append("多语言/术语行新增尚无同版本平台序列化回导合同")
        if knowledge.is_control_type(node_type):
            page_model = str(target.get("page_model_type") or "")
            semantic_parent = str(target.get("semantic_parent_type") or "")
            if not page_model or not semantic_parent:
                issues.append("新增控件必须由引擎解析 page_model_type 和 semantic_parent_type")
            else:
                control_profile = knowledge.control_profile(node_type, model_type, page_model, semantic_parent)
                if control_profile is None:
                    issues.append("控件类型/宿主模型/页面模型/父容器组合没有生产标准完整实例")
        if generic_profile is None:
            issues.append("节点类型/模型/XML 父节点组合没有生产标准完整实例")
        identity = knowledge.identity_contracts["contracts"].get(f"{base_kind}:{node_type}")
        generation = ((identity or {}).get("generation") or {}).get("status")
        if generation != "authoring-verified":
            issues.append("新增身份合同尚未完成同版本 DEV 创建、回导和再导出验证")
        return {
            "status": "blocked" if issues else "ready",
            "reason": "; ".join(issues) if issues else None,
            "issues": issues,
            "action": action,
            "target": target,
            "model_type": model_type,
            "page_model_type": target.get("page_model_type"),
            "parent_type": parent_type,
            "semantic_parent_type": target.get("semantic_parent_type"),
            "profile_source": "control" if control_profile else "generic",
            "profile": control_profile or generic_profile,
            "property_profile": generic_profile,
            "identity_generation": (identity or {}).get("generation"),
            "unit": unit,
            "standard_record": standard_record,
            "standard_lineage": [record for _, record in standard_chain],
        }

    node, standard_node = select_target_node(unit, target, standard_roots)
    root = editable_root(unit)
    parents = parent_map(root)
    parent = parents.get(id(node))
    parent_type = local_tag(parent.tag) if parent is not None else "none"
    props = effective_properties(node, standard_node)
    page = (
        node if local_tag(node.tag) == "FormMetadata" else nearest_ancestor(node, parents, "FormMetadata")
    ) if unit["kind"] == "form" else None
    standard_page = standard_index.get(element_oid(page)) if page is not None else None
    page_model = effective_properties(page, standard_page).get("ModelType", model_type) if page is not None else model_type
    semantic_parent = (
        semantic_parent_type(node, page, standard_node, standard_page, standard_index)
        if unit["kind"] == "form"
        else parent_type
    )
    control_profile = knowledge.control_profile(local_tag(node.tag), model_type, page_model, semantic_parent)
    generic_profile = knowledge.generic_profile(BASE_KIND[target["kind"]], local_tag(node.tag), model_type, parent_type)
    profile = control_profile or generic_profile
    actual_property_names = set(direct_properties(node))
    standard_property_names = set(direct_properties(standard_node)) if standard_node is not None else set()
    allowed_property_names = set(generic_profile.get("observed_properties", [])) if generic_profile else set()
    allowed_property_names |= set(control_profile.get("observed_properties", [])) if control_profile else set()
    allowed_property_names |= standard_property_names | actual_property_names
    normalized_change = copy.deepcopy(change)
    issues = []
    plugin_issue = plugin_evidence_issue(
        normalized_change, local_tag(node.tag), parent_type
    )
    if plugin_issue:
        issues.append(plugin_issue)
    if unit["kind"] not in {"entity", "form"} and action != "modify":
        issues.append("多语言/术语层当前只允许修改基线中已存在的标量属性")
    if action == "move":
        new_parent = str(change.get("new_parent_id") or "")
        if not new_parent:
            issues.append("move 缺少 new_parent_id")
        if change.get("set") or change.get("unset"):
            issues.append("move 不能同时携带其他属性修改")
        normalized_change["set"] = {"ParentId": new_parent}
        normalized_change["unset"] = []
        if new_parent:
            if unit["kind"] == "form":
                destination_type = semantic_parent_type_for_id(
                    new_parent, page, standard_page, standard_index
                )
                destination_profile = knowledge.control_profile(
                    local_tag(node.tag), model_type, page_model, destination_type
                )
                if knowledge.is_control_type(local_tag(node.tag)) and destination_profile is None:
                    issues.append("移动后的控件类型/模型/父容器组合没有生产标准完整实例")
                else:
                    control_profile = destination_profile or control_profile
                    profile = control_profile or generic_profile
                semantic_parent = destination_type
            else:
                destination_index = standard_identity_index_many([*standard_roots, root])
                destination = destination_index.get(new_parent)
                semantic_parent = local_tag(destination.tag) if destination is not None else "unresolved"
                if destination is None:
                    issues.append("移动目标 ParentId 无法在当前实体或标准祖先中解析")
            if would_create_parent_cycle(
                node, standard_node, new_parent, page, standard_page, standard_index, root
            ):
                issues.append("移动会形成 ParentId 循环")
    requested = set((normalized_change.get("set") or {})) | set(normalized_change.get("unset") or [])
    unknown = sorted(requested - allowed_property_names)
    if unknown:
        issues.append("属性未出现在目标节点或精确实际合同: " + ", ".join(unknown))
    if action == "modify" and not requested:
        issues.append("modify 没有属性变化")
    if action == "modify" and requested & (IDENTITY_PROPERTIES | {"ParentId"}):
        issues.append("身份属性不能按普通修改处理；ParentId 必须使用 move，其他身份需平台生成合同")
    if action in {"delete", "restore"} and requested:
        issues.append(f"{action} 不能同时携带属性修改")
    for name in normalized_change.get("unset") or []:
        if name not in actual_property_names:
            issues.append(f"unset 只能删除当前差量节点中实际存在的属性: {name}")
    for name, value in (normalized_change.get("set") or {}).items():
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            issues.append(f"复杂属性不能通过 scalar set 修改: {name}")
            continue
        shape_issue = property_shape_issue(
            knowledge.property_contract(unit["kind"], local_tag(node.tag), name), name, value
        )
        if shape_issue:
            issues.append(shape_issue)
    new_properties = requested - actual_property_names - standard_property_names
    if knowledge.is_control_type(local_tag(node.tag)) and control_profile is None and new_properties:
        issues.append("现有控件组合没有精确标准 profile，不能向其增加新属性")
    if unit["kind"] == "form":
        fields = field_type_index(knowledge, units, unit)
        for binding_name in sorted(BINDING_PROPERTIES & set((normalized_change.get("set") or {}))):
            binding_value = normalized_scalar(normalized_change["set"][binding_name])
            if not binding_value:
                continue
            field_type = fields.get(binding_value)
            if not field_type:
                issues.append(f"{binding_name}={binding_value} 无法解析到同业务对象字段")
            elif not knowledge.binding_observed(
                model_type, field_type, local_tag(node.tag), binding_name
            ):
                issues.append(
                    f"未观察到 {model_type}/{field_type}/{local_tag(node.tag)}/{binding_name} 绑定组合"
                )
        if "OperationKey" in (normalized_change.get("set") or {}):
            issues.extend(
                operation_binding_issues(
                    knowledge,
                    units,
                    unit,
                    model_type,
                    local_tag(node.tag),
                    normalized_scalar(normalized_change["set"]["OperationKey"]),
                )
            )
    if action == "delete" and element_action(node):
        issues.append("继承差量节点不能按完整业务节点删除；使用 restore 或经 DEV 验证的 delete 合同")
    if action == "delete" and not element_action(node):
        references = external_references(units, node, standard_node)
        if references:
            issues.append(f"目标仍被 {len(references)} 个 ParentId/字段/操作引用")
    else:
        references = []
    if action == "restore" and not element_action(node):
        issues.append("restore 只适用于业务层继承覆盖节点")
    return {
        "status": "invalid" if issues else "ready",
        "issues": issues,
        "action": action,
        "change": normalized_change,
        "target": target,
        "unit": unit,
        "node": node,
        "standard_node": standard_node,
        "standard_record": standard_record,
        "standard_lineage": [record for _, record in standard_chain],
        "model_type": model_type,
        "page_model_type": page_model,
        "parent_type": parent_type,
        "semantic_parent_type": semantic_parent,
        "profile_source": "control" if control_profile else "generic",
        "profile": profile,
        "property_profile": generic_profile,
        "effective_properties": props,
        "requested_properties": sorted(requested),
        "references": references,
    }


def public_resolution(resolved: dict[str, Any]) -> dict[str, Any]:
    profile = resolved.get("profile") or {}
    record = resolved.get("standard_record") or {}
    props = resolved.get("effective_properties") or {}
    return {
        "status": resolved["status"],
        "action": resolved["action"],
        "target": resolved["target"],
        "target_name": props.get("Name", ""),
        "model_type": resolved.get("model_type"),
        "page_model_type": resolved.get("page_model_type"),
        "parent_type": resolved.get("parent_type"),
        "semantic_parent_type": resolved.get("semantic_parent_type"),
        "profile_source": resolved.get("profile_source"),
        "profile_occurrences": profile.get("occurrences"),
        "profile_full_definitions": profile.get("full_definition_nodes"),
        "standard_template": record.get("fnumber"),
        "standard_fdata_sha256": (record.get("fdata_summary") or {}).get("sha256"),
        "standard_lineage": [
            {
                "fid": item.get("fid"),
                "number": item.get("fnumber"),
                "fdata_sha256": (item.get("fdata_summary") or {}).get("sha256"),
            }
            for item in resolved.get("standard_lineage", [])
        ],
        "requested_properties": resolved.get("requested_properties", []),
        "blocking_references": resolved.get("references", []),
        "identity_generation": resolved.get("identity_generation"),
        "issues": resolved.get("issues", []),
        "reason": resolved.get("reason"),
    }


def validate_contract(contract: dict[str, Any], artifact: Artifact, knowledge: Knowledge) -> None:
    if contract.get("contract_version") != CONTRACT_VERSION:
        raise ContractError("内部变更描述版本不兼容；请用当前执行器重新生成")
    if contract.get("environment") != knowledge.environment:
        raise ContractError("变更环境与固化知识库环境不一致")
    if contract.get("baseline_sha256") != sha256_bytes(artifact.raw):
        raise ContractError("baseline_sha256 与输入文件不一致")
    provenance = contract.get("baseline_provenance") or {}
    classification = provenance.get("classification")
    if classification not in SAFE_BASELINE_CLASSES:
        raise ContractError(
            "基线血缘不是可写来源；必须是 platform-exported、user-confirmed-original 或 repository-canonical"
        )
    if not str(provenance.get("evidence") or "").strip():
        raise ContractError("baseline_provenance.evidence 不能为空")
    changes = contract.get("changes")
    if not isinstance(changes, list) or not changes:
        raise ContractError("内部变更描述必须包含非空 changes")


def resolve_contract(knowledge: Knowledge, artifact: Artifact, contract: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    validate_contract(contract, artifact, knowledge)
    units = all_document_units(artifact)
    resolved = [resolve_change(knowledge, artifact, units, change) for change in contract["changes"]]
    public = [public_resolution(item) for item in resolved]
    return resolved, public


def line_start(raw: bytes, index: int) -> int:
    value = raw.rfind(b"\n", 0, index)
    return 0 if value < 0 else value + 1


def line_end(raw: bytes, index: int) -> int:
    value = raw.find(b"\n", index)
    return len(raw) if value < 0 else value + 1


def indentation(raw: bytes, index: int) -> bytes:
    start = line_start(raw, index)
    prefix = raw[start:index]
    return prefix if prefix.strip() == b"" else b""


def remove_span(raw: bytes, node: SpanNode) -> tuple[int, int, bytes]:
    start = line_start(raw, node.start)
    end = line_end(raw, node.end)
    if raw[start:node.start].strip() or raw[node.end:end].strip():
        return node.start, node.end, b""
    return start, end, b""


def set_scalar_patch(
    raw: bytes,
    target: SpanNode,
    property_name: str,
    value: str,
    observed_order: list[str],
) -> tuple[int, int, bytes]:
    matches = [child for child in target.children if child.tag == property_name]
    if len(matches) > 1:
        raise ContractError(f"属性节点不唯一: {property_name}")
    encoded = escape(str(value), {'"': "&quot;"}).encode("utf-8")
    if matches:
        child = matches[0]
        return child.start_tag_end + 1, child.end_start, encoded
    child_indent = indentation(raw, target.children[0].start) if target.children else indentation(raw, target.end_start) + b"  "
    newline = b"\r\n" if b"\r\n" in raw else b"\n"
    insert_at = line_start(raw, target.end_start)
    if property_name in observed_order:
        target_order = observed_order.index(property_name)
        for child in target.children:
            if child.tag in observed_order and observed_order.index(child.tag) > target_order:
                insert_at = line_start(raw, child.start)
                break
    fragment = child_indent + b"<" + property_name.encode("utf-8") + b">" + encoded + b"</" + property_name.encode("utf-8") + b">" + newline
    return insert_at, insert_at, fragment


def unset_scalar_patch(raw: bytes, target: SpanNode, property_name: str) -> tuple[int, int, bytes]:
    matches = [child for child in target.children if child.tag == property_name]
    if len(matches) != 1:
        raise ContractError(f"待删除属性必须存在且唯一: {property_name}")
    return remove_span(raw, matches[0])


def apply_patches(raw: bytes, patches: list[tuple[int, int, bytes]]) -> bytes:
    result = raw
    last_start = len(raw) + 1
    for start, end, replacement in sorted(patches, key=lambda item: (item[0], item[1]), reverse=True):
        if end > last_start:
            raise ContractError("XML 修改区间重叠")
        result = result[:start] + replacement + result[end:]
        last_start = start
    ET.fromstring(result)
    return result


def apply_resolved(artifact: Artifact, resolved: list[dict[str, Any]]) -> tuple[bytes, list[dict[str, Any]]]:
    documents = dict(artifact.documents)
    changes_by_document: dict[str, list[dict[str, Any]]] = {}
    for item in resolved:
        if item["status"] != "ready":
            raise ContractError("内部变更描述包含未就绪变更")
        if item["action"] == "add":
            raise ContractError("新增合同尚未 authoring-verified")
        changes_by_document.setdefault(item["unit"]["source"], []).append(item)
    applied = []
    for source, items in changes_by_document.items():
        raw = documents[source]
        document_root = items[0]["unit"]["document_root"]
        paths = element_paths(document_root)
        _, span_paths = span_tree(raw)
        patches = []
        for item in items:
            target_path = paths[id(item["node"])]
            target_span = span_paths.get(target_path)
            if target_span is None:
                raise ContractError(f"无法定位原始 XML 字节区间: {target_path}")
            action = item["action"]
            change = item.get("change") or {}
            if action in {"delete", "restore"}:
                patches.append(remove_span(raw, target_span))
            else:
                profile = item.get("property_profile") or item.get("profile") or {}
                observed_order = profile.get("observed_child_order", [])
                for name, value in (change.get("set") or {}).items():
                    if not isinstance(value, (str, int, float, bool)) and value is not None:
                        raise ContractError(f"复杂属性不能通过 scalar set 修改: {name}")
                    normalized = normalized_scalar(value)
                    patches.append(set_scalar_patch(raw, target_span, name, normalized, observed_order))
                for name in change.get("unset") or []:
                    patches.append(unset_scalar_patch(raw, target_span, name))
            applied.append(
                {
                    "action": action,
                    "document": source,
                    "target": item["target"],
                    "target_name": item.get("effective_properties", {}).get("Name", ""),
                    "properties": item.get("requested_properties", []),
                }
            )
        documents[source] = apply_patches(raw, patches)
    return artifact.build(documents), applied


def structural_signature(element: ET.Element) -> tuple[Any, ...]:
    text = (element.text or "").strip() if len(element) == 0 else ""
    return (
        local_tag(element.tag),
        tuple(sorted((local_tag(name), str(value)) for name, value in element.attrib.items())),
        text,
        tuple(structural_signature(child) for child in list(element)),
    )


def non_metadata_members(artifact: Artifact) -> dict[str, bytes]:
    if not artifact.is_zip:
        return {}
    result = {}
    with zipfile.ZipFile(io.BytesIO(artifact.raw), "r") as archive:
        for info in archive.infolist():
            if info.filename in artifact.documents:
                continue
            result[info.filename] = b"" if info.is_dir() else archive.read(info)
    return result


def validate_platform_added_node(
    knowledge: Knowledge,
    units: list[dict[str, Any]],
    change: dict[str, Any],
) -> dict[str, Any]:
    target = change.get("target") or {}
    if target.get("kind") not in SUPPORTED_KINDS:
        raise ContractError("新增目标 kind 不受支持")
    unit = select_unit(units, target)
    model_type = effective_unit_model_type(units, unit)
    if not model_type:
        raise ContractError("新增候选无法识别 ModelType")
    chain = knowledge.resolve_standard_chain(unit)
    standard_roots = [root for root, _ in chain]
    node, standard_node = select_target_node(unit, target, standard_roots)
    if standard_node is not None or element_action(node):
        raise ContractError("平台新增候选必须是业务层完整节点，不能是继承覆盖节点")
    root = editable_root(unit)
    parents = parent_map(root)
    parent = parents.get(id(node))
    if parent is None:
        raise ContractError("不支持把整个元数据根作为新增节点")
    node_type = local_tag(node.tag)
    parent_type = local_tag(parent.tag)
    props = direct_properties(node)
    issues = []
    plugin_issue = plugin_evidence_issue(change, node_type, parent_type)
    if plugin_issue:
        issues.append(plugin_issue)
    generic_profile = None
    control_profile = None
    page_model = model_type
    semantic_parent = parent_type
    if unit["kind"] in {"entity", "form"}:
        generic_profile = knowledge.generic_profile(
            BASE_KIND[unit["kind"]], node_type, model_type, parent_type
        )
        if generic_profile is None or int(generic_profile.get("full_definition_nodes", 0)) == 0:
            issues.append("新增节点类型/模型/XML 父节点组合没有生产标准完整实例")
    if unit["kind"] == "form" and knowledge.is_control_type(node_type):
        standard_index = standard_identity_index_many(standard_roots)
        page = node if node_type == "FormMetadata" else nearest_ancestor(node, parents, "FormMetadata")
        standard_page = standard_index.get(element_oid(page)) if page is not None else None
        page_model = effective_properties(page, standard_page).get("ModelType", model_type) if page is not None else model_type
        semantic_parent = semantic_parent_type(node, page, None, standard_page, standard_index)
        control_profile = knowledge.control_profile(node_type, model_type, page_model, semantic_parent)
        if control_profile is None:
            issues.append("新增控件类型/宿主模型/页面模型/父容器组合没有生产标准完整实例")
    allowed = set(generic_profile.get("observed_properties", [])) if generic_profile else set()
    allowed |= set(control_profile.get("observed_properties", [])) if control_profile else set()
    if unit["kind"] in {"entity", "form"}:
        unknown = sorted(set(props) - allowed)
        if unknown:
            issues.append("新增节点包含精确实际合同未观察到的属性: " + ", ".join(unknown))
        for name, value in props.items():
            shape_issue = property_shape_issue(
                knowledge.property_contract(unit["kind"], node_type, name), name, value
            )
            if shape_issue:
                issues.append(shape_issue)
        nested = {local_tag(child.tag) for child in list(node) if len(child) > 0}
        allowed_nested = set((generic_profile.get("observed_nested_sections") or {}).keys()) if generic_profile else set()
        if control_profile:
            allowed_nested |= set((control_profile.get("nested_sections") or {}).keys())
        unknown_nested = sorted(nested - allowed_nested)
        if unknown_nested:
            issues.append("新增节点包含精确实际合同未观察到的复杂区段: " + ", ".join(unknown_nested))
        observed_attributes = set(generic_profile.get("observed_attributes", [])) if generic_profile else set()
        unknown_attributes = sorted(
            local_tag(name) for name in node.attrib if local_tag(name) not in observed_attributes
        )
        if unknown_attributes:
            issues.append("新增节点包含精确实际合同未观察到的 XML 属性: " + ", ".join(unknown_attributes))
        required_common = set(generic_profile.get("observed_common_properties", [])) if generic_profile else set()
        if control_profile:
            required_common |= set(control_profile.get("observed_common_properties", []))
        missing_common = sorted(name for name in required_common if name not in props)
        if missing_common:
            issues.append("平台新增节点缺少精确完整实例共有属性: " + ", ".join(missing_common))
        identity = knowledge.identity_contracts.get("contracts", {}).get(
            f"{BASE_KIND[unit['kind']]}:{node_type}"
        )
        exact_identity_profiles = [
            profile
            for profile in (identity or {}).get("profiles", [])
            if profile.get("model_type") == model_type and profile.get("parent_type") == parent_type
        ]
        if len(exact_identity_profiles) != 1:
            issues.append("新增节点缺少精确身份属性合同")
        else:
            required = set(exact_identity_profiles[0].get("observed_common_identity_properties", []))
            missing = sorted(name for name in required if not props.get(name))
            if missing:
                issues.append("平台新增节点缺少实际完整实例共有身份属性: " + ", ".join(missing))
    if unit["kind"] == "form":
        fields = field_type_index(knowledge, units, unit)
        for binding_name in sorted(BINDING_PROPERTIES & set(props)):
            binding_value = props.get(binding_name, "")
            if not binding_value:
                continue
            field_type = fields.get(binding_value)
            if not field_type:
                issues.append(f"{binding_name}={binding_value} 无法解析到同业务对象字段")
            elif not knowledge.binding_observed(model_type, field_type, node_type, binding_name):
                issues.append(
                    f"未观察到 {model_type}/{field_type}/{node_type}/{binding_name} 绑定组合"
                )
        if props.get("OperationKey"):
            issues.extend(
                operation_binding_issues(
                    knowledge,
                    units,
                    unit,
                    model_type,
                    node_type,
                    props["OperationKey"],
                )
            )
    return {
        "status": "invalid" if issues else "ready",
        "issues": issues,
        "action": "add",
        "target": target,
        "unit": unit,
        "node": node,
        "model_type": model_type,
        "page_model_type": page_model,
        "parent_type": parent_type,
        "semantic_parent_type": semantic_parent,
        "profile_source": "control" if control_profile else "generic",
        "profile": control_profile or generic_profile,
        "effective_properties": props,
        "requested_properties": sorted(props),
        "standard_record": chain[-1][1] if chain else None,
        "standard_lineage": [record for _, record in chain],
    }


def verify_platform_candidate(
    knowledge: Knowledge,
    baseline: Artifact,
    candidate: Artifact,
    contract: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    validate_contract(contract, baseline, knowledge)
    if contract.get("candidate_sha256") != sha256_bytes(candidate.raw):
        raise ContractError("candidate_sha256 与平台候选不一致")
    candidate_provenance = contract.get("candidate_provenance") or {}
    if candidate_provenance.get("classification") != "platform-exported":
        raise ContractError("新增候选必须是同版本平台设计器保存后直接导出的文件")
    if not str(candidate_provenance.get("evidence") or "").strip():
        raise ContractError("candidate_provenance.evidence 不能为空")
    if any(change.get("action") != "add" for change in contract["changes"]):
        raise ContractError("verify-platform-candidate 只验证平台创建的新节点")
    if baseline.is_zip != candidate.is_zip:
        raise ContractError("平台新增候选改变了包格式")
    if baseline.is_zip and set(baseline.documents) != set(candidate.documents):
        raise ContractError("平台新增候选改变了元数据 XML 成员集合")
    if non_metadata_members(baseline) != non_metadata_members(candidate):
        raise ContractError("平台新增候选改变了非元数据成员")

    baseline_units = all_document_units(baseline)
    candidate_units = all_document_units(candidate)
    resolved = [validate_platform_added_node(knowledge, candidate_units, change) for change in contract["changes"]]
    issues = [issue for item in resolved for issue in item["issues"]]
    removals: dict[str, list[ET.Element]] = {}
    for item in resolved:
        target = item["target"]
        baseline_matches = [
            unit
            for unit in baseline_units
            if unit["kind"] == target.get("kind")
            and (not target.get("document") or unit["source"] == target["document"])
            and (not target.get("number") or unit_number(unit) == target["number"])
        ]
        existing = []
        for unit in baseline_matches:
            chain = knowledge.resolve_standard_chain(unit)
            existing.extend(matching_target_nodes(unit, target, [root for root, _ in chain]))
        if existing:
            issues.append(f"新增目标在基线中已存在: {target}")
        removals.setdefault(item["unit"]["source"], []).append(item["node"])

    for source, nodes in removals.items():
        document_root = next(item["unit"]["document_root"] for item in resolved if item["unit"]["source"] == source)
        parents = parent_map(document_root)
        for node in nodes:
            parent = parents.get(id(node))
            if parent is None:
                issues.append(f"新增节点没有可移除父节点: {source}")
                continue
            parent.remove(node)
    document_pairs = (
        [(source, source) for source in baseline.documents]
        if baseline.is_zip
        else [(next(iter(baseline.documents)), next(iter(candidate.documents)))]
    )
    for baseline_source, candidate_source in document_pairs:
        baseline_raw = baseline.documents[baseline_source]
        baseline_root = ET.fromstring(baseline_raw)
        candidate_root = next(
            unit["document_root"] for unit in candidate_units if unit["source"] == candidate_source
        )
        if structural_signature(baseline_root) != structural_signature(candidate_root):
            issues.append(f"移除批准新增节点后仍有其他结构差异: {candidate_source}")
    return resolved, issues


def write_file(path: Path, data: bytes, overwrite: bool) -> None:
    path = path.expanduser().resolve()
    if path.exists() and not overwrite:
        raise ContractError(f"输出已存在；使用 --overwrite 才能覆盖: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def rollback_bundle(baseline: Artifact, candidate: bytes, contract: dict[str, Any], applied: list[dict[str, Any]]) -> bytes:
    manifest = {
        "rollback_version": 1,
        "baseline_name": baseline.path.name,
        "baseline_sha256": sha256_bytes(baseline.raw),
        "candidate_sha256": sha256_bytes(candidate),
        "contract_sha256": sha256_bytes(canonical_json(contract).encode("utf-8")),
        "applied": applied,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        archive.writestr("baseline.bin", baseline.raw)
    return output.getvalue()


def inspect_command(args: argparse.Namespace) -> int:
    artifact = Artifact.load(Path(args.artifact))
    units = all_document_units(artifact)
    result = {
        "status": "valid",
        "artifact": str(artifact.path),
        "sha256": sha256_bytes(artifact.raw),
        "format": "zip" if artifact.is_zip else artifact.path.suffix.lower().lstrip("."),
        "documents": sorted(artifact.documents),
        "units": [
            {
                "document": unit["source"],
                "kind": unit["kind"],
                "number": unit_number(unit),
                "model_type": effective_unit_model_type(units, unit),
                "parent_id": metadata_value(unit["xml_root"], "ParentId") if unit["xml_root"] is not None else "",
                "inherit_path": metadata_value(unit["xml_root"], "InheritPath") if unit["xml_root"] is not None else "",
            }
            for unit in units
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def plan_command(args: argparse.Namespace) -> int:
    artifact = Artifact.load(Path(args.baseline))
    knowledge = Knowledge(Path(args.knowledge))
    contract = read_change_spec(Path(args.contract))
    _, public = resolve_contract(knowledge, artifact, contract)
    status = "ready" if all(item["status"] == "ready" for item in public) else "blocked"
    print(
        json.dumps(
            {
                "status": status,
                "environment": knowledge.environment,
                "baseline_sha256": sha256_bytes(artifact.raw),
                "changes": public,
                "meaning": "ready 表示可生成静态候选；不代表平台回导或运行验证通过",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status == "ready" else 1


def apply_command(args: argparse.Namespace) -> int:
    artifact = Artifact.load(Path(args.baseline))
    knowledge = Knowledge(Path(args.knowledge))
    contract = read_change_spec(Path(args.contract))
    resolved, public = resolve_contract(knowledge, artifact, contract)
    if not all(item["status"] == "ready" for item in resolved):
        print(json.dumps({"status": "blocked", "changes": public}, ensure_ascii=False, indent=2))
        return 1
    candidate, applied = apply_resolved(artifact, resolved)
    output = Path(args.output)
    rollback_path = Path(args.rollback_output) if args.rollback_output else Path(str(output) + ".rollback.zip")
    write_file(output, candidate, args.overwrite)
    write_file(rollback_path, rollback_bundle(artifact, candidate, contract, applied), args.overwrite)
    result = {
        "status": "static-candidate",
        "output": str(output.expanduser().resolve()),
        "candidate_sha256": sha256_bytes(candidate),
        "baseline_sha256": sha256_bytes(artifact.raw),
        "rollback": str(rollback_path.expanduser().resolve()),
        "changes": applied,
        "validation_level": "static",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def validate_command(args: argparse.Namespace) -> int:
    baseline = Artifact.load(Path(args.baseline))
    candidate = Artifact.load(Path(args.candidate))
    knowledge = Knowledge(Path(args.knowledge))
    contract = read_change_spec(Path(args.contract))
    resolved, public = resolve_contract(knowledge, baseline, contract)
    issues = []
    if not all(item["status"] == "ready" for item in resolved):
        issues.append("内部变更描述包含未就绪变更")
    else:
        expected, _ = apply_resolved(baseline, resolved)
        if expected != candidate.raw:
            issues.append("候选字节内容不是当前变更对基线的唯一确定结果")
    status = "structurally-ready" if not issues else "invalid"
    print(
        json.dumps(
            {
                "status": status,
                "baseline_sha256": sha256_bytes(baseline.raw),
                "candidate_sha256": sha256_bytes(candidate.raw),
                "changes": public,
                "issues": issues,
                "meaning": "structurally-ready 只证明知识库、内部变更描述和候选一致；不代表平台回导或运行通过",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not issues else 1


def verify_platform_candidate_command(args: argparse.Namespace) -> int:
    baseline = Artifact.load(Path(args.baseline))
    candidate = Artifact.load(Path(args.candidate))
    knowledge = Knowledge(Path(args.knowledge))
    contract = read_change_spec(Path(args.contract))
    resolved, issues = verify_platform_candidate(knowledge, baseline, candidate, contract)
    status = "platform-candidate-structurally-ready" if not issues else "invalid"
    print(
        json.dumps(
            {
                "status": status,
                "baseline_sha256": sha256_bytes(baseline.raw),
                "candidate_sha256": sha256_bytes(candidate.raw),
                "changes": [public_resolution(item) for item in resolved],
                "issues": issues,
                "meaning": "只证明平台导出候选恰好新增批准节点且符合生产实际合同；仍需回导、再导出和运行验证",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not issues else 1


def rollback_command(args: argparse.Namespace) -> int:
    candidate = Path(args.candidate).expanduser().resolve().read_bytes()
    bundle_path = Path(args.rollback_bundle).expanduser().resolve()
    try:
        with zipfile.ZipFile(bundle_path, "r") as archive:
            manifest = json.loads(archive.read("manifest.json"))
            baseline = archive.read("baseline.bin")
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        raise ContractError(f"回滚包无效: {exc}") from exc
    if sha256_bytes(candidate) != manifest.get("candidate_sha256"):
        raise ContractError("当前候选哈希与回滚包不匹配")
    if sha256_bytes(baseline) != manifest.get("baseline_sha256"):
        raise ContractError("回滚包内基线哈希不匹配")
    output = Path(args.output)
    write_file(output, baseline, args.overwrite)
    print(
        json.dumps(
            {
                "status": "restored",
                "output": str(output.expanduser().resolve()),
                "sha256": sha256_bytes(baseline),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="金蝶云苍穹元数据新增修改引擎")
    sub = root.add_subparsers(dest="command", required=True)

    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("artifact")
    inspect_parser.set_defaults(func=inspect_command)

    for name, func in (("plan", plan_command), ("validate", validate_command)):
        command = sub.add_parser(name)
        command.add_argument("knowledge")
        command.add_argument("baseline")
        if name == "validate":
            command.add_argument("candidate")
        command.add_argument("--contract", required=True)
        command.set_defaults(func=func)

    platform_candidate_parser = sub.add_parser("verify-platform-candidate")
    platform_candidate_parser.add_argument("knowledge")
    platform_candidate_parser.add_argument("baseline")
    platform_candidate_parser.add_argument("candidate")
    platform_candidate_parser.add_argument("--contract", required=True)
    platform_candidate_parser.set_defaults(func=verify_platform_candidate_command)

    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("knowledge")
    apply_parser.add_argument("baseline")
    apply_parser.add_argument("--contract", required=True)
    apply_parser.add_argument("--output", required=True)
    apply_parser.add_argument("--rollback-output")
    apply_parser.add_argument("--overwrite", action="store_true")
    apply_parser.set_defaults(func=apply_command)

    rollback_parser = sub.add_parser("rollback")
    rollback_parser.add_argument("candidate")
    rollback_parser.add_argument("rollback_bundle")
    rollback_parser.add_argument("--output", required=True)
    rollback_parser.add_argument("--overwrite", action="store_true")
    rollback_parser.set_defaults(func=rollback_command)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.func(args)
    except (ContractError, ET.ParseError, OSError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("[ERROR] 已中断", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
