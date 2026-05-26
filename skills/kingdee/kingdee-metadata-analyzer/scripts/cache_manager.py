#!/usr/bin/env python3
"""Inspect and clean local metadata analyzer cache files."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / ".metadata_cache"


def file_entry(path: Path) -> Dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "name": path.name,
        "size": stat.st_size,
        "mtime": int(stat.st_mtime),
        "ageSeconds": int(time.time() - stat.st_mtime),
    }


def iter_cache_files(cache_dir: Path) -> List[Path]:
    if not cache_dir.exists():
        return []
    return sorted(path for path in cache_dir.iterdir() if path.is_file())


def command_list(args: argparse.Namespace) -> int:
    cache_dir = Path(args.cache_dir)
    files = [file_entry(path) for path in iter_cache_files(cache_dir)]
    print(json.dumps({"cacheDir": str(cache_dir), "files": files}, ensure_ascii=False, indent=2))
    return 0


def command_prune(args: argparse.Namespace) -> int:
    cache_dir = Path(args.cache_dir)
    max_age = args.max_age_days * 24 * 60 * 60
    now = time.time()
    candidates = [path for path in iter_cache_files(cache_dir) if now - path.stat().st_mtime > max_age]
    removed: List[str] = []
    for path in candidates:
        removed.append(str(path))
        if not args.dry_run:
            path.unlink()
    print(
        json.dumps(
            {
                "cacheDir": str(cache_dir),
                "dryRun": args.dry_run,
                "maxAgeDays": args.max_age_days,
                "removed": removed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_clean(args: argparse.Namespace) -> int:
    cache_dir = Path(args.cache_dir)
    candidates = iter_cache_files(cache_dir)
    removed: List[str] = []
    for path in candidates:
        removed.append(str(path))
        if not args.dry_run:
            path.unlink()
    print(json.dumps({"cacheDir": str(cache_dir), "dryRun": args.dry_run, "removed": removed}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage local Kingdee metadata analyzer cache.")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Cache directory")
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="List cache files")
    list_parser.set_defaults(func=command_list)

    prune_parser = subparsers.add_parser("prune", help="Remove cache files older than N days")
    prune_parser.add_argument("--max-age-days", type=int, default=30)
    prune_parser.add_argument("--dry-run", action="store_true", default=True)
    prune_parser.add_argument("--apply", action="store_false", dest="dry_run")
    prune_parser.set_defaults(func=command_prune)

    clean_parser = subparsers.add_parser("clean", help="Remove all cache files")
    clean_parser.add_argument("--dry-run", action="store_true", default=True)
    clean_parser.add_argument("--apply", action="store_false", dest="dry_run")
    clean_parser.set_defaults(func=command_clean)

    args = parser.parse_args()
    if not args.command:
        return command_list(args)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
