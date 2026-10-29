"""Пиксельные модельки объектов поля (data/objects.json → "art"): бочки, валун, источники врагов, охраняемые
объекты. Холст 32×32, низ — по центру клетки; SpriteBank масштабирует как юнитов. Свой PNG
assets/sprites/<id объекта>.png заменяет заглушку."""
import pygame

from ui.looks import OUTLINE, R, shade


def _barrel(s, c, band=(70, 70, 80), mark=None):
    body = pygame.Rect(9, 10, 14, 20)
    pygame.draw.ellipse(s, shade(c, -0.25), (9, 26, 14, 6))
    pygame.draw.rect(s, c, body, border_radius=4)
    for y in (13, 25):
        R(s, band, 9, y, 14, 2)
    pygame.draw.line(s, shade(c, 0.25), (12, 12), (12, 28))
    pygame.draw.ellipse(s, shade(c, 0.2), (9, 8, 14, 5))
    pygame.draw.ellipse(s, shade(c, -0.35), (11, 9, 10, 3))
    if mark:
        mark(s)


def _powder_mark(s):
    pygame.draw.circle(s, (40, 36, 40), (16, 19), 4)
    pygame.draw.line(s, (255, 220, 120), (16, 9), (19, 4))
    s.set_at((19, 3), (255, 160, 60))


def _oil_mark(s):
    pygame.draw.polygon(s, (40, 30, 20), [(16, 15), (13, 21), (19, 21)])
    pygame.draw.circle(s, (40, 30, 20), (16, 21), 3)


def barrel(s, c):
    _barrel(s, c, mark=_powder_mark)


def barrel_oil(s, c):
    _barrel(s, c, band=(60, 50, 34), mark=_oil_mark)


def boulder(s, c):
    pygame.draw.polygon(s, shade(c, -0.2), [(4, 30), (3, 21), (8, 12), (17, 8), (26, 11), (30, 20), (29, 30)])
    pygame.draw.polygon(s, c, [(6, 28), (6, 21), (10, 14), (17, 11), (24, 13), (27, 20), (26, 27)])
    pygame.draw.polygon(s, shade(c, 0.25), [(10, 15), (17, 12), (21, 14), (14, 19)])
    pygame.draw.line(s, shade(c, -0.35), (16, 20), (21, 26))
    pygame.draw.line(s, shade(c, -0.35), (16, 20), (12, 24))


def mound(s, c):
    pygame.draw.ellipse(s, shade(c, -0.3), (3, 14, 26, 18))
    pygame.draw.ellipse(s, c, (5, 13, 22, 15))
    for x, y in ((10, 18), (17, 16), (21, 21), (13, 23)):
        pygame.draw.circle(s, (30, 24, 20), (x, y), 2)
    pygame.draw.circle(s, shade(c, 0.3), (12, 16), 2)


def furnace(s, c):
    R(s, (90, 80, 76), 6, 10, 20, 20)
    R(s, (120, 110, 104), 5, 8, 22, 4)
    R(s, (70, 60, 56), 13, 2, 6, 7)
    pygame.draw.rect(s, (30, 20, 18), (10, 17, 12, 10), border_radius=3)
    pygame.draw.rect(s, c, (11, 19, 10, 8), border_radius=3)
    pygame.draw.rect(s, (255, 230, 120), (13, 22, 6, 5), border_radius=2)


def coffin(s, c):
    pygame.draw.polygon(s, shade(c, -0.3), [(10, 31), (8, 12), (12, 4), (20, 4), (24, 12), (22, 31)])
    pygame.draw.polygon(s, c, [(11, 29), (10, 13), (13, 6), (19, 6), (22, 13), (21, 29)])
    R(s, (230, 200, 90), 15, 10, 2, 12)
    R(s, (230, 200, 90), 12, 14, 8, 2)


def idol(s, c):
    pygame.draw.polygon(s, shade(c, -0.25), [(16, 2), (24, 14), (21, 31), (11, 31), (8, 14)])
    pygame.draw.polygon(s, c, [(16, 5), (22, 14), (19, 29), (13, 29), (10, 14)])
    pygame.draw.line(s, (255, 255, 255), (14, 9), (12, 16))
    pygame.draw.circle(s, (40, 90, 160), (16, 16), 2)


def tent(s, c):
    pygame.draw.polygon(s, shade(c, -0.25), [(2, 30), (16, 4), (30, 30)])
    pygame.draw.polygon(s, c, [(5, 29), (16, 7), (27, 29)])
    pygame.draw.polygon(s, (40, 26, 20), [(13, 29), (16, 18), (19, 29)])
    pygame.draw.line(s, (120, 90, 60), (16, 4), (16, 0))
    R(s, (200, 60, 50), 16, 0, 4, 3)


def ring(s, c):
    for i in range(8):
        x = 16 + int(11 * pygame.math.Vector2(1, 0).rotate(i * 45).x)
        y = 24 + int(5 * pygame.math.Vector2(1, 0).rotate(i * 45).y)
        pygame.draw.circle(s, (220, 210, 200), (x, y), 3)
        pygame.draw.circle(s, (200, 60, 60), (x, y - 1), 2)
    pygame.draw.circle(s, c, (16, 20), 4)
    pygame.draw.circle(s, shade(c, 0.5), (16, 20), 2)


def shell(s, c):
    pygame.draw.ellipse(s, shade(c, -0.3), (5, 10, 22, 21))
    pygame.draw.ellipse(s, c, (6, 11, 20, 18))
    for i in range(4):
        pygame.draw.arc(s, shade(c, -0.4), (8 + i * 2, 13 + i * 2, 16 - i * 4, 14 - i * 4), 0, 3.5, 1)
    pygame.draw.circle(s, (240, 230, 255), (16, 21), 2)


