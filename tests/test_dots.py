"""Доты: масштабирование, стаки, вода, среда и аффиксы предметов."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.build import build_proto  # noqa: E402
from sim.combat import Combat  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim.teams import ENEMY  # noqa: E402

DATA = GameData()


def battle(classes=("warrior", "archer", "mage", "priest"), enc=1, mods=None):
    squad = [{"cls": c, "proto": build_proto(DATA, c, extra_mods=mods or ())} for c in classes]
    c = Combat(DATA, enc, squad=squad)
    c.ais = []
    c.autocaster.update = lambda dt: None
    for u in c.units:
        if u.obj:
            u.alive = False
    return c


def hero(c, cls):
    return next(u for u in c.heroes() if u.proto_id == cls)


def foe(c, n=0):
    return c.fighters(ENEMY)[n]


def run(c, seconds):
    for _ in range(int(seconds / c.dt)):
        c.step()


def test_fire_scales_from_hit_or_spell_power():
    c = battle()
    mage, enemy = hero(c, "mage"), foe(c)
    enemy.hp = enemy.max_hp = 1000
    c.apply_status(enemy, "fire", mage, hit=40)
    dot = enemy.dots["fire"]
    assert dot["dps"] == 40 * DATA.tags["fire"]["dot"]["hit_pct"]
    c._clear_dot(enemy, "fire")
    c.apply_status(enemy, "fire", mage)
    dot = enemy.dots["fire"]
    assert dot["dps"] == DATA.tags["fire"]["dot"]["spell_base"] * mage.power
    assert "fire" in enemy.statuses


def test_water_extinguishes_fire_and_wet_blocks_new_fire():
    c = battle()
    mage, enemy = hero(c, "mage"), foe(c)
    enemy.hp = enemy.max_hp = 1000
    c.apply_status(enemy, "fire", mage, hit=20)
    c._touch_status(enemy, "water", None, hostile=False)
    assert "fire" not in enemy.statuses and "fire" not in enemy.dots
    assert "water" in enemy.statuses
    c.apply_status(enemy, "fire", mage, hit=20)
    assert "fire" not in enemy.statuses and "fire" not in enemy.dots


def test_poison_stacks_and_reduces_healing():
    c = battle()
    mage, enemy = hero(c, "mage"), foe(c)
    enemy.hp = enemy.max_hp = 1000
    for _ in range(3):
        c.apply_status(enemy, "poison", mage, hit=20)
    dot = enemy.dots["poison"]
    assert dot["stacks"] == 3
    enemy.hp = 500
    healed = c.heal(enemy, 20)
    assert healed < 10


def test_bleed_explodes_at_max_stacks():
    c = battle()
    warrior, enemy = hero(c, "warrior"), foe(c)
    enemy.hp = enemy.max_hp = 1000
    for _ in range(4):
        c.apply_dot(enemy, "bleed", 5, 5, attacker=warrior)
    assert enemy.dots["bleed"]["stacks"] == 4
    hp = enemy.hp
    c.apply_dot(enemy, "bleed", 5, 5, attacker=warrior)
    assert enemy.hp < hp
    assert "bleed" not in enemy.statuses and "bleed" not in enemy.dots


def test_environment_dot_is_percent_and_typed():
    c = battle()
    enemy = foe(c)
    enemy.hp = enemy.max_hp = 200
    enemy.resist["physical"] = 0.5
    briar = DATA.config["hazards"]["briar"]
    assert c._env_amount(enemy, briar) == 4.0
    c.damage(enemy, c._env_amount(enemy, briar), None, kind="hazard",
             dtype=briar["damage_type"])
    assert enemy.hp == 198


def test_direct_status_write_keeps_legacy_dps():
    c = battle()
    enemy = foe(c)
    enemy.hp = enemy.max_hp = 1000
    enemy.statuses["fire"] = 3.0
    c._sync_dots(enemy)
    assert enemy.dots["fire"]["dps"] == DATA.tags["fire"]["dps"]
    assert enemy.dots["fire"]["dps_pct"] is None


def test_environment_status_uses_percent_damage():
    c = battle()
    enemy = foe(c)
    enemy.hp = enemy.max_hp = 1000
    c.apply_status(enemy, "fire", None, hit=0)
    assert enemy.dots["fire"]["dps"] == 0.0
    assert enemy.dots["fire"]["dps_pct"] == DATA.tags["fire"]["dot"]["env_pct"]
    run(c, 1.0)
    assert enemy.hp <= 990


def test_dot_can_scale_from_attack_percentage():
    c = battle()
    archer, enemy = hero(c, "archer"), foe(c)
    enemy.hp = enemy.max_hp = 1000
    archer.atk_damage = 100
    c.apply_status(enemy, "bleed", archer)
    cfg = DATA.tags["bleed"]["dot"]
    assert enemy.dots["bleed"]["dps"] == max(cfg["spell_base"] * archer.power,
                                             archer.atk_damage * cfg["atk_pct"])


def test_dot_duration_affix_extends_fire():
    c = battle()
    mage, enemy = hero(c, "mage"), foe(c)
    enemy.hp = enemy.max_hp = 1000
    mage.dot_duration_mult = 2.0
    c.apply_status(enemy, "fire", mage)
    assert enemy.dots["fire"]["left"] == DATA.tags["fire"]["dot"]["duration"] * 2.0


def test_dot_affixes_are_applied_to_hero():
    proto = build_proto(DATA, "mage", extra_mods=[
        {"stat": "dot_mult", "mult": 1.2},
        {"stat": "dot_fire_mult", "mult": 1.5},
        {"stat": "dot_duration_mult", "mult": 1.5},
    ])
    assert proto["dot_mult"] == 1.2
    assert proto["dot_fire_mult"] == 1.5
    assert proto["dot_duration_mult"] == 1.5
