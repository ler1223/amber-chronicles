"""Переделка механики класса не ломает тесты: тесты исчезнувших навыков и пассивок пропускаются с причиной."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from needs import need, need_core  # noqa: E402


def test_missing_skill_skips_instead_of_failing():
    with pytest.raises(pytest.skip.Exception, match="нет навыка"):
        need("no_such_skill_anymore")
    with pytest.raises(pytest.skip.Exception, match="у класса archer"):
        need("fireball", cls="archer")          # навык есть, но не у этого класса
    need("aimed_shot", cls="archer")            # есть — тест идёт дальше


def test_changed_passive_skips_instead_of_failing():
    with pytest.raises(pytest.skip.Exception, match="пассивка"):
        need_core("archer", "old_core")


def test_setup_with_removed_skill_skips():
    from test_characters import setup
    with pytest.raises(pytest.skip.Exception):
        setup("archer", ["quiver_fire"])        # колчаны-навыки убраны — тест старой механики пропустится
