"""Help-text language detection and translations."""

from __future__ import annotations

import ctypes
import locale
import os
import sys
import warnings

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "usage": "Usage: ",
        "positional": "Positional Arguments",
        "options": "Options",
        "commands": "Commands",
        "help": "show this help and exit",
        "version": "show version and exit",
        "description": (
            "Conservative formatter for Cadence SKILL source.\n\n"
            "Format files or stdin, check for differences, print diffs, and manage configuration."
        ),
        "command_format": "format files or stdin",
        "command_check": "report files that need formatting",
        "command_diff": "print unified diffs",
        "command_config": "inspect or update configuration",
        "format_description": "Format files or stdin; write to stdout unless --write is given.",
        "check_description": "Report files or stdin that need formatting; exit 1 if any differ.",
        "diff_description": "Print unified diffs for files or stdin that need formatting.",
        "config_description": "Inspect or update configuration.",
        "paths": (
            "Input file or directory ('-' = stdin); directories recurse into *.il and *.ils."
        ),
        "write": "Rewrite changed files in place.",
        "lines": (
            "Format only the selected lines A:B (1-based, inclusive; 'A:' and ':B' "
            "open-ended; repeatable). Incomplete fragments are left unchanged. "
            "One input only."
        ),
        "line_width": (
            "Maximum output line width, including indentation (default 150, minimum 20). "
            "Long lists put each element on its own line."
        ),
        "base_indent": "Base indentation for selected fragments or the outermost form.",
        "stdin_path": "Path stdin represents, used to locate skill-formatter.toml.",
        "only": "Only the given categories; required prerequisites are added.",
        "skip": (
            "Skip categories: eol, blank-lines, indent, spacing, wrapping, comments. "
            "Skipping wrapping, indent, spacing or comments keeps original line breaks."
        ),
        "config": "Read settings from PATH instead of searching for skill-formatter.toml.",
        "config_file": "Config file to read or update.",
        "strict": "Treat unsupported-syntax warnings as errors.",
        "best_effort": "Use conservative layout for unsupported syntax.",
        "quiet": "Do not print unsupported-syntax warnings.",
        "verbose": "Print config source and per-input status to stderr.",
        "config_template": "print a commented skill-formatter.toml template",
        "config_get": "print the effective value of KEY",
        "config_set": "write KEY VALUE to the active config file; VALUE may be 'unset'",
        "config_trace": "print the config file in effect",
        "config_key": "configuration key (dotted name)",
        "config_value": "value; use 'unset' to remove the key",
        "force_zh": "Force Chinese help and diagnostics.",
        "force_en": "Force English help and diagnostics.",
        "warning_label": "warning",
        "would_reformat": "would reformat",
        "interrupted": "interrupted",
        "error_label": "error",
        "no_skill_files": "no .il or .ils files found",
        "verbose_config": "config: {path}",
        "verbose_no_config": "config: built-in defaults",
        "config_updated": "updated: {path}",
        "verbose_changed": "{path}: formatted",
        "verbose_unchanged": "{path}: unchanged",
        "err_range_format": "expected A:B",
        "err_range_integer": "line numbers must be integers",
        "err_range_one_based": "line numbers are 1-based",
        "err_range_order": "range end must not be before start",
        "err_category_unknown": "unknown categories: {names}",
        "err_width_integer": "line width must be an integer",
        "err_width_minimum": "line width must be >= 20",
        "err_only_skip": "--only and --skip are mutually exclusive",
        "err_strict_best_effort": "--strict and --best-effort are mutually exclusive",
        "err_quiet_verbose": "--quiet and --verbose are mutually exclusive",
        "err_language_flags": "--zh and --en are mutually exclusive",
        "err_stdin_path": "--stdin-path is only valid when reading stdin",
        "err_write_stdin": "--write cannot be used with stdin",
        "err_dash_mixed": "'-' cannot be combined with file or directory paths",
        "err_lines_one_file": "--lines accepts exactly one input file",
        "err_multiple_need_action": "multiple inputs require --write",
    },
    "zh": {
        "usage": "用法: ",
        "positional": "位置参数",
        "options": "选项",
        "commands": "命令",
        "help": "显示帮助并退出",
        "version": "显示版本号并退出",
        "description": (
            "保守格式化 Cadence SKILL 源码。\n\n"
            "支持格式化文件/stdin、检查差异、输出 diff 与管理配置。"
        ),
        "command_format": "格式化文件或 stdin",
        "command_check": "报告需要格式化的文件",
        "command_diff": "输出 unified diff",
        "command_config": "查看或修改配置",
        "format_description": "格式化文件或 stdin；未给 --write 时写到 stdout。",
        "check_description": "报告文件或 stdin 中需要格式化的内容；有差异退出 1。",
        "diff_description": "为需要格式化的文件或 stdin 输出 unified diff。",
        "config_description": "查看或修改配置。",
        "paths": "输入文件或目录（'-' 表示 stdin）；目录递归查找 *.il/*.ils。",
        "write": "原地改写有变化的文件。",
        "lines": (
            "只格式化第 A:B 行（1 基、含两端，'A:'/':B' 为开放区间，可重复）；"
            "片段不完整时保持原样。只允许一个输入。"
        ),
        "line_width": (
            "整行输出宽度上限，含缩进（默认 150，最小 20）。超长 list 的每个元素独占一行。"
        ),
        "base_indent": "选区片段或最外层 form 的起始缩进。",
        "stdin_path": "stdin 对应的文件路径，用于查找 skill-formatter.toml。",
        "only": "只启用给定分类；会自动补齐依赖分类。",
        "skip": "跳过：eol/blank-lines/indent/spacing/wrapping/comments。",
        "config": "从 PATH 读取配置，不再向上查找 skill-formatter.toml。",
        "config_file": "要读取或写入的配置文件。",
        "strict": "把未支持语法警告视为错误。",
        "best_effort": "未确认语法使用保守空白布局。",
        "quiet": "不输出未支持语法警告。",
        "verbose": "向 stderr 输出配置来源与每个输入的状态。",
        "config_template": "打印带注释的 skill-formatter.toml 模板",
        "config_get": "打印 KEY 的生效值",
        "config_set": "把 KEY VALUE 写入当前配置文件；VALUE 可为 'unset'",
        "config_trace": "打印当前生效的配置文件",
        "config_key": "配置键（点号形式）",
        "config_value": "值；'unset' 表示删除该键",
        "force_zh": "强制中文帮助与诊断。",
        "force_en": "强制英文帮助与诊断。",
        "warning_label": "警告",
        "would_reformat": "需要重新格式化",
        "interrupted": "已中断",
        "error_label": "错误",
        "no_skill_files": "未找到 .il 或 .ils 文件",
        "verbose_config": "配置: {path}",
        "verbose_no_config": "配置: 内置默认值",
        "config_updated": "已更新: {path}",
        "verbose_changed": "{path}: 已格式化",
        "verbose_unchanged": "{path}: 未变化",
        "err_range_format": "格式应为 A:B",
        "err_range_integer": "行号必须是整数",
        "err_range_one_based": "行号从 1 开始",
        "err_range_order": "范围结束行不能早于开始行",
        "err_category_unknown": "未知的格式分类: {names}",
        "err_width_integer": "行宽必须是整数",
        "err_width_minimum": "行宽必须 >= 20",
        "err_only_skip": "--only 与 --skip 互斥",
        "err_strict_best_effort": "--strict 与 --best-effort 互斥",
        "err_quiet_verbose": "--quiet 与 --verbose 互斥",
        "err_language_flags": "--zh 与 --en 互斥",
        "err_stdin_path": "--stdin-path 只在读取 stdin 时有效",
        "err_write_stdin": "--write 不能用于 stdin",
        "err_dash_mixed": "'-' 不能与文件或目录路径混用",
        "err_lines_one_file": "--lines 只接受一个输入文件",
        "err_multiple_need_action": "多个输入需要配合 --write",
    },
}


