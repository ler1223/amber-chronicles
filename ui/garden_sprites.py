"""Спрайты садовых растений: шесть видов, по три стадии роста.

Если в `assets/sprites/garden/` лежит `<вид>_<стадия>.png` (например, `sunleaf_2.png`),
игра использует его; иначе рисует процедурный спрайт. Стадии: 0 — росток,
1 — молодое растение, 2 — взрослое/цветущее.
"""
import math
import os

import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(ROOT, "assets", "sprites", "garden")

PALETTES = {
    "sunleaf": {"leaf": (85, 160, 65), "leaf2": (150, 215, 95), "stem": (92, 128, 55),
                "flower": (245, 205, 65), "accent": (255, 235, 145)},
    "moonroot": {"leaf": (85, 105, 185), "leaf2": (145, 165, 245), "stem": (75, 85, 135),
                 "flower": (190, 210, 255), "accent": (235, 240, 255)},
    "thornbud": {"leaf": (75, 130, 65), "leaf2": (125, 185, 90), "stem": (90, 75, 55),
                 "flower": (205, 95, 175), "accent": (255, 170, 225)},
    "starflower": {"leaf": (70, 150, 120), "leaf2": (125, 220, 185), "stem": (65, 120, 100),
                   "flower": (155, 235, 245), "accent": (245, 255, 255)},
    "emberfern": {"leaf": (190, 85, 55), "leaf2": (245, 145, 75), "stem": (135, 70, 45),
                  "flower": (255, 190, 85), "accent": (255, 225, 150)},
    "frostbell": {"leaf": (95, 155, 170), "leaf2": (165, 220, 235), "stem": (80, 120, 145),
                  "flower": (185, 225, 255), "accent": (245, 255, 255)},
    "bloodpoppy": {"leaf": (60, 115, 55), "leaf2": (110, 175, 80), "stem": (85, 75, 50),
                   "flower": (205, 45, 60), "accent": (255, 130, 105)},
    "stormlotus": {"leaf": (70, 120, 150), "leaf2": (110, 190, 215), "stem": (60, 90, 130),
                   "flower": (95, 145, 245), "accent": (200, 240, 255)},
    "bonemoss": {"leaf": (100, 130, 95), "leaf2": (175, 190, 145), "stem": (105, 105, 85),
                 "flower": (225, 230, 200), "accent": (250, 250, 225)},
    "sugarvine": {"leaf": (100, 155, 70), "leaf2": (190, 205, 100), "stem": (120, 105, 55),
                  "flower": (245, 185, 75), "accent": (255, 235, 150)},
    "tearcap": {"leaf": (75, 135, 135), "leaf2": (125, 195, 190), "stem": (120, 145, 135),
                "flower": (110, 185, 210), "accent": (210, 245, 255)},
    "dreampollen": {"leaf": (90, 80, 145), "leaf2": (150, 130, 215), "stem": (80, 65, 120),
                    "flower": (180, 145, 245), "accent": (245, 220, 255)},
    "ironthorn": {"leaf": (95, 120, 105), "leaf2": (155, 170, 165), "stem": (75, 85, 85),
                  "flower": (185, 195, 205), "accent": (245, 245, 235)},
    "sunpumpkin": {"leaf": (75, 145, 60), "leaf2": (130, 195, 80), "stem": (110, 85, 45),
                   "flower": (240, 140, 50), "accent": (255, 210, 100)},
}

_CACHE = {}


def plant_sprite(pid, stage, height=76):
    """Картинка растения pid на стадии 0..2; height — желаемая высота взрослого растения."""
    stage = max(0, min(2, int(stage)))
    height = max(16, int(height))
    key = (pid, stage, height)
    if key not in _CACHE:
        asset = _load_asset(pid, stage, height)
        if asset is not None:
            _CACHE[key] = asset
        else:
            img = _draw(pid, stage)
            target = max(8, int(height * (0.62 + 0.19 * stage)))
            k = target / img.get_height()
            _CACHE[key] = pygame.transform.smoothscale(img, (max(1, round(img.get_width() * k)), target))
    return _CACHE[key]


