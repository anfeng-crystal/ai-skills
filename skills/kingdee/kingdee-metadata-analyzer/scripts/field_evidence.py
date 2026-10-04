"""Read design-layer field candidates without pretending to merge metadata."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

ZH_LOCALE = "zh_CN"
MAX_ANCESTORS = 32

FIELD_TAGS = {
    'Field', 'Column', 'VarField', 'PKField',
    'BillNoField', 'BillStatusField', 'CreatorField',
    'ModifierField', 'AuditField', 'CreateTimeField',
    'ModifyTimeField', 'AuditTimeField', 'MasterIdField',
    'BasedataField', 'MulBasedataField', 'AmountField',
    'TextField', 'IntegerField', 'LongField', 'DecimalField',
    'DateField', 'DateTimeField', 'TimeField', 'BooleanField',
    'LargeTextField', 'FlexField', 'UserField', 'OrgField',
    'CurrencyField', 'ExchangeRateField', 'GroupField',
    'SubEntryField', 'RelatedFlexField', 'ItemClassField',
    'ComboField',
}

BASEDATA_FIELD_SUFFIXES = (
    'BasedataField',
    'PersonField',
    'UserField',
    'OrgField',
    'CustomerField',
    'SupplierField',
    'MaterielField',
    'AssistantField',
    'UnitField',
    'CurrencyField',
    'AdminDivisionField',
    'CityField',
    'CostCenterField',
    'AccountField',
)

def is_field_tag(tag: str) -> bool:
    """按苍穹字段控件命名识别字段，未知 *Field 也作为字段候选。"""
    return tag in FIELD_TAGS or tag.endswith('Field')

def is_basedata_field_tag(tag: str) -> bool:
    """识别基础资料类字段及其平台派生字段。"""
    return tag in ('BasedataField', 'MulBasedataField') or tag.endswith(BASEDATA_FIELD_SUFFIXES)

def extract_fields(root, entry_tag: Optional[str] = None) -> List[Dict[str, Any]]:
    """从实体 XML 提取字段列表

    Args:
        root: XML 根节点
        entry_tag: 如果指定，只提取该分录下的字段；None 则提取所有

    Returns:
        list of dict: 字段列表
    """
    fields = []
    if root is None:
        return fields

    search_root = root
    if entry_tag:
        # 查找指定分录节点
        for node in root.iter():
            key = node.findtext('Key', '').strip()
            if key == entry_tag:
                search_root = node
                break

    for node in search_root.iter():
        tag = node.tag
        if not is_field_tag(tag):
            continue

        key = node.findtext('Key', '').strip()
        if not key:
            key = node.get('key', '').strip()
        if not key:
            continue

        # 获取中文名
        name = ''
        name_node = node.find('Name')
        if name_node is not None:
            # 多语言：尝试找 zh_CN
            loc = name_node.find(f".//{ZH_LOCALE}")
            if loc is not None:
                name = (loc.text or '').strip()
            if not name:
                name = (name_node.text or '').strip()
        if not name:
            name = node.findtext('Name', '').strip()

        field_type = tag  # 标签名即类型
        ref_entity = ''
        # 基础资料类型提取关联实体
        if is_basedata_field_tag(tag):
            ref_entity = node.findtext('RefEntityNumber', '').strip()
            if not ref_entity:
                ref_entity = node.findtext('LookUpObject', '').strip()
            if not ref_entity:
                ref_entity = node.findtext('BaseEntityId', '').strip()

        is_basedata = is_basedata_field_tag(tag)

        fields.append({
            "fieldKey": key,
            "name": name,
            "type": field_type,
            "refEntity": ref_entity,
            "isBasedata": is_basedata,
        })
        for attribute in ("action", "oid"):
            if node.get(attribute):
                fields[-1][attribute] = node.get(attribute)

    return fields


def parent_reference(root):
    """Recognize the same parent references supported by quick-query's DB reader."""
    if root is None:
        return None
    for name in ("BaseEntityNumber", "ParentEntityNumber", "InheritEntityNumber"):
        value = root.findtext(name, "").strip()
        if value:
            return value
    return (root.get("baseEntityNumber", "").strip()
            or root.findtext("ParentId", "").strip()
            or root.get("ParentId", "").strip() or None)


def collect_field_evidence(row, inherit, query_parent, parse_xml):
    """Collect bounded design layers and report every unresolved boundary.

    `chainComplete` covers traversal of declared XML parents only. This reader
    does not apply action/oid patches or discover external extension layers.
    The caller owns DB resources; query exceptions remain visible to it.
    """
    fields, warnings, sources, deltas = [], [], [], []
    status = {
        "scope": "design-layer-candidates",
        "inheritanceRequested": bool(inherit),
        "chainComplete": True,
        "effectiveFieldsResolved": False,
        "sources": sources,
        "unresolvedDeltas": deltas,
    }

    def warn(code, broken_chain=False):
        if code not in warnings:
            warnings.append(code)
        if broken_chain:
            status["chainComplete"] = False

    seen_ids, seen_numbers = set(), set()
    current = row
    depth = 0
    while current is not None:
        fid, number, data, _ = current
        identity = str(fid) if fid is not None else ""
        if (identity and identity in seen_ids) or number in seen_numbers:
            warn("inheritance_cycle", True)
            break
        if identity:
            seen_ids.add(identity)
        seen_numbers.add(number)
        root = parse_xml(data)
        source = {"entityNumber": number, "depth": depth, "fieldCount": 0,
                  "xmlReadable": root is not None,
                  "xmlSha256": hashlib.sha256(str(data).encode("utf-8")).hexdigest()}
        sources.append(source)
        if root is None:
            warn("entity_xml_unreadable", True)
            break

        candidates = extract_fields(root)
        source["fieldCount"] = len(candidates)
        for field in candidates:
            field["sourceEntity"] = number
            field["sourceDepth"] = depth
            if depth:
                field["inherited_from"] = number
        fields.extend(candidates)
        for node in root.iter():
            action, oid = node.get("action"), node.get("oid")
            key = node.findtext("Key", "").strip() or node.get("key", "").strip()
            if action or oid:
                deltas.append({"nodeTag": node.tag, "action": action, "oid": oid,
                               "fieldKey": key or None, "sourceEntity": number,
                               "sourceDepth": depth})
                warn("inheritance_delta_unresolved")
        parent = parent_reference(root)
        source["hasParentReference"] = bool(parent)
        if not parent:
            if root.findtext("InheritPath", "").strip() or root.get("InheritPath", "").strip():
                warn("ancestor_reference_unresolved", True)
            elif root.get("action") or root.get("oid"):
                warn("ancestor_reference_unresolved", True)
            break
        if not inherit:
            warn("ancestors_not_requested", True)
            break
        if depth >= MAX_ANCESTORS:
            warn("inheritance_depth_limit", True)
            break
        current = query_parent(root)
        if current is None:
            warn("ancestor_not_found", True)
            break
        depth += 1

    if len(sources) > 1:
        warn("design_layers_not_merged")
    return {"fields": fields, "warnings": warnings, "fieldEvidence": status}
