"""Земля «Спуска»: HD-пиксель с рельефом (квиз 2026-11-20, memory: descent-ground).

Пиксель-арт 64 пикселя на клетку (как трава и сор с листов DC3), а не гладкий шум: так земля в одном стиле с
фигурками и не теряет объёма. Как в HD-2D: пиксельная «текстура» на неплоской земле, объём — светом и тенью.

1. Материалы-плитки (дёрн, мох, торф, грязь, осока, галька) — генерируются из бесшовного шума один раз за
   запуск: тон (0..1) и высота каждого пикселя (травинки, подушки мха, волокна торфа, камешки-купола).
2. Карта боя (64/клетку): веса материалов — плавные пятна; на стыке побеждает материал, который «выше»
   (смешивание по высоте: камешки пробиваются сквозь траву, а не расплываются).
3. Рельеф: на доске — едва (кочки, вмятины), вокруг — бугры и кочки, вода ниже земли, у воды — откос.
4. Свет ступенями: нормаль из высоты, свет сверху-слева, 4 ступени с дизерингом (Байер) → сдвиг по палитре
   материала (7 тонов), отбрасываемые тени от бугров и травинок, тёмные впадины.
5. На экран — в родном разрешении, с высотой (каждый пиксель экрана ищет свою точку земли с учётом рельефа:
   бугры встают, у воды видна стенка), пиксели арта — чёткие (ближайший), вдали — уменьшенные копии и дымка.

Строится в фоне (сцена пока рисует прежнюю землю), затем проявляется. height_at(gx, gy) — высота земли для
билбордов (деревья, трава, вороны стоят на буграх, а не тонут в них).
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pygame

try:                                   # scipy может быть собран под другую ABI numpy (частый Mac/Anaconda)
    from scipy import ndimage
except Exception:                      # noqa: BLE001 — игра должна запускаться и без scipy
    ndimage = None

from ui import projection as P

F = np.float32
A = 64                         # пикселей арта на клетку
T = 512                        # плитка материала (8×8 клеток)
_G = np.random.default_rng(7).random((256, 256)).astype(F)
_GF = _G.ravel()
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], F) + 0.5) / 16 - 0.5
LIGHT = np.array((-0.45, -0.6, 0.66), F)
LIGHT /= np.linalg.norm(LIGHT)

# палитры-рампы материалов: 7 тонов от тени к свету
RAMPS = {
    "grass": [(26, 38, 22), (36, 54, 28), (48, 70, 34), (62, 88, 42), (78, 106, 50), (98, 124, 60), (124, 146, 76)],
    "moss": [(22, 36, 25), (30, 50, 31), (40, 66, 37), (52, 82, 43), (66, 98, 49), (84, 116, 57), (108, 136, 68)],
    "peat": [(20, 15, 11), (30, 22, 16), (42, 31, 22), (54, 41, 29), (66, 52, 37), (80, 64, 45), (96, 78, 55)],
    "mud": [(28, 23, 17), (40, 33, 24), (52, 43, 31), (64, 54, 39), (78, 66, 48), (94, 82, 60), (118, 106, 82)],
    "sedge": [(52, 42, 23), (72, 60, 33), (94, 80, 45), (116, 98, 57), (138, 118, 71), (160, 138, 86), (184, 162, 106)],
    "gravel": [(38, 36, 34), (54, 51, 47), (70, 67, 61), (88, 84, 76), (106, 102, 92), (126, 121, 109), (150, 144, 130)],
}
WATER = np.array([(8, 20, 24), (14, 30, 34), (20, 42, 44), (28, 54, 54), (40, 68, 64), (66, 94, 88), (132, 162, 156)], F)
MATS = list(RAMPS)
# темы глав: та же раскладка материалов (слоты), свои цвета и плитки. Кузни: пепел, шлак, базальт, обсидиан, лава
THEMES = {
    "swamp": {"ramps": RAMPS, "tiles": {m: m for m in MATS}, "low": WATER, "glow": False},
    "forge": {"ramps": {
        "grass": [(34, 30, 30), (48, 42, 40), (62, 55, 51), (78, 70, 64), (96, 86, 78), (118, 106, 95), (142, 128, 114)],
        "moss": [(30, 22, 20), (44, 32, 28), (62, 42, 34), (84, 54, 40), (110, 66, 44), (140, 80, 46), (176, 98, 50)],
        "peat": [(18, 16, 18), (26, 24, 27), (36, 33, 37), (47, 43, 48), (60, 55, 61), (76, 70, 77), (96, 89, 97)],
        "mud": [(40, 30, 24), (56, 42, 32), (72, 55, 40), (90, 68, 48), (110, 84, 58), (132, 100, 68), (160, 122, 82)],
        "sedge": [(56, 36, 22), (78, 48, 26), (104, 62, 30), (130, 78, 34), (156, 94, 38), (186, 116, 46), (220, 150, 64)],
        "gravel": [(14, 12, 18), (24, 20, 30), (36, 30, 44), (50, 42, 60), (66, 56, 78), (88, 76, 102), (118, 104, 136)]},
        "tiles": {"grass": "mud", "moss": "peat", "peat": "gravel", "mud": "mud", "sedge": "gravel", "gravel": "gravel"},
        "low": np.array([(60, 10, 4), (110, 24, 6), (168, 44, 8), (214, 74, 12), (244, 118, 24), (255, 170, 60),
                         (255, 228, 150)], F), "glow": True},
}


# --- запасные операции рельефа без scipy ---------------------------------
# На некоторых Mac/Anaconda scipy собран под несовместимую ABI numpy и падает
# ещё на импорте. Для земли достаточно этих трёх операций; ниже — их версии
# на чистом numpy, чтобы игра запускалась в любом окружении.

def _distance(mask):
    """Расстояние от True-точек до ближайшей False (аналог distance_transform_edt)."""
    if ndimage is not None:
        try:
            return ndimage.distance_transform_edt(mask)
        except Exception:              # noqa: BLE001 — сломанная сборка scipy
            pass
    a = np.asarray(mask, dtype=bool)
    if not a.any():
        return np.zeros(a.shape, dtype=F)
    if a.all():                        # до внешней границы массива
        yy, xx = np.indices(a.shape)
        return np.minimum(np.minimum(xx + 1, a.shape[1] - xx),
                          np.minimum(yy + 1, a.shape[0] - yy)).astype(F)
    # two-pass chamfer: 8 соседей, диагональ √2 — визуально неотличимо от EDT
    d = np.where(a, np.inf, 0.0).astype(F)
    h, w = a.shape
    diag = F(2 ** 0.5)
    for y in range(h):
        row, prev = d[y], (d[y - 1] if y else None)
        for x in range(w):
            if not a[y, x]:
                continue
            best = row[x]
            if x:
                best = min(best, row[x - 1] + 1)
            if prev is not None:
                best = min(best, prev[x] + 1)
                if x:
                    best = min(best, prev[x - 1] + diag)
                if x + 1 < w:
                    best = min(best, prev[x + 1] + diag)
            row[x] = best
    for y in range(h - 1, -1, -1):
        row, nxt = d[y], (d[y + 1] if y + 1 < h else None)
        for x in range(w - 1, -1, -1):
            if not a[y, x]:
                continue
            best = row[x]
            if x + 1 < w:
                best = min(best, row[x + 1] + 1)
            if nxt is not None:
                best = min(best, nxt[x] + 1)
                if x + 1 < w:
                    best = min(best, nxt[x + 1] + diag)
                if x:
                    best = min(best, nxt[x - 1] + diag)
            row[x] = best
    return d


def _zoom(a, k):
    """Увеличение целым коэффициентом (аналог ndimage.zoom(order=1) для k=4)."""
    if ndimage is not None:
        try:
            return ndimage.zoom(a.astype(F), k, order=1)
        except Exception:              # noqa: BLE001
            pass
    n = int(round(k))
    if n <= 1:
        return a.astype(F)
    return np.repeat(np.repeat(a.astype(F), n, axis=0), n, axis=1)


def _uniform(a, size=5):
    """Скользящее среднее (аналог ndimage.uniform_filter)."""
    if ndimage is not None:
        try:
            return ndimage.uniform_filter(a, size)
        except Exception:              # noqa: BLE001
            pass
    p = size // 2
    padded = np.pad(a, ((p, p), (p, p)), mode="edge")
    cs = padded.cumsum(0).cumsum(1)
    cs = np.pad(cs, ((1, 0), (1, 0)))
    out = cs[size:, size:] - cs[:-size, size:] - cs[size:, :-size] + cs[:-size, :-size]
    return out / (size * size)


def mirror(i, n):
    """Индекс за краем [0, n) — зеркально (земля на широком экране продолжается, а не тянется полосами)."""
    i = np.mod(i, 2 * n)
    return np.where(i >= n, 2 * n - 1 - i, i)


def theme_of(combat):
    """Тема земли по главе карты поля (карты кузни — chapter forge)."""
    ch = combat.enc.get("chapter") or "swamp"
    return ch if ch in THEMES else "swamp"
MICRO = {"grass": 0.03, "moss": 0.025, "peat": 0.02, "mud": 0.008, "sedge": 0.03, "gravel": 0.04}
_tiles = {}
_POOL = ThreadPoolExecutor(max_workers=max(2, min(16, os.cpu_count() or 4)))   # numpy отпускает GIL — параллельно


def pmap(fn, items):
    return list(_POOL.map(fn, items))


def warm_up():
    """Плитки материалов — заранее, в фоне (при старте игры): к первому бою уже готовы."""
    def job():
        pmap(make_tile, MATS)
    threading.Thread(target=job, daemon=True).start()


_rng0 = np.random.default_rng(11)
_ANG = _rng0.random(256) * 2 * np.pi
_GXT, _GYT = np.cos(_ANG).astype(F), np.sin(_ANG).astype(F)
_PERM = _rng0.permutation(256).astype(np.int32)
_PERM2 = np.concatenate([_PERM, _PERM])


def noise(x, y, seed=0):
    """Градиентный шум (Перлин) 0..1, повёрнутый на свой угол для каждого зерна: пятна округлые, без
    крестов и прямоугольников, которые даёт решётчатый шум с порогом."""
    a = (seed * 2.399963) % (2 * np.pi)                    # золотой угол — у каждого слоя свой поворот
    ca, sa = F(np.cos(a)), F(np.sin(a))
    x, y = x * ca - y * sa + F(seed * 37.13), x * sa + y * ca + F(seed * 17.31)
    xf, yf = np.floor(x), np.floor(y)
    fx, fy = x - xf, y - yf
    xi = xf.astype(np.int32) & 255
    yi = yf.astype(np.int32) & 255

    def grad(ix, iy, dx, dy):
        h = _PERM2[_PERM2[ix] + iy]
        return _GXT[h] * dx + _GYT[h] * dy
    n00 = grad(xi, yi, fx, fy)
    n10 = grad(xi + 1, yi, fx - 1, fy)
    n01 = grad(xi, yi + 1, fx, fy - 1)
    n11 = grad(xi + 1, yi + 1, fx - 1, fy - 1)
    u = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
    v = fy * fy * fy * (fy * (fy * 6 - 15) + 10)
    top = n00 + (n10 - n00) * u
    bot = n01 + (n11 - n01) * u
    return (top + (bot - top) * v) * F(0.9) + F(0.5)


def fbm(x, y, freq, octaves, seed):
    out = np.zeros_like(x)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        f = freq * (2 ** o)
        out += (noise(x * f, y * f, seed + o * 13) - 0.5) * amp
        tot += amp
        amp *= 0.5
    return out / tot + 0.5


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# ---------- бесшовные плитки материалов ----------

def tnoise(sx, sy, rng):
    """Бесшовный плавный шум T×T: решётка sx×sy с переносом через край."""
    g = rng.random((sy, sx)).astype(F)
    y, x = np.mgrid[0:T, 0:T].astype(F)
    x, y = x * sx / T, y * sy / T
    xi, yi = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - xi, y - yi
    u, v = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    x0, y0, x1, y1 = xi % sx, yi % sy, (xi + 1) % sx, (yi + 1) % sy
    a = g[y0, x0] + (g[y0, x1] - g[y0, x0]) * u
    b = g[y1, x0] + (g[y1, x1] - g[y1, x0]) * u
    return a + (b - a) * v


def tfbm(s, octaves, rng, aniso=1):
    out = np.zeros((T, T), F)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        f = s * (2 ** o)
        out += (tnoise(f, max(1, f // aniso), rng) - 0.5) * amp
        tot += amp
        amp *= 0.5
    return out / tot + 0.5


def blades(tone, hgt, rng, n, lmin, lmax, lean, tip=0.45):
    """Травинки: штрихи вверх от корня, к кончику светлее и выше (корень — в тени)."""
    x = rng.integers(0, T, n)
    y = rng.integers(0, T, n)
    ln = rng.integers(lmin, lmax + 1, n)
    dx = rng.uniform(-lean, lean, n) / lmax
    base = rng.uniform(0.2, 0.5, n)
    for k in range(lmax):
        m = k < ln
        q = (k + 1) / ln[m]
        px = (x[m] + np.round(dx[m] * k * k / 2)).astype(int) % T
        py = (y[m] - k) % T
        np.maximum.at(hgt, (py, px), (base[m] + q * 0.6).astype(F))
        np.maximum.at(tone, (py, px), (base[m] + q * tip + 0.15).astype(F))


def pebbles(tone, hgt, rng, n, rmin, rmax):
    """Камешки: купола, у каждого свой тон."""
    x = rng.uniform(0, T, n)
    y = rng.uniform(0, T, n)
    r = rng.uniform(rmin, rmax, n)
    tn = rng.uniform(0.25, 0.85, n).astype(F)
    R = int(np.ceil(rmax))
    for oy in range(-R, R + 1):
        for ox in range(-R, R + 1):
            d = np.hypot(ox, oy * 1.15) / r
            m = d < 1
            if not m.any():
                continue
            px = (np.floor(x[m]) + ox).astype(int) % T
            py = (np.floor(y[m]) + oy).astype(int) % T
            h = (np.sqrt(1 - d[m] ** 2) * 0.8 + 0.3).astype(F)
            old = hgt[py, px]
            up = h > old
            hgt[py[up], px[up]] = h[up]
            tone[py[up], px[up]] = tn[m][up]


def make_tile(name):
    """(тон, высота) плитки материала T×T — один раз за запуск."""
    if name in _tiles:
        return _tiles[name]
    rng = np.random.default_rng(sum(map(ord, name)) + 11)
    if name == "grass":
        tone = tfbm(16, 3, rng) * 0.45
        hgt = tfbm(16, 2, rng) * 0.3
        blades(tone, hgt, rng, T * T // 12, 3, 7, 2.0)
    elif name == "moss":
        cush = tfbm(48, 2, rng)
        hgt = smooth(0.35, 0.7, cush) * 0.7 + tfbm(128, 1, rng) * 0.2
        tone = hgt * 0.7 + (tfbm(96, 1, rng) - 0.5) * 0.3
        spec = rng.random((T, T)) > 0.993                       # коробочки мха — светлые точки
        tone[spec] = 0.95
        hgt[spec] += 0.2
    elif name == "peat":
        tone = tfbm(12, 3, rng) * 0.5 + tfbm(64, 1, rng, aniso=6) * 0.35
        hgt = tfbm(24, 2, rng) * 0.4
        pebbles(tone, hgt, rng, T * T // 260, 1.2, 2.6)          # комья
        tone *= 0.85
    elif name == "mud":
        tone = tfbm(8, 3, rng) * 0.6 + 0.15
        hgt = tfbm(10, 3, rng) * 0.5
        wet = tfbm(32, 2, rng) > 0.62                           # мокрые блики
        tone[wet] = np.minimum(1.0, tone[wet] + 0.35)
        pebbles(tone, hgt, rng, T * T // 900, 1.0, 2.0)
    elif name == "sedge":
        tone = tfbm(12, 3, rng) * 0.4 + 0.1
        hgt = tfbm(12, 2, rng) * 0.25
        blades(tone, hgt, rng, T * T // 7, 4, 10, 5.0, tip=0.55)  # длинные, полёгшие
    else:                                                       # gravel
        tone = tfbm(16, 2, rng) * 0.25
        hgt = np.zeros((T, T), F)
        pebbles(tone, hgt, rng, T * T // 22, 1.6, 4.4)
    _tiles[name] = (np.clip(tone, 0, 1).astype(F).ravel(), np.clip(hgt, 0, 1.2).astype(F).ravel())
    return _tiles[name]


class Ground:
    """Земля боя: рельеф (сразу), картинка — в фоне. surface() — готовая картинка или None."""

    FADE = 0.5
    R = 16                          # рельеф — 16 точек на клетку

    def __init__(self):
        self.key = None
        self.img = None
        self.busy = None
        self.shown = 0.0
        self._lock = threading.Lock()
        self.relief = None              # (ключ, сетка высот, вода, зерно)
        self.flat = None                # (ключ, цвет, высота) — карта 64/клетку

    # ---------- рельеф ----------

    def prepare(self, combat, painter):
        """Рельеф (клетки, высота земли) — быстро и сразу: им пользуются билборды."""
        tm, names = painter._terrain_map(combat)
        key = (tm.tobytes(), tm.shape, combat.enc["id"])
        if self.relief is not None and self.relief[0] == key:
            return self.relief
        seed = sum(ord(c) for c in combat.enc["id"]) % 97
        R = self.R
        ch, cw = tm.shape
        y, x = np.mgrid[0:ch * R, 0:cw * R].astype(F)
        gx, gy = (x + 0.5) / R - P.MARGIN_L, (y + 0.5) / R - P.MARGIN_T
        low = self.low_mask(tm, names, gx, gy, seed)
        gw, gh = combat.grid.w, combat.grid.h
        ddx = np.maximum(np.maximum(-gx, gx - gw), 0)
        ddy = np.maximum(np.maximum(-gy, gy - gh), 0)
        d = np.sqrt(ddx * ddx + ddy * ddy)                        # от доски, в клетках
        amp = 0.03 + np.clip(d * 0.1, 0, 0.32)
        hills = (fbm(gx, gy, 0.35, 3, seed + 30) - 0.5) * 2 * amp
        humm = smooth(0.6, 0.8, noise(gx * 1.7, gy * 1.7, seed + 31)) * np.clip(d / 1.2, 0.2, 1) * 0.12
        h = hills + humm
        if low.any():
            dw = _distance(~low) / R                                   # до воды, в клетках
            h = h * np.clip(dw / 0.8, 0.25, 1) - 0.03 * np.clip(1 - dw / 0.25, 0, 1)
            h = np.where(low, -0.13, h)
        self.relief = (key, h.astype(F), low, seed)
        return self.relief

    @staticmethod
    def low_mask(tm, names, gx, gy, seed):
        low_ids = [names.index(n) for n in ("water", "chasm", "lava") if n in names]
        if not low_ids:
            return np.zeros(gx.shape, bool)
        is_low = np.zeros(len(names), bool)
        is_low[low_ids] = True
        jx = (noise(gx * 1.7, gy * 1.7, seed + 1) - 0.5) * 0.3        # край воды плывёт
        jy = (noise(gx * 1.7, gy * 1.7, seed + 2) - 0.5) * 0.3
        cx = np.clip(np.floor(gx + jx + P.MARGIN_L).astype(np.int32), 0, tm.shape[1] - 1)
        cy = np.clip(np.floor(gy + jy + P.MARGIN_T).astype(np.int32), 0, tm.shape[0] - 1)
        return is_low[tm[cy, cx]]

    def height_at(self, gx, gy):
        """Высота земли (в клетках) в точке — для билбордов (запоминается: декор стоит на месте)."""
        if self.relief is None:
            return 0.0
        memo = self.__dict__.setdefault("_hmemo", {})
        key = (gx, gy, id(self.relief))
        v = memo.get(key)
        if v is None:
            if len(memo) > 20000:
                memo.clear()
            v = memo[key] = self._height(gx, gy)
        return v

    def _height(self, gx, gy):
        h = self.relief[1]
        fx = (gx + P.MARGIN_L) * self.R - 0.5
        fy = (gy + P.MARGIN_T) * self.R - 0.5
        x0, y0 = int(np.floor(fx)), int(np.floor(fy))
        if not (0 <= x0 < h.shape[1] - 1 and 0 <= y0 < h.shape[0] - 1):
            return 0.0
        tx, ty = fx - x0, fy - y0
        a = h[y0, x0] + (h[y0, x0 + 1] - h[y0, x0]) * tx
        b = h[y0 + 1, x0] + (h[y0 + 1, x0 + 1] - h[y0 + 1, x0]) * tx
        return float(a + (b - a) * ty)

    # ---------- картинка ----------

    def surface(self, canvas, combat, painter, decals=(), wait=False):
        """Готовая земля (родные пиксели холста) или None, пока строится. wait — сразу, без потока.
        Строится на всё окно: на широком экране земля уходит и в поля по бокам от кадра 1280×800."""
        r = canvas.native.get_rect()
        rel = self.prepare(combat, painter)
        tm, names = painter._terrain_map(combat)
        off = (canvas.ox, canvas.oy)
        key = (r.size, off, P.view_key(), rel[0], len(decals))
        if key == self.key:
            return self.img
        args = (r.size, canvas.S, combat, tm, names, painter.fog(combat), list(decals), rel, off)
        if wait:
            self.img, self.key, self.shown = self.build(*args), key, self.FADE
            return self.img
        if self.busy != key:
            self.busy = key

            def job():
                img = self.build(*args)
                with self._lock:
                    if self.busy == key:
                        self.img, self.key, self.busy, self.shown = img, key, None, 0.0
            threading.Thread(target=job, daemon=True).start()
        return self.img if self.key is not None and self.key[0] == key[0] else None

    def alpha(self, dt):
        self.shown = min(self.FADE, self.shown + dt)
        return int(255 * self.shown / self.FADE)

    def build(self, size, S, combat, tm, names, fog, decals, rel, off=(0.0, 0.0)):
        col, hgt = self.build_flat(combat, tm, names, decals, rel)
        return self.warp(size, S, combat, col, hgt, fog, off)

    # ---------- карта 64/клетку ----------

    def build_flat(self, combat, tm, names, decals, rel):
        TH = THEMES[theme_of(combat)]
        key = (rel[0], len(decals))
        if self.flat is not None and self.flat[0] == key:
            return self.flat[1], self.flat[2]
        _, relief, low_r, seed = rel
        ch, cw = tm.shape
        H, W = ch * A, cw * A
        k = A // self.R

        def up(a):
            z = _zoom(a, k)
            return z[:H, :W]
        macro = up(relief)
        # веса материалов — плавные пятна (на сетке рельефа, затем растянуть)
        y, x = np.mgrid[0:ch * self.R, 0:cw * self.R].astype(F)
        gx, gy = (x + 0.5) / self.R - P.MARGIN_L, (y + 0.5) / self.R - P.MARGIN_T
        wet = smooth(0.54, 0.72, fbm(gx, gy, 0.32, 3, seed + 4))
        split = smooth(0.5, 0.62, noise(gx * 0.9, gy * 0.9, seed + 6))
        w = {"grass": np.full(gx.shape, 0.5, F),
             "moss": smooth(0.42, 0.7, fbm(gx, gy, 0.45, 2, seed + 3)) * 0.85 * (1 - wet),
             "peat": wet * 0.8 * split,
             "mud": wet * 0.8 * (1 - split),
             "sedge": smooth(0.58, 0.74, fbm(gx, gy, 0.38, 3, seed + 5)) * 0.85 * (1 - wet),
             "gravel": smooth(0.68, 0.8, fbm(gx, gy, 0.55, 2, seed + 7)) * 0.8 * (1 - wet)}
        if low_r.any():                                       # у воды — грязь
            dw = _distance(~low_r) / self.R
            rag = noise(gx * 3.1, gy * 3.1, seed + 40)                # рваная кромка, не по клеткам
            w["mud"] = np.maximum(w["mud"], np.clip(1 - dw / (0.08 + 0.3 * rag), 0, 1) * 0.7)
        Y, X = np.mgrid[0:H, 0:W]
        rng = np.random.default_rng(seed)
        offs = [rng.integers(0, T, 2) for _ in MATS]

        def sample(i):                                         # материалы — параллельно
            tt, th = make_tile(TH["tiles"][MATS[i]])
            ox, oy = offs[i]
            idx = ((Y + oy) % T) * T + (X + ox) % T
            mh = th.take(idx)
            return tt.take(idx), mh * MICRO[MATS[i]], up(w[MATS[i]]) + mh * 0.35   # смешивание по высоте
        res = pmap(sample, range(len(MATS)))
        mat = np.stack([r[2] for r in res]).argmax(0).astype(np.int8)[None]
        tone = np.take_along_axis(np.stack([r[0] for r in res]), mat, 0)[0]
        micro = np.take_along_axis(np.stack([r[1] for r in res]), mat, 0)[0]
        mat = mat[0]
        del Y, X, res
        hgt = macro + micro
        water = up(low_r.astype(F)) > 0.5
        hgt[water] = -0.13
        # свет ступенями: нормаль, тени, впадины
        gxp = np.gradient(hgt, axis=1) * A
        gyp = np.gradient(hgt, axis=0) * A
        nz = 1 / np.sqrt(gxp * gxp + gyp * gyp + 1)
        lam = (-gxp * LIGHT[0] - gyp * LIGHT[1] + LIGHT[2]) * nz / LIGHT[2]
        del gxp, gyp, nz
        bay = np.tile(BAYER, (H // 4 + 1, W // 4 + 1))[:H, :W]
        band = np.digitize(lam + bay * 0.09, [0.74, 0.9, 1.1]).astype(np.int8) - 2
        lxy = np.hypot(LIGHT[0], LIGHT[1])
        dx, dy = LIGHT[0] / lxy, LIGHT[1] / lxy
        rise = LIGHT[2] / lxy / A                                 # клеток высоты на пиксель пути к свету
        def shade(st):
            ox, oy = int(round(dx * st)), int(round(dy * st))
            return np.roll(hgt, (-oy, -ox), axis=(0, 1)) > hgt + st * rise + 0.004
        shadow = np.logical_or.reduce(pmap(shade, range(1, 15)))
        band[shadow] = np.minimum(band[shadow], 0) - 1
        cav = hgt - _uniform(hgt, 5) < -0.006                         # впадины
        band[cav] -= 1
        # доска: шов клеток на пиксель темнее, край доски — темнее
        gw, gh = combat.grid.w, combat.grid.h
        bx0, by0 = P.MARGIN_L * A, P.MARGIN_T * A
        yy, xx = np.ogrid[0:H, 0:W]
        on = (xx >= bx0) & (xx < bx0 + gw * A) & (yy >= by0) & (yy < by0 + gh * A)
        seam = on & (((xx - bx0) % A == 0) | ((yy - by0) % A == 0))
        band[seam] -= 1
        edge = on & ((xx == bx0) | (xx == bx0 + gw * A - 1) | (yy == by0) | (yy == by0 + gh * A - 1))
        band[edge] -= 1
        idx = np.clip(1 + np.round(tone * 4).astype(np.int8) + band, 0, 6)
        ramps = np.array([TH["ramps"][n] for n in MATS], F)
        col = ramps[mat, idx]
        # вода: глубина от берега, рябь, пена у кромки
        if water.any():
            dist = _distance(water)
            wy, wx = np.nonzero(water)
            gxw, gyw = (wx / A - P.MARGIN_L).astype(F), (wy / A - P.MARGIN_T).astype(F)
            d = dist[water]
            rip = noise(gxw * 1.2, gyw * 9, seed + 15) + (noise(gxw * 3, gyw * 20, seed + 16) - 0.5) * 0.6
            wi = 3 - np.clip(d / 18, 0, 2) + (rip > 0.72) * 1 + (rip > 0.86) * 1
            wi += np.clip(0.3 - gyw * 0.08, -0.3, 1.2)                # вдали — отражение неба светлее
            wi = np.clip(np.round(wi + BAYER[wy % 4, wx % 4] * 0.8), 0, 5).astype(int)
            foam = (d < 1.5) & (noise(gxw * 8, gyw * 8, seed + 17) > 0.55)
            wi[foam] = 5
            if TH["glow"]:                                      # лава: светится сильнее в глубине, корка у берега
                wi = np.clip(np.round(2 + np.clip(d / 10, 0, 2.5) + (rip > 0.7) * 1.5 +
                                      BAYER[wy % 4, wx % 4] * 0.8), 0, 6).astype(int)
                wi[d < 2] = 1
            col[water] = TH["low"][wi]
        # вокруг доски — темнее с расстоянием
        dxd = np.maximum(np.maximum(bx0 - xx, xx - bx0 - gw * A), 0) / A
        dyd = np.maximum(np.maximum(by0 - yy, yy - by0 - gh * A), 0) / A
        col *= (1 - np.clip(np.sqrt(dxd * dxd + dyd * dyd) * 0.06, 0, 0.32))[..., None]
        arr = np.clip(col, 0, 255).astype(np.uint8)
        surf = pygame.surfarray.make_surface(arr.swapaxes(0, 1))
        for im, gxd, gyd in decals:                                  # сор — те же 64 на клетку, 1:1
            fx, fy = (gxd + P.MARGIN_L) * A, (gyd + P.MARGIN_T) * A
            surf.blit(im, (round(fx - im.get_width() / 2), round(fy - im.get_height() / 2)))
        arr = pygame.surfarray.array3d(surf).swapaxes(0, 1).copy()
        self.flat = (key, arr, hgt.astype(F))
        return arr, self.flat[2]

    # ---------- на экран ----------

    def warp(self, size, S, combat, col, hgt, fog, off=(0.0, 0.0)):
        """Каждый пиксель экрана — своя точка неплоской земли (луч до пересечения с рельефом, итерациями);
        пиксели арта — ближайшие (чётко), вдали — уменьшенные копии (без ряби). Полосами строк — параллельно."""
        Wd, Hd = size
        levels = [col]
        for _ in range(2):                                          # уменьшенные копии для дали
            c = levels[-1].astype(np.uint16)
            h2, w2 = c.shape[0] // 2 * 2, c.shape[1] // 2 * 2
            c = c[:h2, :w2]
            levels.append(((c[0::2, 0::2] + c[1::2, 0::2] + c[0::2, 1::2] + c[1::2, 1::2]) // 4).astype(np.uint8))
        out = np.empty((Hd, Wd, 3), np.uint8)
        step = 64
        bands = [(y, min(Hd, y + step)) for y in range(0, Hd, step)]
        fogc = np.array(fog, F) * 255

        def band(b):
            y0, y1 = b
            out[y0:y1] = self._warp_rows(y0, y1, Wd, S, hgt, levels, fogc, off)
        pmap(band, bands)
        return pygame.surfarray.make_surface(out.swapaxes(0, 1))

    @staticmethod
    def _warp_rows(y0, y1, Wd, S, hgt, levels, fogc, off=(0.0, 0.0)):
        H, W = hgt.shape
        sy, sx = np.mgrid[y0 - 1:y1 + 1, 0:Wd].astype(F)          # +1 строка с краёв — для производной
        u = ((sx + 0.5 - off[0]) / S - P.CENTER_SCREEN[0]) / P.FOCAL
        v = ((sy + 0.5 - off[1]) / S - P.CENTER_SCREEN[1]) / P.FOCAL
        den = P.SIN + v * P.COS
        ok = den > 1e-4
        den = np.where(ok, den, 1).astype(F)
        hflat = hgt.ravel()
        z = np.zeros_like(u)
        for _ in range(5):                                         # луч ↔ рельеф: высота уточняется
            t = (v * P.DIST + z * (P.COS - v * P.SIN)) / den
            zc = P.DIST - t * P.COS - z * P.SIN
            gy = P.CY + t
            gx = P.CX + u * zc
            fx = mirror(((gx + P.MARGIN_L) * A).astype(np.int32), W)   # за краем карты — отражение
            fy = np.clip(((gy + P.MARGIN_T) * A).astype(np.int32), 0, H - 1)
            z = z * 0.35 + hflat.take(fy * W + fx) * 0.65
        foot = (np.abs(np.gradient(gy, axis=0)) * A)[1:-1]         # пикселей арта на пиксель экрана
        gx, gy, fx, fy, ok = gx[1:-1], gy[1:-1], fx[1:-1], fy[1:-1], ok[1:-1]
        inside = ok & (gy > -P.MARGIN_T) &             (gy < H / A - P.MARGIN_T)
        out = np.empty(gx.shape + (3,), np.uint8)
        lvl = np.where(foot > 3.2, 2, np.where(foot > 1.6, 1, 0))
        for i, L in enumerate(levels):
            m = lvl == i
            if not m.any():
                continue
            kk = 2 ** i
            lh, lw = L.shape[:2]
            px = np.clip(fx[m] // kk, 0, lw - 1)
            py = np.clip(fy[m] // kk, 0, lh - 1)
            out[m] = L.reshape(-1, 3)[py * lw + px]
        fk = np.where(inside, np.clip(-gy / 8.0, 0, 0.85), 1.0).astype(F)[..., None]
        return (out * (1 - fk) + fogc * fk).astype(np.uint8)
