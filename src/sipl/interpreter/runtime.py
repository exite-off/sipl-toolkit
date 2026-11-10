"""Big-step interpreter of SIPL with an event stream.

A state is a finite mapping Var -> int, like st = [X -> 5, Y -> 2] in the course.
Reading a variable that is not in the state is an error: the semantic function
x=> is undefined on such a state, so the whole program is undefined too.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import ast
from ..diagnostics import (
    DivisionByZeroError,
    SiplRuntimeError,
    StepLimitExceeded,
    UndefinedVariableError,
)
from .events import Event, EventKind, Listener

DEFAULT_MAX_STEPS = 100_000

State = dict[str, int]


def format_state(state: State) -> str:
    return "[" + ", ".join(f"{k} ↦ {v}" for k, v in state.items()) + "]"


def eval_aexp(a: ast.Aexp, state: State) -> int:
    if isinstance(a, ast.Num):
        return a.value
    if isinstance(a, ast.Var):
        if a.name not in state:
            raise UndefinedVariableError(f"variable {a.name} is undefined in the current state", a.span)
        return state[a.name]
    if isinstance(a, ast.BinOp):
        left = eval_aexp(a.left, state)
        right = eval_aexp(a.right, state)
        if a.op == "+":
            return left + right
        if a.op == "-":
            return left - right
        if a.op == "*":
            return left * right
        if right == 0:
            raise DivisionByZeroError(f"division by zero in '{a.op}'", a.span)
        if a.op == "div":
            return left // right
        if a.op == "mod":
            return left % right
    raise SiplRuntimeError(f"unknown arithmetic expression {a!r}")


def eval_bexp(b: ast.Bexp, state: State) -> bool:
    if isinstance(b, ast.Compare):
        left = eval_aexp(b.left, state)
        right = eval_aexp(b.right, state)
        return left == right if b.op == "=" else left > right
    if isinstance(b, ast.Or):
        # both operands are evaluated, as in S^2(or, fb1, fb2)
        left = eval_bexp(b.left, state)
        right = eval_bexp(b.right, state)
        return left or right
    if isinstance(b, ast.Not):
        return not eval_bexp(b.operand, state)
    raise SiplRuntimeError(f"unknown condition {b!r}")


@dataclass
class ExecutionResult:
    status: str  # "ok" | "error" | "step_limit"
    state: State
    steps: int
    initial_state: State
    error: SiplRuntimeError | None = None
    events: list[Event] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self, with_trace: bool = False) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "initial_state": dict(self.initial_state),
            "state": dict(self.state),
            "steps": self.steps,
        }
        if self.error is not None:
            d["error"] = self.error.diagnostic.to_dict()
        if with_trace:
            d["trace"] = [e.to_dict() for e in self.events]
        return d


class Interpreter:
    def __init__(
        self,
        program: ast.Program,
        state: State | None = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        listeners: list[Listener] | None = None,
    ):
        self.program = program
        self.initial_state: State = dict(state or {})
        self.state: State = dict(self.initial_state)
        self.max_steps = max_steps
        self.steps = 0
        self.listeners: list[Listener] = list(listeners or [])

    def emit(self, kind: EventKind, node: ast.Node | None = None, **data: Any) -> None:
        if not self.listeners:
            return
        event = Event(
            kind=kind,
            step=self.steps,
            span=node.span if node is not None else ast.UNKNOWN_SPAN,
            node=type(node).__name__ if node is not None else None,
            data=data,
            state=dict(self.state),
        )
        for listener in self.listeners:
            listener(event)

    def run(self) -> ExecutionResult:
        self.emit(EventKind.START, self.program)
        status = "ok"
        error: SiplRuntimeError | None = None
        try:
            self.exec_stm(self.program.body)
        except StepLimitExceeded as e:
            status, error = "step_limit", e
        except SiplRuntimeError as e:
            status, error = "error", e
        if error is not None:
            self.emit(EventKind.ERROR, None, error=error.diagnostic.to_dict())
        else:
            self.emit(EventKind.FINISH, self.program)
        return ExecutionResult(status, dict(self.state), self.steps, dict(self.initial_state), error)

    def _tick(self, node: ast.Node) -> None:
        self.steps += 1
        if self.steps > self.max_steps:
            raise StepLimitExceeded(
                f"step limit of {self.max_steps} exceeded (possible infinite loop)", node.span
            )

    def exec_stm(self, s: ast.Stm) -> None:
        # Seq and Block are structural, they do not count as steps
        if isinstance(s, ast.Seq):
            self.exec_stm(s.first)
            self.exec_stm(s.second)
            return
        if isinstance(s, ast.Block):
            self.exec_stm(s.body)
            return

        self._tick(s)
        self.emit(EventKind.BEFORE_STATEMENT, s)
        if isinstance(s, ast.Assign):
            value = eval_aexp(s.value, self.state)
            old = self.state.get(s.target)
            self.state[s.target] = value
            self.emit(EventKind.ASSIGN, s, variable=s.target, old=old, new=value)
        elif isinstance(s, ast.Skip):
            pass
        elif isinstance(s, ast.If):
            cond = eval_bexp(s.cond, self.state)
            self.emit(EventKind.CONDITION, s.cond, construct="if", value=cond)
            self.exec_stm(s.then_branch if cond else s.else_branch)
        elif isinstance(s, ast.While):
            iteration = 0
            while True:
                cond = eval_bexp(s.cond, self.state)
                self.emit(EventKind.CONDITION, s.cond, construct="while", value=cond, iteration=iteration)
                if not cond:
                    break
                self.exec_stm(s.body)
                iteration += 1
                self._tick(s)
        else:
            raise SiplRuntimeError(f"unknown statement {s!r}", s.span)
        self.emit(EventKind.AFTER_STATEMENT, s)


def run(
    program: ast.Program, state: State | None = None, max_steps: int = DEFAULT_MAX_STEPS
) -> ExecutionResult:
    return Interpreter(program, state, max_steps).run()


def trace(
    program: ast.Program, state: State | None = None, max_steps: int = DEFAULT_MAX_STEPS
) -> ExecutionResult:
    events: list[Event] = []
    interp = Interpreter(program, state, max_steps, listeners=[events.append])
    result = interp.run()
    result.events = events
    return result
