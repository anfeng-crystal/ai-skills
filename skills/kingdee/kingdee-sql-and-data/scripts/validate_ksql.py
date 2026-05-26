#!/usr/bin/env python3
"""
KSQL Syntax Validator

校验SQL语句是否符合KSQL（金蝶苍穹SQL引擎）语法规范。
无需外部依赖，使用Python标准库。

用法:
    python validate_ksql.py "SELECT * FROM t_user WHERE fid = 1"
    python validate_ksql.py < sql_file.sql
    echo "SELECT * FROM t_user" | python validate_ksql.py -

输出: JSON格式，包含 valid(bool), errors(list), warnings(list), statement_type(str)
"""

import json
import re
import sys


def normalize_sql(sql: str) -> str:
    """预处理SQL：去除单行/多行注释，标准化空白，保留字符串字面量。"""
    # 去除多行注释 /* ... */
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
    # 去除单行注释 -- ...
    sql = re.sub(r'--[^\n]*', ' ', sql)
    # 标准化空白
    sql = re.sub(r'\s+', ' ', sql).strip()
    return sql


def tokenize_preserve_strings(sql: str):
    """
    将SQL分词，保留字符串字面量作为单个token。
    返回 (token列表, token位置列表)。
    """
    tokens = []
    positions = []
    i = 0
    n = len(sql)
    while i < n:
        # 跳过空白
        if sql[i].isspace():
            i += 1
            continue
        # 字符串字面量 '...' 或 "..."
        if sql[i] in ("'", '"'):
            quote = sql[i]
            start = i
            i += 1
            while i < n:
                if sql[i] == quote:
                    # 检查是否是转义（连续两个引号）
                    if i + 1 < n and sql[i + 1] == quote:
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            tokens.append(sql[start:i])
            positions.append(start)
            continue
        # 方括号标识符 [ ... ]
        if sql[i] == '[':
            start = i
            i += 1
            while i < n and sql[i] != ']':
                i += 1
            if i < n:
                i += 1
            tokens.append(sql[start:i])
            positions.append(start)
            continue
        # 普通token：连续字母/数字/下划线，或单个非空白字符
        if sql[i].isalnum() or sql[i] == '_' or sql[i] == '.':
            start = i
            while i < n and (sql[i].isalnum() or sql[i] == '_' or sql[i] == '.'):
                i += 1
            tokens.append(sql[start:i])
            positions.append(start)
        else:
            tokens.append(sql[i])
            positions.append(i)
            i += 1
    return tokens, positions


def get_statement_type(tokens: list) -> str:
    """根据首个关键字判断语句类型。"""
    if not tokens:
        return "UNKNOWN"
    first = tokens[0].upper()
    if first in ("SELECT", "WITH"):
        return "SELECT"
    if first == "UPDATE":
        return "UPDATE"
    if first == "DELETE":
        return "DELETE"
    if first == "INSERT":
        return "INSERT"
    if first == "CREATE":
        return "CREATE"
    if first == "DROP":
        return "DROP"
    if first == "ALTER":
        return "ALTER"
    if first == "MERGE":
        return "MERGE"
    if first == "TRUNCATE":
        return "TRUNCATE"
    return "UNKNOWN"


def find_keyword(tokens: list, keyword: str, start: int = 0) -> int:
    """查找关键字在token列表中的索引（不区分大小写）。"""
    kw = keyword.upper()
    for i in range(start, len(tokens)):
        if tokens[i].upper() == kw:
            return i
    return -1


def find_matching_parenthesis(tokens: list, open_idx: int) -> int:
    """找到与开括号匹配的闭括号索引。"""
    if tokens[open_idx] != '(':
        return -1
    depth = 1
    for i in range(open_idx + 1, len(tokens)):
        if tokens[i] == '(':
            depth += 1
        elif tokens[i] == ')':
            depth -= 1
            if depth == 0:
                return i
    return -1


