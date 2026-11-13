"""Ковка «в двух видах» (квиз 2026-11-12, упрощение 3D-ковки): брусок всегда лежит вдоль наковальни; по длине —
станции, у каждой ширина w, толщина t (мм) и округлость r (0 — прямоугольник, 1 — круг) и длина dx.

Поворот — на 45° (A/D): плашмя (0°) — удар тоньшит и чуть уширяет; на ребро (90°) — сужает и чуть утолщает;
на угол (45°) — срубает углы: сечение скругляется и выравнивается. Боёк всегда на всю ширину. Узкий боёк
(клин) тянет металл в длину, широкий (кувалда) раздаёт вширь. Объём сохраняется: тоньше — длиннее.

Цели — профиль по длине (ширина, толщина, округлость); совпадение — пересечение к объединению сечений вдоль
длины. 1 г стали ≈ 128 мм³."""
import math

import numpy as np

MM3_PER_G = 1 / 0.0078
DXMAX = 4.0                                  # станция длиннее — делится (разрешение там, где вытянули)
HAMMERS = {"hand": (0.22, 9.0), "peen": (0.28, 6.0), "sledge": (0.30, 14.0), "flatter": (0.0, 18.0),
           "die_flat": (0.22, 14.0), "die_fuller": (0.26, 4.0)}      # сжатие за полный удар, полудлина бойка (мм)
K_ROUND = 1 - math.pi / 4                    # круг меньше квадрата той же ширины


def shape_k(r):
    """Доля площади прямоугольника w×t, занятая сечением округлости r."""
    return 1 - K_ROUND * np.clip(r, 0, 1)


def orient_name(deg):
    d = int(round(deg)) % 180
    return "плашмя" if d == 0 else "на ребро" if d == 90 else "на угол"


# ---------- цели ----------

TARGETS = {   # (длина, мм, [(u0, u1, ширина:толщина, округлость, доля площади)])
    "rod": (160, [(0.0, 1.0, 1.0, 1.0, 1.0)]),
    "wire": (340, [(0.0, 1.0, 1.0, 1.0, 1.0)]),
    "strip": (260, [(0.0, 1.0, 2.0, 0.0, 1.0)]),
    "sheet": (300, [(0.0, 1.0, 12.0, 0.0, 1.0)]),
}
ITEM_TARGETS = {   # цельная ковка: основная деталь изделия прямой заготовкой (сгибается после)
    "bracers": (200, [(0.0, 0.7, 22.0, 0.0, 0.95), (0.7, 1.0, 26.0, 0.0, 1.12)]),     # пластина с раструбом
    "belt": (420, [(0.0, 0.88, 3.0, 0.0, 0.85), (0.88, 1.0, 1.2, 0.0, 2.1)]),          # полоса и пряжка
    "ring": (80, [(0.0, 0.42, 1.0, 1.0, 0.8), (0.42, 0.58, 1.0, 0.0, 2.0), (0.58, 1.0, 1.0, 1.0, 0.8)]),
    "amulet": (150, [(0.0, 0.3, 1.0, 1.0, 0.35), (0.3, 1.0, 5.0, 0.0, 1.28)]),        # петля и диск
}


class Target:
    """Профиль цели: ширина, толщина, округлость в доле длины u."""

    def __init__(self, kind, mass, item=False):
        self.kind, self.item, self.mass = kind, item, mass
        self.length, self.parts = (ITEM_TARGETS if item else TARGETS)[kind]
        self.length = float(self.length)
        v = mass * MM3_PER_G
        self.a0 = v / self.length / sum((u1 - u0) * k for u0, u1, _, _, k in self.parts)

    def at(self, u):
        """(w, t, r) цели в доле длины u; за концами — (0, 0, 0)."""
        if u < 0 or u > 1:
            return 0.0, 0.0, 0.0
        for u0, u1, aspect, r, k in self.parts:
            if u0 <= u <= u1:
                a = self.a0 * k
                t = math.sqrt(a / aspect / float(shape_k(r)))
                return t * aspect, t, r
        return 0.0, 0.0, 0.0

    def profile(self, n=80):
        us = (np.arange(n) + 0.5) / n
        return us * self.length, np.array([self.at(u) for u in us])


# ---------- брусок ----------

