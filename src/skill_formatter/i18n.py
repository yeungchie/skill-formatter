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
        "help": "show this help message and exit with status 0",
        "version": "show the version number and exit with status 0",
        "description": (
            "Conservative formatter for Cadence SKILL source.\n\n"
            "Reads UTF-8 input, rewrites whitespace and call-bracket placement, and keeps\n"
            "every token and comment unchanged. Reader syntax it does not understand is\n"
            "preserved byte-for-byte at the top-level form.\n\n"
            "Without --write, --check or --diff, one input is formatted to standard output."
        ),
        "paths": (
            "Input file, directory, or '-' for stdin. Directories are searched recursively "
            "for *.il and *.ils files. With no PATH, stdin is read and the result is written "
            "to stdout."
        ),
        "write": (
            "Rewrite each changed file in place. A file is replaced atomically only after the "
            "output re-parses and matches the input structure and comments. Exit 0 on success, "
            "2 on any failure; cannot be used with stdin, --check or --diff."
        ),
        "check": (
            "Do not write. Print a 'would reformat' line for every file that differs; exit 1 "
            "if any file differs and 0 if all input is already formatted."
        ),
        "diff": (
            "Do not write. Print a unified diff for every changed file to stdout; exit 1 if "
            "any file differs and 0 otherwise."
        ),
        "lines": (
            "Format only the form(s) covered by lines A:B, 1-based and inclusive. 'A:' runs to "
            "the end, ':B' starts at line 1, and the option may be repeated. Exactly one input "
            "is allowed; all bytes outside the selected forms are left untouched and the "
            "surrounding indentation is kept."
        ),
        "line_width": (
            "Maximum width of every output line, including indentation. Longer constructs wrap; "
            "list elements each get their own line. Defaults to format.width (150); minimum 20."
        ),
        "base_indent": (
            "Indentation of the outermost form, overriding format.base_indent. Files default to "
            "0; stdin without --lines reuses the smallest leading indent found in the input."
        ),
        "stdin_path": (
            "Path that stdin represents. Used to locate skillfmt.toml and to label diagnostics. "
            "Valid only when reading stdin."
        ),
        "only": (
            "Comma-separated categories to enable: eol, blank-lines, indent, spacing, wrapping, "
            "comments. All other categories are disabled. Cannot be combined with --skip."
        ),
        "skip": (
            "Comma-separated categories to disable. Skipping 'wrapping' keeps the original line "
            "breaks. Cannot be combined with --only."
        ),
        "config": (
            "Read settings from PATH instead of searching for skillfmt.toml upward from the "
            "input location. Exit 2 if the file is missing or invalid."
        ),
        "strict": (
            "Treat any unsupported-syntax warning as an error: print the warning, write nothing, "
            "and exit 2. Cannot be combined with --best-effort."
        ),
        "best_effort": (
            "Ask for the conservative fallback when unsupported reader syntax is found. "
            "Currently the whole top-level form is still preserved unchanged; the flag is "
            "reserved for a future whitespace-only layout. Cannot be combined with --strict."
        ),
        "quiet": (
            "Do not print unsupported-syntax warnings to stderr. Errors and --check/--diff "
            "results are unchanged."
        ),
        "verbose": (
            "Print the config source and per-input formatted/unchanged status to stderr. "
            "Formatted output on stdout is unchanged."
        ),
        "init_config": (
            "Write a commented skillfmt.toml template to PATH (default: skillfmt.toml) and exit "
            "0. Use '-' to print the template to stdout. An existing file is refused unless "
            "--force is given. Cannot be combined with formatting options."
        ),
        "force": (
            "Allow --init-config to overwrite an existing file; only valid with --init-config."
        ),
        "force_zh": (
            "Force Chinese help, warnings and diagnostics. Does not change formatted output. "
            "Mutually exclusive with --en."
        ),
        "force_en": (
            "Force English help, warnings and diagnostics. Does not change formatted output. "
            "Mutually exclusive with --zh."
        ),
        "epilog": (
            "Exit status:\n"
            "  0  success, or --check/--diff found no differences\n"
            "  1  --check or --diff found input that needs formatting\n"
            "  2  usage error, I/O error, parse or verification failure, strict warning,\n"
            "     or refusal to overwrite an existing config file\n"
            "\n"
            "Output channels:\n"
            "  stdout  formatted text (no action flag), unified diff (--diff), or the\n"
            "          config template when --init-config gets '-'\n"
            "  stderr  warnings, errors and --verbose status lines\n"
            "  stdin   on failure the original bytes are echoed to stdout, so editor\n"
            "          filters such as :%!skillfmt never lose text\n"
            "\n"
            "Language:\n"
            "  --zh and --en are optional and mutually exclusive. Without them skillfmt\n"
            "  checks SKILLFMT_LANG, LC_ALL, LC_MESSAGES, LANGUAGE, LANG and the system UI\n"
            "  language, then falls back to English. These switches only affect help,\n"
            "  warnings and diagnostics; they never change formatted output."
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
        "help": "显示本帮助并以状态码 0 退出",
        "version": "显示版本号并以状态码 0 退出",
        "description": (
            "保守格式化 Cadence SKILL 源码。\n\n"
            "读取 UTF-8 输入，只重排空白与调用括号位置，token 和注释正文保持不变；\n"
            "无法识别的读取器语法会在其顶层 form 内按原字节保留。\n\n"
            "未指定 --write、--check 或 --diff 时，单个输入格式化后写到标准输出。"
        ),
        "paths": (
            "输入文件、目录，或 '-' 表示 stdin。目录会递归查找 *.il 与 *.ils。"
            "不提供 PATH 时读取 stdin，结果写到 stdout。"
        ),
        "write": (
            "原地改写有变化的文件。只有输出能重新解析、且 token 结构与注释都与输入一致时"
            "才原子替换文件。成功退出 0，任一失败退出 2；不能与 stdin、--check 或 --diff 同用。"
        ),
        "check": (
            "不写文件。对每个有差异的文件输出一行“需要重新格式化”；有差异退出 1，"
            "全部已格式化退出 0。"
        ),
        "diff": (
            "不写文件。对每个有变化的文件向 stdout 输出 unified diff；有差异退出 1，否则退出 0。"
        ),
        "lines": (
            "只格式化第 A:B 行覆盖的 form（行号 1 基、含两端）。'A:' 表示到文件末尾，"
            "':B' 表示从第 1 行开始，可重复指定。只允许一个输入；选区之外的字节原样保留，"
            "并保留选区所在位置的整体缩进。"
        ),
        "line_width": (
            "每一行输出的宽度上限，包含缩进。超长结构会折行，list 的每个元素独占一行。"
            "默认取 format.width（150），最小 20。"
        ),
        "base_indent": (
            "最外层 form 的起始缩进，覆盖 format.base_indent。文件默认从 0 开始；"
            "stdin 且未使用 --lines 时沿用输入中最小的行首缩进。"
        ),
        "stdin_path": (
            "stdin 内容所代表的文件路径。用于向上查找 skillfmt.toml 并标注诊断信息；"
            "只在读取 stdin 时有效。"
        ),
        "only": (
            "只启用这些格式分类（逗号分隔）：eol、blank-lines、indent、spacing、wrapping、"
            "comments。其余分类全部关闭；不能与 --skip 同用。"
        ),
        "skip": (
            "跳过这些格式分类（逗号分隔）。跳过 wrapping 会保留原有换行位置；不能与 --only 同用。"
        ),
        "config": (
            "从 PATH 读取配置，而不是从输入位置向上查找 skillfmt.toml。"
            "文件不存在或内容非法时退出 2。"
        ),
        "strict": (
            "把任何“未支持语法”警告视为错误：输出警告、不写文件并退出 2；"
            "不能与 --best-effort 同用。"
        ),
        "best_effort": (
            "遇到未支持的读取器语法时请求保守回退。目前仍会原样保留整个顶层 form，"
            "该开关预留给后续的纯空白布局；不能与 --strict 同用。"
        ),
        "quiet": "不向 stderr 输出未支持语法警告；错误信息与 --check/--diff 结果不受影响。",
        "verbose": (
            "向 stderr 输出配置来源以及每个输入的“已格式化/未变化”状态；stdout 上的格式化结果不变。"
        ),
        "init_config": (
            "把带注释的 skillfmt.toml 模板写入 PATH（默认 skillfmt.toml）并退出 0。"
            "PATH 为 '-' 时输出到 stdout。目标已存在时默认拒绝覆盖，除非同时给出 --force；"
            "不能与其他格式化选项同用。"
        ),
        "force": "允许 --init-config 覆盖已存在的文件；只能与 --init-config 同用。",
        "force_zh": "强制使用中文帮助、警告与诊断信息；不影响格式化结果；与 --en 互斥。",
        "force_en": "强制使用英文帮助、警告与诊断信息；不影响格式化结果；与 --zh 互斥。",
        "epilog": (
            "退出码:\n"
            "  0  成功，或 --check/--diff 未发现差异\n"
            "  1  --check 或 --diff 发现需要格式化的输入\n"
            "  2  用法错误、IO 错误、解析或校验失败、strict 警告，或拒绝覆盖已有配置文件\n"
            "\n"
            "输出通道:\n"
            "  stdout  格式化文本（无动作选项）、unified diff（--diff），或\n"
            "          --init-config 收到 '-' 时的配置模板\n"
            "  stderr  警告、错误与 --verbose 状态行\n"
            "  stdin   失败时把原始字节写回 stdout，避免 :%!skillfmt 等\n"
            "          编辑器过滤器丢文本\n"
            "\n"
            "语言:\n"
            "  --zh 与 --en 均为可选且互斥。未指定时依次检查 SKILLFMT_LANG、\n"
            "  LC_ALL、LC_MESSAGES、LANGUAGE、LANG 与系统界面语言，最后回退到英文。\n"
            "  这两个开关只影响帮助、警告与诊断信息，绝不改变格式化结果。"
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