def find_paired_keyword(tokens: list, start_keyword: str, end_keyword: str, start: int = 0) -> tuple:
    """
    查找配对的开始和结束关键字（如 CASE ... END）。
    返回 (start_idx, end_idx)，若未找到返回 (-1, -1)。
    """
    sidx = find_keyword(tokens, start_keyword, start)
    if sidx == -1:
        return -1, -1
    depth = 1
    for i in range(sidx + 1, len(tokens)):
        t = tokens[i].upper()
        if t == start_keyword:
            depth += 1
        elif t == end_keyword:
            depth -= 1
            if depth == 0:
                return sidx, i
    return sidx, -1


def validate_select(sql: str, tokens: list) -> list:
    """校验SELECT语句。返回错误列表。"""
    errors = []
    upper_tokens = [t.upper() for t in tokens]

    # 检查 CTE (WITH)
    if upper_tokens[0] == "WITH":
        errors.append("KSQL不支持CTE（WITH子句）。")
        return errors

    # 检查 FROM 子句位置
    from_idx = find_keyword(tokens, "FROM")
    if from_idx == -1:
        # 无FROM的SELECT（如 SELECT 1）通常是合法的
        pass
    else:
        # 检查 FROM 后是否同时有逗号分隔表和 JOIN
        # 找到 WHERE / GROUP BY / ORDER BY / UNION 的位置作为 FROM 区域的结束
        region_end = len(tokens)
        for kw in ("WHERE", "GROUP", "HAVING", "ORDER", "UNION"):
            idx = find_keyword(tokens, kw, from_idx + 1)
            if idx != -1 and idx < region_end:
                region_end = idx

        from_region = tokens[from_idx + 1:region_end]
        from_region_upper = [t.upper() for t in from_region]

        has_comma_table = False
        has_join = False
        for t in from_region_upper:
            if t == ',':
                has_comma_table = True
            if t in ("JOIN", "LEFT", "RIGHT", "FULL", "INNER", "OUTER"):
                has_join = True

        if has_comma_table and has_join:
            errors.append("KSQL不允许在FROM关键字后同时使用逗号分隔表和联接表（JOIN）。")

        # 检查是否有 LIMIT / OFFSET
        for kw in ("LIMIT", "OFFSET"):
            if find_keyword(tokens, kw) != -1:
                errors.append(f"KSQL不支持{kw}子句，请使用TOP代替。")

    # 检查多个裸 *（未限定表名的 *）
    select_idx = find_keyword(tokens, "SELECT")
    from_idx_for_star = find_keyword(tokens, "FROM")
    if select_idx != -1 and from_idx_for_star != -1:
        select_region = upper_tokens[select_idx + 1:from_idx_for_star]
        bare_stars = [i for i, t in enumerate(select_region) if t == "*"]
        if len(bare_stars) > 1:
            errors.append("KSQL不允许在SELECT中同时使用多个未限定表名的*（如SELECT *, *）。如需查询多表所有列，请使用 SELECT A.*, B.* 格式。")

    # 检查 TOP / DISTINCT / ALL 后的列定义规则
    # KSQL: modifier statement后只允许接受符合一般标识符和引号标识符命名规则的列定义
    # 不应该是函数调用或复杂表达式（如 NOW()、COUNT(*) 等）
    if select_idx != -1 and from_idx_for_star != -1:
        has_modifier = False
        modifier_idx = -1
        for kw in ("TOP", "DISTINCT", "ALL"):
            idx = find_keyword(tokens, kw, select_idx + 1)
            if idx != -1 and idx < from_idx_for_star:
                has_modifier = True
                modifier_idx = max(modifier_idx, idx)

        if has_modifier:
            # 检查SELECT列表中的列是否为简单标识符
            # 找到每个列表达式（逗号分隔）
            sel_tokens = tokens[modifier_idx + 1:from_idx_for_star]
            sel_upper = [t.upper() for t in sel_tokens]

            # 简单检测：如果存在 '(' 且不是子查询（前面没有IN/EXISTS/ALL/ANY/SOME），则可能是函数调用
            # 更精确地说，NOW()、COUNT(*) 等函数调用中有括号
            # 但 CASE WHEN ... END 也有括号，需要排除
            # 这里只做基本检测：如果存在裸函数调用（标识符后跟 '('）则报错
            paren_positions = [i for i, t in enumerate(sel_tokens) if t == '(']
            for p in paren_positions:
                # 检查是否属于 CASE 表达式
                case_idx = find_keyword(sel_tokens, "CASE")
                if case_idx != -1:
                    case_end = find_keyword(sel_tokens, "END")
                    if case_idx < p and (case_end == -1 or p < case_end):
                        continue
                # 检查前面是否是标识符（函数名）
                if p > 0 and re.match(r'^[A-Za-z_]\w*$', sel_tokens[p - 1]):
                    func_name = sel_tokens[p - 1].upper()
                    if func_name not in ("SELECT", "FROM", "WHERE", "AND", "OR"):
                        errors.append(
                            f"KSQL语法规定：在TOP/DISTINCT/ALL修饰符后，查询返回列必须是符合标识符命名规则的列定义，"
                            f"不支持函数调用或复杂表达式（如 {func_name}(...)）。"
                        )
                        break

    # 检查窗口函数
    window_keywords = ("OVER", "ROW_NUMBER", "RANK", "DENSE_RANK", "NTILE",
                       "LEAD", "LAG", "FIRST_VALUE", "LAST_VALUE",
                       "PARTITION", "ROWS", "RANGE")
    for kw in window_keywords:
        if find_keyword(tokens, kw) != -1:
            errors.append(f"KSQL不支持窗口函数相关关键字 '{kw}'。")
            break

    return errors


