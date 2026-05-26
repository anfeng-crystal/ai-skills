#!/usr/bin/env python3
"""
Collect Cosmic metadata plugin bindings and source evidence for one entity.

The script reads project-level settings from ``ok-cosmic.json``. It never reads
the original market package config. Database credentials can come from the
current process environment, project-local dotenv files, or an existing
project JSON password field for legacy compatibility.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ZH_LOCALE = "zh_CN"
ENTITY_TABLE = "t_meta_entitydesign"
ENTITY_L_TABLE = "t_meta_entitydesign_l"
FORM_TABLE = "t_meta_formdesign"
FORM_L_TABLE = "t_meta_formdesign_l"

FORM_AP_NAMES = {
    "BillFormAp": "单据编辑页面",
    "BasedataFormAp": "基础资料页面",
    "FormAp": "列表页面",
    "TreeFormAp": "树形页面",
    "ReportFormAp": "报表页面",
    "MobBillFormAp": "移动单据页面",
    "MobFormAp": "移动列表页面",
    "MobileBillFormAp": "移动单据页面",
    "MobileListFormAp": "移动列表页面",
    "CardEntryViewAp": "卡片入口页面",
}

BUILTIN_EDIT_ORDER = ["save(暂存)", "submit(提交)", "audit(审核)", "unaudit(反审核)"]


Issue = Dict[str, str]


class ConfigError(RuntimeError):
    """Raised when metadata analyzer configuration cannot support the requested action."""


def add_issue(issues: List[Issue], level: str, key: str, message: str) -> None:
    """Append one structured validation issue."""
    issues.append({"level": level, "key": key, "message": message})


def load_json(path: Path) -> Dict[str, Any]:
    """Read a JSON object from disk and raise a concise configuration error."""
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        raise ConfigError(f"找不到配置文件: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"配置文件不是有效 JSON: {path}:{exc.lineno}:{exc.colno} {exc.msg}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"配置文件必须是 JSON 对象: {path}")
    return data


def resolve_path(base_dir: Path, raw_path: str) -> Path:
    """Resolve absolute or project-relative paths."""
    expanded = Path(os.path.expanduser(raw_path))
    if expanded.is_absolute():
        return expanded.resolve()
    return (base_dir / expanded).resolve()


def project_root(config: Dict[str, Any], config_path: Path) -> Path:
    """Resolve the project root used for relative analyzer paths."""
    project = config.get("project") if isinstance(config.get("project"), dict) else {}
    raw_root = str(project.get("root", "")).strip()
    return resolve_path(config_path.parent, raw_root) if raw_root else config_path.parent.resolve()


def analyzer_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return the metadataAnalyzer object or an empty object."""
    value = config.get("metadataAnalyzer")
    return value if isinstance(value, dict) else {}


def as_string_list(value: Any) -> List[str]:
    """Normalize a scalar or array config value to a list of non-blank strings."""
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = [str(item) for item in value]
    else:
        values = []
    return [item.strip() for item in values if item and item.strip()]


def dotenv_paths(config: Dict[str, Any], config_path: Path) -> List[Path]:
    """Return configured and conventional dotenv files used for DB credentials."""
    root_dir = project_root(config, config_path)
    metadata = analyzer_config(config)
    database = metadata.get("database") if isinstance(metadata.get("database"), dict) else {}
    candidates: List[Path] = []

    for raw_path in as_string_list(metadata.get("envFiles")) + as_string_list(database.get("envFiles")):
        candidates.append(resolve_path(root_dir, raw_path))

    candidates.extend([
        config_path.with_suffix(".env"),
        config_path.parent / ".env",
        root_dir / ".env",
    ])

    seen = set()
    ordered: List[Path] = []
    for path in candidates:
        resolved = path.expanduser().resolve()
        if resolved not in seen:
            seen.add(resolved)
            ordered.append(resolved)
    return ordered


def read_dotenv(path: Path) -> Dict[str, str]:
    """Read a small dotenv file without mutating the process environment."""
    values: Dict[str, str] = {}
    if not path.is_file():
        return values

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or any(char.isspace() for char in key):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key] = value
    return values


