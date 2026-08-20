#!/usr/bin/env python3
"""Run one task-scoped HTTP verification request with redacted evidence."""

import argparse
import hashlib
import ipaddress
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


READ_ONLY_METHODS = {"GET", "HEAD", "OPTIONS"}
ALL_METHODS = READ_ONLY_METHODS | {"POST", "PUT", "PATCH", "DELETE"}
MODES = {"local", "dev-test", "prod-readonly", "approved-write"}
SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-csrf-token",
    "csrf-token",
    "proxy-authorization",
}
SENSITIVE_HEADER_PARTS = {
    "authorization",
    "cookie",
    "token",
    "csrf",
    "session",
    "secret",
    "password",
    "api-key",
    "apikey",
}
SECRET_TEXT = re.compile(
    r"(?i)([\"']?(?:password|passwd|token|cookie|authorization|secret|session|csrf)[\"']?)(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
)
IDENTIFIER_TEXT = re.compile(
    r"(?i)([\"']?(?:tenant(?:id)?|account(?:id)?|user(?:id|name)?|person(?:id)?|clientip|remoteip)[\"']?)(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
)
SQL_PARAMS = re.compile(
    r"(?i)([\"']?(?:params?|parameters?|bind(?:ings?)?|args?|arguments?)[\"']?)(\s*[:=]\s*)(\[[^\]\r\n]*\]|\{[^}\r\n]*\}|[^\s;}]+)"
)
URL_HOST = re.compile(r"(?i)\b(https?://)([^/\s]+)")
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
SQL_START = re.compile(r"(?i)\b(select|insert|update|delete|merge)\b")
SQL_STRING = re.compile(r"'(?:''|[^'])*'")
SQL_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def header_is_sensitive(name: str) -> bool:
    normalized = name.strip().lower()
    return normalized in SENSITIVE_HEADER_NAMES or any(part in normalized for part in SENSITIVE_HEADER_PARTS)


def parse_headers(values: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for value in values:
        if ":" not in value:
            raise ValueError(f"invalid header, expected Name: value: {value}")
        name, raw = value.split(":", 1)
        name = name.strip()
        if not name:
            raise ValueError("header name cannot be empty")
        if header_is_sensitive(name):
            raise ValueError(f"sensitive header {name!r} must use --header-env")
        headers[name] = raw.strip()
    return headers


def parse_env_headers(values: list[str], environ: dict[str, str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("invalid env header, expected Header=ENV_NAME")
        name, env_name = (part.strip() for part in value.split("=", 1))
        if not name or not env_name:
            raise ValueError("header name and environment variable are required")
        if env_name not in environ:
            raise ValueError(f"configured credential environment variable is missing: {env_name}")
        headers[name] = environ[env_name]
    return headers


def redact_text(value: str, secret_values: tuple[str, ...] = ()) -> str:
    for secret in sorted((item for item in secret_values if item), key=len, reverse=True):
        value = value.replace(secret, "[REDACTED]")
    value = URL_HOST.sub(lambda match: f"{match.group(1)}[REDACTED_HOST]", value)
    value = IPV4.sub("[REDACTED_IP]", value)
    value = SECRET_TEXT.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value
    )
    value = IDENTIFIER_TEXT.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value
    )
    value = SQL_PARAMS.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value
    )
    sql_match = SQL_START.search(value)
    if sql_match:
        sql = SQL_STRING.sub("?", value[sql_match.start() :])
        sql = SQL_NUMBER.sub("?", sql)
        value = value[: sql_match.start()] + sql
    return value


def redact_headers(headers: dict[str, str], secret_values: tuple[str, ...] = ()) -> dict[str, str]:
    return {
        name: "[REDACTED]"
        if header_is_sensitive(name)
        else redact_text(value, secret_values)
        for name, value in headers.items()
    }


def sanitized_url(url: str) -> str:
    parsed = urlparse(url)
    query = "[REDACTED_QUERY]" if parsed.query else ""
    return urlunparse((parsed.scheme, "[REDACTED_HOST]", parsed.path, "", query, ""))


def is_loopback(hostname: str | None) -> bool:
    if not hostname:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def validate_contract(
    *,
    url: str,
    mode: str,
    method: str,
    scope_id: str,
    target_alias: str,
    approval_ref: str | None,
    rollback_ref: str | None,
    expected_evidence: str,
    allowed_path_prefixes: list[str],
    request_limit: int,
    has_payload: bool,
) -> dict:
    parsed = urlparse(url)
    errors: list[str] = []
    if mode not in MODES:
        errors.append(f"unsupported mode: {mode}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append("url must be an absolute http(s) URL")
    if not scope_id.strip():
        errors.append("scope id is required")
    if not target_alias.strip() or "://" in target_alias:
        errors.append("target alias must be a non-URL environment label")
    if not expected_evidence.strip():
        errors.append("expected evidence is required")
    if request_limit != 1:
        errors.append("this helper performs exactly one request; request limit must be 1")
    if mode == "local" and not is_loopback(parsed.hostname):
        errors.append("local mode only permits loopback targets")
    if mode in {"local", "dev-test", "prod-readonly"} and method not in READ_ONLY_METHODS:
        errors.append(f"{mode} only permits GET, HEAD, or OPTIONS")
    if mode in {"prod-readonly", "approved-write"} and not approval_ref:
        errors.append(f"{mode} requires an approval reference")
    if mode == "approved-write":
        if not rollback_ref:
            errors.append("approved-write requires a rollback reference")
        if not allowed_path_prefixes:
            errors.append("approved-write requires at least one allowed path prefix")
        elif not any(parsed.path.startswith(prefix) for prefix in allowed_path_prefixes):
            errors.append("request path is outside the approved path prefixes")
        if method in {"POST", "PUT", "PATCH"} and not has_payload:
            errors.append(f"{method} requires an explicit --body-file payload source")
    elif allowed_path_prefixes:
        errors.append("allowed path prefixes are only valid in approved-write mode")
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "valid": True,
        "mode": mode,
        "scopeId": scope_id,
        "targetAlias": target_alias,
        "target": sanitized_url(url),
        "method": method,
        "approvalRef": approval_ref,
        "rollbackRef": rollback_ref,
        "expectedEvidence": redact_text(expected_evidence),
        "requestLimit": request_limit,
        "allowedPathPrefixes": allowed_path_prefixes,
    }