def _load_asset(pid, stage, height):
    """PNG из assets/sprites/garden, если он есть. Пурпурный фон генератора вырезается."""
    for name in (f"{pid}_{stage}.png", f"{pid}_{stage}_64.png"):
        path = os.path.join(ASSET_DIR, name)
        if not os.path.exists(path):
            continue
        try:
            img = pygame.image.load(path).convert_alpha()
        except pygame.error:
            continue
        bg = img.get_at((0, 0))[:3]
        if bg[0] > 220 and bg[1] < 45 and bg[2] > 220:      # #FF00FF и близкие
            img = img.copy()
            w, h = img.get_size()
            for y in range(h):
                for x in range(w):
                    r, g, b, a = img.get_at((x, y))
                    if a and abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) < 70:
                        img.set_at((x, y), (0, 0, 0, 0))
        rect = img.get_bounding_rect()
        if rect.w and rect.h:
            img = img.subsurface(rect).copy()
        target = max(8, int(height * (0.62 + 0.19 * stage)))
        k = target / max(1, img.get_height())
        return pygame.transform.smoothscale(img, (max(1, round(img.get_width() * k)), target))
    return None


def _draw(pid, stage):
    pal = PALETTES.get(pid, PALETTES["sunleaf"])
    surf = pygame.Surface((96, 124), pygame.SRCALPHA)
    cx, base_y = 48, 118
    k = (0.62, 0.80, 1.0)[stage]
    top_y = int(base_y - 78 * k)
    stem = pal["stem"]
    pygame.draw.line(surf, (55, 45, 35), (cx + 2, base_y), (cx + 2, base_y - 4), 4)
    pygame.draw.line(surf, stem, (cx, base_y), (cx, top_y), max(2, int(3 * k)))

    # Листья: у взрослого растения их больше и они шире.
    leaf_n = 2 + stage * 2
    for j in range(leaf_n):
        side = -1 if j % 2 else 1
        y = int(base_y - 12 - (j + 1) * (58 * k / (leaf_n + 1)))
        spread = int((14 + stage * 5) * (1.0 - j * 0.06))
        pts = [(cx, y + 4), (cx + side * spread, y - 8), (cx + side * int(spread * 0.7), y + 9)]
        pygame.draw.polygon(surf, pal["leaf"], pts)
        pygame.draw.line(surf, pal["leaf2"], (cx, y + 4), (cx + side * int(spread * 0.65), y - 1), 2)

    if pid == "sunleaf":
        _sunleaf(surf, cx, top_y, stage, pal)
    elif pid == "moonroot":
        _moonroot(surf, cx, base_y, top_y, stage, pal)
    elif pid == "thornbud":
        _thornbud(surf, cx, top_y, stage, pal)
    elif pid == "starflower":
        _starflower(surf, cx, top_y, stage, pal)
    elif pid == "emberfern":
        _emberfern(surf, cx, base_y, top_y, stage, pal)
    elif pid == "bloodpoppy":
        _bloodpoppy(surf, cx, top_y, stage, pal)
    elif pid == "stormlotus":
        _stormlotus(surf, cx, top_y, stage, pal)
    elif pid == "bonemoss":
        _bonemoss(surf, cx, base_y, top_y, stage, pal)
    elif pid == "sugarvine":
        _sugarvine(surf, cx, base_y, top_y, stage, pal)
    elif pid == "tearcap":
        _tearcap(surf, cx, base_y, top_y, stage, pal)
    elif pid == "dreampollen":
        _dreampollen(surf, cx, top_y, stage, pal)
    elif pid == "ironthorn":
        _ironthorn(surf, cx, top_y, stage, pal)
    elif pid == "sunpumpkin":
        _sunpumpkin(surf, cx, base_y, top_y, stage, pal)
    else:
        _frostbell(surf, cx, top_y, stage, pal)
    return surf


def _flower(surf, cx, cy, r, petal, center, petals=6):
    for i in range(petals):
        a = math.tau * i / petals
        x, y = cx + math.cos(a) * r * 0.65, cy + math.sin(a) * r * 0.65
        pygame.draw.circle(surf, petal, (round(x), round(y)), max(2, int(r * 0.48)))
    pygame.draw.circle(surf, center, (cx, cy), max(2, int(r * 0.42)))


