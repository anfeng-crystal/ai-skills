#!/usr/bin/env python3
"""Deterministically redact sensitive runtime evidence without external packages."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path
from typing import Any


REDACTED = "[REDACTED]"
SENSITIVE_KEY_PARTS = {
    "password",
    "passwd",
    "secret",
    "token",
    "cookie",
    "authorization",
    "csrf",
    "session",
    "tenant",
    "account",
    "user",
    "userid",
    "username",
    "person",
    "employee",
    "mobile",
    "phone",
    "email",
    "ipaddress",
    "clientip",
    "remoteip",
    "host",
    "jdbc",
    "connectionstring",
}
SQL_KEYS = {"sql", "statement", "query", "ksql"}
SQL_PARAM_KEYS = {
    "param",
    "params",
    "parameter",
    "parameters",
    "queryparams",
    "bind",
    "binds",
    "binding",
    "bindings",
    "args",
    "arguments",
}

IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
IPV6 = re.compile(r"(?i)(?<![\w:])(?=[0-9a-f:]*:[0-9a-f:]*:)[0-9a-f:]+(?![\w:])")
EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
URL_HOST = re.compile(r"(?i)\b(https?://)([^/\s]+)")
SECRET_PAIR = re.compile(
    r"(?i)([\"']?(?:password|passwd|secret|token|cookie|authorization|csrf|session)[\"']?)(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
)
IDENTIFIER_PAIR = re.compile(
    r"(?i)([\"']?(?:tenant(?:id)?|account(?:id)?|user(?:id|name)?|person(?:id)?|employee(?:id)?|mobile|phone|email|clientip|remoteip|host(?:name)?)[\"']?)(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
)
SQL_PARAMS = re.compile(
    r"(?i)([\"']?(?:params?|parameters?|queryparams?|bind(?:ings?)?|args?|arguments?)[\"']?)(\s*[:=]\s*)(\[[^\]\r\n]*\]|\{[^}\r\n]*\}|[^\s;}]+)"
)
SQL_STRING = re.compile(r"'(?:''|[^'])*'")
SQL_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")
SQL_WHITESPACE = re.compile(r"\s+")
SQL_START = re.compile(r"(?i)\b(select|insert|update|delete|merge)\b")


def normalized_key(key: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def key_is_sensitive(key: object) -> bool:
    normalized = normalized_key(key)
    return normalized == "ip" or any(part in normalized for part in SENSITIVE_KEY_PARTS)


def sanitize_sql(value: str) -> str:
    sanitized = SQL_STRING.sub("?", value)
    sanitized = SQL_NUMBER.sub("?", sanitized)
    sanitized = SQL_PARAMS.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", sanitized
    )
    return SQL_WHITESPACE.sub(" ", sanitized).strip()


def redact_text(value: str) -> str:
    value = URL_HOST.sub(lambda match: f"{match.group(1)}[REDACTED_HOST]", value)
    value = EMAIL.sub("[REDACTED_EMAIL]", value)
    value = IPV4.sub("[REDACTED_IP]", value)
    value = IPV6.sub(redact_ipv6, value)
    value = SECRET_PAIR.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", value
    )
    value = IDENTIFIER_PAIR.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", value
    )
    value = SQL_PARAMS.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", value
    )
    sql_match = SQL_START.search(value)
    if sql_match:
        value = value[: sql_match.start()] + sanitize_sql(value[sql_match.start() :])
    return value


def redact_ipv6(match: re.Match[str]) -> str:
    try:
        parsed = ipaddress.ip_address(match.group(0))
    except ValueError:
        return match.group(0)
    return "[REDACTED_IP]" if parsed.version == 6 else match.group(0)


def redact_value(value: Any, key: object | None = None) -> Any:
    normalized = normalized_key(key) if key is not None else ""
    if key is not None and key_is_sensitive(key):
        return REDACTED
    if normalized in SQL_PARAM_KEYS:
        return REDACTED
    if isinstance(value, dict):
        return {str(item_key): redact_value(item_value, item_key) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        if normalized in SQL_KEYS:
            return sanitize_sql(value)
        return redact_text(value)
    return value


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Redact sensitive fields from a UTF-8 JSON artifact.")
    parser.add_argument("--input", required=True, help="Input JSON path.")
    parser.add_argument("--output", help="Optional output JSON path; omit to print stdout.")
    args = parser.parse_args()

    try:
        redacted = redact_value(load_json(Path(args.input).expanduser().resolve()))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"cannot redact input: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(redacted, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
