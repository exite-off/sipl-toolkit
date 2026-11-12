"""Semantic terms of the SIPL program algebra (practical work 2).

sem_P: Prog -> TFS, sem_S: Stm -> TFS, sem_A: Aexp -> TFA, sem_B: Bexp -> TFB.
The term is built recursively over the AST, every applied rule is recorded,
so the derivation can be shown in the same form as in the textbook.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import ast
from ..printer import to_source

ARITH_NAMES = {"+": "add", "-": "sub", "*": "mult", "div": "div", "mod": "mod"}
COMPARE_NAMES = {"=": "eq", ">": "gr"}


class Term:
    def render(self, ascii_only: bool = False, top: bool = True) -> str:
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    def __str__(self) -> str:
        return self.render()


@dataclass(frozen=True)
class Const(Term):
    # constant function n(st) = n
    value: int

    def render(self, ascii_only: bool = False, top: bool = True) -> str:
        return str(self.value)

    def to_dict(self) -> dict[str, Any]:
        return {"term": "const", "value": self.value}


@dataclass(frozen=True)
class Denom(Term):
    # naming (denomination) function x=>(st) = st(x)
    name: str

    def render(self, ascii_only: bool = False, top: bool = True) -> str:
        return f"{self.name}=>" if ascii_only else f"{self.name}⇒"

    def to_dict(self) -> dict[str, Any]:
        return {"term": "denom", "name": self.name}


@dataclass(frozen=True)
class Superpos(Term):
    # S^n(f, g1, ..., gn)
    func: str
    args: tuple[Term, ...]

    def render(self, ascii_only: bool = False, top: bool = True) -> str:
        inner = ", ".join([self.func] + [a.render(ascii_only, True) for a in self.args])
        return f"S^{len(self.args)}({inner})"

    def to_dict(self) -> dict[str, Any]:
        return {"term": "superposition", "func": self.func, "args": [a.to_dict() for a in self.args]}


@dataclass(frozen=True)
class AssignT(Term):
    # AS^x(fa)
    var: str
    value: Term

    def render(self, ascii_only: bool = False, top: bool = True) -> str:
        return f"AS^{self.var}({self.value.render(ascii_only, True)})"

    def to_dict(self) -> dict[str, Any]:
        return {"term": "assign", "var": self.var, "value": self.value.to_dict()}


@dataclass(frozen=True)
class SeqT(Term):
    # fs1 · fs2 (first fs1, then fs2)
    first: Term
    second: Term

    def render(self, ascii_only: bool = False, top: bool = True) -> str:
        dot = " . " if ascii_only else " · "
        return self.first.render(ascii_only, False) + dot + self.second.render(ascii_only, False)

    def to_dict(self) -> dict[str, Any]:
        return {"term": "seq", "first": self.first.to_dict(), "second": self.second.to_dict()}


@dataclass(frozen=True)
class IfT(Term):
    cond: Term
    then_branch: Term
    else_branch: Term

    def render(self, ascii_only: bool = False, top: bool = True) -> str:
        parts = [t.render(ascii_only, True) for t in (self.cond, self.then_branch, self.else_branch)]
        return f"IF({', '.join(parts)})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": "if",
            "cond": self.cond.to_dict(),
            "then": self.then_branch.to_dict(),
            "else": self.else_branch.to_dict(),
        }


@dataclass(frozen=True)
class WhT(Term):
    cond: Term
    body: Term

    def render(self, ascii_only: bool = False, top: bool = True) -> str:
        return f"WH({self.cond.render(ascii_only, True)}, {self.body.render(ascii_only, True)})"

    def to_dict(self) -> dict[str, Any]:
        return {"term": "while", "cond": self.cond.to_dict(), "body": self.body.to_dict()}


@dataclass(frozen=True)
class IdT(Term):
    def render(self, ascii_only: bool = False, top: bool = True) -> str:
        return "id"

    def to_dict(self) -> dict[str, Any]:
        return {"term": "id"}


@dataclass(frozen=True)
class Group(Term):
    # (fs) from rule NS_Stm_BE; brackets are dropped where they change nothing
    body: Term

    def render(self, ascii_only: bool = False, top: bool = True) -> str:
        inner = self.body.render(ascii_only, top)
        if top or not isinstance(self.body, SeqT):
            return inner
        return f"({inner})"

    def to_dict(self) -> dict[str, Any]:
        return {"term": "group", "body": self.body.to_dict()}


@dataclass(frozen=True)
class RuleStep:
    rule: str
    lhs: str
    rhs: str

    def to_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "lhs": self.lhs, "rhs": self.rhs}

    def __str__(self) -> str:
        return f"{self.rule}: {self.lhs} = {self.rhs}"


@dataclass
class Derivation:
    term: Term
    steps: list[RuleStep] = field(default_factory=list)

    def to_dict(self, ascii_only: bool = False) -> dict[str, Any]:
        return {
            "term": self.term.render(ascii_only),
            "tree": self.term.to_dict(),
            "rules": [s.to_dict() for s in self.steps],
        }


class _Builder:
    def __init__(self) -> None:
        self.steps: list[RuleStep] = []

    def _record(self, rule: str, func: str, node: ast.Node, rhs: str) -> None:
        self.steps.append(RuleStep(rule, f"{func}({to_source(node)})", rhs))

    def prog(self, p: ast.Program) -> Term:
        self._record("NS_Prog", "sem_P", p, f"sem_S({to_source(p.body)})")
        return self.stm(p.body)

    def stm(self, s: ast.Stm) -> Term:
        if isinstance(s, ast.Assign):
            self._record("NS_Stm_As", "sem_S", s, f"AS^{s.target}(sem_A({to_source(s.value)}))")
            return AssignT(s.target, self.aexp(s.value))
        if isinstance(s, ast.Seq):
            self._record(
                "NS_Stm_Seq", "sem_S", s, f"sem_S({to_source(s.first)}) · sem_S({to_source(s.second)})"
            )
            return SeqT(self.stm(s.first), self.stm(s.second))
        if isinstance(s, ast.If):
            self._record(
                "NS_Stm_If",
                "sem_S",
                s,
                f"IF(sem_B({to_source(s.cond)}), sem_S({to_source(s.then_branch)}), "
                f"sem_S({to_source(s.else_branch)}))",
            )
            return IfT(self.bexp(s.cond), self.stm(s.then_branch), self.stm(s.else_branch))
        if isinstance(s, ast.While):
            self._record(
                "NS_Stm_Wh", "sem_S", s, f"WH(sem_B({to_source(s.cond)}), sem_S({to_source(s.body)}))"
            )
            return WhT(self.bexp(s.cond), self.stm(s.body))
        if isinstance(s, ast.Block):
            self._record("NS_Stm_BE", "sem_S", s, f"(sem_S({to_source(s.body)}))")
            return Group(self.stm(s.body))
        self._record("NS_Stm_skip", "sem_S", s, "id")
        return IdT()

    def aexp(self, a: ast.Aexp) -> Term:
        if isinstance(a, ast.Num):
            self._record("NS_A_Num", "sem_A", a, str(a.value))
            return Const(a.value)
        if isinstance(a, ast.Var):
            self._record("NS_A_Var", "sem_A", a, f"{a.name}⇒")
            return Denom(a.name)
        name = ARITH_NAMES[a.op]
        rule = {"add": "NS_A_Add", "sub": "NS_A_Sub", "mult": "NS_A_Mult"}.get(name, f"NS_A_{name.title()}")
        self._record(
            rule, "sem_A", a, f"S^2({name}, sem_A({to_source(a.left)}), sem_A({to_source(a.right)}))"
        )
        return Superpos(name, (self.aexp(a.left), self.aexp(a.right)))

    def bexp(self, b: ast.Bexp) -> Term:
        if isinstance(b, ast.Compare):
            name = COMPARE_NAMES[b.op]
            self._record(
                f"NS_B_{name}",
                "sem_B",
                b,
                f"S^2({name}, sem_A({to_source(b.left)}), sem_A({to_source(b.right)}))",
            )
            return Superpos(name, (self.aexp(b.left), self.aexp(b.right)))
        if isinstance(b, ast.Or):
            self._record(
                "NS_B_or", "sem_B", b, f"S^2(or, sem_B({to_source(b.left)}), sem_B({to_source(b.right)}))"
            )
            return Superpos("or", (self.bexp(b.left), self.bexp(b.right)))
        self._record("NS_B_neg", "sem_B", b, f"S^1(neg, sem_B({to_source(b.operand)}))")
        return Superpos("neg", (self.bexp(b.operand),))


def derive(program: ast.Program) -> Derivation:
    """Build the semantic term of a program with the list of applied rules."""
    b = _Builder()
    term = b.prog(program)
    return Derivation(term, b.steps)


def sem_p(program: ast.Program) -> Term:
    return derive(program).term