def _sunleaf(surf, cx, top, stage, pal):
    if stage == 1:
        pygame.draw.circle(surf, pal["accent"], (cx, top), 5)
    elif stage == 2:
        _flower(surf, cx, top, 15, pal["flower"], pal["accent"], 7)
        pygame.draw.circle(surf, pal["leaf2"], (cx - 13, top + 4), 5)
        pygame.draw.circle(surf, pal["leaf2"], (cx + 13, top + 4), 5)


def _moonroot(surf, cx, base, top, stage, pal):
    pygame.draw.ellipse(surf, pal["leaf"], (cx - 13, base - 12, 26, 12))
    pygame.draw.ellipse(surf, pal["leaf2"], (cx - 8, base - 10, 16, 6))
    if stage == 1:
        pygame.draw.circle(surf, pal["accent"], (cx, top), 5)
    elif stage == 2:
        pygame.draw.circle(surf, pal["flower"], (cx, top), 11)
        pygame.draw.circle(surf, (70, 80, 130), (cx + 3, top - 2), 8)
        pygame.draw.circle(surf, pal["flower"], (cx - 3, top + 3), 6)


def _thornbud(surf, cx, top, stage, pal):
    for j in range(2 + stage):
        y = top + 9 + j * 13
        side = -1 if j % 2 else 1
        pygame.draw.polygon(surf, pal["stem"], [(cx, y), (cx + side * 11, y - 6), (cx + side * 7, y + 5)])
    if stage == 1:
        pygame.draw.circle(surf, pal["flower"], (cx, top), 5)
    elif stage == 2:
        for dx, dy in ((-7, 0), (7, 0), (0, -8)):
            pygame.draw.circle(surf, pal["flower"], (cx + dx, top + dy), 6)
            pygame.draw.circle(surf, pal["accent"], (cx + dx, top + dy - 1), 2)


def _starflower(surf, cx, top, stage, pal):
    if stage == 0:
        return
    r = 8 if stage == 1 else 13
    pts = []
    for i in range(10):
        a = -math.pi / 2 + math.tau * i / 10
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + math.cos(a) * rr, top + math.sin(a) * rr))
    pygame.draw.polygon(surf, pal["flower"], pts)
    pygame.draw.circle(surf, pal["accent"], (cx, top), 3)


def _emberfern(surf, cx, base, top, stage, pal):
    for j in range(3 + stage):
        side = -1 if j % 2 else 1
        y = top + 12 + j * 11
        for q in range(3):
            xx = cx + side * (10 + q * 7)
            yy = y - q * 3
            pygame.draw.line(surf, pal["leaf2"], (cx, y + 5), (xx, yy), 2)
            pygame.draw.circle(surf, pal["flower"], (xx, yy), 3)
    if stage == 2:
        pygame.draw.circle(surf, pal["accent"], (cx, top), 6)


def _frostbell(surf, cx, top, stage, pal):
    if stage == 0:
        return
    n = 2 if stage == 1 else 3
    for j in range(n):
        x = cx + (-9 if j % 2 else 9) + (j - 1) * 2
        y = top + 8 + j * 10
        pygame.draw.line(surf, pal["stem"], (cx, top + 6), (x, y), 2)
        pygame.draw.polygon(surf, pal["flower"], [(x - 6, y), (x + 6, y), (x, y + 10)])
        pygame.draw.circle(surf, pal["accent"], (x, y + 2), 2)


def _bloodpoppy(surf, cx, top, stage, pal):
    if stage == 1:
        pygame.draw.circle(surf, pal["flower"], (cx, top), 6)
    elif stage == 2:
        for dx, dy in ((-10, 0), (10, 0), (0, -10), (0, 10)):
            pygame.draw.circle(surf, pal["flower"], (cx + dx, top + dy), 7)
        pygame.draw.circle(surf, (65, 35, 35), (cx, top), 5)
        pygame.draw.circle(surf, pal["accent"], (cx - 1, top - 1), 2)


