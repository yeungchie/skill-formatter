"""TOML configuration loading."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from .options import CATEGORIES, Options


class ConfigError(Exception):
    pass


def _expect_keys(table: dict[str, Any], allowed: set[str], section: str) -> None:
    unknown = set(table) - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ConfigError(f"unknown key(s) in [{section}]: {names}")


def find_config(start: Path) -> Path | None:
    current = start if start.is_dir() else start.parent
    while True:
        candidate = current / "skillfmt.toml"
        if candidate.is_file():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


def load_config(path: Path | None = None, start: Path | None = None) -> Options:
    config_path = path
    if config_path is None and start is not None:
        config_path = find_config(start)
    if config_path is None:
        return Options()
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read {config_path}: {exc}") from exc

    _expect_keys(data, {"format", "categories", "safety", "rules"}, "skillfmt")
    fmt = data.get("format", {})
    cats = data.get("categories", {})
    safety = data.get("safety", {})
    rules = data.get("rules", {})
    _expect_keys(fmt, {"width", "indent", "base_indent", "output_style"}, "format")
    _expect_keys(cats, set(CATEGORIES), "categories")
    _expect_keys(safety, {"unknown"}, "safety")
    _expect_keys(rules, {"inScheme", "case", "hanging"}, "rules")

    width = fmt.get("width", 150)
    indent = fmt.get("indent", 4)
    base_indent = fmt.get("base_indent")
    output_style = fmt.get("output_style", "c")
    if not isinstance(width, int) or width < 20:
        raise ConfigError("format.width must be an integer >= 20")
    if not isinstance(indent, int) or indent < 1:
        raise ConfigError("format.indent must be a positive integer")
    if base_indent is not None and (not isinstance(base_indent, int) or base_indent < 0):
        raise ConfigError("format.base_indent must be a non-negative integer")
    if output_style not in {"c", "s"}:
        raise ConfigError('format.output_style must be "c" or "s"')

    enabled = set(CATEGORIES)
    for key, value in cats.items():
        if not isinstance(value, bool):
            raise ConfigError(f"categories.{key} must be a boolean")
        if value:
            enabled.add(key)
        else:
            enabled.discard(key)

    unknown = safety.get("unknown", "opaque")
    if unknown not in {"opaque", "error", "conservative"}:
        raise ConfigError('safety.unknown must be "opaque", "error" or "conservative"')
    in_scheme = rules.get("inScheme", "flat")
    case_mode = rules.get("case", "align")
    hanging = rules.get("hanging", ["let", "letseq", "letrec", "quote"])
    if in_scheme not in {"flat", "indent"}:
        raise ConfigError('rules.inScheme must be "flat" or "indent"')
    if case_mode not in {"align", "block"}:
        raise ConfigError('rules.case must be "align" or "block"')
    if not isinstance(hanging, list) or any(not isinstance(x, str) for x in hanging):
        raise ConfigError("rules.hanging must be a list of strings")

    return Options(
        width=width,
        indent=indent,
        base_indent=base_indent,
        categories=frozenset(enabled),
        unknown=unknown,
        in_scheme=in_scheme,
        case_mode=case_mode,
        hanging=tuple(hanging),
        output_style=output_style,
        config_path=str(config_path),
    )
