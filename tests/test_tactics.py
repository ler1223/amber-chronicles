"""CZN-волна: Травля, Область, Сохранение/Изгнание и школы Наёмника/Пиромантки."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deck import model as M  # noqa: E402
from deck.battle import Battle, finish  # noqa: E402
from test_expedition import ED  # noqa: E402


def put(u, cell):
    u.cell = u.prev_cell = tuple(cell)


def test_czn_tactical_tags_are_derived():
    data = M.load()
    cards = data["cards"]["cards"]
    assert "Область" in M.Card("p_grenade", cards).tags
    assert "Область" in M.Card("h_volley", cards).tags
    assert "Область" in M.Card("m_ring", cards).tags
    assert "Сохранение" in M.Card("m_duelist", cards).tags
    assert "Изгнание" in M.Card("battle_rage", cards).tags
    assert "Травля" in M.Card("h_beat", cards).tags
    assert "Травля" in M.Card("h_hunt", cards).tags


def test_hunt_followup_after_single_target_attack():
    data = M.load()
    run = M.Run(data=data, seed=21, hero="hunter", variant="mark")
    b = Battle(ED, run, run.fights[0], seed=21)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (4, 2))
    foe.hp = foe.max_hp = 99
    b.hand = [M.Card("h_hunt_final", run.defs)]
    b.energy = 9
    h.ds["hunt"] = 2
    hp = foe.hp
    finish(b.play(b.hand[0], "main", foe))
    # 6 базовых + 2×2 за травлю + 2 дополнительных выстрела
    assert hp - foe.hp == 6 + 4 + 2


def test_hunt_stack_card_and_hunt_per():
    data = M.load()
    run = M.Run(data=data, seed=22, hero="hunter", variant="mark")
    b = Battle(ED, run, run.fights[0], seed=22)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (4, 2))
    foe.hp = foe.max_hp = 99
    stalk = M.Card("h_stalk", run.defs)
    b.hand = [stalk]
    b.energy = 9
    step = b.targets(stalk, "main")[0]
    finish(b.play(stalk, "main", step))
    assert h.ds["hunt"] == 2
    assert h.shield >= 3


def test_merc_press_and_pyro_ash_decks():
    data = M.load()
    merc = M.Run(data=data, seed=23, hero="merc")
    assert merc.variant == "press"
    assert {"m_bulldoze", "m_ring"} <= {c.cid for c in merc.deck}
    assert "Натиск" == merc.hero["passives"]["press"]["name"]

    pyro = M.Run(data=data, seed=24, hero="pyro")
    assert pyro.variant == "ash"
    assert {"p_grenade", "p_oil"} <= {c.cid for c in pyro.deck}
    assert "Пепел" == pyro.hero["passives"]["ash"]["name"]


def test_merc_push_builds_momentum():
    data = M.load()
    run = M.Run(data=data, seed=25, hero="merc")
    b = Battle(ED, run, run.fights[0], seed=25)
    h, foe = b.hero, b.foes()[0]
    put(h, (2, 2))
    put(foe, (3, 2))
    foe.hp = foe.max_hp = 99
    card = M.Card("m_bulldoze", run.defs)
    b.hand = [card]
    b.energy = 9
    finish(b.play(card, "main", foe))
    assert h.ds["momentum"] >= 1


def test_pyro_ash_buffs_area_damage():
    data = M.load()
    hp = []
    for ash in (True, False):
        run = M.Run(data=data, seed=26, hero="pyro")
        b = Battle(ED, run, run.fights[0], seed=26)
        if not ash:
            b.variant = None
        h, foe = b.hero, b.foes()[0]
        put(h, (2, 2))
        put(foe, (4, 2))
        foe.hp = foe.max_hp = 99
        card = M.Card("p_grenade", run.defs)
        card.lvl = 0
        b.hand = [card]
        h.ds["heat"] = 9
        finish(b.play(card, "main", foe.cell))
        hp.append(foe.hp)
    assert hp[0] == hp[1] - 2


def test_all_tactics_cards_can_be_played():
    data = M.load()
    cards = {
        "h_beat": "hunter", "h_stalk": "hunter", "h_mark_hunt": "hunter",
        "h_area_hunt": "hunter", "h_hunt_final": "hunter",
        "m_bulldoze": "merc", "m_ring": "merc", "m_grapple": "merc",
        "m_break": "merc", "m_quake": "merc",
    }
    for cid, hero in cards.items():
        run = M.Run(data=data, seed=27, hero=hero)
        b = Battle(ED, run, run.fights[0], seed=27)
        h, foe = b.hero, b.foes()[0]
        put(h, (2, 2))
        put(foe, (4, 2))
        foe.hp = foe.max_hp = 99
        card = M.Card(cid, run.defs)
        b.hand = [card]
        b.energy = 9
        targets = b.targets(card, "main")
        assert targets, cid
        finish(b.play(card, "main", targets[0]))
        assert card not in b.hand, cid


def test_area_and_hunt_tag_items():
    data = M.load()
    rel = data["relics"]["relics"]
    assert rel["hunt_horn"]["tag_bonus"][0]["tag"] == "Травля"
    assert rel["area_seal"]["tag_bonus"][0]["tag"] == "Область"
    assert rel["retain_box"]["tag_bonus"][0]["tag"] == "Сохранение"
