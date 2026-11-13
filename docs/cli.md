# Command line interface

```
sipl parse FILE [--json]                      AST of the program
sipl check FILE [--json]                      syntax check
sipl run   FILE [-s X=5 -s Y=2 | -s X=5,Y=2] [--max-steps N] [-v] [--json]
sipl trace FILE [-s ...] [--max-steps N] [--json]   execution with all events
sipl term  FILE [--steps] [--ascii] [--json]  semantic term (course notation)
sipl --version
```

`FILE` can be `-` to read the program from standard input (the VS Code extension uses this,
so unsaved buffers can be checked). `python -m sipl ...` works the same way as `sipl ...`.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | syntax error |
| 2 | runtime error (undefined variable, division by zero) |
| 3 | step limit exceeded |
| 4 | usage error (bad arguments, file cannot be read, bad `-s` value) |

## Text output

```
$ sipl run examples/power.sipl -s X=5,Y=2
[X ↦ 5, Y ↦ 0, R ↦ 25]

$ sipl check examples/errors/missing_else.sipl
examples/errors/missing_else.sipl:3:1: error: unexpected 'end', expected 'else' (in SIPL every 'if' needs an 'else' branch) [E101]
```

Errors go to stderr in the format `file:line:column: error: message [code]`, which most editors understand.

## JSON output

With `--json` every command prints one JSON object to stdout, even on errors.
The format is described by the JSON Schema [`docs/schema/cli-output.schema.json`](schema/cli-output.schema.json)
(`schema_version: 1`) and tests check every command against it.

Common fields: `schema_version`, `command`, `file`, `ok`, `diagnostics`.

```json
{
  "schema_version": 1,
  "command": "run",
  "file": "examples/power.sipl",
  "ok": true,
  "diagnostics": [],
  "status": "ok",
  "initial_state": {"X": 5, "Y": 2},
  "state": {"X": 5, "Y": 0, "R": 25},
  "steps": 8
}
```

A diagnostic:

```json
{"severity": "error", "code": "E101", "message": "unexpected 'end', expected 'else' ...",
 "span": {"line": 3, "column": 1, "end_line": 3, "end_column": 4, "start": 35, "end": 38}}
```

Lines and columns are 1-based, `end_column` points right after the last character,
`start`/`end` are character offsets in the source.

Trace event (`sipl trace --json`, field `trace`):

```json
{"kind": "assign", "step": 3, "node": "Assign", "span": {...}, "variable": "R", "old": 1, "new": 5,
 "state": {"X": 5, "Y": 2, "R": 5}}
```

Event kinds: `start`, `before_statement`, `after_statement`, `assign` (`variable`, `old`, `new`),
`condition` (`construct`: `if`/`while`, `value`, `iteration` for loops), `finish`, `error` (`error`).
`state` is the state right after the event. `step` counts executed statements (assignments, `skip`,
`if`, `while` and every loop iteration); `begin ... end` and `;` do not count.

Error codes:

| Code | Meaning |
|---|---|
| E101 | unexpected token |
| E102 | unexpected end of input |
| E103 | unexpected character |
| E201 | variable has no value in the current state |
| E202 | division by zero |
| E300 | step limit exceeded |
