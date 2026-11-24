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
        "help": "show this help and exit",
        "version": "show version and exit",
        "description": (
            "Conservative formatter for Cadence SKILL source.\n\n"
            "Only whitespace and call-bracket placement change; tokens, comments and\n"
            "unsupported top-level forms are preserved. Reads stdin when PATH is absent or '-'."
        ),
        "paths": (
            "Input file or directory ('-' = stdin). Directories are searched recursively for "
            "*.il and *.ils; with no PATH, stdin is read."
        ),
        "write": "Rewrite changed files in place; replace atomically after verification.",
        "check": "Do not write; report files that differ.",
        "diff": "Do not write; print a unified diff.",
        "lines": (
            "Format only forms covered by lines A:B (1-based, inclusive; 'A:' and ':B' are "
            "open-ended; repeatable). One input only; outside bytes and surrounding indentation "
            "are preserved."
        ),
        "line_width": (
            "Maximum output line width, including indentation (default 150, minimum 20). "
            "Long lists put each element on its own line."
        ),
        "base_indent": (
            "Indent of the outermost form (files default to 0; stdin without --lines reuses its "
            "smallest leading indent)."
        ),
        "stdin_path": "Path stdin represents, used to locate skillfmt.toml and label diagnostics.",
        "only": "Only the given categories (names are listed under --skip).",
        "skip": (
            "Skip categories: eol, blank-lines, indent, spacing, wrapping, comments. "
            "Skipping wrapping keeps original line breaks."
        ),
        "config": "Read settings from PATH instead of searching for skillfmt.toml.",
        "strict": "Treat unsupported-syntax warnings as errors (no write).",
        "best_effort": (
            "Reserved whitespace-only fallback; currently keeps whole top-level forms unchanged."
        ),
        "quiet": "Do not print unsupported-syntax warnings.",
        "verbose": "Print config source and per-input status to stderr.",
        "init_config": (
            "Write a commented skillfmt.toml template to PATH (default: skillfmt.toml; '-' = "
            "stdout). Refuses to overwrite unless --force; cannot be combined with formatting "
            "options."
        ),
        "force": "Allow --init-config to overwrite an existing file.",
        "force_zh": "Force Chinese help and diagnostics.",
        "force_en": "Force English help and diagnostics.",
        "epilog": (
            "Exit status:\n"
            "  0  success or no differences\n"
            "  1  --check/--diff found differences\n"
            "  2  usage, I/O, parse, verification, strict-warning or overwrite-refusal error\n"
            "\n"
            "Formatted text or a diff goes to stdout; diagnostics go to stderr. On stdin failure\n"
            "the original bytes are echoed to stdout, so :%!skillfmt never loses text.\n"
            "Language: --zh/--en are mutually exclusive, override locale detection, and affect\n"
            "only help and diagnostics."
        ),
        "warning_label": "warning",
        "would_reformat": "would reformat",
        "error_label": "error",
        "config_written": "wrote configuration template: {path}",
        "config_exists": "refusing to overwrite existing file: {path} (use --force)",
        "no_skill_files": "no .il or .ils files found",
        "verbose_config": "config: {path}",
        "verbose_no_config": "config: built-in defaults",
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
        "err_write_conflict": "--write cannot be combined with --check or --diff",
        "err_stdin_path": "--stdin-path is only valid when reading stdin",
        "err_write_stdin": "--write cannot be used with stdin",
        "err_dash_mixed": "'-' cannot be combined with file or directory paths",
        "err_lines_one_file": "--lines accepts exactly one input file",
        "err_multiple_need_action": "multiple inputs require --write, --check or --diff",
        "err_init_config_conflict": "--init-config cannot be combined with formatting options",
        "err_force_without_init": "--force is only valid with --init-config",
    },
    "zh": {
        "usage": "用法: ",
        "positional": "位置参数",
        "options": "选项",
        "help": "显示帮助并退出",
        "version": "显示版本号并退出",
        "description": (
            "保守格式化 Cadence SKILL 源码。\n\n"
            "只改空白与调用括号位置，token、注释正文与不支持的顶层 form 保持原样。\n"
            "PATH 为空或为 '-' 时读取 stdin。"
        ),
        "paths": "输入文件或目录（'-' 表示 stdin）。目录递归查找 *.il/*.ils；无 PATH 时读 stdin。",
        "write": "原地改写有变化的文件；校验通过后原子替换。",
        "check": "不写文件；报告有差异的文件。",
        "diff": "不写文件；输出 unified diff。",
        "lines": (
            "只格式化第 A:B 行覆盖的 form（1 基、含两端，'A:'/':B' 为开放区间，可重复）。"
            "只允许一个输入；选区外字节与整体缩进保持不变。"
        ),
        "line_width": (
            "整行输出宽度上限，含缩进（默认 150，最小 20）。超长 list 的每个元素独占一行。"
        ),
        "base_indent": "最外层 form 的缩进（文件默认 0；stdin 未用 --lines 时沿用最小行首缩进）。",
        "stdin_path": "stdin 对应的文件路径，用于查找 skillfmt.toml 与标注诊断。",
        "only": "只启用给定分类（名称见 --skip）。",
        "skip": "跳过：eol/blank-lines/indent/spacing/wrapping/comments；关闭 wrapping 保留换行。",
        "config": "从 PATH 读取配置，不再向上查找 skillfmt.toml。",
        "strict": "把未支持语法警告视为错误（不写文件）。",
        "best_effort": "预留的纯空白回退；目前仍原样保留整个顶层 form。",
        "quiet": "不输出未支持语法警告。",
        "verbose": "向 stderr 输出配置来源与每个输入的状态。",
        "init_config": (
            "把带注释的 skillfmt.toml 模板写入 PATH（默认 skillfmt.toml；'-' 输出到 stdout）。"
            "已有文件默认拒绝，--force 才覆盖；不能与其他格式化选项同用。"
        ),
        "force": "允许 --init-config 覆盖已有文件。",
        "force_zh": "强制中文帮助与诊断。",
        "force_en": "强制英文帮助与诊断。",
        "epilog": (
            "退出码:\n"
            "  0  成功或无差异\n"
            "  1  --check/--diff 发现差异\n"
            "  2  用法、IO、解析、校验、strict 警告或拒绝覆盖等错误\n"
            "\n"
            "格式化文本或 diff 输出到 stdout，诊断信息输出到 stderr。stdin 失败时原字节\n"
            "回显到 stdout，保证 :%!skillfmt 等编辑器过滤器不丢文本。\n"
            "语言: --zh/--en 互斥，覆盖自动检测，仅影响帮助与诊断。"
        ),
        "warning_label": "警告",
        "would_reformat": "需要重新格式化",
        "error_label": "错误",
        "config_written": "已写入配置模板: {path}",
        "config_exists": "拒绝覆盖已存在的文件: {path}（使用 --force 覆盖）",
        "no_skill_files": "未找到 .il 或 .ils 文件",
        "verbose_config": "配置: {path}",
        "verbose_no_config": "配置: 内置默认值",
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
        "err_write_conflict": "--write 不能与 --check 或 --diff 同用",
        "err_stdin_path": "--stdin-path 只在读取 stdin 时有效",
        "err_write_stdin": "--write 不能用于 stdin",
        "err_dash_mixed": "'-' 不能与文件或目录路径混用",
        "err_lines_one_file": "--lines 只接受一个输入文件",
        "err_multiple_need_action": "多个输入需要配合 --write、--check 或 --diff",
        "err_init_config_conflict": "--init-config 不能与格式化选项同用",
        "err_force_without_init": "--force 只能与 --init-config 同用",
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
