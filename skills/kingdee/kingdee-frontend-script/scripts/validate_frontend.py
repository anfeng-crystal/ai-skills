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

from javascript_view import EventCall, javascript_code_view


SUPPORTED_SUFFIXES = {".js": "javascript", ".jsx": "javascript", ".css": "css"}


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    path: str
    line: int


@dataclass(frozen=True)
class AnalysisWarning:
    path: str
    line: int
    reason: str


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


def raw_event_calls(text: str) -> list[EventCall]:
    pattern = re.compile(r"\b(addEventListener|removeEventListener)\s*\(\s*(['\"])([^'\"]+)\2")
    return [EventCall(match.group(1), match.group(3), match.start()) for match in pattern.finditer(text)]


def javascript_issues(text: str, path: str, events: list[EventCall]) -> list[Issue]:
    issues: list[Issue] = []
    added_events = [(event.name, event.offset) for event in events if event.operation == 'addEventListener']
    removed_events = {event.name for event in events if event.operation == 'removeEventListener'}
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

    message_listener = next((offset for name, offset in added_events if name == 'message'), None)
    if message_listener is not None and not re.search(r"\b(?:event|evt|e)\.origin\b|\borigin\s*=", text):
        issues.append(Issue("JS004", "message 监听缺少 origin 白名单证据", path, line_number(text, message_listener)))
    return issues


def validate_javascript(text: str, path: str, *, warnings: list[AnalysisWarning] | None = None) -> list[Issue]:
    view = javascript_code_view(text)
    issues = javascript_issues(view.text, path, view.events)
    if view.limitations:
        # Preserve both scanned-code hints and the previous raw-text hints. Neither
        # is conclusive across an unclassified span; the CLI must expose partial.
        issues = list(dict.fromkeys(issues + javascript_issues(text, path, raw_event_calls(text))))
        if warnings is not None:
            warnings.extend(AnalysisWarning(path, line_number(text, item.offset), item.reason)
                            for item in view.limitations)
    return issues


def mask_css_comments(text: str) -> str:
    """Mask comments, respecting string/escape/url tokens and source offsets."""
    def consume_escape(start: int) -> tuple[str, int]:
        cursor = start + 1
        if cursor == len(text):
            return "\ufffd", cursor
        if text[cursor] in "0123456789abcdefABCDEF":
            end = cursor
            while end < min(cursor + 6, len(text)) and text[end] in "0123456789abcdefABCDEF":
                end += 1
            value = int(text[cursor:end], 16)
            char = chr(value) if 0 < value <= 0x10FFFF and not 0xD800 <= value <= 0xDFFF else "\ufffd"
            if end < len(text) and text[end] in " \t\n\r\f":
                end += 2 if text.startswith("\r\n", end) else 1
            return char, end
        return text[cursor], cursor + 1

    masked = list(text)
    quote: str | None = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            end = len(text) if end == -1 else end + 2
            for offset in range(index, end):
                if text[offset] not in "\r\n":
                    masked[offset] = " "
            index = end
            continue
        elif char.isalnum() or char in "_-\\" or ord(char) >= 128:
            # Consume a name as a unit: escaped quotes/slashes are not delimiters.
            name: list[str] = []
            cursor = index
            while cursor < len(text):
                current = text[cursor]
                if current == "\\" and cursor + 1 < len(text) and text[cursor + 1] not in "\r\n\f":
                    decoded, cursor = consume_escape(cursor)
                    name.append(decoded)
                elif current.isalnum() or current in "_-" or ord(current) >= 128:
                    name.append(current)
                    cursor += 1
                else:
                    break
            if "".join(name).lower() == "url" and cursor < len(text) and text[cursor] == "(":
                cursor += 1
                while cursor < len(text) and text[cursor] in " \t\r\n\f":
                    cursor += 1
                if cursor < len(text) and text[cursor] not in "\"'":
                    # Inside an unquoted URL, /* is URL content, not a comment.
                    while cursor < len(text):
                        if text[cursor] == "\\":
                            _, cursor = consume_escape(cursor)
                        elif text[cursor] == ")":
                            cursor += 1
                            break
                        else:
                            cursor += 1
            index = max(cursor, index + 1)
            continue
        index += 1
    return "".join(masked)


def validate_css(text: str, path: str) -> list[Issue]:
    text = mask_css_comments(text)
    issues: list[Issue] = []
    for match in re.finditer(r"(?m)^[^\S\r\n]*@[A-Za-z_-][A-Za-z0-9_-]*", text):
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


def validate_path(path: Path, forced_kind: str | None = None, *, warnings: list[AnalysisWarning] | None = None) -> list[Issue]:
    issues: list[Issue] = []
    for input_path, kind in iter_inputs(path, forced_kind):
        text = input_path.read_text(encoding="utf-8")
        display_path = str(input_path)
        if kind == "javascript":
            issues.extend(validate_javascript(text, display_path, warnings=warnings))
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
        warnings: list[AnalysisWarning] = []
        issues = validate_path(target, args.kind, warnings=warnings)
    except (OSError, UnicodeError, ValueError) as error:
        payload = {"status": "error", "error": str(error)}
        if args.output_format == "json":
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2

    if args.output_format == "json":
        payload = {"status": "fail" if issues else "partial" if warnings else "pass", "issues": [asdict(issue) for issue in issues]}
        if warnings:
            payload.update(analysis="partial", warnings=[asdict(item) for item in warnings])
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif warnings:
        for issue in issues:
            print(f"{issue.path}:{issue.line}: {issue.code} {issue.message}")
        for item in warnings:
            print(f"{item.path}:{item.line}: PARTIAL: {item.reason}")
    elif not issues:
        print("PASS: no deterministic frontend findings")
    else:
        for issue in issues:
            print(f"{issue.path}:{issue.line}: {issue.code} {issue.message}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
