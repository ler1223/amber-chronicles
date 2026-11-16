"""Некромант: полный пул, трупы, души, костяной контроль и призывы."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.build import build_proto  # noqa: E402
from sim.combat import Combat  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim.teams import ENEMY  # noqa: E402

DATA = GameData()
SKILLS = ["corpse_blast", "raise_dead", "devour", "soul_lance", "corpse_cloud",
          "bone_grip", "bone_wall", "rot", "blood_bones", "grave_tide",
          "last_call", "soul_harvest", "bone_colossus"]


def battle():
    p = build_proto(DATA, "necro", skills=SKILLS)
    c = Combat(DATA, 1, squad=[{"cls": "necro", "proto": p}])
    c.ais = []
    c.autocaster.update = lambda dt: None
    return c, c.heroes()[0]


def put(u, cell):
    u.cell = u.prev_cell = tuple(cell)


def run(c, sec=0.5):
    for _ in range(int(sec / c.dt)):
        c.step()


def foe(c):
    return c.fighters(ENEMY)[0]


def test_necro_pool_has_ten_regular_skills_and_three_ultimates():
    pool = DATA.story_progression["classes"]["necro"]["skills"]
    regular = [e for e in pool if not e.get("ult")]
    ults = [e for e in pool if e.get("ult")]
    assert len(regular) == 10 and len(ults) == 3
    assert {e["id"] for e in ults} == {"last_call", "soul_harvest", "bone_colossus"}
    for e in pool:
        assert e["id"] in DATA.skills and e["id"] in DATA.branches
        assert len(DATA.branches[e["id"]]) == 2


def test_soul_lance_spends_souls_and_hits():
    c, h = battle()
    f = foe(c)
    put(h, (1, 2))
    put(f, (5, 2))
    h.pp = 2
    hp = f.hp
    c._resolve_skill(h, "soul_lance", f)
    run(c, 0.5)
    assert h.pp == 0 and f.hp < hp


def test_bone_grip_roots_poisons_and_damages():
    c, h = battle()
    f = foe(c)
    put(h, (1, 2))
    put(f, (5, 2))
    hp = f.hp
    c._resolve_skill(h, "bone_grip", (5, 2))
    run(c, 0.7)
    assert f.hp < hp
    assert f.stun > 0 and f.stun_look == "root"
    assert "poison" in f.statuses


def test_grave_tide_leaves_a_poison_zone():
    c, h = battle()
    f = foe(c)
    put(h, (1, 2))
    put(f, (3, 2))
    c._resolve_skill(h, "grave_tide", h)
    assert c.zones and c.grid.get((3, 2)).hazard == "poison"
    hp = f.hp
    run(c, 1.1)
    assert f.hp < hp


def test_soul_harvest_spends_all_souls_and_hits_area():
    c, h = battle()
    f = foe(c)
    put(h, (1, 2))
    put(f, (3, 2))
    c.corpses = [{"cell": (4, 2), "left": 10, "name": "x"},
                 {"cell": (4, 3), "left": 10, "name": "y"},
                 {"cell": (4, 4), "left": 10, "name": "z"}]
    h.pp = 4
    hp = f.hp
    c._resolve_skill(h, "soul_harvest", h)
    run(c, 0.5)
    assert h.pp == 0 and f.hp < hp


def test_bone_colossus_raises_from_a_corpse():
    c, h = battle()
    put(h, (1, 2))
    c.corpses = [{"cell": (4, 2), "left": 10, "name": "x"},
                 {"cell": (4, 3), "left": 10, "name": "y"}]
    c._resolve_skill(h, "bone_colossus", (4, 2))
    run(c, 0.25)
    colossus = [u for u in c.units if u.alive and u.proto_id == "bone_colossus"]
    assert colossus and colossus[0].life is not None and colossus[0].life > 0
