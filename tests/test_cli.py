from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run_cli(args: list[str], data: str | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["NO_COLOR"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "skill_formatter", *args],
        input=data,
        text=True,
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
    result = run_cli(["-h"])
    assert result.returncode == 0
    assert "Usage: skillfmt" in result.stdout
    assert "--width" in result.stdout
    assert "\x1b[" not in result.stdout


def test_width_option_controls_wrapping() -> None:
    source = 'list("aaaaaaaaaaaaaaaaaaaa" "bbbbbbbbbbbbbbbbbbbb")\n'
    narrow = run_cli(["--width", "30"], source)
    assert narrow.returncode == 0
    assert narrow.stdout == ('list(\n    "aaaaaaaaaaaaaaaaaaaa"\n    "bbbbbbbbbbbbbbbbbbbb"\n)\n')
    wide = run_cli(["--width", "200"], source)
    assert wide.returncode == 0
    assert wide.stdout == source
