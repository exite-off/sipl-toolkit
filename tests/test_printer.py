import pytest

from sipl import parse
from sipl.printer import to_source

CASES = [
    "begin X := 1 - (2 - 3) end",
    "begin X := (1 + 2) * 3 end",
    "begin X := 1 + 2 * 3 end",
    "begin if not (X = 1 or X > 2) then skip else skip end",
    "begin if X = 1 or (X > 2 or X > 3) then skip else skip end",
    "begin while X > 0 do begin X := X - 1; skip end end",
    "begin Y := X div 2 mod 3 end",
]


@pytest.mark.parametrize("src", CASES)
def test_round_trip(src):
    p = parse(src)
    printed = to_source(p)
    assert parse(printed) == p
    assert printed == src


def test_examples_round_trip(examples_dir):
    for f in examples_dir.glob("*.sipl"):
        p = parse(f.read_text(encoding="utf-8"))
        assert parse(to_source(p)) == p
