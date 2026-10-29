"""Мета: карта биома, захват регионов, янтарь, сохранение профиля."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from sim.combat import ENEMY, PLAYER, Combat  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim import meta  # noqa: E402
from sim.profile import Profile  # noqa: E402
from sim.run import Run  # noqa: E402

DATA = GameData()


def win_run(run):
    """Пройти вылазку: бои выигрываются мгновенно, отдых/торговец пропускаются."""
    while not run.result:
        nid = run.available()[0]
        node = run.enter(nid)
        if node["encounter"] is None:
            continue
        c = Combat(DATA, node["encounter"], squad=run.combat_squad(), enemy_scale=run.enemy_scale())
        c.win_now()
        assert c.result == "victory"
        run.finish_battle(c)
    return run


def test_region_run_is_short_and_ends_with_guard():
    prof = Profile(DATA)
    assert set(prof.available()) == {"reeds", "mill"}
    run = prof.start_run("reeds", seed=3)
    finals = [n for n in run.nodes.values() if not n["next"]]
    assert len(finals) == 1 and finals[0]["type"] == "guard"
    assert DATA.encounters[finals[0]["encounter"]]["id"] == "reeds_guard"
    assert max(n["layer"] for n in run.nodes.values()) == len(prof.region("reeds")["layers"]) - 1
    win_run(run)
    assert run.result == "victory"


def test_capture_unlocks_neighbours_bonus_and_boss():
    prof = Profile(DATA)
    assert prof.lock_reason("nest") and prof.lock_reason("tower")
    s = prof.finish_run(win_run(prof.start_run("reeds", 1)))
    assert s["captured"] and s["amber"] > 0 and prof.amber == s["amber"]
    assert "nest" in prof.available() and "camp" not in prof.available()
    run = prof.start_run("mill", 2)
    assert run.gold == DATA.config["run"]["start_gold"] + 20      # бонус «Деревня»
    prof.finish_run(win_run(run))
    assert prof.lock_reason("tower")
    prof.finish_run(win_run(prof.start_run("camp", 3)))
    assert prof.lock_reason("tower") is None
    boss = prof.finish_run(win_run(prof.start_run("tower", 4)))
    assert boss["biome_done"] and prof.biome_done


def test_replay_and_defeat_give_less_amber():
    prof = Profile(DATA)
    first = prof.finish_run(win_run(prof.start_run("reeds", 1)))["amber"]
    again = prof.finish_run(win_run(prof.start_run("reeds", 1)))
    assert not again["captured"] and again["amber"] < first
    run = prof.start_run("mill", 5)
    run.battles_won, run.result, run.region_id = 2, "defeat", "mill"
    lost = prof.finish_run(run)
    assert not lost["captured"] and "mill" not in prof.captured
    assert lost["amber"] == round(2 * DATA.config["meta"]["amber_per_battle"] * DATA.config["meta"]["defeat_keep"])


def test_threat_scales_enemies_and_bonuses_apply():
    prof = Profile(DATA)
    prof.captured = ["reeds", "mill", "nest", "camp", "court"]
    run = prof.start_run("court", 1)
    base = Combat(DATA, 0)
    scaled = Combat(DATA, 0, enemy_scale=run.enemy_scale())
    assert scaled.alive(ENEMY)[0].max_hp > base.alive(ENEMY)[0].max_hp
    war = run.squad[0]
    assert run.max_hp(war) == round(DATA.classes["warrior"]["hp"] * 1.1)
    assert run.bonus["scout_hp"] and run.bonus["shop_items"] == 1


def test_profile_saves_and_loads(tmp_path):
    path = str(tmp_path / "save" / "profile.json")
    prof = Profile(DATA, path)
    prof.finish_run(win_run(prof.start_run("reeds", 1)))
    again = Profile(DATA, path)
    assert again.captured == ["reeds"] and again.amber == prof.amber and again.expeditions == 1


def test_world_scene_draw_and_start():
    from game.app import App
    from game.run_scenes import MapScene
    from game.world_scene import WorldScene
    from ui import theme as T
    pygame.init()
    screen = pygame.display.set_mode((T.SCREEN_W, T.SCREEN_H))
    app = App(DATA, 7, start="world")
    s = app.scene
    assert isinstance(s, WorldScene)
    s.draw(screen)
    # заблокированный регион выбирается, но вылазка не начинается
    s.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=s.pos["tower"], button=1))
    s.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=s.pos["tower"], button=1))
    s.draw(screen)
    assert app.scene is s and s.selected == "tower"
    s.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=s.pos["mill"], button=1))
    s.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=s.pos["mill"], button=1))
    assert isinstance(app.scene, MapScene) and app.run.region["id"] == "mill"
    app.scene.draw(screen)


def test_mastery_points_and_build_rules():
    from sim import meta
    prof = Profile(DATA)
    war = prof.heroes["warrior"]
    assert meta.points_total(DATA, war) == 2 and prof.mastery("warrior") == 1
    assert meta.click_branch(DATA, war, "power_strike", "A", 2)          # 2 очка
    assert not meta.toggle_talent(DATA, "warrior", war, "w_hardened")   # очков нет
    assert meta.click_branch(DATA, war, "power_strike", "A", 2)          # повторный клик — откат до 1
    assert war["branches"]["power_strike"] == ["A", 1]
    assert meta.toggle_talent(DATA, "warrior", war, "w_shield_wall")
    assert not meta.set_path(DATA, "warrior", war, "berserker")        # путь закрыт до мастерства 3
    war["xp"] = DATA.config["mastery"]["xp_levels"][2]
    assert prof.mastery("warrior") == 3 and meta.set_path(DATA, "warrior", war, "berserker")
    assert "w_shield_wall" not in war["talents"]                        # блока у берсерка нет
    assert meta.click_branch(DATA, war, "whirlwind", "B", 1)
    meta.set_path(DATA, "warrior", war, None)
    assert "whirlwind" not in war["branches"] and "power_strike" in war["branches"]
    run = Run(DATA, 1, heroes=prof.hero_builds())
    assert run.proto(run.squad[0])["skill_defs"]["power_strike"]["branch"] == ("A", 1)


def test_finish_run_gives_mastery_even_on_defeat():
    prof = Profile(DATA)
    run = prof.start_run("reeds", 1)
    run.battles_won, run.result = 2, "defeat"
    s = prof.finish_run(run)
    assert s["mastery_xp"] == 2 * DATA.config["mastery"]["xp_per_battle"] and not s["trophies"]
    assert all(prof.heroes[c]["xp"] == s["mastery_xp"] for c in prof.squad)
    assert all(h["xp"] == 0 for c, h in prof.heroes.items() if c not in prof.squad)
    s = prof.finish_run(win_run(prof.start_run("reeds", 2)))
    assert len(s["trophies"]) == DATA.config["meta"]["trophy_choices"]
    assert all(DATA.items[i]["rarity"] != "common" for i in s["trophies"])


def test_camp_upgrades_and_bonuses():
    prof = Profile(DATA)
    assert not prof.buy_upgrade("treasury")
    prof.amber = 1000
    assert prof.buy_upgrade("treasury") and prof.buy_upgrade("treasury") and prof.buy_upgrade("hardening")
    assert prof.camp_level("treasury") == 2 and prof.amber == 1000 - 30 - 60 - 40
    prof.buy_upgrade("meditation")
    assert prof.camp_cost("meditation") is None and not prof.buy_upgrade("meditation")
    run = prof.start_run("reeds", 1)
    assert run.gold == DATA.config["run"]["start_gold"] + 30
    war = run.proto(run.squad[0])
    assert war["hp"] == round(DATA.classes["warrior"]["hp"] * 1.06) and war["ap_max"] == 7


def test_arsenal_loadout_limits():
    prof = Profile(DATA)
    prof.arsenal = ["storm_staff", "troll_hide", "focus_amulet"]
    assert prof.toggle_loadout("mage", "storm_staff")
    assert not prof.toggle_loadout("warrior", "troll_hide")          # стойка на 1 предмет
    assert not prof.toggle_loadout("warrior", "storm_staff")         # уже у мага
    prof.amber = 100
    prof.buy_upgrade("rack")
    assert prof.toggle_loadout("warrior", "troll_hide")
    run = prof.start_run("reeds", 1)
    assert run.squad[2].items == {"weapon": "storm_staff"} and run.squad[0].items == {"armor": "troll_hide"}
    assert prof.toggle_loadout("mage", "storm_staff") and prof.loadout_count() == 1


def test_profile_v2_roundtrip_and_v1_migration(tmp_path):
    import json
    path = str(tmp_path / "profile.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "biome": "swamp", "captured": ["reeds"], "amber": 70, "expeditions": 3}, f)
    prof = Profile(DATA, path)
    assert prof.captured == ["reeds"] and prof.amber == 70 and prof.heroes["mage"]["xp"] == 0
    prof.heroes["mage"]["xp"] = 200
    prof.heroes["mage"]["path"] = "warlock"
    prof.heroes["mage"]["branches"] = {"curse": ["B", 2], "ghost_skill": ["A", 1]}
    prof.camp = {"rack": 1}
    prof.arsenal = ["storm_staff"]
    prof.save()
    again = Profile(DATA, path)
    assert again.heroes["mage"]["path"] == "warlock" and again.heroes["mage"]["branches"] == {"curse": ["B", 2]}
    assert again.camp == {"rack": 1} and again.arsenal == ["storm_staff"]


def test_meta_screens_draw_and_click():
    from game.app import App
    from game.meta_scenes import CampScene, HeroesScene
    from ui import theme as T
    pygame.init()
    screen = pygame.display.set_mode((T.SCREEN_W, T.SCREEN_H))
    app = App(DATA, 7, start="world")
    app.profile.seen_heroes = list(DATA.classes)            # «Новые союзники» уже показаны
    app.profile.heroes["warrior"]["xp"] = 300
    app.profile.amber = 200
    app.profile.arsenal = ["troll_hide"]
    app.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_h))
    s = app.scene
    assert isinstance(s, HeroesScene)
    s.draw(screen)

    def click(action):
        rect = next(r for r, a, _ in s.hits if a == action)
        s.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rect.center, button=1))
        s.draw(screen)
    click(("path", "berserker"))
    click(("window", "skills"))                            # окна: обзор и путь → способности → таланты
    click(("branch", "whirlwind", "A", 2))
    s.update(0.5)                                          # превью навыка крутится
    s.draw(screen)
    click(("window", "talents"))
    click(("talent", "w_hardened"))
    click(("loadout", "troll_hide"))
    war = app.profile.heroes["warrior"]
    assert war["path"] == "berserker" and war["branches"] == {"whirlwind": ["A", 2]}
    assert war["talents"] == ["w_hardened"] and war["loadout"] == ["troll_hide"]
    s.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_3))
    s.draw(screen)
    s.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    app.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_l))
    s = app.scene
    assert isinstance(s, CampScene)
    s.draw(screen)
    click(("buy", "treasury"))
    assert app.profile.camp_level("treasury") == 1


def test_free_heroes_by_chapter_squad_and_roundtrip(tmp_path):
    path = str(tmp_path / "p.json")
    prof = Profile(DATA, path)
    base = {c for c, v in DATA.classes.items() if not v.get("unlock")}
    assert set(prof.unlocked) == base | {"shaman", "ram"} and len(prof.heroes) == len(DATA.classes)
    assert "cryo" not in prof.unlocked and not prof.unlock_hero("cryo")      # глава 2 ещё закрыта
    amber = prof.amber
    prof._state("swamp", "normal")["done"] = True                             # пройден босс Болота
    prof.sync_heroes()
    assert {"cryo", "geomancer"} <= set(prof.unlocked) and prof.amber == amber   # бесплатно
    ok, _ = prof.toggle_squad("shaman")
    assert not ok                                          # отряд полон
    assert prof.toggle_squad("mage")[0] and prof.toggle_squad("shaman")[0]
    assert [b["cls"] for b in prof.hero_builds()] == ["warrior", "archer", "priest", "shaman"]
    prof.save()
    again = Profile(DATA, path)
    assert again.squad == prof.squad and "cryo" in again.unlocked
    for c in list(again.squad)[1:]:
        again.toggle_squad(c)
    assert not again.toggle_squad(again.squad[0])[0]      # последний остаётся


def test_sandbox_opens_everything(tmp_path):
    prof = Profile(DATA, str(tmp_path / "s.json"), sandbox=True)
    assert set(prof.unlocked) == set(DATA.classes) and prof.amber >= 999999
    assert all(prof.difficulty_unlocked(c, "nightmare") for c in prof.chapters())
    assert prof.set_chapter("citadel", "nightmare") and prof.lock_reason(prof.biome["regions"][-1]["id"]) is None
    assert prof.arsenal == list(DATA.items) and meta.points_free(DATA, prof.heroes["mage"]) > 20
    prof.save()
    again = Profile(DATA, str(tmp_path / "s.json"))
    assert not again.sandbox and again.difficulty == "normal"     # без флага — обычные замки: кошмар закрыт
