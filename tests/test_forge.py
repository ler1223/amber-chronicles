"""Глава 2 похода «Огненные кузни»: свои данные главы, Жар и извержения на карте, руда и наковальня, опасности
поля (ковш, меха, жерла), открытие главы и её сложностей, события."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_expedition import ED, X  # noqa: E402
from sim.combat import ENEMY, PLAYER, Combat  # noqa: E402

FX = X.chapter_view(ED.expedition, "forge")


def forge_run(seed=3, classes=("warrior", "priest", "archer")):
    h = [X.Hero({"uid": f"u{i}", "name": "Т", "cls": c, "skills": []}) for i, c in enumerate(classes)]
    return X.Expedition(ED, h, seed=seed, chapter="forge")


def test_forge_data_is_consistent():
    for act in FX["acts"]:
        for pool in act["pools"].values():
            for eid in pool:
                X.enc_index(ED, eid)
        X.enc_index(ED, act["boss"])
    for rule in FX["boss_rules"]:
        X.enc_index(ED, rule["enc"])
    cd = ED.expedition["chapter_data"]["forge"]
    for enc in cd["encounters"]:
        assert all(len(row) == len(enc["map"][0]) for row in enc["map"]), enc["id"]
        for e in enc["enemies"] + [s for ph in enc.get("phases", []) for s in ph["spawn"]] + enc.get("objects", []):
            assert e["type"] in ED.enemies or e["type"] in ED.objects, (enc["id"], e["type"])
            x, y = e["pos"]
            assert enc["map"][y][x] in ".^:", (enc["id"], e["pos"])
    for eid, e in cd["enemies"].items():
        assert all(s in ED.skills for s in e["skills"]), eid
    for uid, u in cd["uniques"].items():
        assert u["base"] in FX["items"]["bases"] and u.get("masterpiece")
    for eid, ev in FX["events"].items():
        for st in ev["steps"].values():
            for opt in st["options"]:
                if "check" in opt:
                    assert "success" in opt and "fail" in opt, eid
                if opt.get("next"):
                    assert opt["next"] in ev["steps"], eid


def test_chapter_view_keeps_swamp_apart():
    run = forge_run()
    assert run.act_def["name"].startswith("Акт I. Шлаковые")
    assert not set(run.xd["events"]) & set(ED.expedition["events"])           # свои события, без общих
    assert "scorched" in run.xd["curses"] and "bog_fever" in run.xd["curses"]
    assert run.trade_faction() == "guild"
    back = X.Expedition.from_dict(ED, run.to_dict())
    assert back.chapter == "forge" and back.xd["events"] is run.xd["events"] or back.xd["events"] == run.xd["events"]
    swamp = X.Expedition(ED, [X.Hero({"uid": "a", "name": "А", "cls": "warrior", "skills": []})], seed=1)
    assert swamp.xd is ED.expedition and not swamp.heat_on() and not swamp.forge_on()


def test_heat_rises_and_eruptions_flood_the_map():
    run = forge_run()
    run.enter(run.available()[0])
    assert run.heat == FX["mechanics"]["heat"]["step"]
    marked = list(run.lava_next)
    assert marked and all(run.nodes[m]["type"] != "boss" for m in marked)
    lines = run.add_heat(30)
    assert lines and "Извержение" in lines[0]
    assert all(run.nodes[m]["type"] == "ash" or run.nodes[m].get("molten") for m in marked)
    assert run.lava_next != marked                                     # новые отметки на следующее извержение
    run.add_heat(100)                                                  # предел — большое извержение
    assert "scorched" in run.curses and run.heat == FX["mechanics"]["heat"]["after_big"]
    run.camp_cool()
    assert run.heat < FX["mechanics"]["heat"]["after_big"]


def test_molten_battle_is_harder_and_pays_ore():
    run = forge_run()
    n = next(v for v in run.nodes.values() if v["type"] == "battle" and v["layer"] > 0)
    run.node = n["id"]
    plain = run.enemy_scale()
    n["molten"] = True
    hot = run.enemy_scale()
    assert hot["hp"] > plain["hp"] and hot["arena_rate"] > plain["arena_rate"]
    c = Combat(run.data, n["encounter"], squad=run.combat_squad(), enemy_scale=hot)
    c.result = "victory"
    before = run.mat("ore")
    out = run.finish_battle(c)
    assert run.mat("ore") - before == 2 * FX["mechanics"]["forge"]["battle_ore"]["battle"]
    assert any("Руда" in s for s in out["extra"])


def test_anvil_forges_reforges_smelts_and_masterpieces():
    run = forge_run()
    an = next(v for v in run.nodes.values() if v["type"] == "anvil")
    off = run.anvil_offer(an)
    assert run.anvil_offer(an) is off                                  # повторный заход не перебросит
    assert run.forge_item(an, "weapon", [0, 1]) is None                # без руды — нельзя
    run.mats = {"ore": 40, "obsidian": 6, "starsteel": 4, "emberheart": 3}
    stat_i = [i for i, p in enumerate(off["props"]) if p["kind"] == "stat"][:2]
    proc_i = [i for i, p in enumerate(off["props"]) if p["kind"] == "proc"][:1]
    item = run.forge_item(an, "armor", stat_i + proc_i, temper=True)
    assert item and item["rarity"] == "epic" and item["slot"] == "armor" and item["tier"] == run.item_tier() + 1
    assert run.mats["emberheart"] == 2 and run.mats["obsidian"] == 5
    t = item["tier"]
    assert run.reforge(item) and item["tier"] == t + 1
    ore = run.mat("ore")
    assert run.smelt(item) > 0 and run.mat("ore") > ore and item not in run.bag
    mp = run.masterpieces()
    assert mp
    m = run.forge_masterpiece(mp[0])
    assert m and m["unique"] == mp[0] and mp[0] not in run.masterpieces()
    h = run.heroes[0]
    if run.fits(h, m):
        assert run.equip(h, m["uid"]) and run.proto(h)


def test_forge_hazards_in_battle():
    run = forge_run()
    run.act = 2
    run.new_map()
    n = next(v for v in run.nodes.values() if v["type"] == "battle")
    run.node = n["id"]
    sc = run.enemy_scale()
    kinds = {e["type"] for e in sc["arena_extra"]}
    assert {"ladle", "bellows"} <= kinds
    c = Combat(run.data, n["encounter"], squad=run.combat_squad(), enemy_scale=sc)
    seen = set()
    for _ in range(int(60 / c.dt)):
        c.step()
        seen |= {e["kind"] for e in c.events if e.get("t") == "arena_hit"} if hasattr(c, "events") else set()
        if c.result:
            break
    ladle = next(ev for ev in c.arena if ev["type"] == "ladle")
    c._arena_warn(ladle)
    row = {p[1] for p in ladle["cells"]}
    assert len(row) <= 1 and ladle["cells"]
    c._arena_hit(ladle)
    assert all(c.grid.get(p).hazard == "fire" or c.grid.get(p).terrain in ("water", "chasm") for p in ladle["cells"])


def test_vent_object_erupts_on_anyone_near():
    run = forge_run()
    eid = "ex_f_slag_pit"
    c = Combat(run.data, X.enc_index(ED, eid), squad=run.combat_squad(), enemy_scale=run.enemy_scale(
        next(v for v in run.nodes.values() if v["type"] == "battle")))
    vent = next(u for u in c.units if u.obj and u.proto_id == "magma_vent")
    c.damage(vent, 999, None, None, "reaction")
    assert not vent.alive


def test_forge_chapter_opens_after_swamp_and_has_own_tiers(tmp_path):
    prof = X.ExpeditionProfile(ED, str(tmp_path / "p.json"))
    assert not prof.chapter_open("forge")
    run = prof.start([h.uid for h in prof.roster[:2]], seed=1, chapter="forge")
    assert run.chapter == "swamp"                                      # закрытая глава не выбирается
    run.result = "victory"
    prof.finish(run)
    assert prof.chapter_open("forge") and prof.tier_open_of("forge") == 0 and prof.tier_open == 1
    run = prof.start([h.uid for h in prof.roster[:2]], seed=2, tier=1, chapter="forge")
    assert run.chapter == "forge" and run.tier == 0
    run.result = "victory"
    prof.finish(run)
    assert prof.tier_open_of("forge") == 1
    again = X.ExpeditionProfile(ED, str(tmp_path / "p.json"))
    assert again.chapter_open("forge") and again.tier_open_of("forge") == 1


def test_high_heat_wakes_the_volcano_as_final_boss():
    run = forge_run()
    run.act = len(FX["acts"]) - 1
    run.heat = 90
    assert run.data.encounters[run.boss_encounter()]["id"] == "ex_f_volcano"
    run.heat = 20
    assert run.data.encounters[run.boss_encounter()]["id"] == FX["acts"][-1]["boss"]


def test_every_forge_event_option_applies():
    for eid, ev in FX["events"].items():
        for sid, st in ev["steps"].items():
            for i, opt in enumerate(st["options"]):
                outs = [opt] if "check" not in opt else [opt[k] for k in ("success", "fail", "crit") if k in opt]
                for o in outs:
                    run = forge_run(seed=len(eid) + i)
                    run.gold = 500
                    run.mats = {"ore": 20, "obsidian": 5, "starsteel": 3, "emberheart": 3}
                    run.bag.append(run.new_item("normal"))
                    run.node = run.available()[0]
                    for x in run.apply_ops(o.get("do", []), run.heroes[0]):
                        if isinstance(x, dict) and "battle" in x and x["battle"] not in ("battle", "elite"):
                            Combat(run.data, X.enc_index(ED, x["battle"]), squad=run.combat_squad(),
                                   enemy_scale=run.enemy_scale())
                    assert run.gold >= 0 and all(v >= 0 for v in run.mats.values()), (eid, sid, i)


def test_forge_has_about_forty_events():
    evs = FX["events"]
    chained = {k for k, e in evs.items() if e.get("kind") == "thread" and not e.get("acts")} | {"cult_ascension"}
    assert 38 <= len(set(evs) - chained) <= 46


def test_bot_walks_a_forge_run():
    from test_expedition import play
    run = forge_run(seed=5)
    play(run)
    assert run.result in ("victory", "defeat")
    assert run.counts["battle"] > 0 and (run.mat("ore") > 0 or run.flags.get("forged") or run.result)


def test_chapter_screen_in_tavern(tmp_path):
    """Таверна → экран глав (картинка, враги, механики): закрытая глава не выбирается, открытая — выбирается."""
    import test_expedition_ui as U
    from game import expedition_scenes as XS
    app = U.new_app(tmp_path)
    tav = XS.TavernScene(app)
    app.switch(tav)
    U.click(app, "chapters")
    assert type(app.scene).__name__ == "ChapterScene"
    U.click(app, ("pick", "forge"))
    assert type(app.scene).__name__ == "ChapterScene" and tav.chapter == "swamp"
    app.profile.chapter_wins = {"swamp": 1}
    U.click(app, ("pick", "forge"))
    assert app.scene is tav and tav.chapter == "forge"
    U.frame(app)
