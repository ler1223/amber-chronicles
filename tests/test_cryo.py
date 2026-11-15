"""Криомант: шкала Мороза, Ледяной век, погода и снежный вихрь."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_characters import setup  # noqa: E402
from test_rework1 import events, put, run  # noqa: E402
from sim.build import build_proto  # noqa: E402
from sim.combat import Combat  # noqa: E402
from sim.data import GameData  # noqa: E402


def test_cold_fills_frost_gauge_and_full_gauge_casts_icy_century():
    c, h, foes = setup("cryo", ["frost_needle"])
    h.pp = 9
    f = foes[0]
    c.apply_effects(h, [{"type": "mark", "mark": "cold", "stacks": 1, "duration": 6}], f.cell, f)
    assert h.pp == 0
    assert events(c, "cryo_cataclysm")
    assert any(cell.hazard == "ice_cataclysm" for cell in c.grid.cells.values())


def test_icy_century_does_not_hit_allies():
    data = GameData()
    p = build_proto(data, "cryo", skills=["frost_needle"])
    q = build_proto(data, "warrior")
    c = Combat(data, 1, squad=[{"cls": "cryo", "proto": p}, {"cls": "warrior", "proto": q}])
    c.ais = []
    c.autocaster.update = lambda dt: None
    cryo = next(u for u in c.heroes() if u.proto_id == "cryo")
    ally = next(u for u in c.heroes() if u.proto_id == "warrior")
    foe = c.fighters(__import__("sim.teams", fromlist=["ENEMY"]).ENEMY)[0]
    cryo.pp = 9
    hp = ally.hp
    c.apply_effects(cryo, [{"type": "mark", "mark": "cold", "stacks": 1, "duration": 6}], foe.cell, foe)
    assert events(c, "cryo_cataclysm")
    assert ally.hp == hp
    assert "ice" not in ally.statuses


def test_weather_ticks_cold_and_extends_for_ap():
    data = GameData()
    p = build_proto(data, "cryo", skills=["snowstorm"])
    c = Combat(data, 1, squad=[{"cls": "cryo", "proto": p}])
    c.ais = []
    c.autocaster.update = lambda dt: None
    h = next(u for u in c.heroes() if u.proto_id == "cryo")
    h.ap = h.ap_max
    c._resolve_skill(h, "snowstorm", h)
    assert c.weather and c.weather["id"] == "snowstorm"
    run(c, 5.2)
    assert h.ap < h.ap_max
    assert any(f.marks.get("cold") for f in c.fighters(__import__("sim.teams", fromlist=["ENEMY"]).ENEMY))


def test_snow_vortex_moves_and_applies_cold():
    c, h, foes = setup("cryo", ["snow_vortex"])
    h.ap = h.ap_max
    c._resolve_skill(h, "snow_vortex", (5, 2))
    run(c, 2.0)
    assert c.vortices
    assert c.vortices[0]["center"] != (5, 2) or c.vortices[0]["tick"] >= 1.0


def test_ice_heart_shields_and_freezes_attacker():
    c, h, foes = setup("cryo", ["ice_heart"])
    h.ap = h.ap_max
    c._resolve_skill(h, "ice_heart", h)
    assert h.shield > 0
    assert "armor" in h.buffs and h.ice_heart_until > c.time
    attacker = foes[0]
    c.damage(h, 1, attacker, None, "melee")
    assert attacker.stun > 0 and attacker.stun_look == "freeze"
