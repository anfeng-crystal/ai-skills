#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_SCRIPT_RUNTIME = REPO_ROOT / "scripts" / "script_runtime_real.py"
MANIFEST_PATH = REPO_ROOT / "scripts" / "engine_api_manifest.json"
JAR_PATH = REPO_ROOT / "assets" / "isc-iscb-util.jar"
CURATED_CASES_ROOT = REPO_ROOT / "assets" / "cases"
CURATED_CASES_PATH = CURATED_CASES_ROOT / "manifest.json"

SIGNATURE_RE = re.compile(
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$.%]*)\((?P<args>[^)\n]*)\)\s*->\s*(?P<ret>[A-Za-z0-9_<>\[\]|? .]+)"
)
GLOBAL_CALL_RE = re.compile(r"(?<![.\w$])([A-Za-z_$%][A-Za-z0-9_$%]*)\s*\(")
NAMESPACED_CALL_RE = re.compile(r"(?<![\w$])([A-Za-z_$][A-Za-z0-9_$]*)\.([A-Za-z_$%][A-Za-z0-9_$%]*)\s*\(")
FUNCTION_DEF_RE = re.compile(r"\bfunction\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(")
VAR_DECL_RE = re.compile(r"\bvar\s+([A-Za-z_$][A-Za-z0-9_$]*)\b")

IGNORE_GLOBAL_CALLS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "return",
    "throw",
    "println",
    "print",
}
ENGINE_EXTERNAL_GLOBALS = {
    "query_value",
    "query_row",
    "query_list",
    "query_column",
    "execute_update",
    "execute_batch",
    "execute_call",
    "HttpGet",
    "HttpPost",
    "HttpInvoke",
    "HttpAccess",
    "HttpAccess2",
    "HttpDownloadFile",
    "HttpUploadFile",
    "HttpUploadFileX",
    "CallWebService",
}
ENGINE_EXTERNAL_NAMESPACES = {
    "Ftp",
    "OpenAPI",
    "Http",
    "MinIO",
    "Ldap",
    "Mongo",
    "ClickHouse",
    "ClickHouseClient",
    "DataFile",
    "AttachPanel",
    "AttachField",
    "BusinessFlowDataService",
}
CORE_ENGINE_EXTERNAL_PREFIXES = ("query_", "execute_", "Http", "CallWebService")
JAVASCRIPT_FENCE_RE = re.compile(r"```javascript\n(.*?)\n```", re.S)
CURATED_VALIDATION_MODES = {"engine_compile", "engine_run", "reference_only"}
LEAN_SKILL_SIGNATURE_LIMIT = 12

PLATFORM_NAMESPACE_REQUIREMENTS = {
    "Ftp": "FTP/SFTP 连接资源或资源别名",
    "OpenAPI": "OpenAPI / WebAPI 连接资源或资源别名",
    "Http": "HTTP / WebAPI 连接资源或资源别名",
    "MinIO": "MinIO 连接资源或资源别名",
    "Ldap": "LDAP 连接资源或资源别名",
    "Mongo": "MongoDB 连接资源或资源别名",
    "ClickHouse": "ClickHouse 连接资源或资源别名",
    "ClickHouseClient": "ClickHouse 连接资源或资源别名",
    "DataFile": "数据文件资源或资源别名",
    "AttachPanel": "附件面板或平台资源上下文",
    "AttachField": "附件字段或平台资源上下文",
    "BusinessFlowDataService": "业务流程或平台资源上下文",
}
PLATFORM_GLOBAL_REQUIREMENTS = {
    "query_value": "数据源连接或资源别名",
    "query_row": "数据源连接或资源别名",
    "query_list": "数据源连接或资源别名",
    "query_column": "数据源连接或资源别名",
    "execute_update": "数据源连接或资源别名",
    "execute_batch": "数据源连接或资源别名",
    "execute_call": "数据源连接或资源别名",
    "HttpGet": "HTTP / WebAPI 连接资源或资源别名",
    "HttpPost": "HTTP / WebAPI 连接资源或资源别名",
    "HttpInvoke": "HTTP / WebAPI 连接资源或资源别名",
    "HttpAccess": "HTTP / WebAPI 连接资源或资源别名",
    "HttpAccess2": "HTTP / WebAPI 连接资源或资源别名",
    "HttpDownloadFile": "HTTP / WebAPI 连接资源或资源别名",
    "HttpUploadFile": "HTTP / WebAPI 连接资源或资源别名",
    "HttpUploadFileX": "HTTP / WebAPI 连接资源或资源别名",
    "CallWebService": "WebService 连接资源或资源别名",
}
PLATFORM_CONTEXT_MARKERS = (
    (re.compile(r"(?<![\w$])src\b"), "src", "`src`", "数据集成上下文，或允许使用 `src` 的脚本位置"),
    (re.compile(r"(?<![\w$])tar\b"), "tar", "`tar`", "数据集成上下文，或允许使用 `tar` 的脚本位置"),
    (re.compile(r"(?<![\w$])param\b"), "param", "`param`", "值转换规则上下文或固定输入参数定义"),
    (re.compile(r"(?<![\w$])cn\b"), "cn", "`cn`", "实际连接资源别名"),
    (re.compile(r"\$src\b"), None, "`$src`", "来源数据源连接，或允许使用 `$src` 的平台上下文"),
    (re.compile(r"\$tar\b"), None, "`$tar`", "目标数据源连接，或允许使用 `$tar` 的平台上下文"),
    (re.compile(r"\$this\b"), None, "`$this`", "当前苍穹环境连接，或允许使用 `$this` 的平台上下文"),
    (re.compile(r"\$process\b"), None, "`$process`", "服务流程上下文"),
    (re.compile(r"\$cn\b"), None, "`$cn`", "连接资源或 WebAPI / HTTP 上下文"),
    (re.compile(r"#request\b"), None, "`#request`", "请求对象结构或字段定义"),
)


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    location: str


