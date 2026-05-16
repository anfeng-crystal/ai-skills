# -*- coding: utf-8 -*-
"""
JavaParser JSON 到 javalang 的适配层
将 JavaParser 返回的 JSON 转换为 javalang 兼容的对象结构
"""

from typing import List, Dict, Any, Optional, Tuple


def detect_loop_violations_from_javaparser(
    jp_result: Dict, 
    rules_map: Dict,
    file_path: str,
    lines: List[str],
    get_context_func=None,
    match_type_prefix: str = "循环内调用"
) -> List[Dict]:
    """
    从JavaParser的JSON结果中检测循环内违规
    
    统一的JavaParser检测结果处理函数，供各个扫描脚本调用
    
    Args:
        jp_result: JavaParser返回的JSON结果
        rules_map: 规则映射字典，结构取决于检测类型
            - 方法检测: {'class_short_name': {'method_name': [rule1, rule2, ...]}}
            - 类检测: {'class_short_name': [rule1, rule2, ...]}
        file_path: 文件路径
        lines: 源代码行列表
        get_context_func: 获取上下文的函数，签名 (lines, line_num) -> str
        match_type_prefix: 匹配类型前缀
    
    Returns:
        违规列表
    """
    violations = []
    
    if not jp_result or not jp_result.get('success', False):
        return violations
    
    # 收集import信息
    imported_classes = {}
    for imp_data in jp_result.get('imports', []):
        path = imp_data.get('path', '')
        if path and not imp_data.get('wildcard', False):
            class_name = path.split('.')[-1]
            imported_classes[class_name] = path
    
    def get_context(lines, line_num):
        if get_context_func:
            return get_context_func(lines, line_num)
        # 默认的上下文获取
        if not line_num or line_num < 1 or line_num > len(lines):
            return ''
        start = max(0, line_num - 3)
        end = min(len(lines), line_num + 2)
        context_parts = []
        for i in range(start, end):
            prefix = ">>> " if i == line_num - 1 else "    "
            context_parts.append(f"{prefix}{i + 1}: {lines[i].rstrip()}")
        return '\n'.join(context_parts)
    
    def check_call(call_data: Dict) -> Optional[Dict]:
        """检查方法调用是否违规"""
        scope = call_data.get('scope', '')
        name = call_data.get('name', '')
        line = call_data.get('line', 0)
        is_method_ref = call_data.get('isMethodReference', False)
        
        if not scope:
            return None
        
        # 对于方法引用，scope可能是 "ClassName" 或 "package.ClassName"
        # 需要提取类名
        if is_method_ref:
            # 方法引用格式: BusinessDataServiceHelper::loadRefence
            # scope是 "BusinessDataServiceHelper" 或全限定类名
            if '.' in scope:
                # 全限定类名，取最后一部分
                scope = scope.split('.')[-1]
        
        
        # 根据rules_map的结构判断是方法检测还是类检测
        # 方法检测: rules_map[scope][name] -> list
        # 类检测: rules_map[scope] -> list
        
        matched_rules = []
        
        if name and scope in rules_map:
            # 可能是方法检测
            if isinstance(rules_map[scope], dict) and name in rules_map[scope]:
                matched_rules = rules_map[scope][name]
            # 可能是类检测
            elif isinstance(rules_map[scope], list):
                matched_rules = rules_map[scope]
        
        
        if not matched_rules:
            return None
        
        for rule in matched_rules:
            # 验证import是否匹配
            imported_full = imported_classes.get(scope)
            if imported_full and 'full_class_name' in rule:
                if imported_full != rule['full_class_name']:
                    continue
            
            # 构建违规描述
            call_type = "方法引用" if is_method_ref else "方法"
            if name:
                violation_desc = f'{match_type_prefix}禁止{call_type} {rule.get("full_class_name", scope)}.{name}()'
            else:
                violation_desc = f'{match_type_prefix}禁止类 {rule.get("full_class_name", scope)}'
            
            return {
                'rule_code': rule.get('rule_code', ''),
                'rule_name': rule.get('rule_name', ''),
                'rule_level': rule.get('rule_level', ''),
                'file_path': file_path,
                'line_number': line,
                'violation_desc': violation_desc,
                'solution': rule.get('solution', ''),
                'match_type': f'{match_type_prefix}(JavaParser-方法引用)' if is_method_ref else f'{match_type_prefix}(JavaParser)',
                'context': get_context(lines, line)
            }
        
        return None
    
    # 检查每个类型
    for type_data in jp_result.get('types', []):
        # 检查类级别的方法调用
        for call_data in type_data.get('methodCalls', []):
            if call_data.get('inLoop', False):
                violation = check_call(call_data)
                if violation:
                    violations.append(violation)
        
        # 检查方法内的方法调用
        for method_data in type_data.get('methods', []):
            for call_data in method_data.get('methodCalls', []):
                if call_data.get('inLoop', False):
                    violation = check_call(call_data)
                    if violation:
                        violations.append(violation)
    
    return violations


