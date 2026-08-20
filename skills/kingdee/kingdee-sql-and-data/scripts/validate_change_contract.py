#!/usr/bin/env python3
"""Validate a reviewable database change contract without connecting to a database."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path.name}: {exc}") from exc


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def evidence_ref(value: Any) -> bool:
    if not nonempty(value):
        return False
    return value.strip().lower() not in {"unknown", "tbd", "todo", "n/a", "none", "待确认", "未知"}


def validate(contract: Any) -> dict[str, Any]:
    if not isinstance(contract, dict) or contract.get("version") != 1:
        raise ValueError("contract must be an object with version=1")
    errors: list[dict[str, str]] = []

    mode = contract.get("mode")
    if mode not in {"plan-only", "execute-approved"}:
        raise ValueError("mode must be plan-only or execute-approved")
    if mode == "execute-approved" and not nonempty(contract.get("approval_ref")):
        errors.append({"field": "approval_ref", "code": "missing_approval"})
    change_kind = contract.get("change_kind", "direct")
    if change_kind not in {"direct", "relationship-remap", "entity-migration", "symptom-repair"}:
        raise ValueError("change_kind must be direct, relationship-remap, entity-migration, or symptom-repair")
    if not nonempty(contract.get("environment")):
        errors.append({"field": "environment", "code": "missing_target"})

    target = contract.get("target")
    if not isinstance(target, dict):
        raise ValueError("target must be an object")
    for key in ("database", "schema", "table"):
        if not nonempty(target.get(key)):
            errors.append({"field": f"target.{key}", "code": "missing_target"})
    if not isinstance(target.get("key_columns"), list) or not target["key_columns"]:
        errors.append({"field": "target.key_columns", "code": "missing_key"})

    scope = contract.get("scope")
    if not isinstance(scope, dict):
        raise ValueError("scope must be an object")
    if not nonempty(scope.get("where_sql")):
        errors.append({"field": "scope.where_sql", "code": "unbounded_scope"})
    expected = scope.get("expected_rows")
    maximum = scope.get("max_rows")
    if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
        errors.append({"field": "scope.expected_rows", "code": "invalid_count"})
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 0:
        errors.append({"field": "scope.max_rows", "code": "invalid_count"})
    if isinstance(expected, int) and isinstance(maximum, int) and expected > maximum:
        errors.append({"field": "scope.expected_rows", "code": "exceeds_max_rows"})

    stage = contract.get("stage")
    if not isinstance(stage, dict) or stage.get("enabled") is not True:
        errors.append({"field": "stage.enabled", "code": "stage_required"})
    else:
        if not isinstance(stage.get("unique_key"), list) or not stage["unique_key"]:
            errors.append({"field": "stage.unique_key", "code": "missing_unique_key"})
        if stage.get("rejects_unmapped") is not True:
            errors.append({"field": "stage.rejects_unmapped", "code": "unmapped_not_rejected"})

    assignments = contract.get("assignments")
    if not isinstance(assignments, list) or not assignments:
        errors.append({"field": "assignments", "code": "missing_assignments"})
    else:
        for index, assignment in enumerate(assignments):
            field = f"assignments[{index}]"
            if not isinstance(assignment, dict) or not nonempty(assignment.get("column")):
                errors.append({"field": field, "code": "invalid_assignment"})
                continue
            policy = assignment.get("mapping_missing")
            if policy not in {"preserve_old", "stop", "set_null"}:
                errors.append({"field": field, "code": "invalid_missing_mapping_policy"})
            if assignment.get("nullable") is False and policy == "set_null":
                errors.append({"field": field, "code": "not_null_assignment_can_be_null"})

    boolean_gates = (
        ("transaction", contract.get("transaction") is True, "transaction_required"),
        ("before_image.enabled", nested_true(contract, "before_image", "enabled"), "before_image_required"),
        ("concurrency.compare_old_values", nested_true(contract, "concurrency", "compare_old_values"), "old_value_guard_required"),
        ("rollback.compare_before_restore", nested_true(contract, "rollback", "compare_before_restore"), "safe_rollback_required"),
        ("verification.exact_affected_rows", nested_true(contract, "verification", "exact_affected_rows"), "exact_count_required"),
        ("verification.postcheck", nested_true(contract, "verification", "postcheck"), "postcheck_required"),
        ("failure_recovery.rollback", nested_true(contract, "failure_recovery", "rollback"), "failure_rollback_required"),
        ("failure_recovery.recompute_scope", nested_true(contract, "failure_recovery", "recompute_scope"), "recompute_required"),
    )
    for field, passed, code in boolean_gates:
        if not passed:
            errors.append({"field": field, "code": code})

    if change_kind == "relationship-remap":
        relationship = contract.get("relationship")
        if not isinstance(relationship, dict):
            errors.append({"field": "relationship", "code": "relationship_evidence_required"})
        else:
            for field, code in (
                ("authoritative_key_proven", "authoritative_relationship_required"),
                ("target_id_set_equal", "target_set_assertion_required"),
            ):
                if relationship.get(field) is not True:
                    errors.append({"field": f"relationship.{field}", "code": code})
            if relationship.get("uses_rebuilt_target_as_only_key") is not False:
                errors.append({"field": "relationship.uses_rebuilt_target_as_only_key", "code": "circular_relationship_key"})
            for field in ("source_count", "unique_target_count", "conflict_count", "unmapped_count"):
                value = relationship.get(field)
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    errors.append({"field": f"relationship.{field}", "code": "missing_relationship_metric"})

    if change_kind == "entity-migration":
        topology = contract.get("storage_topology")
        if not isinstance(topology, dict):
            errors.append({"field": "storage_topology", "code": "storage_topology_required"})
        else:
            if topology.get("enumerated") is not True:
                errors.append({"field": "storage_topology.enumerated", "code": "storage_topology_incomplete"})
            classes = topology.get("classes")
            all_tables: list[str] = []
            if not isinstance(classes, dict):
                errors.append({"field": "storage_topology.classes", "code": "table_classes_required"})
            else:
                for class_name in ("main", "multilingual", "entries", "relations"):
                    field = f"storage_topology.classes.{class_name}"
                    item = classes.get(class_name)
                    if not isinstance(item, dict):
                        errors.append({"field": field, "code": "table_class_not_enumerated"})
                        continue
                    status = item.get("status")
                    tables = item.get("tables")
                    if status not in {"present", "confirmed_absent"}:
                        errors.append({"field": f"{field}.status", "code": "invalid_table_class_status"})
                    if not isinstance(tables, list) or any(not nonempty(table) for table in tables):
                        errors.append({"field": f"{field}.tables", "code": "invalid_table_list"})
                        tables = []
                    if status == "present" and not tables:
                        errors.append({"field": f"{field}.tables", "code": "present_table_class_empty"})
                    if status == "confirmed_absent" and tables:
                        errors.append({"field": f"{field}.tables", "code": "absent_table_class_has_tables"})
                    if class_name == "main" and status != "present":
                        errors.append({"field": f"{field}.status", "code": "main_table_required"})
                    if not evidence_ref(item.get("evidence_ref")):
                        errors.append({"field": f"{field}.evidence_ref", "code": "table_class_evidence_required"})
                    all_tables.extend(tables)
                if len(all_tables) != len(set(all_tables)):
                    errors.append({"field": "storage_topology.classes", "code": "duplicate_table_in_topology"})

            if not evidence_ref(topology.get("reference_strategy")):
                errors.append({"field": "storage_topology.reference_strategy", "code": "reference_strategy_required"})
            import_order = topology.get("import_order")
            if not isinstance(import_order, list) or not import_order or any(not nonempty(table) for table in import_order):
                errors.append({"field": "storage_topology.import_order", "code": "import_order_required"})
            elif set(import_order) != set(all_tables) or len(import_order) != len(all_tables):
                errors.append({"field": "storage_topology.import_order", "code": "import_order_mismatch"})
            for evidence_name in ("parent_keys", "id_mapping", "row_count_checks"):
                evidence = topology.get(evidence_name)
                if not isinstance(evidence, dict) or set(evidence) != set(all_tables):
                    errors.append({"field": f"storage_topology.{evidence_name}", "code": "per_table_evidence_incomplete"})
                    continue
                for table, value in evidence.items():
                    if evidence_name == "row_count_checks":
                        if not isinstance(value, dict) or not evidence_ref(value.get("before")) or not evidence_ref(value.get("after")):
                            errors.append({"field": f"storage_topology.{evidence_name}.{table}", "code": "row_count_check_incomplete"})
                    elif not evidence_ref(value):
                        errors.append({"field": f"storage_topology.{evidence_name}.{table}", "code": "per_table_evidence_incomplete"})
            if topology.get("orphan_check") is not True:
                errors.append({"field": "storage_topology.orphan_check", "code": "orphan_check_required"})

    if change_kind == "symptom-repair":
        causal = contract.get("causal_target")
        if not isinstance(causal, dict):
            errors.append({"field": "causal_target", "code": "causal_target_required"})
        else:
            for field in ("normal_sample", "abnormal_sample", "read_path", "business_postcondition"):
                if not nonempty(causal.get(field)):
                    errors.append({"field": f"causal_target.{field}", "code": "causal_evidence_missing"})
            for field in ("set_columns_causal", "active_process_checked"):
                if causal.get(field) is not True:
                    errors.append({"field": f"causal_target.{field}", "code": "causal_gate_missing"})

    return {"status": "pass" if not errors else "fail", "error_count": len(errors), "errors": errors}


def nested_true(root: dict[str, Any], parent: str, child: str) -> bool:
    value = root.get(parent)
    return isinstance(value, dict) and value.get(child) is True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = validate(load_json(args.contract))
    except ValueError as exc:
        print(json.dumps({"status": "invalid_input", "message": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
