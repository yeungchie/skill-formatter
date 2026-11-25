"""Formatting options and category definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CATEGORIES: tuple[str, ...] = (
    "eol",
    "blank-lines",
    "indent",
    "spacing",
    "tight-brackets",
    "align-assignments",
    "wrapping",
    "comments",
)

DEFAULT_HANGING: tuple[str, ...] = (
    "let",
    "letseq",
    "letrec",
    "prog",
    "case",
    "if",
    "when",
    "unless",
    "while",
    "foreach",
    "for",
    "quote",
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
    hanging: tuple[str, ...] = DEFAULT_HANGING
    config_path: str | None = None
    warnings: list[str] = field(default_factory=list)

    def enabled(self, name: str) -> bool:
        return name in self.categories

    def normalized(self) -> Options:
        """Return a copy with dependency rules applied."""
        cats = set(self.categories)
        warnings = list(self.warnings)
        if "comments" in cats and "indent" not in cats:
            cats.discard("comments")
            warnings.append("comments disabled because indent is disabled")
        if "wrapping" in cats:
            missing = [name for name in ("indent", "spacing", "comments") if name not in cats]
            if missing:
                cats.discard("wrapping")
                warnings.append("wrapping disabled because " + ", ".join(missing) + " disabled")
        return Options(
            width=self.width,
            indent=self.indent,
            base_indent=self.base_indent,
            categories=frozenset(cats),
            unknown=self.unknown,
            in_scheme=self.in_scheme,
            case_mode=self.case_mode,
            hanging=self.hanging,
            config_path=self.config_path,
            warnings=warnings,
        )
