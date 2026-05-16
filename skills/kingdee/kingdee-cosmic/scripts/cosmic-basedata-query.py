#!/usr/bin/env python3
# SPDX-License-Identifier: NOASSERTION
"""
cosmic-basedata-query.py — Cosmic base data query and cache tool.

Usage:
    python3 cosmic-basedata-query.py --config ok-cosmic.json get --entity-id bd_supplier
    python3 cosmic-basedata-query.py --config ok-cosmic.json get --entity-id bd_supplier --number-or-name 1001
    python3 cosmic-basedata-query.py --config ok-cosmic.json get --entity-id bd_supplier --number-or-name 华东 --full
    python3 cosmic-basedata-query.py --config ok-cosmic.json get --entity-id bd_supplier --refresh
    python3 cosmic-basedata-query.py --config ok-cosmic.json get --entity-id bd_supplier --json

What it provides:
1. Query one base data result by entityId plus number/name keyword
2. Local SQLite cache in a dedicated table with a fixed 10-minute TTL
3. Config-first API resolution with environment-variable fallback
4. Human-readable summary output with optional JSON mode

What it does NOT do:
- It does not infer entityId from Chinese labels or form field names
- It only accepts entityId that is already confirmed by the user or by the metadata script
- It does not auto-query metadata; when entityId is unknown, query metadata for refType or look up the real English identifier by Chinese name first
- It does not batch query multiple entityIds in one request

Prerequisites:
- A valid ok-cosmic.json or equivalent project config
- A configured graph.dbPath for SQLite cache storage
- A reachable basedata query API configured by config or environment
"""

import argparse
import json
import os
import sqlite3
import ssl
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from config_loader import load_project_config


CACHE_TTL_SECONDS = 600
TABLE_NAME = "basedata_query_cache"


def contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


