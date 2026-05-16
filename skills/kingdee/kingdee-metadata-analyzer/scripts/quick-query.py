#!/usr/bin/env python3
"""
快速元数据查询工具 - 完全整合 cosmic-plugin-dev 的查询能力

用法：
  python quick-query.py <entityNumber> --config ok-cosmic.json --fields           # 查询字段列表
  python quick-query.py <entityNumber> --config ok-cosmic.json --fields --inherit # 含继承字段
  python quick-query.py <entityNumber> --config ok-cosmic.json --ops              # 查询操作列表
  python quick-query.py <entityNumber> --config ok-cosmic.json --plugins          # 查询已绑定插件
  python quick-query.py <entityNumber> --config ok-cosmic.json --enums            # 查询枚举字段
  python quick-query.py <entityNumber> --config ok-cosmic.json --all              # 查询所有信息
  python quick-query.py --search "关键词" --config ok-cosmic.json                 # 模糊搜索实体
  python quick-query.py --list --module <module> --config ok-cosmic.json          # 按模块列出实体
  python quick-query.py --cache-dir <dir> --config ok-cosmic.json                 # 指定缓存目录

依赖：pip install psycopg2-binary
"""

import sys
import json
import argparse
import io
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

# 确保 stdout/stderr 使用 UTF-8 编码
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ── 常量 ─────────────────────────────────────────────────────────────────
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

# 字段类型标签集合
FIELD_TAGS = {
    'Field', 'Column', 'VarField', 'PKField',
    'BillNoField', 'BillStatusField', 'CreatorField',
    'ModifierField', 'AuditField', 'CreateTimeField',
    'ModifyTimeField', 'AuditTimeField', 'MasterIdField',
    'BasedataField', 'MulBasedataField', 'AmountField',
    'TextField', 'IntegerField', 'LongField', 'DecimalField',
    'DateField', 'DateTimeField', 'TimeField', 'BooleanField',
    'LargeTextField', 'FlexField', 'UserField', 'OrgField',
    'CurrencyField', 'ExchangeRateField', 'GroupField',
    'SubEntryField', 'RelatedFlexField', 'ItemClassField',
    'ComboField',
}

BASEDATA_FIELD_SUFFIXES = (
    'BasedataField',
    'PersonField',
    'UserField',
    'OrgField',
    'CustomerField',
    'SupplierField',
    'MaterielField',
    'AssistantField',
    'UnitField',
    'CurrencyField',
    'AdminDivisionField',
    'CityField',
    'CostCenterField',
    'AccountField',
)


def is_field_tag(tag: str) -> bool:
    """按苍穹字段控件命名识别字段，未知 *Field 也作为字段候选。"""
    return tag in FIELD_TAGS or tag.endswith('Field')


def is_basedata_field_tag(tag: str) -> bool:
    """识别基础资料类字段及其平台派生字段。"""
    return tag in ('BasedataField', 'MulBasedataField') or tag.endswith(BASEDATA_FIELD_SUFFIXES)


# ── 配置加载与数据库连接 ──────────────────────────────────────────────────
def load_config(config_path: Path) -> Dict[str, Any]:
    """加载 ok-cosmic.json 配置"""
    if not config_path.exists():
        print(f"[ERROR] 配置文件不存在: {config_path}", file=sys.stderr)
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_database_password(config: Dict[str, Any], config_path: Path) -> Optional[str]:
    """解析数据库密码（环境变量 → .env → JSON）"""
    import os

    metadata = config.get("metadataAnalyzer", {})
    database = metadata.get("database", {})
    password_env = database.get("passwordEnv", "").strip()

    # 1. 环境变量
    if password_env:
        process_value = os.getenv(password_env)
        if process_value:
            return process_value

        # 2. .env 文件
        dotenv_paths = [
            config_path.with_suffix(".env"),
            config_path.parent / ".env",
        ]
        for dotenv_path in dotenv_paths:
            if dotenv_path.exists():
                for line in dotenv_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith(f"{password_env}="):
                        value = line.split("=", 1)[1].strip()
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        return value

    # 3. JSON 兼容字段
    json_password = database.get("password", "").strip()
    if json_password:
        return json_password

    return None


