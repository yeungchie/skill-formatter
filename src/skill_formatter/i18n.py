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
        "help": "show this help message and exit",
        "version": "show program's version number and exit",
        "description": "Format Cadence SKILL source conservatively.",
        "paths": "files or directories",
        "write": "write files in place",
        "check": "check without writing",
        "diff": "print a unified diff",
        "lines": "format only lines A:B (1-based, inclusive; repeatable)",
        "line_width": "global line width limit, including indentation (default: 150)",
        "base_indent": "base indentation",
        "stdin_path": "file path for stdin input",
        "only": "only enable these format categories",
        "skip": "skip these format categories",
        "config": "configuration file",
        "strict": "treat warnings as errors",
        "best_effort": "use conservative layout for unsupported reader syntax",
        "quiet": "suppress warnings",
        "verbose": "show more details",
    },
    "zh": {
        "usage": "用法: ",
        "positional": "位置参数",
        "options": "选项",
        "help": "显示本帮助并退出",
        "version": "显示版本号并退出",
        "description": "保守格式化 Cadence SKILL 源码。",
        "paths": "文件或目录",
        "write": "原地写入文件",
        "check": "只检查，不写入",
        "diff": "输出 unified diff",
        "lines": "只格式化第 A:B 行（1 基、含两端、可重复）",
        "line_width": "整行宽度上限（含缩进；默认 150，或配置中的 format.width）",
        "base_indent": "第一层起始缩进",
        "stdin_path": "stdin 输入对应的文件路径",
        "only": "只启用这些格式分类（逗号分隔）",
        "skip": "跳过这些格式分类（逗号分隔）",
        "config": "配置文件路径",
        "strict": "把警告视为错误",
        "best_effort": "未确认读取器语法使用保守布局",
        "quiet": "抑制警告",
        "verbose": "输出更多细节",
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
    override = os.environ.get("SKILLFMT_LANG", "").strip().lower()
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
