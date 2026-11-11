"""Пассивки-основы классов (sim/passives.py) у героев из пула (сюжет и экспедиция)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_characters import setup  # noqa: E402
from test_rework1 import DATA, events, put, run  # noqa: E402
from sim import kit, passives as PS  # noqa: E402
from needs import need_core  # noqa: E402


def test_every_class_has_core_passive_in_pool_mode():
    for cls in DATA.classes:
        c, h, foes = setup(cls, [])
        assert PS.kind(h), cls
        assert "%" in h.passive["desc"] or "×" in h.passive["desc"] or cls in ("tactician", "bard", "chrono"), cls


def test_archer_ramp_on_same_target_and_halves_on_switch():
    c, h, foes = setup("archer", [])
    need_core("archer", "ramp")
    for _ in range(4):
        h.attack_timer = 0
        c._basic_attack(h, foes[0])
        run(c, 0.4)
    assert h.pp >= 3
    n = h.pp
    h.attack_timer = 0
    c._basic_attack(h, foes[1])
    run(c, 0.4)
    assert h.pp <= n // 2 + 1
    assert PS.atk_cd_mult(c, h) < 1.0 or h.pp == 0


def test_warrior_duel_fury_stacks_and_execute_spends():
    c, h, foes = setup("warrior", ["challenge", "duel_execute"])
    need_core("warrior", "duel_fury")
    f = foes[0]
    c._resolve_skill(h, "challenge", f)
    run(c, 0.5)
    for _ in range(3):
        c.damage(f, 5, h, None, "melee")
    assert h.pp >= 3
    assert PS.out_mult(c, h, f, "melee", None, False) > 1.2
    h.ap = h.ap_max
    c._resolve_skill(h, "duel_execute", f)
    assert h.pp == 0


def test_mage_flame_from_fire_and_flashpoint_spends():
    c, h, foes = setup("mage", ["ignite", "flashpoint"])
    need_core("mage", "inner_flame")
    c._resolve_skill(h, "ignite", foes[0])
    run(c, 1.0)
    assert h.pp >= 1
    c._resolve_skill(h, "flashpoint", h)
    assert h.pp == 0


def test_priest_faith_grows_from_healing_and_shields_allies():
    c, h, foes = setup("priest", ["heal"])
    need_core("priest", "faith")
    put(foes[0], (7, 4))
    ally = c.summon(h, {"unit": "skeleton_minion", "duration": 30}, (2, 3))
    ally.hp = 10
    c._resolve_skill(h, "heal", ally)
    run(c, 0.6)
    assert h.pp == 1
    assert PS.in_mult(c, ally, foes[0], "melee") < 1.0


def test_guardian_digs_in_standing_and_resets_on_move():
    c, h, foes = setup("guardian", [])
    need_core("guardian", "dig_in")
    for f in foes:
        put(f, (7, 4))
    run(c, 3.2)
    assert h.pp >= 3 and PS.in_mult(c, h, foes[0], "melee") < 1.0
    h.move_t = 0.0
    PS.tick(c, h, 0.05)
    assert h.pp == 0


def test_alchemist_barrel_with_powder_is_stronger():
    c, h, foes = setup("alchemist", ["powder_keg"])
    need_core("alchemist", "powder")
    h.pp = 1
    c._resolve_skill(h, "powder_keg", (5, 2))
    strong = next(o for o in c.units if o.obj and o.owner is h)
    assert strong.blast_mult == 2.0 and h.pp == 0
    h.cooldowns.clear()
    c._resolve_skill(h, "powder_keg", (5, 3))
    weak = [o for o in c.units if o.obj and o.owner is h and o is not strong][0]
    assert weak.blast_mult == 0.6


def test_bard_notes_play_melody_and_finale():
    c, h, foes = setup("bard", ["note_do", "note_mi", "note_sol", "finale"])
    need_core("bard", "notes")
    for sid in ("note_do", "note_do", "note_do"):
        h.ap = h.ap_max
        h.cooldowns.clear()
        c._resolve_skill(h, sid, h)
    assert h.last_melody == "mel_life" and events(c, "melody")
    h.ap = h.ap_max
    assert c.check_skill(h, "finale", h)[0]
    c._resolve_skill(h, "finale", h)
    assert any(e.get("finale") for e in events(c, "melody"))


def test_chrono_spends_time_not_ap():
    c, h, foes = setup("chrono", ["stasis", "rewind"])
    need_core("chrono", "time")
    assert h.pp == 5
    h.ap = 0
    assert c.check_skill(h, "stasis", foes[0])[0]
    c._resolve_skill(h, "stasis", foes[0])
    assert h.pp == 7
    c._resolve_skill(h, "rewind", h)
    assert h.pp == 4


def test_tactician_commands_instead_of_hitting():
    c, h, foes = setup("tactician", [])
    need_core("tactician", "commander")
    ally = c.summon(h, {"unit": "skeleton_minion", "duration": 30}, (2, 3))
    put(ally, (3, 4))
    put(foes[1], (4, 4))
    hp = foes[1].hp
    h.attack_timer = 0
    c._basic_attack(h, foes[1])
    run(c, 0.5)
    assert foes[1].hp < hp and any(e["t"] == "order" for e in c.events)


def test_ram_collisions_heal_and_hit_harder():
    c, h, foes = setup("ram", [])
    need_core("ram", "hardhead")
    h.hp = h.max_hp // 2
    hp = h.hp
    d = PS.collision(c, h, 10)
    assert d == 20 and h.hp > hp


def test_bloodrager_stronger_near_death():
    c, h, foes = setup("bloodrager", [])
    need_core("bloodrager", "near_death")
    full = PS.out_mult(c, h, foes[0], "melee", None, True)
    h.hp = int(h.max_hp * 0.1)
    assert PS.out_mult(c, h, foes[0], "melee", None, True) > full + 0.6


def test_shaman_totems_boost_and_cryo_structures_guard():
    c, h, foes = setup("shaman", ["storm_totem"])
    need_core("shaman", "totems")
    base = PS.out_mult(c, h, foes[0], "spell", None, False)
    c._resolve_skill(h, "storm_totem", (1, 2))
    assert PS.out_mult(c, h, foes[0], "spell", None, False) > base
    c2, cr, f2 = setup("cryo", ["ice_wall"])
    need_core("cryo", "fortress")
    c2._resolve_skill(cr, "ice_wall", (4, 2))
    run(c2, 0.2)
    assert cr.pp >= 1 and PS.in_mult(c2, cr, f2[0], "melee") < 1.0


def test_binder_compassion_bursts():
    c, h, foes = setup("binder", ["tether"])
    need_core("binder", "compassion")
    ally = c.summon(h, {"unit": "skeleton_minion", "duration": 30}, (2, 3))
    c._resolve_skill(h, "tether", ally)
    for _ in range(6):
        PS.on_tether(c, h, h.max_hp * 0.05)
    assert h.pp < h.pp_max and any(e["t"] == "passive" for e in c.events)


def test_brewer_recipe_counts_unique_tags_and_necro_souls():
    c, h, foes = setup("brewer", [])
    need_core("brewer", "recipe")
    for tag in ("water", "poison", "oil"):
        c.apply_status(foes[0], tag, h)
    assert h.pp >= 2
    c2, n, f2 = setup("necro", [])
    need_core("necro", "souls")
    c2.damage(f2[0], 10 ** 6, None, None, "reaction")
    assert n.pp == 1
