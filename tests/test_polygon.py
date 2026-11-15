"""Тестовый полигон: отдельная комната таверны, тренировочный бой без похода и наград."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from game.app import App  # noqa: E402
from game import tavern_rooms as TR  # noqa: E402
from sim.data import GameData  # noqa: E402

pygame.init()
SCREEN = pygame.display.set_mode((1280, 800))
DATA = GameData()


def new_app(tmp_path):
    app = App(DATA, seed=4)
    app.profile.path = str(tmp_path / "profile.json")
    app.switch_mode("expedition")
    app.to_hub()
    TR.go(app, "polygon")
    app.scene.update(1 / 30)
    app.scene.draw(SCREEN)
    return app


def click_action(app, action):
    r = next(r for r, a, _ in app.scene.hits if a == action)
    app.scene.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=r.center))
    app.scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=r.center, button=1))


def test_polygon_room_is_in_tavern_navigation():
    assert any(r[0] == "polygon" for r in TR.ROOMS)
    assert "polygon" in TR.ROOM_CLASSES


def test_polygon_scale_is_soft_and_grows_with_tier():
    a = TR.polygon_enemy_scale(0, "dummy")
    b = TR.polygon_enemy_scale(9, "dummy")
    assert a["damage"] < 1 and b["damage"] > a["damage"]
    assert a["hp"] < 1 and b["hp"] > a["hp"]


def test_polygon_starts_battle_without_starting_a_run(tmp_path):
    app = new_app(tmp_path)
    assert type(app.scene).__name__ == "PolygonRoom"
    click_action(app, ("polygon_start", "dummy"))
    assert type(app.scene).__name__ == "BattleScene"
    assert app.profile.run_state is None
    assert app.scene.squad and len(app.scene.squad) <= 4


def test_polygon_uses_worn_artifacts_without_crashing(tmp_path):
    from sim import artifacts as AR
    app = new_app(tmp_path)
    h = app.profile.recruitable()[0]
    set_id = next(iter(app.profile.xd["artifacts"]["sets"]))
    art = AR.make(app.profile.xd, "test-art", "bracers", set_id, 1.0)
    app.profile.stash[art["uid"]] = art
    h.arts.append(art["uid"])
    click_action(app, ("polygon_start", "dummy"))
    assert type(app.scene).__name__ == "BattleScene"
    assert app.profile.run_state is None


def test_polygon_saves_and_loads_test_preset(tmp_path):
    app = new_app(tmp_path)
    h = app.profile.recruitable()[0]
    app.scene.room_act(("recruit", h.uid))
    assert h.uid in app.scene.picked
    app.scene.room_act(("polygon_save",))
    assert "1" in app.profile.polygon_presets
    app.scene.picked.clear()
    app.scene.room_act(("polygon_load",))
    assert h.uid in app.scene.picked


def test_polygon_can_cycle_enemy_encounters(tmp_path):
    app = new_app(tmp_path)
    first = app.scene.encounter_name()
    app.scene.room_act(("polygon_enemy", 1))
    assert app.scene.encounter_name() != first


def test_polygon_can_cycle_enemy_power(tmp_path):
    app = new_app(tmp_path)
    first = app.scene.power_label()
    app.scene.room_act(("polygon_power",))
    assert app.scene.power_label() != first


def test_polygon_returns_after_battle_and_does_not_save_rewards(tmp_path):
    app = new_app(tmp_path)
    click_action(app, ("polygon_start", "dummy"))
    app.scene.begin_battle()
    app.scene.combat.win_now()
    for _ in range(8):
        app.scene.update(1 / 30)
        app.scene.draw(SCREEN)
    app.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="", mod=0))
    assert type(app.scene).__name__ == "PolygonRoom"
    last = getattr(app, "polygon_last", {})
    assert last.get("result") == "victory"
    assert last.get("totals", {}).get("dealt", 0) >= 0
    assert app.profile.run_state is None
