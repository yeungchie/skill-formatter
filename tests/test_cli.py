from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from skill_formatter.config import load_config


def run_cli(
    args: list[str],
    data: str | None = None,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["NO_COLOR"] = "1"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "skill_formatter", *args],
        input=data,
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=env,
        check=False,
    )


def test_stdin_filter() -> None:
    result = run_cli(["format"], 'procedure(foo(a "t")\na = 1\n)\n')
    assert result.returncode == 0
    assert 'procedure(foo(a "t")\n    a = 1\n)\n' == result.stdout


def test_stdin_check() -> None:
    result = run_cli(
        ["check"],
        'procedure(foo(a "t")\na = 1\n)\n',
        env_extra={"SKILLFMT_LANG": "en"},
    )
    assert result.returncode == 1
    assert "would reformat" in result.stdout


def test_requires_a_command() -> None:
    result = run_cli([], env_extra={"SKILLFMT_LANG": "en"})
    assert result.returncode == 2
    assert "Usage: skillfmt" in result.stderr


def test_error_echoes_original_stdin() -> None:
    source = "(+ a b)\n"
    result = run_cli(["format", "--strict"], source)
    assert result.returncode == 2
    assert result.stdout == source


def test_diff_prints_unified_diff() -> None:
    source = 'procedure(foo(a "t")\na = 1\n)\n'
    result = run_cli(["--en", "diff"], source)
    assert result.returncode == 1
    assert "--- stdin" in result.stdout
    assert "+++ stdin (formatted)" in result.stdout
    assert "-a = 1" in result.stdout
    assert "+    a = 1" in result.stdout


def test_write_in_place(tmp_path: Path) -> None:
    path = tmp_path / "x.il"
    path.write_text('procedure(foo(a "t")\na = 1\n)\n', encoding="utf-8")
    result = run_cli(["format", "-w", str(path)])
    assert result.returncode == 0
    assert 'procedure(foo(a "t")\n    a = 1\n)\n' == path.read_text(encoding="utf-8")


def test_format_rejects_multiple_stdout_inputs(tmp_path: Path) -> None:
    first = tmp_path / "a.il"
    second = tmp_path / "b.il"
    first.write_text("a=1\n", encoding="utf-8")
    second.write_text("b=2\n", encoding="utf-8")
    result = run_cli(["--en", "format", str(first), str(second)])
    assert result.returncode == 2
    assert "multiple inputs require --write" in result.stderr


def test_help_is_stable_without_color() -> None:
    result = run_cli(["format", "-h"], env_extra={"SKILLFMT_LANG": "en"})
    assert result.returncode == 0
    assert "Usage: skillfmt format" in result.stdout
    assert "--line-width" in result.stdout
    assert "\x1b[" not in result.stdout


def test_width_option_controls_wrapping() -> None:
    source = 'list("aaaaaaaaaaaaaaaaaaaa" "bbbbbbbbbbbbbbbbbbbb")\n'
    narrow = run_cli(["format", "--line-width", "30"], source)
    assert narrow.returncode == 0
    assert narrow.stdout == ('list(\n    "aaaaaaaaaaaaaaaaaaaa"\n    "bbbbbbbbbbbbbbbbbbbb"\n)\n')
    wide = run_cli(["format", "--line-width", "200"], source)
    assert wide.returncode == 0
    assert wide.stdout == source


def test_help_language_override_chinese() -> None:
    result = run_cli(["-h"], env_extra={"SKILLFMT_LANG": "zh"})
    assert result.returncode == 0
    assert "用法:" in result.stdout
    assert "保守格式化" in result.stdout
    assert "选项" in result.stdout
    assert "Usage:" not in result.stdout


def test_help_language_override_english() -> None:
    result = run_cli(["-h"], env_extra={"SKILLFMT_LANG": "en"})
    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "Options" in result.stdout
    assert "用法:" not in result.stdout


def test_help_language_auto_from_locale() -> None:
    result = run_cli(
        ["-h"],
        env_extra={
            "SKILLFMT_LANG": "",
            "LC_ALL": "zh_CN.UTF-8",
            "LANG": "zh_CN.UTF-8",
        },
    )
    assert result.returncode == 0
    assert "用法:" in result.stdout


def test_help_language_auto_english_locale() -> None:
    result = run_cli(
        ["-h"],
        env_extra={
            "SKILLFMT_LANG": "",
            "LC_ALL": "",
            "LC_MESSAGES": "",
            "LANGUAGE": "",
            "LANG": "en_US.UTF-8",
        },
    )
    assert result.returncode == 0
    assert "Usage:" in result.stdout


