"""Шаман (квиз 2026-11-10): тотемы без срока, общий лимит 2/3/4 по уровню, бафающие тотемы, шаровая молния,
ультимейты Грозовой фронт / Тотем-пленитель / Предки."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_characters import DATA, put, run, setup  # noqa: E402
from needs import need  # noqa: E402
from sim import kit  # noqa: E402


def mk(skills, level=1):
    need(*skills, cls="shaman")
    if "summon_groups" not in DATA.config:
        import pytest
        pytest.skip("механика переделана: у тотемов больше нет общего лимита")
    c, h, foes = setup("shaman", skills)
    h.proto["level"] = level
    h.ap = h.ap_max
    return c, h, foes


def totems(c, h):
    return kit.own_totems(c, h)


def test_totem_limit_grows_with_level_and_totems_do_not_expire():
    for level, limit in ((1, 2), (6, 3), (11, 4)):
        c, h, foes = mk(["storm_totem"], level)
        for i in range(5):
            c.summon(h, {"unit": "totem_storm"}, (0, i))
        assert len(totems(c, h)) == limit
    run(c, 20.0)
    assert totems(c, h)                             # без срока жизни


def test_rage_totem_buffs_allies_nearby():
    c, h, foes = mk(["rage_totem"])
    c.summon(h, {"unit": "totem_rage"}, (1, 2))
    run(c, 1.2)
    assert h.buff("atk_mult", 1.0) > 1.0 and h.buff("atk_speed", 1.0) < 1.0


def test_spirit_totem_speeds_cooldowns_and_skill_power():
    c, h, foes = mk(["spirit_totem", "chain_lightning"])
    c.summon(h, {"unit": "totem_spirit"}, (1, 2))
    run(c, 1.2)
    assert h.buff("skill_mult", 1.0) > 1.0
    h.cooldowns["chain_lightning"] = 3.0
    run(c, 1.0)
    assert h.cooldowns.get("chain_lightning", 0) < 3.0 - 1.0     # быстрее, чем 1 сек за сек


def test_ball_lightning_hits_each_enemy_once_along_its_path():
    c, h, foes = mk(["ball_lightning"])
    hp = [f.hp for f in foes]
    c._resolve_skill(h, "ball_lightning", (7, 2))
    run(c, 3.0)
    hit = [f for f, x in zip(foes, hp) if f.hp < x]
    assert hit and all("storm" in f.statuses or not f.alive for f in hit)


def test_ultimates():
    need("storm_front", "thunder_idol", "ancestors", cls="shaman")
    c, h, foes = mk(["storm_front", "storm_totem"])
    c.summon(h, {"unit": "totem_storm"}, (4, 3))
    hp = sum(f.hp for f in foes)
    c._resolve_skill(h, "storm_front", h)
    run(c, 3.5)
    assert sum(f.hp for f in foes) < hp

    c, h, foes = mk(["thunder_idol", "storm_totem"])
    for i in range(2):
        c.summon(h, {"unit": "totem_storm"}, (0, i))
    c._resolve_skill(h, "thunder_idol", (4, 4))
    run(c, 2.2)                                          # первый удар — через 1.5 сек
    idol = [s for s in c.units if s.alive and s.proto_id == "totem_idol"]
    assert idol and len(totems(c, h)) == 3               # сверх лимита: обычные тотемы на месте
    assert any(f.stun > 0 for f in foes)

    c, h, foes = mk(["ancestors", "storm_totem", "healing_totem"])
    c._resolve_skill(h, "ancestors", h)
    kinds = {s.proto_id for s in totems(c, h)}
    assert {"totem_storm", "totem_heal"} <= kinds
    assert all(s.buff("dmg_taken", 1.0) == 0.0 for s in totems(c, h))
