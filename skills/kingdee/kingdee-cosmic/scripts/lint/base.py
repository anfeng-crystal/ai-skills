# -*- coding: utf-8 -*-
"""公共数据结构与工具函数，所有检查模块共享。"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


# ──────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────

class Severity(str, Enum):
    ERROR = "ERROR"      # 必定错误
    WARNING = "WARNING"  # 场景错配 / 强烈不推荐
    INFO = "INFO"        # 风格偏好 / 建议


@dataclass
class LintIssue:
    file: str
    line: int
    severity: Severity
    rule_id: str
    message: str
    fix_hint: str = ""
    source_line: str = ""


@dataclass
class LintReport:
    total_files: int = 0
    total_issues: int = 0
    errors: int = 0
    warnings: int = 0
    infos: int = 0
    issues: List[LintIssue] = field(default_factory=list)

    def add(self, issue: LintIssue):
        self.issues.append(issue)
        self.total_issues += 1
        if issue.severity == Severity.ERROR:
            self.errors += 1
        elif issue.severity == Severity.WARNING:
            self.warnings += 1
        else:
            self.infos += 1


# ──────────────────────────────────────────────
# 注释 / 字符串状态机
# ──────────────────────────────────────────────

def classify_lines(lines: List[str]) -> List[bool]:
    """对每行标记是否为"纯注释或空行"（True=非代码行，应跳过 lint）。

    使用状态机追踪多行注释块（/* ... */），
    单行内同时识别行注释、字符串字面量，避免误判。
    """
    result: List[bool] = []
    in_block_comment = False

    for line in lines:
        if in_block_comment:
            # 当前处于 /* ... */ 块注释中
            end_idx = line.find("*/")
            if end_idx >= 0:
                in_block_comment = False
                # 关闭后如果剩余部分有实质代码，视为代码行
                remainder = line[end_idx + 2:].strip()
                result.append(not bool(remainder))
            else:
                result.append(True)
            continue

        stripped = line.strip()
        # 空行
        if not stripped:
            result.append(True)
            continue
        # 纯单行注释
        if stripped.startswith("//"):
            result.append(True)
            continue
        # Javadoc / 多行注释续行（行首 *）
        if stripped.startswith("*") and not stripped.startswith("*/"):
            result.append(True)
            continue
        # 检查块注释开始
        if stripped.startswith("/*"):
            close_idx = stripped.find("*/", 2)
            if close_idx >= 0:
                # 单行块注释 /* ... */，检查 */ 后是否有代码
                remainder = stripped[close_idx + 2:].strip()
                result.append(not bool(remainder))
            else:
                in_block_comment = True
                result.append(True)
            continue

        # 其他情况：代码行（可能包含行尾注释，但行本身有代码）
        result.append(False)

    return result


def is_comment_or_string(line: str) -> bool:
    """粗略判断当前行是否为注释或字符串（排除误报）。

    注意：此函数为单行判断，无法追踪跨行 /* */ 状态。
    对跨行精确判断，请使用 classify_lines() 代替。
    """
    stripped = line.strip()
    if not stripped:
        return True
    return (stripped.startswith("//")
            or stripped.startswith("*")
            or stripped.startswith("/*"))


def strip_line_comment(line: str) -> str:
    """移除单行注释部分，保留代码主体。"""
    return re.sub(r"//.*$", "", line)


def strip_string_literals(line: str) -> str:
    """移除字符串字面量，便于做结构分析。"""
    return re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '""', line)


def code_for_structure(line: str) -> str:
    """用于结构分析的代码行：去掉行注释与字符串。"""
    return strip_line_comment(strip_string_literals(line))


METHOD_DECL_RE = re.compile(
    r"^\s*(?:@\w+(?:\([^)]*\))?\s*)*"
    r"(?:public|protected|private)\s+"
    r"(?:static\s+|final\s+|synchronized\s+|abstract\s+|native\s+|default\s+)*"
    r"[\w<>\[\], ?.@]+\s+([A-Za-z_]\w*)\s*"
    r"\([^;{}]*\)\s*(?:throws\s+[^{]+)?\s*(?:\{)?\s*$"
)

LOOP_HEADER_RE = re.compile(r"\bfor\s*\(|\bwhile\s*\(|^\s*do\b")
CLASS_DECL_RE = re.compile(r"\bclass\s+[A-Za-z_]\w*")


def looks_like_loop_header(line: str) -> bool:
    """判断当前行是否看起来是 loop 头。"""
    return bool(LOOP_HEADER_RE.search(code_for_structure(line)))


def analyze_java_context(lines: List[str]) -> Tuple[List[Optional[str]], List[bool]]:
    """
    基于轻量 brace 分析构建上下文：
    - 每行所在方法名
    - 每行是否位于循环体中
    """
    method_context: List[Optional[str]] = [None] * len(lines)
    loop_context: List[bool] = [False] * len(lines)

    brace_depth = 0
    current_method: Optional[str] = None
    method_depth: Optional[int] = None
    pending_single_line_loop = False
    loop_depth_stack: List[int] = []

    for i, line in enumerate(lines):
        code = code_for_structure(line)
        stripped = code.strip()

        if pending_single_line_loop and stripped:
            loop_context[i] = True
            pending_single_line_loop = False
        else:
            loop_context[i] = bool(loop_depth_stack)

        method_context[i] = current_method

        method_match = METHOD_DECL_RE.match(stripped)
        if method_match and not stripped.endswith(";"):
            if "{" in stripped:
                current_method = method_match.group(1)
                method_depth = brace_depth + 1

        if looks_like_loop_header(line):
            if "{" in stripped:
                loop_depth_stack.append(brace_depth + 1)
            elif stripped.endswith(")") or stripped.endswith("do"):
                pending_single_line_loop = True

        brace_depth += code.count("{") - code.count("}")

        while loop_depth_stack and brace_depth < loop_depth_stack[-1]:
            loop_depth_stack.pop()

        if current_method and method_depth is not None and brace_depth < method_depth:
            current_method = None
            method_depth = None

    return method_context, loop_context


# 操作插件的类标识模式
OP_PLUGIN_MARKERS = [
    r"extends\s+AbstractOperationServicePlugIn\b",
    r"extends\s+AbstractOperationServicePlugInExt\b",
    r"extends\s+AbstractValidatorExt\b",
    r"implements\s+.*OperationServicePlugIn\b",
]

# UI 插件标识模式
UI_PLUGIN_MARKERS = [
    r"extends\s+AbstractFormPluginExt\b",
    r"extends\s+AbstractBillPlugInExt\b",
    r"extends\s+AbstractListPluginExt\b",
    r"extends\s+AbstractFormPlugin\b",
    r"extends\s+AbstractBillPlugIn\b",
    r"extends\s+AbstractListPlugin\b",
    r"extends\s+AbstractTreeListPlugin\b",
    r"extends\s+StandardTreeListPlugin\b",
]

# 其他继承型插件标识模式（非操作、非 UI，但仍需检查 super 调用）
OTHER_INHERITABLE_MARKERS = [
    r"extends\s+AbstractConvertPlugIn\b",
    r"extends\s+AbstractWriteBackPlugIn\b",
    r"extends\s+AbstractReportFormPlugin\b",
    r"extends\s+AbstractReportListDataPlugin\b",
    r"extends\s+AbstractPrintPlugin\b",
    r"extends\s+AbstractTask\b",
    r"extends\s+BatchImportPlugin\b",
]


def detect_plugin_type(lines: List[str]) -> Tuple[bool, bool, bool]:
    """检测文件是操作插件、UI 插件还是其他继承型插件，返回 (is_op, is_ui, is_other_inheritable)"""
    full_text = "\n".join(lines)
    is_op = any(re.search(p, full_text) for p in OP_PLUGIN_MARKERS)
    is_ui = any(re.search(p, full_text) for p in UI_PLUGIN_MARKERS)
    is_other = any(re.search(p, full_text) for p in OTHER_INHERITABLE_MARKERS)
    return is_op, is_ui, is_other


def _detect_plugin_kind(text: str) -> Optional[str]:
    """基于类声明文本判断当前类属于哪种插件类型。"""
    if any(re.search(p, text) for p in OP_PLUGIN_MARKERS):
        return "op"
    if any(re.search(p, text) for p in UI_PLUGIN_MARKERS):
        return "ui"
    if any(re.search(p, text) for p in OTHER_INHERITABLE_MARKERS):
        return "other"
    return None


def analyze_plugin_context(lines: List[str]) -> List[Optional[str]]:
    """
    基于类声明与 brace 深度分析每一行所在的插件上下文：
    - op: 操作插件类
    - ui: UI 插件类
    - other: 其他继承型插件类
    - None: 非插件类 / 无插件上下文
    """
    contexts: List[Optional[str]] = [None] * len(lines)
    brace_depth = 0
    class_stack: List[Tuple[int, Optional[str]]] = []
    pending_class_decl: List[str] = []

    for i, line in enumerate(lines):
        code = code_for_structure(line)
        stripped = code.strip()
        contexts[i] = class_stack[-1][1] if class_stack else None

        if pending_class_decl:
            if stripped:
                pending_class_decl.append(stripped)
            if "{" in stripped:
                class_text = " ".join(pending_class_decl)
                class_stack.append((brace_depth + 1, _detect_plugin_kind(class_text)))
                pending_class_decl = []
        elif CLASS_DECL_RE.search(stripped):
            pending_class_decl = [stripped]
            if "{" in stripped:
                class_text = " ".join(pending_class_decl)
                class_stack.append((brace_depth + 1, _detect_plugin_kind(class_text)))
                pending_class_decl = []

        brace_depth += code.count("{") - code.count("}")

        while class_stack and brace_depth < class_stack[-1][0]:
            class_stack.pop()

    return contexts


def detect_listener_interfaces(lines: List[str]) -> List[str]:
    """检测文件实现了哪些 Listener 接口"""
    listeners = []
    for line in lines:
        m = re.search(r"implements\s+(.+?)(?:\s*\{|$)", line)
        if m:
            ifaces = [s.strip() for s in m.group(1).split(",")]
            listeners.extend(i for i in ifaces if "Listener" in i)
    return listeners