import pytest

from deck import bot, model as M
from deck.battle import BallistaShot, Battle
from sim.grid import Grid
from test_deck import _foe, card, finish, hero_battle, put


COMMANDS = ("h_ballista_load", "h_ballista_fire")
PILES = ("draw_pile", "hand", "used", "discard", "exhaust", "guard")


def arena():
    battle, run = hero_battle("hunter")
    battle.c.grid = Grid(["." * 9] * 7, {".": {}})
    for foe in battle.foes():
        foe.alive = False
    put(battle, battle.hero, (1, 2))
    battle.hand.clear()
    battle.draw_pile.clear()
    battle.energy = 12
    return battle, run


def deploy(battle, placement=None, cell=(2, 2)):
    if placement is None:
        placement = card(battle, "h_ballista")
    assert cell in battle.targets(placement, "main")
    finish(battle.play(placement, "main", cell))
    return next(unit for unit in battle.ballistas if unit.cell == cell)


def command(battle, cid, owner=None):
    return next(c for c in battle.hand if c.cid == cid and (owner is None or c.ballista_owner is owner))


def copied_placement(battle):
    copy = card(battle, "h_ballista")
    copy.copied = True
    return copy


def wait_round(battle):
    for foe in battle.foes():
        foe.ds["stun"] = True
    finish(battle.end_turn())


def assert_no_commands(battle):
    for pile in PILES:
        assert not any(c.cid in COMMANDS for c in getattr(battle, pile)), pile
    for unit in battle.c.units:
        assert not any(c.cid in COMMANDS for c in getattr(unit, "stolen", ()))


def test_ballista_placement_and_loading():
    battle, run = arena()
    hero = battle.hero
    archer = _foe(battle, "bog_archer", (5, 2))
    assert_no_commands(battle)

    placement = card(battle, "h_ballista")
    ballista = deploy(battle, placement)
    assert (ballista.cell, ballista.hp, ballista.charge, ballista.charge_max) == ((2, 2), 12, 0, 10)
    assert not battle.free(ballista.cell)
    assert not battle.los(archer.cell, hero.cell)
    assert placement in battle.discard and placement not in battle.used
    assert not any(c.cid in COMMANDS for c in run.deck)
    assert not any(c.cid in COMMANDS for c in battle.hand)

    battle.draw(2)
    assert tuple(c.cid for c in battle.hand) == COMMANDS
    assert all(c.cost == 0 and c.d.get("battle_only") for c in battle.hand)
    load, shot = battle.hand
    assert not battle.targets(shot, "main")

    put(battle, hero, (1, 5))
    assert battle.targets(load, "main") == [hero]
    energy = battle.energy
    finish(battle.play(load, "main", ballista))
    assert load in battle.hand and battle.energy == energy
    assert ballista.charge == 0
    put(battle, hero, (1, 2))
    assert battle.targets(load, "main") == [hero, ballista]
    finish(battle.play(load, "main", ballista))
    assert ballista.charge == 2
    assert hero.shield == 3 and ballista.shield == 0 and battle.energy == energy


@pytest.mark.parametrize(("rounds", "load", "charges", "damage"), [(1, False, 1, 5), (0, True, 2, 8), (9, True, 10, 32)])
def test_ballista_shoots_first_enemy_in_chosen_direction(rounds, load, charges, damage):
    battle, _ = arena()
    ballista = deploy(battle)
    near = _foe(battle, "slime", (4, 2))
    near.hp = near.max_hp = 60
    far = _foe(battle, "slime", (6, 2))
    north = _foe(battle, "slime", (2, 0))
    south = _foe(battle, "slime", (2, 5))
    _foe(battle, "slime", (4, 4))
    battle.c.grid.get((2, 1)).passable = False
    battle.draw(2)
    for expected in range(1, rounds + 1):
        wait_round(battle)
        assert ballista.charge == expected
    if load:
        finish(battle.play(command(battle, "h_ballista_load"), "main", ballista))
    assert ballista.charge == charges
    if charges == 10:
        wait_round(battle)
        assert ballista.charge == 10
        assert battle.targets(command(battle, "h_ballista_load"), "main") == [battle.hero]

    shot = command(battle, "h_ballista_fire")
    assert battle.targets(shot, "main") == [near, south]
    assert next(ray for ray, victim in battle.ballista_lines() if victim is near) == [(3, 2), (4, 2)]
    energy = battle.energy
    finish(battle.play(shot, "main", far))
    finish(battle.play(shot, "main", north))
    assert shot in battle.hand and battle.energy == energy and ballista.charge == charges

    hp = near.hp
    assert battle.ballista_damage() == damage
    finish(battle.play(shot, "main", near))
    assert near.hp == hp - damage
    assert ballista.charge == 0 and shot not in battle.hand and battle.energy == energy


