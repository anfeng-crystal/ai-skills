#!/usr/bin/env python3
"""Write a compact Kingdee security review report from JSON findings."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path


SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("input JSON must be an object")
    return data


def md_escape(value: object) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def render_report(data: dict) -> str:
    findings = data.get("findings") or []
    findings = sorted(findings, key=lambda item: SEVERITY_ORDER.get(str(item.get("severity", "Info")), 9))
    title = data.get("title") or "Kingdee Security Review Report"
    mode = data.get("mode") or "audit"
    target = data.get("target") or ""
    scope = data.get("scope") or ""
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# {title}",
        "",
        "## Summary",
        "",
        f"- Mode: `{mode}`",
        f"- Target: `{target}`",
        f"- Scope: `{scope}`",
        f"- Generated: `{now}`",
        f"- Findings: `{len(findings)}`",
        "",
        "## Findings",
        "",
        "| ID | Severity | Title | Target | Verification |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in findings:
        lines.append(
            "| {id} | {severity} | {title} | {target} | {verification} |".format(
                id=md_escape(item.get("id", "")),
                severity=md_escape(item.get("severity", "Info")),
                title=md_escape(item.get("title", "")),
                target=md_escape(item.get("target", "")),
                verification=md_escape(item.get("verification", "unverified")),
            )
        )

    for item in findings:
        lines.extend(
            [
                "",
                f"### {item.get('id', 'FINDING')} - {item.get('title', '')}",
                "",
                f"- Severity: `{item.get('severity', 'Info')}`",
                f"- Target: `{item.get('target', '')}`",
                f"- Verification: `{item.get('verification', 'unverified')}`",
                f"- Evidence: {item.get('evidence', '')}",
                f"- Recommendation: {item.get('recommendation', '')}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a Markdown security review report from JSON findings.")
    parser.add_argument("--input", required=True, help="JSON input file with title/mode/target/scope/findings.")
    parser.add_argument("--output", help="Markdown output path. Omit to print to stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    data = load_json(args.input)
    report = render_report(data)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
        print(str(path))
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
