#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import operator
import os
import re
import secrets
import ssl
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener


SCHEMA_VERSION = 1
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
HEADER_NAME_RE = re.compile(r"^[!#$%&'*+\-.^_|~0-9A-Za-z]+$")
ACTION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
APPROVAL_RE = re.compile(r"^[^\r\n]{1,128}$")
SECRET_HEADERS = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
    "ukey",
    "x-api-key",
    "x-auth-token",
    "x-csrf-token",
    "x-xsrftoken",
}
FORBIDDEN_TRANSPORT_HEADERS = {
    "connection",
    "content-length",
    "host",
    "proxy-connection",
    "transfer-encoding",
}
SECRET_KEY_PARTS = {
    "accesstoken",
    "apikey",
    "authorization",
    "clientsecret",
    "cookie",
    "credential",
    "password",
    "refreshtoken",
    "secret",
    "sessionid",
    "sessionkey",
    "token",
    "ukey",
    "xsrftoken",
}
ALLOWED_EVIDENCE = {
    "official-primary",
    "local-observed",
    "current-session-capture",
}
ALLOWED_ENVIRONMENTS = {"dev", "test", "prod", "unknown"}
ALLOWED_PHASES = {"inspect", "apply", "verify", "rollback"}
READ_METHODS = {"GET", "HEAD"}
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
RELATION_OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}


class KcsOpsError(RuntimeError):
    pass


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fail(message: str) -> None:
    raise KcsOpsError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"JSON file not found: {path}")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"cannot read UTF-8 JSON {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"JSON root must be an object: {path}")
    return value


def atomic_write_json(path: Path, value: Any) -> None:
    temp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with temp.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except OSError as exc:
        fail(f"cannot atomically write UTF-8 JSON {path}: {type(exc).__name__}")
    finally:
        try:
            temp.unlink()
        except OSError:
            pass


def task_local_path(raw_path: str, task_root: str) -> Path:
    try:
        root = Path(task_root).expanduser().resolve()
        target = Path(raw_path).expanduser()
        if not target.is_absolute():
            target = root / target
        target = target.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        fail(f"cannot resolve task-local path: {type(exc).__name__}")
    try:
        target.relative_to(root)
    except ValueError:
        fail(f"path must stay under task root: {target}")
    return target


def canonical_plan_bytes(plan: dict[str, Any]) -> bytes:
    value = copy.deepcopy(plan)
    value.pop("plan_sha256", None)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def plan_digest(plan: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_plan_bytes(plan)).hexdigest()


def require_keys(value: dict[str, Any], required: set[str], label: str) -> None:
    missing = sorted(required - value.keys())
    if missing:
        fail(f"{label} missing required fields: {', '.join(missing)}")


