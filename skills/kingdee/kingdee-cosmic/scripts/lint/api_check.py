# -*- coding: utf-8 -*-
"""
知识库驱动的 API 校验 (API-*) — 动态查 ok-cosmic-knowledge.db

Rules:
  API-001  方法名在该类上不存在（含继承链）              → ERROR
  API-002  方法参数个数与所有重载均不匹配                → ERROR
  API-003  类名解析到白名单包但知识库无记录              → WARNING
  API-004  @Override 方法在父类继承链中不存在             → ERROR

检测范围:
  - 静态调用:   ClassName.method(args)
  - 实例调用:   varName.method(args)    (需变量类型可追踪)
  - this 调用:  this.method(args)       (排除本类声明的方法)
  - 链式调用:   expr.method1().method2() (通过 return_type 解析)
  - 方法覆写:   @Override void method() (校验父类是否存在)
"""

import os
import re
import sqlite3
from collections import namedtuple
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .base import (
    LintIssue, Severity, is_comment_or_string,
    code_for_structure, METHOD_DECL_RE,
)

# ── 配置 ──────────────────────────────────────

WHITELIST_PREFIXES = (
    "kd.bos.",
    "kd.bd.",
    "kd.sdk.",
    "kd.cd.common.",
    "kd.cd.core.",
    "kd.cd.webapi.",
    "kd.cd.feature.",
)

_SCRIPT_DIR = Path(__file__).resolve().parent

# ── 数据结构 ──────────────────────────────────

Overload = namedtuple("Overload", ["param_count", "last_is_array", "return_type"])

# ── 模块级缓存 ────────────────────────────────

_inited = False
_conn: Optional[sqlite3.Connection] = None

_class_set: Set[str] = set()
_simple_index: Dict[str, List[str]] = {}
_super_map: Dict[str, Optional[str]] = {}
_method_cache: Dict[str, Dict[str, List[Overload]]] = {}
_method_exists_cache: Dict[str, bool] = {}


# ══════════════════════════════════════════════
#  初始化 & 知识库查询
# ══════════════════════════════════════════════

def _resolve_db_path() -> Optional[str]:
    """按优先级解析知识库路径：环境变量 > ok-cosmic.json 配置 > None。"""
    # 1. 环境变量（最高优先级，便于 CI 或手动覆盖）
    env_path = os.environ.get("OK_COSMIC_KNOWLEDGE_DB")
    if env_path and os.path.exists(env_path):
        return env_path

    # 2. 从 ok-cosmic.json 加载 graph.dbPath（通过 config_loader）
    try:
        from config_loader import load_project_config
        config = load_project_config()
        db_path = config.get("graph", {}).get("dbPath", "")
        if db_path and os.path.exists(db_path):
            return db_path
    except Exception:
        pass

    return None


def _ensure_init():
    """惰性加载：建立类索引，保持 DB 连接供后续方法查询。"""
    global _inited, _conn
    if _inited:
        return
    _inited = True

    db_path = _resolve_db_path()
    if not db_path:
        return

    _conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    cur = _conn.execute("SELECT class_name, super_class_name FROM class_node")
    for fqn, super_fqn in cur:
        if not any(fqn.startswith(p) for p in WHITELIST_PREFIXES):
            continue
        _class_set.add(fqn)
        _super_map[fqn] = super_fqn if super_fqn else None
        simple = fqn.rsplit(".", 1)[-1]
        _simple_index.setdefault(simple, []).append(fqn)


def _parse_overload(descriptor: str, return_type: str = "") -> Optional[Overload]:
    """从 JVM 方法描述符解析参数个数和 last-is-array 标志。"""
    try:
        params_str = descriptor[1:descriptor.index(")")]
    except (ValueError, IndexError):
        return None

    params: List[str] = []
    i = 0
    while i < len(params_str):
        start = i
        while i < len(params_str) and params_str[i] == "[":
            i += 1
        if i >= len(params_str):
            break
        if params_str[i] == "L":
            try:
                end = params_str.index(";", i)
            except ValueError:
                break
            i = end + 1
        else:
            i += 1
        params.append(params_str[start:i])

    last_is_arr = bool(params and params[-1].startswith("["))
    return Overload(len(params), last_is_arr, return_type)


