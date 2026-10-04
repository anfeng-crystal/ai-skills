"""Local KSQL precheck lexing; not a replacement for the target KSQL parser."""


def _quoted_end(sql: str, start: int) -> int:
    closing = ']' if sql[start] == '[' else sql[start]
    i = start + 1
    while i < len(sql):
        if sql[i] == closing:
            if i + 1 < len(sql) and sql[i + 1] == closing:
                i += 2
                continue
            return i + 1
        i += 1
    raise ValueError("SQL中存在未闭合的字符串或引号标识符。")


def normalize_sql(sql: str) -> str:
    """Remove comments and collapse only unquoted whitespace.

    KSQL supports --, // and /* */ comments. Recognize quotes first so that
    literal comment markers cannot hide the rest of a statement from checks.
    """
    parts = []
    i = 0
    while i < len(sql):
        if sql[i] in ("'", '"', '['):
            end = _quoted_end(sql, i)
            parts.append(sql[i:end])
            i = end
        elif sql.startswith(('--', '//'), i):
            # Verified against KSQL 7.0: bare CR remains inside a line comment.
            while i < len(sql) and sql[i] != '\n':
                i += 1
            parts.append(' ')
        elif sql.startswith('/*', i):
            end = sql.find('*/', i + 2)
            if end == -1:
                raise ValueError("SQL中存在未闭合的块注释。")
            parts.append(' ')
            i = end + 2
        elif sql[i].isspace():
            parts.append(' ')
            while i < len(sql) and sql[i].isspace():
                i += 1
        else:
            parts.append(sql[i])
            i += 1
    return ''.join(parts).strip()


def tokenize_preserve_strings(sql: str):
    """Return tokens and offsets, keeping each quoted value intact."""
    tokens, positions = [], []
    i = 0
    while i < len(sql):
        if sql[i].isspace():
            i += 1
            continue
        start = i
        if sql[i] in ("'", '"', '['):
            i = _quoted_end(sql, i)
        elif sql[i].isalnum() or sql[i] in '_.':
            while i < len(sql) and (sql[i].isalnum() or sql[i] in '_.'):
                i += 1
        else:
            i += 1
        tokens.append(sql[start:i])
        positions.append(start)
    return tokens, positions
