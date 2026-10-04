#!/usr/bin/env python3
"""Unified CLI for union-search-skill."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure local module imports work when run as script.
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from adapters import run_defuddle, run_download, run_image, run_platform, run_search
from doctor import handle_doctor
from errors import CliError, CliUsageError
from output import build_envelope, render_output
from output_io import write_output
from registry import DEFAULT_IMAGE_PLATFORMS, IMAGE_PLATFORMS, load_capabilities, load_groups
from validators import (
    parse_param_pairs, resolve_limit, resolve_query, validate_platforms, validate_search_workers,
)

__version__ = "0.1.0"
PLATFORM_COMMAND_ALIASES: Dict[str, List[str]] = {
    "google": ["gsearch"],
    "bing": ["bsearch"],
}


def parse_args() -> argparse.Namespace:
    """Create parser and parse arguments."""
    parser = argparse.ArgumentParser(
        description="union-search unified CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/cli/main.py list --format markdown\n"
            "  python scripts/cli/main.py doctor --env-file .env\n"
            "  python scripts/cli/main.py search \"AI\" --group dev --limit 3 --pretty\n"
            "  python scripts/cli/main.py platform github \"machine learning\" --limit 5 --pretty\n"
            "  python scripts/cli/main.py google \"AI Agent\" --limit 5 --pretty\n"
            "  python scripts/cli/main.py bsearch \"AI Agent\" --limit 5 --pretty\n"
            "  python scripts/cli/main.py image \"cats\" --platforms baidu bing --limit 20 --output-dir ./image_downloads\n"
            "  python scripts/cli/main.py download \"https://www.youtube.com/watch?v=dQw4w9WgXcQ\" --output-dir ./downloads\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"union-search CLI v{__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # search
    search_parser = subparsers.add_parser("search", help="Aggregated multi-platform search")
    search_parser.add_argument("query", nargs="?", help="Search query")
    search_parser.add_argument("--query", dest="query_opt", help="Search query (overrides positional)")
    search_parser.add_argument("--platforms", "-p", nargs="+", help="Specific platforms")
    search_parser.add_argument("--group", "-g", help="Platform group (default: no_api_key_fast)")
    search_parser.add_argument("--limit", "-l", type=int, default=None, help="Positive per-platform item limit")
    search_parser.add_argument("--preset", choices=["small", "medium", "large", "extra"], help="Predefined result limits (small=3, medium=5, large=10, extra=20)")
    search_parser.add_argument("--max-workers", type=int, default=5, help="Positive concurrency (default: 5)")
    search_parser.add_argument("--timeout", type=int, default=60, help="Timeout seconds")
    search_parser.add_argument("--deduplicate", action="store_true", help="Cross-platform deduplicate")
    search_parser.add_argument("--fail-on-platform-error", action="store_true", help="Exit non-zero on partial platform failures")
    search_parser.add_argument("--env-file", default=".env", help="Env file path")
    _add_output_args(search_parser)

    # platform
    platform_parser = subparsers.add_parser("platform", help="Run a single platform")
    platform_parser.add_argument("platform", help="Platform name")
    platform_parser.add_argument("query", nargs="?", help="Search query")
    platform_parser.add_argument("--query", dest="query_opt", help="Search query (overrides positional)")
    platform_parser.add_argument("--limit", "-l", type=int, default=None, help="Positive result limit")
    platform_parser.add_argument("--timeout", type=int, default=60, help="Timeout seconds")
    platform_parser.add_argument("--param", action="append", help="Adapter passthrough key=value (repeatable)")
    platform_parser.add_argument("--fail-on-platform-error", action="store_true", help="Exit non-zero if platform fails")
    platform_parser.add_argument("--env-file", default=".env", help="Env file path")
    _add_output_args(platform_parser)

    # image
    image_parser = subparsers.add_parser("image", help="Multi-platform image search/download")
    image_parser.add_argument("query", nargs="?", help="Search query")
    image_parser.add_argument("--query", dest="query_opt", help="Search query (overrides positional)")
    image_parser.add_argument("--platforms", "-p", nargs="+", help="Image platforms (default: all except paid volcengine)")
    image_parser.add_argument("--limit", "-l", type=int, default=10, help="Images per platform (<=0 unlimited)")
    image_parser.add_argument("--output-dir", default="image_downloads", help="Output directory")
    image_parser.add_argument("--threads", type=int, default=5, help="Download threads")
    image_parser.add_argument("--delay", type=float, default=1.0, help="Delay between platforms in seconds")
    image_parser.add_argument("--no-metadata", action="store_true", help="Disable metadata output")
    image_parser.add_argument("--env-file", default=".env", help="Env file path")
    image_parser.add_argument("--timeout", type=int, default=1800, help="Command timeout seconds")
    _add_output_args(image_parser)

    # download
    download_parser = subparsers.add_parser("download", help="Download media using yt-dlp")
    download_parser.add_argument("urls", nargs="*", help="Direct media URLs to download")
    download_parser.add_argument("--from-file", help="Load URLs from search result JSON file")
    download_parser.add_argument("--platforms", "-p", nargs="+", help="Filter platforms when using --from-file")
    download_parser.add_argument("--select", help="Select candidate indices from --from-file, e.g. 1,3,5")
    download_parser.add_argument("--limit", "-l", type=int, default=None, help="Max candidates when using --from-file")
    download_parser.add_argument("--output-dir", default="downloads", help="Download output directory")
    download_parser.add_argument("--audio-only", action="store_true", help="Extract audio only")
    download_parser.add_argument("--audio-format", default="mp3", help="Audio format when --audio-only")
    download_parser.add_argument("--media-format", help="yt-dlp format selector, e.g. bestvideo+bestaudio/best")
    download_parser.add_argument("--max-height", type=int, help="Prefer max video height (e.g. 1080)")
    download_parser.add_argument("--cookies-file", help="Path to cookies.txt (Netscape format)")
    download_parser.add_argument("--cookies-from-browser", help="Browser name for cookies import, e.g. chrome")
    download_parser.add_argument("--restrict-filenames", action=argparse.BooleanOptionalAction, default=True, help="Use safe ASCII-ish filenames")
    download_parser.add_argument("--continue-download", action=argparse.BooleanOptionalAction, default=True, help="Resume partial downloads")
    download_parser.add_argument("--retries", type=int, default=None, help="Global retry count for yt-dlp")
    download_parser.add_argument("--fragment-retries", type=int, default=None, help="Retry count for HLS/DASH fragments")
    download_parser.add_argument("--retry-sleep", help="Retry sleep strategy, e.g. fragment:exp=1:10")
    download_parser.add_argument("--proxy", help="Proxy URL, e.g. socks5://127.0.0.1:1080")
    download_parser.add_argument("--timeout", type=int, default=3600, help="Command timeout seconds")
    download_parser.add_argument("--dry-run", action="store_true", help="Resolve metadata without downloading")
    download_parser.add_argument("--fail-on-download-error", action="store_true", help="Exit non-zero if download fails")
    download_parser.add_argument("--env-file", default=".env", help="Env file path")
    _add_output_args(download_parser)

    # list
    list_parser = subparsers.add_parser("list", help="List platform capabilities and groups")
    list_parser.add_argument("--type", choices=["all", "platforms", "groups", "images"], default="all")
    _add_output_args(list_parser)

    # doctor
    doctor_parser = subparsers.add_parser("doctor", help="Run environment and dependency checks")
    doctor_parser.add_argument("--platforms", "-p", nargs="+", help="Only check selected platforms")
    doctor_parser.add_argument("--env-file", default=".env", help="Env file path")
    doctor_parser.add_argument("--strict", action="store_true", help="Return non-zero on warnings")
    _add_output_args(doctor_parser)

    # defuddle - URL to Markdown (special handling because it takes URL not query)
    defuddle_parser = subparsers.add_parser("defuddle", help="Extract web page content to Markdown using Defuddle")
    defuddle_parser.add_argument("url", nargs="?", help="URL to extract content from")
    defuddle_parser.add_argument("--url", dest="url_opt", help="URL to extract (overrides positional)")
    defuddle_parser.add_argument("--json", action="store_true", help="Output JSON with metadata")
    defuddle_parser.add_argument("--timeout", type=int, default=60, help="Timeout seconds")
    defuddle_parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    _add_output_args(defuddle_parser)

    # direct platform commands, e.g. `google "query"` / `bing "query"`
    _add_direct_platform_subcommands(subparsers)

    return parser.parse_args()


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=["json", "markdown", "text"], default="json", help="Output format")
    parser.add_argument("--pretty", action="store_true", help="Pretty JSON")
    parser.add_argument("-o", "--output", help="Write output to file")


def _add_platform_execution_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--query", dest="query_opt", help="Search query (overrides positional)")
    parser.add_argument("--limit", "-l", type=int, default=None, help="Positive result limit")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout seconds")
    parser.add_argument("--param", action="append", help="Adapter passthrough key=value (repeatable)")
    parser.add_argument("--fail-on-platform-error", action="store_true", help="Exit non-zero if platform fails")
    parser.add_argument("--env-file", default=".env", help="Env file path")
    _add_output_args(parser)


def _add_direct_platform_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Add direct platform subcommands (excluding defuddle which has special handling)."""
    capabilities = load_capabilities()
    # Defuddle has its own dedicated command with URL-specific arguments
    excluded_platforms = {"defuddle"}
    for cap in capabilities:
        if cap.name in excluded_platforms:
            continue
        aliases = PLATFORM_COMMAND_ALIASES.get(cap.name, [])
        parser = subparsers.add_parser(
            cap.name,
            aliases=aliases,
            help=f"Direct call: {cap.name} ({cap.description})",
        )
        _add_platform_execution_args(parser)
        parser.set_defaults(platform_command=cap.name)


