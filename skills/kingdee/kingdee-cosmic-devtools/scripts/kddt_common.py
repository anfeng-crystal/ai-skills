from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


class KddtError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise KddtError(message)


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def now_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(read_text(path))


def save_json(path: Path, data: dict[str, Any]) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def read_properties(path: Path) -> dict[str, str]:
    props: dict[str, str] = {}
    if not path.exists():
        return props
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        props[key.strip()] = value.strip()
    return props


def update_properties(path: Path, updates: dict[str, str], remove_empty: set[str] | None = None) -> None:
    remove_empty = remove_empty or set()
    seen: set[str] = set()
    lines: list[str] = []
    if path.exists():
        source_lines = read_text(path).splitlines()
    else:
        source_lines = []
    for raw in source_lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            lines.append(raw)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updates:
            value = updates[key]
            seen.add(key)
            if key in remove_empty and not value:
                continue
            lines.append(f"{key}={value}")
        else:
            lines.append(raw)
    for key, value in updates.items():
        if key in seen:
            continue
        if key in remove_empty and not value:
            continue
        lines.append(f"{key}={value}")
    write_text(path, "\n".join(lines).rstrip() + "\n")


def detect_project(project: Path) -> dict[str, str]:
    root = project.expanduser().resolve()
    props = read_properties(root / "gradle.properties")
    cosmic_json = load_json(root / "cosmic.json")
    old_props = read_properties(root / "cosmic.properties")
    project_flag = cosmic_json.get("COSMIC_PROJECT_FLAG") or props.get("systemProp.project_flag", "")
    res_url = cosmic_json.get("COSMIC_RES_URL") or props.get("systemProp.res_url", "") or old_props.get("MCServerURL", "")
    return {
        "project_root": str(root),
        "project_name": root.name,
        "template_type": props.get("systemProp.template_type", "multi"),
        "developer_flag": cosmic_json.get("COSMIC_DEVELOPER_FLAG") or props.get("systemProp.developer_flag", ""),
        "project_flag": project_flag,
        "has_project_flag": "true" if bool(project_flag) else "false",
        "cloud_flag": props.get("systemProp.cloud_flag", ""),
        "app_flag": props.get("systemProp.app_flag", ""),
        "cosmic_home": props.get("systemProp.cosmic_home", "") or os.environ.get("COSMIC_HOME", ""),
        "res_url": res_url,
        "kddt_version": props.get("systemProp.kddt_version", ""),
        "is_gradle_project": "true" if (root / "settings.gradle").exists() else "false",
    }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_job(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"job not found: {path}")
    return load_json(path)


def save_job(job: dict[str, Any]) -> None:
    job["updated_at"] = now_text()
    save_json(Path(job["job_file"]), job)
