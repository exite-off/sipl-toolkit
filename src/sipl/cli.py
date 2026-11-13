"""Command line interface: sipl parse | check | run | trace | term."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, NoReturn, TextIO

from . import __version__, ast
from .diagnostics import SiplError, SiplSyntaxError
from .interpreter import DEFAULT_MAX_STEPS, Event, EventKind, ExecutionResult, format_state, run, trace
from .parser import parse
from .semantics import derive

SCHEMA_VERSION = 1

EXIT_OK = 0
EXIT_SYNTAX = 1
EXIT_RUNTIME = 2
EXIT_STEP_LIMIT = 3
EXIT_USAGE = 4


class UsageError(Exception):
    pass


class _ArgParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def _read_source(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        raise UsageError(f"cannot read {path}: {e.strerror}") from None


def parse_state(items: list[str]) -> dict[str, int]:
    """Parse ["X=5", "Y=2,Z=-1"] into a state."""
    state: dict[str, int] = {}
    for item in items:
        for part in item.split(","):
            part = part.strip()
            if not part:
                continue
            name, sep, value = part.partition("=")
            name = name.strip()
            if not sep or not name.isidentifier():
                raise UsageError(f"bad state item {part!r}, expected NAME=INT")
            try:
                state[name] = int(value)
            except ValueError:
                raise UsageError(f"bad value for {name}: {value.strip()!r} is not an integer") from None
    return state


def ast_to_text(node: ast.Node, indent: int = 0) -> str:
    label = type(node).__name__
    if isinstance(node, ast.Num):
        label += f" {node.value}"
    elif isinstance(node, ast.Var):
        label += f" {node.name}"
    elif isinstance(node, (ast.BinOp, ast.Compare)):
        label += f" {node.op}"
    elif isinstance(node, ast.Assign):
        label += f" {node.target}"
    pos = f"  @{node.span.line}:{node.span.column}-{node.span.end_line}:{node.span.end_column}"
    lines = ["  " * indent + label + pos]
    for child in node.children():
        lines.append(ast_to_text(child, indent + 1))
    return "\n".join(lines)


def format_event(e: Event) -> str:
    where = f"{e.span.line}:{e.span.column}" if e.span.line else "-"
    head = f"#{e.step:<4} {where:<7} {e.kind.value:<17}"
    if e.kind == EventKind.ASSIGN:
        old = "⊥" if e.data.get("old") is None else e.data["old"]
        return f"{head} {e.data['variable']}: {old} -> {e.data['new']}"
    if e.kind == EventKind.CONDITION:
        extra = f" (iteration {e.data['iteration']})" if "iteration" in e.data else ""
        return f"{head} {e.data['construct']} -> {str(e.data['value']).lower()}{extra}"
    if e.kind in (EventKind.FINISH, EventKind.START):
        return f"{head} {format_state(e.state)}"
    if e.kind == EventKind.ERROR:
        return f"{head} {e.data['error']['message']}"
    return f"{head} {e.node}"


class Cli:
    def __init__(self, out: TextIO, err: TextIO):
        self.out = out
        self.err = err

    def emit_json(self, payload: dict[str, Any]) -> None:
        payload = {"schema_version": SCHEMA_VERSION, **payload}
        json.dump(payload, self.out, ensure_ascii=False, indent=2)
        self.out.write("\n")

    def report_error(
        self, args: argparse.Namespace, error: SiplError, extra: dict[str, Any] | None = None
    ) -> None:
        if args.json:
            self.emit_json(
                {
                    "command": args.command,
                    "file": args.file,
                    "ok": False,
                    "diagnostics": [error.diagnostic.to_dict()],
                    **(extra or {}),
                }
            )
        else:
            self.err.write(error.diagnostic.format(args.file) + "\n")

    def load(self, args: argparse.Namespace) -> ast.Program | None:
        source = _read_source(args.file)
        try:
            return parse(source)
        except SiplSyntaxError as e:
            self.report_error(args, e)
            return None

    def cmd_parse(self, args: argparse.Namespace) -> int:
        program = self.load(args)
        if program is None:
            return EXIT_SYNTAX
        if args.json:
            self.emit_json(
                {
                    "command": "parse",
                    "file": args.file,
                    "ok": True,
                    "diagnostics": [],
                    "ast": program.to_dict(),
                }
            )
        else:
            self.out.write(ast_to_text(program) + "\n")
        return EXIT_OK

    def cmd_check(self, args: argparse.Namespace) -> int:
        program = self.load(args)
        if program is None:
            return EXIT_SYNTAX
        if args.json:
            self.emit_json(
                {
                    "command": "check",
                    "file": args.file,
                    "ok": True,
                    "diagnostics": [],
                    "variables": ast.variables(program),
                }
            )
        else:
            self.out.write(f"{args.file}: OK\n")
        return EXIT_OK

    def _execute(self, args: argparse.Namespace, with_trace: bool) -> int:
        state = parse_state(args.set or [])
        program = self.load(args)
        if program is None:
            return EXIT_SYNTAX
        result = trace(program, state, args.max_steps) if with_trace else run(program, state, args.max_steps)
        code = {"ok": EXIT_OK, "error": EXIT_RUNTIME, "step_limit": EXIT_STEP_LIMIT}[result.status]
        if args.json:
            payload = {
                "command": args.command,
                "file": args.file,
                "ok": result.ok,
                "diagnostics": [result.error.diagnostic.to_dict()] if result.error else [],
            }
            payload.update(result.to_dict(with_trace=with_trace))
            payload.pop("error", None)
            self.emit_json(payload)
            return code
        if with_trace:
            for e in result.events:
                self.out.write(format_event(e) + "\n")
        self._print_result(args, result)
        return code

    def _print_result(self, args: argparse.Namespace, result: ExecutionResult) -> None:
        if result.error is not None:
            self.err.write(result.error.diagnostic.format(args.file) + "\n")
            self.err.write(f"state at failure: {format_state(result.state)}\n")
            return
        self.out.write(f"{format_state(result.state)}\n")
        if args.verbose:
            self.out.write(f"steps: {result.steps}\n")

    def cmd_run(self, args: argparse.Namespace) -> int:
        return self._execute(args, with_trace=False)

    def cmd_trace(self, args: argparse.Namespace) -> int:
        return self._execute(args, with_trace=True)

    def cmd_term(self, args: argparse.Namespace) -> int:
        program = self.load(args)
        if program is None:
            return EXIT_SYNTAX
        d = derive(program)
        if args.json:
            self.emit_json(
                {"command": "term", "file": args.file, "ok": True, "diagnostics": [], **d.to_dict(args.ascii)}
            )
            return EXIT_OK
        if args.steps:
            for i, step in enumerate(d.steps, 1):
                self.out.write(f"{i:>3}. {step}\n")
            self.out.write("\n")
        self.out.write(d.term.render(args.ascii) + "\n")
        return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = _ArgParser(prog="sipl", description="SIPL Language Toolkit")
    p.add_argument("--version", action="version", version=f"sipl {__version__}")
    sub = p.add_subparsers(dest="command", required=True, parser_class=_ArgParser)

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_text, description=help_text)
        sp.add_argument("file", help="path to a .sipl file, '-' for stdin")
        sp.add_argument("--json", action="store_true", help="machine readable output")
        return sp

    add("parse", "parse a program and print its AST")
    add("check", "check syntax")
    for name, text in (("run", "run a program"), ("trace", "run a program and print the event trace")):
        sp = add(name, text)
        sp.add_argument(
            "-s",
            "--set",
            action="append",
            metavar="X=N",
            help="initial value of a variable, can be repeated or comma separated",
        )
        sp.add_argument(
            "--max-steps",
            type=int,
            default=DEFAULT_MAX_STEPS,
            help=f"step limit (default {DEFAULT_MAX_STEPS})",
        )
        sp.add_argument("-v", "--verbose", action="store_true", help="print number of steps")
    sp = add("term", "build the semantic term of a program")
    sp.add_argument("--steps", action="store_true", help="print applied rules")
    sp.add_argument("--ascii", action="store_true", help="ASCII notation (X=> instead of X⇒)")
    return p


def main(argv: list[str] | None = None, out: TextIO | None = None, err: TextIO | None = None) -> int:
    out = out or sys.stdout
    err = err or sys.stderr
    for stream in (out, err):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    cli = Cli(out, err)
    try:
        return int(getattr(cli, f"cmd_{args.command}")(args))
    except UsageError as e:
        err.write(f"sipl: error: {e}\n")
        return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
