"""Сюжетный режим: отдельный профиль, отряд растёт по вылазкам, цепочка боёв, обучение, торговец."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from game.app import App  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim.story import StoryProfile, story_data  # noqa: E402

pygame.init()
SCREEN = pygame.display.set_mode((1280, 800))
DATA = GameData()


def key(app, k):
    app.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode="", mod=0))


def frame(app, dt=1 / 30):
    app.scene.update(dt)
    app.scene.draw(SCREEN)


def play_expedition(app):
    frame(app)
    key(app, pygame.K_RETURN)
    for _ in range(3000):
        name = type(app.scene).__name__
        if name == "StoryHub":
            return
        if name == "DialogScene":
            frame(app)
            key(app, pygame.K_ESCAPE)
        elif name == "BattleScene":
            sc = app.scene
            if sc.phase == "deploy":
                frame(app)
                sc.begin_battle()
            if sc.tutorial:
                sc.tutorial.skip()
            frame(app)
            sc.combat.win_now()
            for _ in range(4):
                frame(app)
            key(app, pygame.K_RETURN)
        elif name in ("BetweenScene",):
            frame(app)
            key(app, pygame.K_SPACE)
        elif name == "ChoiceScene":
            frame(app)
            key(app, pygame.K_1)
        else:
            raise AssertionError(name)
    raise AssertionError("вылазка не закончилась")


def test_story_starts_with_two_and_allies_join_by_expedition(tmp_path):
    app = App(DATA, seed=1)
    app.profile.path = str(tmp_path / "profile.json")
    app.switch_mode("story")
    base_path = app.mode_path("base")
    app.to_hub()
    prof = app.profile
    assert prof.unlocked == ["warrior", "mage"] and prof.squad == ["warrior", "mage"]
    play_expedition(app)
    assert prof.done == ["prologue"] and len(prof.arsenal) == 1 and prof.amber > 0
    assert len(prof.heroes["warrior"]["skill_loadout"]) == 2          # 2 уровень — второй навык
    play_expedition(app)
    assert "priest" in prof.unlocked and "priest" in prof.squad and len(prof.squad) == 3
    assert len(prof.heroes["warrior"]["skill_loadout"]) == 3          # 3 уровень — третий навык
    again = StoryProfile(story_data(DATA), prof.path)            # прогресс сюжета — на диске, в своём файле
    assert again.done == ["prologue", "chapel"] and again.unlocked == ["warrior", "mage", "priest"]
    assert not os.path.exists(base_path)                         # основная игра не тронута


def test_tutorial_waits_for_player_actions(tmp_path):
    app = App(DATA, seed=1)
    app.profile.path = str(tmp_path / "profile.json")
    app.switch_mode("story")
    app.to_hub()
    frame(app)
    key(app, pygame.K_RETURN)
    frame(app)
    key(app, pygame.K_ESCAPE)                                    # вступление пропущено
    sc = app.scene
    t = sc.tutorial
    assert t.step["until"] == "start"
    sc.begin_battle()
    frame(app)
    assert t.step["until"] == "ack" and sc.paused
    key(app, pygame.K_SPACE)
    frame(app)
    assert t.step["until"] == "select:warrior" and sc.selected is None
    for _ in range(30):
        frame(app)
    assert sc.paused and t.step["until"] == "select:warrior"     # ждёт игрока, бой стоит
    war = next(u for u in sc.combat.units if u.proto_id == "warrior")
    sc._select(war)
    frame(app)
    assert t.step["until"] == "order"


def test_story_continues_to_nine_chapters(tmp_path):
    prof = StoryProfile(story_data(DATA), str(tmp_path / "story.json"))
    chapters = prof.story["chapters"]
    assert [c["id"] for c in chapters] == [
        "swamp", "forge", "crypt", "pass", "steppe", "tomb", "fae", "sunken", "citadel"]
    exps = prof.expeditions_list()
    assert len(exps) == 28
    assert all(not e.get("join") for e in exps[7:])          # новые герои — только в первых двух главах
    known = {e["id"] for e in prof.data.encounters}
    for exp in exps:
        for b in exp["battles"]:
            assert b["encounter"] in known
        for line in exp.get("intro", []) + exp.get("outro", []):
            assert line["who"] in prof.story["characters"]
    last = exps[-1]
    assert last["battles"][-1]["encounter"] == "citadel_9"
    assert next(e for e in prof.data.encounters if e["id"] == "citadel_9")["kind"] == "boss"

    prof.done = [e["id"] for e in exps[:7]]
    run = prof.start_chain(1)
    assert run.region_id == "crypt_gate" and run.enemy_scale()["level"] == 7
    assert len(run.nodes) == 3


def test_shop_buys_into_arsenal(tmp_path):
    prof = StoryProfile(story_data(DATA), str(tmp_path / "story.json"))
    prof.amber = 500
    iid, it = prof.shop_stock()[0]
    assert prof.buy(iid) and iid in prof.arsenal and prof.amber == 500 - it.get("price", 50)
    assert iid not in [i for i, _ in prof.shop_stock()]


def test_battle_places_six_heroes_on_four_spawns():
    from sim.build import build_proto
    from sim.combat import PLAYER, Combat
    squad = [{"cls": c, "proto": build_proto(DATA, c)} for c in
             ("warrior", "mage", "priest", "archer", "guardian", "cryo")]
    c = Combat(DATA, 0, squad=squad)                             # «bog»: 4 точки высадки
    heroes = [u for u in c.units if u.team == PLAYER]
    assert len(heroes) == 6 and len({u.cell for u in heroes}) == 6


def test_story_uses_hero_levels_and_weak_slimes(tmp_path):
    from sim.combat import ENEMY, Combat
    prof = StoryProfile(story_data(DATA), str(tmp_path / "story.json"))
    run = prof.start_chain(1)
    assert run.stats and run.enemy_scale()["level"] == 1 and not run.enemy_scale()["titles"]
    node = run.enter(0)
    c = Combat(prof.data, node["encounter"], squad=run.combat_squad(), enemy_scale=run.enemy_scale())
    plain = Combat(prof.data, node["encounter"], squad=run.combat_squad(), enemy_scale={"level": 1, "stats": True, "titles": False})
    slime = next(u for u in c.units if u.team == ENEMY and u.proto_id == "slime")
    base = next(u for u in plain.units if u.team == ENEMY and u.proto_id == "slime")
    assert slime.max_hp == round(base.max_hp * 0.5) and slime.atk_damage < base.atk_damage
    prof.heroes["warrior"]["rpg"]["level"] = 4                   # уровень героя — навсегда, и новичок его догоняет
    prof.heroes["mage"]["rpg"]["level"] = 4
    prof.done.append("prologue")
    prof.start_chain(2)
    assert prof.level("priest") == 4


def test_story_chain_reports_xp_and_level_ups(tmp_path):
    from sim import stats
    prof = StoryProfile(story_data(DATA), str(tmp_path / "story.json"))
    run = prof.start_chain(1)
    for m in run.squad:
        stats.add_xp(prof.data, m.rpg, 10_000)
        m.level = m.rpg["level"]
    run.result = "victory"
    run.battles_won = 1
    run.story_xp = 140
    end = prof.finish_chain(run)
    assert end["hero_xp"] == 140
    assert {c for c, _, _ in end["level_ups"]} == {m.cls for m in run.squad}
    assert all(old < new for _, old, new in end["level_ups"])
    assert all(len(prof.heroes[m.cls]["skill_loadout"]) == 3 for m in run.squad)   # новые навыки заняли слоты


def test_hero_window_help_opens_once_in_story(tmp_path):
    from game.meta_scenes import HeroesScene
    app = App(DATA, seed=1)
    app.profile.path = str(tmp_path / "profile.json")
    app.switch_mode("story")
    sc = HeroesScene(app)
    assert sc.help and sc.help.open and sc.window == "overview"
    seen = set()
    for _ in range(10):
        sc.draw(SCREEN)
        seen.add(sc.window)
        if not sc.help.open:
            break
        sc.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, unicode=" ", mod=0))
    assert not sc.help.open and {"overview", "skills", "talents", "stats"} <= seen
    assert app.profile.help_seen and HeroesScene(app).help is None          # второй раз — только по кнопке


def test_story_skill_pool_and_loadout_grow_with_hero_level(tmp_path):
    from sim import story_meta
    from sim.run import Run

    prof = StoryProfile(story_data(DATA), str(tmp_path / "story.json"))
    hero = prof.heroes["warrior"]
    assert story_meta.slots(prof.data) == 3
    assert hero["skill_loadout"] == ["power_strike"]            # на 1 уровне ровно один навык

    for lvl, count in ((1, 1), (2, 2), (3, 3), (5, 4), (7, 5)):
        assert len(story_meta.unlocked_skills(prof.data, "warrior", lvl)) == count

    hero["rpg"]["level"] = 2
    story_meta.auto_fill(prof.data, "warrior", hero)
    assert hero["skill_loadout"] == ["power_strike", "taunt"]
    hero["rpg"]["level"] = 3
    story_meta.auto_fill(prof.data, "warrior", hero)
    assert hero["skill_loadout"] == ["power_strike", "taunt", "guard_ally"]

    hero["rpg"]["level"] = 5
    story_meta.auto_fill(prof.data, "warrior", hero)
    assert hero["skill_loadout"] == ["power_strike", "taunt", "guard_ally"]   # слоты заняты
    assert story_meta.equip(prof.data, "warrior", hero, "whirlwind", 2)
    assert hero["skill_loadout"] == ["power_strike", "taunt", "whirlwind"]

    build = prof.hero_builds()[prof.squad.index("warrior")]
    run = Run(prof.data, 0, None, {}, [build], mode="story")
    proto = run.proto(run.squad[0])
    assert proto["skills"] == ["power_strike", "taunt", "whirlwind"]
    assert "whirlwind" in proto["skill_defs"]

    hero["rpg"]["level"] = 3
    assert not story_meta.set_doctrine(prof.data, "warrior", hero, "berserker")
    hero["rpg"]["level"] = 4
    assert story_meta.set_doctrine(prof.data, "warrior", hero, "berserker")
    assert hero["doctrine"] == "berserker"
    assert hero["skill_loadout"] == ["power_strike", "taunt", "whirlwind"]
    build = prof.hero_builds()[prof.squad.index("warrior")]
    run = Run(prof.data, 0, None, {}, [build], mode="story")
    proto = run.proto(run.squad[0])
    assert proto["passive"]["name"] == prof.data.paths["berserker"]["passive"]["name"]
    assert proto["skills"] == ["power_strike", "taunt", "whirlwind"]


def test_story_slot_count_is_data_driven(tmp_path):
    from sim import story_meta
    from sim.run import Run

    old = DATA.story_progression["slots"]
    DATA.story_progression["slots"] = 5
    try:
        prof = StoryProfile(story_data(DATA), str(tmp_path / "story.json"))
        hero = prof.heroes["warrior"]
        hero["rpg"]["level"] = 7
        story_meta.auto_fill(prof.data, "warrior", hero)
        assert len(hero["skill_loadout"]) == 5
        build = prof.hero_builds()[prof.squad.index("warrior")]
        run = Run(prof.data, 0, None, {}, [build], mode="story")
        assert len(run.proto(run.squad[0])["skills"]) == 5
    finally:
        DATA.story_progression["slots"] = old


def test_story_hero_scene_edits_loadout_and_doctrine(tmp_path):
    from game.meta_scenes import HeroesScene
    from sim import story_meta

    app = App(DATA, seed=1)
    app.profile.path = str(tmp_path / "profile.json")
    app.switch_mode("story")
    sc = HeroesScene(app, window="skills")
    sc.help = None
    sc.set_window("skills")
    hero = app.profile.heroes["warrior"]
    sc.cls = "warrior"
    sc.slot_sel = 0
    sc.act(("pool", "taunt"))                                  # ещё закрыт на 1 уровне
    assert hero["skill_loadout"] == ["power_strike"]
    hero["rpg"]["level"] = 5
    story_meta.auto_fill(app.data, "warrior", hero)
    sc.slot_sel = 2
    sc.act(("pool", "whirlwind"))
    assert hero["skill_loadout"] == ["power_strike", "taunt", "whirlwind"]
    sc.act(("unequip", 2))
    assert hero["skill_loadout"] == ["power_strike", "taunt"]
    sc.act(("doctrine", "berserker"))
    assert hero["doctrine"] == "berserker"
    sc.update(1 / 30)
    sc.draw(SCREEN)


def test_story_tutorial_uses_skills_available_at_level_one():
    prof = StoryProfile(story_data(DATA), None)
    prologue = next(e for e in prof.expeditions_list() if e["id"] == "prologue")
    frogs = next(b for b in prologue["battles"] if b["encounter"] == "st_frogs")
    assert frogs["tutorial"][0]["until"] == "skill:power_strike"
