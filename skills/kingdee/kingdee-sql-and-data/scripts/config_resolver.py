#!/usr/bin/env python3
"""Resolve the KSQL config.ini path without writing files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_CONFIG = SKILL_ROOT / "templates" / "config.example.ini"


def _expand(path: str | Path, base: Path | None = None) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute() and base is not None:
        candidate = base / candidate
    return candidate.resolve()


def resolve_config(cwd: Path, explicit_config: str | None = None) -> tuple[Path, str]:
    if explicit_config:
        path = _expand(explicit_config, cwd)
        if not path.is_file():
            raise FileNotFoundError(f"--config does not exist or is not a file: {path}")
        return path, "explicit"

    candidates = [
        (cwd / ".kingdee" / "ksql" / "config.ini", "project_dot_kingdee"),
        (cwd / "config" / "kingdee" / "ksql" / "config.ini", "project_config_dir"),
        (TEMPLATE_CONFIG, "skill_template"),
    ]
    for path, source in candidates:
        if path.is_file():
            return path.resolve(), source

    raise FileNotFoundError(f"No KSQL config found; missing template: {TEMPLATE_CONFIG}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve Kingdee KSQL config.ini path.")
    parser.add_argument("--config", help="Explicit config.ini path.")
    parser.add_argument("--cwd", default=".", help="Project directory used for discovery.")
    parser.add_argument("--print", dest="print_path", action="store_true", help="Print only the resolved path.")
    parser.add_argument("--json", action="store_true", help="Print JSON result.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cwd = _expand(args.cwd)
    if not cwd.is_dir():
        print(f"--cwd is not a directory: {cwd}", file=sys.stderr)
        return 2

    try:
        path, source = resolve_config(cwd, args.config)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    result = {
        "path": str(path),
        "source": source,
        "cwd": str(cwd),
        "is_template": source == "skill_template",
    }
    if args.print_path:
        print(path)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.json else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
