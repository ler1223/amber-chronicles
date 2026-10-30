"""Следы ударов на земле: один удар — один след, нарисованный по физике удара, а не по клеткам.

Клетки — инструмент игрока, для мира их нет: воронка в центре, копоть с рваным краем, лучи выброса (гуще по ходу
удара), обугленные пятна там, куда упали раскалённые осколки, — всё одно пятно. Клетка под пикселем решает только
одно: как выглядит выжженное именно здесь (трава — обугленная земля, камень — серая копоть, лёд — талая вода
с трещинами); на воде, лаве и в пропасти следа нет — там своя реакция (ui/pix_spells.py).
"""
import numpy as np
import pygame

from ui import projection as P
from ui.pixfx_sim import blur, bake

RES = 32                 # пикселей следа на клетку (1 пиксель = 2 пикселя плоской карты)

SCAR_PAL = {             # тёмная половина: след не светится (тлеющие угли — частицы, они гаснут)
    "ground": [(16, 11, 9), (30, 21, 16), (48, 34, 24), (66, 48, 34), (88, 66, 46), (110, 86, 62)],
    "stone": [(14, 13, 13), (28, 26, 25), (44, 41, 39), (62, 58, 55), (84, 79, 74), (108, 102, 96)],
    "ice": [(24, 46, 78), (36, 66, 104), (54, 92, 134), (82, 124, 164), (122, 164, 196), (176, 208, 228)],
}
NO_SCAR = {"water", "lava", "chasm"}


def _angular(rng, n, k, sharp, bias=None, bias_k=0.0):
    """Профиль по углу: k лучей случайной ширины (sharp — насколько узкие); bias — угол, куда лучей больше."""
    ang = np.linspace(0, np.pi * 2, n, endpoint=False)
    f = np.zeros(n)
    for _ in range(k):
        a0 = rng.uniform(0, np.pi * 2)
        if bias is not None and rng.random() < bias_k:
            a0 = bias + rng.normal(0, 0.6)
        w = rng.uniform(0.5, 1.0)
        d = np.angle(np.exp(1j * (ang - a0)))
        f = np.maximum(f, w * np.exp(-(d * sharp) ** 2))
    return f


