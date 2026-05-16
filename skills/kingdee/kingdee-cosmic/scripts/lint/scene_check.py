# -*- coding: utf-8 -*-
"""场景错配检查 (SCENE-*) — 来源: anti-patterns.md 场景错配表"""

import re
from typing import List

from .base import (
    LintIssue,
    Severity,
    analyze_java_context,
    analyze_plugin_context,
    code_for_structure,
    detect_listener_interfaces,
    detect_plugin_type,
    is_comment_or_string,
)


INITIALIZE_UI_PATTERN = re.compile(
    r"getView\s*\(\)\s*\.\s*"
    r"(setEnable|setVisible|updateView|show\w+|setFocus|setMustInput|setCaption)\s*\("
)
INITIALIZE_LISTENER_PATTERN = re.compile(r"add\w*Listener[s]?\s*\(")
BIND_MUTATION_PATTERN = re.compile(
    r"(?:(?:getModel\s*\(\)|\bmodel)\s*\.\s*"
    r"(setValue|deleteEntryRow|createNewEntryRow|insertEntryRow|batchCreateNewEntryRow|setDataEntity)\s*\()"
    r"|(?:\.\s*setValueFast\s*\()"
)
META_TABLE_PATTERN = re.compile(r"\bt_meta_[A-Za-z0-9_]+\b", re.IGNORECASE)
ENTITY_METADATA_CREATE_PATTERN = re.compile(
    r"EntityMetadataCache\s*\.\s*getDataEntityType\s*\([^)]*\)\s*\.\s*createInstance\s*\("
)


