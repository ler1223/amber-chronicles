"""Сглаженное рисование (без «лесенки»): линии любой толщины, круги, кольца, многоугольники — для частей игры
без пикселей (огранка). Те же сигнатуры, что у pygame.draw.line/circle/polygon/lines."""
import math

import pygame
from pygame import gfxdraw


def _pt(p):
    return (int(round(p[0])), int(round(p[1])))


def line(surf, color, a, b, width=1):
    if width <= 1:
        pygame.draw.aaline(surf, color, a, b)
        return
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy)
    if ln < 1e-6:
        circle(surf, color, a, width / 2)
        return
    nx, ny = -dy / ln * width / 2, dx / ln * width / 2
    pts = [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)]
    ip = [_pt(p) for p in pts]
    gfxdraw.aapolygon(surf, ip, color)
    gfxdraw.filled_polygon(surf, ip, color)
    if width >= 4:                                   # скруглённые концы
        r = int(width / 2)
        for p in (a, b):
            gfxdraw.aacircle(surf, *_pt(p), r, color)
            gfxdraw.filled_circle(surf, *_pt(p), r, color)


def lines(surf, color, closed, pts, width=1):
    pts = list(pts)
    for i in range(len(pts) - (0 if closed else 1)):
        line(surf, color, pts[i], pts[(i + 1) % len(pts)], width)


def circle(surf, color, center, radius, width=0):
    c = _pt(center)
    r = int(round(radius))
    if r < 1:
        return
    if width == 0:
        gfxdraw.aacircle(surf, c[0], c[1], r, color)
        gfxdraw.filled_circle(surf, c[0], c[1], r, color)
        return
    pygame.draw.circle(surf, color, c, r, width)
    gfxdraw.aacircle(surf, c[0], c[1], r, color)
    if width > 1 and r - width + 1 > 0:
        gfxdraw.aacircle(surf, c[0], c[1], r - width + 1, color)


def polygon(surf, color, pts, width=0):
    ip = [_pt(p) for p in pts]
    if len(ip) < 3:
        return
    if width == 0:
        gfxdraw.aapolygon(surf, ip, color)
        gfxdraw.filled_polygon(surf, ip, color)
    elif width == 1:
        gfxdraw.aapolygon(surf, ip, color)
    else:
        lines(surf, color, True, pts, width)
