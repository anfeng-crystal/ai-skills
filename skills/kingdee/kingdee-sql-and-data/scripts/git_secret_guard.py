#!/usr/bin/env python3
"""Read-only guard for tracked KSQL config and likely committed secrets."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ASSIGNMENT_RE = re.compile(
    r"""(?ix)
    \b(password|passwd|pwd|token|secret|appsecret|access[_-]?key|private[_-]?key)\b
    \s*[:=]\s*
    ["']?([^"'\s,;#]+)
    """
)
EMBEDDED_SECRET_RE = re.compile(r"(?i)(?:[?&;]|\b)(password|token|secret)=([^&;\s#]+)")
TEXT_SUFFIXES = {
    ".env",
    ".ini",
    ".properties",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".gradle",
    ".java",
    ".py",
    ".js",
    ".ts",
    ".sh",
    ".ps1",
}
PLACEHOLDER_VALUES = {
    "",
    "change_me",
    "changeme",
    "example",
    "example_user",
    "example_password",
    "password",
    "your-password",
    "your_password",
    "todo",
    "xxx",
    "xxxx",
    "null",
    "none",
}


def run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def tracked_files(repo: Path) -> list[str]:
    proc = run_git(repo, ["ls-files", "-z"])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git ls-files failed")
    return [item for item in proc.stdout.split("\0") if item]


def is_scannable(path: Path) -> bool:
    if path.name.endswith(".d.ts"):
        return False
    if path.name == ".env" or path.suffix.lower() in TEXT_SUFFIXES:
        return True
    return path.name.lower() == "config.ini"


def looks_real_secret(value: str) -> bool:
    normalized = value.strip().strip("\"'").lower()
    if normalized in PLACEHOLDER_VALUES:
        return False
    if normalized.startswith("env:"):
        return False
    if normalized.startswith("${") or normalized.startswith("$"):
        return False
    if normalized.startswith("<") and normalized.endswith(">"):
        return False
    if "(" in normalized or ")" in normalized:
        return False
    return len(normalized) >= 4


def scan_file(repo: Path, rel_path: str) -> list[dict]:
    path = repo / rel_path
    risks: list[dict] = []
    if path.name.lower() == "config.ini":
        risks.append({"type": "tracked_config_ini", "file": rel_path})
    if not is_scannable(path):
        return risks

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        risks.append({"type": "read_error", "file": rel_path, "message": str(exc)})
        return risks

    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//", "--")):
            continue
        matches = list(ASSIGNMENT_RE.finditer(stripped))
        matches.extend(EMBEDDED_SECRET_RE.finditer(stripped))
        seen_keys: set[tuple[str, str]] = set()
        for match in matches:
            key, value = match.group(1), match.group(2)
            risk_key = (key.lower(), value)
            if risk_key not in seen_keys and looks_real_secret(value):
                seen_keys.add(risk_key)
                risks.append({
                    "type": "suspected_secret",
                    "file": rel_path,
                    "line": line_no,
                    "key": key,
                })
    return risks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only git secret/config guard.")
    parser.add_argument("--repo", default=".", help="Git repository to inspect.")
    parser.add_argument("--json", action="store_true", help="Output JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"--repo is not a directory: {repo}", file=sys.stderr)
        return 2

    proc = run_git(repo, ["rev-parse", "--show-toplevel"])
    if proc.returncode != 0:
        print(proc.stderr.strip() or f"not a git repo: {repo}", file=sys.stderr)
        return 2
    root = Path(proc.stdout.strip()).resolve()

    try:
        files = tracked_files(root)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    risks: list[dict] = []
    for rel_path in files:
        risks.extend(scan_file(root, rel_path))

    result = {"repo": str(root), "risk_count": len(risks), "risks": risks}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif risks:
        for risk in risks:
            location = risk["file"]
            if "line" in risk:
                location += f":{risk['line']}"
            print(f"{risk['type']}: {location}")
    else:
        print("ok: no tracked config.ini or likely secrets found")
    return 1 if risks else 0


if __name__ == "__main__":
    raise SystemExit(main())
