"""Партии 3–4: Гравитомант, Геомант, Зельевар, Берсерк крови, Тактик, Связующий."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_rework1 import DATA, battle, cast, events, foe, hero, put, run  # noqa: E402
from sim.build import build_proto  # noqa: E402
from sim.combat import Combat  # noqa: E402
from sim.teams import ENEMY  # noqa: E402
from test_rework1 import quiet  # noqa: E402


def only(c, n=1):
    for u in c.fighters(ENEMY)[n:]:
        u.alive = False
    return c.fighters(ENEMY)


def test_singularity_gathers_enemies():
    c = battle(["gravity", "warrior", "archer", "mage"])
    g = hero(c, "gravity")
    a, b = only(c, 2)
    put(a, (5, 0))
    put(b, (7, 4))
    cast(c, g, "singularity", (6, 2))
    assert max(abs(a.cell[0] - 6), abs(a.cell[1] - 2)) <= 1 and max(abs(b.cell[0] - 6), abs(b.cell[1] - 2)) <= 1
    assert g.pp >= 1


def test_swap_and_levitate_push():
    c = battle(["gravity", "ram", "archer", "mage"])
    g, ram = hero(c, "gravity"), hero(c, "ram")
    (f,) = only(c)
    put(g, (1, 2))
    put(f, (6, 2))
    cast(c, g, "swap", f)
    assert g.cell == (6, 2) and f.cell == (1, 2)
    put(g, (0, 5))
    put(f, (4, 0))
    put(ram, (3, 0))
    cast(c, g, "levitate", f)
    assert f.stun_look == "levitate"
    cast(c, ram, "kick", (4, 0))
    assert f.cell[0] >= 8                              # пинок по невесомому — на 2 клетки дальше
    hp = f.hp
    run(c, 3.2)
    assert f.hp < hp and events(c, "land")


def test_geomancer_effect_depends_on_ground():
    c = battle(["geomancer", "warrior", "archer", "mage"])
    gm = hero(c, "geomancer")
    (f,) = only(c)
    put(gm, (1, 2))
    put(f, (4, 2))
    c.grid.get((1, 2)).terrain = "grass"
    cast(c, gm, "earth_power", f)
    assert f.stun_look == "root"
    f.stun = 0
    c.grid.get((1, 2)).terrain = "stone"
    hp = f.hp
    cast(c, gm, "earth_power", f)
    assert hp - f.hp >= 20 and f.stun <= 0 and gm.pp >= 1


def test_reshape_cycles_ground_and_rockfall_places_boulder():
    c = battle(["geomancer", "warrior", "archer", "mage"])
    gm = hero(c, "geomancer")
    put(gm, (1, 2))
    c.grid.get((1, 2)).terrain = "grass"
    cast(c, gm, "reshape", gm)
    assert c.grid.get((1, 2)).terrain == "water"
    cast(c, gm, "reshape", gm)
    assert c.grid.get((1, 2)).terrain == "stone"
    cast(c, gm, "rockfall", (4, 0))
    assert any(u.alive and u.proto_id == "boulder" and u.owner is gm for u in c.units)


def test_brewer_coat_flask_reagent():
    c = battle(["brewer", "warrior", "archer", "mage"])
    br, war = hero(c, "brewer"), hero(c, "warrior")
    (f,) = only(c)
    cast(c, br, "coat", war)
    assert war.buff("atk_tag", None) == "fire"
    put(f, (5, 2))
    cast(c, br, "flask", (5, 2))
    f.statuses["poison"] = 3.0
    hp = f.hp
    cast(c, br, "reagent", f)
    assert "water" in f.statuses and hp - f.hp >= 20 - f.armor


def test_bloodrager_pays_hp_and_hits_harder_when_hurt():
    c = battle(["bloodrager", "warrior", "archer", "mage"])
    bl = hero(c, "bloodrager")
    (f,) = only(c)
    put(bl, (4, 2))
    put(f, (5, 2))
    hp = bl.hp
    bl.order = {"type": "skill", "skill": "blood_strike", "target": f}
    c._start_cast(bl, "blood_strike", f)
    assert any(e["t"] == "damage" and e["kind"] == "hp_cost" and e["unit"] is bl for e in c.events)
    assert c.blood_mult(bl) == 1.0 or bl.hp < bl.max_hp
    bl.hp = bl.max_hp // 5
    assert c.blood_mult(bl) > 1.5


def test_trance_turns_heal_into_rage():
    c = battle(["bloodrager", "priest", "archer", "mage"])
    bl = hero(c, "bloodrager")
    cast(c, bl, "trance", bl)
    bl.hp = 50
    c.heal(bl, 40)
    assert bl.hp == 50 and bl.buff("atk_mult", 1) > 1.3


def test_tactician_orders():
    c = battle(["tactician", "warrior", "archer", "mage"])
    tc, war, arch = hero(c, "tactician"), hero(c, "warrior"), hero(c, "archer")
    (f,) = only(c)
    put(war, (4, 2))
    put(f, (5, 2))
    war.attack_timer = 5.0
    cast(c, tc, "forward", war)
    assert any(e["t"] == "attack" and e["src"] is war for e in c.events)
    cast(c, tc, "regroup", (2, 0))
    assert any(u.cell == (2, 0) for u in c.heroes())
    cast(c, tc, "focus", f)
    assert arch.order and arch.order["target"] is f and f.buff("dmg_taken", 1) > 1
    run(c, 1.1)
    assert war.buff("armor", 0) >= 1 or tc.buff("armor", 0) >= 1     # знамя: аура брони


def test_tether_splits_damage_and_merge_hides_binder():
    c = battle(["binder", "warrior", "archer", "mage"])
    bd, war = hero(c, "binder"), hero(c, "warrior")
    cast(c, bd, "tether", war)
    hw, hb = war.hp, bd.hp
    c.damage(war, 40, foe(c), None, "spell")
    assert hb - bd.hp > 10 and hw - war.hp < 40
    cast(c, bd, "merge", bd)
    assert bd.merged > 0 and bd not in c.foes_of(foe(c))
    run(c, 6.3)
    assert bd.merged <= 0 and c.grid.in_bounds(bd.cell)
    hb, hw = bd.hp, war.hp
    cast(c, bd, "life_transfer", war)
    assert bd.hp < hb


def test_every_new_class_builds_with_both_paths():
    for cid in ("gravity", "geomancer", "brewer", "bloodrager", "tactician", "binder"):
        for pid, p in DATA.paths.items():
            if p["class"] == cid:
                proto = build_proto(DATA, cid, path=pid)
                c = quiet(Combat(DATA, 1, squad=[{"cls": cid, "proto": proto}]))
                run(c, 0.5)


def test_singularity_pulls_barrels_too():
    c = battle(["gravity", "warrior", "archer", "mage"])
    g = hero(c, "gravity")
    only(c, 0)
    keg = c.spawn_object("barrel_powder", (8, 1))
    rock = c.spawn_object("boulder", (4, 4))
    cast(c, g, "singularity", (6, 2))
    assert keg.cell != (8, 1) and max(abs(keg.cell[0] - 6), abs(keg.cell[1] - 2)) <= 1
    assert rock.cell != (4, 4)
