"""Новые карты Наёмника и Охотницы: проверка розыгрыша и ключевых эффектов."""
from deck import model as M
from deck.battle import Battle, finish
from tests.test_expedition import ED


def put(u, cell):
    u.cell = u.prev_cell = tuple(cell)


def battle(hero, cid, *, walked=0):
    data = M.load()
    run = M.Run(data=data, seed=71, hero=hero)
    b = Battle(ED, run, run.fights[0], seed=71)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (3, 2))
    foe.hp = foe.max_hp = 99
    b.walked = walked
    card = M.Card(cid, run.defs)
    b.hand = [card]
    b.energy = 9
    return b, h, foe, card, run


def test_new_merc_cards_play_and_standstill():
    b, h, foe, card, _ = battle("merc", "m_brace")
    finish(b.play(card, "main", h))
    assert h.shield == 9 and h.ds["counter"] == 2

    b, h, foe, card, _ = battle("merc", "m_rampart")
    finish(b.play(card, "main", h))
    assert h.shield == 8 and h.ds["thorns"] == 3 and h.ds["fort"]

    b, h, foe, card, _ = battle("merc", "m_battle_plan")
    finish(b.play(card, "main", h))
    assert b.empower["Толчок"] == 4

    b, h, foe, card, _ = battle("merc", "m_blood_exchange")
    finish(b.play(card, "main", foe))
    assert foe.ds["bleed"] == 2 and card not in b.hand


def test_new_hunter_cards_play():
    b, h, foe, card, _ = battle("hunter", "h_kneel")
    finish(b.play(card, "main", foe))
    assert foe.ds["mark"] == 1 and foe.hp <= 99 - 12

    b, h, foe, card, _ = battle("hunter", "h_venom_tip")
    finish(b.play(card, "main", foe))
    assert foe.ds["poison"] == 3 and card not in b.hand

    b, h, foe, card, _ = battle("hunter", "h_beacon")
    finish(b.play(card, "main", foe))
    assert foe.ds["mark"] == 2 and card not in b.hand

    b, h, foe, card, _ = battle("hunter", "h_shadow_step")
    target = b.targets(card, "main")[0]
    finish(b.play(card, "main", target))
    assert h.shield == 4 and card not in b.hand


def test_blood_moon_triggers_on_mark():
    b, h, foe, card, run = battle("hunter", "h_blood_moon")
    finish(b.play(card, "main", h))
    mark = M.Card("h_marking", run.defs)
    b.hand = [mark]
    b.energy = 9
    finish(b.play(mark, "main", foe))
    assert foe.ds["bleed"] >= 2