def handle_search(args: argparse.Namespace) -> Dict[str, Any]:
    query = resolve_query(args.query, args.query_opt)
    limit = resolve_limit(args.limit, args.preset)
    max_workers = validate_search_workers(args.max_workers)
    caps = load_capabilities()
    known = [c.name for c in caps]

    groups = load_groups()
    if args.group and args.group not in groups:
        raise CliUsageError(f"Unknown group '{args.group}'. Available: {', '.join(sorted(groups))}")

    selected_platforms = validate_platforms(args.platforms, known) if args.platforms else None
    data = run_search(
        query=query,
        platforms=selected_platforms,
        group=args.group,
        limit=limit,
        max_workers=max_workers,
        timeout=args.timeout,
        deduplicate=args.deduplicate,
        env_file=args.env_file,
    )
    failed = int(data.get("summary", {}).get("failed", 0))
    success = failed == 0
    errors: List[Dict[str, Any]] = []
    if failed:
        errors.append({"code": "partial_failure", "message": f"{failed} platforms failed"})
    return {
        "query": query,
        "success": success,
        "data": data,
        "errors": errors,
        "meta": {
            "failed_platforms": failed,
            "selected_platforms": data.get("platforms", []),
            "downloadable_items": len(data.get("download_candidates", [])),
        },
        "runtime_exit_code": 2 if (args.fail_on_platform_error and failed > 0) else 0,
    }


