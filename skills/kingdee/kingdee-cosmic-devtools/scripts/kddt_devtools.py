#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


VERSION = "2.3.5-GA"
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ASSET_DIR = SKILL_DIR / "assets" / "kddt" / VERSION
PROJECT_TEMPLATE_DIR = ASSET_DIR / "templates" / "projects"
JAVA_TEMPLATE_DIR = ASSET_DIR / "templates" / "java"

DEV_FLAG_RE = re.compile(r"^[a-z][a-z0-9]{1,3}$")
CLOUD_FLAG_RE = re.compile(r"^[a-z][a-z0-9]{1,16}$")
APP_FLAG_RE = re.compile(r"^[a-z][a-z0-9]{1,21}$")
PROJECT_FLAG_RE = re.compile(r"^[a-z][a-z0-9]{4}$")
JAVA_CLASS_RE = re.compile(r"^[A-Z_$][A-Za-z0-9_$]*$")
JAVA_PACKAGE_RE = re.compile(r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*$")

FULL_TEMPLATES = {
    True: {"multi": "code-2.zip", "app": "code-app-2.zip", "cloud": "code-cloud-2.zip"},
    False: {"multi": "code.zip", "app": "code-app.zip", "cloud": "code-cloud.zip"},
}

SUB_TEMPLATES = {
    True: {"multi": "code-2-sub.zip", "app": "code-app-2-sub.zip", "cloud": "code-cloud-2-sub.zip"},
    False: {"multi": "code-sub.zip", "app": "code-app-sub.zip", "cloud": "code-cloud-sub.zip"},
}

PLUGIN_TEMPLATES = {
    "inherit": "CreateInheritPlugin.java.template",
    "extend": "CreateExtendPointPlugin.java.template",
    "service": "CreateService.java.template",
}

TEXT_SUFFIXES = {
    ".java",
    ".gradle",
    ".properties",
    ".json",
    ".md",
    ".xml",
    ".txt",
    ".conf",
    ".MF",
    ".gitignore",
}


class KddtError(RuntimeError):
    pass


@dataclass
class ProjectContext:
    target: Path
    project_name: str
    template_type: str
    developer_flag: str
    project_flag: str
    cloud_flag: str
    app_flag: str
    cosmic_home: str
    res_url: str
    mc_url: str
    zk_url: str
    version: str
    group_id: str

    @property
    def has_project_flag(self) -> bool:
        return bool(self.project_flag)


def fail(message: str) -> None:
    raise KddtError(message)


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def now_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(read_text(path))


def save_json(path: Path, data: dict[str, Any]) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def read_properties(path: Path) -> dict[str, str]:
    props: dict[str, str] = {}
    if not path.exists():
        return props
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        props[key.strip()] = value.strip()
    return props


def update_properties(path: Path, updates: dict[str, str], remove_empty: set[str] | None = None) -> None:
    remove_empty = remove_empty or set()
    seen: set[str] = set()
    lines: list[str] = []
    if path.exists():
        source_lines = read_text(path).splitlines()
    else:
        source_lines = []
    for raw in source_lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            lines.append(raw)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updates:
            value = updates[key]
            seen.add(key)
            if key in remove_empty and not value:
                continue
            lines.append(f"{key}={value}")
        else:
            lines.append(raw)
    for key, value in updates.items():
        if key in seen:
            continue
        if key in remove_empty and not value:
            continue
        lines.append(f"{key}={value}")
    write_text(path, "\n".join(lines).rstrip() + "\n")


def prompt_if_missing(value: str | None, label: str, interactive: bool, required: bool = True) -> str:
    if value not in (None, ""):
        return str(value)
    if not interactive:
        if required:
            fail(f"missing required argument: {label}; rerun with --{label.replace('_', '-')} or --interactive")
        return ""
    answer = input(f"{label}: ").strip()
    if required and not answer:
        fail(f"{label} is required")
    return answer


def validate_flag(name: str, value: str, pattern: re.Pattern[str], required: bool = True) -> None:
    if not value and not required:
        return
    if not pattern.fullmatch(value):
        fail(f"invalid {name}: {value}")


def validate_context(ctx: ProjectContext, require_target_parent: bool = True) -> None:
    if ctx.template_type not in FULL_TEMPLATES[True]:
        fail("template_type must be one of: app, cloud, multi")
    validate_flag("developer_flag", ctx.developer_flag, DEV_FLAG_RE)
    validate_flag("project_flag", ctx.project_flag, PROJECT_FLAG_RE, required=False)
    validate_flag("cloud_flag", ctx.cloud_flag, CLOUD_FLAG_RE)
    validate_flag("app_flag", ctx.app_flag, APP_FLAG_RE)
    if require_target_parent and not ctx.target.parent.exists():
        fail(f"target parent does not exist: {ctx.target.parent}")


def build_context(args: argparse.Namespace, defaults: dict[str, str] | None = None) -> ProjectContext:
    defaults = defaults or {}
    interactive = bool(getattr(args, "interactive", False))
    target_raw = prompt_if_missing(getattr(args, "target", None), "target", interactive)
    target = Path(target_raw).expanduser().resolve()
    project_name = getattr(args, "project_name", None) or defaults.get("project_name") or target.name
    template_type = prompt_if_missing(
        getattr(args, "template_type", None) or defaults.get("template_type") or "multi",
        "template_type",
        interactive,
    )
    developer_flag = prompt_if_missing(
        getattr(args, "developer_flag", None) or defaults.get("developer_flag"),
        "developer_flag",
        interactive,
    )
    project_flag = prompt_if_missing(
        getattr(args, "project_flag", None) if getattr(args, "project_flag", None) is not None else defaults.get("project_flag", ""),
        "project_flag",
        interactive,
        required=False,
    )
    cloud_flag = prompt_if_missing(
        getattr(args, "cloud_flag", None) or defaults.get("cloud_flag"),
        "cloud_flag",
        interactive,
    )
    app_flag = prompt_if_missing(
        getattr(args, "app_flag", None) or defaults.get("app_flag"),
        "app_flag",
        interactive,
    )
    cosmic_home = prompt_if_missing(
        getattr(args, "cosmic_home", None) or defaults.get("cosmic_home") or os.environ.get("COSMIC_HOME", ""),
        "cosmic_home",
        interactive,
        required=False,
    )
    res_url = prompt_if_missing(
        getattr(args, "res_url", None) or defaults.get("res_url", ""),
        "res_url",
        interactive,
        required=False,
    )
    mc_url = prompt_if_missing(
        getattr(args, "mc_url", None) or defaults.get("mc_url", ""),
        "mc_url",
        interactive,
        required=False,
    )
    zk_url = prompt_if_missing(
        getattr(args, "zk_url", None) or defaults.get("zk_url", "127.0.0.1:2181"),
        "zk_url",
        interactive,
        required=False,
    )
    version = getattr(args, "version", None) or defaults.get("version") or "1.0.0"
    group_id = getattr(args, "group_id", None) or defaults.get("group_id") or f"{developer_flag}.cosmic"
    ctx = ProjectContext(
        target=target,
        project_name=project_name,
        template_type=template_type,
        developer_flag=developer_flag,
        project_flag=project_flag,
        cloud_flag=cloud_flag,
        app_flag=app_flag,
        cosmic_home=cosmic_home,
        res_url=normalize_url(res_url) if res_url else "",
        mc_url=normalize_url(mc_url) if mc_url else "",
        zk_url=zk_url,
        version=version,
        group_id=group_id,
    )
    validate_context(ctx)
    return ctx


def detect_project(project: Path) -> dict[str, str]:
    root = project.expanduser().resolve()
    props = read_properties(root / "gradle.properties")
    cosmic_json = load_json(root / "cosmic.json")
    old_props = read_properties(root / "cosmic.properties")
    project_flag = cosmic_json.get("COSMIC_PROJECT_FLAG") or props.get("systemProp.project_flag", "")
    res_url = cosmic_json.get("COSMIC_RES_URL") or props.get("systemProp.res_url", "") or old_props.get("MCServerURL", "")
    return {
        "project_root": str(root),
        "project_name": root.name,
        "template_type": props.get("systemProp.template_type", "multi"),
        "developer_flag": cosmic_json.get("COSMIC_DEVELOPER_FLAG") or props.get("systemProp.developer_flag", ""),
        "project_flag": project_flag,
        "has_project_flag": "true" if bool(project_flag) else "false",
        "cloud_flag": props.get("systemProp.cloud_flag", ""),
        "app_flag": props.get("systemProp.app_flag", ""),
        "cosmic_home": props.get("systemProp.cosmic_home", "") or os.environ.get("COSMIC_HOME", ""),
        "res_url": res_url,
        "kddt_version": props.get("systemProp.kddt_version", ""),
        "is_gradle_project": "true" if (root / "settings.gradle").exists() else "false",
    }


def replacements(ctx: ProjectContext) -> dict[str, str]:
    mapping = {
        "devflg": ctx.developer_flag,
        "cloudflg": ctx.cloud_flag,
        "appflg": ctx.app_flag,
        "generate_date": now_text(),
        "defualt_static_res_path": str(Path(ctx.cosmic_home) / "static-file-service") if ctx.cosmic_home else "",
        "defualt_zk_url_value": ctx.zk_url,
        "defualt_mc_url_value": ctx.mc_url,
        "defualt_project_dir_value": str(ctx.target),
        "C:/Users/kingdee/kingdee/cosmic001": str(ctx.target),
        "D:/cosmic_home": ctx.cosmic_home,
    }
    if ctx.project_flag:
        mapping["projectflg"] = ctx.project_flag
    return mapping


def apply_replacements(text: str, mapping: dict[str, str]) -> str:
    for old, new in mapping.items():
        text = text.replace(old, new)
    return text


def transform_posix_path(name: str, mapping: dict[str, str]) -> Path:
    posix_path = PurePosixPath(name)
    if posix_path.is_absolute() or ".." in posix_path.parts:
        fail(f"unsafe zip entry: {name}")
    transformed = str(posix_path)
    for old, new in mapping.items():
        if new:
            transformed = transformed.replace(old, new)
    return Path(transformed)


def looks_text(path: Path, data: bytes) -> bool:
    if path.suffix in TEXT_SUFFIXES or path.name in {".gitignore", "gradlew", "gradlew.bat"}:
        return True
    if b"\x00" in data[:4096]:
        return False
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def extract_template(zip_path: Path, target: Path, mapping: dict[str, str], force: bool = False) -> list[Path]:
    if not zip_path.exists():
        fail(f"template not found: {zip_path}")
    written: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            rel = transform_posix_path(info.filename, mapping)
            dest = (target / rel).resolve()
            if not str(dest).startswith(str(target.resolve())):
                fail(f"unsafe output path: {dest}")
            if dest.exists() and not force:
                fail(f"target file already exists: {dest}")
            data = zf.read(info.filename)
            if looks_text(dest, data):
                data = apply_replacements(data.decode("utf-8"), mapping).encode("utf-8")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            mode = (info.external_attr >> 16) & 0o777
            if mode:
                dest.chmod(mode)
            written.append(dest)
    return written


def finalize_project_files(ctx: ProjectContext) -> None:
    props_path = ctx.target / "gradle.properties"
    updates = {
        "systemProp.kddt_version": VERSION,
        "systemProp.template_type": ctx.template_type,
        "systemProp.groupId": ctx.group_id,
        "systemProp.artifactId": ctx.project_name,
        "systemProp.version": ctx.version,
        "systemProp.jdk.version": "1.8",
        "systemProp.developer_flag": ctx.developer_flag,
        "systemProp.project_flag": ctx.project_flag,
        "systemProp.project_dir": str(ctx.target),
        "systemProp.cosmic_home": ctx.cosmic_home,
        "systemProp.res_url": ctx.res_url,
        "systemProp.zk_url": ctx.zk_url,
        "org.gradle.parallel": "true",
        "org.gradle.daemon": "true",
        "org.gradle.caching": "true",
    }
    update_properties(props_path, updates, remove_empty={"systemProp.project_flag", "systemProp.res_url", "systemProp.zk_url"})
    cosmic_data = {
        "COSMIC_DEVELOPER_FLAG": ctx.developer_flag,
    }
    if ctx.project_flag:
        cosmic_data["COSMIC_PROJECT_FLAG"] = ctx.project_flag
    if ctx.res_url:
        cosmic_data["COSMIC_RES_URL"] = ctx.res_url
    save_json(ctx.target / "cosmic.json", cosmic_data)


def cmd_create_project(args: argparse.Namespace) -> None:
    ctx = build_context(args)
    if ctx.target.exists() and any(ctx.target.iterdir()) and not args.force:
        fail(f"target directory is not empty: {ctx.target}")
    ctx.target.mkdir(parents=True, exist_ok=True)
    template = FULL_TEMPLATES[ctx.has_project_flag][ctx.template_type]
    extract_template(PROJECT_TEMPLATE_DIR / template, ctx.target, replacements(ctx), force=args.force)
    finalize_project_files(ctx)
    print(json.dumps({"ok": True, "target": str(ctx.target), "template": template, "project_flag": ctx.project_flag}, ensure_ascii=False, indent=2))


def module_name_from_build_file(root: Path, build_file: Path) -> tuple[str, str]:
    module_dir = build_file.parent
    module_name = module_dir.name
    rel = module_dir.relative_to(root).as_posix()
    return module_name, rel


def append_settings(root: Path, modules: list[tuple[str, str]]) -> None:
    settings = root / "settings.gradle"
    if not settings.exists():
        fail(f"settings.gradle not found: {settings}")
    text = read_text(settings)
    additions: list[str] = []
    for module_name, rel in modules:
        if f"project(':{module_name}')" in text or f'project(":{module_name}")' in text:
            continue
        if f"':{module_name}'" not in text and f'":{module_name}"' not in text:
            additions.append(f"include ':{module_name}'")
        additions.append(f"project(':{module_name}').projectDir = new File('{rel}')")
    if additions:
        write_text(settings, text.rstrip() + "\n\n" + "\n".join(additions) + "\n")


def append_debug_dependencies(root: Path, developer_flag: str, modules: list[tuple[str, str]]) -> list[str]:
    candidates = [
        root / "code" / f"{developer_flag}-cosmic-debug" / "build.gradle",
        root / f"{developer_flag}-cosmic-debug" / "build.gradle",
    ]
    changed: list[str] = []
    for build_file in candidates:
        if not build_file.exists():
            continue
        text = read_text(build_file)
        dep_lines = [f"\timplementation project(':{name}')" for name, _ in modules if f"project(':{name}')" not in text]
        if not dep_lines:
            continue
        if re.search(r"(?m)^dependencies\s*\{", text):
            text = re.sub(r"(?m)^dependencies\s*\{", "dependencies {\n" + "\n".join(dep_lines), text, count=1)
        else:
            text = text.rstrip() + "\n\ndependencies {\n" + "\n".join(dep_lines) + "\n}\n"
        write_text(build_file, text)
        changed.append(str(build_file))
    return changed


def cmd_add_module(args: argparse.Namespace) -> None:
    project = Path(args.project).expanduser().resolve()
    defaults = detect_project(project)
    if defaults["is_gradle_project"] != "true":
        fail(f"not a Gradle Cosmic project root: {project}")
    args.target = str(project)
    ctx = build_context(args, defaults=defaults)
    ctx.target = project
    has_project_flag = bool(defaults.get("project_flag"))
    template = SUB_TEMPLATES[has_project_flag][ctx.template_type]
    before = set(project.rglob("build.gradle"))
    written = extract_template(PROJECT_TEMPLATE_DIR / template, project, replacements(ctx), force=args.force)
    after = set(project.rglob("build.gradle"))
    module_builds = sorted(after - before)
    if not module_builds:
        module_builds = sorted({p for p in written if p.name == "build.gradle"})
    modules = [module_name_from_build_file(project, p) for p in module_builds]
    append_settings(project, modules)
    debug_updates = append_debug_dependencies(project, ctx.developer_flag, modules)
    print(json.dumps({"ok": True, "project": str(project), "template": template, "modules": modules, "debug_updates": debug_updates}, ensure_ascii=False, indent=2))


def cmd_create_plugin(args: argparse.Namespace) -> None:
    kind = args.kind
    template_path = JAVA_TEMPLATE_DIR / PLUGIN_TEMPLATES[kind]
    package_name = prompt_if_missing(args.package, "package", args.interactive)
    class_name = prompt_if_missing(args.class_name, "class_name", args.interactive)
    validate_flag("package", package_name, JAVA_PACKAGE_RE)
    validate_flag("class_name", class_name, JAVA_CLASS_RE)
    parent_full_name = args.parent_full_name or ""
    if kind == "inherit":
        parent_full_name = prompt_if_missing(parent_full_name, "parent_full_name", args.interactive)
        if "." not in parent_full_name:
            fail("parent_full_name must be fully qualified")
    parent_simple_name = parent_full_name.rsplit(".", 1)[-1] if parent_full_name else ""
    desc = args.desc or ""
    out_dir = Path(prompt_if_missing(args.output_dir, "output_dir", args.interactive)).expanduser().resolve()
    dest = out_dir / Path(package_name.replace(".", "/")) / f"{class_name}.java"
    if dest.exists() and not args.force:
        fail(f"target file already exists: {dest}")
    text = read_text(template_path)
    text = text.replace("${PACKAGE_NAME}", package_name)
    text = text.replace("${CLASS_NAME}", class_name)
    text = text.replace("${PARENT_FULL_NAME}", parent_full_name)
    text = text.replace("${PARENT_SIMPLE_NAME}", parent_simple_name)
    text = text.replace("${DESC}", desc)
    write_text(dest, text)
    print(json.dumps({"ok": True, "kind": kind, "file": str(dest)}, ensure_ascii=False, indent=2))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def http_get(url: str, timeout: int = 20) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "kingdee-cosmic-devtools/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def url_join(base: str, *parts: str) -> str:
    cleaned = [base.rstrip("/")]
    cleaned.extend(part.strip("/") for part in parts if part)
    return "/".join(cleaned)


def job_root(cosmic_home: Path) -> Path:
    return cosmic_home / ".kddt-staging"


def job_path(cosmic_home: Path, job_id: str) -> Path:
    return job_root(cosmic_home) / job_id / "job.json"


def load_job(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"job not found: {path}")
    return load_json(path)


def save_job(job: dict[str, Any]) -> None:
    job["updated_at"] = now_text()
    save_json(Path(job["job_file"]), job)


def latest_job_file(cosmic_home: Path) -> Path:
    root = job_root(cosmic_home)
    candidates = sorted(root.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        fail(f"no jobs found under {root}")
    return candidates[0]


def resolve_cosmic_home(args: argparse.Namespace, project: Path | None = None) -> Path:
    value = args.cosmic_home or ""
    if not value and project:
        value = detect_project(project).get("cosmic_home", "")
    if not value:
        value = os.environ.get("COSMIC_HOME", "")
    if not value:
        fail("COSMIC_HOME is required; pass --cosmic-home or configure project gradle.properties")
    return Path(value).expanduser().resolve()


def resolve_res_url(args: argparse.Namespace, project: Path | None = None) -> str:
    value = args.res_url or ""
    if not value and project:
        value = detect_project(project).get("res_url", "")
    if not value:
        fail("resource URL is required; pass --res-url or configure cosmic.json")
    return normalize_url(value)


def parse_update_json(base_url: str, data: bytes) -> list[dict[str, Any]]:
    payload = json.loads(data.decode("utf-8"))
    items: list[dict[str, Any]] = []
    webapp = payload.get("webapp") or {}
    web_path = webapp.get("path") or ""
    for name, md5 in (webapp.get("files") or {}).items():
        items.append({"name": name, "type": "web", "target": "static", "md5": md5, "url": url_join(base_url, web_path, name)})
    appstore = payload.get("appstore") or {}
    app_path = appstore.get("path") or ""
    for lib_type in ("biz", "bos", "trd", "cus"):
        for name, md5 in (appstore.get(lib_type) or {}).items():
            items.append({"name": name, "type": lib_type, "target": f"lib/{lib_type}", "md5": md5, "url": url_join(base_url, app_path, lib_type, name)})
    if not items:
        fail("update.json contains no downloadable zip items")
    return items


def parse_update_md5(base_url: str) -> list[dict[str, Any]]:
    mc_style = "appstore" in base_url
    if mc_style:
        packages = [("cosmic.zip", "legacy-libs"), ("webapp.zip", "legacy-static")]
    else:
        packages = [("apppackage-cosmic.zip", "legacy-libs"), ("static-file-service.zip", "legacy-static")]
    return [{"name": name, "type": "package", "target": target, "md5": "", "url": url_join(base_url, name)} for name, target in packages]


def prepare_manifest(job: dict[str, Any]) -> None:
    base_url = normalize_url(job["res_url"])
    try:
        data = http_get(url_join(base_url, "update.json"))
        job["manifest_type"] = "update.json"
        job["items"] = parse_update_json(base_url, data)
    except Exception as json_error:
        try:
            job["remote_update_md5"] = http_get(url_join(base_url, "update.md5")).decode("utf-8", errors="replace").strip()
        except Exception:
            job["remote_update_md5"] = ""
        job["manifest_type"] = "update.md5"
        job["manifest_warning"] = str(json_error)
        job["items"] = parse_update_md5(base_url)


def download_with_resume(url: str, dest: Path, expected_md5: str = "", timeout: int = 60) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and (not expected_md5 or md5_file(dest).lower() == expected_md5.lower()):
        return
    part = dest.with_name(dest.name + ".part")
    existing = part.stat().st_size if part.exists() else 0
    headers = {"User-Agent": "kingdee-cosmic-devtools/0.1"}
    if existing:
        headers["Range"] = f"bytes={existing}-"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.getcode()
            mode = "ab" if existing and status == 206 else "wb"
            with part.open(mode) as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
    except urllib.error.HTTPError as exc:
        if exc.code == 416 and part.exists():
            part.replace(dest)
        else:
            raise
    if part.exists():
        part.replace(dest)
    if expected_md5 and md5_file(dest).lower() != expected_md5.lower():
        dest.unlink(missing_ok=True)
        fail(f"md5 mismatch after download: {dest.name}")


def worker_run(job_file: Path) -> None:
    job = load_job(job_file)
    try:
        job["status"] = "running"
        job["phase"] = "manifest"
        save_job(job)
        if not job.get("items"):
            prepare_manifest(job)
            save_job(job)
        cache = Path(job["cosmic_home"]) / ".kddt-cache"
        stage_downloads = Path(job["job_dir"]) / "downloads"
        for item in job["items"]:
            if job.get("cancel_requested"):
                job["status"] = "canceled"
                job["phase"] = "canceled"
                save_job(job)
                return
            item["status"] = "downloading"
            job["phase"] = f"download:{item['name']}"
            save_job(job)
            cache_name = hashlib.sha256(item["url"].encode("utf-8")).hexdigest()[:16] + "-" + item["name"]
            cache_file = cache / cache_name
            download_with_resume(item["url"], cache_file, item.get("md5", ""))
            staged_file = stage_downloads / item["type"] / item["name"]
            staged_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cache_file, staged_file)
            item["cache_path"] = str(cache_file)
            item["staged_path"] = str(staged_file)
            item["sha256"] = sha256_file(staged_file)
            item["status"] = "downloaded"
            save_job(job)
        job["status"] = "completed"
        job["phase"] = "ready_to_apply"
        save_job(job)
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        save_job(job)
        raise


def ensure_safe_zip(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            posix_path = PurePosixPath(info.filename)
            if posix_path.is_absolute() or ".." in posix_path.parts:
                fail(f"unsafe zip entry in {zip_path}: {info.filename}")


def unzip_to(zip_path: Path, target: Path) -> None:
    ensure_safe_zip(zip_path)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(target)


def target_for_item(cosmic_home: Path, item: dict[str, Any]) -> Path:
    target = item["target"]
    if target == "static" or target == "legacy-static":
        return cosmic_home / "static-file-service"
    if target.startswith("lib/"):
        return cosmic_home / "mservice-cosmic" / "lib" / target.split("/", 1)[1]
    return cosmic_home


def backup_targets(cosmic_home: Path, items: list[dict[str, Any]]) -> Path:
    backup_dir = cosmic_home / ".kddt-backups" / now_id()
    manifest: dict[str, Any] = {"created_at": now_text(), "components": []}
    seen: set[Path] = set()
    for item in items:
        target = target_for_item(cosmic_home, item).resolve()
        if target in seen:
            continue
        seen.add(target)
        rel = target.relative_to(cosmic_home).as_posix() if str(target).startswith(str(cosmic_home)) else target.name
        backup_path = backup_dir / "files" / rel
        manifest["components"].append({"target": str(target), "backup": str(backup_path), "existed": target.exists()})
        if target.exists():
            if target.is_dir():
                shutil.copytree(target, backup_path)
            else:
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup_path)
    save_json(backup_dir / "backup.json", manifest)
    return backup_dir


def apply_job(job_file: Path) -> None:
    job = load_job(job_file)
    if job.get("status") not in {"completed", "applied"}:
        fail(f"job is not ready to apply: {job.get('status')}")
    cosmic_home = Path(job["cosmic_home"]).resolve()
    backup_dir = backup_targets(cosmic_home, job["items"])
    for item in job["items"]:
        zip_path = Path(item["staged_path"])
        target = target_for_item(cosmic_home, item)
        unzip_to(zip_path, target)
    normalize_legacy_dirs(cosmic_home)
    job["status"] = "applied"
    job["phase"] = "applied"
    job["backup_dir"] = str(backup_dir)
    save_job(job)
    print(json.dumps({"ok": True, "job_id": job["job_id"], "backup_dir": str(backup_dir)}, ensure_ascii=False, indent=2))


def normalize_legacy_dirs(cosmic_home: Path) -> None:
    old_lib = cosmic_home / "cosmic" / "apppackage-cosmic"
    new_lib = cosmic_home / "mservice-cosmic" / "lib"
    if old_lib.exists() and not new_lib.exists():
        new_lib.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_lib), str(new_lib))
    old_static = cosmic_home / "webapp" / "static-file-service"
    new_static = cosmic_home / "static-file-service"
    if old_static.exists() and not new_static.exists():
        shutil.move(str(old_static), str(new_static))