def add_unique(items: list[str], value: str, seen: set[str]) -> None:
    if value in seen:
        return
    items.append(value)
    seen.add(value)


def summarize_hits(items: list[str], limit: int = 3) -> str:
    if not items:
        return "平台依赖"
    if len(items) <= limit:
        return "、".join(items)
    shown = "、".join(items[:limit])
    return f"{shown} 等 {len(items)} 项"


def summarize_missing_items(items: list[str]) -> str:
    return "；".join(items)


def collect_platform_dependencies(script: str, user_functions: set[str]) -> dict[str, object]:
    references: list[str] = []
    missing_items: list[str] = []
    seen_references: set[str] = set()
    seen_missing_items: set[str] = set()
    local_vars = set(VAR_DECL_RE.findall(script))

    for namespace, method in NAMESPACED_CALL_RE.findall(script):
        if namespace not in ENGINE_EXTERNAL_NAMESPACES:
            continue
        add_unique(references, f"`{namespace}.{method}()`", seen_references)
        add_unique(
            missing_items,
            PLATFORM_NAMESPACE_REQUIREMENTS.get(namespace, "平台连接资源或资源别名"),
            seen_missing_items,
        )

    for global_name in GLOBAL_CALL_RE.findall(script):
        if global_name in IGNORE_GLOBAL_CALLS or global_name in user_functions:
            continue
        if global_name not in ENGINE_EXTERNAL_GLOBALS:
            continue
        add_unique(references, f"`{global_name}()`", seen_references)
        add_unique(
            missing_items,
            PLATFORM_GLOBAL_REQUIREMENTS.get(global_name, "平台连接资源或资源别名"),
            seen_missing_items,
        )

    for pattern, local_name, label, requirement in PLATFORM_CONTEXT_MARKERS:
        if local_name is not None and local_name in local_vars:
            continue
        if not pattern.search(script):
            continue
        add_unique(references, label, seen_references)
        add_unique(missing_items, requirement, seen_missing_items)

    return {
        "has_dependency": bool(references),
        "references": references,
        "missing_items": missing_items,
    }


def build_platform_dependency_message(mode: str, dependencies: dict[str, object]) -> str:
    refs = summarize_hits(list(dependencies["references"]))
    missing_items = summarize_missing_items(list(dependencies["missing_items"]))
    if mode == "engine":
        return (
            f"检测到平台资源/上下文依赖（{refs}）。待补齐项：{missing_items}。"
            "这类脚本不在 `check-script --mode engine` 的 engine-only 静态校验范围内；"
            "补齐资源/上下文后，请到苍穹集成平台或使用真实 runtime 验证。"
        )
    return (
        f"检测到平台层参考脚本依赖（{refs}）。待补齐项：{missing_items}。"
        "`check-script --mode general` 仅做 reference-only 弱预检；"
        "bundled manifest 不能完整覆盖平台方法签名，因此不能据此宣称可运行。"
        "补齐资源/上下文后，请到苍穹集成平台或使用真实 runtime 验证。"
    )


@lru_cache(maxsize=1)
def load_manifest() -> dict[str, object]:
    if not MANIFEST_PATH.exists():
        raise SystemExit(f"missing engine api manifest: {MANIFEST_PATH}")

    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for key in ("namespaces", "globals", "signatures"):
        if key not in payload:
            raise SystemExit(f"invalid engine api manifest: missing `{key}` in {MANIFEST_PATH}")
    return payload


@lru_cache(maxsize=1)
def current_jar_sha256() -> str | None:
    if not JAR_PATH.exists():
        return None
    digest = hashlib.sha256()
    with JAR_PATH.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_doc_signatures(path: Path) -> list[tuple[str, str, str]]:
    text = path.read_text(encoding="utf-8")
    return [(m.group("name"), m.group("args"), m.group("ret").strip()) for m in SIGNATURE_RE.finditer(text)]


