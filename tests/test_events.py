"""События болота с последствиями: репутация и цены, засады и гости на ближайшие бои, личные перки,
изменения финального боя, тропы в следующие акты, автовыбор героя для броска."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_expedition import ED, XD, X, new_run  # noqa: E402
from sim.combat import ENEMY, PLAYER, Combat  # noqa: E402


def battle(run, kind="battle"):
    nid = next(n for n, v in run.nodes.items() if v["type"] == kind)
    run.node = nid
    enc = run.nodes[nid]["encounter"] if kind != "boss" else run.boss_encounter()
    return Combat(run.data, enc, squad=run.combat_squad(), enemy_scale=run.enemy_scale(), difficulty=run.difficulty)


def test_saving_the_prisoner_makes_toads_charge_more():
    _, run = new_run()
    base, heal = run.price_k(), run.heal_price()
    run.apply_ops([{"rep": "toads", "add": -3}], None)
    assert run.trade_mult() > 1 and run.price_k() > base and run.heal_price() > heal
    assert run.meets({"rep_below": {"toads": 0}}) and not run.meets({"rep_at_least": {"toads": 1}})
    gold = run.gold = 200
    run.apply_ops([{"pay": 50}], None)
    assert gold - run.gold == run.pay_price(50) > 50
    assert run.fill("Купить ({price:60})") == f"Купить ({run.pay_price(60)})"
    assert any("Жабы" in s for s, _ in run.consequences())


def test_battle_mods_and_guests_last_n_battles():
    _, run = new_run()
    run.apply_ops([{"battle_mod": {"name": "Засада", "battles": 1, "adds": ["toad_spearman"], "hp": 1.5}},
                   {"guest": {"unit": "reed_militia", "name": "Ополченец", "battles": 2}}], None)
    c = battle(run)
    foes = [u for u in c.alive(ENEMY) if u.proto_id == "toad_spearman"]
    allies = [u for u in c.units if u.team == PLAYER and u.summon and u.proto_id == "reed_militia"]
    assert foes and allies
    c.assign_initial_targets(PLAYER)
    assert allies[0].order and allies[0].order["target"].team == ENEMY
    assert len(run.player_units(c)) == len(run.heroes)          # гость — не герой отряда
    c.result = "victory"
    run.finish_battle(c)
    assert not run.battle_mods and run.guests and run.guests[0]["battles"] == 1


def test_boss_mods_change_only_the_final_fight():
    _, run = new_run()
    run.apply_ops([{"boss_mod": {"name": "Ослаблено", "hp": 0.5, "guests": ["toad_spearman"]}}], None)
    run.node = next(n for n, v in run.nodes.items() if v["type"] == "boss")
    act1 = run.enemy_scale()
    assert "guests" not in act1                                  # в первом акте босс ещё не финальный
    run.act = len(XD["acts"]) - 1
    fin = run.enemy_scale()
    assert fin["guests"] == ["toad_spearman"]
    run.boss_mods = []
    assert run.enemy_scale()["hp"] > fin["hp"]


def test_perks_change_hero_stats_and_survive_saving():
    _, run = new_run()
    h = run.heroes[0]
    hp0 = run.max_hp(h)
    run.apply_ops([{"perk": {"name": "Жертва", "mods": [{"stat": "hp", "mult": 0.8}], "desc": "−20%", "who": "hero"}}], h)
    assert h.perks and run.max_hp(h) < hp0
    back = X.Expedition.from_dict(ED, run.to_dict())
    assert back.heroes[0].perks == h.perks and back.boss_mods == run.boss_mods


def test_thread_for_a_later_act_waits_in_pending():
    _, run = new_run()
    lines = run.apply_ops([{"add_node": {"event": "rival_finale", "label": "Лагерь", "in_act": 3}}], None)
    assert run.pending and run.pending[-1]["act"] == 2 and "акте 3" in lines[0]


def test_best_hero_rolls_automatically():
    _, run = new_run()
    chk = {"attr": "int", "dc": 13, "classes": [run.heroes[-1].cls]}
    best = run.best_roller(chk)
    assert all(run.chance(best, chk) >= run.chance(h, chk) for h in run.heroes)


def test_toad_tax_only_for_those_toads_remember():
    _, run = new_run()
    ev = XD["events"]["toad_tax"]
    assert not run.meets(ev["requires"])
    run.apply_ops([{"rep": "toads", "add": -1}], None)
    assert run.meets(ev["requires"])


def test_every_option_of_every_event_applies():
    """Каждый исход каждого варианта применяется без ошибок; бои из событий собираются."""
    for eid, ev in XD["events"].items():
        for sid, st in ev["steps"].items():
            for i, opt in enumerate(st["options"]):
                outs = [opt] if "check" not in opt else [opt[k] for k in ("success", "fail", "crit", "fumble") if k in opt]
                for o in outs:
                    _, run = new_run(seed=len(eid) + i)
                    run.gold = 500
                    run.bag.append(run.new_item("normal"))
                    run.node = run.available()[0]
                    lines = run.apply_ops(o.get("do", []), run.heroes[0])
                    for x in lines:
                        if isinstance(x, dict) and "battle" in x and x["battle"] not in ("battle", "elite"):
                            enc = X.enc_index(ED, x["battle"])
                            Combat(run.data, enc, squad=run.combat_squad(), enemy_scale=run.enemy_scale())
                    assert run.gold >= 0, (eid, sid, i)


def test_chapter_has_about_forty_events():
    """Глава — 40–45 событий; цепочка (нить и её продолжения) считается за одно."""
    evs = XD["events"]
    followups = set()
    for ev in evs.values():
        for st in ev["steps"].values():
            for opt in st["options"]:
                for b in [opt] + [opt.get(k) or {} for k in ("success", "fail", "crit", "fumble")]:
                    stack = list(b.get("do", []))
                    while stack:
                        op = stack.pop()
                        stack += op.get("after", []) + op.get("do", []) + op.get("else", [])
                        if "add_node" in op:
                            followups.add(op["add_node"]["event"])
    chained = followups | {k for k, e in evs.items() if e.get("kind") == "thread" and not e.get("acts")}
    by_flag = {"smith_debt", "witch_envoy", "witch_price", "grotto_entrance", "village_feast", "village_mob",
               "witch_hunters", "magpie_nest"}
    assert 40 <= len(set(evs) - chained - by_flag) <= 46
