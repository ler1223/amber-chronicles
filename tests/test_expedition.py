"""Экспедиция: таверна, поход из трёх актов, снаряжение из блоков, события с проверками, сохранение."""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.combat import ENEMY, PLAYER, Combat  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim import expedition as X  # noqa: E402
from sim import story_meta  # noqa: E402

DATA = GameData()
ED = X.expedition_data(DATA)
XD = ED.expedition


def new_run(tmp_path=None, seed=3, n=3):
    prof = X.ExpeditionProfile(ED, str(tmp_path / "exp.json") if tmp_path else None)
    run = prof.start([h.uid for h in prof.roster[:n]], seed=seed)
    return prof, run


def test_data_is_consistent():
    """Бои, враги, события и блоки предметов ссылаются на существующее."""
    for act in XD["acts"]:
        for pool in act["pools"].values():
            for eid in pool:
                X.enc_index(ED, eid)
        X.enc_index(ED, act["boss"])
    for enc in XD["encounters"]:
        w = len(enc["map"][0])
        assert all(len(row) == w for row in enc["map"]), enc["id"]
        for e in enc["enemies"] + [s for ph in enc.get("phases", []) for s in ph["spawn"]]:
            assert e["type"] in ED.enemies, (enc["id"], e["type"])
            x, y = e["pos"]
            assert enc["map"][y][x] in ".^:", (enc["id"], e["pos"])
        for x, y in enc["player_spawn"]:
            assert enc["map"][y][x] in ".^:", (enc["id"], (x, y))
    for eid, e in XD["enemies"].items():
        for sid in e["skills"]:
            assert sid in DATA.skills, (eid, sid)
    it = XD["items"]
    for u in it["uniques"].values():
        assert u["base"] in it["bases"]
        for spec in u.get("rules", []):
            assert spec["trigger"] in it["triggers"]
            assert all(d in it["effects"] for d in spec.get("do", []))
    known_ops = {"gold", "heal", "hurt", "xp", "skill_point", "item", "gift", "curse", "remove_curse", "wound",
                 "flag", "recruit", "add_node", "boss", "upgrade_item", "lose_hero", "battle", "rep", "pay",
                 "battle_mod", "boss_mod", "guest", "perk", "chance", "lose_item", "trait", "say", "gold_all"}

    def flat(ops):
        """Действия вместе с вложенными: после боя, ветки случайного исхода."""
        for op in ops or []:
            yield op
            yield from flat(op.get("after"))
            yield from flat(op.get("do"))
            yield from flat(op.get("else"))

    for eid, ev in XD["events"].items():
        for st in ev["steps"].values():
            for opt in st["options"]:
                branches = [opt] + [opt.get(k) for k in ("success", "fail", "crit", "fumble") if opt.get(k)]
                for b in branches:
                    for op in flat(b.get("do", [])):
                        assert set(op) - {"who", "add", "after", "do", "else"} <= known_ops, (eid, op)
                        units = [op["guest"]["unit"]] if "guest" in op else []
                        for m in (op.get("battle_mod"), op.get("boss_mod")):
                            units += (m or {}).get("adds", []) + (m or {}).get("guests", [])
                        assert all(u in ED.enemies for u in units), (eid, op)
                        if "trait" in op and op["trait"] != "random":
                            assert op["trait"] in XD["tavern"]["traits"], (eid, op)
                        if "battle" in op and op["battle"] not in ("battle", "elite"):
                            X.enc_index(ED, op["battle"])
                        if "gift" in op and op["gift"] != "random":
                            assert op["gift"] in XD["gifts"], (eid, op)
                        if "curse" in op and op["curse"] != "random":
                            assert op["curse"] in XD["curses"]
                        if "add_node" in op:
                            assert op["add_node"]["event"] in XD["events"]
                        if "boss" in op:
                            X.enc_index(ED, op["boss"])
                    if b.get("next"):
                        assert b["next"] in ev["steps"], (eid, b["next"])
                if "check" in opt:
                    assert "success" in opt and "fail" in opt, eid