def doc_paths() -> list[Path]:
    return [REPO_ROOT / "SKILL.md", *sorted((REPO_ROOT / "references").glob("*.md"))]


def load_curated_case_manifest() -> dict[str, object]:
    if not CURATED_CASES_PATH.exists():
        raise SystemExit(f"missing curated cases manifest: {CURATED_CASES_PATH}")
    payload = json.loads(CURATED_CASES_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise SystemExit(f"invalid curated cases manifest: missing `cases` list in {CURATED_CASES_PATH}")
    return payload


def resolve_curated_case_path(script_path: str) -> Path:
    candidate = REPO_ROOT / script_path
    if candidate.exists():
        return candidate
    if script_path.startswith("cases/"):
        return REPO_ROOT / "assets" / script_path
    return CURATED_CASES_ROOT / script_path


def is_core_engine_signature(name: str) -> bool:
    if name.startswith(CORE_ENGINE_EXTERNAL_PREFIXES):
        return False
    return True


def bundle_findings(require_jar: bool = False) -> list[Finding]:
    payload = load_manifest()
    findings: list[Finding] = []
    jar_meta = payload.get("jar", {})
    expected_sha256 = jar_meta.get("sha256")
    actual_sha256 = current_jar_sha256()

    if require_jar and actual_sha256 is None:
        findings.append(
            Finding(
                "error",
                "missing-jar",
                f"Missing runtime jar `{JAR_PATH.name}`; this skill bundle validates scripts against the bundled jar.",
                "bundle",
            )
        )
        return findings

    if expected_sha256 and actual_sha256 and expected_sha256 != actual_sha256:
        findings.append(
            Finding(
                "warn",
                "jar-checksum-mismatch",
                f"Bundled manifest expects jar sha256 `{expected_sha256}`, but found `{actual_sha256}`.",
                "bundle",
            )
        )
    return findings


def audit_skill() -> dict[str, object]:
    manifest_index = load_manifest()
    manifest_signatures = set(manifest_index["signatures"])
    lower_to_actual = {sig.lower(): sig for sig in manifest_signatures}
    findings: list[Finding] = bundle_findings()
    skill_signature_count = len(extract_doc_signatures(REPO_ROOT / "SKILL.md"))

    checked_entries: list[tuple[str, str]] = []
    docs_to_scan = [
        (
            REPO_ROOT / "references" / "functions-engine.md",
            extract_doc_signatures(REPO_ROOT / "references" / "functions-engine.md"),
        ),
    ]

    for path, signatures in docs_to_scan:
        for name, _args, _ret in signatures:
            if not is_core_engine_signature(name):
                continue
            checked_entries.append((str(path.relative_to(REPO_ROOT)), name))
            if name in manifest_signatures:
                continue
            if name.lower() in lower_to_actual:
                findings.append(
                    Finding(
                        "error",
                        "case-mismatch",
                        f"`{name}` does not match bundled manifest case; bundled manifest uses `{lower_to_actual[name.lower()]}`.",
                        str(path.relative_to(REPO_ROOT)),
                    )
                )
            else:
                findings.append(
                    Finding(
                        "error",
                        "unknown-signature",
                        f"`{name}` is documented but was not found in the bundled engine manifest.",
                        str(path.relative_to(REPO_ROOT)),
                    )
                )

    if skill_signature_count > LEAN_SKILL_SIGNATURE_LIMIT:
        findings.append(
            Finding(
                "error",
                "skill-too-many-signatures",
                f"`SKILL.md` documents {skill_signature_count} signature-style entries; keep detailed function indexes in references/ and keep the main skill lean.",
                "SKILL.md",
            )
        )

    special_rules = [
        (
            REPO_ROOT / "SKILL.md",
            r"String\.getBytes2\(str, charset\?\)\s*->\s*String",
            "error",
            "getbytes2-return-type",
            "`String.getBytes2()` is documented as `String`, but the bundled compatibility rules expect `byte[]`.",
        ),
        (
            REPO_ROOT / "references" / "functions-engine.md",
            r"String\.getBytes2\(str, charset\?\)\s*->\s*String",
            "error",
            "getbytes2-return-type",
            "`String.getBytes2()` is documented as `String`, but the bundled compatibility rules expect `byte[]`.",
        ),
        (
            REPO_ROOT / "SKILL.md",
            r"String\.htmlEncode\(str\)",
            "error",
            "htmlencode-case",
            "`String.htmlEncode()` is documented in lower camel case, but the bundled compatibility rules expose `String.HTMLEncode()`.",
        ),
        (
            REPO_ROOT / "references" / "functions-engine.md",
            r"String\.htmlEncode\(str\)",
            "error",
            "htmlencode-case",
            "`String.htmlEncode()` is documented in lower camel case, but the bundled compatibility rules expose `String.HTMLEncode()`.",
        ),
        (
            REPO_ROOT / "SKILL.md",
            r"Boolean\.X\(value\)",
            "error",
            "boolean-x-namespace",
            "`Boolean.X()` is documented, but the bundled compatibility rules only expose the global alias `X()`.",
        ),
        (
            REPO_ROOT / "references" / "functions-engine.md",
            r"Boolean\.X\(value\)",
            "error",
            "boolean-x-namespace",
            "`Boolean.X()` is documented, but the bundled compatibility rules only expose the global alias `X()`.",
        ),
        (
            REPO_ROOT / "SKILL.md",
            r"DateDiff\(d1, d2\)",
            "error",
            "date-global-alias",
            "`DateDiff`/`DateAdd` style global helpers are documented, but no matching global aliases exist in the bundled manifest.",
        ),
        (
            REPO_ROOT / "references" / "functions-engine.md",
            r"DateDiff\(d1, d2\)",
            "error",
            "date-global-alias",
            "`DateDiff`/`DateAdd` style global helpers are documented, but no matching global aliases exist in the bundled manifest.",
        ),
        (
            REPO_ROOT / "SKILL.md",
            r"JwkToRSAPrivateKey\(jwk\)\s*->\s*PrivateKey",
            "error",
            "jwk-return-type",
            "`JwkToRSAPrivateKey()` is documented as `PrivateKey`, but the bundled compatibility rules expect a PEM string.",
        ),
    ]

    for path, pattern, severity, code, message in special_rules:
        text = path.read_text(encoding="utf-8")
        if re.search(pattern, text):
            findings.append(Finding(severity, code, message, str(path.relative_to(REPO_ROOT))))

    example_rules = [
        (
            REPO_ROOT / "references" / "patterns.md",
            r'Hash\.HmacSHA256\(\s*"[^"]+"\s*,\s*"[^"]+"\s*\)',
            "error",
            "hmac-string-args",
            "HMAC example passes raw strings, but the bundled compatibility rules require `byte[]`.",
        ),
        (
            REPO_ROOT / "references" / "conventions.md",
            r"parseInt 不是此 DSL 的函数",
            "warn",
            "bare-parseint",
            "The guidance bans bare `parseInt()`, but the bundled compatibility rules also support `Number.parseInt()`; wording should be narrowed to the bare global form.",
        ),
        (
            REPO_ROOT / "SKILL.md",
            r"不是 `parseInt\(\)` 等",
            "warn",
            "parseint-wording",
            "The anti-hallucination rule should distinguish bare `parseInt()` from bundled-supported `Number.parseInt()`.",
        ),
    ]

    for path, pattern, severity, code, message in example_rules:
        text = path.read_text(encoding="utf-8")
        if re.search(pattern, text):
            findings.append(Finding(severity, code, message, str(path.relative_to(REPO_ROOT))))

    exact_matches = 0
    for _location, signature in checked_entries:
        if signature in manifest_signatures:
            exact_matches += 1
    return {
        "checked_signature_count": len(checked_entries),
        "exact_match_count": exact_matches,
        "manifest_signature_count": len(manifest_signatures),
        "skill_signature_count": skill_signature_count,
        "findings": [asdict(finding) for finding in findings],
        "manifest_index": manifest_index,
    }


def audit_examples() -> dict[str, object]:
    preflight = bundle_findings(require_jar=True)
    if any(finding.severity == "error" for finding in preflight):
        return {
            "file_count": len(doc_paths()),
            "checked_block_count": 0,
            "passed_block_count": 0,
            "failed_block_count": len(preflight),
            "failures": [
                {
                    "location": finding.location,
                    "fence_index": 0,
                    "start_line": 0,
                    "message": finding.message,
                }
                for finding in preflight
            ],
        }

    files = doc_paths()
    failures: list[dict[str, object]] = []
    checked_count = 0
    passed_count = 0

    for path in files:
        text = path.read_text(encoding="utf-8")
        relative = str(path.relative_to(REPO_ROOT))
        for index, match in enumerate(JAVASCRIPT_FENCE_RE.finditer(text), 1):
            checked_count += 1
            block = match.group(1)
            start_line = text[: match.start()].count("\n") + 1
            runtime_result = runtime_compile(block)
            if runtime_result["status"] == "pass":
                passed_count += 1
                continue
            message = runtime_result["error"] or runtime_result["output"] or "Runtime compile failed."
            failures.append(
                {
                    "location": relative,
                    "fence_index": index,
                    "start_line": start_line,
                    "message": message.splitlines()[0],
                }
            )

    return {
        "file_count": len(files),
        "checked_block_count": checked_count,
        "passed_block_count": passed_count,
        "failed_block_count": len(failures),
        "failures": failures,
    }


def audit_curated_cases() -> dict[str, object]:
    preflight = bundle_findings(require_jar=True)
    if any(finding.severity == "error" for finding in preflight):
        return {
            "case_count": 0,
            "passed_case_count": 0,
            "failed_case_count": len(preflight),
            "engine_runnable_count": 0,
            "mode_counts": {mode: 0 for mode in sorted(CURATED_VALIDATION_MODES)},
            "failures": [
                {
                    "id": "bundle",
                    "location": finding.location,
                    "message": finding.message,
                }
                for finding in preflight
            ],
        }

    manifest = load_curated_case_manifest()
    cases = manifest["cases"]
    failures: list[dict[str, object]] = []
    passed_count = 0
    seen_ids: set[str] = set()
    mode_counts = {mode: 0 for mode in sorted(CURATED_VALIDATION_MODES)}
    engine_runnable_count = 0

    for index, raw_case in enumerate(cases, 1):
        if not isinstance(raw_case, dict):
            failures.append(
                {
                    "id": f"case#{index}",
                    "location": str(CURATED_CASES_PATH.relative_to(REPO_ROOT)),
                    "message": "Curated case entry must be an object.",
                }
            )
            continue

        case_id = str(raw_case.get("id", f"case#{index}"))
        script_path = str(raw_case.get("script_path", ""))
        location = script_path or str(CURATED_CASES_PATH.relative_to(REPO_ROOT))

        def fail(message: str) -> None:
            failures.append({"id": case_id, "location": location, "message": message})

        required_fields = ("id", "intent", "context", "script_path", "validation_mode", "notes")
        missing_fields = [
            field
            for field in required_fields
            if not isinstance(raw_case.get(field), str) or not str(raw_case.get(field)).strip()
        ]
        if missing_fields:
            fail(f"Missing required string fields: {', '.join(missing_fields)}.")
            continue

        if case_id in seen_ids:
            fail("Duplicate curated case id.")
            continue
        seen_ids.add(case_id)

        validation_mode = str(raw_case["validation_mode"])
        if validation_mode not in CURATED_VALIDATION_MODES:
            fail(
                "Unsupported validation_mode; expected one of "
                + ", ".join(sorted(CURATED_VALIDATION_MODES))
                + "."
            )
            continue
        mode_counts[validation_mode] += 1

        context = str(raw_case["context"])
        script_file = resolve_curated_case_path(script_path)
        if not script_file.exists():
            fail("Referenced script_path does not exist.")
            continue
        script = script_file.read_text(encoding="utf-8")
        if not script.strip():
            fail("Referenced script is empty.")
            continue

        if validation_mode in {"engine_compile", "engine_run"}:
            engine_runnable_count += 1
            if context != "engine":
                fail("Engine validation modes must use `context: engine`.")
                continue

        if validation_mode == "engine_compile":
            payload = check_script_with_runtime(script, "engine", True)
            if payload["status"] != "pass":
                findings = payload.get("findings", [])
                runtime = payload.get("runtime") or {}
                if findings:
                    fail(str(findings[0]["message"]))
                else:
                    fail(str(runtime.get("error") or runtime.get("output") or "Engine compile failed."))
                continue

        elif validation_mode == "engine_run":
            payload = check_script(script, "engine")
            if payload["status"] != "pass":
                findings = payload.get("findings", [])
                fail(str(findings[0]["message"]) if findings else "Engine preflight failed.")
                continue
            bindings_json_path = raw_case.get("bindings_json_path")
            bindings_json = None
            if bindings_json_path is not None:
                if not isinstance(bindings_json_path, str) or not bindings_json_path.strip():
                    fail("bindings_json_path must be a non-empty string when provided.")
                    continue
                resolved_bindings = resolve_curated_case_path(bindings_json_path)
                if not resolved_bindings.exists():
                    fail("bindings_json_path does not exist.")
                    continue
                bindings_json = str(resolved_bindings)
            runtime_result = run_script_with_runtime(script, bindings_json)
            if runtime_result["status"] != "pass":
                fail(str(runtime_result["error"] or runtime_result["output"] or "Engine run failed."))
                continue
            expected_output = raw_case.get("expected_output")
            if expected_output is not None and runtime_result["output"] != expected_output:
                fail(
                    f"Expected runtime output `{expected_output}`, but got `{runtime_result['output']}`."
                )
                continue

        else:
            if context == "engine":
                fail("reference_only cases must use a non-engine context.")
                continue
            platform_dependencies = collect_platform_dependencies(script, set(FUNCTION_DEF_RE.findall(script)))
            if not platform_dependencies["has_dependency"]:
                fail(
                    "reference_only script must contain an explicit platform dependency marker such as src/tar/$process/#request/cn, or a known platform namespace/global."
                )
                continue
            payload = check_script(script, "general")
            if payload["status"] == "fail":
                findings = payload.get("findings", [])
                fail(str(findings[0]["message"]) if findings else "Reference-only preflight failed.")
                continue

        passed_count += 1

    return {
        "case_count": len(cases),
        "passed_case_count": passed_count,
        "failed_case_count": len(failures),
        "engine_runnable_count": engine_runnable_count,
        "mode_counts": mode_counts,
        "failures": failures,
    }


def audit_bundle() -> dict[str, object]:
    skill = audit_skill()
    examples = audit_examples()
    runtime = run_runtime_selftest()
    curated = audit_curated_cases()

    failures: list[dict[str, object]] = []
    if skill["findings"]:
        for finding in skill["findings"]:
            failures.append(
                {
                    "component": "audit-skill",
                    "location": finding["location"],
                    "message": finding["message"],
                }
            )
    if examples["failures"]:
        for failure in examples["failures"]:
            failures.append(
                {
                    "component": "audit-examples",
                    "location": failure["location"],
                    "message": failure["message"],
                }
            )
    if runtime["status"] != "pass":
        failures.append(
            {
                "component": "runtime-selftest",
                "location": "bundle",
                "message": runtime["error"] or runtime["output"] or "Runtime selftest failed.",
            }
        )
    if curated["failures"]:
        for failure in curated["failures"]:
            failures.append(
                {
                    "component": "audit-curated-cases",
                    "location": failure["location"],
                    "message": failure["message"],
                }
            )

    return {
        "status": "pass" if not failures else "fail",
        "audit_skill": skill,
        "audit_examples": examples,
        "runtime_selftest": runtime,
        "audit_curated_cases": curated,
        "failure_count": len(failures),
        "failures": failures,
    }


def balance_check(script: str) -> list[Finding]:
    findings: list[Finding] = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    reverse = {value: key for key, value in pairs.items()}
    stack: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    for char in script:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if in_single or in_double:
            continue
        if char in pairs:
            stack.append(char)
        elif char in reverse:
            if not stack or stack[-1] != reverse[char]:
                findings.append(
                    Finding("error", "unbalanced-delimiter", f"Found unmatched `{char}`.", "script")
                )
                return findings
            stack.pop()
    if in_single or in_double:
        findings.append(Finding("error", "unterminated-string", "String literal is not closed.", "script"))
    if stack:
        findings.append(Finding("error", "unbalanced-delimiter", f"Unclosed delimiter `{stack[-1]}`.", "script"))
    return findings


def check_script(script: str, mode: str) -> dict[str, object]:
    manifest_index = load_manifest()
    namespaces: dict[str, set[str]] = {
        key: set(value) for key, value in manifest_index["namespaces"].items()
    }
    globals_set: set[str] = set(manifest_index["globals"])
    findings: list[Finding] = bundle_findings()

    findings.extend(balance_check(script))

    user_functions = set(FUNCTION_DEF_RE.findall(script))
    platform_dependencies = collect_platform_dependencies(script, user_functions)

    for namespace, method in NAMESPACED_CALL_RE.findall(script):
        if namespace in ENGINE_EXTERNAL_NAMESPACES:
            continue
        methods = namespaces.get(namespace)
        if methods is None:
            findings.append(
                Finding("error", "unknown-namespace", f"Unknown namespace `{namespace}`.", "script")
            )
            continue
        if method not in methods:
            lower_to_actual = {value.lower(): value for value in methods}
            if method.lower() in lower_to_actual:
                findings.append(
                    Finding(
                        "error",
                        "case-mismatch",
                        f"`{namespace}.{method}()` uses the wrong case; bundled manifest uses `{namespace}.{lower_to_actual[method.lower()]}()`.",
                        "script",
                    )
                )
            else:
                findings.append(
                    Finding(
                        "error",
                        "unknown-method",
                        f"`{namespace}.{method}()` was not found in the bundled engine manifest.",
                        "script",
                    )
                )
    for global_name in GLOBAL_CALL_RE.findall(script):
        if global_name in IGNORE_GLOBAL_CALLS or global_name in user_functions:
            continue
        if global_name in ENGINE_EXTERNAL_GLOBALS:
            continue
        if global_name not in globals_set:
            continue

    if platform_dependencies["has_dependency"]:
        if mode == "engine":
            findings.append(
                Finding(
                    "error",
                    "external-resource",
                    build_platform_dependency_message("engine", platform_dependencies),
                    "script",
                )
            )
        else:
            findings.append(
                Finding(
                    "warn",
                    "platform-reference-only",
                    build_platform_dependency_message("general", platform_dependencies),
                    "script",
                )
            )

    for bare_name in re.findall(r"(?<![.\w$])(parseInt|parseLong|parseDouble|parseDecimal)\s*\(", script):
        findings.append(
            Finding(
                "warn",
                "bare-parse",
                f"Bare `{bare_name}()` is ambiguous; prefer `I()/L()/D()/N()` or `Number.{bare_name}()`.",
                "script",
            )
        )

    if re.search(r'Hash\.Hmac[A-Za-z0-9_]*\(\s*["\'].*?["\']\s*,\s*["\'].*?["\']\s*\)', script, re.S):
        findings.append(
            Finding(
                "error",
                "hmac-string-args",
                "HMAC calls must pass `byte[]`; use `String.getBytes()` or `String.getBytes2()` first.",
                "script",
            )
        )

    status = "pass"
    if any(f.severity == "error" for f in findings):
        status = "fail"
    elif findings:
        status = "warn"

    return {
        "mode": mode,
        "status": status,
        "finding_count": len(findings),
        "findings": [asdict(finding) for finding in findings],
    }


def run_runtime_selftest() -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(REAL_SCRIPT_RUNTIME), "selftest"],
        text=True,
        capture_output=True,
    )
    output = (result.stdout or "").strip()
    error = (result.stderr or "").strip()
    status = "pass" if result.returncode == 0 else "fail"
    return {
        "status": status,
        "returncode": result.returncode,
        "output": output,
        "error": error,
    }


