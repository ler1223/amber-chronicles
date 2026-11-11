"""Лучник (квиз 2026-11-10) и навыки от статов героя: колчаны 1 / 6 / 11, стрелы чередуются и растут от силы
навыков, три ультимейта (у героя — случайный), числа навыков растут с уровнем."""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_characters import DATA, put, run, setup  # noqa: E402
from sim import expedition as X, stats, story_meta  # noqa: E402

ED = X.expedition_data(DATA)
from needs import need, need_core  # noqa: E402


def _need_archer(*sids):
    """Лучник с колчанами: переделают механику — эти тесты пропустятся, а не упадут."""
    if "arrows" not in DATA.config or not story_meta.cfg(DATA)["classes"]["archer"].get("quivers"):
        import pytest
        pytest.skip("механика переделана: у лучника больше нет колчанов")
    need(*sids, cls="archer")


def hero(cls, level, **kw):
    h = X.Hero(dict({"uid": "a", "name": "А", "cls": cls, "skills": [], "level": level}, **kw))
    h.points = X.auto_points(ED, h)
    run_ = X.Expedition(ED, [h], seed=1)
    h = run_.heroes[0]
    h.gear = {}
    return run_, h


def test_quiver_choice_on_levels_1_6_11():
    _need_archer()
    r, h = hero("archer", 1)
    assert r.quiver_pending(h) == 1 and h.sp >= 1
    cards = r.pick_cards(h)
    assert [c["type"] for c in cards] == ["quiver", "quiver"] and cards[0]["arrow"] != cards[1]["arrow"]
    assert r.take_card(h, 0) and h.quivers == [cards[0]["arrow"]]
    for lvl in range(2, 12):
        h.level = lvl - 1
        h.xp = r.xp_next(h)
        r.gain_xp(h, 0)
    assert r.quivers_due(h) == 3 and r.quiver_pending(h) == 2
    while r.quiver_pending(h):
        assert r.pick_cards(h)[0]["type"] == "quiver"
        r.take_card(h, 1)
    assert len(set(h.quivers)) == 3
    assert not r.proto(h).get("quiver_boost")
    h.level = 15
    assert r.proto(h)["quiver_boost"]


def test_random_ultimate_per_hero():
    _need_archer("all_arrows", "arrow_storm", "fletching", "aimed_shot", "barrage", "headshot")
    ults = story_meta.ults_of(DATA, "archer")
    assert set(ults) == {"all_arrows", "arrow_storm", "fletching"}
    seen = {story_meta.random_kit(ED, "archer", random.Random(i))[3] for i in range(40)}
    assert seen == set(ults)
    r, h = hero("archer", 10, skills=["aimed_shot", "barrage", "headshot", "fletching"])
    assert story_meta.ult_of(DATA, "archer", h.skills) == "fletching"
    assert "fletching" in r.battle_skills(h) and "all_arrows" not in r.battle_skills(h)


def test_skills_grow_with_level_from_their_stat():
    """Навык на % атаки и навык на силу навыков — оба растут с уровнем (призыв тоже)."""
    for cls, sid in (("archer", "aimed_shot"), ("priest", "judgment"), ("mage", "fireball")):
        vals = []
        for lvl in (1, 10):
            r, h = hero(cls, lvl, skills=[sid])
            if sid not in h.skills:
                h.skills = [sid] + h.skills[:2]
            p = r.proto(h)
            vals.append(stats.skill_values(p, p["skill_defs"][sid])[0][1])
        assert vals[1] > vals[0] * 1.8, (cls, vals)


def test_arrows_alternate_and_scale_with_skill_power():
    _need_archer("aimed_shot")
    c, h, foes = setup("archer", ["aimed_shot"])
    h.quivers = ["fire", "frost"]
    f = foes[0]
    put(f, (5, 2))
    k0 = c.stat_k(h, "sp", True)
    h.power = 2.0                                  # сила навыков ×2 — стрела бьёт вдвое сильнее
    assert c.stat_k(h, "sp", True) == k0 * 2
    hp = f.hp
    from sim import kit
    kit.arrow_rider(c, h, f, arrow="fire", owner=h)
    assert "fire" in f.statuses and f.hp < hp
    assert h.arrow_i == 0                          # явная стрела не сдвигает очередь


def test_barrage_fires_three_arrows_with_quivers():
    _need_archer("barrage")
    c, h, foes = setup("archer", ["barrage"])
    h.quivers = ["frost", "fire", "bleed"]
    f = foes[0]
    put(f, (5, 2))
    h.ap = h.ap_max
    h.attack_timer = 99                             # без обычных атак: считаем только стрелы Шквала
    got = []
    emit = c.emit
    c.emit = lambda t, **kw: (got.append(kw["arrow"]) if t == "arrow" else None, emit(t, **kw))[1]
    c._resolve_skill(h, "barrage", f)
    run(c, 1.5)
    assert got[:3] == ["frost", "fire", "bleed"]


def test_shackle_pins_two_enemies_in_a_line():
    _need_archer("shackle_shot")
    c, h, foes = setup("archer", ["shackle_shot"])
    put(foes[0], (4, 2))
    put(foes[1], (5, 2))
    put(foes[2], (6, 4))
    h.ap = h.ap_max
    c._resolve_skill(h, "shackle_shot", foes[0])
    run(c, 0.8)
    assert foes[0].stun > 1.5 and foes[1].stun > 1.5 and foes[2].stun == 0


def test_vault_jumps_away_from_adjacent_enemy():
    _need_archer("vault_shot")
    c, h, foes = setup("archer", ["vault_shot"])
    put(foes[0], (3, 2))
    h.ap = h.ap_max
    before = foes[0].hp
    c._resolve_skill(h, "vault_shot", h)
    run(c, 1.0)
    from sim.grid import cheb
    assert cheb(h.cell, foes[0].cell) >= 3 and foes[0].hp < before
