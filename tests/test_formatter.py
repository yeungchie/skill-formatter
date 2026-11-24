from __future__ import annotations

import pytest

from skill_formatter import format_source


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
        ("errset(\n(foo a)\nnil\n)", "errset(\n    foo(a)\n    nil\n)\n"),
    ],
)
def test_basic_layouts(source: str, expected: str) -> None:
    assert format_source(source).text == expected


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
    from skill_formatter import CATEGORIES, Options

    source = 'procedure(foo(a "t")\nlet((x)\nx = 1\n)\n)\n'
    options = Options(categories=frozenset(CATEGORIES) - {"wrapping"})
    result = format_source(source, options).text
    assert result.count("\n") == source.count("\n")
    assert result == 'procedure(foo(a "t")\n    let((x)\n        x = 1\n    )\n)\n'


def test_two_blank_lines_between_definitions() -> None:
    source = "procedure(a()\n1\n)\nprocedure(b()\n2\n)\n"
    expected = "procedure(a()\n    1\n)\n\n\nprocedure(b()\n    2\n)\n"
    assert format_source(source).text == expected


def test_comment_stays_with_following_definition() -> None:
    source = "procedure(a()\n1\n)\n\n; doc\nprocedure(b()\n2\n)\n"
    expected = "procedure(a()\n    1\n)\n\n\n; doc\nprocedure(b()\n    2\n)\n"
    assert format_source(source).text == expected
