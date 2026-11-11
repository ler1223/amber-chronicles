"""Металл на экране (numpy, по пикселям): слои пакета из настоящих кусков (строки рамки), складывание — слои
множатся (стопка + её зеркало), скрутка — завитки узора; у каждого металла свой цвет, блеск и цвет травления
(expedition.json smithing.metals: color, sheen, etch). Брусок — цилиндр: тень по объёму, отражение мастерской
(светлый верх, тёмный «горизонт», отсвет снизу), тонкая шлифовка; горячий металл светится цветом каления и теряет
блеск. Поковка — рельеф по толщине: свет и отражение по нормалям, мягкие края, узор растянут.
Границы слоёв сглажены (несколько отсчётов на пиксель). Спрайты кузни — prop() (лист K промптов)."""
import math
import os

import numpy as np
import pygame

from sim import smithing as SM

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE = {}
_NOISE = {}
_PROPS = {}
SUB = (-0.33, 0.0, 0.33)                    # отсчёты на пиксель по высоте — гладкие границы слоёв


def prop(name, w=None, h=None):
    """Спрайт кузни (assets/sprites/frg_*.png) по ширине или высоте, без полей; None — картинки нет."""
    key = (name, w, h)
    if key not in _PROPS:
        path = os.path.join(ROOT, "assets", "sprites", f"{name}.png")
        img = None
        if os.path.exists(path):
            try:
                img = pygame.image.load(path)
                r = img.get_bounding_rect()
                img = img.subsurface(r).copy() if r.w and r.h else img
                if w:
                    img = pygame.transform.scale(img, (w, max(1, round(img.get_height() * w / img.get_width()))))
                elif h:
                    img = pygame.transform.scale(img, (max(1, round(img.get_width() * h / img.get_height())), h))
            except pygame.error:
                img = None
        _PROPS[key] = img
    return _PROPS[key]


