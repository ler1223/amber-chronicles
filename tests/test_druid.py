"""Друид: форма на Q, Дикость и разные эффекты шести навыков по обликам."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim import story_meta  # noqa: E402
from sim.build import build_proto  # noqa: E402
from sim.combat import Combat  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim.teams import ENEMY  # noqa: E402

DATA = GameData()


def put(u, cell):
    u.cell = u.prev_cell = cell


def run(c, seconds):
    for _ in range(max(1, int(seconds / c.dt))):
        c.step()


def squad():
    druid = build_proto(DATA, "druid", skills=[
        "form_shift", "entangle", "rejuvenate", "wild_call", "primal_strike",
        "beast_dash", "spirit_tree", "wild_fury", "grove_awakening", "beast_pack",
    ])
    warrior = build_proto(DATA, "warrior", skills=["power_strike"])
    c = Combat(DATA, 1, squad=[{"cls": "druid", "proto": druid},
                               {"cls": "warrior", "proto": warrior}])
    c.ais = []
    c.autocaster.update = lambda dt: None
    u = next(x for x in c.heroes() if x.proto_id == "druid")
    w = next(x for x in c.heroes() if x.proto_id == "warrior")
    f = c.fighters(ENEMY)[0]
    put(u, (1, 2))
    put(w, (2, 2))
    put(f, (3, 2))
    w.attack_timer = w.atk_cd = 999.0
    u.ap = 60
    return c, u, w, f


def test_form_shift_is_first_and_cycles_forms():
    assert story_meta.battle_skills(DATA, "druid", {"skill_loadout": ["entangle", "rejuvenate", "wild_call"],
                                                    "rpg": {"level": 1}})[0] == "form_shift"
    c, u, _w, _f = squad()
    u.pp = 3
    c._resolve_skill(u, "form_shift", u)
    assert u.form == "bear" and u.pp == 0
    u.pp = 3
    c._resolve_skill(u, "form_shift", u)
    assert u.form == "wolf"
    u.pp = 3
    c._resolve_skill(u, "form_shift", u)
    assert u.form is None


def test_three_skills_fill_the_gauge():
    c, u, _w, f = squad()
    u.pp = 0
    for _ in range(3):
        u.cooldowns.clear()
        c._resolve_skill(u, "primal_strike", f)
        run(c, 0.7)
    assert u.pp == 3


def test_roots_change_with_form():
    c, u, _w, f = squad()
    # Человек: контроль.
    c._resolve_skill(u, "entangle", f.cell)
    run(c, 0.7)
    assert f.stun > 0
    f.stun = 0.0
    # Медведь: вытягивание жизни.
    c.set_form(u, "bear")
    u.hp = u.max_hp // 2
    hp = u.hp
    c._resolve_skill(u, "entangle", f.cell)
    run(c, 0.7)
    assert u.hp > hp
    # Волк: кровотечение.
    c.set_form(u, "wolf")
    c._resolve_skill(u, "entangle", f.cell)
    run(c, 0.7)
    assert "bleed" in f.statuses


def test_six_skills_resolve_in_every_form():
    c, u, _w, f = squad()
    sids = ("entangle", "rejuvenate", "wild_call", "primal_strike", "beast_dash", "spirit_tree")
    for form in (None, "bear", "wolf"):
        c.set_form(u, form)
        for sid in sids:
            u.ap = 60
            u.cooldowns.clear()
            sk = u.skill_defs[sid]
            target = f if sk["target"] == "enemy" else (u if sk["target"] == "self" else f.cell)
            c._resolve_skill(u, sid, target)
            run(c, 0.4)
