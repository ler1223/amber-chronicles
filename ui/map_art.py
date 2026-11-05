"""Карта похода: медальоны узлов, тропы пунктиром, ленточки подписей.

Иконка узла — assets/icons/map_<вид>.png (32×32, нарезка tools/import_sheet.py --set icons_map, промпт — лист F в
prompts_expedition.md). Пока картинки нет, рисуется пиксельная заглушка: скрещённые мечи, череп, корона, свиток,
костёр, кошель, звезда.
"""
import math
import os

import pygame

from ui import theme as T

ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icons")
WOOD = (52, 38, 26)
WOOD_DARK = (24, 17, 12)
PARCHMENT = (214, 192, 150)
_cache = {}


def icon(kind, size):
    """Иконка узла size×size: картинка из assets/icons или пиксельная заглушка ×2 (чёткие пиксели)."""
    key = (kind, size)
    if key not in _cache:
        path = os.path.join(ICON_DIR, f"map_{kind}.png")
        img = None
        if os.path.exists(path):
            try:
                img = pygame.image.load(path)
            except pygame.error:
                img = None
        if img is None:
            img = glyph(kind)
        _cache[key] = pygame.transform.scale(img, (size, size))
    return _cache[key]


def _px(s, col, pts):
    for x, y in pts:
        s.set_at((x, y), col)


def glyph(kind):
    """Заглушка 16×16 в пиксель-арте: силуэт со светом сверху и тёмным контуром."""
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    light, mid, dark = (236, 226, 204), (170, 160, 146), (40, 30, 24)
    if kind == "battle":                      # скрещённые мечи
        for i in range(10):
            _px(s, light, [(3 + i, 2 + i), (12 - i, 2 + i)])
        _px(s, mid, [(4 + i, 2 + i) for i in range(9)] + [(11 - i, 2 + i) for i in range(9)])
        for p in ((3, 12), (12, 12)):
            pygame.draw.line(s, (150, 100, 50), (p[0] - 2, p[1] - 1), (p[0] + 2, p[1] + 1), 2)
        _px(s, (110, 70, 40), [(1, 14), (14, 14), (2, 13), (13, 13)])
    elif kind in ("elite", "boss"):           # череп (у элиты — рога, у босса — корона)
        pygame.draw.ellipse(s, light, (3, 3, 10, 9))
        pygame.draw.rect(s, light, (5, 10, 6, 4))
        _px(s, dark, [(5, 7), (6, 7), (9, 7), (10, 7), (5, 8), (10, 8), (6, 8), (9, 8), (7, 10), (8, 10),
                      (6, 13), (8, 13), (10, 13)])
        if kind == "elite":
            _px(s, (200, 170, 120), [(2, 2), (2, 3), (3, 4), (13, 2), (13, 3), (12, 4), (1, 1), (14, 1)])
        else:
            gold = (240, 196, 70)
            pygame.draw.rect(s, gold, (4, 1, 8, 2))
            _px(s, gold, [(4, 0), (7, 0), (8, 0), (11, 0)])
            _px(s, (220, 60, 60), [(7, 1), (8, 1)])
    elif kind == "event":                     # свиток со знаком вопроса
        pygame.draw.rect(s, PARCHMENT, (3, 2, 10, 12))
        pygame.draw.rect(s, (170, 140, 100), (2, 1, 12, 2))
        pygame.draw.rect(s, (170, 140, 100), (2, 13, 12, 2))
        _px(s, dark, [(6, 4), (7, 4), (8, 4), (9, 5), (9, 6), (8, 7), (7, 8), (7, 9), (7, 11)])
    elif kind == "camp":                      # костёр
        pygame.draw.polygon(s, (240, 120, 40), [(4, 12), (8, 2), (12, 12)])
        pygame.draw.polygon(s, (255, 210, 90), [(6, 12), (8, 6), (10, 12)])
        pygame.draw.line(s, (120, 80, 50), (2, 14), (13, 12), 2)
        pygame.draw.line(s, (100, 66, 40), (2, 12), (13, 14), 2)
    elif kind == "shop":                      # кошель с монетой
        pygame.draw.ellipse(s, (160, 110, 60), (2, 5, 12, 10))
        pygame.draw.rect(s, (120, 80, 44), (5, 3, 6, 3))
        pygame.draw.circle(s, (250, 210, 80), (8, 10), 3)
        _px(s, (180, 140, 40), [(8, 9), (8, 10), (8, 11)])
    elif kind == "anvil":                     # наковальня с молотом
        pygame.draw.polygon(s, (150, 160, 170), [(2, 7), (14, 7), (12, 10), (10, 10), (11, 14), (5, 14), (6, 10),
                                                 (3, 10)])
        pygame.draw.line(s, light, (3, 7), (13, 7))
        pygame.draw.line(s, (130, 90, 50), (10, 1), (13, 5), 2)
        pygame.draw.rect(s, (170, 170, 180), (7, 0, 5, 3))
    elif kind == "ash":                       # пепел и угли
        pygame.draw.ellipse(s, (90, 86, 84), (1, 8, 14, 7))
        _px(s, (255, 120, 40), [(5, 10), (9, 11), (11, 9)])
        _px(s, (140, 136, 130), [(7, 6), (6, 4), (8, 2)])
    elif kind == "thread":                    # янтарная звезда
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            r = 7 if i % 2 == 0 else 3
            pts.append((8 + r * math.cos(a), 8 + r * math.sin(a)))
        pygame.draw.polygon(s, (250, 190, 80), pts)
    m = pygame.mask.from_surface(s)
    for x, y in m.outline():
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if 0 <= x + dx < 16 and 0 <= y + dy < 16 and not m.get_at((x + dx, y + dy)):
                s.set_at((x + dx, y + dy), (*dark, 255))
    return s


