# -*- coding: utf-8 -*-
"""
Java代码循环内禁止方法检测工具
使用 javalang 语法解析器检测循环体内禁止方法的调用
功能：
1. 检测 for/while/do 循环内的禁止方法调用
2. 检测 lambda 表达式中的禁止方法调用
3. 支持类名+方法名的精确匹配
"""

import os
import re
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional

try:
    import javalang
except ImportError:
    print("错误: 请先安装 javalang 库")
    print("执行命令: pip install javalang")
    exit(1)

# 是否开启调试日志
DEBUG_LOG = False

# 调试日志文件
DEBUG_LOG_FILE = None

def debug_log(msg):
    """输出调试日志"""
    if DEBUG_LOG:
        print(msg)
        if DEBUG_LOG_FILE:
            with open(DEBUG_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')

# 技能根目录（当前脚本所在目录）
SCRIPT_DIR = Path(__file__).parent

# 项目根目录（工作空间根目录）
# 脚本位于: .qoder/skills/cosmic-cus-java-scan/scripts/
# 项目根目录是 .qoder 的父目录
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent

# 规则文件路径（相对于脚本目录）
RULE_FILE = SCRIPT_DIR.parent / "references" / "sonar_cve_loop_method.md"


# ==================== 规则解析 ====================

def parse_loop_method_rule_file(rule_file: Path) -> List[Dict]:
    """解析循环内禁止方法规则文件"""
    rules = []
    
    if not rule_file.exists():
        print(f"警告: 规则文件不存在 {rule_file}")
        return rules
    
    with open(rule_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line in lines:
        if line.startswith('|') and '规则编码' not in line and '---' not in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 6:
                rule_code = parts[1]
                rule_name = parts[2]
                rule_level = parts[3]
                rule_config = parts[5]
                solution = parts[6] if len(parts) > 6 else ""
                
                # 解析规则配置: loop class = xxx; loop method = yyy
                class_match = re.search(r'loop\s+class\s*=\s*([^;]+)', rule_config)
                method_match = re.search(r'loop\s+method\s*=\s*([^\s;|]+)', rule_config)
                
                if class_match and method_match:
                    full_class_name = class_match.group(1).strip()
                    method_name = method_match.group(1).strip()
                    class_short_name = full_class_name.split('.')[-1]
                    package_name = '.'.join(full_class_name.split('.')[:-1])
                    
                    rules.append({
                        'rule_code': rule_code,
                        'rule_name': rule_name,
                        'rule_level': rule_level,
                        'full_class_name': full_class_name,
                        'class_short_name': class_short_name,
                        'package_name': package_name,
                        'method_name': method_name,
                        'solution': solution
                    })
    
    return rules


# ==================== 文件查找 ====================

def find_java_files(project_root: Path) -> List[str]:
    """查找所有Java文件"""
    java_files = []
    exclude_dirs = {'build', '.gradle', '.idea', 'gradle', 'target', 'out'}
    project_root = Path(project_root).resolve()
    # 技能根目录（当前脚本所在目录的父目录）
    # 脚本路径: <skill_dir>/scripts/scan_xxx.py
    skill_root = SCRIPT_DIR.parent
    
    for root, dirs, files in os.walk(project_root):
        root_path = Path(root).resolve()
        
        # 检查当前目录是否在技能目录下
        try:
            root_path.relative_to(skill_root)
            is_skill_dir = True
        except ValueError:
            is_skill_dir = False
        
        # 排除目录：构建目录 + 技能目录 + *-cosmic-debug目录
        dirs[:] = [d for d in dirs if d not in exclude_dirs 
                   and not d.endswith('-cosmic-debug')]
        
        # 如果当前目录是技能目录，跳过文件收集
        if is_skill_dir:
            continue
            
        for file in files:
            if file.endswith('.java'):
                java_files.append(os.path.join(root, file))
    return java_files


# ==================== AST工具函数 ====================

def is_node_type(node, node_type_name: str) -> bool:
    """检查节点是否是指定类型（同时支持javalang原生类型和MockNode）
    
    Args:
        node: AST节点
        node_type_name: 类型名称，如 'MethodInvocation', 'StatementExpression' 等
    
    Returns:
        是否匹配该类型
    """
    if node is None:
        return False
    
    # 检查是否是MockNode（JavaParser适配层）
    if hasattr(node, '_node_type'):
        return node._node_type == node_type_name
    
    # 检查javalang原生类型
    try:
        import javalang
        node_class = getattr(javalang.tree, node_type_name, None)
        if node_class:
            return isinstance(node, node_class)
    except:
        pass
    
    return False


def get_node_position(node, lines: List[str] = None) -> Optional[int]:
    """从AST节点提取行号
    
    Args:
        node: AST节点
        lines: 源代码行列表（用于正则fallback）
    """
    # 1. 尝试从节点自身的 position 获取
    if hasattr(node, 'position') and node.position:
        return node.position[0]
    
    # 2. 对于 MethodInvocation，从 qualifier 和 member 推断
    if hasattr(node, 'qualifier') and hasattr(node, 'member') and lines:
        qualifier = node.qualifier
        member = node.member
        if qualifier and member:
            pattern = rf'\b{re.escape(qualifier)}\s*\.\s*{re.escape(member)}\s*\('
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    return i
    
    return None


def get_context(lines: List[str], line_number: int, context_lines: int = 2) -> str:
    """获取问题行的上下文代码"""
    if line_number is None or line_number < 1:
        return "无法获取行号"
    
    start = max(0, line_number - context_lines - 1)
    end = min(len(lines), line_number + context_lines)
    
    context_parts = []
    for i in range(start, end):
        prefix = ">>> " if i == line_number - 1 else "    "
        context_parts.append(f"{prefix}{i + 1}: {lines[i].rstrip()}")
    
    return '\n'.join(context_parts)


# ==================== 违规检测器 ====================

class LoopMethodViolationDetector:
    """
    循环内禁止方法违规检测器
    在遍历AST时跟踪循环上下文
    """
    
    def __init__(self, file_path: str, content: str, rules: List[Dict]):
        self.file_path = file_path
        self.content = content
        self.lines = content.split('\n')
        self.rules = rules
        self.violations = []
        
        # 循环上下文跟踪
        self.loop_depth = 0
        self.current_loop_type = ""
        self.lambda_depth = 0
        
        # 构建规则查找表: (类简称, 方法名) -> [规则列表]
        self.method_rule_map = {}
        
        for rule in rules:
            key = (rule['class_short_name'], rule['method_name'])
            if key not in self.method_rule_map:
                self.method_rule_map[key] = []
            self.method_rule_map[key].append(rule)
        
        # 构建类简称到规则的映射（用于快速查找）
        self.class_method_map = {}
        for rule in rules:
            class_short = rule['class_short_name']
            method = rule['method_name']
            if class_short not in self.class_method_map:
                self.class_method_map[class_short] = {}
            if method not in self.class_method_map[class_short]:
                self.class_method_map[class_short][method] = []
            self.class_method_map[class_short][method].append(rule)
        
        # 跨方法检测：记录包含禁止方法调用的方法
        self.methods_with_forbidden_calls = {}  # 方法名 -> [(行号, 类名, 方法名), ...]
        
        # 变量类型追踪：变量名 -> 类型名
        self.local_variables = {}  # 方法内的局部变量类型映射
    
    def is_in_loop(self) -> Tuple[bool, str]:
        """判断当前是否在循环内"""
        if self.loop_depth > 0:
            return True, self.current_loop_type
        if self.lambda_depth > 0:
            return True, "lambda表达式"
        return False, ""
    
    def _get_method_return_type(self, method_name: str) -> Optional[str]:
        """获取方法的返回类型（类简称）
        
        用于链式调用分析，例如 getView() 返回 IFormView
        """
        # 方法返回类型映射表
        # 键：方法名，值：返回类型的类简称
        method_return_types = {
            'getView': 'IFormView',
            # 可以在这里添加更多方法返回类型映射
        }
        return method_return_types.get(method_name)
    
    def _collect_method_invocations(self, node) -> List[javalang.tree.MethodInvocation]:
        """递归收集节点中的所有方法调用"""
        methods = []
        
        if isinstance(node, javalang.tree.MethodInvocation):
            methods.append(node)
        
        # 递归检查所有子节点
        for attr_name in dir(node):
            if attr_name.startswith('_'):
                continue
            try:
                attr = getattr(node, attr_name)
                if isinstance(attr, javalang.tree.MethodInvocation):
                    methods.append(attr)
                    methods.extend(self._collect_method_invocations(attr))
                elif isinstance(attr, list):
                    for item in attr:
                        if isinstance(item, javalang.tree.MethodInvocation):
                            methods.append(item)
                            methods.extend(self._collect_method_invocations(item))
                        elif hasattr(item, '__dict__'):
                            methods.extend(self._collect_method_invocations(item))
                elif hasattr(attr, '__dict__'):
                    methods.extend(self._collect_method_invocations(attr))
            except:
                pass
        
        return methods
    
    def _check_method_chain(self, methods: List[javalang.tree.MethodInvocation], in_loop: bool, loop_type: str, context: str):
        """检查方法调用链中的违规
        
        例如：this.getView().updateView()
        需要识别 getView() 返回 IFormView，然后 updateView() 是 IFormView 的方法
        """
        if not methods or not in_loop:
            return
        
        # 按顺序处理方法调用链
        current_class = None
        
        for i, method in enumerate(methods):
            member = getattr(method, 'member', None)
            if not member:
                continue
            
            # 检查当前方法是否匹配规则
            if current_class and in_loop:
                self._check_method_violation(method, current_class, member, loop_type, context)
            
            # 更新当前类为该方法返回的类型
            current_class = self._get_method_return_type(member)
    
    def detect(self) -> List[Dict]:
        """执行检测（支持跨方法调用链检测）"""
        # 使用统一解析器（javalang + 预处理 + JavaParser fallback）
        from java_parser_unified import parse_java_code
        
        tree = parse_java_code(self.content)
        self.preprocessor = None
        
        if tree is None:
            if DEBUG_LOG:
                print(f"    [警告] 所有解析器均失败")
            return []
        
        # 检查是否使用了JavaParser适配层
        if hasattr(tree, '_javaparser_adapted') and hasattr(tree, '_javaparser_result'):
            # 使用统一的JavaParser检测函数
            from javaparser_adapter import detect_loop_violations_from_javaparser
            return detect_loop_violations_from_javaparser(
                jp_result=tree._javaparser_result,
                rules_map=self.class_method_map,
                file_path=self.file_path,
                lines=self.lines,
                get_context_func=get_context,
                match_type_prefix="循环内调用"
            )
        
        # 检查是否使用了预处理
        if hasattr(tree, '_preprocessor'):
            self.preprocessor = tree._preprocessor
        
        # 收集import信息
        self.imported_classes = {}
        if tree.imports:
            for imp in tree.imports:
                if imp.path and not imp.wildcard:
                    class_name = imp.path.split('.')[-1]
                    self.imported_classes[class_name] = imp.path
        
        # 第一阶段：收集所有方法及其包含的禁止方法调用
        self.methods_with_forbidden_calls = {}  # 方法签名 -> 禁止调用列表
        self.method_nodes = {}  # 方法签名 -> AST节点
        self.method_signatures = {}  # 方法名 -> [方法签名列表] 用于支持重载
        if tree.types:
            for type_decl in tree.types:
                if hasattr(type_decl, 'body') and type_decl.body:
                    self._collect_methods_with_forbidden_calls(type_decl.body)
        
        # 第二阶段：扫描类成员（常规检测）
        if tree.types:
            for type_decl in tree.types:
                if hasattr(type_decl, 'body') and type_decl.body:
                    self._scan_members(type_decl.body)
        
        # 后处理：恢复预处理时替换的占位符
        if self.preprocessor:
            self.violations = self.preprocessor.postprocess_violations(self.violations)
        
        return self.violations
    
    def _get_method_signature(self, method) -> str:
        """获取方法签名（方法名_参数数量），用于区分重载方法"""
        method_name = getattr(method, 'name', None)
        if not method_name:
            return None
        
        # 获取参数数量
        params = getattr(method, 'parameters', None)
        param_count = len(params) if params else 0
        
        return f"{method_name}_{param_count}"
    
    def _get_method_name_from_signature(self, signature: str) -> str:
        """从方法签名中提取方法名"""
        if '_' in signature:
            return signature.rsplit('_', 1)[0]
        return signature
    
    def _collect_methods_with_forbidden_calls(self, members: List):
        """第一阶段：收集包含禁止方法调用的方法（支持递归调用链）"""
        # 首先收集所有方法节点（使用签名作为key以支持重载）
        for member in members:
            if isinstance(member, javalang.tree.MethodDeclaration):
                method_name = getattr(member, 'name', None)
                signature = self._get_method_signature(member)
                if signature:
                    self.method_nodes[signature] = member
                    # 同时记录方法名到签名的映射
                    if method_name not in self.method_signatures:
                        self.method_signatures[method_name] = []
                    self.method_signatures[method_name].append(signature)
        
        if DEBUG_LOG:
            debug_log(f"    [跨方法检测] 收集到的方法: {list(self.method_signatures.keys())}")
        
        # 然后递归收集每个方法的禁止方法调用（包括跨方法调用）
        for signature in self.method_nodes:
            # 收集该方法的局部变量类型
            method = self.method_nodes[signature]
            self._collect_method_local_variables(method)
            
            forbidden_calls = self._find_forbidden_calls_in_method_recursive(signature, set())
            if forbidden_calls:
                self.methods_with_forbidden_calls[signature] = forbidden_calls
                if DEBUG_LOG:
                    debug_log(f"    [跨方法检测] 方法 {signature} 包含禁止调用: {forbidden_calls}")
    
    def _collect_method_local_variables(self, method):
        """收集方法的局部变量类型"""
        self.local_variables = {}
        body = getattr(method, 'body', None)
        if not body:
            return
        
        for stmt in body:
            self._collect_variable_type_from_statement(stmt)
    
    def _find_forbidden_calls_in_method_recursive(self, method_signature: str, visited: set) -> List[Tuple]:
        """递归查找方法及其调用的方法中所有的禁止方法调用"""
        if method_signature in visited:
            return []  # 避免循环调用
        
        visited.add(method_signature)
        
        method = self.method_nodes.get(method_signature)
        if not method:
            return []
        
        # 收集该方法的局部变量类型（用于变量类型匹配）
        self._collect_method_local_variables(method)
        
        forbidden_calls = []
        body = getattr(method, 'body', None)
        if not body:
            return forbidden_calls
        
        for stmt in body:
            self._find_forbidden_calls_and_calls_in_statement(stmt, forbidden_calls, visited)
        
        return forbidden_calls
    
    def _find_forbidden_calls_and_calls_in_statement(self, stmt, forbidden_calls: List, visited: set):
        """递归查找语句中的禁止方法调用和方法调用"""
        if stmt is None:
            return
        
        # 表达式语句
        if isinstance(stmt, javalang.tree.StatementExpression):
            expr = getattr(stmt, 'expression', None)
            if expr:
                self._find_forbidden_calls_and_calls_in_expression(expr, forbidden_calls, visited)
        
        # 局部变量声明
        elif isinstance(stmt, javalang.tree.LocalVariableDeclaration):
            declarators = getattr(stmt, 'declarators', None)
            if DEBUG_LOG and 'isRepeatBom' in str(visited):
                debug_log(f"    [跨方法检测] 处理LocalVariableDeclaration: declarators={declarators is not None}")
            if declarators:
                for decl in declarators:
                    init = getattr(decl, 'initializer', None)
                    if DEBUG_LOG and 'isRepeatBom' in str(visited) and init:
                        debug_log(f"    [跨方法检测]   initializer type={type(init)}")
                    if init:
                        self._find_forbidden_calls_and_calls_in_expression(init, forbidden_calls, visited)
        
        # return语句
        elif isinstance(stmt, javalang.tree.ReturnStatement):
            ret_expr = getattr(stmt, 'expression', None)
            if ret_expr:
                self._find_forbidden_calls_and_calls_in_expression(ret_expr, forbidden_calls, visited)
        
        # if语句
        elif isinstance(stmt, javalang.tree.IfStatement):
            if DEBUG_LOG and 'isRepeatBom' in str(visited):
                debug_log(f"    [跨方法检测] 处理IfStatement: then_stmt type={type(getattr(stmt, 'then_statement', None))}")
            condition = getattr(stmt, 'condition', None)
            if condition:
                self._find_forbidden_calls_and_calls_in_expression(condition, forbidden_calls, visited)
            then_stmt = getattr(stmt, 'then_statement', None)
            else_stmt = getattr(stmt, 'else_statement', None)
            if then_stmt:
                self._find_forbidden_calls_and_calls_in_statement(then_stmt, forbidden_calls, visited)
            if else_stmt:
                self._find_forbidden_calls_and_calls_in_statement(else_stmt, forbidden_calls, visited)
        
        # 循环语句
        elif isinstance(stmt, (javalang.tree.ForStatement, javalang.tree.WhileStatement, javalang.tree.DoStatement)):
            body = getattr(stmt, 'body', None)
            if body:
                if hasattr(body, 'statements'):
                    for s in body.statements:
                        self._find_forbidden_calls_and_calls_in_statement(s, forbidden_calls, visited)
                elif isinstance(body, (list, tuple)):
                    for s in body:
                        self._find_forbidden_calls_and_calls_in_statement(s, forbidden_calls, visited)
                else:
                    self._find_forbidden_calls_and_calls_in_statement(body, forbidden_calls, visited)
        
        # try-catch
        elif isinstance(stmt, javalang.tree.TryStatement):
            # 处理 try-with-resources 的资源声明部分
            resources = getattr(stmt, 'resources', None)
            if resources:
                for resource in resources:
                    # TryResource 有多种属性：name, type, value, modifiers
                    # value 是初始化表达式
                    resource_value = getattr(resource, 'value', None)
                    if resource_value:
                        self._find_forbidden_calls_and_calls_in_expression(resource_value, forbidden_calls, visited)
                    # 也检查其他可能的属性
                    for attr in ['name', 'type']:
                        attr_val = getattr(resource, attr, None)
                        if attr_val and hasattr(attr_val, '__dict__'):
                            self._find_forbidden_calls_and_calls_in_expression(attr_val, forbidden_calls, visited)
            
            try_block = getattr(stmt, 'block', None)
            if try_block:
                for s in try_block:
                    self._find_forbidden_calls_and_calls_in_statement(s, forbidden_calls, visited)
            catches = getattr(stmt, 'catches', None)
            if catches:
                for catch in catches:
                    catch_block = getattr(catch, 'block', None)
                    if catch_block:
                        for s in catch_block:
                            self._find_forbidden_calls_and_calls_in_statement(s, forbidden_calls, visited)
            
            # 处理 finally 块
            finally_block = getattr(stmt, 'finally_block', None)
            if finally_block:
                for s in finally_block:
                    self._find_forbidden_calls_and_calls_in_statement(s, forbidden_calls, visited)
        
        # 代码块
        elif isinstance(stmt, (list, tuple)):
            for s in stmt:
                self._find_forbidden_calls_and_calls_in_statement(s, forbidden_calls, visited)
        
        # BlockStatement
        elif hasattr(stmt, 'statements'):
            statements = getattr(stmt, 'statements', None)
            if DEBUG_LOG and 'isRepeatBom' in str(visited):
                debug_log(f"    [跨方法检测] 处理BlockStatement: statements type={type(statements)}, len={len(statements) if statements else 0}")
            if statements:
                for s in statements:
                    self._find_forbidden_calls_and_calls_in_statement(s, forbidden_calls, visited)
    
    def _find_forbidden_calls_and_calls_in_expression(self, expr, forbidden_calls: List, visited: set):
        """递归查找表达式中的禁止方法调用和方法调用"""
        if expr is None:
            return
        
        # 方法调用
        if isinstance(expr, javalang.tree.MethodInvocation):
            qualifier = getattr(expr, 'qualifier', None)
            member = getattr(expr, 'member', None)
            
            # 调试日志：记录方法调用
            if DEBUG_LOG and member in ['getFilterTest', 'queryPeriod', 'loadFromCache', 'queryDataSet', 'isRepeatBom', 'getEntryDataSet']:
                debug_log(f"    [跨方法检测] MethodInvocation: member={member}, qualifier={qualifier}")
                debug_log(f"    [跨方法检测]   class_method_map keys: {list(self.class_method_map.keys())[:10]}...")
                if qualifier in self.class_method_map:
                    debug_log(f"    [跨方法检测]   {qualifier} methods: {list(self.class_method_map[qualifier].keys())}")
            
            # 检查是否是禁止类的方法调用
            if qualifier and member and qualifier in self.class_method_map:
                if member in self.class_method_map[qualifier]:
                    line_num = get_node_position(expr)
                    forbidden_calls.append((line_num, qualifier, member))
                    if DEBUG_LOG:
                        debug_log(f"    [跨方法检测] 发现禁止调用: {qualifier}.{member} at line {line_num}")
            
            # 检查是否是变量类型匹配（实例方法调用）
            if qualifier and member and qualifier in self.local_variables:
                var_type = self.local_variables[qualifier]
                if var_type in self.class_method_map:
                    if member in self.class_method_map[var_type]:
                        line_num = get_node_position(expr)
                        forbidden_calls.append((line_num, var_type, member))
            
            # 检查是否是本类方法调用（跨方法调用链）
            # 支持方法重载：遍历所有匹配的方法签名
            # qualifier 为 None 或 "this" 时，视为本类方法调用
            if member and (not qualifier or qualifier == "this") and member in self.method_signatures:
                # 获取该方法的所有重载版本
                signatures = self.method_signatures[member]
                for sig in signatures:
                    # 递归查找被调用方法中的禁止方法调用
                    nested_calls = self._find_forbidden_calls_in_method_recursive(sig, visited.copy())
                    forbidden_calls.extend(nested_calls)
                    if DEBUG_LOG and nested_calls:
                        debug_log(f"    [跨方法检测] 从 {member} 递归发现 {len(nested_calls)} 个禁止调用")
            
            # 递归检查参数
            args = getattr(expr, 'arguments', None)
            if args:
                for arg in args:
                    self._find_forbidden_calls_and_calls_in_expression(arg, forbidden_calls, visited)
            
            # 递归检查 selectors
            expr_selectors = getattr(expr, 'selectors', None)
            if expr_selectors:
                for selector in expr_selectors:
                    self._find_forbidden_calls_and_calls_in_expression(selector, forbidden_calls, visited)
        
        # 类创建
        elif isinstance(expr, javalang.tree.ClassCreator):
            args = getattr(expr, 'arguments', None)
            if args:
                for arg in args:
                    self._find_forbidden_calls_and_calls_in_expression(arg, forbidden_calls, visited)
        
        # 赋值表达式
        elif isinstance(expr, javalang.tree.Assignment):
            expr_val = getattr(expr, 'value', None)
            if expr_val:
                self._find_forbidden_calls_and_calls_in_expression(expr_val, forbidden_calls, visited)
        
        # 二元运算
        elif isinstance(expr, javalang.tree.BinaryOperation):
            left = getattr(expr, 'operandl', None)
            right = getattr(expr, 'operandr', None)
            if left:
                self._find_forbidden_calls_and_calls_in_expression(left, forbidden_calls, visited)
            if right:
                self._find_forbidden_calls_and_calls_in_expression(right, forbidden_calls, visited)
        
        # 三元表达式
        elif isinstance(expr, javalang.tree.TernaryExpression):
            condition = getattr(expr, 'condition', None)
            if_true = getattr(expr, 'if_true', None) or getattr(expr, 'true_expression', None)
            if_false = getattr(expr, 'if_false', None) or getattr(expr, 'false_expression', None)
            if condition:
                self._find_forbidden_calls_and_calls_in_expression(condition, forbidden_calls, visited)
            if if_true:
                self._find_forbidden_calls_and_calls_in_expression(if_true, forbidden_calls, visited)
            if if_false:
                self._find_forbidden_calls_and_calls_in_expression(if_false, forbidden_calls, visited)
        
        # 类型转换表达式: (Type) expression
        elif isinstance(expr, javalang.tree.Cast):
            cast_expr = getattr(expr, 'expression', None)
            if cast_expr:
                self._find_forbidden_calls_and_calls_in_expression(cast_expr, forbidden_calls, visited)
        
        # This 表达式 (如 this.detailOperation())
        # javalang 将 this.method() 解析为 This 节点，方法调用在 selectors 中
        elif isinstance(expr, javalang.tree.This):
            this_selectors = getattr(expr, 'selectors', None)
            if this_selectors:
                for selector in this_selectors:
                    if isinstance(selector, javalang.tree.MethodInvocation):
                        member = getattr(selector, 'member', None)
                        
                        # 检查是否是本类方法调用（跨方法调用链）
                        if member and member in self.method_signatures:
                            signatures = self.method_signatures[member]
                            for sig in signatures:
                                nested_calls = self._find_forbidden_calls_in_method_recursive(sig, visited.copy())
                                forbidden_calls.extend(nested_calls)
                        
                        # 递归检查参数
                        args = getattr(selector, 'arguments', None)
                        if args:
                            for arg in args:
                                self._find_forbidden_calls_and_calls_in_expression(arg, forbidden_calls, visited)
                        
                        # 检查嵌套 selectors
                        nested_selectors = getattr(selector, 'selectors', None)
                        if nested_selectors:
                            for ns in nested_selectors:
                                self._find_forbidden_calls_and_calls_in_expression(ns, forbidden_calls, visited)
                    else:
                        # 非 MethodInvocation 的 selector，递归处理
                        self._find_forbidden_calls_and_calls_in_expression(selector, forbidden_calls, visited)
    
    def _scan_members(self, members: List):
        """扫描类成员"""
        for member in members:
            if isinstance(member, javalang.tree.MethodDeclaration):
                self._scan_method(member)
            elif isinstance(member, javalang.tree.ConstructorDeclaration):
                self._scan_constructor(member)
            elif isinstance(member, javalang.tree.FieldDeclaration):
                declarators = getattr(member, 'declarators', None)
                if declarators:
                    for decl in declarators:
                        init = getattr(decl, 'initializer', None)
                        if init:
                            self._check_expression(init, "字段初始化")
    
    def _scan_method(self, method):
        """扫描方法体"""
        # 重置局部变量类型映射
        self.local_variables = {}
        
        # 收集方法内的局部变量类型
        self._collect_local_variable_types(method)
        
        body = getattr(method, 'body', None)
        if body:
            for stmt in body:
                self._scan_statement(stmt)
    
    def _collect_local_variable_types(self, method):
        """收集方法内的局部变量类型"""
        body = getattr(method, 'body', None)
        if not body:
            return
        
        for stmt in body:
            self._collect_variable_type_from_statement(stmt)
    
    def _collect_variable_type_from_statement(self, stmt):
        """从语句中收集变量类型"""
        if stmt is None:
            return
        
        # 局部变量声明
        if isinstance(stmt, javalang.tree.LocalVariableDeclaration):
            type_node = getattr(stmt, 'type', None)
            declarators = getattr(stmt, 'declarators', None)
            if type_node and declarators:
                type_name = self._get_type_name(type_node)
                for decl in declarators:
                    var_name = getattr(decl, 'name', None)
                    if var_name and type_name:
                        self.local_variables[var_name] = type_name
        
        # for 循环
        elif isinstance(stmt, javalang.tree.ForStatement):
            ctrl = getattr(stmt, 'control', None)
            if ctrl:
                init = getattr(ctrl, 'init', None)
                if init:
                    if isinstance(init, list):
                        for i in init:
                            self._collect_variable_type_from_statement(i)
                    else:
                        self._collect_variable_type_from_statement(init)
            body = getattr(stmt, 'body', None)
            if body:
                if hasattr(body, 'statements'):
                    for s in body.statements:
                        self._collect_variable_type_from_statement(s)
                elif isinstance(body, (list, tuple)):
                    for s in body:
                        self._collect_variable_type_from_statement(s)
        
        # while 循环
        elif isinstance(stmt, javalang.tree.WhileStatement):
            body = getattr(stmt, 'body', None)
            if body:
                if hasattr(body, 'statements'):
                    for s in body.statements:
                        self._collect_variable_type_from_statement(s)
                elif isinstance(body, (list, tuple)):
                    for s in body:
                        self._collect_variable_type_from_statement(s)
        
        # if 语句
        elif isinstance(stmt, javalang.tree.IfStatement):
            then_stmt = getattr(stmt, 'then_statement', None)
            else_stmt = getattr(stmt, 'else_statement', None)
            if then_stmt:
                if hasattr(then_stmt, 'statements'):
                    for s in then_stmt.statements:
                        self._collect_variable_type_from_statement(s)
                elif isinstance(then_stmt, (list, tuple)):
                    for s in then_stmt:
                        self._collect_variable_type_from_statement(s)
            if else_stmt:
                if hasattr(else_stmt, 'statements'):
                    for s in else_stmt.statements:
                        self._collect_variable_type_from_statement(s)
                elif isinstance(else_stmt, (list, tuple)):
                    for s in else_stmt:
                        self._collect_variable_type_from_statement(s)
        
        # try-catch
        elif isinstance(stmt, javalang.tree.TryStatement):
            try_block = getattr(stmt, 'block', None)
            if try_block:
                for s in try_block:
                    self._collect_variable_type_from_statement(s)
            catches = getattr(stmt, 'catches', None)
            if catches:
                for catch in catches:
                    catch_block = getattr(catch, 'block', None)
                    if catch_block:
                        for s in catch_block:
                            self._collect_variable_type_from_statement(s)
            finally_block = getattr(stmt, 'finally_block', None)
            if finally_block:
                for s in finally_block:
                    self._collect_variable_type_from_statement(s)
        
        # 代码块
        elif isinstance(stmt, (list, tuple)):
            for s in stmt:
                self._collect_variable_type_from_statement(s)
        
        elif hasattr(stmt, 'statements'):
            statements = getattr(stmt, 'statements', None)
            if statements:
                for s in statements:
                    self._collect_variable_type_from_statement(s)
    
    def _get_type_name(self, type_node) -> Optional[str]:
        """从类型节点获取类型名称"""
        if type_node is None:
            return None
        
        # 简单类型名
        if isinstance(type_node, str):
            return type_node
        
        # 复杂类型（如数组、泛型等）
        if hasattr(type_node, 'name'):
            return type_node.name
        
        return None
    
    def _scan_constructor(self, ctor):
        """扫描构造函数"""
        body = getattr(ctor, 'body', None)
        if body:
            for stmt in body:
                self._scan_statement(stmt)
    
    def _scan_loop_body(self, body):
        """
        扫描循环体，正确处理BlockStatement
        javalang的循环体body可能是：
        1. BlockStatement对象（有statements属性）
        2. list列表
        3. 单条语句
        """
        if body is None:
            return
        
        # 如果是BlockStatement，获取其statements属性
        if hasattr(body, 'statements'):
            statements = getattr(body, 'statements', None)
            if statements:
                for s in statements:
                    self._scan_statement(s)
        elif isinstance(body, (list, tuple)):
            for s in body:
                self._scan_statement(s)
        else:
            # 单条语句
            self._scan_statement(body)
    
    def _scan_statement(self, stmt):
        """扫描语句"""
        if stmt is None:
            return
        
        # 表达式语句
        if isinstance(stmt, javalang.tree.StatementExpression):
            expr = getattr(stmt, 'expression', None) or getattr(stmt, 'expressionl', None)
            if expr:
                self._check_expression(expr, "")
        
        # 局部变量声明
        elif isinstance(stmt, javalang.tree.LocalVariableDeclaration):
            declarators = getattr(stmt, 'declarators', None)
            if declarators:
                for decl in declarators:
                    init = getattr(decl, 'initializer', None)
                    if init:
                        self._check_expression(init, "")
        
        # return语句
        elif isinstance(stmt, javalang.tree.ReturnStatement):
            ret_expr = getattr(stmt, 'expression', None) or getattr(stmt, 'expressionl', None)
            if ret_expr:
                self._check_expression(ret_expr, "")
        
        # if语句
        elif isinstance(stmt, javalang.tree.IfStatement):
            condition = getattr(stmt, 'condition', None)
            if condition:
                self._check_expression(condition, "")
            
            then_stmt = getattr(stmt, 'then_statement', None)
            else_stmt = getattr(stmt, 'else_statement', None)
            
            if then_stmt:
                self._scan_loop_body(then_stmt)
            if else_stmt:
                self._scan_loop_body(else_stmt)
        
        # for循环 - 进入循环上下文
        elif isinstance(stmt, javalang.tree.ForStatement):
            ctrl = getattr(stmt, 'control', None)
            body = getattr(stmt, 'body', None)
            
            # 检查循环控制部分（不在循环体内）
            if ctrl:
                init = getattr(ctrl, 'init', None)
                if init:
                    if isinstance(init, list):
                        for i in init:
                            self._check_expression(i, "")
                    else:
                        self._check_expression(init, "")
                
                cond = getattr(ctrl, 'condition', None)
                if cond:
                    self._check_expression(cond, "")
                
                update = getattr(ctrl, 'update', None)
                if update:
                    for u in update:
                        self._check_expression(u, "")
            
            # 进入循环体
            self.loop_depth += 1
            self.current_loop_type = "for循环"
            
            self._scan_loop_body(body)
            
            self.loop_depth -= 1
        
        # while循环 - 进入循环上下文
        elif isinstance(stmt, javalang.tree.WhileStatement):
            condition = getattr(stmt, 'condition', None)
            body = getattr(stmt, 'body', None)
            
            # 条件不在循环体内
            if condition:
                self._check_expression(condition, "")
            
            # 进入循环体
            self.loop_depth += 1
            self.current_loop_type = "while循环"
            
            self._scan_loop_body(body)
            
            self.loop_depth -= 1
        
        # do循环 - 进入循环上下文
        elif isinstance(stmt, javalang.tree.DoStatement):
            condition = getattr(stmt, 'condition', None)
            body = getattr(stmt, 'body', None)
            
            # 进入循环体
            self.loop_depth += 1
            self.current_loop_type = "do循环"
            
            self._scan_loop_body(body)
            
            self.loop_depth -= 1
            
            # 条件不在循环体内
            if condition:
                self._check_expression(condition, "")
        
        # try-catch
        elif isinstance(stmt, javalang.tree.TryStatement):
            # 处理 try-with-resources 的资源声明部分
            resources = getattr(stmt, 'resources', None)
            if resources:
                for resource in resources:
                    # resource 是 TryResource 类型，有 value 属性
                    resource_value = getattr(resource, 'value', None)
                    if resource_value:
                        self._check_expression(resource_value, "")
            
            try_block = getattr(stmt, 'block', None)
            catches = getattr(stmt, 'catches', None)
            
            if try_block:
                for s in try_block:
                    self._scan_statement(s)
            
            if catches:
                for catch in catches:
                    catch_block = getattr(catch, 'block', None)
                    if catch_block:
                        for s in catch_block:
                            self._scan_statement(s)
            
            # 处理 finally 块
            finally_block = getattr(stmt, 'finally_block', None)
            if finally_block:
                for s in finally_block:
                    self._scan_statement(s)
        
        # 代码块
        elif isinstance(stmt, (list, tuple)):
            for s in stmt:
                self._scan_statement(s)
        
        # BlockStatement (javalang的代码块包装)
        elif hasattr(stmt, 'statements'):
            statements = getattr(stmt, 'statements', None)
            if statements:
                for s in statements:
                    self._scan_statement(s)
    
    def _check_expression(self, expr, context: str, chain_qualifier: str = None):
        """检查表达式中的违规
        
        Args:
            expr: 表达式节点
            context: 上下文描述
            chain_qualifier: 链式调用中的类限定符（用于处理 this.getView().updateView() 这种情况）
        """
        if expr is None:
            return
        
        in_loop, loop_type = self.is_in_loop()
        
        if DEBUG_LOG:
            debug_log(f"    [_check_expression] type={type(expr).__name__}, in_loop={in_loop}")
        
        # 处理 This 表达式（如 this.getView().updateView()）
        # javalang 会将这种链式调用解析为 This 对象包含多个 MethodInvocation
        if isinstance(expr, javalang.tree.This):
            # 处理链式调用：跟踪每个方法返回的类型
            this_selectors = getattr(expr, 'selectors', None)
            if DEBUG_LOG:
                debug_log(f"    [This表达式] 发现This! selectors数量={len(this_selectors) if this_selectors else 0}")
            if this_selectors and in_loop:
                self._check_chain_selectors(this_selectors, loop_type, context)
            return
        
        # 方法调用
        if isinstance(expr, javalang.tree.MethodInvocation):
            qualifier = getattr(expr, 'qualifier', None)
            member = getattr(expr, 'member', None)
            
            # 检查禁止方法调用（直接调用）
            if qualifier and member and in_loop:
                # 先尝试直接匹配类名
                self._check_method_violation(expr, qualifier, member, loop_type, context)
                
                # 如果直接匹配失败，尝试通过变量类型匹配
                if qualifier in self.local_variables:
                    var_type = self.local_variables[qualifier]
                    self._check_method_violation(expr, var_type, member, loop_type, context)
            
            # 检查链式调用中的方法（如 this.getView().updateView()）
            # 如果当前方法没有qualifier，但chain_qualifier存在，则使用chain_qualifier
            if not qualifier and chain_qualifier and member and in_loop:
                self._check_method_violation(expr, chain_qualifier, member, loop_type, context)
            
            # 跨方法检测：检查调用的方法是否包含禁止方法调用
            if member and in_loop:
                self._check_cross_method_call(expr, member, loop_type, context)
            
            # 递归检查参数
            args = getattr(expr, 'arguments', None)
            if args:
                for arg in args:
                    self._check_expression(arg, context)
            
            # 递归检查 selectors（链式调用）
            # 对于 this.getView().updateView()，getView() 是主调用，updateView() 是 selector
            # 需要传递类型信息给 selector
            expr_selectors = getattr(expr, 'selectors', None)
            if expr_selectors:
                # 判断当前方法是否返回特定类型的对象
                # 例如 getView() 返回 IFormView，所以其 selectors 应该使用 IFormView 作为 qualifier
                selector_qualifier = self._get_method_return_type(member)
                for selector in expr_selectors:
                    self._check_expression(selector, context, selector_qualifier)
        
        # 类创建: new ClassName()
        elif isinstance(expr, javalang.tree.ClassCreator):
            args = getattr(expr, 'arguments', None)
            if args:
                for arg in args:
                    self._check_expression(arg, context)
        
        # 赋值表达式
        elif isinstance(expr, javalang.tree.Assignment):
            # Assignment节点的value属性是右侧表达式
            expr_val = getattr(expr, 'value', None)
            if expr_val:
                self._check_expression(expr_val, context)
        
        # 二元运算
        elif isinstance(expr, javalang.tree.BinaryOperation):
            left = getattr(expr, 'operandl', None)
            right = getattr(expr, 'operandr', None)
            if left:
                self._check_expression(left, context)
            if right:
                self._check_expression(right, context)
        
        # 三元表达式
        elif isinstance(expr, javalang.tree.TernaryExpression):
            condition = getattr(expr, 'condition', None)
            if_true = getattr(expr, 'if_true', None) or getattr(expr, 'true_expression', None)
            if_false = getattr(expr, 'if_false', None) or getattr(expr, 'false_expression', None)
            
            if condition:
                self._check_expression(condition, context)
            if if_true:
                self._check_expression(if_true, context)
            if if_false:
                self._check_expression(if_false, context)
        
        # Lambda表达式 - 进入lambda上下文
        elif isinstance(expr, javalang.tree.LambdaExpression):
            self.lambda_depth += 1
            
            body = getattr(expr, 'body', None)
            if body:
                if isinstance(body, list):
                    for s in body:
                        self._scan_statement(s)
                else:
                    self._check_expression(body, context)
            
            self.lambda_depth -= 1
        
        # 方法引用 - 如 BusinessDataServiceHelper::loadRefence
        elif isinstance(expr, javalang.tree.MethodReference):
            # 方法引用的格式: ClassName::methodName
            # expression 是类名，method 是方法名
            # 注意: MethodReference 节点本身的 position 为 None，需要从子节点获取
            ref_expression = getattr(expr, 'expression', None)
            ref_method = getattr(expr, 'method', None)
            
            if ref_expression and ref_method and in_loop:
                # ref_expression 可能是 MemberReference 类型
                class_name = None
                line_num = None
                if isinstance(ref_expression, javalang.tree.MemberReference):
                    class_name = getattr(ref_expression, 'member', None)
                    # 获取行号 - 从 expression 子节点
                    if hasattr(ref_expression, 'position') and ref_expression.position:
                        line_num = ref_expression.position[0]
                elif isinstance(ref_expression, str):
                    class_name = ref_expression
                else:
                    # 尝试获取 member 属性
                    class_name = getattr(ref_expression, 'member', None)
                    if hasattr(ref_expression, 'position') and ref_expression.position:
                        line_num = ref_expression.position[0]
                
                # 获取方法名
                method_name = None
                if isinstance(ref_method, javalang.tree.MemberReference):
                    method_name = getattr(ref_method, 'member', None)
                    # 如果还没获取到行号，从 method 子节点获取
                    if not line_num and hasattr(ref_method, 'position') and ref_method.position:
                        line_num = ref_method.position[0]
                elif isinstance(ref_method, str):
                    method_name = ref_method
                else:
                    method_name = getattr(ref_method, 'member', None)
                    if not line_num and hasattr(ref_method, 'position') and ref_method.position:
                        line_num = ref_method.position[0]
                
                if class_name and method_name:
                    self._check_method_violation(expr, class_name, method_name, loop_type, context, 
                                                  is_method_reference=True, override_line_num=line_num)
    
    def _check_cross_method_call(self, expr, method_name: str, loop_type: str, context: str):
        """检查跨方法调用：如果被调用的方法包含禁止方法调用，则报告违规
        支持方法重载：检查该方法的所有重载版本
        """
        if DEBUG_LOG:
            debug_log(f"    [跨方法检测] _check_cross_method_call: {method_name}")
            debug_log(f"    [跨方法检测]   method_signatures: {list(self.method_signatures.keys())}")
            debug_log(f"    [跨方法检测]   methods_with_forbidden_calls: {list(self.methods_with_forbidden_calls.keys())}")
        
        # 获取该方法的所有重载版本签名
        if method_name not in self.method_signatures:
            if DEBUG_LOG:
                debug_log(f"    [跨方法检测]   {method_name} 不在 method_signatures 中")
            return
        
        signatures = self.method_signatures[method_name]
        all_forbidden_calls = []
        
        # 收集所有重载版本中的禁止方法调用
        for sig in signatures:
            if sig in self.methods_with_forbidden_calls:
                all_forbidden_calls.extend(self.methods_with_forbidden_calls[sig])
                if DEBUG_LOG:
                    debug_log(f"    [跨方法检测]   从 {sig} 收集到禁止调用")
        
        if DEBUG_LOG and not all_forbidden_calls:
            debug_log(f"    [跨方法检测]   {method_name} 没有禁止调用")
        
        if not all_forbidden_calls:
            return
        
        # 去重（同一方法内的同一调用）
        seen = set()
        unique_calls = []
        for call in all_forbidden_calls:
            key = (call[1], call[2])  # (class_name, method_call)
            if key not in seen:
                seen.add(key)
                unique_calls.append(call)
        
        for call_line, class_name, method_call in unique_calls:
            # 验证类和方法是否匹配规则
            if class_name not in self.class_method_map:
                continue
            if method_call not in self.class_method_map[class_name]:
                continue
            
            # 找到匹配的规则
            matched_rules = self.class_method_map[class_name][method_call]
            
            for rule in matched_rules:
                # 验证类是否匹配（通过import验证）
                imported_full = self.imported_classes.get(class_name)
                
                # 如果有import，验证全限定名是否匹配
                if imported_full:
                    if imported_full != rule['full_class_name']:
                        # import的类与规则不匹配，跳过
                        continue
                
                # 报告违规（使用原始调用点的行号）
                # call_line 是实际禁止方法调用的行号
                self.violations.append({
                    'rule_code': rule['rule_code'],
                    'rule_name': rule['rule_name'],
                    'rule_level': rule['rule_level'],
                    'file_path': self.file_path,
                    'line_number': call_line or 1,
                    'violation_desc': f'循环内调用方法 {method_name}()，该方法包含禁止方法调用 {rule["full_class_name"]}.{method_call}()（在循环中间接调用）',
                    'solution': rule['solution'],
                    'match_type': f'跨方法循环调用({loop_type})',
                    'context': get_context(self.lines, call_line) if call_line else ''
                })
    
    def _check_chain_selectors(self, selectors, loop_type: str, context: str, prev_return_type: str = None):
        """递归检查链式调用中的selectors
        
        对于 this.getView().updateView()，javalang解析结构为：
        - This.selectors = [MethodInvocation(getView)]
        - MethodInvocation(getView).selectors = [MethodInvocation(updateView)]
        
        所以需要递归处理嵌套的selectors
        """
        current_return_type = prev_return_type
        
        if DEBUG_LOG:
            debug_log(f"    [链式调用] _check_chain_selectors: 数量={len(selectors)}, prev_return_type={prev_return_type}")
        
        for selector in selectors:
            if isinstance(selector, javalang.tree.MethodInvocation):
                member = getattr(selector, 'member', None)
                
                if DEBUG_LOG:
                    debug_log(f"    [链式调用]   selector: member={member}, current_return_type={current_return_type}")
                
                # 如果有前一个方法的返回类型，则当前方法使用该类型作为qualifier
                if current_return_type and member:
                    # 检查当前方法是否违规（使用前一个方法的返回类型作为qualifier）
                    if DEBUG_LOG:
                        debug_log(f"    [链式调用]   调用 _check_method_violation: qualifier={current_return_type}, member={member}")
                    self._check_method_violation(selector, current_return_type, member, loop_type, context)
                
                # 检查跨方法调用
                if member:
                    self._check_cross_method_call(selector, member, loop_type, context)
                
                # 检查嵌套的selectors（如 getView().updateView() 中的 updateView）
                nested_selectors = getattr(selector, 'selectors', None)
                if nested_selectors:
                    # 更新当前返回类型，传递给嵌套的selectors
                    new_return_type = self._get_method_return_type(member) if member else None
                    if DEBUG_LOG:
                        debug_log(f"    [链式调用]   嵌套selectors数量={len(nested_selectors)}, new_return_type={new_return_type}")
                    self._check_chain_selectors(nested_selectors, loop_type, context, new_return_type)
                
                # 更新当前返回类型
                if member:
                    current_return_type = self._get_method_return_type(member)
            else:
                # 非MethodInvocation的selector，递归处理
                self._check_expression(selector, context)
    
    def _check_method_violation(self, expr, qualifier: str, member: str, loop_type: str, context: str, is_method_reference: bool = False, override_line_num: int = None):
        """检查方法调用是否违规
        
        Args:
            expr: AST节点
            qualifier: 类名
            member: 方法名
            loop_type: 循环类型
            context: 上下文
            is_method_reference: 是否是方法引用
            override_line_num: 覆盖的行号（用于方法引用等节点本身没有position的情况）
        """
        # 检查是否匹配规则中的 类简称.方法名
        if qualifier not in self.class_method_map:
            return
    
        if member not in self.class_method_map[qualifier]:
            return
    
        # 找到匹配的规则
        matched_rules = self.class_method_map[qualifier][member]
    
        for rule in matched_rules:
            # 验证类是否匹配（通过import验证）
            imported_full = self.imported_classes.get(qualifier)
                
            # 如果有import，验证全限定名是否匹配
            if imported_full:
                if imported_full != rule['full_class_name']:
                    # import的类与规则不匹配，跳过
                    continue
                
            # 添加违规
            # 使用覆盖行号或从节点获取行号
            line_num = override_line_num if override_line_num else get_node_position(expr)
                
            # 方法引用的描述不同于普通方法调用
            if is_method_reference:
                violation_desc = f'{context}循环内使用方法引用 {rule["full_class_name"]}::{member}()'
                match_type = f'循环内方法引用({loop_type})'
            else:
                violation_desc = f'{context}循环内调用禁止方法 {rule["full_class_name"]}.{member}()'
                match_type = f'循环内方法调用({loop_type})'
                
            self.violations.append({
                'rule_code': rule['rule_code'],
                'rule_name': rule['rule_name'],
                'rule_level': rule['rule_level'],
                'file_path': self.file_path,
                'line_number': line_num or 1,
                'violation_desc': violation_desc,
                'solution': rule['solution'],
                'match_type': match_type,
                'context': get_context(self.lines, line_num) if line_num else ''
            })


# ==================== 扫描函数 ====================

def scan_java_file(file_path: str, rules: List[Dict]) -> List[Dict]:
    """扫描单个Java文件"""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    rel_path = os.path.relpath(file_path, PROJECT_ROOT)
    file_path_normalized = rel_path.replace('\\', '/')
    
    if DEBUG_LOG:
        lines = content.split('\n')
        print(f"  [扫描] {file_path_normalized} ({len(lines)}行)")
    
    detector = LoopMethodViolationDetector(file_path_normalized, content, rules)
    return detector.detect()


def scan_project(project_root: Path = None, rule_file: Path = None) -> List[Dict]:
    """扫描项目中的所有Java文件"""
    scan_start_time = time.time()
    root = project_root or PROJECT_ROOT
    rules_path = rule_file or RULE_FILE
    
    if DEBUG_LOG:
        print("[步骤1] 解析规则文件...")
    rules = parse_loop_method_rule_file(rules_path)
    if DEBUG_LOG:
        print(f"  加载规则数量: {len(rules)}")
    
    if DEBUG_LOG:
        print("[步骤2] 查找Java文件...")
    java_files = find_java_files(root)
    if DEBUG_LOG:
        print(f"  Java文件数量: {len(java_files)}")
    
    if DEBUG_LOG:
        print("[步骤3] 扫描Java文件...")
    all_violations = []
    
    for idx, java_file in enumerate(java_files):
        violations = scan_java_file(java_file, rules)
        all_violations.extend(violations)
        
        if DEBUG_LOG and (idx + 1) % 20 == 0:
            elapsed = time.time() - scan_start_time
            print(f"  [进度] {idx + 1}/{len(java_files)} 文件, 耗时 {elapsed:.1f}秒")
    
    if DEBUG_LOG:
        total_time = time.time() - scan_start_time
        print(f"\n[总耗时] {total_time:.2f}秒")
    
    return all_violations


def scan_specified_files(file_paths: List[str], rules: List[Dict]) -> List[Dict]:
    """扫描指定的文件列表"""
    all_violations = []
    
    for fp in file_paths:
        if os.path.isabs(fp):
            abs_path = fp
        else:
            abs_path = os.path.join(PROJECT_ROOT, fp)
        
        if os.path.exists(abs_path) and abs_path.endswith('.java'):
            violations = scan_java_file(abs_path, rules)
            all_violations.extend(violations)
    
    return all_violations


# ==================== 结果合并 ====================

def dedup_violations(violations: List[Dict]) -> List[Dict]:
    """去重：仅当 file_path + rule_code + line_number 完全相同时去重
    
    支持处理历史合并数据：如果 line_number 是合并格式（如 "L175, L247"），
    则将其拆分为多行记录
    """
    import re
    
    # 第一步：展开历史合并的数据
    expanded = []
    for v in violations:
        line_number = v.get('line_number', 0)
        
        # 检测是否是合并格式：如 "L175, L247" 或 "L175,L247" 或 "175, 247"
        if isinstance(line_number, str) and (',' in line_number or '，' in line_number):
            # 提取所有行号
            lines = re.findall(r'L?(\d+)', line_number)
            for line in lines:
                # 为每个行号创建独立记录
                new_v = v.copy()
                new_v['line_number'] = int(line)
                expanded.append(new_v)
        else:
            # 确保 line_number 是整数
            try:
                v_copy = v.copy()
                v_copy['line_number'] = int(line_number) if not isinstance(line_number, int) else line_number
                expanded.append(v_copy)
            except (ValueError, TypeError):
                # 如果转换失败，保留原值
                expanded.append(v.copy())
    
    # 第二步：去重
    seen = set()
    result = []
    
    for v in expanded:
        # 使用 file_path + rule_code + line_number 作为去重键
        key = (v.get('file_path', ''), v.get('rule_code', ''), v.get('line_number', 0))
        if key not in seen:
            seen.add(key)
            result.append(v)
    
    # 按 file_path, rule_code, line_number 排序
    result.sort(key=lambda x: (x.get('file_path', ''), x.get('rule_code', ''), x.get('line_number', 0)))
    return result


# ==================== 主函数 ====================

def main():
    """主函数"""
    specified_files = []
    if '--file' in sys.argv:
        file_idx = sys.argv.index('--file')
        for i in range(file_idx + 1, len(sys.argv)):
            if sys.argv[i].startswith('--'):
                break
            specified_files.append(sys.argv[i])
    
    print("=" * 60)
    print("Java代码循环内禁止方法检测工具")
    print("=" * 60)
    
    rules = parse_loop_method_rule_file(RULE_FILE)
    
    if specified_files:
        violations = scan_specified_files(specified_files, rules)
    else:
        violations = scan_project()
    
    # 去重：仅当 file_path + rule_code + line_number 完全相同时去重
    violations = dedup_violations(violations)
    
    violation_files = set(v['file_path'] for v in violations)
    level_counts = {'严重': 0, '高危': 0, '中危': 0, '低危': 0}
    for v in violations:
        level = v['rule_level']
        if level in level_counts:
            level_counts[level] += 1
    
    print(f"\n扫描完成!")
    print(f"  违规文件数: {len(violation_files)}")
    print(f"  总违规数: {len(violations)}")
    print(f"  严重: {level_counts['严重']}, 高危: {level_counts['高危']}, 中危: {level_counts['中危']}, 低危: {level_counts['低危']}")
    
    # 输出 violations 结果到 JSON 文件
    output_result_file = SCRIPT_DIR.parent / "result" / "scan_java_loop_method_result.json"
    try:
        # 确保目录存在
        output_result_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_result_file, 'w', encoding='utf-8') as f:
            json.dump(violations, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到: {output_result_file}")
    except Exception as e:
        print(f"\n[警告] 保存结果文件失败: {e}")
    
    return violations


if __name__ == '__main__':
    main()
