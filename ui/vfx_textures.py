"""Процедурные текстуры эффектов: формы частиц, флипбуки (покадровые огонь, дым, взрыв) и тайлящийся шум для шейдеров.

Формы — белые (цвет даёт частица), 256×256. Флипбуки — 16 кадров 128×128 (сетка 4×4); огонь и взрыв
запечены в цвете, остальные серые. Всё собирается в один атлас 2048×2048 с предумноженной альфой:
rgb может быть ярче альфы — так пиксель одновременно и светится, и закрывает фон (горячий край взрыва над дымом).
Запекание флипбуков занимает пару секунд, поэтому результат кэшируется в assets/cache/.
"""
import math
import os
import random

import numpy as np
import pygame

TEX = 256
NAMES = ["glow", "core", "ring", "star", "spark", "shard", "smoke", "pixel",
         "circle_arcane", "circle_runes", "circle_holy", "beam", "slash", "flame", "hex", "snow",
         "streak", "crescent", "ray", "drop", "circle_frost", "circle_nature", "circle_blood", "cross",
         "note", "leaf", "zap"]
FLIPBOOKS = ["fb_explosion", "fb_blast", "fb_smoke", "fb_burst", "fb_flame", "fb_flame_gray"]
FRAMES = 16
FRAME = 128
# на CPU (без шейдеров) флипбук рисуется одной похожей формой
FALLBACK = {"fb_explosion": "core", "fb_blast": "glow", "fb_smoke": "smoke", "fb_burst": "star",
            "fb_flame": "flame", "fb_flame_gray": "flame"}

INDEX = {n: i for i, n in enumerate(NAMES)}
FLIP = {}                       # имя флипбука → индекс первого кадра в таблице uv
_k = len(NAMES)
for _n in FLIPBOOKS:
    FLIP[_n] = _k
    INDEX[_n] = _k
    _k += FRAMES
TOTAL = _k                      # строк в таблице uv: формы + все кадры
ATLAS = 2048
CELL = 256
CELLS = ATLAS // CELL           # 8×8 ячеек; формы — строки 0–3, флипбуки (2×2 ячейки) — строки 4–7
BAKE_VERSION = 4
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "cache")


def _xy(n=TEX):
    c = (np.arange(n) + 0.5) / n * 2 - 1
    x, y = np.meshgrid(c, c)        # y: -1 сверху, +1 снизу
    return x, y