def _bend(a, b):
    """Контрольная точка тропы: лёгкий изгиб, у каждой пары узлов свой."""
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    k = math.sin(a[0] * 0.013 + b[1] * 0.021) * 0.18
    return mx - (b[1] - a[1]) * k, my + (b[0] - a[0]) * k


def trail_points(a, b, step=11):
    c = _bend(a, b)
    length = math.dist(a, c) + math.dist(c, b)
    n = max(2, int(length / step))
    out = []
    for i in range(n + 1):
        t = i / n
        out.append(((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t * t * b[0],
                    (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t * t * b[1]))
    return out


def draw_trail(surf, a, b, state, clock=0.0, r_a=24, r_b=24):
    """Тропа: future — тусклый пунктир, done — пройдено (сплошные янтарные стежки), open — путь отсюда (бегут огоньки)."""
    pts = [p for p in trail_points(a, b) if math.dist(p, a) > r_a + 4 and math.dist(p, b) > r_b + 4]
    for i, p in enumerate(pts):
        if state == "done":
            pygame.draw.circle(surf, (40, 28, 16), p, 4)
            pygame.draw.circle(surf, T.AMBER, p, 3)
        elif state == "open":
            glow = 0.5 + 0.5 * math.sin(clock * 6 - i * 0.7)
            pygame.draw.circle(surf, (30, 22, 14), p, 4)
            pygame.draw.circle(surf, T.mix((150, 120, 80), (255, 236, 170), glow), p, 3)
        elif i % 2 == 0:
            pygame.draw.circle(surf, (20, 16, 12), p, 3)
            pygame.draw.circle(surf, (96, 84, 66), p, 2)


def _poly(c, r, n, rot=0.0):
    return [(c[0] + r * math.cos(rot + i * 2 * math.pi / n), c[1] + r * math.sin(rot + i * 2 * math.pi / n))
            for i in range(n)]


def draw_node(surf, pos, kind, color, state, clock=0.0, thread=False, molten=False, lava=False):
    """Медальон узла. state: open (можно идти — пульсирует), here (отряд тут), done (пройден), future (впереди).
    molten — огненный бой (залит лавой), lava — его зальёт следующее извержение. Возвращает радиус медальона."""
    x, y = pos
    if lava:                                  # лава подступает: мерцающее оранжевое кольцо
        k = 0.5 + 0.5 * math.sin(clock * 7 + x * 0.1)
        ring = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(ring, (255, 110, 30, int(90 + 110 * k)), (40, 40), 34, 4)
        surf.blit(ring, (x - 40, y - 40))
    r = 30 if kind == "boss" else 25 if kind == "elite" else 22
    dim = state == "future"
    rim = T.mix(color, WOOD_DARK, 0.55) if dim else color
    if state == "open":
        pulse = 0.5 + 0.5 * math.sin(clock * 4)
        halo = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        pygame.draw.circle(halo, (*T.AMBER, int(50 + 60 * pulse)), (r * 2, r * 2), int(r + 8 + 4 * pulse))
        surf.blit(halo, (x - r * 2, y - r * 2))
    # тень и шипы элиты / зубцы босса
    pygame.draw.circle(surf, (0, 0, 0), (x + 2, y + 4), r + 3)
    if kind == "elite":
        pygame.draw.polygon(surf, T.mix(rim, WOOD_DARK, 0.3), _poly(pos, r + 7, 8, math.pi / 8))
    if kind == "boss":
        pygame.draw.polygon(surf, T.mix(rim, WOOD_DARK, 0.25), _poly(pos, r + 9, 12, clock * 0.15))
    pygame.draw.circle(surf, WOOD_DARK, pos, r + 3)
    pygame.draw.circle(surf, rim, pos, r + 1)
    if molten:                                # огненный бой: обод в расплаве
        for i in range(10):
            a = clock * 1.5 + i * math.pi / 5
            pygame.draw.circle(surf, (255, 150 + int(60 * math.sin(clock * 4 + i)), 40),
                               (x + (r + 1) * math.cos(a), y + (r + 1) * math.sin(a)), 3)
    inner = T.mix(WOOD, color, 0.18)
    if dim:
        inner = T.mix(inner, WOOD_DARK, 0.5)
    pygame.draw.circle(surf, inner, pos, r - 3)
    pygame.draw.circle(surf, T.mix(inner, (255, 255, 255), 0.12), (x, y - 2), r - 6, 1)
    size = 48 if kind == "boss" else 32       # целый масштаб иконки 32×32 — пиксели остаются чёткими
    img = icon(kind, size)
    if dim:
        img = img.copy()
        img.fill((120, 110, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
    elif state == "done":
        img = img.copy()
        img.fill((170, 160, 150, 255), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(img, (x - size // 2, y - size // 2))
    if thread:                                # сюжетная нить — янтарная звёздочка на ободе
        star = icon("thread", 16)
        surf.blit(star, (x + r - 10, y - r - 4))
    if state == "done":                       # пройден — галочка
        pygame.draw.circle(surf, WOOD_DARK, (x - r + 6, y + r - 6), 8)
        pygame.draw.lines(surf, (150, 230, 170), False, [(x - r + 2, y + r - 6), (x - r + 5, y + r - 3),
                                                          (x - r + 10, y + r - 10)], 3)
    if state == "here":
        pygame.draw.circle(surf, (255, 246, 220), pos, r + 4, 2)
    return r


def ribbon(surf, label, center, color, bold=False, dim=False):
    """Ленточка подписи под узлом."""
    f = T.font(12, bold)
    w = f.size(label)[0] + 16
    x, y = center
    r = pygame.Rect(int(x - w / 2), int(y), w, 17)
    base = T.mix(PARCHMENT, WOOD_DARK, 0.72 if dim else 0.15)
    tails = [((r.x, r.y + 2), (r.x - 6, r.y + 2), (r.x - 2, r.centery), (r.x - 6, r.bottom - 1), (r.x, r.bottom - 1)),
             ((r.right, r.y + 2), (r.right + 6, r.y + 2), (r.right + 2, r.centery), (r.right + 6, r.bottom - 1),
              (r.right, r.bottom - 1))]
    for t in tails:
        pygame.draw.polygon(surf, T.mix(base, (0, 0, 0), 0.3), t)
    pygame.draw.rect(surf, base, r, border_radius=3)
    pygame.draw.rect(surf, T.mix(color, (0, 0, 0), 0.2), r, 1, border_radius=3)
    T.text(surf, label, r.center, 12, (36, 26, 18) if not dim else (150, 140, 120), bold, center=True)
