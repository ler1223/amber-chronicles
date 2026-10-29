"""Тесты симуляции без окна: python -m pytest tests"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.combat import ENEMY, PLAYER, Combat  # noqa: E402
from sim.data import GameData  # noqa: E402

DATA = GameData()


def make(enc=0, ai_teams=(ENEMY,)):
    c = Combat(DATA, enc, ai_teams=ai_teams)
    return c, c.alive(PLAYER), c.alive(ENEMY)


def run(c, seconds):
    for _ in range(int(seconds / c.dt)):
        c.step()


def events(c, kind):
    return [e for e in c.events if e["t"] == kind]


def test_steam_reaction():
    c, _, foes = make()
    slime = foes[0]
    c.apply_status(slime, "water")
    hp = slime.hp
    c.damage(slime, 10, None, "fire", "spell")
    r = events(c, "reaction")
    assert r and r[0]["id"] == "steam"
    assert "water" not in slime.statuses and "fire" not in slime.statuses
    assert slime.hp < hp - 10 + slime.armor  # удар + пар


def test_melt_doubles_hit():
    c, _, foes = make()
    slime = foes[0]
    c.apply_status(slime, "ice")
    dealt = c.damage(slime, 20, None, "fire", "spell")
    assert dealt == 40 - slime.armor


def test_freeze_stuns_and_interrupts_cast():
    c, squad, foes = make()
    mage = next(u for u in squad if u.proto_id == "mage")
    mage.pp = 0  # без концентрации
    ok, _ = c.order_skill(mage, "fireball", foes[0].cell)
    assert ok
    mage.order = {"type": "skill", "skill": "fireball", "target": mage.cell}
    c._start_cast(mage, "fireball", mage.cell)
    assert mage.cast
    c.apply_status(mage, "water")
    c.apply_status(mage, "ice")
    assert mage.stun > 0 and mage.cast is None


def test_concentration_saves_cast():
    c, squad, _ = make()
    mage = next(u for u in squad if u.proto_id == "mage")
    mage.pp = mage.pp_max          # шкала героя стартует пустой — заполняем
    c._start_cast(mage, "fireball", mage.cell)
    c.apply_stun(mage, 1.0)
    assert mage.cast is not None and mage.pp == 0


def test_reaction_cooldown():
    c, _, foes = make()
    slime = foes[0]
    for _ in range(2):
        c.apply_status(slime, "water")
        c.apply_status(slime, "ice")
    assert len(events(c, "reaction")) == 1


def test_block_spends_pp():
    c, squad, _ = make()
    war = squad[0]
    war.pp = war.pp_max
    c.damage(war, 20, None, None, "melee")
    assert war.pp == war.pp_max - 1
    assert war.hp == war.max_hp - (10 - war.armor)
    p = events(c, "passive")[0]
    assert p["unit"] is war and p["kind"] == "block" and p["detail"]
    assert events(c, "damage")[0]["blocked"] == "Блок"
    assert any("Блок" in e["text"] for e in events(c, "log"))


def test_dodge_only_melee():
    c, squad, _ = make()
    archer = squad[1]
    archer.pp = archer.pp_max
    assert c.damage(archer, 20, None, None, "melee") == 0
    assert c.damage(archer, 20, None, None, "spell") > 0


def test_cancel_cast_refunds_ap():
    c, squad, foes = make()
    mage = squad[2]
    ap = mage.ap
    c._start_cast(mage, "fireball", foes[0].cell)
    assert mage.ap == ap - DATA.skills["fireball"]["ap"]
    c.order_move(mage, (0, 0))
    assert mage.ap == ap and mage.cast is None


def test_skill_resumes_previous_attack_target():
    c, squad, foes = make()
    c.ais = []
    archer = squad[1]
    first, other = foes[0], foes[1]
    c.order_attack(archer, first)
    c.order_skill(archer, "aimed_shot", other)
    for _ in range(200):  # сначала подойдёт на дальность
        c.step()
        if archer.cast:
            break
    assert archer.cast and archer.order == {"type": "attack", "target": first}
    run(c, 1.0)
    assert archer.cast is None and archer.order["target"] is first


def test_skill_on_enemy_then_attacks_it_when_idle():
    c, squad, foes = make()
    c.ais = []
    war = squad[0]
    target = foes[0]
    c.order_skill(war, "power_strike", target)
    run(c, 6)
    assert war.order and war.order["type"] == "attack" and war.order["target"] is target


def test_move_order_forgets_target():
    c, squad, foes = make()
    c.ais = []
    mage = squad[2]
    mage.last_target = foes[0]
    c.order_move(mage, (0, 0))
    c.order_skill(mage, "flashpoint", mage)
    run(c, 2)
    assert mage.order is None or mage.order["type"] != "attack"


def test_redeploy_rules():
    c, squad, foes = make()
    war, archer = squad[0], squad[1]
    assert c.redeploy(war, (0, 0))
    assert not c.redeploy(war, (5, 0))          # вне зоны
    assert not c.redeploy(war, (1, 2))          # укрытие, непроходимо
    old = archer.cell
    assert c.redeploy(war, old) and archer.cell == (0, 0)
    c.step()
    assert not c.redeploy(war, (0, 5))          # бой уже идёт


def test_move_order_reaches_cell():
    c, squad, _ = make()
    war = squad[0]
    c.ais = []
    c.order_move(war, (2, 5))
    run(c, 5)
    assert war.cell == (2, 5)


def test_ice_freezes_water_cell():
    c, _, _ = make()
    c._cell_tag((4, 2), "ice")
    assert c.grid.get((4, 2)).hazard == "ice"
    c._cell_tag((4, 2), "fire")
    assert c.grid.get((4, 2)).hazard is None


def test_all_encounters_finish_with_ai_on_both_sides():
    for i in range(len(DATA.encounters)):
        c = Combat(DATA, i, ai_teams=(PLAYER, ENEMY))
        run(c, 240)
        assert c.result in ("victory", "defeat"), (DATA.encounters[i]["id"], c.time)
        kinds = {e["t"] for e in c.events}
        assert "damage" in kinds and "death" in kinds
