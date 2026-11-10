from sipl import parse
from sipl.interpreter import EventKind, Interpreter, trace

POWER = "begin R := 1; while Y > 0 do begin R := R * X; Y := Y - 1 end end"


def kinds(events):
    return [e.kind for e in events]


def test_trace_starts_and_finishes():
    r = trace(parse(POWER), {"X": 5, "Y": 2})
    ks = kinds(r.events)
    assert ks[0] == EventKind.START
    assert ks[-1] == EventKind.FINISH
    assert r.events[-1].state == {"X": 5, "Y": 0, "R": 25}


def test_assign_events_have_old_and_new():
    r = trace(parse(POWER), {"X": 5, "Y": 2})
    assigns = [
        (e.data["variable"], e.data["old"], e.data["new"]) for e in r.events if e.kind == EventKind.ASSIGN
    ]
    assert assigns == [("R", None, 1), ("R", 1, 5), ("Y", 2, 1), ("R", 5, 25), ("Y", 1, 0)]


def test_condition_events():
    r = trace(parse(POWER), {"X": 5, "Y": 2})
    conds = [(e.data["value"], e.data["iteration"]) for e in r.events if e.kind == EventKind.CONDITION]
    assert conds == [(True, 0), (True, 1), (False, 2)]


def test_before_after_are_balanced():
    r = trace(
        parse("begin if X > 0 then begin skip; X := 1 end else skip; while X > 1 do skip end"), {"X": 1}
    )
    depth = 0
    for e in r.events:
        if e.kind == EventKind.BEFORE_STATEMENT:
            depth += 1
        elif e.kind == EventKind.AFTER_STATEMENT:
            depth -= 1
            assert depth >= 0
    assert depth == 0


def test_events_have_spans_and_state_snapshots():
    r = trace(parse(POWER), {"X": 2, "Y": 1})
    before = [e for e in r.events if e.kind == EventKind.BEFORE_STATEMENT]
    assert all(e.span.line == 1 for e in before)
    snapshot = before[0].state
    assert "R" not in snapshot
    d = before[0].to_dict()
    assert d["node"] == "Assign" and "span" in d and d["state"] == {"X": 2, "Y": 1}


def test_error_event():
    r = trace(parse("begin X := Y end"))
    assert r.events[-1].kind == EventKind.ERROR
    assert r.events[-1].data["error"]["code"] == "E201"


def test_custom_listener():
    seen = []
    Interpreter(parse("begin X := 1; Y := 2 end"), listeners=[lambda e: seen.append(e.kind)]).run()
    assert seen.count(EventKind.ASSIGN) == 2