def _query_methods(fqn: str) -> Dict[str, List[Overload]]:
    """查询某个 FQN 的所有方法（含 return_type），结果缓存。"""
    if fqn in _method_cache:
        return _method_cache[fqn]

    result: Dict[str, List[Overload]] = {}
    if _conn is None:
        _method_cache[fqn] = result
        return result

    cur = _conn.execute(
        "SELECT method_name, method_descriptor, return_type "
        "FROM method_node WHERE class_name = ?",
        (fqn,),
    )
    for name, descriptor, rt in cur:
        ov = _parse_overload(descriptor, rt or "")
        if ov is not None:
            result.setdefault(name, []).append(ov)

    _method_cache[fqn] = result
    return result


def _get_all_overloads(fqn: str, method_name: str, depth: int = 0) -> List[Overload]:
    """获取方法的所有重载（沿继承链向上查找，最多 10 层）。"""
    if depth > 10 or fqn not in _class_set:
        return []

    methods = _query_methods(fqn)
    result = list(methods.get(method_name, []))

    super_fqn = _super_map.get(fqn)
    if super_fqn and super_fqn in _class_set:
        result.extend(_get_all_overloads(super_fqn, method_name, depth + 1))

    return result


def _find_return_type(fqns: List[str], method_name: str, arg_count: int) -> Optional[str]:
    """查找方法调用的返回类型（取第一个参数匹配的重载，用于链式调用解析）。"""
    for fqn in fqns:
        for ov in _get_all_overloads(fqn, method_name):
            if _args_match(arg_count, ov) and ov.return_type:
                if _is_whitelisted(ov.return_type):
                    return ov.return_type
    return None


def _chain_exits_whitelist(fqns: List[str]) -> bool:
    """检查类的继承链是否在非 java.lang.Object 处退出白名单。

    若是，说明该类可能继承了非白名单父类（如 java.util.ArrayList）的方法，
    应对 API-001 采取宽容策略（方法可能来自不在知识库中的父类）。
    """
    for fqn in fqns:
        cur = fqn
        depth = 0
        while cur and depth < 15:
            super_fqn = _super_map.get(cur)
            if not super_fqn:
                break
            if super_fqn not in _class_set:
                # 退出白名单 → 非 Object 则宽容
                if super_fqn != "java.lang.Object":
                    return True
                break
            cur = super_fqn
            depth += 1
    return False


def _method_exists_anywhere(method_name: str) -> bool:
    """查询方法名是否存在于知识库任意类中（带缓存）。

    用于 API-004 / this 调用的宽容判断：方法可能来自接口而非类继承链。
    """
    if method_name in _method_exists_cache:
        return _method_exists_cache[method_name]

    exists = False
    if _conn is not None:
        cur = _conn.execute(
            "SELECT 1 FROM method_node WHERE method_name = ? LIMIT 1",
            (method_name,),
        )
        exists = cur.fetchone() is not None

    _method_exists_cache[method_name] = exists
    return exists


# ══════════════════════════════════════════════
#  类名解析
# ══════════════════════════════════════════════

IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+(?:\.\*)?)\s*;")


def _parse_imports(lines: List[str]) -> Tuple[Dict[str, str], List[str]]:
    """解析 import 语句，返回 (simple_name → FQN, 通配包前缀列表)。"""
    imports: Dict[str, str] = {}
    wildcards: List[str] = []
    for line in lines:
        m = IMPORT_RE.match(line)
        if m:
            fqn = m.group(1)
            if fqn.endswith(".*"):
                wildcards.append(fqn[:-2])
            else:
                simple = fqn.rsplit(".", 1)[-1]
                imports[simple] = fqn
    return imports, wildcards


