# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/), versions: [SemVer](https://semver.org/).
One version number is used for the Python package `sipl-kit` and the VS Code extension `sipl-vscode`.

## [0.1.0] - 2026-11-18

### Added
- Lark grammar of SIPL following the course BNF, with 14 valid and 15 invalid test programs (CORE-01).
- Parser with typed AST and `SourceSpan` for every node, syntax diagnostics with expected tokens (CORE-02).
- CI on GitHub Actions: ruff, mypy, pytest with 80% coverage gate on Linux and Windows (REL-01).