def handle_platform(args: argparse.Namespace) -> Dict[str, Any]:
    query = resolve_query(args.query, args.query_opt)
    caps = load_capabilities()
    known = [c.name for c in caps]
    platform = validate_platforms([args.platform], known)[0]
    return _handle_single_platform_run(platform, query, args, command_name="platform")


def handle_platform_direct(args: argparse.Namespace) -> Dict[str, Any]:
    query = resolve_query(args.query, args.query_opt)
    caps = load_capabilities()
    known = [c.name for c in caps]
    platform = validate_platforms([args.platform_command], known)[0]
    command_name = f"platform:{platform}"
    return _handle_single_platform_run(platform, query, args, command_name=command_name)


def _handle_single_platform_run(
    platform: str,
    query: str,
    args: argparse.Namespace,
    command_name: str,
) -> Dict[str, Any]:
    params = parse_param_pairs(args.param)
    data = run_platform(
        platform=platform,
        query=query,
        limit=args.limit,
        timeout=args.timeout,
        env_file=args.env_file,
        params=params,
    )
    success = bool(data.get("success"))
    errors: List[Dict[str, Any]] = []
    if not success:
        errors.append({"code": "platform_error", "message": str(data.get("error") or "Platform failed")})
    return {
        "command": command_name,
        "query": query,
        "success": success,
        "data": data,
        "errors": errors,
        "meta": {"platform": platform},
        "runtime_exit_code": 2 if (args.fail_on_platform_error and not success) else 0,
    }


def handle_image(args: argparse.Namespace) -> Dict[str, Any]:
    query = resolve_query(args.query, args.query_opt)
    selected_platforms = validate_platforms(args.platforms, IMAGE_PLATFORMS) if args.platforms else None
    data = run_image(
        query=query,
        platforms=selected_platforms,
        limit=args.limit,
        output_dir=args.output_dir,
        threads=args.threads,
        delay=args.delay,
        no_metadata=args.no_metadata,
        env_file=args.env_file,
        timeout=args.timeout,
    )
    summary = data.get("summary", {})
    failed = int(summary.get("failed", 0))
    success = failed == 0
    errors: List[Dict[str, Any]] = []
    if failed:
        errors.append({"code": "partial_failure", "message": f"{failed} image platforms failed"})
    return {
        "query": query,
        "success": success,
        "data": data,
        "errors": errors,
        "meta": {"selected_image_platforms": selected_platforms or list(DEFAULT_IMAGE_PLATFORMS)},
        "runtime_exit_code": 0,
    }