class Position:
    """模拟 javalang 的 Position"""
    def __init__(self, line: int, column: int = 0):
        self.line = line
        self.column = column
    
    def __repr__(self):
        return f"Position(line={self.line}, column={self.column})"


class MockNode:
    """基础模拟节点"""
    def __init__(self, node_type: str = "MockNode"):
        self._node_type = node_type
        self.position = None
        self.attrs = []
    
    def __repr__(self):
        return f"{self._node_type}()"
    
    def filter(self, pattern):
        """模拟 filter 方法"""
        return []
    
    @property
    def children(self):
        """模拟 children 属性"""
        return []


class Import(MockNode):
    """模拟 javalang.tree.Import"""
    def __init__(self, path: str, is_static: bool = False, is_wildcard: bool = False, line: int = 0):
        super().__init__("Import")
        self.path = path
        self.static = is_static
        self.wildcard = is_wildcard
        self.position = (line, 0) if line > 0 else None
        self.attrs = ['path', 'static', 'wildcard', 'position']
    
    def __repr__(self):
        return f"Import(path='{self.path}', static={self.static}, wildcard={self.wildcard})"


class ReferenceType(MockNode):
    """模拟 javalang.tree.ReferenceType"""
    def __init__(self, name: str, arguments: List[Any] = None, dimensions: List[Any] = None, line: int = 0):
        super().__init__("ReferenceType")
        self.name = name
        self.arguments = arguments or []
        self.dimensions = dimensions or []
        self.sub_type = None
        self.position = (line, 0) if line > 0 else None
        self.attrs = ['name', 'arguments', 'dimensions', 'sub_type', 'position']
    
    def __repr__(self):
        return f"ReferenceType(name='{self.name}')"


class ClassDeclaration(MockNode):
    """模拟 javalang.tree.ClassDeclaration"""
    def __init__(self, name: str, line: int = 0):
        super().__init__("ClassDeclaration")
        self.name = name
        self.position = (line, 0) if line > 0 else None
        self.modifiers = []
        self.annotations = []
        self.documentation = None
        self.type_parameters = []
        self.extends = None
        self.implements = []
        self.body = []
        self.fields = []
        self.methods = []
        self.constructors = []
        self.attrs = ['name', 'modifiers', 'annotations', 'documentation', 'type_parameters', 
                      'extends', 'implements', 'body', 'fields', 'methods', 'constructors', 'position']
    
    def __repr__(self):
        return f"ClassDeclaration(name='{self.name}')"


class MethodDeclaration(MockNode):
    """模拟 javalang.tree.MethodDeclaration"""
    def __init__(self, name: str, return_type: Any = None, line: int = 0):
        super().__init__("MethodDeclaration")
        self.name = name
        self.position = (line, 0) if line > 0 else None
        self.modifiers = []
        self.annotations = []
        self.documentation = None
        self.type_parameters = []
        self.return_type = return_type
        self.parameters = []
        self.throws = []
        self.body = []
        self.attrs = ['name', 'modifiers', 'annotations', 'documentation', 'type_parameters',
                      'return_type', 'parameters', 'throws', 'body', 'position']
    
    def __repr__(self):
        return f"MethodDeclaration(name='{self.name}')"


class FieldDeclaration(MockNode):
    """模拟 javalang.tree.FieldDeclaration"""
    def __init__(self, field_type: Any, line: int = 0):
        super().__init__("FieldDeclaration")
        self.position = (line, 0) if line > 0 else None
        self.type = field_type
        self.modifiers = []
        self.annotations = []
        self.declarators = []
        self.attrs = ['type', 'modifiers', 'annotations', 'declarators', 'position']
    
    def __repr__(self):
        return f"FieldDeclaration(type={self.type})"


class ConstructorDeclaration(MockNode):
    """模拟 javalang.tree.ConstructorDeclaration"""
    def __init__(self, name: str = "<init>", line: int = 0):
        super().__init__("ConstructorDeclaration")
        self.name = name
        self.position = (line, 0) if line > 0 else None
        self.modifiers = []
        self.annotations = []
        self.documentation = None
        self.type_parameters = []
        self.parameters = []
        self.throws = []
        self.body = []
        self.attrs = ['name', 'modifiers', 'annotations', 'documentation', 'type_parameters',
                      'parameters', 'throws', 'body', 'position']
    
    def __repr__(self):
        return f"ConstructorDeclaration()"


