"""Широкий экран: сцены используют боковые поля, а не чёрные полосы."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from deck import gfx as G
from deck.battle import Battle
from deck.game import DescentGame
from deck.ui import BattleScreen, MapScreen, wide_layout
from tests.test_expedition import ED
from deck import model as M

pygame.init()


def test_wide_layout_fills_21_9_and_map_uses_the_width():
    native = pygame.Surface((2560, 1080))
    canvas = G.Canvas(native)
    assert wide_layout(canvas)[0] > 1800
    assert canvas.LW > 1800

    game = DescentGame(seed=1, gd=ED)
    game.run = M.Run(data=game.data, seed=1, hero="merc")
    page = MapScreen(game)
    page.relayout(canvas.LW)
    assert page.board.w > 1500


def test_battle_hand_spans_wide_screen_and_hero_is_larger():
    game = DescentGame(seed=1, gd=ED)
    run = game.run = M.Run(data=game.data, seed=1, hero="merc")
    battle = Battle(ED, run, run.fights[0], seed=1)
    screen = BattleScreen(game, battle)
    screen.relayout(1896, 800)
    assert screen.hand_area.w > 1000
    assert screen.W == 1896
    assert screen.view.hero_scale == 1.0
