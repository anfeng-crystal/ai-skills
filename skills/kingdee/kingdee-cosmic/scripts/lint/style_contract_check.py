# -*- coding: utf-8 -*-
"""STYLE-024/026/027: type-sensitive suggestions must preserve business contracts."""

import re
from typing import List

from .base import LintIssue, Severity


# Names and call shapes are cues, not proof of runtime types or business meaning.
_PK_NULL = re.compile(r'\b\w*(?:[Ii]d|[Pp]k)\s*(?:==|!=)\s*null\b')
_PK_ZERO = re.compile(r'\b\w*(?:[Ii]d|[Pp]k)\s*==\s*0[Ll]?(?![\w.])')
_PK_GET_NULL = re.compile(r'\.\s*get\s*\(\s*"\w*[Ii]d"\s*\)\s*(?:==|!=)\s*null')
_DECIMAL_PATTERNS = [
    re.compile(r'\.\s*(?:add|subtract|multiply|divide)\s*\(\s*(?:new\s+BigDecimal|BigDecimal\.)'),
    re.compile(r'\.\s*divide\s*\([^)]*RoundingMode'),
    re.compile(r'\.\s*compareTo\s*\(\s*BigDecimal'),
]
_QFILTER_LITERAL = re.compile(r'\bnew\s+QFilter\s*\([^,]+,\s*"[^"\n]*"\s*,')
_LITERAL_OR_COMMENT = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?(?:\*/|$)')


def _live_match(pattern: re.Pattern, raw: str, masked: str) -> bool:
    """Keep offsets while excluding matches starting in literals/inline comments."""
    return any(masked[match.start():match.start() + 1].strip()
               for match in pattern.finditer(raw))


def check_contracts(filepath: str, lineno: int, line: str, raw_code: str) -> List[LintIssue]:
    """Single-line style cues only; do not infer SDK types or rewrite Java code."""
    masked = _LITERAL_OR_COMMENT.sub(lambda match: " " * len(match.group()), raw_code)
    issues: List[LintIssue] = []
    if _live_match(_QFILTER_LITERAL, raw_code, masked):
        issues.append(LintIssue(
            file=filepath, line=lineno, severity=Severity.INFO, rule_id="STYLE-024",
            message="QFilter 使用字符串运算符时，建议核对目标 SDK 的常量与合法取值",
            fix_hint="QCP 提供 String 常量（如 QCP.equals）；确认目标构件支持该运算符后优先复用常量。字面量本身不是错误，也不能仅凭此提示认定任意取值合法",
            source_line=line.strip(),
        ))

    if 'BigDecimalUtils' not in masked and any(p.search(masked) for p in _DECIMAL_PATTERNS):
        issues.append(LintIssue(
            file=filepath, line=lineno, severity=Severity.INFO, rule_id="STYLE-027",
            message="检测到疑似 BigDecimal 运算或比较，工具替换前需核对业务合同",
            fix_hint="保留显式 null 分支、scale、RoundingMode、比较及异常语义；仅在类型与合同等价时复用 BigDecimalUtils，不自动把 null 归零",
            source_line=line.strip(),
        ))

    # Positive/range validation (<= 0, < 1, etc.) is not an empty-PK predicate.
    if not any(name in masked for name in ('isEmptyPk', 'isNotEmptyPk')):
        pk_hit = _PK_NULL.search(masked) or _PK_ZERO.search(masked)
        if pk_hit or _live_match(_PK_GET_NULL, raw_code, masked):
            issues.append(LintIssue(
                file=filepath, line=lineno, severity=Severity.INFO, rule_id="STYLE-026",
                message="主键样式名称的空值比较需按真实类型与业务含义判断",
                fix_hint="先确认主键类型、默认值与空值合同；仅在目标 EntityUtils 类型受支持且语义等价时考虑 isEmptyPk/isNotEmptyPk。查询未命中的 null 判断和正数/范围校验应保留，不机械替换",
                source_line=line.strip(),
            ))
    return issues
