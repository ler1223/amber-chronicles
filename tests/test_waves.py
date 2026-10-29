"""Этап 0 длинных боёв: волны и передышка, цели боя, объекты и столкновения, личные шкалы."""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.combat import ENEMY, NEUTRAL, PLAYER, Combat  # noqa: E402
from sim.data import GameData  # noqa: E402

DATA = GameData()


def combat_with(**enc_changes):
    """Бой «Трясина» (0) с изменённым описанием: волны, цель, объекты."""
    data = copy.copy(DATA)
    data.encounters = copy.deepcopy(DATA.encounters)
    data.encounters[0].update(copy.deepcopy(enc_changes))
    return Combat(data, 0)


def run(c, seconds):
    for _ in range(int(seconds / c.dt)):
        c.step()


def events(c, kind):
    return [e for e in c.events if e["t"] == kind]


def kill_all(c, team=ENEMY):
    for u in c.fighters(team):
        c.damage(u, 99999, None, kind="reaction")


def test_hp_mult_applies_to_heroes_and_enemies():
    with open(os.path.join(os.path.dirname(__file__), "..", "data", "classes.json"), encoding="utf-8") as f:
        raw = json.load(f)
    k = DATA.config["hp_mult"]
    assert DATA.classes["warrior"]["hp"] == round(raw["warrior"]["hp"] * k)


# ---------- волны ----------

WAVE2 = [[{"type": "slime", "pos": [9, 0]}, {"type": "slime", "pos": [9, 5]}]]


def test_wave_cleared_starts_intermission_then_next_wave():
    c = combat_with(waves=WAVE2)
    assert c.wave_total == 2
    kill_all(c)
    c.step()
    assert c.intermission > 0 and c.result is None
    assert c.next_wave_preview() == [("slime", (9, 0)), ("slime", (9, 5))]
    run(c, c.cfg["waves"]["intermission"] + 0.2)
    assert c.wave == 2 and len(c.fighters(ENEMY)) == 2
    kill_all(c)
    c.step()
    assert c.result == "victory"


def test_intermission_freezes_resources():
    c = combat_with(waves=WAVE2)
    hero = c.heroes()[2]
    kill_all(c)
    c.step()
    hero.ap = 1
    hero.cooldowns["x"] = 3.0
    hero.hp -= 30
    hero.statuses["fire"] = 2.0
    hp, ap = hero.hp, hero.ap
    run(c, 3.0)
    assert c.intermission > 0
    assert hero.ap == ap and hero.cooldowns["x"] == 3.0 and hero.hp == hp and hero.statuses["fire"] == 2.0


def test_heroes_move_during_intermission_and_wave_can_be_called():
    c = combat_with(waves=WAVE2)
    kill_all(c)
    c.step()
    hero = c.heroes()[0]
    goal = (hero.cell[0] + 2, hero.cell[1])
    assert c.order_move(hero, goal)[0]
    run(c, 2.5)
    assert hero.cell == goal
    c.call_wave()
    c.step()
    c.step()
    assert c.wave == 2 and c.intermission == 0


def test_wave_timeout_brings_next_wave_without_pause():
    c = combat_with(waves=WAVE2, wave_timeout=1.0)
    n = len(c.fighters(ENEMY))
    run(c, 1.2)
    assert c.wave == 2 and c.intermission == 0 and len(c.fighters(ENEMY)) >= n


# ---------- цели боя ----------

def test_hold_point_wins_when_held():
    c = combat_with(objective={"type": "hold", "cells": [[1, 1], [1, 2], [2, 1], [2, 2]], "time": 2.0})
    for u in c.fighters(ENEMY):          # враги далеко и не мешают
        u.static = True
    hero = c.heroes()[0]
    hero.cell = hero.prev_cell = (1, 1)
    run(c, 2.3)
    assert c.result == "victory"


