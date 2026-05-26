#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def find_gradlew(start: Path) -> Path | None:
    current = start.resolve()
    for candidate_dir in [current, *current.parents]:
        candidate = candidate_dir / "gradlew"
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def build_command(gradlew: Path, tasks: list[str], tests: list[str], extra_args: list[str]) -> list[str]:
    command = [str(gradlew)]
    command.extend(tasks or ["test"])
    for test in tests:
        command.extend(["--tests", test])
    command.extend(extra_args)
    return command


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Precheck and optionally run Gradle tests for a Kingdee Java project."
    )
    parser.add_argument("--project", default=".", help="Project directory or subdirectory.")
    parser.add_argument(
        "--task",
        action="append",
        default=[],
        help="Gradle task to run. Can be repeated. Defaults to test.",
    )
    parser.add_argument(
        "--tests",
        action="append",
        default=[],
        help="Gradle --tests pattern. Can be repeated.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print the resolved command and precheck result.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )
    parser.add_argument(
        "gradle_args",
        nargs=argparse.REMAINDER,
        help="Extra Gradle arguments after --, for example -- --info.",
    )
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    gradlew = find_gradlew(project)
    if gradlew is None:
        result = {
            "ok": False,
            "project": str(project),
            "error": "gradlew not found in project or ancestors",
        }
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(result["error"], file=sys.stderr)
        return 2

    extra_args = args.gradle_args
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]
    command = build_command(gradlew, args.task, args.tests, extra_args)
    result = {
        "ok": True,
        "project": str(project),
        "gradlew": str(gradlew),
        "workingDirectory": str(gradlew.parent),
        "command": command,
        "dryRun": args.dry_run,
    }

    if args.dry_run:
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(" ".join(command))
        return 0

    env = os.environ.copy()
    process = subprocess.run(command, cwd=gradlew.parent, env=env)
    result["returncode"] = process.returncode
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