def get_conn(config: Dict[str, Any], config_path: Path):
    """建立数据库连接"""
    try:
        import psycopg2
    except ImportError:
        print("[ERROR] 缺少依赖，请执行：pip install psycopg2-binary", file=sys.stderr)
        sys.exit(1)

    metadata = config.get("metadataAnalyzer", {})
    if not metadata.get("enabled", False):
        print("[ERROR] metadataAnalyzer.enabled 为 false，禁止连接数据库", file=sys.stderr)
        sys.exit(1)

    db = metadata.get("database", {})
    password = resolve_database_password(config, config_path)
    if not password:
        print("[ERROR] 未找到数据库密码，请检查环境变量、.env 或 JSON 配置", file=sys.stderr)
        sys.exit(1)

    try:
        return psycopg2.connect(
            host=db.get("host", "localhost"),
            port=db.get("port", 5432),
            dbname=db.get("dbname", ""),
            user=db.get("user", ""),
            password=password,
            connect_timeout=db.get("connectTimeoutSeconds", 10),
        )
    except Exception as e:
        print(f"[ERROR] 数据库连接失败: {e}", file=sys.stderr)
        sys.exit(1)


# ── XML 解析工具 ──────────────────────────────────────────────────────────
def parse_fdata(fdata_raw):
    """解析 fdata 原始数据，返回 root 节点"""
    if not fdata_raw:
        return None
    text = fdata_raw.strip() if isinstance(fdata_raw, str) else str(fdata_raw)
    if not text.startswith("<"):
        return None
    try:
        return ET.fromstring(text)
    except ET.ParseError:
        return None


def _is_real_plugin(cls: str) -> bool:
    """判断是否为真实插件类（排除空值和占位符）"""
    if not cls:
        return False
    cls_lower = cls.lower()
    return not (cls_lower in ("null", "none", "undefined") or cls_lower.startswith("placeholder"))


# ── 缓存管理 ──────────────────────────────────────────────────────────────
CACHE_DIR = None  # 全局缓存目录，由 main() 初始化

def save_cache(entity_number: str, data: Dict[str, Any]):
    """保存查询结果到缓存"""
    if CACHE_DIR is None:
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{entity_number}.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_cache(entity_number: str) -> Optional[Dict[str, Any]]:
    """从缓存加载查询结果"""
    if CACHE_DIR is None:
        return None
    cache_file = CACHE_DIR / f"{entity_number}.json"
    if not cache_file.exists():
        return None
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ── 表格输出 ──────────────────────────────────────────────────────────────
def print_table(headers: List[str], rows: List[List[str]]):
    """输出简洁表格（考虑中文字符宽度）"""
    if not rows:
        print("  （无数据）")
        return

    # 计算列宽（中文字符算2个宽度）
    def display_width(s: str) -> int:
        return sum(2 if ord(c) > 127 else 1 for c in s)

    widths = [display_width(h) for h in headers]
    str_rows = []
    for row in rows:
        str_row = [str(v) for v in row]
        str_rows.append(str_row)
        for i, v in enumerate(str_row):
            widths[i] = max(widths[i], display_width(v))

    # 表头
    header_line = "  "
    for i, h in enumerate(headers):
        pad = widths[i] - display_width(h)
        header_line += h + " " * (pad + 2)
    print(header_line)

    # 数据行
    for row in str_rows:
        line = "  "
        for i, v in enumerate(row):
            pad = widths[i] - display_width(v)
            line += v + " " * (pad + 2)
        print(line)


