#!/usr/bin/env python3
"""Validate a credential-free UI execution contract without browser access."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
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
READ_ONLY_CLICK_EFFECTS = {"navigation", "open", "close", "paginate", "switch-tab", "inspect"}
FORBIDDEN_KEY = re.compile(
    r"(?i)(password|passwd|secret|token|cookie|authorization|csrf|session|storage.?state|request.?header)"
)
FORBIDDEN_VALUE = re.compile(
    r"(?i)[\"']?(password|passwd|secret|token|cookie|authorization|csrf|session|storage_state)[\"']?\s*[:=]"
)
PREFIX = re.compile(r"^[A-Za-z0-9_-]{6,40}$")


def credential_hits(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if FORBIDDEN_KEY.search(str(key)):
                hits.append(f"{path}.{key}")
            hits.extend(credential_hits(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(credential_hits(item, f"{path}[{index}]"))
    elif isinstance(value, str) and FORBIDDEN_VALUE.search(value):
        hits.append(path)
    return hits


def require_steps(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, dict) or not str(value.get("strategy") or "").strip():
        errors.append(f"{label} requires a strategy")
        return
    if not isinstance(value.get("steps"), list) or not value["steps"]:
        errors.append(f"{label} requires non-empty steps")


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    hits = credential_hits(contract)
    if hits:
        errors.append("credential/session material is forbidden: " + ", ".join(hits))
    mode = contract.get("mode")
    environment = contract.get("environmentClass")
    task_id = str(contract.get("taskId") or "").strip()
    target_ref = str(contract.get("targetRef") or "").strip()
    case_ids = contract.get("caseIds")
    actions = contract.get("allowedActions")
    max_cases = contract.get("maxCases")
    max_writes = contract.get("maxWrites")

    if mode not in MODES:
        errors.append("unsupported mode")
    if not task_id:
        errors.append("taskId is required")
    expected_environments = {
        "generate": {"none"},
        "safe-smoke": {"local", "dev-test"},
        "approved-crud": {"local", "dev-test"},
        "prod-safe-smoke": {"prod"},
        "approved-prod-e2e": {"prod"},
    }
    if mode in expected_environments and environment not in expected_environments[mode]:
        errors.append(f"environmentClass {environment!r} is invalid for {mode}")
    if mode != "generate" and (not target_ref or "://" in target_ref):
        errors.append("execution modes require a configured non-URL targetRef")
    if mode == "generate" and target_ref:
        errors.append("generate mode must not bind a runtime target")
    if not isinstance(case_ids, list) or not case_ids or any(not str(item).strip() for item in case_ids):
        errors.append("caseIds must be a non-empty list")
    elif len(case_ids) != len(set(str(item) for item in case_ids)):
        errors.append("caseIds must be unique")
    if not isinstance(max_cases, int) or isinstance(max_cases, bool) or max_cases < 1:
        errors.append("maxCases must be a positive integer")
    elif isinstance(case_ids, list) and len(case_ids) > max_cases:
        errors.append("caseIds exceed maxCases")
    if not isinstance(actions, list) or any(action not in ALL_ACTIONS for action in actions):
        errors.append("allowedActions must contain only known actions")
        action_set: set[str] = set()
    else:
        action_set = set(actions)
    if mode in {"generate", "safe-smoke", "prod-safe-smoke"}:
        if action_set - (READ_ONLY_ACTIONS | {"click"}):
            errors.append(f"{mode} contains write-capable or ambiguous actions")
        if "click" in action_set:
            click_effects = contract.get("allowedClickEffects")
            if (
                not isinstance(click_effects, list)
                or not click_effects
                or any(effect not in READ_ONLY_CLICK_EFFECTS for effect in click_effects)
            ):
                errors.append(f"{mode} click requires explicit read-only allowedClickEffects")
        if max_writes != 0:
            errors.append(f"{mode} requires maxWrites=0")
        if mode == "generate" and action_set:
            errors.append("generate mode must not authorize browser actions")
    else:
        if not isinstance(max_writes, int) or isinstance(max_writes, bool) or max_writes < 1:
            errors.append(f"{mode} requires a positive maxWrites")
        if not action_set.intersection(WRITE_ACTIONS):
            errors.append(f"{mode} requires at least one explicit write action")
    if mode in {"approved-crud", "prod-safe-smoke", "approved-prod-e2e"} and not str(contract.get("approvalRef") or "").strip():
        errors.append(f"{mode} requires approvalRef")
    if mode in {"approved-crud", "approved-prod-e2e"}:
        prefix = str(contract.get("testDataPrefix") or "")
        if not PREFIX.fullmatch(prefix):
            errors.append("write modes require a 6-40 character testDataPrefix")
        for label in ("beforeAssertions", "afterAssertions"):
            if not isinstance(contract.get(label), list) or not contract[label]:
                errors.append(f"write modes require non-empty {label}")
        require_steps(contract.get("cleanup"), "cleanup", errors)
        require_steps(contract.get("rollback"), "rollback", errors)
    if errors:
        raise ValueError("; ".join(errors))
    canonical = json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "valid": True,
        "contractDigest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "contract": contract,
        "perStepConfirmationRequired": False,
        "stopOnOutOfContractAction": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Kingdee UI testing execution contract.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--force", action="store_true", help="Overwrite only the explicit output file.")
    args = parser.parse_args()
    try:
        contract = json.loads(Path(args.input).expanduser().resolve().read_text(encoding="utf-8-sig"))
        if not isinstance(contract, dict):
            raise ValueError("contract root must be an object")
        result = validate_contract(contract)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"invalid execution contract: {exc}", file=sys.stderr)
        return 2
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output).expanduser().resolve()
        input_path = Path(args.input).expanduser().resolve()
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
