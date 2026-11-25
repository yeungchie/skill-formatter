from __future__ import annotations

from pathlib import Path

import pytest

from skfmt import CATEGORIES, Options, format_source
from skfmt.config import load_config


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("foo(a b)", "foo(a b)\n"),
        ("(foo a b)", "foo(a b)\n"),
        ("(cond ((foo a) (bar b)) (t nil))", "cond(\n    (foo(a) bar(b))\n    (t nil)\n)\n"),
        ("(myMacro (a b))", "myMacro((a b))\n"),
        ("(a + b)", "(a + b)\n"),
        ("!(a && b)", "!(a && b)\n"),
        ("a~>b", "a~>b\n"),
        ("a ~> b", "a~>b\n"),
        ("car(g_edge)->x()", "car(g_edge)->x()\n"),
        ("x = remainder(n 3600)/60", "x = remainder(n 3600) / 60\n"),
        ("let((len i)\nlen = 1\n)", "let((len i)\n    len = 1\n)\n"),
        (
            "if(ca == cb\nthen\ni++\nj++\nelse\na = 1\n)",
            "if(ca == cb\nthen\n    i++\n    j++\nelse\n    a = 1\n)\n",
        ),
        (
            'case(x\n("a" 1)\n("bb" 2)\n(t 3)\n)',
            'case(x\n    ("a"  1)\n    ("bb" 2)\n    (t    3)\n)\n',
        ),
        ("errset(\n(foo a)\nnil\n)", "errset(foo(a) nil)\n"),
    ],
)
def test_basic_layouts(source: str, expected: str) -> None:
    assert format_source(source).text == expected


def test_hanging_controls_head_line() -> None:
    source = "let((len i)\nlen = 1\n)"
    assert format_source(source).text == "let((len i)\n    len = 1\n)\n"
    assert format_source(source, Options(hanging=())).text == (
        "let(\n    (len i)\n    len = 1\n)\n"
    )
    generic = 'foo("' + "a" * 20 + '" "' + "b" * 20 + '")'
    assert format_source(generic, Options(width=40, hanging=("foo",))).text == (
        'foo("' + "a" * 20 + '"\n    "' + "b" * 20 + '"\n)\n'
    )


def test_invalid_property_access_is_left_opaque() -> None:
    for source in ("a->()\n", "let(() a->())\n", "let(() a~>())\n"):
        result = format_source(source)
        assert result.text == source
        assert any("non-symbol right operand" in warning for warning in result.warnings)


def test_config_hanging_changes_layout(tmp_path: Path) -> None:
    config = tmp_path / "skfmt.toml"
    config.write_text("[rules]\nhanging = []\n", encoding="utf-8")
    result = format_source("let((len i)\nlen = 1\n)", load_config(config)).text
    assert result == "let(\n    (len i)\n    len = 1\n)\n"


def test_disabling_spacing_falls_back_to_conservative_layout() -> None:
    categories = frozenset(CATEGORIES) - {"spacing"}
    result = format_source("a=1\n", Options(categories=categories))
    assert result.text == "a=1\n"
    assert any("wrapping disabled" in warning for warning in result.warnings)


def test_defclass_slots() -> None:
    source = "defclass(Point () (x(\\@initarg x \\@initform 0.0) y()))"
    expected = (
        "defclass(Point () (\n"
        "    x(\n"
        "        \\@initarg x\n"
        "        \\@initform 0.0\n"
        "    )\n"
        "    y()\n"
        "))\n"
    )
    assert format_source(source).text == expected


def test_definition_and_lambda_layouts() -> None:
    assert format_source('procedure(foo(a "t")\n; doc\na = 1\n)').text == (
        'procedure(foo(a "t")\n    ; doc\n    a = 1\n)\n'
    )
    defmethod = 'defmethod(printself (self(Point))  ; -> str\n; doc\nlsprintf("x")\n)'
    expected = 'defmethod(printself (self(Point))  ; -> str\n    ; doc\n    lsprintf("x")\n)\n'
    assert format_source(defmethod).text == expected
    assert format_source('self->f = lambda((a b "gg")  ; -> t\na = 1\n)').text == (
        'self->f = lambda((a b "gg")  ; -> t\n    a = 1\n)\n'
    )


def test_in_scheme_body_stays_at_column_zero() -> None:
    source = "inScheme(\ndefmethod(x (self(A))  ; -> t\n1\n)\n)\n"
    expected = "inScheme(\ndefmethod(x (self(A))  ; -> t\n    1\n)\n)\n"
    assert format_source(source).text == expected


