from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


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
    result = run_cli([], 'procedure(foo(a "t")\na = 1\n)\n')
    assert result.returncode == 0
    assert 'procedure(foo(a "t")\n    a = 1\n)\n' == result.stdout


def test_stdin_check() -> None:
    result = run_cli(["--check"], 'procedure(foo(a "t")\na = 1\n)\n')
    assert result.returncode == 1
    assert "would reformat" in result.stdout


def test_error_echoes_original_stdin() -> None:
    source = "(+ a b)\n"
    result = run_cli(["--strict"], source)
    assert result.returncode == 2
    assert result.stdout == source


def test_write_in_place(tmp_path: Path) -> None:
    path = tmp_path / "x.il"
    path.write_text('procedure(foo(a "t")\na = 1\n)\n', encoding="utf-8")
    result = run_cli(["-w", str(path)])
    assert result.returncode == 0
    assert 'procedure(foo(a "t")\n    a = 1\n)\n' == path.read_text(encoding="utf-8")


def test_help_is_stable_without_color() -> None:
    result = run_cli(["-h"], env_extra={"SKILLFMT_LANG": "en"})
    assert result.returncode == 0
    assert "Usage: skillfmt" in result.stdout
    assert "--line-width" in result.stdout
    assert "\x1b[" not in result.stdout


def test_width_option_controls_wrapping() -> None:
    source = 'list("aaaaaaaaaaaaaaaaaaaa" "bbbbbbbbbbbbbbbbbbbb")\n'
    narrow = run_cli(["--line-width", "30"], source)
    assert narrow.returncode == 0
    assert narrow.stdout == ('list(\n    "aaaaaaaaaaaaaaaaaaaa"\n    "bbbbbbbbbbbbbbbbbbbb"\n)\n')
    wide = run_cli(["--line-width", "200"], source)
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
