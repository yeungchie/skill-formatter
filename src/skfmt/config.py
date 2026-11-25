"""TOML configuration loading, inspection and updates."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .identity import CONFIG_NAME, TOOL_NAME
from .options import CATEGORIES, DEFAULT_HANGING, Options


class ConfigError(Exception):
    pass


ValueKind = Literal["int", "bool", "str", "list-str"]


@dataclass(frozen=True, slots=True)
class KeySpec:
    section: str
    name: str
    kind: ValueKind
    default: Any
    minimum: int | None = None
    choices: tuple[str, ...] | None = None


def _build_keys() -> dict[str, KeySpec]:
    keys = {
        "format.width": KeySpec("format", "width", "int", 150, minimum=20),
        "format.indent": KeySpec("format", "indent", "int", 4, minimum=1),
        "format.base_indent": KeySpec("format", "base_indent", "int", None, minimum=0),
        "safety.unknown": KeySpec(
            "safety",
            "unknown",
            "str",
            "opaque",
            choices=("opaque", "error", "conservative"),
        ),
        "rules.inScheme": KeySpec("rules", "inScheme", "str", "flat", choices=("flat", "indent")),
        "rules.case": KeySpec("rules", "case", "str", "align", choices=("align", "block")),
        "rules.hanging": KeySpec(
            "rules",
            "hanging",
            "list-str",
            DEFAULT_HANGING,
        ),
    }
    for name in CATEGORIES:
        keys[f"categories.{name}"] = KeySpec("categories", name, "bool", True)
    return keys


CONFIG_KEYS = _build_keys()


def config_key_spec(key: str) -> KeySpec:
    try:
        return CONFIG_KEYS[key]
    except KeyError as exc:
        raise ConfigError(f"unknown configuration key: {key}") from exc


def config_option_value(options: Options, key: str) -> Any:
    spec = config_key_spec(key)
    if spec.section == "categories":
        return spec.name in options.categories
    if key == "format.width":
        return options.width
    if key == "format.indent":
        return options.indent
    if key == "format.base_indent":
        return options.base_indent
    if key == "safety.unknown":
        return options.unknown
    if key == "rules.inScheme":
        return options.in_scheme
    if key == "rules.case":
        return options.case_mode
    return list(options.hanging)


def format_config_value(value: Any, spec: KeySpec) -> str:
    if value is None:
        return "unset"
    if spec.kind == "bool":
        return "true" if value else "false"
    if spec.kind == "int":
        return str(value)
    if spec.kind == "str":
        return json.dumps(value, ensure_ascii=False)
    items = ", ".join(json.dumps(item, ensure_ascii=False) for item in value)
    return f"[{items}]"


def parse_config_value(key: str, raw: str) -> Any | None:
    spec = config_key_spec(key)
    text = raw.strip()
    if text == "unset":
        return None
    if spec.kind == "bool":
        lowered = text.lower()
        if lowered in {"true", "1"}:
            return True
        if lowered in {"false", "0"}:
            return False
        raise ConfigError(f"{key} must be true or false")
    if spec.kind == "int":
        try:
            value = int(text, 10)
        except ValueError as exc:
            raise ConfigError(f"{key} must be an integer") from exc
        if spec.minimum is not None and value < spec.minimum:
            raise ConfigError(f"{key} must be >= {spec.minimum}")
        return value
    if spec.kind == "str":
        if text[:1] in {'"', "'"}:
            try:
                value = tomllib.loads(f"value = {text}")["value"]
            except tomllib.TOMLDecodeError as exc:
                raise ConfigError(f"{key} must be a string") from exc
            if not isinstance(value, str):
                raise ConfigError(f"{key} must be a string")
        else:
            value = text
        if spec.choices is not None and value not in spec.choices:
            choices = ", ".join(spec.choices)
            raise ConfigError(f"{key} must be one of: {choices}")
        return value
    if text.startswith("["):
        try:
            value = tomllib.loads(f"value = {text}")["value"]
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"{key} must be a list of strings") from exc
    else:
        value = [part.strip() for part in text.split(",") if part.strip()]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConfigError(f"{key} must be a list of strings")
    return value


_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*(?:#.*)?$")


def _key_re(name: str) -> re.Pattern[str]:
    return re.compile(rf"^\s*#?\s*{re.escape(name)}\s*=")


def _active_key_re(name: str) -> re.Pattern[str]:
    return re.compile(rf"^\s*{re.escape(name)}\s*=")


def _section_bounds(lines: list[str], section: str) -> tuple[int | None, int]:
    header = None
    for index, line in enumerate(lines):
        match = _SECTION_RE.match(line)
        if match and match.group(1).strip() == section:
            header = index
            break
    if header is None:
        return None, len(lines)
    for index in range(header + 1, len(lines)):
        if _SECTION_RE.match(lines[index]):
            return header, index
    return header, len(lines)


def _write_key(text: str, spec: KeySpec, value: str) -> str:
    lines = text.splitlines()
    header, end = _section_bounds(lines, spec.section)
    assignment = f"{spec.name} = {value}"
    if header is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([f"[{spec.section}]", assignment])
        return "\n".join(lines) + "\n"
    pattern = _key_re(spec.name)
    for index in range(header + 1, end):
        if pattern.match(lines[index]):
            lines[index] = assignment
            break
    else:
        insert = end
        while insert > header + 1 and not lines[insert - 1].strip():
            insert -= 1
        lines.insert(insert, assignment)
    return "\n".join(lines) + "\n"


def _remove_key(text: str, spec: KeySpec) -> str:
    lines = text.splitlines()
    header, end = _section_bounds(lines, spec.section)
    if header is None:
        return text
    pattern = _active_key_re(spec.name)
    for index in range(header + 1, end):
        if pattern.match(lines[index]):
            del lines[index]
            break
    else:
        return text
    return "\n".join(lines) + "\n"


def set_config_text(text: str, key: str, raw: str) -> str:
    spec = config_key_spec(key)
    value = parse_config_value(key, raw)
    if value is None:
        updated = _remove_key(text, spec)
    else:
        updated = _write_key(text, spec, format_config_value(value, spec))
    try:
        data = tomllib.loads(updated)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"cannot update {key}: {exc}") from exc
    _options_from_data(data, None)
    return updated


_TEMPLATE_EN = """\
# @TOOL@ configuration
# Generated by: @TOOL@ config template
#
# @TOOL@ searches for this file as "@CONFIG@" from the input location
# upward, or reads the path given with --config. Command-line options override
# values from this file.

