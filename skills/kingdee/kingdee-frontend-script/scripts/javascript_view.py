"""Bounded lexical code view for lifecycle hints; not a JavaScript/JSX parser."""
from __future__ import annotations

from dataclasses import dataclass


MAX_TEMPLATE_DEPTH = 32
LINE_BREAKS = '\r\n\u2028\u2029'
EXPRESSION_KEYWORDS = {'return', 'throw', 'case', 'delete', 'void', 'typeof', 'new',
                       'yield', 'await', 'in', 'instanceof', 'of', 'else', 'do', 'default', 'debugger'}
CONTROL_KEYWORDS = {'if', 'while', 'for', 'with', 'switch', 'catch'}
CONTEXTUAL_KEYWORDS = {'of', 'await', 'yield'}


@dataclass(frozen=True)
class EventCall:
    operation: str
    name: str
    offset: int


@dataclass(frozen=True)
class Limitation:
    offset: int
    reason: str


@dataclass(frozen=True)
class CodeView:
    text: str
    events: list[EventCall]
    limitations: list[Limitation]


@dataclass(frozen=True)
class Token:
    value: str
    start: int
    end: int


class PartialSyntax(Exception):
    def __init__(self, offset: int, reason: str):
        self.limitation = Limitation(offset, reason)


class Scanner:
    def __init__(self, text: str):
        self.text = text
        self.view = [char if char in LINE_BREAKS else ' ' for char in text]
        self.tokens: list[Token] = []
        self.parens: list[bool] = []
        self.delimiters: list[tuple[str, int]] = []
        self.events: list[EventCall] = []
        self.limitations: list[Limitation] = []
        self.regex_allowed = True

    def copy(self, start: int, end: int) -> None:
        self.view[start:end] = self.text[start:end]

    def emit(self, value: str, start: int, end: int, regex_allowed: bool) -> None:
        self.tokens.append(Token(value, start, end))
        self.tokens = self.tokens[-3:]
        self.regex_allowed = regex_allowed

    def event_argument(self) -> Token | None:
        if (len(self.tokens) >= 2 and self.tokens[-1].value == '('
                and self.tokens[-2].value in {'addEventListener', 'removeEventListener'}):
            return self.tokens[-2]
        return None

    def quoted(self, start: int) -> int:
        quote, cursor = self.text[start], start + 1
        while cursor < len(self.text):
            char = self.text[cursor]
            if char == '\\':
                cursor += 2
                if self.text[cursor - 1:cursor + 1] == '\r\n':
                    cursor += 1
            elif char == quote:
                end = cursor + 1
                event = self.event_argument()
                if event:
                    name = self.text[start + 1:cursor]
                    self.events.append(EventCall(event.value, name, event.start))
                    if '\\' in name:
                        self.limitations.append(Limitation(start, 'Escaped event names are not fully decoded'))
                self.emit('<string>', start, end, False)
                return end
            elif char in LINE_BREAKS:
                raise PartialSyntax(start, 'Unterminated quoted string')
            else:
                cursor += 1
        raise PartialSyntax(start, 'Unterminated quoted string')

    def template(self, start: int, depth: int) -> int:
        if depth > MAX_TEMPLATE_DEPTH:
            raise PartialSyntax(start, f'Template depth exceeds lexical limit {MAX_TEMPLATE_DEPTH}')
        self.copy(start, start + 1)
        self.emit('<template-start>', start, start + 1, False)
        cursor = start + 1
        while cursor < len(self.text):
            if self.text[cursor] == '\\':
                cursor += 2
            elif self.text[cursor] == '`':
                self.copy(cursor, cursor + 1)
                self.emit('<template>', start, cursor + 1, False)
                return cursor + 1
            elif self.text.startswith('${', cursor):
                self.copy(cursor, cursor + 2)
                self.emit('<expression-start>', cursor, cursor + 2, True)
                cursor = self.code(cursor + 2, depth, close_brace=True)
            else:
                cursor += 1
        raise PartialSyntax(start, 'Unterminated template literal')

    def regexp(self, start: int) -> int:
        cursor, in_class = start + 1, False
        while cursor < len(self.text):
            char = self.text[cursor]
            if char in LINE_BREAKS:
                break
            if char == '\\':
                cursor += 2
                continue
            if char == '[':
                if in_class:
                    raise PartialSyntax(start, 'Nested regular-expression character classes need a parser')
                in_class = True
            elif char == ']':
                in_class = False
            elif char == '/' and not in_class:
                end = cursor + 1
                while end < len(self.text) and self.text[end].isalpha():
                    end += 1
                flags = self.text[cursor + 1:end]
                if 'v' in flags or any(flag not in 'dgimsuy' for flag in flags):
                    raise PartialSyntax(start, 'Regular-expression flags are outside the lexical subset')
                # Keep delimiters so masking never joins neighboring code tokens.
                self.copy(start, start + 1)
                self.copy(cursor, end)
                self.emit('<regexp>', start, end, False)
                return end
            cursor += 1
        raise PartialSyntax(start, 'Unterminated or ambiguous regular-expression literal')

    def code(self, start: int = 0, depth: int = 0, close_brace: bool = False) -> int:
        cursor, scope_depth = start, len(self.delimiters)
        while cursor < len(self.text):
            char = self.text[cursor]
            if char.isspace():
                cursor += 1
                continue
            if self.text.startswith('//', cursor) or (cursor == 0 and self.text.startswith('#!')):
                while cursor < len(self.text) and self.text[cursor] not in LINE_BREAKS:
                    cursor += 1
                continue
            if self.text.startswith('/*', cursor):
                end = self.text.find('*/', cursor + 2)
                if end < 0:
                    raise PartialSyntax(cursor, 'Unterminated block comment')
                cursor = end + 2
                continue
            if self.text.startswith(('<!--', '-->'), cursor):
                raise PartialSyntax(cursor, 'Legacy HTML comment syntax is not classified')
            if char == '\\':
                raise PartialSyntax(cursor, 'Escaped identifiers are not decoded')
            if char in {'"', "'"}:
                cursor = self.quoted(cursor)
                continue
            event = self.event_argument()
            if event:
                self.limitations.append(Limitation(cursor, 'Dynamic or template event names are not resolved'))
            if char == '`':
                cursor = self.template(cursor, depth + 1)
                continue
            if char == '}' and close_brace and len(self.delimiters) == scope_depth:
                self.copy(cursor, cursor + 1)
                self.emit('<expression-end>', cursor, cursor + 1, False)
                return cursor + 1
            if char == '/':
                previous = self.tokens[-1] if self.tokens else None
                before = self.tokens[-2].value if len(self.tokens) > 1 else ''
                if previous and previous.value in CONTEXTUAL_KEYWORDS and before not in {'.', '?.'}:
                    raise PartialSyntax(cursor, 'Contextual keyword versus identifier goal needs a parser')
                if previous and (previous.value == '}' or (not self.regex_allowed and any(
                        mark in self.text[previous.end:cursor] for mark in LINE_BREAKS))):
                    raise PartialSyntax(cursor, 'Regular-expression versus division goal is ambiguous here')
                if self.regex_allowed:
                    cursor = self.regexp(cursor)
                    continue
            if char == '<' and self.regex_allowed:
                following = self.text[cursor + 1:cursor + 2]
                if following and (following.isalpha() or following in {'>', '/'}):
                    raise PartialSyntax(cursor, 'JSX or angle-bracket syntax needs a parser')
            if char.isalpha() or char in {'_', '$'}:
                end = cursor + 1
                while end < len(self.text) and (self.text[end].isalnum() or self.text[end] in {'_', '$'}):
                    end += 1
                value = self.text[cursor:end]
                property_name = bool(self.tokens and self.tokens[-1].value in {'.', '?.'})
                self.copy(cursor, end)
                self.emit(value, cursor, end, value in EXPRESSION_KEYWORDS and not property_name)
                cursor = end
                continue
            if char.isdigit():
                end = cursor + 1
                while end < len(self.text) and (self.text[end].isalnum() or self.text[end] in '._'):
                    end += 1
                self.copy(cursor, end)
                self.emit('<number>', cursor, end, False)
                cursor = end
                continue
            width = 2 if self.text[cursor:cursor + 2] in {'++', '--', '=>', '?.', '/='} else 1
            value = self.text[cursor:cursor + width]
            allowed = value not in {')', ']', '}', '.', '?.', '++', '--'}
            if value in {'(', '[', '{'}:
                self.delimiters.append((value, cursor))
            elif value in {')', ']', '}'}:
                expected = {')': '(', ']': '[', '}': '{'}[value]
                if not self.delimiters or self.delimiters[-1][0] != expected:
                    raise PartialSyntax(cursor, 'Unmatched or mismatched code delimiter')
                self.delimiters.pop()
            if value == '(':
                previous = self.tokens[-1].value if self.tokens else ''
                before = self.tokens[-2].value if len(self.tokens) > 1 else ''
                self.parens.append((previous in CONTROL_KEYWORDS and before not in {'.', '?.'})
                                   or (previous == 'await' and before == 'for'))
            elif value == ')':
                allowed = self.parens.pop() if self.parens else False
            self.copy(cursor, cursor + width)
            self.emit(value, cursor, cursor + width, allowed)
            cursor += width
        if close_brace:
            raise PartialSyntax(start, 'Unterminated template expression')
        return cursor


def javascript_code_view(text: str) -> CodeView:
    scanner = Scanner(text)
    try:
        scanner.code()
        if scanner.delimiters:
            _, offset = scanner.delimiters[-1]
            scanner.limitations.append(Limitation(offset, 'Unterminated code delimiter'))
    except PartialSyntax as exc:
        scanner.limitations.append(exc.limitation)
    return CodeView(''.join(scanner.view), scanner.events, scanner.limitations)
