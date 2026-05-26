#!/usr/bin/env python3
"""Validate whether active verification is allowed for a Kingdee target."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from urllib.parse import urlparse


ALLOWED_ACTIVE_SCOPES = {"local", "dev", "test", "staging"}
BLOCKED_SCOPES = {"prod", "unknown"}


@dataclass
class ScopeDecision:
    allowed: bool
    mode: str
    declared_scope: str
    inferred_scope: str
    target_url: str
    reason: str


def infer_scope(target_url: str) -> str:
    parsed = urlparse(target_url)
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return "local"
    if re.match(r"^127\.", host) or host.endswith(".local"):
        return "local"
    if any(token in host for token in ("dev", "develop", "development")):
        return "dev"
    if any(token in host for token in ("test", "qa", "uat")):
        return "test"
    if any(token in host for token in ("stage", "staging", "preprod", "pre-prod")):
        return "staging"
    if any(token in host for token in ("prod", "production")):
        return "prod"
    return "unknown"


def decide(args: argparse.Namespace) -> ScopeDecision:
    mode = args.mode
    declared = args.scope
    inferred = infer_scope(args.target_url) if args.target_url else "unknown"

    if mode == "audit":
        return ScopeDecision(True, mode, declared, inferred, args.target_url or "", "audit mode is static/read-only")

    if not args.target_url:
        return ScopeDecision(False, mode, declared, inferred, "", "verify/redteam-lite requires --target-url")

    if declared in ALLOWED_ACTIVE_SCOPES:
        return ScopeDecision(True, mode, declared, inferred, args.target_url, "declared scope allows active checks")

    if declared == "prod":
        if args.allow_prod and args.reason:
            return ScopeDecision(True, mode, declared, inferred, args.target_url, "prod explicitly authorized: " + args.reason)
        return ScopeDecision(False, mode, declared, inferred, args.target_url, "prod is blocked without --allow-prod and --reason")

    if declared == "unknown":
        if args.allow_unknown and args.reason:
            return ScopeDecision(True, mode, declared, inferred, args.target_url, "unknown scope explicitly authorized: " + args.reason)
        return ScopeDecision(False, mode, declared, inferred, args.target_url, "unknown scope is blocked without --allow-unknown and --reason")

    return ScopeDecision(False, mode, declared, inferred, args.target_url, "unsupported scope")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check target scope before Kingdee security verification or POC.")
    parser.add_argument("--mode", choices=["audit", "verify", "redteam-lite"], default="audit", help="Requested work mode.")
    parser.add_argument("--target-url", default="", help="Target base URL for active checks.")
    parser.add_argument("--scope", choices=["local", "dev", "test", "staging", "prod", "unknown"], default="unknown", help="Declared target scope.")
    parser.add_argument("--allow-prod", action="store_true", help="Allow production only with an explicit reason.")
    parser.add_argument("--allow-unknown", action="store_true", help="Allow unknown scope only with an explicit reason.")
    parser.add_argument("--reason", default="", help="User-provided authorization reason for prod/unknown scope.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    decision = decide(args)
    if args.json:
        print(json.dumps(asdict(decision), ensure_ascii=False, indent=2))
    else:
        status = "ALLOWED" if decision.allowed else "BLOCKED"
        print(f"{status}: mode={decision.mode} declared={decision.declared_scope} inferred={decision.inferred_scope}")
        print(decision.reason)
    return 0 if decision.allowed else 2


if __name__ == "__main__":
    sys.exit(main())