def noise(h, w, seed=3):
    """Шлифовка: тонкие штрихи вдоль бруска + мелкое зерно."""
    key = (h, w, seed)
    if key not in _NOISE:
        rng = np.random.default_rng(seed)
        streak = rng.random((h, max(2, w // 24) + 2))
        xs = np.linspace(0, streak.shape[1] - 1.001, w)
        i0 = xs.astype(int)
        f = xs - i0
        rows = streak[:, i0] * (1 - f) + streak[:, i0 + 1] * f
        _NOISE[key] = (rows - 0.5) * 0.22 + (rng.random((h, w)) - 0.5) * 0.08
    return _NOISE[key]


def heat_rgb(t):
    stops = ((500, (70, 64, 66)), (700, (120, 30, 22)), (850, (200, 50, 25)), (1000, (240, 110, 30)),
             (1150, (255, 180, 60)), (1300, (255, 235, 150)), (1450, (255, 250, 235)))
    if t <= stops[0][0]:
        return np.array(stops[0][1], float)
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if t <= b:
            k = (t - a) / (b - a)
            return np.array(ca, float) * (1 - k) + np.array(cb, float) * k
    return np.array(stops[-1][1], float)


def palette(xd, rows):
    """Металлы пакета → индексы и таблицы цвета, блеска и травления (0 — пусто)."""
    M = SM.cfg(xd)["metals"]
    rows = SM.solid_rows(rows)
    ids = sorted({m for r in rows for m in r if m})
    idx = {m: i + 1 for i, m in enumerate(ids)}
    base = np.zeros((len(ids) + 1, 3))
    etch = np.zeros((len(ids) + 1, 3))
    sheen = np.zeros(len(ids) + 1)
    base[0] = etch[0] = (60, 58, 60)
    for m, i in idx.items():
        base[i] = M[m]["color"]
        etch[i] = M[m].get("etch", M[m]["color"])
        sheen[i] = M[m].get("sheen", 0.6)
    grid = np.array([[idx.get(m, 0) for m in r] for r in rows], int)
    return grid, base, etch, sheen


def layer_map(grid, folds, twist, h, w, wave=1.0, seed=0, dy=0.0):
    """Индекс металла в каждом пикселе: слой по высоте (стопка ×2 на каждое складывание), колонка — по длине."""
    R, Cn = grid.shape
    seq = list(range(R))
    for _ in range(folds):
        seq = seq + seq[::-1]                              # сложили пополам — стопка и её зеркало
    seq = np.array(seq)
    L = len(seq)
    y = (np.arange(h)[:, None] + 0.5 + dy) / h
    x = (np.arange(w)[None, :] + 0.5) / w
    d = wave * 0.35 / L * np.sin(x * math.tau * 1.3 + seed)                    # проковка: слои слегка волнистые
    if twist:                                                                  # скрутка: «роза» и завитки
        d = d + twist * (0.9 / L + 0.04) * np.sin(x * math.tau * 4 + y * 9 + seed) * np.cos(x * math.tau * 1.5)
    u = np.clip(y + d, 0, 0.9999)
    layer = (u * L).astype(int)
    row = seq[np.clip(layer, 0, L - 1)]
    col = np.clip((x * Cn).astype(int), 0, Cn - 1)
    col = np.broadcast_to(col, row.shape)
    return grid[row, col]


def metal_color(grid, base, etch, folds, twist, h, w, wave, seed, etched):
    """Цвет металла (до света) со сглаженными границами слоёв."""
    acc = np.zeros((h, w, 3))
    for dy in SUB:
        ids = layer_map(grid, folds, twist, h, w, wave, seed, dy)
        acc += base[ids] * (1 - etched) + etch[ids] * etched
    return acc / len(SUB), layer_map(grid, folds, twist, h, w, wave, seed)


def env_reflect(ny):
    """Отражение мастерской по вертикальной составляющей нормали: светлый свод, тёмный горизонт, отсвет снизу."""
    t = np.clip(ny, -1, 1)
    return 0.55 * np.exp(-((t + 0.7) / 0.25) ** 2) + 0.12 * np.exp(-((t - 0.65) / 0.3) ** 2) + \
        0.18 * np.clip(-t, 0, 1) + 0.04


def finish(col, ids, sheen, lit, refl, spec, temp, grain):
    k = max(0.0, min(1.0, (temp - 520) / 700))             # каление: свечение, блеск уходит
    out = col * lit[..., None] * (1 + grain[..., None])
    gloss = sheen[ids][..., None] * (1 - k)
    out = out * (1 - 0.35 * gloss) + refl[..., None] * 255 * gloss * 0.9 + \
        (spec * sheen[ids] * (1 - k))[..., None] * 255
    if k > 0:
        glow = heat_rgb(temp)
        out = out * (1 - 0.88 * k) + glow * (0.3 + 0.7 * k) * k
    return np.clip(out, 0, 255)


def to_surface(rgb, alpha=None):
    surf = pygame.Surface((rgb.shape[1], rgb.shape[0]), pygame.SRCALPHA)
    arr = pygame.surfarray.pixels3d(surf)
    arr[:] = rgb.astype(np.uint8).swapaxes(0, 1)
    del arr
    al = pygame.surfarray.pixels_alpha(surf)
    al[:] = 255 if alpha is None else (np.clip(alpha, 0, 1).swapaxes(0, 1) * 255).astype(np.uint8)
    del al
    return surf


def remember(key, surf):
    if len(_CACHE) > 300:
        _CACHE.clear()
    _CACHE[key] = surf
    return surf


def bar(xd, rows, folds, twist, w, h, temp, seed=0):
    """Брусок или пакет (вид сбоку): слои, цилиндрический объём, отражение, шлифовка, каление."""
    key = ("bar", tuple(map(tuple, rows)), folds, twist, w, h, int(temp // 15), seed)
    if key in _CACHE:
        return _CACHE[key]
    grid, base, etch, sheen = palette(xd, rows)
    col, ids = metal_color(grid, base, etch, folds, twist, h, w, 1.0, seed, 0.5)
    y = (np.arange(h)[:, None] + 0.5) / h
    ny = np.broadcast_to(-np.cos(y * math.pi), (h, w))                     # нормаль цилиндра: вверх → вниз
    lit = np.broadcast_to(0.5 + 0.55 * np.sin(y * math.pi) ** 0.6 * (1.1 - 0.4 * y), (h, w))
    refl = env_reflect(ny)
    spec = np.broadcast_to(np.exp(-((y - 0.2) / 0.05) ** 2) * 0.6, (h, w))
    rgb = finish(col, ids, sheen, lit, refl, spec, temp, noise(h, w, seed + 1))
    xs = (np.arange(w)[None, :] + 0.5) / w
    endk = np.clip(np.minimum(xs, 1 - xs) * w / 3, 0.55, 1.0)                # торцы чуть темнее
    rgb = rgb * endk[..., None]
    alpha = np.broadcast_to(np.clip(np.minimum(y, 1 - y) * h / 1.2, 0, 1), (h, w))   # мягкая кромка
    return remember(key, to_surface(rgb, alpha))


def forging(xd, rows, folds, twist, th, cell, temp, seed=0):
    """Поковка сверху: рельеф по толщине, свет и отражение по нормалям, мягкие края, узор металла."""
    th = np.asarray(th, float)
    gh, gw = th.shape
    key = ("forge", tuple(map(tuple, rows)), folds, twist, th.round(2).tobytes(), cell, int(temp // 20), seed)
    if key in _CACHE:
        return _CACHE[key]
    h, w = gh * cell, gw * cell
    big = np.kron(th, np.ones((cell, cell)))
    k = np.ones(cell) / cell
    for _ in range(2):                                       # сгладить ступеньки сетки
        for ax in (0, 1):
            big = np.apply_along_axis(lambda v: np.convolve(np.pad(v, cell // 2, mode="edge"), k, "valid")[:len(v)],
                                      ax, big)
    alpha = np.clip((big - 0.08) / 0.1, 0, 1)
    gy, gx = np.gradient(big * 7.0)
    n = np.stack([-gx, -gy, np.ones_like(big)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    L = np.array([-0.45, -0.55, 0.7])
    L /= np.linalg.norm(L)
    diff = np.clip(n @ L, 0, 1)
    H = L + np.array([0, 0, 1.0])
    H /= np.linalg.norm(H)
    spec = np.clip(n @ H, 0, 1) ** 40 * 0.8
    grid, base, etch, sheen = palette(xd, rows)
    col, ids = metal_color(grid, base, etch, folds, twist, h, w, 2.5, seed, 0.42)
    lit = 0.4 + 0.7 * diff
    refl = env_reflect(n[..., 1] * 1.6 - 0.3)
    rgb = finish(col, ids, sheen, lit, refl, spec, temp, noise(h, w, seed + 2) * 0.7)
    rim = np.where(alpha < 0.999, 0.7, 1.0)                  # тёмная кромка по краю поковки
    rgb = rgb * rim[..., None]
    return remember(key, to_surface(rgb, alpha))


def swatch(xd, metal, w, h, temp=20.0, seed=0):
    """Образец металла (кусок на полке)."""
    return bar(xd, [[metal]], 0, 0, w, h, temp, seed)
