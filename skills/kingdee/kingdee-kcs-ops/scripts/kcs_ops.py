#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import ssl
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from kcs_errors import KcsOpsError, fail
from kcs_plan import plan_digest, validate_plan
from kcs_response import check_expect, parse_response, response_view


MAX_RESPONSE_BYTES = 5 * 1024 * 1024
APPROVAL_RE = re.compile(r"^[^\r\n]{1,128}$")
class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


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
    # Values live only in this action's stack; never add them to plan/report.
    runtime_credentials = tuple(
        headers[name] for name in action.get("headers_from_env", {})
    )
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

    try:
        parsed = parse_response(body, content_type)
        check_expect(action, status, parsed)
        response = response_view(
            body, parsed, action["response_policy"], runtime_credentials,
        )
        # Verify encodability before returning a completed action. A later
        # report includes wrappers, so parsed JSON also has a fixed depth cap.
        json.dumps(response, ensure_ascii=False).encode("utf-8")
    except RecursionError:
        fail(f"action {action['id']} response processing exceeded nesting capacity")
    except UnicodeError:
        fail(f"action {action['id']} response cannot be represented as UTF-8")
    return {
        "action_id": action["id"],
        "phase": action["phase"],
        "risk": action["risk"],
        "method": action["method"],
        "path": action["path"],
        "http_status": status,
        "response": response,
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