def test_tavern_roster_and_upgrades(tmp_path):
    prof = X.ExpeditionProfile(ED, str(tmp_path / "exp.json"))
    assert len(prof.roster) == 6
    assert {h.cls for h in prof.roster} <= set(XD["tavern"]["start_classes"])
    for h in prof.roster:
        assert len(h.skills) == 4 and len(h.gear) == 1 and h.trait in XD["tavern"]["traits"]
        assert h.skills[3] == story_meta.ult_of(ED, h.cls)                   # ультимейт — четвёртым, на R
        assert story_meta.kit_ok(ED, h.cls, h.skills[:3])                    # набор не ломает механику класса
    prof.glory = 200
    assert prof.buy_upgrade("hall") and len(prof.roster) == 8
    assert prof.buy_upgrade("guests") and "shaman" in prof.classes()
    again = X.ExpeditionProfile(ED, prof.path)
    assert again.level("hall") == 1 and len(again.roster) == 8 and again.glory == prof.glory


def test_hero_power_grows_but_bonuses_add_up():
    _, run = new_run()
    h = run.heroes[0]
    p1 = run.proto(h)
    for _ in range(18):
        run.gain_xp(h, run.xp_next(h))
    run.act = 2
    for slot in X.SLOTS:
        it = run.new_item("boss", slot=slot, rarity="epic")
        run.bag.append(it)
        run.equip(h, it["uid"])
    assert run.give_gift(h, "amber_heart")
    p2 = run.proto(h)
    assert h.level >= 19
    # растёт заметно, но бонусы складываются, а уровень — линейно: без взрыва ×15
    assert p1["attack"]["damage"] * 3 <= p2["attack"]["damage"] <= p1["attack"]["damage"] * 12
    assert p1["hp"] * 2 <= p2["hp"] <= p1["hp"] * 25          # враги 3-го акта к боссу ×30 HP
    from sim.expedition import merge_bonus
    m = merge_bonus([{"stat": "hp", "mult": 1.5}, {"stat": "hp", "mult": 1.4}])
    assert m == [{"stat": "hp", "mult": 1.9}]


def test_item_affixes_become_rules_that_fire_in_combat():
    rng = random.Random(5)
    for _ in range(200):                                   # любые сочетания блоков собираются в правила
        it = X.make_item(XD, rng, rng.randint(1, 3), rng.choice(["common", "rare", "epic", "unique"]), uid="t")
        mods, extra, rules = X.item_effects(XD, it)
        assert X.item_lines(XD, it)
        for r in rules:
            assert r["on"] in ("hit", "crit", "kill", "dodge", "cast", "start")
    _, run = new_run()
    h = run.heroes[0]
    h.gear["ring"] = X.make_item(XD, rng, 1, unique="beetle_seal", uid="u1")
    h.gear["amulet"] = X.make_item(XD, rng, 1, unique="drowned_lamp", uid="u2")
    n = run.enter(run.available()[0])
    c = Combat(ED, n["encounter"], ai_teams=(PLAYER, ENEMY), squad=run.combat_squad(),
               enemy_scale=run.enemy_scale(), difficulty=run.difficulty)
    for _ in range(30 * 60):
        c.step()
        if c.result:
            break
    fired = {rid for rid, _ in c.rules.fired if rid}
    assert any(r.startswith("u2:") for r in fired)           # щит в начале боя
    assert c.result


def test_events_checks_and_threads():
    _, run = new_run()
    h = run.heroes[0]
    chk = {"attr": "str", "dc": 11}
    ch = run.chance(h, chk)
    assert 0.05 <= ch <= 1.0
    r = run.roll(h, chk)
    assert r["result"] in ("crit", "success", "fail", "fumble") and r["total"] == r["d20"] + r["bonus"]
    # нить: след телеги добавляет на карту узел лагеря налётчиков
    run.enter(run.available()[0])
    before = len(run.nodes)
    lines = run.apply_ops([{"flag": "smith_trail"}, {"add_node": {"event": "smith_rescue", "ahead": 2}}], h)
    assert len(run.nodes) == before + 1 and any("тропа" in str(x) for x in lines)
    tn = next(n for n in run.nodes.values() if n["thread"])
    assert tn["event"] == "smith_rescue" and tn["next"]
    # нить ведьмы меняет финального босса третьего акта
    run.flags["witch_broken"] = 1
    run.act = 2
    assert ED.encounters[run.boss_encounter()]["id"] == "ex_witch_wrath"
    run.boss_override = "ex_amber_grotto"
    assert ED.encounters[run.boss_encounter()]["id"] == "ex_amber_grotto"


