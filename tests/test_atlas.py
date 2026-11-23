"""Атлас карт: все карты доступны из выбора героя, фильтры и возврат работают."""
import pygame

from deck.atlas import CardAtlasScreen
from deck.game import DescentGame
from deck.ui import HeroSelect
from tests.test_expedition import ED
from tests.test_expedition_ui import SCREEN


def test_atlas_opens_from_hero_select_and_shows_all_cards():
    g = DescentGame(seed=2, gd=ED)
    sc = HeroSelect(g)
    sc.draw(SCREEN)
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=sc.atlas_rect.center))
    assert isinstance(g.scene, CardAtlasScreen)
    atlas = g.scene
    g.update(1 / 60)                                           # общий цикл игры не должен падать
    g.draw(SCREEN)
    assert len(atlas.filtered()) == len(atlas.data["cards"]["cards"])
    assert atlas.card_rects                                   # на экране есть карты


def test_atlas_filters_and_esc_returns():
    g = DescentGame(seed=2, gd=ED)
    g.open_atlas()
    atlas = g.scene
    g.draw(SCREEN)
    priest = next(r for r, key, _ in atlas.filter_rects if key == "priest")
    atlas.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=priest.center))
    assert atlas.filter == "priest"
    assert all(atlas._owner(c) == "priest" for c in atlas.filtered())
    atlas.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert not isinstance(g.scene, CardAtlasScreen)
