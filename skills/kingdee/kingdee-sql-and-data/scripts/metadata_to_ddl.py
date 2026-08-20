#!/usr/bin/env python3
"""Generate reviewable CREATE TABLE DDL from normalized Kingdee metadata evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
SENSITIVE_KEY = re.compile(r"(?:password|passwd|pwd|token|secret|cookie|credential|access[_-]?key)", re.I)
TYPE_ALIASES = {
    "varchar": "string", "nvarchar": "string", "char": "string", "string": "string",
    "text": "text", "clob": "text",
    "int": "integer", "integer": "integer",
    "long": "bigint", "bigint": "bigint",
    "number": "decimal", "numeric": "decimal", "decimal": "decimal",
    "bool": "boolean", "boolean": "boolean", "bit": "boolean",
    "date": "date",
    "datetime": "datetime", "timestamp": "datetime",
    "binary": "binary", "blob": "binary", "bytea": "binary",
}
TYPE_RENDERERS = {
    "postgresql": {
        "string": lambda c: f"VARCHAR({c['length']})",
        "text": lambda c: "TEXT",
        "integer": lambda c: "INTEGER",
        "bigint": lambda c: "BIGINT",
        "decimal": lambda c: f"DECIMAL({c['precision']},{c['scale']})",
        "boolean": lambda c: "BOOLEAN",
        "date": lambda c: "DATE",
        "datetime": lambda c: "TIMESTAMP",
        "binary": lambda c: "BYTEA",
    },
    "mysql": {
        "string": lambda c: f"VARCHAR({c['length']})",
        "text": lambda c: "TEXT",
        "integer": lambda c: "INTEGER",
        "bigint": lambda c: "BIGINT",
        "decimal": lambda c: f"DECIMAL({c['precision']},{c['scale']})",
        "boolean": lambda c: "BOOLEAN",
        "date": lambda c: "DATE",
        "datetime": lambda c: "DATETIME",
        "binary": lambda c: "LONGBLOB",
    },
    "oracle": {
        "string": lambda c: f"VARCHAR2({c['length']})",
        "text": lambda c: "CLOB",
        "integer": lambda c: "NUMBER(10)",
        "bigint": lambda c: "NUMBER(19)",
        "decimal": lambda c: f"NUMBER({c['precision']},{c['scale']})",
        "boolean": lambda c: "NUMBER(1)",
        "date": lambda c: "DATE",
        "datetime": lambda c: "TIMESTAMP",
        "binary": lambda c: "BLOB",
    },
}


class MetadataError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedSchema:
    table: str
    db_route: str | None
    columns: list[dict[str, Any]]
    indexes: list[dict[str, Any]]


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


def reject_sensitive_keys(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            current = f"{path}.{key}" if path else str(key)
            if SENSITIVE_KEY.search(str(key)):
                raise MetadataError(f"credential-like field is not allowed: {current}")
            reject_sensitive_keys(child, current)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_sensitive_keys(child, f"{path}[{index}]")


def require_identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise MetadataError(f"{field} must be a simple SQL identifier")
    return value


def positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise MetadataError(f"{field} must be a positive integer")
    return value


def normalize_column(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise MetadataError(f"column #{index} must be an object")
    if "default" in raw or "default_sql" in raw:
        raise MetadataError("defaults require database-specific review and are not generated")
    name = require_identifier(raw.get("name") or raw.get("column_name"), f"column #{index} name")
    raw_type = raw.get("type") or raw.get("data_type")
    if not isinstance(raw_type, str) or raw_type.lower() not in TYPE_ALIASES:
        raise MetadataError(f"column {name} has unsupported type")
    data_type = TYPE_ALIASES[raw_type.lower()]
    if "nullable" not in raw or not isinstance(raw["nullable"], bool):
        raise MetadataError(f"column {name} must declare nullable as boolean")
    column = {
        "name": name,
        "type": data_type,
        "nullable": raw["nullable"],
        "primary_key": raw.get("primary_key", False),
    }
    if not isinstance(column["primary_key"], bool):
        raise MetadataError(f"column {name} primary_key must be boolean")
    if data_type == "string":
        column["length"] = positive_int(raw.get("length"), f"column {name} length")
    if data_type == "decimal":
        precision = positive_int(raw.get("precision"), f"column {name} precision")
        scale = raw.get("scale")
        if not isinstance(scale, int) or isinstance(scale, bool) or scale < 0 or scale > precision:
            raise MetadataError(f"column {name} scale must be between 0 and precision")
        column["precision"] = precision
        column["scale"] = scale
    return column


def normalize_schema(raw: dict[str, Any]) -> NormalizedSchema:
    reject_sensitive_keys(raw)
    table = require_identifier(raw.get("table") or raw.get("table_name"), "table")
    db_route_value = raw.get("db_route")
    db_route = require_identifier(db_route_value, "db_route") if db_route_value is not None else None
    raw_columns = raw.get("columns") or raw.get("fields")
    if not isinstance(raw_columns, list) or not raw_columns:
        raise MetadataError("columns/fields must be a non-empty array")
    columns = [normalize_column(column, index) for index, column in enumerate(raw_columns, 1)]
    column_names = [column["name"] for column in columns]
    if len(column_names) != len(set(column_names)):
        raise MetadataError("duplicate column names are not allowed")

    raw_indexes = raw.get("indexes", [])
    if not isinstance(raw_indexes, list):
        raise MetadataError("indexes must be an array")
    indexes: list[dict[str, Any]] = []
    index_names: set[str] = set()
    for position, raw_index in enumerate(raw_indexes, 1):
        if not isinstance(raw_index, dict):
            raise MetadataError(f"index #{position} must be an object")
        name = require_identifier(raw_index.get("name"), f"index #{position} name")
        if name in index_names:
            raise MetadataError(f"duplicate index name: {name}")
        index_names.add(name)
        index_columns = raw_index.get("columns")
        if not isinstance(index_columns, list) or not index_columns:
            raise MetadataError(f"index {name} columns must be a non-empty array")
        normalized_columns = [require_identifier(value, f"index {name} column") for value in index_columns]
        unknown = sorted(set(normalized_columns) - set(column_names))
        if unknown:
            raise MetadataError(f"index {name} references unknown columns: {', '.join(unknown)}")
        unique = raw_index.get("unique", False)
        if not isinstance(unique, bool):
            raise MetadataError(f"index {name} unique must be boolean")
        indexes.append({"name": name, "columns": normalized_columns, "unique": unique})
    return NormalizedSchema(table, db_route, columns, indexes)


def render_ddl(schema: NormalizedSchema, dialect: str) -> str:
    renderer = TYPE_RENDERERS[dialect]
    primary_keys = [column["name"] for column in schema.columns if column["primary_key"]]
    lines = []
    if schema.db_route:
        lines.append(f"-- db_route: {schema.db_route}")
    lines.append(f"CREATE TABLE {schema.table} (")
    definitions = []
    for column in schema.columns:
        nullability = "" if column["nullable"] else " NOT NULL"
        definitions.append(f"    {column['name']} {renderer[column['type']](column)}{nullability}")
    if primary_keys:
        definitions.append(f"    CONSTRAINT PK_{schema.table} PRIMARY KEY ({', '.join(primary_keys)})")
    lines.append(",\n".join(definitions))
    lines.append(");")
    for index in schema.indexes:
        unique = "UNIQUE " if index["unique"] else ""
        lines.append(f"CREATE {unique}INDEX {index['name']} ON {schema.table} ({', '.join(index['columns'])});")
    return "\n".join(lines) + "\n"


def load_schema(path: Path) -> NormalizedSchema:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise MetadataError("metadata root must be an object")
    return normalize_schema(raw)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect", "generate"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--metadata", required=True)
        subparser.add_argument("--dialect", choices=tuple(TYPE_RENDERERS), required=True)
        if command == "generate":
            subparser.add_argument("--output", required=True)
            subparser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        schema = load_schema(resolve_user_path(args.metadata))
        ddl = render_ddl(schema, args.dialect)
        if args.command == "inspect":
            print(json.dumps({
                "status": "validated",
                "dialect": args.dialect,
                "table": schema.table,
                "db_route": schema.db_route,
                "columns": len(schema.columns),
                "indexes": len(schema.indexes),
            }, ensure_ascii=False, indent=2))
            return 0
        output = resolve_user_path(args.output)
        if output.exists() and not args.overwrite:
            raise MetadataError("output exists; pass --overwrite to replace it")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(ddl, encoding="utf-8", newline="\n")
        print(json.dumps({"status": "generated_not_executed", "output": str(output)}, ensure_ascii=False))
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, MetadataError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