def _is_whitelisted(fqn: str) -> bool:
    return any(fqn.startswith(p) for p in WHITELIST_PREFIXES)


def _resolve_class(simple_name: str, imports: Dict[str, str],
                   wildcards: List[str]) -> Tuple[List[str], bool]:
    """解析简单类名 → 白名单 FQN 列表。返回 (fqn_list, is_explicit_import)。"""
    if simple_name in imports:
        fqn = imports[simple_name]
        if _is_whitelisted(fqn):
            return [fqn], True
        return [], False

    for pkg in wildcards:
        candidate = f"{pkg}.{simple_name}"
        if _is_whitelisted(candidate) and candidate in _class_set:
            return [candidate], True

    if simple_name in _simple_index:
        return _simple_index[simple_name], False

    return [], False


# ══════════════════════════════════════════════
#  正则模式
# ══════════════════════════════════════════════

# 静态调用: ClassName.methodName(
STATIC_CALL_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]+)\s*\.\s*([a-z][A-Za-z0-9_]*)\s*\(")

# 实例调用: varName.methodName(   (varName 首字母小写)
INSTANCE_CALL_RE = re.compile(r"\b([a-z][A-Za-z0-9_]*)\s*\.\s*([a-z][A-Za-z0-9_]*)\s*\(")

# 类继承声明: class X extends Y
CLASS_EXTENDS_RE = re.compile(r"\bclass\s+(\w+)(?:<[^>]*>)?\s+extends\s+(\w+)")

# 变量/参数类型: TypeName varName  (后跟 = ; , ) :)
TYPE_VAR_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]+)\s+([a-z]\w*)\s*(?=[=;,):])")

# @Override 注解
OVERRIDE_RE = re.compile(r"@Override\b")

# 链式调用起始 (在 ) 之后): .methodName(
CHAIN_AFTER_PAREN_RE = re.compile(r"\s*\.\s*([a-z][A-Za-z0-9_]*)\s*\(")


# ══════════════════════════════════════════════
#  调用提取 & 参数计数
# ══════════════════════════════════════════════

def _extract_args_text(lines: List[str], line_idx: int, col: int
                       ) -> Tuple[Optional[str], int, int]:
    """
    从 lines[line_idx][col] 处的 '(' 开始提取到匹配 ')' 的参数文本。
    返回 (参数文本, 结束行号, ')' 之后的列号)。
    """
    depth = 0
    in_str = False
    str_ch = None
    escape = False
    parts: List[str] = []
    started = False

    for i in range(line_idx, min(line_idx + 30, len(lines))):
        line = lines[i]
        j = col if i == line_idx else 0
        while j < len(line):
            ch = line[j]

            if escape:
                escape = False
                if started:
                    parts.append(ch)
                j += 1
                continue
            if ch == "\\":
                escape = True
                if started:
                    parts.append(ch)
                j += 1
                continue
            if in_str:
                if started:
                    parts.append(ch)
                if ch == str_ch:
                    in_str = False
                j += 1
                continue

            # 行内注释
            if ch == "/" and j + 1 < len(line) and line[j + 1] == "/":
                break

            if ch in ('"', "'"):
                in_str = True
                str_ch = ch
                if started:
                    parts.append(ch)
                j += 1
                continue

            if ch == "(":
                depth += 1
                if depth == 1:
                    started = True
                    j += 1
                    continue
                if started:
                    parts.append(ch)
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return "".join(parts), i, j + 1
                if started:
                    parts.append(ch)
            elif started:
                parts.append(ch)

            j += 1

        if started:
            parts.append(" ")

    return None, -1, -1


def _count_args(args_text: str) -> int:
    """对已提取的参数文本计数。"""
    s = args_text.strip()
    if not s:
        return 0
    depth = 0
    in_str = False
    str_ch = None
    escape = False
    count = 1
    for ch in s:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if in_str:
            if ch == str_ch:
                in_str = False
            continue
        if ch in ('"', "'"):
            in_str = True
            str_ch = ch
            continue
        if ch in "(<[{":
            depth += 1
        elif ch in ")>]}":
            depth -= 1
        elif ch == "," and depth == 0:
            count += 1
    return count