def dotenv_values(config: Dict[str, Any], config_path: Path) -> Dict[str, str]:
    """Merge dotenv values in lookup order; earlier files win."""
    merged: Dict[str, str] = {}
    for path in dotenv_paths(config, config_path):
        for key, value in read_dotenv(path).items():
            merged.setdefault(key, value)
    return merged


def resolve_database_password(config: Dict[str, Any], config_path: Path) -> Tuple[Optional[str], str]:
    """
    Resolve metadata DB password from environment, dotenv, or legacy JSON.

    The returned source label is safe to print because it never contains the
    password value.
    """
    metadata = analyzer_config(config)
    database = metadata.get("database") if isinstance(metadata.get("database"), dict) else {}
    password_env = str(database.get("passwordEnv", "")).strip()

    if password_env:
        process_value = os.getenv(password_env)
        if process_value:
            return process_value, f"env:{password_env}"
        dot_values = dotenv_values(config, config_path)
        dot_value = dot_values.get(password_env)
        if dot_value:
            return dot_value, f"dotenv:{password_env}"

    json_password = str(database.get("password", "")).strip()
    if json_password:
        return json_password, "json:metadataAnalyzer.database.password"

    checked = ["process env", "dotenv files", "metadataAnalyzer.database.password"]
    if password_env:
        checked.insert(0, f"passwordEnv:{password_env}")
    return None, ", ".join(checked)


def optional_positive_number(value: Any) -> bool:
    """Return true when value can be treated as a positive number."""
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def validate_config(config_path: Path, require_enabled: bool = False) -> Tuple[Dict[str, Any], List[Issue]]:
    """
    Validate project config and return the parsed JSON plus structured issues.

    ``require_enabled`` is used for real analysis; it turns missing runtime
    dependencies into blocking errors.
    """
    config = load_json(config_path)
    issues: List[Issue] = []
    root_dir = project_root(config, config_path)
    metadata = analyzer_config(config)

    if not metadata:
        add_issue(issues, "ERROR", "metadataAnalyzer", "缺少 `metadataAnalyzer` 配置节。")
        return config, issues

    enabled = bool(metadata.get("enabled", False))
    if require_enabled and not enabled:
        add_issue(issues, "ERROR", "metadataAnalyzer.enabled", "`metadataAnalyzer.enabled` 为 false，禁止连接元数据数据库。")

    database = metadata.get("database")
    if not isinstance(database, dict):
        add_issue(issues, "ERROR", "metadataAnalyzer.database", "`database` 必须是 JSON 对象。")
        database = {}

    password_env = str(database.get("passwordEnv", "")).strip()
    json_password = str(database.get("password", "")).strip()
    if json_password:
        add_issue(
            issues,
            "WARNING",
            "metadataAnalyzer.database.password",
            "检测到 JSON 明文密码；脚本会兼容读取，但新项目优先使用项目 `.env` 或临时环境变量。",
        )
    if not password_env and not json_password and require_enabled:
        add_issue(issues, "ERROR", "metadataAnalyzer.database.password", "启用分析时必须能从环境变量、`.env` 或既有 JSON 字段解析数据库密码。")
    elif require_enabled:
        password, source = resolve_database_password(config, config_path)
        if not password:
            add_issue(issues, "ERROR", "metadataAnalyzer.database.password", f"未找到数据库密码，已检查: {source}。")

    for key in ("host", "dbname", "user"):
        if require_enabled and not str(database.get(key, "")).strip():
            add_issue(issues, "ERROR", f"metadataAnalyzer.database.{key}", f"启用分析时必须配置 `{key}`。")

    if "connectTimeoutSeconds" in database and not optional_positive_number(database.get("connectTimeoutSeconds")):
        add_issue(issues, "ERROR", "metadataAnalyzer.database.connectTimeoutSeconds", "`connectTimeoutSeconds` 必须大于 0。")

    try:
        import psycopg2  # noqa: F401
    except ImportError:
        level = "ERROR" if require_enabled else "WARNING"
        add_issue(issues, level, "python.psycopg2", "缺少 Python 依赖 `psycopg2`，启用分析前需安装。")

    workspace = metadata.get("workspace") if isinstance(metadata.get("workspace"), dict) else {}
    workspace_root = str(workspace.get("projectRoot", "")).strip() or str(root_dir)
    resolved_workspace = resolve_path(root_dir, workspace_root)
    if not resolved_workspace.exists():
        add_issue(issues, "ERROR", "metadataAnalyzer.workspace.projectRoot", f"源码根目录不存在: {resolved_workspace}")

    jar_paths = metadata.get("jarLibPaths")
    if not isinstance(jar_paths, list) or not jar_paths:
        add_issue(issues, "ERROR", "metadataAnalyzer.jarLibPaths", "`jarLibPaths` 必须是非空数组。")
    else:
        for index, raw_path in enumerate(jar_paths):
            resolved = resolve_path(root_dir, str(raw_path))
            if not resolved.exists():
                add_issue(issues, "ERROR", f"metadataAnalyzer.jarLibPaths[{index}]", f"JAR 目录不存在: {resolved}")

    output = metadata.get("output") if isinstance(metadata.get("output"), dict) else {}
    report_dir = str(output.get("reportDir", "")).strip()
    if not report_dir:
        add_issue(issues, "ERROR", "metadataAnalyzer.output.reportDir", "缺少输出目录 `reportDir`。")

    decompiler = metadata.get("decompiler") if isinstance(metadata.get("decompiler"), dict) else {}
    if bool(decompiler.get("enabled", False)):
        cfr_path = str(decompiler.get("cfrJarPath", "")).strip()
        if not cfr_path:
            add_issue(issues, "ERROR", "metadataAnalyzer.decompiler.cfrJarPath", "启用反编译时必须配置 CFR JAR 路径。")
        else:
            resolved_cfr = resolve_path(root_dir, cfr_path)
            if not resolved_cfr.exists():
                add_issue(issues, "ERROR", "metadataAnalyzer.decompiler.cfrJarPath", f"CFR JAR 不存在: {resolved_cfr}")

    return config, issues


