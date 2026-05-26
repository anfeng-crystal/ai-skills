#!/usr/bin/env python3
"""Synchronize Kingdee skills into supported agent hosts.

The default mode is a read-only dry run. Non-dry-run execution only creates
missing symlinks for non-Hermes hosts; it does not replace existing files,
directories, or links owned by a host.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REGISTRY_PATH = SCRIPT_DIR / "host-registry.json"


@dataclass(frozen=True)
class Host:
    id: str
    label: str
    default: str
    install_mode: str
    target_dir: Path
    config_path: Path | None
    explicit: bool


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    load_dotenv(root / ".env")

    try:
        registry = load_registry()
        hosts = resolve_hosts(registry, args.host, root)
        skills = list_kingdee_skills(root)
        records = build_plan(root, hosts, skills)
        applied = [] if args.dry_run else apply_plan(records)
        report = build_report(root, hosts, skills, records, applied, args.dry_run)
    except UserFacingError as exc:
        report = {
            "ok": False,
            "error": exc.message,
            "code": exc.code,
        }
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(f"error: {exc.message}", file=sys.stderr)
        return exc.exit_code

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_text_report(report)

    return 0 if report["ok"] else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Kingdee skills into agent host skill directories.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Active skills root.")
    parser.add_argument("--host", action="append", default=[], help="Host id or alias to check/sync.")
    parser.add_argument("--dry-run", action="store_true", help="Only report planned changes.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    return parser.parse_args()


class UserFacingError(Exception):
    def __init__(self, message: str, code: str = "error", exit_code: int = 2) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.exit_code = exit_code


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


def load_registry() -> dict[str, Any]:
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UserFacingError(f"host registry not found: {REGISTRY_PATH}", "registry_missing") from exc
    except json.JSONDecodeError as exc:
        raise UserFacingError(f"host registry is invalid JSON: {exc}", "registry_invalid") from exc


def resolve_hosts(registry: dict[str, Any], requested: list[str], root: Path) -> list[Host]:
    home = Path(os.environ.get("AI_HOST_HOME", str(Path.home()))).expanduser()
    entries = registry.get("hosts", [])
    aliases: dict[str, dict[str, Any]] = {}
    for entry in entries:
        aliases[entry["id"]] = entry
        for alias in entry.get("aliases", []):
            aliases[alias] = entry

    if requested:
        resolved_entries = []
        for name in requested:
            entry = aliases.get(name)
            if not entry:
                raise UserFacingError(f"unknown host: {name}", "unknown_host")
            resolved_entries.append(entry)
    else:
        resolved_entries = entries

    seen: set[str] = set()
    hosts: list[Host] = []
    for entry in resolved_entries:
        host_id = entry["id"]
        if host_id in seen:
            continue
        seen.add(host_id)
        hosts.append(
            Host(
                id=host_id,
                label=entry.get("label", host_id),
                default=entry.get("default", "optional"),
                install_mode=entry.get("installMode", "symlink"),
                target_dir=expand_host_path(entry["targetDir"], home, root),
                config_path=expand_host_path(entry["configPath"], home, root) if entry.get("configPath") else None,
                explicit=bool(requested),
            )
        )
    return hosts


def expand_host_path(value: str, home: Path, root: Path) -> Path:
    expanded = value.replace("~", str(home), 1) if value.startswith("~/") or value == "~" else value
    expanded = expanded.replace("${root}", str(root))
    return Path(expanded).expanduser().resolve()


def list_kingdee_skills(root: Path) -> list[dict[str, str]]:
    kingdee_root = root / "skills" / "kingdee"
    if not kingdee_root.is_dir():
        raise UserFacingError(f"Kingdee skills root not found: {kingdee_root}", "source_root_missing")

    skills = []
    for child in sorted(kingdee_root.iterdir()):
        if child.name.startswith(".") or not child.is_dir():
            continue
        if (child / "SKILL.md").is_file():
            skills.append({"id": child.name, "path": str(child.resolve())})
    if not skills:
        raise UserFacingError(f"no Kingdee skills with SKILL.md found under: {kingdee_root}", "source_empty")
    return skills


def build_plan(root: Path, hosts: list[Host], skills: list[dict[str, str]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for host in hosts:
        host_status = inspect_host(host, root)
        if host_status["status"] != "available":
            for skill in skills:
                records.append(
                    {
                        "host": host.id,
                        "skill": skill["id"],
                        "sourcePath": skill["path"],
                        "targetRoot": str(host.target_dir),
                        "targetPath": str(host.target_dir / skill["id"]),
                        "action": "skip",
                        "status": host_status["status"],
                        "reason": host_status["reason"],
                        "wouldChange": False,
                    }
                )
            continue

        if host.install_mode == "external_dirs":
            for skill in skills:
                records.append(
                    {
                        "host": host.id,
                        "skill": skill["id"],
                        "sourcePath": skill["path"],
                        "targetRoot": str(host.target_dir),
                        "targetPath": str(host.target_dir / skill["id"]),
                        "action": "noop",
                        "status": "managed_via_external_dir",
                        "reason": "host_discovers_active_root",
                        "wouldChange": False,
                    }
                )
            continue

        for skill in skills:
            records.append(inspect_symlink_target(host, skill))
    return records


def inspect_host(host: Host, root: Path) -> dict[str, str]:
    if host.install_mode == "external_dirs":
        configured = inspect_external_dirs(root, host.config_path)
        if configured["ok"]:
            return {"status": "available", "reason": "external_dirs_includes_active_root"}
        if host.explicit:
            return {"status": "needs_external_dir_config", "reason": configured["reason"]}
        return {"status": "optional_host_unavailable", "reason": f"optional_host_external_dirs:{configured['reason']}"}

    if host.target_dir.is_dir():
        return {"status": "available", "reason": "target_root_exists"}
    if host.default == "optional" and not host.explicit:
        return {"status": "optional_host_unavailable", "reason": "optional_host_target_root_missing"}
    return {"status": "missing_target_root", "reason": "target_root_missing"}


def inspect_external_dirs(root: Path, config_path: Path | None) -> dict[str, Any]:
    if config_path is None:
        return {"ok": False, "reason": "config_path_missing"}
    try:
        values = parse_external_dirs(config_path.read_text(encoding="utf-8"))
    except OSError:
        return {"ok": False, "reason": "config_unreadable"}

    resolved = {str(Path(value).expanduser().resolve()) for value in values}
    if str(root.resolve()) in resolved:
        return {"ok": True, "reason": "active_root_listed"}
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


def inspect_symlink_target(host: Host, skill: dict[str, str]) -> dict[str, Any]:
    source_path = Path(skill["path"])
    target_path = host.target_dir / skill["id"]
    record = {
        "host": host.id,
        "skill": skill["id"],
        "sourcePath": str(source_path),
        "targetRoot": str(host.target_dir),
        "targetPath": str(target_path),
        "wouldChange": False,
    }

    try:
        stat = target_path.lstat()
    except FileNotFoundError:
        return {**record, "action": "create_link", "status": "planned", "reason": "target_missing", "wouldChange": True}

    if target_path.is_symlink():
        link_raw = os.readlink(target_path)
        link_resolved = (target_path.parent / link_raw).resolve()
        if link_resolved == source_path:
            return {**record, "action": "noop", "status": "already_linked", "reason": "link_matches_source"}
        return {
            **record,
            "action": "skip",
            "status": "external_symlink_conflict",
            "reason": "existing_symlink_points_elsewhere",
            "targetLinkResolved": str(link_resolved),
        }

    kind = "directory" if target_path.is_dir() else "file"
    return {**record, "action": "skip", "status": "real_path_conflict", "reason": f"real_{kind}_exists"}


def apply_plan(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    applied: list[dict[str, str]] = []
    for record in records:
        if record["action"] != "create_link" or record["status"] != "planned":
            continue
        target = Path(record["targetPath"])
        target.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(record["sourcePath"], target, target_is_directory=True)
        record["action"] = "noop"
        record["status"] = "applied"
        record["reason"] = "created_symlink"
        record["wouldChange"] = False
        applied.append({"host": record["host"], "skill": record["skill"], "targetPath": record["targetPath"]})
    return applied


def build_report(
    root: Path,
    hosts: list[Host],
    skills: list[dict[str, str]],
    records: list[dict[str, Any]],
    applied: list[dict[str, str]],
    dry_run: bool,
) -> dict[str, Any]:
    hard_statuses = {"missing_target_root", "needs_external_dir_config", "real_path_conflict", "external_symlink_conflict"}
    errors = [
        f"{record['host']}:{record['skill']}:{record['status']}:{record['reason']}"
        for record in records
        if record["status"] in hard_statuses
    ]
    summary: dict[str, Any] = {"total": len(records), "wouldChange": 0, "byStatus": {}, "byAction": {}}
    for record in records:
        summary["wouldChange"] += 1 if record.get("wouldChange") else 0
        summary["byStatus"][record["status"]] = summary["byStatus"].get(record["status"], 0) + 1
        summary["byAction"][record["action"]] = summary["byAction"].get(record["action"], 0) + 1

    return {
        "ok": not errors,
        "dryRun": dry_run,
        "root": str(root),
        "hosts": [host.id for host in hosts],
        "skillCount": len(skills),
        "summary": summary,
        "errors": errors,
        "applied": applied,
        "records": records,
    }


def print_text_report(report: dict[str, Any]) -> None:
    status = "ok" if report["ok"] else "failed"
    print(f"Kingdee host sync {status}: {report['summary']['total']} records")
    print(f"wouldChange={report['summary']['wouldChange']} dryRun={report['dryRun']}")
    for key, value in sorted(report["summary"]["byStatus"].items()):
        print(f"- {key}: {value}")
    for error in report["errors"]:
        print(f"error: {error}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