class BaseDataDbCache:
    def __init__(self, db_path: str, ttl: int = CACHE_TTL_SECONDS):
        self.db_path = db_path
        self.ttl = ttl
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                        cache_key TEXT PRIMARY KEY,
                        entity_id TEXT NOT NULL,
                        number_or_name TEXT NOT NULL,
                        full INTEGER NOT NULL,
                        payload TEXT NOT NULL,
                        updated_at INTEGER NOT NULL
                    )
                """)
        except Exception as e:
            print(f" (DEBUG) 初始化基础资料缓存表失败: {e}", file=sys.stderr)

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    f"SELECT payload, updated_at FROM {TABLE_NAME} WHERE cache_key = ?",
                    (cache_key,),
                ).fetchone()
                if not row or (time.time() - row["updated_at"] > self.ttl):
                    return None
                return json.loads(row["payload"])
        except Exception:
            return None

    def set(
        self,
        cache_key: str,
        entity_id: str,
        number_or_name: str,
        full: bool,
        payload: Dict[str, Any],
    ):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {TABLE_NAME}
                    (cache_key, entity_id, number_or_name, full, payload, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cache_key,
                        entity_id,
                        number_or_name,
                        1 if full else 0,
                        json.dumps(payload, ensure_ascii=False),
                        int(time.time()),
                    ),
                )
        except Exception as e:
            print(f" (DEBUG) 写入基础资料缓存失败: {e}", file=sys.stderr)

    def remove(self, cache_key: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(f"DELETE FROM {TABLE_NAME} WHERE cache_key = ?", (cache_key,))
        except Exception:
            pass


class BaseDataQuery:
    def __init__(self, config: Dict[str, Any], debug: bool = False):
        self.debug = debug
        self.config_dir = str(config.get("__config_dir__", "")).strip()

        graph_config = config.get("graph", {})
        if not isinstance(graph_config, dict):
            graph_config = {}

        basedata_config = self._resolve_basedata_config(config)
        db_path = str(graph_config.get("dbPath", "")).strip()
        if not db_path:
            raise ValueError("未配置 graph.dbPath，请在 ok-cosmic.json 中指定 SQLite 数据库路径。")

        raw_db_path = os.path.expanduser(db_path)
        if os.path.isabs(raw_db_path):
            self.db_path = os.path.normpath(raw_db_path)
        else:
            base_dir = self.config_dir or os.getcwd()
            self.db_path = os.path.normpath(os.path.abspath(os.path.join(base_dir, raw_db_path)))

        self.cache = BaseDataDbCache(self.db_path, ttl=CACHE_TTL_SECONDS)
        self.api_url = str(
            basedata_config.get("apiUrl")
            or os.getenv("COSMIC_BASEDATA_QUERY_API")
            or os.getenv("COSMIC_RUNTIME_QUERY_ONE_API")
            or ""
        ).strip()
        self.api_token = str(
            basedata_config.get("apiToken")
            or basedata_config.get("token")
            or os.getenv("COSMIC_BASEDATA_QUERY_TOKEN")
            or os.getenv("COSMIC_RUNTIME_QUERY_ONE_TOKEN")
            or os.getenv("COSMIC_META_TOKEN", "")
        ).strip()
        self.timeout = float(
            basedata_config.get("timeoutSeconds")
            or os.getenv("COSMIC_BASEDATA_QUERY_TIMEOUT")
            or os.getenv("COSMIC_RUNTIME_QUERY_ONE_TIMEOUT")
            or os.getenv("COSMIC_META_TIMEOUT")
            or 8
        )

        skip_ssl_verify = basedata_config.get("skipSslVerify")
        if skip_ssl_verify is None:
            meta_config = config.get("meta", {})
            if isinstance(meta_config, dict) and meta_config.get("skipSslVerify") is not None:
                skip_ssl_verify = meta_config.get("skipSslVerify")
            else:
                skip_ssl_verify = True
        self.skip_ssl_verify = bool(skip_ssl_verify)

    @staticmethod
    def _resolve_basedata_config(config: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        for key in ("runtimeQueryOne", "basedataQuery", "basedata"):
            section = config.get(key)
            if isinstance(section, dict):
                merged.update(section)
        return merged

    def _log_debug(self, msg: str):
        if self.debug:
            print(f" (DEBUG) {msg}", file=sys.stderr)

    @staticmethod
    def _cache_key(entity_id: str, number_or_name: str, full: bool) -> str:
        return f"{entity_id}|{number_or_name}|{1 if full else 0}"

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_url:
            raise RuntimeError(
                "未配置基础资料查询 API。请在 ok-cosmic.json 的 basedata.apiUrl / basedataQuery.apiUrl / "
                "runtimeQueryOne.apiUrl 中配置，或设置 COSMIC_BASEDATA_QUERY_API / "
                "COSMIC_RUNTIME_QUERY_ONE_API 环境变量。"
            )

        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        req_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.api_url,
            data=req_body,
            headers=headers,
            method="POST",
        )

        try:
            ssl_context = ssl.create_default_context()
            if self.skip_ssl_verify:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=self.timeout, context=ssl_context) as resp:
                raw = json.loads(resp.read().decode("utf-8", errors="replace"))
            if not isinstance(raw, dict):
                raise RuntimeError("远程接口返回的根对象不是 JSON Object。")
            return raw
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace").strip()
            detail_part = f": {detail}" if detail else ""
            raise RuntimeError(f"HTTP {e.code}{detail_part}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"响应 JSON 解析失败: {e}")
        except Exception as e:
            raise RuntimeError(f"Network error: {e}")

    @staticmethod
    def _normalize_result(
        raw: Dict[str, Any],
        entity_id: str,
        number_or_name: str,
        full: bool,
    ) -> Dict[str, Any]:
        payload_data = raw.get("data")
        if not isinstance(payload_data, dict):
            return {
                "entityId": entity_id,
                "numberOrName": number_or_name,
                "full": full,
                "traceId": None,
                "data": payload_data,
            }

        return {
            "entityId": payload_data.get("entityId", entity_id),
            "numberOrName": payload_data.get("numberOrName", number_or_name),
            "full": bool(payload_data.get("full", full)),
            "traceId": payload_data.get("traceId"),
            "data": payload_data.get("data"),
        }

    def query_one(self, entity_id: str, number_or_name: str = "", full: bool = False) -> Dict[str, Any]:
        normalized_entity_id = (entity_id or "").strip()
        normalized_keyword = (number_or_name or "").strip()
        normalized_full = bool(full)

        if not normalized_entity_id:
            raise ValueError(
                "entityId 不能为空。只允许使用用户明确给出的准确英文标识或元数据脚本确认出的真实标识；如不清楚，请先用元数据脚本查 refType 或按中文名称查英文标识。"
            )
        if contains_cjk(normalized_entity_id):
            raise ValueError(
                "entityId 必须是已确认的英文基础资料标识；只允许使用用户明确给出的准确英文标识或元数据脚本确认出的真实标识，不能直接传中文名称。"
            )

        cache_key = self._cache_key(normalized_entity_id, normalized_keyword, normalized_full)
        cached = self.cache.get(cache_key)
        if cached:
            self._log_debug(f"命中基础资料缓存: {cache_key}")
            return {"status": "ok", "source": "cache", **cached}

        payload = {
            "data": {
                "entityId": normalized_entity_id,
                "numberOrName": normalized_keyword,
                "full": normalized_full,
            }
        }
        raw = self._post(payload)

        if raw.get("status") is False:
            message = str(raw.get("message") or "remote api status=false")
            error_code = raw.get("errorCode")
            if " is not exist" in message:
                return {
                    "status": "not_found",
                    "message": message,
                    "errorCode": error_code,
                    "entityId": normalized_entity_id,
                    "numberOrName": normalized_keyword,
                    "full": normalized_full,
                }
            raise RuntimeError(f"{message} (errorCode={error_code})")

        result = self._normalize_result(raw, normalized_entity_id, normalized_keyword, normalized_full)
        self.cache.set(cache_key, normalized_entity_id, normalized_keyword, normalized_full, result)
        return {"status": "ok", "source": "api", **result}

    def refresh(self, entity_id: str, number_or_name: str = "", full: bool = False):
        cache_key = self._cache_key((entity_id or "").strip(), (number_or_name or "").strip(), bool(full))
        self.cache.remove(cache_key)

    @staticmethod
    def _maybe_render_mapping_table(data: Any) -> List[str]:
        if not isinstance(data, list) or not data:
            return []

        rows: List[Dict[str, str]] = []
        for item in data:
            if not isinstance(item, dict):
                return []
            number = item.get("number") or item.get("Number") or item.get("code") or item.get("Code")
            name = item.get("name") or item.get("Name")
            item_id = item.get("id") or item.get("Id") or item.get("pkId") or item.get("masterId")
            if number is None and name is None and item_id is None:
                return []
            rows.append(
                {
                    "number": str(number or "-"),
                    "name": str(name or "-"),
                    "id": str(item_id or "-"),
                }
            )

        md = [
            "### 📑 编码名称映射",
            "| 编码 | 名称 | ID |",
            "| :--- | :--- | :--- |",
        ]
        for row in rows:
            md.append(f"| `{row['number']}` | {row['name']} | `{row['id']}` |")
        return md

    def render(self, result: Dict[str, Any], json_mode: bool = False) -> str:
        if json_mode:
            return json.dumps(result, ensure_ascii=False, indent=2)

        status = result.get("status")
        if status == "not_found":
            message = str(result.get("message") or "未找到基础资料")
            error_code = result.get("errorCode")
            lines = [
                "## ❌ 未找到基础资料",
                f"**基础资料标识**: `{result.get('entityId') or '-'}`",
                f"**查询词**: `{result.get('numberOrName') or '-'}`",
                f"**完整模式**: `{bool(result.get('full'))}`",
                f"**说明**: {message}",
            ]
            if error_code is not None:
                lines.append(f"**错误码**: `{error_code}`")
            return "\n".join(lines)

        lines = [
            f"## 📦 基础资料: `{result.get('entityId') or '-'}`",
            f"**查询词**: `{result.get('numberOrName') or '(空，通常返回前50条映射)'}`",
            f"**完整模式**: `{bool(result.get('full'))}`",
            f"**结果来源**: `{result.get('source') or '-'}`",
        ]

        trace_id = result.get("traceId")
        if trace_id:
            lines.append(f"**traceId**: `{trace_id}`")

        data = result.get("data")
        mapping_table = self._maybe_render_mapping_table(data)
        if mapping_table:
            lines.append("")
            lines.extend(mapping_table)
        else:
            lines.append("\n### 📄 返回数据")
            lines.append("```json")
            lines.append(json.dumps(data, ensure_ascii=False, indent=2))
            lines.append("```")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Cosmic BaseData Query CLI")
    parser.add_argument("--config", help="Path to ok-cosmic.json")
    parser.add_argument("--debug", action="store_true")

    sub_parser = parser.add_subparsers(dest="command")
    get_parser = sub_parser.add_parser("get")
    get_parser.add_argument(
        "--entity-id",
        required=True,
        help="基础资料标识（英文 entityId，且来源必须已确认；不确定时先用元数据脚本查 refType 或按中文名称查英文标识）",
    )
    get_parser.add_argument("--number-or-name", default="", help="编码或名称；为空时通常返回前50条映射")
    get_parser.add_argument("--keyword", dest="number_or_name", help="--number-or-name 的别名")
    get_parser.add_argument("--full", action="store_true", help="返回完整字段")
    get_parser.add_argument("--json", action="store_true", help="直接输出 JSON")
    get_parser.add_argument("--refresh", action="store_true", help="删除当前查询条件对应的本地缓存后再请求")
    get_parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    if args.command != "get":
        parser.print_help()
        return

    try:
        config = load_project_config(args.config)
        query = BaseDataQuery(config, debug=(args.debug or getattr(args, "debug", False)))
        if args.refresh:
            query.refresh(args.entity_id, args.number_or_name, args.full)
        result = query.query_one(args.entity_id, args.number_or_name, args.full)
        print(query.render(result, json_mode=args.json))
    except Exception as e:
        print(f"❌ 错误: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
