"""Layout engine and public formatting entry points."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .ast import Node
from .lexer import LexError, LexResult, lex
from .options import Options
from .parser import ParseIssue, Parser


class FormatError(Exception):
    pass


@dataclass(slots=True)
class FormatResult:
    text: str
    changed: bool
    warnings: list[str]
    opaque_spans: list[tuple[int, int]]


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


FOREACH_MODIFIERS = frozenset({"map", "mapc", "mapcar", "mapcan", "maplist", "mapcon"})


class LineBuilder:
    def __init__(self, indent: int = 0) -> None:
        self.lines: list[str] = []
        self.current = " " * indent

    def write(self, text: str) -> None:
        self.current += text

    def newline(self, indent: int = 0) -> None:
        if self.current.strip():
            self.lines.append(self.current.rstrip())
        self.current = " " * indent

    def blankline(self, indent: int = 0) -> None:
        self.newline(indent)
        self.lines.append("")
        self.current = " " * indent

    def raw_line(self, text: str) -> None:
        self.lines.append(text)

    def finish(self) -> list[str]:
        if self.current.strip() or not self.lines:
            self.lines.append(self.current.rstrip())
        return self.lines


class Renderer:
    def __init__(self, options: Options) -> None:
        self.options = options
        self.out = LineBuilder(options.base_indent or 0)
        self.reserve = 0
        self.node_info: dict[int, tuple[int, int, int]] = {}

    # -- public --------------------------------------------------------
    def render_root(self, root: Node) -> list[str]:
        self.render(root, self.options.base_indent or 0, top=True)
        return self.out.finish()

    def render_node(self, node: Node, indent: int) -> list[str]:
        self.render(node, indent)
        return self.out.finish()

    def render(self, node: Node, indent: int, top: bool = False) -> None:
        start_line = len(self.out.lines)
        if node.kind == "seq":
            self._render_block(node.children, indent)
        elif node.kind in {"atom", "string"}:
            self.out.write(node.value)
        elif node.kind == "comment":
            self._render_comment(node, indent)
        elif node.kind == "opaque":
            self._render_opaque(node, indent)
        elif node.kind == "plist":
            self._render_plist(node, indent)
        elif node.kind == "group":
            self.out.write("(")
            self.render(node.children[0], indent)
            self.out.write(")")
        elif node.kind == "call":
            self._render_call(node, indent)
        elif node.kind == "index":
            self._render_index(node, indent)
        elif node.kind == "prefix":
            self.out.write(node.value)
            self.render(node.children[0], indent)
        elif node.kind in {"unary", "postfix"}:
            flat = self.flat(node)
            if flat is not None and self._fits(flat):
                self.out.write(flat)
            elif node.kind == "postfix":
                self.reserve += len(node.value)
                try:
                    self.render(node.children[0], indent)
                finally:
                    self.reserve -= len(node.value)
                self.out.write(node.value)
            else:
                self.out.write(node.value)
                if self._unary_needs_parens(node.children[0]):
                    self.out.write("(")
                    self.render(node.children[0], indent)
                    self.out.write(")")
                else:
                    self.render(node.children[0], indent)
        elif node.kind in {"binary", "assign"}:
            self._render_binary(node, indent)
        else:
            self.out.write(node.value)
        end_line = len(self.out.lines)
        if self.out.current.strip():
            end_line = len(self.out.lines)
        self.node_info[id(node)] = (start_line, end_line, indent)

    # -- primitives ----------------------------------------------------
    def _fits(self, text: str) -> bool:
        if "\n" in text:
            return False
        return len(self.out.current) + len(text) + self.reserve <= self.options.width

    def _flat_if_fits(self, node: Node) -> str | None:
        flat = self.flat(node)
        if flat is None or not self._fits(flat):
            return None
        return flat

    def _unary_needs_parens(self, node: Node) -> bool:
        return node.kind in {"binary", "assign", "call", "plist"}

    def _render_comment(self, node: Node, indent: int) -> None:
        if node.inline and self.out.current.strip():
            self.out.write("  " + node.value)
            self.out.newline(indent)
            return
        if self.out.current.strip():
            self.out.newline(indent)
        self.out.write(node.value)
        self.out.newline(indent)

    def _render_opaque(self, node: Node, indent: int) -> None:
        parts = node.value.splitlines() or [""]
        self.out.write(parts[0])
        for part in parts[1:]:
            self.out.newline(0)
            self.out.write(part)

    def _render_block(self, children: list[Node], indent: int) -> None:
        first = True
        previous_non_comment: Node | None = None
        index = 0
        while index < len(children):
            child = children[index]
            if child.kind == "comment" and child.inline:
                self.out.write("  " + child.value)
                first = False
                index += 1
                continue
            if not first or self.out.current.strip():
                self.out.newline(indent)
            blanks = 0
            definition_needs_two = False
            if not first:
                leading_comment = False
                if child.kind == "comment":
                    for later in children[index + 1 :]:
                        if later.kind != "comment":
                            leading_comment = self._is_definition(later)
                            break
                definition_needs_two = (
                    self.options.enabled("blank-lines")
                    and previous_non_comment is not None
                    and self._is_definition(previous_non_comment)
                    and (self._is_definition(child) or leading_comment)
                )
                if definition_needs_two:
                    blanks = 2
                elif child.blank_before:
                    blanks = 1 if self.options.enabled("blank-lines") else child.blank_before
            if blanks:
                self.out.lines.extend([""] * blanks)
            if self.options.enabled("align-assignments") and self._is_assignment(child):
                rows, end = self._assignment_rows(children, index)
                if len(rows) > 1:
                    if not self._render_aligned_assignments(rows, indent):
                        self._render_assignment_rows(rows, indent)
                    previous_non_comment = rows[-1][0]
                    first = False
                    index = end
                    continue
            self.render(child, indent)
            if definition_needs_two and child.kind == "comment":
                previous_non_comment = None
            elif child.kind != "comment":
                previous_non_comment = child
            first = False
            index += 1
        if children and self.out.current.strip():
            self.out.newline(indent)

    def _is_assignment(self, node: Node) -> bool:
        return node.kind == "assign" and node.value == "="

    def _assignment_rows(
        self, children: list[Node], start: int
    ) -> tuple[list[tuple[Node, Node | None]], int]:
        rows: list[tuple[Node, Node | None]] = []
        index = start
        while index < len(children):
            node = children[index]
            if not self._is_assignment(node):
                break
            if rows and node.blank_before:
                break
            comment: Node | None = None
            index += 1
            if (
                index < len(children)
                and children[index].kind == "comment"
                and children[index].inline
            ):
                comment = children[index]
                index += 1
            rows.append((node, comment))
        return rows, index

    def _render_aligned_assignments(
        self, rows: list[tuple[Node, Node | None]], indent: int
    ) -> bool:
        parts: list[tuple[str, str, Node | None]] = []
        for node, comment in rows:
            left = self.flat(node.children[0])
            right = self.flat(node.children[1])
            if left is None or right is None:
                return False
            parts.append((left, right, comment))
        left_width = max(len(left) for left, _, _ in parts)
        bodies = [f"{left.ljust(left_width)} = {right}" for left, right, _ in parts]
        comment_col = max(len(body) for body in bodies) + 2
        lines: list[str] = []
        for body, (_, _, comment) in zip(bodies, parts, strict=True):
            padding = "" if comment is None else " " * (comment_col - len(body))
            line = body + padding + ("" if comment is None else comment.value)
            if indent + len(line) > self.options.width:
                return False
            lines.append(line)
        for i, line in enumerate(lines):
            if i:
                self.out.newline(indent)
            self.out.write(line)
        return True

    def _render_assignment_rows(self, rows: list[tuple[Node, Node | None]], indent: int) -> None:
        for i, (node, comment) in enumerate(rows):
            if i:
                self.out.newline(indent)
            self.render(node, indent)
            if comment is not None:
                self.out.write("  " + comment.value)

    def _is_definition(self, node: Node) -> bool:
        return node.kind == "call" and node.value in {
            "procedure",
            "defmacro",
            "defmethod",
            "defclass",
        }

    def _render_plist(self, node: Node, indent: int) -> None:
        meta = node.meta.get("context")
        if meta == "bindings":
            self._render_bindings(node, indent)
            return
        if meta == "clause":
            self._render_clause(node, indent)
            return
        flat = self.flat(node)
        if flat is not None and self._fits(flat):
            self.out.write(flat)
            return
        delim = node.value
        if delim == "[":
            self.out.write(self._flat_force(node) or "[]")
            return
        if delim == "{":
            self.out.write("{")
            if node.children:
                self.out.newline(indent + self.options.indent)
                self._render_block(node.children, indent + self.options.indent)
            self.out.newline(indent)
            self.out.write("}")
            return
        self.out.write("(")
        align = len(self.out.current)
        if node.children:
            self.out.newline(align)
            self._render_block(node.children, align)
        self.out.newline(indent)
        self.out.write(")")

    def _render_clause(self, node: Node, indent: int) -> None:
        flat = self.flat(node)
        items = node.children
        body = items[1:]
        simple_body = len(body) == 1 and body[0].kind != "assign"
        if body and body[0].kind == "plist" and body[0].value == "{" and len(body[0].children) > 1:
            simple_body = False
        if flat is not None and simple_body and self._fits(flat):
            self.out.write(flat)
            return
        self.out.write("(")
        if not items:
            self.out.write(")")
            return
        self.out.write(self._inner_pad())
        self.render(items[0], indent)
        if len(items) > 1:
            self.out.newline(indent + self.options.indent)
            self._render_block(items[1:], indent + self.options.indent)
        self.out.newline(indent)
        self.out.write(")")

    def _render_bindings(self, node: Node, indent: int) -> None:
        flat = self.flat(node)
        if flat is not None and self._fits(flat):
            self.out.write(flat)
            return
        self.out.write("(")
        align = len(self.out.current)
        if node.children:
            self.out.newline(align)
            self._render_block(node.children, align)
        self.out.newline(indent)
        self.out.write(")")

    def _render_binary(self, node: Node, indent: int) -> None:
        if node.value in {"->", "~>"}:
            right_flat = self.flat(node.children[1])
            reserve = len(node.value) + (len(right_flat) if right_flat is not None else 0)
            self.reserve += reserve
            try:
                self.render(node.children[0], indent)
            finally:
                self.reserve -= reserve
            self.out.write(node.value)
            self.render(node.children[1], indent)
            return
        flat = self.flat(node)
        if flat is not None and self._fits(flat):
            self.out.write(flat)
            return
        left, right = node.children
        if node.kind == "assign":
            self.render(left, indent)
            self.out.write(" " + node.value + " ")
            self.render(right, indent)
        else:
            self.render(left, indent)
            self.out.newline(indent + self.options.indent)
            tight = node.value in {"->", "~>"}
            self.out.write(node.value + ("" if tight else " "))
            self.render(right, indent + self.options.indent)

    def _render_index(self, node: Node, indent: int) -> None:
        base, index = node.children
        index_flat = self.flat(index)
        pad = self._inner_pad() if index_flat else ""
        reserve = len(index_flat) + 2 + 2 * len(pad) if index_flat is not None else 1
        self.reserve += reserve
        try:
            self.render(base, indent)
        finally:
            self.reserve -= reserve
        self.out.write("[" + pad)
        if index_flat is not None and self._fits(index_flat + pad + "]"):
            self.out.write(index_flat + pad)
        else:
            self.render(index, indent)
        self.out.write("]")

    # -- calls ---------------------------------------------------------
    def _render_call(self, node: Node, indent: int) -> None:
        head = node.value
        if not node.children:
            self.out.write(head + "()")
        elif head in {"procedure", "defmacro", "defmethod"}:
            self._render_definition(node, indent)
        elif head == "defclass":
            self._render_defclass(node, indent)
        elif head in {"let", "letseq", "letrec", "prog"}:
            self._render_let(node, indent)
        elif head in {"cond", "case"}:
            self._render_cond(node, indent)
        elif head == "if":
            self._render_if(node, indent)
        elif head == "inScheme":
            self._render_in_scheme(node, indent)
        elif head == "lambda":
            self._render_lambda(node, indent)
        elif head in {
            "progn",
            "unless",
            "when",
            "while",
            "foreach",
            "for",
            "unwindProtect",
            "setq",
        }:
            self._render_control(node, indent)
        else:
            self._render_generic_call(node, indent)

    def _render_definition(self, node: Node, indent: int) -> None:
        args = node.children
        if not args:
            self.out.write(node.value + "()")
            return
        if node.value == "procedure":
            sig = args[:1]
            rest = args[1:]
            if rest and rest[0].kind == "string":
                sig.append(rest[0])
                rest = rest[1:]
        else:
            sig = args[:2]
            rest = args[2:]
        inline: list[Node] = []
        while rest and rest[0].kind == "comment" and rest[0].inline:
            inline.append(rest.pop(0))
        sig_flat = " ".join(self.flat(a) or "" for a in sig if a.kind != "comment")
        body = rest
        pad = self._inner_pad() if sig_flat else ""
        self.out.write(node.value + "(" + pad + sig_flat)
        for comment in inline:
            self.out.write("  " + comment.value)
        if not body:
            self.out.write(")" if inline else pad + ")")
            return
        if body:
            self.out.newline(indent + self.options.indent)
            self._render_block(body, indent + self.options.indent)
        self.out.newline(indent)
        self.out.write(")")

    def _render_defclass(self, node: Node, indent: int) -> None:
        args = node.children
        name = self.flat(args[0]) if args else ""
        supers = self.flat(args[1]) if len(args) > 1 else "()"
        slots = args[2] if len(args) > 2 else None
        pad = self._inner_pad()
        head = f"defclass({pad}{name} {supers}"
        if slots is None or not slots.children:
            self.out.write(head + " ()" + pad + ")")
            return
        self.out.write(head + " (")
        self.out.newline(indent + self.options.indent)
        first = True
        for slot in slots.children:
            if isinstance(slot, Node) and slot.kind == "comment":
                if slot.inline:
                    self.out.write("  " + slot.value)
                    continue
            if not first:
                self.out.newline(indent + self.options.indent)
            self._render_slot(slot, indent + self.options.indent)
            first = False
        self.out.newline(indent)
        self.out.write("))")

    def _render_slot(self, node: Node, indent: int) -> None:
        if node.kind == "call" and node.children:
            self.out.write(node.value + "(")
            self.out.newline(indent + self.options.indent)
            args = node.children
            index = 0
            first = True
            while index < len(args):
                arg = args[index]
                if not first:
                    self.out.newline(indent + self.options.indent)
                if arg.kind == "atom" and arg.value.startswith("\\@") and index + 1 < len(args):
                    nxt = self.flat(args[index + 1])
                    if nxt is not None:
                        self.out.write(arg.value + " " + nxt)
                        index += 2
                        first = False
                        continue
                self.render(arg, indent + self.options.indent)
                index += 1
                first = False
            self.out.newline(indent)
            self.out.write(")")
        else:
            self.render(node, indent)

    def _render_let(self, node: Node, indent: int) -> None:
        flat = self.flat(node)
        if flat is not None and self._fits(flat):
            self.out.write(flat)
            return
        args = node.children
        self.out.write(node.value + "(")
        if node.value in self.options.hanging:
            self.out.write(self._inner_pad())
            self._render_bindings(args[0], indent)
        else:
            self.out.newline(indent + self.options.indent)
            self._render_bindings(args[0], indent + self.options.indent)
        body = args[1:]
        if body:
            self.out.newline(indent + self.options.indent)
            self._render_block(body, indent + self.options.indent)
        self.out.newline(indent)
        self.out.write(")")

    def _render_cond(self, node: Node, indent: int) -> None:
        flat = self.flat(node)
        if flat is not None and self._fits(flat):
            self.out.write(flat)
            return
        args = node.children
        self.out.write(node.value + "(")
        clauses: list[Node]
        if node.value == "case" and args:
            first = self._flat_if_fits(args[0])
            if first is None or node.value not in self.options.hanging:
                self.out.newline(indent + self.options.indent)
                self.render(args[0], indent + self.options.indent)
            else:
                self.out.write(self._inner_pad() + first)
            clauses = args[1:]
        else:
            clauses = args
        if clauses:
            self.out.newline(indent + self.options.indent)
            if node.value == "case":
                self._render_case_clauses(clauses, indent + self.options.indent)
            else:
                for index, clause in enumerate(clauses):
                    if index:
                        self.out.newline(indent + self.options.indent)
                    self.render(clause, indent + self.options.indent)
        self.out.newline(indent)
        self.out.write(")")

    def _render_case_clauses(self, clauses: list[Node], indent: int) -> None:
        if self.options.case_mode == "align":
            heads: list[str] = []
            bodies: list[str] = []
            can_align = True
            for clause in clauses:
                if clause.kind != "plist" or len(clause.children) != 2:
                    can_align = False
                    break
                h = self.flat(clause.children[0])
                b = self.flat(clause.children[1])
                if h is None or b is None:
                    can_align = False
                    break
                heads.append(h)
                bodies.append(b)
            if can_align:
                width = max((len(h) for h in heads), default=0)
                for i, (head, body) in enumerate(zip(heads, bodies, strict=True)):
                    if i:
                        self.out.newline(indent)
                    left, right = self._pad_pair(head + body)
                    self.out.write(
                        "(" + left + head + " " * (width - len(head) + 1) + body + right + ")"
                    )
                return
        for i, clause in enumerate(clauses):
            if i:
                self.out.newline(indent)
            self.render(clause, indent)

    def _render_if(self, node: Node, indent: int) -> None:
        args = node.children
        markers = [
            i for i, arg in enumerate(args) if arg.kind == "atom" and arg.value in {"then", "else"}
        ]
        if not markers:
            flat = self.flat(node)
            if flat is not None and self._fits(flat):
                self.out.write(flat)
                return
            self.out.write("if(")
            if args:
                cond = self._flat_if_fits(args[0])
                if cond is None or "if" not in self.options.hanging:
                    self.out.newline(indent + self.options.indent)
                    self.render(args[0], indent + self.options.indent)
                else:
                    self.out.write(self._inner_pad() + cond)
            rest = args[1:]
            if rest:
                self.out.newline(indent + self.options.indent)
                self._render_block(rest, indent + self.options.indent)
            self.out.newline(indent)
            self.out.write(")")
            return
        self.out.write("if(")
        cond = self._flat_if_fits(args[0])
        if cond is None or "if" not in self.options.hanging:
            self.out.newline(indent + self.options.indent)
            self.render(args[0], indent + self.options.indent)
            self.out.newline(indent)
        else:
            self.out.write(self._inner_pad() + cond)
        index = 1
        while index < len(args):
            arg = args[index]
            if arg.kind == "atom" and arg.value in {"then", "else"}:
                self.out.newline(indent)
                self.out.write(arg.value)
                index += 1
                branch: list[Node] = []
                while index < len(args) and not (
                    args[index].kind == "atom" and args[index].value in {"then", "else"}
                ):
                    branch.append(args[index])
                    index += 1
                if branch:
                    self.out.newline(indent + self.options.indent)
                    self._render_block(branch, indent + self.options.indent)
                continue
            index += 1
        self.out.newline(indent)
        self.out.write(")")

    def _render_in_scheme(self, node: Node, indent: int) -> None:
        self.out.write("inScheme(")
        body_indent = indent if self.options.in_scheme == "flat" else indent + self.options.indent
        if node.children:
            self.out.newline(body_indent)
            self._render_block(node.children, body_indent)
        self.out.newline(indent)
        self.out.write(")")

    def _render_lambda(self, node: Node, indent: int) -> None:
        args = node.children
        if not args:
            self.out.write("lambda()")
            return
        sig = self.flat(args[0])
        rest = args[1:]
        inline: list[Node] = []
        while rest and rest[0].kind == "comment" and rest[0].inline:
            inline.append(rest.pop(0))
        pad = self._inner_pad() if sig else ""
        self.out.write("lambda(" + pad + (sig or ""))
        for comment in inline:
            self.out.write("  " + comment.value)
        if rest:
            self.out.newline(indent + self.options.indent)
            self._render_block(rest, indent + self.options.indent)
            self.out.newline(indent)
            self.out.write(")")
        else:
            self.out.write(")" if inline else pad + ")")

    def _render_control(self, node: Node, indent: int) -> None:
        flat = self.flat(node)
        if flat is not None and self._fits(flat):
            self.out.write(flat)
            return
        args = node.children
        self.out.write(node.value + "(")
        if not args:
            self.out.write(")")
            return
        if node.value in self.options.hanging:
            handled = False
            if node.value == "foreach":
                handled = self._render_foreach_head(args, indent)
            elif node.value == "for":
                handled = self._render_head_group(args, indent, 1, 2)
            if handled:
                self.out.newline(indent)
                self.out.write(")")
                return
        first = self._flat_if_fits(args[0])
        if first is None or node.value not in self.options.hanging:
            self.out.newline(indent + self.options.indent)
            self._render_block(args, indent + self.options.indent)
            self.out.newline(indent)
            self.out.write(")")
            return
        self.out.write(self._inner_pad() + first)
        rest = args[1:]
        if rest:
            self.out.newline(indent + self.options.indent)
            self._render_block(rest, indent + self.options.indent)
        self.out.newline(indent)
        self.out.write(")")

    def _render_foreach_head(self, args: list[Node], indent: int) -> bool:
        index = 0
        if args and args[0].kind == "atom" and args[0].value in FOREACH_MODIFIERS and len(args) > 2:
            index = 1
        if index >= len(args):
            return False
        var = args[index]
        count = (
            len([child for child in var.children if child.kind != "comment"])
            if var.kind == "plist"
            else 1
        )
        return self._render_head_group(args, indent, index + 1, count)

    def _render_head_group(
        self, args: list[Node], indent: int, prefix_count: int, payload_count: int
    ) -> bool:
        """Keep a form's leading semantic group on the head line when it fits."""
        payload = args[prefix_count : prefix_count + payload_count]
        if len(payload) < payload_count:
            return False
        body_indent = indent + self.options.indent
        prefix = args[:prefix_count]
        body = args[prefix_count + payload_count :]
        head_flats = [self.flat(item) for item in [*prefix, *payload]]
        if all(flat is not None for flat in head_flats):
            joined = " ".join(flat for flat in head_flats if flat is not None)
            if self._fits(joined):
                self.out.write(self._inner_pad() + joined)
                if body:
                    self.out.newline(body_indent)
                    self._render_block(body, body_indent)
                return True
        prefix_flats = [self.flat(item) for item in prefix]
        if any(flat is None for flat in prefix_flats):
            return False
        prefix_text = " ".join(flat for flat in prefix_flats if flat is not None)
        if not self._fits(prefix_text):
            return False
        self.out.write(self._inner_pad() + prefix_text)
        for item in payload:
            self.out.newline(body_indent)
            self.render(item, body_indent)
        if body:
            self.out.newline(body_indent)
            self._render_block(body, body_indent)
        return True

    def _render_generic_call(self, node: Node, indent: int) -> None:
        flat = self.flat(node)
        if flat is not None and self._fits(flat):
            self.out.write(flat)
            return
        self.out.write(node.value + "(")
        if node.children:
            args = node.children
            first = self._flat_if_fits(args[0]) if node.value in self.options.hanging else None
            if first is not None:
                self.out.write(self._inner_pad() + first)
                args = args[1:]
            if args:
                body_indent = indent + self.options.indent
                self.out.newline(body_indent)
                self._render_args(args, body_indent, pack=node.value != "list")
        self.out.newline(indent)
        self.out.write(")")

    def _render_args(self, args: list[Node], indent: int, pack: bool = True) -> None:
        flats = [self.flat(arg) for arg in args]
        if pack and all(flat is not None for flat in flats):
            packed = " ".join(flat for flat in flats if flat is not None)
            if indent + len(packed) + self.reserve <= self.options.width:
                self.out.write(packed)
                self.out.newline(indent)
                return
        first = True
        for arg, flat in zip(args, flats, strict=True):
            if arg.kind == "comment":
                if arg.inline and not first:
                    self.out.write("  " + arg.value)
                else:
                    if not first:
                        self.out.newline(indent)
                    self.out.write(arg.value)
                self.out.newline(indent)
                first = True
                continue
            if not first:
                self.out.newline(indent)
            if flat is not None and indent + len(flat) + self.reserve <= self.options.width:
                self.out.write(flat)
            else:
                self.render(arg, indent)
            first = False
        if not first:
            self.out.newline(indent)

    # -- flat rendering ------------------------------------------------
    def flat(self, node: Node) -> str | None:
        if any(child.kind == "comment" for child in node.children):
            return None
        if node.kind in {"atom", "string"}:
            return node.value if "\n" not in node.value else None
        if node.kind == "comment" or node.kind == "opaque":
            return None
        if node.kind == "seq":
            if len([c for c in node.children if c.kind != "comment"]) != 1:
                return None
            return self.flat(next(c for c in node.children if c.kind != "comment"))
        if node.kind == "plist":
            return self._flat_plist(node)
        if node.kind == "group":
            inner = self.flat(node.children[0])
            if inner is None:
                return None
            left, right = self._pad_pair(inner)
            return f"({left}{inner}{right})"
        if node.kind == "call":
            return self._flat_call(node)
        if node.kind == "index":
            base = self.flat(node.children[0])
            index = self.flat(node.children[1])
            if base is None or index is None:
                return None
            left, right = self._pad_pair(index)
            return f"{base}[{left}{index}{right}]"
        if node.kind == "prefix":
            operand = self.flat(node.children[0])
            return None if operand is None else node.value + operand
        if node.kind in {"unary", "postfix"}:
            operand = self.flat(node.children[0])
            if operand is None:
                return None
            if node.kind == "unary":
                if self._unary_needs_parens(node.children[0]):
                    left, right = self._pad_pair(operand)
                    operand = f"({left}{operand}{right})"
                return node.value + operand
            return operand + node.value
        if node.kind in {"binary", "assign"}:
            left = self.flat(node.children[0])
            right = self.flat(node.children[1])
            if left is None or right is None:
                return None
            if node.value in {"->", "~>"}:
                return f"{left}{node.value}{right}"
            return f"{left} {node.value} {right}"
        return None

    def _flat_force(self, node: Node) -> str | None:
        if node.kind == "plist" and node.value == "[":
            items = [self.flat(c) for c in node.children if c.kind != "comment"]
            if any(i is None for i in items):
                return None
            body = " ".join(i for i in items if i is not None)
            left, right = self._pad_pair(body)
            return f"[{left}{body}{right}]"
        return self.flat(node)

    def _flat_plist(self, node: Node) -> str | None:
        if node.value == "[":
            items = [self.flat(c) for c in node.children if c.kind != "comment"]
            if any(i is None for i in items):
                return None
            body = " ".join(i for i in items if i is not None)
            left, right = self._pad_pair(body)
            return f"[{left}{body}{right}]"
        items = [self.flat(c) for c in node.children if c.kind != "comment"]
        if any(i is None for i in items):
            return None
        body = " ".join(i for i in items if i is not None)
        left, right = self._pad_pair(body)
        if node.value == "{":
            return f"{{{left}{body}{right}}}"
        return f"({left}{body}{right})"

    def _flat_call(self, node: Node) -> str | None:
        if node.value in {"procedure", "defmacro", "defmethod", "defclass", "inScheme"}:
            empty_defclass = node.value == "defclass" and (
                len(node.children) < 3 or not node.children[2].children
            )
            if empty_defclass:
                pass
            else:
                return None
        if node.value == "lambda" and len(node.children) > 1:
            return None
        if node.value == "if" and any(
            c.kind == "atom" and c.value in {"then", "else"} for c in node.children
        ):
            return None
        if node.value in {"let", "letseq", "letrec", "prog"}:
            return None
        if node.value in {"cond", "case"}:
            if any(c.kind != "comment" for c in node.children):
                return None
        if node.value in {"when", "unless", "while"}:
            if len([c for c in node.children if c.kind != "comment"]) > 1:
                return None
        if node.value == "if":
            if len([c for c in node.children if c.kind != "comment"]) > 3:
                return None
        if node.value in {"foreach", "for"}:
            if len([c for c in node.children if c.kind != "comment"]) > 2:
                return None
        args = [self.flat(c) for c in node.children if c.kind != "comment"]
        if any(a is None for a in args):
            return None
        body = " ".join(a for a in args if a is not None)
        left, right = self._pad_pair(body)
        return f"{node.value}({left}{body}{right})"

    def _pad_pair(self, body: str) -> tuple[str, str]:
        if not body or self.options.enabled("tight-brackets"):
            return "", ""
        return " ", " "

    def _inner_pad(self) -> str:
        return "" if self.options.enabled("tight-brackets") else " "


