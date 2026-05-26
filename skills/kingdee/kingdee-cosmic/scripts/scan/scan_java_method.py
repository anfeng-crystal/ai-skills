# -*- coding: utf-8 -*-
"""
Java代码方法检测工具（语法解析版）
使用 javalang 语法解析器检测禁止方法的调用
功能：检测禁止调用指定类的指定方法
"""

import os
import re
import sys
import json
import time
from pathlib import Path

# 技能根目录（当前脚本所在目录）
SCRIPT_DIR = Path(__file__).parent

# Direct debug file write at module load
_debug_file = str(SCRIPT_DIR.parent / "result" / "scan_method_debug.txt")
try:
    os.makedirs(os.path.dirname(_debug_file), exist_ok=True)
    with open(_debug_file, 'w', encoding='utf-8') as f:
        f.write("=== scan_java_method.py module loaded ===\n")
except Exception as e:
    pass

try:
    import javalang
except ImportError:
    print("错误: 请先安装 javalang 库")
    print("执行命令: pip install javalang")
    exit(1)

# 是否开启调试日志
DEBUG_LOG = False

# Debug output file - use relative path
DEBUG_OUTPUT_FILE = str(SCRIPT_DIR.parent / "result" / "scan_method_debug.txt")

def debug_print(msg):
    """Print debug message to both console and file"""
    if DEBUG_LOG:
        try:
            print(msg)
        except:
            pass
        if DEBUG_OUTPUT_FILE:
            try:
                import os
                os.makedirs(os.path.dirname(DEBUG_OUTPUT_FILE), exist_ok=True)
                with open(DEBUG_OUTPUT_FILE, 'a', encoding='utf-8') as f:
                    f.write(msg + '\n')
            except Exception as e:
                try:
                    print(f"[DEBUG ERROR] Failed to write to debug file: {e}")
                except:
                    pass

# 项目根目录（工作空间根目录）
# 脚本位于: <skill-root>/scripts/scan/
# 默认项目根目录按当前工作目录或显式参数传入
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent

# 规则文件路径（相对于脚本目录）
RULE_FILE = SCRIPT_DIR.parent / "references" / "sonar_cve_method.md"


def parse_method_rule_file(rule_file):
    """
    解析方法规则文件
    规则格式：class = xxx; method = yyy
    """
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
                
                # 解析 class 和 method
                class_match = re.search(r'class\s*=\s*([^\s;]+)', rule_config)
                method_match = re.search(r'method\s*=\s*([^\s;]+)', rule_config)
                
                if class_match and method_match:
                    full_class_name = class_match.group(1)
                    methods_str = method_match.group(1)
                    # 方法可能有多个，用逗号分隔
                    methods = [m.strip() for m in methods_str.split(',')]
                    class_short_name = full_class_name.split('.')[-1]
                    package_name = '.'.join(full_class_name.split('.')[:-1])
                    
                    for method_name in methods:
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


def find_java_files(project_root):
    """查找所有Java文件"""
    java_files = []
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
        dirs[:] = [d for d in dirs if d not in ['build', '.gradle', '.idea', 'gradle']
                   and not d.endswith('-cosmic-debug')]
        
        # 如果当前目录是技能目录，跳过文件收集
        if is_skill_dir:
            continue
            
        for file in files:
            if file.endswith('.java'):
                java_files.append(os.path.join(root, file))
    return java_files


def get_context(lines, line_number, context_lines=2):
    """获取问题行的上下文代码"""
    if line_number is None:
        return "无法获取行号"
    
    start = max(0, line_number - context_lines - 1)
    end = min(len(lines), line_number + context_lines)
    
    context_parts = []
    for i in range(start, end):
        prefix = ">>> " if i == line_number - 1 else "    "
        context_parts.append(f"{prefix}{i + 1}: {lines[i]}")
    
    return '\n'.join(context_parts)


def extract_position(node, lines=None):
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


