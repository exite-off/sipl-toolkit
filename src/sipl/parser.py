"""SIPL parser: source text -> typed AST (sipl.ast)."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from typing import Any

from lark import Lark, Token, Transformer, Tree, v_args
from lark.exceptions import UnexpectedCharacters, UnexpectedEOF, UnexpectedInput, UnexpectedToken, VisitError

from . import ast
from .ast import SourceSpan
from .diagnostics import SiplSyntaxError

TOKEN_NAMES = {
    "VAR": "variable",
    "INT": "number",
    "$END": "end of input",
    "OR": "'or'",
    "NOT": "'not'",
    "DIV": "'div'",
    "MOD": "'mod'",
}


def grammar_text() -> str:
    return resources.files("sipl.grammar").joinpath("sipl.lark").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _lark() -> Lark:
    return Lark(
        grammar_text(), parser="lalr", lexer="basic", propagate_positions=True, maybe_placeholders=False
    )


def parse_tree(source: str) -> Tree:
    """Raw Lark parse tree (concrete syntax). Raises SiplSyntaxError."""
    try:
        return _lark().parse(source)
    except UnexpectedInput as e:
        raise _syntax_error(e, source) from None


def parse(source: str) -> ast.Program:
    tree = parse_tree(source)
    try:
        result = _ToAst().transform(tree)
    except VisitError as e:
        if isinstance(e.orig_exc, SiplSyntaxError):
            raise e.orig_exc from None
        raise
    assert isinstance(result, ast.Program)
    return result


def parse_file(path: str) -> ast.Program:
    with open(path, encoding="utf-8") as f:
        return parse(f.read())


def _token_label(name: str) -> str:
    if name in TOKEN_NAMES:
        return TOKEN_NAMES[name]
    for t in _lark().terminals:
        if t.name == name and t.pattern.type == "str":
            return f"'{t.pattern.value}'"
    return name.lower()


def _offset_to_span(source: str, pos: int, length: int = 1) -> SourceSpan:
    line = source.count("\n", 0, pos) + 1
    col = pos - (source.rfind("\n", 0, pos) + 1) + 1
    return SourceSpan(line, col, line, col + length, pos, pos + length)


def _syntax_error(e: UnexpectedInput, source: str) -> SiplSyntaxError:
    if isinstance(e, UnexpectedToken) and e.token.type != "$END":
        tok = e.token
        expected = _expected(e)
        span = _token_span(tok)
        msg = f"unexpected {_token_label(tok.type) if tok.type in ('VAR', 'INT') else repr(str(tok))}"
        if tok.type in ("VAR", "INT"):
            msg += f" {tok!s}"
        msg += f", expected {_join(expected)}"
        before = source[: tok.start_pos or 0].rstrip()
        if before.endswith(";") and tok.type == "END":
            msg += " (a ';' before 'end' is not allowed: ';' separates statements)"
        if "';'" in expected and tok.type in _STMT_START:
            msg += " (missing ';' between statements?)"
        if "'else'" in expected and len(expected) <= 6:
            msg += " (in SIPL every 'if' needs an 'else' branch)"
        return SiplSyntaxError(msg, span, "E101")
    if isinstance(e, (UnexpectedEOF, UnexpectedToken)):
        expected = _expected(e)
        pos = len(source.rstrip())
        return SiplSyntaxError(
            f"unexpected end of input, expected {_join(expected)}", _offset_to_span(source, pos, 0), "E102"
        )
    if isinstance(e, UnexpectedCharacters):
        ch = source[e.pos_in_stream] if e.pos_in_stream is not None and e.pos_in_stream < len(source) else "?"
        span = _offset_to_span(source, e.pos_in_stream or 0)
        return SiplSyntaxError(f"unexpected character {ch!r}", span, "E103")
    return SiplSyntaxError(str(e), _offset_to_span(source, 0), "E100")


_STMT_START = {"VAR", "IF", "WHILE", "BEGIN", "SKIP"}


def _expected(e: UnexpectedInput) -> list[str]:
    names: set[str] = set(getattr(e, "expected", None) or [])
    ip = getattr(e, "interactive_parser", None)
    if ip is not None:
        try:
            names = set(ip.accepts())
        except Exception:  # noqa: BLE001
            pass
    return sorted({_token_label(x) for x in names})


def _join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return "one of " + ", ".join(items)


def _token_span(tok: Token) -> SourceSpan:
    return SourceSpan(
        tok.line or 0,
        tok.column or 0,
        tok.end_line or 0,
        tok.end_column or 0,
        tok.start_pos or 0,
        tok.end_pos or 0,
    )


def _meta_span(meta: Any) -> SourceSpan:
    if getattr(meta, "empty", True):
        return ast.UNKNOWN_SPAN
    return SourceSpan(meta.line, meta.column, meta.end_line, meta.end_column, meta.start_pos, meta.end_pos)


def _join_spans(a: SourceSpan, b: SourceSpan) -> SourceSpan:
    return SourceSpan(a.line, a.column, b.end_line, b.end_column, a.start, b.end)


@v_args(meta=True)
class _ToAst(Transformer):
    def start(self, meta, items):
        return items[0]

    def program(self, meta, items):
        return ast.Program(items[0], span=_meta_span(meta))

    def seq(self, meta, items):
        # S1; S2; S3 is folded to the left: (S1; S2); S3
        result = items[0]
        for stm in items[1:]:
            result = ast.Seq(result, stm, span=_join_spans(result.span, stm.span))
        return result

    def assign(self, meta, items):
        name, value = items
        return ast.Assign(str(name), value, span=_meta_span(meta), target_span=_token_span(name))

    def if_stmt(self, meta, items):
        cond, then_b, else_b = items
        return ast.If(cond, then_b, else_b, span=_meta_span(meta))

    def while_stmt(self, meta, items):
        cond, body = items
        return ast.While(cond, body, span=_meta_span(meta))

    def block(self, meta, items):
        return ast.Block(items[0], span=_meta_span(meta))

    def skip(self, meta, items):
        return ast.Skip(span=_meta_span(meta))

    def binop(self, meta, items):
        left, op, right = items
        return ast.BinOp(str(op), left, right, span=_meta_span(meta))

    def num(self, meta, items):
        text = "".join(str(t) for t in items)
        return ast.Num(int(text), span=_meta_span(meta))

    def var(self, meta, items):
        return ast.Var(str(items[0]), span=_meta_span(meta))

    def compare(self, meta, items):
        left, op, right = items
        return ast.Compare(str(op), left, right, span=_meta_span(meta))

    def or_(self, meta, items):
        left, _, right = items
        return ast.Or(left, right, span=_meta_span(meta))

    def not_(self, meta, items):
        _, operand = items
        return ast.Not(operand, span=_meta_span(meta))
