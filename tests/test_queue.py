"""Очередь приказов (Shift): ход, атака и навыки по порядку; навык в очереди ждёт AP."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_rework1 import battle, hero, put, run  # noqa: E402
from sim.teams import ENEMY  # noqa: E402


def test_queue_runs_move_then_attack_then_skill():
    c = battle(["warrior", "archer", "mage", "priest"])
    w = hero(c, "warrior")
    foes = c.fighters(ENEMY)
    for f in foes[1:]:
        f.alive = False
    f = foes[0]
    put(w, (0, 0))
    put(f, (5, 3))
    f.max_hp = f.hp = 5000
    c.order_move(w, (2, 0))
    assert c.queue_order(w, {"type": "move", "cell": (3, 2)})[0]
    assert c.queue_order(w, {"type": "skill", "skill": "power_strike", "target": f})[0]
    assert c.queue_order(w, {"type": "attack", "target": f})[0]
    assert len(w.queue) == 3
    seen = []
    for _ in range(int(12 / c.dt)):
        c.step()
        o = w.order
        key = (o["type"], o.get("cell"), o.get("skill")) if o else None
        if key and (not seen or seen[-1] != key):
            seen.append(key)
    assert [k[0] for k in seen[:4]] == ["move", "move", "skill", "attack"], seen
    assert seen[1][1] == (3, 2)
    assert not w.queue


def test_queued_skill_waits_for_ap_and_plain_order_clears_queue():
    c = battle(["warrior", "archer", "mage", "priest"])
    w = hero(c, "warrior")
    f = c.fighters(ENEMY)[0]
    put(w, (2, 2))
    put(f, (3, 2))
    w.ap = 0
    assert c.queue_order(w, {"type": "skill", "skill": "power_strike", "target": f})[0]
    assert w.order and w.order["type"] == "skill"
    run(c, 0.3)
    assert w.order and w.order["skill"] == "power_strike"       # ждёт AP, а не отменяется
    c.queue_order(w, {"type": "move", "cell": (0, 0)})
    c.order_move(w, (1, 1))
    assert not w.queue


def test_scene_shift_select_groups_and_queue():
    import pygame
    from test_scene import DATA as SD, click, frame, key  # noqa: F401
    from game.battle_scene import BattleScene
    from sim.teams import PLAYER
    s = BattleScene(SD, 0)
    key(s, pygame.K_SPACE)
    frame(s)
    war, archer, mage, priest = s.combat.alive(PLAYER)
    slime = s.combat.alive(ENEMY)[0]
    click(s, war.cell)
    pygame.key.set_mods(pygame.KMOD_SHIFT)
    try:
        click(s, mage.cell)                                  # Shift+клик — добавить
        assert set(s.selected_units) == {war, mage}
        click(s, (2, 5), button=3)                           # Shift+ПКМ — ход в очередь
        click(s, slime.cell, button=3)                       # Shift+ПКМ по врагу — атака в очередь
        assert any(q["type"] == "attack" for q in war.queue + ([war.order] if war.order else []))
    finally:
        pygame.key.set_mods(0)
    pygame.key.set_mods(pygame.KMOD_CTRL)
    try:
        key(s, pygame.K_1)                                   # Ctrl+1 — запомнить группу
    finally:
        pygame.key.set_mods(0)
    click(s, archer.cell)
    assert s.selected_units == [archer]
    key(s, pygame.K_1)                                       # 1 — вернуть группу
    assert set(s.selected_units) == {war, mage}
    key(s, pygame.K_ESCAPE)                                  # Esc — очистить очередь
    assert not war.queue and not mage.queue
