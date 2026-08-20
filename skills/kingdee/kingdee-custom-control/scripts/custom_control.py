#!/usr/bin/env python3
"""Cross-platform Kingdee Cosmic custom-control project and release helper."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence


SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "classic-control"
CONFIG_NAME = "cosmic-control.json"
TEXT_SUFFIXES = {".css", ".html", ".js", ".json", ".md", ".mjs", ".txt", ".xml", ".yml", ".yaml"}
IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
REGISTER_RE = re.compile(r"KDApi\.register\s*\(\s*(['\"])([^'\"]+)\1")
RESOURCE_RE = re.compile(
    r"KDApi\.(?:loadFile|getTemplateStringByFilePath)\s*\(\s*(['\"])([^'\"]+)\1"
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|token|secret|cookie|authorization)\b\s*[:=]\s*(['\"])([^'\"\r\n]+)\2"
)
WINDOWS_ABSOLUTE_RE = re.compile(r"(?i)(?:^|[\s'\"])[A-Z]:[\\/]")
URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)
FORBIDDEN_PACKAGE_NAMES = {
    CONFIG_NAME,
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    ".env",
    ".ds_store",
}
FORBIDDEN_SECRET_NAMES = {
    ".env",
    ".env.local",
    ".git-credentials",
    ".netrc",
    ".npmrc",
    ".pypirc",
    ".envrc",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
    "service-account.json",
}
FORBIDDEN_PACKAGE_PARTS = {".git", ".hg", ".svn", ".idea", ".vscode", "__macosx", "__pycache__", "node_modules"}
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
MAX_ARCHIVE_MEMBERS = 2_000
MAX_ARCHIVE_MEMBER_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 500 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 250
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    message: str
    path: str
    line: int = 1


class ControlError(RuntimeError):
    pass


def resolve_user_path(raw_path: str, cwd: Path | None = None) -> Path:
    """Resolve native paths and relative alternate separators without guessing drives."""
    base = cwd or Path.cwd()
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    if candidate.exists():
        return candidate.resolve()
    if os.name != "nt" and "\\" in raw_path and not re.match(r"^[A-Za-z]:\\", raw_path):
        portable = Path(raw_path.replace("\\", "/")).expanduser()
        if not portable.is_absolute():
            portable = base / portable
        return portable.resolve()
    return candidate.resolve()


def relative_contract_path(raw_path: str, label: str) -> PurePosixPath:
    normalized = raw_path.replace("\\", "/")
    if not normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        raise ControlError(f"{label} must be a project-relative path: {raw_path!r}")
    path = PurePosixPath(normalized)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ControlError(f"{label} contains an unsafe segment: {raw_path!r}")
    return path


def project_path(project: Path, raw_path: str, label: str) -> Path:
    relative = relative_contract_path(raw_path, label)
    candidate = (project / Path(*relative.parts)).resolve()
    try:
        candidate.relative_to(project.resolve())
    except ValueError as error:
        raise ControlError(f"{label} escapes the project: {raw_path!r}") from error
    if candidate == project.resolve():
        raise ControlError(f"{label} cannot resolve to the project root")
    return candidate


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ControlError(f"missing {path.name}: {path}") from error
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ControlError(f"invalid UTF-8 JSON at {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ControlError(f"{path.name} must contain a JSON object")
    return payload


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def safe_identifier(value: str, label: str) -> str:
    if not IDENTIFIER_RE.fullmatch(value):
        raise ControlError(f"{label} must start with a letter and contain only letters, digits, '_' or '-'")
    return value


def class_name(control_id: str) -> str:
    parts = [part for part in re.split(r"[-_]+", control_id) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) + "Control"


def package_name(control_id: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", control_id.lower()).strip("-")
    return f"{normalized}-cosmic-control"


def parse_targets(raw_targets: str) -> list[str]:
    targets = [item.strip().lower() for item in raw_targets.split(",") if item.strip()]
    if not targets or any(item not in {"pc", "mobile"} for item in targets):
        raise ControlError("targets must be a comma-separated subset of pc,mobile")
    return list(dict.fromkeys(targets))


def template_mapping(args: argparse.Namespace) -> dict[str, str]:
    return {
        "__CONTROL_ID__": args.control_id,
        "__CONTROL_CLASS__": class_name(args.control_id),
        "__DISPLAY_NAME_HTML__": html.escape(args.display_name, quote=True),
        "__DISPLAY_NAME_JS__": json.dumps(args.display_name, ensure_ascii=False),
        "__PACKAGE_NAME__": package_name(args.control_id),
        "__VERSION__": args.version,
    }


def copy_template(target: Path, mapping: dict[str, str]) -> list[str]:
    if not TEMPLATE_ROOT.is_dir():
        raise ControlError(f"missing bundled template: {TEMPLATE_ROOT}")
    written: list[str] = []
    for source in sorted(path for path in TEMPLATE_ROOT.rglob("*") if path.is_file()):
        relative = source.relative_to(TEMPLATE_ROOT)
        output_name = relative.name[:-5] if relative.name.endswith(".tmpl") else relative.name
        destination = target / relative.parent / output_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix.lower() in TEXT_SUFFIXES or source.name.endswith(".tmpl"):
            text = source.read_text(encoding="utf-8")
            for token, value in mapping.items():
                text = text.replace(token, value)
            write_text_atomic(destination, text)
        else:
            shutil.copyfile(source, destination)
        written.append(destination.relative_to(target).as_posix())
    return written


def init_project(args: argparse.Namespace) -> dict[str, Any]:
    project = resolve_user_path(args.project)
    if project.exists() and (not project.is_dir() or any(project.iterdir())):
        raise ControlError(f"project target must be absent or empty: {project}")
    safe_identifier(args.control_id, "control-id")
    safe_identifier(args.domain, "domain")
    safe_identifier(args.module, "module")
    if not VERSION_RE.fullmatch(args.version):
        raise ControlError("version must be semantic version text such as 0.1.0")
    targets = parse_targets(args.targets)
    project.mkdir(parents=True, exist_ok=True)
    written = copy_template(project, template_mapping(args))
    config = {
        "schemaVersion": 1,
        "controlId": args.control_id,
        "displayName": args.display_name,
        "version": args.version,
        "runtimeContract": "classic-kdapi-candidate-v1",
        "targets": targets,
        "platform": {
            "schemeId": args.control_id,
            "domain": args.domain,
            "module": args.module,
            "forms": [],
        },
        "platformEvidence": {
            "version": args.platform_version,
            "profileStatus": "candidate",
            "source": "",
            "verifiedAt": "",
        },
        "features": {
            "pageInvoke": True,
            "pageEvents": True,
            "serverInvoke": True,
        },
        "sourceDir": "src",
        "build": {
            "mode": "static",
            "outputDir": f"dist/{args.control_id}",
            "command": [],
        },
        "test": {
            "mode": "node-test",
            "files": ["tests/control.test.mjs"],
            "command": [],
        },
        "package": {"layout": "flat-runtime-root"},
    }
    write_json_atomic(project / CONFIG_NAME, config)
    written.append(CONFIG_NAME)
    return {
        "status": "created",
        "project": str(project),
        "controlId": args.control_id,
        "profileStatus": "candidate",
        "files": sorted(written),
    }


def add_finding(
    findings: list[Finding], level: str, code: str, message: str, path: Path | str, line: int = 1
) -> None:
    findings.append(Finding(level, code, message, str(path), line))


def validate_config(config: dict[str, Any], config_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    if config.get("schemaVersion") != 1:
        add_finding(findings, "error", "CC001", "schemaVersion must be 1", config_path)
    control_id = config.get("controlId")
    if not isinstance(control_id, str) or not IDENTIFIER_RE.fullmatch(control_id):
        add_finding(findings, "error", "CC002", "controlId is missing or path-unsafe", config_path)
    version = config.get("version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        add_finding(findings, "error", "CC003", "version must be semantic version text", config_path)
    targets = config.get("targets")
    if not isinstance(targets, list) or not targets or any(item not in {"pc", "mobile"} for item in targets):
        add_finding(findings, "error", "CC004", "targets must be a non-empty pc/mobile list", config_path)
    platform = config.get("platform")
    if not isinstance(platform, dict):
        add_finding(findings, "error", "CC005", "platform contract is missing", config_path)
    elif isinstance(control_id, str) and platform.get("schemeId") != control_id:
        add_finding(findings, "error", "CC006", "platform.schemeId must equal controlId", config_path)
    for key in ("domain", "module"):
        value = platform.get(key) if isinstance(platform, dict) else None
        if not isinstance(value, str) or not IDENTIFIER_RE.fullmatch(value):
            add_finding(findings, "error", "CC007", f"platform.{key} is missing or path-unsafe", config_path)
    evidence = config.get("platformEvidence")
    if not isinstance(evidence, dict) or not str(evidence.get("version", "")).strip():
        add_finding(findings, "error", "CC008", "target platform version is required", config_path)
    elif evidence.get("profileStatus") not in {"candidate", "verified"}:
        add_finding(findings, "error", "CC009", "profileStatus must be candidate or verified", config_path)
    elif evidence.get("profileStatus") == "verified":
        if not evidence.get("source") or not evidence.get("verifiedAt"):
            add_finding(
                findings,
                "error",
                "CC010",
                "verified profile requires source and verifiedAt evidence",
                config_path,
            )
    else:
        add_finding(
            findings,
            "warning",
            "CC011",
            "runtime profile is candidate; target-platform verification is still required",
            config_path,
        )
    for raw_path, label in (
        (config.get("sourceDir"), "sourceDir"),
        ((config.get("build") or {}).get("outputDir") if isinstance(config.get("build"), dict) else None, "build.outputDir"),
    ):
        if not isinstance(raw_path, str):
            add_finding(findings, "error", "CC012", f"{label} is missing", config_path)
            continue
        try:
            relative_contract_path(raw_path, label)
        except ControlError as error:
            add_finding(findings, "error", "CC013", str(error), config_path)
    sensitive_keys = {"password", "passwd", "token", "secret", "cookie", "authorization"}

    def inspect_sensitive(value: Any, prefix: str = "") -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                key_path = f"{prefix}.{key}" if prefix else str(key)
                is_empty_or_placeholder = nested is None or (
                    isinstance(nested, str) and nested in {"", "<redacted>", "${ENV}"}
                )
                if str(key).lower() in sensitive_keys and not is_empty_or_placeholder:
                    add_finding(
                        findings,
                        "error",
                        "CC014",
                        f"credential-like config value is not allowed: {key_path}",
                        config_path,
                    )
                inspect_sensitive(nested, key_path)
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                inspect_sensitive(nested, f"{prefix}[{index}]")

    inspect_sensitive(config)
    return findings


def apply_deterministic_fixes(project: Path, config: dict[str, Any]) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    control_id = config.get("controlId")
    if not isinstance(control_id, str) or not IDENTIFIER_RE.fullmatch(control_id):
        return changes
    platform = config.get("platform")
    if isinstance(platform, dict) and platform.get("schemeId") != control_id:
        before = str(platform.get("schemeId", ""))
        platform["schemeId"] = control_id
        write_json_atomic(project / CONFIG_NAME, config)
        changes.append({"path": CONFIG_NAME, "change": f"schemeId: {before!r} -> {control_id!r}"})
    source_dir = config.get("sourceDir")
    if not isinstance(source_dir, str):
        return changes
    try:
        entry = project_path(project, source_dir, "sourceDir") / "index.js"
    except ControlError:
        return changes
    if not entry.is_file():
        return changes
    text = entry.read_text(encoding="utf-8")
    matches = list(REGISTER_RE.finditer(text))
    if len(matches) == 1 and matches[0].group(2) != control_id:
        match = matches[0]
        quote = match.group(1)
        start, end = match.span(2)
        updated = text[:start] + control_id + text[end:]
        write_text_atomic(entry, updated)
        changes.append(
            {
                "path": entry.relative_to(project).as_posix(),
                "change": f"KDApi.register: {match.group(2)!r} -> {control_id!r} ({quote})",
            }
        )
    return changes


def iter_files(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file() or path.is_symlink())


def is_credential_like_name(name: str) -> bool:
    lower_name = name.casefold()
    return (
        lower_name in FORBIDDEN_SECRET_NAMES
        or lower_name.startswith(".env.")
        or lower_name.startswith("credentials.")
        or lower_name.startswith("service-account.")
    )


def read_scannable_text(path: Path) -> str | None:
    if path.stat().st_size > 2_000_000:
        return None
    content = path.read_bytes()
    if b"\x00" in content and path.suffix.lower() not in TEXT_SUFFIXES:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeError:
        if path.suffix.lower() in TEXT_SUFFIXES:
            raise
        return None


def scan_tree_security(root: Path, *, package_stage: bool) -> list[Finding]:
    findings: list[Finding] = []
    if not root.is_dir():
        add_finding(findings, "error", "CC100", "runtime tree is missing", root)
        return findings
    for path in iter_files(root):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            add_finding(findings, "error", "CC101", "symbolic links are not allowed", relative)
            continue
        lower_name = path.name.lower()
        if is_credential_like_name(lower_name) or path.suffix.lower() in {".pem", ".p12", ".pfx", ".key"}:
            add_finding(findings, "error", "CC102", "credential-like file is not allowed", relative)
        if package_stage and (
            lower_name in FORBIDDEN_PACKAGE_NAMES
            or "tests" in {part.lower() for part in path.relative_to(root).parts}
            or "tools" in {part.lower() for part in path.relative_to(root).parts}
            or bool(FORBIDDEN_PACKAGE_PARTS & {part.casefold() for part in path.relative_to(root).parts})
            or path.suffix.lower() == ".map"
        ):
            add_finding(findings, "error", "CC103", "project-only file leaked into runtime package", relative)
        try:
            text = read_scannable_text(path)
        except UnicodeError:
            add_finding(findings, "error", "CC104", "text resource is not UTF-8", relative)
            continue
        if text is None:
            continue
        absolute = WINDOWS_ABSOLUTE_RE.search(text)
        if absolute or "file://" in text:
            offset = absolute.start() if absolute else text.index("file://")
            add_finding(
                findings,
                "error",
                "CC105",
                "host-specific absolute resource path is not allowed",
                relative,
                line_number(text, offset),
            )
        for match in SECRET_ASSIGNMENT_RE.finditer(text):
            value = match.group(3).strip()
            if value and not value.startswith(("<", "${", "__")) and value.lower() not in {"null", "none", "example"}:
                add_finding(
                    findings,
                    "error",
                    "CC106",
                    f"hard-coded {match.group(1)}-like value is not allowed",
                    relative,
                    line_number(text, match.start()),
                )
        for match in URL_RE.finditer(text):
            add_finding(
                findings,
                "warning",
                "CC107",
                "external URL requires target CSP, version, license and integrity review",
                relative,
                line_number(text, match.start()),
            )
    return findings


def validate_runtime_tree(root: Path, config: dict[str, Any], *, package_stage: bool) -> list[Finding]:
    findings = scan_tree_security(root, package_stage=package_stage)
    entry = root / "index.js"
    if not entry.is_file():
        add_finding(findings, "error", "CC110", "runtime root must contain index.js", "index.js")
        return findings
    try:
        text = entry.read_text(encoding="utf-8")
    except UnicodeError:
        add_finding(findings, "error", "CC111", "index.js must be UTF-8", "index.js")
        return findings
    node = shutil.which("node")
    if node:
        try:
            syntax = subprocess.run(
                [node, "--check", str(entry)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            add_finding(findings, "error", "CC123", "JavaScript syntax check timed out", "index.js")
        else:
            if syntax.returncode != 0:
                detail = redact_text((syntax.stderr or syntax.stdout).strip().splitlines()[-1] if (syntax.stderr or syntax.stdout).strip() else "syntax error")
                add_finding(findings, "error", "CC123", f"JavaScript syntax check failed: {detail}", "index.js")
    else:
        add_finding(findings, "warning", "CC124", "node is unavailable; JavaScript parser check was not run", "index.js")
    control_id = config.get("controlId")
    matches = list(REGISTER_RE.finditer(text))
    if len(matches) != 1:
        add_finding(findings, "error", "CC112", "index.js must contain exactly one literal KDApi.register", "index.js")
    elif matches[0].group(2) != control_id:
        add_finding(
            findings,
            "error",
            "CC113",
            f"registered ID {matches[0].group(2)!r} does not match controlId {control_id!r}",
            "index.js",
            line_number(text, matches[0].start()),
        )
    for hook in ("init", "update"):
        if not re.search(rf"\b{hook}\s*(?::\s*function|\()", text):
            add_finding(findings, "error", "CC114", f"missing {hook} lifecycle hook", "index.js")
    destroy_hooks = [hook for hook in ("destoryed", "destroyed") if re.search(rf"\b{hook}\s*(?::\s*function|\()", text)]
    if not destroy_hooks:
        add_finding(findings, "error", "CC115", "missing destruction lifecycle hook", "index.js")
    elif len(destroy_hooks) == 1:
        add_finding(
            findings,
            "warning",
            "CC116",
            f"only {destroy_hooks[0]} is present; require target-version lifecycle evidence",
            "index.js",
        )
    features = config.get("features") if isinstance(config.get("features"), dict) else {}
    feature_patterns = {
        "pageInvoke": (r"\bhandleDirective\s*(?::\s*function|\()", "handleDirective"),
        "pageEvents": (r"\.triggerCustomMsgEvent\s*\(", "triggerCustomMsgEvent"),
        "serverInvoke": (r"\.invoke\s*\(", "model.invoke"),
    }
    for key, (pattern, label) in feature_patterns.items():
        if features.get(key) is True and not re.search(pattern, text):
            add_finding(findings, "error", "CC117", f"feature {key} requires {label}", "index.js")
    if re.search(r"\bdocument\.(?:querySelector|getElementById|querySelectorAll)\s*\(", text):
        add_finding(findings, "warning", "CC118", "scope DOM lookup to model.dom", "index.js")
    if re.search(r"\bwindow\.on(?:resize|message|click)\s*=", text):
        add_finding(findings, "warning", "CC119", "global event assignment needs paired cleanup", "index.js")
    dangerous = re.search(r"\b(?:eval|Function)\s*\(|\bdocument\.write\s*\(", text)
    if dangerous:
        add_finding(
            findings,
            "error",
            "CC125",
            "dynamic code execution/document.write is not allowed in the runtime baseline",
            "index.js",
            line_number(text, dangerous.start()),
        )
    unsafe_html = re.search(r"\.innerHTML\s*=\s*(?:props|data|arg|payload)\b", text)
    if unsafe_html:
        add_finding(
            findings,
            "error",
            "CC126",
            "untrusted message data must not be assigned directly to innerHTML",
            "index.js",
            line_number(text, unsafe_html.start()),
        )
    for match in RESOURCE_RE.finditer(text):
        resource = match.group(2)
        if re.match(r"^(?:https?:|//|/|[A-Za-z]:[\\/])", resource):
            add_finding(
                findings,
                "error",
                "CC120",
                f"runtime resource must be relative: {resource}",
                "index.js",
                line_number(text, match.start()),
            )
            continue
        try:
            relative = relative_contract_path(resource.removeprefix("./"), "runtime resource")
        except ControlError as error:
            add_finding(findings, "error", "CC121", str(error), "index.js", line_number(text, match.start()))
            continue
        resource_path = root / Path(*relative.parts)
        if not resource_path.is_file():
            add_finding(
                findings,
                "error",
                "CC122",
                f"referenced runtime resource is missing: {resource}",
                "index.js",
                line_number(text, match.start()),
            )
    return sorted(findings, key=lambda item: (item.level != "error", item.path, item.line, item.code))


def validate_project(project: Path, *, stage: str = "source", fix: bool = False) -> dict[str, Any]:
    config_path = project / CONFIG_NAME
    config = read_json(config_path)
    changes = apply_deterministic_fixes(project, config) if fix and stage == "source" else []
    if changes:
        config = read_json(config_path)
    findings = validate_config(config, config_path)
    raw_root = config.get("sourceDir") if stage == "source" else (config.get("build") or {}).get("outputDir")
    if isinstance(raw_root, str):
        try:
            root = project_path(project, raw_root, f"{stage} root")
            findings.extend(validate_runtime_tree(root, config, package_stage=stage == "build"))
        except ControlError as error:
            add_finding(findings, "error", "CC123", str(error), config_path)
    errors = sum(item.level == "error" for item in findings)
    warnings = sum(item.level == "warning" for item in findings)
    return {
        "status": "pass" if errors == 0 else "fail",
        "stage": stage,
        "project": str(project),
        "errors": errors,
        "warnings": warnings,
        "changes": changes,
        "findings": [asdict(item) for item in findings],
        "config": config,
    }


def command_array(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
        raise ControlError(f"{label} must be a non-empty JSON string array")
    executable = shutil.which(value[0])
    if not executable:
        raise ControlError(f"command not found: {value[0]}")
    return [executable, *value[1:]]


def run_command(argv: Sequence[str], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=300,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode() if isinstance(error.stdout, bytes) else (error.stdout or "")
        stderr = error.stderr.decode() if isinstance(error.stderr, bytes) else (error.stderr or "")
        return {
            "command": [argv[0], "<args-redacted>"],
            "exitCode": 124,
            "stdout": redact_text(stdout[-20_000:]),
            "stderr": redact_text((stderr + "\ncommand timed out after 300 seconds")[-20_000:]),
            "status": "fail",
        }
    return {
        "command": [argv[0], "<args-redacted>"],
        "exitCode": completed.returncode,
        "stdout": redact_text(completed.stdout[-20_000:]),
        "stderr": redact_text(completed.stderr[-20_000:]),
        "status": "pass" if completed.returncode == 0 else "fail",
    }


def redact_text(text: str) -> str:
    text = re.sub(
        r"(?i)\b(password|passwd|token|secret|cookie|authorization)\b(\s*[:=]\s*)([^\s,;]+)",
        r"\1\2<redacted>",
        text,
    )
    return re.sub(r"(?i)([?&](?:token|signature|sig|key)=)[^&\s]+", r"\1<redacted>", text)


def test_project(project: Path, *, allow_external_command: bool) -> dict[str, Any]:
    config = read_json(project / CONFIG_NAME)
    test_config = config.get("test")
    if not isinstance(test_config, dict):
        raise ControlError("test contract is missing")
    mode = test_config.get("mode")
    if mode == "node-test":
        raw_files = test_config.get("files")
        if not isinstance(raw_files, list) or not raw_files:
            raise ControlError("node-test requires test.files")
        files: list[str] = []
        for raw_file in raw_files:
            if not isinstance(raw_file, str):
                raise ControlError("test.files must contain strings")
            path = project_path(project, raw_file, "test file")
            if not path.is_file():
                raise ControlError(f"missing test file: {raw_file}")
            files.append(str(path))
        node = shutil.which("node")
        if not node:
            raise ControlError("node is required to run generated control tests")
        result = run_command([node, "--test", *files], project)
    elif mode == "external":
        if not allow_external_command:
            raise ControlError("external test command requires --run-command after command review")
        result = run_command(command_array(test_config.get("command"), "test.command"), project)
    else:
        raise ControlError(f"unsupported test mode: {mode!r}")
    result["mode"] = mode
    return result


def remove_precise_build_dir(project: Path, build_dir: Path) -> None:
    try:
        relative = build_dir.resolve().relative_to(project.resolve())
    except ValueError as error:
        raise ControlError("build directory escapes the project") from error
    if len(relative.parts) < 2:
        raise ControlError("build directory must be a nested project directory")
    if build_dir.exists():
        if build_dir.is_symlink() or not build_dir.is_dir():
            raise ControlError(f"refusing to replace non-directory build target: {build_dir}")
        shutil.rmtree(build_dir)


def build_project(project: Path, *, allow_external_command: bool) -> dict[str, Any]:
    validation = validate_project(project, stage="source")
    if validation["errors"]:
        raise ControlError("source validation failed; build was not started")
    config = validation["config"]
    build_config = config.get("build")
    if not isinstance(build_config, dict):
        raise ControlError("build contract is missing")
    build_dir = project_path(project, str(build_config.get("outputDir", "")), "build.outputDir")
    source_dir = project_path(project, str(config.get("sourceDir", "")), "sourceDir")
    if is_within(build_dir, source_dir) or is_within(source_dir, build_dir):
        raise ControlError("sourceDir and build.outputDir must not contain each other")
    mode = build_config.get("mode")
    command_result: dict[str, Any] | None = None
    if mode == "static":
        remove_precise_build_dir(project, build_dir)
        build_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_dir, build_dir, symlinks=False)
    elif mode == "external":
        if not allow_external_command:
            raise ControlError("external build command requires --run-command after command review")
        remove_precise_build_dir(project, build_dir)
        build_dir.parent.mkdir(parents=True, exist_ok=True)
        command_result = run_command(command_array(build_config.get("command"), "build.command"), project)
        if command_result["exitCode"] != 0:
            raise ControlError("external build command failed")
    else:
        raise ControlError(f"unsupported build mode: {mode!r}")
    validation = validate_project(project, stage="build")
    if validation["errors"]:
        raise ControlError("built runtime failed package-stage validation")
    files = [path.relative_to(build_dir).as_posix() for path in iter_files(build_dir) if path.is_file()]
    return {
        "status": "pass",
        "mode": mode,
        "buildDir": str(build_dir),
        "files": sorted(files),
        "warnings": validation["warnings"],
        "findings": validation["findings"],
        "commandResult": command_result,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_project(project: Path, archive: Path, *, replace: bool) -> dict[str, Any]:
    validation = validate_project(project, stage="build")
    if validation["errors"]:
        raise ControlError("build validation failed; package was not created")
    config = validation["config"]
    build_dir = project_path(project, str((config.get("build") or {}).get("outputDir", "")), "build.outputDir")
    if is_within(archive, build_dir):
        raise ControlError("archive must be outside build.outputDir")
    if archive.exists() and not replace:
        raise ControlError(f"archive already exists; pass --replace for this exact file: {archive}")
    archive.parent.mkdir(parents=True, exist_ok=True)
    files = [path for path in iter_files(build_dir) if path.is_file() and not path.is_symlink()]
    if not files:
        raise ControlError("build directory contains no runtime files")
    handle, temp_name = tempfile.mkstemp(prefix=f".{archive.name}.", suffix=".zip", dir=archive.parent)
    os.close(handle)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
            for path in sorted(files, key=lambda item: item.relative_to(build_dir).as_posix()):
                relative = path.relative_to(build_dir).as_posix()
                info = zipfile.ZipInfo(relative, ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = (0o100644 & 0xFFFF) << 16
                bundle.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        verification = verify_archive(project, temp_path)
        if verification["errors"]:
            raise ControlError("new archive failed verification")
        os.replace(temp_path, archive)
        verification["archive"] = str(archive)
        for finding in verification["findings"]:
            if finding.get("path") == str(temp_path):
                finding["path"] = str(archive)
    except BaseException:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        raise
    return {
        "status": "pass",
        "archive": str(archive),
        "sha256": sha256_file(archive),
        "size": archive.stat().st_size,
        "files": verification["files"],
        "warnings": verification["warnings"],
        "findings": verification["findings"],
    }


def unsafe_archive_name(name: str) -> bool:
    if "\\" in name:
        return True
    normalized = unicodedata.normalize("NFC", name)
    path = PurePosixPath(normalized)
    return (
        not normalized
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:/", normalized) is not None
        or any(part in {"", ".", ".."} for part in path.parts)
    )


def windows_unsafe_archive_name(name: str) -> bool:
    normalized = unicodedata.normalize("NFC", name.rstrip("/"))
    for part in PurePosixPath(normalized).parts:
        if part.endswith((" ", ".")):
            return True
        if any(ord(character) < 32 or character in '<>:"|?*' for character in part):
            return True
        if part.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
            return True
    return False


def archive_collision_key(name: str) -> str:
    return unicodedata.normalize("NFC", name.rstrip("/")).casefold()


def verify_archive(project: Path, archive: Path) -> dict[str, Any]:
    config_path = project / CONFIG_NAME
    config = read_json(config_path)
    findings = [finding for finding in validate_config(config, config_path) if finding.level == "error"]
    names: list[str] = []
    if not archive.is_file():
        add_finding(findings, "error", "CC300", "archive is missing", archive)
        return {
            "status": "fail",
            "archive": str(archive),
            "errors": 1,
            "warnings": 0,
            "files": [],
            "findings": [asdict(item) for item in findings],
        }
    try:
        with zipfile.ZipFile(archive, "r") as bundle:
            infos = bundle.infolist()
            all_names = [info.filename for info in infos]
            names = [info.filename for info in infos if not info.is_dir()]
            if len(infos) > MAX_ARCHIVE_MEMBERS:
                add_finding(
                    findings,
                    "error",
                    "CC316",
                    f"archive member count exceeds {MAX_ARCHIVE_MEMBERS}",
                    archive,
                )
            if len(all_names) != len(set(all_names)):
                add_finding(findings, "error", "CC301", "archive contains duplicate entries", archive)
            collision_keys: dict[str, str] = {}
            total_size = 0
            for info in infos:
                name = info.filename
                if unsafe_archive_name(name):
                    add_finding(findings, "error", "CC302", f"unsafe archive path: {name!r}", archive)
                if windows_unsafe_archive_name(name):
                    add_finding(findings, "error", "CC315", f"Windows-unsafe archive path: {name!r}", archive)
                collision_key = archive_collision_key(name)
                previous = collision_keys.get(collision_key)
                if previous is not None and previous != name:
                    add_finding(
                        findings,
                        "error",
                        "CC315",
                        f"cross-platform archive path collision: {previous!r} and {name!r}",
                        archive,
                    )
                else:
                    collision_keys[collision_key] = name
                mode = (info.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    add_finding(findings, "error", "CC303", f"archive symlink is not allowed: {name}", archive)
                if info.flag_bits & 0x1:
                    add_finding(findings, "error", "CC317", f"encrypted archive member is not allowed: {name}", archive)
                lower_name = PurePosixPath(name).name.lower()
                if (
                    is_credential_like_name(lower_name)
                    or lower_name in FORBIDDEN_PACKAGE_NAMES
                    or "tests" in {part.casefold() for part in PurePosixPath(name).parts}
                    or "tools" in {part.casefold() for part in PurePosixPath(name).parts}
                    or bool(FORBIDDEN_PACKAGE_PARTS & {part.casefold() for part in PurePosixPath(name).parts})
                    or PurePosixPath(name).suffix.lower() == ".map"
                ):
                    add_finding(findings, "error", "CC304", f"project-only file in archive: {name}", archive)
                if info.is_dir():
                    continue
                total_size += info.file_size
                if info.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                    add_finding(findings, "error", "CC316", f"archive member is too large: {name}", archive)
                if info.file_size and (
                    info.compress_size == 0
                    or info.file_size / max(info.compress_size, 1) > MAX_ARCHIVE_COMPRESSION_RATIO
                ):
                    add_finding(findings, "error", "CC316", f"archive compression ratio is unsafe: {name}", archive)
            if total_size > MAX_ARCHIVE_TOTAL_BYTES:
                add_finding(
                    findings,
                    "error",
                    "CC316",
                    f"archive expanded size exceeds {MAX_ARCHIVE_TOTAL_BYTES} bytes",
                    archive,
                )

            if not any(item.level == "error" for item in findings):
                with tempfile.TemporaryDirectory(prefix="kingdee-control-verify-") as temp_dir:
                    runtime_root = Path(temp_dir)
                    for info in infos:
                        if info.is_dir():
                            continue
                        relative = PurePosixPath(unicodedata.normalize("NFC", info.filename))
                        destination = runtime_root.joinpath(*relative.parts)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with bundle.open(info, "r") as source, destination.open("wb") as target:
                            shutil.copyfileobj(source, target, length=1024 * 1024)
                    findings.extend(validate_runtime_tree(runtime_root, config, package_stage=True))
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        add_finding(findings, "error", "CC309", f"invalid ZIP archive: {error}", archive)
    evidence = config.get("platformEvidence") if isinstance(config.get("platformEvidence"), dict) else {}
    if evidence.get("profileStatus") != "verified":
        add_finding(
            findings,
            "warning",
            "CC310",
            "archive layout and runtime remain candidate until target-version verification",
            archive,
        )
    errors = sum(item.level == "error" for item in findings)
    warnings = sum(item.level == "warning" for item in findings)
    return {
        "status": "pass" if errors == 0 else "fail",
        "archive": str(archive),
        "errors": errors,
        "warnings": warnings,
        "files": sorted(names),
        "findings": [asdict(item) for item in findings],
    }


def release_project(
    project: Path, output_dir: Path, *, replace: bool, allow_external_command: bool
) -> dict[str, Any]:
    source_validation = validate_project(project, stage="source")
    if source_validation["errors"]:
        raise ControlError("source validation failed; release was not started")
    config = source_validation["config"]
    build_dir = project_path(project, str((config.get("build") or {}).get("outputDir", "")), "build.outputDir")
    source_dir = project_path(project, str(config.get("sourceDir", "")), "sourceDir")
    if is_within(output_dir, build_dir) or is_within(output_dir, source_dir):
        raise ControlError("release output must be outside sourceDir and build.outputDir")
    artifact_base = f"{config['controlId']}-{config['version']}"
    archive = output_dir / f"{artifact_base}.zip"
    checksum_path = output_dir / f"{archive.name}.sha256"
    manifest_path = output_dir / f"{artifact_base}.delivery.json"
    existing = [path for path in (archive, checksum_path, manifest_path) if path.exists()]
    if existing and not replace:
        raise ControlError(
            "release artifact already exists; pass --replace for these exact files: "
            + ", ".join(str(path) for path in existing)
        )
    tests = test_project(project, allow_external_command=allow_external_command)
    if tests["exitCode"] != 0:
        raise ControlError("tests failed; release was not built")
    build = build_project(project, allow_external_command=allow_external_command)
    output_dir.mkdir(parents=True, exist_ok=True)
    packaged = package_project(project, archive, replace=replace)
    runtime_profile = config.get("platformEvidence", {})
    manifest = {
        "schemaVersion": 1,
        "controlId": config["controlId"],
        "displayName": config["displayName"],
        "version": config["version"],
        "runtimeContract": config["runtimeContract"],
        "targets": config["targets"],
        "platform": config["platform"],
        "platformEvidence": runtime_profile,
        "artifact": {
            "file": archive.name,
            "sha256": packaged["sha256"],
            "size": packaged["size"],
            "files": packaged["files"],
        },
        "gates": {
            "sourceValidation": "pass",
            "unitTests": "pass",
            "build": "pass",
            "packageVerification": "pass",
        },
        "localRelease": "pass",
        "platformInstall": "not-run",
        "runtimeVerification": {"status": "not-run", "required": True},
        "rollback": "not-defined",
        "warnings": source_validation["warnings"] + build["warnings"] + packaged["warnings"],
    }
    write_text_atomic(checksum_path, f"{packaged['sha256']}  {archive.name}\n")
    write_json_atomic(manifest_path, manifest)
    return {
        "status": "pass",
        "project": str(project),
        "archive": str(archive),
        "checksum": str(checksum_path),
        "manifest": str(manifest_path),
        "sha256": packaged["sha256"],
        "profileStatus": runtime_profile.get("profileStatus", "candidate"),
        "platformInstall": "not-run",
        "runtimeVerification": "not-run",
        "tests": tests,
        "build": build,
    }


def emit(payload: dict[str, Any], *, output_json: bool) -> None:
    if output_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"STATUS: {payload.get('status', 'unknown')}")
    for key in (
        "project",
        "stage",
        "controlId",
        "profileStatus",
        "buildDir",
        "archive",
        "sha256",
        "checksum",
        "manifest",
        "platformInstall",
        "runtimeVerification",
    ):
        if key in payload:
            print(f"{key}: {payload[key]}")
    if payload.get("changes"):
        for change in payload["changes"]:
            print(f"FIXED: {change['path']}: {change['change']}")
    for finding in payload.get("findings", []):
        print(
            f"{finding['level'].upper()}: {finding['path']}:{finding['line']}: "
            f"{finding['code']} {finding['message']}"
        )
    if "stdout" in payload and payload["stdout"]:
        print(payload["stdout"].rstrip())
    if "stderr" in payload and payload["stderr"]:
        print(payload["stderr"].rstrip(), file=sys.stderr)


def add_common_project_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", required=True, help="Custom-control project root")
    parser.add_argument("--json", action="store_true", dest="output_json", help="Emit JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a candidate classic KDApi project")
    add_common_project_argument(init_parser)
    init_parser.add_argument("--control-id", required=True)
    init_parser.add_argument("--display-name", required=True)
    init_parser.add_argument("--domain", required=True)
    init_parser.add_argument("--module", required=True)
    init_parser.add_argument("--platform-version", required=True)
    init_parser.add_argument("--targets", default="pc", help="pc,mobile")
    init_parser.add_argument("--version", default="0.1.0")

    validate_parser = subparsers.add_parser("validate", help="Validate source or built runtime")
    add_common_project_argument(validate_parser)
    validate_parser.add_argument("--stage", choices=("source", "build"), default="source")
    validate_parser.add_argument("--fix", action="store_true")
    validate_parser.add_argument("--strict", action="store_true", help="Treat warnings as failure")

    test_parser = subparsers.add_parser("test", help="Run declared unit tests")
    add_common_project_argument(test_parser)
    test_parser.add_argument("--run-command", action="store_true", help="Allow reviewed external command")

    build_parser_ = subparsers.add_parser("build", help="Build the runtime tree")
    add_common_project_argument(build_parser_)
    build_parser_.add_argument("--run-command", action="store_true", help="Allow reviewed external command")

    package_parser = subparsers.add_parser("package", help="Create a deterministic ZIP from build output")
    add_common_project_argument(package_parser)
    package_parser.add_argument("--archive", required=True)
    package_parser.add_argument("--replace", action="store_true")

    release_parser = subparsers.add_parser("release", help="Test, build, package and emit delivery evidence")
    add_common_project_argument(release_parser)
    release_parser.add_argument("--output-dir", required=True)
    release_parser.add_argument("--replace", action="store_true")
    release_parser.add_argument("--run-command", action="store_true", help="Allow reviewed external commands")

    verify_parser = subparsers.add_parser(
        "verify-package", help="Verify a ZIP through an isolated, bounded temporary runtime tree"
    )
    add_common_project_argument(verify_parser)
    verify_parser.add_argument("--archive", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            payload = init_project(args)
        else:
            project = resolve_user_path(args.project)
            if not project.is_dir():
                raise ControlError(f"project directory does not exist: {project}")
            if args.command == "validate":
                payload = validate_project(project, stage=args.stage, fix=args.fix)
                failed = payload["errors"] > 0 or (args.strict and payload["warnings"] > 0)
                emit(payload, output_json=args.output_json)
                return 1 if failed else 0
            if args.command == "test":
                payload = test_project(project, allow_external_command=args.run_command)
            elif args.command == "build":
                payload = build_project(project, allow_external_command=args.run_command)
            elif args.command == "package":
                payload = package_project(
                    project, resolve_user_path(args.archive), replace=args.replace
                )
            elif args.command == "release":
                payload = release_project(
                    project,
                    resolve_user_path(args.output_dir),
                    replace=args.replace,
                    allow_external_command=args.run_command,
                )
            elif args.command == "verify-package":
                payload = verify_archive(project, resolve_user_path(args.archive))
                emit(payload, output_json=args.output_json)
                return 1 if payload["errors"] else 0
            else:
                raise ControlError(f"unsupported command: {args.command}")
        emit(payload, output_json=args.output_json)
        if payload.get("status") == "fail" or payload.get("exitCode", 0) != 0:
            return 1
        return 0
    except (ControlError, OSError, UnicodeError, json.JSONDecodeError) as error:
        payload = {"status": "error", "error": str(error)}
        if getattr(args, "output_json", False):
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
