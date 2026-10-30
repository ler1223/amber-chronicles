"""Маленькие 3D-модели в пиксельной сетке эффектов: программный растеризатор с z-буфером (numpy).

Модели строит Blender (tools/blender/ice_wall.py → assets/vfx/ice_wall.json): треугольники в клетках, цвет и затенение
углублений (AO) по граням. Здесь они ставятся на поле и рисуются точной перспективой камеры боя (ui/projection.py):
1 пиксель = 2 экранных, свет сверху-слева-спереди, расширенная палитра льда (12 тонов) с упорядоченным дизерингом.
Результат — картинка для слоя юнитов; кэшируется (стена неподвижна, перерисовка — при росте, таянии, смене камеры).
"""
import json
import os

import numpy as np
import pygame

from ui import projection as P
from ui.pixfx_sim import BAYER, PAL

E = 2
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "assets", "vfx", "ice_wall.json")
LIGHT = np.array([-0.45, 0.55, 1.0]) / np.linalg.norm([-0.45, 0.55, 1.0])     # x влево, y к камере, z вверх


def ramp(pal, n):
    """Палитра из n тонов: 6 цветов стихии, растянутые линейно (тёмный край → белое ядро)."""
    src = np.array(pal, float)
    t = np.linspace(0, len(src) - 1, n)
    i = np.minimum(t.astype(int), len(src) - 2)
    f = (t - i)[:, None]
    return np.round(src[i] * (1 - f) + src[i + 1] * f).astype(np.uint8)


ICE12 = ramp(PAL["ice"], 12)
_DATA = None


def data():
    global _DATA
    if _DATA is None:
        with open(PATH, encoding="utf-8") as f:
            d = json.load(f)
        walls = {}
        for k, tris in d["walls"].items():
            walls[k] = (np.array([t["v"] for t in tris], float), np.array([t["c"] for t in tris], float),
                        np.array([t["ao"] for t in tris], float).mean(1))
        breaks = []
        for b in d["breaks"]:
            chunks = [(np.array([t["v"] for t in ch["tris"]], float), np.array([t["c"] for t in ch["tris"]], float),
                       np.array(ch["frames"], float).reshape(-1, 3, 4)) for ch in b]
            breaks.append(chunks)
        _DATA = {"walls": walls, "breaks": breaks, "height": d["height"], "fps": d["fps"]}
    return _DATA


def runs(cells):
    """Клетки стены → прямые отрезки: [(ось 'x'|'y', [клетки по порядку])]. Сначала ряды, остальное — столбцы."""
    left = set(cells)
    out = []
    for y in sorted({p[1] for p in left}):
        xs = sorted(p[0] for p in left if p[1] == y)
        run = []
        for x in xs + [None]:
            if run and (x is None or x != run[-1][0] + 1):
                if len(run) > 1:
                    out.append(("x", run))
                    left -= set(run)
                run = []
            if x is not None:
                run.append((x, y))
    for x in sorted({p[0] for p in left}):
        ys = sorted(p[1] for p in left if p[0] == x)
        run = []
        for y in ys + [None]:
            if run and (y is None or y != run[-1][1] + 1):
                out.append(("y" if len(run) > 1 else "x", run))
                run = []
            if y is not None:
                run.append((x, y))
    return out


def place(v, axis, cell, side):
    """Локальные координаты модели (x вдоль стены, y поперёк: −y — лицевая сторона, z вверх) → клетки поля.
    axis 'x' — стена вдоль ряда, лицом к камере; 'y' — вглубь поля, лицом к центру доски (side = ±1)."""
    cx, cy = cell
    lx, ly, lz = v[..., 0], v[..., 1], v[..., 2]
    if axis == "x":
        return np.stack([cx + lx, cy + 0.5 - ly, lz], -1)
    return np.stack([cx + 0.5 + ly * side, cy + lx, lz], -1)


