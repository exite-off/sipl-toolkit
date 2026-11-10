"""Execution events (trace model) used by CLI, debugger and visualizers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..ast import UNKNOWN_SPAN, SourceSpan


class EventKind(str, Enum):
    START = "start"
    BEFORE_STATEMENT = "before_statement"
    AFTER_STATEMENT = "after_statement"
    ASSIGN = "assign"
    CONDITION = "condition"
    FINISH = "finish"
    ERROR = "error"


@dataclass(frozen=True)
class Event:
    kind: EventKind
    step: int
    span: SourceSpan = UNKNOWN_SPAN
    node: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    state: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"kind": self.kind.value, "step": self.step}
        if self.node is not None:
            d["node"] = self.node
        if self.span != UNKNOWN_SPAN:
            d["span"] = self.span.to_dict()
        d.update(self.data)
        d["state"] = dict(self.state)
        return d


Listener = Callable[[Event], None]
