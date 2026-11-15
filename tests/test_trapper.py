"""Ловчий: метка добычи, новые капканы, собака и добивание."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_characters import setup  # noqa: E402
from test_rework1 import DATA, events, put, run  # noqa: E402
from sim.build import build_proto  # noqa: E402
from sim.combat import Combat  # noqa: E402


def test_trap_applies_prey_mark_and_exposed():
    c, h, foes = setup("trapper", ["snare"])
    f = foes[0]
    put(h, (2, 2))
    put(f, (4, 2))
    c._resolve_skill(h, "snare", (3, 2))
    c._place(f, (3, 2), 0.01)
    f.move_t = 1.0
    c.step()
    assert "prey" in f.marks
    assert f.marks["prey"]["prey_type"] == "base"
    assert f.buffs["exposed"][0] > 1.0
    assert h.pp >= 1


def test_net_trap_marks_and_holds_enemy():
    c, h, foes = setup("trapper", ["trap_net"])
    f = foes[0]
    put(h, (2, 2))
    put(f, (4, 2))
    c._resolve_skill(h, "trap_net", (3, 2))
    c._place(f, (3, 2), 0.01)
    f.move_t = 1.0
    c.step()
    assert "prey" in f.marks and f.stun_look == "net"
    assert c.grid.get((3, 2)).hazard is None


def test_dog_spawns_with_the_trapper():
    c, h, foes = setup("trapper", ["snare"])
    dog = next(u for u in c.units if u.alive and u.proto_id == "hunting_dog")
    assert dog.owner is h and dog.summon


def test_prey_mark_archetype_multipliers():
    c, h, foes = setup("trapper", ["hunter_mark"])
    f = foes[0]
    h.mark_type = "own"
    h.mark_tier = 2
    c.apply_effects(h, [{"type": "prey_mark"}], f.cell, f)
    assert f.marks["prey"]["prey_type"] == "own"
    assert f.marks["prey"]["tier"] == 2


def test_hunter_ambush_stealth_survives_attacks():
    c, h, foes = setup("trapper", ["hunter_ambush"])
    h.ap = h.ap_max
    c._resolve_skill(h, "hunter_ambush", h)
    run(c, 0.1)
    assert "stealth" in h.buffs and "veil" in h.buffs
    h.attack_timer = 0
    c._basic_attack(h, foes[0])
    run(c, 0.2)
    assert "stealth" in h.buffs and "veil" in h.buffs


def test_hunter_feast_executes_a_low_marked_target():
    c, h, foes = setup("trapper", ["hunter_mark", "hunter_feast"])
    f = foes[0]
    c.apply_effects(h, [{"type": "prey_mark"}], f.cell, f)
    f.hp = max(1, int(f.max_hp * 0.2))
    h.ap = h.ap_max
    h.cooldowns.clear()
    c._resolve_skill(h, "hunter_feast", h)
    run(c, 0.8)
    assert not f.alive
    assert "prey" not in f.marks


def test_hunter_beast_buffs_and_revives_the_dog():
    proto = build_proto(DATA, "trapper", skills=["hunter_beast"])
    c = Combat(DATA, 1, squad=[{"cls": "trapper", "proto": proto}])
    c.ais = []
    c.autocaster.update = lambda dt: None
    h = next(u for u in c.heroes() if u.proto_id == "trapper")
    h.ap = h.ap_max
    c._resolve_skill(h, "hunter_beast", h)
    run(c, 0.2)
    dog = next(u for u in c.units if u.alive and u.proto_id == "hunting_dog")
    assert dog.owner is h
    assert dog.buffs["atk_mult"][0] == 1.5
    assert dog.buffs["atk_speed"][0] == 0.77
    assert dog.prey_hunter_until > c.time