def scar(cx, cy, R, terrain_at, dirv=(0.0, 0.0), embers=(), seed=0, crater=0.35, style="soot"):
    """След удара с центром (cx, cy) клеток и радиусом R клеток. terrain_at(xs, ys) → массив названий рельефа.
    embers — точки (x, y), куда упали раскалённые осколки. Возвращает (картинка плоской карты, точка вставки)
    или None, если весь след пришёлся на воду/лаву."""
    rng = np.random.default_rng(seed)
    ext = R * 1.45 + 0.3
    for ex, ey in embers:
        ext = max(ext, abs(ex - cx) + 0.3, abs(ey - cy) + 0.3)
    half = int(np.ceil(ext * RES))
    n = 2 * half
    ys, xs = np.mgrid[0:n, 0:n]
    gx = cx + (xs + 0.5 - half) / RES
    gy = cy + (ys + 0.5 - half) / RES
    dx, dy = gx - cx, gy - cy
    dist = np.hypot(dx, dy) / R
    theta = np.arctan2(dy, dx)
    ti = ((theta + np.pi) / (np.pi * 2) * 256).astype(int) % 256
    # рваный край: радиус меняется по углу (крупно и мелко)
    edge = 0.82 + 0.22 * (_angular(rng, 256, 7, 2.5) - 0.5) + 0.08 * (rng.random(256) - 0.5)
    edge = np.convolve(np.r_[edge[-4:], edge, edge[:4]], np.ones(5) / 5, "same")[4:-4]
    bias = float(np.arctan2(dirv[1], dirv[0])) if (dirv[0] or dirv[1]) else None
    rays = _angular(rng, 256, 22, 9.0, bias, 0.45)          # лучи выброса — гуще по ходу удара
    noise = blur(blur(rng.random((n, n))))
    noise = (noise - noise.min()) / (np.ptp(noise) + 1e-6)
    body = np.clip((edge[ti] - dist) / 0.35 + 0.5, 0, 1)                 # копоть с мягким рваным краем
    soot = body * (0.55 + 0.45 * np.clip(1 - dist / edge[ti], 0, 1))
    ray = rays[ti] * np.clip(1.45 - dist, 0, 1) * (dist > 0.4) * 0.8      # лучи тянутся за край
    core = np.clip((crater - dist) / 0.12, 0, 1)                          # воронка: самое тёмное
    v = np.maximum(soot, ray) * (0.75 + 0.35 * noise)
    for ex, ey in embers:                     # брызги от упавших осколков: вытянуты по ходу разлёта, рваные
        ax, ay = ex - cx, ey - cy
        L = np.hypot(ax, ay) or 1.0
        ux, uy = ax / L, ay / L
        along = (gx - ex) * ux + (gy - ey) * uy
        across = -(gx - ex) * uy + (gy - ey) * ux
        d = np.hypot(along / rng.uniform(0.18, 0.28), across / rng.uniform(0.06, 0.1))
        v = np.maximum(v, np.clip((1.0 + 0.9 * (noise - 0.5) - d) / 0.35, 0, 1) * 0.6)
        t = np.clip((dx * ax + dy * ay) / (L * L), 0, 1)
        perp = np.hypot(dx - ax * t, dy - ay * t)
        v = np.maximum(v, np.clip((0.05 - perp) / 0.03, 0, 1) * (0.35 + 0.4 * t) * (dist > 0.3))
    v = np.clip(np.maximum(v, core), 0, 1)
    if v.max() < 0.05:
        return None
    ter = terrain_at(gx.ravel(), gy.ravel()).reshape(n, n)
    if style == "frost":
        rgba = _frost(v, body, ray, ter, theta, dist, edge[ti], noise, rng)
        if not rgba[..., 3].any():
            return None
        surf = pygame.image.frombuffer(np.ascontiguousarray(rgba).tobytes(), (n, n), "RGBA")
        surf = pygame.transform.scale(surf, (n * P.FLAT // RES, n * P.FLAT // RES))
        return surf, P.ground_to_flat(cx, cy)
    bright = np.clip(0.75 - v * 0.75 + core * 0.0, 0, 1)                  # темнее к центру
    rgba = np.zeros((n, n, 4), np.uint8)
    for kind, pal in SCAR_PAL.items():
        m = (ter == kind) if kind != "ground" else ~np.isin(ter, list(SCAR_PAL) + list(NO_SCAR))
        if not m.any():
            continue
        if kind == "ice":                     # лёд не коптится — подтаял: мокрое пятно и трещины
            crack = (np.abs(np.sin(theta * 5 + noise * 6)) < 0.08) & (dist < edge[ti])
            out = bake(np.clip(0.55 - v * 0.35 + crack * 0.3, 0, 1), pal, np.clip(v * 1.1, 0, 1) * 0.8)
        else:
            out = bake(bright, pal, np.clip(v * 1.2, 0, 1) * 0.95)
        rgba[m] = out[m]
    if not rgba[..., 3].any():
        return None
    surf = pygame.image.frombuffer(np.ascontiguousarray(rgba).tobytes(), (n, n), "RGBA")
    surf = pygame.transform.scale(surf, (n * P.FLAT // RES, n * P.FLAT // RES))
    fx, fy = P.ground_to_flat(cx, cy)
    return surf, (fx, fy)


def _frost(v, body, ray, ter, theta, dist, edge, noise, rng):
    """Морозный след: на земле и камне — иней (белёсые кристаллы по лучам и пятну, искрится), на воде —
    ледяная корка с трещинами (вода замёрзла там, где прошёл мороз); на лаве и в пропасти — ничего."""
    n = v.shape[0]
    rgba = np.zeros((n, n, 4), np.uint8)
    sparkle = rng.random((n, n)) < 0.3
    crack = (np.abs(np.sin(theta * 6 + noise * 7)) < 0.07) & (dist < edge)
    land = ~np.isin(ter, ["water", "lava", "chasm"])
    if land.any():
        out = bake(np.clip(0.5 + 0.35 * v * sparkle + crack * 0.15, 0, 1), "ice", np.clip(v * 1.1, 0, 1) * 0.18)
        rgba[land] = out[land]
    wet = ter == "water"
    if wet.any():
        sheet = np.clip(body * 1.3 + ray * 0.6, 0, 1)
        out = bake(np.clip(0.42 + 0.12 * noise + crack * 0.35, 0, 1), "ice", sheet * 0.9)
        rgba[wet] = out[wet]
    return rgba


def area_scar(cells, terrain_at, seed=0):
    """Выжженная земля по форме площади (взорвавшийся пожар): одно пятно на все клетки, край рваный, внутри
    копоть пятнами и пепел. Возвращает (картинка плоской карты, точка вставки центра) или None."""
    from ui.pixfire import _box, _coarse
    if not cells:
        return None
    rng = np.random.default_rng(seed)
    xs = [p[0] for p in cells]
    ys = [p[1] for p in cells]
    x0, y0 = min(xs) - 1, min(ys) - 1
    w, h = (max(xs) - x0 + 2) * RES, (max(ys) - y0 + 2) * RES
    m = np.zeros((h, w))
    for (cx, cy) in cells:
        m[(cy - y0) * RES:(cy - y0 + 1) * RES, (cx - x0) * RES:(cx - x0 + 1) * RES] = 1.0
    cover = _box(_box(m, RES // 2), RES // 2)
    band = np.clip(cover * (1 - cover) * 4, 0, 1)
    edge = cover + (_coarse(h, w, rng) - 0.5) * 1.5 * band
    noise = blur(blur(rng.random((h, w))))
    noise = (noise - noise.min()) / (np.ptp(noise) + 1e-6)
    v = np.clip((edge - 0.42) * 4, 0, 1) * (0.7 + 0.4 * noise)
    if v.max() < 0.05:
        return None
    gy, gx = np.mgrid[0:h, 0:w]
    ter = terrain_at((x0 + (gx.ravel() + 0.5) / RES), (y0 + (gy.ravel() + 0.5) / RES)).reshape(h, w)
    land = ~np.isin(ter, list(NO_SCAR) + ["ice"])
    pal = np.where(ter == "stone", 1, 0)
    rgba = np.zeros((h, w, 4), np.uint8)
    for k, kind in enumerate(("ground", "stone")):
        mk = land & (pal == k)
        if mk.any():
            out = bake(np.clip(0.62 - v * 0.6 + (noise > 0.8) * 0.15, 0, 1), SCAR_PAL[kind], np.clip(v * 1.2, 0, 1))
            rgba[mk] = out[mk]
    if not rgba[..., 3].any():
        return None
    surf = pygame.image.frombuffer(np.ascontiguousarray(rgba).tobytes(), (w, h), "RGBA")
    surf = pygame.transform.scale(surf, (w * P.FLAT // RES, h * P.FLAT // RES))
    return surf, P.ground_to_flat(x0 + w / RES / 2, y0 + h / RES / 2)

