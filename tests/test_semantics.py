import pytest

from sipl import parse
from sipl.semantics import derive, sem_p

GOLDEN = [
    (
        "begin R := 1; while Y > 0 do begin R := R * X; Y := Y - 1 end end",
        "AS^R(1) · WH(S^2(gr, Y⇒, 0), AS^R(S^2(mult, R⇒, X⇒)) · AS^Y(S^2(sub, Y⇒, 1)))",
    ),
    ("begin skip end", "id"),
    ("begin X := N - M end", "AS^X(S^2(sub, N⇒, M⇒))"),
    (
        "begin if M > N then X := M else X := N end",
        "IF(S^2(gr, M⇒, N⇒), AS^X(M⇒), AS^X(N⇒))",
    ),
    (
        "begin if not (X = 0) or X > 1 then skip else X := 1 + 2 end",
        "IF(S^2(or, S^1(neg, S^2(eq, X⇒, 0)), S^2(gr, X⇒, 1)), id, AS^X(S^2(add, 1, 2)))",
    ),
    (
        "begin A := 1; begin B := 2; C := 3 end end",
        "AS^A(1) · (AS^B(2) · AS^C(3))",
    ),
    ("begin Q := X div 2; R := X mod 2 end", "AS^Q(S^2(div, X⇒, 2)) · AS^R(S^2(mod, X⇒, 2))"),
]


@pytest.mark.parametrize("src, expected", GOLDEN)
def test_golden_terms(src, expected):
    assert sem_p(parse(src)).render() == expected


def test_textbook_example_file(examples_dir):
    term = sem_p(parse((examples_dir / "power.sipl").read_text(encoding="utf-8")))
    assert str(term) == GOLDEN[0][1]


def test_ascii_rendering():
    t = sem_p(parse("begin X := Y; Z := 1 end"))
    assert t.render(ascii_only=True) == "AS^X(Y=>) . AS^Z(1)"


def test_derivation_steps_follow_textbook():
    d = derive(parse("begin R := 1; while Y > 0 do begin R := R * X; Y := Y - 1 end end"))
    rules = [s.rule for s in d.steps]
    assert rules[:5] == ["NS_Prog", "NS_Stm_Seq", "NS_Stm_As", "NS_A_Num", "NS_Stm_Wh"]
    assert "NS_Stm_BE" in rules and "NS_A_Mult" in rules and "NS_A_Sub" in rules
    assert str(d.steps[2]) == "NS_Stm_As: sem_S(R := 1) = AS^R(sem_A(1))"


def test_every_rule_kind_is_reachable():
    src = (
        "begin if not (X = 1) or X > 2 then begin X := X + 1 - 2 * 3 end else skip; "
        "while X > 0 do X := X div 2 mod 3 end"
    )
    rules = {s.rule for s in derive(parse(src)).steps}
    assert rules >= {
        "NS_Prog",
        "NS_Stm_Seq",
        "NS_Stm_If",
        "NS_Stm_BE",
        "NS_Stm_skip",
        "NS_Stm_Wh",
        "NS_Stm_As",
        "NS_A_Add",
        "NS_A_Sub",
        "NS_A_Mult",
        "NS_A_Div",
        "NS_A_Mod",
        "NS_A_Num",
        "NS_A_Var",
        "NS_B_eq",
        "NS_B_gr",
        "NS_B_or",
        "NS_B_neg",
    }


def test_term_json():
    d = derive(parse("begin while X > 0 do if X = 1 then skip else X := X - 1 end")).to_dict()
    assert d["tree"]["term"] == "while"
    assert d["tree"]["body"]["term"] == "if"
    assert d["rules"][0]["rule"] == "NS_Prog"
    full = derive(parse("begin begin X := 1; skip end; Y := -1 end")).to_dict()
    assert full["tree"]["first"]["term"] == "group"
    assert full["tree"]["second"]["value"] == {"term": "const", "value": -1}