# ── 字段提取 ──────────────────────────────────────────────────────────────
def extract_fields(root, entry_tag: Optional[str] = None) -> List[Dict[str, Any]]:
    """从实体 XML 提取字段列表

    Args:
        root: XML 根节点
        entry_tag: 如果指定，只提取该分录下的字段；None 则提取所有

    Returns:
        list of dict: 字段列表
    """
    fields = []
    if root is None:
        return fields

    search_root = root
    if entry_tag:
        # 查找指定分录节点
        for node in root.iter():
            key = node.findtext('Key', '').strip()
            if key == entry_tag:
                search_root = node
                break

    for node in search_root.iter():
        tag = node.tag
        if not is_field_tag(tag):
            continue

        key = node.findtext('Key', '').strip()
        if not key:
            key = node.get('key', '').strip()
        if not key:
            continue

        # 获取中文名
        name = ''
        name_node = node.find('Name')
        if name_node is not None:
            # 多语言：尝试找 zh_CN
            loc = name_node.find(f".//{ZH_LOCALE}")
            if loc is not None:
                name = (loc.text or '').strip()
            if not name:
                name = (name_node.text or '').strip()
        if not name:
            name = node.findtext('Name', '').strip()

        field_type = tag  # 标签名即类型
        ref_entity = ''
        # 基础资料类型提取关联实体
        if is_basedata_field_tag(tag):
            ref_entity = node.findtext('RefEntityNumber', '').strip()
            if not ref_entity:
                ref_entity = node.findtext('LookUpObject', '').strip()
            if not ref_entity:
                ref_entity = node.findtext('BaseEntityId', '').strip()

        is_basedata = is_basedata_field_tag(tag)

        fields.append({
            "fieldKey": key,
            "name": name,
            "type": field_type,
            "refEntity": ref_entity,
            "isBasedata": is_basedata,
        })

    return fields


# ── 操作提取 ──────────────────────────────────────────────────────────────
def extract_operations(root) -> List[Dict[str, Any]]:
    """从实体 XML 提取操作列表"""
    results = []
    if root is None:
        return results

    edit_counter = 0
    for op in root.iter('Operation'):
        key = op.findtext('Key', '').strip()
        name = op.findtext('Name', '').strip()
        action = op.get('action', '').strip()
        op_type = action or 'custom'

        if key:
            op_label = f"{key}({name})" if name else key
        elif action == 'edit':
            op_label = BUILTIN_EDIT_ORDER[edit_counter] if edit_counter < len(BUILTIN_EDIT_ORDER) else f"标准操作#{edit_counter}"
            edit_counter += 1
        elif action == 'remove':
            op_label = "delete(删除)"
        else:
            op_label = action or "unknown"

        # 统计插件数量
        plugin_count = 0
        plugins_node = op.find('Plugins')
        if plugins_node is not None:
            for p in plugins_node.findall('Plugin'):
                cls = p.findtext('ClassName', '').strip()
                if not cls:
                    cls = p.get('oid', '').strip()
                if _is_real_plugin(cls):
                    plugin_count += 1

        results.append({
            "opKey": key or op_label,
            "name": name,
            "opType": op_type,
            "pluginCount": plugin_count,
        })

    return results


# ── 插件提取 ──────────────────────────────────────────────────────────────
def extract_plugins(root, entity_number: str) -> List[Dict[str, Any]]:
    """从实体 XML 提取所有插件"""
    plugins = []
    if root is None:
        return plugins

    # 提取操作插件
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
                plugins.append({
                    "type": "操作插件",
                    "operation": op_label,
                    "className": cls,
                    "enabled": enabled,
                    "description": desc,
                })

    return plugins


# ── 枚举提取 ──────────────────────────────────────────────────────────────
def extract_enums(root) -> List[Dict[str, Any]]:
    """从实体 XML 提取枚举类型字段及其枚举值列表"""
    enums = []
    if root is None:
        return enums

    for node in root.iter():
        combo_type = node.findtext('ComboDataType', '').strip()
        items_node = node.find('Items')
        if items_node is None:
            items_node = node.find('EnumItems')
        if items_node is None:
            items_node = node.find('ComboItems')

        ctrl_type = node.findtext('ControlType', '').strip()
        if items_node is None and ctrl_type != 'Combo' and not combo_type:
            continue

        key = node.findtext('Key', '').strip()
        if not key:
            key = node.get('key', '').strip()
        if not key:
            continue

        # 提取字段名称
        name = ''
        name_node = node.find('Name')
        if name_node is not None:
            loc = name_node.find(f".//{ZH_LOCALE}")
            if loc is not None:
                name = (loc.text or '').strip()
            if not name:
                name = (name_node.text or '').strip()
        if not name:
            name = node.findtext('Name', '').strip()

        # 提取枚举值
        enum_values = []
        if items_node is not None:
            for item in items_node:
                val = item.findtext('Value', '').strip() or item.get('value', '').strip()
                item_name = ''
                item_name_node = item.find('Name')
                if item_name_node is not None:
                    loc = item_name_node.find(f".//{ZH_LOCALE}")
                    if loc is not None:
                        item_name = (loc.text or '').strip()
                    if not item_name:
                        item_name = (item_name_node.text or '').strip()
                if not item_name:
                    item_name = item.findtext('Name', '').strip()
                if not item_name:
                    item_name = item.findtext('Caption', '').strip()
                enum_values.append({"value": val, "name": item_name})

        if enum_values or items_node is not None:
            enums.append({
                "fieldKey": key,
                "name": name,
                "type": node.tag,
                "values": enum_values,
            })

    return enums


