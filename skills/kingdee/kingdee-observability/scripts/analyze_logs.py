#!/usr/bin/env python3
"""Parse and classify redacted Kingdee runtime evidence deterministically."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from redact import redact_text, redact_value, sanitize_sql


ALIASES = {
    "timestamp": ("timestamp", "time", "@timestamp", "logTime", "occurTime"),
    "trace_id": ("traceId", "trace_id", "traceID", "trace"),
    "span_id": ("spanId", "span_id", "spanID"),
    "parent_span_id": ("parentSpanId", "parent_span_id", "parentId"),
    "service": ("service", "serviceName", "app", "application", "mservice"),
    "logger": ("logger", "loggerName", "class", "source"),
    "thread": ("thread", "threadName", "thread_name"),
    "level": ("level", "logLevel", "severity"),
    "duration": ("durationMs", "elapsedMs", "costMs", "duration", "elapsed", "cost"),
    "message": ("message", "msg", "content", "log", "text"),
    "exception": ("exception", "throwable", "stackTrace", "error"),
    "sql": ("sql", "statement", "query", "ksql"),
    "params": ("params", "parameters", "bindings", "binds", "args"),
    "operation": ("operation", "operationName", "spanName", "name"),
}
EXCEPTION_MARKER = re.compile(
    r"(?i)\b(exception|error|throwable|caused by|stacktrace|outofmemoryerror|deadlock)\b"
)
SQL_MARKER = re.compile(r"(?is)\b(select|insert|update|delete|merge)\b.+")
DURATION_MARKER = re.compile(r"(?i)\b(?:duration|elapsed|cost|took)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(ms|s)\b")
SLOW_SQL_MARKER = re.compile(r"(?i)\b(slow\s*sql|sql\s*slow|slowquery)\b")
THREAD_MARKER = re.compile(
    r"(?i)\b(deadlock|blocked|thread[- ]?pool|rejectedexecution|queue\s+full|pool\s+exhausted|thread\s+dump)\b"
)
GC_MARKER = re.compile(
    r"(?i)\b(full\s+gc|gc\s+pause|allocation\s+failure|gc\s+overhead|metaspace|heap\s+pressure)\b"
)


def pick(event: dict[str, Any], alias: str, default: Any = None) -> Any:
    for name in ALIASES[alias]:
        if name in event and event[name] is not None:
            return event[name]
    return default


def parse_duration(value: Any, message: str) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"(\d+(?:\.\d+)?)\s*(ms|s)?", value, re.IGNORECASE)
        if match:
            amount = float(match.group(1))
            return amount * 1000 if (match.group(2) or "").lower() == "s" else amount
    match = DURATION_MARKER.search(message)
    if match:
        amount = float(match.group(1))
        return amount * 1000 if match.group(2).lower() == "s" else amount
    return None


def load_events(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    text = path.read_text(encoding="utf-8-sig")
    warnings: list[str] = []
    suffix = path.suffix.lower()
    events: list[Any]
    if suffix == ".json":
        root = json.loads(text)
        if isinstance(root, list):
            events = root
        elif isinstance(root, dict):
            collection = next(
                (root[key] for key in ("events", "logs", "records", "items") if isinstance(root.get(key), list)),
                None,
            )
            events = collection if collection is not None else [root]
        else:
            raise ValueError("JSON root must be an object or array")
    elif suffix in {".jsonl", ".ndjson"}:
        events = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                warnings.append(f"line {line_number}: invalid JSON skipped")
    else:
        events = [{"message": line} for line in text.splitlines() if line.strip()]

    normalized: list[dict[str, Any]] = []
    for index, event in enumerate(events, start=1):
        if isinstance(event, dict):
            normalized.append(event)
        else:
            warnings.append(f"event {index}: non-object value converted to text")
            normalized.append({"message": str(event)})
    return normalized, warnings


def normalize_event(event: dict[str, Any], sequence: int) -> dict[str, Any]:
    raw_message = str(pick(event, "message", ""))
    exception_value = pick(event, "exception")
    if exception_value and not raw_message:
        raw_message = str(exception_value)
    raw_sql = pick(event, "sql")
    if raw_sql is None:
        match = SQL_MARKER.search(raw_message)
        raw_sql = match.group(0) if match else None
    duration_ms = parse_duration(pick(event, "duration"), raw_message)
    message = redact_text(raw_message)
    level = str(pick(event, "level", "")).upper()
    return {
        "sequence": sequence,
        "timestamp": redact_text(str(pick(event, "timestamp", ""))),
        "traceId": redact_text(str(pick(event, "trace_id", ""))),
        "spanId": redact_text(str(pick(event, "span_id", ""))),
        "parentSpanId": redact_text(str(pick(event, "parent_span_id", ""))),
        "service": redact_text(str(pick(event, "service", ""))),
        "operation": redact_text(str(pick(event, "operation", ""))),
        "logger": redact_text(str(pick(event, "logger", ""))),
        "thread": redact_text(str(pick(event, "thread", ""))),
        "level": level,
        "durationMs": duration_ms,
        "message": message,
        "exception": redact_value(exception_value),
        "sqlSignature": sanitize_sql(str(raw_sql)) if raw_sql else "",
        "hasSqlParams": pick(event, "params") is not None or "params" in raw_message.lower(),
    }


def evidence_item(event: dict[str, Any], include_sql: bool = False) -> dict[str, Any]:
    item = {
        "sequence": event["sequence"],
        "timestamp": event["timestamp"],
        "traceId": event["traceId"],
        "spanId": event["spanId"],
        "service": event["service"],
        "logger": event["logger"],
        "thread": event["thread"],
        "level": event["level"],
        "durationMs": event["durationMs"],
        "message": event["message"],
    }
    if include_sql:
        item["sqlSignature"] = event["sqlSignature"]
        item["parametersRedacted"] = event["hasSqlParams"]
    return item


def would_cycle(node_id: str, parent_id: str, parent_by_id: dict[str, str]) -> bool:
    seen = {node_id}
    current = parent_id
    while current:
        if current in seen:
            return True
        seen.add(current)
        current = parent_by_id.get(current, "")
    return False


def build_trace_trees(events: list[dict[str, Any]], warnings: list[str]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event["traceId"]:
            grouped[event["traceId"]].append(event)
    traces: list[dict[str, Any]] = []
    for trace_id in sorted(grouped):
        trace_events = sorted(grouped[trace_id], key=lambda item: item["sequence"])
        nodes: dict[str, dict[str, Any]] = {}
        original_to_first: dict[str, str] = {}
        for event in trace_events:
            base_id = event["spanId"] or f"event-{event['sequence']}"
            node_id = base_id
            suffix = 2
            while node_id in nodes:
                node_id = f"{base_id}#{suffix}"
                suffix += 1
            original_to_first.setdefault(base_id, node_id)
            nodes[node_id] = {
                "nodeId": node_id,
                "spanId": event["spanId"],
                "parentSpanId": event["parentSpanId"],
                "timestamp": event["timestamp"],
                "service": event["service"],
                "operation": event["operation"] or event["logger"],
                "durationMs": event["durationMs"],
                "sequence": event["sequence"],
                "children": [],
            }
        parent_by_id: dict[str, str] = {}
        roots: list[str] = []
        for node_id, node in nodes.items():
            parent_span = node["parentSpanId"]
            parent_id = original_to_first.get(parent_span, "") if parent_span else ""
            if parent_id and parent_id != node_id and not would_cycle(node_id, parent_id, parent_by_id):
                parent_by_id[node_id] = parent_id
            else:
                if parent_span and not parent_id:
                    node["missingParent"] = True
                if parent_id == node_id or (parent_id and would_cycle(node_id, parent_id, parent_by_id)):
                    node["cycleBroken"] = True
                    warnings.append(f"trace {trace_id}: cycle broken at span {node['spanId'] or node_id}")
                roots.append(node_id)
        for child_id, parent_id in parent_by_id.items():
            nodes[parent_id]["children"].append(nodes[child_id])
        for node in nodes.values():
            node["children"].sort(key=lambda item: item["sequence"])
        root_nodes = [nodes[node_id] for node_id in roots]
        root_nodes.sort(key=lambda item: item["sequence"])
        traces.append({"traceId": trace_id, "eventCount": len(trace_events), "roots": root_nodes})
    return traces


def analyze(
    events: list[dict[str, Any]],
    *,
    slow_sql_ms: float,
    n_plus_one_threshold: int,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    warnings = list(warnings or [])
    normalized = [normalize_event(event, index) for index, event in enumerate(events, start=1)]
    exceptions: list[dict[str, Any]] = []
    slow_sql: list[dict[str, Any]] = []
    thread_evidence: list[dict[str, Any]] = []
    gc_evidence: list[dict[str, Any]] = []
    sql_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for event in normalized:
        searchable = " ".join((event["message"], str(event["exception"] or "")))
        if event["level"] in {"ERROR", "FATAL", "SEVERE"} or event["exception"] or EXCEPTION_MARKER.search(searchable):
            exceptions.append(evidence_item(event))
        if event["sqlSignature"]:
            if event["traceId"]:
                sql_groups[(event["traceId"], event["sqlSignature"])].append(event)
            if (event["durationMs"] is not None and event["durationMs"] >= slow_sql_ms) or SLOW_SQL_MARKER.search(event["message"]):
                slow_sql.append(evidence_item(event, include_sql=True))
        if THREAD_MARKER.search(searchable):
            thread_evidence.append(evidence_item(event))
        if GC_MARKER.search(searchable):
            gc_evidence.append(evidence_item(event))

    n_plus_one = []
    for (trace_id, signature), members in sorted(sql_groups.items()):
        if len(members) >= n_plus_one_threshold:
            n_plus_one.append(
                {
                    "traceId": trace_id,
                    "sqlSignature": signature,
                    "count": len(members),
                    "firstSequence": members[0]["sequence"],
                    "lastSequence": members[-1]["sequence"],
                    "confidence": "hypothesis",
                }
            )

    traces = build_trace_trees(normalized, warnings)
    result = {
        "summary": {
            "eventCount": len(normalized),
            "traceCount": len(traces),
            "exceptionCount": len(exceptions),
            "slowSqlCount": len(slow_sql),
            "possibleNPlusOneCount": len(n_plus_one),
            "threadEvidenceCount": len(thread_evidence),
            "gcEvidenceCount": len(gc_evidence),
        },
        "thresholds": {"slowSqlMs": slow_sql_ms, "nPlusOneRepeats": n_plus_one_threshold},
        "exceptions": exceptions[:100],
        "slowSql": slow_sql[:100],
        "possibleNPlusOne": n_plus_one[:100],
        "threadEvidence": thread_evidence[:100],
        "gcEvidence": gc_evidence[:100],
        "traceTrees": traces[:100],
        "warnings": warnings,
        "redactionApplied": True,
    }
    return redact_value(result)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze redacted Kingdee runtime log evidence.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--source-mode", choices=("offline", "dev-query", "prod-readonly"), default="offline")
    parser.add_argument("--approval-ref")
    parser.add_argument("--slow-sql-ms", type=float, default=1000.0)
    parser.add_argument("--n-plus-one-threshold", type=int, default=3)
    args = parser.parse_args()

    if args.source_mode == "prod-readonly" and not args.approval_ref:
        print("prod-readonly source mode requires --approval-ref", file=sys.stderr)
        return 2
    if args.slow_sql_ms < 0 or args.n_plus_one_threshold < 2:
        print("thresholds must be non-negative and N+1 repeats must be at least 2", file=sys.stderr)
        return 2

    path = Path(args.input).expanduser().resolve()
    try:
        events, warnings = load_events(path)
        result = analyze(
            events,
            slow_sql_ms=args.slow_sql_ms,
            n_plus_one_threshold=args.n_plus_one_threshold,
            warnings=warnings,
        )
        result["source"] = {
            "mode": args.source_mode,
            "name": redact_text(path.name),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "approvalRef": args.approval_ref,
        }
        result = redact_value(result)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"cannot analyze input: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output).expanduser().resolve()
        if output == path:
            print("output must not overwrite input", file=sys.stderr)
            return 2
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
