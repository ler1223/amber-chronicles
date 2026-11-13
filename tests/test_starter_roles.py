"""Стартовая четвёрка: у каждого своя полевая роль, а не только способ наносить урон."""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim import story_meta  # noqa: E402
from sim.build import build_proto  # noqa: E402
from sim.combat import Combat  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim.teams import ENEMY  # noqa: E402

DATA = GameData()


def battle(classes):
    squad = [{"cls": c, "proto": build_proto(DATA, c, skills=DATA.classes[c]["skills"])} for c in classes]
    c = Combat(DATA, 1, squad=squad)
    c.ais = []
    c.autocaster.update = lambda dt: None
    for u in c.units:
        if u.obj:
            u.alive = False
    return c


def hero(c, cls):
    return next(u for u in c.heroes() if u.proto_id == cls)


def put(u, cell):
    u.cell = u.prev_cell = tuple(cell)


def cast(c, u, sid, target):
    c._resolve_skill(u, sid, target)


def run(c, sec):
    for _ in range(int(sec / c.dt)):
        c.step()


def test_warrior_guard_creates_protective_zone():
    c = battle(["warrior", "archer", "mage", "priest"])
    war, mage = hero(c, "warrior"), hero(c, "mage")
    put(mage, (2, 2))
    put(war, (1, 2))
    cast(c, war, "guard_ally", mage)
    run(c, 0.5)                                       # прыжок и эффект долетают
    assert c.zones and c.zones[0].get("anchor") is mage
    run(c, 1.2)
    assert mage.buff("dmg_taken", 1.0) < 1.0          # охраняемая зона ослабляет удар


def test_priest_holy_water_leaves_healing_ground():
    c = battle(["priest", "warrior", "archer", "mage"])
    pr, war = hero(c, "priest"), hero(c, "warrior")
    put(war, (3, 2))
    c.damage(war, 30, None, None, "reaction")
    cast(c, pr, "holy_water", war.cell)
    hp = war.hp
    run(c, 1.2)
    assert war.hp > hp                               # освящённая земля лечит в секунду


def test_starter_classes_have_ten_regular_skills_and_three_ults():
    for cls in ("warrior", "archer", "mage", "priest"):
        pool = story_meta.all_skills(DATA, cls)
        ults = story_meta.ults_of(DATA, cls)
        assert len([s for s in pool if s not in ults]) == 10, cls
        assert len(ults) == 3, cls


def test_starter_random_kits_reach_all_three_ults():
    for cls in ("warrior", "archer", "mage", "priest"):
        seen = {story_meta.random_kit(DATA, cls, random.Random(i))[3] for i in range(120)}
        assert seen == set(story_meta.ults_of(DATA, cls)), (cls, seen)


def test_warrior_new_effects():
    c = Combat(DATA, 1, squad=[{"cls": "warrior", "proto": build_proto(
        DATA, "warrior", skills=["power_strike", "challenge", "shield_bash", "duel_execute"])}])
    c.ais = []
    c.autocaster.update = lambda dt: None
    u, foe = c.heroes()[0], c.fighters(ENEMY)[0]
    put(u, (2, 2))
    put(foe, (3, 2))

    u.ap = 20
    c._resolve_skill(u, "power_strike", foe)
    run(c, 0.6)
    assert foe.stun > 0 and foe.buff("exposed", 1.0) > 1.0

    foe.ap, foe.skills, foe.cooldowns = 5, ["power_strike"], {}
    c._resolve_skill(u, "shield_bash", foe)
    run(c, 0.4)
    assert foe.ap <= 3 and foe.cooldowns.get("power_strike", 0) > 0

    c._resolve_skill(u, "challenge", foe)
    run(c, 0.5)
    c._resolve_skill(u, "duel_execute", foe)
    run(c, 0.5)
    assert foe.buff("heal_taken", 1.0) < 1.0