# ── 数据库查询 ────────────────────────────────────────────────────────────
def query_entity(cur, entity_number: str) -> Optional[Tuple[Any, str, str, Any]]:
    """查询实体元数据，返回 (fid, fnumber, fdata, fname)"""
    cur.execute(f"""
        SELECT e.fid, e.fnumber, e.fdata, l.fname
        FROM {ENTITY_TABLE} e
        LEFT JOIN {ENTITY_L_TABLE} l ON e.fid = l.fid AND l.flocaleid = %s
        WHERE e.fnumber = %s
    """, (ZH_LOCALE, entity_number))
    return cur.fetchone()


def search_entities(cur, keyword: str) -> List[Tuple]:
    """模糊搜索实体"""
    pattern = f"%{keyword}%"
    cur.execute(f"""
        SELECT e.fid, e.fnumber, l.fname
        FROM {ENTITY_TABLE} e
        LEFT JOIN {ENTITY_L_TABLE} l ON l.fid = e.fid AND l.flocaleid = %s
        WHERE e.fnumber ILIKE %s OR l.fname ILIKE %s
        ORDER BY length(e.fnumber)
        LIMIT 20
    """, (ZH_LOCALE, pattern, pattern))
    return cur.fetchall()


def list_entities_by_module(cur, module_prefix: str) -> List[Tuple]:
    """按模块前缀列出实体"""
    pattern = f"{module_prefix}%"
    cur.execute(f"""
        SELECT e.fid, e.fnumber, l.fname
        FROM {ENTITY_TABLE} e
        LEFT JOIN {ENTITY_L_TABLE} l ON l.fid = e.fid AND l.flocaleid = %s
        WHERE e.fnumber LIKE %s
        ORDER BY e.fnumber
        LIMIT 50
    """, (ZH_LOCALE, pattern))
    return cur.fetchall()


def query_parent_entity(cur, root) -> Optional[Tuple]:
    """从 XML 中查找父实体标识并递归查询"""
    if root is None:
        return None

    # 查找继承相关节点
    parent_number = root.findtext('BaseEntityNumber', '').strip()
    if not parent_number:
        parent_number = root.findtext('ParentEntityNumber', '').strip()
    if not parent_number:
        parent_number = root.findtext('InheritEntityNumber', '').strip()
    if not parent_number:
        parent_number = root.get('baseEntityNumber', '').strip()

    # 检查 ParentId 元素或属性
    if not parent_number:
        parent_id = root.findtext('ParentId', '').strip()
        if not parent_id:
            parent_id = root.get('ParentId', '').strip()
        if parent_id:
            # 通过 ParentId 查询数据库获取 fnumber
            cur.execute(f"""
                SELECT e.fnumber
                FROM {ENTITY_TABLE} e
                WHERE CAST(e.fid AS TEXT) = %s
                LIMIT 1
            """, (parent_id,))
            row = cur.fetchone()
            if row:
                parent_number = row[0]

    if parent_number:
        return query_entity(cur, parent_number)
    return None


