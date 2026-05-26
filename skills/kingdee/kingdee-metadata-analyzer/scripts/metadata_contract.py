#!/usr/bin/env python3
"""Build a compact metadata contract from analyzer outputs."""

from __future__ import annotations

import argparse
import json
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def page_type(form_page: str, page_element: str, plugin_type: str) -> str:
    text = f"{form_page} {page_element} {plugin_type}".lower()
    if "operation" in text or "操作" in text:
        return "operation"
    if "mobilelist" in text or "mobile-list" in text or "移动列表" in text:
        return "mobile-list"
    if "mobilebill" in text or "mobile-bill" in text or "移动" in text:
        return "mobile-bill"
    if "entry" in text or "分录" in text:
        return "entry"
    if form_page:
        return "pc-form"
    return "unknown"


def source_label(item: Dict[str, Any]) -> str:
    raw = str(item.get("sourceType") or item.get("source") or "metadata").lower()
    if "source" in raw or raw in {"java", "local"}:
        return "source"
    if "jar" in raw or "decompile" in raw:
        return "jar"
    return "metadata"


def plugin_form_id(item: Dict[str, Any]) -> str:
    if item.get("formPage"):
        return str(item["formPage"])
    if item.get("operation"):
        return f"operation:{item['operation']}"
    return "entity"


def build_forms(inventory: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not inventory:
        return []

    grouped: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for item in inventory.get("plugins", []):
        if not isinstance(item, dict):
            continue
        class_name = str(item.get("className") or "").strip()
        if not class_name:
            continue
        form_id = plugin_form_id(item)
        page_element = str(item.get("pageElement") or item.get("operation") or item.get("type") or "form")
        plugin_type = str(item.get("type") or "")
        form = grouped.setdefault(
            form_id,
            {
                "formId": form_id,
                "pageType": page_type(form_id, page_element, plugin_type),
                "plugins": [],
            },
        )
        form["plugins"].append(
            {
                "className": class_name,
                "pageElement": page_element,
                "formPage": str(item.get("formPage") or item.get("operation") or ""),
                "source": source_label(item),
            }
        )
    return list(grouped.values())


def normalize_fields(raw_fields: Iterable[Any], evidence: str) -> List[Dict[str, Any]]:
    fields: List[Dict[str, Any]] = []
    for raw in raw_fields:
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("fieldKey") or raw.get("key") or "").strip()
        if not key:
            continue
        field_type = raw.get("fieldType") or raw.get("type") or raw.get("tag")
        fields.append(
            {
                "fieldKey": key,
                "name": raw.get("name") or "",
                "fieldType": field_type or "",
                "entryKey": raw.get("entryKey"),
                "physicalColumn": raw.get("physicalColumn"),
                "evidence": sorted(set(raw.get("evidence") or [evidence])),
            }
        )
    return fields


def entity_number_from(inventory: Optional[Dict[str, Any]], quick_cache: Optional[Dict[str, Any]], explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    if inventory:
        entity = inventory.get("entity") or {}
        if isinstance(entity, dict):
            value = entity.get("fnumber") or entity.get("entityNumber")
            if value:
                return str(value)
    if quick_cache:
        value = quick_cache.get("entityNumber") or quick_cache.get("entity")
        if value:
            return str(value)
    return "unknown"


def build_contract(args: argparse.Namespace) -> Dict[str, Any]:
    inventory = load_json(Path(args.inventory)) if args.inventory else None
    quick_cache = load_json(Path(args.quick_cache)) if args.quick_cache else None
    warnings: List[str] = []

    fields: List[Dict[str, Any]] = []
    if quick_cache:
        fields.extend(normalize_fields(quick_cache.get("fields", []), "cache"))
    if inventory and inventory.get("fields"):
        fields.extend(normalize_fields(inventory.get("fields", []), "entitydesign"))
    if not fields:
        warnings.append("fields_not_available")
    if inventory and not inventory.get("plugins"):
        warnings.append("plugins_not_available")

    return {
        "entityNumber": entity_number_from(inventory, quick_cache, args.entity_number),
        "environment": args.environment,
        "forms": build_forms(inventory),
        "fields": fields,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build machine-readable Kingdee metadata contract JSON.")
    parser.add_argument("--inventory", help="Path to cosmic-metadata-analyzer inventory.json")
    parser.add_argument("--quick-cache", help="Path to quick-query cache JSON containing fields")
    parser.add_argument("--entity-number", help="Entity number override")
    parser.add_argument("--environment", default="dev", choices=["dev", "prod", "test", "unknown"], help="Source environment")
    parser.add_argument("--output", help="Write contract JSON to this path instead of stdout")
    args = parser.parse_args()

    if not args.inventory and not args.quick_cache:
        parser.error("at least one of --inventory or --quick-cache is required")

    contract = build_contract(args)
    payload = json.dumps(contract, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