class Parameter(MockNode):
    """模拟 javalang.tree.FormalParameter"""
    def __init__(self, name: str, param_type: Any, line: int = 0):
        super().__init__("FormalParameter")
        self.name = name
        self.type = param_type
        self.position = (line, 0) if line > 0 else None
        self.modifiers = []
        self.annotations = []
        self.varargs = False
        self.attrs = ['name', 'type', 'modifiers', 'annotations', 'varargs', 'position']
    
    def __repr__(self):
        return f"FormalParameter(name='{self.name}', type={self.type})"


class VariableDeclarator(MockNode):
    """模拟 javalang.tree.VariableDeclarator"""
    def __init__(self, name: str, initializer: Any = None, line: int = 0):
        super().__init__("VariableDeclarator")
        self.name = name
        self.initializer = initializer
        self.position = (line, 0) if line > 0 else None
        self.attrs = ['name', 'initializer', 'position']


class MethodInvocation(MockNode):
    """模拟 javalang.tree.MethodInvocation"""
    def __init__(self, name: str, qualifier: str = None, line: int = 0):
        super().__init__("MethodInvocation")
        self.member = name
        self.qualifier = qualifier
        self.position = (line, 0) if line > 0 else None
        self.arguments = []
        self.type_arguments = []
        self.attrs = ['member', 'qualifier', 'arguments', 'type_arguments', 'position']
    
    def __repr__(self):
        return f"MethodInvocation(qualifier={self.qualifier}, member='{self.member}')"


class ClassCreator(MockNode):
    """模拟 javalang.tree.ClassCreator"""
    def __init__(self, type_name: str, line: int = 0):
        super().__init__("ClassCreator")
        self.type = ReferenceType(type_name, line=line)
        self.position = (line, 0) if line > 0 else None
        self.arguments = []
        self.body = None
        self.type_arguments = []
        self.attrs = ['type', 'arguments', 'body', 'type_arguments', 'position']


class CompilationUnit(MockNode):
    """模拟 javalang.tree.CompilationUnit"""
    def __init__(self, package: str = None, imports: List[Import] = None, types: List[ClassDeclaration] = None):
        super().__init__("CompilationUnit")
        self.package = package
        self.imports = imports or []
        self.types = types or []
        self.position = None
        self.attrs = ['package', 'imports', 'types', 'position']
    
    def __repr__(self):
        return f"CompilationUnit(package={self.package}, imports={len(self.imports)}, types={len(self.types)})"
    
    def __iter__(self):
        """使 CompilationUnit 可迭代"""
        return iter(self.types)


