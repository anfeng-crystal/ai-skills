"""数据模型 - 数据库连接配置"""

from dataclasses import dataclass


@dataclass
class DBConfig:
    """数据库连接配置"""
    host: str
    port: int
    database: str
    username: str
    password: str
    db_type: str = "postgresql"  # postgresql, mysql, oracle, sqlserver