def command_fields(args):
    """查询字段列表"""
    config = load_config(Path(args.config))
    conn = get_conn(config, Path(args.config))
    cur = conn.cursor()

    row = query_entity(cur, args.entityNumber)
    if not row:
        suggestions = search_entities(cur, args.entityNumber)
        cur.close()
        conn.close()
        print(f"[ERROR] 未找到实体 '{args.entityNumber}'", file=sys.stderr)
        if suggestions:
            print("\n你是否要找以下实体？\n", file=sys.stderr)
            table_rows = [(str(i + 1), s[1], s[2] or '') for i, s in enumerate(suggestions)]
            print_table(["序号", "entityNumber", "实体名称"], table_rows)
        return 1

    entity_fid, entity_fnumber, entity_fdata, entity_fname = row
    root = parse_fdata(entity_fdata)
    all_fields = extract_fields(root)

    # 处理继承链
    if args.inherit:
        inherit_chain = []
        current_root = root
        while True:
            parent_row = query_parent_entity(cur, current_root)
            if parent_row:
                p_fid, p_fnumber, p_fdata, p_fname = parent_row
                proot = parse_fdata(p_fdata)
                if proot is not None:
                    inherit_chain.append(p_fnumber)
                    parent_fields = extract_fields(proot)
                    # 标记来源
                    for f in parent_fields:
                        f["inherited_from"] = p_fnumber
                    all_fields.extend(parent_fields)
                    current_root = proot
                else:
                    break
            else:
                break

    cur.close()
    conn.close()

    print(f"实体 {entity_fnumber}({entity_fname or ''}) 共 {len(all_fields)} 个字段：\n")
    table_rows = []
    for i, f in enumerate(all_fields):
        inherited = f.get("inherited_from", "")
        ref = f.get("refEntity", "")
        extra = ""
        if inherited:
            extra += f"[继承自:{inherited}]"
        if ref:
            extra += f"[关联:{ref}]"
        table_rows.append((
            str(i + 1),
            f["fieldKey"],
            f["name"],
            f["type"],
            "是" if f.get("isBasedata") else "",
            extra,
        ))
    print_table(["序号", "fieldKey", "中文名", "类型", "基础资料", "备注"], table_rows)

    # 保存缓存
    if CACHE_DIR:
        cache_data = {
            "entityNumber": entity_fnumber,
            "entityName": entity_fname,
            "fields": all_fields,
            "timestamp": datetime.now().isoformat(),
        }
        save_cache(entity_fnumber, cache_data)

    return 0


def command_ops(args):
    """查询操作列表"""
    config = load_config(Path(args.config))
    conn = get_conn(config, Path(args.config))
    cur = conn.cursor()

    row = query_entity(cur, args.entityNumber)
    if not row:
        suggestions = search_entities(cur, args.entityNumber)
        cur.close()
        conn.close()
        print(f"[ERROR] 未找到实体 '{args.entityNumber}'", file=sys.stderr)
        if suggestions:
            print("\n你是否要找以下实体？\n", file=sys.stderr)
            table_rows = [(str(i + 1), s[1], s[2] or '') for i, s in enumerate(suggestions)]
            print_table(["序号", "entityNumber", "实体名称"], table_rows)
        return 1

    entity_fid, entity_fnumber, entity_fdata, entity_fname = row
    root = parse_fdata(entity_fdata)
    ops = extract_operations(root)
    cur.close()
    conn.close()

    print(f"实体 {entity_fnumber}({entity_fname or ''}) 共 {len(ops)} 个操作：\n")
    table_rows = []
    for i, op in enumerate(ops):
        table_rows.append((
            str(i + 1),
            op["opKey"],
            op["name"],
            op["opType"],
            str(op["pluginCount"]),
        ))
    print_table(["序号", "opKey", "名称", "操作类型", "插件数"], table_rows)

    return 0


