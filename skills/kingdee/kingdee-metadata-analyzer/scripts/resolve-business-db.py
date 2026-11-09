#!/usr/bin/env python3
"""Resolve and verify Cosmic business databases without reading business values."""

import argparse
import json
import sys

from business_db import RoutingError, resolve


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entities", nargs="+")
    parser.add_argument("--config", required=True)
    parser.add_argument("--environment", required=True, choices=("dev", "test", "prod"))
    parser.add_argument("--datacenter-id")
    parser.add_argument("--login-config")
    parser.add_argument("--management-db")
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args(argv)
    if args.timeout <= 0 or args.timeout > 60:
        parser.error("--timeout must be between 1 and 60 seconds")
    try:
        result = resolve(args.config, args.environment, args.entities,
            args.datacenter_id, args.login_config, args.management_db, args.timeout)
    except Exception as exc:
        # Driver errors can contain connection details; emit only stable categories.
        code = exc.code if isinstance(exc, RoutingError) else type(exc).__name__
        result = {"status": "failed", "error": code}
        sqlstate = getattr(exc, "pgcode", None)
        if sqlstate:
            result["sqlstate"] = sqlstate
        print(json.dumps(result, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