def adapt_javaparser_result(json_result: Dict[str, Any]) -> Optional[CompilationUnit]:
    """
    将 JavaParser 返回的 JSON 转换为 javalang 兼容的 CompilationUnit
    
    Args:
        json_result: JavaParser 返回的 JSON 字典
        
    Returns:
        适配后的 CompilationUnit 对象，或 None（如果解析失败）
    """
    if not json_result or not json_result.get('success', False):
        return None
    
    # 创建 CompilationUnit
    cu = CompilationUnit()
    
    # 包声明
    if 'package' in json_result:
        cu.package = json_result['package']
    
    # 导入语句
    for imp_data in json_result.get('imports', []):
        imp = Import(
            path=imp_data.get('path', ''),
            is_static=imp_data.get('static', False),
            is_wildcard=imp_data.get('wildcard', False),
            line=imp_data.get('line', 0)
        )
        cu.imports.append(imp)
    
    # 类型声明
    for type_data in json_result.get('types', []):
        class_decl = ClassDeclaration(
            name=type_data.get('name', 'Unknown'),
            line=type_data.get('line', 0)
        )
        
        # 继承
        extends_list = type_data.get('extends', [])
        if extends_list:
            class_decl.extends = ReferenceType(extends_list[0], line=type_data.get('line', 0))
        
        # 实现
        for impl_name in type_data.get('implements', []):
            class_decl.implements.append(ReferenceType(impl_name, line=type_data.get('line', 0)))
        
        # 字段
        for field_data in type_data.get('fields', []):
            field_type = ReferenceType(field_data.get('type', 'Object'), line=field_data.get('line', 0))
            field = FieldDeclaration(field_type, line=field_data.get('line', 0))
            
            # 设置字段修饰符（static, final, private, public 等）
            field.modifiers = field_data.get('modifiers', [])
            
            # 设置变量声明符（变量名）
            for decl_data in field_data.get('declarators', []):
                declarator = VariableDeclarator(
                    name=decl_data.get('name', 'unknown'),
                    line=field_data.get('line', 0)
                )
                field.declarators.append(declarator)
            
            class_decl.fields.append(field)
            class_decl.body.append(field)
        
        # 方法
        for method_data in type_data.get('methods', []):
            return_type = None
            if 'returnType' in method_data:
                return_type = ReferenceType(method_data['returnType'], line=method_data.get('line', 0))

            method = MethodDeclaration(
                name=method_data.get('name', 'unknown'),
                return_type=return_type,
                line=method_data.get('line', 0)
            )

            # 参数
            for param_data in method_data.get('parameters', []):
                param_type = ReferenceType(param_data.get('type', 'Object'), line=method_data.get('line', 0))
                param = Parameter(
                    name=param_data.get('name', 'arg'),
                    param_type=param_type,
                    line=method_data.get('line', 0)
                )
                method.parameters.append(param)

            # 方法体内的方法调用
            for call_data in method_data.get('methodCalls', []):
                call = MethodInvocation(
                    name=call_data.get('name', 'call'),
                    qualifier=call_data.get('scope'),
                    line=call_data.get('line', 0)
                )
                # 创建一个表达式语句包装
                stmt = MockNode("StatementExpression")
                stmt.expression = call
                stmt.position = (call_data.get('line', 0), 0)
                method.body.append(stmt)

            class_decl.methods.append(method)
            class_decl.body.append(method)

        # 构造函数
        for ctor_data in type_data.get('constructors', []):
            ctor = ConstructorDeclaration(line=ctor_data.get('line', 0))

            # 参数
            for param_data in ctor_data.get('parameters', []):
                param_type = ReferenceType(param_data.get('type', 'Object'), line=ctor_data.get('line', 0))
                param = Parameter(
                    name=param_data.get('name', 'arg'),
                    param_type=param_type,
                    line=ctor_data.get('line', 0)
                )
                ctor.parameters.append(param)

            class_decl.constructors.append(ctor)
            class_decl.body.append(ctor)

        # 类级别的旧格式 methodCalls（向后兼容）
        for call_data in type_data.get('methodCalls', []):
            call = MethodInvocation(
                name=call_data.get('name', 'call'),
                qualifier=call_data.get('scope'),
                line=call_data.get('line', 0)
            )
            # 创建一个表达式语句包装
            stmt = MockNode("StatementExpression")
            stmt.expression = call
            stmt.position = (call_data.get('line', 0), 0)
            class_decl.body.append(stmt)
        
        # 对象创建
        for creation_data in type_data.get('objectCreations', []):
            creator = ClassCreator(
                type_name=creation_data.get('type', 'Object'),
                line=creation_data.get('line', 0)
            )
            class_decl.body.append(creator)
        
        cu.types.append(class_decl)
    
    return cu


# 兼容性别名，让适配后的对象可以通过 isinstance 检查
def is_adapted_node(obj, node_type: str) -> bool:
    """检查对象是否是特定类型的适配节点"""
    return isinstance(obj, MockNode) and obj._node_type == node_type


if __name__ == '__main__':
    # 测试适配层
    test_json = {
        "success": True,
        "package": "com.example",
        "imports": [
            {"path": "java.util.Map", "static": False, "wildcard": False},
            {"path": "java.util.List", "static": False, "wildcard": False}
        ],
        "types": [
            {
                "name": "Test",
                "line": 3,
                "extends": ["Object"],
                "implements": ["Runnable"],
                "fields": [
                    {"type": "Map", "line": 4}
                ],
                "methods": [
                    {
                        "name": "run",
                        "line": 5,
                        "returnType": "void",
                        "parameters": []
                    }
                ],
                "constructors": [],
                "methodCalls": [],
                "objectCreations": []
            }
        ]
    }
    
    cu = adapt_javaparser_result(test_json)
    print("Adapted CompilationUnit:", cu)
    print("Package:", cu.package)
    print("Imports:", cu.imports)
    print("Types:", cu.types)
    if cu.types:
        t = cu.types[0]
        print("  Class name:", t.name)
        print("  Extends:", t.extends)
        print("  Implements:", t.implements)
        print("  Fields:", t.fields)
        print("  Methods:", t.methods)
