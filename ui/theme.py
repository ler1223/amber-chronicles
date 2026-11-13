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

# стиль «янтарь и тёмное дерево»: тёплые тёмные панели, янтарная кайма, светлый тёплый текст
BG = (18, 16, 15)
PANEL = (40, 31, 24)
PANEL_DARK = (28, 21, 16)
PANEL_EDGE = (112, 82, 46)
AMBER = (232, 170, 72)
AMBER_DIM = (150, 106, 50)
TEXT = (240, 232, 216)
TEXT_DIM = (176, 160, 136)
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


def hero_tint(color):
    """Худ героя в цвете его класса: кайма (accent), приглушённая кайма (dim), заливка (fill) и заливка выбора (hot).
    Тёмные цвета классов (ассасин, некромант) высветляются, чтобы кайма читалась на тёмном дереве."""
    c = tuple(int(v) for v in color[:3])
    lum = 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
    acc = mix(c, (255, 255, 255), min(0.5, (165 - lum) / 220)) if lum < 165 else c
    return {"accent": acc, "dim": mix(acc, PANEL, 0.5), "fill": mix(PANEL, c, 0.14), "hot": mix(PANEL, c, 0.32)}


_ORN = {}


def orn(name, w=None, h=None, flip=(False, False)):
    """Украшение интерфейса (лист UI: assets/sprites/ui_*.png, высокое разрешение) в нужном размере или None."""
    key = (name, w, h, flip)
    if key not in _ORN:
        import os
        src = _ORN.get((name, "src"))
        if (name, "src") not in _ORN:
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sprites",
                                f"{name}.png")
            src = None
            if os.path.exists(path):
                try:
                    src = pygame.image.load(path)
                    r = src.get_bounding_rect()
                    src = src.subsurface(r).copy() if r.w and r.h else src
                except pygame.error:
                    src = None
            _ORN[(name, "src")] = src
        img = None
        if src is not None:
            if w and not h:
                h = max(1, round(src.get_height() * w / src.get_width()))
            elif h and not w:
                w = max(1, round(src.get_width() * h / src.get_height()))
            img = pygame.transform.smoothscale(src, (w, h)) if w and h else src
            if flip != (False, False):
                img = pygame.transform.flip(img, *flip)
        if len(_ORN) > 400:
            srcs = {k: v for k, v in _ORN.items() if k[1] == "src"}
            _ORN.clear()
            _ORN.update(srcs)
        _ORN[key] = img
    return _ORN[key]


def divider(surf, cx, y, w, color=None):
    """Разделитель под заголовком: орнамент (лист UI) или тонкая янтарная линия с ромбиком."""
    img = orn("ui_divider", int(w))
    if img is not None and w >= 40:
        surf.blit(img, (cx - img.get_width() // 2, y - img.get_height() // 2))
        return
    col = color or AMBER_DIM
    pygame.draw.line(surf, col, (cx - w // 2, y), (cx + w // 2, y), 1)
    pygame.draw.polygon(surf, AMBER, [(cx, y - 4), (cx + 4, y), (cx, y + 4), (cx - 4, y)])


def frame(surf, rect, alpha=238, accent=None, corners=True, radius=7, fill=None, corner=None):
    """Панель «тёмное дерево»: заливка с тёмным низом, тёмный контур, кайма (по умолчанию янтарная) и ромбики в
    углах (corner — их цвет, у панелей героя — цвет класса)."""
    rect = pygame.Rect(rect)
    if rect.w < 4 or rect.h < 4:
        return rect
    accent = accent or AMBER_DIM
    box = pygame.Surface(rect.size, pygame.SRCALPHA)
    top = fill or PANEL
    pygame.draw.rect(box, (*top, alpha), box.get_rect(), border_radius=radius)
    low = pygame.Rect(0, rect.h // 2, rect.w, rect.h - rect.h // 2)
    pygame.draw.rect(box, (*mix(top, (0, 0, 0), 0.25), alpha), low,
                     border_bottom_left_radius=radius, border_bottom_right_radius=radius)
    pygame.draw.rect(box, (10, 7, 5, 230), box.get_rect(), 1, border_radius=radius)
    pygame.draw.rect(box, (*accent, 220), box.get_rect().inflate(-2, -2), 1, border_radius=max(1, radius - 1))
    surf.blit(box, rect)
    if corners and rect.w > 24 and rect.h > 24:
        big = min(rect.w, rect.h) >= 90
        cs = int(max(14, min(40, min(rect.w, rect.h) * 0.16)))
        name = "ui_corner" if big else "ui_corner_small"
        if orn(name, cs, cs) is not None and corner is None:       # уголки-завитки (лист UI)
            for (x, y), fl in (((rect.x - 2, rect.y - 2), (False, False)), ((rect.right - cs + 2, rect.y - 2), (True, False)),
                               ((rect.x - 2, rect.bottom - cs + 2), (False, True)),
                               ((rect.right - cs + 2, rect.bottom - cs + 2), (True, True))):
                surf.blit(orn(name, cs, cs, fl), (x, y))
            return rect
        for cx, cy in ((rect.x + 3, rect.y + 3), (rect.right - 4, rect.y + 3),
                       (rect.x + 3, rect.bottom - 4), (rect.right - 4, rect.bottom - 4)):
            pygame.draw.polygon(surf, corner or AMBER, [(cx, cy - 3), (cx + 3, cy), (cx, cy + 3), (cx - 3, cy)])
    return rect


def badge(surf, s, center, size=15, color=None, bg=None, r=None):
    """Круглая плашка с буквой клавиши (Q, W, E, R) или числом."""
    color = color or (30, 20, 10)
    bg = bg or AMBER
    r = r or size * 0.75
    pygame.draw.circle(surf, (12, 8, 6), center, r + 1)
    pygame.draw.circle(surf, bg, center, r)
    pygame.draw.circle(surf, mix(bg, (255, 255, 255), 0.35), center, r, 1)
    text(surf, s, center, size, color, True, center=True)
