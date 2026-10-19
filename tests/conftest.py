from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EPHE = ROOT / "data" / "ephe"


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT
