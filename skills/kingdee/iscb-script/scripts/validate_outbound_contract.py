#!/usr/bin/env python3
"""Validate an outbound JSON payload against a field and provenance contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


JSON_TYPES = {"string", "number", "integer", "boolean", "object", "array", "null"}
REAL_KINDS = {"production_record", "production_master_data"}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path.name}: {exc}") from exc


def matches_json_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return value is None


def validate(
    contract: Any,
    payload: Any,
    provenance: Any | None,
    require_real_provenance: bool,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if not isinstance(contract, dict) or contract.get("version") != 1:
        raise ValueError("contract must be an object with version=1")
    fields = contract.get("fields")
    if not isinstance(fields, dict) or not fields:
        raise ValueError("contract.fields must be a non-empty object")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")

    provenance_fields: dict[str, Any] = {}
    if provenance is not None:
        if not isinstance(provenance, dict) or not isinstance(provenance.get("fields"), dict):
            raise ValueError("provenance.fields must be an object")
        provenance_fields = provenance["fields"]
    elif require_real_provenance:
        raise ValueError("--require-real-provenance requires --provenance")

    for field_name, raw_rule in fields.items():
        if not isinstance(raw_rule, dict):
            raise ValueError(f"contract field {field_name!r} must be an object")
        expected_type = raw_rule.get("json_type")
        if expected_type not in JSON_TYPES:
            raise ValueError(f"contract field {field_name!r} has unsupported json_type")
        if raw_rule.get("required", False) and field_name not in payload:
            errors.append({"field": field_name, "code": "missing_required"})
            continue
        if field_name not in payload:
            continue
        if not matches_json_type(payload[field_name], expected_type):
            errors.append({"field": field_name, "code": "json_type_mismatch"})

        evidence = provenance_fields.get(field_name)
        if require_real_provenance:
            if not isinstance(evidence, dict):
                errors.append({"field": field_name, "code": "missing_provenance"})
                continue
            source_policy = raw_rule.get("source_policy", "real")
            kind = evidence.get("kind")
            if source_policy == "real" and kind not in REAL_KINDS:
                errors.append({"field": field_name, "code": "non_real_provenance"})
            elif source_policy == "constant" and kind != "verified_constant":
                errors.append({"field": field_name, "code": "unverified_constant"})
            elif source_policy not in {"real", "constant"}:
                raise ValueError(f"contract field {field_name!r} has unsupported source_policy")
            if not isinstance(evidence.get("source"), str) or not evidence["source"].strip():
                errors.append({"field": field_name, "code": "missing_source_evidence"})

        expected_semantic = raw_rule.get("semantic_type")
        if expected_semantic is not None:
            if not isinstance(evidence, dict) or evidence.get("semantic_type") != expected_semantic:
                errors.append({"field": field_name, "code": "semantic_type_mismatch"})

    if not contract.get("allow_extra", False):
        for field_name in sorted(set(payload) - set(fields)):
            errors.append({"field": field_name, "code": "unexpected_field"})

    return {
        "status": "pass" if not errors else "fail",
        "checked_fields": len(payload),
        "error_count": len(errors),
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--provenance", type=Path)
    parser.add_argument("--require-real-provenance", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = validate(
            load_json(args.contract),
            load_json(args.payload),
            load_json(args.provenance) if args.provenance else None,
            args.require_real_provenance,
        )
    except ValueError as exc:
        print(json.dumps({"status": "invalid_input", "message": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
