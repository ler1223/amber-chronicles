"""Состояния по тегам, очищение, реакции союзника и среды, правила взаимодействий, цена хода, сдвиги, маршрут."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim import conditions as C  # noqa: E402
from sim import movement as M  # noqa: E402
from sim.build import build_proto  # noqa: E402
from sim.combat import Combat  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim.teams import ENEMY  # noqa: E402

DATA = GameData()


def battle(classes=("warrior", "archer", "mage", "priest"), enc=1):
    squad = [{"cls": c, "proto": build_proto(DATA, c)} for c in classes]
    c = Combat(DATA, enc, squad=squad)
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


def test_purify_removes_freeze_stun_root_and_debuffs_but_not_stasis():
    c = battle()
    pr, war = hero(c, "priest"), hero(c, "warrior")
    for look in ("freeze", "stun", "root"):
        c.apply_stun(war, 3.0, look)
        war.statuses["fire"] = 4.0
        c.add_buff(war, "slow", 1.5, 5)
        c.add_buff(war, "armor", 3, 5)                     # полезный бафф остаётся
        cast(c, pr, "purify", war)
        assert war.stun == 0 and "fire" not in war.statuses and "slow" not in war.buffs and "armor" in war.buffs
    war.stasis = 3.0
    c.apply_stun(war, 3.0, "stasis")
    cast(c, pr, "purify", war)
    assert war.stun > 0                                    # стазис — защита, очищение его не снимает


def test_holy_water_puts_out_burning_ally_without_hurting():
    c = battle()
    pr, war = hero(c, "priest"), hero(c, "warrior")
    put(war, (3, 3))
    war.hp = 100
    war.statuses["fire"] = 4.0
    cast(c, pr, "holy_water", (3, 3))
    assert "fire" not in war.statuses and war.hp > 100


def test_ally_water_neutralizes_but_enemy_water_reacts():
    c = battle()
    war, pr = hero(c, "warrior"), hero(c, "priest")
    foe = c.fighters(ENEMY)[0]
    war.statuses["fire"] = 4.0
    hp = war.hp
    c._touch_status(war, "water", pr)                      # союзник плеснул водой — потушил
    assert not war.statuses and war.hp == hp
    assert any(e["t"] == "reaction" and e.get("friendly") for e in c.events)
    foe.statuses["fire"] = 4.0
    fhp = foe.hp
    c._touch_status(foe, "water", war)                     # враг — пар, урон
    assert foe.hp < fhp


def test_standing_in_water_extinguishes():
    c = battle(enc=0)                                       # «Трясина»: вода посередине
    war = hero(c, "warrior")
    water = next(p for p, cell in c.grid.cells.items() if cell.terrain == "water" and c.is_free(p))
    put(war, water)
    war.statuses["fire"] = 4.0
    run(c, 0.2)
    assert "fire" not in war.statuses and "water" in war.statuses
    assert any(e["t"] == "reaction" and e.get("friendly") and e["unit"] is war for e in c.events)


def test_rule_burning_collision_ignites_target():
    c = battle(("ram", "warrior", "archer", "mage"))
    ram = hero(c, "ram")
    a, b = c.fighters(ENEMY)[:2]
    put(ram, (2, 2))
    put(a, (3, 2))
    put(b, (4, 2))
    a.statuses["fire"] = 4.0
    cast(c, ram, "kick", (3, 2))
    assert "fire" in b.statuses and ("burning_ram", "collision") in c.rules.fired


def test_rule_from_unit_proto():
    """Правило героя: его удар с огнём — ещё и масло на цель (пример эффекта на результат другого)."""
    proto = build_proto(DATA, "mage")
    proto["rules"] = [{"id": "test", "on": "hit", "tags": ["fire"], "owner": "source",
                       "do": [{"type": "status", "tag": "oil", "to": "unit"}]}]
    c = Combat(DATA, 1, squad=[{"cls": "mage", "proto": proto}])
    c.ais = []
    mage, foe = c.heroes()[0], c.fighters(ENEMY)[0]
    c.damage(foe, 10, mage, "fire", "spell")
    assert ("test", "hit") in c.rules.fired


def test_conditions_have_tags():
    c = battle()
    war = hero(c, "warrior")
    c.apply_stun(war, 2.0, "root")
    war.statuses["ice"] = 3.0
    tags = C.unit_tags(c, war)
    assert {"control", "root", "nature", "element", "ice", "cold"} <= tags


def test_water_slows_humans_not_slimes():
    c = battle(enc=0)
    war = hero(c, "warrior")
    slime = next(u for u in c.fighters(ENEMY) if u.proto_id == "slime")
    water = next(p for p, cell in c.grid.cells.items() if cell.terrain == "water")
    assert M.step_cost(c, war, water) > 1.5 and M.step_cost(c, slime, water) == 1.0
    grass = next(p for p, cell in c.grid.cells.items() if cell.terrain == "grass")
    assert M.step_cost(c, war, grass) == 1.0


def test_everything_but_walls_moves_and_collides():
    c = battle(("ram", "shaman", "archer", "mage"))
    ram, sh = hero(c, "ram"), hero(c, "shaman")
    put(ram, (2, 2))
    totem = c.summon(sh, {"unit": "totem_heal", "duration": 9}, (3, 2))
    put(totem, (3, 2))
    cast(c, ram, "kick", (3, 2))
    assert totem.cell != (3, 2)                            # тотем сдвинулся
    wall = c.spawn_object("ice_wall", (6, 2))
    c.knockback((5, 2), wall, 2, ram)
    assert wall.cell == (6, 2) and not M.movable(c, wall)
    foe = c.fighters(ENEMY)[0]
    put(foe, (4, 4))
    rock = c.spawn_object("boulder", (2, 4))
    hp = foe.hp
    put(ram, (1, 4))
    c.pull(ram, foe, 3)                                    # валун на пути — столкновение
    assert foe.hp < hp and rock.alive


def test_player_path_is_followed():
    c = battle(enc=0)
    war = hero(c, "warrior")
    put(war, (0, 0))
    route = [(1, 0), (2, 0), (3, 0), (3, 1)]
    ok, _ = c.order_path(war, [(3, 0), (3, 1)])
    assert ok and war.order["cells"] == route
    seen = [war.cell]
    for _ in range(int(8 / c.dt)):
        c.step()
        if not seen or seen[-1] != war.cell:
            seen.append(war.cell)
        if war.order is None:
            break
    assert seen == [(0, 0)] + route


def test_path_through_water_takes_longer():
    c = battle(enc=0)
    war = hero(c, "warrior")
    water = [p for p, cell in c.grid.cells.items() if cell.terrain == "water"]
    land = [p for p, cell in c.grid.cells.items() if cell.terrain == "grass"]
    assert M.path_time(c, war, water[:2]) > M.path_time(c, war, land[:2])