def has_errors(issues: List[Issue]) -> bool:
    """Return true when validation contains at least one blocking issue."""
    return any(issue.get("level") == "ERROR" for issue in issues)


def print_issues(issues: List[Issue]) -> None:
    """Print validation issues in a compact human-readable form."""
    if not issues:
        print("配置检查通过。")
        return
    for issue in issues:
        print(f"[{issue['level']}] {issue['key']}: {issue['message']}")


def parse_fdata(fdata_raw: Any) -> Tuple[str, Optional[ET.Element]]:
    """Parse Cosmic metadata fdata and return its format marker plus XML root."""
    if not fdata_raw:
        return "empty", None
    text = fdata_raw.strip() if isinstance(fdata_raw, str) else str(fdata_raw)
    if text.startswith("<"):
        try:
            return "xml", ET.fromstring(text)
        except ET.ParseError:
            return "error", None
    return "unknown", None


def is_real_plugin(class_name: str) -> bool:
    """Filter out blank or non-class plugin markers."""
    return bool(class_name) and "." in class_name and not class_name[0].isdigit()


def operation_label(op: ET.Element, edit_index: int) -> str:
    """Return a truthful operation label without guessing unnamed edit semantics."""
    key = op.findtext("Key", "").strip()
    name = op.findtext("Name", "").strip()
    action = op.get("action", "").strip()
    oid = op.get("oid", "").strip()

    if key:
        return f"{key}({name})" if name else key
    if action == "remove":
        return "delete(删除)"
    if action == "edit":
        suffix = f"[{oid}]" if oid else ""
        return f"edit#{edit_index}{suffix}"
    return action or "unknown"


def extract_op_plugins(root: Optional[ET.Element]) -> List[Dict[str, Any]]:
    """Extract operation plugin bindings from entity metadata XML."""
    results: List[Dict[str, Any]] = []
    if root is None:
        return results

    edit_counter = 0
    for op in root.iter("Operation"):
        key = op.findtext("Key", "").strip()
        action = op.get("action", "").strip()
        if action == "edit" and not key:
            edit_counter += 1
        op_label = operation_label(op, edit_counter)

        plugins_node = op.find("Plugins")
        if plugins_node is None:
            continue
        for plugin in plugins_node.findall("Plugin"):
            class_name = plugin.findtext("ClassName", "").strip() or plugin.get("oid", "").strip()
            if is_real_plugin(class_name):
                results.append({
                    "type": "操作插件",
                    "operation": op_label,
                    "className": class_name,
                    "enabled": plugin.findtext("Enabled", "").strip(),
                    "description": plugin.findtext("Description", "").strip(),
                })
    return results