def _is_chinese_locale(value: str) -> bool:
    lowered = value.lower()
    return "zh" in lowered or "chinese" in lowered


def _explicit_locale() -> str | None:
    for key in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        value = os.environ.get(key, "").strip()
        if not value:
            continue
        for part in value.split(":"):
            part = part.strip()
            if not part:
                continue
            lowered = part.lower()
            if lowered in {"c", "posix"} or lowered.startswith("c."):
                continue
            return part
    return None


def _os_locale() -> str | None:
    if sys.platform == "win32":
        try:
            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if (langid & 0x3FF) == 0x04:
                return "zh"
            return "en"
        except (AttributeError, OSError):
            pass
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            name = locale.getlocale()[0] or locale.getdefaultlocale()[0]
    except (ValueError, TypeError):
        name = None
    return name


def detect_language() -> str:
    override = os.environ.get("SKILL_FORMATTER_LANG", "").strip().lower()
    if override.startswith("zh"):
        return "zh"
    if override.startswith("en"):
        return "en"
    explicit = _explicit_locale()
    if explicit is not None:
        return "zh" if _is_chinese_locale(explicit) else "en"
    system = _os_locale()
    if system is not None and _is_chinese_locale(system):
        return "zh"
    return "en"


def text(lang: str, key: str) -> str:
    return TEXTS.get(lang, TEXTS["en"])[key]
