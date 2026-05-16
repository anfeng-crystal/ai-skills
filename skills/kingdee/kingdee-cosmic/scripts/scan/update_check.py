# -*- coding: utf-8 -*-
"""
技能更新清理工具
功能：
1. 检查是否存在 references 目录，如存在则删除历史 resource 目录
2. 删除 README.md 文件（如存在）
3. 删除 requirements.txt 文件（如存在）
4. 删除 test.txt 文件（如存在）
"""

import os
import shutil
from pathlib import Path

# 脚本所在目录
SCRIPT_DIR = Path(__file__).parent

# 技能根目录（脚本父目录）
SKILL_ROOT = SCRIPT_DIR.parent


def clean_legacy_files():
    """
    清理历史遗留文件和目录
    """
    cleaned_items = []
    
    # 1. 检查 references 目录是否存在，如存在则删除历史 resource 目录
    references_dir = SKILL_ROOT / "references"
    resource_dir = SKILL_ROOT / "resource"
    
    if references_dir.exists():
        if resource_dir.exists():
            try:
                shutil.rmtree(resource_dir)
                cleaned_items.append(f"已删除历史目录: {resource_dir}")
            except Exception as e:
                cleaned_items.append(f"删除目录失败 {resource_dir}: {e}")
    
    # 2. 删除 README.md 文件（如存在）
    readme_file = SKILL_ROOT / "README.md"
    if readme_file.exists():
        try:
            readme_file.unlink()
            cleaned_items.append(f"已删除文件: {readme_file}")
        except Exception as e:
            cleaned_items.append(f"删除文件失败 {readme_file}: {e}")
    
    # 3. 删除 requirements.txt 文件（如存在）
    requirements_file = SKILL_ROOT / "requirements.txt"
    if requirements_file.exists():
        try:
            requirements_file.unlink()
            cleaned_items.append(f"已删除文件: {requirements_file}")
        except Exception as e:
            cleaned_items.append(f"删除文件失败 {requirements_file}: {e}")
    
    # 4. 删除 test.txt 文件（如存在）
    test_file = SKILL_ROOT / "test.txt"
    if test_file.exists():
        try:
            test_file.unlink()
            cleaned_items.append(f"已删除文件: {test_file}")
        except Exception as e:
            cleaned_items.append(f"删除文件失败 {test_file}: {e}")
    
    return cleaned_items


def main():
    """
    主函数
    """
    print("[信息] 开始执行技能更新清理检查...")
    print(f"[信息] 技能根目录: {SKILL_ROOT}")
    
    # 执行清理
    cleaned_items = clean_legacy_files()
    
    if cleaned_items:
        print("[信息] 清理完成:")
        for item in cleaned_items:
            print(f"  - {item}")
    else:
        print("[信息] 无需清理，未发现历史遗留文件")
    
    print("[信息] 更新清理检查完成")
    return 0


if __name__ == '__main__':
    exit(main())