def _parse(text: str) -> tuple[LexResult, Node, list[str], list[tuple[int, int]]]:
    lexed = lex(text)
    parsed = Parser(lexed.tokens, text).parse_file()
    return lexed, parsed.root, parsed.warnings, parsed.opaque_spans


def _canonical_without_opaque(root: Node) -> str:
    parts: list[str] = []
    for child in root.children:
        if child.kind == "comment" or child.kind == "opaque":
            continue
        parts.append(child.canonical())
    return "\n".join(parts)


def _comments(root: Node) -> list[str]:
    return [c for c in root.comments() if c]


def _apply_eol(lines: list[str], lexed: LexResult, options: Options) -> str:
    if options.enabled("eol"):
        text = "\n".join(line.rstrip() for line in lines)
        if text and not text.endswith("\n"):
            text += "\n"
        return text
    eol = lexed.eol
    text = eol.join(lines)
    if lexed.final_newline and text and not text.endswith(("\n", "\r")):
        text += eol
    return text


CLOSE_KINDS = {"rparen", "rbracket", "rbrace"}
OPEN_KINDS = {"lparen", "lbracket", "lbrace"}


def _format_conservative(text: str, lexed: LexResult, options: Options) -> str:
    """Whitespace-only mode: keep original line breaks and token order."""
    lines: list[str] = []
    current = ""
    depth = 0
    previous: str | None = None
    indent_enabled = options.enabled("indent")
    spacing_enabled = options.enabled("spacing")
    comments_enabled = options.enabled("comments")
    tight_brackets = options.enabled("tight-brackets")

    def flush() -> None:
        nonlocal current
        lines.append(current.rstrip())
        current = ""

    for token in lexed.tokens:
        if token.kind == "eof":
            break
        if token.newlines:
            flush()
            blank = max(0, token.newlines - 1)
            if options.enabled("blank-lines"):
                blank = min(blank, 1)
            lines.extend([""] * blank)
            close = token.kind in CLOSE_KINDS
            target_depth = max(0, depth - (1 if close else 0))
            if indent_enabled and token.kind != "comment":
                current = " " * (target_depth * options.indent)
            elif indent_enabled and comments_enabled:
                current = " " * (target_depth * options.indent)
            else:
                original = token.gap.rsplit("\n", 1)[-1]
                current = original.replace("\t", " " * options.indent)
        else:
            gap = token.gap
            if spacing_enabled:
                if token.kind == "comment":
                    if current.strip():
                        current += "  "
                elif tight_brackets:
                    if token.kind in CLOSE_KINDS:
                        pass
                    elif previous in {"lparen", "lbracket", "lbrace"}:
                        pass
                    elif not gap:
                        pass
                    elif previous == "prefix":
                        pass
                    elif token.kind == "prefix":
                        if current.strip():
                            current += " "
                    else:
                        current += " "
                elif token.kind in CLOSE_KINDS:
                    if gap and previous not in {"lparen", "lbracket", "lbrace"}:
                        current += " "
                elif not gap:
                    pass
                elif previous in {"lparen", "lbracket", "lbrace"}:
                    current += " "
                elif previous == "prefix":
                    pass
                elif token.kind == "prefix":
                    if current.strip():
                        current += " "
                else:
                    current += " "
            else:
                current += gap.replace("\t", " " * options.indent)

        if token.kind in {"string"} and "\n" in token.text:
            parts = token.text.split("\n")
            current += parts[0]
            for part in parts[1:]:
                flush()
                current = part
        else:
            current += token.text
        if token.kind in OPEN_KINDS:
            depth += 1
        elif token.kind in CLOSE_KINDS:
            depth = max(0, depth - 1)
        previous = token.kind
    flush()
    return _apply_eol(lines, lexed, options)


