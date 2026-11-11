"""Подрывник (квиз 2026-11-10): заряды от статов героя, Фитиль-кнопка (F, 0 AP, без перезарядки) рвёт всё цепочкой,
граната и дорожка поджигают соседние заряды, три ультимейта, автокаст «зарядов на поле ≥ N»."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_characters import DATA, put, run, setup  # noqa: E402
from needs import need, need_core  # noqa: E402
from sim import expedition as X, kit, story_meta  # noqa: E402
from sim.grid import cheb  # noqa: E402

ED = X.expedition_data(DATA)


def _need(*sids):
    if story_meta.mech_of(DATA, "alchemist") != "fuse":
        import pytest
        pytest.skip("механика переделана: у подрывника больше нет Фитиля-кнопки")
    need(*sids, cls="alchemist")


def mk(skills):
    c, h, foes = setup("alchemist", list(skills) + ["fuse"])
    h.ap, h.pp = h.ap_max, h.pp_max
    h.proto["ref"] = {"atk": DATA.classes["alchemist"]["attack"]["damage"], "hp": DATA.classes["alchemist"]["hp"]}
    return c, h, foes


def place(c, h, sid, target):
    """Поставить заряд и дождаться попадания (навыки бьют по прилёте)."""
    h.cooldowns.pop(sid, None)
    h.ap = h.ap_max
    c._resolve_skill(h, sid, target)
    run(c, 0.8)


def test_fuse_is_a_free_mech_button_in_every_kit():
    _need()
    sk = DATA.skills["fuse"]
    assert sk["mech"] and sk["ap"] == 0 and sk["cooldown"] == 0 and sk.get("hotkey") == "F"
    h = X.Hero({"uid": "a", "name": "А", "cls": "alchemist", "skills": [], "level": 1})
    r = X.Expedition(ED, [h], seed=1)
    assert r.battle_skills(r.heroes[0])[-1] == "fuse"


def test_fuse_chain_blows_charges_near_to_far_within_a_second():
    _need("powder_keg", "mine")
    c, h, foes = mk(["powder_keg", "mine"])
    put(foes[0], (6, 2))
    place(c, h, "powder_keg", (2, 4))
    place(c, h, "mine", (5, 2))
    assert len(kit.own_charges(c, h)) == 2
    hp = foes[0].hp
    c._resolve_skill(h, "fuse", h)
    run(c, 0.2)
    assert len(kit.own_charges(c, h)) == 2             # 0.3 сек — ещё горит фитиль
    run(c, 1.0)
    assert not kit.own_charges(c, h) and foes[0].hp < hp


def test_charges_grow_with_skill_power():
    _need("powder_keg")
    dmg = []
    for power in (1.0, 2.0):
        c, h, foes = mk(["powder_keg"])
        h.power = power
        c._resolve_skill(h, "powder_keg", (4, 4))
        keg = next(o for o in c.units if o.obj and o.owner is h)
        dmg.append(keg.blast_dmg)
        assert keg.max_hp == max(1, round(h.max_hp * 0.15))   # прочность — от здоровья подрывника
    assert abs(dmg[1] - 2 * dmg[0]) < 1e-6


def test_grenade_ignites_nearby_charges():
    _need("grenade", "powder_keg")
    c, h, foes = mk(["grenade", "powder_keg"])
    c._resolve_skill(h, "powder_keg", (4, 4))
    keg = next(o for o in c.units if o.obj and o.owner is h)
    c._resolve_skill(h, "grenade", (4, 3))
    run(c, 1.2)
    assert not keg.alive


def test_powder_trail_lays_line_and_fuse_runs_along():
    _need("powder_trail")
    c, h, foes = mk(["powder_trail"])
    place(c, h, "powder_trail", (6, 2))
    cells = [p for _, _, p in kit.own_charges(c, h)]
    assert len(cells) >= 3 and all(c.grid.get(p).hazard == "powder" for p in cells)
    c._resolve_skill(h, "fuse", h)
    run(c, 1.5)
    assert not kit.own_charges(c, h)


def test_dynamite_takes_three_powder():
    _need("dynamite")
    c, h, foes = mk(["dynamite"])
    h.pp = 3
    c._resolve_skill(h, "dynamite", (5, 4))
    crate = next(o for o in c.units if o.obj and o.owner is h)
    assert h.pp == 0 and crate.blast_mult == 2.0 and crate.blast_r == 2


def test_ultimates_barrel_rain_reactive_armor_powder_plate():
    _need("barrel_rain", "reactive_armor", "powder_plate")
    c, h, foes = mk(["barrel_rain"])
    hp = [f.hp for f in foes]
    c._resolve_skill(h, "barrel_rain", foes[0].cell)
    run(c, 2.0)
    assert sum(1 for f, x in zip(foes, hp) if f.hp < x) >= 2

    c, h, foes = mk(["reactive_armor"])
    c._resolve_skill(h, "reactive_armor", h)
    assert "reactive" in h.buffs and h.shield > 0
    f = foes[0]
    hp = f.hp
    c.damage(h, 1, f, None, "melee")
    assert f.hp < hp

    c, h, foes = mk(["powder_plate"])
    put(foes[0], (3, 2))
    c._resolve_skill(h, "powder_plate", h)
    run(c, 0.1)
    assert h.shield > 0 and foes[0].stun > 0


def test_autocast_fuse_waits_for_enough_charges():
    _need("powder_keg")
    from sim.autocast import AutoCaster
    c, h, foes = mk(["powder_keg"])
    h.autocast = {"fuse": {"on": True, "conds": [{"type": "charges_at_least", "value": 2}]}}
    ac = AutoCaster(c, h.team)
    put(foes[0], (2, 3))
    place(c, h, "powder_keg", (1, 3))
    assert ac.choose(h) is None or ac.choose(h)[0] != "fuse"     # одна бочка — ждём
    place(c, h, "powder_keg", (2, 4))
    put(foes[0], (2, 3))
    choice = ac.choose(h)
    assert choice is not None and choice[0] == "fuse"
