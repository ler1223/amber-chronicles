"""Стойки «Спуска»: переключение, защита и геометрия добровольного перемещения."""
from deck import model as M
from deck.battle import Battle, finish
from sim.grid import Grid, cheb
from test_expedition import ED


def battle():
    run = M.Run(seed=3, hero="merc")
    b = Battle(ED, run, run.fights[0], seed=3)
    b.c.grid = Grid(["......."] * 7, {".": {"terrain": "grass"}})
    b.hero.cell = b.hero.prev_cell = (2, 2)
    for i, foe in enumerate(b.foes()):
        foe.cell = foe.prev_cell = (6, 6 - i)
        foe.hp = foe.max_hp = 99
    b.energy = 12
    b.hand.clear()
    return b


def give(b, main, kind="skill", **extras):
    definition = {"name": "Манёвр", "type": kind, "cost": 1, "main": main, **extras}
    card = M.Card("test_maneuver", {"test_maneuver": definition})
    b.hand.append(card)
    return card


def stance_card(b, stance, **main):
    return give(b, {"target": "self", "do": [{"op": "stance", "id": stance}], **main})


def test_replaying_stance_exits_and_another_stance_replaces_it():
    b = battle()
    stance_repeat = [{"when": {"k": "series", "n": 0}, "repeat": 1}]
    ready = stance_card(b, "ready", **{"if": stance_repeat})
    finish(b.play(ready, "main", b.hero))
    assert b.stance == "ready"
    finish(b.start_player_turn())
    assert b.stance == "ready"

    knight = stance_card(b, "knight")
    finish(b.play(knight, "main", b.hero))
    assert b.stance == "knight"

    repeated_knight = stance_card(b, "knight", **{"if": stance_repeat})
    finish(b.play(repeated_knight, "main", b.hero))
    assert b.stance is None


def test_ready_adds_two_to_first_positive_shield_and_refreshes_next_turn():
    b = battle()
    hero = b.hero
    b.set_stance("ready")
    b.gain_shield(hero, 0)
    assert not hero.shield
    assert b.shield_value(hero, 2) == 4
    b.gain_shield(hero, 2)
    assert hero.shield == 4
    b.gain_shield(hero, 2)
    assert hero.shield == 6
    b.set_stance("knight")
    b.set_stance("ready")
    assert b.shield_value(hero, 2) == 2
    finish(b.start_player_turn())
    assert b.shield_value(hero, 2) == 4


def test_guard_boosts_shield_and_blocks_attack_cards_including_alt_and_echo():
    b = battle()
    h, foe = b.hero, b.foes()[0]
    foe.cell = foe.prev_cell = (2, 3)
    attack = give(b, {"target": "enemy", "do": [{"op": "damage", "n": 5}]}, kind="attack",
                  alt={"target": "self", "do": [{"op": "block", "n": 3}]},
                  echo={"on": "hit", "do": [{"op": "damage", "n": 5}]})
    defense = give(b, {"target": "self", "do": [{"op": "block", "n": 3}]})
    assert b.can_play(attack, "main") and b.can_play(attack, "alt")

    b.set_stance("guard")
    for mode, target in (("main", foe), ("alt", h)):
        assert not b.can_play(attack, mode)
        finish(b.play(attack, mode, target))
    assert b.range_cells(attack, "main") == []
    finish(b.fire_echo(attack, foe))
    assert attack in b.hand and attack.uses == 0 and not b.echoed
    assert h.shield == 0 and foe.hp == 99

    finish(b.play(defense, "main", h))
    assert h.shield == 5
    h.ds["counter"] = 1
    finish(b.strike(foe, h, 1))
    finish(b.react())
    assert foe.hp < 99 and h.ds["counter"] == 0 and attack.uses == 0

    exit_card = M.Card("m_stance_guard", b.run.defs)
    b.hand.append(exit_card)
    shield = h.shield
    finish(b.play(exit_card, "main", h))
    assert b.stance is None and h.shield == shield + 3
    assert b.can_play(attack, "main") and b.can_play(attack, "alt")


def test_knight_step_dash_and_forced_motion_use_correct_cells():
    b = battle()
    h = b.hero
    b.set_stance("knight")
    b.set_surface((2, 3), "poison")
    b.c.grid.get((3, 3)).passable = False
    b.set_surface((3, 4), "fire")
    step = give(b, {"target": "cell_step", "step": 1, "do": []})
    assert (2, 3) not in b.targets(step, "main")
    assert (3, 4) in b.targets(step, "main") and (3, 4) in b.range_cells(step, "main")
    assert b.paths(h, 1)[(3, 4)] == [(3, 4)]
    finish(b.play(step, "main", (3, 4)))
    assert (h.cell, h.shield, b.walked) == ((3, 4), 3, 1)
    assert h.ds["poison"] == 0 and h.ds["burn"] == 2

    dash = give(b, {"target": "cell_dash", "dash": 1, "do": []})
    assert b.dash_paths(1)[(4, 2)] == [(4, 2)]
    assert (4, 2) in b.targets(dash, "main") and (4, 2) in b.range_cells(dash, "main")
    finish(b.play(dash, "main", (4, 2)))
    assert (h.cell, h.shield, b.walked) == ((4, 2), 3, 2)
    finish(b.push(None, h, 1, d=(1, 0)))
    assert (h.cell, h.shield, b.walked) == ((5, 2), 3, 2)

    finish(b.start_player_turn())
    step = give(b, {"target": "cell_step", "step": 1, "do": []})
    finish(b.play(step, "main", (4, 4)))
    assert (h.cell, h.shield, b.walked) == ((4, 4), 3, 1)


def test_knight_approach_and_embedded_retreat_are_jumps():
    b = battle()
    h, foe = b.hero, b.foes()[0]
    foe.cell = foe.prev_cell = (4, 5)
    b.set_stance("knight")
    approach = give(b, {"target": "reach", "reach": 1, "do": [{"op": "damage", "n": 1}]}, kind="attack")
    assert foe in b.targets(approach, "main")
    assert (3, 4) in b.reach_spots(approach, "main")
    finish(b.play(approach, "main", ((3, 4), foe)))
    assert h.cell == (3, 4)

    before = h.cell
    retreat = give(b, {"target": "enemy", "do": [{"op": "retreat", "n": 1}]})
    finish(b.play(retreat, "main", foe))
    assert {abs(h.cell[0] - before[0]), abs(h.cell[1] - before[1])} == {1, 2}
    assert cheb(h.cell, foe.cell) > cheb(before, foe.cell)
    assert h.shield == 3 and b.walked == 2
