#!/usr/bin/env python3
"""
Ensure the Python runtime needed by Kingdee metadata scripts.

The script creates a local virtual environment when the current interpreter is
missing required packages, installs the missing dependencies, then optionally
runs the requested metadata script with the prepared interpreter.
"""

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


REQUIRED_PACKAGES = {
    "psycopg2": "psycopg2-binary",
}


DEFAULT_INDEX_URLS = [
    None,
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.aliyun.com/pypi/simple",
]


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_venv_dir() -> Path:
    raw_path = os.environ.get("KINGDEE_METADATA_ANALYZER_VENV")
    return Path(raw_path).expanduser().resolve() if raw_path else skill_root() / ".venv"


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def python_is_runnable(python: Path) -> bool:
    if not python.exists():
        return False
    result = subprocess.run(
        [str(python), "--version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def importable(python: Path, modules: Iterable[str]) -> bool:
    if not python_is_runnable(python):
        return False
    code = "import " + ", ".join(modules)
    result = subprocess.run(
        [str(python), "-c", code],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def create_venv(venv_dir: Path) -> Path:
    python = venv_python(venv_dir)
    if python.exists() and not python_is_runnable(python):
        shutil.rmtree(venv_dir)
    if not venv_python(venv_dir).exists():
        venv_dir.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(str(venv_dir))
    return venv_python(venv_dir)


def configured_index_urls() -> List[Optional[str]]:
    raw = os.environ.get("KINGDEE_METADATA_ANALYZER_PIP_INDEX_URLS") or os.environ.get(
        "KINGDEE_METADATA_ANALYZER_PIP_INDEX_URL"
    )
    if not raw:
        return DEFAULT_INDEX_URLS
    values = [item.strip() for item in raw.replace(";", ",").split(",")]
    urls = [item for item in values if item]
    return urls or DEFAULT_INDEX_URLS


def install_requirements(python: Path, packages: Sequence[str]) -> None:
    last_error: subprocess.CalledProcessError | None = None
    for index_url in configured_index_urls():
        command = [str(python), "-m", "pip", "install", "--disable-pip-version-check"]
        if index_url:
            command.extend(["--index-url", index_url])
        command.extend(packages)
        result = subprocess.run(command, check=False)
        if result.returncode == 0:
            return
        last_error = subprocess.CalledProcessError(result.returncode, command)
    if last_error:
        raise last_error
    raise RuntimeError("No pip index URLs are configured.")


def ensure_python() -> Path:
    modules = list(REQUIRED_PACKAGES)
    current = Path(sys.executable).resolve()
    if importable(current, modules):
        return current

    prepared = create_venv(default_venv_dir())
    if not importable(prepared, modules):
        install_requirements(prepared, list(REQUIRED_PACKAGES.values()))
    if not importable(prepared, modules):
        raise RuntimeError("Python dependencies are still unavailable after installation.")
    return prepared


def run_with_python(python: Path, command: Sequence[str]) -> int:
    if not command:
        print(str(python))
        return 0
    return subprocess.run([str(python), *command], check=False).returncode


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Create or reuse a local Python environment for Kingdee metadata scripts."
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Optional command to run with the prepared Python, usually after --.",
    )
    args = parser.parse_args(argv)

    command = args.command
    if command and command[0] == "--":
        command = command[1:]

    try:
        python = ensure_python()
    except Exception as exc:
        print(f"[ERROR] Python environment bootstrap failed: {exc}", file=sys.stderr)
        return 1
    return run_with_python(python, command)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
