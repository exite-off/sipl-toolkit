import io
import json
import subprocess
import sys

import pytest

from sipl.cli import EXIT_OK, EXIT_RUNTIME, EXIT_STEP_LIMIT, EXIT_SYNTAX, EXIT_USAGE, main, parse_state


def call(*argv, stdin=None, monkeypatch=None):
    out, err = io.StringIO(), io.StringIO()
    code = main(list(argv), out, err)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture
def power(examples_dir):
    return str(examples_dir / "power.sipl")


@pytest.fixture
def bad(tmp_path):
    f = tmp_path / "bad.sipl"
    f.write_text("begin\n  X := 1;\nend\n", encoding="utf-8")
    return str(f)


def test_check_ok(power):
    code, out, _ = call("check", power)
    assert code == EXIT_OK and out.strip().endswith("OK")


def test_check_error_text(bad):
    code, _, err = call("check", bad)
    assert code == EXIT_SYNTAX
    assert "bad.sipl:3:1: error:" in err


def test_check_error_json(bad):
    code, out, _ = call("check", bad, "--json")
    data = json.loads(out)
    assert code == EXIT_SYNTAX
    assert data["schema_version"] == 1 and data["ok"] is False
    diag = data["diagnostics"][0]
    assert diag["span"]["line"] == 3 and diag["span"]["column"] == 1
    assert diag["code"] == "E101"


def test_check_json_ok(power):
    data = json.loads(call("check", power, "--json")[1])
    assert data["ok"] and data["variables"] == ["R", "Y", "X"]


def test_parse_text_and_json(power):
    code, out, _ = call("parse", power)
    assert code == 0 and out.startswith("Program") and "While" in out
    data = json.loads(call("parse", power, "--json")[1])
    assert data["ast"]["type"] == "Program"


def test_run(power):
    code, out, _ = call("run", power, "-s", "X=5", "-s", "Y=2", "-v")
    assert code == 0
    assert "R ↦ 25" in out and "steps:" in out


def test_run_json(power):
    data = json.loads(call("run", power, "-s", "X=5,Y=2", "--json")[1])
    assert data["status"] == "ok" and data["state"]["R"] == 25
    assert data["initial_state"] == {"X": 5, "Y": 2}
    assert "trace" not in data


def test_trace_text_and_json(power):
    code, out, _ = call("trace", power, "-s", "X=2,Y=1")
    assert code == 0 and "assign" in out and "R: ⊥ -> 1" in out and "while -> false" in out
    data = json.loads(call("trace", power, "-s", "X=2,Y=1", "--json")[1])
    kinds = [e["kind"] for e in data["trace"]]
    assert kinds[0] == "start" and kinds[-1] == "finish"


def test_runtime_error(tmp_path):
    f = tmp_path / "u.sipl"
    f.write_text("begin X := Y end", encoding="utf-8")
    code, _, err = call("run", str(f))
    assert code == EXIT_RUNTIME and "Y is undefined" in err
    data = json.loads(call("run", str(f), "--json")[1])
    assert data["status"] == "error" and data["diagnostics"][0]["code"] == "E201"


def test_step_limit(examples_dir):
    f = str(examples_dir / "errors" / "infinite_loop.sipl")
    code, _, err = call("run", f, "--max-steps", "20")
    assert code == EXIT_STEP_LIMIT and "step limit" in err
    code, _, err = call("trace", f, "--max-steps", "5")
    assert code == EXIT_STEP_LIMIT


def test_syntax_error_in_run(bad):
    assert call("run", bad)[0] == EXIT_SYNTAX
    assert call("parse", bad)[0] == EXIT_SYNTAX
    assert call("term", bad)[0] == EXIT_SYNTAX


def test_term(power):
    code, out, _ = call("term", power)
    assert out.strip() == "AS^R(1) · WH(S^2(gr, Y⇒, 0), AS^R(S^2(mult, R⇒, X⇒)) · AS^Y(S^2(sub, Y⇒, 1)))"
    code, out, _ = call("term", power, "--steps", "--ascii")
    assert "1. NS_Prog" in out and "Y=>" in out
    data = json.loads(call("term", power, "--json")[1])
    assert data["tree"]["term"] == "seq"


def test_usage_errors(power):
    assert call("run", power, "-s", "X")[0] == EXIT_USAGE
    assert call("run", power, "-s", "X=abc")[0] == EXIT_USAGE
    assert call("check", "missing-file.sipl")[0] == EXIT_USAGE
    with pytest.raises(SystemExit) as info:
        main(["unknown"], io.StringIO(), io.StringIO())
    assert info.value.code == EXIT_USAGE


def test_parse_state():
    assert parse_state(["X=1, Y=-2", "Z=3", ""]) == {"X": 1, "Y": -2, "Z": 3}


def test_stdin(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("begin X := 2 end"))
    code, out, _ = call("run", "-")
    assert code == 0 and "X ↦ 2" in out


def test_module_entry_point(power):
    # real process, as an IDE would call it
    proc = subprocess.run(
        [sys.executable, "-m", "sipl", "run", power, "-s", "X=3,Y=3", "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["state"]["R"] == 27


def test_version():
    with pytest.raises(SystemExit) as info:
        main(["--version"], io.StringIO(), io.StringIO())
    assert info.value.code == 0


SCHEMA = json.loads(
    (
        __import__("pathlib").Path(__file__).parent.parent / "docs" / "schema" / "cli-output.schema.json"
    ).read_text(encoding="utf-8")
)


@pytest.mark.parametrize(
    "argv",
    [
        ["parse"],
        ["check"],
        ["run", "-s", "X=2,Y=3"],
        ["trace", "-s", "X=2,Y=3"],
        ["term"],
        ["run"],
        ["trace", "--max-steps", "3", "-s", "X=2,Y=3"],
    ],
)
def test_json_output_matches_schema(power, bad, argv):
    jsonschema = pytest.importorskip("jsonschema")
    for path in (power, bad):
        out = call(argv[0], path, *argv[1:], "--json")[1]
        jsonschema.validate(json.loads(out), SCHEMA)