def _args_match(arg_count: int, overload: Overload) -> bool:
    """判断调用参数个数是否匹配某个重载。"""
    if arg_count == overload.param_count:
        return True
    if overload.last_is_array and arg_count >= overload.param_count - 1:
        return True
    return False


# ══════════════════════════════════════════════
#  辅助工具
# ══════════════════════════════════════════════

def _strip_generics(text: str) -> str:
    """移除泛型参数 <...>，使 `Map<String, List<Integer>> map` → `Map map`。"""
    result: List[str] = []
    depth = 0
    for ch in text:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth = max(0, depth - 1)
        elif depth == 0:
            result.append(ch)
    return "".join(result)


def _collect_declared_methods(lines: List[str]) -> Set[str]:
    """预扫描文件，收集所有声明的方法名（用于 this.xxx() 防误报）。"""
    methods: Set[str] = set()
    for line in lines:
        stripped = code_for_structure(line).strip()
        m = METHOD_DECL_RE.match(stripped)
        if m:
            methods.add(m.group(1))
    return methods


# ══════════════════════════════════════════════
#  校验核心
# ══════════════════════════════════════════════

def _validate_method_on_fqns(
    fqns: List[str], method_name: str, arg_count: int,
    lineno: int, filepath: str, line_text: str,
    display_receiver: str, issues: List[LintIssue],
    lenient: bool = False,
) -> Tuple[bool, bool]:
    """校验方法调用，返回 (method_found, param_matched)。

    lenient=True 时，若方法未找到但可能来自非白名单父类或接口，则跳过 API-001。
    """
    method_found = False
    param_match = False

    for fqn in fqns:
        overloads = _get_all_overloads(fqn, method_name)
        if overloads:
            method_found = True
            if any(_args_match(arg_count, ov) for ov in overloads):
                param_match = True
                break
        if param_match:
            break

    if not method_found:
        if lenient:
            return method_found, param_match
        issues.append(LintIssue(
            file=filepath, line=lineno,
            severity=Severity.ERROR,
            rule_id="API-001",
            message=f"{display_receiver}.{method_name}() 在知识库中未找到该方法（含继承链）",
            fix_hint="使用 cosmic-api-knowledge.py search 查询正确方法名",
            source_line=line_text.strip(),
        ))
    elif not param_match:
        all_ov: List[Overload] = []
        for fqn in fqns:
            all_ov.extend(_get_all_overloads(fqn, method_name))
        ov_desc = ", ".join(sorted(set(
            f"{ov.param_count}{'+'if ov.last_is_array else ''}" for ov in all_ov
        )))
        issues.append(LintIssue(
            file=filepath, line=lineno,
            severity=Severity.ERROR,
            rule_id="API-002",
            message=(
                f"{display_receiver}.{method_name}() 传了 {arg_count} 个参数，"
                f"已知重载参数个数: [{ov_desc}]"
            ),
            fix_hint="使用 cosmic-api-knowledge.py search 查询正确签名",
            source_line=line_text.strip(),
        ))

    return method_found, param_match


