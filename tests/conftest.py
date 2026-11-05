"""Общие настройки тестов: логический холст по умолчанию 1280×800.

Адаптивный экран меняет ui.theme.SCREEN_W/H на лету; тесты, которые проверяют вёрстку 1280,
не должны зависеть от порядка запуска.
"""
import pytest

from sim.combat import Combat
from ui import theme as T

# тесты механик кастуют и сразу проверяют итог — для них удар без полёта (время попадания проверяет test_hit_timing)
INSTANT_MODULES = {"test_heroes", "test_rework1", "test_rework2", "test_rework3", "test_tags", "test_pixfx"}


@pytest.fixture(autouse=True)
def _reset_screen_size():
    old = (T.SCREEN_W, T.SCREEN_H)
    T.SCREEN_W, T.SCREEN_H = 1280, 800
    try:
        yield
    finally:
        T.SCREEN_W, T.SCREEN_H = old


@pytest.fixture(autouse=True)
def _instant_hits(request):
    old = Combat.HIT_TIMING
    Combat.HIT_TIMING = request.module.__name__.rsplit(".", 1)[-1] not in INSTANT_MODULES
    try:
        yield
    finally:
        Combat.HIT_TIMING = old