def extract_form_plugins(root: Optional[ET.Element], form_number: str = "", form_name: str = "") -> List[Dict[str, Any]]:
    """Extract page plugin bindings from form metadata XML."""
    results: List[Dict[str, Any]] = []
    if root is None:
        return results

    parent_map = {child: parent for parent in root.iter() for child in parent}
    for plugins_node in root.iter("Plugins"):
        parent = parent_map.get(plugins_node)
        if parent is not None and parent.tag == "Operation":
            continue
        parent_tag = parent.tag if parent is not None else "unknown"
        parent_action = parent.get("action", "") if parent is not None else ""
        element_desc = FORM_AP_NAMES.get(parent_tag, parent_tag)
        if parent_action:
            element_desc += f"({parent_action})"

        for plugin in plugins_node.findall("Plugin"):
            class_name = plugin.findtext("ClassName", "").strip() or plugin.get("oid", "").strip()
            if is_real_plugin(class_name):
                results.append({
                    "type": "页面插件",
                    "formPage": f"{form_number}({form_name})" if form_name else form_number,
                    "pageElement": element_desc,
                    "className": class_name,
                    "enabled": plugin.findtext("Enabled", "").strip(),
                    "description": plugin.findtext("Description", "").strip(),
                })
    return results


def connect_metadata_db(config: Dict[str, Any], config_path: Path):
    """Create a PostgreSQL connection using the resolved metadata DB password."""
    try:
        import psycopg2
    except ImportError as exc:
        raise ConfigError("缺少 Python 依赖 `psycopg2`，无法连接元数据数据库。") from exc

    database = analyzer_config(config)["database"]
    password, source = resolve_database_password(config, config_path)
    if not password:
        raise ConfigError(f"未找到数据库密码，已检查: {source}。")

    return psycopg2.connect(
        host=database["host"],
        port=database.get("port", 5432),
        dbname=database["dbname"],
        user=database["user"],
        password=password,
        connect_timeout=database.get("connectTimeoutSeconds", 10),
        options=f"-c search_path={database.get('schema', 'public')}",
    )


