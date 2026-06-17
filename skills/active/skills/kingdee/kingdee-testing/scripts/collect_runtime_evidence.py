#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import platform
import shutil
import time
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_log(path: Path, output_dir: Path, max_bytes: int) -> dict:
    target = output_dir / "logs" / path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    size = path.stat().st_size
    with path.open("rb") as source, target.open("wb") as dest:
        if size > max_bytes:
            source.seek(max(0, size - max_bytes))
        shutil.copyfileobj(source, dest)
    return {
        "source": str(path),
        "copiedTo": str(target),
        "sourceSize": size,
        "copiedSize": target.stat().st_size,
        "sha256": sha256_file(target),
        "truncatedFromHead": size > max_bytes,
    }


def collect(args: argparse.Namespace) -> dict:
    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    project = Path(args.project).expanduser().resolve() if args.project else None
    logs = []
    for value in args.log:
        path = Path(value).expanduser().resolve()
        if path.exists() and path.is_file():
            logs.append(copy_log(path, output, args.max_log_bytes))
        else:
            logs.append({"source": str(path), "missing": True})

    evidence = {
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "output": str(output),
        "project": str(project) if project else None,
        "environment": {
            "cwd": os.getcwd(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "javaHome": os.environ.get("JAVA_HOME"),
            "gradleUserHome": os.environ.get("GRADLE_USER_HOME"),
        },
        "logs": logs,
        "notes": args.note,
    }
    if project and project.exists():
        evidence["projectFiles"] = {
            "gradlew": str(project / "gradlew") if (project / "gradlew").exists() else None,
            "settingsGradle": str(project / "settings.gradle") if (project / "settings.gradle").exists() else None,
            "settingsGradleKts": str(project / "settings.gradle.kts") if (project / "settings.gradle.kts").exists() else None,
        }
    report = output / "runtime-evidence.json"
    report.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    evidence["report"] = str(report)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect read-only runtime evidence for Kingdee testing and dev verification."
    )
    parser.add_argument("--output", required=True, help="Directory for collected evidence.")
    parser.add_argument("--project", help="Optional project directory to fingerprint.")
    parser.add_argument(
        "--log",
        action="append",
        default=[],
        help="Log file to copy. Can be repeated. Copies only tail bytes by default.",
    )
    parser.add_argument(
        "--max-log-bytes",
        type=int,
        default=1024 * 1024,
        help="Maximum bytes copied per log file.",
    )
    parser.add_argument(
        "--note",
        action="append",
        default=[],
        help="Free-form note to include in evidence. Can be repeated.",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON evidence.")
    args = parser.parse_args()

    evidence = collect(args)
    if args.json:
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    else:
        print(f"evidence report: {evidence['report']}")
        print(f"logs: {len(evidence['logs'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