def test_ballista_kill_credit_and_zone_destruction():
    battle, run = arena()
    ballista = deploy(battle)
    archer = _foe(battle, "bog_archer", (5, 2))
    victim = _foe(battle, "slime", (2, 5))
    victim.hp = 1
    battle.draw(2)
    finish(battle.play(command(battle, "h_ballista_load"), "main", ballista))
    finish(battle.play(command(battle, "h_ballista_fire"), "main", victim))
    assert not victim.alive and run.kills == 1 and battle.items.kills_turn == 1

    beam = {"kind": "zone", "shape": "beam", "dmg": 7, "name": "Луч"}
    beam["cells"] = battle.zone_cells(archer, beam)
    archer.intent = beam
    assert battle.zone_hit_cells(beam) == [(4, 2), (3, 2), (2, 2)]
    hp = battle.hero.hp
    assert battle.intent_damage(archer) == 0
    finish(battle.act(archer))
    assert ballista.hp == 5 and battle.hero.hp == hp
    finish(battle.act(archer))
    assert battle.ballista is None and battle.free(ballista.cell) and run.kills == 1
    assert battle.intent_damage(archer) == 7 and battle.hero.hp == hp
    assert_no_commands(battle)


def test_ballista_locks_other_copies_until_destruction_and_redeploys():
    battle, run = arena()
    archer = _foe(battle, "bog_archer", (5, 2))
    placement = card(battle, "h_ballista")
    second = card(battle, "h_ballista")
    third = M.Card("h_ballista", run.defs)
    battle.draw_pile.append(third)
    first_ballista = deploy(battle, placement)
    first_commands = tuple(c for c in battle.draw_pile if c.cid in COMMANDS)

    assert set(battle.discard) == {placement, second, third}
    battle.draw(8)
    assert tuple(c.cid for c in battle.hand) == COMMANDS
    assert set(battle.discard) == {placement, second, third}
    assert not battle.draw_pile

    battle.hurt(first_ballista, 12, archer, "zone")
    assert not battle.ballista
    assert_no_commands(battle)
    battle.draw(8)
    assert set(battle.hand) == {placement, second, third}
    next_ballista = deploy(battle, placement)
    assert next_ballista is not first_ballista and next_ballista.charge == 0
    assert set(battle.discard) == {placement, second, third}
    battle.draw(8)
    assert tuple(c.cid for c in battle.hand) == COMMANDS
    assert not set(first_commands) & set(battle.hand)


def test_copied_ballistas_survive_and_redeploy_independently():
    battle, _ = arena()
    foe = _foe(battle, "bog_archer", (5, 2))
    original_card = card(battle, "h_ballista")
    copied_card = copied_placement(battle)
    other_copy = copied_placement(battle)
    original = deploy(battle, original_card)
    copied = deploy(battle, copied_card, (1, 3))
    extra = deploy(battle, other_copy, (1, 1))
    assert battle.ballista is original and battle.ballistas == [original, copied, extra]
    assert all(unit.hp == 12 and unit.charge == 0 for unit in battle.ballistas)
    assert all(battle.ballista_locked(c) for c in (original_card, copied_card, other_copy))
    battle.hurt(copied, 5, foe, "zone")
    assert [unit.hp for unit in battle.ballistas] == [12, 7, 12]

    wait_round(battle)
    assert all(unit.charge == 1 for unit in battle.ballistas)
    assert len(battle.hand) == 5 and len(battle.draw_pile) == 1
    commands = battle.hand + battle.draw_pile
    copied_commands = {c for c in commands if c.ballista_owner is copied}
    survivor_commands = {c for c in commands if c.ballista_owner is not copied}
    assert len(copied_commands) == 2 and len(survivor_commands) == 4

    battle.hurt(copied, 7, foe, "zone")
    assert battle.ballistas == [original, extra] and set(battle.hand + battle.draw_pile) == survivor_commands
    assert battle.ballista_locked(original_card) and not battle.ballista_locked(copied_card)
    battle.draw(8)
    assert copied_card in battle.hand and original_card not in battle.hand and other_copy not in battle.hand
    battle.energy = 12
    recreated = deploy(battle, copied_card, (1, 3))
    assert recreated is not copied and recreated.hp == 12 and recreated.charge == 0
    battle.draw(2)
    assert not copied_commands & set(battle.hand)

    battle.hurt(original, 12, foe, "zone")
    assert battle.ballista is extra and battle.ballistas == [extra, recreated]
    battle.draw(8)
    assert original_card in battle.hand and copied_card not in battle.hand
    assert deploy(battle, original_card).hp == 12


