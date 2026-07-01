#!/usr/bin/env python3
# SPDX-License-Identifier: NOASSERTION
"""
cosmic-form-metadata.py — Cosmic form metadata query and cache tool.

Usage:
    python3 cosmic-form-metadata.py --config ok-cosmic.json get --form-id <formId>
    python3 cosmic-form-metadata.py --config ok-cosmic.json get --bill-name <billName>
    python3 cosmic-form-metadata.py --config ok-cosmic.json get --form-id <formId> --fuzzy qty price amount
    python3 cosmic-form-metadata.py --config ok-cosmic.json get --form-id <formId> --fuzzy "组织 物料 批号"
    python3 cosmic-form-metadata.py --config ok-cosmic.json get --form-id <formId> --fuzzy "数量|金额"
    python3 cosmic-form-metadata.py --config ok-cosmic.json get --form-id <formId> --fuzzy status --show-detail
    python3 cosmic-form-metadata.py --config ok-cosmic.json get --form-id <formId> --tree
    python3 cosmic-form-metadata.py --config ok-cosmic.json get --form-id <formId> --refresh

What it provides:
1. Form metadata lookup by formId or billName
2. Local SQLite cache for metadata payloads
3. Fuzzy field filtering for keys / names
4. Optional detail mode for enum mappings and reference types

What it does NOT do:
- It does not query the form_metadata_cache table directly for user-facing output semantics
- It does not infer field meaning beyond metadata returned by the configured API
- It does not rebuild the API knowledge graph database

Prerequisites:
- A valid ok-cosmic.json or equivalent meta config
- A reachable COSMIC_META_API / meta.apiUrl endpoint for cache misses
"""

import json
import os
import sys
import argparse
import time
import sqlite3
import re
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from config_loader import load_project_config


