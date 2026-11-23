"""Новые колоды Охотницы: три школы, метки и первые пейоффы."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deck import model as M  # noqa: E402
from deck.battle import Battle, finish  # noqa: E402
from sim.grid import cheb  # noqa: E402
from test_expedition import ED  # noqa: E402


def put(u, cell):
    u.cell = u.prev_cell = tuple(cell)


def test_hunter_variants_have_distinct_decks_and_core_rewards():
    data = M.load()
    decks = {}
    for variant in ("range", "mark", "quiver"):
        run = M.Run(data=data, seed=1, hero="hunter", variant=variant)
        decks[variant] = [c.cid for c in run.deck]
        assert len(run.deck) == 11
        core = set(run.hero["rewards_by_variant"][variant])
        offers = [c.cid for c in run.reward_offer()]
        assert len(offers) == 3
        neutral = set(data["cards"].get("neutral", []))
        assert all(cid in run.hero["rewards"] or cid in neutral for cid in offers)
        assert sum(cid in core for cid in offers) == 2          # 2 карты школы + 1 свободная
    assert decks["range"] != decks["mark"] != decks["quiver"]
    assert "h_mark_burst" in decks["mark"] and "h_rapid" in decks["quiver"]


def test_mark_burst_scales_with_marks_and_has_tags():
    data = M.load()
    run = M.Run(data=data, seed=2, hero="hunter", variant="mark")
    b = Battle(ED, run, run.fights[0], seed=2)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (4, 2))
    foe.hp = foe.max_hp = 99
    foe.ds["mark"] = 4
    card = M.Card("h_mark_burst", run.defs)
    b.hand.append(card)
    b.energy = 9
    hp = foe.hp
    finish(b.play(card, "main", foe))
    assert hp - foe.hp == 4 + 3 * 4 + 4                     # 4 базовых + 3 за каждую метку + обычный бонус метки
    assert foe.ds["mark"] == 0                              # удар снял метку
    assert "Метка" in M.Card("h_mark_burst", run.defs).tags


def test_new_school_tags_are_derived():
    data = M.load()
    tags = M.Card("h_echo_shot", data["cards"]["cards"]).tags
    assert "Цепочка" in tags and "Резонанс" in tags
    assert "Комбо" in M.Card("h_rapid", data["cards"]["cards"]).tags


def test_all_new_hunter_cards_can_be_played():
    data = M.load()
    new = ("h_scope", "h_snipe", "h_mark_burst", "h_mark_web", "h_hunt",
           "h_echo_shot", "h_rapid", "h_arrow_well", "h_quiver_echo",
           "h_chain_1", "h_chain_2", "h_chain_3", "h_chain_finish", "h_chain_draw",
           "h_chain_guard", "h_chain_mark", "h_chain_song",
           "h_beat", "h_stalk", "h_mark_hunt", "h_hunt_final",
           "arrow_blood", "h_bloodlust", "h_blood_rite", "h_blood_volley",
           "h_dark_reload", "h_second_wind", "h_smoke_screen", "h_snare_net",
           "h_patient_shot", "h_dmg_expose", "h_dmg_pack_mark",
           "h_dmg_predator", "h_dmg_trophy",
           "h_dmg_ritual", "h_dmg_execute")
    new += tuple(cid for cid in data["cards"]["cards"] if cid.startswith("h_rng_"))
    for cid in new:
        run = M.Run(data=data, seed=4, hero="hunter", variant="mark")
        b = Battle(ED, run, run.fights[0], seed=4)
        h, foe = b.hero, b.foes()[0]
        put(h, (2, 2))
        put(foe, (4, 2))
        foe.hp = foe.max_hp = 99
        card = M.Card(cid, run.defs)
        b.hand.append(card)
        b.energy = 9
        targets = b.targets(card, "main")
        assert targets, cid
        target = targets[0]
        finish(b.play(card, "main", target))
        assert card not in b.hand or card in b.powers, cid


def test_chain_auto_plays_resonance_card():
    data = M.load()
    run = M.Run(data=data, seed=6, hero="hunter", variant="quiver")
    b = Battle(ED, run, run.fights[0], seed=6)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (4, 2))
    foe.hp = foe.max_hp = 99
    # два выстрела уже сыграны — резонанс [Выстрел] 2 выполнен
    b.turn_tags = [{"Выстрел"}, {"Выстрел"}]
    b.played = 2
    card = M.Card("h_echo_shot", run.defs)
    b.hand.append(card)
    b.energy = 0                                           # Цепочка играет без оплаты
    hp = foe.hp
    finish(b.echoes())
    assert hp - foe.hp == 5 and card not in b.hand


def test_quiver_rewards_guarantee_arrow_cards():
    data = M.load()
    run = M.Run(data=data, seed=7, hero="hunter", variant="quiver")
    creators = {"h_fill", "h_master_quiver", "h_arrow_well"}
    for _ in range(12):
        offers = {c.cid for c in run.reward_offer()}
        assert offers & creators, offers


def test_chain_variant_cascades_from_two_shots():
    data = M.load()
    run = M.Run(data=data, seed=11, hero="hunter", variant="chain")
    assert len(run.deck) == 11
    assert {"h_chain_1", "h_chain_2", "h_chain_3", "h_chain_draw", "h_chain_guard"} <= {c.cid for c in run.deck}
    assert "h_chain_mark" in data["heroes"]["heroes"]["hunter"]["rewards_by_variant"]["chain"]
    b = Battle(ED, run, run.fights[0], seed=11)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (4, 2))
    foe.hp = foe.max_hp = 999
    for cid in ("h_shot", "h_shot", "h_chain_1", "h_chain_2", "h_chain_3", "h_chain_finish",
                "h_chain_guard", "h_chain_mark"):
        b.hand.append(M.Card(cid, run.defs))
    b.energy = 9
    actions = []
    for cid in ("h_shot", "h_shot"):
        c = next(c for c in b.hand if c.cid == cid)
        actions.extend(b.play(c, "main", foe))
    shown = [a[2] for a in actions if a and a[0] == "chain_card"]
    assert len(shown) >= 4                                 # карты показываются по одной
    assert any(a and a[0] == "wait" and a[1] >= 0.4 for a in actions)  # пауза между цепочками
    assert b.played >= 8
    assert b.chain_drawn == 2                              # пассивка Цепной реакции
    assert len(b.hand) >= 6                                # большая рука после каскада
    assert h.shield > 0                                   # защитная цепочка сыграла сама
    assert any(c.cid == "h_chain_mark" for c in b.used + b.hand)  # мост тоже сработал
    hand_uids = {c.uid for c in b.hand}
    used_uids = {c.uid for c in b.used}
    assert shown and all(c.uid not in hand_uids for c in shown)    # разыгранные не остаются в руке
    assert all(c.uid in used_uids for c in shown)                  # до конца хода лежат в Used
    assert foe.hp < 999


def test_resonance_text_is_short_and_does_not_repeat_tag_description():
    data = M.load()
    assert M.plain(M.cond_text({"k": "resonance", "tag": "Выстрел", "n": 2})) == "Резонанс Выстрел 2"
    extra = M.plain(M.card_extras(data["cards"]["cards"]["h_chain_1"]))
    assert extra == "Цепочка: Резонанс Выстрел 2."
    assert "играется сама" not in extra and "разыгрывается" not in extra


def test_chain_quiver_item_buffs_chain_damage():
    data = M.load()
    run = M.Run(data=data, seed=12, hero="hunter", variant="chain")
    run.relics = [dict(data["relics"]["relics"]["chain_quiver"], id="chain_quiver")]
    b = Battle(ED, run, run.fights[0], seed=12)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (4, 2))
    foe.hp = foe.max_hp = 99
    c = M.Card("h_chain_1", run.defs)
    b.hand.append(c)
    b.energy = 9
    hp = foe.hp
    finish(b.play(c, "main", foe))
    assert hp - foe.hp == 6                                # 4 базовых + 2 от Колчана эха


def test_tag_items_passively_buff_cards():
    data = M.load()
    rel = data["relics"]["relics"]
    run = M.Run(data=data, seed=9, hero="hunter", variant="mark")
    run.relics = [dict(rel["shot_eye"], id="shot_eye")]
    b = Battle(ED, run, run.fights[0], seed=9)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (4, 2))
    foe.hp = foe.max_hp = 99
    shot = M.Card("h_shot", run.defs)
    b.hand.append(shot)
    b.energy = 9
    hp = foe.hp
    finish(b.play(shot, "main", foe))
    assert hp - foe.hp == 7                                # 5 базовых + 2 от предмета [Выстрел]


def test_arrow_well_creates_free_shots():
    data = M.load()
    run = M.Run(data=data, seed=8, hero="hunter", variant="quiver")
    b = Battle(ED, run, run.fights[0], seed=8)
    card = M.Card("h_arrow_well", run.defs)
    b.hand.append(card)
    b.energy = 9
    finish(b.play(card, "main", b.hero))
    assert sum(1 for c in b.hand if c.cid == "arrow") >= 2
