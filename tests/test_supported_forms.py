from __future__ import annotations

from skfmt import format_source

FORMS = {
    "c-call": ("foo(a b)", "foo(a b)\n"),
    "s-call": ("(foo a b)", "foo(a b)\n"),
    "group": ("(a + b)", "(a + b)\n"),
    "putprop": ("a~>b", "a~>b\n"),
    "tight-access": ("car(g_edge)->x()", "car(g_edge)->x()\n"),
    "cond": (
        "(cond ((foo a) (bar b)) (t nil))",
        "cond(\n    (foo(a) bar(b))\n    (t nil)\n)\n",
    ),
    "case": (
        'case(x\n("a" 1)\n("bb" 2)\n(t 3)\n)',
        'case(x\n    ("a"  1)\n    ("bb" 2)\n    (t    3)\n)\n',
    ),
    "let": ("let((len i)\nlen = 1\n)", "let((len i)\n    len = 1\n)\n"),
    "errset": ("errset(\n(foo a)\nnil\n)", "errset(foo(a) nil)\n"),
    "if-then-else": (
        "if(ca == cb\nthen\ni++\nelse\na = 1\n)",
        "if(ca == cb\nthen\n    i++\nelse\n    a = 1\n)\n",
    ),
    "unknown-macro": ("(myMacro (a b))", "myMacro((a b))\n"),
}


def test_documented_forms_match_implementation() -> None:
    for name, (source, expected) in FORMS.items():
        assert format_source(source).text == expected, name