def test_ash_veil_creates_fog_with_blind_and_evasion():
    c = Combat(DATA, 1, squad=[{"cls": "mage", "proto": build_proto(DATA, "mage", skills=["ash_veil"])},
                               {"cls": "warrior", "proto": build_proto(DATA, "warrior", skills=["power_strike"])}])
    c.ais = []
    c.autocaster.update = lambda dt: None
    mage = next(u for u in c.heroes() if u.proto_id == "mage")
    war = next(u for u in c.heroes() if u.proto_id == "warrior")
    foe = c.fighters(ENEMY)[0]
    put(mage, (1, 2))
    put(war, (2, 2))
    put(foe, (4, 2))
    war.attack_timer = war.atk_cd = 999.0
    mage.attack_timer = mage.atk_cd = 999.0
    mage.ap = 20
    c._resolve_skill(mage, "ash_veil", (3, 2))
    run(c, 1.8)
    assert c.grid.get((3, 2)).hazard == "fog"
    assert war.buff("evasion", 0) > 0
    assert foe.stun > 0 and foe.stun_look == "blind"


def test_priest_kit_has_no_shields_or_attack_buffs():
    priest_skills = ("heal", "holy_water", "vow", "faith_shield", "purify", "consecrate", "judgment",
                     "sanctuary", "prayer", "blessing", "divine_light", "miracle", "revive", "sacrifice")
    for sid in priest_skills:
        text = json.dumps(DATA.skills[sid], ensure_ascii=False)
        assert '"type": "shield"' not in text, sid
        assert '"stat": "atk_mult"' not in text, sid
        if sid in DATA.branches:
            text = json.dumps(DATA.branches[sid], ensure_ascii=False)
            assert '"type": "shield"' not in text, sid
            assert '"stat": "atk_mult"' not in text, sid


def test_phoenix_grants_shield_to_revived_ally():
    c = Combat(DATA, 1, squad=[{"cls": "mage", "proto": build_proto(DATA, "mage", skills=["phoenix"])},
                               {"cls": "warrior", "proto": build_proto(DATA, "warrior", skills=["power_strike"])}])
    c.ais = []
    c.autocaster.update = lambda dt: None
    mage = next(u for u in c.heroes() if u.proto_id == "mage")
    war = next(u for u in c.heroes() if u.proto_id == "warrior")
    put(mage, (1, 2))
    put(war, (3, 2))
    war.alive, war.hp = False, 0
    mage.ap = 20
    c._resolve_skill(mage, "phoenix", (3, 2))
    run(c, 0.3)
    assert war.alive and war.shield > 0


def test_debuff_resist_shortens_control():
    c = Combat(DATA, 1, squad=[{"cls": "priest", "proto": build_proto(DATA, "priest", skills=["heal"])}])
    c.ais = []
    c.autocaster.update = lambda dt: None
    pr = c.heroes()[0]
    c.add_buff(pr, "debuff_resist", 0.5, 5)
    c.apply_stun(pr, 2.0)
    assert 0.9 < pr.stun < 1.1


def test_pyromancer_new_skills_have_effects():
    c = Combat(DATA, 1, squad=[{"cls": "mage", "proto": build_proto(
        DATA, "mage", skills=["flame_wall", "ash_veil", "flashover", "meteor", "phoenix"])}])
    c.ais = []
    c.autocaster.update = lambda dt: None
    u, foe = c.heroes()[0], c.fighters(ENEMY)[0]
    put(u, (1, 2))
    put(foe, (3, 2))
    cell = c.grid.get((3, 2))
    cell.passable, cell.terrain = True, "grass"

    u.ap = 30
    c._resolve_skill(u, "flame_wall", (3, 2))
    run(c, 0.7)
    assert cell.hazard == "fire"

    cell.hazard, cell.hazard_time = "fire", 5
    c._resolve_skill(u, "ash_veil", (3, 2))
    run(c, 0.9)
    assert cell.hazard == "fog"

    cell.hazard, cell.hazard_time = "fire", 5
    c.apply_status(foe, "fire", u, hit=10)
    c._resolve_skill(u, "flashover", (3, 2))
    run(c, 0.7)
    assert cell.blaze

    c._start_cast(u, "meteor", (3, 2))
    run(c, 2.6)
    assert any(g.hazard == "fire" for g in c.grid.cells.values())

    c._resolve_skill(u, "phoenix", (3, 2))
    run(c, 0.2)
    assert any(z.get("kind") == "phoenix" for z in c.zones)


