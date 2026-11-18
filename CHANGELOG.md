# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/), versions: [SemVer](https://semver.org/).
One version number is used for the Python package `sipl-kit` and the VS Code extension `sipl-vscode`.

## [0.4.1] - 2026-11-18

### Fixed
- VS Code extension on Windows: when `python` is the Microsoft Store alias (exit code 9009) the extension
  now tries `py -3`, `python`, `python3` and `sipl` and remembers the one that works.
  If none works, the error explains how to set `sipl.pythonPath`.
- CI: extension tests run on Node 22 without a glob pattern.

### Added
- Screenshots of the VS Code extension in both READMEs (REL-04).

## [0.4.0] - 2026-11-18

### Added
- VS Code extension `sipl-vscode` (IDE-01, IDE-02): `.sipl` language registration, TextMate highlighting,
  comments, `begin`/`end` brackets, auto indent, snippets.
- Commands *SIPL: Run*, *Check*, *Trace*, *Show Semantic Term*; live diagnostics with exact line and column.
- Release workflow: GitHub Release with wheel, sdist and `.vsix`; publishing to PyPI.

## [0.3.0] - 2026-11-13

### Added
- `sipl` CLI (CORE-05): `parse`, `check`, `run`, `trace`, `term`; `--json` output with JSON Schema
  `docs/schema/cli-output.schema.json`; stable exit codes 0-4.
- Semantic terms in course notation with the list of applied rules (SEM-01).

## [0.2.0] - 2026-11-10

### Added
- Interpreter (CORE-03): states, `:=`, `;`, `if`, `while`, `begin/end`, `skip`; step limit for infinite loops;
  runtime errors with source position.
- Event model (CORE-04): `start`, `before_statement`, `after_statement`, `assign`, `condition`, `finish`, `error`.

## [0.1.0] - 2026-11-09

### Added
- Lark grammar of SIPL following the course BNF, with 14 valid and 15 invalid test programs (CORE-01).
- Parser with typed AST and `SourceSpan` for every node, syntax diagnostics with expected tokens (CORE-02).
- CI on GitHub Actions: ruff, mypy, pytest with 80% coverage gate on Linux and Windows (REL-01).
