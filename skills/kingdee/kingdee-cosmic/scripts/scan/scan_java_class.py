# -*- coding: utf-8 -*-
"""
Java代码类检测工具（语法解析版）
使用 javalang 语法解析器解析Java代码，准确检测禁止类的使用
优化点：
1. 使用AST语法树解析，避免正则误报
2. 准确识别import、类型声明、方法参数、泛型、继承等
3. 输出上下文代码片段
"""

import os
import re
import sys
import json
import time
from pathlib import Path

try:
    import javalang
except ImportError:
    print("错误: 请先安装 javalang 库")
    print("执行命令: pip install javalang")
    exit(1)

# 是否开启调试日志
DEBUG_LOG = False

# 技能根目录（当前脚本所在目录）
SCRIPT_DIR = Path(__file__).parent

# 项目根目录（工作空间根目录）
# 脚本位于: <skill-root>/scripts/scan/
# 默认项目根目录按当前工作目录或显式参数传入
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent

# 规则文件路径（相对于脚本目录）
RULE_FILE = SCRIPT_DIR.parent / "references" / "sonar_cve_class.md"


def parse_rule_file(rule_file):
    """解析规则文件，提取类检测规则"""
    rules = []
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
                
                # 解析 class = xxx
                class_match = re.search(r'class\s*=\s*([^\s|]+)', rule_config)
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


def find_java_files(project_root):
    """查找所有Java文件"""
    java_files = []
    project_root = Path(project_root).resolve()
    # 技能根目录（当前脚本所在目录的父目录的父目录）
    # 脚本路径: <skill_dir>/scripts/scan_xxx.py
    # 技能目录: <skill_dir>/
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
    """
    获取问题行的上下文代码
    line_number: 1-based行号
    """
    if line_number is None:
        return "无法获取行号"
    
    start = max(0, line_number - context_lines - 1)
    end = min(len(lines), line_number + context_lines)
    
    context_parts = []
    for i in range(start, end):
        prefix = ">>> " if i == line_number - 1 else "    "
        context_parts.append(f"{prefix}{i + 1}: {lines[i]}")
    
    return '\n'.join(context_parts)


