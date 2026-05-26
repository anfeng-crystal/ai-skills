"""Web 服务启动入口"""

import logging
import sys
from pathlib import Path

# 获取当前脚本所在目录（如 skills/your_skill/scripts/）
SCRIPT_DIR = Path(__file__).parent
# 将根目录加入搜索路径
sys.path.append(str(SCRIPT_DIR))
sys.path.append(str(SCRIPT_DIR.parent)) # 通常需3级返回：scripts → skill_dir → skills → root

from config_manager import ConfigManager
from web_server import SqlScriptRequestHandler, SqlScriptWebServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main(config_path: str = None):
    """启动 Web 服务"""
    cm = ConfigManager(config_path)
    cm.load()

    SqlScriptRequestHandler.default_config = cm.to_form_defaults()
    SqlScriptRequestHandler.config_manager = cm

    server_cfg = cm.get_server_config()
    server = SqlScriptWebServer(server_cfg["host"], server_cfg["port"])
    server.start()


if __name__ == "__main__":
    config = sys.argv[1] if len(sys.argv) > 1 else None
    main(config)
