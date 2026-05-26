# -*- coding: utf-8 -*-
"""
Java代码关键字检测工具
使用正则表达式检测代码中的禁止关键字
功能：检测代码中是否包含特定的关键字字符串
"""

import os
import re
import sys
import json
import time
from pathlib import Path

# 是否开启调试日志
DEBUG_LOG = False

# 技能根目录（当前脚本所在目录）
SCRIPT_DIR = Path(__file__).parent

# 项目根目录（工作空间根目录）
# 脚本位于: <skill-root>/scripts/scan/
# 默认项目根目录按当前工作目录或显式参数传入
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent

# 规则文件路径（相对于脚本目录）
RULE_FILE = SCRIPT_DIR.parent / "references" / "sonar_cve_keyword.md"


def parse_keyword_rule_file(rule_file):
    """
    解析关键字规则文件
    规则格式：keyword = xxx
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
                
                # 解析 keyword = xxx
                keyword_match = re.search(r'keyword\s*=\s*(.+?)(?:\s*$|\s*\|)', rule_config)
                if keyword_match:
                    keyword = keyword_match.group(1).strip()
                    rules.append({
                        'rule_code': rule_code,
                        'rule_name': rule_name,
                        'rule_level': rule_level,
                        'keyword': keyword,
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
    if line_number is None or line_number < 1:
        return "无法获取行号"
    
    start = max(0, line_number - context_lines - 1)
    end = min(len(lines), line_number + context_lines)
    
    context_parts = []
    for i in range(start, end):
        prefix = ">>> " if i == line_number - 1 else "    "
        context_parts.append(f"{prefix}{i + 1}: {lines[i]}")
    
    return '\n'.join(context_parts)


def remove_comments(content):
    """
    移除注释内容，保留字符串字面量
    返回处理后的内容（注释替换为空格）
    注意：保留 /*dialect*/ 标记，因为它是SQL方言标识而非注释
    """
    # 先保护 /*dialect*/ 标记，用特殊占位符替换
    protected_markers = []
    DIALECT_MARKER = '/*dialect*/'
    PLACEHOLDER = '\x00DIALECT\x00'
    
    temp_content = content
    i = 0
    while True:
        idx = temp_content.find(DIALECT_MARKER, i)
        if idx == -1:
            break
        protected_markers.append((idx, DIALECT_MARKER))
        temp_content = temp_content[:idx] + PLACEHOLDER + temp_content[idx + len(DIALECT_MARKER):]
        i = idx + len(PLACEHOLDER)
    
    result = []
    i = 0
    n = len(temp_content)
    
    while i < n:
        # 检测单行注释 //
        if i + 1 < n and temp_content[i:i+2] == '//':
            # 跳过到行尾
            while i < n and temp_content[i] != '\n':
                result.append(' ')
                i += 1
            if i < n:
                result.append('\n')
                i += 1
        # 检测多行注释 /* */
        elif i + 1 < n and temp_content[i:i+2] == '/*':
            result.append(' ')
            result.append(' ')
            i += 2
            while i + 1 < n and temp_content[i:i+2] != '*/':
                if temp_content[i] == '\n':
                    result.append('\n')
                else:
                    result.append(' ')
                i += 1
            if i + 1 < n:
                result.append(' ')
                result.append(' ')
                i += 2
        else:
            result.append(temp_content[i])
            i += 1
    
    # 恢复保护的标记
    result_content = ''.join(result)
    result_content = result_content.replace(PLACEHOLDER, DIALECT_MARKER)
    
    return result_content


def scan_java_file(file_path, rules):
    """
    使用正则表达式扫描Java文件，检测关键字
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
        print(f"  [扫描] {file_path_normalized} ({len(lines)}行)")
    
    # 移除注释，避免误报
    clean_content = remove_comments(content)
    clean_lines = clean_content.split('\n')
    
    # 对每个规则进行检测
    for rule in rules:
        keyword = rule['keyword']
        
        # 构建正则表达式，忽略大小写
        # 对关键字中的特殊字符进行转义
        escaped_keyword = re.escape(keyword)
        # 将转义后的空格替换为 \s+（匹配一个或多个空格）
        # 这样既能保证有空格，又忽略空格数量
        escaped_keyword = escaped_keyword.replace(r'\ ', r'\s+')
        pattern = re.compile(escaped_keyword, re.IGNORECASE)
        
        # 在清理后的代码中搜索
        for i, line in enumerate(clean_lines, 1):
            matches = pattern.finditer(line)
            for match in matches:
                # 再次确认原始行中也存在（避免误报）
                original_line = lines[i - 1] if i <= len(lines) else ""
                if pattern.search(original_line):
                    violations.append({
                        'rule_code': rule['rule_code'],
                        'rule_name': rule['rule_name'],
                        'rule_level': rule['rule_level'],
                        'file_path': file_path_normalized,
                        'line_number': i,
                        'violation_desc': f'使用了关键字 {keyword}',
                        'solution': rule['solution'],
                        'match_type': '关键字检测',
                        'context': get_context(lines, i)
                    })
                    break  # 同一行只报告一次
    
    if DEBUG_LOG:
        file_total_time = time.time() - file_start_time
        if file_total_time > 0.5:
            print(f"    [文件总耗时] {file_total_time:.3f}秒, 发现{len(violations)}个违规")
    
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
    rules = parse_keyword_rule_file(rules_path)
    if DEBUG_LOG:
        print(f"  加载规则数量: {len(rules)}")

    # 打印需要检测的关键字
    if DEBUG_LOG and rules:
        print("\n  [检测关键字列表]")
        for rule in rules:
            print(f"    {rule['keyword']}")
        print()
    
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
        violations = scan_java_file(java_file, rules)
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
    rules = parse_keyword_rule_file(RULE_FILE)
    if DEBUG_LOG:
        print(f"  加载规则数量: {len(rules)}")

    # 打印需要检测的关键字
    if DEBUG_LOG and rules:
        print("\n  [检测关键字列表]")
        for rule in rules:
            print(f"    {rule['keyword']}")
        print()
    
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
        violations = scan_java_file(java_file, rules)
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
    print("Java代码关键字检测工具")
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
    output_result_file = SCRIPT_DIR.parent / "result" / "scan_java_keyword_result.json"
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
