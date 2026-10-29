"""Партия 1 переработки героев: телохранитель, дозор, вспышка, обет, бочки и фитиль, ритм, таран."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.build import build_proto  # noqa: E402
from sim.combat import Combat  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim.teams import ENEMY, NEUTRAL  # noqa: E402

DATA = GameData()


def battle(classes, enc=1, path=None):
    squad = [{"cls": c, "proto": build_proto(DATA, c, path=path if i == 0 else None)} for i, c in enumerate(classes)]
    c = Combat(DATA, enc, squad=squad)
    return quiet(c)


def quiet(c):
    """Без ИИ, без автокаста и без бочек и валунов карты — проверяем только механику."""
    c.ais = []
    c.autocaster.update = lambda dt: None
    for u in c.units:
        if u.obj:
            u.alive = False
    return c


def hero(c, cls):
    return next(u for u in c.heroes() if u.proto_id == cls)


def foe(c, i=0):
    return c.fighters(ENEMY)[i]


def put(u, cell):
    u.cell = u.prev_cell = tuple(cell)


def cast(c, u, sid, target):
    c._resolve_skill(u, sid, target)


def run(c, sec):
    for _ in range(int(sec / c.dt)):
        c.step()


def events(c, kind):
    return [e for e in c.events if e["t"] == kind]


def test_bodyguard_takes_hits_for_adjacent_ward():
    c = battle(["warrior", "archer", "mage", "priest"])
    war, mage = hero(c, "warrior"), hero(c, "mage")
    put(mage, (2, 2))
    put(war, (0, 0))
    cast(c, war, "guard_ally", mage)
    assert war.cell != (0, 0) and abs(war.cell[0] - 2) <= 1 and mage.guarded_by is war
    hp_w, hp_m = war.hp, mage.hp
    c.damage(mage, 20, foe(c), None, "melee")
    assert mage.hp == hp_m and war.hp < hp_w and events(c, "intercept")
    assert war.pp >= 1 or events(c, "passive")         # Стойкость от перехвата — или сразу ушла в Блок
    put(war, (6, 5))                                   # отошёл — защита не работает
    c.damage(mage, 20, foe(c), None, "melee")
    assert mage.hp < hp_m


def test_two_guards_do_not_loop():
    c = battle(["warrior", "archer", "mage", "priest"])
    a, b = hero(c, "warrior"), hero(c, "archer")
    put(a, (1, 1))
    put(b, (1, 2))
    a.guarded_by, a.guard_time, b.guarded_by, b.guard_time = b, 5, a, 5
    c.damage(a, 10, foe(c), None, "melee")            # не уходит в бесконечный перехват


def test_overwatch_fires_on_entry_and_on_push():
    c = battle(["archer", "warrior", "mage", "ram"])
    arch, f = hero(c, "archer"), foe(c)
    put(arch, (1, 2))
    put(f, (6, 2))
    cast(c, arch, "overwatch", (4, 2))
    assert arch.watch
    hp = f.hp
    c._place(f, (5, 2), 0.3)                           # шаг в зону
    assert f.hp < hp and not arch.watch and events(c, "watch_fire")
    # толчок в зону тоже считается
    g = foe(c, 1)
    put(g, (7, 4))
    cast(c, arch, "overwatch", (5, 4))
    hp = g.hp
    c.knockback((8, 4), g, 2)
    assert g.hp < hp


def test_flashpoint_detonates_burning_cells_and_units():
    c = battle(["mage", "warrior", "archer", "priest"])
    mage, f, g = hero(c, "mage"), foe(c), foe(c, 1)
    put(mage, (2, 2))
    put(f, (4, 2))
    put(g, (5, 4))
    cell = c.grid.get((4, 2))
    cell.hazard, cell.hazard_time = "fire", 5
    g.statuses["fire"] = 3.0
    hf, hg = f.hp, g.hp
    cast(c, mage, "flashpoint", mage)
    assert f.hp < hf and g.hp < hg and cell.hazard is None and "fire" not in g.statuses
    assert hg - g.hp > hf - f.hp - 5                   # горящий получает больше


def test_vow_heals_later_and_cleanses():
    c = battle(["priest", "warrior", "archer", "mage"])
    pr, war = hero(c, "priest"), hero(c, "warrior")
    war.hp = 40
    war.statuses["poison"] = 4.0
    cast(c, pr, "vow", war)
    assert war.hp == 40 and c.pending_on(war)
    run(c, 2.6)
    assert war.hp > 100 and "poison" not in war.statuses and not c.pending_on(war)


def test_powder_keg_placed_and_fuse_detonates():
    c = battle(["alchemist", "warrior", "archer", "mage"])
    al, f = hero(c, "alchemist"), foe(c)
    put(al, (2, 2))
    put(f, (4, 3))
    cast(c, al, "powder_keg", (4, 2))
    keg = next(u for u in c.units if u.obj and u.owner is al)
    assert keg.team == NEUTRAL and keg.cell == (4, 2)
    hp = f.hp
    cast(c, al, "fuse", al)
    assert keg.fuse > 0 and keg.alive
    run(c, 2.2)
    assert not keg.alive and f.hp < hp


def test_keg_limit_breaks_oldest():
    c = battle(["alchemist", "warrior", "archer", "mage"])
    al = hero(c, "alchemist")
    put(al, (2, 2))
    for cell in ((3, 0), (3, 1), (3, 3), (3, 4)):
        cast(c, al, "powder_keg", cell)
    mine = [u for u in c.units if u.obj and u.owner is al and u.alive]
    assert len(mine) == 3


def test_ram_kick_pushes_ally_and_barrel():
    c = battle(["ram", "warrior", "archer", "mage"])
    ram, war = hero(c, "ram"), hero(c, "warrior")
    put(ram, (2, 2))
    put(war, (3, 2))
    hp = war.hp
    cast(c, ram, "kick", (3, 2))
    assert war.cell == (5, 2) and war.hp == hp            # союзника толкает без урона
    put(war, (0, 0))
    o = c.spawn_object("barrel_powder", (3, 2))
    f = foe(c)
    put(f, (5, 2))
    hp = f.hp
    cast(c, ram, "kick", (3, 2))
    run(c, 0.3)
    assert not o.alive and f.hp < hp                  # бочка долетела до врага и взорвалась


def test_ram_rush_hits_first_and_collides():
    c = battle(["ram", "warrior", "archer", "mage"])
    ram, f = hero(c, "ram"), foe(c)
    put(ram, (1, 2))
    put(f, (5, 2))
    for u in c.fighters(ENEMY)[1:]:
        put(u, (9, 0 if u is c.fighters(ENEMY)[1] else 5))
    hp = f.hp
    cast(c, ram, "rush", (5, 2))
    assert ram.cell == (4, 2) and f.hp < hp and f.cell[0] >= 6


def test_momentum_passive_pushes_further():
    c = battle(["ram", "warrior", "archer", "mage"])
    ram, f = hero(c, "ram"), foe(c)
    put(ram, (2, 2))
    put(f, (3, 2))
    for u in c.fighters(ENEMY)[1:]:
        put(u, (9, 5))
    ram.pp = ram.pp_max
    cast(c, ram, "kick", (3, 2))
    assert f.cell == (6, 2) and events(c, "passive")


def test_toss_throws_neighbour_to_cell():
    proto = build_proto(DATA, "ram", path="thrower")
    assert "toss" in proto["skills"]
    c = quiet(Combat(DATA, 1, squad=[{"cls": "ram", "proto": proto}] +
                     [{"cls": k, "proto": DATA.classes[k]} for k in ("warrior", "archer", "mage")]))
    ram, f = hero(c, "ram"), foe(c)
    put(ram, (3, 2))
    put(f, (4, 2))
    cast(c, ram, "toss", (2, 0))
    assert f.cell == (2, 0) and events(c, "toss")


def test_song_counts_notes_and_finale_scales():
    c = battle(["bard", "warrior", "archer", "mage"])
    bard, war = hero(c, "bard"), hero(c, "warrior")
    put(bard, (1, 1))
    put(war, (1, 2))
    cast(c, bard, "rhythm", bard)
    assert bard.song
    for _ in range(3):
        cast(c, war, "taunt", war)
    run(c, 8.2)
    fin = events(c, "finale")
    assert fin and fin[0]["notes"] == 3 and war.buff("atk_mult", 1) > 1.15


def test_line_push_from_fault_line():
    proto = build_proto(DATA, "ram", path="breaker")
    c = quiet(Combat(DATA, 1, squad=[{"cls": "ram", "proto": proto}] +
                     [{"cls": k, "proto": DATA.classes[k]} for k in ("warrior", "archer", "mage")]))
    ram, f = hero(c, "ram"), foe(c)
    put(ram, (2, 2))
    put(f, (3, 2))
    for u in c.fighters(ENEMY)[1:]:
        put(u, (9, 5))
    cast(c, ram, "fault_line", (4, 2))
    assert f.cell[0] >= 5
