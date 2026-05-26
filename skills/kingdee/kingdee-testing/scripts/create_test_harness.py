#!/usr/bin/env python3
import argparse
import json
import shutil
from pathlib import Path


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def copy_harness(output: Path, force: bool) -> dict:
    source = skill_root() / "assets" / "java-test-harness"
    if not source.exists():
        raise SystemExit(f"missing harness asset directory: {source}")
    output.mkdir(parents=True, exist_ok=True)
    copied = []
    skipped = []
    for path in sorted(source.rglob("*")):
        if path.is_dir():
            continue
        relative = path.relative_to(source)
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not force:
            skipped.append(str(relative))
            continue
        shutil.copy2(path, target)
        copied.append(str(relative))
    return {
        "source": str(source),
        "output": str(output),
        "copied": copied,
        "skipped": skipped,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a local Kingdee Cosmic Java test harness from bundled templates."
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Directory to receive the harness files. Only this directory is written.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files under --output.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON.",
    )
    args = parser.parse_args()

    result = copy_harness(Path(args.output).expanduser().resolve(), args.force)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"created harness: {result['output']}")
        print(f"copied: {len(result['copied'])}")
        if result["skipped"]:
            print(f"skipped existing: {len(result['skipped'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
