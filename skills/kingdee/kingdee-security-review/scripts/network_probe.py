#!/usr/bin/env python3
"""Scoped network reachability probe. Defaults to no connection."""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
import urllib.parse
import urllib.request

import scope_check


SENSITIVE_HEADERS = {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key"}


def redact_headers(headers: dict) -> dict:
    return {key: ("<redacted>" if key.lower() in SENSITIVE_HEADERS else value) for key, value in headers.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe a Kingdee target only after scope approval. Defaults to dry-run.")
    parser.add_argument("--mode", choices=["audit", "audit-readonly", "verify", "redteam-lite"], default="audit")
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--scope", choices=["local", "dev", "test", "staging", "prod", "unknown"], default="unknown")
    parser.add_argument("--allow-prod", action="store_true")
    parser.add_argument("--allow-unknown", action="store_true")
    parser.add_argument("--reason", default="")
    parser.add_argument("--connect", action="store_true", help="Actually open a connection and send HEAD.")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--json", action="store_true")
    return parser


def probe(target_url: str, timeout: float) -> dict:
    parsed = urllib.parse.urlparse(target_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not host:
        return {"ok": False, "error": "target URL has no host"}

    result = {"host": host, "port": port, "addresses": []}
    try:
        result["addresses"] = sorted({item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
    except Exception as exc:
        result["dns_error"] = scope_check.redact_text(str(exc))

    req = urllib.request.Request(target_url, method="HEAD", headers={"User-Agent": "kingdee-security-review-probe/1.0"})
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            result.update({"ok": True, "status": resp.status, "headers": redact_headers(dict(resp.headers.items()))})
    except Exception as exc:
        result.update({"ok": False, "error": scope_check.redact_text(str(exc))})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    decision = scope_check.decide(args)
    output = {"scope": scope_check.asdict(decision), "dry_run": not args.connect}

    if not decision.allowed:
        output["result"] = "BLOCKED_BY_SCOPE"
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 2

    if args.mode == "audit" and args.connect:
        output["result"] = "BLOCKED_BY_MODE"
        output["reason"] = "use audit-readonly with a complete target contract for a read-only connection"
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 2

    if not args.connect:
        output["result"] = "DRY_RUN_ONLY"
        output["target_url"] = scope_check.redact_url(args.target_url)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    output["probe"] = probe(args.target_url, args.timeout)
    output["result"] = "PROBED"
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["probe"].get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
