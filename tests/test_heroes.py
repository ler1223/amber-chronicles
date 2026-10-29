"""Новые герои и механики: каждый класс во всех путях и ветках отыгрывает бой без ошибок; скрытность, сон, облики,
зона контроля, притягивание, тотемы, мины, воскрешение, новые реакции."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from sim.build import build_proto, class_skills  # noqa: E402
from sim.combat import Combat  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim.teams import ENEMY, PLAYER  # noqa: E402

DATA = GameData()


def squad_of(classes, path=None, branch=None):
    out = []
    for cls in classes:
        p = path if path and DATA.paths[path]["class"] == cls else None
        skills = class_skills(DATA, cls, p)
        branches = {sid: (branch, 2) for sid in skills} if branch else None
        out.append({"cls": cls, "proto": build_proto(DATA, cls, branches=branches, path=p)})
    return out


def play(squad, seconds=50, enc=1, seed=3):
    c = Combat(DATA, enc, seed=seed, ai_teams=(ENEMY, PLAYER), squad=squad)
    for _ in range(int(seconds / c.dt)):
        c.step()
        c.events.clear()
        if c.result:
            break
    return c


NEW = ["assassin", "druid", "guardian", "shaman", "bard", "alchemist"]


@pytest.mark.parametrize("branch", [None, "A", "B"])
def test_new_heroes_fight_in_every_branch(branch):
    for i in range(0, len(NEW), 3):
        c = play(squad_of(NEW[i:i + 3] + ["priest"], branch=branch), enc=1 + i // 3)
        assert c.time > 3


def test_every_path_fights():
    for pid, p in DATA.paths.items():
        for branch in (None, "A", "B"):
            c = play(squad_of([p["class"], "warrior", "priest"], path=pid, branch=branch), seconds=30, enc=2)
            assert c.time > 3, pid


def unit(c, cls):
    return next(u for u in c.units if u.proto_id == cls)


def foe(c):
    return next(u for u in c.units if u.team == ENEMY and u.alive)


def test_stealth_hides_and_ambush_hits_harder():
    c = Combat(DATA, 1, squad=squad_of(["assassin", "warrior", "mage", "priest"]))
    a, f = unit(c, "assassin"), foe(c)
    c.order_attack(f, a)
    c.apply_effects(a, [{"type": "stealth", "duration": 5, "mult": 2.0}], a.cell, a)
    assert not c.visible(a) and f.order is None and a not in c.foes_of(f)
    hp = f.hp
    f.cell = (a.cell[0] + 1, a.cell[1])
    c._basic_attack(a, f)
    assert c.visible(a) and hp - f.hp >= a.atk_damage * 2 - f.total_armor() - 1


def test_sleep_breaks_on_damage():
    c = Combat(DATA, 1, squad=squad_of(["bard", "warrior", "mage", "priest"]))
    b, f = unit(c, "bard"), foe(c)
    c.apply_effects(b, [{"type": "sleep", "duration": 4}], f.cell, f)
    assert f.stun > 0 and f.asleep
    c.damage(f, 5, b, kind="melee")
    assert f.stun == 0 and not f.asleep


def test_bear_form_toggles_stats():
    c = Combat(DATA, 1, squad=squad_of(["druid", "warrior", "mage", "priest"]))
    d = unit(c, "druid")
    armor, rng, hp = d.armor, d.atk_range, d.max_hp
    c.set_form(d, "bear")
    assert d.armor == armor + 4 and d.atk_range == 1 and d.max_hp == hp + 40
    c.set_form(d, "bear")
    assert d.form is None and d.armor == armor and d.atk_range == rng and d.max_hp == hp


def test_zone_of_control_hits_approaching_enemy():
    c = Combat(DATA, 1, squad=squad_of(["guardian", "warrior", "mage", "priest"]))
    g, f = unit(c, "guardian"), foe(c)
    g.cell = g.prev_cell = (4, 3)
    f.cell = f.prev_cell = (6, 3)
    g.pp = g.pp_max
    hp, pp = f.hp, g.pp
    c._step_toward(f, g.cell, 1)
    assert f.hp < hp and g.pp == pp - 1 and f.wait > 0


def test_pull_brings_target_next_to_caster():
    c = Combat(DATA, 1, squad=squad_of(["guardian", "warrior", "mage", "priest"]))
    g, f = unit(c, "guardian"), foe(c)
    g.cell, f.cell = (2, 3), (6, 3)
    for u in c.units:
        if u not in (g, f) and u.cell in {(3, 3), (4, 3), (5, 3)}:
            u.cell = (0, 0)
    c.pull(g, f, 3)
    assert f.cell == (3, 3)


def test_totems_heal_expire_and_do_not_count_as_squad():
    c = Combat(DATA, 1, squad=squad_of(["shaman", "warrior", "mage", "priest"]))
    s = unit(c, "shaman")
    w = unit(c, "warrior")
    w.hp = 50
    c.ais = []                                   # враги не мешают: проверяем только лечение тотема
    t = c.summon(s, {"unit": "totem_heal", "duration": 2}, w.cell)
    assert t and t.summon and t.static and t.team == PLAYER
    for _ in range(int(1.5 / c.dt)):
        c.step()
    assert w.hp > 50
    for _ in range(int(1.0 / c.dt)):
        c.step()
    assert not t.alive
    for u in c.heroes(PLAYER):
        u.alive = False
    c._check_end()
    assert c.result == "defeat"


def test_mine_triggers_only_on_enemies():
    c = Combat(DATA, 1, squad=squad_of(["alchemist", "warrior", "mage", "priest"]))
    al, f = unit(c, "alchemist"), foe(c)
    cell = (4, 3)
    c._apply_one(al, {"type": "hazard", "hazard": "mine", "duration": 30}, cell, None)
    al.cell = cell
    c._cell_effects(al, c.dt)
    assert c.grid.get(cell).hazard == "mine"
    al.cell = (0, 0)
    f.cell = cell
    hp = f.hp
    c._cell_effects(f, c.dt)
    assert f.hp < hp and c.grid.get(cell).hazard is None and f.stun > 0


def test_oil_and_fire_make_a_blaze():
    c = Combat(DATA, 1, squad=squad_of(["alchemist", "warrior", "mage", "priest"]))
    al, f = unit(c, "alchemist"), foe(c)
    c.apply_status(f, "oil", al)
    hp = f.hp
    c.damage(f, 10, al, "fire", "spell")
    assert "blaze" in f.reaction_cd and hp - f.hp > 20
    assert c.grid.get(f.cell).hazard == "fire" or c.grid.get(f.cell).terrain == "water"


def test_storm_on_wet_target_shocks():
    c = Combat(DATA, 1, squad=squad_of(["shaman", "warrior", "mage", "priest"]))
    s, f = unit(c, "shaman"), foe(c)
    c.apply_status(f, "water", s)
    c.damage(f, 10, s, "storm", "spell")
    assert "shock" in f.reaction_cd and f.stun > 0


def test_revive_raises_fallen_ally():
    c = Combat(DATA, 1, squad=squad_of(["priest", "warrior", "mage", "archer"], path="lifekeeper"))
    p, w = unit(c, "priest"), unit(c, "warrior")
    c._kill(w)
    c.revive(p, {"pct": 0.35, "radius": 1}, w.cell)
    assert w.alive and w.hp == int(w.max_hp * 0.35)


def test_poison_halves_healing():
    c = Combat(DATA, 1, squad=squad_of(["warrior", "archer", "mage", "priest"]))
    w = unit(c, "warrior")
    w.hp = 50
    c.apply_status(w, "poison")
    assert c.heal(w, 20) == 10


def test_control_looks_come_from_skill_and_reaction():
    c = Combat(DATA, 1, squad=squad_of(["druid", "warrior", "mage", "priest"]))
    druid, f = unit(c, "druid"), foe(c)
    c._skill = "entangle"
    c.apply_effects(druid, [{"type": "stun", "duration": 1.0}], f.cell, f)
    assert f.stun > 0 and f.stun_look == "root" and f.stun_total == 1.0
    c._skill = None
    g = c.fighters(ENEMY)[1]
    c.apply_status(g, "water")
    c.apply_status(g, "ice")
    assert g.stun > 0 and g.stun_look == "freeze"
