"""数据库连接工厂

支持 PostgreSQL、MySQL、Oracle、SQL Server 四种数据库。
使用统一的 DB-API 2.0 接口，调用方无需关心具体驱动。

驱动安装：
  PostgreSQL: pip install psycopg2-binary
  MySQL:      pip install pymysql
  Oracle:     pip install oracledb
  SQL Server: pip install pymssql
"""

import logging
import sys
from pathlib import Path

# 获取当前脚本所在目录（如 skills/your_skill/scripts/）
SCRIPT_DIR = Path(__file__).parent
# 将根目录加入搜索路径
sys.path.append(str(SCRIPT_DIR))
sys.path.append(str(SCRIPT_DIR.parent)) # 通常需3级返回：scripts → skill_dir → skills → root

from models import DBConfig

logger = logging.getLogger(__name__)


def get_connection(db_config: DBConfig):
    """根据 db_type 创建数据库连接，返回 DB-API 2.0 connection 对象。"""
    db_type = (db_config.db_type or "postgresql").lower().strip()

    if db_type in ("postgresql", "postgres", "pg"):
        return _connect_postgresql(db_config)
    elif db_type in ("mysql",):
        return _connect_mysql(db_config)
    elif db_type in ("oracle",):
        return _connect_oracle(db_config)
    elif db_type in ("sqlserver", "mssql"):
        return _connect_sqlserver(db_config)
    else:
        raise ValueError(f"不支持的数据库类型: {db_type}，支持: postgresql, mysql, oracle, sqlserver")


def _connect_postgresql(cfg: DBConfig):
    import psycopg2
    return psycopg2.connect(
        host=cfg.host, port=cfg.port, database=cfg.database,
        user=cfg.username, password=cfg.password,
    )


def _connect_mysql(cfg: DBConfig):
    import pymysql
    return pymysql.connect(
        host=cfg.host, port=cfg.port, database=cfg.database,
        user=cfg.username, password=cfg.password,
        charset="utf8mb4",
    )


def _connect_oracle(cfg: DBConfig):
    import oracledb
    dsn = f"{cfg.host}:{cfg.port}/{cfg.database}"
    return oracledb.connect(user=cfg.username, password=cfg.password, dsn=dsn)


def _connect_sqlserver(cfg: DBConfig):
    import pymssql
    return pymssql.connect(
        server=cfg.host, port=cfg.port, database=cfg.database,
        user=cfg.username, password=cfg.password,
        charset="utf8",
    )
