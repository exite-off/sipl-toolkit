import pytest

from sipl import parse
from sipl.diagnostics import DivisionByZeroError, StepLimitExceeded, UndefinedVariableError
from sipl.interpreter import eval_aexp, eval_bexp, format_state, run, trace


def run_src(src, **state):
    return run(parse(src), state)


def test_power_from_textbook(examples_dir):
    p = parse((examples_dir / "power.sipl").read_text(encoding="utf-8"))
    r = run(p, {"X": 5, "Y": 2})
    assert r.ok
    assert r.state == {"X": 5, "Y": 0, "R": 25}


@pytest.mark.parametrize("x, y", [(2, 1), (2, 10), (3, 4), (7, 3)])
def test_power_many_inputs(examples_dir, x, y):
    p = parse((examples_dir / "power.sipl").read_text(encoding="utf-8"))
    assert run(p, {"X": x, "Y": y}).state["R"] == x**y


@pytest.mark.parametrize(
    "name, state, var, expected",
    [
        ("double_factorial_even", {"N": 3}, "R", 48),
        ("fibonacci", {"N": 1}, "F", 1),
        ("fibonacci", {"N": 10}, "F", 55),
        ("parity", {"N": 5}, "E", 0),
        ("parity", {"N": 8}, "E", 1),
        ("divides", {"X": 9, "Y": 5}, "D", 0),
        ("divides", {"X": 9, "Y": 3}, "D", 1),
        ("isqrt", {"N": 7}, "R", 2),
        ("isqrt", {"N": 16}, "R", 4),
        ("prime", {"N": 3}, "P", 1),
        ("prime", {"N": 91}, "P", 0),
        ("prime", {"N": 1}, "P", 0),
        ("gcd", {"X": 12, "Y": 18}, "G", 6),
    ],
)
def test_examples(examples_dir, name, state, var, expected):
    p = parse((examples_dir / f"{name}.sipl").read_text(encoding="utf-8"))
    r = run(p, state)
    assert r.ok, r.error
    assert r.state[var] == expected


def test_skip_keeps_state():
    assert run_src("begin skip end", X=1).state == {"X": 1}


def test_if_branches():
    src = "begin if X > 0 then Y := 1 else Y := 2 end"
    assert run_src(src, X=1).state["Y"] == 1
    assert run_src(src, X=0).state["Y"] == 2


def test_while_zero_iterations():
    r = run_src("begin while X > 0 do X := X - 1 end", X=0)
    assert r.state == {"X": 0}


def test_arithmetic():
    r = run_src("begin A := 7 + 3 * 2 - 1; B := 7 div 2; C := 7 mod 2; D := -7 div 2; E := -1 end")
    assert r.state == {"A": 12, "B": 3, "C": 1, "D": -4, "E": -1}


def test_conditions():
    src = "begin if not (X = 1) or X > 5 then R := 1 else R := 0 end"
    assert run_src(src, X=1).state["R"] == 0
    assert run_src(src, X=2).state["R"] == 1
    assert run_src(src, X=6).state["R"] == 1


def test_undefined_variable_is_error():
    r = run_src("begin X := Y + 1 end")
    assert r.status == "error"
    assert isinstance(r.error, UndefinedVariableError)
    assert r.error.span.column == 12


def test_division_by_zero():
    r = run_src("begin X := 1 div 0 end")
    assert isinstance(r.error, DivisionByZeroError)
    r = run_src("begin X := 1 mod (Y - Y) end", Y=3)
    assert isinstance(r.error, DivisionByZeroError)


def test_step_limit_stops_infinite_loop():
    r = run(parse("begin X := 0; while 1 > 0 do X := X + 1 end"), max_steps=100)
    assert r.status == "step_limit"
    assert isinstance(r.error, StepLimitExceeded)
    assert r.steps == 101
    assert "infinite loop" in r.error.message


def test_step_limit_with_skip_body():
    r = run(parse("begin while 1 > 0 do skip end"), max_steps=10)
    assert r.status == "step_limit"


def test_initial_state_not_mutated():
    st = {"X": 3}
    r = run(parse("begin X := X - 1 end"), st)
    assert st == {"X": 3}
    assert r.initial_state == {"X": 3} and r.state == {"X": 2}


def test_result_to_dict():
    r = trace(parse("begin X := 1 end"))
    d = r.to_dict(with_trace=True)
    assert d["status"] == "ok" and d["state"] == {"X": 1}
    assert d["trace"][0]["kind"] == "start"
    r = run_src("begin X := Y end")
    assert r.to_dict()["error"]["code"] == "E201"


def test_format_state():
    assert format_state({"X": 5, "Y": 2}) == "[X ↦ 5, Y ↦ 2]"
    assert format_state({}) == "[]"


def test_eval_helpers():
    p = parse("begin if X > 1 then R := X * 2 else skip end")
    assert eval_aexp(p.body.then_branch.value, {"X": 4}) == 8
    assert eval_bexp(p.body.cond, {"X": 4}) is True
