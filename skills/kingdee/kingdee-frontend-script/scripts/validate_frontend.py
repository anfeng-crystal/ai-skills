#!/usr/bin/env python3
"""Deterministic checks for Kingdee frontend JavaScript and custom CSS."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


SUPPORTED_SUFFIXES = {".js": "javascript", ".jsx": "javascript", ".css": "css"}


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    path: str
    line: int


def resolve_user_path(raw_path: str, cwd: Path | None = None) -> Path:
    """Resolve native paths and relative Windows separators without guessing drives."""
    base = cwd or Path.cwd()
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    if candidate.exists():
        return candidate.resolve()
    if os.name != "nt" and "\\" in raw_path and not re.match(r"^[A-Za-z]:\\", raw_path):
        portable = Path(raw_path.replace("\\", "/")).expanduser()
        if not portable.is_absolute():
            portable = base / portable
        if portable.exists():
            return portable.resolve()
    return candidate.resolve()


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def validate_javascript(text: str, path: str) -> list[Issue]:
    issues: list[Issue] = []
    add_pattern = re.compile(r"\baddEventListener\s*\(\s*(['\"])([^'\"]+)\1")
    remove_pattern = re.compile(r"\bremoveEventListener\s*\(\s*(['\"])([^'\"]+)\1")
    added_events = [(match.group(2), match.start()) for match in add_pattern.finditer(text)]
    removed_events = {match.group(2) for match in remove_pattern.finditer(text)}
    reported_events: set[str] = set()
    for event_name, offset in added_events:
        if event_name not in removed_events and event_name not in reported_events:
            issues.append(Issue("JS001", f"事件 {event_name!r} 已注册但未配对移除", path, line_number(text, offset)))
            reported_events.add(event_name)

    interval = re.search(r"\bsetInterval\s*\(", text)
    if interval and not re.search(r"\bclearInterval\s*\(", text):
        issues.append(Issue("JS002", "setInterval 缺少 clearInterval 清理", path, line_number(text, interval.start())))

    append = re.search(r"\b(?:appendChild|insertBefore|append)\s*\(", text)
    if append and not re.search(r"\b(?:removeChild|remove)\s*\(", text):
        issues.append(Issue("JS003", "动态插入的 DOM 缺少卸载删除动作", path, line_number(text, append.start())))

    message_listener = re.search(r"\baddEventListener\s*\(\s*(['\"])message\1", text)
    if message_listener and not re.search(r"\b(?:event|evt|e)\.origin\b|\borigin\s*=", text):
        issues.append(Issue("JS004", "message 监听缺少 origin 白名单证据", path, line_number(text, message_listener.start())))
    return issues


def validate_css(text: str, path: str) -> list[Issue]:
    issues: list[Issue] = []
    for match in re.finditer(r"(?m)^\s*@[A-Za-z_-][A-Za-z0-9_-]*", text):
        issues.append(Issue("CSS001", "自定义样式不支持 at-rule", path, line_number(text, match.start())))

    for match in re.finditer(r"\$(?=[.\[>])", text):
        issues.append(Issue("CSS002", "$ 与后代或子选择器之间必须有空格", path, line_number(text, match.start())))

    for match in re.finditer(r"themeColor", text):
        start, end = match.span()
        quoted = start > 0 and end < len(text) and text[start - 1] == "'" and text[end] == "'"
        if not quoted:
            issues.append(Issue("CSS003", "themeColor 必须使用单引号", path, line_number(text, start)))
    return issues


def iter_inputs(path: Path, forced_kind: str | None) -> Iterable[tuple[Path, str]]:
    if path.is_file():
        kind = forced_kind or SUPPORTED_SUFFIXES.get(path.suffix.lower())
        if not kind:
            raise ValueError(f"cannot infer input kind from suffix: {path.suffix or '<none>'}")
        yield path, kind
        return
    if not path.is_dir():
        raise FileNotFoundError(path)
    for child in sorted(path.rglob("*")):
        if child.is_file() and child.suffix.lower() in SUPPORTED_SUFFIXES:
            yield child, forced_kind or SUPPORTED_SUFFIXES[child.suffix.lower()]


def validate_path(path: Path, forced_kind: str | None = None) -> list[Issue]:
    issues: list[Issue] = []
    for input_path, kind in iter_inputs(path, forced_kind):
        text = input_path.read_text(encoding="utf-8")
        display_path = str(input_path)
        if kind == "javascript":
            issues.extend(validate_javascript(text, display_path))
        elif kind == "css":
            issues.extend(validate_css(text, display_path))
        else:
            raise ValueError(f"unsupported kind: {kind}")
    return issues


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="JavaScript/CSS file or directory")
    parser.add_argument("--kind", choices=("javascript", "css"), help="Override suffix detection")
    parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        target = resolve_user_path(args.path)
        issues = validate_path(target, args.kind)
    except (OSError, UnicodeError, ValueError) as error:
        payload = {"status": "error", "error": str(error)}
        if args.output_format == "json":
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2

    if args.output_format == "json":
        print(json.dumps({"status": "pass" if not issues else "fail", "issues": [asdict(issue) for issue in issues]}, ensure_ascii=False, indent=2))
    elif not issues:
        print("PASS: no deterministic frontend findings")
    else:
        for issue in issues:
            print(f"{issue.path}:{issue.line}: {issue.code} {issue.message}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
