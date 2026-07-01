#!/usr/bin/env python3
# SPDX-License-Identifier: NOASSERTION
"""
config_loader.py — Shared configuration loader for ok-cosmic scripts.

Provides shared helpers to:
1. Locate and parse ``ok-cosmic.json``
2. Validate Step 0 required content
3. Inject resolved config path metadata for downstream scripts
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Windows console encoding fix (shared by all scripts)
if os.name == "nt":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


Issue = Dict[str, str]


def resolve_project_config_path(config_path: Optional[str] = None) -> Path:
    """Resolve ``ok-cosmic.json`` path from CLI input or current working directory."""
    return Path(config_path).expanduser() if config_path else Path.cwd() / "ok-cosmic.json"


def read_project_config(config_path: Optional[str] = None) -> Tuple[Path, Dict[str, Any]]:
    """
    Read and parse ``ok-cosmic.json`` without mutating the payload.

    Returns:
    - resolved absolute config path
    - raw JSON object as dict
    """
    target_path = resolve_project_config_path(config_path)

    if not target_path.is_file():
        raise FileNotFoundError(
            f"找不到配置文件: {target_path}。请确保文件存在或通过 --config 参数指定正确路径。"
        )

    try:
        with target_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"加载配置文件 {target_path} 失败: JSON 解析错误，第 {e.lineno} 行第 {e.colno} 列: {e.msg}"
        ) from e
    except Exception as e:
        raise RuntimeError(f"加载配置文件 {target_path} 失败: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"配置文件格式错误: {target_path} 必须包含有效的 JSON 对象")

    return target_path.resolve(), data


def _add_issue(issues: List[Issue], level: str, key: str, message: str) -> None:
    issues.append({"level": level, "key": key, "message": message})


def _is_positive_number(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _resolve_child_path(base_dir: Path, raw_path: str) -> Path:
    expanded = Path(os.path.expanduser(raw_path))
    if expanded.is_absolute():
        return expanded.resolve()
    return (base_dir / expanded).resolve()


def validate_project_config(config: Dict[str, Any], config_path: Optional[str] = None) -> List[Issue]:
    """
    Validate ``ok-cosmic.json`` content for Step 0 preflight.

    Validation levels:
    - ERROR: should stop before running skill scripts
    - WARNING: non-blocking but means some capabilities are unavailable
    """
    issues: List[Issue] = []
    raw_config_path = config_path or str(config.get("__config_path__", "")).strip()
    base_dir = (
        Path(raw_config_path).expanduser().resolve().parent
        if raw_config_path
        else Path.cwd()
    )

    graph_config = config.get("graph")
    if graph_config is None:
        _add_issue(issues, "ERROR", "graph", "缺少 `graph` 配置对象。")
    elif not isinstance(graph_config, dict):
        _add_issue(issues, "ERROR", "graph", "`graph` 必须是 JSON 对象。")
    else:
        db_path = str(graph_config.get("dbPath", "")).strip()
        if not db_path:
            _add_issue(issues, "ERROR", "graph.dbPath", "缺少必填项 `graph.dbPath`。")
        else:
            resolved_db_path = _resolve_child_path(base_dir, db_path)
            if not resolved_db_path.exists():
                _add_issue(
                    issues,
                    "WARNING",
                    "graph.dbPath",
                    f"`graph.dbPath` 指向的文件不存在: {resolved_db_path}",
                )

    meta_config = config.get("meta")
    if meta_config is None:
        _add_issue(issues, "WARNING", "meta", "缺少 `meta` 配置节，元数据在线查询将不可用。")
    elif not isinstance(meta_config, dict):
        _add_issue(issues, "ERROR", "meta", "`meta` 必须是 JSON 对象。")
    else:
        if not str(meta_config.get("apiUrl", "")).strip():
            _add_issue(
                issues,
                "WARNING",
                "meta.apiUrl",
                "`meta.apiUrl` 为空，`cosmic-form-metadata.py` 发生缓存未命中时将无法在线查询。",
            )
        if "timeoutSeconds" in meta_config and not _is_positive_number(meta_config.get("timeoutSeconds")):
            _add_issue(
                issues,
                "ERROR",
                "meta.timeoutSeconds",
                "`meta.timeoutSeconds` 必须是大于 0 的数字。",
            )

    basedata_section_names = ("basedata", "basedataQuery", "runtimeQueryOne")
    seen_basedata_section = False
    basedata_api_url = ""
    for section_name in basedata_section_names:
        section = config.get(section_name)
        if section is None:
            continue
        seen_basedata_section = True
        if not isinstance(section, dict):
            _add_issue(issues, "ERROR", section_name, f"`{section_name}` 必须是 JSON 对象。")
            continue
        if not basedata_api_url:
            basedata_api_url = str(section.get("apiUrl", "")).strip()
        if "timeoutSeconds" in section and not _is_positive_number(section.get("timeoutSeconds")):
            _add_issue(
                issues,
                "ERROR",
                f"{section_name}.timeoutSeconds",
                f"`{section_name}.timeoutSeconds` 必须是大于 0 的数字。",
            )

    if not seen_basedata_section:
        _add_issue(
            issues,
            "WARNING",
            "basedata",
            "缺少 `basedata` / `basedataQuery` / `runtimeQueryOne` 配置节，基础资料在线查询将依赖环境变量。",
        )
    elif not basedata_api_url and not (
        os.getenv("COSMIC_BASEDATA_QUERY_API") or os.getenv("COSMIC_RUNTIME_QUERY_ONE_API")
    ):
        _add_issue(
            issues,
            "WARNING",
            "basedata.apiUrl",
            "`basedata.apiUrl` 为空，且未检测到基础资料查询环境变量，`cosmic-basedata-query.py` 将无法在线查询。",
        )

    return issues


def load_project_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load project-level config from provided path or current working directory.

    Returns a dict with two injected keys for downstream consumers:
    - ``__config_path__``: absolute path to the resolved config file
    - ``__config_dir__``: absolute path to the parent directory of the config file
    """
    resolved, data = read_project_config(config_path)
    data.setdefault("__config_path__", str(resolved))
    data.setdefault("__config_dir__", str(resolved.parent))
    return data