def test_hold_point_stalls_when_enemy_inside():
    c = combat_with(objective={"type": "hold", "cells": [[1, 1], [1, 2]], "time": 2.0})
    hero = c.heroes()[0]
    hero.cell = hero.prev_cell = (1, 1)
    foe = c.fighters(ENEMY)[0]
    foe.cell = foe.prev_cell = (1, 2)
    foe.static = True
    c.ais = []
    c._objective_update(1.0)
    assert c.hold == 0
    assert c.result is None


def test_defend_lost_object_is_defeat():
    c = combat_with(objects=[{"type": "cart", "pos": [3, 2]}], objective={"type": "defend"})
    cart = c.guards()[0]
    assert cart.team == PLAYER and cart not in c.heroes()
    c.damage(cart, 9999, c.fighters(ENEMY)[0], kind="melee")
    c.step()
    assert c.result == "defeat"


def test_half_of_enemies_go_for_guarded_object():
    c = combat_with(objects=[{"type": "cart", "pos": [5, 2]}], objective={"type": "defend"})
    cart = c.guards()[0]
    assert all(cart not in c.foes_of(f) for f in c.fighters(ENEMY))   # сам по себе обоз не цель
    run(c, 0.5)
    hunters = [f for f in c.fighters(ENEMY) if f.order and f.order.get("target") is cart]
    assert hunters and len(hunters) < len(c.fighters(ENEMY))


def test_source_spawns_until_destroyed():
    c = combat_with(objects=[{"type": "nest", "pos": [8, 3], "spawn": ["slime"]}], objective={"type": "destroy"})
    nest = next(u for u in c.units if u.obj)
    run(c, nest.obj["source"]["every"] + 0.2)
    spawned = [e["unit"] for e in events(c, "source_spawn")]
    assert len(spawned) == 1 and spawned[0].team == ENEMY and nest.spawned == spawned
    kill_all(c)
    c.step()
    assert c.result is None                 # источник ещё цел
    c.damage(nest, 9999, c.heroes()[0], kind="melee")
    c.step()
    assert c.result == "victory"


# ---------- объекты и столкновения ----------

def test_powder_barrel_explodes_from_fire_and_hurts_neighbours():
    c = combat_with(objects=[{"type": "barrel_powder", "pos": [5, 0]}])
    barrel = next(u for u in c.units if u.obj)
    assert barrel.team == NEUTRAL
    foe = c.fighters(ENEMY)[0]
    foe.cell = foe.prev_cell = (6, 0)
    hp = foe.hp
    c.damage(barrel, 1, c.heroes()[2], "fire", "spell")
    assert not barrel.alive and foe.hp < hp
    assert events(c, "object_break")


def test_barrel_chain_reaction():
    c = combat_with(objects=[{"type": "barrel_powder", "pos": [5, 0]}, {"type": "barrel_powder", "pos": [6, 0]}])
    a, b = [u for u in c.units if u.obj]
    c.damage(a, 999, None, kind="melee")
    assert not a.alive and not b.alive


def test_neutral_objects_are_not_auto_targets():
    c = combat_with(objects=[{"type": "boulder", "pos": [4, 0]}])
    boulder = next(u for u in c.units if u.obj)
    hero = c.heroes()[0]
    assert boulder not in c.foes_of(hero)
    assert c.order_attack(hero, boulder)[0]         # но по приказу бить можно


def test_knockback_into_wall_is_collision():
    c = combat_with()
    foe = c.fighters(ENEMY)[0]
    foe.cell = foe.prev_cell = (9, 2)
    hp = foe.hp
    c.knockback((8, 2), foe, 2)
    col = DATA.config["collision"]
    assert hp - foe.hp == col["base"] + col["per_cell"]
    assert events(c, "collision")


def test_knockback_into_unit_hurts_both():
    c = combat_with()
    a, b = c.fighters(ENEMY)[:2]
    a.cell = a.prev_cell = (6, 0)
    b.cell = b.prev_cell = (7, 0)
    ha, hb = a.hp, b.hp
    c.knockback((5, 0), a, 1)
    assert a.hp == ha - DATA.config["collision"]["base"]
    assert hb - b.hp == round(DATA.config["collision"]["base"] * 0.5)


