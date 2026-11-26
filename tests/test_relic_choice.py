import pygame
import pytest

from deck.game import DescentGame
from deck import model as M
from deck.relic_choice import RelicChoice
from deck.ui import BattleScreen
from tests.test_expedition import ED
from test_deck import hero_battle


@pytest.mark.parametrize("key, expected", [(pygame.K_ESCAPE, None), (pygame.K_2, (4, 2))])
def test_battle_relic_choice_suspends_and_resumes_job(key, expected):
    game = DescentGame(seed=2, gd=ED)
    battle, game.run = hero_battle("merc")
    screen = BattleScreen(game, battle)
    selected = []

    def effect():
        selected.append((yield RelicChoice("Масляный желоб", [("Клетка 3, 2", (3, 2)), ("Клетка 4, 2", (4, 2))])))

    screen.run_job(effect())
    screen.update(1 / 60)
    assert screen.relic_choice and not selected
    screen.update(1 / 60)
    assert not selected
    screen.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
    screen.update(1 / 60)
    assert selected == [expected] and screen.job is None


def test_relic_with_unassigned_tag_appears_in_atlas_but_not_loot_until_usable():
    run = M.Run(hero="hunter", seed=2)
    assert "tin_bandolier" in run.data["relics"]["relics"]
    assert "tin_bandolier" not in {r["id"] for r in run.relic_offer(1000)}
    run.defs = {**run.defs, "test_bullet": dict(run.defs["h_shot"], rules=["bullet"])}
    assert "tin_bandolier" in {r["id"] for r in run.relic_offer(1000)}
