"""Снайперский архетип Охотницы: линия, пробитие, заряд и X-выстрел."""
from deck import model as M
from deck.battle import Battle, finish
from tests.test_expedition import ED


def put(u, cell):
    u.cell = u.prev_cell = tuple(cell)


def battle(cid, *, energy=9, fight=0):
    data = M.load()
    run = M.Run(data=data, seed=101, hero="hunter", variant="mark")
    b = Battle(ED, run, run.fights[fight], seed=101)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (4, 2))
    foe.hp = foe.max_hp = 99
    b.hand = [M.Card(cid, run.defs)]
    b.energy = energy
    return b, h, foe, run


def test_line_targets_only_cardinal_directions():
    b, h, foe, run = battle("h_sniper_line")
    assert foe in b.targets(b.hand[0], "main")
    put(foe, (4, 3))                                      # диагональ — не линия
    assert not b.targets(b.hand[0], "main")


def test_piercing_line_hits_every_enemy_on_the_line():
    b, h, foe, run = battle("h_sniper_pierce", fight=1)
    a, c = b.foes()[1], b.foes()[2]
    put(a, (5, 2))
    put(c, (6, 2))
    for u in (foe, a, c):
        u.hp = u.max_hp = 99
    hp = [u.hp for u in (foe, a, c)]
    finish(b.play(b.hand[0], "main", foe))
    assert all(u.hp < old for u, old in zip((foe, a, c), hp))


def test_growing_arrow_retains_and_grows_at_end_of_turn():
    b, h, foe, run = battle("h_sniper_grow")
    card = b.hand[0]
    before = b.temper.get(card.uid, 0)
    finish(b.end_turn())
    assert card in b.hand and b.temper.get(card.uid, 0) == before + 2


def test_double_attack_and_x_cost():
    b, h, foe, run = battle("h_sniper_double")
    finish(b.play(b.hand[0], "main", h))
    assert b.double_attacks == 2
    strike = M.Card("strike", run.defs)
    put(foe, (3, 2))
    b.hand = [strike]
    hp = foe.hp
    finish(b.play(strike, "main", foe))
    assert hp - foe.hp == 12                            # удар 6 ×2
    assert b.double_attacks == 1

    b, h, foe, run = battle("h_sniper_allin", energy=4)
    card = b.hand[0]
    assert card.cost_label == "X"
    hp = foe.hp
    finish(b.play(card, "main", foe))
    assert b.energy == 0 and hp - foe.hp == 6 + 4 * 4
