"""Боевые QoL: прогноз навыка, реакция и автопауза."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from sim.data import GameData  # noqa: E402
from sim.combat import Combat, ENEMY, PLAYER  # noqa: E402
from ui.battle_view import BattleView  # noqa: E402

pygame.init()
DATA = GameData()


def test_forecast_and_reaction_preview():
    c = Combat(DATA, 0, ai_teams=(ENEMY,))
    hero = c.heroes(PLAYER)[0]
    foe = c.alive(ENEMY)[0]
    sk = DATA.skills["ice_bolt"]
    view = BattleView(DATA)
    dmg = view._forecast_damage(hero, sk, foe)
    assert dmg > 0
    foe.statuses["water"] = 2.0
    react = view._reaction_preview(sk, foe)
    assert react and react["id"] == "freeze"


def test_full_stats_contains_core_unit_numbers():
    c = Combat(DATA, 0, ai_teams=(ENEMY,))
    hero = c.heroes(PLAYER)[0]
    view = BattleView(DATA)
    view.reset(c)
    rows = {label: value for label, value, _ in view.full_stats(hero)}
    for label in ("Здоровье", "Атака", "Скорость атаки", "Дальность", "Сила навыков",
                  "Крит", "Уклонение", "Броня", "AP", "Шаг"):
        assert label in rows


def test_auto_pause_toggle_in_run_battle():
    from game.battle_scene import BattleScene

    scene = BattleScene(DATA, 0, on_finish=lambda *a: None)
    assert scene.auto_pause
    scene._key(pygame.K_F4)
    assert not scene.auto_pause
    scene._key(pygame.K_F4)
    assert scene.auto_pause


def test_hero_info_button_opens_left_card_and_close_button_works():
    from game.battle_scene import BattleScene
    from tests.test_expedition_ui import SCREEN

    scene = BattleScene(DATA, 0, on_finish=lambda *a: None)
    scene.begin_battle()
    scene.draw(SCREEN)
    r, hero = scene.view.squad_rects[0]
    scene._click(r.center, 1)
    assert scene.inspect_hero is None          # клик по герою только выбирает
    scene.draw(SCREEN)
    assert scene.view.hero_info_rect is not None
    scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=scene.view.hero_info_rect.center, button=1))
    assert scene.inspect_hero is hero
    scene.draw(SCREEN)
    assert scene.view.info_close is not None
    scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=scene.view.info_close.center, button=1))
    assert scene.inspect_hero is None