class MetadataDbCache:
    def __init__(self, db_path: str, ttl: int = 600):
        self.db_path = db_path
        self.ttl = ttl
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS form_metadata_cache (
                        form_id TEXT PRIMARY KEY,
                        payload TEXT,
                        updated_at INTEGER
                    )
                """)
        except Exception as e:
            print(f" (DEBUG) 初始化数据库失败: {e}", file=sys.stderr)

    def get(self, form_id: str) -> Optional[Dict[str, Any]]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT payload, updated_at FROM form_metadata_cache WHERE form_id = ?",
                    (form_id,)
                ).fetchone()
                if not row or (time.time() - row['updated_at'] > self.ttl):
                    return None
                return json.loads(row['payload'])
        except Exception:
            return None

    def set(self, form_id: str, payload: Dict[str, Any]):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO form_metadata_cache (form_id, payload, updated_at) VALUES (?, ?, ?)",
                    (form_id, json.dumps(payload, ensure_ascii=False), int(time.time()))
                )
        except Exception as e:
            print(f" (DEBUG) 写入数据库失败: {e}", file=sys.stderr)

    def remove(self, form_id: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM form_metadata_cache WHERE form_id = ?", (form_id,))
        except Exception:
            pass


class FormMetadata:
    def __init__(self, config: Dict[str, Any], debug: bool = False):
        self.debug = debug
        self.config_dir = str(config.get("__config_dir__", "")).strip()
        graph_config = config.get("graph", {})
        meta_config = config.get("meta", config)
        db_path = str(graph_config.get("dbPath", "")).strip()
        if not db_path:
            raise ValueError("未配置 graph.dbPath，请在 ok-cosmic.json 中指定数据库全路径")
        raw_db_path = os.path.expanduser(db_path)
        if os.path.isabs(raw_db_path):
            self.db_path = os.path.normpath(raw_db_path)
        else:
            base_dir = self.config_dir or os.getcwd()
            self.db_path = os.path.normpath(os.path.abspath(os.path.join(base_dir, raw_db_path)))
        self.cache = MetadataDbCache(self.db_path)
        self.api_url = str(meta_config.get("apiUrl", "")).strip()
        self.timeout = float(meta_config.get("timeoutSeconds", 15))
        self.skip_ssl_verify = meta_config.get("skipSslVerify", True)

    def _log_debug(self, msg: str):
        if self.debug:
            print(f" (DEBUG) {msg}", file=sys.stderr)

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_url:
            raise RuntimeError("COSMIC_META_API is not configured.")
        req_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.api_url, data=req_body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            ssl_context = ssl.create_default_context()
            if self.skip_ssl_verify:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=self.timeout, context=ssl_context) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as e:
            raise RuntimeError(f"Network error: {e}")

    @staticmethod
    def _normalize_operates(raw_operates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        兼容旧版 `buttons` 与新版 `operateMetas` 结构:
        - buttons: {name, key, ...}
        - operateMetas: {opName, opKey, opType}
        统一输出为: {name, key, type}
        """
        normalized: List[Dict[str, Any]] = []
        for op in raw_operates:
            if not isinstance(op, dict):
                continue
            key = op.get("key") or op.get("opKey")
            name = op.get("name") or op.get("opName")
            op_type = op.get("type") or op.get("opType")
            if not key and not name:
                continue
            normalized.append({
                "name": name or "-",
                "key": key or "-",
                "type": op_type or "-"
            })
        return normalized

    @staticmethod
    def _field_sort_key(field: Dict[str, Any], sort_by: str = "key") -> tuple:
        value = str(field.get(sort_by, "") or "").lower()
        key = str(field.get("key", "") or "").lower()
        name = str(field.get("name", "") or "").lower()
        node_type = str(field.get("type", "") or "").lower()
        db_key = str(field.get("dbKey", "") or "").lower()
        return (value, key, name, node_type, db_key)

    @classmethod
    def _sort_fields(cls, fields: List[Dict[str, Any]], sort_by: str = "key") -> List[Dict[str, Any]]:
        return sorted(fields, key=lambda f: cls._field_sort_key(f, sort_by=sort_by))

    @classmethod
    def _build_tree_lines(
        cls,
        fields: List[Dict[str, Any]],
        filter_patterns: Optional[List[str]] = None,
        sort_by: str = "key"
    ) -> List[str]:
        def is_hit(f: Dict[str, Any]) -> bool:
            if not filter_patterns:
                return True
            target_text = (
                str(f.get("key", ""))
                + "|"
                + str(f.get("name", ""))
                + "|"
                + str(f.get("type", ""))
                + "|"
                + str(f.get("dbKey", ""))
                + "|"
                + str(f.get("refType", ""))
            ).lower()
            for p in filter_patterns:
                try:
                    if re.search(p, target_text, re.IGNORECASE):
                        return True
                except Exception:
                    if p.lower() in target_text:
                        return True
            return False

        by_key: Dict[str, Dict[str, Any]] = {}
        for f in fields:
            key = str(f.get("key", "")).strip()
            if key and key not in by_key:
                by_key[key] = f

        if not by_key:
            return []

        children: Dict[Optional[str], List[str]] = {}
        for k, f in by_key.items():
            parent = f.get("parentKey")
            parent_key = str(parent).strip() if parent is not None else None
            if parent_key == "":
                parent_key = None
            children.setdefault(parent_key, []).append(k)

        for parent_key, ks in children.items():
            children[parent_key] = sorted(
                ks,
                key=lambda k: cls._field_sort_key(by_key.get(k, {}), sort_by=sort_by)
            )

        include_keys = set(by_key.keys())
        if filter_patterns:
            include_keys = {k for k, f in by_key.items() if is_hit(f)}
            # 补齐祖先节点，便于阅读路径
            queue = list(include_keys)
            while queue:
                cur = queue.pop()
                parent = by_key.get(cur, {}).get("parentKey")
                parent_key = str(parent).strip() if parent is not None else None
                if parent_key and parent_key in by_key and parent_key not in include_keys:
                    include_keys.add(parent_key)
                    queue.append(parent_key)

        def fmt_node(key: str) -> str:
            f = by_key[key]
            name = f.get("name", "-")
            node_type = f.get("type", "-")
            db_key = f.get("dbKey", "-")
            return f"{name} (`{key}`) [{node_type}] dbKey=`{db_key}`"

        lines: List[str] = []
        visited: set = set()

        def walk(node_key: str, prefix: str, is_last: bool):
            if node_key in visited or node_key not in include_keys:
                return
            visited.add(node_key)
            branch = "`- " if is_last else "|- "
            lines.append(f"{prefix}{branch}{fmt_node(node_key)}")
            child_keys = [ck for ck in children.get(node_key, []) if ck in include_keys]
            for i, ck in enumerate(child_keys):
                next_prefix = prefix + ("   " if is_last else "|  ")
                walk(ck, next_prefix, i == len(child_keys) - 1)

        roots = []
        for k in sorted(include_keys, key=lambda x: cls._field_sort_key(by_key.get(x, {}), sort_by=sort_by)):
            parent = by_key.get(k, {}).get("parentKey")
            parent_key = str(parent).strip() if parent is not None else None
            if not parent_key or parent_key not in include_keys:
                roots.append(k)

        roots = sorted(set(roots), key=lambda x: cls._field_sort_key(by_key.get(x, {}), sort_by=sort_by))
        for i, rk in enumerate(roots):
            walk(rk, "", i == len(roots) - 1)

        return lines

    def get_meta_fields(
        self,
        formId: Optional[str] = None,
        billName: Optional[str] = None,
        filter_patterns: Optional[List[str]] = None,
        raw_patterns: Optional[List[str]] = None,
        show_detail: bool = False,
        tree_view: bool = False,
        sql_mode: bool = False,
        sort_by: str = "key",
        view: str = "all"
    ) -> str:
        if not formId and not billName:
            return "❌ 错误: 必须提供 formId 或 billName"

        target_payload = None
        if formId:
            target_payload = self.cache.get(formId)
            if target_payload: self._log_debug(f"命中缓存 (FormId: {formId})")

        if not target_payload:
            self._log_debug("数据库无有效缓存，发起远程全量拉取...")
            # 始终拉取全量用于本地缓存
            payload = {"data": {"formId": formId or "", "billName": billName or "", "fuzzyFields": []}}
            resp = self._post(payload)
            if not resp.get("status"):
                return f"❌ 接口请求失败: {resp.get('message', '未知错误')}"

            data = resp.get("data", {})
            if data.get("code") in ("MULTI_MATCH", "BILL_NOT_FOUND"):
                msg = data.get("message", "单据未找到")
                cand_str = "\n".join([f"- {c.get('formName') or c.get('name') or '-'} (`{c.get('formId') or c.get('id') or '-'}`)" for c in data.get("candidates", [])])
                return f"❌ {msg}\n{cand_str}"

            target_payload = data
            real_form_id = data.get("form", {}).get("formId")
            if real_form_id:
                self.cache.set(real_form_id, data)

        # 数据提取
        form = target_payload.get("form", {})
        form_fields = target_payload.get("formFields") or []
        entity_fields = target_payload.get("entityFields") or []
        raw_operates = (
            target_payload.get("operateMetas")
            or target_payload.get("buttons")
            or []
        )
        buttons = self._normalize_operates(raw_operates)

        # 过滤与搜索逻辑
        def is_hit(f):
            if not filter_patterns: return True
            target_text = (
                str(f.get('key', ''))
                + "|"
                + str(f.get('name', ''))
                + "|"
                + str(f.get('type', ''))
            ).lower()
            for p in filter_patterns:
                try:
                    if re.search(p, target_text, re.IGNORECASE): return True
                except Exception:
                    if p.lower() in target_text: return True
            return False

        # 应用过滤
        biz_form_fields = self._sort_fields(form_fields, sort_by=sort_by)
        biz_entity_fields = self._sort_fields(entity_fields, sort_by=sort_by)

        def get_match_score(f):
            if not filter_patterns: return 0
            k = str(f.get('key', '')).lower()
            n = str(f.get('name', '')).lower()
            t = str(f.get('type', '')).lower()
            db = str(f.get('dbKey', '')).lower()
            ref = str(f.get('refType', '')).lower()
            
            score = 99
            for p in filter_patterns:
                p_lower = p.lower()
                if p_lower == k or p_lower == n:
                    return 0
                if k.startswith(p_lower) or n.startswith(p_lower):
                    score = min(score, 1)
                elif p_lower in k or p_lower in n:
                    score = min(score, 2)
                else:
                    try:
                        if re.search(p_lower, f"{k}|{n}", re.IGNORECASE):
                            score = min(score, 3)
                        elif p_lower in t or p_lower in db or p_lower in ref or re.search(p_lower, f"{t}|{db}|{ref}", re.IGNORECASE):
                            score = min(score, 4)
                    except Exception:
                        pass
            return score

        display_form_fields = sorted([f for f in biz_form_fields if is_hit(f)], key=get_match_score)
        display_entity_fields = sorted([f for f in biz_entity_fields if is_hit(f)], key=get_match_score)
        display_buttons = sorted([b for b in buttons if is_hit(b)], key=get_match_score)

        # ── 三级降级机制 ────────────────────────────────────────
        _used_fallback = False
        _fallback_hint = ""
        _no_results = lambda: not display_form_fields and not display_entity_fields and not display_buttons

        # 降级 1: 规范化后查不到 → 用原始输入重查
        #   场景: "物料 编码" 被拆成 ['物料','编码']，但字段名确实是 "物料 编码"
        if (filter_patterns and raw_patterns
                and filter_patterns != raw_patterns
                and _no_results()):
            filter_patterns = raw_patterns
            display_form_fields = sorted([f for f in biz_form_fields if is_hit(f)], key=get_match_score)
            display_entity_fields = sorted([f for f in biz_entity_fields if is_hit(f)], key=get_match_score)
            display_buttons = sorted([b for b in buttons if is_hit(b)], key=get_match_score)
            if not _no_results():
                _used_fallback = True
                _fallback_hint = f"已降级为原始输入重查: `{' '.join(raw_patterns)}`"

        # 降级 2: 仍查不到 → 转义为纯文本匹配
        #   场景: "数量(基本)" 括号被当正则 / "C++标记" 加号被当量词
        if filter_patterns and _no_results():
            escaped = [re.escape(p) for p in (raw_patterns or filter_patterns)]
            if escaped != filter_patterns:
                filter_patterns = escaped
                display_form_fields = sorted([f for f in biz_form_fields if is_hit(f)], key=get_match_score)
                display_entity_fields = sorted([f for f in biz_entity_fields if is_hit(f)], key=get_match_score)
                display_buttons = sorted([b for b in buttons if is_hit(b)], key=get_match_score)
                if not _no_results():
                    _used_fallback = True
                    _src = raw_patterns or filter_patterns
                    _fallback_hint = f"已降级为纯文本匹配: `{' '.join(_src)}`"

        view = (view or "all").strip()
        show_form = view in ("form", "all")
        show_entity = view in ("entity", "all")
        show_operate = view in ("operate", "all")

        selected_biz_form_fields = biz_form_fields if show_form else []
        selected_biz_entity_fields = biz_entity_fields if show_entity else []
        selected_display_form_fields = display_form_fields if show_form else []
        selected_display_entity_fields = display_entity_fields if show_entity else []
        selected_display_buttons = display_buttons if show_operate else []
        selected_buttons = buttons if show_operate else []

        _form_name = form.get('formName') or form.get('name') or form.get('title') or '-'
        _form_id = form.get('formId') or form.get('id') or form.get('key') or '-'
        md = [f"## 📋 单据: {_form_name} ({_form_id})"]
        md.append(
            "**模型信息**: "
            f"dbTableKey=`{form.get('dbTableKey', '-')}`, "
            f"dbRoute=`{form.get('dbRoute', '-')}`, "
            f"modelType=`{form.get('modelType', '-')}`"
        )
        md.append(f"**视图**: `{view}`")
        md.append(f"**元数据状态**: 已缓存本地 (DB驱动)")
        if _used_fallback:
            md.append(f"> ⚠️ {_fallback_hint}")
        md.append("")

        # 根据是否有过滤词切换视图
        if tree_view:
            all_biz = []
            seen = set()
            for f in selected_biz_form_fields + selected_biz_entity_fields:
                k = f.get("key")
                if k and k not in seen:
                    all_biz.append(f)
                    seen.add(k)

            tree_lines = self._build_tree_lines(all_biz, filter_patterns=filter_patterns, sort_by=sort_by) if all_biz else []
            if filter_patterns:
                md.append(f"### 🌳 字段树 (按条件筛选: {', '.join(filter_patterns)}，排序: {sort_by})")
            else:
                md.append(f"### 🌳 字段树 (按 parentKey，排序: {sort_by})")

            if tree_lines:
                md.extend(tree_lines)
            else:
                md.append("> 未找到匹配字段（当前 view 可能不包含字段类型）")

            if selected_display_buttons:
                md.append("\n### 🔘 操作按钮 (匹配)")
                md.append(", ".join([f"{b.get('name')}(`{b.get('key')}`/{b.get('type')})" for b in selected_display_buttons]))
        elif filter_patterns:
            md.append(f"### 🔍 字段详情 (按条件筛选: {', '.join(filter_patterns)}，排序: {sort_by})")
            
            all_fields_by_key = {str(f.get('key', '')).lower(): f for f in form_fields + entity_fields}
            
            def get_entity_info(f):
                parent_key = f.get('parentKey')
                if not parent_key:
                    return "表头"
                parent_key_lower = str(parent_key).lower()
                parent = all_fields_by_key.get(parent_key_lower)
                if not parent:
                    return f"未知 (`{parent_key}`)"
                ptype = str(parent.get('type', '')).lower()
                if 'subentry' in ptype:
                    grandparent_key = parent.get('parentKey')
                    if grandparent_key:
                        return f"子表体 (`{grandparent_key}` -> `{parent_key}`)"
                    return f"子表体 (`{parent_key}`)"
                elif 'entry' in ptype:
                    return f"表体 (`{parent_key}`)"
                else:
                    return f"容器 (`{parent_key}`)"

            def get_db_table(f):
                parent_key = f.get('parentKey')
                if not parent_key:
                    return form.get('dbTableKey') or '-'
                parent = all_fields_by_key.get(str(parent_key).lower())
                return parent.get('dbKey') or '-' if parent else '-'

            if selected_display_form_fields or selected_display_entity_fields:
                if sql_mode:
                    md.append("| 名称 | 标识 (Key) | 表名 (dbTableName) | 数据库字段 (dbKey) |")
                    md.append("| :--- | :--- | :--- | :--- |")
                elif show_detail:
                    md.append("| 名称 | 标识 (Key) | 类型 | 所属实体 | 详情 (枚举/基础资料引用) |")
                    md.append("| :--- | :--- | :--- | :--- | :--- |")
                else:
                    md.append("| 名称 | 标识 (Key) | 类型 | 所属实体 | 附加信息 (Ext) |")
                    md.append("| :--- | :--- | :--- | :--- | :--- |")

                # 优先显示表单字段，再显示实体字段（去重）
                seen_keys = set()
                for f in selected_display_form_fields + selected_display_entity_fields:
                    if f.get('key') not in seen_keys:
                        ent_info = get_entity_info(f)
                        db_key = f.get('dbKey', '-')
                        
                        if sql_mode:
                            db_table = get_db_table(f)
                            md.append(f"| {f.get('name')} | `{f.get('key')}` | `{db_table}` | `{db_key}` |")
                        elif show_detail:
                            detail_parts = []
                            ext_map = f.get('extMap')
                            ref_type = f.get('refType')
                            if ext_map:
                                detail_parts.append("枚举: " + ", ".join([f"{k}:{v}" for k, v in ext_map.items()]))
                            if ref_type:
                                detail_parts.append(f"基础资料引用: `{ref_type}`")
                            detail_str = "；".join(detail_parts) if detail_parts else "-"
                            md.append(f"| {f.get('name')} | `{f.get('key')}` | {f.get('type')} | {ent_info} | {detail_str} |")
                        else:
                            ext_map = f.get('extMap')
                            ref_type = f.get('refType')
                            ext_parts = []
                            if ext_map:
                                ext_parts.append(", ".join([f"{k}:{v}" for k, v in ext_map.items()]))
                            if ref_type:
                                ext_parts.append(f"ref:`{ref_type}`")
                            ext_str = "；".join(ext_parts) if ext_parts else "-"
                            md.append(f"| {f.get('name')} | `{f.get('key')}` | {f.get('type')} | {ent_info} | {ext_str} |")
                        seen_keys.add(f.get('key'))
            else:
                md.append("> 当前 view 不包含字段类型或无匹配字段")

            if selected_display_buttons:
                md.append("\n### 🔘 操作按钮 (匹配)")
                md.append(", ".join([f"{b.get('name')}(`{b.get('key')}`/{b.get('type')})" for b in selected_display_buttons]))
        else:
            # 概览模式：只输出紧凑的 Key-Name 映射
            md.append(f"### 📑 字段概览 (共 {len(selected_biz_form_fields) + len(selected_biz_entity_fields)} 个字段，排序: {sort_by})")
            # 合并展示
            all_biz = []
            seen = set()
            for f in selected_biz_form_fields + selected_biz_entity_fields:
                if f.get('key') not in seen:
                    all_biz.append(f)
                    seen.add(f.get('key'))

            chunk_size = 3
            for i in range(0, min(len(all_biz), 120), chunk_size):
                chunk = all_biz[i:i+chunk_size]
                line = "  ".join([f"• {f.get('name')}: `{f.get('key')}`" for f in chunk])
                md.append(line)

            if len(all_biz) > 120:
                md.append(f"\n> *提示: 字段较多已截断。本地已缓存全量，请传入关键词（支持正则）获取特定字段详情。*")

            if selected_buttons:
                md.append("\n### 🔘 全部操作按钮")
                md.append(", ".join([f"{b.get('name')}(`{b.get('key')}`/{b.get('type')})" for b in selected_buttons]))

        return "\n".join(md)


