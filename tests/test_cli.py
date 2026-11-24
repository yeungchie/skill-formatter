from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from skill_formatter import __version__
from skill_formatter.config import load_config


def run_cli(
    args: list[str],
    data: str | None = None,
    env_extra: dict[str, str] | None = None,
    cwd: Path | None = None,
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
        cwd=cwd,
        check=False,
    )


def test_stdin_filter() -> None:
    result = run_cli(["format"], 'procedure(foo(a "t")\na = 1\n)\n')
    assert result.returncode == 0
    assert 'procedure(foo(a "t")\n    a = 1\n)\n' == result.stdout


def test_version_output() -> None:
    result = run_cli(["--version"])
    assert result.returncode == 0
    assert result.stdout == f"skillfmt {__version__}\n"


def test_best_effort_uses_conservative_layout() -> None:
    result = run_cli(["format", "--best-effort"], "(+ a   b)\n")
    assert result.returncode == 0
    assert result.stdout == "(+ a b)\n"


def test_skipping_required_category_disables_wrapping() -> None:
    result = run_cli(["format", "--skip", "spacing"], "a=1\n", env_extra={"SKILLFMT_LANG": "en"})
    assert result.returncode == 0
    assert result.stdout == "a=1\n"
    assert "wrapping disabled" in result.stderr


def test_stdin_eof_is_empty_input() -> None:
    for command in ("format", "check", "diff"):
        result = run_cli([command], "")
        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""


def test_keyboard_interrupt_exits_130(monkeypatch, capsys) -> None:
    from skill_formatter import cli

    def interrupt() -> bytes:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_read_stdin", interrupt)
    code = cli.main(["--en", "format"])
    captured = capsys.readouterr()
    assert code == 130
    assert captured.out == ""
    assert "interrupted" in captured.err


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
    assert "--best-effort" in result.stdout
    assert "Reserved" not in result.stdout
    assert "\x1b[" not in result.stdout


def test_width_option_controls_wrapping() -> None:
    source = 'list("aaaaaaaaaaaaaaaaaaaa" "bbbbbbbbbbbbbbbbbbbb")\n'
    narrow = run_cli(["format", "--line-width", "30"], source)
    assert narrow.returncode == 0
    assert narrow.stdout == ('list(\n    "aaaaaaaaaaaaaaaaaaaa"\n    "bbbbbbbbbbbbbbbbbbbb"\n)\n')
    wide = run_cli(["format", "--line-width", "200"], source)
    assert wide.returncode == 0
    assert wide.stdout == source


def test_lines_option_formats_multiple_selected_forms() -> None:
    source = "foo( 1 2 )\nbar( 3 4 )\nbaz( 5 6 )\n"
    result = run_cli(["format", "--lines", "1:2"], source)
    assert result.returncode == 0
    assert result.stdout == "foo(1 2)\nbar(3 4)\nbaz( 5 6 )\n"


def test_lines_option_writes_only_selection(tmp_path: Path) -> None:
    path = tmp_path / "x.il"
    path.write_text("foo( 1 2 )\nbar( 3 4 )\n", encoding="utf-8")
    result = run_cli(["format", "-w", "--lines", "1:1", str(path)])
    assert result.returncode == 0
    assert path.read_text(encoding="utf-8") == "foo(1 2)\nbar( 3 4 )\n"


def test_base_indent_option() -> None:
    result = run_cli(["format", "--base-indent", "4"], "foo( 1 2 )\n")
    assert result.returncode == 0
    assert result.stdout == "    foo(1 2)\n"


def test_stdin_path_locates_config(tmp_path: Path) -> None:
    (tmp_path / "skillfmt.toml").write_text("[format]\nindent = 2\n", encoding="utf-8")
    source = 'procedure(foo(a "t")\n1\n)\n'
    result = run_cli(
        ["format", "--stdin-path", str(tmp_path / "x.il")],
        source,
    )
    assert result.returncode == 0
    assert result.stdout == 'procedure(foo(a "t")\n  1\n)\n'


def test_only_option_enables_one_category() -> None:
    source = 'procedure(foo(a "t")\nx=1\n)\n'
    indent_only = run_cli(["format", "--only", "indent"], source)
    assert indent_only.returncode == 0
    assert indent_only.stdout == 'procedure(foo(a "t")\n    x=1\n)\n'
    spacing_only = run_cli(["format", "--only", "spacing"], source)
    assert spacing_only.returncode == 0
    assert spacing_only.stdout == 'procedure(foo(a "t")\nx=1\n)\n'


