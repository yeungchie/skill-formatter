from __future__ import annotations

import pytest

from skfmt import CATEGORIES, Options, format_range
from skfmt.formatter import FormatError

SOURCE = """useNamespace("x")
procedure(foo(a "t")
let((x)
x=1
when(x
printf("hi")
)
)
)
; END
"""


def test_range_keeps_outside_bytes_and_formats_the_fragment() -> None:
    result = format_range(SOURCE, [(5, 7)])
    assert result.text.startswith('useNamespace("x")\nprocedure(foo(a "t")\nlet((x)\nx=1\n')
    assert 'when(x\n    printf("hi")\n)\n' in result.text
    assert result.text.endswith(")\n; END\n")


def test_range_preserves_fragment_base_indent() -> None:
    source = 'procedure(foo()\n    when(x\n    printf("hi")\n    )\n)\n'
    result = format_range(source, [(2, 4)])
    assert result.text == 'procedure(foo()\n    when(x\n        printf("hi")\n    )\n)\n'


def test_range_does_not_expand_to_the_enclosing_form() -> None:
    source = (
        "inScheme(\n"
        "defmethod(a (self(A))\n"
        "    let((x)\n"
        "        foo( 1 2 )\n"
        "        bar( 3 4 )\n"
        "    )\n"
        ")\n"
        "defmethod(b (self(B))\n"
        "    baz( 5 6 )\n"
        ")\n"
        ")\n"
    )
    result = format_range(source, [(4, 5)])
    assert result.text == (
        "inScheme(\n"
        "defmethod(a (self(A))\n"
        "    let((x)\n"
        "        foo(1 2)\n"
        "        bar(3 4)\n"
        "    )\n"
        ")\n"
        "defmethod(b (self(B))\n"
        "    baz( 5 6 )\n"
        ")\n"
        ")\n"
    )


def test_range_leaves_incomplete_fragment_unchanged() -> None:
    source = "procedure(foo()\n    bar( 1 2\n)\n)\n"
    result = format_range(source, [(2, 2)])
    assert result.text == source
    assert any("unchanged" in warning for warning in result.warnings)


def test_range_leaves_context_sensitive_fragment_unchanged() -> None:
    source = 'cond(\n    (pcreMatchp("^true" t_name) "True")\n)\n'
    result = format_range(source, [(2, 2)])
    assert result.text == source
    assert any("structure changed" in warning for warning in result.warnings)


def test_range_is_idempotent_with_boundary_blank_lines() -> None:
    source = 'useNamespace("x")\n\n\n; comment\n\nprocedure(a()\n1\n)\n'
    once = format_range(source, [(1, 4)]).text
    assert format_range(once, [(1, 4)]).text == once


def test_range_can_format_a_top_level_form() -> None:
    result = format_range(SOURCE, [(2, 9)])
    assert "    let((x)\n        x=1\n" in result.text
    assert result.text.startswith('useNamespace("x")\nprocedure(foo(a "t")\n')


def test_range_formats_multiple_top_level_forms() -> None:
    source = "foo( 1 2 )\nbar( 3 4 )\nbaz( 5 6 )\n"
    result = format_range(source, [(1, 2)])
    assert result.text == "foo(1 2)\nbar(3 4)\nbaz( 5 6 )\n"


def test_range_formats_multiple_forms_with_definition_blank_lines() -> None:
    source = "procedure(a()\n  1\n)\nfoo( 1 2 )\n\nprocedure(b()\n  2\n)\n"
    result = format_range(source, [(1, 4)])
    assert result.text == ("procedure(a()\n    1\n)\nfoo(1 2)\n\nprocedure(b()\n  2\n)\n")


def test_range_deduplicates_overlapping_selections() -> None:
    source = "foo( 1 2 )\nbar( 3 4 )\nbaz( 5 6 )\n"
    result = format_range(source, [(1, 2), (2, 3)])
    assert result.text == "foo(1 2)\nbar(3 4)\nbaz(5 6)\n"


def test_comment_only_range_is_noop() -> None:
    source = "a = 1\n; only comment\nb = 2\n"
    assert format_range(source, [(2, 2)]).text == source


def test_base_indent_override() -> None:
    source = "foo(a)\n"
    assert format_range(source, [(1, 1)], options=None).text == "foo(a)\n"


def test_range_requires_wrapping() -> None:
    categories = frozenset(CATEGORIES) - {"wrapping"}
    with pytest.raises(FormatError):
        format_range("a=1\n", [(1, 1)], Options(categories=categories))


def test_range_rejects_conservative_unknown_policy() -> None:
    with pytest.raises(FormatError):
        format_range("(+ a b)\n", [(1, 1)], Options(unknown="conservative"))
