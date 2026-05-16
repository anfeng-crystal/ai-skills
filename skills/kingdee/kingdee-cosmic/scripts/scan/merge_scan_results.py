# -*- coding: utf-8 -*-
"""
Java代码扫描结果合并工具
合并6个扫描脚本的输出结果，按 rule_code + file_path 进行合并
"""

import json
import os
import sys
from pathlib import Path
from collections import defaultdict

# 技能根目录（当前脚本所在目录）
SCRIPT_DIR = Path(__file__).parent

# 项目根目录（相对于脚本位置的固定路径）
# 脚本位于: scripts/ 目录，项目根目录是脚本的父目录的父目录
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# 结果文件路径（相对于脚本目录）
RESULT_DIR = SCRIPT_DIR.parent / "result"

# 6个扫描脚本的结果文件
SCAN_RESULT_FILES = [
    "scan_java_class_result.json",
    "scan_java_keyword_result.json",
    "scan_java_method_result.json",
    "scan_java_static_result.json",
    "scan_java_loop_method_result.json",
    "scan_java_loop_class_result.json"
]


def load_json_result(file_path: Path) -> list:
    """加载JSON结果文件"""
    if not file_path.exists():
        print(f"  [警告] 结果文件不存在: {file_path}")
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                print(f"  [警告] 结果文件格式错误（应为列表）: {file_path}")
                return []
    except json.JSONDecodeError as e:
        print(f"  [警告] JSON解析错误: {file_path} - {e}")
        return []
    except Exception as e:
        print(f"  [警告] 读取文件失败: {file_path} - {e}")
        return []


def merge_violations(violations: list) -> list:
    """
    合并违规结果
    按 rule_code + file_path 进行合并，相同规则的多次命中合并为一条，count 统计数量
    行号合并显示，去掉 context 属性
    """
    # 使用字典进行分组，key 为 (rule_code, file_path)
    merged_map = {}
    
    for v in violations:
        rule_code = v.get('rule_code', '')
        file_path = v.get('file_path', '')
        line_number = v.get('line_number', 0)
        
        if not rule_code or not file_path:
            continue
        
        key = (rule_code, file_path)
        
        if key not in merged_map:
            # 首次出现，创建新记录（不包含 context）
            merged_map[key] = {
                'rule_code': rule_code,
                'rule_name': v.get('rule_name', ''),
                'rule_level': v.get('rule_level', ''),
                'file_path': file_path,
                'line_number': str(line_number) if line_number else '',
                'violation_desc': v.get('violation_desc', ''),
                'solution': v.get('solution', ''),
                'match_type': v.get('match_type', ''),
                'count': 1
            }
        else:
            # 已存在，合并行号并增加计数
            existing = merged_map[key]
            existing['count'] += 1
            # 行号合并显示
            if line_number and str(line_number) not in existing['line_number']:
                if existing['line_number']:
                    existing['line_number'] += f",{line_number}"
                else:
                    existing['line_number'] = str(line_number)
    
    # 转换为列表
    result = list(merged_map.values())
    
    # 按 rule_code, file_path, line_number 排序
    result.sort(key=lambda x: (x['rule_code'], x['file_path'], x['line_number']))
    
    return result


def main():
    """主函数"""
    print("=" * 60)
    print("Java代码扫描结果合并工具")
    print("=" * 60)
    
    # 确保结果目录存在
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 收集所有扫描结果
    all_violations = []
    
    print("\n[步骤1] 加载各扫描脚本结果...")
    for result_file in SCAN_RESULT_FILES:
        file_path = RESULT_DIR / result_file
        print(f"  加载: {result_file}")
        violations = load_json_result(file_path)
        print(f"    记录数: {len(violations)}")
        all_violations.extend(violations)
    
    print(f"\n  总记录数: {len(all_violations)}")
    
    # 合并结果
    print("\n[步骤2] 合并结果...")
    merged_result = merge_violations(all_violations)
    print(f"  合并后记录数: {len(merged_result)}")
    
    # 统计信息
    violation_files = set(v['file_path'] for v in merged_result)
    level_counts = {'严重': 0, '高危': 0, '中危': 0, '低危': 0}
    for v in merged_result:
        level = v.get('rule_level', '')
        if level in level_counts:
            level_counts[level] += v.get('count', 0)
    
    print(f"\n[步骤3] 统计信息...")
    print(f"  违规文件数: {len(violation_files)}")
    print(f"  合并后条目数: {len(merged_result)}")
    print(f"  严重: {level_counts['严重']}, 高危: {level_counts['高危']}, 中危: {level_counts['中危']}, 低危: {level_counts['低危']}")
    
    # 保存合并结果
    output_file = RESULT_DIR / "scan_java_result.json"
    print(f"\n[步骤4] 保存合并结果...")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(merged_result, f, ensure_ascii=False, indent=2)
        print(f"  结果已保存到: {output_file}")
    except Exception as e:
        print(f"  [错误] 保存结果失败: {e}")
        return 1
    
    print("\n" + "=" * 60)
    print("合并完成!")
    print("=" * 60)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
