"""Ассасин: Q-исчезновение, стаки скрытности и синергия остальных навыков."""
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


def squad(branch="D"):
    assassin = build_proto(
        DATA, "assassin",
        skills=["vanish", "backstab", "venom_darts", "smoke_bomb", "shadow_mark", "bloodletting", "assassin_decoy"],
        branches={"vanish": (branch, 1)},
    )
    warrior = build_proto(DATA, "warrior", skills=["power_strike"])
    c = Combat(DATA, 1, squad=[{"cls": "assassin", "proto": assassin},
                               {"cls": "warrior", "proto": warrior}])
    c.ais = []
    c.autocaster.update = lambda dt: None
    u = next(x for x in c.heroes() if x.proto_id == "assassin")
    w = next(x for x in c.heroes() if x.proto_id == "warrior")
    f = c.fighters(ENEMY)[0]
    put(u, (1, 2))
    put(w, (2, 2))
    put(f, (4, 2))
    w.attack_timer = w.atk_cd = 999.0
    u.ap = 20
    return c, u, w, f


def test_q_is_first_and_has_four_branches():
    assert story_meta.battle_skills(DATA, "assassin", {"skill_loadout": ["backstab", "venom_darts", "smoke_bomb"],
                                                      "rpg": {"level": 1}})[0] == "vanish"
    assert set(DATA.branches["vanish"]) == {"A", "B", "C", "D"}


def test_vanish_spends_all_stealth_stacks():
    c, u, _w, _f = squad("D")
    u.pp = 3
    assert c.check_skill(u, "vanish", u)[0]
    c._resolve_skill(u, "vanish", u)
    run(c, 0.2)
    assert u.pp == 0 and u.buff("stealth", 0) > 0
    assert 2.7 <= u.buffs["stealth"][1] <= 3.1


def test_vanish_requires_a_stack():
    c, u, _w, _f = squad("D")
    u.pp = 0
    ok, why = c.check_skill(u, "vanish", u)
    assert not ok and "скрыт" in why.lower()


def test_vanish_slide_moves_and_leaves_fog():
    c, u, _w, _f = squad("B")
    u.pp = 2
    c._resolve_skill(u, "vanish", (3, 2))
    run(c, 1.0)
    assert u.cell == (3, 2)
    assert c.grid.get((1, 2)).hazard == "fog"


def test_backstab_generates_stealth_stack():
    c, u, w, f = squad("D")
    f.order = {"type": "attack", "target": w}
    f.last_target = w
    u.pp = 0
    c._resolve_skill(u, "backstab", f)
    run(c, 1.0)
    assert u.pp >= 1


def test_mark_increases_backstab_damage():
    c, u, w, f = squad("D")
    f.order = {"type": "attack", "target": w}
    f.last_target = w
    u.pp = 0
    c._resolve_skill(u, "shadow_mark", f)
    run(c, 1.0)
    hp = f.hp
    c._resolve_skill(u, "backstab", f)
    run(c, 1.0)
    assert f.hp < hp


def test_new_assassin_skills_resolve():
    c, u, _w, f = squad("D")
    for sid, target in (("venom_darts", f), ("bloodletting", f), ("assassin_decoy", (3, 2))):
        u.ap = 20
        u.cooldowns.clear()
        c._resolve_skill(u, sid, target)
        run(c, 0.6)
