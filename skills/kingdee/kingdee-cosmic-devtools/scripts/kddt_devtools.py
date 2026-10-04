#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from kddt_common import (KddtError, detect_project, fail, load_json, normalize_url,
                         now_text, read_properties, read_text, save_json, update_properties, write_text)
from kddt_environment import cmd_update_env


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
