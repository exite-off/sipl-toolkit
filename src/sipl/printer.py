"""AST -> SIPL source text (one line or indented)."""

from __future__ import annotations

from . import ast

_PREC = {"+": 1, "-": 1, "*": 2, "div": 2, "mod": 2}


def aexp_to_str(a: ast.Aexp, parent_prec: int = 0, right: bool = False) -> str:
    if isinstance(a, ast.Num):
        return str(a.value)
    if isinstance(a, ast.Var):
        return a.name
    prec = _PREC[a.op]
    text = f"{aexp_to_str(a.left, prec)} {a.op} {aexp_to_str(a.right, prec, right=True)}"
    # left-assoc: the right operand of equal precedence needs parentheses
    if prec < parent_prec or (right and prec == parent_prec):
        return f"({text})"
    return text


def bexp_to_str(b: ast.Bexp, parent: int = 0, right: bool = False) -> str:
    if isinstance(b, ast.Compare):
        text = f"{aexp_to_str(b.left)} {b.op} {aexp_to_str(b.right)}"
        return f"({text})" if parent == 2 else text
    if isinstance(b, ast.Not):
        return f"not {bexp_to_str(b.operand, 2)}"
    text = f"{bexp_to_str(b.left, 1)} or {bexp_to_str(b.right, 1, right=True)}"
    return f"({text})" if parent == 2 or right else text


def stm_to_str(s: ast.Stm) -> str:
    if isinstance(s, ast.Assign):
        return f"{s.target} := {aexp_to_str(s.value)}"
    if isinstance(s, ast.Seq):
        return f"{stm_to_str(s.first)}; {stm_to_str(s.second)}"
    if isinstance(s, ast.If):
        return f"if {bexp_to_str(s.cond)} then {_inner(s.then_branch)} else {_inner(s.else_branch)}"
    if isinstance(s, ast.While):
        return f"while {bexp_to_str(s.cond)} do {_inner(s.body)}"
    if isinstance(s, ast.Block):
        return f"begin {stm_to_str(s.body)} end"
    return "skip"


def _inner(s: ast.Stm) -> str:
    # a Seq directly inside if/while is impossible in valid SIPL, wrap it to stay correct
    if isinstance(s, ast.Seq):
        return f"begin {stm_to_str(s)} end"
    return stm_to_str(s)


def program_to_str(p: ast.Program) -> str:
    return f"begin {stm_to_str(p.body)} end"


def to_source(node: ast.Node) -> str:
    if isinstance(node, ast.Program):
        return program_to_str(node)
    if isinstance(node, (ast.Num, ast.Var, ast.BinOp)):
        return aexp_to_str(node)
    if isinstance(node, (ast.Compare, ast.Or, ast.Not)):
        return bexp_to_str(node)
    return stm_to_str(node)  # type: ignore[arg-type]