def scan_java_file_with_ast(file_path, rules):
    """
    使用javalang语法解析器扫描Java文件，检测方法调用
    """
    # Clear debug file at start of scan
    if DEBUG_OUTPUT_FILE:
        try:
            with open(DEBUG_OUTPUT_FILE, 'w', encoding='utf-8') as f:
                f.write(f"=== Scan started for: {file_path} ===\n")
        except Exception as e:
            print(f"[DEBUG ERROR] Failed to clear debug file: {e}")
    
    file_start_time = time.time()
    violations = []
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        lines = content.split('\n')
    
    # 获取相对路径
    rel_path = os.path.relpath(file_path, PROJECT_ROOT)
    file_path_normalized = rel_path.replace('\\', '/')
    
    if DEBUG_LOG:
        print(f"  [解析] {file_path_normalized} ({len(lines)}行)")
    
    # 解析Java代码为AST
    parse_start = time.time()
    
    # 使用统一解析器（javalang + 预处理 + JavaParser fallback）
    from java_parser_unified import parse_java_code, JavaCodePreprocessor
    
    tree = parse_java_code(content)
    preprocessor = None
    
    if tree is None:
        if DEBUG_LOG:
            print(f"    [警告] 所有解析器均失败")
        return [{
            'rule_code': 'PARSE_ERROR',
            'rule_name': '语法解析错误',
            'rule_level': '低危',
            'file_path': file_path_normalized,
            'line_number': 1,
            'violation_desc': '文件无法解析: 所有解析器均失败',
            'solution': '请检查Java语法是否正确',
            'match_type': '解析错误',
            'context': lines[0] if lines else ''
        }]
    
    # 检查是否使用了预处理
    if hasattr(tree, '_preprocessor'):
        preprocessor = tree._preprocessor
    
    if DEBUG_LOG:
        parse_time = time.time() - parse_start
        print(f"    [AST解析耗时] {parse_time:.3f}秒")
    
    # 构建规则查找表
    # key: (class_short_name, method_name) -> [rules]
    method_rule_map = {}
    for rule in rules:
        key = (rule['class_short_name'], rule['method_name'])
        if key not in method_rule_map:
            method_rule_map[key] = []
        method_rule_map[key].append(rule)
    
    # 收集文件中的import信息
    imported_classes = {}  # 类简称 -> 全限定类名
    wildcard_packages = set()  # 通配符导入的包
    
    if tree.imports:
        for imp in tree.imports:
            if imp.path:
                if imp.wildcard:
                    package = imp.path.rstrip('.*')
                    wildcard_packages.add(package)
                else:
                    full_path = imp.path
                    class_name = full_path.split('.')[-1]
                    imported_classes[class_name] = full_path
    
    # 构建变量类型映射表：变量名 -> 类简称
    # 用于跟踪局部变量的类型，以检测实例方法调用
    variable_types = {}
    
    def extract_class_name_from_type(type_node):
        """从类型节点提取类名"""
        if type_node is None:
            return None
        # 处理 ReferenceType 类型
        if hasattr(type_node, 'name'):
            name = type_node.name
            if isinstance(name, str):
                return name
            elif hasattr(name, 'value'):
                return name.value
        # 处理 javalang 的 Type 类型
        if hasattr(type_node, 'dimensions') and hasattr(type_node, 'sub_type'):
            # 数组类型，获取基本类型
            sub_type = type_node
            while hasattr(sub_type, 'sub_type') and sub_type.sub_type:
                sub_type = sub_type.sub_type
            if hasattr(sub_type, 'name'):
                return sub_type.name
        return None
    
    def collect_variable_types(node, visited=None):
        """递归收集局部变量声明中的变量类型"""
        if node is None:
            return
        
        # 防止循环引用导致的无限递归
        if visited is None:
            visited = set()
        
        node_id = id(node)
        if node_id in visited:
            return
        visited.add(node_id)
        
        # 检查是否是局部变量声明
        if isinstance(node, javalang.tree.LocalVariableDeclaration) or type(node).__name__ == 'LocalVariableDeclaration':
            var_type = getattr(node, 'type', None)
            class_name = extract_class_name_from_type(var_type)
            if class_name:
                declarators = getattr(node, 'declarators', None)
                if declarators:
                    for decl in declarators:
                        var_name = getattr(decl, 'name', None)
                        if var_name:
                            variable_types[var_name] = class_name
        
        # 递归检查子节点 - 使用 javalang 的 walk_tree 方式
        try:
            if hasattr(node, '__iter__') and not isinstance(node, (str, bytes)):
                for child in node:
                    if child is not node and child is not None:
                        collect_variable_types(child, visited)
        except (TypeError, RecursionError):
            pass
        
        # 检查常见的包含子节点的属性
        for attr_name in ['body', 'statements', 'then_statement', 'else_statement', 
                          'control', 'block', 'catches', 'members', 'types', 'arguments']:
            if hasattr(node, attr_name):
                try:
                    attr_val = getattr(node, attr_name)
                    if attr_val is not None and attr_val is not node:
                        if isinstance(attr_val, list):
                            for item in attr_val:
                                if item is not None:
                                    collect_variable_types(item, visited)
                        else:
                            collect_variable_types(attr_val, visited)
                except (TypeError, RecursionError):
                    pass
    
    # 收集所有局部变量类型
    collect_variable_types(tree)
    
    # 方法返回类型映射表（用于链式调用分析）
    # 键：方法名，值：返回类型的类简称
    method_return_types = {
        'getView': 'IFormView',
        # 可以在这里添加更多方法返回类型映射
    }
    
    def collect_method_invocations(node, methods=None):
        """递归收集节点中的所有方法调用"""
        if methods is None:
            methods = []
        
        if isinstance(node, javalang.tree.MethodInvocation) or type(node).__name__ == 'MethodInvocation':
            methods.append(node)
        
        # 递归检查所有子节点
        for attr_name in dir(node):
            if attr_name.startswith('_'):
                continue
            try:
                attr = getattr(node, attr_name)
                if isinstance(attr, javalang.tree.MethodInvocation) or type(attr).__name__ == 'MethodInvocation':
                    methods.append(attr)
                    collect_method_invocations(attr, methods)
                elif isinstance(attr, list):
                    for item in attr:
                        if isinstance(item, javalang.tree.MethodInvocation) or type(item).__name__ == 'MethodInvocation':
                            methods.append(item)
                            collect_method_invocations(item, methods)
                        elif hasattr(item, '__dict__'):
                            collect_method_invocations(item, methods)
                elif hasattr(attr, '__dict__'):
                    collect_method_invocations(attr, methods)
            except:
                pass
        
        return methods
    
    def check_method_chain(methods, context=""):
        """检查方法调用链中的违规
        
        例如：this.getView().updateView()
        需要识别 getView() 返回 IFormView，然后 updateView() 是 IFormView 的方法
        """
        if not methods:
            return
        
        # 按顺序处理方法调用链
        current_class = None
        
        for method in methods:
            member = getattr(method, 'member', None)
            if not member:
                continue
            
            # 检查当前方法是否匹配规则
            if current_class:
                key = (current_class, member)
                if key in method_rule_map:
                    for rule in method_rule_map[key]:
                        imported_full = imported_classes.get(current_class)
                        is_wildcard_match = rule['package_name'] in wildcard_packages
                        is_java_lang_class = rule['package_name'] == 'java.lang' and current_class == rule['class_short_name']
                        is_variable_type_match = current_class == rule['class_short_name']
                        
                        if imported_full == rule['full_class_name'] or is_wildcard_match or is_java_lang_class or is_variable_type_match:
                            line_num = extract_position(method)
                            violations.append({
                                'rule_code': rule['rule_code'],
                                'rule_name': rule['rule_name'],
                                'rule_level': rule['rule_level'],
                                'file_path': file_path_normalized,
                                'line_number': line_num or 1,
                                'violation_desc': f'{context}调用禁止方法 {rule["full_class_name"]}.{member}()',
                                'solution': rule['solution'],
                                'match_type': '方法调用链',
                                'context': get_context(lines, line_num) if line_num else ''
                            })
            
            # 更新当前类为该方法返回的类型
            current_class = method_return_types.get(member)
    
    # 检查方法调用
    def check_method_call(expr, context=""):
        """检查方法调用是否违规"""
        if expr is None:
            return
        
        # 处理 This 表达式（如 this.getView().updateView()）
        # javalang 会将这种链式调用解析为 This 对象包含多个 MethodInvocation
        if isinstance(expr, javalang.tree.This) or type(expr).__name__ == 'This':
            # 收集 This 表达式中的所有方法调用
            methods_in_this = collect_method_invocations(expr)
            # 检查方法调用链
            check_method_chain(methods_in_this, context)
            return
        
        # MethodInvocation: object.method(args)
        # 使用类型名称检查，兼容 javalang 和适配层
        if isinstance(expr, javalang.tree.MethodInvocation) or type(expr).__name__ == 'MethodInvocation':
            qualifier = getattr(expr, 'qualifier', None)
            member = getattr(expr, 'member', None)
            line_num = extract_position(expr)
            
            debug_print(f"    [MethodCall] qualifier='{qualifier}', member='{member}' at line {line_num}")

            if member:
                # 确定用于规则匹配的类名
                # 1. 如果 qualifier 是类名（静态方法调用），直接使用
                # 2. 如果 qualifier 是变量名，尝试从变量类型映射中获取其类型
                # 3. 如果 qualifier 为空（如 this.method()），跳过
                class_name_for_match = None
                
                if qualifier:
                    # 先检查 qualifier 是否是已知类名（在import中或变量类型映射中）
                    if qualifier in imported_classes:
                        class_name_for_match = qualifier
                    else:
                        # 检查是否是局部变量，获取其类型
                        var_type = variable_types.get(qualifier)
                        if var_type:
                            class_name_for_match = var_type
                        else:
                            # 可能是全限定类名，直接使用
                            class_name_for_match = qualifier
                
                # 检查是否匹配规则
                if class_name_for_match:
                    key = (class_name_for_match, member)
                    if key in method_rule_map:
                        for rule in method_rule_map[key]:
                            # 验证类是否匹配（通过import确认）
                            imported_full = imported_classes.get(class_name_for_match)
                            is_wildcard_match = rule['package_name'] in wildcard_packages
                            # java.lang 包下的类自动导入，无需显式 import
                            is_java_lang_class = rule['package_name'] == 'java.lang' and class_name_for_match == rule['class_short_name']
                            # 检查变量类型是否匹配
                            is_variable_type_match = class_name_for_match == rule['class_short_name']

                            if imported_full == rule['full_class_name'] or is_wildcard_match or is_java_lang_class or is_variable_type_match:
                                violations.append({
                                    'rule_code': rule['rule_code'],
                                    'rule_name': rule['rule_name'],
                                    'rule_level': rule['rule_level'],
                                    'file_path': file_path_normalized,
                                    'line_number': line_num or 1,
                                    'violation_desc': f'{context}调用禁止方法 {rule["full_class_name"]}.{member}()',
                                    'solution': rule['solution'],
                                    'match_type': '方法调用',
                                    'context': get_context(lines, line_num) if line_num else ''
                                })
            
            # 递归检查参数中的方法调用
            args = getattr(expr, 'arguments', None)
            if args:
                for arg in args:
                    check_method_call(arg, context)
            
            # 递归检查 selectors（链式调用，如 System.getProperties().toString()）
            expr_selectors = getattr(expr, 'selectors', None)
            if expr_selectors:
                for selector in expr_selectors:
                    check_method_call(selector, context)
        
        # ClassCreator: new ClassName(args) - 检查参数中的方法调用
        elif isinstance(expr, javalang.tree.ClassCreator) or type(expr).__name__ == 'ClassCreator':
            args = getattr(expr, 'arguments', None)
            if args:
                for arg in args:
                    check_method_call(arg, context)
        
        # BinaryOperation
        elif isinstance(expr, javalang.tree.BinaryOperation) or type(expr).__name__ == 'BinaryOperation':
            left = getattr(expr, 'operandl', None)
            right = getattr(expr, 'operandr', None)
            if left:
                check_method_call(left, context)
            if right:
                check_method_call(right, context)
        
        # Assignment
        elif isinstance(expr, javalang.tree.Assignment) or type(expr).__name__ == 'Assignment':
            expr_val = getattr(expr, 'expressionl', None) or getattr(expr, 'expression', None)
            if expr_val:
                check_method_call(expr_val, context)
        
        # TernaryExpression
        elif isinstance(expr, javalang.tree.TernaryExpression) or type(expr).__name__ == 'TernaryExpression':
            condition = getattr(expr, 'condition', None)
            if_true = getattr(expr, 'if_true', None) or getattr(expr, 'true_expression', None)
            if_false = getattr(expr, 'if_false', None) or getattr(expr, 'false_expression', None)
            if condition:
                check_method_call(condition, context)
            if if_true:
                check_method_call(if_true, context)
            if if_false:
                check_method_call(if_false, context)
        
        # Literal, This, Super 等节点可能有 selectors 属性（链式调用）
        # 例如: "test".equalsIgnoreCase(...) 中 "test" 是 Literal，equalsIgnoreCase 是 selector
        else:
            # 检查是否有 selectors 属性（链式方法调用）
            selectors = getattr(expr, 'selectors', None)
            if selectors:
                for selector in selectors:
                    check_method_call(selector, context)
            
            # 检查是否是 Lambda 表达式（可能作为方法参数）
            if type(expr).__name__ in ('LambdaExpression', 'Lambda'):
                lambda_body = getattr(expr, 'body', None)
                if lambda_body:
                    if hasattr(lambda_body, 'statements'):
                        for s in lambda_body.statements:
                            scan_statement(s, context)
                    elif isinstance(lambda_body, list):
                        for s in lambda_body:
                            scan_statement(s, context)
                    else:
                        check_method_call(lambda_body, context)
    
    def scan_statement(stmt, context=""):
        """扫描语句"""
        if stmt is None:
            return

        # 局部变量声明
        # 使用类型名称检查，兼容 javalang 和适配层
        if isinstance(stmt, javalang.tree.LocalVariableDeclaration) or type(stmt).__name__ == 'LocalVariableDeclaration':
            # 检查初始化表达式
            declarators = getattr(stmt, 'declarators', None)
            if declarators:
                for decl in declarators:
                    init = getattr(decl, 'initializer', None)
                    if init:
                        check_method_call(init, context)
        
        # 表达式语句
        elif isinstance(stmt, javalang.tree.StatementExpression) or type(stmt).__name__ == 'StatementExpression':
            expr_val = getattr(stmt, 'expression', None) or getattr(stmt, 'expressionl', None)
            if expr_val:
                check_method_call(expr_val, context)
        
        # return语句
        elif isinstance(stmt, javalang.tree.ReturnStatement) or type(stmt).__name__ == 'ReturnStatement':
            ret_expr = getattr(stmt, 'expression', None) or getattr(stmt, 'expressionl', None)
            if ret_expr:
                check_method_call(ret_expr, context)
        
        # if语句
        elif isinstance(stmt, javalang.tree.IfStatement) or type(stmt).__name__ == 'IfStatement':
            # 检查条件
            condition = getattr(stmt, 'condition', None)
            if condition:
                check_method_call(condition, context)
            # 递归处理then/else
            then_stmt = getattr(stmt, 'then_statement', None)
            else_stmt = getattr(stmt, 'else_statement', None)
            if then_stmt:
                # BlockStatement 需要获取其 statements 属性
                if hasattr(then_stmt, 'statements'):
                    for s in then_stmt.statements:
                        scan_statement(s, context)
                elif isinstance(then_stmt, list):
                    for s in then_stmt:
                        scan_statement(s, context)
                else:
                    scan_statement(then_stmt, context)
            if else_stmt:
                if hasattr(else_stmt, 'statements'):
                    for s in else_stmt.statements:
                        scan_statement(s, context)
                else:
                    scan_statement(else_stmt, context)
        
        # for循环
        elif isinstance(stmt, javalang.tree.ForStatement) or type(stmt).__name__ == 'ForStatement':
            # 检查循环条件
            ctrl = getattr(stmt, 'control', None)
            if ctrl:
                # 检查循环条件中的方法调用
                for attr in ['condition', 'init', 'update']:
                    val = getattr(ctrl, attr, None)
                    if val:
                        if isinstance(val, list):
                            for v in val:
                                check_method_call(v, context)
                        else:
                            check_method_call(val, context)
            # 递归处理循环体
            body_stmt = getattr(stmt, 'body', None)
            if body_stmt:
                # BlockStatement 需要获取其 statements 属性
                if hasattr(body_stmt, 'statements'):
                    for s in body_stmt.statements:
                        scan_statement(s, context)
                elif isinstance(body_stmt, list):
                    for s in body_stmt:
                        scan_statement(s, context)
                else:
                    scan_statement(body_stmt, context)
        
        # while循环
        elif isinstance(stmt, javalang.tree.WhileStatement) or type(stmt).__name__ == 'WhileStatement':
            condition = getattr(stmt, 'condition', None)
            if condition:
                check_method_call(condition, context)
            while_body = getattr(stmt, 'body', None)
            if while_body:
                # BlockStatement 需要获取其 statements 属性
                if hasattr(while_body, 'statements'):
                    for s in while_body.statements:
                        scan_statement(s, context)
                elif isinstance(while_body, list):
                    for s in while_body:
                        scan_statement(s, context)
                else:
                    scan_statement(while_body, context)
        
        # try-catch
        elif isinstance(stmt, javalang.tree.TryStatement) or type(stmt).__name__ == 'TryStatement':
            try_block = getattr(stmt, 'block', None)
            if try_block:
                for s in try_block:
                    scan_statement(s, context)
            try_catches = getattr(stmt, 'catches', None)
            if try_catches:
                for catch in try_catches:
                    catch_block = getattr(catch, 'block', None)
                    if catch_block:
                        for s in catch_block:
                            scan_statement(s, context)
        
        # Lambda表达式
        elif type(stmt).__name__ == 'LambdaExpression' or type(stmt).__name__ == 'Lambda':
            debug_print(f"    [Lambda] Found LambdaExpression")
            lambda_body = getattr(stmt, 'body', None)
            if lambda_body:
                # Lambda body 可能是表达式或代码块
                if hasattr(lambda_body, 'statements'):
                    # 代码块形式: (x) -> { statements }
                    stmts = lambda_body.statements if lambda_body.statements else []
                    debug_print(f"    [Lambda] Body is block with {len(stmts)} statements")
                    for s in stmts:
                        scan_statement(s, context)
                elif isinstance(lambda_body, list):
                    for s in lambda_body:
                        scan_statement(s, context)
                else:
                    # 表达式形式: (x) -> expression
                    debug_print(f"    [Lambda] Body is expression: {type(lambda_body).__name__}")
                    check_method_call(lambda_body, context)
        
        # 代码块
        elif isinstance(stmt, (list, tuple)):
            for s in stmt:
                scan_statement(s, context)
    
    def scan_methods(members, context=""):
        """扫描方法声明"""
        for member in members:
            if isinstance(member, javalang.tree.MethodDeclaration) or type(member).__name__ == 'MethodDeclaration':
                method_name = getattr(member, 'name', 'unknown')
                # 检查方法体
                method_body = getattr(member, 'body', None)
                if method_body:
                    # javalang 的 body 可能是列表或 BlockStatement
                    if isinstance(method_body, list):
                        statements = method_body
                    elif hasattr(method_body, 'statements'):
                        statements = method_body.statements
                    else:
                        statements = [method_body]
                    for stmt in statements:
                        scan_statement(stmt, f"{context}方法{method_name}中")

            elif isinstance(member, javalang.tree.ConstructorDeclaration) or type(member).__name__ == 'ConstructorDeclaration':
                ctor_body = getattr(member, 'body', None)
                if ctor_body:
                    for stmt in ctor_body:
                        scan_statement(stmt, context)

            elif isinstance(member, javalang.tree.FieldDeclaration) or type(member).__name__ == 'FieldDeclaration':
                # 检查字段初始化
                declarators = getattr(member, 'declarators', None)
                if declarators:
                    for decl in declarators:
                        init = getattr(decl, 'initializer', None)
                        if init:
                            check_method_call(init, context)
    
    # 扫描类成员
    if tree.types:
        for type_decl in tree.types:
            class_name = getattr(type_decl, 'name', 'unknown')
            body = getattr(type_decl, 'body', None)
            if body:
                scan_methods(body, f"类{class_name}中")
    
    # 额外的全局扫描：直接遍历所有 MethodInvocation 节点
    # 这样可以捕获 Lambda 表达式、匿名类等结构内的方法调用
    try:
        for path, node in tree.filter(javalang.tree.MethodInvocation):
            qualifier = getattr(node, 'qualifier', None)
            member = getattr(node, 'member', None)
            line_num = extract_position(node)
            
            if member:
                class_name_for_match = None
                
                if qualifier:
                    if qualifier in imported_classes:
                        class_name_for_match = qualifier
                    else:
                        var_type = variable_types.get(qualifier)
                        if var_type:
                            class_name_for_match = var_type
                        else:
                            class_name_for_match = qualifier
                
                if class_name_for_match:
                    key = (class_name_for_match, member)
                    if key in method_rule_map:
                        for rule in method_rule_map[key]:
                            imported_full = imported_classes.get(class_name_for_match)
                            is_wildcard_match = rule['package_name'] in wildcard_packages
                            is_java_lang_class = rule['package_name'] == 'java.lang' and class_name_for_match == rule['class_short_name']
                            is_variable_type_match = class_name_for_match == rule['class_short_name']

                            if imported_full == rule['full_class_name'] or is_wildcard_match or is_java_lang_class or is_variable_type_match:
                                # 检查是否已经报告过（避免重复）
                                already_reported = False
                                for v in violations:
                                    if v['line_number'] == line_num and v['rule_code'] == rule['rule_code']:
                                        already_reported = True
                                        break
                                
                                if not already_reported:
                                    violations.append({
                                        'rule_code': rule['rule_code'],
                                        'rule_name': rule['rule_name'],
                                        'rule_level': rule['rule_level'],
                                        'file_path': file_path_normalized,
                                        'line_number': line_num or 1,
                                        'violation_desc': f'调用禁止方法 {rule["full_class_name"]}.{member}()',
                                        'solution': rule['solution'],
                                        'match_type': '全局扫描',
                                        'context': get_context(lines, line_num) if line_num else ''
                                    })
    except Exception as e:
        pass  # 忽略遍历错误
    
    # 全局扫描：检测方法引用（MethodReference）
    # 方法引用语法: ClassName::methodName 或 instance::methodName
    # 例如: BusinessDataServiceHelper::loadRefence
    try:
        for path, node in tree.filter(javalang.tree.MethodReference):
            # 获取方法引用的类名和方法名
            expr = getattr(node, 'expression', None)
            method_ref = getattr(node, 'method', None)
            line_num = extract_position(node)
            
            # expression 通常是 MemberReference，其 member 属性是类名
            class_name = None
            method_name = None
            
            if expr and hasattr(expr, 'member'):
                class_name = expr.member
                # 获取 expression 的行号（更准确）
                if hasattr(expr, 'position') and expr.position:
                    line_num = expr.position[0]
            
            # method 通常是 MemberReference，其 member 属性是方法名
            if method_ref and hasattr(method_ref, 'member'):
                method_name = method_ref.member
            
            debug_print(f"    [MethodReference] class='{class_name}', method='{method_name}' at line {line_num}")
            
            if class_name and method_name:
                # 检查是否匹配规则
                key = (class_name, method_name)
                if key in method_rule_map:
                    for rule in method_rule_map[key]:
                        imported_full = imported_classes.get(class_name)
                        is_wildcard_match = rule['package_name'] in wildcard_packages
                        is_java_lang_class = rule['package_name'] == 'java.lang' and class_name == rule['class_short_name']
                        is_variable_type_match = class_name == rule['class_short_name']
                        
                        if imported_full == rule['full_class_name'] or is_wildcard_match or is_java_lang_class or is_variable_type_match:
                            # 检查是否已经报告过（避免重复）
                            already_reported = False
                            for v in violations:
                                if v['line_number'] == line_num and v['rule_code'] == rule['rule_code']:
                                    already_reported = True
                                    break
                            
                            if not already_reported:
                                violations.append({
                                    'rule_code': rule['rule_code'],
                                    'rule_name': rule['rule_name'],
                                    'rule_level': rule['rule_level'],
                                    'file_path': file_path_normalized,
                                    'line_number': line_num or 1,
                                    'violation_desc': f'方法引用禁止方法 {rule["full_class_name"]}::{method_name}',
                                    'solution': rule['solution'],
                                    'match_type': '方法引用',
                                    'context': get_context(lines, line_num) if line_num else ''
                                })
    except Exception as e:
        debug_print(f"    [MethodReference扫描错误] {e}")
    
    if DEBUG_LOG:
        file_total_time = time.time() - file_start_time
        if file_total_time > 0.5:
            print(f"    [文件总耗时] {file_total_time:.3f}秒, 发现{len(violations)}个违规")
    
    # 后处理：恢复预处理时替换的占位符
    if preprocessor:
        violations = preprocessor.postprocess_violations(violations)
    
    # Extra global scan: directly traverse all MethodInvocation nodes
    # This captures method calls inside Lambda expressions, anonymous classes, etc.
    try:
        for path, node in tree.filter(javalang.tree.MethodInvocation):
            qualifier = getattr(node, 'qualifier', None)
            member = getattr(node, 'member', None)
            line_num = extract_position(node)
            
            if member:
                class_name_for_match = None
                
                if qualifier:
                    if qualifier in imported_classes:
                        class_name_for_match = qualifier
                    else:
                        var_type = variable_types.get(qualifier)
                        if var_type:
                            class_name_for_match = var_type
                        else:
                            class_name_for_match = qualifier
                
                if class_name_for_match:
                    key = (class_name_for_match, member)
                    if key in method_rule_map:
                        for rule in method_rule_map[key]:
                            imported_full = imported_classes.get(class_name_for_match)
                            is_wildcard_match = rule['package_name'] in wildcard_packages
                            is_java_lang_class = rule['package_name'] == 'java.lang' and class_name_for_match == rule['class_short_name']
                            is_variable_type_match = class_name_for_match == rule['class_short_name']

                            if imported_full == rule['full_class_name'] or is_wildcard_match or is_java_lang_class or is_variable_type_match:
                                already_reported = False
                                for v in violations:
                                    if v['line_number'] == line_num and v['rule_code'] == rule['rule_code']:
                                        already_reported = True
                                        break
                                
                                if not already_reported:
                                    violations.append({
                                        'rule_code': rule['rule_code'],
                                        'rule_name': rule['rule_name'],
                                        'rule_level': rule['rule_level'],
                                        'file_path': file_path_normalized,
                                        'line_number': line_num or 1,
                                        'violation_desc': f'调用禁止方法 {rule["full_class_name"]}.{member}()',
                                        'solution': rule['solution'],
                                        'match_type': '全局扫描',
                                        'context': get_context(lines, line_num) if line_num else ''
                                    })
    except Exception as e:
        pass
    
    return violations