def crystal(s, c):
    pygame.draw.polygon(s, shade(c, -0.3), [(16, 1), (23, 12), (20, 30), (12, 30), (9, 12)])
    pygame.draw.polygon(s, c, [(16, 4), (21, 12), (18, 28), (14, 28), (11, 12)])
    pygame.draw.line(s, (255, 255, 255), (15, 7), (13, 17))
    R(s, (90, 80, 100), 9, 28, 14, 3)


def cart(s, c):
    R(s, shade(c, -0.25), 4, 12, 24, 10)
    R(s, c, 4, 10, 24, 9)
    pygame.draw.line(s, shade(c, 0.3), (5, 11), (26, 11))
    R(s, (230, 220, 190), 7, 4, 16, 7)
    for x in (9, 23):
        pygame.draw.circle(s, (60, 44, 30), (x, 25), 5)
        pygame.draw.circle(s, (140, 110, 70), (x, 25), 3)
    pygame.draw.line(s, (110, 80, 50), (28, 16), (31, 20), 2)


def captive(s, c):
    R(s, (90, 70, 50), 8, 28, 16, 3)
    pygame.draw.line(s, (110, 80, 50), (16, 4), (16, 30), 2)
    R(s, (60, 70, 120), 12, 15, 8, 10)
    pygame.draw.circle(s, c, (16, 11), 4)
    pygame.draw.line(s, (190, 170, 130), (11, 18), (21, 18), 2)


def torch(s, c):
    pygame.draw.line(s, (110, 80, 50), (16, 31), (16, 12), 3)
    R(s, (80, 70, 60), 13, 11, 7, 3)
    pygame.draw.polygon(s, (255, 120, 40), [(12, 11), (16, 1), (20, 11)])
    pygame.draw.polygon(s, c, [(14, 11), (16, 4), (18, 11)])


def rod(s, c):
    R(s, (90, 90, 100), 10, 27, 12, 4)
    pygame.draw.line(s, c, (16, 28), (16, 3), 2)
    pygame.draw.polygon(s, (240, 230, 140), [(16, 0), (19, 6), (13, 6)])
    pygame.draw.line(s, (140, 140, 160), (16, 12), (11, 16))
    pygame.draw.line(s, (140, 140, 160), (16, 12), (21, 16))


def sapling(s, c):
    pygame.draw.line(s, (90, 64, 44), (16, 31), (16, 14), 3)
    for x, y, r in ((11, 12, 6), (21, 12, 6), (16, 6, 7)):
        pygame.draw.circle(s, shade(c, -0.25), (x, y), r)
        pygame.draw.circle(s, c, (x - 1, y - 1), r - 2)
    for x, y in ((9, 9), (22, 7), (15, 14)):
        s.set_at((x, y), (255, 255, 180))


def bell(s, c):
    R(s, (110, 80, 50), 6, 3, 20, 3)
    pygame.draw.line(s, (110, 80, 50), (7, 3), (7, 31), 2)
    pygame.draw.line(s, (110, 80, 50), (25, 3), (25, 31), 2)
    pygame.draw.polygon(s, shade(c, -0.25), [(10, 24), (12, 9), (20, 9), (22, 24)])
    pygame.draw.polygon(s, c, [(11, 23), (13, 10), (19, 10), (21, 23)])
    pygame.draw.circle(s, (80, 60, 30), (16, 25), 2)


def pillar(s, c):
    R(s, shade(c, -0.25), 10, 6, 12, 25)
    R(s, c, 11, 6, 9, 24)
    R(s, shade(c, 0.2), 8, 3, 16, 4)
    R(s, shade(c, 0.2), 8, 28, 16, 3)
    pygame.draw.line(s, shade(c, -0.4), (14, 12), (17, 20))


def ice_block(s, c):
    pygame.draw.polygon(s, shade(c, -0.2), [(4, 31), (3, 12), (9, 5), (24, 4), (29, 10), (28, 31)])
    pygame.draw.polygon(s, c, [(6, 29), (5, 13), (10, 7), (23, 6), (27, 11), (26, 29)])
    pygame.draw.polygon(s, shade(c, 0.45), [(10, 7), (23, 6), (20, 11), (12, 12)])
    pygame.draw.line(s, (255, 255, 255), (9, 14), (9, 26), 2)
    pygame.draw.line(s, shade(c, -0.3), (17, 13), (21, 26))


def bones(s, c):
    pygame.draw.polygon(s, shade(c, -0.35), [(4, 31), (6, 10), (26, 10), (28, 31)])
    for x in range(7, 26, 5):
        pygame.draw.line(s, c, (x, 30), (x + 1, 10), 3)
    for y in (14, 22):
        pygame.draw.line(s, shade(c, 0.15), (5, y), (27, y), 2)
    pygame.draw.circle(s, c, (16, 8), 5)
    s.set_at((14, 8), (30, 24, 30))
    s.set_at((18, 8), (30, 24, 30))


ARTS = {f.__name__: f for f in (barrel, barrel_oil, boulder, mound, furnace, coffin, idol, tent, ring, shell,
                                 crystal, cart, captive, torch, rod, sapling, bell, pillar, ice_block, bones)}


def draw_object(art, color):
    """32×32 с контуром в 1 пиксель."""
    s = pygame.Surface((32, 32), pygame.SRCALPHA)
    ARTS.get(art, boulder)(s, tuple(color))
    mask = pygame.mask.from_surface(s)
    out = pygame.Surface((32, 32), pygame.SRCALPHA)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        out.blit(mask.to_surface(setcolor=(*OUTLINE, 255), unsetcolor=(0, 0, 0, 0)), (dx, dy))
    out.blit(s, (0, 0))
    return out
