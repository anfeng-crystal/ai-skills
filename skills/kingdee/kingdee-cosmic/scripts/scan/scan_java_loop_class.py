# -*- coding: utf-8 -*-
"""
Java代码循环内禁止类检测工具
使用 javalang 语法解析器检测循环体内禁止类的使用
功能：
1. 检测 for/while/do 循环内的禁止类调用
2. 检测 lambda 表达式中的禁止类调用
3. 日志类特殊处理（检测循环内的日志方法调用）
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

def debug_print(msg):
    """输出调试日志到文件"""
    global DEBUG_LOG_FILE
    if DEBUG_LOG:
        if DEBUG_LOG_FILE is None:
            import os
            script_dir = Path(__file__).parent
            DEBUG_LOG_FILE = open(script_dir.parent / 'scan_debug.log', 'w', encoding='utf-8')
        DEBUG_LOG_FILE.write(msg + '\n')
        DEBUG_LOG_FILE.flush()

# 技能根目录（当前脚本所在目录）
SCRIPT_DIR = Path(__file__).parent

# 项目根目录（工作空间根目录）
# 脚本位于: <skill-root>/scripts/scan/
# 默认项目根目录按当前工作目录或显式参数传入
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent

# 规则文件路径（相对于脚本目录）
RULE_FILE = SCRIPT_DIR.parent / "references" / "sonar_cve_loop_class.md"


# ==================== 规则解析 ====================

def parse_loop_class_rule_file(rule_file: Path) -> List[Dict]:
    """解析循环内禁止类规则文件"""
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
                
                class_match = re.search(r'loop\s+class\s*=\s*([^\s|]+)', rule_config)
                if class_match:
                    full_class_name = class_match.group(1)
                    class_short_name = full_class_name.split('.')[-1]
                    package_name = '.'.join(full_class_name.split('.')[:-1])
                    
                    rules.append({
                        'rule_code': rule_code,
                        'rule_name': rule_name,
                        'rule_level': rule_level,
                        'full_class_name': full_class_name,
                        'class_short_name': class_short_name,
                        'package_name': package_name,
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

def get_node_position(node, lines: List[str] = None) -> Optional[int]:
    """从AST节点提取行号
    
    Args:
        node: AST节点
        lines: 源代码行列表（用于正则fallback）
    """
    # 1. 尝试从节点自身的 position 获取
    if hasattr(node, 'position') and node.position:
        return node.position[0]
    
    # 2. 对于 ClassCreator，尝试从 type 属性获取
    if hasattr(node, 'type') and node.type:
        if hasattr(node.type, 'position') and node.type.position:
            return node.type.position[0]
        # 尝试从 type.name 推断
        if hasattr(node.type, 'name') and lines:
            type_name = node.type.name
            pattern = rf'\bnew\s+{re.escape(type_name)}\s*\('
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    return i
    
    # 3. 对于 MethodInvocation，从 qualifier 和 member 推断
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

class LoopClassViolationDetector:
    """
    循环内禁止类违规检测器
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
        
        # 构建规则查找表
        self.full_class_map = {}
        self.short_class_map = {}
        
        for rule in rules:
            self.full_class_map[rule['full_class_name']] = rule
            if rule['class_short_name'] not in self.short_class_map:
                self.short_class_map[rule['class_short_name']] = []
            self.short_class_map[rule['class_short_name']].append(rule)
        
        # 日志类规则
        self.log_rules = [
            r for r in rules 
            if 'Log' in r['class_short_name'] or 'log' in r['class_short_name'].lower()
        ]
        
        # 日志变量名
        self.log_var_names = {'logger', 'log', 'LOGGER', 'LOG'}
        self.log_methods = {'info', 'debug', 'error', 'warn', 'trace', 'fatal'}
        
        # 跨方法检测：记录包含禁止类调用的方法
        self.methods_with_forbidden_calls = {}  # 方法签名 -> [(行号, 类名, 方法名), ...]
        self.method_signatures = {}  # 方法名 -> [方法签名列表，支持重载]
        
        # 变量类型追踪：变量名 -> 类型名
        self.local_variables = {}  # 方法内的局部变量类型映射
        self.field_types = {}  # 类字段类型映射
        
        # import 映射：短类名 -> 完整类名
        self.imported_classes = {}
    
    def _get_type_name(self, type_node) -> Optional[str]:
        """从类型节点获取类型名称"""
        if type_node is None:
            return None
        if isinstance(type_node, str):
            return type_node
        if hasattr(type_node, 'name'):
            return type_node.name
        return None
    
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
        
        # try-with-resources
        elif isinstance(stmt, javalang.tree.TryStatement):
            resources = getattr(stmt, 'resources', None)
            if resources:
                for resource in resources:
                    resource_type = getattr(resource, 'type', None)
                    resource_name = getattr(resource, 'name', None)
                    if resource_type and resource_name:
                        type_name = self._get_type_name(resource_type)
                        if type_name:
                            self.local_variables[resource_name] = type_name
            
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
        
        # if语句
        elif isinstance(stmt, javalang.tree.IfStatement):
            then_stmt = getattr(stmt, 'then_statement', None)
            else_stmt = getattr(stmt, 'else_statement', None)
            if then_stmt:
                self._collect_variable_type_from_statement(then_stmt)
            if else_stmt:
                self._collect_variable_type_from_statement(else_stmt)
        
        # 循环语句
        elif isinstance(stmt, (javalang.tree.ForStatement, javalang.tree.WhileStatement, javalang.tree.DoStatement)):
            body = getattr(stmt, 'body', None)
            if body:
                if hasattr(body, 'statements'):
                    for s in body.statements:
                        self._collect_variable_type_from_statement(s)
                elif isinstance(body, (list, tuple)):
                    for s in body:
                        self._collect_variable_type_from_statement(s)
                else:
                    self._collect_variable_type_from_statement(body)
        
        # for循环初始化部分
        elif isinstance(stmt, javalang.tree.ForStatement):
            ctrl = getattr(stmt, 'control', None)
            if ctrl:
                init = getattr(ctrl, 'init', None)
                if init and isinstance(init, list):
                    for i in init:
                        if isinstance(i, javalang.tree.LocalVariableDeclaration):
                            type_node = getattr(i, 'type', None)
                            declarators = getattr(i, 'declarators', None)
                            if type_node and declarators:
                                type_name = self._get_type_name(type_node)
                                for decl in declarators:
                                    var_name = getattr(decl, 'name', None)
                                    if var_name and type_name:
                                        self.local_variables[var_name] = type_name
        
        # 代码块
        elif isinstance(stmt, (list, tuple)):
            for s in stmt:
                self._collect_variable_type_from_statement(s)
        
        # BlockStatement
        elif hasattr(stmt, 'statements'):
            statements = getattr(stmt, 'statements', None)
            if statements:
                for s in statements:
                    self._collect_variable_type_from_statement(s)
    
    def _collect_method_local_variables(self, method):
        """收集方法的局部变量类型"""
        self.local_variables = {}
        body = getattr(method, 'body', None)
        if not body:
            return
        for stmt in body:
            self._collect_variable_type_from_statement(stmt)
    
    def is_in_loop(self) -> Tuple[bool, str]:
        """判断当前是否在循环内"""
        if self.loop_depth > 0:
            return True, self.current_loop_type
        if self.lambda_depth > 0:
            return True, "lambda表达式"
        return False, ""
    
    def detect(self) -> List[Dict]:
        """执行检测（支持跨方法调用链检测）"""
        # 使用统一解析器（javalang + 预处理 + JavaParser fallback）
        from java_parser_unified import parse_java_code, JavaCodePreprocessor
        
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
            javaparser_violations = detect_loop_violations_from_javaparser(
                jp_result=tree._javaparser_result,
                rules_map=self.short_class_map,
                file_path=self.file_path,
                lines=self.lines,
                get_context_func=get_context,
                match_type_prefix="循环内调用"
            )
            
            # 尝试使用javalang进行跨方法调用链检测
            # 注意：统一解析器已经进行了预处理，如果失败才会走到这里
            # 所以这里不需要再次预处理，直接使用原始代码尝试解析即可
            try:
                import javalang
                
                # 直接使用原始代码尝试解析（统一解析器已经尝试过预处理）
                javalang_tree = javalang.parse.parse(self.content)
                if javalang_tree:
                    # 使用javalang树进行跨方法调用链检测
                    tree = javalang_tree
                    if DEBUG_LOG:
                        print(f"    [检测器] 使用javalang重新解析原始代码")
                else:
                    return javaparser_violations
            except Exception as e:
                # javalang解析失败，尝试使用预处理后代码重新解析
                if DEBUG_LOG:
                    print(f"    [警告] javalang 解析原始代码失败: {e}")
                    print(f"    [检测器] 尝试使用预处理后代码重新解析...")
                
                # 尝试使用预处理后代码重新解析
                try:
                    from java_parser_unified import JavaCodePreprocessor
                    preprocessor = JavaCodePreprocessor()
                    processed_code = preprocessor.preprocess(self.content)
                    
                    if processed_code != self.content:
                        javalang_tree = javalang.parse.parse(processed_code)
                        if javalang_tree:
                            tree = javalang_tree
                            tree._preprocessor = preprocessor
                            tree._preprocessed_content = processed_code
                            if DEBUG_LOG:
                                print(f"    [检测器] 使用预处理后代码重新解析成功")
                        else:
                            return javaparser_violations
                    else:
                        return javaparser_violations
                except Exception as e2:
                    if DEBUG_LOG:
                        print(f"    [警告] 预处理后代码重新解析失败: {e2}")
                    return javaparser_violations
        
        # 检查是否使用了预处理
        if hasattr(tree, '_preprocessor'):
            self.preprocessor = tree._preprocessor
            # 如果使用预处理后的代码，需要更新 self.lines 以匹配预处理后的代码
            if hasattr(tree, '_preprocessed_content'):
                self.lines = tree._preprocessed_content.split('\n')
                if DEBUG_LOG:
                    print(f"    [检测器] 使用预处理后的代码，行数: {len(self.lines)}")
        
        # 收集import信息
        self.imported_classes = {}
        if tree.imports:
            for imp in tree.imports:
                if imp.path and not imp.wildcard:
                    class_name = imp.path.split('.')[-1]
                    self.imported_classes[class_name] = imp.path
        
        # 第一阶段：收集所有方法及其包含的禁止类调用
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
        
        # 后处理：跨方法违规去重（同一文件、同一规则、同一行号只保留一条）
        seen_keys = set()
        deduped = []
        for v in self.violations:
            key = (v.get('rule_code', ''), v.get('file_path', ''), v.get('line_number', 0))
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(v)
        self.violations = deduped
        
        return self.violations
    
    def _scan_members(self, members: List, is_inner_class: bool = False):
        """第二阶段：扫描类成员（常规检测）
        
        Args:
            members: 类成员列表
            is_inner_class: 是否是内部类（用于决定是否清空field_types）
        """
        # 只有扫描外部类时才重新收集字段类型
        # 内部类会继承外部类的field_types，并在此基础上添加自己的字段
        if not is_inner_class:
            self.field_types = {}
            # 只收集当前类的字段，不递归收集内部类的字段
            self._collect_current_class_field_types(members)
        else:
            # 内部类：在现有field_types基础上添加内部类的字段
            self._collect_current_class_field_types(members)
        
        # 然后扫描方法
        for member in members:
            if isinstance(member, javalang.tree.MethodDeclaration):
                self._scan_method(member)
            elif isinstance(member, javalang.tree.FieldDeclaration):
                # 字段声明中可能包含初始化表达式
                for decl in getattr(member, 'declarators', []):
                    init = getattr(decl, 'initializer', None)
                    if init:
                        self._check_expression(init, "字段初始化: ")
            elif isinstance(member, javalang.tree.ClassDeclaration):
                # 处理内部类
                if hasattr(member, 'body') and member.body:
                    # 保存当前字段类型（包含外部类字段）
                    saved_field_types = self.field_types.copy()
                    # 扫描内部类（传入is_inner_class=True）
                    self._scan_members(member.body, is_inner_class=True)
                    # 恢复字段类型
                    self.field_types = saved_field_types
    
    def _collect_current_class_field_types(self, members: List):
        """只收集当前类的字段类型（不递归处理内部类）"""
        for member in members:
            if isinstance(member, javalang.tree.FieldDeclaration):
                type_node = getattr(member, 'type', None)
                declarators = getattr(member, 'declarators', None)
                if type_node and declarators:
                    type_name = self._get_type_name(type_node)
                    for decl in declarators:
                        var_name = getattr(decl, 'name', None)
                        if var_name and type_name:
                            self.field_types[var_name] = type_name
                            if DEBUG_LOG:
                                debug_print(f"    [字段类型] {var_name} -> {type_name}")
    
    def _collect_field_types(self, members: List):
        """递归收集所有字段类型（包括内部类）- 保留用于向后兼容"""
        self._collect_current_class_field_types(members)
        # 递归处理内部类
        for member in members:
            if isinstance(member, javalang.tree.ClassDeclaration):
                if hasattr(member, 'body') and member.body:
                    self._collect_field_types(member.body)
    
    def _scan_method(self, method):
        """扫描方法体内的代码"""
        # 收集方法的局部变量类型
        self._collect_method_local_variables(method)
        
        body = getattr(method, 'body', None)
        if not body:
            return
        
        for stmt in body:
            self._scan_statement(stmt)
    
    def _get_method_signature(self, method) -> str:
        """获取方法签名（方法名_参数数量），用于区分重载方法"""
        method_name = getattr(method, 'name', None)
        if not method_name:
            return None
        
        # 获取参数数量
        params = getattr(method, 'parameters', None)
        param_count = len(params) if params else 0
        
        return f"{method_name}_{param_count}"
    
    def _collect_methods_with_forbidden_calls(self, members: List):
        """第一阶段：收集包含禁止类调用的方法（支持递归调用链）"""
        # 首先收集所有方法节点（使用签名作为key以支持重载）
        if DEBUG_LOG:
            debug_print(f"    [跨方法检测] 开始收集方法，members数量: {len(members) if members else 0}")
        
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
                        debug_print(f"    [跨方法检测] 收集方法: {signature}")
            elif isinstance(member, javalang.tree.ClassDeclaration):
                # 递归处理内部类
                inner_class_name = getattr(member, 'name', None)
                if DEBUG_LOG:
                    debug_print(f"    [跨方法检测] 发现内部类: {inner_class_name}")
                if hasattr(member, 'body') and member.body:
                    self._collect_methods_with_forbidden_calls(member.body)
        
        if DEBUG_LOG:
            debug_print(f"    [跨方法检测] 共收集 {len(self.method_nodes)} 个方法")
            debug_print(f"    [跨方法检测] 方法签名映射: {self.method_signatures}")
        
        # 然后递归收集每个方法的禁止类调用（包括跨方法调用）
        for signature in self.method_nodes:
            forbidden_calls = self._find_forbidden_calls_in_method_recursive(signature, set())
            if forbidden_calls:
                self.methods_with_forbidden_calls[signature] = forbidden_calls
                if DEBUG_LOG:
                    debug_print(f"    [跨方法检测] 方法 {signature} 包含 {len(forbidden_calls)} 个禁止调用: {forbidden_calls}")
    
    def _find_forbidden_calls_in_method(self, method) -> List[Tuple]:
        """查找方法体内所有的禁止类调用"""
        forbidden_calls = []
        body = getattr(method, 'body', None)
        if not body:
            return forbidden_calls
        
        for stmt in body:
            self._find_forbidden_calls_in_statement(stmt, forbidden_calls)
        
        return forbidden_calls
    
    def _find_forbidden_calls_in_method_recursive(self, method_signature: str, visited: set) -> List[Tuple]:
        """递归查找方法及其调用的方法中所有的禁止类调用"""
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
        """递归查找语句中的禁止类调用和方法调用"""
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
            if declarators:
                for decl in declarators:
                    init = getattr(decl, 'initializer', None)
                    if init:
                        self._find_forbidden_calls_and_calls_in_expression(init, forbidden_calls, visited)
        
        # return语句
        elif isinstance(stmt, javalang.tree.ReturnStatement):
            ret_expr = getattr(stmt, 'expression', None)
            if ret_expr:
                self._find_forbidden_calls_and_calls_in_expression(ret_expr, forbidden_calls, visited)
        
        # if语句
        elif isinstance(stmt, javalang.tree.IfStatement):
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
                    resource_value = getattr(resource, 'value', None)
                    if resource_value:
                        self._find_forbidden_calls_and_calls_in_expression(resource_value, forbidden_calls, visited)
            
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
            if statements:
                for s in statements:
                    self._find_forbidden_calls_and_calls_in_statement(s, forbidden_calls, visited)
    
    def _find_forbidden_calls_and_calls_in_expression(self, expr, forbidden_calls: List, visited: set):
        """递归查找表达式中的禁止类调用和方法调用"""
        if expr is None:
            return
        
        # 方法调用
        if isinstance(expr, javalang.tree.MethodInvocation):
            qualifier = getattr(expr, 'qualifier', None)
            member = getattr(expr, 'member', None)
            
            # 检查是否是禁止类的方法调用（直接类名匹配）
            if qualifier and member and qualifier in self.short_class_map:
                line_num = get_node_position(expr, self.lines)
                forbidden_calls.append((line_num, qualifier, member))
            
            # 检查是否是变量类型匹配（实例方法调用）
            # 例如：ORM orm = ...; orm.query() -> qualifier="orm", 变量类型="ORM"
            if qualifier and member and qualifier in self.local_variables:
                var_type = self.local_variables[qualifier]
                if var_type in self.short_class_map:
                    line_num = get_node_position(expr, self.lines)
                    forbidden_calls.append((line_num, var_type, member))
            
            # 【新增】检查是否是日志变量调用（logger.info, log.debug等）
            # 日志变量调用需要特殊处理，因为logger是变量名而非类名
            if qualifier and member and member in self.log_methods:
                if qualifier in self.log_var_names:
                    line_num = get_node_position(expr, self.lines)
                    forbidden_calls.append((line_num, qualifier, member, 'log'))
            
            # 检查是否是本类方法调用（跨方法调用链）
            # 支持方法重载：遍历所有匹配的方法签名
            # qualifier 为 None 或 "this" 时，视为本类方法调用
            if member and (not qualifier or qualifier == "this") and member in self.method_signatures:
                # 获取该方法的所有重载版本
                signatures = self.method_signatures[member]
                for sig in signatures:
                    # 递归查找被调用方法中的禁止类调用
                    nested_calls = self._find_forbidden_calls_in_method_recursive(sig, visited.copy())
                    forbidden_calls.extend(nested_calls)
            
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
    
    def _find_forbidden_calls_in_statement(self, stmt, forbidden_calls: List):
        """递归查找语句中的禁止类调用"""
        if stmt is None:
            return
        
        # 表达式语句
        if isinstance(stmt, javalang.tree.StatementExpression):
            expr = getattr(stmt, 'expression', None)
            if expr:
                self._find_forbidden_calls_in_expression(expr, forbidden_calls)
        
        # 局部变量声明
        elif isinstance(stmt, javalang.tree.LocalVariableDeclaration):
            declarators = getattr(stmt, 'declarators', None)
            if declarators:
                for decl in declarators:
                    init = getattr(decl, 'initializer', None)
                    if init:
                        self._find_forbidden_calls_in_expression(init, forbidden_calls)
        
        # return语句
        elif isinstance(stmt, javalang.tree.ReturnStatement):
            ret_expr = getattr(stmt, 'expression', None)
            if ret_expr:
                self._find_forbidden_calls_in_expression(ret_expr, forbidden_calls)
        
        # if语句
        elif isinstance(stmt, javalang.tree.IfStatement):
            condition = getattr(stmt, 'condition', None)
            if condition:
                self._find_forbidden_calls_in_expression(condition, forbidden_calls)
            then_stmt = getattr(stmt, 'then_statement', None)
            else_stmt = getattr(stmt, 'else_statement', None)
            if then_stmt:
                self._find_forbidden_calls_in_statement(then_stmt, forbidden_calls)
            if else_stmt:
                self._find_forbidden_calls_in_statement(else_stmt, forbidden_calls)
        
        # 循环语句 - 递归扫描但不增加循环深度
        elif isinstance(stmt, (javalang.tree.ForStatement, javalang.tree.WhileStatement, javalang.tree.DoStatement)):
            body = getattr(stmt, 'body', None)
            if body:
                if hasattr(body, 'statements'):
                    for s in body.statements:
                        self._find_forbidden_calls_in_statement(s, forbidden_calls)
                elif isinstance(body, (list, tuple)):
                    for s in body:
                        self._find_forbidden_calls_in_statement(s, forbidden_calls)
                else:
                    self._find_forbidden_calls_in_statement(body, forbidden_calls)
        
        # try-catch
        elif isinstance(stmt, javalang.tree.TryStatement):
            # 处理 try-with-resources 的资源声明部分
            resources = getattr(stmt, 'resources', None)
            if resources:
                for resource in resources:
                    resource_value = getattr(resource, 'value', None)
                    if resource_value:
                        self._find_forbidden_calls_in_expression(resource_value, forbidden_calls)
            
            try_block = getattr(stmt, 'block', None)
            if try_block:
                for s in try_block:
                    self._find_forbidden_calls_in_statement(s, forbidden_calls)
            catches = getattr(stmt, 'catches', None)
            if catches:
                for catch in catches:
                    catch_block = getattr(catch, 'block', None)
                    if catch_block:
                        for s in catch_block:
                            self._find_forbidden_calls_in_statement(s, forbidden_calls)
            
            # 处理 finally 块
            finally_block = getattr(stmt, 'finally_block', None)
            if finally_block:
                for s in finally_block:
                    self._find_forbidden_calls_in_statement(s, forbidden_calls)
        
        # 代码块
        elif isinstance(stmt, (list, tuple)):
            for s in stmt:
                self._find_forbidden_calls_in_statement(s, forbidden_calls)
        
        # BlockStatement
        elif hasattr(stmt, 'statements'):
            statements = getattr(stmt, 'statements', None)
            if statements:
                for s in statements:
                    self._find_forbidden_calls_in_statement(s, forbidden_calls)
    
    def _find_forbidden_calls_in_expression(self, expr, forbidden_calls: List):
        """递归查找表达式中的禁止类调用"""
        if expr is None:
            return
        
        # 方法调用
        if isinstance(expr, javalang.tree.MethodInvocation):
            qualifier = getattr(expr, 'qualifier', None)
            member = getattr(expr, 'member', None)
            
            # 检查是否是禁止类的方法调用
            if qualifier and member and qualifier in self.short_class_map:
                line_num = get_node_position(expr, self.lines)
                forbidden_calls.append((line_num, qualifier, member))
            
            # 【新增】检查是否是日志变量调用（logger.info, log.debug等）
            if qualifier and member and member in self.log_methods:
                if qualifier in self.log_var_names:
                    line_num = get_node_position(expr, self.lines)
                    forbidden_calls.append((line_num, qualifier, member, 'log'))
            
            # 递归检查参数
            args = getattr(expr, 'arguments', None)
            if args:
                for arg in args:
                    self._find_forbidden_calls_in_expression(arg, forbidden_calls)
            
            # 递归检查 selectors
            expr_selectors = getattr(expr, 'selectors', None)
            if expr_selectors:
                for selector in expr_selectors:
                    self._find_forbidden_calls_in_expression(selector, forbidden_calls)
        
        # 类创建
        elif isinstance(expr, javalang.tree.ClassCreator):
            args = getattr(expr, 'arguments', None)
            if args:
                for arg in args:
                    self._find_forbidden_calls_in_expression(arg, forbidden_calls)
        
        # 赋值表达式
        elif isinstance(expr, javalang.tree.Assignment):
            expr_val = getattr(expr, 'value', None)
            if expr_val:
                self._find_forbidden_calls_in_expression(expr_val, forbidden_calls)
        
        # 二元运算
        elif isinstance(expr, javalang.tree.BinaryOperation):
            left = getattr(expr, 'operandl', None)
            right = getattr(expr, 'operandr', None)
            if left:
                self._find_forbidden_calls_in_expression(left, forbidden_calls)
            if right:
                self._find_forbidden_calls_in_expression(right, forbidden_calls)
        
        # 三元表达式
        elif isinstance(expr, javalang.tree.TernaryExpression):
            condition = getattr(expr, 'condition', None)
            if_true = getattr(expr, 'if_true', None) or getattr(expr, 'true_expression', None)
            if_false = getattr(expr, 'if_false', None) or getattr(expr, 'false_expression', None)
            if condition:
                self._find_forbidden_calls_in_expression(condition, forbidden_calls)
            if if_true:
                self._find_forbidden_calls_in_expression(if_true, forbidden_calls)
            if if_false:
                self._find_forbidden_calls_in_expression(if_false, forbidden_calls)
        
        # 类型转换表达式: (Type) expression
        elif isinstance(expr, javalang.tree.Cast):
            cast_expr = getattr(expr, 'expression', None)
            if cast_expr:
                self._find_forbidden_calls_in_expression(cast_expr, forbidden_calls)
    
    def _scan_members_old(self, members: List):
        """扫描类成员 - 旧版本（已废弃）"""
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
        # 收集方法的局部变量类型
        self._collect_method_local_variables(method)
        
        body = getattr(method, 'body', None)
        if body:
            for stmt in body:
                self._scan_statement(stmt)
    
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
    
    def _scan_statement_or_body(self, stmt_or_body):
        """
        扫描单条语句或语句块（用于if语句的then/else分支）
        与_scan_loop_body的区别：此函数不会增加loop_depth
        """
        if stmt_or_body is None:
            return
            
        # 如果是BlockStatement，获取其statements属性
        if hasattr(stmt_or_body, 'statements'):
            statements = getattr(stmt_or_body, 'statements', None)
            if statements:
                for s in statements:
                    self._scan_statement(s)
        elif isinstance(stmt_or_body, (list, tuple)):
            for s in stmt_or_body:
                self._scan_statement(s)
        else:
            # 单条语句
            self._scan_statement(stmt_or_body)
    
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
                self._scan_statement_or_body(then_stmt)
            if else_stmt:
                self._scan_statement_or_body(else_stmt)
        
        # for循环 - 进入循环上下文
        elif isinstance(stmt, javalang.tree.ForStatement):
            ctrl = getattr(stmt, 'control', None)
            body = getattr(stmt, 'body', None)
            
            # 检查循环控制部分（不在循环体内）
            if ctrl:
                # 标准for循环: for (init; condition; update)
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
                
                # 增强for循环: for (Type var : iterable)
                # 检查iterable部分（不在循环体内）
                iterable = getattr(ctrl, 'iterable', None)
                if iterable:
                    self._check_expression(iterable, "")
            
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
    
    def _check_expression(self, expr, context: str):
        """检查表达式中的违规"""
        if expr is None:
            return
        
        in_loop, loop_type = self.is_in_loop()
        
        # 方法调用
        if isinstance(expr, javalang.tree.MethodInvocation):
            qualifier = getattr(expr, 'qualifier', None)
            member = getattr(expr, 'member', None)
            
            # 检查日志方法调用
            if qualifier and member and member in self.log_methods:
                # 直接匹配: log.info(), logger.debug() 等
                if qualifier in self.log_var_names and in_loop:
                    self._add_log_violation(expr, member, loop_type, context)
                # 匹配 this.log, this.logger 等
                elif qualifier.startswith('this.') and in_loop:
                    log_var = qualifier.split('.')[-1]  # 提取 'log' 或 'logger'
                    if log_var in self.log_var_names:
                        self._add_log_violation(expr, member, loop_type, context)
                # 匹配字段类型为 Logger 的变量（如 private Logger log;）
                elif qualifier in self.field_types and in_loop:
                    field_type = self.field_types[qualifier]
                    if field_type in self.short_class_map:
                        # 检查字段类型是否是日志类（Logger 或 Log）
                        for rule in self.short_class_map.get(field_type, []):
                            if 'Log' in rule['class_short_name'] or 'log' in rule['class_short_name'].lower():
                                self._add_log_violation(expr, member, loop_type, context)
                                break
            
            # 检查禁止类的方法调用（直接调用）
            if qualifier and member and qualifier in self.short_class_map and in_loop:
                self._add_class_violation(expr, qualifier, member, loop_type, context)
            
            # 检查变量类型匹配（实例方法调用）
            # 例如：ORM orm = ...; orm.query() -> qualifier="orm", 变量类型="ORM"
            if qualifier and member and qualifier in self.local_variables and in_loop:
                var_type = self.local_variables[qualifier]
                if var_type in self.short_class_map:
                    self._add_class_violation(expr, var_type, member, loop_type, context)
            
            # 检查字段类型匹配（类成员变量）
            # 例如：private Logger log; log.info() -> qualifier="log", 字段类型="Logger"
            if qualifier and member and qualifier in self.field_types and in_loop:
                field_type = self.field_types[qualifier]
                if field_type in self.short_class_map:
                    self._add_class_violation(expr, field_type, member, loop_type, context)
            
            # 跨方法检测：检查调用的方法是否包含禁止类调用
            if member and in_loop:
                self._check_cross_method_call(expr, member, loop_type, context)
            
            # 递归检查参数
            args = getattr(expr, 'arguments', None)
            if args:
                for arg in args:
                    self._check_expression(arg, context)
            
            # 递归检查 selectors（链式调用）
            expr_selectors = getattr(expr, 'selectors', None)
            if expr_selectors:
                for selector in expr_selectors:
                    self._check_expression(selector, context)
        
        # 类创建: new ClassName()
        elif isinstance(expr, javalang.tree.ClassCreator):
            creator_type = getattr(expr, 'type', None)
            if creator_type:
                type_name = getattr(creator_type, 'name', None)
                if type_name and type_name in self.short_class_map and in_loop:
                    self._add_instantiation_violation(expr, type_name, loop_type, context)
            
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
        
        # 成员引用 (如 OperationServiceHelper.executeOperate)
        elif isinstance(expr, javalang.tree.MemberReference):
            qualifier = getattr(expr, 'qualifier', None)
            member = getattr(expr, 'member', None)
            
            # 检查禁止类的方法调用
            if qualifier and member and qualifier in self.short_class_map and in_loop:
                self._add_class_violation(expr, qualifier, member, loop_type, context)
        
        # This 表达式 (如 this.detailOperation(), this.log.info())
        # javalang 将 this.method() 解析为 This 节点，方法调用在 selectors 中
        # 使用递归收集所有方法调用（参考 scan_java_loop_method.py 的实现）
        elif isinstance(expr, javalang.tree.This):
            # 收集 This 表达式中的所有方法调用
            methods_in_this = self._collect_method_invocations(expr)
            # 检查每个方法调用
            for method_call in methods_in_this:
                # 检查是否是日志方法调用
                self._check_this_log_call(expr, method_call, in_loop, loop_type, context)
                # 检查跨方法调用链
                member = getattr(method_call, 'member', None)
                if member and in_loop and member in self.method_signatures:
                    self._check_cross_method_call(method_call, member, loop_type, context)
        
        # 构造器引用 (MethodReference with method = 'new')
        # 例如: Supplier<List> supplier = ArrayList::new;
        elif isinstance(expr, javalang.tree.MethodReference):
            # 获取方法引用的类名和方法名
            ref_expr = getattr(expr, 'expression', None)
            method_ref = getattr(expr, 'method', None)
            
            # expression 通常是 MemberReference，其 member 属性是类名
            class_name = None
            if ref_expr and hasattr(ref_expr, 'member'):
                class_name = ref_expr.member
            
            # method 通常是 MemberReference，其 member 属性是方法名
            method_name = None
            if method_ref and hasattr(method_ref, 'member'):
                method_name = method_ref.member
            
            # 只检测构造器引用（method = 'new'）
            if class_name and method_name == 'new' and in_loop:
                if class_name in self.short_class_map:
                    self._add_instantiation_violation(expr, class_name, loop_type, context, '构造器引用')
    
    def _collect_method_invocations(self, node) -> list:
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
    
    def _check_this_log_call(self, this_expr, method_call, in_loop: bool, loop_type: str, context: str):
        """检查 this.log.info() 等日志调用"""
        if not in_loop:
            return
        
        method_name = getattr(method_call, 'member', None)
        if not method_name or method_name not in self.log_methods:
            return
        
        # 检查是否是 this.log / this.logger 等
        # 方法调用可能来自 selectors 中的 MemberReference
        # 遍历 This 的 selectors 找到日志变量
        this_selectors = getattr(this_expr, 'selectors', None)
        if this_selectors:
            for selector in this_selectors:
                if isinstance(selector, javalang.tree.MemberReference):
                    member = getattr(selector, 'member', None)
                    if member in self.log_var_names:
                        self._add_log_violation(method_call, method_name, loop_type, context)
                        return
                elif isinstance(selector, javalang.tree.MethodInvocation):
                    # 检查 qualifier 是否是 this.log
                    qualifier = getattr(selector, 'qualifier', None)
                    if qualifier and qualifier.startswith('this.'):
                        log_var = qualifier.split('.')[-1]
                        if log_var in self.log_var_names:
                            self._add_log_violation(method_call, method_name, loop_type, context)
                            return
    
    def _check_cross_method_call(self, expr, method_name: str, loop_type: str, context: str):
        """检查跨方法调用：如果被调用的方法包含禁止类调用，则报告违规
        支持方法重载：检查该方法的所有重载版本
        """
        if DEBUG_LOG:
            debug_print(f"    [跨方法检测] 检查方法调用: {method_name}")
            debug_print(f"    [跨方法检测] 可用方法签名: {list(self.method_signatures.keys())}")
            debug_print(f"    [跨方法检测] 方法包含禁止调用: {list(self.methods_with_forbidden_calls.keys())}")
        
        # 获取该方法的所有重载版本签名
        if method_name not in self.method_signatures:
            if DEBUG_LOG:
                debug_print(f"    [跨方法检测] 方法 {method_name} 不在签名映射中")
            return
        
        signatures = self.method_signatures[method_name]
        if DEBUG_LOG:
            debug_print(f"    [跨方法检测] 方法 {method_name} 的签名: {signatures}")
        
        all_forbidden_calls = []
        
        # 收集所有重载版本中的禁止类调用
        for sig in signatures:
            if sig in self.methods_with_forbidden_calls:
                calls = self.methods_with_forbidden_calls[sig]
                all_forbidden_calls.extend(calls)
                if DEBUG_LOG:
                    debug_print(f"    [跨方法检测] 签名 {sig} 包含 {len(calls)} 个禁止调用")
        
        if not all_forbidden_calls:
            if DEBUG_LOG:
                debug_print(f"    [跨方法检测] 方法 {method_name} 没有禁止调用")
            return
        
        # 去重（同一方法内的同一调用）
        seen = set()
        unique_calls = []
        for call in all_forbidden_calls:
            # 区分日志调用（4元素）和类调用（3元素）
            if len(call) == 4 and call[3] == 'log':
                key = ('log', call[1], call[2])  # ('log', 'logger', 'info')
            else:
                key = (call[1], call[2])  # (class_name, method_call)
            if key not in seen:
                seen.add(key)
                unique_calls.append(call)
        
        for call in unique_calls:
            # 区分日志调用和类调用
            if len(call) == 4 and call[3] == 'log':
                # 日志调用: (line_num, var_name, method_name, 'log')
                call_line_log, log_var, log_method, _ = call
                # 使用日志规则报告违规
                for rule in self.log_rules:
                    self.violations.append({
                        'rule_code': rule['rule_code'],
                        'rule_name': rule['rule_name'],
                        'rule_level': rule['rule_level'],
                        'file_path': self.file_path,
                        'line_number': call_line_log or 1,
                        "violation_desc": f"循环内调用方法 {method_name}()，该方法包含日志调用 {log_var}.{log_method}()（在循环中间接调用）",
                        'solution': rule['solution'],
                        'match_type': f'跨方法循环调用({loop_type})',
                        'context': get_context(self.lines, call_line_log) if call_line_log else ''
                    })
                    break  # 只使用第一个匹配的日志规则
            else:
                # 类调用: (line_num, class_name, method_call)
                call_line, class_name, method_call = call
                # 验证类是否匹配规则
                imported_full = self.imported_classes.get(class_name)
                matched_rule = None
                
                if imported_full and imported_full in self.full_class_map:
                    matched_rule = self.full_class_map[imported_full]
                else:
                    for rule in self.short_class_map.get(class_name, []):
                        matched_rule = rule
                        break
                
                if not matched_rule:
                    continue
                
                # 报告违规（使用原始禁止类调用的行号 call_line）
                self.violations.append({
                    'rule_code': matched_rule['rule_code'],
                    'rule_name': matched_rule['rule_name'],
                    'rule_level': matched_rule['rule_level'],
                    'file_path': self.file_path,
                    'line_number': call_line or 1,
                    "violation_desc": f"循环内调用方法 {method_name}()，该方法包含禁止类调用 {matched_rule['full_class_name']}.{method_call}()（在循环中间接调用）",
                    'solution': matched_rule['solution'],
                    'match_type': f'跨方法循环调用({loop_type})',
                    'context': get_context(self.lines, call_line) if call_line else ''
                })
    
    def _add_log_violation(self, expr, method: str, loop_type: str, context: str):
        """添加日志违规"""
        line_num = get_node_position(expr)
        
        for rule in self.log_rules:
            self.violations.append({
                'rule_code': rule['rule_code'],
                'rule_name': rule['rule_name'],
                'rule_level': rule['rule_level'],
                'file_path': self.file_path,
                'line_number': line_num or 1,
                'violation_desc': f'{context}循环内调用日志方法 logger.{method}()',
                'solution': rule['solution'],
                'match_type': f'循环内日志调用({loop_type})',
                'context': get_context(self.lines, line_num) if line_num else ''
            })
    
    def _add_log_violation(self, expr, method: str, loop_type: str, context: str):
        """添加日志违规"""
        line_num = get_node_position(expr)
        
        for rule in self.log_rules:
            self.violations.append({
                'rule_code': rule['rule_code'],
                'rule_name': rule['rule_name'],
                'rule_level': rule['rule_level'],
                'file_path': self.file_path,
                'line_number': line_num or 1,
                'violation_desc': f'{context}循环内调用日志方法 logger.{method}()',
                'solution': rule['solution'],
                'match_type': f'循环内日志调用({loop_type})',
                'context': get_context(self.lines, line_num) if line_num else ''
            })
    
    def _add_class_violation(self, expr, class_name: str, method: str, loop_type: str, context: str):
        """添加类方法调用违规"""
        line_num = get_node_position(expr)
        
        # 验证类是否匹配
        imported_full = self.imported_classes.get(class_name)
        matched_rule = None
        
        if imported_full and imported_full in self.full_class_map:
            matched_rule = self.full_class_map[imported_full]
        else:
            for rule in self.short_class_map.get(class_name, []):
                matched_rule = rule
                break
        
        if not matched_rule:
            return
        
        self.violations.append({
            'rule_code': matched_rule['rule_code'],
            'rule_name': matched_rule['rule_name'],
            'rule_level': matched_rule['rule_level'],
            'file_path': self.file_path,
            'line_number': line_num or 1,
            'violation_desc': f'{context}循环内调用禁止类方法 {matched_rule["full_class_name"]}.{method}()',
            'solution': matched_rule['solution'],
            'match_type': f'循环内类方法调用({loop_type})',
            'context': get_context(self.lines, line_num) if line_num else ''
        })
    
    def _add_instantiation_violation(self, expr, class_name: str, loop_type: str, context: str, match_type_override: str = None):
        """添加类实例化违规"""
        line_num = get_node_position(expr)
        
        imported_full = self.imported_classes.get(class_name)
        matched_rule = None
        
        if imported_full and imported_full in self.full_class_map:
            matched_rule = self.full_class_map[imported_full]
        else:
            for rule in self.short_class_map.get(class_name, []):
                matched_rule = rule
                break
        
        if not matched_rule:
            return
        
        # 根据是否有 match_type_override 决定描述和匹配类型
        if match_type_override:
            violation_desc = f'{context}循环内构造器引用禁止类 {matched_rule["full_class_name"]}::new'
            match_type = f'{match_type_override}({loop_type})'
        else:
            violation_desc = f'{context}循环内实例化禁止类 {matched_rule["full_class_name"]}'
            match_type = f'循环内类实例化({loop_type})'
        
        
        self.violations.append({
            'rule_code': matched_rule['rule_code'],
            'rule_name': matched_rule['rule_name'],
            'rule_level': matched_rule['rule_level'],
            'file_path': self.file_path,
            'line_number': line_num or 1,
            'violation_desc': violation_desc,
            'solution': matched_rule['solution'],
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
    
    detector = LoopClassViolationDetector(file_path_normalized, content, rules)
    return detector.detect()


def scan_project(project_root: Path = None, rule_file: Path = None) -> List[Dict]:
    """扫描项目中的所有Java文件"""
    scan_start_time = time.time()
    root = project_root or PROJECT_ROOT
    rules_path = rule_file or RULE_FILE
    
    if DEBUG_LOG:
        print("[步骤1] 解析规则文件...")
    rules = parse_loop_class_rule_file(rules_path)
    if DEBUG_LOG:
        print(f"  加载规则数量: {len(rules)}")
    
    # 打印待检测的规则类清单
    short_class_map = {}
    for rule in rules:
        if rule['class_short_name'] not in short_class_map:
            short_class_map[rule['class_short_name']] = []
        short_class_map[rule['class_short_name']].append(rule)
    print(f"[检测规则类清单] {list(short_class_map.keys())}")
    
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
    # 打印待检测的规则类清单
    short_class_map = {}
    for rule in rules:
        if rule['class_short_name'] not in short_class_map:
            short_class_map[rule['class_short_name']] = []
        short_class_map[rule['class_short_name']].append(rule)
    print(f"[检测规则类清单] {list(short_class_map.keys())}")
    
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
    print("Java代码循环内禁止类检测工具")
    print("=" * 60)
    
    rules = parse_loop_class_rule_file(RULE_FILE)
    
    if specified_files:
        violations = scan_specified_files(specified_files, rules)
    else:
        violations = scan_project()
    
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
    output_result_file = SCRIPT_DIR.parent / "result" / "scan_java_loop_class_result.json"
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