def test_idempotent() -> None:
    samples = [
        'procedure(foo(a "t")\n; doc\nlet((x)\nx = 1\n)\n)\n',
        "cond(\n(a (foo b))\n(t nil)\n)\n",
        'case(x\n("a" 1)\n(t 2)\n)\n',
        "errset({ (foo a) (bar b) } nil)\n",
    ]
    for sample in samples:
        once = format_source(sample).text
        assert format_source(once).text == once


def test_wrapping_off_keeps_line_breaks() -> None:
    from skfmt import CATEGORIES, Options

    source = 'procedure(foo(a "t")\nlet((x)\nx = 1\n)\n)\n'
    options = Options(categories=frozenset(CATEGORIES) - {"wrapping"})
    result = format_source(source, options).text
    assert result.count("\n") == source.count("\n")
    assert result == 'procedure(foo(a "t")\n    let((x)\n        x = 1\n    )\n)\n'


def test_two_blank_lines_between_definitions() -> None:
    source = "procedure(a()\n1\n)\nprocedure(b()\n2\n)\n"
    expected = "procedure(a()\n    1\n)\n\n\nprocedure(b()\n    2\n)\n"
    assert format_source(source).text == expected


def test_list_wraps_one_element_per_line() -> None:
    assert format_source("list(1 2 3333)").text == "list(1 2 3333)\n"
    assert format_source("list(1 2 3333)", Options(width=13)).text == (
        "list(\n    1\n    2\n    3333\n)\n"
    )
    long = 'list("' + "a" * 80 + '" "' + "b" * 80 + '")'
    expected = 'list(\n    "' + "a" * 80 + '"\n    "' + "b" * 80 + '"\n)\n'
    assert format_source(long).text == expected


def test_arguments_wrap_in_three_tiers() -> None:
    source = "myfunction(aaaa bbbb cccc)"
    assert format_source(source, Options(width=40)).text == source + "\n"
    assert format_source(source, Options(width=25)).text == ("myfunction(\n    aaaa bbbb cccc\n)\n")
    assert format_source(source, Options(width=17)).text == (
        "myfunction(\n    aaaa\n    bbbb\n    cccc\n)\n"
    )


def test_wrapped_arguments_never_mix_packed_and_split_lines() -> None:
    source = "myfunction(aaaa bbbb ccccccccccccc)"
    result = format_source(source, Options(width=25)).text
    assert result == "myfunction(\n    aaaa\n    bbbb\n    ccccccccccccc\n)\n"


def test_second_tier_keeps_nested_indent() -> None:
    source = "let((x)\nmyfunction(aaaa bbbb cccc)\n)"
    expected = "let((x)\n    myfunction(\n        aaaa bbbb cccc\n    )\n)\n"
    assert format_source(source, Options(width=29)).text == expected


def test_nested_calls_break_outermost_first() -> None:
    source = "foo1(foo2(a b c))"
    assert format_source(source, Options(width=16)).text == "foo1(\n    foo2(a b c)\n)\n"
    deep = "foo1(foo2(foo3(aaaaaaaaaa bbbbbbbbbb)))"
    result = format_source(deep, Options(width=20)).text
    assert result == (
        "foo1(\n"
        "    foo2(\n"
        "        foo3(\n"
        "            aaaaaaaaaa\n"
        "            bbbbbbbbbb\n"
        "        )\n"
        "    )\n"
        ")\n"
    )
    assert "foo1(foo2(" not in result
    assert "foo2(foo3(" not in result


def test_errset_brace_follows_call_wrapping() -> None:
    source = "errset({ nil ,@l_body } nil)"
    assert format_source(source).text == "errset({nil ,@l_body} nil)\n"
    assert format_source(source, Options(width=22)).text == ("errset(\n    {nil ,@l_body} nil\n)\n")
    assert format_source(source, Options(width=21)).text == (
        "errset(\n    {nil ,@l_body}\n    nil\n)\n"
    )
    assert format_source(source, Options(width=17)).text == (
        "errset(\n    {\n        nil\n        ,@l_body\n    }\n    nil\n)\n"
    )