def validate_update(sql: str, tokens: list) -> list:
    """校验UPDATE语句。返回错误列表。"""
    errors = []
    upper_tokens = [t.upper() for t in tokens]

    update_idx = find_keyword(tokens, "UPDATE")
    set_idx = find_keyword(tokens, "SET")

    if update_idx == -1 or set_idx == -1:
        errors.append("UPDATE语句缺少UPDATE或SET关键字。")
        return errors

    # 检查 UPDATE 后是否有表别名
    # UPDATE table_name [alias] SET ...
    # KSQL语法：UPDATE db_nam[.tab_nam] SET ...，不支持别名
    # 简单判断：UPDATE 和 SET 之间有两个以上token，且最后一个不是点号
    between = tokens[update_idx + 1:set_idx]
    if len(between) >= 2:
        # 过滤掉数据库名.表名中的点号
        non_dot = [t for t in between if t != '.']
        # 如果除了表名（可能带db.）外还有额外的标识符，可能是别名
        # 例如 "UPDATE t_user u SET" -> between = ["t_user", "u"]
        # 例如 "UPDATE db.t_user SET" -> between = ["db", ".", "t_user"]
        if len(non_dot) > 1:
            errors.append("KSQL的UPDATE语句不支持表别名。语法为：UPDATE db_nam[.tab_nam] SET ...")

    # 检查是否有 FROM 子句（在SET之后）
    from_idx = find_keyword(tokens, "FROM", set_idx + 1)
    if from_idx != -1:
        errors.append("KSQL的UPDATE语句不支持FROM子句。语法为：UPDATE db_nam[.tab_nam] SET set_lis [WHERE sc_sta]")

    # 检查是否有 JOIN（在UPDATE语句中）
    join_keywords = ("JOIN", "LEFT", "RIGHT", "FULL", "INNER", "OUTER")
    for kw in join_keywords:
        if find_keyword(tokens, kw) != -1:
            errors.append(f"KSQL的UPDATE语句不支持JOIN操作（发现关键字 '{kw}'）。")
            break

    return errors


