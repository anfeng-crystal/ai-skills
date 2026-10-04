#!/usr/bin/env python3
"""Dependency and credential-presence diagnostics for the unified CLI."""

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

from registry import load_capabilities, load_groups
from validators import validate_platforms


def handle_doctor(args: argparse.Namespace) -> Dict[str, Any]:
    capabilities = load_capabilities()
    groups = load_groups()
    selected = set(validate_platforms(args.platforms, [c.name for c in capabilities])) if args.platforms else None

    # Best-effort env loading using existing union loader.
    scripts_dir = Path(__file__).resolve().parents[1]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from union_search.union_search import load_env_file

    load_env_file(args.env_file)
    env_path = Path(args.env_file)
    if not env_path.is_absolute():
        env_path = Path.cwd() / env_path

    checks: List[Dict[str, Any]] = []
    checks.append(
        {
            "name": "env_file",
            "status": "pass" if env_path.exists() else "warn",
            "message": f"env file {'found' if env_path.exists() else 'not found'} at {env_path}",
        }
    )

    try:
        import requests  # noqa: F401

        requests_status = "pass"
        requests_message = "requests is installed"
    except Exception:
        requests_status = "fail"
        requests_message = "requests is missing"
    checks.append({"name": "dependency_requests", "status": requests_status, "message": requests_message})

    try:
        import dotenv  # noqa: F401

        dotenv_status = "pass"
        dotenv_message = "python-dotenv is installed"
    except Exception:
        dotenv_status = "fail"
        dotenv_message = "python-dotenv is missing"
    checks.append({"name": "dependency_dotenv", "status": dotenv_status, "message": dotenv_message})

    try:
        import lxml  # noqa: F401

        lxml_status = "pass"
        lxml_message = "lxml is installed"
    except Exception:
        lxml_status = "fail"
        lxml_message = "lxml is missing"
    checks.append({"name": "dependency_lxml", "status": lxml_status, "message": lxml_message})

    try:
        import pygments  # noqa: F401

        pygments_status = "pass"
        pygments_message = "pygments is installed"
    except Exception:
        pygments_status = "warn"
        pygments_message = "pygments not installed (reddit module may fail)"
    checks.append({"name": "dependency_pygments", "status": pygments_status, "message": pygments_message})

    try:
        import feedparser  # noqa: F401

        feedparser_status = "pass"
        feedparser_message = "feedparser is installed"
    except Exception:
        feedparser_status = "warn"
        feedparser_message = "feedparser not installed (rss module may fail)"
    checks.append({"name": "dependency_feedparser", "status": feedparser_status, "message": feedparser_message})

    try:
        import loguru  # noqa: F401

        loguru_status = "pass"
        loguru_message = "loguru is installed"
    except Exception:
        loguru_status = "warn"
        loguru_message = "loguru not installed (logging may be degraded)"
    checks.append({"name": "dependency_loguru", "status": loguru_status, "message": loguru_message})

    try:
        import pydantic  # noqa: F401

        pydantic_status = "pass"
        pydantic_message = "pydantic is installed"
    except Exception:
        pydantic_status = "warn"
        pydantic_message = "pydantic not installed"
    checks.append({"name": "dependency_pydantic", "status": pydantic_status, "message": pydantic_message})

    try:
        import firecrawl  # noqa: F401

        firecrawl_status = "pass"
        firecrawl_message = "firecrawl-py is installed"
    except Exception:
        firecrawl_status = "warn"
        firecrawl_message = "firecrawl-py not installed (url_to_markdown firecrawl engine may fail)"
    checks.append({"name": "dependency_firecrawl", "status": firecrawl_status, "message": firecrawl_message})

    try:
        import imagedl  # noqa: F401

        image_dep_status = "pass"
        image_dep_message = "pyimagedl is installed"
    except Exception:
        image_dep_status = "warn"
        image_dep_message = "pyimagedl not installed (image command unavailable)"
    checks.append({"name": "dependency_pyimagedl", "status": image_dep_status, "message": image_dep_message})

    ytdlp_path = shutil.which("yt-dlp")
    ytdlp_status = "pass" if ytdlp_path else "warn"
    ytdlp_message = f"yt-dlp found at {ytdlp_path}" if ytdlp_path else "yt-dlp not found (download command unavailable)"
    checks.append({"name": "dependency_ytdlp", "status": ytdlp_status, "message": ytdlp_message})

    ffmpeg_path = shutil.which("ffmpeg")
    ffmpeg_status = "pass" if ffmpeg_path else "warn"
    ffmpeg_message = f"ffmpeg found at {ffmpeg_path}" if ffmpeg_path else "ffmpeg not found (format merge/audio extraction may fail)"
    checks.append({"name": "dependency_ffmpeg", "status": ffmpeg_status, "message": ffmpeg_message})

    node_path = shutil.which("node")
    node_status = "pass" if node_path else "warn"
    node_message = f"node found at {node_path}" if node_path else "Node.js not found (defuddle/wechat modules may fail)"
    checks.append({"name": "dependency_node", "status": node_status, "message": node_message})

    npm_path = shutil.which("npm")
    npm_status = "pass" if npm_path else "warn"
    npm_message = f"npm found at {npm_path}" if npm_path else "npm not found (cannot install Node.js dependencies)"
    checks.append({"name": "dependency_npm", "status": npm_status, "message": npm_message})

    # Check for critical npm modules if node is available
    if node_path:
        # Check root node_modules for cheerio and commander
        root_dir = Path(__file__).resolve().parents[2]
        cheerio_path = root_dir / "node_modules" / "cheerio"
        commander_path = root_dir / "node_modules" / "commander"

        checks.append({
            "name": "npm_module_cheerio",
            "status": "pass" if cheerio_path.exists() else "fail",
            "message": "cheerio is installed" if cheerio_path.exists() else "cheerio is missing (required for wechat). Run 'npm install'"
        })
        checks.append({
            "name": "npm_module_commander",
            "status": "pass" if commander_path.exists() else "fail",
            "message": "commander is installed" if commander_path.exists() else "commander is missing (required for defuddle). Run 'npm install'"
        })

        jsdom_path = root_dir / "node_modules" / "jsdom"
        checks.append({
            "name": "npm_module_jsdom",
            "status": "pass" if jsdom_path.exists() else "fail",
            "message": "jsdom is installed" if jsdom_path.exists() else "jsdom is missing (required for defuddle). Run 'npm install'"
        })

        # Check defuddle-node build
        defuddle_dist = root_dir / "scripts" / "url_to_markdown" / "engines" / "defuddle-node" / "dist" / "cli.js"
        checks.append({
            "name": "defuddle_build",
            "status": "pass" if defuddle_dist.exists() else "fail",
            "message": "defuddle-node build found" if defuddle_dist.exists() else "defuddle-node build missing. Run 'npm install' in scripts/url_to_markdown/engines/defuddle-node"
        })

    platform_checks: List[Dict[str, Any]] = []
    for cap in capabilities:
        if selected and cap.name not in selected:
            continue
        missing = [key for key in cap.required_env if not os.getenv(key)]
        if cap.status == "disabled":
            status = "warn"
            message = cap.notes or "disabled platform"
        elif missing:
            status = "warn"
            message = f"missing required env: {', '.join(missing)}"
        else:
            status = "pass"
            message = "ready"
        platform_checks.append(
            {
                "platform": cap.name,
                "status": status,
                "message": message,
                "required_env": list(cap.required_env),
                "groups": list(cap.groups),
            }
        )

    summary = {
        "checks_pass": len([c for c in checks if c["status"] == "pass"]),
        "checks_warn": len([c for c in checks if c["status"] == "warn"]),
        "checks_fail": len([c for c in checks if c["status"] == "fail"]),
        "platform_pass": len([c for c in platform_checks if c["status"] == "pass"]),
        "platform_warn": len([c for c in platform_checks if c["status"] == "warn"]),
        "platform_total": len(platform_checks),
        "groups_available": sorted(groups.keys()),
    }

    has_fail = summary["checks_fail"] > 0
    has_warn = summary["checks_warn"] > 0 or summary["platform_warn"] > 0
    success = not has_fail and not (args.strict and has_warn)
    errors: List[Dict[str, Any]] = []
    if has_fail:
        errors.append({"code": "dependency_failure", "message": "One or more required dependencies are missing"})
    if args.strict and has_warn:
        errors.append({"code": "strict_warning", "message": "Warnings detected under --strict mode"})

    return {
        "query": None,
        "success": success,
        "data": {"checks": checks, "platforms": platform_checks, "summary": summary},
        "errors": errors,
        "meta": {"env_file": str(env_path)},
        "runtime_exit_code": 2 if not success else 0,
    }