def test_every_event_option_applies():
    _, run = new_run(n=2)
    run.gold = 500
    run.enter(run.available()[0])
    for eid, ev in XD["events"].items():
        for st in ev["steps"].values():
            for opt in st["options"]:
                outs = [opt] if "check" not in opt else [run.outcome(opt, r) for r in ("crit", "success", "fail")]
                for o in outs:
                    lines = run.apply_ops(o.get("do", []), run.heroes[0])
                    for x in lines:
                        if isinstance(x, dict) and "battle" in x:
                            run.battle_from_event(x["battle"])
                    assert run.heroes


def test_save_and_resume(tmp_path):
    prof, run = new_run(tmp_path)
    nid = run.available()[0]
    run.enter(nid)
    run.bag.append(run.new_item("elite"))
    run.flags["shard"] = 2
    prof.save(run)
    again = X.ExpeditionProfile(ED, prof.path)
    r2 = again.resume()
    assert r2 is not None and r2.node == nid and r2.flags["shard"] == 2
    assert [h.name for h in r2.heroes] == [h.name for h in run.heroes]
    assert r2.proto(r2.heroes[0])["hp"] == run.proto(run.heroes[0])["hp"]
    assert len(r2.bag) == len(run.bag)


def play(run, max_nodes=80):
    """Бот: идёт по карте, бои — ИИ против ИИ, события — первый доступный вариант с лучшим героем."""
    for _ in range(max_nodes):
        if run.result:
            return
        avail = run.available()
        low = min(run.hp_of(h) / run.max_hp(h) for h in run.heroes) < 0.45
        hot = run.heat_on() and run.heat >= 55        # кузня на грани извержения — остудить в лагере
        pref = ["camp", "shop", "anvil", "battle", "event", "elite"] if low or hot else             ["battle", "elite", "event", "anvil", "camp", "shop"]
        nid = min(avail, key=lambda a: pref.index(run.nodes[a]["type"]) if run.nodes[a]["type"] in pref else 9)
        n = run.enter(nid)
        t = n["type"]
        if t == "anvil":                               # наковальня: куёт вещи в пустые слоты, пока хватает руды
            off = run.anvil_offer(n)
            stats_ = [i for i, p in enumerate(off["props"]) if p["kind"] == "stat"]
            for slot in X.SLOTS:
                if any(slot not in h.gear for h in run.heroes) and run.forge_item(n, slot, stats_[:2]) is None:
                    break
            continue
        if t == "ash":
            continue
        if t == "event":
            run.start_event(n["event"])
            ev = run.event(n["event"])
            step = "start"
            fight = None
            while step:
                opts = [o for o in ev["steps"][step]["options"] if run.option_ok(o)]
                opt = opts[0]
                hero = run.heroes[0]
                if "check" in opt:
                    hero = max(run.heroes, key=lambda h: run.chance(h, opt["check"]))
                    o = run.outcome(opt, run.roll(hero, opt["check"])["result"])
                else:
                    o = opt
                for x in run.apply_ops(o.get("do", []), hero):
                    if isinstance(x, dict) and "battle" in x:
                        fight = x["battle"]
                    elif isinstance(x, dict) and "gift" in x:
                        g = x["gift"][0]
                        run.give_gift(next(h for h in run.heroes if run.gift_ok(h, g)), g)
                step = None if fight else o.get("next")
            if fight:
                run.battle_from_event(fight)
                t = "battle"
            else:
                continue
        if t in ("battle", "elite", "boss"):
            for h in run.heroes:
                while h.sp > 0 and run.take_card(h, 0):    # карты улучшения — первая
                    pass
            for it in list(run.bag):
                for h in run.heroes:
                    if it["slot"] not in h.gear:
                        run.equip(h, it["uid"])
                        break
            c = Combat(ED, run.nodes[nid]["encounter"], ai_teams=(PLAYER, ENEMY), squad=run.combat_squad(),
                       enemy_scale=run.enemy_scale(), difficulty=run.difficulty)
            for _ in range(30 * 240):
                c.step()
                if c.result:
                    break
            if not c.result:
                c.result = "defeat"
            s = run.finish_battle(c)
            if s["result"] != "victory":
                return
            kind = run.node_kind(run.nodes[nid])
            offers = run.reward_offers(kind)
            if offers:
                o = offers[0]
                hero = next((x for x in run.heroes if o["type"] != "gift" or run.gift_ok(x, o["id"])), None)
                run.apply_offer(o, hero)
            if kind in ("elite", "boss"):
                run.bag.append(run.bonus_item(kind))
            if s.get("act_done") is not None and not run.result:
                run.next_act()
        elif t == "camp":
            run.camp_cool() if hot and not low else run.camp_rest()
        elif t == "shop":
            run.buy_heal()


