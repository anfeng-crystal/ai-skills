# -*- coding: utf-8 -*-
"""资源管理检查 (RESOURCE-*) — 来源: anti-patterns.md"""

import re
from typing import List

from .base import LintIssue, Severity, code_for_structure


# 资源持有规则列表
RESOURCE_RULES = [
    {
        "pattern": r"(private|protected|public)\s+(DataSet|InputStream|OutputStream|Connection|ResultSet)\s+\w+\s*;",
        "rule_id": "RESOURCE-001",
        "severity": Severity.WARNING,
        "message": "插件成员变量不应持有 DataSet/InputStream 等资源对象，有序列化问题",
        "fix_hint": "在方法内使用后立即关闭，不持有引用",
    },
    {
        "pattern": r"static\s+(?!final\b)\w+\s+\w+\s*=",
        "rule_id": "RESOURCE-002",
        "severity": Severity.WARNING,
        "message": "不应使用非 final 的 static 变量存储状态，多实例会冲突",
        "fix_hint": "使用 PageCache 或实例变量",
        "exclude_pattern": r"(static\s+final|static\s+\w+\s+[A-Z_]+\s*=|LogFactory|getLogger|Log\s+log)",
    },
    {
        "pattern": r"static\s+final\s+String\s+\w+\s*=\s*ResManager\s*\.\s*loadKDString\s*\(",
        "rule_id": "RESOURCE-003",
        "severity": Severity.WARNING,
        "message": "不要将 ResManager.loadKDString(...) 固化为 static final 常量，运行时语言切换会失效",
        "fix_hint": "改为方法内实时调用 ResManager.loadKDString(...)",
    },
]

DATASET_VAR_DECL_PATTERN = re.compile(r"\bDataSet\s+([A-Za-z_]\w*)\s*=")
DATASET_CLOSE_PATTERN = re.compile(r"\b([A-Za-z_]\w*)\s*\.\s*close\s*\(")
DATASET_TRY_WITH_RESOURCE_PATTERN = re.compile(r"\btry\s*\(\s*DataSet\s+([A-Za-z_]\w*)\s*=")


def check(filepath: str, lines: List[str]) -> List[LintIssue]:
    """执行资源管理检查，返回问题列表。"""
    issues: List[LintIssue] = []
    dataset_vars: dict[str, int] = {}
    closed_dataset_vars: set[str] = set()
    in_try_resource = False

    for i, line in enumerate(lines):
        lineno = i + 1
        code_line = code_for_structure(line)

        decl_match = DATASET_VAR_DECL_PATTERN.search(code_line)
        if decl_match:
            dataset_vars.setdefault(decl_match.group(1), lineno)

        if re.search(r"\btry\s*\(", code_line):
            in_try_resource = True

        if in_try_resource:
            for var_name in DATASET_VAR_DECL_PATTERN.findall(code_line):
                closed_dataset_vars.add(var_name)
            if re.search(r"\)\s*\{", code_line):
                in_try_resource = False
        else:
            try_with_resource_match = DATASET_TRY_WITH_RESOURCE_PATTERN.search(code_line)
            if try_with_resource_match:
                closed_dataset_vars.add(try_with_resource_match.group(1))

        for close_var in DATASET_CLOSE_PATTERN.findall(code_line):
            closed_dataset_vars.add(close_var)

        for rule in RESOURCE_RULES:
            exclude = rule.get("exclude_pattern")
            if exclude and re.search(exclude, code_line):
                continue
            if re.search(rule["pattern"], code_line):
                issues.append(LintIssue(
                    file=filepath, line=lineno,
                    severity=rule["severity"],
                    rule_id=rule["rule_id"],
                    message=rule["message"],
                    fix_hint=rule["fix_hint"],
                    source_line=line.strip(),
                ))

    for var_name, decl_line in dataset_vars.items():
        if var_name not in closed_dataset_vars:
            issues.append(LintIssue(
                file=filepath,
                line=decl_line,
                severity=Severity.ERROR,
                rule_id="RESOURCE-004",
                message=f"检测到 DataSet 变量 `{var_name}` 但未发现 close() 调用",
                fix_hint="在最靠近使用完成的位置调用 close()，避免资源泄漏",
                source_line=lines[decl_line - 1].strip(),
            ))

    return issues