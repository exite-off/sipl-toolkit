from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def examples_dir() -> Path:
    return ROOT / "examples"
