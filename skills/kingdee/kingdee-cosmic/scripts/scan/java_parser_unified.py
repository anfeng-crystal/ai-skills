# -*- coding: utf-8 -*-
"""
统一 Java 解析模块
提供渐进式解析策略：
1. 首先尝试 javalang（快速，纯 Python）
2. 如果失败，尝试预处理（处理 .class 字面量等）
3. 如果仍失败，尝试 JavaParser（通过 JPype，更健壮）

兼容层设计：对外提供与 javalang 类似的 API
"""

import os
import sys
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

# 技能根目录（当前脚本所在目录）
SCRIPT_DIR = Path(__file__).parent

# 项目根目录（工作空间根目录）
# 脚本位于: <skill-root>/scripts/scan/
# 默认项目根目录按当前工作目录或显式参数传入
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent

# 是否启用调试日志
DEBUG_LOG = False

# ==================== 预处理器 ====================

class JavaCodePreprocessor:
    """Java代码预处理器 - 处理 javalang 已知问题"""
    
    def __init__(self):
        self.replacements = []
    
    def preprocess(self, content: str) -> str:
        """预处理 Java 代码"""
        self.replacements = []
        processed = content
        
        # 1. 处理类字面量 (如 Map.class, String.class)
        processed = self._handle_class_literals(processed)
        
        # 2. 处理非标准 for 循环语法 (如 for (Type var : var = expr))
        processed = self._handle_nonstandard_for_loop(processed)
        
        return processed
    
    def _handle_class_literals(self, content: str) -> str:
        """处理类字面量 .class"""
        pattern = r'(?<!@)\b(\w+)\s*\.\s*class\b(?!\s*\w)'
        
        def replace_match(match):
            class_name = match.group(1)
            placeholder = f'{class_name}__CLASS_LITERAL__'
            self.replacements.append({
                'type': 'class_literal',
                'original': match.group(0),
                'placeholder': placeholder,
                'class_name': class_name,
            })
            return placeholder
        
        return re.sub(pattern, replace_match, content)
    
    def _handle_nonstandard_for_loop(self, content: str) -> str:
        """
        处理非标准 for 循环语法
        将 for (Type var : varName = expression) { 转换为标准语法
        原代码：for (DynamicObject task : taskObjects = expression) { body }
        新代码：for (Type var : expression) { body }
        
        策略：直接移除赋值变量，只保留表达式部分
        这样 javalang 可以正确解析为增强 for 循环
        """
        # 使用更可靠的方法：找到 for 循环的开始和结束位置
        result = content
        
        # 匹配 for (Type var : varName = 
        pattern_start = r'for\s*\(\s*(\w+(?:<[^>]+>)?(?:\[\])*)\s+(\w+)\s*:\s*(\w+)\s*=\s*'
        
        for match in re.finditer(pattern_start, content):
            type_decl = match.group(1)  # 类型声明
            var_name = match.group(2)   # 循环变量名
            assign_var = match.group(3) # 赋值变量名（丢弃）
            
            # 从等号后开始，找到匹配的表达式（处理嵌套括号）
            start_pos = match.end()
            paren_count = 0
            end_pos = start_pos
            
            for i, char in enumerate(content[start_pos:]):
                if char == '(':
                    paren_count += 1
                elif char == ')':
                    if paren_count == 0:
                        # 找到 for 循环的结束括号
                        end_pos = start_pos + i
                        break
                    paren_count -= 1
            
            # 提取表达式
            expression = content[start_pos:end_pos].strip()
            
            # 构建新的 for 循环
            original = content[match.start():end_pos+1]
            new_code = f'for ({type_decl} {var_name} : {expression})'
            
            # 记录替换信息
            self.replacements.append({
                'type': 'for_loop_simplify',
                'original': original,
                'placeholder': new_code,
                'type_decl': type_decl,
                'var_name': var_name,
                'assign_var': assign_var,
                'expression': expression,
                'line_offset': 0,
            })
            
            if DEBUG_LOG:
                print(f"    [预处理] 简化 for 循环语法: for ({type_decl} {var_name} : {expression[:50]}...)")
            
            # 替换（只替换这一部分，不包括后面的空格和{）
            result = result.replace(original, new_code)
        
        return result
    
    def postprocess_violations(self, violations: List[Dict]) -> List[Dict]:
        """后处理违规结果，恢复占位符并映射行号"""
        for v in violations:
            if 'violation_desc' in v:
                v['violation_desc'] = self._restore_placeholders(v['violation_desc'])
            if 'context' in v:
                v['context'] = self._restore_placeholders(v['context'])
            if 'match_type' in v:
                v['match_type'] = self._restore_placeholders(v['match_type'])
            # 映射行号（从预处理后的行号映射回原始行号）
            if 'line_number' in v:
                v['line_number'] = self._map_line_number_back(v['line_number'])
        return violations
    
    def _restore_placeholders(self, text: str) -> str:
        """将占位符恢复为原始代码"""
        result = text
        for rep in self.replacements:
            if rep.get('type') == 'for_loop_simplify':
                # 将简化后的 for 循环恢复为原始形式
                result = result.replace(rep['placeholder'], rep['original'])
            else:
                result = result.replace(rep['placeholder'], rep['original'])
        return result
    
    def _map_line_number_back(self, line_num: int) -> int:
        """将预处理后的行号映射回原始行号
        
        新的预处理方案使用注释包裹，不添加新行，所以行号保持不变
        """
        # 新的注释包裹方案保持行号不变，无需映射
        return line_num


