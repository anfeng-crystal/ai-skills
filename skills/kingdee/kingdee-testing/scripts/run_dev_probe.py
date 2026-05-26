#!/usr/bin/env python3
import argparse
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


READ_ONLY_METHODS = {"GET", "HEAD", "OPTIONS"}


def parse_headers(values: list[str]) -> dict[str, str]:
    headers = {}
    for value in values:
        if ":" not in value:
            raise SystemExit(f"invalid header, expected Name: value: {value}")
        name, raw = value.split(":", 1)
        headers[name.strip()] = raw.strip()
    return headers


def probe(url: str, method: str, headers: dict[str, str], timeout: float, preview_bytes: int) -> dict:
    request = Request(url, method=method, headers=headers)
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(preview_bytes)
            return {
                "ok": True,
                "status": response.status,
                "reason": response.reason,
                "elapsedMs": round((time.monotonic() - started) * 1000, 2),
                "headers": dict(response.headers.items()),
                "preview": body.decode("utf-8", errors="replace"),
            }
    except HTTPError as exc:
        body = exc.read(preview_bytes)
        return {
            "ok": False,
            "status": exc.code,
            "reason": exc.reason,
            "elapsedMs": round((time.monotonic() - started) * 1000, 2),
            "headers": dict(exc.headers.items()) if exc.headers else {},
            "preview": body.decode("utf-8", errors="replace"),
        }
    except URLError as exc:
        return {
            "ok": False,
            "error": str(exc.reason),
            "elapsedMs": round((time.monotonic() - started) * 1000, 2),
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an explicit read-only HTTP probe against a Kingdee dev/test runtime."
    )
    parser.add_argument("--url", required=True, help="Target dev/test URL.")
    parser.add_argument(
        "--method",
        default="GET",
        choices=sorted(READ_ONLY_METHODS),
        help="Read-only HTTP method.",
    )
    parser.add_argument(
        "--header",
        action="append",
        default=[],
        help="Request header in 'Name: value' form. Can be repeated.",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="Timeout seconds.")
    parser.add_argument("--expect-status", type=int, help="Expected HTTP status.")
    parser.add_argument("--preview-bytes", type=int, default=4096, help="Response preview byte cap.")
    parser.add_argument("--output", help="Optional JSON output file.")
    args = parser.parse_args()

    parsed = urlparse(args.url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        print("url must be an absolute http(s) URL", file=sys.stderr)
        return 2

    headers = parse_headers(args.header)
    result = probe(args.url, args.method, headers, args.timeout, args.preview_bytes)
    result.update({"url": args.url, "method": args.method})
    if args.expect_status is not None:
        result["expectedStatus"] = args.expect_status
        result["statusMatched"] = result.get("status") == args.expect_status

    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.expect_status is not None and not result.get("statusMatched"):
        return 1
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
