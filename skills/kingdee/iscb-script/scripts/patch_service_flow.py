#!/usr/bin/env python3
"""Build a hash-pinned ISCB service-flow review copy from explicit Script replacements."""

from __future__ import annotations

import argparse
import copy
import ctypes
import errno
import hashlib
import json
import os
import re
import secrets
import sys
import tempfile
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

from analyze_service_flow import (
    DEFAULT_MAX_INPUT_BYTES,
    InspectionError,
    SENSITIVE_INLINE_RE,
    file_sha256,
    parse_dts_records,
    parse_finite_json_float,
    read_limited,
    reject_duplicate_object_pairs,
    reject_nonfinite_json,
    scalar_text,
    script_flags,
)


SCHEMA_VERSION = 1
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_REPLACEMENT_BYTES = 2 * 1024 * 1024
MAX_TOTAL_REPLACEMENT_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 80 * 1024 * 1024
MAX_CHANGES = 64
MAX_VERSION_DIGITS = 32
SHA256_RE = re.compile(r"[0-9a-fA-F]{64}\Z")
MODIFYTIME_RE = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?\Z")
RULE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}\Z")
EVIDENCE_LEVELS = {
    "bundle_runtime",
    "bundle_surface",
    "platform_reference",
    "platform_weak_precheck",
    "experience_hypothesis",
    "conflict",
}
EXPERIENCE_RULE_IDS = {
    "EXP-ARRAY-SUB-001",
    "EXP-COL-ADDALL-001",
    "EXP-COL-APPEND-001",
    "EXP-COL-FILTER-001",
    "EXP-CTRL-ELSEIF-001",
    "EXP-CTRL-FOREACH-001",
    "EXP-CTRL-TRY-001",
    "EXP-DATA-CTOR-001",
    "EXP-DATE-001",
    "EXP-HTTP-001",
    "EXP-JS-BLANKET-001",
    "EXP-JSON-PROFILE-001",
    "EXP-OPT-AUTO-001",
    "EXP-OPT-HEURISTIC-001",
    "EXP-SQL-001",
}
ALLOWED_SENSITIVE_FLAGS = {"endpoint_literal", "connection_literal"}
ALLOWED_COMMENT_SEPARATORS = {"", " ", " | ", "\n", "\n\n", "；", "； "}


class PatchRefused(ValueError):
    """Raised when the review-copy contract is incomplete, ambiguous, or stale."""


class FileSnapshot(NamedTuple):
    """Hash and resolved identity of one local input used to build a review copy."""

    label: str
    lexical_path: Path
    resolved_path: Path
    sha256: str
    size: int
    max_bytes: int


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PatchRefused(f"{path} must be an object")
    return value


def require_exact_keys(
    value: dict[str, Any],
    required: set[str],
    allowed: set[str],
    path: str,
) -> None:
    missing = sorted(required - value.keys())
    unknown_count = len(value.keys() - allowed)
    if missing:
        raise PatchRefused(f"{path} missing fields: {', '.join(missing)}")
    if unknown_count:
        raise PatchRefused(f"{path} has {unknown_count} unsupported field(s)")


