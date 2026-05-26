"""配置管理器 - 从 INI 配置文件读取数据库连接信息

配置格式：[database] 节包含公共连接参数和三个库的数据库名。
三个库共用 host/port/username/password/db_type，只有 database 名各自不同。
"""

import configparser
import logging
from pathlib import Path
from models import DBConfig
import sys

# 获取当前脚本所在目录（如 skills/your_skill/scripts/）
SCRIPT_DIR = Path(__file__).parent
# 将根目录加入搜索路径
sys.path.append(str(SCRIPT_DIR))
sys.path.append(str(SCRIPT_DIR.parent)) # 通常需3级返回：scripts → skill_dir → skills → root


logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = Path(__file__).parent.parent / "config.ini"


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_path: str = None):
        self._config_path = config_path or str(_DEFAULT_CONFIG)
        self._parser = configparser.ConfigParser()
        self._loaded = False

    def load(self) -> dict:
        path = Path(self._config_path)
        if not path.exists():
            logger.warning("配置文件不存在: %s，将使用默认值", self._config_path)
            self._loaded = True
            return {}
        self._parser.read(str(path), encoding="utf-8")
        self._loaded = True
        return {s: dict(self._parser[s]) for s in self._parser.sections()}

    def _ensure_loaded(self):
        if not self._loaded:
            self.load()

    def _get_section(self, section: str) -> dict:
        self._ensure_loaded()
        if self._parser.has_section(section):
            return dict(self._parser[section])
        return {}

    def _get_common_params(self) -> dict:
        """获取公共连接参数"""
        db = self._get_section("database")
        return {
            "host": db.get("host", "localhost"),
            "port": int(db.get("port", "5432")),
            "username": db.get("username", ""),
            "password": db.get("password", ""),
            "db_type": db.get("db_type", "postgresql"),
        }

    def _build_db_config(self, db_name_key: str) -> DBConfig:
        """用公共参数 + 指定的数据库名构建 DBConfig"""
        common = self._get_common_params()
        db = self._get_section("database")
        database = db.get(db_name_key, "") or db.get("meta_database", "")
        return DBConfig(
            host=common["host"],
            port=common["port"],
            database=database,
            username=common["username"],
            password=common["password"],
            db_type=common["db_type"],
        )

    def get_meta_db_config(self) -> DBConfig:
        return self._build_db_config("meta_database")

    def get_sys_db_config(self) -> DBConfig:
        return self._build_db_config("sys_database")

    def get_workflow_db_config(self) -> DBConfig:
        return self._build_db_config("workflow_database")

    def get_biz_db_config(self) -> DBConfig:
        return self._build_db_config("biz_database")

    def get_server_config(self) -> dict:
        self._ensure_loaded()
        section = self._get_section("server")
        return {
            "host": section.get("host", "localhost"),
            "port": int(section.get("port", "8089")),
        }

    def get_all_db_configs(self) -> dict:
        return {
            "meta": self.get_meta_db_config(),
            "sys": self.get_sys_db_config(),
            "workflow": self.get_workflow_db_config(),
            "biz": self.get_biz_db_config(),
        }

    def to_form_defaults(self) -> dict:
        """将配置转换为 Web 表单默认值字典"""
        common = self._get_common_params()
        db = self._get_section("database")
        return {
            "db_type": common["db_type"],
            "host": common["host"],
            "port": str(common["port"]),
            "username": common["username"],
            "password": common["password"],
            "meta_database": db.get("meta_database", ""),
            "sys_database": db.get("sys_database", ""),
            "workflow_database": db.get("workflow_database", ""),
            "biz_database": db.get("biz_database", ""),
        }