def test_pushed_powder_barrel_explodes_on_impact():
    c = combat_with(objects=[{"type": "barrel_powder", "pos": [5, 0]}])
    barrel = next(u for u in c.units if u.obj)
    foe = c.fighters(ENEMY)[0]
    foe.cell = foe.prev_cell = (7, 0)
    hp = foe.hp
    c.knockback((4, 0), barrel, 3, c.heroes()[0])
    assert not barrel.alive and foe.hp < hp


def test_heavy_boulder_moves_one_less():
    c = combat_with(objects=[{"type": "boulder", "pos": [4, 0]}])
    boulder = next(u for u in c.units if u.obj)
    c.knockback((3, 0), boulder, 2)
    assert boulder.cell == (5, 0)


def test_objects_block_paths():
    c = combat_with(objects=[{"type": "boulder", "pos": [5, 5]}])
    boulder = next(u for u in c.units if u.obj)
    hero = c.heroes()[0]
    hero.cell = hero.prev_cell = (4, 5)
    c.ais = []
    assert c.order_move(hero, (6, 5))[0]
    run(c, 4.0)
    assert hero.cell == (6, 5) and boulder.cell == (5, 5)


def test_object_gives_cover_from_shots():
    c = combat_with(objects=[{"type": "boulder", "pos": [5, 2]}])
    foe = c.fighters(ENEMY)[0]
    foe.cell = foe.prev_cell = (6, 2)
    foe.armor = 0
    archer = c.heroes()[1]
    archer.cell = archer.prev_cell = (1, 2)
    archer.pp = 0
    dealt = c.damage(foe, 20, archer, None, "ranged")
    assert dealt == round(20 * DATA.config["cover"]["full"])


# ---------- личные шкалы ----------

def test_hero_gauge_starts_empty_enemy_full():
    c = combat_with()
    assert all(h.pp == 0 for h in c.heroes())
    boss = Combat(DATA, next(i for i, e in enumerate(DATA.encounters) if e["id"] == "forge_9"))
    b = next(u for u in boss.fighters(ENEMY) if u.boss)
    assert b.pp == b.pp_max


def test_warrior_gauge_fills_from_hits_and_blocks():
    c = combat_with()
    war = next(h for h in c.heroes() if h.proto_id == "warrior")
    c.damage(war, 20, None, None, "melee")
    assert war.pp == 1
    hp = war.hp
    c.damage(war, 20, None, None, "melee")
    assert war.pp == 0 and hp - war.hp < 20 - war.armor     # второй удар — в блок


def test_archer_gauge_fills_standing_still():
    c = combat_with()
    c.ais = []
    archer = next(h for h in c.heroes() if h.proto_id == "archer")
    run(c, 2.1)
    assert archer.pp >= 1


def test_gauge_survives_intermission():
    c = combat_with(waves=WAVE2)
    war = c.heroes()[0]
    war.pp = 1
    kill_all(c)
    c.step()
    run(c, 2.0)
    assert war.pp == 1


# ---------- фазы босса ----------

def test_boss_phase_spawns_adds():
    i = next(i for i, e in enumerate(DATA.encounters) if e["id"] == "witch")
    data = copy.copy(DATA)
    data.encounters = copy.deepcopy(DATA.encounters)
    data.encounters[i]["phases"] = [{"at": 0.5, "name": "Ярость", "spawn": [{"type": "slime", "pos": [9, 0]}]}]
    c = Combat(data, i)
    boss = next(u for u in c.fighters(ENEMY) if u.boss)
    n = len(c.fighters(ENEMY))
    boss.hp = boss.max_hp // 3
    c.step()
    assert len(c.fighters(ENEMY)) == n + 1 and events(c, "phase")