[format]
# Maximum width of every output line, including indentation. Minimum 20.
width = 150

# Spaces per nesting level.
indent = 4

# Indentation of the outermost form. Uncomment to pin it; when absent, files
# start at column 0 and stdin without --lines reuses the input indentation.
# base_indent = 0

[categories]
# Enable or disable individual formatting categories.
# "wrapping" requires indent, spacing and comments; disabling any of them
# turns wrapping off and keeps the original line breaks.
eol = true
blank-lines = true
indent = true
spacing = true
# Keep delimiters tight: true writes foo(a b) and {x y};
# false writes foo( a b ) and { x y }.
tight-brackets = true
wrapping = true
comments = true

[safety]
# What to do with a top-level form that uses reader syntax the parser does
# not understand:
#   "opaque"       keep that form byte-for-byte and print a warning (default)
#   "error"        stop with exit status 2 (same as --strict)
#   "conservative" use whitespace-only layout for the whole input
unknown = "opaque"

[rules]
# "flat" puts inScheme at column 0; "indent" indents it like a normal body.
inScheme = "flat"

# "align" aligns keys of single-value case clauses; "block" puts every case
# clause on its own indented line.
case = "align"

# Call/special forms whose first argument stays on the head line. Definition
# signatures always stay on the head line.
hanging = @HANGING@
"""

_TEMPLATE_ZH = """\
# @TOOL@ 配置
# 由 @TOOL@ config template 生成
#
# @TOOL@ 会从输入位置向上查找名为 "@CONFIG@" 的文件，或用 --config
# 指定路径。命令行选项优先于本文件中的值。