def validate_delete(sql: str, tokens: list) -> list:
    """校验DELETE语句。返回错误列表。"""
    errors = []
    upper_tokens = [t.upper() for t in tokens]

    # 检查多表 DELETE / DELETE ... FROM ... JOIN
    # SQL Server 风格: DELETE t FROM t JOIN ...
    # MySQL 风格: DELETE t FROM t, t2 ...
    # KSQL 只支持: DELETE [FROM] db_nam.tab_nam [WHERE sc_sta]

    delete_idx = find_keyword(tokens, "DELETE")
    from_idx = find_keyword(tokens, "FROM")

    if from_idx != -1:
        # 检查 FROM 后是否有 JOIN
        join_keywords = ("JOIN", "LEFT", "RIGHT", "FULL", "INNER", "OUTER")
        for kw in join_keywords:
            if find_keyword(tokens, kw, from_idx + 1) != -1:
                errors.append("KSQL的DELETE语句不支持JOIN操作。语法为：DELETE [FROM] db_nam[.tab_nam] [WHERE sc_sta]")
                break

        # 检查是否有多个表名（逗号分隔）在FROM后
        # 找到 WHERE 的位置
        where_idx = find_keyword(tokens, "WHERE", from_idx + 1)
        region_end = where_idx if where_idx != -1 else len(tokens)
        from_region = tokens[from_idx + 1:region_end]
        comma_count = sum(1 for t in from_region if t == ',')
        if comma_count > 0:
            errors.append("KSQL的DELETE语句不支持多表删除。语法为：DELETE [FROM] db_nam[.tab_nam] [WHERE sc_sta]")

    # 检查是否有 USING（PostgreSQL风格的多表DELETE）
    if find_keyword(tokens, "USING") != -1:
        errors.append("KSQL的DELETE语句不支持USING子句。")

    return errors


def validate_insert(sql: str, tokens: list) -> list:
    """校验INSERT语句。返回错误列表。"""
    errors = []
    upper_tokens = [t.upper() for t in tokens]

    # INSERT INTO ... VALUES (...) 或 INSERT INTO ... SELECT ...
    # KSQL: INSERT INTO db_nam[.tab_nam][(col_lis)]{ VALUES (in_lis) | sel_sta}
    # 基本结构检查
    if find_keyword(tokens, "INTO") == -1:
        errors.append("INSERT语句缺少INTO关键字。")

    # 检查是否有 ON CONFLICT / ON DUPLICATE KEY UPDATE 等扩展语法
    extensions = ("CONFLICT", "DUPLICATE")
    for kw in extensions:
        if find_keyword(tokens, kw) != -1:
            errors.append(f"KSQL的INSERT语句不支持 '{kw}' 扩展语法。")

    return errors


def validate_create(sql: str, tokens: list) -> list:
    """校验CREATE语句。返回错误列表。"""
    errors = []
    upper_tokens = [t.upper() for t in tokens]

    # 检查 CREATE 后是否有 TABLE / VIEW / INDEX / UNIQUE
    second = upper_tokens[1] if len(upper_tokens) > 1 else ""
    if second not in ("TABLE", "VIEW", "INDEX", "UNIQUE"):
        errors.append("KSQL的CREATE语句只支持TABLE、VIEW、INDEX。")

    return errors


def validate_drop(sql: str, tokens: list) -> list:
    """校验DROP语句。返回错误列表。"""
    errors = []
    upper_tokens = [t.upper() for t in tokens]

    second = upper_tokens[1] if len(upper_tokens) > 1 else ""
    if second not in ("TABLE", "VIEW", "INDEX"):
        errors.append("KSQL的DROP语句只支持TABLE、VIEW、INDEX。")

    return errors


def validate_alter(sql: str, tokens: list) -> list:
    """校验ALTER语句。返回错误列表。"""
    errors = []
    upper_tokens = [t.upper() for t in tokens]

    if len(upper_tokens) < 2 or upper_tokens[1] != "TABLE":
        errors.append("KSQL的ALTER语句只支持ALTER TABLE。")
        return errors

    # 检查操作类型
    ops = ("ADD", "DROP", "ALTER")
    has_valid_op = False
    for op in ops:
        if find_keyword(tokens, op, 2) != -1:
            has_valid_op = True
            break
    if not has_valid_op:
        errors.append("KSQL的ALTER TABLE只支持ADD、DROP、ALTER操作。")

    return errors