def format_source(text: str, options: Options | None = None) -> FormatResult:
    opts = (options or Options()).normalized()
    try:
        lexed, root, parse_warnings, opaque = _parse(text)
    except (LexError, ParseIssue) as exc:
        raise FormatError(str(exc)) from exc
    if opts.unknown == "error" and parse_warnings:
        raise FormatError(parse_warnings[0])
    warnings = list(opts.warnings) + parse_warnings

    if opts.unknown == "conservative" and parse_warnings:
        output = _format_conservative(text, lexed, opts)
        try:
            _, out_root, _, _ = _parse(output)
        except (LexError, ParseIssue) as exc:
            raise FormatError(f"internal verification failed: {exc}") from exc
        if _canonical_without_opaque(root) != _canonical_without_opaque(out_root):
            raise FormatError("internal verification failed: structure changed")
        return FormatResult(output, output != text, warnings, opaque)

    if not opts.enabled("wrapping"):
        output = _format_conservative(text, lexed, opts)
        try:
            _, out_root, _, _ = _parse(output)
        except (LexError, ParseIssue) as exc:
            raise FormatError(f"internal verification failed: {exc}") from exc
        if _canonical_without_opaque(root) != _canonical_without_opaque(out_root):
            raise FormatError("internal verification failed: structure changed")
        return FormatResult(output, output != text, warnings, opaque)

    renderer = Renderer(opts)
    lines = renderer.render_root(root)
    output = _apply_eol(lines, lexed, opts)

    try:
        _, out_root, _, _ = _parse(output)
    except (LexError, ParseIssue) as exc:
        raise FormatError(f"internal verification failed: {exc}") from exc
    if _canonical_without_opaque(root) != _canonical_without_opaque(out_root):
        raise FormatError("internal verification failed: structure changed")
    if _comments(root) != _comments(out_root):
        raise FormatError("internal verification failed: comments changed")

    return FormatResult(output, output != text, warnings, opaque)


