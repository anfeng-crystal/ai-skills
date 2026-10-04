"""Plan normalization, digest and authorization contracts; no I/O or credentials."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from kcs_errors import fail
from kcs_response import RELATION_OPERATORS, sanitize_string, secret_key


SCHEMA_VERSION = 1

ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

HEADER_NAME_RE = re.compile(r"^[!#$%&'*+\-.^_|~0-9A-Za-z]+$")

ACTION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

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

ALLOWED_EVIDENCE = {
    "official-primary",
    "local-observed",
    "current-session-capture",
}

ALLOWED_ENVIRONMENTS = {"dev", "test", "prod", "unknown"}

ALLOWED_PHASES = {"inspect", "apply", "verify", "rollback"}

READ_METHODS = {"GET", "HEAD"}

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}



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
