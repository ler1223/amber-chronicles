"""Горящая поверхность поля: все горящие клетки — одно поле жара (как классический огонь Doom PSX: значения жара →
цвета палитры), соседние клетки сливаются в единую горящую плоскость, край рваный и живой.

Слой земли (плоская карта): тлеющие угли — тёмно-красное с бегущими оранжевыми прожилками и яркими пятнами.
Над ним — мелкие языки пламени (частицы ui/pixsim.py) по всей площади, гуще в середине; редкие искры улетают.
"""
import numpy as np
import pygame

from ui import projection as P
from ui.pixfx_sim import bake, blur

RES = 32                 # пикселей эффекта на клетку (1 пиксель = 2 пикселя плоской карты)
FPS = 12


def _noise(h, w, rng, passes):
    f = rng.random((h, w))
    for _ in range(passes):
        f = blur(f)
    f -= f.min()
    return f / (f.max() + 1e-6)


def _coarse(h, w, rng, step=10):
    """Крупный плавный шум (пятна размером ~step пикселей) — для формы края: пятно, а не скруглённый квадрат."""
    f = rng.random((h // step + 3, w // step + 3))
    f = np.repeat(np.repeat(f, step, 0), step, 1)[:h, :w]
    for _ in range(4):
        f = _box(f, step // 2)
    f -= f.min()
    return f / (f.max() + 1e-6)


def _box(m, r):
    """Сглаживание маски квадратным окном радиуса r (через суммы) — углы скругляются, соседи сливаются."""
    k = 2 * r + 1
    pad = np.pad(m, r, mode="edge")
    c = pad.cumsum(0).cumsum(1)
    c = np.pad(c, ((1, 0), (1, 0)))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


class FireField:
    def __init__(self, seed=3):
        self.rng = np.random.default_rng(seed)
        self.acc = 0.0
        self.t = 0
        self.key = None
        self.img = None          # (поверхность плоской карты, точка вставки)
        self.inside = None       # маска горящего (для языков пламени)
        self.box = None          # (x0, y0) клетки угла поля
        self.noise = None

    def clear(self):
        self.key = self.img = self.inside = None

    def _board_noise(self, cols, rows):
        if self.noise is None or self.noise[0].shape != (rows * RES, cols * RES):
            h, w = rows * RES, cols * RES
            self.noise = (_noise(h, w, self.rng, 6), _noise(h, w, self.rng, 3), _noise(h, w, self.rng, 2),
                          _coarse(h, w, self.rng))
        return self.noise

    def update(self, dt, burning, cols, rows):
        """burning — клетки, которые сейчас горят. Кадр поля обновляется 12 раз в секунду."""
        if not burning:
            self.clear()
            return
        self.acc += dt
        key = frozenset(burning)
        if key == self.key and self.acc < 1 / FPS:
            return
        self.acc = 0.0
        self.t += 1
        xs = [p[0] for p in burning]
        ys = [p[1] for p in burning]
        x0, y0 = max(0, min(xs) - 1), max(0, min(ys) - 1)
        x1, y1 = min(cols, max(xs) + 2), min(rows, max(ys) + 2)
        h, w = (y1 - y0) * RES, (x1 - x0) * RES
        if key != self.key or self.box != (x0, y0, x1, y1):
            m = np.zeros((h, w))
            for (cx, cy) in burning:
                m[(cy - y0) * RES:(cy - y0 + 1) * RES, (cx - x0) * RES:(cx - x0 + 1) * RES] = 1.0
            self.cover = _box(_box(m, RES // 2), RES // 2)       # единая площадь, край — пятном, а не клеткой
            self.key, self.box = key, (x0, y0, x1, y1)
            self.facets = None
        n0, n1, n2, n3 = (a[y0 * RES:y1 * RES, x0 * RES:x1 * RES] for a in self._board_noise(cols, rows))
        # форма — крупными пятнами, сетки клеток не видно; шум только в полосе края: снаружи пусто, внутри полно
        band = np.clip(self.cover * (1 - self.cover) * 4, 0, 1)
        self.cover_n = self.cover + (n3 - 0.5) * 1.5 * band
        self.n3 = n3
        rgba, inside, depth = self._paint(n0, n1, n2, self.t)
        surf = pygame.image.frombuffer(np.ascontiguousarray(rgba).tobytes(), (w, h), "RGBA")
        surf = pygame.transform.scale(surf, (w * P.FLAT // RES, h * P.FLAT // RES))
        self.img = (surf, P.ground_to_flat(x0, y0))
        self.inside = inside & (depth > 0.15)

    def _paint(self, n0, n1, n2, t):
        """Кадр поверхности: (RGBA, маска «внутри», глубина 0..1 к середине)."""
        # край огня живой: медленный шум «съедает» и отпускает границу
        edge = self.cover_n + ((np.roll(n0, t // 3, 0) - 0.5) * 0.6 + (n1 - 0.5) * 0.2) * (self.cover > 0.02)
        inside = edge > 0.5
        depth = np.clip((edge - 0.5) * 2.5, 0, 1)                 # к середине горит сильнее
        # прожилки и пятна: два шума бегут навстречу — угли перемигиваются
        flick = np.roll(n1, t, 1) * 0.55 + np.roll(n2, -t, 0) * 0.45
        hot = np.clip(flick * 2.6 - 1.45, 0, 1)
        # земля под огнём обуглена и темна, угли тлеют редкими пятнами; само пламя — языки-частицы над ней
        heat = (0.12 + 0.12 * depth + 0.6 * hot * depth) * inside
        alpha = np.clip((edge - 0.45) * 5, 0, 1) * (0.55 + 0.35 * depth)
        return bake(np.clip(heat, 0, 1), "scorch", alpha), inside, depth

    def draw(self, flat):
        if self.img is not None:
            flat.blit(*self.img)

    def sample(self, n, rng):
        """n случайных точек горящей площади (клетки поля) — откуда поднимаются языки пламени."""
        if self.inside is None or n <= 0:
            return None
        ys, xs = np.nonzero(self.inside)
        if not len(xs):
            return None
        i = rng.integers(0, len(xs), n)
        x0, y0 = self.box[0], self.box[1]
        return x0 + (xs[i] + rng.random(n)) / RES, y0 + (ys[i] + rng.random(n)) / RES


class IceField(FireField):
    """Ледяные клетки — единая ледяная корка: край общий и рваный (сетки нет), внутри — грани и трещины,
    по льду медленно ползёт блик. Вода под коркой выглядит замёрзшей: корка непрозрачнее воды вокруг."""

    def _facets(self, h, w):
        """Ячейки вокруг случайных центров (~3 на клетку): между ними — трещины."""
        k = max(4, int(h * w / (RES * RES) * 3))
        py, px = self.rng.uniform(0, h, k), self.rng.uniform(0, w, k)
        ys, xs = np.mgrid[0:h, 0:w]
        best = np.full((h, w), np.inf)
        lab = np.zeros((h, w), int)
        for i in range(k):
            d = (ys - py[i]) ** 2 + (xs - px[i]) ** 2
            m = d < best
            best[m] = d[m]
            lab[m] = i
        return lab

    def _paint(self, n0, n1, n2, t):
        edge = self.cover_n + ((n0 - 0.5) * 0.5 + (n1 - 0.5) * 0.15) * (self.cover > 0.02)   # край неподвижный
        inside = edge > 0.5
        depth = np.clip((edge - 0.5) * 2.5, 0, 1)
        if getattr(self, "facets", None) is None or self.facets.shape != n0.shape:
            self.facets = self._facets(*n0.shape)
        cells = self.facets                                           # грани льда — ячейки вокруг случайных центров
        crack = (cells != np.roll(cells, 1, 0)) | (cells != np.roll(cells, 1, 1))
        h, w = n0.shape
        ys, xs = np.mgrid[0:h, 0:w]
        glint = np.abs(((xs + ys) - (t * 3) % (w + h + 80)) + 40) < 3   # блик идёт по льду наискось
        # наледь: полупрозрачная, голубая, белые трещины и блик — земля сквозь неё видна
        # дизеринг делает прозрачность редкими точками: основа — ~10% пикселей, трещины и блик — сплошь
        v = 0.28 + 0.08 * (cells % 3) / 2 + crack * 0.4 + glint * 0.35
        alpha = np.clip((edge - 0.45) * 5, 0, 1) * (0.1 + 0.06 * depth + crack * 0.6 + glint * 0.5)
        return bake(np.clip(v * inside, 0, 1), "ice", alpha), inside, depth