def _line_offsets(text: str) -> list[int]:
    offsets = [0]
    for index, ch in enumerate(text):
        if ch == "\n":
            offsets.append(index + 1)
    return offsets


def _fragment_indent(fragment: str) -> int:
    for line in fragment.splitlines():
        if line.strip():
            return len(line) - len(line.lstrip(" "))
    return 0


def _format_fragment(fragment: str, options: Options) -> FormatResult:
    base = options.base_indent
    if base is None:
        base = _fragment_indent(fragment)
    return format_source(fragment, replace(options, base_indent=base, warnings=[]))


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _core_span(text: str, start: int, end: int) -> tuple[int, int] | None:
    """Trim boundary blank lines so repeated range formatting is stable."""
    lines = text[start:end].splitlines(keepends=True)
    lead = 0
    while lead < len(lines) and not lines[lead].strip():
        lead += 1
    trail = len(lines)
    while trail > lead and not lines[trail - 1].strip():
        trail -= 1
    if lead == trail:
        return None
    core_start = start + sum(len(line) for line in lines[:lead])
    core_end = start + sum(len(line) for line in lines[:trail])
    return core_start, core_end


def _verification_problem(root: Node, output: str) -> str | None:
    try:
        _, check_root, _, _ = _parse(output)
    except (LexError, ParseIssue) as exc:
        return f"internal verification failed: {exc}"
    if _canonical_without_opaque(root) != _canonical_without_opaque(check_root):
        return "internal verification failed: structure changed"
    if _comments(root) != _comments(check_root):
        return "internal verification failed: comments changed"
    return None


