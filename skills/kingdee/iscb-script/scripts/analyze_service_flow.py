#!/usr/bin/env python3
"""Read-only inspection of ISCB service-flow topology in DTS files or ZIP packages."""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Iterable, Iterator


SENSITIVE_NAME_RE = re.compile(
    r"(?:password|passwd|pwd|token|secret|cookie|credential|access[_-]?key|"
    r"app[_-]?(?:key|secret)|connection[_-]?string|jdbc|host|domain|tenant|eid)",
    re.IGNORECASE,
)
SENSITIVE_LITERAL_RE = re.compile(
    r"\b(?:password|passwd|pwd|token|secret|cookie|credential|access[_-]?key|"
    r"app[_-]?(?:key|secret))\b\s*[:=]\s*(['\"]).*?\1",
    re.IGNORECASE | re.DOTALL,
)
SENSITIVE_INLINE_RE = re.compile(
    r"\b(?:password|passwd|pwd|token|secret|cookie|credential|access[_-]?key|"
    r"app[_-]?(?:key|secret))\b\s*[:=]",
    re.IGNORECASE,
)
URL_LITERAL_RE = re.compile(r"https?://[^\s'\"]+", re.IGNORECASE)
JDBC_LITERAL_RE = re.compile(r"jdbc:[^\s'\"]+", re.IGNORECASE)
BIZQUERY_STRING_CONNECTION_RE = re.compile(r"\bbizQuery\s*\(\s*(['\"])", re.IGNORECASE)
DIGEST_VARIABLE_RE = re.compile(r"#\{\s*([A-Za-z_$][\w$]*)\s*\}")
SEPARATOR_CHARS = " \t\r\n,;\ufeff"
DEFAULT_MAX_INPUT_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_ZIP_MEMBERS = 128


class InspectionError(ValueError):
    """Raised when an input cannot be inspected safely or unambiguously."""


def reject_nonfinite_json(value: str) -> Any:
    raise InspectionError(f"non-finite JSON constant is not allowed: {value}")


def parse_finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise InspectionError("non-finite JSON number is not allowed")
    return parsed


