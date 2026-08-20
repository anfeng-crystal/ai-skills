#!/usr/bin/env python3
"""Join normalized UI steps with redacted execution results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from validate_execution_contract import validate_contract


STATUSES = {"passed", "failed", "blocked", "skipped", "not-run"}
SENSITIVE_KEY = re.compile(
    r"(?i)(password|passwd|secret|token|cookie|authorization|csrf|session|tenant|account|user|person|employee|phone|mobile|email|client.?ip|remote.?ip|storage.?state)"
)
SENSITIVE_PAIR = re.compile(
    r"(?i)([\"']?(?:password|passwd|secret|token|cookie|authorization|csrf|session|tenant(?:id)?|account(?:id)?|user(?:id|name)?|person(?:id)?|clientip|remoteip)[\"']?)(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
)
URL_HOST = re.compile(r"(?i)\b(https?://)([^/\s]+)")
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")


def redact_text(value: str) -> str:
    value = URL_HOST.sub(lambda match: f"{match.group(1)}[REDACTED_HOST]", value)
    value = IPV4.sub("[REDACTED_IP]", value)
    value = EMAIL.sub("[REDACTED_EMAIL]", value)
    return SENSITIVE_PAIR.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value
    )


def redact(value: Any, key: str = "") -> Any:
    if key and SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): redact(item, str(item_key)) for item_key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_results(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        results = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError(f"result line {line_number} must be an object")
            results.append(item)
        return results
    root = load_json(path)
    if isinstance(root, list):
        return root
    if isinstance(root, dict) and isinstance(root.get("results"), list):
        return root["results"]
    raise ValueError("results must be an array, JSONL, or object with results")


def build_report(
    normalized: dict[str, Any],
    results: list[dict[str, Any]],
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cases = normalized.get("cases")
    if not isinstance(cases, list):
        raise ValueError("normalized cases must contain a cases array")
    result_map: dict[tuple[str, str], dict[str, Any]] = {}
    for index, result in enumerate(results, start=1):
        if not isinstance(result, dict):
            raise ValueError(f"result {index} must be an object")
        key = (str(result.get("caseId") or ""), str(result.get("stepId") or ""))
        if not all(key):
            raise ValueError(f"result {index} requires caseId and stepId")
        if key in result_map:
            raise ValueError(f"duplicate result for {key[0]}/{key[1]}")
        status = str(result.get("status") or "").lower()
        if status not in STATUSES - {"not-run"}:
            raise ValueError(f"result {index} has invalid status {status!r}")
        result_map[key] = result

    status_counts: Counter[str] = Counter()
    report_cases = []
    for case in cases:
        case_id = str(case.get("caseId") or "")
        step_reports = []
        for step in case.get("steps", []):
            step_id = str(step.get("stepId") or "")
            result = result_map.pop((case_id, step_id), None)
            if result is None:
                status = "not-run"
                evidence = {}
            else:
                status = str(result.get("status")).lower()
                evidence = {
                    key: result[key]
                    for key in (
                        "startedAt",
                        "endedAt",
                        "actual",
                        "expected",
                        "screenshot",
                        "error",
                        "before",
                        "after",
                        "createdIds",
                        "cleanup",
                        "rollback",
                    )
                    if key in result
                }
            status_counts[status] += 1
            step_reports.append(
                {
                    "stepId": step_id,
                    "order": step.get("order"),
                    "action": step.get("action"),
                    "target": step.get("target"),
                    "mutates": step.get("mutates", False),
                    "status": status,
                    "evidence": redact(evidence),
                }
            )
        report_cases.append(
            {
                "caseId": case_id,
                "name": case.get("name"),
                "requirements": case.get("requirements", []),
                "steps": step_reports,
            }
        )

    report: dict[str, Any] = {
        "schemaVersion": "1.0",
        "mode": normalized.get("mode"),
        "summary": {
            "caseCount": len(report_cases),
            "stepCount": sum(status_counts.values()),
            "statusCounts": {status: status_counts.get(status, 0) for status in sorted(STATUSES)},
            "unexpectedResultCount": len(result_map),
        },
        "cases": report_cases,
        "unexpectedResults": [
            {"caseId": case_id, "stepId": step_id, "result": redact(result)}
            for (case_id, step_id), result in sorted(result_map.items())
        ],
        "redactionApplied": True,
    }
    if contract is not None:
        validated = validate_contract(contract)
        report["contract"] = {
            "taskId": contract.get("taskId"),
            "mode": contract.get("mode"),
            "contractDigest": validated["contractDigest"],
            "perStepConfirmationRequired": False,
        }
    return redact(report)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a redacted Kingdee UI step evidence report.")
    parser.add_argument("--cases", required=True, help="Normalized testcase JSON.")
    parser.add_argument("--results", required=True, help="JSON or JSONL step results.")
    parser.add_argument("--contract", help="Optional execution contract JSON.")
    parser.add_argument("--output")
    parser.add_argument("--force", action="store_true", help="Overwrite only the explicit output file.")
    args = parser.parse_args()
    cases_path = Path(args.cases).expanduser().resolve()
    results_path = Path(args.results).expanduser().resolve()
    contract_path = Path(args.contract).expanduser().resolve() if args.contract else None
    try:
        normalized = load_json(cases_path)
        results = load_results(results_path)
        contract = load_json(contract_path) if contract_path else None
        report = build_report(normalized, results, contract)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"cannot build evidence report: {exc}", file=sys.stderr)
        return 2
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output).expanduser().resolve()
        if output in {cases_path, results_path, contract_path}:
            print("output must not overwrite an input", file=sys.stderr)
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
