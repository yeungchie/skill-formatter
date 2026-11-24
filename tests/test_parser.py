from __future__ import annotations

from skfmt.formatter import _canonical_without_opaque, _parse


def canon(source: str) -> str:
    _, root, _, _ = _parse(source)
    return _canonical_without_opaque(root)


def test_s_style_call_is_normalised_to_c_structure() -> None:
    assert canon("(foo a b)") == "(foo a b)"
    assert canon("foo(a b)") == "(foo a b)"


def test_cond_clause_stays_a_list_but_inside_calls_convert() -> None:
    assert canon("(cond ((foo a) (bar b)) (t nil))") == ("(cond ((foo a) (bar b)) (t nil))")


def test_let_binding_values_are_code() -> None:
    assert canon("(let (x) (foo x))") == "(let (x) (foo x))"


def test_unknown_macro_arguments_are_not_converted() -> None:
    assert canon("(myMacro (a b))") == "(myMacro (a b))"


def test_infix_and_grouped_expressions() -> None:
    assert canon("a + b * c") == "(+ a (* b c))"
    assert canon("(a + b)") == "(group (+ a b))"
    assert canon("!(a && b)") == "(! (group (&& a b)))"
    assert canon("a~>b") == "(~> a b)"
    assert canon("a -> b") == "(-> a b)"
    assert canon("g_err->context()") == "(-> g_err (context))"


def test_operator_headed_forms_are_opaque() -> None:
    _, _, warnings, opaque = _parse("(+ a b)")
    assert warnings and opaque
    _, _, warnings, opaque = _parse("+(a b)")
    assert warnings and opaque
