"""CLI 命令行入口 - 通过命令行参数生成 SQL 脚本或启动 Web 服务

用法：
  python -m ksql_script_generator.scripts.cli generate --type coderule --entity bd_supplier
  python -m ksql_script_generator.scripts.cli generate --type perm --number QXX0114,QXX0115
  python -m ksql_script_generator.scripts.cli generate --type coderule --entity bd_supplier -o output.sql
  python -m ksql_script_generator.scripts.cli serve
  python -m ksql_script_generator.scripts.cli serve --config /path/to/config.ini
"""

import argparse
import logging
import sys
from pathlib import Path

# 获取当前脚本所在目录（如 skills/your_skill/scripts/）
SCRIPT_DIR = Path(__file__).parent
# 将根目录加入搜索路径
sys.path.append(str(SCRIPT_DIR))
sys.path.append(str(SCRIPT_DIR.parent)) # 通常需3级返回：scripts → skill_dir → skills → root


from config_manager import ConfigManager
from script_generator import ScriptGenerator
from type_handler import TypeHandler, SUPPORTED_TYPES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def cmd_generate(args):
    """执行 generate 子命令"""
    type_name = args.type
    if type_name not in SUPPORTED_TYPES:
        supported = ", ".join(SUPPORTED_TYPES)
        print(f"错误：不支持的类型 '{type_name}'，支持的类型: {supported}", file=sys.stderr)
        sys.exit(1)

    cm = ConfigManager(args.config)
    cm.load()
    db_configs = cm.get_all_db_configs()

    generator = ScriptGenerator()
    handler = TypeHandler(generator, db_configs)

    params = {}
    if args.entity:
        params["entity"] = args.entity
    if args.number:
        params["number"] = args.number
    if args.filter:
        params["filter"] = args.filter

    try:
        script = handler.dispatch(type_name, params)
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(script, encoding="utf-8")
        print(f"脚本已写入: {output_path}")
    else:
        print(script)


def cmd_serve(args):
    """执行 serve 子命令"""
    from main import main as start_server
    start_server(args.config)


def main():
    """CLI 主入口"""
    parser = argparse.ArgumentParser(
        description="SQL脚本生成器 - 从数据库查询数据并生成 INSERT INTO 脚本"
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # generate 子命令
    gen_parser = subparsers.add_parser("generate", help="生成 SQL 脚本")
    gen_parser.add_argument("--type", "-t", required=True,
                            help=f"脚本类型: {', '.join(SUPPORTED_TYPES)}")
    gen_parser.add_argument("--entity", "-e", default="",
                            help="实体编码（coderule/import/event/basedata 类型使用）")
    gen_parser.add_argument("--number", "-n", default="",
                            help="编码列表，逗号分隔（perm/schdule/openapi 类型使用）")
    gen_parser.add_argument("--filter", "-f", default="",
                            help="自定义过滤条件（basedata 类型使用，如 fnumber in ('CNY','USD')）")
    gen_parser.add_argument("--output", "-o", default="",
                            help="输出文件路径，不指定则输出到控制台")
    gen_parser.add_argument("--config", "-c", default=None,
                            help="配置文件路径，默认使用模块目录下的 config.ini")

    # serve 子命令
    serve_parser = subparsers.add_parser("serve", help="启动 Web 服务")
    serve_parser.add_argument("--config", "-c", default=None,
                              help="配置文件路径，默认使用模块目录下的 config.ini")

    args = parser.parse_args()

    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "serve":
        cmd_serve(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
