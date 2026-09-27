"""Fixtures do motor. Os geradores sintéticos moram em sinteticos.py."""

import pytest

from arco_motor.tipos import SerieRestricao
from sinteticos import serie_sintetica


@pytest.fixture
def serie_dois_dias() -> SerieRestricao:
    return serie_sintetica()