def rollback_backup(backup_dir: Path) -> None:
    manifest = load_json(backup_dir / "backup.json")
    for component in manifest.get("components", []):
        target = Path(component["target"])
        backup = Path(component["backup"])
        if target.exists():
            replaced = target.with_name(target.name + f".rollback-replaced-{now_id()}")
            shutil.move(str(target), str(replaced))
        if component.get("existed"):
            if backup.is_dir():
                shutil.copytree(backup, target)
            elif backup.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, target)
    print(json.dumps({"ok": True, "backup_dir": str(backup_dir)}, ensure_ascii=False, indent=2))


def create_job(args: argparse.Namespace) -> dict[str, Any]:
    project = Path(args.project).expanduser().resolve() if args.project else None
    cosmic_home = resolve_cosmic_home(args, project)
    res_url = resolve_res_url(args, project)
    job_id = now_id()
    jdir = job_root(cosmic_home) / job_id
    jdir.mkdir(parents=True, exist_ok=True)
    job = {
        "job_id": job_id,
        "status": "pending",
        "phase": "created",
        "created_at": now_text(),
        "updated_at": now_text(),
        "project": str(project) if project else "",
        "cosmic_home": str(cosmic_home),
        "res_url": res_url,
        "job_dir": str(jdir),
        "job_file": str(jdir / "job.json"),
        "items": [],
    }
    save_job(job)
    return job


