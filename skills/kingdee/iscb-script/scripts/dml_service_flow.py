#!/usr/bin/env python3
"""Validate and patch an approved parameterized DML node into an existing DTS baseline."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ALLOWED_TYPES = {
    "VARCHAR", "NVARCHAR", "CHAR", "NCHAR", "DOUBLE", "BINARY", "BLOB",
    "CLOB", "NCLOB", "BIT", "BIGINT", "INTEGER", "DECIMAL", "TIMESTAMP",
    "DATETIME", "VARBINARY",
}
REQUIRED_CONTRACT_FIELDS = {
    "authorization_ref", "environment", "scope", "rollback_plan", "max_rows",
    "resource_alias", "flow_number", "node_id",
}
SENSITIVE_KEY = re.compile(r"(?:password|passwd|pwd|token|secret|cookie|credential|access[_-]?key)", re.I)


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class SqlSpec:
    verb: str
    table: str
    sql: str
    placeholder_count: int


def resolve_user_path(raw_path: str, cwd: Path | None = None) -> Path:
    base = cwd or Path.cwd()
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    if candidate.exists():
        return candidate.resolve()
    if os.name != "nt" and "\\" in raw_path and not re.match(r"^[A-Za-z]:\\", raw_path):
        portable = Path(raw_path.replace("\\", "/")).expanduser()
        if not portable.is_absolute():
            portable = base / portable
        return portable.resolve()
    return candidate.resolve()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(read_text(path))
    if not isinstance(data, dict):
        raise ContractError(f"JSON root must be an object: {path.name}")
    reject_sensitive_keys(data)
    return data


def reject_sensitive_keys(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            if SENSITIVE_KEY.search(str(key)):
                raise ContractError(f"credential-like field is not allowed: {key_path}")
            reject_sensitive_keys(child, key_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_sensitive_keys(child, f"{path}[{index}]")


def scan_sql(sql: str) -> tuple[list[str], int, str]:
    statements: list[str] = []
    current: list[str] = []
    masked: list[str] = []
    placeholders = 0
    quote: str | None = None
    index = 0
    while index < len(sql):
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < len(sql) else ""
        if quote:
            current.append(char)
            masked.append(" ")
            if char == quote:
                if next_char == quote:
                    current.append(next_char)
                    masked.append(" ")
                    index += 1
                else:
                    quote = None
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
            masked.append(" ")
        elif char == "-" and next_char == "-":
            raise ContractError("SQL comments are not allowed in generated DML")
        elif char == "/" and next_char == "*":
            raise ContractError("SQL comments are not allowed in generated DML")
        elif char == "?":
            placeholders += 1
            current.append(char)
            masked.append(char)
        elif char == ";":
            value = "".join(current).strip()
            if value:
                statements.append(value)
            current = []
            masked.append(" ")
        else:
            current.append(char)
            masked.append(char)
        index += 1
    if quote:
        raise ContractError("unterminated SQL string literal")
    value = "".join(current).strip()
    if value:
        statements.append(value)
    return statements, placeholders, "".join(masked)


def parse_dml(sql: str) -> SqlSpec:
    statements, placeholders, masked = scan_sql(sql)
    if len(statements) != 1:
        raise ContractError("exactly one DML statement is required")
    statement = statements[0]
    head = re.match(r"^\s*(INSERT|UPDATE|DELETE)\b", statement, re.I)
    if not head:
        raise ContractError("only INSERT, UPDATE, or DELETE is allowed")
    verb = head.group(1).upper()
    masked_statement = masked.strip()
    if verb in {"UPDATE", "DELETE"} and not re.search(r"\bWHERE\b", masked_statement, re.I):
        raise ContractError(f"{verb} requires a WHERE clause")
    table_patterns = {
        "INSERT": r"^\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_$]*(?:@[A-Za-z_][A-Za-z0-9_$]*)?)",
        "UPDATE": r"^\s*UPDATE\s+([A-Za-z_][A-Za-z0-9_$]*(?:@[A-Za-z_][A-Za-z0-9_$]*)?)",
        "DELETE": r"^\s*DELETE\s+FROM\s+([A-Za-z_][A-Za-z0-9_$]*(?:@[A-Za-z_][A-Za-z0-9_$]*)?)",
    }
    table_match = re.match(table_patterns[verb], statement, re.I)
    if not table_match:
        raise ContractError("cannot determine a single DML target table")
    return SqlSpec(verb, table_match.group(1), statement, placeholders)


def parse_precheck(sql: str) -> SqlSpec:
    statements, placeholders, _ = scan_sql(sql)
    if len(statements) != 1 or not re.match(r"^\s*SELECT\b", statements[0], re.I):
        raise ContractError("precheck must be exactly one SELECT statement")
    if re.search(r"\b(?:INSERT|UPDATE|DELETE|MERGE|ALTER|DROP|TRUNCATE|CALL)\b", statements[0], re.I):
        raise ContractError("precheck must be read-only")
    return SqlSpec("SELECT", "", statements[0], placeholders)


def validate_types(values: Any, field: str) -> list[str]:
    if not isinstance(values, list):
        raise ContractError(f"{field} must be an array")
    normalized = []
    for value in values:
        if not isinstance(value, str) or value.upper() not in ALLOWED_TYPES:
            raise ContractError(f"unsupported SQL type in {field}")
        normalized.append(value.upper())
    return normalized


def validate_parameters(parameters: dict[str, Any], dml: SqlSpec, precheck: SqlSpec) -> dict[str, Any]:
    required = {"params", "types", "precheck_params", "precheck_types"}
    missing = sorted(required - parameters.keys())
    if missing:
        raise ContractError("parameter file missing fields: " + ", ".join(missing))
    params = parameters["params"]
    precheck_params = parameters["precheck_params"]
    if not isinstance(params, list) or not isinstance(precheck_params, list):
        raise ContractError("params and precheck_params must be arrays")
    types = validate_types(parameters["types"], "types")
    precheck_types = validate_types(parameters["precheck_types"], "precheck_types")
    if not (len(params) == len(types) == dml.placeholder_count):
        raise ContractError("DML placeholder, params, and types counts differ")
    if not (len(precheck_params) == len(precheck_types) == precheck.placeholder_count):
        raise ContractError("precheck placeholder, params, and types counts differ")
    return {
        "params": params,
        "types": types,
        "precheck_params": precheck_params,
        "precheck_types": precheck_types,
    }


def validate_contract(contract: dict[str, Any], require_approved: bool) -> dict[str, Any]:
    missing = sorted(field for field in REQUIRED_CONTRACT_FIELDS if field not in contract or contract[field] in (None, ""))
    if missing:
        raise ContractError("contract missing fields: " + ", ".join(missing))
    if require_approved and contract.get("approved") is not True:
        raise ContractError("generate mode requires approved=true")
    if not isinstance(contract["max_rows"], int) or isinstance(contract["max_rows"], bool) or contract["max_rows"] <= 0:
        raise ContractError("max_rows must be a positive integer")
    for field in ("authorization_ref", "environment", "scope", "rollback_plan", "resource_alias", "flow_number", "node_id"):
        if not isinstance(contract[field], str) or not contract[field].strip():
            raise ContractError(f"{field} must be a non-empty string")
    return contract


def render_value(value: Any, sql_type: str) -> str:
    if value is None:
        return "null"
    if sql_type == "BIGINT":
        return f"L({json.dumps(str(value), ensure_ascii=False)})"
    if sql_type == "INTEGER":
        return f"I({json.dumps(str(value), ensure_ascii=False)})"
    if sql_type in {"DECIMAL", "DOUBLE"}:
        return f"N({json.dumps(str(value), ensure_ascii=False)})"
    if sql_type in {"TIMESTAMP", "DATETIME"}:
        return f"T({json.dumps(str(value), ensure_ascii=False)})"
    if sql_type == "BIT" and isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def render_array(values: list[Any], types: list[str]) -> str:
    return "[" + ", ".join(render_value(value, sql_type) for value, sql_type in zip(values, types)) + "]"


def render_types(types: list[str]) -> str:
    return "[" + ", ".join(types) + "]"


def build_node_script(dml: SqlSpec, precheck: SqlSpec, parameters: dict[str, Any], contract: dict[str, Any]) -> str:
    alias = contract["resource_alias"]
    if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", alias):
        raise ContractError("resource_alias is not a valid script variable")
    dml_sql = json.dumps(dml.sql, ensure_ascii=False)
    precheck_sql = json.dumps(precheck.sql, ensure_ascii=False)
    pre_params = render_array(parameters["precheck_params"], parameters["precheck_types"])
    pre_types = render_types(parameters["precheck_types"])
    dml_params = render_array(parameters["params"], parameters["types"])
    dml_types = render_types(parameters["types"])
    max_rows = contract["max_rows"]
    return "\n".join([
        f"var plannedCount = I(query_value({alias}, {precheck_sql}, {pre_params}, {pre_types}));",
        f"if (plannedCount > {max_rows}) {{",
        f"    throw \"precheck count exceeds approved maximum {max_rows}\";",
        "}",
        f"var affectedCount = execute_update({alias}, {dml_sql}, {dml_params}, {dml_types});",
        f"if (affectedCount > {max_rows}) {{",
        f"    throw \"affected rows exceed approved maximum {max_rows}\";",
        "}",
        "return {plannedCount: plannedCount, affectedCount: affectedCount};",
    ])


def unwrap_json(value: str) -> tuple[dict[str, Any], bool]:
    stripped = value.strip()
    wrapped = stripped.startswith("(") and stripped.endswith(")")
    payload = stripped[1:-1] if wrapped else stripped
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ContractError("DTS record must be a JSON object")
    return parsed, wrapped


def patch_dts(baseline_text: str, contract: dict[str, Any], node_script: str) -> str:
    source_lines = [line for line in baseline_text.splitlines() if line.strip()]
    if not source_lines:
        raise ContractError("DTS baseline is empty")
    records: list[tuple[dict[str, Any], bool]] = []
    for index, line in enumerate(source_lines, 1):
        try:
            records.append(unwrap_json(line))
        except (json.JSONDecodeError, ContractError) as error:
            raise ContractError(f"unsupported DTS record at line {index}: {error}") from error

    matches = [
        record for record, _ in records
        if record.get("$entityname") == "isc_service_flow" and str(record.get("number")) == contract["flow_number"]
    ]
    if len(matches) != 1:
        raise ContractError("contract flow_number must match exactly one isc_service_flow record")
    flow = matches[0]
    resources = flow.get("resources")
    if not isinstance(resources, list) or not any(
        isinstance(resource, dict) and resource.get("res_alias") == contract["resource_alias"]
        for resource in resources
    ):
        raise ContractError("resource_alias is not present in the baseline flow resources")
    definition_raw = flow.get("define_json_tag") or flow.get("define_json")
    if not isinstance(definition_raw, str) or not definition_raw.strip():
        raise ContractError("service flow has no parseable define_json_tag/define_json")
    definition, definition_wrapped = unwrap_json(definition_raw)
    nodes = definition.get("nodes")
    if not isinstance(nodes, dict) or contract["node_id"] not in nodes:
        raise ContractError("node_id is not present in the baseline flow")
    node = nodes[contract["node_id"]]
    if not isinstance(node, dict) or str(node.get("type", "")).lower() != "script":
        raise ContractError("node_id must identify a Script node")
    node["script"] = node_script
    serialized_definition = json.dumps(definition, ensure_ascii=False, separators=(",", ":"))
    if definition_wrapped:
        serialized_definition = f"({serialized_definition})"
    if flow.get("define_json_tag"):
        flow["define_json_tag"] = serialized_definition
    else:
        flow["define_json"] = serialized_definition

    output_lines = []
    for record, wrapped in records:
        serialized = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        output_lines.append(f"({serialized})" if wrapped else serialized)
    return "\n".join(output_lines) + "\n"


def prepare(args: argparse.Namespace, require_approved: bool) -> tuple[SqlSpec, SqlSpec, dict[str, Any], dict[str, Any], str]:
    contract = validate_contract(read_json(resolve_user_path(args.contract_file)), require_approved)
    dml = parse_dml(read_text(resolve_user_path(args.sql_file)))
    precheck = parse_precheck(read_text(resolve_user_path(args.precheck_sql_file)))
    parameters = validate_parameters(read_json(resolve_user_path(args.parameters_file)), dml, precheck)
    script = build_node_script(dml, precheck, parameters, contract)
    baseline = read_text(resolve_user_path(args.baseline))
    patch_dts(baseline, contract, script)
    return dml, precheck, parameters, contract, script


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--sql-file", required=True)
    parser.add_argument("--precheck-sql-file", required=True)
    parser.add_argument("--parameters-file", required=True)
    parser.add_argument("--contract-file", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect", help="Validate and emit a redacted plan")
    add_common_arguments(inspect_parser)
    generate_parser = subparsers.add_parser("generate", help="Write a reviewed DTS copy")
    add_common_arguments(generate_parser)
    generate_parser.add_argument("--output", required=True)
    generate_parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        dml, precheck, _, contract, script = prepare(args, require_approved=args.command == "generate")
        baseline_path = resolve_user_path(args.baseline)
        if args.command == "inspect":
            summary = {
                "status": "validated",
                "verb": dml.verb,
                "table": dml.table,
                "dml_placeholders": dml.placeholder_count,
                "precheck_placeholders": precheck.placeholder_count,
                "environment": contract["environment"],
                "flow_number": contract["flow_number"],
                "node_id": contract["node_id"],
                "resource_alias": contract["resource_alias"],
                "max_rows": contract["max_rows"],
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0
        output_path = resolve_user_path(args.output)
        if output_path == baseline_path:
            raise ContractError("baseline cannot be overwritten in place")
        if output_path.exists() and not args.overwrite:
            raise ContractError("output exists; pass --overwrite to replace it")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        patched = patch_dts(read_text(baseline_path), contract, script)
        output_path.write_text(patched, encoding="utf-8", newline="\n")
        print(json.dumps({"status": "generated_not_executed", "output": str(output_path)}, ensure_ascii=False))
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, ContractError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