def reject_duplicate_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject ambiguous JSON objects without echoing untrusted keys or values."""

    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InspectionError("duplicate JSON object key is not allowed")
        result[key] = value
    return result


def _line_starts(text: str) -> list[int]:
    starts = [0]
    starts.extend(index + 1 for index, char in enumerate(text) if char == "\n")
    return starts


def _line_number(starts: list[int], offset: int) -> int:
    return bisect.bisect_right(starts, offset)


def parse_dts_records(text: str, source: str) -> list[dict[str, Any]]:
    """Parse adjacent, wrapped, multiline JSON DTS records without regex slicing."""

    decoder = json.JSONDecoder(
        parse_constant=reject_nonfinite_json,
        parse_float=parse_finite_json_float,
        object_pairs_hook=reject_duplicate_object_pairs,
    )
    starts = _line_starts(text)
    records: list[dict[str, Any]] = []
    position = 0
    length = len(text)
    while position < length:
        while position < length and text[position] in SEPARATOR_CHARS:
            position += 1
        if position >= length:
            break

        record_start = position
        wrapped = text[position] == "("
        if wrapped:
            position += 1
            while position < length and text[position].isspace():
                position += 1
        try:
            value, end = decoder.raw_decode(text, position)
        except json.JSONDecodeError as exc:
            line = _line_number(starts, exc.pos)
            raise InspectionError(
                f"{source}:{line}: invalid DTS JSON at column {exc.colno}: {exc.msg}"
            ) from None
        except RecursionError:
            line = _line_number(starts, record_start)
            raise InspectionError(
                f"{source}:{line}: DTS JSON exceeds the supported nesting depth"
            ) from None
        position = end
        while position < length and text[position].isspace():
            position += 1
        if wrapped:
            if position >= length or text[position] != ")":
                line = _line_number(starts, position)
                raise InspectionError(f"{source}:{line}: wrapped DTS record is missing closing ')'")
            position += 1

        values = value if isinstance(value, list) else [value]
        if not all(isinstance(item, dict) for item in values):
            line = _line_number(starts, record_start)
            raise InspectionError(f"{source}:{line}: DTS record must be an object or object array")
        line = _line_number(starts, record_start)
        for array_index, item in enumerate(values):
            suffix = f"[{array_index}]" if isinstance(value, list) else ""
            records.append({"location": f"{source}:{line}{suffix}", "value": item})
    return records


def read_limited(handle: Any, limit: int, label: str) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = handle.read(min(1024 * 1024, limit - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise InspectionError(f"{label} exceeds --max-input-bytes ({limit})")
        chunks.append(chunk)
    return b"".join(chunks)


def iter_inputs(
    path: Path,
    max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES,
    max_zip_members: int = DEFAULT_MAX_ZIP_MEMBERS,
) -> Iterator[tuple[str, str, str]]:
    """Yield safe display name, decoded text, and SHA-256 for a DTS file or ZIP."""

    display_name = scalar_text(path.name, "input")
    if not path.exists() or not path.is_file():
        raise InspectionError(f"input does not exist or is not a file: {display_name}")
    if path.stat().st_size > max_input_bytes:
        raise InspectionError(
            f"input exceeds --max-input-bytes ({max_input_bytes}): {display_name}"
        )
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            members = sorted(
                (
                    info for info in archive.infolist()
                    if not info.is_dir() and info.filename.lower().endswith(".dts")
                ),
                key=lambda info: info.filename,
            )
            if not members:
                raise InspectionError(f"ZIP contains no .dts files: {display_name}")
            if len(members) > max_zip_members:
                raise InspectionError(
                    f"ZIP contains more than --max-zip-members ({max_zip_members}) DTS files"
                )
            total_size = sum(info.file_size for info in members)
            if total_size > max_input_bytes:
                raise InspectionError(
                    f"ZIP DTS content exceeds --max-input-bytes ({max_input_bytes})"
                )
            remaining = max_input_bytes
            for index, info in enumerate(members, 1):
                try:
                    with archive.open(info) as member:
                        raw = read_limited(
                            member,
                            remaining,
                            f"{display_name}!member-{index}",
                        )
                except (RuntimeError, NotImplementedError, zipfile.BadZipFile) as exc:
                    raise InspectionError(
                        f"{display_name}!member-{index}: cannot read DTS member: {type(exc).__name__}"
                    ) from None
                remaining -= len(raw)
                try:
                    text = raw.decode("utf-8-sig")
                except UnicodeDecodeError as exc:
                    raise InspectionError(
                        f"{display_name}!member-{index}: DTS is not UTF-8: {exc.reason}"
                    ) from None
                member_name = scalar_text(Path(info.filename).name, f"member-{index}.dts")
                source = f"{display_name}!member-{index}:{member_name}"
                yield source, text, hashlib.sha256(raw).hexdigest()
        return

    with path.open("rb") as handle:
        raw = read_limited(handle, max_input_bytes, display_name)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InspectionError(f"{display_name}: DTS is not UTF-8: {exc.reason}") from None
    yield display_name, text, hashlib.sha256(raw).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unwrap_json(value: Any, location: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        raise InspectionError(f"{location}: service-flow definition is missing or is not JSON text")
    candidate = value.strip()
    if candidate.startswith("(") and candidate.endswith(")"):
        candidate = candidate[1:-1].strip()
    try:
        parsed = json.loads(
            candidate,
            parse_constant=reject_nonfinite_json,
            parse_float=parse_finite_json_float,
            object_pairs_hook=reject_duplicate_object_pairs,
        )
    except json.JSONDecodeError as exc:
        raise InspectionError(
            f"{location}: invalid service-flow definition at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from None
    except RecursionError:
        raise InspectionError(
            f"{location}: service-flow definition exceeds the supported nesting depth"
        ) from None
    if not isinstance(parsed, dict):
        raise InspectionError(f"{location}: service-flow definition must be an object")
    return parsed


def localized_name(value: Any, fallback: str = "") -> str:
    if isinstance(value, str):
        return scalar_text(value, fallback)
    if isinstance(value, dict):
        for key in ("zh_CN", "zh_TW", "en_US"):
            if isinstance(value.get(key), str) and value[key]:
                return scalar_text(value[key], fallback)
    return fallback


def primitive(value: Any) -> Any:
    if isinstance(value, str):
        return scalar_text(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value if value is None or isinstance(value, (int, float, bool)) else None


def scalar_text(value: Any, fallback: str = "") -> str:
    if value is None or not isinstance(value, (str, int, float, bool)):
        return fallback
    text = str(value)
    if (
        SENSITIVE_NAME_RE.search(text)
        or SENSITIVE_INLINE_RE.search(text)
        or URL_LITERAL_RE.search(text)
        or JDBC_LITERAL_RE.search(text)
    ):
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        return f"<redacted:{digest}>"
    return "".join(char if char >= " " else " " for char in text)


def same_existing_file(left: Path, right: Path) -> bool:
    try:
        return left.exists() and right.exists() and os.path.samefile(left, right)
    except OSError:
        return False


def lexists(path: Path) -> bool:
    return os.path.lexists(path)


def diagnostic(
    severity: str,
    code: str,
    location: str,
    message: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "location": location,
        "message": message,
    }
    if evidence:
        result["evidence"] = evidence
    return result


def normalize_nodes(value: Any, location: str, diagnostics: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    items: Iterable[tuple[Any, Any]]
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, list):
        items = enumerate(value)
    elif value is None:
        return []
    else:
        diagnostics.append(diagnostic("error", "INVALID_NODES", location, "nodes must be an object or array"))
        return []

    normalized: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for key, node in items:
        fallback_id = scalar_text(key, f"node-{len(normalized)}")
        if not isinstance(node, dict):
            diagnostics.append(
                diagnostic("error", "INVALID_NODE", f"{location}.{fallback_id}", "node must be an object")
            )
            continue
        raw_node_id = node.get("id", key)
        node_id = scalar_text(raw_node_id, fallback_id)
        if not isinstance(raw_node_id, (str, int, float, bool)):
            diagnostics.append(
                diagnostic(
                    "error",
                    "INVALID_NODE_ID",
                    f"{location}.{fallback_id}",
                    "node id must be a scalar; container content was not emitted",
                )
            )
        if node_id in seen:
            diagnostics.append(
                diagnostic("error", "DUPLICATE_NODE_ID", location, "node id is duplicated", {"node_id": node_id})
            )
            continue
        seen.add(node_id)
        normalized.append((node_id, node))
    return normalized


def endpoint(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("id", "nodeId", "node_id"):
            if key in value:
                return scalar_text(value[key])
        return ""
    return scalar_text(value)


def normalize_links(value: Any, location: str, diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: Iterable[tuple[Any, Any]]
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, list):
        items = enumerate(value)
    elif value is None:
        return []
    else:
        diagnostics.append(diagnostic("error", "INVALID_LINKS", location, "links must be an object or array"))
        return []

    links: list[dict[str, Any]] = []
    for key, link in items:
        if not isinstance(link, dict):
            diagnostics.append(
                diagnostic("error", "INVALID_LINK", f"{location}.{key}", "link must be an object")
            )
            continue
        source = endpoint(link.get("source", link.get("src", link.get("sourceId"))))
        target = endpoint(link.get("target", link.get("dst", link.get("targetId"))))
        raw_link_id = link.get("id", key)
        links.append(
            {
                "id": scalar_text(raw_link_id, scalar_text(key, f"link-{len(links)}")),
                "source": source,
                "target": target,
                "has_condition": bool(link.get("condition") or link.get("title")),
            }
        )
    return links


def script_flags(script: str) -> list[str]:
    flags: list[str] = []
    if SENSITIVE_LITERAL_RE.search(script):
        flags.append("credential_literal")
    if URL_LITERAL_RE.search(script):
        flags.append("endpoint_literal")
    if JDBC_LITERAL_RE.search(script):
        flags.append("connection_literal")
    return flags


def safe_component(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")[:48]
    return normalized or fallback


def _subflow(value: Any, location: str, diagnostics: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not value:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return unwrap_json(value, location)
        except InspectionError as exc:
            diagnostics.append(diagnostic("error", "INVALID_SUBFLOW", location, str(exc)))
            return None
    diagnostics.append(diagnostic("error", "INVALID_SUBFLOW", location, "subNode must be an object or JSON text"))
    return None


def inspect_scope(
    container: dict[str, Any],
    path: str,
    name: str,
    flow_number: str,
    record_location: str,
    diagnostics: list[dict[str, Any]],
    scripts: list[dict[str, Any]],
    depth: int = 0,
    scope_node_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    if depth > 32:
        diagnostics.append(diagnostic("error", "SUBFLOW_DEPTH", path, "subflow nesting exceeds 32 levels"))
        return {
            "path": path,
            "name": name,
            "node_count": 0,
            "link_count": 0,
            "node_type_counts": {},
            "starter_node_ids": [],
            "end_node_ids": [],
            "nodes": [],
            "links": [],
            "children": [],
        }

    nodes = normalize_nodes(container.get("nodes"), f"{path}.nodes", diagnostics)
    links = normalize_links(container.get("links"), f"{path}.links", diagnostics)
    node_ids = {node_id for node_id, _ in nodes}
    node_infos: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []
    type_counts: Counter[str] = Counter()

    for node_id, node in nodes:
        node_type = scalar_text(node.get("type", ""))
        title = localized_name(node.get("title", node.get("name")), node_id)
        type_counts[node_type or "<unknown>"] += 1
        script = node.get("script")
        has_script = isinstance(script, str) and bool(script)
        node_info = {
            "id": node_id,
            "name": title,
            "type": node_type,
            "has_script": has_script,
        }
        node_infos.append(node_info)
        if has_script:
            metadata = {
                "record_location": record_location,
                "flow_number": flow_number,
                "scope_path": path,
                "scope_node_ids": list(scope_node_ids),
                "node_id": node_id,
                "node_name": title,
                "node_type": node_type,
                "characters": len(script),
                "lines": script.count("\n") + 1,
                "sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
                "sensitive_flags": script_flags(script),
                "_content": script,
            }
            scripts.append(metadata)
            if metadata["sensitive_flags"]:
                diagnostics.append(
                    diagnostic(
                        "warning",
                        "SCRIPT_SENSITIVE_LITERAL",
                        f"{path}.nodes.{node_id}.script",
                        "script contains sensitive literal categories; values were not emitted",
                        {"categories": metadata["sensitive_flags"]},
                    )
                )
            if BIZQUERY_STRING_CONNECTION_RE.search(script):
                diagnostics.append(
                    diagnostic(
                        "error",
                        "BIZQUERY_STRING_CONNECTION",
                        f"{path}.nodes.{node_id}.script",
                        "bizQuery first argument appears to be a string, not a verified ConnectionWrapper",
                    )
                )
        subflow = _subflow(node.get("subNode"), f"{path}.nodes.{node_id}.subNode", diagnostics)
        if subflow is not None:
            children.append(
                inspect_scope(
                    subflow,
                    f"{path}/node:{node_id}",
                    title,
                    flow_number,
                    record_location,
                    diagnostics,
                    scripts,
                    depth + 1,
                    scope_node_ids + (node_id,),
                )
            )

    adjacency: dict[str, set[str]] = defaultdict(set)
    for link in links:
        missing = [value for value in (link["source"], link["target"]) if value not in node_ids]
        if missing:
            diagnostics.append(
                diagnostic(
                    "error",
                    "DANGLING_LINK",
                    f"{path}.links.{link['id']}",
                    "link endpoint is not present in this scope",
                    {"missing_node_ids": missing},
                )
            )
        elif link["source"] and link["target"]:
            adjacency[link["source"]].add(link["target"])

    starters = [
        item["id"] for item in node_infos
        if item["type"].lower().endswith("starter") or item["type"].lower() == "start"
    ]
    ends = [
        item["id"] for item in node_infos
        if item["type"].lower() in {"end", "endnode"}
    ]
    if node_infos and not starters:
        diagnostics.append(
            diagnostic("warning", "NO_STARTER", path, "no recognized starter node was found; trigger type needs review")
        )
    if node_infos and not ends:
        diagnostics.append(diagnostic("warning", "NO_END", path, "no recognized End node was found"))

    if starters:
        reachable = set(starters)
        queue: deque[str] = deque(starters)
        while queue:
            current = queue.popleft()
            for target in adjacency.get(current, set()):
                if target not in reachable:
                    reachable.add(target)
                    queue.append(target)
        for missing_id in sorted(node_ids - reachable):
            diagnostics.append(
                diagnostic(
                    "warning",
                    "UNREACHABLE_NODE",
                    path,
                    "node is not reachable from a recognized starter using declared links",
                    {"node_id": missing_id},
                )
            )

    return {
        "path": path,
        "name": name,
        "node_count": len(node_infos),
        "link_count": len(links),
        "node_type_counts": dict(sorted(type_counts.items())),
        "starter_node_ids": starters,
        "end_node_ids": ends,
        "nodes": node_infos,
        "links": links,
        "children": children,
    }


def variable_metadata(
    flow: dict[str, Any],
    diagnostics: list[dict[str, Any]],
    location: str,
) -> list[dict[str, Any]]:
    raw = flow.get("variables", flow.get("varDefs", flow.get("var_defs", [])))
    if isinstance(raw, dict):
        values = list(raw.items())
    elif isinstance(raw, list):
        values = list(enumerate(raw))
    else:
        diagnostics.append(
            diagnostic("error", "INVALID_VARIABLES", location, "variables must be an object or array")
        )
        return []
    result = []
    for index, (key, value) in enumerate(values):
        if not isinstance(value, dict):
            diagnostics.append(
                diagnostic(
                    "error",
                    "INVALID_VARIABLE",
                    f"{location}.{scalar_text(key, str(index))}",
                    "variable definition must be an object",
                )
            )
            continue
        raw_name = value.get("var_name", value.get("name", value.get("varName", key)))
        name = scalar_text(raw_name, f"variable-{index}")
        if not isinstance(raw_name, (str, int, float, bool)):
            diagnostics.append(
                diagnostic(
                    "error",
                    "INVALID_VARIABLE_NAME",
                    f"{location}.{scalar_text(key, str(index))}",
                    "variable name must be a scalar; container content was not emitted",
                )
            )
        default = value.get("default_value", value.get("defaultValue", value.get("default")))
        result.append(
            {
                "name": name,
                "type": primitive(value.get("var_type_id", value.get("type", value.get("varType")))) or "",
                "sensitive_name": bool(SENSITIVE_NAME_RE.search(name)),
                "has_default": default not in (None, ""),
            }
        )
    return result


def resource_metadata(
    flow: dict[str, Any],
    diagnostics: list[dict[str, Any]],
    location: str,
) -> list[dict[str, Any]]:
    raw = flow.get("resources", [])
    if not isinstance(raw, list):
        diagnostics.append(
            diagnostic("error", "INVALID_RESOURCES", location, "resources must be an array")
        )
        return []
    result = []
    for index, value in enumerate(raw):
        if not isinstance(value, dict):
            diagnostics.append(
                diagnostic(
                    "error",
                    "INVALID_RESOURCE",
                    f"{location}[{index}]",
                    "resource definition must be an object",
                )
            )
            continue
        alias = value.get("res_alias", value.get("alias", value.get("name", "")))
        resource_type = value.get("res_type", value.get("type", ""))
        if not isinstance(alias, (str, int, float, bool)) or not isinstance(
            resource_type, (str, int, float, bool)
        ):
            diagnostics.append(
                diagnostic(
                    "error",
                    "INVALID_RESOURCE_METADATA",
                    f"{location}[{index}]",
                    "resource alias/type must be scalar; container content was not emitted",
                )
            )
        result.append({"alias": scalar_text(alias), "type": scalar_text(resource_type)})
    return result


def flatten_scopes(scope: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield scope
    for child in scope.get("children", []):
        yield from flatten_scopes(child)


def inspect_flow(record: dict[str, Any], diagnostics: list[dict[str, Any]], scripts: list[dict[str, Any]]) -> dict[str, Any]:
    value = record["value"]
    number = scalar_text(value.get("number", ""))
    name = localized_name(value.get("name"), number)
    definition_field = "define_json_tag" if value.get("define_json_tag") is not None else "define_json"
    raw_definition = value.get(definition_field)
    variables = variable_metadata(value, diagnostics, f"{record['location']}.variables")
    flow = {
        "record_location": record["location"],
        "number": number,
        "name": name,
        "enable": primitive(value.get("enable")),
        "init_mode": primitive(value.get("init_mode")),
        "definition_field": definition_field,
        "resources": resource_metadata(value, diagnostics, f"{record['location']}.resources"),
        "variables": variables,
        "definition_status": "invalid",
        "root_scope": None,
    }
    try:
        definition = unwrap_json(raw_definition, f"{record['location']}.{definition_field}")
    except InspectionError as exc:
        diagnostics.append(diagnostic("error", "INVALID_FLOW_DEFINITION", record["location"], str(exc)))
        return flow

    flow["definition_status"] = "parsed"
    root = inspect_scope(
        definition,
        f"flow:{number or record['location']}",
        name,
        number,
        record["location"],
        diagnostics,
        scripts,
    )
    flow["root_scope"] = root
    scopes = list(flatten_scopes(root))
    aggregate_types: Counter[str] = Counter()
    for scope in scopes:
        aggregate_types.update(scope["node_type_counts"])
    flow["summary"] = {
        "scope_count": len(scopes),
        "node_count": sum(scope["node_count"] for scope in scopes),
        "link_count": sum(scope["link_count"] for scope in scopes),
        "script_count": sum(
            1 for item in scripts
            if item["flow_number"] == number and item["record_location"] == record["location"]
        ),
        "node_type_counts": dict(sorted(aggregate_types.items())),
    }

    digest = value.get("proc_digest", definition.get("proc_digest"))
    if isinstance(digest, str):
        defined = {item["name"] for item in variables}
        for missing in sorted(set(DIGEST_VARIABLE_RE.findall(digest)) - defined):
            diagnostics.append(
                diagnostic(
                    "error",
                    "DIGEST_VARIABLE_UNDEFINED",
                    f"{record['location']}.proc_digest",
                    "process digest references an undefined variable",
                    {"variable": missing},
                )
            )
    return flow


def public_script(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if key != "_content"}


def markdown_cell(value: Any) -> str:
    text = str(value)
    text = "".join(char if char >= " " else " " for char in text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("`", "&#96;")
        .replace("|", "\\|")
        .replace("!", "&#33;")
        .replace("[", "&#91;")
        .replace("]", "&#93;")
        .replace("(", "&#40;")
        .replace(")", "&#41;")
        .replace("\n", " ")
    )


def inspect_path(
    path: Path,
    flow_selector: str | None = None,
    max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES,
    max_zip_members: int = DEFAULT_MAX_ZIP_MEMBERS,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    inputs = []
    for source, text, digest in iter_inputs(path, max_input_bytes, max_zip_members):
        source_records = parse_dts_records(text, source)
        records.extend(source_records)
        inputs.append({"source": source, "sha256": digest, "record_count": len(source_records)})

    record_summaries = [
        {
            "location": record["location"],
            "entityname": scalar_text(record["value"].get("$entityname", "")),
            "number": scalar_text(record["value"].get("number", "")),
        }
        for record in records
    ]
    entity_counts = Counter(item["entityname"] or "<unknown>" for item in record_summaries)
    diagnostics: list[dict[str, Any]] = []
    scripts: list[dict[str, Any]] = []
    flow_records = [record for record in records if record["value"].get("$entityname") == "isc_service_flow"]
    flows = [inspect_flow(record, diagnostics, scripts) for record in flow_records]

    by_number: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for flow in flows:
        by_number[flow["number"]].append(flow)
    for number, matches in sorted(by_number.items()):
        if not number:
            for match in matches:
                diagnostics.append(
                    diagnostic(
                        "error",
                        "FLOW_NUMBER_MISSING",
                        match["record_location"],
                        "service-flow number is empty",
                    )
                )
        if len(matches) > 1:
            diagnostics.append(
                diagnostic(
                    "error",
                    "DUPLICATE_FLOW_NUMBER",
                    "records",
                    "service-flow number is not unique; no candidate was auto-selected",
                    {"number": number, "count": len(matches)},
                )
            )

    selection = {"requested": flow_selector, "status": "all", "match_count": len(flows)}
    selected_flows = flows
    if flow_selector is not None:
        selected_flows = [flow for flow in flows if flow["number"] == flow_selector]
        selection["match_count"] = len(selected_flows)
        if len(selected_flows) == 1:
            selection["status"] = "selected"
        elif not selected_flows:
            selection["status"] = "not_found"
            diagnostics.append(
                diagnostic("error", "FLOW_NOT_FOUND", "records", "requested service flow was not found")
            )
        else:
            selection["status"] = "ambiguous"
            diagnostics.append(
                diagnostic(
                    "error",
                    "FLOW_SELECTION_AMBIGUOUS",
                    "records",
                    "requested service flow is not unique; no candidate was auto-selected",
                    {"match_count": len(selected_flows)},
                )
            )
            selected_flows = []
    elif not flows:
        diagnostics.append(diagnostic("error", "NO_SERVICE_FLOW", "records", "no isc_service_flow record was found"))

    selected_numbers = {flow["number"] for flow in selected_flows}
    selected_scripts = [item for item in scripts if item["flow_number"] in selected_numbers]
    error_count = sum(item["severity"] == "error" for item in diagnostics)
    warning_count = sum(item["severity"] == "warning" for item in diagnostics)
    report = {
        "schema_version": 1,
        "status": "error" if error_count else ("pass_with_findings" if warning_count else "pass"),
        "validation_level": "static_structure_only",
        "platform_execution": False,
        "input_modified": False,
        "inputs": inputs,
        "selection": selection,
        "record_count": len(records),
        "entity_counts": dict(sorted(entity_counts.items())),
        "records": record_summaries,
        "flows": selected_flows,
        "scripts": [public_script(item) for item in selected_scripts],
        "diagnostics": diagnostics,
        "diagnostic_counts": {"error": error_count, "warning": warning_count},
    }
    return report, selected_scripts


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# ISCB 服务流程静态解析报告",
        "",
        "> 证据级别：仅静态结构解析；未导入、未发布、未在苍穹平台运行。",
        "",
        f"- 状态：`{report['status']}`",
        f"- 顶层记录：{report['record_count']}",
        f"- 服务流程：{len(report['flows'])}",
        f"- 输入已修改：{str(report['input_modified']).lower()}",
        "",
        "## 实体分布",
        "",
        "| 实体 | 数量 |",
        "|---|---:|",
    ]
    lines.extend(
        f"| `{markdown_cell(name)}` | {count} |"
        for name, count in report["entity_counts"].items()
    )
    for flow in report["flows"]:
        lines.extend(
            [
                "",
                f"## {markdown_cell(flow['name'])} (`{markdown_cell(flow['number'])}`)",
                "",
            ]
        )
        if flow.get("summary"):
            summary = flow["summary"]
            lines.extend(
                [
                    f"- 范围数：{summary['scope_count']}",
                    f"- 节点数：{summary['node_count']}",
                    f"- 连线数：{summary['link_count']}",
                    f"- Script 数：{summary['script_count']}",
                ]
            )
        root = flow.get("root_scope")
        if root:
            for scope in flatten_scopes(root):
                lines.extend(
                    [
                        "",
                        f"### 范围 `{markdown_cell(scope['path'])}`",
                        "",
                        "| ID | 名称 | 类型 | Script |",
                        "|---|---|---|---|",
                    ]
                )
                for node in scope["nodes"]:
                    name = markdown_cell(node["name"])
                    lines.append(
                        f"| `{markdown_cell(node['id'])}` | {name} | `{markdown_cell(node['type'])}` | "
                        f"{'是' if node['has_script'] else '否'} |"
                    )
    lines.extend(["", "## 诊断", ""])
    if not report["diagnostics"]:
        lines.append("未发现结构诊断项。")
    else:
        lines.extend(["| 级别 | 代码 | 位置 | 说明 |", "|---|---|---|---|"])
        for item in report["diagnostics"]:
            message = markdown_cell(item["message"])
            lines.append(
                f"| {markdown_cell(item['severity'])} | `{markdown_cell(item['code'])}` | "
                f"`{markdown_cell(item['location'])}` | {message} |"
            )
    return "\n".join(lines) + "\n"


def mermaid_label(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def mermaid_report(report: dict[str, Any]) -> str:
    blocks: list[str] = []
    for flow in report["flows"]:
        root = flow.get("root_scope")
        if not root:
            continue
        for scope in flatten_scopes(root):
            blocks.extend(
                [
                    f"## {markdown_cell(flow['name'])} - {markdown_cell(scope['name'])}",
                    "",
                    "```mermaid",
                    "flowchart TD",
                ]
            )
            aliases = {node["id"]: f"n{index}" for index, node in enumerate(scope["nodes"])}
            for node in scope["nodes"]:
                label = mermaid_label(f"{node['id']} {node['name']} ({node['type']})")
                blocks.append(f'    {aliases[node["id"]]}["{label}"]')
            for link in scope["links"]:
                if link["source"] in aliases and link["target"] in aliases:
                    blocks.append(f"    {aliases[link['source']]} --> {aliases[link['target']]}")
            blocks.extend(["```", ""])
    return "\n".join(blocks).rstrip() + "\n"


def prepare_script_outputs(
    scripts: list[dict[str, Any]],
    output_dir: Path,
    overwrite: bool,
    protected_paths: Iterable[Path] = (),
) -> list[tuple[Path, str]]:
    if lexists(output_dir) and not output_dir.is_dir():
        raise InspectionError("script output path exists and is not a directory")
    targets: list[tuple[Path, str]] = []
    for index, item in enumerate(scripts, 1):
        flow = safe_component(item["flow_number"], "flow")
        node = safe_component(item["node_id"], "node")
        title = safe_component(item["node_name"], "script")
        target = output_dir / f"{index:03d}_{flow}_{node}_{title}.iscb"
        targets.append((target, item["_content"]))
    collisions = [target.name for target, _ in targets if lexists(target) and not overwrite]
    if collisions:
        raise InspectionError("script output exists; use --overwrite to replace: " + ", ".join(collisions))
    root = output_dir.resolve()
    protected = list(protected_paths)
    prepared_targets: list[tuple[Path, str]] = []
    for target, content in targets:
        lexical_target = root / target.name
        resolved_target = lexical_target.resolve()
        if lexical_target.parent.resolve() != root or resolved_target.parent != root:
            raise InspectionError("resolved script output escaped the requested directory")
        if any(
            resolved_target == protected_path.resolve()
            or same_existing_file(lexical_target, protected_path)
            for protected_path in protected
        ):
            raise InspectionError("script output conflicts with a protected input or report path")
        prepared_targets.append((lexical_target, content))
    return prepared_targets


def write_prepared_scripts(
    prepared: list[tuple[Path, str]],
    output_dir: Path,
    overwrite: bool,
) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    created: list[tuple[Path, tuple[int, int]]] = []
    try:
        for resolved, content in prepared:
            identity = atomic_write(resolved, content, overwrite=overwrite)
            created.append((resolved, identity))
            written.append(resolved.name)
        return written
    except InspectionError:
        if not overwrite:
            for path, identity in created:
                unlink_if_identity(path, identity)
        raise


def extract_scripts(
    scripts: list[dict[str, Any]],
    output_dir: Path,
    overwrite: bool,
    protected_paths: Iterable[Path] = (),
) -> list[str]:
    prepared = prepare_script_outputs(scripts, output_dir, overwrite, protected_paths)
    return write_prepared_scripts(prepared, output_dir, overwrite)


def preflight_output(
    path: Path,
    input_path: Path,
    overwrite: bool,
    protected_paths: Iterable[Path] = (),
) -> None:
    if path.resolve() == input_path.resolve() or same_existing_file(path, input_path):
        raise InspectionError("analysis output cannot overwrite or alias the input")
    for protected in protected_paths:
        if path.resolve() == protected.resolve() or same_existing_file(path, protected):
            raise InspectionError("analysis output conflicts with a script output")
    if lexists(path) and path.is_dir():
        raise InspectionError("analysis output path is a directory")
    if lexists(path) and not overwrite:
        raise InspectionError("analysis output exists; use --overwrite to replace it")


def write_output(path: Path, content: str, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, content, overwrite=overwrite)


def unlink_if_identity(path: Path, identity: tuple[int, int]) -> None:
    try:
        current = path.lstat()
        if (current.st_dev, current.st_ino) == identity:
            path.unlink()
    except OSError:
        return


def atomic_write(path: Path, content: str, overwrite: bool) -> tuple[int, int]:
    """Publish atomically; with no overwrite, never replace an existing directory entry."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        temp_stat = temp_path.lstat()
        identity = (temp_stat.st_dev, temp_stat.st_ino)
        if overwrite:
            os.replace(temp_path, path)
        else:
            try:
                os.link(temp_path, path)
            except FileExistsError:
                raise InspectionError(
                    "output appeared during publication; nothing was overwritten"
                ) from None
            temp_path.unlink()
        temp_path = None
        return identity
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="DTS file or ZIP package")
    parser.add_argument("--flow", help="require one exact service-flow number")
    parser.add_argument("--format", choices=("json", "markdown", "mermaid"), default="json")
    parser.add_argument("--output", type=Path, help="write the report instead of stdout")
    parser.add_argument(
        "--extract-scripts",
        type=Path,
        help="explicitly write raw Script-node content; files can contain secrets",
    )
    parser.add_argument("--overwrite", action="store_true", help="replace explicitly selected output files")
    parser.add_argument(
        "--max-input-bytes",
        type=positive_int,
        default=DEFAULT_MAX_INPUT_BYTES,
        help=f"maximum plain or total uncompressed DTS bytes (default: {DEFAULT_MAX_INPUT_BYTES})",
    )
    parser.add_argument(
        "--max-zip-members",
        type=positive_int,
        default=DEFAULT_MAX_ZIP_MEMBERS,
        help=f"maximum DTS members in a ZIP (default: {DEFAULT_MAX_ZIP_MEMBERS})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report, scripts = inspect_path(
            args.input,
            args.flow,
            max_input_bytes=args.max_input_bytes,
            max_zip_members=args.max_zip_members,
        )
        input_digest = file_sha256(args.input)
        report["input_container_sha256"] = input_digest
        if args.format == "mermaid" and args.flow and report["selection"]["status"] != "selected":
            raise InspectionError("Mermaid output requires one unambiguous --flow match")
        prepared_scripts: list[tuple[Path, str]] = []
        if args.extract_scripts:
            protected = [args.input]
            if args.output:
                protected.append(args.output)
            prepared_scripts = prepare_script_outputs(
                scripts,
                args.extract_scripts,
                args.overwrite,
                protected_paths=protected,
            )
            report["extracted_script_files"] = [path.name for path, _ in prepared_scripts]
        if args.output:
            preflight_output(
                args.output,
                args.input,
                args.overwrite,
                protected_paths=[path for path, _ in prepared_scripts],
            )
        if prepared_scripts:
            write_prepared_scripts(prepared_scripts, args.extract_scripts, args.overwrite)
            if file_sha256(args.input) != input_digest:
                raise InspectionError("input hash changed during script extraction")
        if args.format == "json":
            content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        elif args.format == "markdown":
            content = markdown_report(report)
        else:
            content = mermaid_report(report)
        if args.output:
            write_output(args.output, content, args.overwrite)
            if file_sha256(args.input) != input_digest:
                raise InspectionError("input hash changed during report output")
        else:
            sys.stdout.write(content)
        return 1 if report["diagnostic_counts"]["error"] else 0
    except (OSError, UnicodeError, zipfile.BadZipFile, InspectionError, RecursionError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