def _stormlotus(surf, cx, top, stage, pal):
    if stage == 0:
        return
    r = 8 if stage == 1 else 13
    for i in range(6):
        a = math.tau * i / 6
        x, y = cx + math.cos(a) * r * 0.65, top + math.sin(a) * r * 0.65
        pygame.draw.polygon(surf, pal["flower"], [(cx, top), (x - 4, y), (x + 4, y)])
    pygame.draw.circle(surf, pal["accent"], (cx, top), max(3, r // 3))
    if stage == 2:
        pygame.draw.lines(surf, (190, 240, 255), False,
                          [(cx - 13, top - 15), (cx - 8, top - 9), (cx - 13, top - 3)], 2)


def _bonemoss(surf, cx, base, top, stage, pal):
    for j in range(3 + stage):
        x = cx + (j - 2) * 8
        y = base - 8 - (j % 2) * 5
        pygame.draw.circle(surf, pal["leaf"], (x, y), 6)
        pygame.draw.circle(surf, pal["leaf2"], (x - 1, y - 2), 3)
    if stage == 2:
        for j in range(3):
            x = cx + (j - 1) * 7
            y = top + 12 + j * 5
            pygame.draw.line(surf, pal["stem"], (x, base - 12), (x, y), 2)
            pygame.draw.circle(surf, pal["flower"], (x, y), 3)


def _sugarvine(surf, cx, base, top, stage, pal):
    pts = []
    for j in range(8):
        y = base - 8 - j * 7
        x = cx + int(math.sin(j * 0.9) * (5 + stage * 2))
        pts.append((x, y))
    if len(pts) > 1:
        pygame.draw.lines(surf, pal["stem"], False, pts, 2)
    for j in range(1 + stage):
        x, y = pts[2 + j * 2]
        pygame.draw.circle(surf, pal["flower"], (x + 4, y - 3), 4)
        pygame.draw.circle(surf, pal["accent"], (x + 4, y - 4), 2)


def _tearcap(surf, cx, base, top, stage, pal):
    pygame.draw.line(surf, pal["stem"], (cx, base), (cx, top + 10), 4)
    r = 8 if stage == 1 else 13
    pygame.draw.ellipse(surf, pal["flower"], (cx - r, top - 4, r * 2, r))
    pygame.draw.ellipse(surf, pal["accent"], (cx - r + 3, top - 1, r * 2 - 6, r // 2))
    if stage == 2:
        for dx in (-9, 7):
            pygame.draw.circle(surf, (125, 205, 235), (cx + dx, top + 13), 3)


def _dreampollen(surf, cx, top, stage, pal):
    if stage == 0:
        return
    r = 7 if stage == 1 else 12
    _flower(surf, cx, top, r, pal["flower"], pal["accent"], 6)
    if stage == 2:
        for dx, dy in ((-18, -12), (17, -7), (-12, 14), (20, 11)):
            pygame.draw.circle(surf, pal["accent"], (cx + dx, top + dy), 2)


def _ironthorn(surf, cx, top, stage, pal):
    for j in range(2 + stage):
        side = -1 if j % 2 else 1
        y = top + 8 + j * 9
        pygame.draw.polygon(surf, pal["stem"], [(cx, y), (cx + side * 14, y - 7), (cx + side * 8, y + 4)])
        pygame.draw.circle(surf, pal["accent"], (cx + side * 12, y - 7), 2)
    if stage == 2:
        _flower(surf, cx, top, 10, pal["flower"], pal["accent"], 5)


def _sunpumpkin(surf, cx, base, top, stage, pal):
    if stage == 0:
        return
    r = 9 if stage == 1 else 14
    pygame.draw.ellipse(surf, pal["flower"], (cx - r, base - r - 4, r * 2, r * 2))
    for dx in (-r // 2, r // 2):
        pygame.draw.arc(surf, pal["accent"], (cx + dx - 4, base - r - 3, 8, r * 2 - 2), 0, math.pi, 2)
    pygame.draw.line(surf, pal["stem"], (cx, base - r - 2), (cx, top + 6), 3)
    if stage == 2:
        pygame.draw.circle(surf, pal["accent"], (cx - r - 5, top + 13), 3)
