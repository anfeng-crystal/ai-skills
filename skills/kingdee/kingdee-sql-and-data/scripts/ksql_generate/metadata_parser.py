"""元数据解析器 - 解析实体元数据 XML，提取字段列表并按表分组"""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
import sys
from pathlib import Path

# 获取当前脚本所在目录（如 skills/your_skill/scripts/）
SCRIPT_DIR = Path(__file__).parent
# 将根目录加入搜索路径
sys.path.append(str(SCRIPT_DIR))
sys.path.append(str(SCRIPT_DIR.parent)) # 通常需3级返回：scripts → skill_dir → skills → root

from db_connector import get_connection
from models import DBConfig

logger = logging.getLogger(__name__)

# 需要解析的字段类型节点
FIELD_TYPE_NODES = [
    "BillNoField", "BillStatusField", "CreaterField", "ModifierField",
    "UserField", "DateTimeField", "ModifyDateField", "CreateDateField",
    "OrgField", "BasedataField", "ComboField", "DateField", "TextField",
    "CurrencyField", "AmountField", "BigIntField", "BizUniqueCode",
    "EntryEntity", "CheckBoxField", "DecimalField", "IntegerField",
    "MuliLangTextField", "AccountField", "MulBasedataField",
    "ItemClassTypeField", "ItemClassField", "LargeTextField",
    "BasedataPropField", "SubEntryEntity",
]


@dataclass
class FieldDef:
    """字段定义"""
    id: str = ""
    field_name: str = ""
    suffix: str = ""
    table_name: str = ""
    parent_id: str = ""


@dataclass
class EntityMeta:
    """实体元数据信息"""
    inherit_path: str = ""
    main_table: str = ""
    fields: list = field(default_factory=list)  # list[FieldDef]


def query_entity_meta(db_config: DBConfig, entity: str) -> tuple:
    """查询实体元数据基本信息。

    Returns:
        (inherit_path, fdata_xml, main_table) 或 None
    """
    sql = (
        "SELECT e.finheritpath, e.fdata, m.ftablename "
        "FROM t_meta_entitydesign e, t_meta_mainentityinfo m "
        "WHERE e.fid = m.fdentityid AND e.fnumber = %s"
    )
    # Oracle 用不同占位符，这里简化处理用字符串拼接
    raw_sql = (
        "SELECT e.finheritpath, e.fdata, m.ftablename "
        "FROM t_meta_entitydesign e, t_meta_mainentityinfo m "
        f"WHERE e.fid = m.fdentityid AND e.fnumber = '{entity}'"
    )
    try:
        conn = get_connection(db_config)
        cursor = conn.cursor()
        cursor.execute(raw_sql)
        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0], row[1], row[2]
        return None
    except Exception as e:
        logger.error("查询实体元数据失败 [%s]: %s", entity, e)
        raise


def query_parent_fdata(db_config: DBConfig, inherit_path: str) -> list:
    """查询父实体的 fdata XML 列表。"""
    if not inherit_path or not inherit_path.strip():
        return []
    parent_ids = [pid.strip() for pid in inherit_path.split(",") if pid.strip()]
    in_clause = ", ".join(f"'{pid}'" for pid in parent_ids)
    sql = f"SELECT fdata FROM t_meta_entitydesign WHERE fid IN ({in_clause})"
    try:
        conn = get_connection(db_config)
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows if row[0]]
    except Exception as e:
        logger.error("查询父实体元数据失败: %s", e)
        return []


def _get_attr_or_child(elem, name: str) -> str:
    """从 XML 元素获取值：优先取属性，取不到则取同名子节点的文本。

    例如：
      <ComboField FieldName="abc"/>          → 从属性取 "abc"
      <ComboField><FieldName>abc</FieldName> → 从子节点取 "abc"
    """
    val = elem.get(name, "")
    if val:
        return val
    child = elem.find(name)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def parse_fields_from_xml(fdata_xml: str) -> list:
    """从 fdata XML 中解析字段列表。

    Returns:
        list[FieldDef]
    """
    fields = []
    if not fdata_xml:
        return fields
    try:
        root = ET.fromstring(fdata_xml)
    except ET.ParseError as e:
        logger.error("XML 解析失败: %s", e)
        return fields

    items = root.find("Items")
    if items is None:
        return fields

    for node_name in FIELD_TYPE_NODES:
        for elem in items.findall(node_name):
            fd = FieldDef()
            # Id: 优先取 oid 属性，其次取 Id 属性，最后取 Id 子节点
            oid = elem.get("oid", "")
            fd.id = oid if oid else _get_attr_or_child(elem, "Id")
            fd.field_name = _get_attr_or_child(elem, "FieldName")
            fd.suffix = _get_attr_or_child(elem, "Suffix")
            fd.table_name = _get_attr_or_child(elem, "TableName")
            fd.parent_id = _get_attr_or_child(elem, "ParentId")
            # TableName 有值的是分录/子实体容器字段，跳过不作为数据列
            if fd.id and not fd.table_name:
                fields.append(fd)
    return fields


def merge_fields(all_fields_list: list) -> list:
    """合并多个来源的字段列表，按 Id 去重合并属性。

    后出现的字段覆盖先出现的（子实体覆盖父实体）。
    """
    merged = {}  # id -> FieldDef
    for fields in all_fields_list:
        for fd in fields:
            if fd.id in merged:
                existing = merged[fd.id]
                if fd.field_name:
                    existing.field_name = fd.field_name
                if fd.suffix:
                    existing.suffix = fd.suffix
                if fd.table_name:
                    existing.table_name = fd.table_name
                if fd.parent_id:
                    existing.parent_id = fd.parent_id
            else:
                merged[fd.id] = FieldDef(
                    id=fd.id,
                    field_name=fd.field_name,
                    suffix=fd.suffix,
                    table_name=fd.table_name,
                    parent_id=fd.parent_id,
                )
    return list(merged.values())


def resolve_table_names(fields: list, main_table: str) -> list:
    """解析每个字段的实际数据库表名。

    规则：
    - FieldName 为空的跳过
    - Suffix 不为空：表名 = main_table + '_' + Suffix
    - ParentId 为空：表名 = main_table
    - ParentId 不为空：找到 ParentId 对应的字段，取其 TableName
    """
    # 建立 id -> field 映射
    id_map = {fd.id: fd for fd in fields}

    result = []
    for fd in fields:
        if not fd.field_name:
            continue

        # 确定表名
        if fd.suffix:
            fd.table_name = f"{main_table}_{fd.suffix}"
        elif not fd.parent_id:
            fd.table_name = main_table
        else:
            # 根据 ParentId 查找父字段的 TableName
            parent = id_map.get(fd.parent_id)
            if parent and parent.table_name:
                fd.table_name = parent.table_name
            elif parent and parent.suffix:
                fd.table_name = f"{main_table}_{parent.suffix}"
            else:
                fd.table_name = main_table

        result.append(fd)
    return result


def group_fields_by_table(fields: list) -> dict:
    """按数据库表分组字段，返回 {table_name: [field_name, ...]}"""
    groups = {}
    for fd in fields:
        table = fd.table_name
        if table not in groups:
            groups[table] = []
        if fd.field_name not in groups[table]:
            groups[table].append(fd.field_name)
    return groups