_RE_META = re.compile(r'[|*+?\[\]()\\{}^$]')


def _normalize_fuzzy_patterns(raw_patterns: List[str]) -> List[str]:
    """
    智能拆分 fuzzy 参数，兼容各种 AI/Agent 的传参习惯:
      --fuzzy 组织 物料 批号       → ['组织', '物料', '批号']      (nargs 原生)
      --fuzzy "组织 物料 批号"     → ['组织', '物料', '批号']      (引号包裹，按空格拆)
      --fuzzy "数量|金额"          → ['数量|金额']                 (正则，保持原样)
      --fuzzy "qty.*amount"       → ['qty.*amount']               (正则，保持原样)
      --fuzzy "组织" "物料"        → ['组织', '物料']              (多引号，逐个处理)
    判定规则：含正则元字符 ``|*+?[](){}^$`` 的 token 视为正则，否则按空格拆分。
    """
    result: List[str] = []
    for p in raw_patterns:
        p = p.strip()
        if not p:
            continue
        if _RE_META.search(p):
            # 含正则元字符，保持原样
            result.append(p)
        else:
            # 纯文本：可能是 "组织 物料 批号" 这样的引号包裹，按空格拆
            result.extend(p.split())
    return [x for x in result if x]


def main():
    parser = argparse.ArgumentParser(description="Cosmic Form Metadata CLI (View Filter Mode)")
    parser.add_argument("--config", help="Path to ok-cosmic.json")
    parser.add_argument("--debug", action="store_true")

    sub_parser = parser.add_subparsers(dest="command")
    get_parser = sub_parser.add_parser("get")
    get_parser.add_argument("--form-id")
    get_parser.add_argument("--bill-name")
    get_parser.add_argument("--fuzzy", nargs="*", help="筛选关键词或正则模式，触发详情视图。支持多种传参方式: --fuzzy a b c / --fuzzy 'a b c' / --fuzzy 'a|b'")
    get_parser.add_argument("--show-detail", action="store_true", help="显示枚举值映射(extMap)或基础资料引用类型(refType)")
    get_parser.add_argument("--tree", action="store_true", help="按 parentKey 输出字段树（可与 --fuzzy 联用）")
    get_parser.add_argument("--sql", action="store_true", help="启用 SQL 模式，展示表名与数据库字段名 (dbTableName/dbKey)")
    get_parser.add_argument("--sort", choices=["key", "name", "type", "dbKey"], default="key", help="字段排序方式")
    get_parser.add_argument("--view", choices=["form", "entity", "operate", "all"], default="all", help="元数据视图范围")
    get_parser.add_argument("--debug", action="store_true")
    get_parser.add_argument("--refresh", action="store_true")

    args = parser.parse_args()
    config = load_project_config(args.config)
    fm = FormMetadata(config, debug=(args.debug or getattr(args, 'debug', False)))

    if args.command == "get":
        # 智能拆分 fuzzy 参数：纯关键词按空格拆开，正则模式保持原样
        raw_fuzzy = list(args.fuzzy) if args.fuzzy else None
        if args.fuzzy:
            args.fuzzy = _normalize_fuzzy_patterns(args.fuzzy)
        # 当 fuzzy 关键词 ≥3 个时，自动升级为详情模式（含枚举/refType）
        auto_detail = False
        show_detail = args.show_detail
        if not show_detail and args.fuzzy and len(args.fuzzy) >= 3:
            show_detail = True
            auto_detail = True
        if args.refresh and args.form_id:
            fm.cache.remove(args.form_id)
        result = fm.get_meta_fields(
            formId=args.form_id,
            billName=args.bill_name,
            filter_patterns=args.fuzzy,
            raw_patterns=raw_fuzzy,
            show_detail=show_detail,
            tree_view=args.tree,
            sql_mode=args.sql,
            sort_by=args.sort,
            view=args.view
        )
        if auto_detail:
            result += "\n\n> 💡 已自动启用详情模式（fuzzy 关键词 ≥3），包含枚举映射和基础资料引用类型。"
        print(result)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()