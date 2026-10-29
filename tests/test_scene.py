"""Проверка ввода сцены боя без окна (SDL dummy)."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from game.battle_scene import BattleScene  # noqa: E402
from sim.combat import ENEMY, PLAYER  # noqa: E402
from sim.data import GameData  # noqa: E402
from ui import theme as T  # noqa: E402

pygame.init()
SCREEN = pygame.display.set_mode((T.SCREEN_W, T.SCREEN_H))
DATA = GameData()


def click(scene, cell, button=1):
    x, y = T.cell_center(cell)
    scene.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(x, y)))
    scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x, y), button=button))


def key(scene, k):
    scene.handle(pygame.event.Event(pygame.KEYDOWN, key=k))


def frame(scene, dt=1 / 60):
    scene.update(dt)
    scene.draw(SCREEN)


def mouse(scene, kind, pos, button=1):
    scene.handle(pygame.event.Event(kind, pos=pos, button=button))


def test_deploy_click_drag_swap_and_zone():
    s = BattleScene(DATA, 0)
    frame(s)
    assert s.phase == "deploy"
    war, archer, mage, priest = s.combat.alive(PLAYER)
    zone = s.combat.deploy_cells()

    # клик по юниту, клик по клетке
    click(s, war.cell)
    mouse(s, pygame.MOUSEBUTTONUP, T.cell_center(war.cell))
    assert s.picked is war
    click(s, (0, 5))
    assert war.cell == (0, 5) and s.picked is None

    # перетаскивание
    start = T.cell_center(mage.cell)
    mouse(s, pygame.MOUSEBUTTONDOWN, start)
    s.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=T.cell_center((2, 0))))
    assert s.dragging
    frame(s)
    mouse(s, pygame.MOUSEBUTTONUP, T.cell_center((2, 0)))
    assert mage.cell == (2, 0)

    # обмен местами
    a, b = archer.cell, priest.cell
    click(s, archer.cell)
    click(s, priest.cell)
    assert archer.cell == b and priest.cell == a

    # вне зоны нельзя
    click(s, war.cell)
    click(s, (6, 5))
    assert war.cell == (0, 5) and (6, 5) not in zone and s.toast

    # время стоит, пока не нажат «В бой»
    for _ in range(30):
        frame(s)
    assert s.combat.time == 0
    key(s, pygame.K_RETURN)
    assert s.phase == "battle" and s.paused

    # переигровка запоминает расстановку
    s.combat.result = "defeat"
    key(s, pygame.K_r)
    assert s.phase == "deploy"
    assert s.combat.alive(PLAYER)[0].cell == (0, 5)


def test_select_move_attack_and_skill():
    s = BattleScene(DATA, 0)
    key(s, pygame.K_RETURN)
    frame(s)
    assert s.paused
    war, archer, mage, priest = s.combat.alive(PLAYER)
    slime = s.combat.alive(ENEMY)[0]

    click(s, mage.cell)
    assert s.selected is mage
    key(s, pygame.K_q)
    assert s.targeting == "fireball"
    click(s, slime.cell)
    assert s.targeting is None
    assert mage.order["type"] == "skill" and mage.order["target"] == slime.cell

    key(s, pygame.K_2)
    assert s.selected is archer
    click(s, slime.cell)
    assert archer.order == {"type": "attack", "target": slime}

    key(s, pygame.K_TAB)
    assert s.selected is mage
    key(s, pygame.K_1)
    click(s, (2, 5), button=3)
    assert war.order == {"type": "move", "cell": (2, 5)}
    key(s, pygame.K_w)  # провокация — без прицеливания
    assert war.order["type"] == "skill" and s.targeting is None

    key(s, pygame.K_4)
    key(s, pygame.K_q)  # обет — нужна цель-союзник
    click(s, slime.cell)
    assert s.targeting == "vow" and s.toast
    click(s, war.cell)
    assert priest.order["target"] is war

    key(s, pygame.K_SPACE)
    for _ in range(600):
        frame(s)
    assert s.combat.time > 5
    assert any(f for f in s.view.log)


def test_restart_and_next_encounter():
    s = BattleScene(DATA, 0, autoplay=True)
    for _ in range(60 * 60):
        frame(s, 1 / 30)
        if s.combat.result:
            break
    assert s.combat.result
    key(s, pygame.K_n)
    assert s.encounter_index == 1 and not s.combat.result


def test_draw_route_with_right_mouse():
    s = BattleScene(DATA, 0)
    key(s, pygame.K_RETURN)
    war = s.combat.alive(PLAYER)[0]
    s._select(war)
    start = war.cell
    cells = [(start[0] + 1, start[1]), (start[0] + 2, start[1]), (start[0] + 2, start[1] + 1)]
    click(s, cells[0], button=3)                       # клик ПКМ — уже приказ «идти»
    assert war.order["type"] == "move" and s.route == [cells[0]]
    for c in cells[1:]:
        x, y = T.cell_center(c)
        s.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(x, y), buttons=(0, 0, 1)))
    frame(s)                                           # предпросмотр маршрута рисуется
    mouse(s, pygame.MOUSEBUTTONUP, T.cell_center(cells[-1]), button=3)
    assert war.order["type"] == "path" and war.order["cells"] == cells and s.route is None
