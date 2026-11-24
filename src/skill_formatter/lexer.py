"""Tokenizer for SKILL source.

The lexer is deliberately conservative.  Atom boundaries are never invented:
operators are only split when they are written as standalone, whitespace
separated atoms.  Anything the lexer cannot classify is emitted as an
``unsupported`` token so the parser can leave the enclosing top-level form
byte-for-byte unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass


class LexError(Exception):
    def __init__(self, message: str, line: int, col: int) -> None:
        super().__init__(f"{message} at line {line}, column {col}")
        self.message = message
        self.line = line
        self.col = col


@dataclass(slots=True)
class Token:
    kind: str
    text: str
    start: int
    end: int
    line: int
    col: int
    gap: str = ""
    newlines: int = 0
    blank_before: int = 0
    inline: bool = False
    unsupported: str | None = None


@dataclass(slots=True)
class LexResult:
    tokens: list[Token]
    eol: str
    final_newline: bool


DELIMITERS = set('()[]{}";')
PREFIXES = ("'", "`", ",@", ",", "#.")


def _count_blank(gap: str) -> tuple[int, int]:
    newlines = gap.count("\n")
    return newlines, max(0, newlines - 1)


def lex(text: str) -> LexResult:
    if "\x00" in text:
        index = text.index("\x00")
        line = text.count("\n", 0, index) + 1
        col = index - text.rfind("\n", 0, index)
        raise LexError("NUL byte in source", line, col)

    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    eol = "\r\n" if crlf > lf else "\n"
    final_newline = text.endswith(("\n", "\r"))

    tokens: list[Token] = []
    pos = 0
    line = 1
    col = 1
    gap = ""
    length = len(text)

    def advance(chunk: str) -> None:
        nonlocal line, col
        newlines = chunk.count("\n")
        if newlines:
            line += newlines
            col = len(chunk) - chunk.rfind("\n")
        else:
            col += len(chunk)

    def push(kind: str, start: int, end: int, start_line: int, start_col: int) -> None:
        nonlocal gap
        newlines, blank = _count_blank(gap)
        tokens.append(
            Token(
                kind=kind,
                text=text[start:end],
                start=start,
                end=end,
                line=start_line,
                col=start_col,
                gap=gap,
                newlines=newlines,
                blank_before=blank,
                inline=(kind == "comment" and newlines == 0 and bool(tokens)),
            )
        )
        gap = ""

    while pos < length:
        ch = text[pos]
        if ch in " \t\r\n":
            start = pos
            while pos < length and text[pos] in " \t\r\n":
                pos += 1
            chunk = text[start:pos]
            gap += chunk
            advance(chunk)
            continue

        start = pos
        start_line, start_col = line, col

        if ch == ";":
            pos += 1
            while pos < length and text[pos] not in "\r\n":
                pos += 1
            push("comment", start, pos, start_line, start_col)
            advance(text[start:pos])
            continue

        if ch == '"':
            pos += 1
            escaped = False
            while pos < length:
                cur = text[pos]
                if escaped:
                    escaped = False
                elif cur == "\\":
                    escaped = True
                elif cur == '"':
                    pos += 1
                    break
                pos += 1
            else:
                raise LexError("unterminated string", start_line, start_col)
            push("string", start, pos, start_line, start_col)
            advance(text[start:pos])
            continue

        matched_prefix = None
        for prefix in PREFIXES:
            if text.startswith(prefix, pos):
                matched_prefix = prefix
                break
        if matched_prefix is not None:
            pos += len(matched_prefix)
            push("prefix", start, pos, start_line, start_col)
            advance(matched_prefix)
            continue

        if text.startswith("/*", pos):
            end = text.find("*/", pos + 2)
            pos = length if end < 0 else end + 2
            kind = "unsupported"
            push(kind, start, pos, start_line, start_col)
            tokens[-1].unsupported = "block comment"
            advance(text[start:pos])
            continue

        if ch == "#":
            pos += 1
            while pos < length and text[pos] not in DELIMITERS and text[pos] not in " \t\r\n":
                pos += 1
            push("unsupported", start, pos, start_line, start_col)
            tokens[-1].unsupported = "unknown # reader syntax"
            advance(text[start:pos])
            continue

        if ch == "|":
            if text.startswith("||", pos):
                pos += 2
                push("atom", start, pos, start_line, start_col)
                advance("||")
                continue
            closing = text.find("|", pos + 1)
            newline = text.find("\n", pos + 1)
            if closing < 0 or (newline >= 0 and closing > newline):
                pos += 1
                push("atom", start, pos, start_line, start_col)
                advance("|")
                continue
            pos += 1
            while pos < length and text[pos] != "|" and text[pos] not in "\r\n":
                pos += 1
            if pos < length and text[pos] == "|":
                pos += 1
            push("unsupported", start, pos, start_line, start_col)
            tokens[-1].unsupported = "quoted symbol syntax"
            advance(text[start:pos])
            continue

        if ch in "([{":
            pos += 1
            kind = {"(": "lparen", "[": "lbracket", "{": "lbrace"}[ch]
            push(kind, start, pos, start_line, start_col)
            advance(ch)
            continue
        if ch in ")]}":
            pos += 1
            kind = {")": "rparen", "]": "rbracket", "}": "rbrace"}[ch]
            push(kind, start, pos, start_line, start_col)
            advance(ch)
            continue

        pos += 1
        while pos < length:
            cur = text[pos]
            if cur in DELIMITERS or cur in " \t\r\n":
                break
            pos += 1
        atom = text[start:pos]
        push("atom", start, pos, start_line, start_col)
        advance(atom)
        if atom.endswith("\\") and pos < length and text[pos] in "\r\n":
            tokens[-1].kind = "unsupported"
            tokens[-1].unsupported = "line continuation"

    newlines, blank = _count_blank(gap)
    tokens.append(
        Token(
            kind="eof",
            text="",
            start=length,
            end=length,
            line=line,
            col=col,
            gap=gap,
            newlines=newlines,
            blank_before=blank,
        )
    )
    return LexResult(tokens=tokens, eol=eol, final_newline=final_newline)
