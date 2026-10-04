"""Response expectations, bounded JSON handling and memory-only redaction."""
from __future__ import annotations

import hashlib
import json
import operator
import re
from typing import Any

from kcs_errors import fail


# A client output limit, not a KCS product contract. Leave ample headroom for
# expectation comparisons, redaction and the JSON report encoder.
MAX_RESPONSE_DEPTH = 100


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

RELATION_OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}



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



def credential_string(value: str, runtime_credentials: tuple[str, ...]) -> bool:
    if any(secret and secret in value for secret in runtime_credentials):
        return True
    if re.search(r"(?i)\b(?:bearer|basic)\s+\S+", value):
        return True
    if re.search(r"(?i)(?:password|token|cookie|ukey)=", value):
        return True
    return False


def sanitize_string(value: str, runtime_credentials: tuple[str, ...] = ()) -> str:
    # Check before truncation, including echoes embedded in ordinary messages.
    # Empty environment values must not turn every response into a secret.
    if credential_string(value, runtime_credentials):
        return "<redacted>"
    if len(value) > 4096:
        return value[:4096] + "<truncated>"
    return value



def sanitize(value: Any, runtime_credentials: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        return {
            ("<redacted>" if credential_string(str(key), runtime_credentials)
             else str(key)): (
                "<redacted>" if secret_key(str(key))
                else sanitize(item, runtime_credentials)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item, runtime_credentials) for item in value]
    if isinstance(value, str):
        return sanitize_string(value, runtime_credentials)
    # JSON can echo a numeric credential as a number instead of a string.
    if runtime_credentials and (
        str(value) in runtime_credentials or json.dumps(value) in runtime_credentials
    ):
        return "<redacted>"
    return value



def parse_response(body: bytes, content_type: str) -> Any | None:
    stripped = body.lstrip()
    if "json" not in content_type.lower() and not stripped.startswith((b"{", b"[")):
        return None
    try:
        parsed = json.loads(body.decode("utf-8"))
    except RecursionError:
        fail("response JSON exceeds parser nesting capacity")
    except (UnicodeError, json.JSONDecodeError):
        return None
    except ValueError:
        # For example, Python's bounded integer conversion; never expose the
        # parser exception text or silently accept it as a non-JSON success.
        fail("response JSON exceeds parser value limits")
    check_response_depth(parsed)
    return parsed


def check_response_depth(value: Any) -> None:
    # Iterators keep auxiliary space bounded by depth instead of array width.
    stack = [iter((value,))]
    while stack:
        try:
            item = next(stack[-1])
        except StopIteration:
            stack.pop()
            continue
        if isinstance(item, (dict, list)):
            if len(stack) > MAX_RESPONSE_DEPTH:
                fail(f"response JSON exceeds {MAX_RESPONSE_DEPTH} container levels")
            stack.append(iter(item.values() if isinstance(item, dict) else item))



def response_view(
    body: bytes, parsed: Any, policy: str,
    runtime_credentials: tuple[str, ...] = (),
) -> dict[str, Any]:
    digest = hashlib.sha256(body).hexdigest()
    if policy == "sanitized-json" and parsed is not None:
        return {
            "type": "sanitized-json",
            "bytes": len(body),
            "sha256": digest,
            "body": sanitize(parsed, runtime_credentials),
        }
    return {"type": "summary", "bytes": len(body), "sha256": digest}
