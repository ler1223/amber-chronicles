"""Цвета, шрифты, раскладка экрана."""
from contextlib import contextmanager

import pygame

from ui import layout, projection

SCREEN_W, SCREEN_H = layout.BASE_W, layout.BASE_H


def content_ox():
    """Левый край центральной колонки 1280 (для экранов, которые остаются колонкой)."""
    return layout.content_ox(SCREEN_W)


def battle_rects():
    """(GRID_X, RIGHT_X) для текущей ширины холста."""
    return layout.battle_rects(SCREEN_W)


@contextmanager
def design(width=layout.BASE_W, height=layout.BASE_H):
    """Временно вернуть координаты проектирования 1280×800 (сцены-«колонки» рисуются в этот размер)."""
    global SCREEN_W, SCREEN_H
    old = (SCREEN_W, SCREEN_H)
    SCREEN_W, SCREEN_H = width, height
    try:
        yield
    finally:
        SCREEN_W, SCREEN_H = old


# вид 3/4: клетка сплюснута по вертикали, юниты стоят «ногами» чуть ниже центра клетки
CELL_W, CELL_H = 88, 72
CELL = CELL_W
GRID_X, GRID_Y = 24, 100
GRID_W, GRID_H = 10 * CELL_W, 6 * CELL_H
FEET_DY = 14
UNIT_R = 24

BG = (18, 20, 24)
PANEL = (30, 33, 40)
PANEL_EDGE = (58, 62, 74)
TEXT = (225, 228, 235)
TEXT_DIM = (140, 146, 160)
GRID_LINE = (20, 24, 22)

TEAM_PLAYER = (90, 180, 255)
TEAM_ENEMY = (240, 80, 70)
SELECT = (255, 220, 80)
AP_COLOR = (90, 190, 255)
PP_COLOR = (255, 120, 190)
HEAL = (110, 230, 120)
DMG_TO_PLAYER = (255, 110, 100)
DMG_TO_ENEMY = (255, 255, 255)
CAST = (255, 170, 60)

_fonts = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        f = pygame.font.SysFont("segoeui,arial,dejavusans", size, bold=bold)
        _fonts[key] = f
    return _fonts[key]


_renders = {}
_wraps = {}
CACHE_LIMIT = 4000


def render(s, size, color, bold=False):
    """Готовая надпись из кэша: интерфейс перерисовывается каждый кадр, а текст почти не меняется."""
    key = (s, size, tuple(color), bold)
    img = _renders.get(key)
    if img is None:
        if len(_renders) > CACHE_LIMIT:
            _renders.clear()
        img = _renders[key] = font(size, bold).render(s, True, color)
    return img


def text(surf, s, pos, size=16, color=TEXT, bold=False, center=False, shadow=False):
    img = render(s, size, color, bold)
    r = img.get_rect()
    if center:
        r.center = pos
    else:
        r.topleft = pos
    if shadow:
        surf.blit(render(s, size, (0, 0, 0), bold), r.move(1, 1))
    surf.blit(img, r)
    return r


def wrap(s, size, width, bold=False):
    key = (s, size, width, bold)
    if key in _wraps:
        return _wraps[key]
    f = font(size, bold)
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if f.size(trial)[0] <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if len(_wraps) > CACHE_LIMIT:
        _wraps.clear()
    _wraps[key] = lines
    return list(lines)


def cell_rect(pos):
    """Прямоугольник на экране, охватывающий клетку (поле — наклонная плоскость, см. ui/projection.py)."""
    pts = projection.cell_corners(pos)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return pygame.Rect(int(min(xs)), int(min(ys)), int(max(xs) - min(xs)), int(max(ys) - min(ys)))


def cell_center(pos):
    """Точка над центром клетки на высоте пояса — сюда целятся снаряды и встают надписи."""
    x, y, _ = projection.project(pos[0] + 0.5, pos[1] + 0.5, 0.3)
    return x, y


def cell_feet(pos):
    """Точка на земле в центре клетки — там стоят ноги юнита."""
    return projection.cell_screen(pos)


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
