"""Typed AST of SIPL. Every node keeps its SourceSpan."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceSpan:
    # lines and columns are 1-based, end_column points past the last char
    line: int
    column: int
    end_line: int
    end_column: int
    start: int
    end: int

    def to_dict(self) -> dict[str, int]:
        return {
            "line": self.line,
            "column": self.column,
            "end_line": self.end_line,
            "end_column": self.end_column,
            "start": self.start,
            "end": self.end,
        }

    def contains_line(self, line: int) -> bool:
        return self.line <= line <= self.end_line


UNKNOWN_SPAN = SourceSpan(0, 0, 0, 0, 0, 0)


@dataclass(frozen=True)
class Node:
    span: SourceSpan = field(compare=False, repr=False, kw_only=True)

    def children(self) -> Iterator[Node]:
        return iter(())

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    def walk(self) -> Iterator[Node]:
        yield self
        for child in self.children():
            yield from child.walk()


# arithmetic expressions (Aexp)


@dataclass(frozen=True)
class Num(Node):
    value: int

    def to_dict(self) -> dict[str, Any]:
        return {"type": "Num", "value": self.value, "span": self.span.to_dict()}


@dataclass(frozen=True)
class Var(Node):
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": "Var", "name": self.name, "span": self.span.to_dict()}


ARITH_OPS = ("+", "-", "*", "div", "mod")


@dataclass(frozen=True)
class BinOp(Node):
    op: str
    left: Aexp
    right: Aexp

    def children(self) -> Iterator[Node]:
        yield self.left
        yield self.right

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "BinOp",
            "op": self.op,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "span": self.span.to_dict(),
        }


Aexp = Num | Var | BinOp


# conditions (Bexp)


@dataclass(frozen=True)
class Compare(Node):
    op: str  # "=" or ">"
    left: Aexp
    right: Aexp

    def children(self) -> Iterator[Node]:
        yield self.left
        yield self.right

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "Compare",
            "op": self.op,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class Or(Node):
    left: Bexp
    right: Bexp

    def children(self) -> Iterator[Node]:
        yield self.left
        yield self.right

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "Or",
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class Not(Node):
    operand: Bexp

    def children(self) -> Iterator[Node]:
        yield self.operand

    def to_dict(self) -> dict[str, Any]:
        return {"type": "Not", "operand": self.operand.to_dict(), "span": self.span.to_dict()}


Bexp = Compare | Or | Not


# statements (Stm)


@dataclass(frozen=True)
class Assign(Node):
    target: str
    value: Aexp
    target_span: SourceSpan = field(compare=False, repr=False, kw_only=True)

    def children(self) -> Iterator[Node]:
        yield self.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "Assign",
            "target": self.target,
            "value": self.value.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class Seq(Node):
    first: Stm
    second: Stm

    def children(self) -> Iterator[Node]:
        yield self.first
        yield self.second

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "Seq",
            "first": self.first.to_dict(),
            "second": self.second.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class If(Node):
    cond: Bexp
    then_branch: Stm
    else_branch: Stm

    def children(self) -> Iterator[Node]:
        yield self.cond
        yield self.then_branch
        yield self.else_branch

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "If",
            "cond": self.cond.to_dict(),
            "then": self.then_branch.to_dict(),
            "else": self.else_branch.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class While(Node):
    cond: Bexp
    body: Stm

    def children(self) -> Iterator[Node]:
        yield self.cond
        yield self.body

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "While",
            "cond": self.cond.to_dict(),
            "body": self.body.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class Block(Node):
    body: Stm

    def children(self) -> Iterator[Node]:
        yield self.body

    def to_dict(self) -> dict[str, Any]:
        return {"type": "Block", "body": self.body.to_dict(), "span": self.span.to_dict()}


@dataclass(frozen=True)
class Skip(Node):
    def to_dict(self) -> dict[str, Any]:
        return {"type": "Skip", "span": self.span.to_dict()}


Stm = Assign | Seq | If | While | Block | Skip


@dataclass(frozen=True)
class Program(Node):
    body: Stm

    def children(self) -> Iterator[Node]:
        yield self.body

    def to_dict(self) -> dict[str, Any]:
        return {"type": "Program", "body": self.body.to_dict(), "span": self.span.to_dict()}


def variables(node: Node) -> list[str]:
    """Variables in order of first occurrence."""
    seen: dict[str, None] = {}
    for n in node.walk():
        if isinstance(n, Assign):
            seen.setdefault(n.target)
        elif isinstance(n, Var):
            seen.setdefault(n.name)
    return list(seen)
