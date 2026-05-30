"""
苍穹元数据插件分析脚本

功能：给定实体标识，自动遍历实体元数据和页面元数据，提取所有绑定的插件，
     查找插件源码（优先工作区源文件，其次从 JAR 反编译），输出结构化分析报告。

用法：
  python analyze_plugins.py <entityNumber>              # 分析指定实体的所有插件
  python analyze_plugins.py <entityNumber> --output DIR  # 指定报告输出目录
  python analyze_plugins.py <entityNumber> --allow-git-output  # 显式允许写入 Git 工作树

输出：
  - 控制台摘要
  - inventory.json + sources/*，默认位于本机缓存目录

依赖：pip install psycopg2-binary
"""

import os
import sys
import json
import hashlib
import re
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

# ── 常量 ─────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
CONFIG_FILE = SKILL_DIR / "config.json"
OUTPUT_DIR_ENV = "KINGDEE_METADATA_ANALYZER_OUTPUT_DIR"
ALLOW_GIT_OUTPUT_ENV = "KINGDEE_METADATA_ANALYZER_ALLOW_GIT_OUTPUT"

ZH_LOCALE = "zh_CN"
ENTITY_TABLE = "t_meta_entitydesign"
ENTITY_L_TABLE = "t_meta_entitydesign_l"
FORM_TABLE = "t_meta_formdesign"
FORM_L_TABLE = "t_meta_formdesign_l"

FORM_AP_NAMES = {
    "BillFormAp": "单据编辑页面",
    "FormAp": "列表页面",
    "TreeFormAp": "树形页面",
    "ReportFormAp": "报表页面",
    "MobBillFormAp": "移动单据页面",
    "MobFormAp": "移动列表页面",
}

BUILTIN_EDIT_ORDER = ["save(暂存)", "submit(提交)", "audit(审核)", "unaudit(反审核)"]


# ── 配置加载 ─────────────────────────────────────────────────────────────
def load_config():
    if not CONFIG_FILE.exists():
        print(f"[ERROR] 配置文件不存在: {CONFIG_FILE}")
        sys.exit(1)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _truthy_env(name):
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_path_segment(value, fallback):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip()).strip("._-")
    return cleaned[:80] if cleaned else fallback


def _path_from(base_dir, raw_path):
    expanded = Path(os.path.expanduser(str(raw_path)))
    if expanded.is_absolute():
        return expanded.resolve()
    return (base_dir / expanded).resolve()


def _containing_git_root(path):
    resolved = path.expanduser().resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _project_cache_label(cfg):
    workspace_root = str(cfg.get("workspace", {}).get("projectRoot", "")).strip()
    if workspace_root:
        root_path = Path(os.path.expanduser(workspace_root))
        label = root_path.name
        digest_source = str(root_path)
    else:
        label = SKILL_DIR.name
        digest_source = str(SKILL_DIR)
    digest = hashlib.sha1(digest_source.encode("utf-8")).hexdigest()[:8]
    return f"{_safe_path_segment(label, 'project')}-{digest}"


def _default_output_root(cfg, honor_env=True):
    configured_root = os.getenv(OUTPUT_DIR_ENV, "").strip() if honor_env else ""
    base_root = Path(os.path.expanduser(configured_root)) if configured_root else Path(tempfile.gettempdir()) / "kingdee-metadata-analyzer"
    if not base_root.is_absolute():
        base_root = Path.cwd() / base_root
    return (base_root / _project_cache_label(cfg) / "legacy-config").resolve()