def query_plugins(conn, entity_number: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Query entity metadata, form metadata, and all bound plugins."""
    cursor = conn.cursor()
    plugins: List[Dict[str, Any]] = []
    entity_info: Dict[str, Any] = {}

    cursor.execute(
        f"""
        SELECT e.fid, e.fnumber, e.fdata, l.fname
        FROM {ENTITY_TABLE} e
        LEFT JOIN {ENTITY_L_TABLE} l ON l.fid = e.fid AND l.flocaleid = %s
        WHERE e.fnumber = %s
        LIMIT 1
        """,
        (ZH_LOCALE, entity_number),
    )
    entities = cursor.fetchall()

    if not entities:
        cursor.execute(
            f"""
            SELECT e.fid, e.fnumber, e.fdata, l.fname
            FROM {ENTITY_TABLE} e
            LEFT JOIN {ENTITY_L_TABLE} l ON l.fid = e.fid AND l.flocaleid = %s
            WHERE e.fnumber ILIKE %s
            ORDER BY length(e.fnumber)
            LIMIT 5
            """,
            (ZH_LOCALE, f"%{entity_number}%"),
        )
        entities = cursor.fetchall()

    if not entities:
        cursor.close()
        return entity_info, plugins

    entity_fid, entity_fnumber, entity_fdata, entity_name = entities[0]
    entity_info = {
        "fnumber": entity_fnumber,
        "fname": entity_name or "",
        "fid": entity_fid,
    }

    data_format, entity_root = parse_fdata(entity_fdata)
    if data_format == "xml":
        plugins.extend(extract_op_plugins(entity_root))

    cursor.execute(
        f"""
        SELECT f.fid, f.fnumber, f.fdata, l.fname
        FROM {FORM_TABLE} f
        LEFT JOIN {FORM_L_TABLE} l ON l.fid = f.fid AND l.flocaleid = %s
        WHERE f.fentityid = %s OR f.fnumber ILIKE %s
        LIMIT 20
        """,
        (ZH_LOCALE, entity_fid, f"%{entity_fnumber}%"),
    )
    for _, form_number, form_data, form_name in cursor.fetchall():
        data_format, form_root = parse_fdata(form_data)
        if data_format == "xml":
            plugins.extend(extract_form_plugins(form_root, form_number, form_name or ""))

    cursor.close()
    return entity_info, plugins


def find_source_in_workspace(class_name: str, workspace_root: Path) -> Optional[Path]:
    """Find a Java source file by full class name or simple class name."""
    if not workspace_root.exists():
        return None

    simple_name = class_name.rsplit(".", 1)[-1]
    target_file = f"{simple_name}.java"
    if "." in class_name:
        package_path = class_name.rsplit(".", 1)[0].replace(".", os.sep)
        for src_root in workspace_root.rglob("src"):
            candidate = src_root / "main" / "java" / package_path / target_file
            if candidate.exists():
                return candidate

    for match in workspace_root.rglob(target_file):
        return match
    return None


def rank_jar_dirs(class_name: str, jar_paths: List[Path]) -> List[Tuple[Path, Optional[str]]]:
    """Order JAR directories by package prefix and optional JAR filename hint."""
    parts = class_name.split(".")
    module = parts[1] if len(parts) > 1 else None
    submodule = parts[2] if len(parts) > 2 else None

    by_name = {path.name.lower(): path for path in jar_paths}
    ordered: List[Tuple[Path, Optional[str]]] = []
    if module == "bos":
        if "bos" in by_name:
            ordered.append((by_name["bos"], None))
        ordered.extend((path, None) for name, path in by_name.items() if name != "bos")
    else:
        if "biz" in by_name:
            ordered.append((by_name["biz"], submodule))
        if "cus" in by_name:
            ordered.append((by_name["cus"], submodule))
        ordered.extend((path, None) for name, path in by_name.items() if name not in ("biz", "cus"))
    return ordered or [(path, submodule) for path in jar_paths]


def find_class_in_jars(class_name: str, jar_paths: List[Path]) -> Optional[Path]:
    """Find the first JAR containing the requested class."""
    class_file = class_name.replace(".", "/") + ".class"
    for jar_dir, hint in rank_jar_dirs(class_name, jar_paths):
        if not jar_dir.exists():
            continue

        candidates = list(jar_dir.rglob("*.jar"))
        if hint:
            hinted = [jar for jar in candidates if hint.lower() in jar.name.lower()]
            candidates = hinted + [jar for jar in candidates if jar not in hinted]

        for jar_file in candidates:
            try:
                with zipfile.ZipFile(jar_file, "r") as zf:
                    if class_file in zf.namelist():
                        return jar_file
            except (zipfile.BadZipFile, PermissionError):
                continue
    return None


def javap_fallback(class_name: str, jar_path: Path) -> Optional[str]:
    """Read public class signatures with javap when source is unavailable."""
    try:
        result = subprocess.run(
            ["javap", "-classpath", str(jar_path), "-public", class_name],
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
        )
    except Exception:
        return None
    return result.stdout if result.returncode == 0 and result.stdout.strip() else None


def decompile_from_jar(class_name: str, jar_path: Path, cfr_path: Path) -> Tuple[Optional[str], Optional[str]]:
    """Use CFR to decompile one class from a JAR when explicitly enabled."""
    if not cfr_path.exists():
        return None, f"CFR JAR 不存在: {cfr_path}"

    try:
        result = subprocess.run(
            ["java", "-jar", str(cfr_path), str(jar_path), "--methodname", "", "--outputdir", "-", class_name],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout, None
    except Exception:
        pass

    try:
        class_file = class_name.replace(".", "/") + ".class"
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(jar_path, "r") as zf:
                zf.extract(class_file, tmpdir)
            class_path = Path(tmpdir) / class_file
            result = subprocess.run(
                ["java", "-jar", str(cfr_path), str(class_path)],
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout, None
            return None, result.stderr[:500] if result.stderr else "反编译失败"
    except Exception as exc:
        return None, str(exc)


def resolved_metadata_paths(config: Dict[str, Any], config_path: Path) -> Tuple[Path, List[Path], Path, bool, Optional[Path]]:
    """Resolve workspace, JAR, output, and decompiler paths from config."""
    root_dir = project_root(config, config_path)
    metadata = analyzer_config(config)
    workspace = metadata.get("workspace") if isinstance(metadata.get("workspace"), dict) else {}
    output = metadata.get("output") if isinstance(metadata.get("output"), dict) else {}
    decompiler = metadata.get("decompiler") if isinstance(metadata.get("decompiler"), dict) else {}

    workspace_root = resolve_path(root_dir, str(workspace.get("projectRoot", "")).strip() or str(root_dir))
    jar_paths = [resolve_path(root_dir, str(path)) for path in metadata.get("jarLibPaths", [])]
    output_dir = resolve_path(root_dir, str(output.get("reportDir", "build/reports/cosmic-metadata-analyzer")))
    decompiler_enabled = bool(decompiler.get("enabled", False))
    cfr_path = resolve_path(root_dir, str(decompiler.get("cfrJarPath", ""))) if decompiler.get("cfrJarPath") else None
    return workspace_root, jar_paths, output_dir, decompiler_enabled, cfr_path


def resolve_source(class_name: str, workspace_root: Path, jar_paths: List[Path], decompiler_enabled: bool, cfr_path: Optional[Path]) -> Dict[str, Any]:
    """Resolve plugin source by workspace file, optional CFR, or javap signature."""
    source_file = find_source_in_workspace(class_name, workspace_root)
    if source_file:
        try:
            return {
                "source": "workspace",
                "path": str(source_file),
                "code": source_file.read_text(encoding="utf-8"),
                "extension": ".java",
                "error": None,
            }
        except Exception as exc:
            return {"source": "workspace", "path": str(source_file), "code": None, "extension": ".java", "error": str(exc)}

    jar_path = find_class_in_jars(class_name, jar_paths)
    if not jar_path:
        return {"source": "not_found", "path": None, "code": None, "extension": ".txt", "error": "源码和 JAR 均未找到"}

    if decompiler_enabled and cfr_path:
        code, error = decompile_from_jar(class_name, jar_path, cfr_path)
        if code:
            return {"source": "jar_decompiled", "path": str(jar_path), "code": code, "extension": ".java", "error": None}
        javap = javap_fallback(class_name, jar_path)
        return {"source": "jar_javap", "path": str(jar_path), "code": javap, "extension": ".txt", "error": error}

    javap = javap_fallback(class_name, jar_path)
    return {"source": "jar_javap", "path": str(jar_path), "code": javap, "extension": ".txt", "error": None if javap else "javap 未返回结果"}


def source_output_name(class_name: str, extension: str) -> str:
    """Create a collision-safe source evidence filename."""
    return class_name.replace(".", "__").replace("$", "_") + extension


def save_inventory(entity_info: Dict[str, Any], plugins_with_source: List[Dict[str, Any]], output_dir: Path) -> Tuple[Path, Path]:
    """Write inventory JSON and source evidence files for AI-side analysis."""
    entity_number = entity_info.get("fnumber", "unknown")
    base_dir = output_dir / entity_number
    sources_dir = base_dir / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    saved_sources: Dict[str, str] = {}
    inventory_items: List[Dict[str, Any]] = []
    for plugin_with_source in plugins_with_source:
        plugin = plugin_with_source["plugin"]
        resolved = plugin_with_source["resolved"]
        class_name = plugin["className"]
        simple_name = class_name.rsplit(".", 1)[-1]
        local_source_file = None

        if class_name not in saved_sources and resolved.get("code"):
            source_path = sources_dir / source_output_name(class_name, resolved.get("extension", ".txt"))
            source_path.write_text(resolved["code"], encoding="utf-8")
            saved_sources[class_name] = str(source_path)
            local_source_file = str(source_path)
        elif class_name in saved_sources:
            local_source_file = saved_sources[class_name]

        item = {
            "className": class_name,
            "simpleName": simple_name,
            "type": plugin["type"],
            "enabled": plugin.get("enabled", ""),
            "description": plugin.get("description", ""),
            "sourceType": resolved["source"],
            "originalPath": resolved.get("path", ""),
            "localSourceFile": local_source_file,
        }
        for optional_key in ("operation", "pageElement", "formPage"):
            if plugin.get(optional_key):
                item[optional_key] = plugin[optional_key]
        if resolved.get("error"):
            item["error"] = resolved["error"]
        inventory_items.append(item)

    inventory = {
        "entity": entity_info,
        "pluginCount": len(inventory_items),
        "uniqueClassCount": len(saved_sources),
        "plugins": inventory_items,
    }
    inventory_path = base_dir / "inventory.json"
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    return base_dir, inventory_path


def command_check_config(args: argparse.Namespace) -> int:
    """Validate configuration without connecting to the metadata database."""
    config_path = Path(args.config).expanduser().resolve()
    config, issues = validate_config(config_path, require_enabled=False)
    if args.json:
        print(json.dumps({"ok": not has_errors(issues), "configPath": str(config_path), "issues": issues}, ensure_ascii=False, indent=2))
    else:
        print_issues(issues)
    return 1 if has_errors(issues) else 0


def command_analyze(args: argparse.Namespace) -> int:
    """Collect plugin inventory and source evidence for one entity."""
    config_path = Path(args.config).expanduser().resolve()
    config, issues = validate_config(config_path, require_enabled=True)
    if has_errors(issues):
        print_issues(issues)
        return 1

    workspace_root, jar_paths, output_dir, decompiler_enabled, cfr_path = resolved_metadata_paths(config, config_path)
    if args.output:
        output_dir = resolve_path(project_root(config, config_path), args.output)

    try:
        conn = connect_metadata_db(config, config_path)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1

    try:
        entity_info, plugins = query_plugins(conn, args.entityNumber)
    finally:
        conn.close()

    if not entity_info:
        print(f"[ERROR] 未找到实体: {args.entityNumber}")
        return 1
    if not plugins:
        print(f"[INFO] 实体 {entity_info.get('fnumber')} 未找到绑定插件。")
        return 0

    plugins_with_source: List[Dict[str, Any]] = []
    resolved_by_class: Dict[str, Dict[str, Any]] = {}
    for plugin in plugins:
        class_name = plugin["className"]
        if class_name not in resolved_by_class:
            resolved_by_class[class_name] = resolve_source(class_name, workspace_root, jar_paths, decompiler_enabled, cfr_path)
        plugins_with_source.append({"plugin": plugin, "resolved": resolved_by_class[class_name]})

    base_dir, inventory_path = save_inventory(entity_info, plugins_with_source, output_dir)
    print(f"实体: {entity_info.get('fnumber')} ({entity_info.get('fname', '')})")
    print(f"插件总数: {len(plugins)}")
    print(f"去重类数: {len(resolved_by_class)}")
    print(f"输出目录: {base_dir}")
    print(f"__INVENTORY_PATH__={inventory_path}")
    print(f"__OUTPUT_DIR__={base_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Create CLI parser with explicit config-based commands."""
    parser = argparse.ArgumentParser(description="苍穹元数据绑定插件采集工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check-config", help="检查 ok-cosmic.json 中的 metadataAnalyzer 配置")
    check.add_argument("--config", required=True, help="项目 ok-cosmic.json 路径")
    check.add_argument("--json", action="store_true", help="输出 JSON 格式检查结果")
    check.set_defaults(func=command_check_config)

    analyze = subparsers.add_parser("analyze", help="采集指定实体的插件清单和源码证据")
    analyze.add_argument("entityNumber", help="苍穹实体标识")
    analyze.add_argument("--config", required=True, help="项目 ok-cosmic.json 路径")
    analyze.add_argument("--output", help="覆盖 metadataAnalyzer.output.reportDir")
    analyze.set_defaults(func=command_analyze)
    return parser


def normalize_argv(argv: List[str]) -> List[str]:
    """Support the short form: ``script.py <entityNumber> --config ok-cosmic.json``."""
    if argv and argv[0] not in ("check-config", "analyze", "-h", "--help"):
        return ["analyze"] + argv
    return argv


def main(argv: Optional[List[str]] = None) -> int:
    """Run the metadata analyzer command line interface."""
    parser = build_parser()
    args = parser.parse_args(normalize_argv(list(argv if argv is not None else sys.argv[1:])))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