def check(filepath: str, lines: List[str]) -> List[LintIssue]:
    """执行场景错配检查，返回问题列表。"""
    issues: List[LintIssue] = []
    listeners = detect_listener_interfaces(lines)
    method_context, _ = analyze_java_context(lines)
    plugin_context = analyze_plugin_context(lines)

    # ── 逐行检查 ──
    for i, line in enumerate(lines):
        lineno = i + 1
        code_line = code_for_structure(line)
        method_name = (method_context[i] or "").lower()
        is_op_line = plugin_context[i] == "op"

        # SCENE-001: 操作插件不应调 getView()
        if is_op_line and not is_comment_or_string(line):
            if re.search(r"this\s*\.\s*getView\s*\(\s*\)", code_line) or re.search(r"getView\(\)", code_line):
                if not re.search(r"(log\.|getContextSample\s*\()", code_line):
                    issues.append(LintIssue(
                        file=filepath, line=lineno,
                        severity=Severity.WARNING,
                        rule_id="SCENE-001",
                        message="操作插件中调用 getView()：操作插件无 UI 上下文",
                        fix_hint="使用 log 记录日志或 OpUtils.addErrorMessage() 报告错误",
                        source_line=line.strip(),
                    ))

        # SCENE-002: 操作插件不应通过 model 操作
        if is_op_line and not is_comment_or_string(line):
            if re.search(r"this\s*\.\s*getModel\s*\(\s*\)\s*\.\s*setValue", code_line):
                issues.append(LintIssue(
                    file=filepath, line=lineno,
                    severity=Severity.WARNING,
                    rule_id="SCENE-002",
                    message="操作插件中调用 getModel().setValue()：操作插件不通过 model 操作",
                    fix_hint="直接操作 DynamicObject 数据包: dataEntity.set(\"field\", value)",
                    source_line=line.strip(),
                ))

        # SCENE-003: registerListener 中读数据
        if method_name == "registerlistener" and re.search(r"(getModel|getValue)\s*\(", code_line) and not is_comment_or_string(line):
            issues.append(LintIssue(
                file=filepath, line=lineno,
                severity=Severity.WARNING,
                rule_id="SCENE-003",
                message="在 registerListener 中调用 getValue()：此时数据尚未绑定",
                fix_hint="推迟到 afterBindData() 中处理",
                source_line=line.strip(),
            ))

        # SCENE-006: initialize 中注册监听
        if method_name == "initialize" and INITIALIZE_LISTENER_PATTERN.search(code_line):
            issues.append(LintIssue(
                file=filepath, line=lineno,
                severity=Severity.ERROR,
                rule_id="SCENE-006",
                message="禁止在 initialize() 中注册监听事件",
                fix_hint="将 addXxxListener(...) 挪到 registerListener() 中",
                source_line=line.strip(),
            ))

        # SCENE-007: initialize 中做 UI 状态逻辑
        if method_name == "initialize" and INITIALIZE_UI_PATTERN.search(code_line):
            issues.append(LintIssue(
                file=filepath, line=lineno,
                severity=Severity.ERROR,
                rule_id="SCENE-007",
                message="禁止在 initialize() 中处理 UI 状态或弹窗逻辑",
                fix_hint="将界面控制逻辑挪到 afterBindData() 或正确的 UI 事件中",
                source_line=line.strip(),
            ))

        # SCENE-008: before/afterBindData 中修改数据对象
        if method_name in {"beforebinddata", "afterbinddata"} and BIND_MUTATION_PATTERN.search(code_line):
            issues.append(LintIssue(
                file=filepath, line=lineno,
                severity=Severity.ERROR,
                rule_id="SCENE-008",
                message="禁止在 beforeBindData()/afterBindData() 中修改数据对象",
                fix_hint="将 setValue/分录增删等数据变更挪到 createNewData、afterCreateNewData、propertyChanged 或正确的业务事件",
                source_line=line.strip(),
            ))

        # SCENE-009: 直接访问平台元数据表
        if META_TABLE_PATTERN.search(line) and not is_comment_or_string(line):
            issues.append(LintIssue(
                file=filepath, line=lineno,
                severity=Severity.ERROR,
                rule_id="SCENE-009",
                message="业务代码禁止直接访问平台元数据表 t_meta_xxx",
                fix_hint="使用元数据脚本或平台 API 获取字段/实体信息，不要直接查 t_meta_xxx",
                source_line=line.strip(),
            ))

        # SCENE-010: 用其他实体 createInstance() 构造引用对象
        if ENTITY_METADATA_CREATE_PATTERN.search(code_line):
            issues.append(LintIssue(
                file=filepath, line=lineno,
                severity=Severity.ERROR,
                rule_id="SCENE-010",
                message="直接用 EntityMetadataCache.getDataEntityType(...).createInstance() 构造对象，容易出现引用类型不一致",
                fix_hint="优先通过当前实体属性复杂类型或当前实体元数据 createInstance()",
                source_line=line.strip(),
            ))

    # ── 文件级检查: Listener 注册 ──
    if listeners:
        has_register = any(
            re.search(r"void\s+registerListener\s*\(", l) for l in lines
        )
        if not has_register:
            # SCENE-004: 实现了 Listener 但没有 registerListener 方法
            issues.append(LintIssue(
                file=filepath, line=1,
                severity=Severity.WARNING,
                rule_id="SCENE-004",
                message=f"实现了 Listener 接口 ({', '.join(listeners)}) 但未找到 registerListener 方法",
                fix_hint="在 registerListener() 中调用 addXxxListener() 注册监听",
            ))
        else:
            # SCENE-005: 有 registerListener 但没有 addXxxListener 调用
            # 使用 brace depth 精确定位方法体范围
            has_add_listener = False
            in_register = False
            register_brace_depth = 0
            register_started = False
            for line in lines:
                code = code_for_structure(line)
                if not in_register and re.search(r"void\s+registerListener\s*\(", line):
                    in_register = True
                    register_brace_depth = 0
                    register_started = False
                if in_register:
                    register_brace_depth += code.count("{") - code.count("}")
                    if "{" in code:
                        register_started = True
                    if re.search(r"add\w*Listener[s]?\s*\(", code):
                        has_add_listener = True
                    if register_started and register_brace_depth <= 0:
                        in_register = False
            if not has_add_listener:
                issues.append(LintIssue(
                    file=filepath, line=1,
                    severity=Severity.WARNING,
                    rule_id="SCENE-005",
                    message=f"实现了 Listener 接口 ({', '.join(listeners)}) 但 registerListener 中未调用 addXxxListener()",
                    fix_hint="在 registerListener() 中调用对应的 addXxxListener(this) 注册",
                ))

    # ── 文件级检查: 继承型插件 @Override 不调 super ──
    is_op, is_ui, is_other = detect_plugin_type(lines)
    is_inheritable = is_op or is_ui or is_other
    if is_inheritable:
        _check_missing_super(filepath, lines, plugin_context, issues)

    return issues


