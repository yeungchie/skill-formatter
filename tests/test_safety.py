from __future__ import annotations

import pytest

from skill_formatter import Options, format_source
from skill_formatter.formatter import FormatError


def test_operator_head_is_left_byte_identical() -> None:
    source = "(+ a b)\n"
    result = format_source(source)
    assert result.text == source
    assert result.opaque_spans


def test_unknown_reader_syntax_is_left_byte_identical() -> None:
    source = "/* block */ foo(a b)\n"
    result = format_source(source)
    assert result.text == source
    assert result.opaque_spans


def test_strict_mode_rejects_opaque_forms() -> None:
    with pytest.raises(FormatError):
        format_source("(+ a b)\n", Options(unknown="error"))


def test_conservative_layout_for_unknown_syntax() -> None:
    result = format_source("(+ a   b)\n", Options(unknown="conservative"))
    assert result.text == "(+ a b)\n"


def test_grouped_infix_is_not_flattened() -> None:
    source = "!(_Code(t_s close) == 42 && _Code(t_s close + 1) == 47)\n"
    result = format_source(source)
    assert "!(" in result.text
    assert "== 42 &&" in result.text
