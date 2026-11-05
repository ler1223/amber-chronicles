"""Режим «Одиночка» и статистика боя: один герой в таверне, 6 слотов навыков (D и F — картами «новый навык»),
герой крепче, врагов меньше, выбор с героя не спадает, камера едет за ним; учёт урона, лечения и убийств."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame  # noqa: E402

from test_expedition import ED, X  # noqa: E402
from sim.combat import ENEMY, PLAYER, Combat  # noqa: E402

pygame.init()


def solo_run(seed=2, cls=None):
    prof = X.ExpeditionProfile(ED, solo=True)
    h = next((h for h in prof.roster if cls is None or h.cls == cls), prof.roster[0])
    return prof, prof.start([h.uid], seed=seed)


def test_solo_profile_takes_one_hero():
    prof = X.ExpeditionProfile(ED, solo=True)
    assert prof.mode == "solo" and not any(h.solo for h in prof.roster)   # таверна общая: «одиночка» — только в походе
    try:
        prof.start([h.uid for h in prof.roster[:2]], seed=1)
        assert False, "двоих в одиночку не берут"
    except ValueError:
        pass
    run = prof.start([prof.roster[0].uid], seed=1)
    assert run.solo and run.heroes[0].solo and len(run.heroes) == 1 and run.cfg["squad_max"] == 1
    assert run.apply_ops([{"recruit": 1}], None) == []                  # спутники не присоединяются
    back = X.Expedition.from_dict(ED, run.to_dict())
    assert back.solo and back.heroes[0].solo


def test_solo_hero_is_tougher_and_fights_fewer_enemies():
    _, run = solo_run()
    squad = X.Expedition(ED, [X.Hero(dict(run.heroes[0].to_dict(), solo=False))], seed=2)
    assert run.max_hp(run.heroes[0]) > 2 * squad.max_hp(squad.heroes[0])
    keep = ED.expedition["config"]["solo"]["keep"]
    for n in run.nodes.values():
        if n["type"] in ("battle", "elite") and n["encounter"] is not None:
            run.node = n["id"]
            c = Combat(run.data, n["encounter"], squad=run.combat_squad(), enemy_scale=run.enemy_scale())
            assert len(c.alive(ENEMY)) <= max(keep, len([u for u in c.alive(ENEMY) if u.elite or u.boss]))


def test_solo_learns_skills_into_d_and_f():
    _, run = solo_run()
    h = run.heroes[0]
    for _ in range(8):
        run.gain_xp(h, run.xp_next(h))
    assert h.level >= 7 and run.slots_open(h) == 5
    cards = run.pick_cards(h)
    assert cards and cards[0]["type"] == "learn"
    while h.sp > 0 and run.take_card(h, 0):
        pass
    ult = X.story_meta.ult_of(ED, h.cls)
    regular = [s for s in h.skills if s != ult]
    assert len(regular) == 5 and h.skills[3] == ult                       # Q W E, R — ультимейт, D, F
    again = X.fix_kit(ED, X.Hero(h.to_dict()))
    assert again.skills == h.skills                                       # перезагрузка не ломает шесть слотов


def test_solo_battle_keeps_hero_selected_and_camera_follows():
    from game.battle_scene import BattleScene
    _, run = solo_run()
    nid = run.available()[0]
    run.enter(nid)
    sc = BattleScene(run.data, run.nodes[nid]["encounter"], squad=run.combat_squad(), enemy_scale=run.enemy_scale(),
                     simple=True, solo=True, on_finish=lambda c, f: None)
    hero = sc.hero
    assert sc.phase == "battle" and sc.selected is hero                  # расстановки нет — сразу бой
    foe = sc.combat.alive(ENEMY)[0]
    sc._select(foe)
    sc._key(pygame.K_ESCAPE)
    sc.update(1 / 30)
    assert sc.selected is hero and sc.selected_units == [hero]
    v = sc.view
    v.gl_camera = True                                                   # камера (как в OpenGL)
    sc.paused = False
    for _ in range(20):
        sc.update(1 / 30)
    scr = v.vfx.screen
    assert abs(scr.zoom - v.follow_zoom) < 0.05
    hx, hy = v.cam(v.feet_pos(hero))
    ax, ay = v.follow_anchor()
    assert abs(hx - ax) < 40 and abs(hy - ay) < 40                       # герой — в центре кадра
    p = (300.0, 200.0)
    back = v.uncam(v.cam(p))
    assert abs(back[0] - p[0]) < 1e-6 and abs(back[1] - p[1]) < 1e-6    # клики попадают туда же
    z = v.follow_zoom
    sc.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1))
    assert v.follow_zoom > z


def test_battle_stats_count_damage_heals_and_kills():
    _, run = solo_run(cls="priest")
    nid = run.available()[0]
    run.enter(nid)
    c = Combat(run.data, run.nodes[nid]["encounter"], squad=run.combat_squad(), enemy_scale=run.enemy_scale(),
               ai_teams=(ENEMY, PLAYER))
    while not c.result and c.time < 150:
        c.step()
    st = c.battle_stats()
    row = st["rows"][0]
    assert row["dealt"] > 0 and row["taken"] >= 0 and st["foes"] >= st["killed"]
    assert sum(r["kills"] for r in st["rows"]) <= st["killed"]
    if c.result == "victory":
        assert row["kills"] >= 1
    out = run.finish_battle(c)
    assert out["stats"]["rows"][0]["name"] == row["name"]


def test_main_launcher_offers_only_new_modes(tmp_path):
    from game.app import App, last_mode, remember_mode
    from game.title_scene import TitleScene
    base = str(tmp_path / "profile.json")
    assert last_mode(base) == "expedition"
    remember_mode("solo", base)
    assert last_mode(base) == "solo"
    prof = X.ExpeditionProfile(ED, None)
    app = App(ED, None, False, prof, start="title", launcher="main")
    keys = [k for _, k, _ in app.scene.buttons]
    assert isinstance(app.scene, TitleScene) and keys[0] == "continue"
    assert not {"solo", "expedition", "story", "mode"} & set(keys)  # один сейв: отряд или одиночка — в таверне
    app._base_path = base
    app.switch_mode("solo")
    assert app.profile.mode == "solo" and app.profile.solo and last_mode(base) == "solo"
