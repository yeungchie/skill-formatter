"""A small concrete syntax tree for SKILL source."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Node:
    kind: str
    value: str = ""
    children: list[Node] = field(default_factory=list)
    start: int = 0
    end: int = 0
    line: int = 0
    blank_before: int = 0
    inline: bool = False
    style: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def canonical(self) -> str:
        """Layout-insensitive structure used to verify formatting safety."""
        if self.kind in {"atom", "string"}:
            return self.value
        if self.kind == "comment":
            return ""
        if self.kind == "opaque":
            return f"<opaque:{self.value}>"
        if self.kind == "seq":
            return "(" + " ".join(c.canonical() for c in self.children if c.kind != "comment") + ")"
        if self.kind == "call":
            head = self.value
            args = " ".join(c.canonical() for c in self.children if c.kind != "comment")
            return f"({head} {args})" if args else f"({head})"
        if self.kind == "plist":
            items = " ".join(c.canonical() for c in self.children if c.kind != "comment")
            return f"({items})" if items else "()"
        if self.kind == "group":
            return f"(group {self.children[0].canonical()})"
        if self.kind == "index":
            return f"(index {self.children[0].canonical()} {self.children[1].canonical()})"
        if self.kind == "prefix":
            return f"({self.value} {self.children[0].canonical()})"
        if self.kind in {"binary", "assign"}:
            return f"({self.value} {self.children[0].canonical()} {self.children[1].canonical()})"
        if self.kind in {"unary", "postfix"}:
            return f"({self.value} {self.children[0].canonical()})"
        return f"<{self.kind}:{self.value}>"

    def comments(self) -> list[str]:
        out: list[str] = []
        if self.kind == "comment":
            out.append(self.value)
        for child in self.children:
            out.extend(child.comments())
        return out

    def walk(self) -> list[Node]:
        out = [self]
        for child in self.children:
            out.extend(child.walk())
        return out


def sequence(children: list[Node]) -> Node:
    return Node("seq", children=children)