def test_quiet_suppresses_warnings() -> None:
    source = "(+ a b)\n"
    loud = run_cli(["--en", "format"], source)
    assert loud.returncode == 0
    assert "warning" in loud.stderr
    quiet = run_cli(["--en", "format", "--quiet"], source)
    assert quiet.returncode == 0
    assert quiet.stdout == source
    assert quiet.stderr == ""


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


def test_help_introduces_tool_and_commands() -> None:
    result = run_cli(["--en", "-h"], env_extra={"COLUMNS": "100"})
    assert result.returncode == 0
    assert len(result.stdout.splitlines()) <= 45
    assert "Conservative formatter for Cadence SKILL source." in result.stdout
    assert "Format files or stdin, check for differences" in result.stdout
    assert "Commands:" in result.stdout
    assert "inspect or update configuration" in result.stdout
    assert "config-template" not in result.stdout
    assert "Exit status:" not in result.stdout
    assert "Language:" not in result.stdout


def test_help_introduces_tool_and_commands_in_chinese() -> None:
    result = run_cli(["--zh", "-h"], env_extra={"COLUMNS": "100"})
    assert result.returncode == 0
    assert len(result.stdout.splitlines()) <= 45
    assert "保守格式化 Cadence SKILL 源码。" in result.stdout
    assert "支持格式化文件/stdin、检查差异" in result.stdout
    assert "命令" in result.stdout
    assert "查看或修改配置" in result.stdout
    assert "config-template" not in result.stdout
    assert "退出码:" not in result.stdout
    assert "语言:" not in result.stdout


def test_config_template_is_loadable(tmp_path: Path) -> None:
    result = run_cli(["--en", "config", "template"])
    assert result.returncode == 0
    assert result.stderr == ""
    target = tmp_path / "skillfmt.toml"
    target.write_text(result.stdout, encoding="utf-8")
    options = load_config(target)
    assert options.width == 150
    assert options.indent == 4
    assert options.base_indent is None
    assert options.unknown == "opaque"
    assert options.config_path == str(target)


def test_config_template_uses_selected_language() -> None:
    chinese = run_cli(["config", "template", "--zh"])
    english = run_cli(["config", "template", "--en"])
    assert chinese.returncode == 0
    assert english.returncode == 0
    zh_text = chinese.stdout
    en_text = english.stdout
    assert "配置" in zh_text
    assert "缩进" in zh_text
    assert "configuration" in en_text
    assert "indentation" in en_text
    assert "width = 150" in zh_text
    assert "width = 150" in en_text


def test_config_help_lists_nested_subcommands() -> None:
    result = run_cli(["--en", "config", "-h"], env_extra={"COLUMNS": "100"})
    assert result.returncode == 0
    assert "{template,get,set,trace}" in result.stdout
    assert "--config PATH" not in result.stdout
    leaf = run_cli(["--en", "config", "get", "-h"], env_extra={"COLUMNS": "100"})
    assert leaf.returncode == 0
    assert "--config PATH" in leaf.stdout


def test_config_requires_a_subcommand() -> None:
    missing = run_cli(["--en", "config"])
    assert missing.returncode == 2
    get_without_key = run_cli(["--en", "config", "get"])
    assert get_without_key.returncode == 2


def test_config_rejects_extra_arguments() -> None:
    result = run_cli(["--en", "config", "template", "missing.il"])
    assert result.returncode == 2
    assert result.stdout == ""


def test_config_get_uses_defaults(tmp_path: Path) -> None:
    width = run_cli(["--en", "config", "get", "format.width"], cwd=tmp_path)
    assert width.returncode == 0
    assert width.stdout == "150\n"
    base = run_cli(["--en", "config", "get", "format.base_indent"], cwd=tmp_path)
    assert base.stdout == "unset\n"
    wrapping = run_cli(["--en", "config", "get", "categories.wrapping"], cwd=tmp_path)
    assert wrapping.stdout == "true\n"
    hanging = run_cli(["--en", "config", "get", "rules.hanging"], cwd=tmp_path)
    assert hanging.stdout == (
        '["let", "letseq", "letrec", "prog", "case", "if", "when", "unless", '
        '"while", "foreach", "for", "quote"]\n'
    )


def test_config_get_rejects_unknown_key(tmp_path: Path) -> None:
    result = run_cli(["--en", "config", "get", "format.nope"], cwd=tmp_path)
    assert result.returncode == 2
    assert "unknown configuration key" in result.stderr