def test_forced_language_flags() -> None:
    zh = run_cli(["--zh", "-h"], env_extra={"SKILLFMT_LANG": "en"})
    assert zh.returncode == 0
    assert "用法:" in zh.stdout
    assert "强制中文帮助" in zh.stdout
    en = run_cli(["--en", "-h"], env_extra={"SKILLFMT_LANG": "zh"})
    assert en.returncode == 0
    assert "Usage:" in en.stdout
    assert "Force English help" in en.stdout


def test_forced_language_flags_are_mutually_exclusive() -> None:
    result = run_cli(["--zh", "--en", "-h"])
    assert result.returncode == 2


def test_forced_language_flags_are_mutually_exclusive_across_command() -> None:
    result = run_cli(["--zh", "check", "--en"], "a=1\n")
    assert result.returncode == 2


def test_language_flag_before_command_localizes_subcommand_help() -> None:
    result = run_cli(["--zh", "format", "-h"])
    assert result.returncode == 0
    assert "用法: skillfmt format" in result.stdout


def test_forced_language_affects_check_message() -> None:
    source = 'procedure(foo(a "t")\na = 1\n)\n'
    result = run_cli(["--zh", "check"], source)
    assert result.returncode == 1
    assert "需要重新格式化" in result.stdout


def test_help_documents_exit_status_and_language_scope() -> None:
    result = run_cli(["--en", "-h"], env_extra={"COLUMNS": "100"})
    assert result.returncode == 0
    assert len(result.stdout.splitlines()) <= 60
    assert "Exit status:" in result.stdout
    assert "Language:" in result.stdout
    assert "only help and diagnostics" in result.stdout
    assert "config-template" in result.stdout
    assert "Output channels:" not in result.stdout


def test_help_documents_exit_status_and_language_scope_in_chinese() -> None:
    result = run_cli(["--zh", "-h"], env_extra={"COLUMNS": "100"})
    assert result.returncode == 0
    assert len(result.stdout.splitlines()) <= 60
    assert "退出码:" in result.stdout
    assert "语言:" in result.stdout
    assert "仅影响帮助与诊断" in result.stdout
    assert "config-template" in result.stdout
    assert "输出通道:" not in result.stdout


def test_config_template_is_loadable(tmp_path: Path) -> None:
    result = run_cli(["--en", "config-template"])
    assert result.returncode == 0
    assert result.stderr == ""
    target = tmp_path / "skillfmt.toml"
    target.write_text(result.stdout, encoding="utf-8")
    options = load_config(target)
    assert options.width == 150
    assert options.indent == 4
    assert options.base_indent is None
    assert options.output_style == "c"
    assert options.unknown == "opaque"
    assert options.config_path == str(target)


def test_config_template_uses_selected_language() -> None:
    chinese = run_cli(["config-template", "--zh"])
    english = run_cli(["config-template", "--en"])
    assert chinese.returncode == 0
    assert english.returncode == 0
    zh_text = chinese.stdout
    en_text = english.stdout
    assert "配置" in zh_text
    assert "输出风格" in zh_text
    assert "configuration" in en_text
    assert "Output style" in en_text
    assert "width = 150" in zh_text
    assert "width = 150" in en_text


def test_config_template_rejects_extra_arguments() -> None:
    result = run_cli(["--en", "config-template", "missing.il"])
    assert result.returncode == 2
    assert result.stdout == ""


def test_directory_input_expands_recursively(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    first = tmp_path / "a.il"
    second = tmp_path / "nested" / "b.ils"
    first.write_text("a=1\n", encoding="utf-8")
    second.write_text("b=2\n", encoding="utf-8")
    (tmp_path / "skip.txt").write_text("c=3\n", encoding="utf-8")
    result = run_cli(["--en", "check", str(tmp_path)])
    assert result.returncode == 1
    assert str(first) in result.stdout
    assert str(second) in result.stdout
    assert "skip.txt" not in result.stdout


def test_empty_directory_is_an_error(tmp_path: Path) -> None:
    result = run_cli(["--en", "check", str(tmp_path)])
    assert result.returncode == 2
    assert "no .il or .ils files found" in result.stderr


def test_verbose_reports_config_and_status() -> None:
    result = run_cli(["--en", "format", "--verbose"], 'procedure(foo(a "t")\na = 1\n)\n')
    assert result.returncode == 0
    assert "config:" in result.stderr
    assert "stdin: formatted" in result.stderr


def test_argument_errors_follow_language_override() -> None:
    chinese = run_cli(["--zh", "format", "--line-width", "10"], "a=1\n")
    assert chinese.returncode == 2
    assert "错误:" in chinese.stderr
    assert "行宽必须 >= 20" in chinese.stderr
    english = run_cli(["--en", "format", "--line-width", "10"], "a=1\n")
    assert english.returncode == 2
    assert "error:" in english.stderr
    assert "line width must be >= 20" in english.stderr