def command_plugins(args):
    """查询已绑定插件"""
    config = load_config(Path(args.config))
    conn = get_conn(config, Path(args.config))
    cur = conn.cursor()

    row = query_entity(cur, args.entityNumber)
    if not row:
        suggestions = search_entities(cur, args.entityNumber)
        cur.close()
        conn.close()
        print(f"[ERROR] 未找到实体 '{args.entityNumber}'", file=sys.stderr)
        if suggestions:
            print("\n你是否要找以下实体？\n", file=sys.stderr)
            table_rows = [(str(i + 1), s[1], s[2] or '') for i, s in enumerate(suggestions)]
            print_table(["序号", "entityNumber", "实体名称"], table_rows)
        return 1

    entity_fid, entity_fnumber, entity_fdata, entity_fname = row
    root = parse_fdata(entity_fdata)
    plugins = extract_plugins(root, entity_fnumber)
    cur.close()
    conn.close()

    print(f"实体 {entity_fnumber}({entity_fname or ''}) 共 {len(plugins)} 个插件：\n")
    table_rows = []
    for i, p in enumerate(plugins):
        bind_loc = p.get("operation", "")
        enabled_str = "启用" if p.get("enabled") == "true" else "禁用" if p.get("enabled") else ""
        table_rows.append((
            str(i + 1),
            p["type"],
            bind_loc,
            p["className"],
            enabled_str,
            p.get("description", ""),
        ))
    print_table(["序号", "类型", "挂载点", "类名", "状态", "说明"], table_rows)

    return 0


def command_enums(args):
    """查询枚举字段"""
    config = load_config(Path(args.config))
    conn = get_conn(config, Path(args.config))
    cur = conn.cursor()

    row = query_entity(cur, args.entityNumber)
    if not row:
        suggestions = search_entities(cur, args.entityNumber)
        cur.close()
        conn.close()
        print(f"[ERROR] 未找到实体 '{args.entityNumber}'", file=sys.stderr)
        if suggestions:
            print("\n你是否要找以下实体？\n", file=sys.stderr)
            table_rows = [(str(i + 1), s[1], s[2] or '') for i, s in enumerate(suggestions)]
            print_table(["序号", "entityNumber", "实体名称"], table_rows)
        return 1

    entity_fid, entity_fnumber, entity_fdata, entity_fname = row
    root = parse_fdata(entity_fdata)
    enums = extract_enums(root)
    cur.close()
    conn.close()

    print(f"实体 {entity_fnumber}({entity_fname or ''}) 共 {len(enums)} 个枚举字段：\n")
    for enum in enums:
        print(f"  {enum['fieldKey']}: {enum['name']} [{enum['type']}]")
        for val in enum['values']:
            print(f"    - {val['value']}: {val['name']}")
        print()

    return 0


def command_all(args):
    """查询所有信息"""
    config = load_config(Path(args.config))
    conn = get_conn(config, Path(args.config))
    cur = conn.cursor()

    row = query_entity(cur, args.entityNumber)
    if not row:
        suggestions = search_entities(cur, args.entityNumber)
        cur.close()
        conn.close()
        print(f"[ERROR] 未找到实体 '{args.entityNumber}'", file=sys.stderr)
        if suggestions:
            print("\n你是否要找以下实体？\n", file=sys.stderr)
            table_rows = [(str(i + 1), s[1], s[2] or '') for i, s in enumerate(suggestions)]
            print_table(["序号", "entityNumber", "实体名称"], table_rows)
        return 1

    entity_fid, entity_fnumber, entity_fdata, entity_fname = row
    root = parse_fdata(entity_fdata)

    print(f"实体 {entity_fnumber}({entity_fname or ''})\n")

    # 字段
    fields = extract_fields(root)
    print(f"=== 字段 ({len(fields)}) ===")
    for field in fields[:10]:
        ref_info = f" -> {field['refEntity']}" if field['refEntity'] else ""
        print(f"  {field['fieldKey']}: {field['name']} [{field['type']}]{ref_info}")
    if len(fields) > 10:
        print(f"  ... 还有 {len(fields) - 10} 个字段")
    print()

    # 操作
    operations = extract_operations(root)
    print(f"=== 操作 ({len(operations)}) ===")
    for op in operations:
        plugin_info = f" (插件数: {op['pluginCount']})" if op['pluginCount'] > 0 else ""
        print(f"  {op['opKey']}: {op['name']} [{op['opType']}]{plugin_info}")
    print()

    # 插件
    plugins = extract_plugins(root, entity_fnumber)
    print(f"=== 插件 ({len(plugins)}) ===")
    for plugin in plugins[:10]:
        print(f"  {plugin['type']} @ {plugin['operation']}")
        print(f"    {plugin['className']}")
    if len(plugins) > 10:
        print(f"  ... 还有 {len(plugins) - 10} 个插件")
    print()

    # 枚举
    enums = extract_enums(root)
    print(f"=== 枚举字段 ({len(enums)}) ===")
    for enum in enums[:5]:
        print(f"  {enum['fieldKey']}: {enum['name']} [{enum['type']}]")
        for val in enum['values'][:3]:
            print(f"    - {val['value']}: {val['name']}")
        if len(enum['values']) > 3:
            print(f"    ... 还有 {len(enum['values']) - 3} 个枚举值")
    if len(enums) > 5:
        print(f"  ... 还有 {len(enums) - 5} 个枚举字段")

    cur.close()
    conn.close()
    return 0


