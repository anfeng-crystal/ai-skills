#!/usr/bin/env python3
"""Dry-run and explicitly scoped POC runner for Kingdee security verification."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import scope_check


SAFE_PAYLOADS = {
    "xss": ["plain-test", "<b>test</b>"],
    "sqli": ["1", "1'"],
    "ssrf": ["http://127.0.0.1/"],
    "path-traversal": ["../test.txt"],
    "xxe": ["<!-- xxe marker only; no external entity -->"],
    "rce": ["echo-test"],
}


def load_poc(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("POC file must contain a JSON object")
    return data


def build_request(target_url: str, poc: dict) -> urllib.request.Request:
    base = target_url.rstrip("/") + "/"
    path = str(poc.get("path", "")).lstrip("/")
    url = urllib.parse.urljoin(base, path)
    params = poc.get("params") or {}
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        separator = "&" if urllib.parse.urlparse(url).query else "?"
        url = url + separator + query

    method = str(poc.get("method", "GET")).upper()
    headers = {str(k): str(v) for k, v in (poc.get("headers") or {}).items()}
    body = poc.get("body")
    data = None
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers.setdefault("Content-Type", poc.get("content_type") or "application/json")
        else:
            data = str(body).encode("utf-8")
            if poc.get("content_type"):
                headers.setdefault("Content-Type", str(poc["content_type"]))
    return urllib.request.Request(url, data=data, headers=headers, method=method)


def run_request(req: urllib.request.Request, timeout: float) -> dict:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(4096)
            return {
                "ok": True,
                "status": resp.status,
                "headers": dict(resp.headers.items()),
                "body_preview": body.decode("utf-8", errors="replace"),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(4096)
        return {
            "ok": False,
            "status": exc.code,
            "headers": dict(exc.headers.items()),
            "body_preview": body.decode("utf-8", errors="replace"),
            "error": str(exc),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a scoped Kingdee POC request. Defaults to dry-run.")
    parser.add_argument("--mode", choices=["audit", "verify", "redteam-lite"], default="audit", help="Work mode. Active execution requires verify or redteam-lite.")
    parser.add_argument("--target-url", default="", help="Target base URL.")
    parser.add_argument("--scope", choices=["local", "dev", "test", "staging", "prod", "unknown"], default="unknown", help="Declared target scope.")
    parser.add_argument("--allow-prod", action="store_true", help="Allow production only with explicit authorization.")
    parser.add_argument("--allow-unknown", action="store_true", help="Allow unknown scope only with explicit authorization.")
    parser.add_argument("--reason", default="", help="Authorization reason for prod/unknown scope.")
    parser.add_argument("--poc-file", help="JSON POC specification file.")
    parser.add_argument("--payloads", choices=sorted(SAFE_PAYLOADS), help="Print safe starter payloads for a vulnerability type and exit.")
    parser.add_argument("--execute", action="store_true", help="Actually send the request. Omit for dry-run.")
    parser.add_argument("--timeout", type=float, default=8.0, help="Network timeout in seconds for --execute.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.payloads:
        output = {"vuln_type": args.payloads, "payloads": SAFE_PAYLOADS[args.payloads]}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    if not args.poc_file:
        parser.error("--poc-file is required unless --payloads is used")

    poc = load_poc(args.poc_file)
    decision = scope_check.decide(args)
    req = build_request(args.target_url or "http://example.invalid", poc)
    plan = {
        "scope": scope_check.asdict(decision),
        "dry_run": not args.execute,
        "request": {
            "method": req.get_method(),
            "url": req.full_url,
            "headers": dict(req.header_items()),
            "body_bytes": len(req.data or b""),
            "poc_file": str(Path(args.poc_file).resolve()),
        },
    }

    if not decision.allowed:
        plan["result"] = "BLOCKED_BY_SCOPE"
        print(json.dumps(plan, ensure_ascii=False, indent=2) if args.json else "BLOCKED_BY_SCOPE\n" + json.dumps(plan, ensure_ascii=False, indent=2))
        return 2

    if args.mode == "audit" and args.execute:
        plan["result"] = "BLOCKED_BY_MODE"
        plan["reason"] = "audit mode does not allow active POC"
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 2

    if not args.execute:
        plan["result"] = "DRY_RUN_ONLY"
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    plan["response"] = run_request(req, args.timeout)
    plan["result"] = "EXECUTED"
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0 if plan["response"].get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