class Bar:
    """Брусок: станции (w, t, r, dx), положение orient (градусы: 0 — плашмя, 90 — на ребро, 45 — на угол)."""

    def __init__(self, mass_g, n=12):
        v = mass_g * MM3_PER_G
        s = (v / 1.2) ** (1 / 3)
        self.w = np.full(n, s)
        self.t = np.full(n, s)
        self.r = np.zeros(n)
        self.dx = np.full(n, 1.2 * s / n)
        self.orient = 0.0
        self.roll = 0.0                         # поворот для рисунка (догоняет orient)
        self.vol0 = self.volume()

    def area(self):
        return self.w * self.t * shape_k(self.r)

    def volume(self):
        return float((self.area() * self.dx).sum())

    def length(self):
        return float(self.dx.sum())

    def centers(self):
        return np.cumsum(self.dx) - self.dx / 2

    def turn(self, deg):
        self.orient = (self.orient + deg) % 180

    # ----- удар -----

    def strike(self, x, power, hammer="hand"):
        """Удар в точку x (мм от левого конца). → доля сжатия (0 — мимо)."""
        c0, hx = HAMMERS[hammer]
        if hammer == "flatter":
            return self.smooth(x, power, hx)
        cen = self.centers()
        wgt = np.exp(-(np.abs(cen - x) / hx) ** 4)
        c = np.clip(c0 * power * wgt, 0, 0.5)
        hit = c > 0.005
        if not hit.any():
            return 0.0
        a0 = self.area()
        d = int(round(self.orient)) % 180
        bite = 2 * hx
        if d in (0, 90):                                  # плашмя (сжимаем t) или на ребро (сжимаем w)
            v, h = (self.t, self.w) if d == 0 else (self.w, self.t)
            lat = bite / (bite + h)                       # узкий боёк — меньше вбок, больше в длину
            v_new = v * (1 - c)
            h_new = h * (1 - c) ** (-0.5 * lat)
            if d == 0:
                self.t, self.w = v_new, h_new
            else:
                self.w, self.t = v_new, h_new
            self.r = self.r * (1 - 2.5 * c)              # плоский удар — грани плоские
        else:                                             # на угол: срубаем углы — круглее и ровнее
            g = np.sqrt(self.w * self.t)
            self.w = self.w + (g - self.w) * np.clip(c * 3, 0, 1)
            self.t = self.t + (g - self.t) * np.clip(c * 3, 0, 1)
            self.w *= (1 - 0.45 * c)
            self.t *= (1 - 0.45 * c)
            self.r = np.clip(self.r + 1.8 * c, 0, 1)
        self.dx *= a0 / self.area()                      # объём: тоньше — длиннее
        self.refine()
        return float(c.max())

    def swage(self, x, power, hx=10.0):
        """Обжимка: сечение к кругу той же площади (как ни лежит) и чуть тянет."""
        cen = self.centers()
        k = np.clip(0.35 * power * np.exp(-(np.abs(cen - x) / hx) ** 4), 0, 1)
        if not (k > 0.005).any():
            return 0.0
        a0 = self.area()
        g = np.sqrt(self.w * self.t)
        self.w += (g - self.w) * k
        self.t += (g - self.t) * k
        self.r += (1 - self.r) * k
        s = np.sqrt(a0 / self.area()) * (1 - 0.04 * k)  # площадь та же (чуть меньше — тянет)
        self.w *= s
        self.t *= s
        self.dx *= a0 / self.area()
        self.refine()
        return float(k.max())

    def smooth(self, x, power, hx):
        """Гладилка: выравнивает ширину, толщину и округлость с соседями (объём сохраняется)."""
        cen = self.centers()
        k = np.clip(0.5 * power * np.exp(-(np.abs(cen - x) / hx) ** 4), 0, 1)
        if not (k > 0.01).any():
            return 0.0
        vol = self.volume()
        for arr in (self.w, self.t, self.r):
            p = np.pad(arr, 1, mode="edge")
            avg = (p[:-2] + 2 * p[1:-1] + p[2:]) / 4
            arr += (avg - arr) * k
        self.dx *= vol / self.volume()
        return float(k.max())

    def refine(self):
        """Длинные станции делятся пополам (вытянутый металл — больше точек)."""
        for _ in range(6):
            long = np.nonzero(self.dx > DXMAX)[0]
            if not len(long) or len(self.dx) > 400:
                return
            for arr in ("w", "t", "r"):
                a = getattr(self, arr)
                setattr(self, arr, np.insert(a, long + 1, a[long]))
            self.dx[long] /= 2
            self.dx = np.insert(self.dx, long + 1, self.dx[long])

    # ----- оценка -----

    def score(self, target):
        """Совпадение 0–1: пересечение к объединению сечений вдоль длины (ширину и толщину можно поменять
        местами — брусок тот же, повёрнутый)."""
        cen = self.centers()
        best = 0.0
        tw = np.array([target.at(u) for u in cen / target.length])
        for swap in (False, True):
            w, t = (self.t, self.w) if swap else (self.w, self.t)
            inter = np.minimum(w, tw[:, 0]) * np.minimum(t, tw[:, 1]) * shape_k(np.maximum(self.r, tw[:, 2])) \
                * (1 - 0.35 * np.abs(self.r - tw[:, 2]))
            at = tw[:, 0] * tw[:, 1] * shape_k(tw[:, 2])
            union = (self.area() + at - inter) @ self.dx
            if self.length() < target.length:                  # недотянуто — хвост цели мимо
                xs, prof = target.profile(60)
                tail = xs > self.length()
                union += float((prof[tail, 0] * prof[tail, 1] * shape_k(prof[tail, 2])).sum()) * target.length / 60
            v = float((inter @ self.dx) / union) if union > 0 else 0.0
            if v > best:
                best, self.swapped = v, swap
        return best

    def at_x(self, x):
        """Станция под точкой x: (w, t, r)."""
        i = int(np.clip(np.searchsorted(np.cumsum(self.dx), x), 0, len(self.dx) - 1))
        return float(self.w[i]), float(self.t[i]), float(self.r[i]), i

    # ----- поверхность (для 3D-вида) -----

    def rings(self, w, t, r, roll, seg=24):
        """Сечения-суперэллипсы (n = 8 − 6r) с поворотом roll: (станции × seg × 2) в осях (y, z)."""
        a = np.linspace(0, 2 * math.pi, seg, endpoint=False)
        n = 8 - 6 * np.clip(r, 0, 1)
        ca, sa = np.cos(a), np.sin(a)
        e = 2 / n[:, None]
        y = (w[:, None] / 2) * np.sign(ca) * np.abs(ca) ** e
        z = (t[:, None] / 2) * np.sign(sa) * np.abs(sa) ** e
        cr, sr = math.cos(roll), math.sin(roll)
        return np.stack([y * cr - z * sr, y * sr + z * cr], -1)

    def surface(self, x0=None):
        """Мировая сетка бруска (лежит на z = 0; левый конец — x0, по умолчанию по середине наковальни)."""
        x0 = getattr(self, "x0", None) if x0 is None else x0
        return tube(self.centers(), self.w, self.t, self.r, self.roll, self.length(), x0)