def runtime_compile(script: str) -> dict[str, object]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".iscb", delete=False) as handle:
        handle.write(script)
        temp_path = Path(handle.name)
    try:
        result = subprocess.run(
            [sys.executable, str(REAL_SCRIPT_RUNTIME), "compile", str(temp_path)],
            text=True,
            capture_output=True,
        )
    finally:
        temp_path.unlink(missing_ok=True)

    output = (result.stdout or "").strip()
    error = (result.stderr or "").strip()
    status = "pass" if result.returncode == 0 else "fail"
    return {
        "status": status,
        "returncode": result.returncode,
        "output": output,
        "error": error,
    }


def runtime_eval(script: str, bindings_json: str | None = None) -> dict[str, object]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".iscb", delete=False) as handle:
        handle.write(script)
        temp_path = Path(handle.name)
    try:
        args = [sys.executable, str(REAL_SCRIPT_RUNTIME), "eval", str(temp_path)]
        if bindings_json:
            args.extend(["--bindings-json", bindings_json])
        result = subprocess.run(
            args,
            text=True,
            capture_output=True,
        )
    finally:
        temp_path.unlink(missing_ok=True)

    output = (result.stdout or "").strip()
    error = (result.stderr or "").strip()
    status = "pass" if result.returncode == 0 else "fail"
    return {
        "status": status,
        "returncode": result.returncode,
        "output": output,
        "error": error,
    }