def spawn_worker(job: dict[str, Any]) -> None:
    log_path = Path(job["job_dir"]) / "worker.log"
    with log_path.open("ab") as log:
        subprocess.Popen([sys.executable, __file__, "update-env", "_worker", "--job-file", job["job_file"]], stdout=log, stderr=log)
    job["worker_log"] = str(log_path)
    save_job(job)


def cmd_update_env(args: argparse.Namespace) -> None:
    action = args.env_action
    if action == "start":
        job = create_job(args)
        if args.foreground:
            worker_run(Path(job["job_file"]))
            job = load_job(Path(job["job_file"]))
        else:
            spawn_worker(job)
        print(json.dumps({"ok": True, "job_id": job["job_id"], "job_file": job["job_file"], "status": job["status"]}, ensure_ascii=False, indent=2))
        return
    if action == "_worker":
        worker_run(Path(args.job_file))
        return
    cosmic_home = resolve_cosmic_home(args, Path(args.project).expanduser().resolve() if args.project else None)
    jf = Path(args.job_file) if args.job_file else (job_path(cosmic_home, args.job_id) if args.job_id else latest_job_file(cosmic_home))
    if action == "status":
        print(json.dumps(load_job(jf), ensure_ascii=False, indent=2))
    elif action == "resume":
        job = load_job(jf)
        job["cancel_requested"] = False
        job["status"] = "pending"
        save_job(job)
        if args.foreground:
            worker_run(jf)
        else:
            spawn_worker(job)
        print(json.dumps({"ok": True, "job_id": job["job_id"], "job_file": str(jf)}, ensure_ascii=False, indent=2))
    elif action == "cancel":
        job = load_job(jf)
        job["cancel_requested"] = True
        save_job(job)
        print(json.dumps({"ok": True, "job_id": job["job_id"], "status": "cancel_requested"}, ensure_ascii=False, indent=2))
    elif action == "apply":
        apply_job(jf)
    elif action == "rollback":
        if args.backup:
            rollback_backup(Path(args.backup).expanduser().resolve())
        else:
            job = load_job(jf)
            backup = job.get("backup_dir")
            if not backup:
                fail("no backup_dir on job; pass --backup")
            rollback_backup(Path(backup))
    else:
        fail(f"unknown update-env action: {action}")