[format]
# 每一行输出的宽度上限（包含缩进），最小 20。
width = 150

# 每一层嵌套的缩进空格数。
indent = 4

# 最外层 form 的起始缩进。取消注释可固定该值；缺省时文件从第 0 列开始，
# stdin 且未使用 --lines 时沿用输入中的整体缩进。
# base_indent = 0

[categories]
# 分别开启或关闭各格式化分类。
# "wrapping" 需要 indent、spacing 与 comments；关闭其中任一分类会关闭 wrapping，
# 保留原有换行位置。
eol = true
blank-lines = true
indent = true
spacing = true
# 括号内侧是否紧凑：true 写 foo(a b) 与 {x y}；false 写 foo( a b ) 与 { x y }。
tight-brackets = true
wrapping = true
comments = true

[safety]
# 顶层 form 使用解析器无法识别的读取器语法时如何处理：
#   "opaque"       整个 form 按原字节保留并输出警告（默认）
#   "error"        以状态码 2 停止（等同于 --strict）
#   "conservative" 对整份输入使用保守的空白布局
unknown = "opaque"

[rules]
# "flat" 让 inScheme 顶格；"indent" 像普通 body 一样缩进。
inScheme = "flat"

# "align" 对齐单值 case 分支的键；"block" 让每个 case 分支独立成缩进行。
case = "align"

# 首参数保留在头行上的调用/特殊 form；定义签名固定留在头行。
hanging = @HANGING@
"""


def render_template(lang: str) -> str:
    """Return a complete, loadable configuration template."""
    text = _TEMPLATE_ZH if lang.lower().startswith("zh") else _TEMPLATE_EN
    hanging = format_config_value(DEFAULT_HANGING, CONFIG_KEYS["rules.hanging"])
    return (
        text.replace("@TOOL@", TOOL_NAME)
        .replace("@CONFIG@", CONFIG_NAME)
        .replace("@HANGING@", hanging)
    )


def _expect_keys(table: dict[str, Any], allowed: set[str], section: str) -> None:
    unknown = set(table) - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ConfigError(f"unknown key(s) in [{section}]: {names}")


def find_config(start: Path) -> Path | None:
    current = start if start.is_dir() else start.parent
    while True:
        candidate = current / CONFIG_NAME
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
    return _options_from_data(data, config_path)


def _options_from_data(data: dict[str, Any], config_path: Path | None) -> Options:
    _expect_keys(data, {"format", "categories", "safety", "rules"}, TOOL_NAME)
    fmt = data.get("format", {})
    cats = data.get("categories", {})
    safety = data.get("safety", {})
    rules = data.get("rules", {})
    _expect_keys(fmt, {"width", "indent", "base_indent"}, "format")
    _expect_keys(cats, set(CATEGORIES), "categories")
    _expect_keys(safety, {"unknown"}, "safety")
    _expect_keys(rules, {"inScheme", "case", "hanging"}, "rules")

    width = fmt.get("width", 150)
    indent = fmt.get("indent", 4)
    base_indent = fmt.get("base_indent")
    if not isinstance(width, int) or width < 20:
        raise ConfigError("format.width must be an integer >= 20")
    if not isinstance(indent, int) or indent < 1:
        raise ConfigError("format.indent must be a positive integer")
    if base_indent is not None and (not isinstance(base_indent, int) or base_indent < 0):
        raise ConfigError("format.base_indent must be a non-negative integer")

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
    hanging = rules.get("hanging", list(DEFAULT_HANGING))
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
        config_path=str(config_path) if config_path is not None else None,
    )
