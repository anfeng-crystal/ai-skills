"""Small lexical preflight for ISCB, not a parser or runtime type checker.

The bundled JAR accepts // comments, quoted literals and local .each/.filter
receivers. Keep a same-offset literal view for checks that inspect arguments.
Other member methods still require a manifest or runtime/target evidence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

IDENTIFIER = r"[A-Za-z_$][A-Za-z0-9_$]*"
FUNCTION_PARAMS_RE = re.compile(rf"\bfunction\s+({IDENTIFIER})\s*\(([^()]*)\)\s*\{{")
VAR_DECL_RE = re.compile(rf"\bvar\s+({IDENTIFIER})\b")
LAMBDA_RE = re.compile(rf"(?:(?P<single>{IDENTIFIER})|\((?P<multi>[^()]*)\))\s*->")
CALL_RE = re.compile(r"(?<![\w$])([A-Za-z_$%][A-Za-z0-9_$%]*)\s*\(")
RECEIVER_RE = re.compile(rf"({IDENTIFIER}(?:\s*\.\s*{IDENTIFIER})*)\s*$")
# Verified with pure local JAR eval; accepting the syntax does not infer a type.
VERIFIED_STREAM_METHODS = {"each", "filter"}


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    location: str


@dataclass
class Call:
    name: str
    start: int
    receiver: str | None
    member: bool
    partial_receiver: bool = False


@dataclass
class SourceViews:
    code: str
    literals: str
    unterminated_string: bool


def source_views(script: str) -> SourceViews:
    """Mask only JAR-supported // comments and single/double quoted literals.

    Spaces preserve offsets; newlines preserve line boundaries. In particular,
    do not silently accept JavaScript /* */ comments as ISCB syntax.
    """
    code, literals = list(script), list(script)
    quote = None
    index = 0
    while index < len(script):
        char = script[index]
        if quote is not None:
            if char not in "\r\n":
                code[index] = " "
            if char == "\\" and index + 1 < len(script):
                index += 1
                if script[index] not in "\r\n":
                    code[index] = " "
            elif char == quote:
                quote = None
        elif char in "\"'":
            quote = char
            code[index] = " "
        elif script.startswith("//", index):
            while index < len(script) and script[index] not in "\r\n":
                code[index] = literals[index] = " "
                index += 1
            continue
        index += 1
    return SourceViews("".join(code), "".join(literals), quote is not None)


class ScriptAnalysis:
    def __init__(self, script: str):
        self.views = source_views(script)
        self.code = self.views.code
        self.pairs = self._pairs()
        self.bindings: list[tuple[str, int, int]] = []
        self._bindings()
        self.calls = self._calls()

    def _pairs(self) -> dict[int, int]:
        stack, pairs = [], {}
        closing = {"}": "{", "]": "[", ")": "("}
        for index, char in enumerate(self.code):
            if char in "{[(":
                stack.append((index, char))
            elif char in closing and stack and stack[-1][1] == closing[char]:
                start, _ = stack.pop()
                pairs[start] = index
        return pairs

    def _block_end(self, position: int) -> int:
        return min((end for start, end in self.pairs.items()
                    if self.code[start] == "{" and start < position < end), default=len(self.code))

    def _expression_end(self, position: int) -> int:
        index = position
        while index < len(self.code):
            char = self.code[index]
            if char in ";,)}]":
                return index
            if index in self.pairs:
                index = self.pairs[index]
            index += 1
        return len(self.code)

    def _add_params(self, text: str, start: int, end: int) -> None:
        for param in text.split(","):
            name = param.strip()
            if re.fullmatch(IDENTIFIER, name):
                self.bindings.append((name, start, end))

    def _bindings(self) -> None:
        for match in VAR_DECL_RE.finditer(self.code):
            self.bindings.append((match[1], match.end(), self._block_end(match.end())))
        for match in FUNCTION_PARAMS_RE.finditer(self.code):
            self.bindings.append((match[1], match.start(), self._block_end(match.start())))
            start = match.end() - 1
            self._add_params(match[2], start, self.pairs.get(start, len(self.code)))
        for match in LAMBDA_RE.finditer(self.code):
            self._add_params(match["single"] or match["multi"], match.end(), self._expression_end(match.end()))

    def is_local(self, name: str, position: int) -> bool:
        return any(bound == name and start <= position < end for bound, start, end in self.bindings)

    def _calls(self) -> list[Call]:
        calls = []
        for match in CALL_RE.finditer(self.code):
            prefix = self.code[:match.start()].rstrip()
            member = prefix.endswith(".")
            receiver_match = RECEIVER_RE.search(prefix[:-1]) if member else None
            # Keep a dotted property path intact: its leaf may collide with a
            # local name or toolbox. Only its root can establish a local binding.
            receiver = re.sub(r"\s+", "", receiver_match[1]) if receiver_match else None
            # A suffix after a call/index/group is not a complete identifier path.
            partial = bool(receiver_match and prefix[:receiver_match.start()].rstrip().endswith("."))
            calls.append(Call(match[1], match.start(), receiver, member, partial))
        return calls

    def code_match(self, match: re.Match) -> bool:
        """A literal-aware rule may match text only when its start is code."""
        return bool(self.code[match.start():match.end()].lstrip()) and not self.code[match.start()].isspace()

    def balance_findings(self) -> list[Finding]:
        findings = []
        if self.views.unterminated_string:
            findings.append(Finding("error", "unterminated-string", "String literal is not closed.", "script"))
        stack = []
        reverse = {")": "(", "]": "[", "}": "{"}
        for char in self.code:
            if char in "([{":
                stack.append(char)
            elif char in reverse:
                if not stack or stack[-1] != reverse[char]:
                    findings.append(Finding("error", "unbalanced-delimiter", f"Found unmatched `{char}`.", "script"))
                    return findings
                stack.pop()
        if stack:
            findings.append(Finding("error", "unbalanced-delimiter", f"Unclosed delimiter `{stack[-1]}`.", "script"))
        return findings


def call_findings(analysis: ScriptAnalysis, mode: str, engine: dict, platform: dict,
                  ignored_globals: set[str], external_globals: set[str], external_namespaces: set[str]) -> list[Finding]:
    findings = []
    namespaces = {key: set(value) for key, value in engine["namespaces"].items()}
    platform_namespaces = {key: set(value) for key, value in platform["namespaces"].items()}
    globals_set = set(engine["globals"])
    platform_globals = set(platform["globals"]) | set(platform["deprecated"])
    platform_globals.update(token for token in platform["operators"] if re.fullmatch(IDENTIFIER, token))
    for call in analysis.calls:
        name = call.name
        if call.member:
            namespace = call.receiver
            if call.partial_receiver or namespace is None or analysis.is_local(namespace.split(".", 1)[0], call.start):
                if call.partial_receiver or name not in VERIFIED_STREAM_METHODS:
                    findings.append(Finding("warn", "unverified-member-method",
                        f"成员调用 `{name}()` 的接收者类型与方法未由静态目录确认；需用真实 runtime 或目标证据验证。", "script"))
                continue
            official_methods = platform_namespaces.get(namespace)
            if official_methods is not None:
                if name not in official_methods:
                    findings.append(Finding("warn", "unverified-platform-method",
                        f"`{namespace}.{name}()` 不在当前官方平台速查目录；需用目标版本官方文档或运行证据确认。", "script"))
                continue
            if namespace in external_namespaces:
                continue
            methods = namespaces.get(namespace)
            if methods is None:
                findings.append(Finding("error" if mode == "engine" else "warn",
                    "unknown-namespace" if mode == "engine" else "unverified-platform-namespace",
                    f"Unknown namespace `{namespace}`." if mode == "engine" else
                    f"`{namespace}` 不在 bundled engine 或当前官方平台目录；需用目标版本证据确认。", "script"))
                continue
            if name not in methods:
                candidates = {value.lower(): value for value in methods}
                code = "case-mismatch" if name.lower() in candidates else "unknown-method"
                message = (f"`{namespace}.{name}()` uses the wrong case; bundled manifest uses `{namespace}.{candidates[name.lower()]}()`."
                    if code == "case-mismatch" else f"`{namespace}.{name}()` was not found in the bundled engine manifest.")
                findings.append(Finding("error", code, message, "script"))
            continue
        if name in ignored_globals or analysis.is_local(name, call.start) or name in external_globals:
            continue
        if name in globals_set or (mode == "platform" and name in platform_globals):
            continue
        candidates = {value.lower(): value for value in globals_set | (platform_globals if mode == "platform" else set())}
        if name.lower() in candidates:
            findings.append(Finding("error", "case-mismatch",
                f"`{name}()` uses the wrong case; current profile uses `{candidates[name.lower()]}()`.", "script"))
        else:
            findings.append(Finding("error" if mode == "engine" else "warn",
                "unknown-global" if mode == "engine" else "unverified-platform-global",
                f"Unknown global function `{name}()`." if mode == "engine" else
                f"`{name}()` 不在 bundled engine 或当前官方平台目录；需用目标版本证据确认。", "script"))
    return findings
