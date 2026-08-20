#!/usr/bin/env python3
"""Scan standalone and nested DTS strings for known target SQL dialect violations."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterable, Iterator


SQL_MARKER_RE = re.compile(r"\b(?:SELECT|UPDATE|INSERT|DELETE|FROM|WHERE|JOIN)\b", re.IGNORECASE)
BARE_TRIM_RE = re.compile(r"(?<![\w.])TRIM\s*\(", re.IGNORECASE)


def inputs(paths: Iterable[Path]) -> Iterator[tuple[str, str]]:
    for path in paths:
        if path.is_dir():
            yield from inputs(sorted(path.rglob("*.dts")))
        elif zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.lower().endswith(".dts"):
                        yield f"{path}!{name}", archive.read(name).decode("utf-8")
        else:
            yield str(path), path.read_text(encoding="utf-8")


def dts_objects(text: str, source: str) -> Iterator[tuple[str, dict[str, Any]]]:
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if line.startswith("(") and line.endswith(")"):
            line = line[1:-1]
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{source}:{line_number}: invalid DTS JSON: {exc}") from exc
        if isinstance(value, dict):
            yield f"{source}:{line_number}", value


def unwrap_json_string(value: str) -> Any | None:
    candidate = value.strip()
    if candidate.startswith("(") and candidate.endswith(")"):
        candidate = candidate[1:-1]
    if not candidate.startswith(("{", "[")):
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def strings(value: Any, location: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from strings(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from strings(child, f"{location}[{index}]")
    elif isinstance(value, str):
        nested = unwrap_json_string(value)
        if nested is not None:
            yield from strings(nested, f"{location}<json>")
        else:
            yield location, value


def check(paths: Iterable[Path], dialect: str) -> tuple[list[dict[str, str]], list[str]]:
    violations: list[dict[str, str]] = []
    errors: list[str] = []
    try:
        for source, text in inputs(paths):
            for location, value in dts_objects(text, source):
                for string_location, content in strings(value, location):
                    if not SQL_MARKER_RE.search(content):
                        continue
                    if dialect == "sqlserver-legacy" and BARE_TRIM_RE.search(content):
                        violations.append({
                            "location": string_location,
                            "code": "SQLSERVER_LEGACY_TRIM",
                            "message": "bare SQL TRIM is not allowed for this target dialect",
                        })
    except (OSError, UnicodeDecodeError, ValueError, zipfile.BadZipFile) as exc:
        errors.append(str(exc))
    return violations, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dialect", required=True, choices=("sqlserver-legacy", "sqlserver", "postgresql"))
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    violations, errors = check(args.paths, args.dialect)
    result = {"violations": violations, "errors": errors}
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in violations:
            print(f"ERROR {item['location']} {item['code']}: {item['message']}")
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        if not violations and not errors:
            print(f"PASS no known {args.dialect} SQL dialect violations")
    if errors:
        return 2
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