def _try_chain_validation(
    lines: List[str], end_line: int, end_col: int,
    receiver_fqns: List[str], prev_method: str, prev_arg_count: int,
    filepath: str, issues: List[LintIssue], seen: Set,
    max_depth: int = 5,
):
    """检测并校验链式调用 ...).methodName(，递归处理多级链。"""
    if max_depth <= 0 or end_line < 0:
        return

    chain_method = None
    paren_line = end_line
    paren_col = -1

    # 1) 同一行 ) 之后
    if end_col < len(lines[end_line]):
        remaining = lines[end_line][end_col:]
        cm = CHAIN_AFTER_PAREN_RE.match(remaining)
        if cm:
            chain_method = cm.group(1)
            paren_col = end_col + cm.end() - 1  # '(' 在原始行中的位置

    # 2) 下一行开头
    if chain_method is None:
        nxt = end_line + 1
        if nxt < len(lines):
            nxt_line = lines[nxt]
            nxt_stripped = nxt_line.lstrip()
            cm = re.match(r"\.\s*([a-z][A-Za-z0-9_]*)\s*\(", nxt_stripped)
            if cm:
                chain_method = cm.group(1)
                paren_line = nxt
                indent = len(nxt_line) - len(nxt_stripped)
                paren_col = indent + cm.end() - 1

    if chain_method is None:
        return

    lineno = paren_line + 1
    key = (lineno, "chain", chain_method)
    if key in seen:
        return
    seen.add(key)

    # 获取前一调用的返回类型
    ret_type = _find_return_type(receiver_fqns, prev_method, prev_arg_count)
    if not ret_type or ret_type not in _class_set:
        return

    # 提取链式调用参数
    args_text, c_end_line, c_end_col = _extract_args_text(lines, paren_line, paren_col)
    if args_text is None:
        return
    arg_count = _count_args(args_text)

    chain_fqns = [ret_type]
    display = ret_type.rsplit(".", 1)[-1]

    _validate_method_on_fqns(
        chain_fqns, chain_method, arg_count,
        lineno, filepath, lines[paren_line], display, issues,
        lenient=_chain_exits_whitelist(chain_fqns) or _method_exists_anywhere(chain_method),
    )

    # 递归更深层链
    _try_chain_validation(
        lines, c_end_line, c_end_col,
        chain_fqns, chain_method, arg_count,
        filepath, issues, seen, max_depth - 1,
    )


# ══════════════════════════════════════════════
#  主检查入口
# ══════════════════════════════════════════════

