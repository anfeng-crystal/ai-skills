#!/usr/bin/env python3
"""Read-only inventory and comparison for Kingdee metadata ZIP packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import sys
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET


TEXT_SUFFIXES = {".dym", ".dymx", ".xml", ".json", ".js", ".css"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_member(name: str) -> bool:
    normalized = posixpath.normpath(name)
    return not (
        name.startswith("/")
        or normalized == ".."
        or normalized.startswith("../")
        or "\\" in name
    )


def child_text(node: ET.Element, name: str) -> str | None:
    child = node.find(name)
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def xml_summary(name: str, data: bytes) -> dict:
    result = {"entry": name, "sha256": sha256_bytes(data), "validXml": False}
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        result["parseError"] = str(exc)
        return result

    result["validXml"] = True
    result["modelTypes"] = sorted(
        {text for node in root.iter("ModelType") if (text := (node.text or "").strip())}
    )
    result["numbers"] = sorted(
        {text for node in root.iter("Number") if (text := (node.text or "").strip())}
    )
    result["parentIds"] = sorted(
        {text for node in root.iter("ParentId") if (text := (node.text or "").strip())}
    )
    result["inheritPaths"] = sorted(
        {text for node in root.iter("InheritPath") if (text := (node.text or "").strip())}
    )

    actions = Counter()
    overrides = []
    for node in root.iter():
        action = node.attrib.get("action")
        if action:
            actions[action] += 1
        if action in {"edit", "reset", "delete"}:
            overrides.append(
                {
                    "tag": node.tag,
                    "action": action,
                    "oid": node.attrib.get("oid"),
                    "key": child_text(node, "Key"),
                    "name": child_text(node, "Name"),
                    "operationKey": child_text(node, "OperationKey"),
                }
            )
    result["actions"] = dict(sorted(actions.items()))
    result["overrides"] = overrides
    return result


def inspect_package(path: Path) -> dict:
    raw = path.read_bytes()
    result = {
        "path": str(path),
        "sha256": sha256_bytes(raw),
        "size": len(raw),
        "validZip": False,
        "members": [],
        "unsafeMembers": [],
        "xml": [],
    }
    try:
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            result["validZip"] = bad is None
            if bad:
                result["badMember"] = bad
            for info in archive.infolist():
                member = {
                    "name": info.filename,
                    "size": info.file_size,
                    "crc": f"{info.CRC:08x}",
                    "directory": info.is_dir(),
                }
                result["members"].append(member)
                if not safe_member(info.filename):
                    result["unsafeMembers"].append(info.filename)
                suffix = Path(info.filename).suffix.lower()
                if not info.is_dir() and suffix in TEXT_SUFFIXES:
                    data = archive.read(info)
                    if suffix in {".dym", ".dymx", ".xml"}:
                        result["xml"].append(xml_summary(info.filename, data))
    except zipfile.BadZipFile as exc:
        result["zipError"] = str(exc)
    return result


def member_hashes(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as archive:
        return {
            info.filename: sha256_bytes(archive.read(info))
            for info in archive.infolist()
            if not info.is_dir()
        }


def compare_packages(before: Path, after: Path, strict_members: bool) -> tuple[dict, int]:
    before_info = inspect_package(before)
    after_info = inspect_package(after)
    before_hashes = member_hashes(before) if before_info["validZip"] else {}
    after_hashes = member_hashes(after) if after_info["validZip"] else {}
    before_names = set(before_hashes)
    after_names = set(after_hashes)
    result = {
        "before": before_info,
        "after": after_info,
        "addedMembers": sorted(after_names - before_names),
        "removedMembers": sorted(before_names - after_names),
        "changedMembers": sorted(
            name for name in before_names & after_names if before_hashes[name] != after_hashes[name]
        ),
        "unchangedMembers": sorted(
            name for name in before_names & after_names if before_hashes[name] == after_hashes[name]
        ),
        "strictMembers": strict_members,
    }
    invalid = (
        not before_info["validZip"]
        or not after_info["validZip"]
        or bool(before_info["unsafeMembers"])
        or bool(after_info["unsafeMembers"])
        or any(not item["validXml"] for item in before_info["xml"] + after_info["xml"])
        or (strict_members and (result["addedMembers"] or result["removedMembers"]))
    )
    return result, 2 if invalid else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect", help="Inspect one ZIP without extracting it")
    inspect_parser.add_argument("package", type=Path)
    compare_parser = subparsers.add_parser("compare", help="Compare two ZIPs without modifying them")
    compare_parser.add_argument("before", type=Path)
    compare_parser.add_argument("after", type=Path)
    compare_parser.add_argument("--strict-members", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "inspect":
        result = inspect_package(args.package)
        code = 0
        if (
            not result["validZip"]
            or result["unsafeMembers"]
            or any(not item["validXml"] for item in result["xml"])
        ):
            code = 2
    else:
        result, code = compare_packages(args.before, args.after, args.strict_members)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
