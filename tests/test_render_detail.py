"""Земля боя после смены рельефа (перековка геоманта) перерисовывается окном и совпадает с полной сборкой;
детализация моделей меняет спрайты; худ героя — в цвете класса."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
import pygame  # noqa: E402

from test_expedition import ED, X  # noqa: E402
from sim.combat import Combat  # noqa: E402
from ui import settings as S  # noqa: E402
from ui import theme as T  # noqa: E402
from ui.ground import GroundPainter  # noqa: E402
from ui.sprites import SpriteBank  # noqa: E402

pygame.init()


def combat():
    h = [X.Hero({"uid": "g", "name": "Г", "cls": "geomancer", "skills": []})]
    run = X.Expedition(ED, h, seed=3)
    run.node = next(n for n, v in run.nodes.items() if v["type"] == "battle")
    return Combat(run.data, run.nodes[run.node]["encounter"], squad=run.combat_squad(), enemy_scale=run.enemy_scale())


def test_reshaped_cell_repaints_window_like_full_build():
    c = combat()
    g = GroundPainter(ED)
    g.base(c)
    cells = [p for p, cell in sorted(c.grid.cells.items()) if cell.passable][:3]
    for p, t in zip(cells, ("stone", "water", "stone")):
        c.grid.get(p).terrain = t
        g.base(c)
    inc = g._prep["last"][1]
    tm, names = g._terrain_map(c)
    full = g._paint(c, tm, names, g.palette(c), g.style(c), g._prep, (0, inc.shape[0], 0, inc.shape[1]))
    assert (inc == full).all()
    before = g.base(c)
    c.grid.get(cells[0]).terrain = "grass"
    g.base(c)
    c.grid.get(cells[0]).terrain = "stone"
    assert g.base(c) is before                       # вернулся прежний рельеф — готовая карта из кеша


def test_model_detail_setting_changes_sprites():
    bank = SpriteBank()
    old = S.SETTINGS.get("sprite_res", 32)
    try:
        sizes = {}
        for res in (16, 32, 64):
            S.SETTINGS["sprite_res"] = res
            img = bank.get(["warrior"], "warrior", (200, 90, 60))
            sizes[res] = img.get_height()
            colors = np.unique(pygame.surfarray.array3d(img).reshape(-1, 3), axis=0)
            sizes[f"c{res}"] = len(colors)
        assert sizes[16] == sizes[32] == sizes[64] == 64              # на экране — тот же рост
        if os.path.exists(os.path.join("assets", "sprites", "x2", "warrior.png")):
            assert sizes["c64"] > sizes["c32"]                         # высокая детализация — больше деталей
    finally:
        S.SETTINGS["sprite_res"] = old


def test_hero_tint_follows_class_color():
    war, cryo = T.hero_tint(ED.classes["warrior"]["color"]), T.hero_tint(ED.classes["cryo"]["color"])
    assert war["accent"] != cryo["accent"] and war["accent"][0] > war["accent"][2]
    dark = T.hero_tint(ED.classes["assassin"]["color"])["accent"]
    assert 0.3 * dark[0] + 0.59 * dark[1] + 0.11 * dark[2] > 110       # тёмный класс высветлен, кайма читается
