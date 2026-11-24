"""Formatting options and category definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CATEGORIES: tuple[str, ...] = (
    "eol",
    "blank-lines",
    "indent",
    "spacing",
    "wrapping",
    "comments",
)

UnknownPolicy = Literal["opaque", "error", "conservative"]


@dataclass(slots=True)
class Options:
    width: int = 150
    indent: int = 4
    base_indent: int | None = None
    categories: frozenset[str] = frozenset(CATEGORIES)
    unknown: UnknownPolicy = "opaque"
    in_scheme: Literal["flat", "indent"] = "flat"
    case_mode: Literal["align", "block"] = "align"
    hanging: tuple[str, ...] = ("let", "letseq", "letrec", "quote")
    output_style: Literal["c", "s"] = "c"
    config_path: str | None = None
    stdin_path: str | None = None
    warnings: list[str] = field(default_factory=list)

    def enabled(self, name: str) -> bool:
        return name in self.categories

    def normalized(self) -> Options:
        """Return a copy with dependency rules applied."""
        cats = set(self.categories)
        if "wrapping" in cats:
            cats.update({"indent", "spacing"})
        if "comments" in cats:
            cats.add("indent")
        return Options(
            width=self.width,
            indent=self.indent,
            base_indent=self.base_indent,
            categories=frozenset(cats),
            unknown=self.unknown,
            in_scheme=self.in_scheme,
            case_mode=self.case_mode,
            hanging=self.hanging,
            output_style=self.output_style,
            config_path=self.config_path,
            stdin_path=self.stdin_path,
        )