def format_range(
    text: str, ranges: list[tuple[int | None, int | None]], options: Options | None = None
) -> FormatResult:
    opts = (options or Options()).normalized()
    if not opts.enabled("wrapping"):
        raise FormatError("range formatting requires wrapping")
    _, root, parse_warnings, opaque = _parse(text)
    if opts.unknown == "error" and parse_warnings:
        raise FormatError(parse_warnings[0])
    if opts.unknown == "conservative" and parse_warnings:
        raise FormatError("conservative unknown policy is not supported with range formatting")
    warnings = list(opts.warnings) + parse_warnings
    offsets = _line_offsets(text)
    total_lines = max(1, len(offsets))

    spans: list[tuple[int, int]] = []
    for start_line, end_line in ranges:
        start_line = 1 if start_line is None else start_line
        end_line = total_lines if end_line is None else end_line
        if start_line < 1 or end_line < start_line:
            raise FormatError("invalid line range")
        start = offsets[min(start_line - 1, len(offsets) - 1)]
        end = offsets[end_line] if end_line < len(offsets) else len(text)
        spans.append((start, end))

    replacements: list[tuple[int, int, str]] = []
    for start, end in _merge_spans(spans):
        core = _core_span(text, start, end)
        if core is None:
            continue
        core_start, core_end = core
        fragment = text[core_start:core_end]
        try:
            result = _format_fragment(fragment, opts)
        except FormatError as exc:
            line = text.count("\n", 0, core_start) + 1
            warnings.append(f"line {line}: {exc}; selection left unchanged")
            continue
        for warning in result.warnings:
            if warning not in warnings:
                warnings.append(warning)
        if result.text == fragment:
            continue
        replacements.append((core_start, core_end, result.text))

    output = text
    for start, end, replacement in reversed(replacements):
        candidate = output[:start] + replacement + output[end:]
        problem = _verification_problem(root, candidate)
        if problem is not None:
            line = text.count("\n", 0, start) + 1
            warnings.append(f"line {line}: {problem}; selection left unchanged")
            continue
        output = candidate

    problem = _verification_problem(root, output)
    if problem is not None:
        raise FormatError(problem)
    return FormatResult(output, output != text, warnings, opaque)
