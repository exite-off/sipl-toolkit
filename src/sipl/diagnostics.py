"""Diagnostics and error types shared by parser, interpreter and CLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ast import UNKNOWN_SPAN, SourceSpan


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    span: SourceSpan = UNKNOWN_SPAN
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "span": self.span.to_dict(),
        }

    def format(self, filename: str = "<input>") -> str:
        return (
            f"{filename}:{self.span.line}:{self.span.column}: {self.severity}: {self.message} [{self.code}]"
        )


class SiplError(Exception):
    code = "E000"

    def __init__(self, message: str, span: SourceSpan = UNKNOWN_SPAN, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.span = span
        if code is not None:
            self.code = code

    @property
    def diagnostic(self) -> Diagnostic:
        return Diagnostic(self.code, self.message, self.span)


class SiplSyntaxError(SiplError):
    code = "E100"


class SiplRuntimeError(SiplError):
    code = "E200"


class UndefinedVariableError(SiplRuntimeError):
    code = "E201"


class DivisionByZeroError(SiplRuntimeError):
    code = "E202"


class StepLimitExceeded(SiplRuntimeError):
    code = "E300"
