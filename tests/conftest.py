import copy
from datetime import date
from pathlib import Path

import pytest

from airisk.loader import load_raw

EXAMPLE = Path(__file__).parent.parent / "examples" / "northwind"
AS_OF = date(2026, 11, 3)


@pytest.fixture
def raw():
    return copy.deepcopy(load_raw(EXAMPLE))


def risk(raw, risk_id):
    return next(r for r in raw["risks"] if r["id"] == risk_id)
