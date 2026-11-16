# Architecture

```
 source text ──► parser.py ──► ast.Program ──┬──► interpreter/ ──► ExecutionResult + Event stream
   (.sipl)       (Lark LALR,    (typed nodes │      runtime.py          (state, steps, trace)
                  grammar/       with        │      events.py
                  sipl.lark)     SourceSpan) ├──► semantics/terms.py ──► Term + list of applied rules
                                             └──► printer.py ──► source text (round trip)

 cli.py: parse | check | run | trace | term   (text or --json, stable exit codes)
          ▲
          │  spawn "python -m sipl <cmd> - --json", source on stdin
 vscode-sipl/src/extension.js: diagnostics, Run/Check/Trace/Term commands, output panel
```

- `parser.py` turns the Lark parse tree into own dataclasses from `ast.py`; library trees never leave the module.
  Syntax errors become `SiplSyntaxError` with a `SourceSpan` and a list of tokens that were expected.
- `ast.py` nodes are immutable and comparable by value (spans are ignored by `==`), so tests can compare trees
  and the printer round trip can be checked by `parse(print(p)) == p`.
- `interpreter/runtime.py` is a direct big-step interpreter. Every statement is reported to listeners
  (`Event`), so the same run can feed a trace printer, a debugger or a visualizer without changes in the interpreter.
- `semantics/terms.py` implements `sem_P/sem_S/sem_A/sem_B` recursively over the AST and records each rule.
- The VS Code extension has no parser or interpreter of its own. It is a client of the CLI and uses only
  the JSON contract from `docs/schema/cli-output.schema.json`.