def extract_position(node, lines, search_pattern=None):
    """从AST节点提取行号
    
    Args:
        node: AST节点
        lines: 源代码行列表
        search_pattern: 正则匹配模式（用于fallback）
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
    
    # 4. 使用传入的正则模式
    if search_pattern and lines:
        for i, line in enumerate(lines, 1):
            if re.search(search_pattern, line):
                return i
    
    return None


def scan_java_file_with_ast(file_path, rules):
    """
    使用javalang语法解析器扫描Java文件
    """
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
    full_class_map = {}  # 全限定类名 -> 规则
    short_class_map = {}  # 类简称 -> [规则列表]
    
    for rule in rules:
        full_class_map[rule['full_class_name']] = rule
        if rule['class_short_name'] not in short_class_map:
            short_class_map[rule['class_short_name']] = []
        short_class_map[rule['class_short_name']].append(rule)
    
    # 收集文件中的import信息
    imported_classes = {}  # 类简称 -> 全限定类名
    wildcard_packages = set()  # 通配符导入的包
    
    if tree.imports:
        for imp in tree.imports:
            if imp.path:
                if imp.wildcard:
                    # 通配符导入: import java.util.*;
                    package = imp.path.rstrip('.*')
                    wildcard_packages.add(package)
                else:
                    # 显式导入: import java.util.Date;
                    full_path = imp.path
                    class_name = full_path.split('.')[-1]
                    imported_classes[class_name] = full_path
    
    # 辅助函数：检查类型是否匹配禁止类
    def check_type_reference(type_obj, context_desc, node_for_position):
        """检查类型引用是否使用了禁止类"""
        if type_obj is None:
            return []
        
        results = []
        type_name = None
        
        # 获取类型名称
        if isinstance(type_obj, str):
            type_name = type_obj
        elif hasattr(type_obj, 'name'):
            type_name = type_obj.name
        elif hasattr(type_obj, 'qualifier') and type_obj.qualifier:
            # 全限定类名
            qualifier = type_obj.qualifier
            if qualifier in full_class_map:
                rule = full_class_map[qualifier]
                line_num = extract_position(node_for_position, lines)
                # 如果AST节点没有位置信息，尝试通过正则定位
                if line_num is None:
                    pattern = rf'\b{re.escape(qualifier)}\b'
                    for i, line in enumerate(lines, 1):
                        if re.search(pattern, line):
                            line_num = i
                            break
                if line_num is None:
                    return results  # 找不到行号则跳过
                results.append({
                    'rule_code': rule['rule_code'],
                    'rule_name': rule['rule_name'],
                    'rule_level': rule['rule_level'],
                    'file_path': file_path_normalized,
                    'line_number': line_num,
                    'violation_desc': f'{context_desc}直接使用全限定类名 {qualifier}',
                    'solution': rule['solution'],
                    'match_type': '全限定类名直接使用',
                    'context': get_context(lines, line_num)
                })
                return results
        
        if type_name and type_name in short_class_map:
            # 检查是否导入了该禁止类
            imported_full = imported_classes.get(type_name)
            is_in_wildcard = any(
                any(rule['package_name'] == pkg for rule in short_class_map[type_name])
                for pkg in wildcard_packages
            )
            
            if imported_full and imported_full in full_class_map:
                rule = full_class_map[imported_full]
                line_num = extract_position(node_for_position, lines)
                # 如果AST节点没有位置信息，尝试通过正则定位
                if line_num is None:
                    # 根据上下文选择不同的定位模式
                    if 'new' in context_desc:
                        pattern = rf'\bnew\s+{re.escape(type_name)}\s*\('
                    else:
                        pattern = rf'\b{re.escape(type_name)}\b'
                    for i, line in enumerate(lines, 1):
                        if re.search(pattern, line):
                            line_num = i
                            break
                if line_num is None:
                    return results  # 找不到行号则跳过
                results.append({
                    'rule_code': rule['rule_code'],
                    'rule_name': rule['rule_name'],
                    'rule_level': rule['rule_level'],
                    'file_path': file_path_normalized,
                    'line_number': line_num,
                    'violation_desc': f'{context_desc}使用禁止类 {imported_full}',
                    'solution': rule['solution'],
                    'match_type': '类简称使用',
                    'context': get_context(lines, line_num)
                })
            elif is_in_wildcard:
                # 通配符导入中包含禁止类
                for rule in short_class_map[type_name]:
                    if rule['package_name'] in wildcard_packages:
                        line_num = extract_position(node_for_position, lines)
                        # 如果AST节点没有位置信息，尝试通过正则定位
                        if line_num is None:
                            if 'new' in context_desc:
                                pattern = rf'\bnew\s+{re.escape(type_name)}\s*\('
                            else:
                                pattern = rf'\b{re.escape(type_name)}\b'
                            for i, line in enumerate(lines, 1):
                                if re.search(pattern, line):
                                    line_num = i
                                    break
                        if line_num is None:
                            continue  # 找不到行号则跳过
                        results.append({
                            'rule_code': rule['rule_code'],
                            'rule_name': rule['rule_name'],
                            'rule_level': rule['rule_level'],
                            'file_path': file_path_normalized,
                            'line_number': line_num,
                            'violation_desc': f'{context_desc}使用禁止类 {rule["full_class_name"]}（通过通配符导入）',
                            'solution': rule['solution'],
                            'match_type': '类简称使用',
                            'context': get_context(lines, line_num)
                        })
        
        return results
    
    # ========== 1. 检测import语句 ==========
    if tree.imports:
        for imp in tree.imports:
            if imp.path:
                line_num = extract_position(imp, lines)
                
                # 如果 AST 节点没有位置信息，通过正则表达式在源码中定位
                if line_num is None:
                    # 查找 import 语句的位置
                    import_pattern = rf'^\s*import\s+{re.escape(imp.path)}\s*;'
                    for i, line in enumerate(lines, 1):
                        if re.search(import_pattern, line):
                            line_num = i
                            break
                
                # 检查显式导入
                if not imp.wildcard and imp.path in full_class_map:
                    rule = full_class_map[imp.path]
                    violations.append({
                        'rule_code': rule['rule_code'],
                        'rule_name': rule['rule_name'],
                        'rule_level': rule['rule_level'],
                        'file_path': file_path_normalized,
                        'line_number': line_num or 1,
                        'violation_desc': f'导入禁止类 {imp.path}',
                        'solution': rule['solution'],
                        'match_type': 'import显式导入',
                        'context': get_context(lines, line_num) if line_num else ''
                    })
                
                # 检查静态导入
                if imp.static:
                    for full_name in full_class_map:
                        if imp.path.startswith(full_name):
                            rule = full_class_map[full_name]
                            violations.append({
                                'rule_code': rule['rule_code'],
                                'rule_name': rule['rule_name'],
                                'rule_level': rule['rule_level'],
                                'file_path': file_path_normalized,
                                'line_number': line_num or 1,
                                'violation_desc': f'静态导入禁止类 {full_name}',
                                'solution': rule['solution'],
                                'match_type': '静态导入',
                                'context': get_context(lines, line_num) if line_num else ''
                            })
                            break
                
                # 检查通配符导入
                if imp.wildcard:
                    package = imp.path.rstrip('.*')
                    for rule in rules:
                        if rule['package_name'] == package:
                            violations.append({
                                'rule_code': rule['rule_code'],
                                'rule_name': rule['rule_name'],
                                'rule_level': rule['rule_level'],
                                'file_path': file_path_normalized,
                                'line_number': line_num or 1,
                                'violation_desc': f'通配符导入可能包含禁止类 {rule["full_class_name"]}',
                                'solution': rule['solution'],
                                'match_type': '通配符导入',
                                'context': get_context(lines, line_num) if line_num else ''
                            })
    
    # ========== 2. 检测类声明（extends/implements）==========
    if tree.types:
        for type_decl in tree.types:
            line_num = extract_position(type_decl, lines)
            
            # 检查 extends
            if hasattr(type_decl, 'extends') and type_decl.extends:
                violations.extend(check_type_reference(
                    type_decl.extends, 
                    '类继承', 
                    type_decl
                ))
            
            # 检查 implements
            if hasattr(type_decl, 'implements') and type_decl.implements:
                for impl in type_decl.implements:
                    violations.extend(check_type_reference(
                        impl, 
                        '接口实现', 
                        type_decl
                    ))
    
    # ========== 3. 检测方法声明（返回值、参数、异常）==========
    def scan_methods(members, context=""):
        """扫描方法声明"""
        for member in members:
            if isinstance(member, javalang.tree.MethodDeclaration):
                line_num = extract_position(member, lines)
                
                # 返回值类型
                ret_type = getattr(member, 'return_type', None)
                if ret_type:
                    violations.extend(check_type_reference(
                        ret_type,
                        f'{context}方法返回值',
                        member
                    ))
                
                # 参数类型
                method_params = getattr(member, 'parameters', None)
                if method_params:
                    for param in method_params:
                        param_type = getattr(param, 'type', None)
                        if param_type:
                            violations.extend(check_type_reference(
                                param_type,
                                f'{context}方法参数',
                                member
                            ))
                
                # 异常声明
                method_throws = getattr(member, 'throws', None)
                if method_throws:
                    for throw_type in method_throws:
                        violations.extend(check_type_reference(
                            throw_type,
                            f'{context}方法异常声明',
                            member
                        ))
                
                # 方法体内的局部变量
                method_body = getattr(member, 'body', None)
                if method_body:
                    for stmt in method_body:
                        scan_statement(stmt, context)
            
            elif isinstance(member, javalang.tree.FieldDeclaration):
                # 字段声明
                field_type = getattr(member, 'type', None)
                if field_type:
                    violations.extend(check_type_reference(
                        field_type,
                        f'{context}字段声明',
                        member
                    ))
            
            elif isinstance(member, javalang.tree.ConstructorDeclaration):
                # 构造函数
                ctor_params = getattr(member, 'parameters', None)
                if ctor_params:
                    for param in ctor_params:
                        param_type = getattr(param, 'type', None)
                        if param_type:
                            violations.extend(check_type_reference(
                                param_type,
                                f'{context}构造函数参数',
                                member
                            ))
                
                ctor_body = getattr(member, 'body', None)
                if ctor_body:
                    for stmt in ctor_body:
                        scan_statement(stmt, context)
    
    def scan_statement(stmt, context=""):
        """扫描语句"""
        if stmt is None:
            return
        
        # 局部变量声明
        if isinstance(stmt, javalang.tree.LocalVariableDeclaration):
            local_type = getattr(stmt, 'type', None)
            if local_type:
                violations.extend(check_type_reference(
                    local_type,
                    f'{context}局部变量声明',
                    stmt
                ))
            # 检查局部变量的初始值表达式
            declarators = getattr(stmt, 'declarators', None)
            if declarators:
                for declarator in declarators:
                    initializer = getattr(declarator, 'initializer', None)
                    if initializer:
                        scan_expression(initializer, context)
        
        # 赋值语句中的 new 表达式
        elif isinstance(stmt, javalang.tree.StatementExpression):
            # javalang 0.13.0 兼容
            expr_val = getattr(stmt, 'expression', None) or getattr(stmt, 'expressionl', None)
            if expr_val:
                scan_expression(expr_val, context)
        
        # return 语句
        elif isinstance(stmt, javalang.tree.ReturnStatement):
            # javalang 0.13.0 兼容
            ret_expr = getattr(stmt, 'expression', None) or getattr(stmt, 'expressionl', None)
            if ret_expr:
                scan_expression(ret_expr, context)
        
        # if 语句
        elif isinstance(stmt, javalang.tree.IfStatement):
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
        
        # for 循环
        elif isinstance(stmt, javalang.tree.ForStatement):
            ctrl = getattr(stmt, 'control', None)
            body_stmt = getattr(stmt, 'body', None)
            if ctrl:
                inner_ctrl = getattr(ctrl, 'control', None)
                if inner_ctrl:
                    inner_ctrl_type = getattr(inner_ctrl, 'type', None)
                    if inner_ctrl_type:
                        violations.extend(check_type_reference(
                            inner_ctrl_type,
                            f'{context}for循环变量',
                            stmt
                        ))
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
        
        # while 循环
        elif isinstance(stmt, javalang.tree.WhileStatement):
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
        elif isinstance(stmt, javalang.tree.TryStatement):
            try_block = getattr(stmt, 'block', None)
            try_catches = getattr(stmt, 'catches', None)
            if try_block:
                for s in try_block:
                    scan_statement(s, context)
            if try_catches:
                for catch in try_catches:
                    catch_param = getattr(catch, 'parameter', None)
                    if catch_param and hasattr(catch_param, 'type'):
                        violations.extend(check_type_reference(
                            catch_param.type,
                            f'{context}catch异常类型',
                            catch
                        ))
                    catch_block = getattr(catch, 'block', None)
                    if catch_block:
                        for s in catch_block:
                            scan_statement(s, context)
        
        # 代码块
        elif isinstance(stmt, (list, tuple)):
            for s in stmt:
                scan_statement(s, context)
    
    def scan_expression(expr, context=""):
        """扫描表达式"""
        if expr is None:
            return
        
        # new 表达式: new ClassName()
        if isinstance(expr, javalang.tree.ClassCreator):
            creator_type = getattr(expr, 'type', None)
            if creator_type:
                violations.extend(check_type_reference(
                    creator_type,
                    f'{context}new对象实例化',
                    expr
                ))
            # 检查构造函数参数
            creator_args = getattr(expr, 'arguments', None)
            if creator_args:
                for arg in creator_args:
                    if isinstance(arg, javalang.tree.Expression):
                        scan_expression(arg, context)
        
        # 方法调用
        elif isinstance(expr, javalang.tree.MethodInvocation):
            qualifier = getattr(expr, 'qualifier', None)
            member = getattr(expr, 'member', None)
            if qualifier:
                # 检查 qualifier 是否是禁止类（显式导入）
                if qualifier in short_class_map:
                    imported_full = imported_classes.get(qualifier)
                    if imported_full and imported_full in full_class_map:
                        rule = full_class_map[imported_full]
                        line_num = extract_position(expr, lines)
                        violations.append({
                            'rule_code': rule['rule_code'],
                            'rule_name': rule['rule_name'],
                            'rule_level': rule['rule_level'],
                            'file_path': file_path_normalized,
                            'line_number': line_num or 1,
                            'violation_desc': f'{context}调用禁止类方法 {imported_full}.{member}',
                            'solution': rule['solution'],
                            'match_type': '类方法调用',
                            'context': get_context(lines, line_num) if line_num else ''
                        })
                    # 检查通配符导入
                    elif wildcard_packages:
                        for rule in short_class_map[qualifier]:
                            if rule['package_name'] in wildcard_packages:
                                line_num = extract_position(expr, lines)
                                violations.append({
                                    'rule_code': rule['rule_code'],
                                    'rule_name': rule['rule_name'],
                                    'rule_level': rule['rule_level'],
                                    'file_path': file_path_normalized,
                                    'line_number': line_num or 1,
                                    'violation_desc': f'{context}调用禁止类方法 {rule["full_class_name"]}.{member}（通过通配符导入）',
                                    'solution': rule['solution'],
                                    'match_type': '类方法调用（通配符导入）',
                                    'context': get_context(lines, line_num) if line_num else ''
                                })
                                break
            method_args = getattr(expr, 'arguments', None)
            if method_args:
                for arg in method_args:
                    scan_expression(arg, context)
        
        # 赋值表达式
        elif isinstance(expr, javalang.tree.Assignment):
            # javalang Assignment: expressionl 是左值，value 是右值
            # 需要扫描右值表达式（可能包含禁止类调用）
            right_value = getattr(expr, 'value', None)
            if right_value:
                scan_expression(right_value, context)
        
        # 二元运算
        elif isinstance(expr, javalang.tree.BinaryOperation):
            # javalang 0.13.0 使用 operandl/operandr
            left = getattr(expr, 'operandl', None) or getattr(expr, 'operandl', None)
            right = getattr(expr, 'operandr', None) or getattr(expr, 'operandr', None)
            if left:
                scan_expression(left, context)
            if right:
                scan_expression(right, context)
        
        # 类型转换: (ClassName) obj
        elif isinstance(expr, javalang.tree.Cast):
            cast_type = getattr(expr, 'type', None)
            if cast_type:
                violations.extend(check_type_reference(
                    cast_type,
                    f'{context}类型转换',
                    expr
                ))
            # 扫描类型转换的表达式（可能包含禁止类调用）
            cast_expr = getattr(expr, 'expression', None)
            if cast_expr:
                scan_expression(cast_expr, context)
        
        # 条件表达式
        elif isinstance(expr, javalang.tree.TernaryExpression):
            # 兼容不同版本的属性名
            condition = getattr(expr, 'condition', None)
            if_true = getattr(expr, 'if_true', None) or getattr(expr, 'true_expression', None)
            if_false = getattr(expr, 'if_false', None) or getattr(expr, 'false_expression', None)
            if condition:
                scan_expression(condition, context)
            if if_true:
                scan_expression(if_true, context)
            if if_false:
                scan_expression(if_false, context)
        
        # 数组创建
        elif isinstance(expr, javalang.tree.ArrayCreator):
            array_type = getattr(expr, 'type', None)
            if array_type:
                violations.extend(check_type_reference(
                    array_type,
                    f'{context}数组创建',
                    expr
                ))
    
    # 扫描类成员
    if tree.types:
        for type_decl in tree.types:
            class_name = type_decl.name
            if hasattr(type_decl, 'body') and type_decl.body:
                scan_methods(type_decl.body, context=f'类{class_name}中')
    
    # ========== 4. 检测注解使用 ==========
    def scan_annotations(annotations, context=""):
        """扫描注解"""
        if annotations:
            for ann in annotations:
                if hasattr(ann, 'name') and ann.name:
                    ann_name = ann.name
                    if ann_name in short_class_map:
                        imported_full = imported_classes.get(ann_name)
                        if imported_full and imported_full in full_class_map:
                            rule = full_class_map[imported_full]
                            line_num = extract_position(ann, lines)
                            violations.append({
                                'rule_code': rule['rule_code'],
                                'rule_name': rule['rule_name'],
                                'rule_level': rule['rule_level'],
                                'file_path': file_path_normalized,
                                'line_number': line_num or 1,
                                'violation_desc': f'{context}使用禁止类注解 @{ann_name}',
                                'solution': rule['solution'],
                                'match_type': '注解使用',
                                'context': get_context(lines, line_num) if line_num else ''
                            })
    
    # 扫描类上的注解
    if tree.types:
        for type_decl in tree.types:
            if hasattr(type_decl, 'annotations'):
                scan_annotations(type_decl.annotations, f'类{type_decl.name}')
    
    # 注：已移除字符串字面量检测（find_string_literals），原因：
    # 1. 反射调用场景少见
    # 2. 字符串中类名误报多（日志、注释等）
    # 3. 递归遍历AST性能差
    
    if DEBUG_LOG:
        file_total_time = time.time() - file_start_time
        if file_total_time > 0.5:  # 只打印耗时超过0.5秒的文件
            print(f"    [文件总耗时] {file_total_time:.3f}秒, 发现{len(violations)}个违规")
    
    # 后处理：恢复预处理时替换的占位符
    if preprocessor:
        violations = preprocessor.postprocess_violations(violations)
    
    # 全局扫描：直接遍历所有 ClassCreator 节点
    # 这样可以捕获 Lambda 表达式、匿名类等结构内的类实例化
    try:
        for path, node in tree.filter(javalang.tree.ClassCreator):
            # 获取实例化的类名
            class_name = None
            if hasattr(node, 'type') and node.type:
                if hasattr(node.type, 'name'):
                    class_name = node.type.name
            
            if class_name and class_name in short_class_map:
                for rule in short_class_map[class_name]:
                    # 验证import是否匹配
                    imported_full = imported_classes.get(class_name)
                    is_wildcard_match = rule['package_name'] in wildcard_packages
                    is_java_lang_class = rule['package_name'] == 'java.lang'
                    
                    if imported_full == rule['full_class_name'] or is_wildcard_match or is_java_lang_class:
                        # 检查是否已报告（避免重复）
                        line_num = extract_position(node, lines)
                        
                        # 如果 AST 节点没有位置信息，通过正则表达式在源码中定位
                        if line_num is None:
                            # 使用正则表达式查找 new ClassName( 的位置
                            pattern = rf'\bnew\s+{re.escape(class_name)}\s*\('
                            for i, line in enumerate(lines, 1):
                                if re.search(pattern, line):
                                    line_num = i
                                    break
                        
                        # 如果仍然找不到行号，跳过该违规（避免误报）
                        if line_num is None:
                            continue
                        
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
                                'line_number': line_num,
                                'violation_desc': f'实例化禁止类 {rule["full_class_name"]}',
                                'solution': rule['solution'],
                                'match_type': '全局扫描',
                                'context': get_context(lines, line_num)
                            })
    except Exception as e:
        pass  # 忽略遍历错误
    
    # 全局扫描：检测构造器引用（MethodReference with method = 'new'）
    # 构造器引用语法: ClassName::new
    # 例如: Supplier<List> supplier = ArrayList::new;
    try:
        for path, node in tree.filter(javalang.tree.MethodReference):
            # 获取方法引用的类名和方法名
            expr = getattr(node, 'expression', None)
            method_ref = getattr(node, 'method', None)
            line_num = extract_position(node, lines)
            
            # expression 通常是 MemberReference，其 member 属性是类名
            class_name = None
            
            if expr and hasattr(expr, 'member'):
                class_name = expr.member
                # 获取 expression 的行号（更准确）
                if hasattr(expr, 'position') and expr.position:
                    line_num = expr.position[0]
            
            # method 通常是 MemberReference，其 member 属性是方法名
            method_name = None
            if method_ref and hasattr(method_ref, 'member'):
                method_name = method_ref.member
            
            # 只检测构造器引用（method = 'new'）
            if class_name and method_name == 'new':
                if class_name in short_class_map:
                    for rule in short_class_map[class_name]:
                        # 验证import是否匹配
                        imported_full = imported_classes.get(class_name)
                        is_wildcard_match = rule['package_name'] in wildcard_packages
                        is_java_lang_class = rule['package_name'] == 'java.lang'
                        
                        if imported_full == rule['full_class_name'] or is_wildcard_match or is_java_lang_class:
                            # 检查是否已报告（避免重复）
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
                                    'violation_desc': f'构造器引用禁止类 {rule["full_class_name"]}::new',
                                    'solution': rule['solution'],
                                    'match_type': '构造器引用',
                                    'context': get_context(lines, line_num) if line_num else ''
                                })
    except Exception as e:
        pass  # 忽略遍历错误
    
    return violations


def scan_project(project_root=None, rule_file=None):
    """
    扫描项目中的Java文件，返回违规列表
    
    参数:
        project_root: 项目根目录，默认为当前项目
        rule_file: 规则文件路径，默认为 skill-local references 规则文件
    
    返回:
        list: 违规对象列表
    """
    scan_start_time = time.time()
    root = Path(project_root) if project_root else PROJECT_ROOT
    rules_path = Path(rule_file) if rule_file else RULE_FILE
    
    # 1. 解析规则文件
    if DEBUG_LOG:
        print("[步骤1] 解析规则文件...")
    rules = parse_rule_file(rules_path)
    if DEBUG_LOG:
        print(f"  加载规则数量: {len(rules)}")
    
    # 2. 查找Java文件
    if DEBUG_LOG:
        print("[步骤2] 查找Java文件...")
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
        
        # 每10个文件打印一次进度
        if DEBUG_LOG and (idx + 1) % 10 == 0:
            elapsed = time.time() - scan_start_time
            print(f"  [进度] {idx + 1}/{len(java_files)} 文件, 耗时 {elapsed:.1f}秒")
    
    if DEBUG_LOG:
        total_time = time.time() - scan_start_time
        print(f"\n[总耗时] {total_time:.2f}秒, 平均 {total_time/len(java_files):.3f}秒/文件")
    
    return all_violations


def merge_violations(violations):
    """
    合并同一文件同一规则同一行号的多个违规
    按 (file_path, rule_code, line_number) 合并，确保每行只记录一次
    """
    merged = {}
    for v in violations:
        key = (v['file_path'], v['rule_code'], v['line_number'])
        if key not in merged:
            merged[key] = {
                'rule_code': v['rule_code'],
                'rule_name': v['rule_name'],
                'rule_level': v['rule_level'],
                'file_path': v['file_path'],
                'line_number': v['line_number'],
                'violation_desc': v['violation_desc'],
                'solution': v['solution'],
                'match_type': v.get('match_type', '')
            }
    
    # 转换为列表
    result = list(merged.values())
    
    # 按 file_path, rule_code, line_number 排序
    result.sort(key=lambda x: (x['file_path'], x['rule_code'], x['line_number']))
    
    return result


def main():
    """
    主函数：执行扫描并输出结果
    """
    # 检查是否有 --file 参数
    specified_files = []
    if '--file' in sys.argv:
        file_idx = sys.argv.index('--file')
        # 获取 --file 后面的所有参数（直到遇到下一个 -- 开头的参数或结束）
        for i in range(file_idx + 1, len(sys.argv)):
            if sys.argv[i].startswith('--'):
                break
            specified_files.append(sys.argv[i])
    
    print("=" * 60)
    print("Java代码类检测工具（语法解析版）")
    print("=" * 60)
    
    # 执行扫描
    if specified_files:
        # 扫描指定文件
        violations = scan_specified_files(specified_files)
    else:
        # 扫描整个项目
        violations = scan_project()
    
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
    output_result_file = SCRIPT_DIR.parent / "result" / "scan_java_class_result.json"
    try:
        # 确保目录存在
        output_result_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_result_file, 'w', encoding='utf-8') as f:
            json.dump(violations, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到: {output_result_file}")
    except Exception as e:
        print(f"\n[警告] 保存结果文件失败: {e}")
    
    return violations


def scan_specified_files(file_paths):
    """
    扫描指定的文件列表
    
    参数:
        file_paths: 文件路径列表（可以是绝对路径或相对路径）
    
    返回:
        list: 违规对象列表
    """
    scan_start_time = time.time()
    
    # 1. 解析规则文件
    if DEBUG_LOG:
        print("[步骤1] 解析规则文件...")
    rules = parse_rule_file(RULE_FILE)
    if DEBUG_LOG:
        print(f"  加载规则数量: {len(rules)}")
    
    # 2. 过滤出 Java 文件
    java_files = []
    for fp in file_paths:
        # 处理路径
        if os.path.isabs(fp):
            # 绝对路径，检查是否在项目内
            if fp.startswith(str(PROJECT_ROOT)):
                java_files.append(fp)
            else:
                if DEBUG_LOG:
                    print(f"  [跳过] 文件不在项目目录内: {fp}")
        else:
            # 相对路径，转换为绝对路径
            abs_path = os.path.join(PROJECT_ROOT, fp)
            if os.path.exists(abs_path):
                java_files.append(abs_path)
            else:
                if DEBUG_LOG:
                    print(f"  [跳过] 文件不存在: {fp}")
    
    # 只保留 .java 文件
    java_files = [f for f in java_files if f.endswith('.java')]
    
    if DEBUG_LOG:
        print(f"[步骤2] 过滤Java文件...")
        print(f"  待扫描文件数量: {len(java_files)}")
    
    # 3. 扫描文件
    if DEBUG_LOG:
        print("[步骤3] 扫描Java文件...")
    all_violations = []
    for idx, java_file in enumerate(java_files):
        violations = scan_java_file_with_ast(java_file, rules)
        all_violations.extend(violations)
    
    if DEBUG_LOG:
        total_time = time.time() - scan_start_time
        print(f"\n[总耗时] {total_time:.2f}秒")
    
    return all_violations


if __name__ == '__main__':
    main()
