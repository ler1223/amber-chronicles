"""Главы и сложности: все бои глав на всех сложностях играются; механики глав (события поля, нежить, скользкий лёд,
порталы, пропасти, полёт, очарование, песчаная буря, прилив, туман); прогресс по главам и сложностям в профиле."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from sim.combat import Combat  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim.profile import Profile  # noqa: E402
from sim.run import Run  # noqa: E402
from sim.teams import ENEMY, PLAYER  # noqa: E402

DATA = GameData()
DIFFS = DATA.config["difficulty_order"]


def enc_of(chapter, kind="normal"):
    return next(i for i, e in enumerate(DATA.encounters) if e.get("chapter", "swamp") == chapter and e["kind"] == kind)


@pytest.mark.parametrize("diff", DIFFS)
def test_every_chapter_battle_plays(diff):
    for i, e in enumerate(DATA.encounters):
        c = Combat(DATA, i, seed=2, ai_teams=(ENEMY, PLAYER), difficulty=diff)
        for _ in range(int(12 / c.dt)):
            c.step()
            c.events.clear()
            if c.result:
                break


def test_difficulty_adds_enemies_and_affixes():
    i = enc_of("forge", "guard")
    base = Combat(DATA, i, seed=3)
    hero = Combat(DATA, i, seed=3, difficulty="heroic")
    night = Combat(DATA, i, seed=3, difficulty="nightmare")
    n = len(base.alive(ENEMY))
    assert len(hero.alive(ENEMY)) == n + 1 and len(night.alive(ENEMY)) == n + 2
    pool = set(DATA.biomes["forge"]["adds"]["heroic"] + DATA.biomes["forge"]["adds"]["nightmare"])
    extra = [u.proto_id for u in night.alive(ENEMY)][n:]
    assert set(extra) <= pool
    assert sum(1 for u in night.alive(ENEMY) if u.affix) == DATA.config["difficulties"]["nightmare"]["affixes"]


def run_until(c, pred, seconds=40):
    for _ in range(int(seconds / c.dt)):
        c.step()
        if pred(c):
            return True
    return False


def test_eruption_warns_then_burns():
    c = Combat(DATA, enc_of("forge"), seed=1)
    seen = []

    def pred(c):
        seen.extend(e["t"] for e in c.events if e["t"] in ("arena_warn", "arena_hit"))
        c.events.clear()
        return "arena_hit" in seen
    assert run_until(c, pred)
    assert seen.index("arena_warn") < seen.index("arena_hit")


def test_undead_rise_unless_burned():
    c = Combat(DATA, enc_of("crypt"), seed=1)
    sk = next(u for u in c.alive(ENEMY) if u.proto_id == "skeleton")
    c.damage(sk, 9999, None, None, "melee")
    assert not sk.alive and c.rising
    for _ in range(int(3.2 / c.dt)):
        c.step()
    assert sk.alive and sk.hp == int(sk.max_hp * 0.4)
    c.damage(sk, 9999, None, None, "melee")      # второй раз не встаёт
    assert not sk.alive and not any(item[0] is sk for item in c.rising)
    sk2 = next(u for u in c.alive(ENEMY) if u.proto_id == "skeleton")
    c.damage(sk2, 9999, None, "fire", "spell")    # огонь — сразу насовсем
    assert not sk2.alive and not any(item[0] is sk2 for item in c.rising)


def test_ice_slide_portal_and_chasm():
    c = Combat(DATA, enc_of("pass"), seed=1)
    w = c.heroes()[0]
    ice = next(p for p, cell in sorted(c.grid.cells.items()) if cell.terrain == "ice_floor"
               and c.is_free((p[0] - 1, p[1])) and c.is_free((p[0] + 1, p[1])) and c.is_free(p))
    w.cell = (ice[0] - 1, ice[1])
    c._place(w, ice, 0.3)
    c._after_step(w, (ice[0] - 1, ice[1]))
    assert w.cell == (ice[0] + 1, ice[1])                    # проехал дальше

    c = Combat(DATA, enc_of("citadel"), seed=1)
    a, b = list(c.grid.portal_pair.items())[0]
    w = c.heroes()[0]
    for u in c.units:
        if u.cell in (a, b):
            u.cell = (0, 0)
    c._place(w, a, 0.3)
    c._after_step(w, (a[0] - 1, a[1]))
    assert w.cell == b
    chasm = next(p for p, cell in sorted(c.grid.cells.items()) if cell.terrain == "chasm")
    foe = next(u for u in c.alive(ENEMY) if not u.boss and not u.flying)
    edge = (chasm[0] - 1, chasm[1])
    if not c.is_free(edge, exclude=foe):
        edge = (chasm[0] + 1, chasm[1])
    for u in c.units:
        if u is not foe and u.cell in (edge, (edge[0] - (chasm[0] - edge[0]), edge[1])):
            u.cell = (0, 5)
    foe.cell = edge
    src = (edge[0] - (chasm[0] - edge[0]), edge[1])
    c.knockback(src, foe, 2)
    assert not foe.alive                                     # сброшен в пропасть
    assert c.grid.passable(chasm, flying=True) and not c.grid.passable(chasm)


def test_charm_flips_sides_and_wears_off():
    c = Combat(DATA, enc_of("fae"), seed=1)
    w, a = c.heroes()[0], c.heroes()[1]
    fae = next(u for u in c.alive(ENEMY) if not u.boss)
    c._apply_one(fae, {"type": "charm", "duration": 1.0}, w.cell, w)
    assert w.charmed and w.is_enemy(a) and not w.is_enemy(fae)
    for _ in range(int(1.2 / c.dt)):
        c.step()
    assert not w.charmed and not w.is_enemy(a) and w.is_enemy(fae)


def test_sandstorm_and_tide():
    c = Combat(DATA, enc_of("tomb"), seed=1)
    archer = next(u for u in c.heroes() if u.atk_range > 1)
    ev = next(e for e in c.arena if e["type"] == "sandstorm")
    c._arena_hit(ev)
    assert c.reach(archer) == archer.atk_range - 2

    c = Combat(DATA, enc_of("sunken"), seed=1)
    ev = next(e for e in c.arena if e["type"] == "tide")
    c._arena_warn(ev)
    c._arena_hit(ev)
    cells = ev["cells"]
    assert cells and all(c.grid.get(p).terrain == "water" for p in cells)
    c.time += 10
    c.step()
    assert not c.tides


def test_fog_hides_enemies_at_scouting():
    i = next(i for i, e in enumerate(DATA.encounters) if e.get("fog"))
    c = Combat(DATA, i, seed=1)
    assert sum(1 for u in c.alive(ENEMY) if u.hidden) == DATA.encounters[i]["fog"]


def test_chapter_map_uses_own_battles():
    run = Run(DATA, 3, DATA.biomes["steppe"]["regions"][2], {}, None, "steppe", "heroic")
    ids = [DATA.encounters[n["encounter"]]["chapter"] for n in run.nodes.values() if n["encounter"] is not None]
    assert ids and set(ids) == {"steppe"}
    scale = run.enemy_scale()
    assert scale["hp"] > DATA.biomes["steppe"]["power"]["hp"]


def win(prof, rid):
    run = prof.start_run(rid, 1)
    run.result, run.battles_won = "victory", 3
    return prof.finish_run(run)


def test_chapters_and_difficulties_unlock_in_order(tmp_path):
    prof = Profile(DATA, str(tmp_path / "p.json"))
    order = prof.chapters()
    assert order[0] == "swamp" and prof.chapter_unlocked("swamp") and not prof.chapter_unlocked(order[1])
    assert not prof.difficulty_unlocked("swamp", "heroic")
    prof.captured = [r["id"] for r in prof.biome["regions"] if not r.get("boss")]
    boss = next(r["id"] for r in prof.biome["regions"] if r.get("boss"))
    end = win(prof, boss)
    assert ("forge", "normal") in end["opened"] and ("swamp", "heroic") in end["opened"]
    assert prof.set_chapter("forge", "normal") and prof.captured == []
    first = DATA.biomes["forge"]["regions"][0]["id"]
    amber = prof.amber
    end = win(prof, first)
    assert end["captured"] and prof.amber - amber > 0
    assert prof.bonuses().get("power_pct", 0) > 0                 # бонус кузни работает и в другой главе
    prof.set_chapter("swamp", "heroic")
    assert prof.difficulty == "heroic" and prof.captured == []
    again = Profile(DATA, str(tmp_path / "p.json"))
    assert again.difficulty == "heroic" and again.done("swamp", "normal")
    assert first in again._state("forge", "normal")["captured"]


def test_v3_save_migrates_to_chapters(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"version": 3, "biome": "swamp", "captured": ["reeds"], "biome_done": True,
                                "amber": 50}), encoding="utf-8")
    prof = Profile(DATA, str(path))
    assert prof.captured == ["reeds"] and prof.done("swamp") and prof.chapter_unlocked("forge") and prof.amber == 50
