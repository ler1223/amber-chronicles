import pygame

from deck import elf_ui
from deck.game import DescentGame
from deck.ui import BattleScreen
from test_deck import hero_battle
from tests.test_expedition import ED


def test_garden_hud_tracks_live_plants_and_ring_duration(monkeypatch):
    game = DescentGame(seed=3, gd=ED)
    battle, game.run = hero_battle("elf")
    garden = battle.garden
    a, b, c, *_ = [cell for cell in battle.c.grid.cells if battle.free(cell)]
    tree = garden.spawn_plant("world_tree", a, 1)
    seed = garden.spawn_plant("thorn_seed", b, 2)
    removed = garden.spawn_plant("moon_flower", c, 0)
    removed.alive = False
    garden.rings.append({"cells": {a}, "turns": 1, "cell": a})
    battle.hero.ds["fae"] = 6

    assert elf_ui.plant_progress(garden, tree) == (5, 3, True)
    screen = BattleScreen(game, battle)
    surface = pygame.Surface((1280, 800))
    screen.ui_hidden = False
    screen.draw_mechanic(surface, 14, 516)
    assert [plant for _, plant in screen.garden_rows] == [seed, tree]

    calls = []
    monkeypatch.setattr(elf_ui, "draw_plant", lambda *args: calls.append(args[-1]))
    screen.mouse = screen.garden_rows[1][0].center
    screen.draw_unit_hud(surface, tree)
    assert calls == [True]

    battle.hero.ds["fae"] = 5
    assert elf_ui.plant_progress(garden, tree) == (5, 4, False)