def cmd_inspect(args: argparse.Namespace) -> None:
    project = Path(args.project).expanduser().resolve()
    info = detect_project(project)
    cosmic_home = Path(info["cosmic_home"]).expanduser() if info.get("cosmic_home") else None
    if cosmic_home:
        info["has_libs"] = "true" if (cosmic_home / "mservice-cosmic" / "lib").exists() else "false"
        info["has_static"] = "true" if (cosmic_home / "static-file-service").exists() else "false"
    print(json.dumps(info, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kddt_devtools.py")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-project")
    add_common_project_args(create)
    create.add_argument("--force", action="store_true")
    create.set_defaults(func=cmd_create_project)

    add = sub.add_parser("add-module")
    add.add_argument("--project", required=True)
    add_common_project_args(add, include_target=False)
    add.add_argument("--force", action="store_true")
    add.set_defaults(func=cmd_add_module)

    plugin = sub.add_parser("create-plugin")
    plugin.add_argument("--kind", choices=sorted(PLUGIN_TEMPLATES), required=True)
    plugin.add_argument("--package")
    plugin.add_argument("--class-name")
    plugin.add_argument("--output-dir")
    plugin.add_argument("--parent-full-name")
    plugin.add_argument("--desc")
    plugin.add_argument("--interactive", action="store_true")
    plugin.add_argument("--force", action="store_true")
    plugin.set_defaults(func=cmd_create_plugin)

    update = sub.add_parser("update-env")
    update.add_argument("env_action", choices=["start", "status", "resume", "cancel", "apply", "rollback", "_worker"])
    update.add_argument("--project")
    update.add_argument("--cosmic-home")
    update.add_argument("--res-url")
    update.add_argument("--job-id")
    update.add_argument("--job-file")
    update.add_argument("--backup")
    update.add_argument("--foreground", action="store_true")
    update.set_defaults(func=cmd_update_env)

    inspect = sub.add_parser("inspect")
    inspect.add_argument("--project", required=True)
    inspect.set_defaults(func=cmd_inspect)
    return parser


def add_common_project_args(parser: argparse.ArgumentParser, include_target: bool = True) -> None:
    if include_target:
        parser.add_argument("--target")
    parser.add_argument("--project-name")
    parser.add_argument("--template-type", choices=["app", "cloud", "multi"])
    parser.add_argument("--developer-flag")
    parser.add_argument("--project-flag")
    parser.add_argument("--cloud-flag")
    parser.add_argument("--app-flag")
    parser.add_argument("--cosmic-home")
    parser.add_argument("--res-url")
    parser.add_argument("--mc-url")
    parser.add_argument("--zk-url")
    parser.add_argument("--version")
    parser.add_argument("--group-id")
    parser.add_argument("--interactive", action="store_true")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except KddtError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