def probe(
    url: str,
    method: str,
    headers: dict[str, str],
    data: bytes | None,
    timeout: float,
    preview_bytes: int,
    secret_values: tuple[str, ...] = (),
) -> dict:
    request = Request(url, method=method, headers=headers, data=data)
    opener = build_opener(NoRedirect())
    started = time.monotonic()
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(preview_bytes)
            return {
                "ok": True,
                "status": response.status,
                "reason": str(response.reason),
                "elapsedMs": round((time.monotonic() - started) * 1000, 2),
                "headers": redact_headers(dict(response.headers.items()), secret_values),
                "preview": redact_text(body.decode("utf-8", errors="replace"), secret_values),
            }
    except HTTPError as exc:
        body = exc.read(preview_bytes)
        return {
            "ok": False,
            "status": exc.code,
            "reason": str(exc.reason),
            "elapsedMs": round((time.monotonic() - started) * 1000, 2),
            "headers": redact_headers(dict(exc.headers.items()) if exc.headers else {}, secret_values),
            "preview": redact_text(body.decode("utf-8", errors="replace"), secret_values),
        }
    except URLError as exc:
        return {
            "ok": False,
            "error": type(exc.reason).__name__,
            "elapsedMs": round((time.monotonic() - started) * 1000, 2),
        }


def load_payload(path_value: str | None) -> tuple[bytes | None, str | None]:
    if not path_value:
        return None, None
    path = Path(path_value).expanduser().resolve()
    data = path.read_bytes()
    if len(data) > 1024 * 1024:
        raise ValueError("payload exceeds the 1 MiB task helper limit")
    return data, hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one task-scoped Kingdee runtime probe.")
    parser.add_argument("--mode", required=True, choices=sorted(MODES))
    parser.add_argument("--scope-id", required=True)
    parser.add_argument("--target-alias", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--method", default="GET", choices=sorted(ALL_METHODS))
    parser.add_argument("--approval-ref")
    parser.add_argument("--rollback-ref")
    parser.add_argument("--expected-evidence", required=True)
    parser.add_argument("--allow-path-prefix", action="append", default=[])
    parser.add_argument("--request-limit", type=int, default=1)
    parser.add_argument("--header", action="append", default=[])
    parser.add_argument("--header-env", action="append", default=[])
    parser.add_argument("--body-file")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--expect-status", type=int)
    parser.add_argument("--preview-bytes", type=int, default=4096)
    parser.add_argument("--output")
    parser.add_argument("--force", action="store_true", help="Overwrite only the explicit output file.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        headers = parse_headers(args.header)
        env_headers = parse_env_headers(args.header_env, os.environ)
        headers.update(env_headers)
        secret_values = tuple(env_headers.values())
        payload, payload_sha256 = load_payload(args.body_file)
        contract = validate_contract(
            url=args.url,
            mode=args.mode,
            method=args.method,
            scope_id=args.scope_id,
            target_alias=args.target_alias,
            approval_ref=args.approval_ref,
            rollback_ref=args.rollback_ref,
            expected_evidence=args.expected_evidence,
            allowed_path_prefixes=args.allow_path_prefix,
            request_limit=args.request_limit,
            has_payload=payload is not None,
        )
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    result = {"contract": contract, "dryRun": args.dry_run}
    if payload_sha256:
        result["payload"] = {"sha256": payload_sha256, "bytes": len(payload or b"")}
    if not args.dry_run:
        result["response"] = probe(
            args.url,
            args.method,
            headers,
            payload,
            args.timeout,
            args.preview_bytes,
            secret_values,
        )
        if args.expect_status is not None:
            result["expectedStatus"] = args.expect_status
            result["statusMatched"] = result["response"].get("status") == args.expect_status

    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output).expanduser().resolve()
        body_path = Path(args.body_file).expanduser().resolve() if args.body_file else None
        if output == body_path:
            print("output must not overwrite the request payload", file=sys.stderr)
            return 2
        if output.exists() and not args.force:
            print("output exists; pass --force only when overwrite is explicitly requested", file=sys.stderr)
            return 2
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    print(serialized)

    if args.dry_run:
        return 0
    if args.expect_status is not None and not result.get("statusMatched"):
        return 1
    return 0 if result["response"].get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
