"""CZN-волна: Преследование, Область, Сохранение/Изгнание и школы Наёмника/Пиромантки."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deck import model as M  # noqa: E402
from deck.battle import Battle, finish  # noqa: E402
from sim.grid import cheb  # noqa: E402
from test_expedition import ED  # noqa: E402


def put(u, cell):
    u.cell = u.prev_cell = tuple(cell)


def test_combat_vfx_tag_palette_has_deck_tags():
    from sim.data import GameData
    tags = GameData().tags
    for tag in ("bleed", "blood", "poison", "Преследование"):
        assert tag in tags


def test_pursuit_has_vfx_tag_description():
    from sim.data import GameData
    assert "Преследование" in GameData().tags


def test_czn_tactical_tags_are_derived():
    data = M.load()
    cards = data["cards"]["cards"]
    assert "Область" in M.Card("p_grenade", cards).tags
    assert "Область" in M.Card("h_volley", cards).tags
    assert "Область" in M.Card("m_ring", cards).tags
    assert "Сохранение" in M.Card("m_duelist", cards).tags
    assert "Изгнание" in M.Card("battle_rage", cards).tags
    assert "Преследование" in M.Card("h_beat", cards).tags
    assert "Преследование" in M.Card("h_hunt", cards).tags


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
    # 6 базовых + 2×2 за преследование + 2 дополнительных выстрела
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


def test_non_attack_chain_waits_for_player_target():
    data = M.load()
    run = M.Run(data=data, seed=28, hero="hunter", variant="mark")
    b = Battle(ED, run, run.fights[0], seed=28)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (4, 2))
    card = M.Card("h_trail", run.defs)
    b.hand = [card]
    b.turn_tags = [{"Выстрел"}, {"Выстрел"}]
    b.played = 2
    gen = b.echoes()
    first = next(gen)
    assert first[0] == "chain_card" and first[2].cid == "h_trail"
    choice = next(gen)
    assert choice[0] == "chain_choice" and choice[1].cid == "h_trail"
    target = b.targets(card, "main")[0]
    try:
        gen.send(target)
    except StopIteration:
        pass
    finish(gen)
    assert card not in b.hand and card in b.used


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


def test_tressa_style_blood_arrows_and_curse():
    data = M.load()
    run = M.Run(data=data, seed=31, hero="hunter", variant="quiver")
    b = Battle(ED, run, run.fights[0], seed=31)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (4, 2))
    foe.hp = foe.max_hp = 99
    quiver = M.Card("h_shadow_quiver", run.defs)
    b.hand = [quiver]
    b.energy = 9
    finish(b.play(quiver, "main", h))
    arrows = [c for c in b.hand if c.cid == "arrow_blood"]
    assert arrows and "Кровь" in arrows[0].tags
    arrow = arrows[0]
    hp = foe.hp
    finish(b.play(arrow, "main", foe))
    assert hp - foe.hp >= 3 and foe.ds["bleed"] >= 2


def test_bloodlust_and_area_utility_cards():
    data = M.load()
    run = M.Run(data=data, seed=32, hero="hunter", variant="mark")
    b = Battle(ED, run, run.fights[0], seed=32)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (4, 2))
    foe.hp = foe.max_hp = 99
    lust = M.Card("h_bloodlust", run.defs)
    b.hand = [lust]
    b.energy = 9
    finish(b.play(lust, "main", h))
    assert h.ds["strength"] >= 2

    smoke = M.Card("h_smoke_screen", run.defs)
    b.hand = [smoke]
    target = min(b.targets(smoke, "main"), key=lambda p: cheb(p, foe.cell))
    finish(b.play(smoke, "main", target))
    assert foe.ds["weak"] >= 1 or not foe.alive


def test_tressa_curse_support_and_multi_hit():
    data = M.load()
    run = M.Run(data=data, seed=33, hero="hunter", variant="mark")
    b = Battle(ED, run, run.fights[0], seed=33)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (4, 2))
    foe.hp = foe.max_hp = 99

    curse = M.Card("h_blood_rite", run.defs)
    b.hand = [curse]
    b.energy = 9
    finish(b.play(curse, "main", h))
    shot = M.Card("h_shot", run.defs)
    b.hand = [shot]
    finish(b.play(shot, "main", foe))
    assert foe.ds["bleed"] >= 1

    foe.ds["bleed"] = 3
    volley = M.Card("h_blood_volley", run.defs)
    b.hand = [volley]
    hp = foe.hp
    finish(b.play(volley, "main", foe))
    assert hp - foe.hp == 15                              # 3 удара по 3 + 2 за кровь

    wind = M.Card("h_second_wind", run.defs)
    b.hand = [wind]
    b.energy = 2
    finish(b.play(wind, "main", h))
    assert b.energy == 3 and wind in b.exhaust

    reload = M.Card("h_dark_reload", run.defs)
    b.hand = [reload]
    b.energy = 2
    finish(b.play(reload, "main", h))
    assert b.energy == 2 and any(c.cid == "arrow_blood" for c in b.hand)


def test_hunter_damage_amplifiers_and_debuffs():
    data = M.load()
    run = M.Run(data=data, seed=34, hero="hunter", variant="mark")
    b = Battle(ED, run, run.fights[0], seed=34)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (3, 2))
    foe.hp = foe.max_hp = 99
    b.energy = 9

    expose = M.Card("h_dmg_expose", run.defs)
    b.hand = [expose]
    finish(b.play(expose, "main", foe))
    assert foe.ds["vulnerable"] >= 2

    execute = M.Card("h_dmg_execute", run.defs)
    b.hand = [execute]
    hp = foe.hp
    finish(b.play(execute, "main", foe))
    assert hp - foe.hp > 8

    predator = M.Card("h_dmg_predator", run.defs)
    b.hand = [predator]
    finish(b.play(predator, "main", h))
    shot = M.Card("h_shot", run.defs)
    b.hand = [shot]
    finish(b.play(shot, "main", foe))
    assert h.ds["ranged_bonus"] >= 1


def test_area_and_hunt_tag_items():
    data = M.load()
    rel = data["relics"]["relics"]
    assert rel["hunt_horn"]["tag_bonus"][0]["tag"] == "Преследование"
    assert rel["area_seal"]["tag_bonus"][0]["tag"] == "Область"
    assert rel["retain_box"]["tag_bonus"][0]["tag"] == "Сохранение"
