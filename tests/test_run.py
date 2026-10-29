"""Тесты вылазки: карта, сборка билдов, уровни, предметы в слотах, руны, реликвии, награды, торговец."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.build import build_proto  # noqa: E402
from sim.combat import ENEMY, PLAYER, Combat  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim.run import Run  # noqa: E402

DATA = GameData()


def test_map_shape_for_many_seeds():
    for seed in range(60):
        run = Run(DATA, seed)
        nodes = run.nodes
        layers = DATA.config["run"]["map_layers"]
        assert all(nodes[n]["type"] == "battle" for n in run.available())
        boss = [n for n in nodes.values() if n["type"] == "boss"]
        assert len(boss) == 1 and boss[0]["layer"] == len(layers) - 1
        assert any(n["type"] == "elite" for n in nodes.values())
        # всё достижимо от старта, у всех кроме босса есть выход
        seen, stack = set(), list(run.available())
        while stack:
            nid = stack.pop()
            if nid in seen:
                continue
            seen.add(nid)
            stack += nodes[nid]["next"]
        assert seen == set(nodes)
        for n in nodes.values():
            assert n["next"] or n["type"] == "boss"
            if n["type"] in ("battle", "elite", "boss"):
                kind = DATA.encounters[n["encounter"]]["kind"]
                assert kind == {"battle": "normal"}.get(n["type"], n["type"])


def test_build_talents_path_items_runes():
    base = DATA.classes["warrior"]
    p = build_proto(DATA, "warrior", ["w_hardened", "w_shield_wall"], branches={"power_strike": ("A", 2)})
    assert p["hp"] == base["hp"] + 30
    assert p["passive"]["mult"] == 0.3
    strike = p["skill_defs"]["power_strike"]
    assert strike["name"] == "Сокрушение" and strike["radius"] == 1
    assert [e["type"] for e in strike["effects"]] == ["damage", "knockback", "stun", "damage", "stun"]
    assert DATA.skills["power_strike"]["name"] == "Мощный удар"  # общие данные не тронуты

    # путь меняет пассивку и навык; модификатор блока к ярости не применяется
    b = build_proto(DATA, "warrior", ["w_shield_wall"], path="berserker")
    assert "whirlwind" in b["skills"] and "taunt" not in b["skills"]
    assert b["passive"]["kind"] == "rage" and "mult" not in b["passive"]
    assert b["armor"] == base["armor"] - 1 and b["attack"]["damage"] == base["attack"]["damage"] + 4

    m = build_proto(DATA, "mage", ["m_quick_cast", "m_blink"], ["frost_heart", "storm_staff"])
    assert m["skill_defs"]["fireball"]["cast"] == round(DATA.skills["fireball"]["cast"] * 0.7, 2)
    assert "blink" in m["skills"] and m["power"] == 1.2
    assert all(e.get("tag") != "fire" for e in m["skill_defs"]["fireball"]["effects"])

    r = build_proto(DATA, "mage", runes={"fireball": ["r_power", "r_breadth"]})
    fb = r["skill_defs"]["fireball"]
    assert fb["effects"][0]["amount"] == round(DATA.skills["fireball"]["effects"][0]["amount"] * 1.25)
    assert fb["radius"] == 2 and fb["runes"] == ["r_power", "r_breadth"]


def test_every_branch_and_path_builds_and_fights():
    """Все ступени веток (и на путях) собираются, а бой с ними проходит без ошибок."""
    paths = {cls: [None] + [p for p, d in DATA.paths.items() if d["class"] == cls] for cls in DATA.classes}
    for variant in (0, 1):
        for b in ("A", "B"):
            for tier in (1, 2):
                squad = []
                for c in DATA.squad["units"]:
                    path = paths[c][variant]
                    p0 = build_proto(DATA, c, path=path)
                    branches = {sid: (b, tier) for sid in p0["skills"] if sid in DATA.branches}
                    p = build_proto(DATA, c, branches=branches, path=path)
                    for sid in branches:
                        sk = p["skill_defs"][sid]
                        assert sk["branch"] == (b, tier) and sk["desc"] and sk["effects"]
                    squad.append({"cls": c, "proto": p})
                for enc in range(len(DATA.encounters)):
                    c = Combat(DATA, enc, ai_teams=(PLAYER, ENEMY), squad=squad)
                    while not c.result and c.time < 120:
                        c.step()


def test_resist_halves_tagged_damage():
    run = Run(DATA, 1)
    run.equip(run.squad[1], "flame_ward")
    c = Combat(DATA, 0, squad=run.combat_squad())
    archer = c.alive(PLAYER)[1]
    dealt = c.damage(archer, 20, None, "fire", "spell")
    assert dealt == 20 * 0.5 - archer.armor


def test_levels_give_stats_without_choices():
    run = Run(DATA, 3)
    war = run.squad[0]
    hp1, power1 = run.max_hp(war), run.proto(war)["power"]
    war.hp -= 50
    ups = run.gain_xp(100)
    assert len(ups) == 4 and all(m.level == 2 for m in run.squad)
    assert run.max_hp(war) > hp1 and run.proto(war)["power"] > power1
    assert war.hp == hp1 - 50 + (run.max_hp(war) - hp1)     # прибавка к макс. HP идёт и в текущее
    run.gain_xp(10_000)
    assert all(m.level == DATA.config["run"]["max_level"] for m in run.squad)


def test_equip_slots():
    run = Run(DATA, 4)
    war = run.squad[0]
    hp = DATA.classes["warrior"]["hp"]
    run.inventory.append("power_belt")
    run.equip(war, "power_belt")
    run.equip(war, "fire_sword")
    assert war.items == {"armor": "power_belt", "weapon": "fire_sword"} and not run.inventory
    assert war.hp == hp + 25
    run.equip(war, "chainmail")                       # тот же слот — пояс уходит в сумку
    assert war.items["armor"] == "chainmail" and run.inventory == ["power_belt"] and war.hp == hp + 10
    run.unequip(war, "weapon")
    assert "weapon" not in war.items and sorted(run.inventory) == ["fire_sword", "power_belt"]


def test_runes_and_relics():
    run = Run(DATA, 5)
    offers = run.rune_offers(3)
    assert len(offers) == 3 and len({(o["member"], o["skill"]) for o in offers}) == 3
    mage = run.squad[2]
    run.apply_rune({"type": "rune", "member": 2, "skill": "fireball", "rune": "r_thrift"})
    assert run.proto(mage)["skill_defs"]["fireball"]["ap"] == DATA.skills["fireball"]["ap"] - 1
    # на навык не больше max_runes_per_skill рун
    run.apply_rune({"type": "rune", "member": 2, "skill": "fireball", "rune": "r_power"})
    assert all(not (o["member"] == 2 and o["skill"] == "fireball") for o in run.rune_offers(50))
    hp = run.max_hp(mage)
    run.add_relic("amber_charm")
    run.add_relic("iron_vow")
    assert run.proto(mage)["ap_max"] == DATA.classes["mage"]["ap_max"] + 1 and run.max_hp(mage) == hp
    c = Combat(DATA, 0, squad=run.combat_squad(), fx=run.combat_fx())
    assert all(u.shield == 20 for u in c.alive(PLAYER))


def test_full_battle_in_run_carries_hp_and_rewards():
    run = Run(DATA, 5)
    node = run.enter(run.available()[0])
    c = Combat(DATA, node["encounter"], ai_teams=(PLAYER, ENEMY), squad=run.combat_squad())
    while not c.result:
        c.step()
    gold = run.gold
    summary = run.finish_battle(c, c.positions())
    assert summary["result"] == c.result
    if c.result == "victory":
        assert run.gold == gold + DATA.config["run"]["rewards"]["normal"]["gold"]
        assert all(m.xp == 60 for m in run.squad)
        opts = run.reward_options()
        assert len(opts) == 3 and {o["type"] for o in opts} >= {"item", "rune"}
        item = run.apply_reward(opts[0])
        assert item in DATA.items
    assert run.formation == c.positions()


def test_rewards_reroll_and_elite():
    run = Run(DATA, 7, bonus={"rerolls": 1})
    run.node = next(n for n, v in run.nodes.items() if v["type"] == "elite")
    opts = run.reward_options()
    assert opts[0]["type"] == "relic"
    assert all(DATA.items[o["item"]]["rarity"] != "common" for o in opts if o["type"] == "item")
    assert run.reroll() and run.rerolls == 0 and run.reroll() is None


def test_shop_offers_buy_and_discount():
    run = Run(DATA, 6, bonus={"discount": 0.15})
    run.shop_stock = run.shop_offers()
    kinds = [o["type"] for o in run.shop_stock]
    assert kinds.count("item") == DATA.config["run"]["shop_items"] - 1 and "rune" in kinds and "relic" in kinds
    run.gold = 1000
    item = next(o for o in run.shop_stock if o["type"] == "item")
    assert item["price"] == round(DATA.items[item["item"]]["price"] * 0.85)
    ok, got = run.buy(item)
    assert ok and got == item["item"] and item not in run.shop_stock
    relic = next(o for o in run.shop_stock if o["type"] == "relic")
    assert run.buy(relic) == (True, None) and relic["relic"] in run.relics
    run.gold = 0
    assert run.buy(run.shop_stock[0]) == (False, None) and not run.buy_heal()
