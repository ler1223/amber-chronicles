"""Бесконечный забег: обычный отряд, у каждого героя одна способность, акты не кончаются."""
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_expedition import ED, X  # noqa: E402
from sim.combat import ENEMY, PLAYER, Combat  # noqa: E402
from sim import story_meta  # noqa: E402


def endless_run(seed=2, cls=None):
    prof = X.ExpeditionProfile(ED, solo=True)
    picked = list(prof.roster[:2])
    if cls is not None:
        h = next((x for x in prof.roster if x.cls == cls), None)
        if h is not None:
            picked = [h] + [x for x in prof.roster if x.uid != h.uid][:1]
    return prof, prof.start([h.uid for h in picked], seed=seed)


def battle_node(run):
    n = next(n for n in run.nodes.values() if n["type"] == "battle")
    run.node = n["id"]
    return n


def test_endless_profile_takes_team_and_one_skill():
    prof = X.ExpeditionProfile(ED, solo=True)
    assert prof.mode == "solo" and prof.solo
    assert prof.squad_cfg("swamp")["squad_start"] == 2
    try:
        prof.start([prof.roster[0].uid], seed=1)
        assert False, "в бесконечный забег берут обычный отряд"
    except ValueError:
        pass
    run = prof.start([h.uid for h in prof.roster[:2]], seed=1)
    assert run.endless and not run.solo and len(run.heroes) == 2
    assert run.cfg["squad_max"] == 2
    for h in run.heroes:
        assert h.endless_skill
        assert run.battle_skills(h) == [h.endless_skill]
    back = X.Expedition.from_dict(ED, run.to_dict())
    assert back.endless and not back.solo and len(back.heroes) == 2
    assert all(len(back.battle_skills(h)) == 1 for h in back.heroes)


def test_endless_uses_normal_team_stats_and_enemy_count():
    _, run = endless_run()
    h = run.heroes[0]
    normal = X.Expedition(ED, [X.Hero(dict(h.to_dict()))], seed=2)
    assert run.max_hp(h) == normal.max_hp(normal.heroes[0])
    battle_node(run)
    scale = run.enemy_scale()
    assert "solo" not in scale


def test_endless_acts_grow_and_do_not_end_on_boss():
    _, run = endless_run()
    battle_node(run)
    hp0 = run.enemy_scale()["hp"]
    run.act = 2
    hp2 = run.enemy_scale()["hp"]
    run.act = 3
    hp3 = run.enemy_scale()["hp"]
    assert hp3 > hp2 > hp0
    assert run.act_def["name"] and run.reward_offers("battle")
    assert run.price_k() > 1.0

    # Босс третьего акта в бесконечном режиме не завершает поход.
    run.act = 2
    run.new_map()
    boss = next(n for n in run.nodes.values() if n["type"] == "boss")
    run.node = boss["id"]
    boss["encounter"] = run.boss_encounter()
    c = Combat(run.data, boss["encounter"], squad=run.combat_squad(), enemy_scale=run.enemy_scale())
    c.result = "victory"
    out = run.finish_battle(c)
    assert out["act_done"] == 2 and run.result is None
    run.next_act()
    assert run.act == 3 and run.act_def is not None


def test_endless_one_skill_can_be_any_kit_skill():
    _, run = endless_run()
    h = run.heroes[0]
    choices = story_meta.one_skill_choices(run.data, h.cls, h.level, h)
    assert len(choices) >= 2
    non_ult = next(s for s in choices if not story_meta.is_ult(run.data, h.cls, s))
    h.endless_skill = non_ult
    assert run.battle_skills(h) == [non_ult]
    h.level = 10
    ults = [s for s in story_meta.one_skill_choices(run.data, h.cls, h.level, h)
            if story_meta.is_ult(run.data, h.cls, s)]
    if ults:
        h.endless_skill = ults[0]
        assert run.battle_skills(h) == [ults[0]]


def test_endless_elites_grow_with_act_and_get_modifiers():
    _, run = endless_run()
    n = battle_node(run)
    s0 = run.enemy_scale()
    assert s0["endless"]["elite_count"] == 1
    c = Combat(run.data, n["encounter"], squad=run.combat_squad(), enemy_scale=s0)
    elites = [u for u in c.fighters(ENEMY) if u.elite and not u.boss]
    assert elites and all(u.mutator for u in elites)
    assert {"frostburst", "stormcaller", "juggernaut", "vampiric", "swift", "thorns"} <= set(run.data.mutators)
    run.act = 4
    s4 = run.enemy_scale()
    assert s4["endless"]["elite_count"] > s0["endless"]["elite_count"]
    assert run.endless_growth("hp") > 1 + 2 * 0.24      # уже не линейный рост


def test_endless_run_can_end_after_boss():
    prof, run = endless_run()
    run.result = "ended"
    end = prof.finish(run)
    assert end["result"] == "ended" and end["endless"]
    assert end["act"] >= 0


def test_items_scale_past_three_and_shop_can_reroll():
    _, run = endless_run()
    assert X.tier_k(run.xd, 4) > X.tier_k(run.xd, 3)
    assert X.tier_k(run.xd, 10) > X.tier_k(run.xd, 4)
    item = X.make_item(run.xd, random.Random(1), 4, "rare")
    assert " IV" in X.item_name(item)
    old = {"tier": 3, "name": "Тест", "rarity": "rare"}
    run.act = 4
    assert run.upgrade_cap() == 5 and run.upgrade_item(old) and old["tier"] == 4

    node = next(iter(run.nodes.values()))
    node["stock"] = run.shop_stock()
    run.gold = 9999
    before = run.gold
    cost = run.shop_reroll_cost()
    assert cost > 0 and run.reroll_shop(node["id"])
    assert run.gold == before - cost and len(node["stock"]) == run.cfg["shop"]["items"]

    it = run.xd["items"]
    assert {"warded", "duelist", "focused", "thorned", "savage",
            "archmage", "colossus", "lucky", "bloodthirst"} <= set(it["stat_affixes"])
    assert {"frost_nova", "thunder_chain", "blood_nova", "quake", "siphon"} <= set(it["effects"])
    mods, extra, rules = X.item_effects(run.xd, {
        "uid": 1, "base": "blade", "slot": "weapon", "tier": 4, "rarity": "rare",
        "name": "Тест", "unique": None, "affixes": [{"kind": "stat", "id": "warded"}],
    })
    assert mods


def test_battle_stats_count_damage_heals_and_kills():
    _, run = endless_run(cls="priest")
    nid = run.available()[0]
    run.enter(nid)
    c = Combat(run.data, run.nodes[nid]["encounter"], squad=run.combat_squad(), enemy_scale=run.enemy_scale(),
               ai_teams=(ENEMY, PLAYER))
    while not c.result and c.time < 150:
        c.step()
    st = c.battle_stats()
    assert st["rows"] and st["foes"] >= st["killed"]
    out = run.finish_battle(c)
    assert out["stats"]["rows"][0]["name"] == st["rows"][0]["name"]


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
    assert not {"solo", "expedition", "story", "mode"} & set(keys)  # один сейв: отряд или забег — в таверне
    app._base_path = base
    app.switch_mode("solo")
    assert app.profile.mode == "solo" and app.profile.solo and last_mode(base) == "solo"
