"""Failure boundaries for the legacy CLI; library callers keep their contracts."""
import sys


def _error_kind(error):
    """Configuration and filesystem exception messages may include private data."""
    code = getattr(error, "errno", None)
    return type(error).__name__ + (f", errno={code}" if code is not None else "")


def report_cli_error(stage, error):
    print(f"错误: {stage} ({_error_kind(error)})", file=sys.stderr)


def load_cli_environment(loader, env_file):
    try:
        loader(env_file)
        return True
    except (OSError, UnicodeError, ValueError) as error:
        report_cli_error("环境配置加载失败", error)
        return False


def record_cli_search(logger_factory, args, results, elapsed, logger):
    """A diagnostic file is optional; disk failure must not discard search output."""
    metadata = {
        "response_time": elapsed,
        "status": "success" if results["summary"]["successful"] > 0 else "failed",
        "total_platforms": results["summary"]["total_platforms"],
        "successful_platforms": results["summary"]["successful"],
        "failed_platforms": results["summary"]["failed"],
        "total_items": results["summary"]["total_items"],
        "platform_details": [
            {
                "platform": platform,
                "status": "success" if result.get("success") else "failed",
                "items": result.get("total", 0),
                "timing_ms": result.get("timing_ms", 0),
                "error": result.get("error"),
            }
            for platform, result in results["results"].items()
        ],
    }
    try:
        search_logger = logger_factory(verbose=args.verbose)
        log_filepath = search_logger.log_union_search(
            query=args.keyword, results=results["final_items"], metadata=metadata)
    except OSError as error:
        print(f"警告: 搜索日志未保存 ({_error_kind(error)})；搜索结果继续输出", file=sys.stderr)
        return
    logger.info(f"搜索日志已保存到: {log_filepath}")
