from pathlib import Path

import pytest

from sipl import parse
from sipl.diagnostics import SiplSyntaxError

HERE = Path(__file__).parent / "grammar"
VALID = sorted((HERE / "valid").glob("*.sipl"))
INVALID = sorted((HERE / "invalid").glob("*.sipl"))


def test_enough_fixtures():
    assert len(VALID) >= 10
    assert len(INVALID) >= 10


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_programs_parse(path):
    parse(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_programs_fail(path):
    with pytest.raises(SiplSyntaxError) as info:
        parse(path.read_text(encoding="utf-8"))
    span = info.value.span
    assert span.line >= 1 and span.column >= 1


def test_examples_parse(examples_dir):
    files = list(examples_dir.glob("*.sipl"))
    assert len(files) >= 3
    for f in files:
        parse(f.read_text(encoding="utf-8"))
