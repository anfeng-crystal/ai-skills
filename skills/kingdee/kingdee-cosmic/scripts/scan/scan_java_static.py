# -*- coding: utf-8 -*-
"""
Java代码静态集合变量检测工具（语法解析版）
使用 javalang 语法解析器检测禁止的静态集合变量
功能：检测静态字段声明中使用了禁止的集合类型
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
RULE_FILE = SCRIPT_DIR.parent / "references" / "sonar_cve_static.md"


def parse_static_rule_file(rule_file):
    """
    解析静态集合变量规则文件
    规则格式：static variable = java.util.HashMap
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
                
                # 解析 static variable = xxx
                var_match = re.search(r'static\s+variable\s*=\s*([^\s|]+)', rule_config)
                if var_match:
                    full_class_name = var_match.group(1)
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
    
    # 2. 对于 FieldDeclaration，尝试从 type 属性获取
    if hasattr(node, 'type') and node.type:
        if hasattr(node.type, 'position') and node.type.position:
            return node.type.position[0]
        # 尝试从 type.name 推断
        if hasattr(node.type, 'name') and lines:
            type_name = node.type.name
            pattern = rf'\b{re.escape(type_name)}\b'
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    return i
    
    return None


def scan_java_file_with_ast(file_path, rules):
    """
    使用javalang语法解析器扫描Java文件，检测静态集合变量
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
    # key: class_short_name -> [rules]
    class_rule_map = {}
    for rule in rules:
        key = rule['class_short_name']
        if key not in class_rule_map:
            class_rule_map[key] = []
        class_rule_map[key].append(rule)
    
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
    
    def check_static_field(field_decl, context=""):
        """
        检查字段声明是否是禁止的静态集合变量
        """
        # 获取修饰符
        modifiers = getattr(field_decl, 'modifiers', None)
        if not modifiers:
            return
        
        # 必须是静态字段
        if 'static' not in modifiers:
            return
        
        # 获取字段类型
        field_type = getattr(field_decl, 'type', None)
        if not field_type:
            return
        
        # 获取类型名称
        type_name = None
        if hasattr(field_type, 'name'):
            type_name = field_type.name
        elif isinstance(field_type, str):
            type_name = field_type
        
        if not type_name:
            return
        
        # 移除泛型部分（如 Map<String,String> -> Map）
        base_type_name = type_name.split('<')[0] if '<' in type_name else type_name
        
        # 检查是否匹配规则
        if base_type_name in class_rule_map:
            for rule in class_rule_map[base_type_name]:
                # 验证类是否匹配（通过import确认）
                imported_full = imported_classes.get(base_type_name)
                is_wildcard_match = rule['package_name'] in wildcard_packages
                
                if imported_full == rule['full_class_name'] or is_wildcard_match:
                    line_num = extract_position(field_decl)
                    violations.append({
                        'rule_code': rule['rule_code'],
                        'rule_name': rule['rule_name'],
                        'rule_level': rule['rule_level'],
                        'file_path': file_path_normalized,
                        'line_number': line_num or 1,
                        'violation_desc': f'{context}使用了静态集合变量 {rule["full_class_name"]}',
                        'solution': rule['solution'],
                        'match_type': '静态集合变量',
                        'context': get_context(lines, line_num) if line_num else ''
                    })
    
    def scan_class_members(members, context=""):
        """扫描类成员"""
        for member in members:
            # 字段声明（兼容 javalang 和 javaparser_adapter）
            member_type_name = type(member).__name__
            if 'FieldDeclaration' in member_type_name:
                check_static_field(member, context)
            
            # 内部类
            elif 'ClassDeclaration' in member_type_name:
                inner_body = getattr(member, 'body', None)
                if inner_body:
                    inner_name = getattr(member, 'name', 'unknown')
                    scan_class_members(inner_body, f"{context}内部类{inner_name}中")
            
            # 方法声明（检查方法内的局部类）
            elif 'MethodDeclaration' in member_type_name:
                method_body = getattr(member, 'body', None)
                if method_body:
                    for stmt in method_body:
                        # 检查方法内的局部类
                        stmt_type_name = type(stmt).__name__
                        if 'ClassDeclaration' in stmt_type_name:
                            local_body = getattr(stmt, 'body', None)
                            if local_body:
                                local_name = getattr(stmt, 'name', 'unknown')
                                scan_class_members(local_body, f"{context}局部类{local_name}中")
    
    # 扫描类
    if tree.types:
        for type_decl in tree.types:
            class_name = getattr(type_decl, 'name', 'unknown')
            body = getattr(type_decl, 'body', None)
            if body:
                scan_class_members(body, f"类{class_name}中")
    
    if DEBUG_LOG:
        file_total_time = time.time() - file_start_time
        if file_total_time > 0.5:
            print(f"    [文件总耗时] {file_total_time:.3f}秒, 发现{len(violations)}个违规")
    
    # 后处理：恢复预处理时替换的占位符
    if preprocessor:
        violations = preprocessor.postprocess_violations(violations)
    
    return violations


def scan_project(project_root=None, rule_file=None):
    """
    扫描项目中的Java文件，返回违规列表
    """
    scan_start_time = time.time()
    root = Path(project_root) if project_root else PROJECT_ROOT
    rules_path = Path(rule_file) if rule_file else RULE_FILE
    
    # 1. 解析规则文件
    if DEBUG_LOG:
        print("[步骤1] 解析规则文件...")
    rules = parse_static_rule_file(rules_path)
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
        
        if DEBUG_LOG and (idx + 1) % 10 == 0:
            elapsed = time.time() - scan_start_time
            print(f"  [进度] {idx + 1}/{len(java_files)} 文件, 耗时 {elapsed:.1f}秒")
    
    if DEBUG_LOG:
        total_time = time.time() - scan_start_time
        print(f"\n[总耗时] {total_time:.2f}秒, 平均 {total_time/len(java_files):.3f}秒/文件")
    
    return all_violations


def dedup_violations(violations):
    """去重：仅当 file_path + rule_code + line_number 完全相同时去重"""
    seen = set()
    result = []
    
    for v in violations:
        # 使用 file_path + rule_code + line_number 作为去重键
        key = (v.get('file_path', ''), v.get('rule_code', ''), v.get('line_number', 0))
        if key not in seen:
            seen.add(key)
            result.append(v)
    
    # 按 file_path, rule_code, line_number 排序
    result.sort(key=lambda x: (x.get('file_path', ''), x.get('rule_code', ''), x.get('line_number', 0)))
    return result


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
    rules = parse_static_rule_file(RULE_FILE)
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


def main():
    """主函数"""
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
    print("Java代码静态集合变量检测工具（语法解析版）")
    print("=" * 60)
    
    # 执行扫描
    if specified_files:
        # 扫描指定文件
        violations = scan_specified_files(specified_files)
    else:
        # 扫描整个项目
        violations = scan_project()
    
    # 去重：仅当 file_path + rule_code + line_number 完全相同时去重
    violations = dedup_violations(violations)
    
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
    output_result_file = SCRIPT_DIR.parent / "result" / "scan_java_static_result.json"
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