def test_tight_brackets_is_configurable() -> None:
    spaced = frozenset(CATEGORIES) - {"tight-brackets"}
    assert format_source("foo( a b c )").text == "foo(a b c)\n"
    assert format_source("{ nil ,@l_body }").text == "{nil ,@l_body}\n"
    assert format_source("[ 1 2 3 ]").text == "[1 2 3]\n"
    assert format_source("a[ 0 ]").text == "a[0]\n"
    assert format_source("foo(a b c)", Options(categories=spaced)).text == "foo( a b c )\n"
    assert format_source("{nil ,@l_body}", Options(categories=spaced)).text == (
        "{ nil ,@l_body }\n"
    )
    assert format_source("[1 2 3]", Options(categories=spaced)).text == "[ 1 2 3 ]\n"
    assert format_source("a[0]", Options(categories=spaced)).text == "a[ 0 ]\n"
    assert format_source("errset(foo(a) nil)", Options(categories=spaced)).text == (
        "errset( foo( a ) nil )\n"
    )


def test_foreach_keeps_head_when_it_fits() -> None:
    source = "foreach(mapcar x list(1 2 3) long_long_command)"
    assert format_source(source, Options(width=40)).text == (
        "foreach(mapcar x list(1 2 3)\n    long_long_command\n)\n"
    )
    assert format_source(source, Options(width=21)).text == (
        "foreach(mapcar x\n    list(1 2 3)\n    long_long_command\n)\n"
    )
    plain = "foreach(x list(1 2 3) do_it)"
    assert format_source(plain, Options(width=24)).text == ("foreach(x list(1 2 3)\n    do_it\n)\n")
    assert format_source(plain, Options(width=20)).text == (
        "foreach(x\n    list(1 2 3)\n    do_it\n)\n"
    )


def test_foreach_multiple_lists_stay_with_variables() -> None:
    source = "foreach((x y) list(1 2) list(3 4) body_long)"
    assert format_source(source, Options(width=40)).text == (
        "foreach((x y) list(1 2) list(3 4)\n    body_long\n)\n"
    )
    assert format_source(source, Options(width=30)).text == (
        "foreach((x y)\n    list(1 2)\n    list(3 4)\n    body_long\n)\n"
    )


def test_assignments_align_without_blank_lines() -> None:
    source = "a = 1\nab = 2  ; ab is a variable\nabc = 33  ; abc is a variable\n"
    expected = "a   = 1\nab  = 2   ; ab is a variable\nabc = 33  ; abc is a variable\n"
    assert format_source(source).text == expected


def test_assignment_alignment_groups_break_on_blank_lines_and_other_forms() -> None:
    source = "a = 1\nab = 2\n\nc = 3\nd = 4\nfoo(1)\ne = 5\n"
    expected = "a  = 1\nab = 2\n\nc = 3\nd = 4\n\n\nfoo(1)\n\n\ne = 5\n"
    assert format_source(source).text == expected


def test_top_level_statements_get_two_blank_lines() -> None:
    source = "foo(1)\nbar(2)\nbaz(3)\n"
    assert format_source(source).text == "foo(1)\n\n\nbar(2)\n\n\nbaz(3)\n"


def test_top_level_assignment_groups_keep_one_blank_line() -> None:
    source = "a = 1\nb = 2\n\nc = 3\n"
    assert format_source(source).text == "a = 1\nb = 2\n\nc = 3\n"


def test_top_level_comment_stays_with_following_statement() -> None:
    source = "foo(1)\n; doc\nbar(2)\n"
    assert format_source(source).text == "foo(1)\n\n\n; doc\nbar(2)\n"


def test_nested_statements_keep_single_blank_lines() -> None:
    source = "procedure(a()\nfoo(1)\nbar(2)\n)\n"
    assert format_source(source).text == "procedure(a()\n    foo(1)\n    bar(2)\n)\n"


def test_assignment_alignment_can_be_disabled() -> None:
    cats = frozenset(CATEGORIES) - {"align-assignments"}
    source = "a = 1\nabc = 33\n"
    assert format_source(source, Options(categories=cats)).text == source


def test_assignment_alignment_yields_to_line_width() -> None:
    source = "a = 1  ; x\nabc = 333  ; y\n"
    assert format_source(source, Options(width=13)).text == source


def test_comment_stays_with_following_definition() -> None:
    source = "procedure(a()\n1\n)\n\n; doc\nprocedure(b()\n2\n)\n"
    expected = "procedure(a()\n    1\n)\n\n\n; doc\nprocedure(b()\n    2\n)\n"
    assert format_source(source).text == expected
