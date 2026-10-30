"""Режим героев: атрибуты, уровни, скейлы навыков, уровни регионов и врагов. Основа игры не меняется."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from sim import stats  # noqa: E402
from sim.combat import Combat  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim.profile import Profile  # noqa: E402
from sim.teams import ENEMY  # noqa: E402

DATA = GameData()


def test_level_one_equals_base_game():
    base = Profile(DATA, None).start_run("reeds", 1)
    st = Profile(DATA, None, mode="stats").start_run("reeds", 1)
    for a, b in zip(base.squad, st.squad):
        pa, pb = base.proto(a), st.proto(b)
        assert pa["hp"] == pb["hp"] and pa["attack"]["damage"] == pb["attack"]["damage"]
        assert all(abs(v - 1.0) < 1e-9 for v in pb["scale"].values())


def test_points_and_growth_scale_hero():
    prof = Profile(DATA, None, mode="stats")
    rpg = prof.heroes["warrior"]["rpg"]
    rpg["level"] = 10
    assert stats.points_free(DATA, rpg) == 27
    assert prof.add_point("warrior", "str", 20) and not prof.add_point("warrior", "agi", 10)
    der = stats.derive(DATA, "warrior", rpg)
    assert der["scale"]["melee"] > 1.9 and der["scale"]["spell"] > 1.0       # авторост тоже даёт Интеллект
    run = prof.start_run("reeds", 1)
    war = next(m for m in run.squad if m.cls == "warrior")
    p0 = Profile(DATA, None).start_run("reeds", 1)
    assert run.proto(war)["hp"] > p0.proto(p0.squad[0])["hp"] * 1.8
    prof.reset_points("warrior")
    assert stats.points_free(DATA, rpg) == 27


def test_skill_damage_uses_school_attribute_and_crit():
    prof = Profile(DATA, None, mode="stats")
    prof.heroes["mage"]["rpg"]["level"] = 15
    run = prof.start_run("reeds", 1)
    c = Combat(DATA, 1, squad=run.combat_squad(), enemy_scale={"level": 1, "stats": True})
    c.ais = []
    mage = next(u for u in c.heroes() if u.proto_id == "mage")
    foe = c.fighters(ENEMY)[0]
    foe.max_hp = foe.hp = 9999
    foe.armor = 0
    hp = foe.hp
    c.damage(foe, 20, mage, None, "spell")
    assert hp - foe.hp >= int(20 * mage.proto["scale"]["spell"]) - 1 > 20


def test_enemy_levels_and_titles():
    scale = {"level": 12, "stats": True}
    c = Combat(DATA, 1, enemy_scale=scale, seed=5)
    plain = Combat(DATA, 1, seed=5)
    for a, b in zip(c.fighters(ENEMY), plain.fighters(ENEMY)):
        assert a.level >= 12 and a.max_hp > b.max_hp and a.atk_damage > b.atk_damage
    titled = [u for s in range(1, 30) for u in Combat(DATA, 1, enemy_scale=scale, seed=s).fighters(ENEMY) if u.title]
    assert titled and all(u.level > 12 for u in titled)


def test_region_levels_grow_by_chapter_and_xp_levels_heroes():
    prof = Profile(DATA, None, mode="stats", sandbox=True)
    assert prof.region_level("reeds", "swamp") < prof.region_level("citadel_r0", "citadel")
    assert prof.region_level("reeds", "swamp", "nightmare") > prof.region_level("reeds", "swamp")
    run = prof.start_run("reeds", 1)
    before = run.squad[0].rpg["level"]
    run.node = next(n for n, v in run.nodes.items() if v["next"])
    run.stats_xp("elite")
    run.stats_xp("elite")
    assert run.squad[0].rpg["level"] > before
    run.result = "victory"
    prof.finish_run(run)
    assert prof.heroes[run.squad[0].cls]["rpg"]["level"] > before        # уровень сохраняется в профиле


def test_base_profile_untouched_and_mode_switch(tmp_path):
    from game.app import App
    pygame.init()
    base = tmp_path / "profile.json"
    prof = Profile(DATA, str(base))
    prof.amber = 77
    prof.save()
    app = App(DATA, 1, profile=Profile(DATA, str(base)), start="title")
    app.switch_mode("stats")
    assert app.profile.mode == "stats" and app.profile.path.endswith("stats.json") and app.profile.amber == 0
    app.profile.heroes["warrior"]["rpg"]["level"] = 5
    app.profile.save()
    app.switch_mode("base")
    assert app.profile.mode == "base" and app.profile.amber == 77
    app.switch_mode("stats")
    assert app.profile.heroes["warrior"]["rpg"]["level"] == 5


def test_stats_window_draws():
    from game.app import App
    from game.meta_scenes import HeroesScene
    pygame.init()
    screen = pygame.display.set_mode((1280, 800))
    prof = Profile(DATA, None, mode="stats")
    prof.heroes["warrior"]["rpg"]["level"] = 4
    app = App(DATA, 1, profile=prof, start="hub")
    s = HeroesScene(app, "warrior", "stats")
    s.draw(screen)
    rect = next(r for r, a, _ in s.hits if a == ("attr", "str", 5))
    s.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rect.center, button=1))
    assert prof.heroes["warrior"]["rpg"]["points"]["str"] == 5
    s.set_window("skills")
    s.update(0.1)
    s.draw(screen)
