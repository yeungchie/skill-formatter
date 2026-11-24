from __future__ import annotations

from skill_formatter import format_range

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


def test_range_keeps_outside_bytes_and_uses_structural_indent() -> None:
    result = format_range(SOURCE, [(5, 7)])
    assert result.text.startswith('useNamespace("x")\nprocedure(foo(a "t")\nlet((x)\nx=1\n')
    assert '        when(x\n            printf("hi")\n        )\n' in result.text
    assert result.text.endswith(")\n; END\n")


def test_range_can_format_a_top_level_form() -> None:
    result = format_range(SOURCE, [(2, 9)])
    assert "    let((x)\n        x=1\n" in result.text
    assert result.text.startswith('useNamespace("x")\nprocedure(foo(a "t")\n')


def test_comment_only_range_is_noop() -> None:
    source = "a = 1\n; only comment\nb = 2\n"
    assert format_range(source, [(2, 2)]).text == source


def test_base_indent_override() -> None:
    source = "foo(a)\n"
    assert format_range(source, [(1, 1)], options=None).text == "foo(a)\n"
