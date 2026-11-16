# SIPL Language Toolkit

[![CI](https://github.com/exite-off/sipl-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/exite-off/sipl-toolkit/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/sipl-kit)](https://pypi.org/project/sipl-kit/)

Інструменти для мови SIPL (SImple Programming Language) з курсу «Теорія програмування»:
граматика, парсер у типізоване AST, інтерпретатор із trace, семантичні терми в нотації курсу,
CLI з JSON-режимом і розширення для VS Code.

Курсовий проєкт. Виконавець: **Vitalii Fedin**, група **ТК-32**.

## Обрані завдання

| ID | Завдання | Бали | Де реалізовано |
|---|---|---|---|
| CORE-01 | Формальна специфікація SIPL | 0.5 | `src/sipl/grammar/sipl.lark`, `docs/language.md`, `tests/grammar/` |
| CORE-02 | Парсер і типізоване AST з SourceSpan | 1.5 | `src/sipl/parser.py`, `src/sipl/ast.py` |
| CORE-03 | Інтерпретатор | 2.0 | `src/sipl/interpreter/runtime.py` |
| CORE-04 | Подієва модель виконання та trace | 1.0 | `src/sipl/interpreter/events.py`, `sipl trace` |
| CORE-05 | CLI parse/check/run/trace, JSON | 1.0 | `src/sipl/cli.py`, `docs/cli.md`, `docs/schema/` |
| IDE-01 | VS Code: мова, підсвітка, сніпети, .vsix | 1.0 | `vscode-sipl/` |
| IDE-02 | VS Code: Run/Check, diagnostics | 1.0 | `vscode-sipl/src/extension.js` |
| REL-01 | CI | 0.5 | `.github/workflows/ci.yml` |
| REL-02 | GitHub Releases + SemVer + CHANGELOG | 0.5 | `.github/workflows/release.yml`, `CHANGELOG.md` |
| REL-03 | Публікація в PyPI | 0.5 | пакет `sipl-kit` |
| REL-04 | Публікація VS Code extension (.vsix) | 0.5 | `.vsix` у GitHub Release |
| | **Разом** | **10.0** | |
| SEM-01 | Семантичний терм (додатково, запас) | 2.0 | `src/sipl/semantics/terms.py`, `sipl term` |

Заявлено 12.0 бали, оцінка обмежується 10.

## Встановлення

Потрібен Python 3.10+.

```bash
pip install sipl-kit
```

Для розробки (з тестами й лінтерами):

```bash
git clone https://github.com/exite-off/sipl-toolkit.git
cd sipl-toolkit
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Якщо в PowerShell активація блокується політикою виконання:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Використання

```text
$ sipl run examples/power.sipl -s X=5,Y=2
[X ↦ 5, Y ↦ 0, R ↦ 25]

$ sipl check examples/errors/missing_else.sipl
examples/errors/missing_else.sipl:3:1: error: unexpected 'end', expected 'else' (in SIPL every 'if' needs an 'else' branch) [E101]

$ sipl run examples/errors/infinite_loop.sipl --max-steps 50
examples/errors/infinite_loop.sipl:5:9: error: step limit of 50 exceeded (possible infinite loop) [E300]
state at failure: [X ↦ 24]

$ sipl trace examples/power.sipl -s X=5,Y=2
#0    2:1     start             [X ↦ 5, Y ↦ 2]
#1    3:5     before_statement  Assign
#1    3:5     assign            R: ⊥ -> 1
#1    3:5     after_statement   Assign
#2    4:5     before_statement  While
#2    4:11    condition         while -> true (iteration 0)
...
#8    4:11    condition         while -> false (iteration 2)
#8    4:5     after_statement   While
#8    2:1     finish            [X ↦ 5, Y ↦ 0, R ↦ 25]
[X ↦ 5, Y ↦ 0, R ↦ 25]

$ sipl term examples/power.sipl
AS^R(1) · WH(S^2(gr, Y⇒, 0), AS^R(S^2(mult, R⇒, X⇒)) · AS^Y(S^2(sub, Y⇒, 1)))
```

`sipl term --steps` виводить усі застосовані правила (`NS_Prog`, `NS_Stm_Seq`, `NS_Stm_As`, ...)
так само, як у практичній роботі 2. Кожна команда має `--json` для інтеграцій.
Повний опис команд, кодів завершення та JSON-формату: [docs/cli.md](docs/cli.md).

Як бібліотека:

```python
from sipl import parse
from sipl.interpreter import run, trace
from sipl.semantics import derive

program = parse(open("examples/power.sipl", encoding="utf-8").read())
print(run(program, {"X": 5, "Y": 2}).state)    # {'X': 5, 'Y': 0, 'R': 25}
print(derive(program).term)                     # AS^R(1) · WH(...)
```

## VS Code

1. Встановіть пакет: `pip install sipl-kit`.
2. Завантажте `sipl-vscode-<версія>.vsix` з [Releases](https://github.com/exite-off/sipl-toolkit/releases)
   і встановіть: `code --install-extension sipl-vscode-0.4.0.vsix`.
3. Відкрийте `.sipl`-файл. Помилки підсвічуються одразу під час набору.
   Кнопки ▶ (Run) і ✓ (Check) у заголовку редактора, Ctrl+F5 запускає програму.
   Команди *SIPL: Trace* і *SIPL: Show Semantic Term* доступні з Command Palette.

Якщо Python не в PATH, вкажіть інтерпретатор у налаштуванні `sipl.pythonPath`.
Сумісність: VS Code 1.85+, Windows / Linux / macOS.

<!-- screenshots: docs/images/highlight.png, docs/images/run.png -->

## Приклади

`examples/` містить програми для варіантів практичних робіт: степінь (приклад з посібника),
(2n)!!, числа Фібоначчі, парність, подільність, ⌊√n⌋, простота числа, НСД.
`examples/errors/` містить програми з типовими помилками.

## Структура

```
grammar/              опис граматики і відповідність БНФ курсу
src/sipl/
  grammar/sipl.lark   машинозчитувана граматика (Lark, LALR(1))
  ast.py              типізовані вузли AST, SourceSpan
  parser.py           текст -> AST, синтаксична діагностика
  printer.py          AST -> текст
  diagnostics.py      коди помилок
  interpreter/        виконання, стани, події trace
  semantics/          семантичні терми, правила NS_*
  cli.py              команди parse/check/run/trace/term
examples/             приклади SIPL
tests/                pytest, покриття ядра понад 95%
docs/                 мова, CLI, JSON Schema, архітектура
vscode-sipl/          VS Code extension, клієнт CLI
```

Як дані проходять через шари: [docs/architecture.md](docs/architecture.md).

## Тести

```bash
pytest                           # Python: граматика, парсер, інтерпретатор, trace, CLI, терми
cd vscode-sipl && npm ci && npm test   # extension: підсвітка на TextMate-рушії VS Code, інтеграція з CLI
```

CI запускає ruff, mypy і pytest на Linux і Windows (Python 3.10, 3.12, 3.13), збирає wheel
і `.vsix`. Тег `vX.Y.Z` створює GitHub Release і публікує пакет у PyPI.

## Обмеження

- `while` без завершення виявляється лише через ліміт кроків (`--max-steps`, типово 100000).
  Це обмеження інструменту, а не доведення незавершуваності.
- Читання змінної, якої немає в стані, є помилкою: у курсі `x⇒` на такому стані не визначена.
- `div`, `mod` і коментарі є розширенням SIPL+, у БНФ курсу їх немає ([docs/language.md](docs/language.md)).
- Розширення VS Code не містить власного парсера: без встановленого `sipl-kit` воно не працює.

## Ліцензія

MIT
