#!/usr/bin/env python3
"""Read-only health check for Kingdee host adapters and installation targets."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REGISTRY_PATH = SCRIPT_DIR / "host-registry.json"


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    load_dotenv(root / ".env")
    report = build_report(root)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_text_report(report)
    return 0 if report["ok"] else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Kingdee host adapter readiness without writing files.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Active skills root.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    return parser.parse_args()


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.removeprefix("export ").strip()
        if key and key not in os.environ:
            os.environ[key] = strip_quotes(value.strip())


def strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def build_report(root: Path) -> dict[str, Any]:
    registry = load_registry()
    kingdee_root = root / "skills" / "kingdee"
    skills = list_kingdee_skills(kingdee_root)
    host_checks = [inspect_host(root, entry) for entry in registry.get("hosts", [])]
    errors = []

    if not kingdee_root.is_dir():
        errors.append(f"source_root_missing:{kingdee_root}")
    if not skills:
        errors.append("source_empty:no_kingdee_skills_with_SKILL_md")
    for check in host_checks:
        if check["required"] and check["status"] != "available":
            errors.append(f"{check['host']}:{check['status']}:{check['reason']}")

    return {
        "ok": not errors,
        "root": str(root),
        "registry": str(REGISTRY_PATH),
        "skillCount": len(skills),
        "skills": skills,
        "errors": errors,
        "hosts": host_checks,
    }


def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def list_kingdee_skills(kingdee_root: Path) -> list[str]:
    if not kingdee_root.is_dir():
        return []
    return [
        child.name
        for child in sorted(kingdee_root.iterdir())
        if child.is_dir() and not child.name.startswith(".") and (child / "SKILL.md").is_file()
    ]


def inspect_host(root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    home = Path(os.environ.get("AI_HOST_HOME", str(Path.home()))).expanduser()
    target_dir = expand_host_path(entry["targetDir"], home, root)
    adapter_path = (SCRIPT_DIR / entry["adapter"]).resolve()
    install_mode = entry.get("installMode", "symlink")
    default = entry.get("default", "optional")
    required = default == "enabled"

    base = {
        "host": entry["id"],
        "label": entry.get("label", entry["id"]),
        "required": required,
        "default": default,
        "installMode": install_mode,
        "targetDir": str(target_dir),
        "adapterPath": str(adapter_path),
        "adapterExists": adapter_path.is_file(),
    }

    if not adapter_path.is_file():
        return {**base, "status": "adapter_missing", "reason": "adapter_file_missing"}

    if install_mode == "external_dirs":
        config_path = expand_host_path(entry["configPath"], home, root) if entry.get("configPath") else None
        external = inspect_external_dirs(root, config_path)
        status = "available" if external["ok"] else "optional_host_unavailable"
        return {
            **base,
            "configPath": str(config_path) if config_path else None,
            "status": status,
            "reason": external["reason"],
        }

    if target_dir.is_dir():
        return {**base, "status": "available", "reason": "target_root_exists"}
    if required:
        return {**base, "status": "missing_target_root", "reason": "target_root_missing"}
    return {**base, "status": "optional_host_unavailable", "reason": "optional_host_target_root_missing"}


def expand_host_path(value: str, home: Path, root: Path) -> Path:
    expanded = value.replace("~", str(home), 1) if value.startswith("~/") or value == "~" else value
    expanded = expanded.replace("${root}", str(root))
    return Path(expanded).expanduser().resolve()


def inspect_external_dirs(root: Path, config_path: Path | None) -> dict[str, Any]:
    if config_path is None:
        return {"ok": False, "reason": "config_path_missing"}
    try:
        values = parse_external_dirs(config_path.read_text(encoding="utf-8"))
    except OSError:
        return {"ok": False, "reason": "config_unreadable"}

    resolved = {str(Path(value).expanduser().resolve()) for value in values}
    if str(root.resolve()) in resolved:
        return {"ok": True, "reason": "external_dirs_includes_active_root"}
    return {"ok": False, "reason": "source_root_not_listed" if resolved else "external_dirs_empty"}


def parse_external_dirs(content: str) -> list[str]:
    values: list[str] = []
    in_skills = False
    skills_indent = -1
    in_external_dirs = False
    external_indent = -1

    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip())
        if not in_skills:
            if stripped == "skills:":
                in_skills = True
                skills_indent = indent
            continue
        if indent <= skills_indent and ":" in stripped:
            in_skills = stripped == "skills:"
            in_external_dirs = False
            continue
        if not in_external_dirs:
            if stripped.startswith("external_dirs:"):
                in_external_dirs = True
                external_indent = indent
                remainder = stripped.split(":", 1)[1].strip()
                if remainder.startswith("[") and remainder.endswith("]"):
                    values.extend(normalize_yaml_scalar(item) for item in remainder[1:-1].split(","))
            continue
        if indent <= external_indent and ":" in stripped:
            in_external_dirs = False
            continue
        if stripped.startswith("- "):
            values.append(normalize_yaml_scalar(stripped[2:]))
    return [value for value in values if value]


def normalize_yaml_scalar(value: str) -> str:
    return strip_quotes(value.strip())


def print_text_report(report: dict[str, Any]) -> None:
    status = "ok" if report["ok"] else "failed"
    print(f"Kingdee host doctor {status}: {report['skillCount']} skills, {len(report['hosts'])} hosts")
    for host in report["hosts"]:
        print(f"- {host['host']}: {host['status']} ({host['reason']})")
    for error in report["errors"]:
        print(f"error: {error}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