def render(tris, cols, ao, sink=0.0, smooth=False):
    """Треугольники в клетках поля → (картинка, экранная точка левого верхнего угла) или None.
    sink — насколько модель утоплена в землю (рост, таяние): всё ниже земли отрезается.
    smooth — без пикселизации (стили ui/fxlab): пиксель 1:1, плавные тона, блик и светлый край граней."""
    if not len(tris):
        return None
    E = 1 if smooth else globals()["E"]
    w = tris.copy()
    w[..., 2] -= sink
    x, y, z = w[..., 0], w[..., 1], w[..., 2]
    t = y - P.CY
    zc = np.maximum(P.DIST - t * P.COS - z * P.SIN, 0.05)
    sx = (P.CENTER_SCREEN[0] + P.FOCAL * (x - P.CX) / zc) / E
    sy = (P.CENTER_SCREEN[1] - P.FOCAL * (-t * P.SIN + z * P.COS) / zc) / E
    keep = (z.max(1) > 0)
    if not keep.any():
        return None
    x0, y0 = int(np.floor(sx[keep].min())) - 1, int(np.floor(sy[keep].min())) - 1
    W, Hh = int(np.ceil(sx[keep].max())) - x0 + 2, int(np.ceil(sy[keep].max())) - y0 + 2
    zbuf = np.full((Hh, W), np.inf)
    val = np.full((Hh, W), -1.0)
    # свет по грани: нормаль развёрнута к камере (зеркальная постановка меняет обход вершин)
    n = np.cross(w[:, 1] - w[:, 0], w[:, 2] - w[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9
    n[n[:, 2] < -0.2] *= -1
    view = np.array([0.0, 0.7, 0.7])
    flip = (n @ view < 0) & (np.abs(n[:, 2]) < 0.5)
    n[flip] *= -1
    lam = np.clip(n @ LIGHT, 0, 1)
    lum = cols @ np.array([0.25, 0.45, 0.30])
    snow = lum > 0.85
    shade = lum * (0.35 + 0.75 * lam) * (0.35 + 0.65 * np.clip(ao, 0, 1))
    shade += 0.1 * np.clip(n[:, 1], 0, 1) * ~snow                         # к камере грань льда светлее (просвет)
    shade = np.where(snow, 0.72 + 0.28 * lam * np.clip(ao, 0.5, 1), shade)  # снег светлый, тени на нём голубые
    for i in np.nonzero(keep)[0]:
        ax, ay = sx[i] - x0, sy[i] - y0
        bx0, by0 = int(max(0, np.floor(ax.min()))), int(max(0, np.floor(ay.min())))
        bx1, by1 = int(min(W - 1, np.ceil(ax.max()))), int(min(Hh - 1, np.ceil(ay.max())))
        if bx1 < bx0 or by1 < by0:
            continue
        gy, gx = np.mgrid[by0:by1 + 1, bx0:bx1 + 1] + 0.5
        d = (ay[1] - ay[2]) * (ax[0] - ax[2]) + (ax[2] - ax[1]) * (ay[0] - ay[2])
        if abs(d) < 1e-9:
            continue
        l0 = ((ay[1] - ay[2]) * (gx - ax[2]) + (ax[2] - ax[1]) * (gy - ay[2])) / d
        l1 = ((ay[2] - ay[0]) * (gx - ax[2]) + (ax[0] - ax[2]) * (gy - ay[2])) / d
        l2 = 1 - l0 - l1
        inside = (l0 >= -1e-3) & (l1 >= -1e-3) & (l2 >= -1e-3)
        if not inside.any():
            continue
        depth = l0 * zc[i, 0] + l1 * zc[i, 1] + l2 * zc[i, 2]
        wz = l0 * z[i, 0] + l1 * z[i, 1] + l2 * z[i, 2]
        sub = zbuf[by0:by1 + 1, bx0:bx1 + 1]
        m = inside & (depth < sub) & (wz >= 0)
        sub[m] = depth[m]
        val[by0:by1 + 1, bx0:bx1 + 1][m] = shade[i]
    alpha = val >= 0
    if not alpha.any():
        return None
    if smooth:
        t = np.clip(val, 0, 1) * (len(ICE12) - 1)
        i = np.minimum(t.astype(int), len(ICE12) - 2)
        fr = (t - i)[..., None]
        rgb = ICE12[i] * (1 - fr) + ICE12[i + 1] * fr
        edge = alpha & ~(np.roll(alpha, 1, 0) & np.roll(alpha, -1, 0) & np.roll(alpha, 1, 1) & np.roll(alpha, -1, 1))
        rgb[edge] = rgb[edge] * 0.6 + 255 * 0.4                      # светлая кромка — лёд просвечивает по краю
        rgba = np.zeros((Hh, W, 4), np.uint8)
        rgba[..., :3] = np.clip(rgb, 0, 255)
        rgba[..., 3] = alpha * 255
        surf = pygame.image.frombuffer(np.ascontiguousarray(rgba).tobytes(), (W, Hh), "RGBA")
        return surf.copy(), (x0, y0)
    th = np.tile(BAYER, (Hh // 4 + 1, W // 4 + 1))[:Hh, :W]
    idx = np.clip((np.clip(val, 0, 1) * len(ICE12) + th - 0.5).astype(int), 0, len(ICE12) - 1)
    rgba = np.zeros((Hh, W, 4), np.uint8)
    rgba[..., :3] = ICE12[idx]
    rgba[..., 3] = alpha * 255
    surf = pygame.image.frombuffer(np.ascontiguousarray(rgba).tobytes(), (W, Hh), "RGBA")
    return pygame.transform.scale(surf, (W * E, Hh * E)), (x0 * E, y0 * E)


def wall(axis, run, variant, side, sink=0.0, smooth=False):
    """Стена-ледник на отрезке клеток run (по порядку вдоль оси). Длиннее 5 — составляется из кусков."""
    d = data()
    parts = []
    i = 0
    while i < len(run):
        n = min(5, len(run) - i)
        tris, cols, ao = d["walls"][f"{n}_{variant % 3}"]
        parts.append((place(tris, axis, run[i], side), cols, ao))
        i += n
    tris = np.concatenate([p[0] for p in parts])
    return render(tris, np.concatenate([p[1] for p in parts]), np.concatenate([p[2] for p in parts]), sink, smooth)


def wall_break(axis, cell, side, variant, frame):
    """Кадр раскола куска стены (глыбы по траекториям Blender)."""
    chunks = data()["breaks"][variant % len(data()["breaks"])]
    all_t, all_c = [], []
    for tris, cols, frames in chunks:
        m = frames[min(frame, len(frames) - 1)]
        loc = tris @ m[:, :3].T + m[:, 3]
        all_t.append(place(loc, axis, cell, side))
        all_c.append(cols)
    tris = np.concatenate(all_t)
    return render(tris, np.concatenate(all_c), np.full(len(tris), 0.9))


def break_frames():
    return len(data()["breaks"][0][0][2]), data()["fps"]
