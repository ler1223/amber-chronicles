"""Простые UI-помощники прототипа: панели, кнопки, текст."""
import pygame

BG = (24, 20, 18)
PANEL = (45, 36, 30)
PANEL_HI = (62, 48, 37)
EDGE = (128, 92, 54)
GOLD = (232, 184, 92)
TEXT = (236, 226, 208)
DIM = (160, 145, 125)
GREEN = (150, 220, 150)
RED = (230, 110, 100)
BLUE = (150, 200, 240)

_FONTS = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _FONTS:
        _FONTS[key] = pygame.font.SysFont("georgia", size, bold=bold)
    return _FONTS[key]


def text(surf, s, pos, size=16, color=TEXT, bold=False, center=False, shadow=False):
    img = font(size, bold).render(str(s), True, color)
    r = img.get_rect()
    if center:
        r.center = pos
    else:
        r.topleft = pos
    if shadow:
        sh = font(size, bold).render(str(s), True, (0, 0, 0))
        surf.blit(sh, (r.x + 1, r.y + 1))
    surf.blit(img, r)
    return r


def wrap(s, size, width, bold=False):
    words = str(s).split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if font(size, bold).size(test)[0] <= width or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit(s, size, width, bold=False):
    s = str(s)
    while s and font(size, bold).size(s)[0] > width:
        s = s[:-2] + "…"
    return s


def panel(surf, r, fill=PANEL, edge=EDGE, width=2, radius=10):
    pygame.draw.rect(surf, fill, r, border_radius=radius)
    pygame.draw.rect(surf, edge, r, width, border_radius=radius)


def button(surf, r, label, mouse, enabled=True, accent=GOLD, small=False):
    hot = enabled and r.collidepoint(mouse)
    panel(surf, r, PANEL_HI if hot else PANEL, accent if enabled else (80, 72, 64), 2, 8)
    text(surf, fit(label, 15 if small else 18, r.w - 16, True), r.center,
         15 if small else 18, TEXT if enabled else DIM, True, True)
    return hot