def scan_project(project_root=None, rule_file=None, target_files=None):
    """
    扫描项目中的Java文件，返回违规列表
    
    参数:
        project_root: 项目根目录
        rule_file: 规则文件路径
        target_files: 指定扫描的文件列表（相对路径），如果为None则扫描整个项目
    """
    scan_start_time = time.time()
    root = Path(project_root) if project_root else PROJECT_ROOT
    rules_path = Path(rule_file) if rule_file else RULE_FILE
    
    # 1. 解析规则文件
    if DEBUG_LOG:
        print("[步骤1] 解析规则文件...")
    rules = parse_method_rule_file(rules_path)
    if DEBUG_LOG:
        print(f"  加载规则数量: {len(rules)}")

    # 打印需要检测的类和方法
    if DEBUG_LOG and rules:
        print("\n  [检测规则列表]")
        # 按类分组显示
        class_methods = {}
        for rule in rules:
            class_name = rule['full_class_name']
            method_name = rule['method_name']
            if class_name not in class_methods:
                class_methods[class_name] = []
            class_methods[class_name].append(method_name)

        for class_name, methods in sorted(class_methods.items()):
            print(f"    {class_name}: {', '.join(sorted(set(methods)))}")
        print()

    # 2. 确定要扫描的Java文件
    if DEBUG_LOG:
        print("[步骤2] 确定要扫描的Java文件...")
    
    if target_files:
        # 使用指定的文件列表
        java_files = []
        for target_file in target_files:
            # 处理相对路径，转换为绝对路径
            if not os.path.isabs(target_file):
                target_file = os.path.join(root, target_file)
            if os.path.exists(target_file) and target_file.endswith('.java'):
                java_files.append(target_file)
            elif DEBUG_LOG:
                print(f"  [警告] 文件不存在或非Java文件: {target_file}")
        if DEBUG_LOG:
            print(f"  指定扫描文件数量: {len(java_files)}")
    else:
        # 扫描整个项目
        java_files = find_java_files(root)
        if DEBUG_LOG:
            print(f"  Java文件数量: {len(java_files)}")
    
    # 3. 扫描文件
    if DEBUG_LOG:
        print("[步骤3] 扫描Java文件...")
    all_violations = []
    for idx, java_file in enumerate(java_files):
        violations = scan_java_file_with_ast(java_file, rules)
        all_violations.extend(violations)
        
        if DEBUG_LOG and (idx + 1) % 10 == 0:
            elapsed = time.time() - scan_start_time
            print(f"  [进度] {idx + 1}/{len(java_files)} 文件, 耗时 {elapsed:.1f}秒")
    
    if DEBUG_LOG:
        total_time = time.time() - scan_start_time
        print(f"\n[总耗时] {total_time:.2f}秒, 平均 {total_time/len(java_files):.3f}秒/文件")
    
    return all_violations



