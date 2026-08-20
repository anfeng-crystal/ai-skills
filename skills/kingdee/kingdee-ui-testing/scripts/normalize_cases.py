#!/usr/bin/env python3
"""Normalize credential-free UI test cases from JSON or CSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


MODES = {"generate", "safe-smoke", "approved-crud", "prod-safe-smoke", "approved-prod-e2e"}
READ_ONLY_ACTIONS = {
    "navigate",
    "inspect",
    "assert",
    "screenshot",
    "wait",
    "search",
    "open",
    "close",
    "paginate",
    "switch-tab",
}
WRITE_ACTIONS = {
    "input",
    "select",
    "upload",
    "save",
    "create",
    "update",
    "delete",
    "submit",
    "audit",
    "unaudit",
    "enable",
    "disable",
    "workflow",
    "cleanup",
    "rollback",
}
ALL_ACTIONS = READ_ONLY_ACTIONS | WRITE_ACTIONS | {"click"}
READ_ONLY_EFFECTS = {"navigation", "open", "close", "paginate", "switch-tab", "inspect"}
FORBIDDEN_KEY_PARTS = {
    "password",
    "passwd",
    "secret",
    "token",
    "cookie",
    "authorization",
    "csrf",
    "session",
    "storage_state",
    "storageState",
}
FORBIDDEN_VALUE = re.compile(
    r"(?i)[\"']?(password|passwd|secret|token|cookie|authorization|csrf|session|storage_state)[\"']?\s*[:=]"
)


def find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if any(re.sub(r"[^a-z0-9]", "", part.lower()) in normalized for part in FORBIDDEN_KEY_PARTS):
                hits.append(f"{path}.{key}")
            hits.extend(find_forbidden_keys(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(find_forbidden_keys(item, f"{path}[{index}]"))
    elif isinstance(value, str) and FORBIDDEN_VALUE.search(value):
        hits.append(path)
    return hits


def as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split("|") if item.strip()]


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return False
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"invalid boolean value: {value}")


def parse_data(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return None
    if stripped[:1] in {"{", "["}:
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    return stripped


def normalize_step(raw: dict[str, Any], index: int, mode: str) -> dict[str, Any]:
    action = str(raw.get("action") or "").strip().lower().replace("_", "-")
    if action not in ALL_ACTIONS:
        raise ValueError(f"step {index}: unsupported action {action!r}")
    effect = str(raw.get("effect") or "").strip().lower().replace("_", "-")
    explicit_mutates = as_bool(raw.get("mutates"))
    mutates = explicit_mutates or action in WRITE_ACTIONS
    if action == "click":
        if not effect:
            raise ValueError(f"step {index}: click requires an explicit effect")
        mutates = mutates or effect not in READ_ONLY_EFFECTS
    if mode in {"safe-smoke", "prod-safe-smoke"} and mutates:
        raise ValueError(f"step {index}: {mode} forbids mutating action {action}")
    target = str(raw.get("target") or "").strip()
    if "://" in target:
        raise ValueError(f"step {index}: target must be a logical page/control reference, not a URL")
    return {
        "stepId": str(raw.get("stepId") or raw.get("step_id") or f"step-{index}").strip(),
        "order": int(raw.get("order") or raw.get("step_order") or index),
        "action": action,
        "target": target,
        "data": parse_data(raw.get("data", raw.get("value"))),
        "expected": str(raw.get("expected") or "").strip(),
        "mutates": mutates,
        "effect": effect,
    }


def normalize_case(raw: dict[str, Any], index: int, mode: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"case {index}: case must be an object")
    case_id = str(raw.get("caseId") or raw.get("case_id") or raw.get("id") or "").strip()
    if not case_id:
        raise ValueError(f"case {index}: caseId is required")
    steps_raw = raw.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        raise ValueError(f"case {case_id}: at least one step is required")
    if any(not isinstance(step, dict) for step in steps_raw):
        raise ValueError(f"case {case_id}: every step must be an object")
    steps = [normalize_step(step, step_index, mode) for step_index, step in enumerate(steps_raw, start=1)]
    step_ids = [step["stepId"] for step in steps]
    if len(step_ids) != len(set(step_ids)):
        raise ValueError(f"case {case_id}: duplicate stepId")
    orders = [step["order"] for step in steps]
    if len(orders) != len(set(orders)):
        raise ValueError(f"case {case_id}: duplicate step order")
    steps.sort(key=lambda step: step["order"])
    priority = str(raw.get("priority") or "P2").upper()
    if priority not in {"P0", "P1", "P2", "P3"}:
        raise ValueError(f"case {case_id}: invalid priority {priority}")
    return {
        "caseId": case_id,
        "name": str(raw.get("name") or raw.get("caseName") or raw.get("case_name") or case_id).strip(),
        "priority": priority,
        "requirements": as_list(raw.get("requirements")),
        "preconditions": as_list(raw.get("preconditions")),
        "steps": steps,
    }


def cases_from_json(path: Path) -> list[dict[str, Any]]:
    root = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(root, list):
        return root
    if isinstance(root, dict) and isinstance(root.get("cases"), list):
        return root["cases"]
    if isinstance(root, dict):
        return [root]
    raise ValueError("JSON root must be a case object, case array, or object with cases")


def cases_from_csv(path: Path) -> list[dict[str, Any]]:
    grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            case_id = str(row.get("case_id") or "").strip()
            if not case_id:
                raise ValueError(f"CSV row {row_number}: case_id is required")
            case = grouped.setdefault(
                case_id,
                {
                    "caseId": case_id,
                    "name": row.get("case_name") or case_id,
                    "priority": row.get("priority") or "P2",
                    "requirements": as_list(row.get("requirements")),
                    "preconditions": as_list(row.get("preconditions")),
                    "steps": [],
                },
            )
            case["steps"].append(
                {
                    "step_id": row.get("step_id"),
                    "step_order": row.get("step_order"),
                    "action": row.get("action"),
                    "target": row.get("target"),
                    "data": row.get("data"),
                    "expected": row.get("expected"),
                    "mutates": row.get("mutates"),
                    "effect": row.get("effect"),
                }
            )
    return list(grouped.values())


def normalize(raw_cases: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    forbidden = find_forbidden_keys(raw_cases)
    if forbidden:
        raise ValueError("credential/session fields are forbidden: " + ", ".join(forbidden))
    cases = [normalize_case(case, index, mode) for index, case in enumerate(raw_cases, start=1)]
    if not cases:
        raise ValueError("at least one case is required")
    case_ids = [case["caseId"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("duplicate caseId")
    return {"schemaVersion": "1.0", "mode": mode, "cases": cases}


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize Kingdee UI test cases from JSON or CSV.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--mode", required=True, choices=sorted(MODES))
    parser.add_argument("--output")
    parser.add_argument("--force", action="store_true", help="Overwrite only the explicit output file.")
    args = parser.parse_args()
    input_path = Path(args.input).expanduser().resolve()
    try:
        raw_cases = cases_from_csv(input_path) if input_path.suffix.lower() == ".csv" else cases_from_json(input_path)
        result = normalize(raw_cases, args.mode)
    except (OSError, UnicodeError, csv.Error, json.JSONDecodeError, ValueError) as exc:
        print(f"cannot normalize cases: {exc}", file=sys.stderr)
        return 2
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output).expanduser().resolve()
        if output == input_path:
            print("output must not overwrite input", file=sys.stderr)
            return 2
        if output.exists() and not args.force:
            print("output exists; pass --force only when overwrite is explicitly requested", file=sys.stderr)
            return 2
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
