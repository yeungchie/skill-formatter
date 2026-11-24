"""Conservative SKILL parser.

The parser understands C-style calls, parenthesized lists, quoted forms and
the documented infix operators.  It intentionally refuses to guess: whenever a
construct is ambiguous or unsupported it raises ``Unsupported`` and the caller
keeps the whole top-level form byte-for-byte.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .ast import Node, sequence
from .lexer import Token


class ParseIssue(Exception):
    pass


class Unsupported(ParseIssue):
    pass


class OperatorHead(Unsupported):
    pass


class Context:
    CODE = "code"
    SYNTAX = "syntax"
    DATA = "data"
    TEMPLATE = "template"
    UNKNOWN = "unknown"


BINARY: dict[str, tuple[int, str]] = {
    "~>": (90, "left"),
    "->": (90, "left"),
    ".": (90, "left"),
    "**": (80, "right"),
    "*": (70, "left"),
    "/": (70, "left"),
    "+": (60, "left"),
    "-": (60, "left"),
    "<<": (55, "left"),
    ">>": (55, "left"),
    "<": (50, "left"),
    ">": (50, "left"),
    "<=": (50, "left"),
    ">=": (50, "left"),
    "==": (45, "left"),
    "!=": (45, "left"),
    "&": (40, "left"),
    "~&": (40, "left"),
    "^": (38, "left"),
    "~^": (38, "left"),
    "|": (36, "left"),
    "~|": (36, "left"),
    "&&": (30, "left"),
    "||": (25, "left"),
    ":": (20, "left"),
    "=": (10, "right"),
    "+=": (10, "right"),
    "-=": (10, "right"),
    "*=": (10, "right"),
    "/=": (10, "right"),
    "**=": (10, "right"),
    "|=": (10, "right"),
    "&=": (10, "right"),
}
ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "**=", "|=", "&="}
UNARY = {"!", "~", "-", "++", "--"}

SPECIAL_FORMS = {
    "procedure",
    "defmacro",
    "defmethod",
    "defclass",
    "lambda",
    "inScheme",
    "let",
    "letseq",
    "letrec",
    "prog",
    "progn",
    "if",
    "when",
    "unless",
    "while",
    "foreach",
    "for",
    "cond",
    "case",
    "errset",
    "unwindProtect",
    "setq",
}


def _is_number(text: str) -> bool:
    if not text:
        return False
    body = text[1:] if text[0] in "+-" else text
    if not body:
        return False
    try:
        float(body)
    except ValueError:
        return False
    return True


@dataclass(slots=True)
class ParseResult:
    root: Node
    warnings: list[str] = field(default_factory=list)
    opaque_spans: list[tuple[int, int]] = field(default_factory=list)


class Parser:
    def __init__(self, tokens: list[Token], source: str) -> None:
        self.tokens = tokens
        self.source = source
        self.i = 0
        self.warnings: list[str] = []
        self.opaque_spans: list[tuple[int, int]] = []

    # -- token helpers -------------------------------------------------
    def peek(self, offset: int = 0) -> Token:
        index = self.i + offset
        return self.tokens[index]

    def at(self, kind: str) -> bool:
        return self.peek().kind == kind

    def take(self) -> Token:
        token = self.peek()
        self.i += 1
        return token

    def at_end(self) -> bool:
        return self.at("eof")

    # -- top level -----------------------------------------------------
    def parse_file(self) -> ParseResult:
        items: list[Node] = []
        while not self.at_end():
            token = self.peek()
            if token.kind == "comment":
                items.append(self.comment_node())
                continue
            start = self.i
            try:
                node = self.parse_expr(Context.CODE)
                nxt = self.peek()
                prev = self.tokens[self.i - 1]
                if not self.at_end() and nxt.kind == "comment":
                    pass
                elif not self.at_end():
                    same_line = nxt.line == prev.line
                    if same_line and (
                        nxt.kind in {"lparen", "lbracket"}
                        or nxt.kind in {"atom", "prefix", "string", "unsupported"}
                    ):
                        raise Unsupported("adjacent expressions without an operator")
                items.append(node)
            except ParseIssue as exc:
                self.i = start
                end = self.scan_form_end(start)
                node = self.opaque_node(start, end, str(exc))
                items.append(node)
                self.i = end
        return ParseResult(sequence(items), self.warnings, self.opaque_spans)

    def scan_form_end(self, start: int) -> int:
        start_token = self.tokens[start]
        if start_token.kind == "unsupported":
            index = start + 1
            while index < len(self.tokens) and self.tokens[index].line == start_token.line:
                if self.tokens[index].kind == "eof":
                    break
                index += 1
            return index
        depth = 0
        need_operand = 0
        index = start
        while index < len(self.tokens):
            token = self.tokens[index]
            if token.kind == "eof":
                return index
            if token.kind == "comment":
                if depth == 0 and need_operand == 0 and index > start:
                    return index
                index += 1
                continue
            if token.kind == "prefix":
                need_operand += 1
                index += 1
                continue
            if token.kind in {"lparen", "lbracket", "lbrace"}:
                depth += 1
                index += 1
                continue
            if token.kind in {"rparen", "rbracket", "rbrace"}:
                depth = max(0, depth - 1)
                index += 1
                if depth == 0 and need_operand == 0:
                    return index
                continue
            if need_operand:
                need_operand -= 1
            index += 1
            if depth == 0 and need_operand == 0:
                nxt = self.tokens[index] if index < len(self.tokens) else None
                if (
                    nxt is not None
                    and nxt.kind in {"lparen", "lbracket"}
                    and nxt.line == token.line
                ):
                    index += 1
                    depth += 1
                    continue
                return index
        return len(self.tokens) - 1

    def opaque_node(self, start: int, end: int, reason: str) -> Node:
        first = self.tokens[start]
        last = self.tokens[max(start, end - 1)]
        if last.kind == "eof":
            last = self.tokens[max(start, end - 2)]
        self.warnings.append(f"line {first.line}: {reason}; left top-level form unchanged")
        self.opaque_spans.append((first.start, last.end))
        return Node(
            "opaque",
            value=self.source[first.start : last.end],
            start=first.start,
            end=last.end,
            line=first.line,
            blank_before=first.blank_before,
        )

    # -- expressions ---------------------------------------------------
    def parse_expr(self, context: str, min_prec: int = 0, allow_convert: bool = True) -> Node:
        left = self.parse_primary(context, allow_convert)

        while True:
            token = self.peek()
            if token.kind != "atom":
                break
            if token.text[:2] in {"->", "~>"} and len(token.text) > 2 and token.gap == "":
                self.take()
                rhs = self._atom_with_suffix(token.text[2:], token)
                left = Node(
                    "binary",
                    value=token.text[:2],
                    children=[left, rhs],
                    start=left.start,
                    end=rhs.end,
                    line=left.line,
                )
                continue
            leading_op = None
            for op in ("/", "*", "+", "-", "%", "&&", "||", "==", "!="):
                if token.text.startswith(op) and len(token.text) > len(op) and token.gap == "":
                    info = BINARY.get(op)
                    if info is None or info[0] < min_prec:
                        break
                    self.take()
                    rhs = self._atom_with_suffix(token.text[len(op) :], token)
                    left = Node(
                        "binary",
                        value=op,
                        children=[left, rhs],
                        start=left.start,
                        end=rhs.end,
                        line=left.line,
                    )
                    leading_op = op
                    break
            if leading_op is not None:
                continue
            if token.text in {"++", "--"} and token is not self.tokens[self.i - 1]:
                self.take()
                left = Node(
                    "postfix",
                    value=token.text,
                    children=[left],
                    start=left.start,
                    end=token.end,
                    line=left.line,
                )
                continue
            info = BINARY.get(token.text)
            if info is None:
                break
            prec, assoc = info
            if prec < min_prec:
                break
            self.take()
            next_min = prec if assoc == "right" else prec + 1
            right = self.parse_expr(context, next_min, allow_convert)
            kind = "assign" if token.text in ASSIGN_OPS else "binary"
            left = Node(
                kind,
                value=token.text,
                children=[left, right],
                start=left.start,
                end=right.end,
                line=left.line,
            )
        return left

    def parse_primary(self, context: str, allow_convert: bool) -> Node:
        token = self.peek()
        if token.kind == "comment":
            raise ParseIssue("comment in expression")
        if token.kind == "atom":
            if ("->" in token.text or "~>" in token.text) and token.text not in {"->", "~>"}:
                self.take()
                chain = self._atom_chain(token)
                if chain is not None:
                    return chain
                return Node(
                    "atom",
                    value=token.text,
                    start=token.start,
                    end=token.end,
                    line=token.line,
                    blank_before=token.blank_before,
                )
            if token.text in UNARY and token.text not in {"++", "--"}:
                if self._can_start(self.peek(1)):
                    self.take()
                    operand = self.parse_expr(context, 85, allow_convert)
                    return Node(
                        "unary",
                        value=token.text,
                        children=[operand],
                        start=token.start,
                        end=operand.end,
                        line=token.line,
                    )
            if token.text in {"++", "--"} and self._can_start(self.peek(1)):
                self.take()
                operand = self.parse_expr(context, 85, allow_convert)
                return Node(
                    "unary",
                    value=token.text,
                    children=[operand],
                    start=token.start,
                    end=operand.end,
                    line=token.line,
                )
            self.take()
            nxt = self.peek()
            if nxt.kind == "lparen" and nxt.gap == "":
                if token.text in BINARY or token.text in {"++", "--", "!"}:
                    raise OperatorHead(f"operator-headed call '{token.text}('")
                self.take()
                args = self.parse_args_for_head(token.text, "c")
                close = self.take()
                if close.kind != "rparen":
                    raise ParseIssue("expected ')'")
                return Node(
                    "call",
                    value=token.text,
                    children=args,
                    start=token.start,
                    end=close.end,
                    line=token.line,
                    blank_before=token.blank_before,
                    style="c",
                )
            if nxt.kind == "lbracket" and nxt.gap == "":
                self.take()
                index = self.parse_expr(Context.CODE, 0, allow_convert)
                close = self.take()
                if close.kind != "rbracket":
                    raise ParseIssue("expected ']'")
                atom = Node(
                    "atom",
                    value=token.text,
                    start=token.start,
                    end=token.end,
                    line=token.line,
                )
                return Node(
                    "index",
                    children=[atom, index],
                    start=token.start,
                    end=close.end,
                    line=token.line,
                )
            return Node(
                "atom",
                value=token.text,
                start=token.start,
                end=token.end,
                line=token.line,
                blank_before=token.blank_before,
            )

        if token.kind == "string":
            self.take()
            return Node(
                "string",
                value=token.text,
                start=token.start,
                end=token.end,
                line=token.line,
                blank_before=token.blank_before,
            )

        if token.kind == "prefix":
            self.take()
            if token.text in {"'", "`"}:
                sub_context = Context.DATA if token.text == "'" else Context.TEMPLATE
                operand = self.parse_expr(sub_context, 0, False)
            else:
                operand = self.parse_expr(Context.CODE, 0, True)
            return Node(
                "prefix",
                value=token.text,
                children=[operand],
                start=token.start,
                end=operand.end,
                line=token.line,
                blank_before=token.blank_before,
            )

        if token.kind == "lparen":
            return self.parse_paren(context, allow_convert)
        if token.kind == "lbracket":
            return self.parse_bracket(context)
        if token.kind == "lbrace":
            return self.parse_brace(context, allow_convert)
        if token.kind == "unsupported":
            raise Unsupported(token.unsupported or "unsupported token")
        raise ParseIssue(f"unexpected token {token.text!r}")

    def _can_start(self, token: Token) -> bool:
        return token.kind in {"atom", "string", "prefix", "lparen", "lbracket", "lbrace"}

    def _atom_chain(self, token: Token) -> Node | None:
        parts = re.split(r"(~>|->)", token.text)
        if len(parts) < 3 or any(part == "" for part in parts):
            return None
        left = Node(
            "atom",
            value=parts[0],
            start=token.start,
            end=token.start + len(parts[0]),
            line=token.line,
            blank_before=token.blank_before,
        )
        for index in range(1, len(parts), 2):
            op = parts[index]
            name = parts[index + 1]
            rhs = self._atom_with_suffix(name, token, attach=index + 2 == len(parts))
            left = Node(
                "binary",
                value=op,
                children=[left, rhs],
                start=left.start,
                end=rhs.end,
                line=left.line,
            )
        return left

    def _atom_with_suffix(self, name: str, token: Token, attach: bool = True) -> Node:
        base = Node(
            "atom",
            value=name,
            start=token.start,
            end=token.start + len(name),
            line=token.line,
        )
        if attach and self.peek().kind == "lparen" and self.peek().gap == "":
            self.take()
            args = self.parse_args_for_head(name, "c")
            close = self.take()
            if close.kind != "rparen":
                raise ParseIssue("expected ')'")
            return Node(
                "call",
                value=name,
                children=args,
                start=token.start,
                end=close.end,
                line=token.line,
                style="c",
            )
        if attach and self.peek().kind == "lbracket" and self.peek().gap == "":
            self.take()
            index = self.parse_expr(Context.CODE, 0, True)
            close = self.take()
            if close.kind != "rbracket":
                raise ParseIssue("expected ']'")
            return Node(
                "index",
                children=[base, index],
                start=token.start,
                end=close.end,
                line=token.line,
            )
        return base

    # -- lists ---------------------------------------------------------
    def parse_paren(self, context: str, allow_convert: bool) -> Node:
        open_tok = self.take()
        if context in {Context.CODE, Context.UNKNOWN}:
            if self._has_toplevel_binary():
                expr = self.parse_expr(Context.CODE, 0, allow_convert)
                close = self.take()
                if close.kind != "rparen":
                    raise ParseIssue("expected ')'")
                return Node(
                    "group",
                    children=[expr],
                    start=open_tok.start,
                    end=close.end,
                    line=open_tok.line,
                    blank_before=open_tok.blank_before,
                )
            if not allow_convert:
                return self.parse_plist_items(open_tok, Context.UNKNOWN)
            head_index = self.i
            while self.peek().kind == "comment":
                self.take()
            head_tok = self.peek()
            if head_tok.kind == "atom":
                if head_tok.text in BINARY or head_tok.text in UNARY:
                    raise OperatorHead(f"operator-headed list '({head_tok.text} ...'")
                if head_tok.text in {"t", "nil"} or _is_number(head_tok.text):
                    self.warnings.append(
                        f"line {head_tok.line}: parenthesized list with non-callable head "
                        f"'{head_tok.text}' kept as data"
                    )
                    self.i = head_index
                    return self.parse_plist_items(open_tok, Context.DATA)
                comments_before_head = self.i != head_index
                self.take()
                comments_after_head = self.peek().kind == "comment"
                if comments_before_head or comments_after_head:
                    self.warnings.append(
                        f"line {head_tok.line}: comment around S-style head prevents conversion"
                    )
                    self.i = head_index
                    return self.parse_plist_items(open_tok, Context.SYNTAX)
                args = self.parse_args_for_head(head_tok.text, "s")
                close = self.take()
                if close.kind != "rparen":
                    raise ParseIssue("expected ')'")
                return Node(
                    "call",
                    value=head_tok.text,
                    children=args,
                    start=open_tok.start,
                    end=close.end,
                    line=open_tok.line,
                    blank_before=open_tok.blank_before,
                    style="s",
                )
            self.i = head_index
            return self.parse_plist_items(open_tok, Context.DATA)
        if context in {Context.DATA, Context.TEMPLATE, Context.SYNTAX}:
            return self.parse_plist_items(open_tok, context)
        return self.parse_plist_items(open_tok, Context.UNKNOWN)

    def _has_toplevel_binary(self) -> bool:
        depth = 0
        index = self.i
        while index < len(self.tokens):
            token = self.tokens[index]
            if token.kind == "eof":
                return False
            if token.kind in {"lparen", "lbracket", "lbrace"}:
                depth += 1
            elif token.kind in {"rparen", "rbracket", "rbrace"}:
                if depth == 0:
                    return False
                depth -= 1
            elif depth == 0 and token.kind == "atom" and token.text in BINARY:
                return True
            index += 1
        return False

    def parse_plist_items(self, open_tok: Token, context: str) -> Node:
        items: list[Node] = []
        while not self.at("rparen"):
            if self.at_end():
                raise ParseIssue("unterminated parenthesized list")
            if self.peek().kind == "comment":
                items.append(self.comment_node())
                continue
            items.append(self.parse_data_item(context))
        close = self.take()
        return Node(
            "plist",
            value="(",
            children=items,
            start=open_tok.start,
            end=close.end,
            line=open_tok.line,
            blank_before=open_tok.blank_before,
            meta={"context": context},
        )

    def parse_bracket(self, context: str) -> Node:
        open_tok = self.take()
        items: list[Node] = []
        while not self.at("rbracket"):
            if self.at_end():
                raise ParseIssue("unterminated bracket list")
            if self.peek().kind == "comment":
                items.append(self.comment_node())
            else:
                items.append(self.parse_data_item(Context.DATA))
        close = self.take()
        return Node(
            "plist",
            value="[",
            children=items,
            start=open_tok.start,
            end=close.end,
            line=open_tok.line,
            blank_before=open_tok.blank_before,
            meta={"context": Context.DATA},
        )

    def parse_brace(self, context: str, allow_convert: bool) -> Node:
        open_tok = self.take()
        items: list[Node] = []
        while not self.at("rbrace"):
            if self.at_end():
                raise ParseIssue("unterminated brace list")
            if self.peek().kind == "comment":
                items.append(self.comment_node())
            elif context == Context.CODE and allow_convert:
                items.append(self.parse_expr(Context.CODE, 0, True))
            else:
                items.append(self.parse_data_item(context))
        close = self.take()
        return Node(
            "plist",
            value="{",
            children=items,
            start=open_tok.start,
            end=close.end,
            line=open_tok.line,
            blank_before=open_tok.blank_before,
            meta={"context": context},
        )

    def parse_data_item(self, context: str) -> Node:
        token = self.peek()
        if token.kind == "atom":
            self.take()
            nxt = self.peek()
            if nxt.kind == "lparen" and nxt.gap == "":
                if token.text in BINARY or token.text in UNARY:
                    raise OperatorHead(f"operator-headed call '{token.text}('")
                self.take()
                args = self.parse_args_for_head(token.text, "c")
                close = self.take()
                if close.kind != "rparen":
                    raise ParseIssue("expected ')'")
                return Node(
                    "call",
                    value=token.text,
                    children=args,
                    start=token.start,
                    end=close.end,
                    line=token.line,
                    blank_before=token.blank_before,
                    style="c",
                )
            return Node(
                "atom",
                value=token.text,
                start=token.start,
                end=token.end,
                line=token.line,
                blank_before=token.blank_before,
            )
        if token.kind == "string":
            self.take()
            return Node(
                "string",
                value=token.text,
                start=token.start,
                end=token.end,
                line=token.line,
                blank_before=token.blank_before,
            )
        if token.kind == "prefix":
            self.take()
            operand = self.parse_data_item(context)
            return Node(
                "prefix",
                value=token.text,
                children=[operand],
                start=token.start,
                end=operand.end,
                line=token.line,
                blank_before=token.blank_before,
            )
        if token.kind == "lparen":
            open_tok = self.take()
            return self.parse_plist_items(open_tok, context)
        if token.kind == "lbracket":
            return self.parse_bracket(context)
        if token.kind == "lbrace":
            return self.parse_brace(context, False)
        if token.kind == "unsupported":
            raise Unsupported(token.unsupported or "unsupported token")
        raise ParseIssue(f"unexpected token {token.text!r}")

    # -- special argument roles ---------------------------------------
    def parse_args_for_head(self, head: str, style: str) -> list[Node]:
        def take_comments(into: list[Node]) -> None:
            while self.peek().kind == "comment":
                into.append(self.comment_node())

        if head == "cond":
            return self._parse_clauses(first_is_data=False)
        if head == "case":
            args = [self.parse_expr(Context.CODE, 0, True)]
            args.extend(self._parse_clauses(first_is_data=True))
            return args
        if head in {"let", "letseq", "letrec", "prog"}:
            args: list[Node] = [self._parse_bindings()]
            take_comments(args)
            args.extend(self._parse_exprs(Context.CODE, True))
            return args
        if head == "procedure":
            args = [self._parse_callspec()]
            take_comments(args)
            if self.peek().kind == "string":
                args.append(self.parse_data_item(Context.DATA))
            take_comments(args)
            args.extend(self._parse_exprs(Context.CODE, True))
            return args
        if head == "defmacro":
            args = [self.parse_data_item(Context.DATA)]
            take_comments(args)
            args.append(self.parse_data_item(Context.DATA))
            take_comments(args)
            args.extend(self._parse_exprs(Context.CODE, True))
            return args
        if head == "defmethod":
            args = [self.parse_data_item(Context.DATA)]
            take_comments(args)
            args.append(self.parse_data_item(Context.DATA))
            take_comments(args)
            args.extend(self._parse_exprs(Context.CODE, True))
            return args
        if head == "defclass":
            args = [
                self.parse_data_item(Context.DATA),
            ]
            take_comments(args)
            args.append(self.parse_data_item(Context.DATA))
            take_comments(args)
            args.append(self.parse_data_item(Context.DATA))
            take_comments(args)
            args.extend(self._parse_data_items())
            return args
        if head == "lambda":
            args = [self.parse_data_item(Context.DATA)]
            take_comments(args)
            args.extend(self._parse_exprs(Context.CODE, True))
            return args
        if head == "foreach":
            args = [self.parse_data_item(Context.DATA)]
            take_comments(args)
            args.extend(self._parse_exprs(Context.CODE, True))
            return args
        if head == "for":
            args = [self.parse_data_item(Context.DATA)]
            take_comments(args)
            args.extend(self._parse_exprs(Context.CODE, True))
            return args
        if head in {
            "inScheme",
            "progn",
            "errset",
            "unwindProtect",
            "if",
            "when",
            "unless",
            "while",
            "setq",
        }:
            return self._parse_exprs(Context.CODE, True)
        return self._parse_exprs(Context.UNKNOWN, False)

    def _parse_exprs(self, context: str, allow_convert: bool) -> list[Node]:
        items: list[Node] = []
        while not self.at("rparen"):
            if self.at_end():
                raise ParseIssue("unterminated call")
            if self.peek().kind == "comment":
                items.append(self.comment_node())
            else:
                items.append(self.parse_expr(context, 0, allow_convert))
        return items

    def _parse_data_items(self) -> list[Node]:
        items: list[Node] = []
        while not self.at("rparen"):
            if self.at_end():
                raise ParseIssue("unterminated call")
            if self.peek().kind == "comment":
                items.append(self.comment_node())
            else:
                items.append(self.parse_data_item(Context.DATA))
        return items

    def _parse_bindings(self) -> Node:
        if not self.at("lparen"):
            return self.parse_data_item(Context.DATA)
        open_tok = self.take()
        items: list[Node] = []
        while not self.at("rparen"):
            if self.at_end():
                raise ParseIssue("unterminated bindings")
            if self.peek().kind == "comment":
                items.append(self.comment_node())
                continue
            if self.at("lparen"):
                binding_open = self.take()
                binding_items = [self.parse_data_item(Context.DATA)]
                while not self.at("rparen"):
                    if self.at_end():
                        raise ParseIssue("unterminated binding")
                    if self.peek().kind == "comment":
                        binding_items.append(self.comment_node())
                    else:
                        binding_items.append(self.parse_expr(Context.CODE, 0, True))
                binding_close = self.take()
                items.append(
                    Node(
                        "plist",
                        value="(",
                        children=binding_items,
                        start=binding_open.start,
                        end=binding_close.end,
                        line=binding_open.line,
                    )
                )
            else:
                items.append(self.parse_data_item(Context.DATA))
        close = self.take()
        return Node(
            "plist",
            value="(",
            children=items,
            start=open_tok.start,
            end=close.end,
            line=open_tok.line,
            meta={"context": "bindings"},
        )

    def _parse_callspec(self) -> Node:
        if not self.at("lparen"):
            return self.parse_data_item(Context.DATA)
        open_tok = self.take()
        name = self.parse_data_item(Context.DATA)
        formals: list[Node] = []
        while not self.at("rparen"):
            if self.at_end():
                raise ParseIssue("unterminated function spec")
            if self.peek().kind == "comment":
                formals.append(self.comment_node())
            else:
                formals.append(self.parse_data_item(Context.DATA))
        close = self.take()
        if name.kind == "atom":
            return Node(
                "call",
                value=name.value,
                children=formals,
                start=open_tok.start,
                end=close.end,
                line=open_tok.line,
                style="c",
            )
        return Node(
            "plist",
            value="(",
            children=[name, *formals],
            start=open_tok.start,
            end=close.end,
            line=open_tok.line,
        )

    def _parse_clauses(self, first_is_data: bool) -> list[Node]:
        clauses: list[Node] = []
        while not self.at("rparen"):
            if self.at_end():
                raise ParseIssue("unterminated clause list")
            if self.peek().kind == "comment":
                clauses.append(self.comment_node())
                continue
            if not self.at("lparen"):
                clauses.append(self.parse_expr(Context.CODE, 0, True))
                continue
            open_tok = self.take()
            items: list[Node] = []
            if self.at("rparen"):
                close = self.take()
                clauses.append(
                    Node(
                        "plist",
                        value="(",
                        children=items,
                        start=open_tok.start,
                        end=close.end,
                        line=open_tok.line,
                    )
                )
                continue
            if first_is_data:
                items.append(self.parse_data_item(Context.DATA))
            else:
                items.append(self.parse_expr(Context.CODE, 0, True))
            while not self.at("rparen"):
                if self.at_end():
                    raise ParseIssue("unterminated clause")
                if self.peek().kind == "comment":
                    items.append(self.comment_node())
                else:
                    items.append(self.parse_expr(Context.CODE, 0, True))
            close = self.take()
            clauses.append(
                Node(
                    "plist",
                    value="(",
                    children=items,
                    start=open_tok.start,
                    end=close.end,
                    line=open_tok.line,
                    meta={"context": "clause"},
                )
            )
        return clauses

    def comment_node(self) -> Node:
        token = self.take()
        return Node(
            "comment",
            value=token.text,
            start=token.start,
            end=token.end,
            line=token.line,
            blank_before=token.blank_before,
            inline=token.inline,
        )