def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Java代码方法检测工具（语法解析版）')
    parser.add_argument('--file', dest='target_file',
                        help='指定要扫描的Java文件路径（相对于项目根目录），不指定则扫描整个项目')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Java代码方法检测工具（语法解析版）")
    print("=" * 60)
    
    # 确定目标文件
    target_files = None
    if args.target_file:
        target_files = [args.target_file]
        print(f"\n[模式] 指定文件扫描: {args.target_file}")
    else:
        print(f"\n[模式] 全项目扫描")
    
    violations = scan_project(target_files=target_files)
    
    # 统计
    violation_files = set(v['file_path'] for v in violations)
    level_counts = {'严重': 0, '高危': 0, '中危': 0, '低危': 0}
    for v in violations:
        level = v['rule_level']
        if level in level_counts:
            level_counts[level] += 1
    
    # 输出摘要
    print(f"\n扫描完成!")
    print(f"  违规文件数: {len(violation_files)}")
    print(f"  总违规数: {len(violations)}")
    print(f"  严重: {level_counts['严重']}, 高危: {level_counts['高危']}, 中危: {level_counts['中危']}, 低危: {level_counts['低危']}")
    
    # 输出 violations 结果到 JSON 文件
    output_result_file = SCRIPT_DIR.parent / "result" / "scan_java_method_result.json"
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
