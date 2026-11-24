from __future__ import annotations

from skill_formatter.lexer import lex


def kinds(source: str) -> list[str]:
    return [token.kind for token in lex(source).tokens]


def test_call_adjacency_is_preserved() -> None:
    tokens = lex("foo(a b)").tokens
    assert [t.text for t in tokens[:-1]] == ["foo", "(", "a", "b", ")"]
    assert tokens[1].gap == ""
    assert tokens[2].gap == ""


def test_spaced_paren_is_not_a_call() -> None:
    tokens = lex("foo (a)").tokens
    assert tokens[1].gap == " "


def test_operators_are_only_split_when_spaced() -> None:
    tight = lex("a->b 1:2 x=1").tokens
    assert [t.text for t in tight[:-1]] == ["a->b", "1:2", "x=1"]
    spaced = lex("a + b").tokens
    assert [t.text for t in spaced[:-1]] == ["a", "+", "b"]


def test_logical_or_and_quoted_symbol() -> None:
    assert [t.text for t in lex("a || b").tokens[:-1]] == ["a", "||", "b"]
    assert [t.text for t in lex("a | b").tokens[:-1]] == ["a", "|", "b"]
    assert lex("|quoted symbol|").tokens[0].kind == "unsupported"


def test_comments_strings_and_prefixes() -> None:
    tokens = lex("; c\n'foo `bar ,baz ,@qux #.eval").tokens
    assert tokens[0].kind == "comment"
    assert [t.text for t in tokens[1:-1]] == [
        "'",
        "foo",
        "`",
        "bar",
        ",",
        "baz",
        ",@",
        "qux",
        "#.",
        "eval",
    ]


def test_block_comment_is_unsupported() -> None:
    tokens = lex("/* c */ foo()").tokens
    assert tokens[0].kind == "unsupported"


def test_eol_detection() -> None:
    assert lex("a\r\nb\r\n").eol == "\r\n"
    assert lex("a\nb\n").eol == "\n"