def _surface(alpha, rgb=None):
    """alpha — массив [y][x] 0..1; rgb — белый, если не задан."""
    s = pygame.Surface((TEX, TEX), pygame.SRCALPHA)
    a = (np.clip(alpha, 0, 1) * 255).astype(np.uint8)
    col = np.full((TEX, TEX, 3), 255, np.uint8) if rgb is None else (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    pygame.surfarray.pixels3d(s)[:] = col.transpose(1, 0, 2)
    pygame.surfarray.pixels_alpha(s)[:] = a.T
    return s


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# ---------- шум ----------

def vnoise(coords, period, rng):
    """Value-шум в решётке, периодичной по каждой оси. coords — массивы координат в единицах решётки."""
    lat = rng.random(period).astype(np.float32)
    base = [np.floor(c).astype(np.int64) for c in coords]
    frac = [c - b for c, b in zip(coords, base)]
    w = [f * f * (3 - 2 * f) for f in frac]
    out = 0.0
    dims = len(coords)
    for corner in range(1 << dims):
        idx, k = [], 1.0
        for d in range(dims):
            bit = (corner >> d) & 1
            idx.append((base[d] + bit) % period[d])
            k = k * (w[d] if bit else 1 - w[d])
        out = out + lat[tuple(idx)] * k
    return out


def fbm(coords, period, rng, octaves=4, gain=0.5):
    """Сумма октав value-шума, 0..1. Период по каждой оси удваивается вместе с частотой — шум тайлится."""
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        m = 1 << o
        total = total + vnoise([c * m for c in coords], [p * m for p in period], rng) * amp
        norm += amp
        amp *= gain
    return total / norm


def voronoi_edges(n, cells, rng):
    """F2−F1 тайлящегося вороного (0 — на границе ячеек): трещины, соты, «стекло»."""
    pts = np.stack(np.meshgrid(np.arange(cells), np.arange(cells), indexing="ij"), -1).astype(np.float32)
    pts = (pts + rng.random(pts.shape)) / cells           # по точке в каждой ячейке, координаты 0..1
    c = (np.arange(n) + 0.5) / n
    px, py = np.meshgrid(c, c, indexing="ij")
    f1 = np.full((n, n), 9.0, np.float32)
    f2 = np.full((n, n), 9.0, np.float32)
    for p in pts.reshape(-1, 2):
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                d = np.hypot(px - p[0] - ox, py - p[1] - oy)
                f2 = np.where(d < f1, f1, np.minimum(f2, d))
                f1 = np.minimum(f1, d)
    e = (f2 - f1) * cells
    return np.clip(e, 0, 1).T


def make_noise(seed=11, n=256):
    """Тайлящийся шум для шейдеров: R, G — мягкий fbm, B — границы вороного, A — мелкий fbm. uint8 [n, n, 4]."""
    rng = np.random.default_rng(seed)
    c = np.arange(n) / n
    x, y = np.meshgrid(c, c)
    r = fbm([x * 4, y * 4], [4, 4], rng, 5)
    g = fbm([x * 6, y * 6], [6, 6], rng, 4)
    b = voronoi_edges(n, 8, rng)
    a = fbm([x * 16, y * 16], [16, 16], rng, 3)

    def stretch(v):                     # fbm кучкуется около 0.5 — растягиваем на весь диапазон
        lo, hi = np.percentile(v, 1), np.percentile(v, 99)
        return np.clip((v - lo) / (hi - lo), 0, 1)
    out = np.stack([stretch(r), stretch(g), b, stretch(a)], -1)
    return (out * 255).astype(np.uint8)


# ---------- формы (pygame) ----------

def make_textures(seed=3):
    rng = random.Random(seed)
    x, y = _xy()
    r = np.sqrt(x * x + y * y)
    out = {}
    out["glow"] = _surface(np.exp(-r * r * 5) * (r < 1))
    out["core"] = _surface((np.exp(-r * r * 22) + 0.45 * np.exp(-r * r * 5)) * (r < 1))
    out["ring"] = _surface(np.exp(-((r - 0.82) / 0.07) ** 2))
    rays = np.maximum(np.exp(-np.abs(x) * 26) * (1 - np.abs(y)) ** 3, np.exp(-np.abs(y) * 26) * (1 - np.abs(x)) ** 3)
    diag = np.exp(-np.abs(x - y) * 40) * (1 - r) ** 4 + np.exp(-np.abs(x + y) * 40) * (1 - r) ** 4
    out["star"] = _surface(rays + 0.35 * diag * (r < 1) + 0.6 * np.exp(-r * r * 30))
    out["spark"] = _surface(np.exp(-(y / 0.1) ** 2) * np.clip(1 - np.abs(x), 0, 1) ** 1.4)
    shard = np.clip(1 - (np.abs(x) / 0.28 + np.abs(y) / 0.98), 0, 1)
    out["shard"] = _surface(np.clip(shard * 3, 0, 1) * (0.55 + 0.45 * (1 - shard)))
    noise = np.zeros_like(r)
    for k in range(1, 5):                     # грубый «шум» из синусов — пышный край дыма
        noise += np.sin(x * (3 * k + rng.random()) + rng.random() * 6) * np.cos(y * (3 * k + rng.random()) + 2) / k
    out["smoke"] = _surface(np.exp(-r * r * 3.2) * np.clip(0.75 + 0.25 * noise, 0, 1) * (r < 1))
    out["pixel"] = _surface(((np.abs(x) < 0.8) & (np.abs(y) < 0.8)).astype(float))
    for kind in ("arcane", "runes", "holy", "frost", "nature", "blood"):
        out[f"circle_{kind}"] = _circle(rng, kind)
    out["beam"] = _surface(np.exp(-(x / 0.32) ** 2) * _smooth(-1, -0.2, y) * _smooth(1, 0.75, y)
                           + 0.6 * np.exp(-(x / 0.08) ** 2) * _smooth(-1, 0.0, y) * _smooth(1, 0.8, y))
    outer = np.sqrt(x ** 2 + (y - 0.35) ** 2)
    inner = np.sqrt(x ** 2 + (y - 0.62) ** 2)
    band = _smooth(0.95, 0.85, outer) * _smooth(0.86, 0.98, inner) * (y < 0.75)
    out["slash"] = _surface(band * (1 - np.abs(x)) ** 0.6)
    width = 0.12 + 0.42 * np.clip((y + 1) / 2, 0, 1) ** 0.8
    flame = np.exp(-(x / width) ** 2) * _smooth(-1, -0.4, y) * _smooth(1, 0.55, y)
    out["flame"] = _surface(flame)
    ang = np.arctan2(y, x)
    hex_r = np.cos(math.pi / 6) / np.cos((ang % (math.pi / 3)) - math.pi / 6)
    out["hex"] = _surface(np.exp(-((r / hex_r - 0.85) / 0.05) ** 2) + 0.12 * (r / hex_r < 0.85))
    out["snow"] = _snow()
    # длинный мягкий штрих (линии скорости), серп (взмах), луч (свет сверху), капля, крест
    out["streak"] = _surface(np.exp(-(y / 0.06) ** 2) * np.clip(1 - x * x, 0, 1) ** 2 * (0.4 + 0.6 * (x + 1) / 2))
    cr = np.sqrt(x ** 2 + (y + 0.25) ** 2)
    ci = np.sqrt(x ** 2 + (y + 0.05) ** 2)
    out["crescent"] = _surface(_smooth(1.0, 0.86, cr) * _smooth(0.78, 0.92, ci) * (y > -0.2) * (1 - np.abs(x)) ** 0.35)
    out["ray"] = _surface(np.exp(-(x / (0.05 + 0.25 * (y + 1) / 2)) ** 2) * _smooth(-1, -0.5, y) * _smooth(1, 0.6, y))
    dr = np.sqrt((x / 0.55) ** 2 + ((y - 0.25) / 0.7) ** 2)
    tip = (y < -0.1) & (np.abs(x) < (y + 1.0) * 0.6)
    out["drop"] = _surface(np.clip((dr < 1) | tip, 0, 1) * (0.7 + 0.3 * _smooth(0.2, -0.4, x + y)))
    out["cross"] = _surface(np.maximum(np.exp(-(x / 0.12) ** 2) * (np.abs(y) < 0.9),
                                       np.exp(-((y + 0.3) / 0.12) ** 2) * (np.abs(x) < 0.55)))
    out["note"] = _glyph(lambda s, c: (pygame.draw.ellipse(s, c, (60, 150, 80, 60)),
                                       pygame.draw.rect(s, c, (126, 40, 14, 140)),
                                       pygame.draw.polygon(s, c, [(126, 40), (200, 70), (200, 100), (140, 74)])))
    out["leaf"] = _glyph(lambda s, c: (pygame.draw.ellipse(s, c, (40, 90, 176, 76)),
                                       pygame.draw.line(s, (0, 0, 0, 0), (50, 128), (206, 128), 6)))
    out["zap"] = _glyph(lambda s, c: pygame.draw.polygon(s, c, [(150, 10), (70, 140), (124, 140), (96, 246),
                                                                (190, 100), (134, 100), (176, 10)]))
    return out


def _glyph(draw):
    """Силуэт, нарисованный pygame, с мягким ореолом."""
    s = pygame.Surface((TEX, TEX), pygame.SRCALPHA)
    draw(s, (255, 255, 255, 255))
    blur = pygame.transform.smoothscale(pygame.transform.smoothscale(s, (TEX // 8, TEX // 8)), (TEX, TEX))
    blur.fill((255, 255, 255, 120), special_flags=pygame.BLEND_RGBA_MULT)
    blur.blit(s, (0, 0))
    return blur


def _circle(rng, kind):
    """Магический круг: кольца, фигуры и «руны» — рисуются линиями pygame с антиалиасингом."""
    s = pygame.Surface((TEX, TEX), pygame.SRCALPHA)
    c = TEX / 2
    W = (255, 255, 255, 255)
    soft = (255, 255, 255, 140)

    def ring(rr, width=2, col=W):
        pygame.draw.circle(s, col, (c, c), rr, width)

    def poly(n, rr, step=1, rot=0.0, col=W):
        pts = [(c + rr * math.cos(rot + i * math.tau / n), c + rr * math.sin(rot + i * math.tau / n)) for i in range(n)]
        for i in range(n):
            pygame.draw.aaline(s, col, pts[i], pts[(i + step) % n])
        return pts

    def runes(rr, n, size=6):
        for i in range(n):                           # «руны» — случайные штрихи в ячейках по кругу
            a = i * math.tau / n
            gx, gy = c + rr * math.cos(a), c + rr * math.sin(a)
            for _ in range(3):
                p0 = (gx + rng.uniform(-size, size), gy + rng.uniform(-size, size))
                p1 = (gx + rng.uniform(-size, size), gy + rng.uniform(-size, size))
                pygame.draw.line(s, W, p0, p1, 2)

    ring(126, 3)
    ring(116, 1, soft)
    if kind == "arcane":
        ring(96, 2)
        pts = poly(6, 96, 2, -math.pi / 2)            # гексаграмма
        for p in pts:
            pygame.draw.circle(s, W, p, 7, 2)
        ring(40, 2)
        poly(6, 40, 1, 0)
        for i in range(48):
            a = i * math.tau / 48
            r0, r1 = 116, (108 if i % 4 else 100)
            pygame.draw.aaline(s, W, (c + r0 * math.cos(a), c + r0 * math.sin(a)), (c + r1 * math.cos(a), c + r1 * math.sin(a)))
    elif kind == "runes":
        ring(92, 2)
        runes(104, 16)
        poly(4, 88, 1, math.pi / 4)
        poly(4, 88, 1, 0)
        ring(30, 3)
        pygame.draw.circle(s, soft, (c, c), 14)
    elif kind == "holy":
        ring(100, 2)
        for i in range(24):
            a = i * math.tau / 24
            r1 = 96 if i % 2 else 60
            pygame.draw.line(s, W, (c + 30 * math.cos(a), c + 30 * math.sin(a)),
                             (c + r1 * math.cos(a), c + r1 * math.sin(a)), 2 if i % 2 == 0 else 1)
        ring(30, 3)
        pygame.draw.line(s, W, (c, c - 22), (c, c + 22), 4)
        pygame.draw.line(s, W, (c - 22, c), (c + 22, c), 4)
    elif kind == "frost":                             # шестилучевая снежинка в кольцах
        ring(98, 2)
        ring(60, 1)
        for i in range(6):
            a = i * math.pi / 3
            ex, ey = c + 96 * math.cos(a), c + 96 * math.sin(a)
            pygame.draw.line(s, W, (c, c), (ex, ey), 3)
            for t in (0.45, 0.72):
                bx, by = c + 96 * t * math.cos(a), c + 96 * t * math.sin(a)
                for da in (-0.7, 0.7):
                    pygame.draw.line(s, W, (bx, by), (bx + 22 * math.cos(a + da), by + 22 * math.sin(a + da)), 2)
        poly(12, 108, 5, 0, soft)
    elif kind == "nature":                            # лепестки и спираль
        ring(96, 2)
        for i in range(8):
            a = i * math.tau / 8
            px, py = c + 58 * math.cos(a), c + 58 * math.sin(a)
            rect = pygame.Rect(0, 0, 70, 30)
            petal = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.ellipse(petal, W, rect, 2)
            petal = pygame.transform.rotate(petal, -math.degrees(a))
            s.blit(petal, petal.get_rect(center=(px, py)))
        ring(24, 3)
        runes(110, 12, 5)
    else:  # blood: острые зубцы внутрь и треугольники
        ring(100, 3)
        for i in range(12):
            a = i * math.tau / 12
            pts = [(c + 100 * math.cos(a - 0.12), c + 100 * math.sin(a - 0.12)),
                   (c + 70 * math.cos(a), c + 70 * math.sin(a)),
                   (c + 100 * math.cos(a + 0.12), c + 100 * math.sin(a + 0.12))]
            pygame.draw.polygon(s, W, pts)
        poly(3, 64, 1, -math.pi / 2)
        poly(3, 64, 1, math.pi / 2)
        ring(20, 3)
    # мягкое свечение: размытая копия под чёткими линиями
    blur = pygame.transform.smoothscale(pygame.transform.smoothscale(s, (TEX // 8, TEX // 8)), (TEX, TEX))
    blur.fill((255, 255, 255, 150), special_flags=pygame.BLEND_RGBA_MULT)
    blur.blit(s, (0, 0))
    return blur


def _snow():
    s = pygame.Surface((TEX, TEX), pygame.SRCALPHA)
    c = TEX / 2
    for i in range(6):
        a = i * math.pi / 3
        ex, ey = c + 110 * math.cos(a), c + 110 * math.sin(a)
        pygame.draw.line(s, (255, 255, 255), (c, c), (ex, ey), 6)
        for t in (0.45, 0.7):
            bx, by = c + 110 * t * math.cos(a), c + 110 * t * math.sin(a)
            for da in (-0.6, 0.6):
                pygame.draw.line(s, (255, 255, 255), (bx, by),
                                 (bx + 34 * math.cos(a + da), by + 34 * math.sin(a + da)), 4)
    blur = pygame.transform.smoothscale(pygame.transform.smoothscale(s, (TEX // 6, TEX // 6)), (TEX, TEX))
    blur.blit(s, (0, 0))
    return blur


# ---------- флипбуки (numpy) ----------

FIRE_RAMP = np.array([[0.10, 0.08, 0.08], [0.45, 0.07, 0.02], [0.95, 0.32, 0.05], [1.0, 0.68, 0.18],
                      [1.0, 0.92, 0.55], [1.0, 1.0, 0.92]], np.float32)


def _ramp(v, ramp=FIRE_RAMP):
    """Градиент «температуры»: 0 — дым, 1 — белое ядро."""
    v = np.clip(v, 0, 1) * (len(ramp) - 1)
    i = np.minimum(v.astype(int), len(ramp) - 2)
    f = (v - i)[..., None]
    return ramp[i] * (1 - f) + ramp[i + 1] * f


def _frames(seed):
    """Координаты всех кадров сразу: x, y [-1, 1] и t [0, 1] — массивы [16, 128, 128]."""
    c = (np.arange(FRAME) + 0.5) / FRAME * 2 - 1
    t = np.linspace(0, 1, FRAMES)
    tt, y, x = np.meshgrid(t, c, c, indexing="ij")
    return x.astype(np.float32), y.astype(np.float32), tt.astype(np.float32), np.random.default_rng(seed)


def _explosion(gray):
    x, y, t, rng = _frames(21)
    r = np.sqrt(x * x + y * y)
    n = fbm([x * 2.5 + 8, y * 2.5 + 8, t * 3], [16, 16, 8], rng, 4)
    n2 = fbm([x * 5 + 8, y * 5 + 8, t * 4], [32, 32, 8], rng, 3)
    grow = 1 - (1 - np.minimum(1, t * 2.2)) ** 3
    R = 0.4 + 0.5 * grow
    # клубы: крупный шум рвёт край, мелкий даёт «цветную капусту»
    d = r / R + (n - 0.5) * 1.1 + (n2 - 0.5) * 0.35 - np.maximum(-y, 0) * 0.12 * t
    dens = _smooth(1.05, 0.65, d)
    thr = np.clip((t - 0.5) / 0.5, 0, 1) * 0.9                     # под конец тает дырами по шуму
    dens *= _smooth(thr, thr + 0.25, n2 * 0.6 + n * 0.4)
    heat = np.clip(1.4 - d * 0.85 - t * 1.0 + (n2 - 0.5) * 0.9, 0, 1)
    if gray:
        v = dens * (0.25 + 0.75 * heat)
        return np.stack([v, v, v, dens * (0.3 + 0.7 * heat)], -1)
    col = _ramp(heat)
    glow = 0.35 + 1.4 * _smooth(0.3, 0.9, heat)               # горячее светится сильнее, чем закрывает
    a = dens * 0.92
    return np.concatenate([col * (a * glow)[..., None], a[..., None]], -1)


def _smoke():
    x, y, t, rng = _frames(33)
    n = fbm([x * 2 + 4, y * 2 + 4 + t * 0.6, t * 2], [8, 8, 4], rng, 4)
    R = 0.35 + 0.55 * (1 - (1 - t) ** 2)
    r = np.sqrt(x * x + (y + t * 0.1) ** 2)
    dens = _smooth(1.0, 0.45, r / R + (n - 0.5) * 1.0)
    shade = np.clip(0.72 + 0.28 * (-y * 0.6 - x * 0.3) + (n - 0.5) * 0.5, 0.3, 1)
    a = dens * (1 - t) ** 1.1 * 0.95
    return np.stack([shade * a, shade * a, shade * a, a], -1)


def _burst():
    x, y, t, rng = _frames(44)
    r = np.sqrt(x * x + y * y)
    ang = np.arctan2(y, x)
    spikes = fbm([np.cos(ang) * 3 + 3, np.sin(ang) * 3 + 3, t], [12, 12, 2], rng, 3)
    R = 0.15 + 0.85 * (1 - (1 - t) ** 3)
    reach = R * (0.45 + 0.9 * spikes ** 1.5)
    body = _smooth(reach, reach * 0.2, r)
    ring = np.exp(-((r - R) / (0.05 + 0.06 * t)) ** 2) * 0.8
    n = fbm([x * 6 + 6, y * 6 + 6, t * 2], [24, 24, 4], rng, 3)
    v = (body + ring) * (1 - t) ** 0.8 * _smooth(t * 0.8, t * 0.8 + 0.2, n)
    v = np.clip(v, 0, 1)
    return np.stack([v, v, v, v], -1)


def _flame(gray):
    """Язык пламени, зацикленный: шум периодичен по времени."""
    x, y, t, rng = _frames(55)
    up = (1 - y) / 2                                        # 0 — низ, 1 — верх
    n = fbm([x * 2.5 + 4, (y + t * 2.0) * 2.5 + 4, t * 4], [10, 10, 4], rng, 4)
    xs = x + (n - 0.5) * 0.8 * up
    w = 0.36 * np.clip(1 - up, 0, 1) ** 0.6 + 0.02
    bottom = _smooth(0.95, 0.6, y + xs * xs * 0.8)                # круглое основание
    body = _smooth(1, 0.3, np.abs(xs) / w) * bottom * _smooth(0.95, 0.6, up + (n - 0.5) * 0.6)
    heat = np.clip(body * (1.0 - up * 0.8) + (n - 0.5) * 0.25, 0, 1)
    if gray:
        v = body * (0.4 + 0.6 * heat)
        return np.stack([v, v, v, v], -1)
    col = _ramp(0.3 + heat * 0.55)
    a = np.clip(body * 1.1, 0, 1)
    return np.concatenate([col * (a * (0.55 + heat * 0.7))[..., None], a[..., None]], -1)


def _bake_flipbooks():
    return {"fb_explosion": _explosion(False), "fb_blast": _explosion(True), "fb_smoke": _smoke(),
            "fb_burst": _burst(), "fb_flame": _flame(False), "fb_flame_gray": _flame(True)}


def _premul(surf):
    """pygame-поверхность → float [h, w, 4] с предумноженной альфой."""
    rgb = pygame.surfarray.array3d(surf).transpose(1, 0, 2).astype(np.float32) / 255
    a = pygame.surfarray.array_alpha(surf).T.astype(np.float32) / 255
    return np.concatenate([rgb * a[..., None], a[..., None]], -1)


def build_atlas(textures=None, cache=True):
    """Атлас (uint8 [2048, 2048, 4], предумноженная альфа) и uv-прямоугольники (u0, v0, u1, v1) для всех форм
    и кадров флипбуков; v=0 — верхняя строка (так байты уходят в GL)."""
    path = os.path.join(CACHE_DIR, f"vfx_atlas_v{BAKE_VERSION}.npz")
    if cache and os.path.exists(path):
        with np.load(path) as z:
            return z["atlas"], z["uvs"]
    textures = textures or make_textures()
    atlas = np.zeros((ATLAS, ATLAS, 4), np.float32)
    uvs = np.zeros((TOTAL, 4), np.float32)
    pad = 1.5 / ATLAS
    for i, n in enumerate(NAMES):
        gx, gy = i % CELLS, i // CELLS
        atlas[gy * CELL:(gy + 1) * CELL, gx * CELL:(gx + 1) * CELL] = _premul(textures[n])
        uvs[i] = (gx * CELL / ATLAS + pad, gy * CELL / ATLAS + pad, (gx + 1) * CELL / ATLAS - pad,
                  (gy + 1) * CELL / ATLAS - pad)
    books = _bake_flipbooks()
    for b, name in enumerate(FLIPBOOKS):
        bx, by = (b % 4) * 2 * CELL, (4 + (b // 4) * 2) * CELL
        frames = np.clip(books[name], 0, 1)
        for f in range(FRAMES):
            fx, fy = bx + (f % 4) * FRAME, by + (f // 4) * FRAME
            atlas[fy:fy + FRAME, fx:fx + FRAME] = frames[f]
            uvs[FLIP[name] + f] = (fx / ATLAS + pad, fy / ATLAS + pad, (fx + FRAME) / ATLAS - pad,
                                   (fy + FRAME) / ATLAS - pad)
    atlas = (np.clip(atlas, 0, 1) * 255 + 0.5).astype(np.uint8)
    if cache:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            np.savez_compressed(path, atlas=atlas, uvs=uvs)
        except OSError:
            pass
    return atlas, uvs


def cpu_ids():
    """Таблица «uv» для CPU-отрисовки: вместо координат — номер формы (кадры флипбука → похожая форма)."""
    ids = np.zeros((TOTAL, 4), np.float32)
    ids[:len(NAMES), 0] = np.arange(len(NAMES))
    for name, start in FLIP.items():
        ids[start:start + FRAMES, 0] = NAMES.index(FALLBACK[name])
    return ids
