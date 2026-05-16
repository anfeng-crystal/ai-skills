#!/usr/bin/env python3
# SPDX-License-Identifier: NOASSERTION
"""
cosmic-config-check.py — Step 0 config preflight for ok-cosmic.

Usage:
    python3 cosmic-config-check.py
    python3 cosmic-config-check.py --config /path/to/ok-cosmic.json
    python3 cosmic-config-check.py --config ok-cosmic.json --strict
    python3 cosmic-config-check.py --config ok-cosmic.json --json
"""

import argparse
import json
import sys
from typing import Any, Dict, List

from config_loader import read_project_config, validate_project_config


def _group_issues(issues: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    errors = [issue for issue in issues if issue.get("level") == "ERROR"]
    warnings = [issue for issue in issues if issue.get("level") == "WARNING"]
    return {"errors": errors, "warnings": warnings}


def _print_text_report(config_path: str, issues: List[Dict[str, str]]) -> None:
    print(f"[OK] 已找到配置文件: {config_path}")
    if not issues:
        print("[OK] 配置预检通过，未发现缺失项。")
        return

    for issue in issues:
        level = issue.get("level", "INFO")
        key = issue.get("key", "-")
        message = issue.get("message", "")
        print(f"[{level}] {key}: {message}")

    grouped = _group_issues(issues)
    print(f"[SUMMARY] errors={len(grouped['errors'])} warnings={len(grouped['warnings'])}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Step 0 配置预检：检查 ok-cosmic.json 是否存在以及关键内容是否缺失。"
    )
    parser.add_argument("--config", help="Path to ok-cosmic.json")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON report.")
    args = parser.parse_args()

    try:
        resolved_path, raw_config = read_project_config(args.config)
        config: Dict[str, Any] = dict(raw_config)
        config["__config_path__"] = str(resolved_path)
        config["__config_dir__"] = str(resolved_path.parent)
        issues = validate_project_config(config, str(resolved_path))
    except Exception as e:
        message = str(e)
        if args.json:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "configPath": args.config or "ok-cosmic.json",
                        "errors": [{"level": "ERROR", "key": "__file__", "message": message}],
                        "warnings": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(f"[ERROR] __file__: {message}", file=sys.stderr)
        return 1

    grouped = _group_issues(issues)
    ok = not grouped["errors"] and not (args.strict and grouped["warnings"])

    if args.json:
        print(
            json.dumps(
                {
                    "ok": ok,
                    "configPath": str(resolved_path),
                    "errors": grouped["errors"],
                    "warnings": grouped["warnings"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        _print_text_report(str(resolved_path), issues)
        if args.strict and grouped["warnings"] and not grouped["errors"]:
            print("[STRICT] strict 模式下 warning 也会导致失败。", file=sys.stderr)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
