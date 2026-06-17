"""核心脚本生成器 - 执行 SQL 查询并生成 INSERT INTO 语句"""

import logging
from datetime import datetime, date
from decimal import Decimal
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


class ScriptGenerator:
    """SQL INSERT 脚本生成器"""

    def generate(self, db_config: DBConfig, table: str,
                 fields: str, where: str = "",
                 pk_field: str = "", pk_index: int = -1,
                 extra_delete_fields: list = None) -> str:
        """
        核心方法：查询数据库并生成脚本。

        当 pk_field 非空时，为每行生成 DELETE + INSERT 交替脚本；
        否则只生成 INSERT 脚本。

        Args:
            db_config: 数据库连接配置
            table: 目标表名
            fields: 逗号分隔的字段列表字符串
            where: WHERE 过滤条件（不含 WHERE 关键字）
            pk_field: 主键字段名，用于生成 DELETE 语句
            pk_index: 主键字段在 field_list 中的索引，-1 表示自动查找
            extra_delete_fields: 额外的 DELETE WHERE 条件字段列表，
                                 如 ["FID"] 则 DELETE 语句变为
                                 DELETE FROM t WHERE pk=v AND FID=fid_val

        Returns:
            生成的 SQL 脚本文本。空结果集返回空字符串。
        """
        field_list = self._parse_fields(fields)
        sql = self._build_select_sql(table, field_list, where)

        try:
            conn = get_connection(db_config)
        except Exception as e:
            msg = f"数据库连接失败 [{db_config.database}]: {e}"
            logger.error(msg)
            raise ConnectionError(msg) from e

        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()

            if not rows:
                logger.info("表 %s 查询无数据 (条件: %s)", table, where or "无")
                return ""

            # 如果用 * 查询，从 cursor.description 获取实际字段名
            if field_list == ["*"] and cursor.description:
                field_list = [desc[0] for desc in cursor.description]

            col_types = (
                [desc[1] for desc in cursor.description]
                if cursor.description
                else [None] * len(field_list)
            )

            # 确定主键在字段列表中的位置
            actual_pk_index = pk_index
            if pk_field and actual_pk_index < 0:
                upper_fields = [f.upper() for f in field_list]
                pk_upper = pk_field.upper()
                if pk_upper in upper_fields:
                    actual_pk_index = upper_fields.index(pk_upper)

            # 确定额外 DELETE 条件字段的索引
            extra_indices = []
            if extra_delete_fields:
                upper_fields = [f.upper() for f in field_list]
                for ef in extra_delete_fields:
                    ef_upper = ef.upper()
                    if ef_upper in upper_fields:
                        extra_indices.append((ef, upper_fields.index(ef_upper)))

            results = []
            for row in rows:
                values = []
                for i, val in enumerate(row):
                    values.append(self._format_value(
                        val, col_types[i] if i < len(col_types) else None
                    ))

                # 生成 DELETE（如果指定了主键字段）
                if pk_field and actual_pk_index >= 0 and actual_pk_index < len(row):
                    pk_val = self._format_value(row[actual_pk_index])
                    delete_where = f"{pk_field} = {pk_val}"
                    # 追加额外条件
                    for ef_name, ef_idx in extra_indices:
                        if ef_idx < len(row):
                            ef_val = self._format_value(row[ef_idx])
                            delete_where += f" AND {ef_name} = {ef_val}"
                    results.append(
                        f"DELETE FROM {table} WHERE {delete_where};"
                    )

                results.append(self._build_insert_sql(table, field_list, values))

            return "\n".join(results) + "\n"
        except Exception as e:
            msg = f"查询表 {table} 失败: {e}"
            logger.error(msg)
            raise RuntimeError(msg) from e
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def _parse_fields(fields: str) -> list:
        """解析逗号分隔的字段列表，去除首尾空格"""
        return [f.strip() for f in fields.split(",") if f.strip()]

    @staticmethod
    def _build_select_sql(table: str, field_list: list, where: str) -> str:
        """构造 SELECT 查询语句"""
        fields_str = ", ".join(field_list)
        sql = f"SELECT {fields_str} FROM {table}"
        if where and where.strip():
            sql += f" WHERE {where.strip()}"
        return sql

    @staticmethod
    def _format_value(value, column_type=None) -> str:
        """
        格式化单个字段值为 SQL 值表达式。

        规则：
        - None → NULL
        - datetime/date → ts{'yyyy-MM-dd HH:mm:ss'}
        - str → '值'（单引号包裹，内部单引号转义）
        - int/float/Decimal → 直接数值
        - 其他 → 转为字符串后单引号包裹
        """
        if value is None:
            return "NULL"

        if isinstance(value, datetime):
            formatted = value.strftime("%Y-%m-%d %H:%M:%S")
            return f"ts{{'{formatted}'}}"

        if isinstance(value, date):
            formatted = value.strftime("%Y-%m-%d") + " 00:00:00"
            return f"ts{{'{formatted}'}}"

        if isinstance(value, bool):
            return "1" if value else "0"

        if isinstance(value, (int, float, Decimal)):
            return str(value)

        # 字符串类型：转义内部单引号
        s = str(value).replace("'", "''")
        return f"'{s}'"

    @staticmethod
    def _build_insert_sql(table: str, field_list: list, values: list) -> str:
        """构造单条 INSERT INTO 语句"""
        fields_str = ", ".join(field_list)
        values_str = ", ".join(values)
        return f"INSERT INTO {table} ({fields_str}) VALUES ({values_str});"
