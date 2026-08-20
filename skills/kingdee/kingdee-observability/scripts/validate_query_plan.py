#!/usr/bin/env python3
"""Validate a bounded, credential-free observability query plan without network access."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from redact import redact_value


MODES = {"dev-query", "prod-readonly"}
QUERY_TYPES = {"trace", "time-window", "service", "exception", "slow-sql"}
FORBIDDEN_KEY_PARTS = {
    "password",
    "secret",
    "token",
    "cookie",
    "authorization",
    "csrf",
    "session",
    "storage_state",
    "connectionstring",
    "jdbc",
    "header",
}
FORBIDDEN_VALUE = re.compile(
    r"(?i)[\"']?(password|passwd|secret|token|cookie|authorization|csrf|session|storage_state)[\"']?\s*[:=]"
)


def parse_datetime(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(part in normalized for part in FORBIDDEN_KEY_PARTS):
                hits.append(f"{path}.{key}")
            hits.extend(find_forbidden_keys(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(find_forbidden_keys(item, f"{path}[{index}]"))
    elif isinstance(value, str) and FORBIDDEN_VALUE.search(value):
        hits.append(path)
    return hits


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    mode = plan.get("mode")
    query_type = plan.get("queryType")
    scope_id = str(plan.get("scopeId") or "").strip()
    target_ref = str(plan.get("targetRef") or "").strip()
    filters = plan.get("filters")
    max_records = plan.get("maxRecords")

    forbidden = find_forbidden_keys(plan)
    if forbidden:
        errors.append("credential/session fields are forbidden: " + ", ".join(forbidden))
    if mode not in MODES:
        errors.append("mode must be dev-query or prod-readonly")
    if query_type not in QUERY_TYPES:
        errors.append("unsupported queryType")
    if not scope_id:
        errors.append("scopeId is required")
    if not target_ref or "://" in target_ref:
        errors.append("targetRef must be a configured non-URL alias")
    if plan.get("redaction") is not True:
        errors.append("redaction must be true")
    if not isinstance(max_records, int) or isinstance(max_records, bool) or not 1 <= max_records <= 5000:
        errors.append("maxRecords must be an integer from 1 to 5000")
    if mode == "prod-readonly":
        if not str(plan.get("approvalRef") or "").strip():
            errors.append("prod-readonly requires approvalRef")
        if isinstance(max_records, int) and max_records > 1000:
            errors.append("prod-readonly maxRecords cannot exceed 1000")
    if not isinstance(filters, dict):
        errors.append("filters must be an object")
    else:
        trace_id = str(filters.get("traceId") or "").strip()
        start = filters.get("start")
        end = filters.get("end")
        if query_type == "trace" and not trace_id:
            errors.append("trace query requires filters.traceId")
        if query_type != "trace" or (start is not None or end is not None):
            if not isinstance(start, str) or not isinstance(end, str):
                errors.append("bounded filters.start and filters.end are required")
            else:
                try:
                    start_dt = parse_datetime(start)
                    end_dt = parse_datetime(end)
                    if end_dt <= start_dt:
                        errors.append("filters.end must be after filters.start")
                    elif mode == "prod-readonly" and (end_dt - start_dt).total_seconds() > 3600:
                        errors.append("prod-readonly time window cannot exceed 60 minutes")
                except ValueError as exc:
                    errors.append(str(exc))
    if errors:
        raise ValueError("; ".join(errors))

    sanitized = redact_value(plan)
    canonical = json.dumps(sanitized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "valid": True,
        "contractDigest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "plan": sanitized,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a read-only observability query plan.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        plan = json.loads(Path(args.input).expanduser().resolve().read_text(encoding="utf-8-sig"))
        if not isinstance(plan, dict):
            raise ValueError("plan root must be an object")
        result = validate_plan(plan)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"invalid query plan: {exc}", file=sys.stderr)
        return 2
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
