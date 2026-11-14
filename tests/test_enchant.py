"""Сильные зачарования артефактов: каждый N-й удар/каст, а не маленький стат-аффикс."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.data import GameData  # noqa: E402
from sim.combat import Combat  # noqa: E402
from sim.build import build_proto  # noqa: E402
from sim.teams import PLAYER, ENEMY  # noqa: E402
from sim import expedition as X  # noqa: E402

DATA = GameData()
XD = X.expedition_data(DATA).expedition


def _combat():
    c = Combat(DATA, 0, squad=[{"cls": "warrior", "proto": build_proto(DATA, "warrior")}])
    c.hit_timing = False
    h = c.fighters(PLAYER)[0]
    foes = [u for u in c.fighters(ENEMY) if not u.obj]
    for f in foes:
        f.hp = f.max_hp = 9999
    return c, h, foes


def test_enchant_data_is_strong_and_valid():
    ench = XD["artifacts"]["enchants"]
    assert {"fifth_shot", "third_spell", "frost_echo", "storm_chain",
            "death_burst", "first_haste", "first_skill_double", "single_target_bonus", "bleed_extra"} <= set(ench)
    for e in ench.values():
        for r in e.get("rules", []):
            assert r["trigger"] in XD["items"]["triggers"]
            assert all(x in XD["items"]["effects"] for x in r.get("do", []))
    combos = {c["id"]: c for c in XD["artifacts"]["enchant_combos"]}
    assert combos["ashen_burst"]["effect"] == "death_burst"
    assert combos["first_dawn"]["effect"] == "first_haste"
    assert combos["storm_opening"]["effect"] == "first_skill_double"
    assert combos["hunters_instinct"]["effect"] == "single_target_bonus"
    assert combos["blood_thorn"]["effect"] == "bleed_extra"


def test_fifth_shot_hits_extra_target():
    c, h, foes = _combat()
    h.enchants = [{"id": "fifth_shot"}]
    for _ in range(5):
        h.attack_timer = 0
        c._basic_attack(h, foes[0])
    assert h.enchant_counts["fifth_shot"] == 5
    assert any(f.hp < f.max_hp for f in foes[1:])


def test_third_spell_echoes():
    c, h, foes = _combat()
    h.enchants = [{"id": "third_spell"}]
    sid = h.skills[0]
    for _ in range(3):
        h.ap = h.ap_max
        c._resolve_skill(h, sid, foes[0])
    assert h.enchant_counts["third_spell"] == 3
    assert any(e.get("t") == "enchant_proc" and e.get("id") == "third_spell" for e in c.events)


def test_first_haste_and_first_skill():
    c, h, foes = _combat()
    h.enchants = [{"id": "first_haste"}]
    c.time = 0
    h.attack_timer = 0
    c._basic_attack(h, foes[0])
    assert h.attack_timer < h.atk_cd

    h.enchants = [{"id": "first_skill_double"}]
    h.enchant_counts = {}
    h.ap = h.ap_max
    c._resolve_skill(h, h.skills[0], foes[0])
    assert h.enchant_counts["first_skill_double"] == 1
    assert any(e.get("t") == "enchant_proc" and e.get("id") == "first_skill_double" for e in c.events)


def test_single_target_and_bleed_bonus():
    c, h, foes = _combat()
    sid = h.skills[0]
    sk = h.skill_defs[sid]
    assert c._is_single_target_skill(sk, sk["effects"])
    h.enchants = [{"id": "bleed_extra"}]
    f = foes[2]
    c.rng.random = lambda: 0.0
    c.apply_dot(f, "bleed", 5, 4, attacker=h, stacks=1)
    assert f.dots["bleed"]["stacks"] >= 2


def test_death_burst():
    c, h, foes = _combat()
    h.enchants = [{"id": "death_burst"}]
    f1, f2 = foes[0], foes[1]
    f2.cell = (f1.cell[0] + 1, f1.cell[1])
    before = f2.hp
    c.damage(f1, 99999, h, None, "melee")
    assert f2.hp < before
    assert any(e.get("t") == "death_burst" for e in c.events)
