import pytest

from sipl import ast, parse
from sipl.diagnostics import SiplSyntaxError
from sipl.parser import grammar_text, parse_tree

POWER = """begin
 R := 1;
 while Y > 0 do
 begin
  R := R * X;
  Y := Y - 1
 end
end"""


def body(src: str):
    return parse(src).body


def test_power_program_structure():
    p = parse(POWER)
    assert isinstance(p, ast.Program)
    seq = p.body
    assert isinstance(seq, ast.Seq)
    assert seq.first == ast.Assign(
        "R", ast.Num(1, span=ast.UNKNOWN_SPAN), span=ast.UNKNOWN_SPAN, target_span=ast.UNKNOWN_SPAN
    )
    loop = seq.second
    assert isinstance(loop, ast.While)
    assert isinstance(loop.body, ast.Block)
    assert isinstance(loop.body.body, ast.Seq)


def test_spans_point_to_source():
    p = parse(POWER)
    loop = p.body.second
    assert (loop.span.line, loop.span.column) == (3, 2)
    assert (loop.span.end_line, loop.span.end_column) == (7, 5)
    assert POWER[loop.cond.span.start : loop.cond.span.end] == "Y > 0"
    assign = loop.body.body.first
    assert POWER[assign.span.start : assign.span.end] == "R := R * X"
    assert assign.target_span.line == 5
    assert p.span.start == 0 and p.span.end == len(POWER)


def test_seq_is_weaker_than_while():
    # while b do S1; S2  ==  (while b do S1); S2
    s = body("begin while X > 0 do X := X - 1; Y := 1 end")
    assert isinstance(s, ast.Seq)
    assert isinstance(s.first, ast.While)
    assert isinstance(s.second, ast.Assign)


def test_seq_is_left_assoc():
    s = body("begin A := 1; B := 2; C := 3 end")
    assert isinstance(s, ast.Seq) and isinstance(s.first, ast.Seq)
    assert s.second.target == "C"


def test_arith_precedence_and_assoc():
    a = body("begin X := 1 - 2 - 3 * 4 end").value
    assert a.op == "-"
    assert a.left.op == "-"
    assert a.right.op == "*"


def test_parentheses_change_tree():
    a = body("begin X := (1 - 2) * 3 end").value
    assert a.op == "*" and a.left.op == "-"


def test_negative_literal():
    a = body("begin X := Y - -1 end").value
    assert a.op == "-" and a.right == ast.Num(-1, span=ast.UNKNOWN_SPAN)


def test_condition_operators():
    c = body("begin if not X = 1 or X > 2 then skip else skip end").cond
    assert isinstance(c, ast.Or)
    assert isinstance(c.left, ast.Not)
    assert isinstance(c.right, ast.Compare) and c.right.op == ">"


def test_unicode_and_ascii_operators_are_equal():
    a = body("begin if ¬ X = 1 ∨ X > 2 then skip else skip end")
    b = body("begin if not X = 1 or X > 2 then skip else skip end")
    c = body("begin if ! X = 1 \\/ X > 2 then skip else skip end")
    assert a == b == c


def test_to_dict_has_spans():
    d = parse("begin X := 1 end").to_dict()
    assert d["type"] == "Program"
    assert d["body"]["type"] == "Assign"
    assert d["body"]["value"] == {"type": "Num", "value": 1, "span": d["body"]["value"]["span"]}
    assert d["body"]["span"]["column"] == 7


def test_all_node_kinds_serialize():
    src = (
        "begin if not (X = 1) or X > 2 then begin X := X div 2 end else skip; while X > 0 do X := X mod 3 end"
    )
    d = parse(src).to_dict()
    assert "Or" in str(d) and "Not" in str(d) and "While" in str(d) and "Block" in str(d)


def test_variables_order():
    p = parse("begin R := 1; while Y > 0 do R := R * X end")
    assert ast.variables(p) == ["R", "Y", "X"]


def test_walk_visits_all_nodes():
    p = parse(POWER)
    kinds = {type(n).__name__ for n in p.walk()}
    assert kinds >= {"Program", "Seq", "Assign", "While", "Block", "BinOp", "Var", "Num", "Compare"}


def test_parse_tree_is_concrete():
    tree = parse_tree("begin X := (1) end")
    assert tree.data == "start"


def test_grammar_text_available():
    assert "program" in grammar_text()


@pytest.mark.parametrize(
    "src, line, col, fragment",
    [
        ("begin X := 1; end", 1, 15, "';' before 'end'"),
        ("begin if X > 0 then skip end", 1, 26, "needs an 'else'"),
        ("begin X := 1 Y := 2 end", 1, 14, "missing ';'"),
        ("begin X = 1 end", 1, 9, "expected ':='"),
        ("begin X := 1 @ end", 1, 14, "unexpected character '@'"),
        ("begin\n  X := 1\n", 3, 1, "unexpected end of input"),
        ("begin while X do skip end", 1, 15, "expected one of '+', '-', '=', '>'"),
    ],
)
def test_syntax_diagnostics(src, line, col, fragment):
    with pytest.raises(SiplSyntaxError) as info:
        parse(src)
    err = info.value
    assert fragment in err.message
    if "end of input" not in fragment:
        assert (err.span.line, err.span.column) == (line, col)
    d = err.diagnostic.to_dict()
    assert d["severity"] == "error" and d["code"].startswith("E1")


def test_parse_file(tmp_path):
    from sipl import parse_file

    f = tmp_path / "a.sipl"
    f.write_text("begin skip end", encoding="utf-8")
    assert isinstance(parse_file(str(f)).body, ast.Skip)