# ==================== JavaParser 桥接器 (subprocess 版本) ====================

import subprocess
import json
import tempfile
import os
import shutil

class JavaParserBridge:
    """JavaParser 桥接器 - 通过 subprocess 调用 Java"""
    
    _initialized = False
    _init_error = None
    _jar_path = None
    _java_cmd = None
    
    @classmethod
    def _ensure_initialized(cls):
        """确保 JavaParser 已初始化"""
        if cls._initialized:
            return True
        if cls._init_error:
            return False
        
        # 1. 查找 Java 命令
        java_cmd = cls._find_java()
        if not java_cmd:
            cls._init_error = "未找到 Java，请安装 JDK 并设置 JAVA_HOME"
            return False
        cls._java_cmd = java_cmd
        
        # 2. 查找 JavaParser jar 包
        jar_paths = [
            SCRIPT_DIR / "javaparser-core-3.25.8.jar",
            SCRIPT_DIR / "javaparser-core.jar",
        ]
        
        jar_file = None
        for jar in jar_paths:
            if jar.exists():
                jar_file = jar
                break
        
        if jar_file is None:
            cls._init_error = "JavaParser jar 包不存在，请放到当前 scan 脚本目录"
            return False
        
        cls._jar_path = str(jar_file)
        
        # 3. 检查 JavaParserBridge.class 是否存在，不存在则编译
        bridge_class = SCRIPT_DIR / "JavaParserBridge.class"
        if not bridge_class.exists():
            if not cls._compile_bridge():
                return False
        
        cls._initialized = True
        return True
    
    @classmethod
    def _find_java(cls):
        """查找 Java 命令"""
        return cls._find_executable("java")

    @staticmethod
    def _find_executable(name: str):
        """跨平台查找 Java/Javac 可执行文件"""
        java_home = os.environ.get('JAVA_HOME')
        candidates = []
        if java_home:
            candidates.extend([
                os.path.join(java_home, 'bin', name),
                os.path.join(java_home, 'bin', f'{name}.exe'),
            ])

        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate

        return shutil.which(name)
    
    @classmethod
    def _compile_bridge(cls):
        """编译 JavaParserBridge.java"""
        java_file = SCRIPT_DIR / "JavaParserBridge.java"
        if not java_file.exists():
            cls._init_error = "JavaParserBridge.java 不存在"
            return False
        
        # 查找 javac
        javac_cmd = cls._find_executable("javac")
        if not javac_cmd:
            cls._init_error = "未找到 javac，无法编译 JavaParserBridge"
            return False
        
        # 编译
        try:
            cmd = [
                javac_cmd,
                '-cp', cls._jar_path,
                str(java_file)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                cls._init_error = f"编译失败: {result.stderr}"
                return False
            return True
        except Exception as e:
            cls._init_error = f"编译异常: {e}"
            return False
    
    @classmethod
    def parse(cls, code: str) -> Optional[Dict]:
        """使用 JavaParser 解析代码"""
        if not cls._ensure_initialized():
            return None
        
        try:
            # 使用 subprocess 调用 Java
            cmd = [
                cls._java_cmd,
                '-cp', os.pathsep.join([cls._jar_path, str(SCRIPT_DIR)]),
                'JavaParserBridge',
                '--stdin'
            ]
            
            result = subprocess.run(
                cmd,
                input=code,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=30
            )
            
            if result.returncode != 0:
                if DEBUG_LOG:
                    print(f"    [JavaParser] 进程错误: {result.stderr}")
                return None
            
            # 解析 JSON 输出
            output = result.stdout.strip()
            if not output:
                return None
            
            ast_info = json.loads(output)
            
            if not ast_info.get('success', False):
                if DEBUG_LOG:
                    print(f"    [JavaParser] 解析失败: {ast_info.get('message', 'Unknown error')}")
                return None
            
            return ast_info
            
        except subprocess.TimeoutExpired:
            if DEBUG_LOG:
                print(f"    [JavaParser] 超时")
            return None
        except json.JSONDecodeError as e:
            if DEBUG_LOG:
                print(f"    [JavaParser] JSON 解析错误: {e}")
            return None
        except Exception as e:
            if DEBUG_LOG:
                print(f"    [JavaParser] 异常: {e}")
            return None
    
    @classmethod
    def is_available(cls) -> bool:
        """检查 JavaParser 是否可用"""
        return cls._ensure_initialized()
    
    @classmethod
    def get_error(cls) -> Optional[str]:
        """获取初始化错误信息"""
        return cls._init_error


# ==================== 统一解析接口 ====================

class UnifiedJavaParser:
    """
    统一 Java 解析器
    提供与 javalang 兼容的 API
    """
    
    @staticmethod
    def parse(code: str) -> Optional[Any]:
        """
        解析 Java 代码，自动选择最佳解析器
        
        策略：
        1. 首先尝试 javalang 解析原始代码
        2. 如果失败，进行预处理后再尝试 javalang
        3. 如果仍失败，返回 None（后续可由 JavaParser 验证）
        
        返回:
            解析结果（javalang 树）
        """
        # 步骤 1：尝试直接解析原始代码
        try:
            import javalang
            tree = javalang.parse.parse(code)
            if DEBUG_LOG:
                print("    [解析器] javalang")
            return tree
        except Exception as e:
            if DEBUG_LOG:
                print(f"    [javalang] 解析失败，尝试预处理...")
        
        # 步骤 2：预处理 + javalang
        preprocessor = JavaCodePreprocessor()
        processed_code = preprocessor.preprocess(code)
        
        # 如果预处理有替换，尝试解析预处理后的代码
        if processed_code != code:
            if DEBUG_LOG:
                print(f"    [预处理] 替换{len(preprocessor.replacements)}处，尝试重新解析...")
            try:
                import javalang
                tree = javalang.parse.parse(processed_code)
                if DEBUG_LOG:
                    print(f"    [解析器] javalang（预处理后）")
                # 标记使用了预处理
                tree._preprocessor = preprocessor
                # 保存预处理后的内容，用于后续行号映射
                tree._preprocessed_content = processed_code
                return tree
            except Exception as e:
                if DEBUG_LOG:
                    print(f"    [javalang+预处理] 仍失败: {e}")
        else:
            if DEBUG_LOG:
                print(f"    [预处理] 未进行任何替换，尝试 JavaParser...")
        
        # 步骤 3：尝试 JavaParser + 适配层
        if JavaParserBridge.is_available():
            jp_result = JavaParserBridge.parse(code)
            if jp_result is not None and jp_result.get('success', False):
                if DEBUG_LOG:
                    print("    [解析器] JavaParser (通过适配层)")
                # 使用适配层将 JSON 转换为 javalang 兼容的对象
                from javaparser_adapter import adapt_javaparser_result
                adapted_tree = adapt_javaparser_result(jp_result)
                if adapted_tree:
                    # 标记使用了 JavaParser 适配
                    adapted_tree._javaparser_adapted = True
                    adapted_tree._javaparser_result = jp_result
                    return adapted_tree
        else:
            if DEBUG_LOG:
                print(f"    [JavaParser] 不可用: {JavaParserBridge.get_error()}")
        
        # 所有解析器都失败
        return None
    
    @staticmethod
    def get_context(lines: List[str], line_number: int, context_lines: int = 2) -> str:
        """获取代码上下文（兼容函数）"""
        if line_number is None or line_number < 1:
            return "无法获取行号"
        
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)
        
        context_parts = []
        for i in range(start, end):
            prefix = ">>> " if i == line_number - 1 else "    "
            context_parts.append(f"{prefix}{i + 1}: {lines[i]}")
        
        return '\n'.join(context_parts)


# 模块级便捷函数
def parse_java_code(code: str) -> Optional[Any]:
    """解析 Java 代码"""
    return UnifiedJavaParser.parse(code)


# 兼容 javalang 的模块级 API
class parse:
    """兼容 javalang.parse"""
    
    @staticmethod
    def parse(code: str) -> Optional[Any]:
        return UnifiedJavaParser.parse(code)


if __name__ == '__main__':
    # 测试代码
    test_code = '''
import java.util.Map;
import java.util.HashMap;

public class Test {
    private Map<String, String> map = new HashMap<>();
    
    public void method() {
        Class<?> clazz = Map.class;
        System.out.println("hello");
    }
}
'''
    
    print("测试统一解析器:")
    result = parse_java_code(test_code)
    if result:
        print(f"解析成功: {type(result)}")
    else:
        print("解析失败")