def reject_unknown_keys(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(value.keys() - allowed)
    if unknown:
        fail(f"{label} contains unknown fields: {', '.join(unknown)}")


def validate_base_url(raw: Any) -> None:
    if not isinstance(raw, str) or not raw.strip() or raw != raw.strip():
        fail("target.base_url must be a non-empty trimmed string")
    try:
        parsed = urlsplit(raw)
        parsed.port
    except ValueError:
        fail("target.base_url is not a valid origin URL")
    if parsed.scheme not in {"http", "https"}:
        fail("target.base_url scheme must be https, or http for loopback tests")
    if not parsed.hostname or parsed.username or parsed.password:
        fail("target.base_url must be an origin without embedded credentials")
    if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        fail("target.base_url must not contain a path, query, or fragment")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
        fail("plain HTTP is allowed only for loopback mock servers")


def validate_scalar(value: Any, label: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    fail(f"{label} must be a scalar or null")


def validate_query(query: Any, label: str) -> None:
    if query is None:
        return
    if not isinstance(query, dict):
        fail(f"{label} must be an object")
    for key, value in query.items():
        if not isinstance(key, str) or not key:
            fail(f"{label} keys must be non-empty strings")
        if isinstance(value, list):
            for index, item in enumerate(value):
                validate_scalar(item, f"{label}.{key}[{index}]")
        else:
            validate_scalar(value, f"{label}.{key}")


def validate_api_path(raw: Any, label: str) -> None:
    if not isinstance(raw, str) or not raw.startswith("/kcs/"):
        fail(f"{label} must begin with /kcs/")
    if any(character in raw for character in ("\r", "\n", "\\")):
        fail(f"{label} contains forbidden characters")
    parsed = urlsplit(raw)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        fail(f"{label} must contain only a relative API path")
    if ".." in Path(parsed.path).parts:
        fail(f"{label} must not contain parent traversal")


def validate_headers(action: dict[str, Any], label: str) -> None:
    headers = action.get("headers", {})
    if not isinstance(headers, dict):
        fail(f"{label}.headers must be an object")
    for name, value in headers.items():
        if not isinstance(name, str) or not HEADER_NAME_RE.fullmatch(name):
            fail(f"{label}.headers contains an invalid name")
        if name.lower() in FORBIDDEN_TRANSPORT_HEADERS:
            fail(f"{label}.headers must not override transport header {name}")
        if name.lower() in SECRET_HEADERS:
            fail(f"{label}.headers must not persist secret header {name}")
        if not isinstance(value, str) or "\r" in value or "\n" in value:
            fail(f"{label}.headers.{name} must be a single-line string")
        if sanitize_string(value) == "<redacted>":
            fail(f"{label}.headers.{name} appears to contain a persisted credential")

    env_headers = action.get("headers_from_env", {})
    if not isinstance(env_headers, dict):
        fail(f"{label}.headers_from_env must be an object")
    for name, env_name in env_headers.items():
        if not isinstance(name, str) or not HEADER_NAME_RE.fullmatch(name):
            fail(f"{label}.headers_from_env contains an invalid header name")
        if name.lower() in FORBIDDEN_TRANSPORT_HEADERS:
            fail(f"{label}.headers_from_env must not override transport header {name}")
        if not isinstance(env_name, str) or not ENV_NAME_RE.fullmatch(env_name):
            fail(f"{label}.headers_from_env.{name} must name an environment variable")


def reject_persisted_secrets(value: Any, label: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if secret_key(str(key)):
                fail(f"{label} must not persist credential-like field {key}")
            reject_persisted_secrets(item, f"{label}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            reject_persisted_secrets(item, f"{label}[{index}]")
    elif isinstance(value, str) and sanitize_string(value) == "<redacted>":
        fail(f"{label} appears to contain a persisted credential")


def validate_expect(expect: Any, label: str) -> None:
    if not isinstance(expect, dict):
        fail(f"{label}.expect must be an object")
    reject_unknown_keys(
        expect,
        {"http_status", "json_equals", "json_relations"},
        f"{label}.expect",
    )
    statuses = expect.get("http_status")
    if (
        not isinstance(statuses, list)
        or not statuses
        or any(not isinstance(item, int) or not 100 <= item <= 599 for item in statuses)
    ):
        fail(f"{label}.expect.http_status must be a non-empty HTTP status list")
    json_equals = expect.get("json_equals", {})
    if not isinstance(json_equals, dict):
        fail(f"{label}.expect.json_equals must be an object")
    for path in json_equals:
        if not isinstance(path, str) or not path:
            fail(f"{label}.expect.json_equals paths must be non-empty strings")
    relations = expect.get("json_relations", [])
    if not isinstance(relations, list):
        fail(f"{label}.expect.json_relations must be an array")
    for index, relation in enumerate(relations):
        relation_label = f"{label}.expect.json_relations[{index}]"
        if not isinstance(relation, dict):
            fail(f"{relation_label} must be an object")
        require_keys(relation, {"left", "op"}, relation_label)
        reject_unknown_keys(relation, {"left", "op", "right", "right_path"}, relation_label)
        if relation.get("op") not in RELATION_OPERATORS:
            fail(f"{relation_label}.op is invalid")
        if not isinstance(relation.get("left"), str) or not relation["left"]:
            fail(f"{relation_label}.left must be a JSON dot path")
        has_right = "right" in relation
        has_right_path = "right_path" in relation
        if has_right == has_right_path:
            fail(f"{relation_label} must contain exactly one of right or right_path")
        if has_right_path and (
            not isinstance(relation["right_path"], str) or not relation["right_path"]
        ):
            fail(f"{relation_label}.right_path must be a JSON dot path")


def validate_action(action: Any, index: int) -> None:
    label = f"actions[{index}]"
    if not isinstance(action, dict):
        fail(f"{label} must be an object")
    allowed = {
        "id",
        "phase",
        "risk",
        "description",
        "method",
        "path",
        "query",
        "headers",
        "headers_from_env",
        "encoding",
        "body",
        "expect",
        "response_policy",
        "verify_actions",
        "rollback_action",
        "irreversible_reason",
    }
    reject_unknown_keys(action, allowed, label)
    require_keys(action, {"id", "phase", "risk", "method", "path", "expect"}, label)

    action_id = action["id"]
    if not isinstance(action_id, str) or not ACTION_ID_RE.fullmatch(action_id):
        fail(f"{label}.id is invalid")
    phase = action["phase"]
    if phase not in ALLOWED_PHASES:
        fail(f"{label}.phase is invalid")
    method = action["method"]
    if not isinstance(method, str):
        fail(f"{label}.method must be a string")
    method = method.upper()
    action["method"] = method

    risk = action["risk"]
    if phase in {"inspect", "verify"}:
        if method not in READ_METHODS or risk != "read-only":
            fail(f"{label} read-only phase requires GET/HEAD and risk=read-only")
    else:
        if method not in WRITE_METHODS or risk not in {"write", "destructive"}:
            fail(f"{label} write phase requires a write method and write/destructive risk")

    validate_api_path(action["path"], f"{label}.path")
    validate_query(action.get("query"), f"{label}.query")
    reject_persisted_secrets(action.get("query", {}), f"{label}.query")
    validate_headers(action, label)
    validate_expect(action["expect"], label)

    description = action.get("description")
    if description is not None and (
        not isinstance(description, str)
        or not description.strip()
        or len(description) > 500
        or "\r" in description
        or "\n" in description
    ):
        fail(f"{label}.description must be a non-empty single-line string up to 500 characters")

    encoding = action.get("encoding", "none")
    if encoding not in {"none", "json", "form"}:
        fail(f"{label}.encoding must be none, json, or form")
    if phase in {"inspect", "verify"} and ("body" in action or encoding != "none"):
        fail(f"{label} read-only actions cannot have a body")
    if encoding == "form" and not isinstance(action.get("body"), dict):
        fail(f"{label}.body must be an object for form encoding")
    if encoding == "form":
        validate_query(action.get("body"), f"{label}.body")
    if encoding == "none" and action.get("body") is not None:
        fail(f"{label}.body requires json or form encoding")
    reject_persisted_secrets(action.get("body"), f"{label}.body")

    response_policy = action.get(
        "response_policy",
        "summary",
    )
    if response_policy not in {"sanitized-json", "summary"}:
        fail(f"{label}.response_policy is invalid")
    action["response_policy"] = response_policy

    values = action.get("verify_actions", [])
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        fail(f"{label}.verify_actions must be an array of action IDs")
    rollback_action = action.get("rollback_action")
    if rollback_action is not None and not isinstance(rollback_action, str):
        fail(f"{label}.rollback_action must be an action ID or null")
    irreversible_reason = action.get("irreversible_reason")
    if irreversible_reason is not None and (
        not isinstance(irreversible_reason, str)
        or not irreversible_reason.strip()
        or len(irreversible_reason) > 500
        or "\r" in irreversible_reason
        or "\n" in irreversible_reason
    ):
        fail(f"{label}.irreversible_reason must be a single-line string up to 500 characters")
    if phase == "apply" and not rollback_action and not irreversible_reason:
        fail(f"{label} apply action requires rollback_action or irreversible_reason")
    if phase in {"apply", "rollback"} and not values:
        fail(f"{label} write action requires at least one verify action")


def validate_plan(plan: dict[str, Any], finalized: bool = False) -> None:
    allowed = {
        "schema_version",
        "target",
        "contract_evidence",
        "actions",
        "plan_sha256",
    }
    reject_unknown_keys(plan, allowed, "plan")
    require_keys(plan, {"schema_version", "target", "contract_evidence", "actions"}, "plan")
    if plan["schema_version"] != SCHEMA_VERSION:
        fail(f"schema_version must be {SCHEMA_VERSION}")

    target = plan["target"]
    if not isinstance(target, dict):
        fail("target must be an object")
    reject_unknown_keys(target, {"label", "base_url", "environment"}, "target")
    require_keys(target, {"label", "base_url", "environment"}, "target")
    if (
        not isinstance(target["label"], str)
        or not target["label"].strip()
        or len(target["label"]) > 128
        or "\r" in target["label"]
        or "\n" in target["label"]
    ):
        fail("target.label must be a non-empty single-line string up to 128 characters")
    if target["environment"] not in ALLOWED_ENVIRONMENTS:
        fail("target.environment is invalid")
    validate_base_url(target["base_url"])

    evidence = plan["contract_evidence"]
    if not isinstance(evidence, dict):
        fail("contract_evidence must be an object")
    reject_unknown_keys(evidence, {"kind", "reference", "verified_at"}, "contract_evidence")
    require_keys(evidence, {"kind", "reference"}, "contract_evidence")
    if evidence["kind"] not in ALLOWED_EVIDENCE:
        fail("contract_evidence.kind is not authoritative or locally verified")
    if (
        not isinstance(evidence["reference"], str)
        or not evidence["reference"].strip()
        or len(evidence["reference"]) > 500
        or "\r" in evidence["reference"]
        or "\n" in evidence["reference"]
    ):
        fail("contract_evidence.reference must be a non-secret single-line identifier")
    if "verified_at" in evidence and not isinstance(evidence["verified_at"], str):
        fail("contract_evidence.verified_at must be a string")

    actions = plan["actions"]
    if not isinstance(actions, list) or not actions:
        fail("actions must be a non-empty array")
    for index, action in enumerate(actions):
        validate_action(action, index)
    ids = [action["id"] for action in actions]
    if len(ids) != len(set(ids)):
        fail("action IDs must be unique")
    by_id = {action["id"]: action for action in actions}
    for action in actions:
        for verify_id in action.get("verify_actions", []):
            if verify_id not in by_id or by_id[verify_id]["phase"] != "verify":
                fail(f"action {action['id']} references invalid verify action {verify_id}")
        rollback_id = action.get("rollback_action")
        if rollback_id and (
            rollback_id not in by_id or by_id[rollback_id]["phase"] != "rollback"
        ):
            fail(f"action {action['id']} references invalid rollback action {rollback_id}")

    if finalized:
        stored = plan.get("plan_sha256")
        if not isinstance(stored, str) or not re.fullmatch(r"[0-9a-f]{64}", stored):
            fail("finalized plan has no valid plan_sha256")
        actual = plan_digest(plan)
        if stored != actual:
            fail("plan_sha256 mismatch; regenerate and reapprove the plan")


def json_path_get(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, list):
            try:
                index = int(part)
            except ValueError:
                fail(f"JSON path {path} expects an array index at {part}")
            if index < 0 or index >= len(current):
                fail(f"JSON path not found: {path}")
            current = current[index]
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            fail(f"JSON path not found: {path}")
    return current


def check_expect(action: dict[str, Any], status: int, parsed: Any) -> None:
    expect = action["expect"]
    if status not in expect["http_status"]:
        fail(f"action {action['id']} returned unexpected HTTP status {status}")
    needs_json = bool(expect.get("json_equals") or expect.get("json_relations"))
    if needs_json and parsed is None:
        fail(f"action {action['id']} expected JSON but response was not JSON")
    for path, expected in expect.get("json_equals", {}).items():
        if json_path_get(parsed, path) != expected:
            fail(f"action {action['id']} failed JSON equality check at {path}")
    for relation in expect.get("json_relations", []):
        left = json_path_get(parsed, relation["left"])
        right = (
            json_path_get(parsed, relation["right_path"])
            if "right_path" in relation
            else relation["right"]
        )
        try:
            passed = RELATION_OPERATORS[relation["op"]](left, right)
        except TypeError:
            passed = False
        if not passed:
            fail(
                f"action {action['id']} failed JSON relation "
                f"{relation['left']} {relation['op']}"
            )


def secret_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return any(part in normalized for part in SECRET_KEY_PARTS)


def sanitize_string(value: str) -> str:
    if re.search(r"(?i)\b(?:bearer|basic)\s+\S+", value):
        return "<redacted>"
    if re.search(r"(?i)(?:password|token|cookie|ukey)=", value):
        return "<redacted>"
    if len(value) > 4096:
        return value[:4096] + "<truncated>"
    return value


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "<redacted>" if secret_key(str(key)) else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        return sanitize_string(value)
    return value


def encode_body(action: dict[str, Any], headers: dict[str, str]) -> bytes | None:
    encoding = action.get("encoding", "none")
    body = action.get("body")
    if encoding == "none":
        return None
    for name in list(headers):
        if name.lower() == "content-type":
            del headers[name]
    if encoding == "json":
        headers["Content-Type"] = "application/json; charset=UTF-8"
        return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    return urlencode(body, doseq=True).encode("utf-8")


def load_runtime_headers(action: dict[str, Any]) -> dict[str, str]:
    headers = dict(action.get("headers", {}))
    for header_name, env_name in action.get("headers_from_env", {}).items():
        value = os.environ.get(env_name)
        if value is None:
            fail(f"missing task-scoped credential environment variable: {env_name}")
        if "\r" in value or "\n" in value or len(value) > 16384:
            fail(f"invalid task-scoped credential environment variable: {env_name}")
        headers[header_name] = value
    return headers


def parse_response(body: bytes, content_type: str) -> Any | None:
    stripped = body.lstrip()
    if "json" not in content_type.lower() and not stripped.startswith((b"{", b"[")):
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None


def response_view(body: bytes, parsed: Any, policy: str) -> dict[str, Any]:
    digest = hashlib.sha256(body).hexdigest()
    if policy == "sanitized-json" and parsed is not None:
        return {
            "type": "sanitized-json",
            "bytes": len(body),
            "sha256": digest,
            "body": sanitize(parsed),
        }
    return {"type": "summary", "bytes": len(body), "sha256": digest}


def execute_action(
    plan: dict[str, Any],
    action: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    base_url = plan["target"]["base_url"].rstrip("/")
    query = urlencode(action.get("query", {}), doseq=True)
    url = f"{base_url}{action['path']}"
    if query:
        url = f"{url}?{query}"
    headers = load_runtime_headers(action)
    data = encode_body(action, headers)
    request = Request(url, data=data, headers=headers, method=action["method"])
    opener = build_opener(
        NoRedirectHandler(),
        HTTPSHandler(context=ssl.create_default_context()),
    )

    try:
        with opener.open(request, timeout=timeout) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        status = exc.code
        content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
        body = exc.read(MAX_RESPONSE_BYTES + 1)
    except (URLError, OSError, TimeoutError, ValueError, UnicodeError) as exc:
        fail(f"action {action['id']} transport failed: {type(exc).__name__}")

    if len(body) > MAX_RESPONSE_BYTES:
        fail(f"action {action['id']} response exceeded {MAX_RESPONSE_BYTES} bytes")
    if 300 <= status <= 399:
        fail(f"action {action['id']} redirect refused with HTTP status {status}")

    parsed = parse_response(body, content_type)
    check_expect(action, status, parsed)
    return {
        "action_id": action["id"],
        "phase": action["phase"],
        "risk": action["risk"],
        "method": action["method"],
        "path": action["path"],
        "http_status": status,
        "response": response_view(body, parsed, action["response_policy"]),
    }


def select_actions(
    plan: dict[str, Any],
    phase: str,
    selected_ids: list[str] | None,
) -> list[dict[str, Any]]:
    candidates = [action for action in plan["actions"] if action["phase"] == phase]
    if selected_ids:
        wanted = set(selected_ids)
        found = {action["id"] for action in candidates}
        unknown = sorted(wanted - found)
        if unknown:
            fail(f"selected actions are not in phase {phase}: {', '.join(unknown)}")
        candidates = [action for action in candidates if action["id"] in wanted]
    if not candidates:
        fail(f"plan contains no selected {phase} actions")
    return candidates


def load_final_plan(path: str, task_root: str) -> dict[str, Any]:
    plan = read_json(task_local_path(path, task_root))
    validate_plan(plan, finalized=True)
    return plan


def result_path(args: argparse.Namespace) -> Path | None:
    if not args.result:
        return None
    return task_local_path(args.result, args.task_root)


def print_json(value: Any, stream=None) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2), file=stream or sys.stdout)


def command_plan(args: argparse.Namespace) -> dict[str, Any]:
    draft = read_json(task_local_path(args.draft, args.task_root))
    draft.pop("plan_sha256", None)
    validate_plan(draft, finalized=False)
    draft["plan_sha256"] = plan_digest(draft)
    output = task_local_path(args.output, args.task_root)
    atomic_write_json(output, draft)
    return {
        "mode": "plan",
        "target_label": draft["target"]["label"],
        "environment": draft["target"]["environment"],
        "plan_sha256": draft["plan_sha256"],
        "actions": [
            {
                "id": action["id"],
                "phase": action["phase"],
                "risk": action["risk"],
                "method": action["method"],
                "path": action["path"],
                "rollback_action": action.get("rollback_action"),
                "irreversible_reason": action.get("irreversible_reason"),
            }
            for action in draft["actions"]
        ],
    }


def command_execute(args: argparse.Namespace, phase: str) -> dict[str, Any]:
    plan = load_final_plan(args.plan, args.task_root)
    stored_digest = plan["plan_sha256"]
    approval_ref = None
    if phase in {"apply", "rollback"}:
        if args.expected_sha256 != stored_digest:
            fail("expected SHA-256 does not match the finalized plan")
        if not APPROVAL_RE.fullmatch(args.approval_id):
            fail("approval-id must be a non-empty single-line task reference")
        approval_ref = hashlib.sha256(args.approval_id.encode("utf-8")).hexdigest()[:12]

    actions = select_actions(plan, phase, args.action)
    completed = []
    try:
        for action in actions:
            completed.append(execute_action(plan, action, args.timeout))
    except KcsOpsError as exc:
        report = {
            "mode": "apply-approved" if phase == "apply" else phase,
            "target_label": plan["target"]["label"],
            "plan_sha256": stored_digest,
            "approval_ref": approval_ref,
            "completed": completed,
            "status": "failed",
            "error": str(exc),
        }
        output = result_path(args)
        if output:
            atomic_write_json(output, report)
        print_json(report, stream=sys.stderr)
        setattr(exc, "already_reported", True)
        raise

    report = {
        "mode": "apply-approved" if phase == "apply" else phase,
        "target_label": plan["target"]["label"],
        "plan_sha256": stored_digest,
        "approval_ref": approval_ref,
        "completed": completed,
        "status": "passed",
    }
    output = result_path(args)
    if output:
        atomic_write_json(output, report)
    return report


def add_execution_arguments(parser: argparse.ArgumentParser, approval: bool) -> None:
    parser.add_argument("--plan", required=True, help="Finalized UTF-8 plan JSON")
    parser.add_argument("--task-root", default=".", help="Task root for optional result writes")
    parser.add_argument("--action", action="append", help="Action ID; repeat to select multiple")
    parser.add_argument("--result", help="Optional task-local sanitized result JSON")
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout seconds")
    if approval:
        parser.add_argument("--expected-sha256", required=True)
        parser.add_argument("--approval-id", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Contract-gated Kingdee KCS inspect/plan/apply/verify/rollback client",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Validate and finalize a task-local draft")
    plan_parser.add_argument("--draft", required=True)
    plan_parser.add_argument("--output", required=True)
    plan_parser.add_argument("--task-root", default=".")

    inspect_parser = subparsers.add_parser("inspect", help="Run read-only inspect actions")
    add_execution_arguments(inspect_parser, approval=False)

    apply_parser = subparsers.add_parser(
        "apply-approved",
        help="Run exact write actions from a user-approved plan digest",
    )
    add_execution_arguments(apply_parser, approval=True)

    verify_parser = subparsers.add_parser("verify", help="Run read-only verification actions")
    add_execution_arguments(verify_parser, approval=False)

    rollback_parser = subparsers.add_parser(
        "rollback",
        help="Run exact compensating actions from the same approved plan",
    )
    add_execution_arguments(rollback_parser, approval=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "timeout") and not 0 < args.timeout <= 300:
        print_json({"status": "failed", "error": "timeout must be in (0, 300]"}, sys.stderr)
        return 2
    try:
        if args.command == "plan":
            report = command_plan(args)
        elif args.command == "inspect":
            report = command_execute(args, "inspect")
        elif args.command == "apply-approved":
            report = command_execute(args, "apply")
        elif args.command == "verify":
            report = command_execute(args, "verify")
        elif args.command == "rollback":
            report = command_execute(args, "rollback")
        else:
            fail(f"unsupported command: {args.command}")
        print_json(report)
        return 0
    except KcsOpsError as exc:
        if not getattr(exc, "already_reported", False):
            print_json({"status": "failed", "error": str(exc)}, sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