def handle_download(args: argparse.Namespace) -> Dict[str, Any]:
    if not args.urls and not args.from_file:
        raise CliUsageError("Provide at least one URL or use --from-file")

    data = run_download(
        urls=args.urls,
        from_file=args.from_file,
        platforms=args.platforms,
        select=args.select,
        limit=args.limit,
        output_dir=args.output_dir,
        audio_only=args.audio_only,
        audio_format=args.audio_format,
        media_format=args.media_format,
        max_height=args.max_height,
        cookies_file=args.cookies_file,
        cookies_from_browser=args.cookies_from_browser,
        restrict_filenames=args.restrict_filenames,
        continue_download=args.continue_download,
        retries=args.retries,
        fragment_retries=args.fragment_retries,
        retry_sleep=args.retry_sleep,
        proxy=args.proxy,
        env_file=args.env_file,
        timeout=args.timeout,
        dry_run=args.dry_run,
    )
    success = bool(data.get("success"))
    errors: List[Dict[str, Any]] = []
    if not success:
        errors.append(
            {
                "code": "download_error",
                "message": str(data.get("stderr") or data.get("stdout") or "yt-dlp download failed"),
            }
        )

    return {
        "query": None,
        "success": success,
        "data": data,
        "errors": errors,
        "meta": {
            "source_file": args.from_file,
            "provided_urls": len(args.urls or []),
            "resolved_urls": len(data.get("resolved_urls", [])),
        },
        "runtime_exit_code": 2 if (args.fail_on_download_error and not success) else 0,
    }


def handle_list(args: argparse.Namespace) -> Dict[str, Any]:
    capabilities = load_capabilities()
    groups = load_groups()
    payload: Dict[str, Any] = {}

    if args.type in {"all", "platforms"}:
        payload["platforms"] = [cap.to_dict() for cap in capabilities]
    if args.type in {"all", "groups"}:
        payload["groups"] = groups
    if args.type in {"all", "images"}:
        payload["image_platforms"] = list(IMAGE_PLATFORMS)

    return {
        "query": None,
        "success": True,
        "data": payload,
        "errors": [],
        "meta": {"count_platforms": len(capabilities), "count_groups": len(groups)},
        "runtime_exit_code": 0,
    }


def handle_defuddle(args: argparse.Namespace) -> Dict[str, Any]:
    """Handle defuddle URL to Markdown command."""
    from url_to_markdown.engines.defuddle_engine import DefuddleEngine

    # The explicit option overrides the positional URL, as advertised by --help.
    url = args.url_opt or args.url
    if not url:
        raise CliUsageError("URL is required for defuddle command. Use: defuddle <url> or defuddle --url <url>")

    started = datetime.now()
    try:
        client = DefuddleEngine(timeout=args.timeout)
        result = client.fetch(
            url=url,
            markdown=True,
            json_output=args.json,
            timeout=args.timeout,
        )
        success = True
        errors: List[Dict[str, Any]] = []
    except Exception as exc:
        result = {"error": str(exc)}
        success = False
        errors = [{"code": "defuddle_error", "message": str(exc)}]

    duration_ms = int((datetime.now() - started).total_seconds() * 1000)
    result["adapter_timing_ms"] = duration_ms

    return {
        "command": "defuddle",
        "query": url,
        "success": success,
        "data": result,
        "errors": errors,
        "meta": {"url": url},
        "runtime_exit_code": 0 if success else 2,
    }


def dispatch(args: argparse.Namespace) -> Dict[str, Any]:
    if hasattr(args, "platform_command"):
        return handle_platform_direct(args)
    if args.command == "search":
        return handle_search(args)
    if args.command == "platform":
        return handle_platform(args)
    if args.command == "image":
        return handle_image(args)
    if args.command == "download":
        return handle_download(args)
    if args.command == "list":
        return handle_list(args)
    if args.command == "doctor":
        return handle_doctor(args)
    if args.command == "defuddle":
        return handle_defuddle(args)
    raise CliUsageError(f"Unknown command: {args.command}")


def main() -> int:
    started_at = datetime.now()
    try:
        args = parse_args()
        result = dispatch(args)
        envelope = build_envelope(
            command=str(result.get("command", args.command)),
            query=result.get("query"),
            started_at=started_at,
            success=bool(result.get("success")),
            data=result.get("data"),
            errors=result.get("errors"),
            meta=result.get("meta"),
        )
        rendered = render_output(envelope, fmt=args.format, pretty=bool(args.pretty))
        write_output(rendered, args.output)
        return int(result.get("runtime_exit_code", 0))
    except CliError as exc:
        envelope = build_envelope(
            command="error",
            query=None,
            started_at=started_at,
            success=False,
            data={},
            errors=[
                {
                    "code": exc.__class__.__name__,
                    "message": exc.message,
                    "detail": exc.detail,
                }
            ],
            meta={},
        )
        print(render_output(envelope, fmt="json", pretty=True), file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
