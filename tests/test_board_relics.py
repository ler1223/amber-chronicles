from deck import model as M
from deck.relic_board import BoardRelics, RELICS
from deck.relic_choice import RelicChoice
from test_deck import _foe, card, finish, put
from test_field_ballista import arena, command, deploy


def give_relics(battle, *ids):
    battle.run.relics = [dict(RELICS[iid], id=iid) for iid in ids]
    battle.board_relics = BoardRelics(battle)
    return battle.board_relics


def choose(generator, *values):
    options = iter(values)
    answer = None
    while True:
        try:
            event = generator.send(answer)
        except StopIteration as ended:
            return ended.value
        answer = next(options) if isinstance(event, RelicChoice) else None


def test_ice_horseshoes_freeze_a_water_step_until_next_turn():
    battle, _ = arena()
    foe = _foe(battle, "bog_archer", (6, 5))
    give_relics(battle, "ice_horseshoes")
    move = card(battle, "h_dodge")
    cell = battle.c.grid.get((1, 3))
    cell.terrain = "water"

    finish(battle.play(move, "main", cell.pos))
    assert battle.hero.cell == cell.pos and cell.terrain == "ice_floor"
    foe.ds["stun"] = True
    finish(battle.end_turn())
    assert cell.terrain == "water"


def test_turning_oil_slide_changes_the_last_cell_only():
    battle, _ = arena()
    foe = _foe(battle, "bog_archer", (3, 2))
    give_relics(battle, "oil_chute")
    battle.set_surface((4, 2), "oil")
    push = M.Card("test_push", {"test_push": dict(battle.run.defs["h_tendon"], tags=["push"])})

    choose(battle.push(battle.hero, foe, 1, card=push), (4, 3))
    assert foe.cell == (4, 3)


def test_piercing_seal_allows_firing_into_an_intervening_ballista():
    battle, _ = arena()
    foe = _foe(battle, "bog_archer", (5, 2))
    give_relics(battle, "piercing_seal")
    unit = deploy(battle)
    shot = card(battle, "h_shot")
    hp = foe.hp
    assert unit in battle.targets(shot, "main") and foe not in battle.targets(shot, "main")

    finish(battle.play(shot, "main", unit))

    assert unit.charge == 2 and foe.hp == hp and shot in battle.used
    assert unit not in battle.targets(card(battle, "h_shot"), "main")


def test_full_ballista_can_keep_three_charges():
    battle, _ = arena()
    foe = _foe(battle, "bog_archer", (5, 2))
    foe.hp = foe.max_hp = 100
    give_relics(battle, "metered_shutter")
    unit = deploy(battle)
    battle.draw(2)
    shot = command(battle, "h_ballista_fire")
    unit.charge = 10

    choose(battle.play(shot, "main", foe), True)
    assert unit.charge == 3
    assert foe.hp == 77


def test_mobile_mount_trades_the_next_passive_charge_for_a_move():
    battle, _ = arena()
    foe = _foe(battle, "bog_archer", (6, 2))
    give_relics(battle, "mobile_mount")
    unit = deploy(battle)
    battle.draw(2)
    finish(battle.play(card(battle, "h_dodge"), "main", (1, 3)))
    load = command(battle, "h_ballista_load")

    choose(battle.play(load, "main", unit), (2, 3))
    assert unit.cell == (2, 3) and unit.charge == 2
    foe.ds["stun"] = True
    finish(battle.end_turn())
    assert unit.charge == 2


def test_cracked_clock_keeps_the_exact_skipped_intention_for_next_turn():
    battle, _ = arena()
    foe = _foe(battle, "bog_archer", (4, 2))
    board = give_relics(battle, "cracked_clock")
    it = {"kind": "zone", "name": "Зона", "dmg": 5, "shape": "cell", "cells": [battle.hero.cell]}
    foe.intent = it
    definition = dict(battle.run.defs["h_shot"], rules=["finale"])
    finale = M.Card("finale_test", {"finale_test": definition})

    choose(board.finale(finale), foe)
    hp = battle.hero.hp
    finish(battle.end_turn())
    assert foe.intent is it and battle.hero.hp == hp


def test_double_spring_repositions_only_the_first_trap():
    battle, _ = arena()
    foe = _foe(battle, "bog_archer", (4, 2))
    give_relics(battle, "double_spring")
    battle.traps[(5, 2)] = 1
    choose(battle.walk(foe, [(5, 2)]), (5, 3))
    assert (5, 2) not in battle.traps and (5, 3) in battle.traps
    finish(battle.walk(foe, [(5, 3)]))
    assert not battle.traps


def test_bullet_can_return_after_an_enemy_phase_trap():
    battle, _ = arena()
    foe = _foe(battle, "bog_archer", (4, 2))
    give_relics(battle, "tin_bandolier")
    battle.traps[(4, 3)] = 1
    battle.enemy_phase = True
    finish(battle.walk(foe, [(4, 3)]))
    battle.tick_end(foe)
    battle.enemy_phase = False
    finish(battle.start_player_turn())
    definition = dict(battle.run.defs["h_shot"], tags=["bullet"])
    bullet = M.Card("test_bullet", {"test_bullet": definition})
    battle.hand.append(bullet)

    choose(battle.play(bullet, "main", foe), True)

    assert battle.draw_pile[-1] is bullet
    assert bullet not in battle.used


def test_rag_double_redirects_the_bog_archers_marked_shot():
    battle, _ = arena()
    foe = _foe(battle, "bog_archer", (4, 2))
    board = give_relics(battle, "rag_double")
    foe.intent = dict(foe.edef["cycle"][0], cells=[battle.hero.cell])
    defense = M.Card("defend", battle.run.defs)
    choose(board.retained(defense), (1, 3))
    hp = battle.hero.hp

    finish(battle.act(foe))

    assert battle.hero.hp == hp
    assert board.decoy is None
