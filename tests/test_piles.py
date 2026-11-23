"""Боевые стопки: клик по колоде/сбросу открывает отдельные вкладки."""
import pygame

from deck import model as M
from deck.game import DescentGame
from deck.piles import PileScreen
from tests.test_expedition import ED
from tests.test_expedition_ui import SCREEN


def _battle():
    g = DescentGame(seed=9, gd=ED)
    g.start_run("merc")
    n = next(n for n in g.run.floor.available() if g.run.floor.nodes[n]["type"] in ("battle", "elite"))
    g.enter_node(n)
    sc = g.scene
    sc.draw(SCREEN)
    return g, sc, sc.b


def test_click_deck_and_discard_open_separate_piles():
    g, sc, b = _battle()
    assert sc.deck_pile_rect is not None and sc.discard_pile_rect is not None
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=sc.deck_pile_rect.center))
    assert isinstance(g.scene, PileScreen) and g.scene.tab == "deck"
    pile = g.scene
    assert len(pile.sources["deck"]) == len(b.draw_pile)
    pile.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert g.scene is sc

    b.used = [M.Card("strike", b.run.defs)]
    b.discard = [M.Card("strike", b.run.defs)]
    sc.draw(SCREEN)
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=sc.discard_pile_rect.center))
    assert isinstance(g.scene, PileScreen) and g.scene.tab == "discard"
    piles = g.scene
    assert len(piles.sources["used"]) == 1 and len(piles.sources["discard"]) == 1
    g.draw(SCREEN)
    used_tab = next(r for r, key, _ in piles.tab_rects if key == "used")
    piles.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=used_tab.center))
    assert piles.tab == "used" and piles.cards == piles.sources["used"]
