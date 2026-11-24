from __future__ import annotations

from pathlib import Path

from skill_formatter import format_source
from skill_formatter.config import load_config


def _config(tmp_path: Path, text: str):
    path = tmp_path / "skillfmt.toml"
    path.write_text(text, encoding="utf-8")
    return load_config(path)


def test_format_width(tmp_path: Path) -> None:
    source = 'list("aaaaaaaaaaaaaaaaaaaa" "bbbbbbbbbbbbbbbbbbbb")\n'
    result = format_source(source, _config(tmp_path, "[format]\nwidth = 30\n"))
    assert result.text == 'list(\n    "aaaaaaaaaaaaaaaaaaaa"\n    "bbbbbbbbbbbbbbbbbbbb"\n)\n'


def test_format_indent(tmp_path: Path) -> None:
    result = format_source(
        "procedure(a()\n1\n)\n",
        _config(tmp_path, "[format]\nindent = 2\n"),
    )
    assert result.text == "procedure(a()\n  1\n)\n"


def test_format_base_indent(tmp_path: Path) -> None:
    result = format_source("foo( 1 2 )\n", _config(tmp_path, "[format]\nbase_indent = 4\n"))
    assert result.text == "    foo(1 2)\n"


def test_categories_eol(tmp_path: Path) -> None:
    result = format_source(
        "foo( 1 2 )\r\nbar(3 4)",
        _config(tmp_path, "[categories]\neol = false\n"),
    )
    assert result.text == "foo(1 2)\r\nbar(3 4)"


def test_categories_blank_lines(tmp_path: Path) -> None:
    source = "procedure(a()\n1\n)\n\n\n\nprocedure(b()\n2\n)\n"
    result = format_source(
        source,
        _config(tmp_path, "[categories]\nblank-lines = false\n"),
    )
    assert result.text == "procedure(a()\n    1\n)\n\n\n\nprocedure(b()\n    2\n)\n"


def test_categories_indent(tmp_path: Path) -> None:
    result = format_source(
        "procedure(a()\n1\n)\n",
        _config(tmp_path, "[categories]\nindent = false\n"),
    )
    assert result.text == "procedure(a()\n1\n)\n"
    assert any("indent" in warning for warning in result.warnings)


def test_categories_spacing(tmp_path: Path) -> None:
    result = format_source(
        "foo( 1  2 )\n",
        _config(tmp_path, "[categories]\nspacing = false\n"),
    )
    assert result.text == "foo( 1  2 )\n"
    assert any("spacing" in warning for warning in result.warnings)


def test_categories_wrapping(tmp_path: Path) -> None:
    result = format_source(
        "foo(1\n2)\n",
        _config(tmp_path, "[categories]\nwrapping = false\n"),
    )
    assert result.text == "foo(1\n    2)\n"


def test_categories_comments(tmp_path: Path) -> None:
    result = format_source(
        "procedure(a()\n; c\n1\n)\n",
        _config(tmp_path, "[categories]\ncomments = false\n"),
    )
    assert result.text == "procedure(a()\n; c\n    1\n)\n"
    assert any("comments" in warning for warning in result.warnings)


def test_rules_case(tmp_path: Path) -> None:
    source = 'case(x\n("a" 1)\n("bb" 2)\n)\n'
    result = format_source(source, _config(tmp_path, '[rules]\ncase = "block"\n'))
    assert result.text == 'case(x\n    ("a" 1)\n    ("bb" 2)\n)\n'


def test_rules_in_scheme(tmp_path: Path) -> None:
    source = "inScheme(\ndefmethod(x (self(A))  ; -> t\n1\n)\n)\n"
    result = format_source(source, _config(tmp_path, '[rules]\ninScheme = "indent"\n'))
    assert result.text == ("inScheme(\n    defmethod(x (self(A))  ; -> t\n        1\n    )\n)\n")