def check(filepath: str, lines: List[str]) -> List[LintIssue]:
    """执行知识库 API 校验（静态 + 实例 + 链式 + 覆写），返回问题列表。"""
    _ensure_init()

    if not _class_set:
        return []

    issues: List[LintIssue] = []
    imports, wildcards = _parse_imports(lines)
    declared_methods = _collect_declared_methods(lines)

    # ── 有状态上下文 ──
    seen: Set[Tuple[int, str, str]] = set()
    brace_depth = 0
    # (进入深度, 类简名, 父类简名)
    class_stack: List[Tuple[int, str, str]] = []
    var_types: Dict[str, str] = {}   # varName → 简单类名
    pending_override = False

    for i, line in enumerate(lines):
        # ── 注释/字符串行：只追踪花括号 ──
        if is_comment_or_string(line):
            code = code_for_structure(line)
            brace_depth += code.count("{") - code.count("}")
            while class_stack and brace_depth < class_stack[-1][0]:
                class_stack.pop()
            continue

        code = code_for_structure(line)
        stripped = code.strip()
        lineno = i + 1

        # ── 1. 追踪 class 声明 ──
        cls_m = CLASS_EXTENDS_RE.search(stripped)
        if cls_m and "{" in stripped:
            class_stack.append((brace_depth + 1, cls_m.group(1), cls_m.group(2)))

        # ── 2. 追踪 @Override ──
        if OVERRIDE_RE.search(stripped):
            pending_override = True

        # ── 3. 方法声明 → API-004 覆写校验 ──
        method_decl = METHOD_DECL_RE.match(stripped)
        if method_decl and not stripped.endswith(";"):
            decl_name = method_decl.group(1)

            if pending_override and class_stack:
                parent_simple = class_stack[-1][2]
                parent_fqns, _ = _resolve_class(parent_simple, imports, wildcards)
                existing = [f for f in parent_fqns if f in _class_set]
                if existing and not any(
                    _get_all_overloads(f, decl_name) for f in existing
                ) and not _method_exists_anywhere(decl_name):
                    issues.append(LintIssue(
                        file=filepath, line=lineno,
                        severity=Severity.ERROR,
                        rule_id="API-004",
                        message=(
                            f"@Override {decl_name}() 在父类 "
                            f"{parent_simple} 继承链中未找到"
                        ),
                        fix_hint="使用 cosmic-api-knowledge.py search 查询正确方法名",
                        source_line=line.strip(),
                    ))

            pending_override = False

            # 追踪方法参数中的类型
            paren_idx = stripped.find("(")
            if paren_idx >= 0:
                param_text = _strip_generics(stripped[paren_idx:])
                for tv in TYPE_VAR_RE.finditer(param_text):
                    var_types[tv.group(2)] = tv.group(1)

        elif method_decl:
            pending_override = False

        # ── 4. 追踪变量类型 ──
        if not method_decl:
            clean = _strip_generics(stripped)
            for tv in TYPE_VAR_RE.finditer(clean):
                var_types[tv.group(2)] = tv.group(1)

        # ── 5. 静态调用 ClassName.method() ──
        for m in STATIC_CALL_RE.finditer(line):
            class_name = m.group(1)
            method_name = m.group(2)
            key = (lineno, class_name, method_name)
            if key in seen:
                continue
            seen.add(key)

            fqns, is_explicit = _resolve_class(class_name, imports, wildcards)
            if not fqns:
                continue

            existing_fqns = [f for f in fqns if f in _class_set]
            if not existing_fqns:
                if is_explicit:
                    issues.append(LintIssue(
                        file=filepath, line=lineno,
                        severity=Severity.WARNING,
                        rule_id="API-003",
                        message=f"类 {class_name} (→ {fqns[0]}) 在知识库中未找到",
                        fix_hint="确认类名拼写，或 cosmic-api-knowledge.py search 查询",
                        source_line=line.strip(),
                    ))
                continue

            try:
                paren_pos = line.index("(", m.start())
            except ValueError:
                continue
            args_text, end_line, end_col = _extract_args_text(lines, i, paren_pos)
            if args_text is None:
                continue
            arg_count = _count_args(args_text)

            _validate_method_on_fqns(
                existing_fqns, method_name, arg_count,
                lineno, filepath, line, class_name, issues,
                lenient=_chain_exits_whitelist(existing_fqns),
            )
            _try_chain_validation(
                lines, end_line, end_col,
                existing_fqns, method_name, arg_count,
                filepath, issues, seen,
            )

        # ── 6. 实例调用 varName.method() / this.method() ──
        for m in INSTANCE_CALL_RE.finditer(line):
            var_name = m.group(1)
            method_name = m.group(2)
            key = (lineno, var_name, method_name)
            if key in seen:
                continue

            # 确定 receiver 类型
            type_name: Optional[str] = None
            if var_name == "this":
                if method_name in declared_methods:
                    continue  # 本类方法 → 跳过
                if class_stack:
                    type_name = class_stack[-1][2]  # 父类简名
            elif var_name in var_types:
                type_name = var_types[var_name]

            if not type_name:
                continue

            fqns, _ = _resolve_class(type_name, imports, wildcards)
            existing_fqns = [f for f in fqns if f in _class_set]
            if not existing_fqns:
                continue

            seen.add(key)

            try:
                paren_pos = line.index("(", m.start())
            except ValueError:
                continue
            args_text, end_line, end_col = _extract_args_text(lines, i, paren_pos)
            if args_text is None:
                continue
            arg_count = _count_args(args_text)

            display = f"{var_name}({type_name})"
            is_this = (var_name == "this")
            _validate_method_on_fqns(
                existing_fqns, method_name, arg_count,
                lineno, filepath, line, display, issues,
                lenient=(
                    _method_exists_anywhere(method_name) if is_this
                    else (_chain_exits_whitelist(existing_fqns)
                          or _method_exists_anywhere(method_name))
                ),
            )
            _try_chain_validation(
                lines, end_line, end_col,
                existing_fqns, method_name, arg_count,
                filepath, issues, seen,
            )

        # ── 7. 更新花括号深度 & 作用域 ──
        brace_depth += code.count("{") - code.count("}")

        while class_stack and brace_depth < class_stack[-1][0]:
            class_stack.pop()

    return issues