def require_string(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise PatchRefused(f"{path} must be a {'string' if allow_empty else 'non-empty string'}")
    return value


def require_sha256(value: Any, path: str) -> str:
    text = require_string(value, path)
    if not SHA256_RE.fullmatch(text):
        raise PatchRefused(f"{path} must be a 64-character SHA-256")
    return text.lower()


def read_json_file(
    path: Path,
    limit: int,
    label: str,
) -> tuple[dict[str, Any], FileSnapshot]:
    try:
        if not path.exists() or not path.is_file():
            raise PatchRefused(f"{label} does not exist or is not a file")
        lexical_path = path.absolute()
        resolved_path = path.resolve(strict=True)
        with path.open("rb") as handle:
            raw = read_limited(handle, limit, label)
    except PatchRefused:
        raise
    except (OSError, ValueError):
        raise PatchRefused(f"{label} path is unavailable or unsupported") from None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PatchRefused(f"{label} is not UTF-8: {exc.reason}") from None
    try:
        value = json.loads(
            text,
            parse_constant=reject_nonfinite_json,
            parse_float=parse_finite_json_float,
            object_pairs_hook=reject_duplicate_object_pairs,
        )
    except json.JSONDecodeError as exc:
        raise PatchRefused(
            f"{label} has invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from None
    except RecursionError:
        raise PatchRefused(f"{label} exceeds the supported JSON nesting depth") from None
    snapshot = FileSnapshot(
        label,
        lexical_path,
        resolved_path,
        sha256_bytes(raw),
        len(raw),
        limit,
    )
    return require_object(value, label), snapshot


def validate_manifest(path: Path) -> tuple[dict[str, Any], FileSnapshot]:
    manifest, snapshot = read_json_file(path, MAX_MANIFEST_BYTES, "manifest")
    require_exact_keys(
        manifest,
        {"schema_version", "input_sha256", "flow_number", "metadata", "changes"},
        {"schema_version", "input_sha256", "flow_number", "metadata", "changes"},
        "manifest",
    )
    if isinstance(manifest["schema_version"], bool) or manifest["schema_version"] != SCHEMA_VERSION:
        raise PatchRefused(f"manifest.schema_version must be {SCHEMA_VERSION}")
    manifest["input_sha256"] = require_sha256(manifest["input_sha256"], "manifest.input_sha256")
    manifest["flow_number"] = require_string(manifest["flow_number"], "manifest.flow_number")

    metadata = require_object(manifest["metadata"], "manifest.metadata")
    require_exact_keys(
        metadata,
        {
            "expected_version",
            "expected_modifytime",
            "expected_comment_sha256",
            "new_modifytime",
            "comment_separator",
            "summary",
        },
        {
            "expected_version",
            "expected_modifytime",
            "expected_comment_sha256",
            "new_modifytime",
            "comment_separator",
            "summary",
        },
        "manifest.metadata",
    )
    metadata["expected_comment_sha256"] = require_sha256(
        metadata["expected_comment_sha256"],
        "manifest.metadata.expected_comment_sha256",
    )
    if metadata["expected_modifytime"] is not None and not isinstance(
        metadata["expected_modifytime"], str
    ):
        raise PatchRefused("manifest.metadata.expected_modifytime must be string or null")
    new_modifytime = require_string(metadata["new_modifytime"], "manifest.metadata.new_modifytime")
    if not MODIFYTIME_RE.fullmatch(new_modifytime):
        raise PatchRefused("manifest.metadata.new_modifytime must be an exact date-time value")
    try:
        datetime.fromisoformat(new_modifytime.replace(" ", "T", 1))
    except ValueError:
        raise PatchRefused(
            "manifest.metadata.new_modifytime must be a valid date-time value"
        ) from None
    separator = require_string(
        metadata["comment_separator"],
        "manifest.metadata.comment_separator",
        allow_empty=True,
    )
    if separator not in ALLOWED_COMMENT_SEPARATORS:
        raise PatchRefused("manifest.metadata.comment_separator is not an allowed separator")
    summary = require_string(metadata["summary"], "manifest.metadata.summary")
    if summary != summary.strip():
        raise PatchRefused("manifest.metadata.summary must not have outer whitespace")
    if len(summary) > 500 or any(ord(char) < 32 and char not in "\t" for char in summary):
        raise PatchRefused("manifest.metadata.summary contains unsupported control text or is too long")
    if SENSITIVE_INLINE_RE.search(summary) or script_flags(summary):
        raise PatchRefused("manifest.metadata.summary contains sensitive literal categories")
    metadata["summary"] = summary

    changes = manifest["changes"]
    if not isinstance(changes, list) or not changes:
        raise PatchRefused("manifest.changes must be a non-empty array")
    if len(changes) > MAX_CHANGES:
        raise PatchRefused(f"manifest.changes exceeds the supported limit ({MAX_CHANGES})")
    seen: set[tuple[tuple[str, ...], str]] = set()
    for index, raw_change in enumerate(changes):
        path_label = f"manifest.changes[{index}]"
        change = require_object(raw_change, path_label)
        require_exact_keys(
            change,
            {
                "scope_path",
                "node_id",
                "expected_script_sha256",
                "replacement_file",
                "replacement_sha256",
                "evidence_level",
                "experience_rules",
                "allow_sensitive_flags",
            },
            {
                "scope_path",
                "node_id",
                "expected_script_sha256",
                "replacement_file",
                "replacement_sha256",
                "evidence_level",
                "experience_rules",
                "allow_sensitive_flags",
            },
            path_label,
        )
        if not isinstance(change["scope_path"], list) or not all(
            isinstance(item, str) and item for item in change["scope_path"]
        ):
            raise PatchRefused(f"{path_label}.scope_path must be an array of node ids")
        change["node_id"] = require_string(change["node_id"], f"{path_label}.node_id")
        change["expected_script_sha256"] = require_sha256(
            change["expected_script_sha256"], f"{path_label}.expected_script_sha256"
        )
        replacement_file = require_string(
            change["replacement_file"], f"{path_label}.replacement_file"
        )
        if any(ord(char) < 32 for char in replacement_file):
            raise PatchRefused(f"{path_label}.replacement_file contains unsupported characters")
        if Path(replacement_file).is_absolute():
            raise PatchRefused(f"{path_label}.replacement_file must be relative to the manifest")
        change["replacement_sha256"] = require_sha256(
            change["replacement_sha256"], f"{path_label}.replacement_sha256"
        )
        evidence_level = require_string(
            change["evidence_level"], f"{path_label}.evidence_level"
        )
        if evidence_level not in EVIDENCE_LEVELS:
            raise PatchRefused(f"{path_label}.evidence_level is unsupported")
        if not isinstance(change["experience_rules"], list) or not all(
            isinstance(item, str) and RULE_ID_RE.fullmatch(item)
            for item in change["experience_rules"]
        ):
            raise PatchRefused(f"{path_label}.experience_rules must contain safe rule ids")
        if set(change["experience_rules"]) - EXPERIENCE_RULE_IDS:
            raise PatchRefused(
                f"{path_label}.experience_rules contains an unknown experience rule id"
            )
        if len(change["experience_rules"]) != len(set(change["experience_rules"])):
            raise PatchRefused(f"{path_label}.experience_rules must not contain duplicates")
        if evidence_level == "experience_hypothesis" and not change["experience_rules"]:
            raise PatchRefused(
                f"{path_label}.experience_rules is required for experience_hypothesis"
            )
        if not isinstance(change["allow_sensitive_flags"], list) or not all(
            isinstance(item, str) for item in change["allow_sensitive_flags"]
        ):
            raise PatchRefused(f"{path_label}.allow_sensitive_flags must be a string array")
        unknown_flags = set(change["allow_sensitive_flags"]) - ALLOWED_SENSITIVE_FLAGS
        if unknown_flags:
            raise PatchRefused(
                f"{path_label}.allow_sensitive_flags contains unsupported categories"
            )
        target = (tuple(change["scope_path"]), change["node_id"])
        if target in seen:
            raise PatchRefused(f"{path_label} duplicates another scope/node target")
        seen.add(target)
    return manifest, snapshot


def line_ending(line: str) -> tuple[str, str]:
    for ending in ("\r\n", "\n", "\r"):
        if line.endswith(ending):
            return line[: -len(ending)], ending
    return line, ""


def parse_plain_dts(raw: bytes, source: str) -> tuple[str, list[str], list[dict[str, Any]]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PatchRefused(f"baseline is not UTF-8: {exc.reason}") from None
    lines = text.splitlines(keepends=True)
    if not lines and text == "":
        raise PatchRefused("baseline is empty")
    records: list[dict[str, Any]] = []
    for line_index, line in enumerate(lines):
        body, _ = line_ending(line)
        if not body.strip(" \t\ufeff"):
            continue
        token = body.strip(" \t\ufeff")
        if token.startswith("(") and token.endswith(")"):
            token = token[1:-1].strip()
        if not token.startswith("{"):
            raise PatchRefused(
                "baseline patch v1 accepts only object records, not top-level arrays"
            )
        try:
            parsed = parse_dts_records(body, f"{source}:{line_index + 1}")
        except InspectionError as exc:
            raise PatchRefused(
                f"baseline must use one complete DTS record per physical line: {exc}"
            ) from None
        if len(parsed) != 1:
            raise PatchRefused("baseline must contain exactly one object record per non-empty line")
        records.append(
            {
                "line_index": line_index,
                "location": parsed[0]["location"],
                "value": parsed[0]["value"],
            }
        )
    if not records:
        raise PatchRefused("baseline contains no DTS records")
    return text, lines, records


def unwrap_definition(value: Any, location: str) -> tuple[dict[str, Any], bool]:
    if isinstance(value, dict):
        return copy.deepcopy(value), False
    if not isinstance(value, str) or not value.strip():
        raise PatchRefused(f"{location} is missing or is not an object/JSON string")
    candidate = value.strip()
    wrapped = candidate.startswith("(") and candidate.endswith(")")
    if wrapped:
        candidate = candidate[1:-1].strip()
    try:
        parsed = json.loads(
            candidate,
            parse_constant=reject_nonfinite_json,
            parse_float=parse_finite_json_float,
            object_pairs_hook=reject_duplicate_object_pairs,
        )
    except json.JSONDecodeError as exc:
        raise PatchRefused(
            f"{location} has invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from None
    except RecursionError:
        raise PatchRefused(f"{location} exceeds the supported JSON nesting depth") from None
    if not isinstance(parsed, dict):
        raise PatchRefused(f"{location} must contain a JSON object")
    return parsed, wrapped


def serialize_definition(value: dict[str, Any], wrapped: bool) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return f"({payload})" if wrapped else payload


def node_index(container: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    """Map analyzer-visible node ids to their actual JSON object keys."""

    nodes = container.get("nodes")
    if not isinstance(nodes, dict):
        raise PatchRefused("each patched flow scope must contain a nodes object")
    indexed: dict[str, tuple[str, dict[str, Any]]] = {}
    for raw_key, node in nodes.items():
        if not isinstance(node, dict):
            raise PatchRefused("node definitions must be objects")
        raw_node_id = node.get("id", raw_key)
        if not isinstance(raw_node_id, (str, int, float, bool)):
            raise PatchRefused("node ids must be scalar")
        node_id = scalar_text(raw_node_id)
        if not node_id:
            raise PatchRefused("node ids must not be empty")
        if node_id in indexed:
            raise PatchRefused("node ids must be unique within each patched scope")
        indexed[node_id] = (str(raw_key), node)
    return indexed


def expand_subflows(
    container: dict[str, Any],
    path: tuple[str, ...] = (),
    string_paths: dict[tuple[str, ...], bool] | None = None,
    depth: int = 0,
) -> dict[tuple[str, ...], bool]:
    if depth > 32:
        raise PatchRefused("subflow nesting exceeds 32 levels")
    paths = string_paths if string_paths is not None else {}
    for node_id, (_, node) in node_index(container).items():
        sub_raw = node.get("subNode")
        if not sub_raw:
            continue
        child_path = path + (node_id,)
        if isinstance(sub_raw, str):
            child, wrapped = unwrap_definition(sub_raw, f"subNode:{'/'.join(child_path)}")
            node["subNode"] = child
            paths[child_path] = wrapped
        elif isinstance(sub_raw, dict):
            child = sub_raw
        else:
            raise PatchRefused("subNode must be an object or JSON string")
        expand_subflows(child, child_path, paths, depth + 1)
    return paths


def collapse_subflows(
    container: dict[str, Any],
    string_paths: dict[tuple[str, ...], bool],
    path: tuple[str, ...] = (),
) -> None:
    for node_id, (_, node) in node_index(container).items():
        sub_node = node.get("subNode") if isinstance(node, dict) else None
        if not isinstance(sub_node, dict):
            continue
        child_path = path + (node_id,)
        collapse_subflows(sub_node, string_paths, child_path)
        if child_path in string_paths:
            node["subNode"] = serialize_definition(sub_node, string_paths[child_path])


def resolve_target_node(
    definition: dict[str, Any],
    scope_path: list[str],
    node_id: str,
) -> tuple[dict[str, Any], list[str]]:
    scope = definition
    key_path: list[str] = []
    for block_id in scope_path:
        indexed = node_index(scope)
        if block_id not in indexed:
            raise PatchRefused("scope_path does not exist in the selected flow")
        block_key, block = indexed[block_id]
        if not isinstance(block, dict) or not isinstance(block.get("subNode"), dict):
            raise PatchRefused("scope_path must traverse Block nodes with subNode definitions")
        key_path.append(block_key)
        scope = block["subNode"]
    indexed = node_index(scope)
    if node_id not in indexed:
        raise PatchRefused("node_id does not exist in the selected scope")
    node_key, node = indexed[node_id]
    if not isinstance(node, dict) or scalar_text(node.get("type")).lower() != "script":
        raise PatchRefused("node_id must identify a Script node")
    key_path.append(node_key)
    return node, key_path


def target_node(definition: dict[str, Any], scope_path: list[str], node_id: str) -> dict[str, Any]:
    return resolve_target_node(definition, scope_path, node_id)[0]


def read_replacement(
    manifest_path: Path,
    change: dict[str, Any],
    baseline_path: Path,
) -> tuple[str, bytes, list[str], FileSnapshot]:
    try:
        root = manifest_path.parent.resolve(strict=True)
        lexical_candidate = (manifest_path.parent / change["replacement_file"]).absolute()
        candidate = lexical_candidate.resolve(strict=True)
        candidate.relative_to(root)
        if not candidate.is_file():
            raise PatchRefused("replacement_file does not exist or is not a file")
        if candidate.samefile(baseline_path) or candidate.samefile(manifest_path):
            raise PatchRefused("replacement_file cannot alias the baseline or manifest")
        with lexical_candidate.open("rb") as handle:
            raw = read_limited(handle, MAX_REPLACEMENT_BYTES, "replacement_file")
    except PatchRefused:
        raise
    except ValueError:
        raise PatchRefused("replacement_file escapes the manifest directory") from None
    except OSError:
        raise PatchRefused("replacement_file is unavailable or cannot be verified") from None
    if sha256_bytes(raw) != change["replacement_sha256"]:
        raise PatchRefused("replacement_sha256 does not match replacement_file")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise PatchRefused("replacement_file must not contain a UTF-8 BOM")
    try:
        script = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PatchRefused(f"replacement_file is not UTF-8: {exc.reason}") from None
    if not script.strip():
        raise PatchRefused("replacement_file is empty")
    flags = script_flags(script)
    if "credential_literal" in flags:
        raise PatchRefused("replacement_file contains a credential literal")
    if set(flags) - set(change["allow_sensitive_flags"]):
        raise PatchRefused("replacement_file has unacknowledged sensitive literal categories")
    snapshot = FileSnapshot(
        "replacement_file",
        lexical_candidate,
        candidate,
        sha256_bytes(raw),
        len(raw),
        MAX_REPLACEMENT_BYTES,
    )
    return script, raw, flags, snapshot


def increment_version(value: Any) -> Any:
    if isinstance(value, bool):
        raise PatchRefused("version boolean cannot be incremented")
    if isinstance(value, int):
        return value + 1
    if isinstance(value, str) and value.isdigit():
        if len(value) > MAX_VERSION_DIGITS:
            raise PatchRefused("numeric string version is too long to increment safely")
        return str(int(value) + 1).zfill(len(value))
    raise PatchRefused("version must be an integer or numeric string for automatic +1")


def decoded_definition_pointer(key_path: list[str]) -> str:
    parts = ["nodes"]
    for block_key in key_path[:-1]:
        parts.extend([block_key, "subNode", "nodes"])
    parts.extend([key_path[-1], "script"])
    parts = [scalar_text(part, "<redacted>") for part in parts]
    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)


def rebuild_target_line(original_line: str, flow: dict[str, Any]) -> str:
    body, ending = line_ending(original_line)
    prefix_length = 0
    while prefix_length < len(body) and (
        body[prefix_length].isspace() or body[prefix_length] == "\ufeff"
    ):
        prefix_length += 1
    prefix = body[:prefix_length]
    token = body[prefix_length:].rstrip(" \t")
    trailing = body[len(body.rstrip(" \t")) :]
    if token.startswith("(") and token.endswith(")"):
        wrapped = True
    elif token.startswith("{") and token.endswith("}"):
        wrapped = False
    else:
        raise PatchRefused("target record must be one plain or parenthesized JSON object line")
    payload = json.dumps(
        flow,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return prefix + (f"({payload})" if wrapped else payload) + trailing + ending


def bounded_file_sha256(path: Path, limit: int, label: str) -> str:
    digest = hashlib.sha256()
    total = 0
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(min(1024 * 1024, limit - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise PatchRefused(f"{label} exceeds its validated size limit")
                digest.update(chunk)
    except PatchRefused:
        raise
    except OSError:
        raise PatchRefused(f"{label} became unavailable after validation") from None
    return digest.hexdigest()


def verify_file_snapshot(snapshot: FileSnapshot) -> None:
    try:
        if snapshot.lexical_path.resolve(strict=True) != snapshot.resolved_path:
            raise PatchRefused(f"{snapshot.label} path changed after validation")
        if not snapshot.lexical_path.is_file():
            raise PatchRefused(f"{snapshot.label} is no longer a file")
        if snapshot.lexical_path.stat().st_size != snapshot.size:
            raise PatchRefused(f"{snapshot.label} size changed after validation")
        if bounded_file_sha256(
            snapshot.lexical_path,
            snapshot.max_bytes,
            snapshot.label,
        ) != snapshot.sha256:
            raise PatchRefused(f"{snapshot.label} content changed after validation")
    except PatchRefused:
        raise
    except (OSError, ValueError):
        raise PatchRefused(f"{snapshot.label} became unavailable after validation") from None


def verify_input_snapshots(snapshots: list[FileSnapshot]) -> None:
    for snapshot in snapshots:
        verify_file_snapshot(snapshot)
    baseline = snapshots[0]
    manifest = snapshots[1]
    for replacement in snapshots[2:]:
        try:
            if os.path.samefile(replacement.lexical_path, baseline.lexical_path) or os.path.samefile(
                replacement.lexical_path, manifest.lexical_path
            ):
                raise PatchRefused("replacement_file became an alias of a protected input")
        except PatchRefused:
            raise
        except (OSError, ValueError):
            raise PatchRefused("replacement_file identity could not be verified") from None


def rename_no_replace(source: Path, destination: Path) -> None:
    """Atomically rename without replacing a destination on supported host platforms."""

    if sys.platform == "darwin":
        libc = ctypes.CDLL(None, use_errno=True)
        try:
            rename_exclusive = libc.renamex_np
        except AttributeError:
            raise PatchRefused("atomic no-replace publication is unavailable") from None
        rename_exclusive.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename_exclusive.restype = ctypes.c_int
        ctypes.set_errno(0)
        result = rename_exclusive(os.fsencode(source), os.fsencode(destination), 0x00000004)
    elif sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        try:
            rename_exclusive = libc.renameat2
        except AttributeError:
            raise PatchRefused("atomic no-replace publication is unavailable") from None
        rename_exclusive.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename_exclusive.restype = ctypes.c_int
        ctypes.set_errno(0)
        result = rename_exclusive(
            -100,
            os.fsencode(source),
            -100,
            os.fsencode(destination),
            0x00000001,
        )
    elif os.name == "nt":
        os.rename(source, destination)
        return
    else:
        raise PatchRefused("atomic no-replace publication is unavailable")

    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(error_number, "destination exists")
    raise OSError(error_number, "atomic no-replace rename failed")


def publish_review_copy(
    output_path: Path,
    output_raw: bytes,
    expected_output_sha256: str,
    snapshots: list[FileSnapshot],
) -> Path:
    """Publish a new review copy atomically without replacing any directory entry."""

    if any(ord(char) < 32 for char in str(output_path)):
        raise PatchRefused("output path contains unsupported characters")
    try:
        lexical_output = output_path.absolute()
        lexical_output.parent.mkdir(parents=True, exist_ok=True)
        if not lexical_output.parent.is_dir():
            raise PatchRefused("output parent is not a directory")
        if os.path.lexists(lexical_output):
            raise PatchRefused("output already exists; review-copy generation never overwrites")
        resolved_output = lexical_output.resolve(strict=False)
        if any(
            resolved_output == snapshot.resolved_path
            or lexical_output == snapshot.lexical_path
            for snapshot in snapshots
        ):
            raise PatchRefused("output conflicts with a protected input")
    except PatchRefused:
        raise
    except (OSError, ValueError):
        raise PatchRefused("output path is unavailable or unsupported") from None

    staging_dir: Path | None = None
    staging_identity: tuple[int, int] | None = None
    temp_path: Path | None = None
    temp_handle: Any | None = None
    committed = False
    try:
        staging_dir = Path(
            tempfile.mkdtemp(
                dir=lexical_output.parent,
                prefix=f".{lexical_output.name}.stage.{secrets.token_hex(16)}.",
            )
        )
        staging_dir.chmod(0o700)
        staging_stat = staging_dir.lstat()
        staging_identity = (staging_stat.st_dev, staging_stat.st_ino)
        temp_path = staging_dir / "payload.tmp"
        temp_handle = temp_path.open("x+b")
        if temp_handle.write(output_raw) != len(output_raw):
            raise PatchRefused("prepared review-copy write was incomplete")
        temp_handle.flush()
        os.fsync(temp_handle.fileno())
        if os.fstat(temp_handle.fileno()).st_size != len(output_raw):
            raise PatchRefused("prepared review-copy size differs before publication")
        temp_handle.seek(0)
        prepared_hash = hashlib.sha256()
        remaining = len(output_raw)
        while remaining:
            chunk = temp_handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            prepared_hash.update(chunk)
            remaining -= len(chunk)
        if remaining or prepared_hash.hexdigest() != expected_output_sha256:
            raise PatchRefused("prepared review-copy hash differs before publication")
        verify_input_snapshots(snapshots)
        try:
            rename_no_replace(temp_path, lexical_output)
        except FileExistsError:
            raise PatchRefused("output appeared during publication; nothing was overwritten") from None
        except OSError:
            raise PatchRefused("review copy could not be published without overwrite") from None
        committed = True
        temp_path = None
        return lexical_output
    except PatchRefused:
        raise
    except (OSError, ValueError):
        raise PatchRefused("review-copy publication could not be verified") from None
    finally:
        cleanup_failed = False
        if temp_handle is not None:
            try:
                if not committed:
                    temp_handle.seek(0)
                    temp_handle.truncate(0)
                    temp_handle.flush()
                    os.fsync(temp_handle.fileno())
            except OSError:
                cleanup_failed = True
            finally:
                try:
                    temp_handle.close()
                except OSError:
                    cleanup_failed = True
        if staging_dir is not None and staging_identity is not None:
            try:
                current_stage = staging_dir.lstat()
                if (current_stage.st_dev, current_stage.st_ino) != staging_identity:
                    cleanup_failed = True
                else:
                    if temp_path is not None and os.path.lexists(temp_path):
                        temp_path.unlink()
                    staging_dir.rmdir()
            except OSError:
                cleanup_failed = True
        if cleanup_failed and not committed:
            raise PatchRefused(
                "private staging content could not be removed after refusal"
            ) from None
        if cleanup_failed and committed:
            # The review copy is already committed atomically; staging contains no payload.
            pass


def build_review_copy(
    baseline_path: Path,
    manifest_path: Path,
    max_input_bytes: int,
) -> tuple[bytes, dict[str, Any], list[FileSnapshot]]:
    if zipfile.is_zipfile(baseline_path):
        raise PatchRefused("ZIP patching is not supported in v1; analyze ZIP read-only and select a plain DTS")
    try:
        if not baseline_path.exists() or not baseline_path.is_file():
            raise PatchRefused("baseline does not exist or is not a file")
        baseline_lexical = baseline_path.absolute()
        baseline_resolved = baseline_path.resolve(strict=True)
        with baseline_path.open("rb") as handle:
            baseline_raw = read_limited(handle, max_input_bytes, "baseline")
    except PatchRefused:
        raise
    except (OSError, ValueError):
        raise PatchRefused("baseline path is unavailable or unsupported") from None
    manifest, manifest_snapshot = validate_manifest(manifest_path)
    input_sha256 = sha256_bytes(baseline_raw)
    baseline_snapshot = FileSnapshot(
        "baseline",
        baseline_lexical,
        baseline_resolved,
        input_sha256,
        len(baseline_raw),
        max_input_bytes,
    )
    if input_sha256 != manifest["input_sha256"]:
        raise PatchRefused("input_sha256 does not match the current baseline")

    _, lines, records = parse_plain_dts(baseline_raw, scalar_text(baseline_path.name, "baseline.dts"))
    matches = [
        record for record in records
        if record["value"].get("$entityname") == "isc_service_flow"
        and scalar_text(record["value"].get("number")) == manifest["flow_number"]
    ]
    if len(matches) != 1:
        raise PatchRefused("flow_number must match exactly one isc_service_flow record")
    selected = matches[0]
    original_flow = copy.deepcopy(selected["value"])
    flow = copy.deepcopy(original_flow)
    definition_field = "define_json_tag" if flow.get("define_json_tag") is not None else "define_json"
    if definition_field not in flow:
        raise PatchRefused("selected flow has no define_json_tag/define_json")
    original_definition, top_wrapped = unwrap_definition(
        flow[definition_field], f"flow.{definition_field}"
    )
    original_expanded = copy.deepcopy(original_definition)
    original_string_paths = expand_subflows(original_expanded)
    modified_expanded = copy.deepcopy(original_expanded)

    change_reports: list[dict[str, Any]] = []
    old_scripts: list[tuple[list[str], str, str]] = []
    replacement_snapshots: list[FileSnapshot] = []
    total_replacement_bytes = 0
    for index, change in enumerate(manifest["changes"]):
        node, key_path = resolve_target_node(
            modified_expanded, change["scope_path"], change["node_id"]
        )
        old_script = node.get("script")
        if not isinstance(old_script, str):
            raise PatchRefused("target Script node has no string script content")
        old_hash = sha256_text(old_script)
        if old_hash != change["expected_script_sha256"]:
            raise PatchRefused("expected_script_sha256 does not match the current target node")
        replacement, replacement_raw, flags, replacement_snapshot = read_replacement(
            manifest_path, change, baseline_path
        )
        total_replacement_bytes += len(replacement_raw)
        if total_replacement_bytes > MAX_TOTAL_REPLACEMENT_BYTES:
            raise PatchRefused(
                "replacement files exceed the supported cumulative size limit"
            )
        replacement_snapshots.append(replacement_snapshot)
        new_hash = sha256_text(replacement)
        if new_hash == old_hash:
            raise PatchRefused("replacement Script is identical to the current target node")
        node["script"] = replacement
        old_scripts.append((change["scope_path"], change["node_id"], old_script))
        change_reports.append(
            {
                "index": index,
                "definition_field_pointer": f"/{definition_field}",
                "decoded_definition_pointer": decoded_definition_pointer(key_path),
                "definition_storage": (
                    "json_string" if isinstance(original_flow[definition_field], str) else "object"
                ),
                "old_script_sha256": old_hash,
                "new_script_sha256": new_hash,
                "replacement_sha256": sha256_bytes(replacement_raw),
                "replacement_bytes": len(replacement_raw),
                "replacement_lines": replacement.count("\n") + 1,
                "declared_evidence_level": change["evidence_level"],
                "evidence_verified": False,
                "experience_rules": list(change["experience_rules"]),
                "sensitive_flags": flags,
            }
        )

    restored_definition = copy.deepcopy(modified_expanded)
    for scope_path, node_id, old_script in old_scripts:
        target_node(restored_definition, scope_path, node_id)["script"] = old_script
    if restored_definition != original_expanded:
        raise PatchRefused("unexpected semantic changes were detected outside target scripts")

    collapsed_definition = copy.deepcopy(modified_expanded)
    collapse_subflows(collapsed_definition, original_string_paths)
    if isinstance(flow[definition_field], str):
        flow[definition_field] = serialize_definition(collapsed_definition, top_wrapped)
    else:
        flow[definition_field] = collapsed_definition

    metadata = manifest["metadata"]
    if flow.get("version") != metadata["expected_version"]:
        raise PatchRefused("metadata.expected_version does not match the selected flow")
    if flow.get("modifytime") != metadata["expected_modifytime"]:
        raise PatchRefused("metadata.expected_modifytime does not match the selected flow")
    old_comment = flow.get("comment", "")
    if not isinstance(old_comment, str):
        raise PatchRefused("selected flow comment must be a string or absent")
    if sha256_text(old_comment) != metadata["expected_comment_sha256"]:
        raise PatchRefused("metadata.expected_comment_sha256 does not match the selected flow")
    old_version = flow.get("version")
    new_version = increment_version(old_version)
    flow["version"] = new_version
    flow["modifytime"] = metadata["new_modifytime"]
    flow["comment"] = (
        old_comment + metadata["comment_separator"] + metadata["summary"]
        if old_comment
        else metadata["summary"]
    )

    restored_flow = copy.deepcopy(flow)
    for key in (definition_field, "version", "modifytime", "comment"):
        if key in original_flow:
            restored_flow[key] = copy.deepcopy(original_flow[key])
        else:
            restored_flow.pop(key, None)
    if restored_flow != original_flow:
        raise PatchRefused("unexpected top-level flow fields changed")

    output_lines = list(lines)
    output_lines[selected["line_index"]] = rebuild_target_line(
        lines[selected["line_index"]], flow
    )
    output_text = "".join(output_lines)
    output_raw = output_text.encode("utf-8")
    if len(output_raw) > min(
        MAX_OUTPUT_BYTES,
        max_input_bytes + MAX_TOTAL_REPLACEMENT_BYTES,
    ):
        raise PatchRefused("review copy exceeds the supported output size limit")
    for record in records:
        if record["line_index"] == selected["line_index"]:
            continue
        if output_lines[record["line_index"]].encode("utf-8") != lines[
            record["line_index"]
        ].encode("utf-8"):
            raise PatchRefused("a non-target record changed unexpectedly")

    snapshots = [baseline_snapshot, manifest_snapshot, *replacement_snapshots]
    verify_input_snapshots(snapshots)
    evidence_counts = Counter(item["declared_evidence_level"] for item in change_reports)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "validated_patch_plan_not_generated",
        "platform_execution": False,
        "requires_platform_validation": True,
        "input": scalar_text(baseline_path.name, "baseline.dts"),
        "input_sha256": input_sha256,
        "manifest_sha256": manifest_snapshot.sha256,
        "review_copy_sha256": sha256_bytes(output_raw),
        "flow_number": scalar_text(manifest["flow_number"], "<redacted>"),
        "version": {"old": old_version, "new": new_version},
        "modifytime": {"old_sha256": sha256_text(str(metadata["expected_modifytime"])), "new": metadata["new_modifytime"]},
        "comment": {
            "old_sha256": metadata["expected_comment_sha256"],
            "new_sha256": sha256_text(flow["comment"]),
            "summary_sha256": sha256_text(metadata["summary"]),
        },
        "changes": change_reports,
        "declared_evidence_level_counts": dict(sorted(evidence_counts.items())),
        "evidence_artifacts_verified": False,
        "unchanged_record_bytes": {
            "unchanged": len(records) - 1,
            "total": len(records),
        },
        "non_target_nodes_semantically_identical": True,
        "unexpected_diff_paths": [],
        "input_unchanged": True,
        "input_snapshots_verified": True,
    }
    return output_raw, report, snapshots


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "generate"):
        command = subparsers.add_parser(name)
        command.add_argument("--baseline", required=True, type=Path)
        command.add_argument("--manifest", required=True, type=Path)
        command.add_argument(
            "--max-input-bytes",
            type=positive_int,
            default=DEFAULT_MAX_INPUT_BYTES,
        )
        if name == "generate":
            command.add_argument("--output", required=True, type=Path)
    return parser


def emit_error(status: str, message: str, code: int) -> int:
    payload = {"status": status, "message": message}
    print(json.dumps(payload, ensure_ascii=False, allow_nan=False), file=sys.stderr)
    return code


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output_raw, report, snapshots = build_review_copy(
            args.baseline,
            args.manifest,
            args.max_input_bytes,
        )
        if args.command == "generate":
            published_output = publish_review_copy(
                args.output,
                output_raw,
                report["review_copy_sha256"],
                snapshots,
            )
            report["status"] = "generated_review_copy_not_imported"
            report["output"] = scalar_text(published_output.name, "review.dts")
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (PatchRefused, InspectionError) as exc:
        return emit_error("patch_refused", str(exc), 1)
    except RecursionError:
        return emit_error("patch_refused", "input exceeds the supported nesting depth", 1)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return emit_error("patch_error", f"local patch operation failed: {type(exc).__name__}", 2)


if __name__ == "__main__":
    raise SystemExit(main())
