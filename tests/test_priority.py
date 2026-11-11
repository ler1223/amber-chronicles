"""Приоритет автокаста (порядок навыков и резерв AP), горящее масло, настройки читаемости боя."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame  # noqa: E402

from test_characters import DATA, put, run, setup  # noqa: E402
from sim import autocast as AC  # noqa: E402


def test_priority_order_and_reserve():
    order, res = AC.priority_for(["q", "w", "e"], ["e", "x", "q"], {"q": 2, "w": -1, "zz": 3})
    assert order == ["e", "q", "w"] and res == {"q": 2}
    assert AC.reserve_before(order, {"q": 2, "w": 1}, "w") == 3        # резервы сверху суммируются
    assert AC.reserve_before(order, {"e": 5}, "e") == 0                # у первого резерва нет


def test_autocast_follows_priority_and_keeps_reserve():
    c, h, foes = setup("archer", ["aimed_shot", "barrage"])
    from sim.autocast import AutoCaster
    ac = AutoCaster(c, h.team)
    for sid in h.skills:
        h.autocast[sid] = {"on": True, "conds": []}
    put(foes[0], (5, 2))
    h.ap = 6
    h.ac_order = ["aimed_shot", "barrage"] + [s for s in h.skills if s not in ("aimed_shot", "barrage")]
    assert ac.choose(h)[0] == "aimed_shot"                             # выше — раньше
    h.ac_order = ["barrage", "aimed_shot"] + h.ac_order[2:]
    assert ac.choose(h)[0] == "barrage"
    h.cooldowns["barrage"] = 5
    h.ap = 3                                                           # прицельный (3 AP) оставил бы 0
    h.ac_reserve = {"aimed_shot": 3}                                   # держим 3 AP под шквал выше
    assert ac.choose(h) is None or ac.choose(h)[0] != "aimed_shot"
    h.ap = 6
    assert ac.choose(h)[0] == "aimed_shot"


def test_oil_puddle_burns_whole_and_stronger():
    c, h, foes = setup("alchemist", ["oil_flask"])
    for p in ((5, 1), (5, 2), (5, 3), (6, 3)):
        cell = c.grid.get(p)
        cell.hazard, cell.hazard_time = "oil", 8.0
    c.grid.get((4, 2)).hazard, c.grid.get((4, 2)).hazard_time = "fire", 3.0     # огонь рядом с лужей
    run(c, 0.4)
    burning = [p for p in ((5, 1), (5, 2), (5, 3), (6, 3)) if c.grid.get(p).hazard == "fire"]
    assert len(burning) == 4 and all(c.grid.get(p).blaze for p in burning)
    assert c.grid.get((5, 2)).hazard_time > 6.0


def test_text_groups_can_be_hidden():
    pygame.init()
    from ui import settings
    from ui.battle_view import BattleView
    c, h, foes = setup("warrior", [])
    v = BattleView(DATA)
    v.reset(c)
    settings.SETTINGS["text_numbers"] = False
    assert v.float_text(h, "-10", (255, 255, 255), kind="number") is None
    assert v.float_text(h, "КРИТ!", (255, 255, 255)) is not None
    settings.SETTINGS["text_status"] = False
    assert v.float_text(h, "КРИТ!", (255, 255, 255)) is None
    settings.SETTINGS["text_skills"] = False
    assert v.float_text(h, "Удар", (255, 255, 255), kind="skill") is None


def test_line_skills_target_along_a_straight_path():
    pygame.init()
    from ui.battle_view import BattleView
    c, h, foes = setup("shaman", ["ball_lightning"])
    v = BattleView(DATA)
    v.reset(c)
    path, near = v._skill_shape(h, h.skill_defs["ball_lightning"], (h.cell[0] + 2, h.cell[1]))
    assert len(path) >= 4 and all(p[1] == h.cell[1] for p in path)    # прямая до конца дальности
    assert near                                                        # и клетки, которые шар заденет рядом


def test_effects_transparency_setting():
    from ui import settings
    from ui.vfx import Screen
    s = Screen()
    settings.SETTINGS["fx_alpha"] = 0.5
    assert abs(s.fx_alpha() - 0.5) < 1e-6                              # + пауза ещё прозрачнее
