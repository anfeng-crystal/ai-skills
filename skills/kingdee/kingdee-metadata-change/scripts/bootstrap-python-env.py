#!/usr/bin/env python3
"""Prepare a local Python runtime for the metadata authoring skill."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path


REQUIRED = {"psycopg2": "psycopg2-binary"}


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def venv_dir() -> Path:
    configured = os.environ.get("KINGDEE_METADATA_CHANGE_VENV")
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        cache_root = Path(os.environ["LOCALAPPDATA"]) / "Codex"
    elif sys.platform == "darwin":
        cache_root = Path.home() / "Library" / "Caches" / "Codex"
    else:
        cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "codex"
    return cache_root / "kingdee-metadata-change" / "python-env"


def python_path(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def usable(python: Path) -> bool:
    if not python.exists():
        return False
    code = ";".join(f"import {name}" for name in REQUIRED)
    return subprocess.run([str(python), "-c", code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def ensure_python() -> Path:
    current = Path(sys.executable).resolve()
    if usable(current):
        return current
    root = venv_dir()
    python = python_path(root)
    if not python.exists():
        root.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(root)
    if not usable(python):
        command = [str(python), "-m", "pip", "install", "--disable-pip-version-check"]
        index = os.environ.get("KINGDEE_METADATA_CHANGE_PIP_INDEX_URL")
        if index:
            command.extend(["--index-url", index])
        command.extend(REQUIRED.values())
        subprocess.run(command, check=True)
    if not usable(python):
        raise RuntimeError("依赖安装后 psycopg2 仍不可用")
    return python


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    try:
        python = ensure_python()
    except Exception as exc:
        print(f"[ERROR] Python 环境准备失败: {exc}", file=sys.stderr)
        return 1
    if not command:
        print(python)
        return 0
    return subprocess.run([str(python), *command], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
