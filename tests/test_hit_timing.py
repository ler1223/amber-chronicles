"""Урон навыка и выстрела — в момент попадания: снаряд летит, площадь вспыхивает после метки."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.build import build_proto  # noqa: E402
from sim.combat import ENEMY, PLAYER, Combat  # noqa: E402
from sim.data import GameData  # noqa: E402

DATA = GameData()


def make(classes=("mage", "archer", "warrior", "priest")):
    return Combat(DATA, 0, squad=[{"cls": c, "proto": build_proto(DATA, c)} for c in classes])


def test_fireball_damage_lands_after_flight():
    c = make()
    mage = next(u for u in c.units if u.proto_id == "mage")
    foe = c.alive(ENEMY)[0]
    hp = foe.hp
    sk = mage.skill_defs["fireball"]
    delay = c.hit_delay(mage, "fireball", sk, foe.cell, foe)
    assert 0.3 <= delay <= 1.1
    c._resolve_skill(mage, "fireball", foe)
    assert foe.hp == hp                                    # ещё летит
    ev = [e for e in c.events if e["t"] == "skill"][-1]
    assert ev["hit"] == delay
    steps = 0
    while not any(e["t"] == "skill_hit" for e in c.events) and steps < 100:
        c.events.clear()
        c.step()
        steps += 1
    assert abs(steps * c.dt - delay) <= c.dt * 1.5         # попадание — ровно через время полёта
    assert any(e["t"] == "damage" and e["unit"] is foe for e in c.events)


def test_arrow_lands_after_flight_and_melee_almost_at_once():
    c = make()
    archer = next(u for u in c.units if u.proto_id == "archer")
    foe = c.alive(ENEMY)[0]
    hp = foe.hp
    c._basic_attack(archer, foe)
    assert foe.hp == hp
    for _ in range(30):
        c.step()
    assert foe.hp < hp or any(e["t"] in ("dodge",) for e in c.events)


def test_dash_and_buffs_are_instant():
    c = make(("assassin", "warrior", "mage", "priest"))
    a = next(u for u in c.units if u.proto_id == "assassin")
    sk = a.skill_defs["vanish"]
    assert c.hit_delay(a, "vanish", sk, a.cell, a) == 0.0