def _resolve_output_dir(cfg, output_override, allow_git_output):
    configured_report_dir = str(cfg.get("output", {}).get("reportDir", "")).strip()
    warnings = []

    if output_override:
        candidate = _path_from(SKILL_DIR, output_override)
        source_label = "--output"
    elif os.getenv(OUTPUT_DIR_ENV, "").strip():
        candidate = _default_output_root(cfg)
        source_label = OUTPUT_DIR_ENV
    elif configured_report_dir and Path(os.path.expanduser(configured_report_dir)).is_absolute():
        candidate = _path_from(SKILL_DIR, configured_report_dir)
        source_label = "output.reportDir"
    elif configured_report_dir and allow_git_output:
        candidate = _path_from(SKILL_DIR, configured_report_dir)
        source_label = "output.reportDir"
    else:
        candidate = _default_output_root(cfg)
        source_label = "local-cache"
        if configured_report_dir:
            warnings.append(f"output.reportDir 是相对路径 `{configured_report_dir}`，已改用本机缓存目录，避免写入 Git 工作树。")

    git_root = _containing_git_root(candidate)
    if git_root and not allow_git_output:
        fallback = _default_output_root(cfg, honor_env=False)
        warnings.append(
            f"{source_label} 指向 Git 工作树 `{git_root}`，已重定向到 `{fallback}`；如确需写入仓库，请使用 --allow-git-output 或设置 {ALLOW_GIT_OUTPUT_ENV}=1。"
        )
        return str(fallback), warnings
    return str(candidate), warnings


def get_conn(cfg):
    try:
        import psycopg2
    except ImportError:
        print("[ERROR] 缺少依赖，请执行：pip install psycopg2-binary")
        sys.exit(1)
    db = cfg["database"]
    if not db.get("enabled", False):
        print("[ERROR] 数据库未启用，请在 config.json 中设置 database.enabled=true")
        sys.exit(1)
    return psycopg2.connect(
        host=db["host"], port=db.get("port", 5432),
        dbname=db["dbname"], user=db["user"], password=db["password"],
        connect_timeout=db.get("connect_timeout", 10),
        options=f"-c search_path={db.get('schema', 'public')}"
    )


# ── XML 解析 ─────────────────────────────────────────────────────────────
def _parse_fdata(fdata_raw):
    if not fdata_raw:
        return None, None
    text = fdata_raw.strip() if isinstance(fdata_raw, str) else str(fdata_raw)
    if text.startswith("<"):
        try:
            return "xml", ET.fromstring(text)
        except ET.ParseError:
            return "error", None
    return "unknown", None


def _is_real_plugin(cls):
    if not cls:
        return False
    return '.' in cls and not cls[0].isdigit()


# ── 提取操作插件 ─────────────────────────────────────────────────────────
def extract_op_plugins(root):
    """从实体 XML 提取操作插件 → [(op_label, class_name, enabled, desc)]"""
    results = []
    if root is None:
        return results
    edit_counter = 0
    for op in root.iter('Operation'):
        key = op.findtext('Key', '').strip()
        name = op.findtext('Name', '').strip()
        action = op.get('action', '').strip()
        if key:
            op_label = f"{key}({name})" if name else key
        elif action == 'edit':
            op_label = BUILTIN_EDIT_ORDER[edit_counter] if edit_counter < len(BUILTIN_EDIT_ORDER) else f"标准操作#{edit_counter}"
            edit_counter += 1
        elif action == 'remove':
            op_label = "delete(删除)"
        else:
            op_label = action or "unknown"
        plugins_node = op.find('Plugins')
        if plugins_node is None:
            continue
        for p in plugins_node.findall('Plugin'):
            cls = p.findtext('ClassName', '').strip()
            if not cls:
                cls = p.get('oid', '').strip()
            enabled = p.findtext('Enabled', '').strip()
            desc = p.findtext('Description', '').strip()
            if _is_real_plugin(cls):
                results.append({
                    "type": "操作插件",
                    "operation": op_label,
                    "className": cls,
                    "enabled": enabled,
                    "description": desc,
                })
    return results