def run_script_with_runtime(script: str, bindings_json: str | None = None) -> dict[str, object]:
    runtime_result = runtime_eval(script, bindings_json)
    return {
        "status": runtime_result["status"],
        "returncode": runtime_result["returncode"],
        "output": runtime_result["output"],
        "error": runtime_result["error"],
    }


def check_script_with_runtime(script: str, mode: str, runtime: bool) -> dict[str, object]:
    payload = check_script(script, mode)
    if not runtime or mode != "engine":
        return payload

    runtime_result = None
    if payload["status"] != "fail":
        runtime_result = runtime_compile(script)
        if runtime_result["status"] != "pass":
            message = runtime_result["error"] or runtime_result["output"] or "Runtime compile failed."
            findings = list(payload["findings"])
            findings.append(
                asdict(
                    Finding(
                        "error",
                        "runtime-compile-failed",
                        f"Real Script runtime compile failed: {message}",
                        "script",
                    )
                )
            )
            payload["findings"] = findings
            payload["finding_count"] = len(findings)
            payload["status"] = "fail"

    payload["runtime"] = runtime_result
    return payload


def print_text(payload: dict[str, object], command: str) -> None:
    if command == "index":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if command == "audit-skill":
        findings = payload["findings"]
        print(
            f"checked_signatures={payload['checked_signature_count']} "
            f"skill_signatures={payload['skill_signature_count']} "
            f"exact_matches={payload['exact_match_count']} "
            f"manifest_signatures={payload['manifest_signature_count']}"
        )
        if not findings:
            print("findings=0")
            return
        print(f"findings={len(findings)}")
        for finding in findings:
            print(
                f"[{finding['severity'].upper()}] {finding['code']} "
                f"{finding['location']}: {finding['message']}"
            )
        return
    if command == "audit-examples":
        print(
            f"files={payload['file_count']} "
            f"checked_blocks={payload['checked_block_count']} "
            f"passed_blocks={payload['passed_block_count']}"
        )
        if not payload["failures"]:
            print("failures=0")
            return
        print(f"failures={payload['failed_block_count']}")
        for failure in payload["failures"]:
            print(
                f"[FAIL] {failure['location']} fence#{failure['fence_index']} "
                f"line={failure['start_line']}: {failure['message']}"
            )
        return
    if command == "audit-curated-cases":
        print(
            f"cases={payload['case_count']} "
            f"passed_cases={payload['passed_case_count']} "
            f"engine_runnable={payload['engine_runnable_count']}"
        )
        print(
            "mode_counts="
            + ",".join(f"{mode}:{count}" for mode, count in sorted(payload["mode_counts"].items()))
        )
        if not payload["failures"]:
            print("failures=0")
            return
        print(f"failures={payload['failed_case_count']}")
        for failure in payload["failures"]:
            print(f"[FAIL] {failure['id']} {failure['location']}: {failure['message']}")
        return
    if command == "audit-bundle":
        print(f"status={payload['status']} failures={payload['failure_count']}")
        print(
            f"audit_skill_findings={len(payload['audit_skill']['findings'])} "
            f"audit_examples_failures={payload['audit_examples']['failed_block_count']} "
            f"runtime_selftest={payload['runtime_selftest']['status']} "
            f"curated_case_failures={payload['audit_curated_cases']['failed_case_count']}"
        )
        if not payload["failures"]:
            return
        for failure in payload["failures"]:
            print(f"[FAIL] {failure['component']} {failure['location']}: {failure['message']}")
        return
    if command == "runtime-selftest":
        print(f"status={payload['status']} returncode={payload['returncode']}")
        if payload["output"]:
            print(payload["output"])
        if payload["error"]:
            print(payload["error"])
        return
    if command == "run-script":
        print(f"status={payload['status']} returncode={payload['returncode']}")
        if payload["output"]:
            print("return_value:")
            print(payload["output"])
        if payload["error"]:
            print("runtime_error:")
            print(payload["error"])
        return
    if command == "check-script":
        runtime = payload.get("runtime")
        runtime_text = ""
        if runtime is not None:
            runtime_text = f" runtime={runtime['status']}"
        print(
            f"status={payload['status']} mode={payload['mode']} findings={payload['finding_count']}{runtime_text}"
        )
        for finding in payload["findings"]:
            print(f"[{finding['severity'].upper()}] {finding['code']}: {finding['message']}")
        if runtime:
            if runtime["output"]:
                print(runtime["output"])
            if runtime["error"]:
                print(runtime["error"])


