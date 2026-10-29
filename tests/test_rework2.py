"""Партия 2 переработки героев: Ловчий, Криомант, Некромант, Хрономант, «Раздуть» Пироманта."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_rework1 import DATA, battle, cast, events, foe, hero, put, run  # noqa: E402
from sim.teams import ENEMY  # noqa: E402


def clear_foes(c, keep=1):
    for u in c.fighters(ENEMY)[keep:]:
        u.alive = False


def test_snare_is_hidden_holds_and_exposes():
    c = battle(["trapper", "warrior", "archer", "mage"])
    tr, f = hero(c, "trapper"), foe(c)
    clear_foes(c)
    put(tr, (1, 2))
    put(f, (6, 2))
    cast(c, tr, "snare", (4, 2))
    assert c.traps_of(tr) == [(4, 2)]
    assert c._danger(f, (4, 2)) == 0                 # враг капкан не видит и не обходит
    hp = f.hp
    c._place(f, (4, 2), 0.01)
    f.move_t = 1.0
    c.step()
    assert f.hp < hp and f.stun > 0 and f.stun_look == "trap" and "exposed" in f.buffs and tr.pp >= 1
    assert c.exposed(f, tr) and not c.traps_of(tr)


def test_snare_limit():
    c = battle(["trapper", "warrior", "archer", "mage"])
    tr = hero(c, "trapper")
    put(tr, (2, 2))
    for p in ((4, 0), (4, 1), (4, 3), (4, 4)):
        cast(c, tr, "snare", p)
    assert len(c.traps_of(tr)) == 3 and (4, 0) not in c.traps_of(tr)


def test_decoy_taunts_enemies():
    c = battle(["trapper", "warrior", "archer", "mage"])
    tr, f = hero(c, "trapper"), foe(c)
    put(tr, (1, 2))
    put(f, (6, 2))
    cast(c, tr, "lure", (5, 2))
    run(c, 1.1)
    decoy = next(u for u in c.units if u.proto_id == "decoy")
    assert f.taunted_by is decoy


def test_ice_wall_blocks_melts_and_fire_breaks():
    c = battle(["cryo", "warrior", "archer", "mage"])
    cr = hero(c, "cryo")
    put(cr, (1, 2))
    cast(c, cr, "ice_wall", (4, 2))
    walls = [u for u in c.units if u.alive and u.obj and u.owner is cr]
    assert {w.cell for w in walls} == {(4, 1), (4, 2), (4, 3)}
    c.damage(walls[0], 1, foe(c), "fire", "spell")
    assert not walls[0].alive and c.grid.get(walls[0].cell).hazard == "ice"
    run(c, 10.5)
    assert not any(w.alive for w in walls)


def test_rink_makes_ice_and_push_slides():
    c = battle(["cryo", "ram", "archer", "mage"])
    cr, ram, f = hero(c, "cryo"), hero(c, "ram"), foe(c)
    clear_foes(c)
    put(cr, (0, 0))
    put(ram, (2, 2))
    put(f, (3, 2))
    cast(c, cr, "rink", (4, 2))
    assert c.grid.get((4, 2)).terrain == "ice_floor"
    cast(c, ram, "kick", (3, 2))
    assert f.cell[0] >= 6                              # проехал по льду дальше двух клеток
    run(c, 8.5)
    assert c.grid.get((4, 2)).terrain != "ice_floor"


def test_shatter_hurts_enemies_near_walls():
    c = battle(["cryo", "warrior", "archer", "mage"])
    cr, f = hero(c, "cryo"), foe(c)
    put(cr, (1, 2))
    cast(c, cr, "ice_wall", (4, 2))
    put(f, (5, 2))
    hp = f.hp
    cast(c, cr, "shatter", cr)
    assert f.hp < hp and not any(u.alive for u in c.units if u.obj and u.owner is cr)


def test_corpses_blast_raise_devour():
    c = battle(["necro", "warrior", "archer", "mage"])
    nc, f, g = hero(c, "necro"), foe(c), foe(c, 1)
    put(nc, (1, 2))
    put(f, (4, 2))
    c.damage(f, 99999, None, kind="reaction")
    assert c.corpses and c.corpses[0]["cell"] == (4, 2)
    put(g, (5, 2))
    hp = g.hp
    cast(c, nc, "corpse_blast", (4, 2))
    assert g.hp < hp and not c.corpses and nc.pp >= 1
    c.damage(g, 99999, None, kind="reaction")
    cast(c, nc, "raise_dead", (5, 2))
    assert any(u.proto_id == "risen" and u.alive and u.team == nc.team for u in c.units)
    h = foe(c)
    put(h, (2, 2))
    c.damage(h, 99999, None, kind="reaction")
    cast(c, nc, "devour", nc)
    assert nc.shield > 0 and not c.corpses


def test_corpses_rot_away():
    c = battle(["necro", "warrior", "archer", "mage"])
    c.damage(foe(c), 99999, None, kind="reaction")
    run(c, DATA.config["corpse_time"] + 0.5)
    assert not c.corpses


def test_rewind_returns_cell_and_hp():
    c = battle(["chrono", "warrior", "archer", "mage"])
    ch, war = hero(c, "chrono"), hero(c, "warrior")
    put(war, (3, 2))
    run(c, 1.0)
    hp = war.hp
    run(c, 2.0)
    war.hp = 30
    put(war, (5, 4))
    cast(c, ch, "rewind", war)
    assert war.cell == (3, 2) and war.hp == hp


def test_stasis_makes_invulnerable_and_inactive():
    c = battle(["chrono", "warrior", "archer", "mage"])
    ch, f = hero(c, "chrono"), foe(c)
    cast(c, ch, "stasis", f)
    hp = f.hp
    assert c.damage(f, 50, hero(c, "warrior"), None, "melee") == 0 and f.hp == hp
    assert f.stun > 0 and f.stun_look == "stasis"
    run(c, 3.2)
    assert c.damage(f, 50, hero(c, "warrior"), None, "melee") > 0


def test_fan_flames_spreads_fire():
    c = battle(["mage", "warrior", "archer", "priest"])
    mg, f = hero(c, "mage"), foe(c)
    put(f, (6, 4))
    c.grid.get((5, 2)).hazard, c.grid.get((5, 2)).hazard_time = "fire", 3
    cast(c, mg, "fan_flames", (5, 2))
    assert c.grid.get((5, 3)).hazard == "fire" and c.grid.get((5, 1)).hazard == "fire"
    nothing = battle(["mage", "warrior", "archer", "priest"])
    cast(nothing, hero(nothing, "mage"), "fan_flames", (5, 2))
    assert events(nothing, "fizzle")