def validate_unsupported_statements(sql: str, tokens: list, stmt_type: str) -> list:
    """校验全局不支持语句类型。"""
    errors = []
    if stmt_type == "MERGE":
        errors.append("KSQL不支持MERGE语句。")
    if stmt_type == "TRUNCATE":
        errors.append("KSQL不支持TRUNCATE语句。")
    return errors


def validate_common(sql: str, tokens: list) -> list:
    """通用校验（适用于所有语句类型）。返回错误列表。"""
    errors = []
    upper_tokens = [t.upper() for t in tokens]

    # 检查是否有未闭合的括号
    open_count = sum(1 for t in tokens if t == '(')
    close_count = sum(1 for t in tokens if t == ')')
    if open_count != close_count:
        errors.append(f"SQL中存在未闭合的括号（开括号{open_count}个，闭括号{close_count}个）。")

    # 检查是否有 CTE (WITH) — 即使不是SELECT开头也可能出现
    # 但已在各语句类型中处理，这里不重复

    return errors


def validate(sql: str) -> dict:
    """
    校验SQL是否符合KSQL规范。
    返回字典：{ "valid": bool, "statement_type": str, "errors": [...], "warnings": [...] }
    """
    if not sql or not sql.strip():
        return {"valid": False, "statement_type": "EMPTY", "errors": ["SQL语句为空。"], "warnings": []}

    normalized = normalize_sql(sql)
    tokens, _ = tokenize_preserve_strings(normalized)

    if not tokens:
        return {"valid": False, "statement_type": "EMPTY", "errors": ["SQL语句为空或仅包含注释。"], "warnings": []}

    stmt_type = get_statement_type(tokens)
    errors = []
    warnings = []

    # 通用校验
    errors.extend(validate_common(sql, tokens))

    # 全局不支持语句
    errors.extend(validate_unsupported_statements(sql, tokens, stmt_type))

    # 按语句类型校验
    if stmt_type == "SELECT":
        errors.extend(validate_select(sql, tokens))
    elif stmt_type == "UPDATE":
        errors.extend(validate_update(sql, tokens))
    elif stmt_type == "DELETE":
        errors.extend(validate_delete(sql, tokens))
    elif stmt_type == "INSERT":
        errors.extend(validate_insert(sql, tokens))
    elif stmt_type == "CREATE":
        errors.extend(validate_create(sql, tokens))
    elif stmt_type == "DROP":
        errors.extend(validate_drop(sql, tokens))
    elif stmt_type == "ALTER":
        errors.extend(validate_alter(sql, tokens))
    elif stmt_type == "UNKNOWN":
        errors.append(f"无法识别的SQL语句类型（首词：{tokens[0]}）。")

    # 警告级别检查
    # 检查是否使用了非KSQL标准函数（只做提示，不一定是错误）
    non_standard_hints = {
        "GETDATE": "建议使用NOW()或CURDATE()代替GETDATE()。",
        "ISNULL": "建议使用COALESCE或NULLIF，KSQL中NULLIF受支持。",
        "CONVERT": "KSQL中CONVERT仅支持CONVERT(DATETIME, val_exp)。",
    }
    upper_sql = normalized.upper()
    for func, hint in non_standard_hints.items():
        if func in upper_sql:
            warnings.append(hint)

    return {
        "valid": len(errors) == 0,
        "statement_type": stmt_type,
        "errors": errors,
        "warnings": warnings
    }


def main():
    if len(sys.argv) < 2:
        print("用法: python validate_ksql.py \"<SQL语句>\"", file=sys.stderr)
        print("      python validate_ksql.py -    # 从标准输入读取", file=sys.stderr)
        sys.exit(1)

    arg = sys.argv[1]
    if arg == '-':
        sql = sys.stdin.read()
    else:
        sql = arg

    result = validate(sql)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