def test_priest_branches_have_distinct_effects():
    priest = build_proto(DATA, "priest", skills=["heal", "judgment", "sanctuary", "prayer", "revive"],
                         branches={"heal": ("B", 1), "judgment": ("B", 1), "sanctuary": ("A", 1),
                                   "prayer": ("B", 1), "revive": ("A", 1)})
    c = Combat(DATA, 1, squad=[{"cls": "priest", "proto": priest},
                               {"cls": "warrior", "proto": build_proto(DATA, "warrior", skills=["power_strike"])}])
    c.ais = []
    c.autocaster.update = lambda dt: None
    pr = next(u for u in c.heroes() if u.proto_id == "priest")
    war = next(u for u in c.heroes() if u.proto_id == "warrior")
    foe = c.fighters(ENEMY)[0]
    put(pr, (1, 2))
    put(war, (2, 2))
    put(foe, (4, 2))
    war.attack_timer = war.atk_cd = 999.0
    pr.attack_timer = pr.atk_cd = 999.0

    pr.ap = 40
    war.hp = war.max_hp // 2
    hp = war.hp
    c._resolve_skill(pr, "heal", war)
    run(c, 1.2)
    assert war.hp > hp and war.buff("regen", 0) == 0

    hp = foe.hp
    c._resolve_skill(pr, "judgment", foe)
    run(c, 0.7)
    assert foe.hp == hp and foe.buff("exposed", 1.0) > 1.0

    c._resolve_skill(pr, "sanctuary", pr)
    run(c, 0.2)
    assert any(z.get("kind") == "sanctuary" for z in c.zones)

    pr.ap = 30
    c._start_cast(pr, "prayer", pr.cell)
    run(c, 1.8)
    assert pr.ap < 30 and war.buff("heal_taken", 1.0) > 1.0

    c._resolve_skill(pr, "revive", (5, 2))
    run(c, 0.7)
    assert any(u.proto_id == "spirit_healer" for u in c.units if u.alive)


def test_meteor_branches_change_the_rain():
    a = build_proto(DATA, "mage", skills=["meteor"], branches={"meteor": ("A", 1)})
    b = build_proto(DATA, "mage", skills=["meteor"], branches={"meteor": ("B", 1)})
    assert a["skill_defs"]["meteor"]["channel"]["count"] == 7
    assert b["skill_defs"]["meteor"]["channel"]["empowered"] == 1


def test_new_starter_skills_resolve():
    cases = {
        "warrior": ["last_stand", "shield_charge"],
        "archer": ["piercing_shot", "concussive_shot", "suppressing_fire"],
        "mage": ["flame_wall", "ash_veil", "flashover", "meteor", "phoenix"],
        "priest": ["prayer", "miracle", "sacrifice"],
    }
    for cls, sids in cases.items():
        c = Combat(DATA, 1, squad=[{"cls": cls, "proto": build_proto(DATA, cls, skills=sids)}])
        c.ais = []
        c.autocaster.update = lambda dt: None
        u, foe = c.heroes()[0], c.fighters(ENEMY)[0]
        for sid in sids:
            u.ap = 20
            sk = u.skill_defs[sid]
            target = foe if sk["target"] == "enemy" else (u if sk["target"] == "self" else foe.cell)
            c._resolve_skill(u, sid, target)
            run(c, 0.3)


def test_warrior_bodyguard_aura_weakens_damage_to_adjacent_ally():
    c = battle(["warrior", "archer", "mage", "priest"])
    war, arch = hero(c, "warrior"), hero(c, "archer")
    put(war, (2, 2))
    put(arch, (2, 3))
    war.pp = war.pp_max
    before = arch.hp
    c.damage(arch, 20, None, None, "melee")
    assert arch.hp > before - 20                      # соседний воин прикрыл часть удара
