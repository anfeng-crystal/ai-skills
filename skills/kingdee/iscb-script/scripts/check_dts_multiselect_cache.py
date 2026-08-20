#!/usr/bin/env python3
"""Reject cached ISCB value rules that return multi-select base-data ID lists."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Iterable, Iterator, Tuple


LIST_INIT_RE = re.compile(r"\bvar\s+([A-Za-z_$][\w$]*)\s*=\s*\[\s*\]\s*;")


def _objects(text: str, source: str) -> Iterator[Tuple[str, dict]]:
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
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


def _inputs(paths: Iterable[Path]) -> Iterator[Tuple[str, str]]:
    for path in paths:
        if path.is_dir():
            yield from _inputs(sorted(path.rglob("*.dts")))
        elif zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.lower().endswith(".dts"):
                        yield f"{path}!{name}", archive.read(name).decode("utf-8")
        else:
            yield str(path), path.read_text(encoding="utf-8")


def _returns_id_list(script: str) -> bool:
    if "fid" not in script.lower():
        return False
    for variable in LIST_INIT_RE.findall(script):
        if re.search(rf"\breturn\s+{re.escape(variable)}\s*;", script):
            return True
    return False


def check(paths: Iterable[Path]) -> Tuple[list[dict], list[str]]:
    violations: list[dict] = []
    errors: list[str] = []
    try:
        for source, text in _inputs(paths):
            for location, value in _objects(text, source):
                if value.get("$entityname") != "isc_value_conver_rule":
                    continue
                script = value.get("isc_script_tag") or ""
                if _returns_id_list(script) and value.get("iscached") is not False:
                    violations.append(
                        {
                            "location": location,
                            "number": value.get("number", ""),
                            "iscached": value.get("iscached"),
                        }
                    )
    except (OSError, UnicodeDecodeError, ValueError, zipfile.BadZipFile) as exc:
        errors.append(str(exc))
    return violations, errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check that multi-select base-data ID-list rules use iscached=false."
    )
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    violations, errors = check(args.paths)
    result = {"violations": violations, "errors": errors}
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in violations:
            print(
                f"ERROR {item['location']} {item['number']}: "
                f"multi-select base-data ID list must use iscached=false"
            )
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        if not violations and not errors:
            print("PASS no cached multi-select base-data ID-list rules")
    if errors:
        return 2
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