def test_bot_plays_first_act():
    _, run = new_run(seed=11)
    play(run)
    assert run.counts["battle"] >= 1
    assert run.result in ("victory", "defeat") or run.act >= 1


def test_gifts_are_personal_and_class_bound():
    _, run = new_run()
    h = run.heroes[0]
    others = run.heroes[1:]
    before = [run.proto(x)["hp"] for x in others]
    assert run.give_gift(h, "amber_blood")
    assert [run.proto(x)["hp"] for x in others] == before          # другим героям ничего
    assert not run.give_gift(h, "amber_blood")                      # дважды нельзя
    mage_gift = "ash_heart"
    for x in run.heroes:
        assert run.gift_ok(x, mage_gift) == (x.cls in XD["gifts"][mage_gift]["classes"])
    offers = run.gift_offers(3)
    assert offers and all(any(run.gift_ok(x, g) for x in run.heroes) for g in offers)
    assert not any(XD["gifts"][g].get("thread") for g in offers)


def test_tag_items_are_rare():
    _, run = new_run()
    run.act = 2
    for _ in range(60):
        run.bag.append(run.new_item("boss"))
    assert run.tag_items() <= XD["config"]["tag_items_max"]
    rng = random.Random(1)
    for _ in range(100):                                            # обычные и редкие теги не вешают
        it = X.make_item(XD, rng, 2, rng.choice(["common", "rare"]), uid="t", allow_tags=True)
        assert not X.has_tags(XD, it)


def test_skill_values_grow_with_level_and_items():
    from sim import stats
    _, run = new_run()
    h = run.heroes[0]
    sid = next(s for s in h.skills if stats.skill_values(run.proto(h), DATA.skills[s]))
    v1 = stats.skill_values(run.proto(h), run.proto(h)["skill_defs"][sid])[0]
    for _ in range(6):
        run.gain_xp(h, run.xp_next(h))
    h.sp += 2
    run.rank_up(h, sid)
    p = run.proto(h)
    v2 = stats.skill_values(p, p["skill_defs"][sid])[0]
    assert v2[1] > v1[1] * 1.5
    if v2[2]:
        assert v2[2] > v2[1]


def test_random_kits_are_whole_for_every_class():
    """Таверна не ломает героев: тысячи случайных наборов — всегда цельные, ультимейт на R."""
    rng = random.Random(5)
    for cls in ED.classes:
        for _ in range(200):
            kit = story_meta.random_kit(ED, cls, rng)
            assert len(kit) == 4 and len(set(kit)) == 4, (cls, kit)
            assert kit[3] == story_meta.ult_of(ED, cls)
            assert story_meta.kit_ok(ED, cls, kit[:3]), (cls, kit)


def test_broken_saved_kit_is_rebuilt():
    h = X.Hero({"uid": "h9", "name": "Тест", "cls": "druid", "skills": ["maul", "pounce", "bear_roar"]})
    X.fix_kit(ED, h)
    assert story_meta.kit_ok(ED, "druid", h.skills[:3]) and h.skills[3] == "wild_fury"
