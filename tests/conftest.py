import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def profiles():
    result = []
    for name in ("sympy-equation.json", "open-meteo-weathernext2.json"):
        with (ROOT / "profiles" / name).open(encoding="utf-8") as stream:
            result.append(json.load(stream))
    return result


@pytest.fixture
def root():
    return ROOT