def tube(xc, w, t, r, roll, length, x0=None, seg=24):
    """Трубка по станциям: кольца-суперэллипсы и торцы; низ — на z = 0."""
    bar = Bar.__new__(Bar)
    R = bar.rings(np.asarray(w, float), np.asarray(t, float), np.asarray(r, float), roll, seg)
    x0 = -length / 2 if x0 is None else x0
    xs = np.concatenate([[0.0], xc, [length]]) + x0
    R = np.concatenate([R[:1], R, R[-1:]])
    lift = -R[..., 1].min()
    n = len(xs)
    V = np.zeros((n, seg, 3))
    V[..., 0] = xs[:, None]
    V[..., 1] = R[..., 0]
    V[..., 2] = R[..., 1] + lift
    V = V.reshape(-1, 3)
    I = np.arange(n * seg).reshape(n, seg)
    J = np.roll(I, -1, 1)
    T = np.concatenate([np.stack([I[:-1], I[1:], J[1:]], -1).reshape(-1, 3),
                        np.stack([I[:-1], J[1:], J[:-1]], -1).reshape(-1, 3)])
    c0 = len(V)
    c1 = c0 + 1
    V = np.concatenate([V, [[xs[0], 0, lift], [xs[-1], 0, lift]]])
    caps = [(c0, J[0, k], I[0, k]) for k in range(seg)] + [(c1, I[-1, k], J[-1, k]) for k in range(seg)]
    T = np.concatenate([T, np.array(caps)])
    N = np.zeros_like(V)
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    for k in range(3):
        np.add.at(N, T[:, k], fn)
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    return V, T, N, np.ones(len(V), bool)


def forged_score(match, cracks=0, burn=0.0):
    """Оценка ковки 0–1: 90% совпадения — идеал, трещины и окалина снижают."""
    return round(max(0.0, min(1.0, (match - 0.3) / 0.6)) * (0.85 ** cracks) * (1 - burn), 3)
