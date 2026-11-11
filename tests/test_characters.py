"""Характеры классов (sim/kit.py): у каждого класса 8 навыков вокруг 1–2 механик; все навыки во всех ветках
срабатывают; ключевые механики работают."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_rework1 import DATA, events, put, quiet, run  # noqa: E402
from needs import need  # noqa: E402
from sim import kit, story_meta  # noqa: E402
from sim.build import build_proto  # noqa: E402
from sim.combat import Combat  # noqa: E402
from sim.teams import ENEMY  # noqa: E402

POOL = {cls: story_meta.all_skills(DATA, cls) for cls in DATA.classes}
CASES = [(cls, sid, br) for cls, ids in POOL.items() for sid in ids
         for br in (None, ("A", 1), ("A", 2), ("B", 1), ("B", 2))]


def test_every_class_has_skills_unlocked_by_level():
    """У класса 7+ навыков в слоты (1–12 уровень) и 1–3 ультимейта на 10 уровне (разные способы игры)."""
    for cls in DATA.classes:
        ults = story_meta.ults_of(DATA, cls)
        regular = [s for s in POOL[cls] if s not in ults]
        assert 1 <= len(ults) <= 3 and len(regular) >= story_meta.slots(DATA), cls
        levels = [story_meta.skill_level(DATA, cls, s) for s in regular]
        assert min(levels) == 1 and levels == sorted(levels), cls      # первый навык с 1 уровня, дальше по росту
        for ult in ults:
            sk = DATA.skills[ult]
            assert story_meta.skill_level(DATA, cls, ult) == 10 and sk["ap"] <= 2 and sk.get("ult_cond"), (cls, ult)
        for sid in POOL[cls]:
            assert sid in DATA.branches, sid


def setup(cls, skills, br=None):
    need(*skills, *(br or {}), cls=cls)          # механику переделали — тест пропускается, а не падает
    proto = build_proto(DATA, cls, skills=list(skills), branches=br)
    c = quiet(Combat(DATA, 1, squad=[{"cls": cls, "proto": proto}]))
    h = next(u for u in c.heroes() if u.proto_id == cls)
    foes = c.fighters(ENEMY)
    for f in foes[3:]:
        f.alive = False
    foes = foes[:3]
    for cell in [(x, y) for x in range(0, 8) for y in range(0, 5)]:
        g = c.grid.get(cell)
        if g:
            g.passable, g.terrain, g.cover, g.hazard = True, "grass", None, None
    put(h, (2, 2))
    for f, cell in zip(foes, [(3, 2), (3, 3), (4, 2)]):
        put(f, cell)
        f.max_hp = f.hp = 400
    return c, h, foes


def sid_of(h, sk):
    return next(s for s, d in h.skill_defs.items() if d is sk)


def prepare(c, h, foes, sk):
    """Условия навыка механики: облик, тень, метка, тотем, знамя, песня, трупы, шкала."""
    h.ap = h.ap_max
    h.pp = h.pp_max
    if sk.get("ult_cond"):                        # условие ультимейта проверяется отдельно
        h.skill_defs[sid_of(h, sk)] = {k: v for k, v in sk.items() if k != "ult_cond"}
    if sk.get("form") and sk["form"] != "human":
        c.set_form(h, sk["form"])
    if sk.get("needs_shadow"):
        c.add_buff(h, "stealth", 1.6, 5)
    if sk.get("needs_mark"):
        kit.add_mark(c, foes[0], sk["needs_mark"], 1, 8, h)
    if sk.get("needs_totem"):
        c.summon(h, {"unit": "totem_storm", "duration": 12}, (1, 2))
    if sk.get("needs_banner"):
        c.summon(h, {"unit": "banner", "duration": 12}, (1, 3))
    if any(e["type"] in ("song_notes", "song_tempo", "song_finale") for e in sk["effects"]):
        c.apply_effects(h, DATA.skills["rhythm"]["effects"], h.cell, h)
    c.corpses.append({"cell": (4, 3), "left": 10, "name": "труп"})


@pytest.mark.parametrize("cls,sid,br", CASES)
def test_pool_skill_resolves(cls, sid, br):
    c, h, foes = setup(cls, [sid], {sid: br} if br else None)
    sk = h.skill_defs[sid]
    prepare(c, h, foes, sk)
    target = {"self": h, "enemy": foes[0], "ally": h, "cell": (5, 3) if sk.get("free_cell") else (3, 2)}[sk["target"]]
    if sk["target"] == "cell" and sk.get("range", 0) <= 1:
        target = (3, 2)
    ok, msg = c.check_skill(h, sid, target)
    assert ok, (sid, br, msg)
    c._resolve_skill(h, sid, target)
    run(c, 3.0)


def test_challenge_duel_multipliers_and_taunt():
    c, h, foes = setup("warrior", ["challenge", "power_strike", "duel_execute"])
    f, other = foes[0], foes[1]
    c._resolve_skill(h, "challenge", f)
    run(c, 0.6)
    assert "challenge" in f.marks and f.taunted_by is h
    assert kit.duel_mult(c, f, h) == pytest.approx(1.3) and kit.duel_mult(c, h, f) == pytest.approx(0.75)
    ok, _ = c.check_skill(h, "duel_execute", other)
    assert not ok                                         # казнь — только по вызванному
    c._resolve_skill(h, "challenge", other)
    run(c, 0.6)
    assert "challenge" not in f.marks and "challenge" in other.marks     # вызов на поле один


def test_cold_stacks_freeze_and_shatter():
    c, h, foes = setup("cryo", ["ice_shard", "shatter"])
    f = foes[0]
    for _ in range(3):
        h.cooldowns.clear()
        c._resolve_skill(h, "ice_shard", f)
        run(c, 0.8)
    assert f.stun > 0 and f.stun_look == "freeze" and "cold" not in f.marks
    hp = f.hp
    c._resolve_skill(h, "shatter", h)
    run(c, 0.8)
    assert f.hp < hp


def test_sticky_bomb_explodes_and_detonator_triggers_early():
    c, h, foes = setup("alchemist", ["sticky_bomb", "detonator"])
    f = foes[0]
    c._resolve_skill(h, "sticky_bomb", f)
    run(c, 0.8)
    assert "bomb" in f.marks
    hp = f.hp
    c._resolve_skill(h, "detonator", h)
    run(c, 0.5)
    assert "bomb" not in f.marks and f.hp < hp


def test_quivers_alternate_on_basic_attacks():
    """Колчаны лучника чередуются: первая стрела — первый колчан, вторая — второй."""
    c, h, foes = setup("archer", ["aimed_shot"])
    h.quivers = ["frost", "fire"]
    f = foes[0]
    put(f, (5, 2))
    h.attack_timer = 0
    c._basic_attack(h, f)
    run(c, 1.0)
    assert "cold" in f.marks and "fire" not in f.statuses
    h.attack_timer = 0
    c._basic_attack(h, f)
    run(c, 1.0)
    assert "fire" in f.statuses


def test_priest_miracles_cost_faith():
    c, h, foes = setup("priest", ["sanctuary", "judgment"])
    h.pp = 1
    ok, msg = c.check_skill(h, "sanctuary", h)
    assert not ok and "Вера" in msg
    h.pp = 5
    c._resolve_skill(h, "judgment", foes[0])
    assert h.pp == 0                                       # приговор тратит всю Веру


def test_shadow_dance_jumps_after_kill_and_kill_returns_to_shadow():
    c, h, foes = setup("assassin", ["shadow_dance"])
    foes[0].hp = 5
    c._resolve_skill(h, "shadow_dance", foes[0])
    run(c, 1.0)
    assert not foes[0].alive and any(e["stat"] == "stealth" for e in events(c, "buff") if e["unit"] is h)
    assert any(f.hp < 400 for f in foes[1:])


def test_totem_pulse_and_trap_pull():
    c, h, foes = setup("shaman", ["storm_totem", "totem_pulse"])
    c._resolve_skill(h, "storm_totem", (2, 3))
    run(c, 0.5)
    n = len(events(c, "attack"))
    c._resolve_skill(h, "totem_pulse", h)
    assert len(events(c, "attack")) > n
    c2, t, foes2 = setup("trapper", ["snare", "big_hunt"])
    c2._resolve_skill(t, "snare", (6, 2))
    run(c2, 0.5)
    c2._resolve_skill(t, "big_hunt", t)
    run(c2, 1.0)
    assert any(f.cell == (6, 2) or (f.stun > 0 and f.stun_look == "trap") for f in foes2)


def test_density_and_gravity_well_pull():
    c, h, foes = setup("gravity", ["crush"])
    lone = setup("gravity", ["crush"])
    a = foes[0]
    hp = a.hp
    c._resolve_skill(h, "crush", a)
    run(c, 1.0)
    packed = hp - a.hp
    c2, h2, f2 = lone
    for f in f2[1:]:
        put(f, (7, 4) if f is f2[1] else (0, 4))
    hp2 = f2[0].hp
    c2._resolve_skill(h2, "crush", f2[0])
    run(c2, 1.0)
    assert packed > hp2 - f2[0].hp                         # в толпе — больнее


def test_bleed_feast_heals_bloodrager():
    c, h, foes = setup("bloodrager", ["rupture", "feast"])
    c._resolve_skill(h, "rupture", foes[0])
    run(c, 0.5)
    assert "bleed" in foes[0].buffs
    h.hp = 40
    c._resolve_skill(h, "feast", h)
    assert h.hp > 40 and "bleed" not in foes[0].buffs


def test_banner_doubles_forward():
    c, h, foes = setup("tactician", ["plant_banner"])
    c._resolve_skill(h, "plant_banner", (2, 3))
    run(c, 1.2)
    assert "banner" in h.buffs


def test_silence_blocks_skills():
    c, h, foes = setup("warrior", ["disarm"])
    c.add_buff(h, "silence", 1, 2)
    ok, msg = c.check_skill(h, "disarm", foes[0])
    assert not ok and msg == "Безмолвие"


def test_ult_needs_its_condition():
    c, h, foes = setup("warrior", ["challenge", "duel"])
    h.ap = h.ap_max
    ok, msg = c.check_skill(h, "duel", foes[0])
    assert not ok and "Ультимейт" in msg and "0/4" in msg
    c._resolve_skill(h, "challenge", foes[0])
    run(c, 0.5)
    for _ in range(4):
        c.damage(foes[0], 5, h, None, "melee")
    ok, msg = c.check_skill(h, "duel", foes[0])
    assert ok, msg
    c._resolve_skill(h, "duel", foes[0])
    ok, msg = c.check_skill(h, "duel", foes[0])
    assert not ok                                        # счётчик потрачен


def test_ult_live_condition_corpses():
    c, h, foes = setup("necro", ["last_call"])
    h.ap = h.ap_max
    assert not c.check_skill(h, "last_call", h)[0]
    for i in range(3):
        c.corpses.append({"cell": (5, i), "left": 10, "name": "труп"})
    assert c.check_skill(h, "last_call", h)[0]


def test_expedition_ult_opens_at_level_ten():
    from sim import expedition as X
    ED = X.expedition_data(DATA)
    h = X.Hero({"uid": "u1", "name": "Т", "cls": "warrior", "skills": ["power_strike", "challenge", "riposte", "duel"]})
    run_ = X.Expedition(ED, [h], seed=1)
    assert "duel" not in run_.battle_skills(run_.heroes[0])
    run_.heroes[0].level = 10
    assert run_.battle_skills(run_.heroes[0])[-1] == "duel"