def command_search(args):
    """模糊搜索实体"""
    config = load_config(Path(args.config))
    conn = get_conn(config, Path(args.config))
    cur = conn.cursor()

    rows = search_entities(cur, args.search)
    cur.close()
    conn.close()

    if not rows:
        print(f"未找到包含 '{args.search}' 的实体")
        return 0

    print(f"搜索 '{args.search}' 找到 {len(rows)} 个实体：\n")
    table_rows = [(str(i + 1), row[1], row[2] or '') for i, row in enumerate(rows)]
    print_table(["序号", "entityNumber", "实体名称"], table_rows)
    return 0


def command_list(args):
    """按模块列出实体"""
    config = load_config(Path(args.config))
    conn = get_conn(config, Path(args.config))
    cur = conn.cursor()

    rows = list_entities_by_module(cur, args.module)
    cur.close()
    conn.close()

    if not rows:
        print(f"未找到模块 '{args.module}' 下的实体")
        return 0

    print(f"模块 '{args.module}' 下共 {len(rows)} 个实体：\n")
    table_rows = [(str(i + 1), row[1], row[2] or '') for i, row in enumerate(rows)]
    print_table(["序号", "entityNumber", "实体名称"], table_rows)
    return 0


def main():
    global CACHE_DIR

    parser = argparse.ArgumentParser(description="快速元数据查询工具")
    parser.add_argument("entityNumber", nargs="?", help="苍穹实体标识")
    parser.add_argument("--config", required=True, help="项目 ok-cosmic.json 路径")
    parser.add_argument("--fields", action="store_true", help="查询字段列表")
    parser.add_argument("--inherit", action="store_true", help="含继承字段（与 --fields 配合使用）")
    parser.add_argument("--ops", action="store_true", help="查询操作列表")
    parser.add_argument("--plugins", action="store_true", help="查询已绑定插件")
    parser.add_argument("--enums", action="store_true", help="查询枚举字段")
    parser.add_argument("--all", action="store_true", help="查询所有信息")
    parser.add_argument("--search", help="模糊搜索实体")
    parser.add_argument("--list", action="store_true", help="列出实体（配合 --module 使用）")
    parser.add_argument("--module", help="模块前缀（配合 --list 使用）")
    parser.add_argument("--cache-dir", help="缓存目录路径（默认：脚本目录下的 .metadata_cache）")

    args = parser.parse_args()

    # 初始化缓存目录
    if args.cache_dir:
        CACHE_DIR = Path(args.cache_dir)
    else:
        CACHE_DIR = Path(__file__).parent / ".metadata_cache"

    # 搜索模式
    if args.search:
        return command_search(args)

    # 列出模块实体
    if args.list:
        if not args.module:
            print("[ERROR] --list 需要配合 --module 使用", file=sys.stderr)
            return 1
        return command_list(args)

    # 需要 entityNumber
    if not args.entityNumber:
        parser.print_help()
        return 1

    # 查询模式
    if args.fields:
        return command_fields(args)
    elif args.ops:
        return command_ops(args)
    elif args.plugins:
        return command_plugins(args)
    elif args.enums:
        return command_enums(args)
    elif args.all:
        return command_all(args)
    else:
        # 默认查询所有信息
        args.all = True
        return command_all(args)


if __name__ == "__main__":
    sys.exit(main())