@pytest.mark.parametrize("explicit", [True, False])
def test_ballista_commands_can_target_any_installation(explicit):
    battle, _ = arena()
    foe = _foe(battle, "slime", (2, 3))
    foe.hp = foe.max_hp = 40
    flank = _foe(battle, "slime", (1, 5))
    first = deploy(battle)
    second = deploy(battle, copied_placement(battle), (1, 3))
    battle.draw(4)
    first_load = command(battle, "h_ballista_load", first)
    second_load = command(battle, "h_ballista_load", second)
    assert battle.targets(first_load, "main") == [battle.hero, first, second]
    finish(battle.play(first_load, "main", second))
    finish(battle.play(second_load, "main", first))
    assert first.charge == second.charge == 2

    shot = command(battle, "h_ballista_fire", first)
    assert battle.targets(shot, "main") == [foe, flank]
    assert battle.ballista_shooters(foe) == [first, second]
    assert battle.ballista_shooters(flank) == [second]
    finish(battle.play(shot, "main", BallistaShot(first, flank)))
    assert shot in battle.hand and first.charge == second.charge == 2
    finish(battle.play(shot, "main", BallistaShot(second, foe) if explicit else foe))
    assert foe.hp == 32
    assert (first.charge, second.charge) == ((2, 0) if explicit else (0, 2))

    battle.hurt(first, 12, foe, "zone")
    assert shot not in battle.used and first_load not in battle.used
    assert second_load in battle.used and battle.ballista is second
    assert command(battle, "h_ballista_fire", second) in battle.hand


def test_beam_stops_at_closest_ballista_and_blast_hits_both():
    battle, _ = arena()
    foe = _foe(battle, "bog_archer", (5, 2))
    first = deploy(battle)
    put(battle, battle.hero, (4, 2))
    second = deploy(battle, copied_placement(battle), (3, 2))
    put(battle, battle.hero, (1, 2))
    beam = {"kind": "zone", "shape": "beam", "dmg": 7, "name": "Луч"}
    beam["cells"] = battle.zone_cells(foe, beam)
    foe.intent = beam
    assert battle.zone_hit_cells(beam) == [(4, 2), (3, 2)]
    finish(battle.act(foe))
    assert (first.hp, second.hp) == (12, 5)

    foe.intent = {"kind": "zone", "dmg": 5, "name": "Взрыв", "cells": [first.cell, second.cell]}
    finish(battle.act(foe))
    assert battle.ballistas == [first] and first.hp == 7 and not second.alive


@pytest.mark.parametrize("storage", [*PILES, "stolen"])
def test_ballista_commands_are_removed_from_combat_storage(storage):
    battle, _ = arena()
    archer = _foe(battle, "bog_archer", (5, 2))
    ballista = deploy(battle)
    load = battle.draw_pile.pop()
    assert load.cid == "h_ballista_load"
    if storage == "stolen":
        archer.stolen = [load]
    else:
        getattr(battle, storage).append(load)

    battle.hurt(ballista, 12, archer, "zone")
    assert_no_commands(battle)


def test_ballista_destroyed_at_end_of_turn_removes_commands_before_draw():
    battle, _ = arena()
    archer = _foe(battle, "bog_archer", (5, 2))
    placement = card(battle, "h_ballista")
    ballista = deploy(battle, placement)
    battle.draw(1)
    finish(battle.play(command(battle, "h_ballista_load"), "main", ballista))
    archer.intent = {"kind": "zone", "name": "Обвал", "dmg": 12, "cells": [ballista.cell]}
    hp = battle.hero.hp
    finish(battle.end_turn())

    assert battle.ballista is None and battle.hero.hp == hp
    assert_no_commands(battle)
    assert placement in battle.hand


def test_battle_filters_old_ballista_commands_from_run_deck():
    battle, run = hero_battle("hunter")
    run.deck.extend(M.Card(cid, run.defs) for cid in COMMANDS)
    next_battle = Battle(battle.gd, run, battle.fight, seed=1)
    assert_no_commands(next_battle)


def test_bot_places_loads_and_fires_ballista():
    battle, _ = arena()
    foe = _foe(battle, "slime", (7, 2))
    foe.intent = {"kind": "block", "n": 3, "name": "Защита"}
    card(battle, "h_ballista")

    assert bot.step_once(battle)
    assert battle.ballista.cell == (2, 2)
    battle.draw(2)
    assert bot.step_once(battle)
    assert battle.ballista.charge == 2 and battle.hero.shield == 3
    hp = foe.hp
    assert bot.step_once(battle)
    assert battle.ballista.charge == 0 and foe.hp == hp - 8