# ── 提取页面插件 ─────────────────────────────────────────────────────────
def extract_form_plugins(root, form_fnumber="", form_fname=""):
    """从页面 XML 提取表单/列表插件 → [dict]"""
    results = []
    if root is None:
        return results
    parent_map = {c: p for p in root.iter() for c in p}
    for plugins_node in root.iter('Plugins'):
        parent = parent_map.get(plugins_node)
        parent_tag = parent.tag if parent is not None else "unknown"
        parent_action = parent.get('action', '') if parent is not None else ""
        # 排除 Operation 下的 Plugins（那些归操作插件）
        if parent is not None and parent.tag == 'Operation':
            continue
        for p in plugins_node.findall('Plugin'):
            cls = p.findtext('ClassName', '').strip()
            enabled = p.findtext('Enabled', '').strip()
            desc = p.findtext('Description', '').strip()
            if _is_real_plugin(cls):
                elem_desc = FORM_AP_NAMES.get(parent_tag, parent_tag)
                if parent_action:
                    elem_desc += f"({parent_action})"
                results.append({
                    "type": "页面插件",
                    "formPage": f"{form_fnumber}({form_fname})" if form_fname else form_fnumber,
                    "pageElement": elem_desc,
                    "className": cls,
                    "enabled": enabled,
                    "description": desc,
                })
    return results
# ── 源码查找 ─────────────────────────────────────────────────────────────
def find_source_in_workspace(class_name, workspace_root):
    """在工作区中搜索 .java 源文件"""
    if not workspace_root or not Path(workspace_root).exists():
        return None
    simple_name = class_name.rsplit('.', 1)[-1]
    target_file = f"{simple_name}.java"
    # 精确匹配：按包路径搜索
    if '.' in class_name:
        package_path = class_name.rsplit('.', 1)[0].replace('.', os.sep)
        for src_root in Path(workspace_root).rglob('src'):
            candidate = src_root / 'main' / 'java' / package_path / target_file
            if candidate.exists():
                return str(candidate)
    # fallback: 按文件名
    for match in Path(workspace_root).rglob(target_file):
        return str(match)
    return None


def _rank_jar_search_dirs(class_name, jar_paths):
    """根据类名包路径，智能排序 JAR 搜索目录并缩小范围。

    规则：
      kd.bos.*       → 优先 bos 目录
      kd.ec.ectem.*  → 优先 biz 目录，且优先匹配含 'ectem' 的 JAR
      kd.ec.xxx.*    → 优先 biz 目录，且优先匹配含 'xxx' 的 JAR
      其他            → 按配置顺序
    返回: [(jar_dir, jar_hint)] 列表，jar_hint 为优先匹配的关键词（可为 None）
    """
    parts = class_name.split('.')
    # 分析包路径: kd.<module>.<submodule>...
    module = parts[1] if len(parts) > 1 else None    # bos / ec / ...
    submodule = parts[2] if len(parts) > 2 else None  # ectem / ecma / ...

    # 按目录名分组
    dir_map = {}
    for p in jar_paths:
        dir_name = Path(p).name.lower()  # bos / biz / cus
        dir_map[dir_name] = p

    ordered = []
    jar_hint = submodule  # e.g. 'ectem'

    if module == 'bos':
        # kd.bos.* → bos 目录优先
        if 'bos' in dir_map:
            ordered.append((dir_map['bos'], None))
        for name, path in dir_map.items():
            if name != 'bos':
                ordered.append((path, None))
    else:
        # kd.ec.* / kd.fi.* 等 → biz 目录优先，用 submodule 缩小范围
        if 'biz' in dir_map:
            ordered.append((dir_map['biz'], jar_hint))
        if 'cus' in dir_map:
            ordered.append((dir_map['cus'], jar_hint))
        for name, path in dir_map.items():
            if name not in ('biz', 'cus'):
                ordered.append((path, None))

    # 如果排序后为空，则回退到原始顺序
    if not ordered:
        ordered = [(p, jar_hint) for p in jar_paths]

    return ordered