def test_config_trace_is_blank_without_file(tmp_path: Path) -> None:
    defaults = run_cli(["--en", "config", "trace"], cwd=tmp_path)
    assert defaults.returncode == 0
    assert defaults.stdout == ""
    assert defaults.stderr == ""
    target = tmp_path / "skillfmt.toml"
    target.write_text("[format]\nwidth = 120\n", encoding="utf-8")
    traced = run_cli(["--en", "config", "trace"], cwd=tmp_path)
    assert traced.returncode == 0
    assert str(target.resolve()) in traced.stdout
    width = run_cli(["--en", "config", "get", "format.width"], cwd=tmp_path)
    assert width.stdout == "120\n"


def test_config_set_creates_and_updates_file(tmp_path: Path) -> None:
    created = run_cli(["--en", "config", "set", "format.width", "100"], cwd=tmp_path)
    assert created.returncode == 0
    target = tmp_path / "skillfmt.toml"
    assert target.is_file()
    assert "updated:" in created.stdout
    assert load_config(target).width == 100
    updated = run_cli(["--en", "config", "set", "format.indent", "2"], cwd=tmp_path)
    assert updated.returncode == 0
    options = load_config(target)
    assert options.width == 100
    assert options.indent == 2


def test_config_set_preserves_comments_and_other_keys(tmp_path: Path) -> None:
    target = tmp_path / "skillfmt.toml"
    target.write_text(
        "# keep this comment\n[format]\nwidth = 150\nindent = 2\n",
        encoding="utf-8",
    )
    result = run_cli(["--en", "config", "set", "format.width", "90"], cwd=tmp_path)
    assert result.returncode == 0
    text = target.read_text(encoding="utf-8")
    assert "# keep this comment" in text
    assert "indent = 2" in text
    options = load_config(target)
    assert options.width == 90
    assert options.indent == 2


def test_config_set_boolean_and_list_values(tmp_path: Path) -> None:
    target = tmp_path / "skillfmt.toml"
    target.write_text("", encoding="utf-8")
    wrapping = run_cli(["--en", "config", "set", "categories.wrapping", "false"], cwd=tmp_path)
    assert wrapping.returncode == 0
    hanging = run_cli(
        ["--en", "config", "set", "rules.hanging", '["let", "quote"]'],
        cwd=tmp_path,
    )
    assert hanging.returncode == 0
    options = load_config(target)
    assert "wrapping" not in options.categories
    assert options.hanging == ("let", "quote")


def test_config_set_unset_restores_default(tmp_path: Path) -> None:
    target = tmp_path / "skillfmt.toml"
    target.write_text("[format]\nwidth = 90\n", encoding="utf-8")
    result = run_cli(["--en", "config", "set", "format.width", "unset"], cwd=tmp_path)
    assert result.returncode == 0
    assert "width =" not in target.read_text(encoding="utf-8")
    assert load_config(target).width == 150


def test_config_set_invalid_value_does_not_write(tmp_path: Path) -> None:
    target = tmp_path / "skillfmt.toml"
    original = "[format]\nwidth = 150\n"
    target.write_text(original, encoding="utf-8")
    result = run_cli(["--en", "config", "set", "format.width", "10"], cwd=tmp_path)
    assert result.returncode == 2
    assert "must be >= 20" in result.stderr
    assert target.read_text(encoding="utf-8") == original


def test_config_set_rejects_unknown_key(tmp_path: Path) -> None:
    target = tmp_path / "skillfmt.toml"
    original = "[format]\nwidth = 150\n"
    target.write_text(original, encoding="utf-8")
    result = run_cli(["--en", "config", "set", "format.nope", "1"], cwd=tmp_path)
    assert result.returncode == 2
    assert "unknown configuration key" in result.stderr
    assert target.read_text(encoding="utf-8") == original


def test_config_set_does_not_overwrite_invalid_file(tmp_path: Path) -> None:
    target = tmp_path / "skillfmt.toml"
    original = "not = [\n"
    target.write_text(original, encoding="utf-8")
    result = run_cli(["--en", "config", "set", "format.width", "90"], cwd=tmp_path)
    assert result.returncode == 2
    assert target.read_text(encoding="utf-8") == original


def test_config_set_and_get_with_explicit_path(tmp_path: Path) -> None:
    target = tmp_path / "custom.toml"
    set_result = run_cli(
        ["--en", "config", "set", "--config", str(target), "format.width", "88"],
        cwd=tmp_path,
    )
    assert set_result.returncode == 0
    assert load_config(target).width == 88
    get_result = run_cli(
        ["--en", "config", "get", "--config", str(target), "format.width"],
        cwd=tmp_path,
    )
    assert get_result.returncode == 0
    assert get_result.stdout == "88\n"


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
