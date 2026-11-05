"""Сеть на пойманном (контроль «Сеть»: крюк стража, сеть ловчего) — пиксель-арт по силуэту фигурки.

Сеть накинута сверху: верёвочная ячейка ромбом, ряды провисают между узлами, на узлах — светлые узелки. Сетка
облегает силуэт (маска фигурки, чуть раздутая), ниже колен разлетается шире и ложится на землю, по краю — тяжёлые
грузила. Набрасывается за 0.25 с сверху вниз; пойманный дёргается — сетка подрагивает вместе с ним.
Кадр кэшируется по (силуэт, размер, фаза), рисуется пикселями ×2, как вся пиксельная графика.
"""
import math

import numpy as np
import pygame

ROPE = (166, 130, 80)
ROPE_DARK = (46, 32, 20)
KNOT = (228, 200, 140)
WEIGHT = (70, 72, 80)
_cache = {}


def net_image(sprite, grow, phase, cell=7):
    """Картинка сети поверх sprite (тот же размер + поля). grow 0..1 — насколько накинута сверху вниз."""
    w, h = sprite.get_size()
    g = max(0, min(4, int(grow * 4)))
    key = (id(sprite), w, h, g, phase % 3, cell)
    if key in _cache:
        return _cache[key]
    if len(_cache) > 400:
        _cache.clear()
    pad = max(6, w // 6)
    W, H = (w + 2 * pad) // 2, (h + pad) // 2              # сетка арта: пиксель = 2 экранных
    a = pygame.surfarray.array_alpha(pygame.transform.scale(sprite, (w // 2, h // 2))).T > 60
    m = np.zeros((H, W), bool)
    m[: a.shape[0], pad // 2: pad // 2 + a.shape[1]] = a
    # раздуть силуэт: сеть лежит поверх тела, а не впритык
    for _ in range(2):
        m = m | np.roll(m, 1, 0) | np.roll(m, -1, 0) | np.roll(m, 1, 1) | np.roll(m, -1, 1)
    rows = np.nonzero(m.any(1))[0]
    if not len(rows):
        return None
    top, bot = rows[0], H - 1
    ys, xs = np.mgrid[0:H, 0:W]
    # юбка: ниже 65% роста сеть расходится шире силуэта и ложится на землю
    skirt_y = top + (bot - top) * 0.65
    cols = np.nonzero(m.any(0))[0]
    cx = (cols[0] + cols[-1]) / 2
    half = (cols[-1] - cols[0]) / 2 + 1
    spread = np.clip((ys - skirt_y) / max(1, bot - skirt_y), 0, 1)
    skirt = (np.abs(xs - cx) < half * (1 + 0.45 * spread)) & (ys >= skirt_y)
    region = (m | skirt) & (ys <= top + (bot - top + 1) * (g / 4 if g < 4 else 1.0))
    # ромбическая ячейка с провисом: диагонали, смещённые вниз по синусу между узлами
    c = cell
    wob = 0.6 * math.sin(phase * 2.1)
    sag = 1.2 * np.sin((xs % c) / c * math.pi)
    u = (xs + ys + sag + wob) % c
    v = (xs - ys - sag + wob) % c
    line = (u < 1.0) | (v < 1.0)
    knot = (u < 1.0) & (v < 1.0)
    rgba = np.zeros((H, W, 4), np.uint8)
    shade = np.where(xs < cx, 1.0, 0.82)[..., None]              # свет слева
    body = region & line
    rgba[body, :3] = (np.array(ROPE) * shade)[body].astype(np.uint8)
    rgba[body, 3] = 255
    # тёмный контур по обе стороны верёвки — сеть читается на любом цвете фигурки
    out_ = region & ~line & (np.roll(line, 1, 0) | np.roll(line, -1, 0) | np.roll(line, 1, 1) | np.roll(line, -1, 1))
    rgba[out_, :3] = ROPE_DARK
    rgba[out_, 3] = 200
    rgba[region & knot, :3] = KNOT
    rgba[region & knot, 3] = 255
    edge = region & ~np.roll(region, -1, 0) & (ys > skirt_y)     # нижний край юбки — грузила
    ex = np.nonzero(edge)
    for y_, x_ in zip(*ex):
        if x_ % (c + 1) == 0:
            rgba[max(0, y_ - 1):y_ + 1, max(0, x_ - 1):x_ + 1, :3] = WEIGHT
            rgba[max(0, y_ - 1):y_ + 1, max(0, x_ - 1):x_ + 1, 3] = 255
    surf = pygame.image.frombuffer(np.ascontiguousarray(rgba).tobytes(), (W, H), "RGBA")
    surf = pygame.transform.scale(surf, (W * 2, H * 2))
    out = (surf, pad)
    _cache[key] = out
    return out
