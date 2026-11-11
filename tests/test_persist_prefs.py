"""Скорость боя и автокаст похода запоминаются; настройки переживают перезапуск; после последнего босса — сразу итог."""
import pygame

from tests.test_expedition_ui import frame, key
from tests.test_map_keys import start


def test_settings_survive_reload(tmp_path):
    from ui import settings
    settings.SETTINGS["sprite_res"] = 64
    settings.save()
    settings.SETTINGS["sprite_res"] = 32
    settings.load()
    assert settings.SETTINGS["sprite_res"] == 64
    assert settings.PATH.startswith(str(tmp_path))          # тесты не пишут в save/settings.json игрока


def test_battle_speed_carries_over(tmp_path):
    from game.battle_scene import BattleScene
    from sim.data import GameData
    from ui import settings
    data = GameData()
    b = BattleScene(data, 0, on_finish=lambda c, f: None)
    assert b.speed_idx == 1
    b.begin_battle()
    b._key(pygame.K_F3)
    assert settings.SETTINGS["battle_speed"] == 2
    settings.load()
    assert BattleScene(data, 1, on_finish=lambda c, f: None).speed_idx == 2


def test_autocast_mode_at_start(tmp_path):
    from game.tavern_rooms import MusterRoom
    for mode, want in (("off", False), ("on", True)):
        app = start_with(tmp_path / mode, mode)
        run = app.exp
        assert run.autocast_mode == mode
        for sq, h in zip(run.combat_squad(), run.heroes):
            assert sq["autocast"] and all(st["on"] is want for st in sq["autocast"].values())
        h = run.heroes[0]
        sid = next(iter(h.autocast))
        h.autocast[sid]["on"] = not want                       # переключили в бою — режим это не трогает
        run.combat_squad()
        assert h.autocast[sid]["on"] is (not want)
    assert MusterRoom                                           # экран с переключателем существует


def start_with(path, mode):
    from ui import settings
    path.mkdir()
    settings.put("autocast_start", mode)
    return start(path)


def test_final_boss_goes_to_end(tmp_path):
    from game.expedition_scenes import EndScene, StatsScene, battle_done
    app = start(tmp_path)
    run = app.exp
    run.act = len(run.xd["acts"]) - 1
    boss = next(n for n in run.nodes.values() if n["type"] == "boss")
    run.node = boss["id"]
    for h in run.heroes:
        h.sp = 1                                                # даже с невыбранными улучшениями — сразу итог

    class FakeCombat:
        result = "victory"

    stats = {"rows": [], "time": 1.0, "killed": 1, "foes": 1}
    run.finish_battle = lambda c, f: (setattr(run, "result", "victory"),
                                      {"result": "victory", "stats": stats})[1]
    battle_done(app, FakeCombat(), None)
    assert isinstance(app.scene, EndScene) and app.scene.stats is stats
    frame(app)
    key(app, pygame.K_TAB)
    assert isinstance(app.scene, StatsScene)
