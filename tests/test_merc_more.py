"""Новые карты Наёмника: стойка «без шага» и толчок со столкновением."""
from deck import model as M
from deck.battle import Battle, finish
from tests.test_expedition import ED


def put(u, cell):
    u.cell = u.prev_cell = tuple(cell)


def battle(cid, *, walked=0):
    data = M.load()
    run = M.Run(data=data, seed=61, hero="merc")
    b = Battle(ED, run, run.fights[0], seed=61)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (3, 2))
    foe.hp = foe.max_hp = 99
    b.walked = walked
    b.hand = [M.Card(cid, run.defs)]
    b.energy = 9
    return b, h, foe, b.hand[0]


def test_not_walked_stand_and_hammer():
    b, h, foe, card = battle("m_stand")
    finish(b.play(card, "main", h))
    assert b.empower.get("Удар") == 5
    assert h.shield == 6

    b2, h2, foe2, card2 = battle("m_hammer")
    finish(b2.play(card2, "main", foe2))
    assert foe2.ds["stun"] and foe2.hp <= 99 - 12

    b3, h3, foe3, card3 = battle("m_hammer", walked=1)
    finish(b3.play(card3, "main", foe3))
    assert not foe3.ds["stun"] and foe3.hp <= 99 - 8


def test_collision_and_bleed_cards_are_playable():
    for cid in ("m_receive", "m_kegel", "m_pin", "m_blood_rush"):
        b, h, foe, card = battle(cid)
        targets = b.targets(card, "main")
        assert targets, cid
        finish(b.play(card, "main", targets[0]))
        assert card not in b.hand, cid
    b, h, foe, card = battle("m_pin")
    finish(b.play(card, "main", foe))
    assert foe.ds["root"] and foe.ds["vulnerable"]