def load_script(args: argparse.Namespace) -> str:
    if args.stdin:
        return sys.stdin.read()
    if args.path:
        return Path(args.path).read_text(encoding="utf-8")
    raise SystemExit("script input is required")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit and validate the ISCB skill against its bundled engine manifest and jar runtime."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Dump the bundled engine api manifest.")
    index_parser.add_argument("--format", choices=("text", "json"), default="text")

    audit_parser = subparsers.add_parser("audit-skill", help="Audit engine docs against the bundled manifest.")
    audit_parser.add_argument("--format", choices=("text", "json"), default="text")

    examples_parser = subparsers.add_parser(
        "audit-examples", help="Compile all markdown javascript examples with the real Script runtime."
    )
    examples_parser.add_argument("--format", choices=("text", "json"), default="text")

    curated_parser = subparsers.add_parser(
        "audit-curated-cases", help="Audit curated regression cases and run the required validation mode for each."
    )
    curated_parser.add_argument("--format", choices=("text", "json"), default="text")

    bundle_parser = subparsers.add_parser(
        "audit-bundle", help="Run audit-skill, audit-examples, runtime-selftest, and curated case regression."
    )
    bundle_parser.add_argument("--format", choices=("text", "json"), default="text")

    check_parser = subparsers.add_parser("check-script", help="Static-check a generated DSL script.")
    check_parser.add_argument("path", nargs="?", help="Path to a script file.")
    check_parser.add_argument("--stdin", action="store_true", help="Read script from stdin.")
    check_parser.add_argument("--mode", choices=("engine", "general"), default="engine")
    check_parser.add_argument("--runtime", action="store_true", help="Also run real Script runtime compile.")
    check_parser.add_argument("--format", choices=("text", "json"), default="text")

    runtime_parser = subparsers.add_parser("runtime-selftest", help="Run real Script runtime self-tests.")
    runtime_parser.add_argument("--format", choices=("text", "json"), default="text")

    run_parser = subparsers.add_parser("run-script", help="Run a Script and print its actual return value or runtime error.")
    run_parser.add_argument("path", nargs="?", help="Path to a script file.")
    run_parser.add_argument("--stdin", action="store_true", help="Read script from stdin.")
    run_parser.add_argument("--bindings-json", help="Path to a JSON object file used as eval bindings.")
    run_parser.add_argument("--format", choices=("text", "json"), default="text")

    args = parser.parse_args(argv)

    if args.command == "index":
        payload = load_manifest()
    elif args.command == "audit-skill":
        payload = audit_skill()
    elif args.command == "audit-examples":
        payload = audit_examples()
    elif args.command == "audit-curated-cases":
        payload = audit_curated_cases()
    elif args.command == "audit-bundle":
        payload = audit_bundle()
    elif args.command == "runtime-selftest":
        payload = run_runtime_selftest()
    elif args.command == "run-script":
        payload = run_script_with_runtime(load_script(args), args.bindings_json)
    else:
        payload = check_script_with_runtime(load_script(args), args.mode, args.runtime)

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_text(payload, args.command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
