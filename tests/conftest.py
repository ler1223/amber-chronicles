"""Общие настройки тестов: логический холст по умолчанию 1280×800.

Адаптивный экран меняет ui.theme.SCREEN_W/H на лету; тесты, которые проверяют вёрстку 1280,
не должны зависеть от порядка запуска.
"""
import pytest

from ui import theme as T


@pytest.fixture(autouse=True)
def _reset_screen_size():
    old = (T.SCREEN_W, T.SCREEN_H)
    T.SCREEN_W, T.SCREEN_H = 1280, 800
    try:
        yield
    finally:
        T.SCREEN_W, T.SCREEN_H = old
