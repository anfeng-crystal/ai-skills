#!/usr/bin/env python3
"""Legacy text CLI parsing; validation precedes credentials, logs and backends.

Keep this boundary separate from the search library: image/download commands and
library callers retain their own limit contracts.
"""
import argparse


def positive_integer(value: str) -> int:
    """Reject invalid CLI numbers with argparse's standard usage exit (2)."""
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def parse_args(platform_groups, version):
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Union Search - 统一多平台搜索",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 默认搜索无 API Key 快速组
  python union_search.py "machine learning"

  # 已有费用授权时显式搜索所有平台
  python union_search.py "machine learning" --group all

  # 搜索指定平台
  python union_search.py "Python" --platforms github reddit

  # 搜索平台组
  python union_search.py "AI" --group dev

  # 自定义每个平台返回数量
  python union_search.py "深度学习" --limit 5

  # JSON 输出
  python union_search.py "React" --json --pretty

  # 保存结果
  python union_search.py "Vue" -o results.json

  # URL转Markdown
  python union_search.py --read-url "https://example.com"
  python union_search.py --read-url "https://github.com" --read-timeout 60 --json
        """
    )

    parser.add_argument("keyword", nargs="?", help="搜索关键词")
    parser.add_argument(
        "--platforms", "-p",
        nargs="+",
        help="指定平台列表（空格分隔）"
    )
    parser.add_argument(
        "--group", "-g",
        choices=list(platform_groups.keys()),
        help="使用预定义平台组（未指定来源时默认 no_api_key_fast）"
    )
    parser.add_argument(
        "--limit", "-l",
        type=positive_integer,
        default=None,
        help="每个平台返回结果数量，须为正整数 (默认: 使用各平台自身默认值)"
    )
    parser.add_argument(
        "--max-workers",
        type=positive_integer,
        default=5,
        help="最大并发数，须为正整数（默认: 5）"
    )
    parser.add_argument(
        "--timeout",
        type=positive_integer,
        default=60,
        help="超时时间（正整数秒，默认: 60）"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON 格式输出"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="格式化 JSON 输出"
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Markdown 格式输出（默认）"
    )
    parser.add_argument(
        "-o", "--output",
        help="保存输出到文件"
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="环境变量文件路径"
    )
    parser.add_argument(
        "--list-platforms",
        action="store_true",
        help="列出所有可用平台"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细日志"
    )
    parser.add_argument(
        "--deduplicate",
        action="store_true",
        help="启用跨平台结果去重（按标题或链接）"
    )
    parser.add_argument(
        "--read-url",
        metavar="URL",
        help="将指定URL转换为Markdown内容（基于Jina AI Reader API）"
    )
    parser.add_argument(
        "--read-timeout",
        type=positive_integer,
        default=30,
        help="URL读取超时时间（正整数秒，默认: 30）"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Union Search v{version}",
        help="显示版本信息"
    )

    return parser.parse_args()