def find_class_in_jars(class_name, jar_paths):
    """在 JAR 文件中查找类（智能路径 + 关键词优先匹配）"""
    class_file = class_name.replace('.', '/') + '.class'
    ranked_dirs = _rank_jar_search_dirs(class_name, jar_paths)

    for jar_dir, hint in ranked_dirs:
        jar_dir_path = Path(jar_dir)
        if not jar_dir_path.exists():
            continue

        # 如果有 hint（如 'ectem'），先只搜文件名含 hint 的 JAR
        if hint:
            for jar_file in jar_dir_path.rglob('*.jar'):
                if hint.lower() not in jar_file.name.lower():
                    continue
                try:
                    with zipfile.ZipFile(jar_file, 'r') as zf:
                        if class_file in zf.namelist():
                            return str(jar_file)
                except (zipfile.BadZipFile, PermissionError):
                    continue

        # hint 没命中，再全量搜当前目录
        for jar_file in jar_dir_path.rglob('*.jar'):
            try:
                with zipfile.ZipFile(jar_file, 'r') as zf:
                    if class_file in zf.namelist():
                        return str(jar_file)
            except (zipfile.BadZipFile, PermissionError):
                continue

    return None


def decompile_from_jar(class_name, jar_path, cfr_jar_path):
    """使用 CFR 从 JAR 反编译指定类，返回源码字符串"""
    cfr_path = Path(cfr_jar_path)
    if not cfr_path.is_absolute():
        cfr_path = SKILL_DIR / cfr_jar_path
    if not cfr_path.exists():
        return None, f"CFR 不存在: {cfr_path}"

    try:
        result = subprocess.run(
            ["java", "-jar", str(cfr_path), str(jar_path),
             "--methodname", "", "--outputdir", "-",
             class_name],
            capture_output=True, text=True, timeout=30, encoding="utf-8"
        )
        # CFR 输出到 stdout
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout, None
    except Exception:
        pass

    # 备选方式：解压 .class 再反编译
    try:
        class_file = class_name.replace('.', '/') + '.class'
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(jar_path, 'r') as zf:
                zf.extract(class_file, tmpdir)
            class_path = os.path.join(tmpdir, class_file)
            result = subprocess.run(
                ["java", "-jar", str(cfr_path), class_path],
                capture_output=True, text=True, timeout=30, encoding="utf-8"
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout, None
            return None, result.stderr[:500] if result.stderr else "反编译失败"
    except Exception as e:
        return None, str(e)

def resolve_source(class_name, workspace_root, jar_paths, cfr_jar_path):
    """解析插件源码：优先源码 → JAR 反编译 → javap 兜底"""
    # 1. 工作区源码
    src = find_source_in_workspace(class_name, workspace_root)
    if src:
        try:
            with open(src, 'r', encoding='utf-8') as f:
                code = f.read()
            return {"source": "workspace", "path": src, "code": code, "error": None}
        except Exception as e:
            return {"source": "workspace", "path": src, "code": None, "error": str(e)}

    # 2. JAR 反编译
    jar_path = find_class_in_jars(class_name, jar_paths)
    if jar_path:
        code, err = decompile_from_jar(class_name, jar_path, cfr_jar_path)
        if code:
            return {"source": "jar_decompiled", "path": jar_path, "code": code, "error": None}
        # 3. javap 兜底
        javap_result = _javap_fallback(class_name, jar_path)
        return {"source": "jar_javap", "path": jar_path, "code": javap_result, "error": err}

    return {"source": "not_found", "path": None, "code": None, "error": "源码和JAR均未找到"}


def _javap_fallback(class_name, jar_path):
    """用 javap 获取类签名作为兜底"""
    try:
        result = subprocess.run(
            ["javap", "-classpath", jar_path, "-public", class_name],
            capture_output=True, text=True, timeout=15, encoding="utf-8"
        )
        if result.returncode == 0:
            return result.stdout
    except Exception:
        pass
    return None


# ── 主查询 ───────────────────────────────────────────────────────────────
def query_all_plugins(conn, entity_number):
    """查询实体的所有插件（操作插件 + 页面插件）"""
    cur = conn.cursor()
    all_plugins = []
    entity_info = {}

    # 查实体：优先精确匹配，再模糊搜索
    cur.execute(f"""
        SELECT e.fid, e.fnumber, e.fdata, l.fname
        FROM {ENTITY_TABLE} e
        LEFT JOIN {ENTITY_L_TABLE} l ON l.fid = e.fid AND l.flocaleid = %s
        WHERE e.fnumber = %s
        LIMIT 1
    """, (ZH_LOCALE, entity_number))
    entities = cur.fetchall()
    if not entities:
        cur.execute(f"""
            SELECT e.fid, e.fnumber, e.fdata, l.fname
            FROM {ENTITY_TABLE} e
            LEFT JOIN {ENTITY_L_TABLE} l ON l.fid = e.fid AND l.flocaleid = %s
            WHERE e.fnumber ILIKE %s
            ORDER BY length(e.fnumber)
            LIMIT 5
        """, (ZH_LOCALE, f"%{entity_number}%"))
        entities = cur.fetchall()

    if not entities:
        print(f"[ERROR] 未找到包含 '{entity_number}' 的实体")
        cur.close()
        return entity_info, all_plugins

    for entity_fid, entity_fnumber, entity_fdata, entity_fname in entities:
        entity_info = {
            "fnumber": entity_fnumber,
            "fname": entity_fname or "",
            "fid": entity_fid,
        }
        print(f"[INFO] 实体: {entity_fnumber} ({entity_fname or ''})")

        # 1. 操作插件
        fmt, root = _parse_fdata(entity_fdata)
        if fmt == 'xml' and root is not None:
            op_plugins = extract_op_plugins(root)
            all_plugins.extend(op_plugins)
            print(f"  操作插件: {len(op_plugins)} 个")

        # 2. 页面插件
        cur.execute(f"""
            SELECT f.fid, f.fnumber, f.fdata, l.fname
            FROM {FORM_TABLE} f
            LEFT JOIN {FORM_L_TABLE} l ON l.fid = f.fid AND l.flocaleid = %s
            WHERE f.fentityid = %s OR f.fnumber ILIKE %s
            LIMIT 20
        """, (ZH_LOCALE, entity_fid, f"%{entity_fnumber}%"))
        forms = cur.fetchall()

        form_plugin_count = 0
        for form_fid, form_fnumber, form_fdata, form_fname in forms:
            fmt, root = _parse_fdata(form_fdata)
            if fmt == 'xml' and root is not None:
                fp = extract_form_plugins(root, form_fnumber, form_fname or "")
                all_plugins.extend(fp)
                form_plugin_count += len(fp)
        print(f"  页面插件: {form_plugin_count} 个")
        break  # 取第一个匹配的实体

    cur.close()
    return entity_info, all_plugins

# ── 数据输出（清单 + 源码文件）────────────────────────────────────────────
def save_inventory(entity_info, plugins_with_source, output_dir):
    """保存插件清单（JSON）和各插件源码到独立文件，供 Agent 读取分析"""
    entity_num = entity_info.get("fnumber", "unknown")
    base_dir = Path(output_dir) / entity_num
    sources_dir = base_dir / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    # 去重：同一个类只保存一份源码
    saved_sources = {}  # className → source file path
    inventory_items = []

    for p in plugins_with_source:
        plugin = p["plugin"]
        resolved = p["resolved"]
        cls = plugin["className"]
        simple_name = cls.rsplit('.', 1)[-1] if '.' in cls else cls

        # 保存源码文件（去重）
        source_file = None
        if cls not in saved_sources and resolved.get("code"):
            source_file = str(sources_dir / f"{simple_name}.java")
            with open(source_file, "w", encoding="utf-8") as f:
                f.write(resolved["code"])
            saved_sources[cls] = source_file
        elif cls in saved_sources:
            source_file = saved_sources[cls]

        src_label = {"workspace": "源码", "jar_decompiled": "反编译", "jar_javap": "javap", "not_found": "未找到"}.get(resolved["source"], "?")

        item = {
            "className": cls,
            "simpleName": simple_name,
            "type": plugin["type"],
            "enabled": plugin.get("enabled", ""),
            "description": plugin.get("description", ""),
            "sourceType": resolved["source"],
            "sourceLabel": src_label,
            "originalPath": resolved.get("path", ""),
            "localSourceFile": source_file,
        }
        if plugin.get("operation"):
            item["operation"] = plugin["operation"]
        if plugin.get("pageElement"):
            item["pageElement"] = plugin["pageElement"]
        if plugin.get("formPage"):
            item["formPage"] = plugin["formPage"]
        if resolved.get("error"):
            item["error"] = resolved["error"]

        inventory_items.append(item)

    # 保存清单 JSON
    inventory = {
        "entity": entity_info,
        "pluginCount": len(inventory_items),
        "uniqueClassCount": len(saved_sources),
        "plugins": inventory_items,
    }
    inventory_path = str(base_dir / "inventory.json")
    with open(inventory_path, "w", encoding="utf-8") as f:
        json.dump(inventory, f, ensure_ascii=False, indent=2)

    return str(base_dir), inventory_path


# ── 主入口 ───────────────────────────────────────────────────────────────
def main():
    cfg = load_config()
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    allow_git_output = _truthy_env(ALLOW_GIT_OUTPUT_ENV)
    if "--allow-git-output" in args:
        allow_git_output = True
        args = [arg for arg in args if arg != "--allow-git-output"]

    entity_number = args[0]

    output_override = None
    if "--output" in args:
        idx = args.index("--output")
        if idx + 1 < len(args):
            output_override = args[idx + 1]
    output_dir, output_warnings = _resolve_output_dir(cfg, output_override, allow_git_output)
    for warning in output_warnings:
        print(f"[WARNING] {warning}")

    workspace_root = cfg.get("workspace", {}).get("projectRoot", "")
    jar_paths = cfg.get("jarLibPaths", {}).get("paths", [])
    cfr_jar = cfg.get("decompiler", {}).get("cfrJarPath", "scripts/cfr-0.152.jar")

    # 1. 查询所有插件
    conn = get_conn(cfg)
    try:
        entity_info, all_plugins = query_all_plugins(conn, entity_number)
    finally:
        conn.close()

    if not all_plugins:
        print("[INFO] 未找到任何插件，退出")
        return

    print(f"\n[INFO] 共 {len(all_plugins)} 个插件，开始查找源码...")

    # 2. 解析每个插件的源码
    plugins_with_source = []
    unique_classes = []
    for p in all_plugins:
        cls = p["className"]
        if cls in unique_classes:
            # 复用已解析的
            for prev in plugins_with_source:
                if prev["plugin"]["className"] == cls:
                    plugins_with_source.append({"plugin": p, "resolved": prev["resolved"]})
                    break
            continue
        unique_classes.append(cls)

        print(f"  [{len(unique_classes)}/{len(set(pp['className'] for pp in all_plugins))}] {cls}...", end=" ")
        resolved = resolve_source(cls, workspace_root, jar_paths, cfr_jar)
        print(f"→ {resolved['source']}" + (f" ({resolved['path']})" if resolved.get('path') else ""))
        plugins_with_source.append({"plugin": p, "resolved": resolved})

    # 3. 保存清单和源码文件
    base_dir, inventory_path = save_inventory(entity_info, plugins_with_source, output_dir)
    print(f"\n{'='*60}")
    print(f"  输出目录: {base_dir}")
    print(f"  清单文件: {inventory_path}")
    print(f"  插件总数: {len(all_plugins)}（去重类: {len(unique_classes)}）")
    print(f"{'='*60}")

    # 输出路径供 agent 读取
    print(f"\n__INVENTORY_PATH__={inventory_path}")
    print(f"__OUTPUT_DIR__={base_dir}")


if __name__ == "__main__":
    main()