# 继承型插件生命周期方法（需要调 super 的方法名，全小写）
_LIFECYCLE_METHODS = {
    "initialize", "registerlistener", "preopenform",
    "createnewdata", "aftercreatenewdata", "loaddata", "afterloaddata",
    "beforebinddata", "afterbinddata", "aftercopydata",
    "propertychanged", "beforedooperation", "afterdooperation",
    "beforeitemclick", "itemclick", "beforeclick", "click",
    "beforef7select", "confirmcallback", "closedcallback",
    "clientcallback", "beforeclosed", "customevent",
    "afteraddrow", "afterdeleterow", "afterdeleteentry", "destory",
    "onpreparepropertys", "onaddvalidators",
    "beforeexecuteoperationtransaction", "beginoperationtransaction",
    "endoperationtransaction", "afterexecuteoperationtransaction",
    "onreturnoperation",
    "setfilter", "beforedoselectrow",
}

_OVERRIDE_PATTERN = re.compile(r"@Override")
_METHOD_NAME_PATTERN = re.compile(
    r"(?:public|protected)\s+\w[\w<>\[\], ?.]*\s+([A-Za-z_]\w*)\s*\("
)
_SUPER_CALL_PATTERN_TEMPLATE = r"\bsuper\s*\.\s*{method}\s*\("


def _check_missing_super(filepath: str, lines: List[str],
                         plugin_context: List, issues: List[LintIssue]):
    """检测继承型插件中 @Override 生命周期方法是否遗漏 super 调用。"""
    i = 0
    while i < len(lines):
        line = lines[i]
        if not _OVERRIDE_PATTERN.search(line):
            i += 1
            continue
        # 找到 @Override，向下搜索方法声明（最多看 3 行）
        method_name = None
        method_line = i
        for j in range(i, min(i + 4, len(lines))):
            m = _METHOD_NAME_PATTERN.search(lines[j])
            if m:
                method_name = m.group(1)
                method_line = j
                break
        if method_name and plugin_context[method_line] not in {"op", "ui", "other"}:
            i = method_line + 1
            continue
        if not method_name or method_name.lower() not in _LIFECYCLE_METHODS:
            i += 1
            continue
        # 在方法体内搜索 super.methodName(
        super_pattern = re.compile(
            _SUPER_CALL_PATTERN_TEMPLATE.format(method=re.escape(method_name))
        )
        found_super = False
        brace_count = 0
        started = False
        for k in range(method_line, min(method_line + 50, len(lines))):
            code = code_for_structure(lines[k])
            brace_count += code.count("{") - code.count("}")
            if "{" in code:
                started = True
            if super_pattern.search(code):
                found_super = True
                break
            if started and brace_count <= 0:
                break
        if not found_super:
            issues.append(LintIssue(
                file=filepath, line=method_line + 1,
                severity=Severity.WARNING,
                rule_id="SCENE-011",
                message=f"继承型插件 @Override {method_name}() 未调用 super.{method_name}()，基类初始化逻辑可能不执行",
                fix_hint=f"在方法体首行添加 super.{method_name}(...)；接口型插件（如 IWorkflowPlugin）无需此调用",
                source_line=lines[method_line].strip(),
            ))
        i = method_line + 1