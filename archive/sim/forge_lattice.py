"""Объёмная ковка на деформируемой решётке (квиз 2026-11-12): металл — гибкий каркас узлов X[i, j, k] (как сетка
внутри пластилина; i — вдоль бруска). Поверхность — внешние грани решётки (готовая гладкая 3D-сетка).

Удар — отображение пространства в мировых координатах (молот всегда сверху, наковальня — плоскость z = 0):
металл под бойком сжимается к наковальне и течёт туда, где пятно контакта уже (клин поперёк бруска — металл
тянется вдоль), дальние части сдвигаются целиком. Узлы переносятся этим отображением. Деталь поворачивается как
угодно (R: деталь → мир) — удар приходится на любую грань, скашивает конец под углом, осаживает торец.
Изгиб — поворот части детали вокруг рога наковальни. Растянутые ячейки делятся (вставляется слой узлов) —
разрешение растёт там, где металл вытянут. Объём сохраняется (малый дрейф поправляется).

Цели (примитивы и изделия) — формы с функцией расстояния; совпадение — объём металла внутри цели к объединению,
после совмещения по главным осям. Всё в миллиметрах; 1 г стали ≈ 128 мм³."""
import math

import numpy as np

MM3_PER_G = 1 / 0.0078
LMAX = 4.0                         # ячейка длиннее (мм) делится
HAMMERS = {"hand": (0.16, 11.0, 11.0), "peen": (0.20, 5.0, 24.0), "sledge": (0.24, 17.0, 17.0),
           "flatter": (0.07, 30.0, 30.0),
           "die_flat": (0.20, 14.0, 34.0), "die_fuller": (0.24, 4.0, 34.0)}   # бойки автомолота (обжимка — swage)   # сжатие за удар, полуразмеры бойка по x и y мира (клин — узкий по x)
HORN = {"x0": -260.0, "x1": -130.0, "r0": 9.0, "r1": 42.0, "y": 0.0}   # рог вдоль x: тонкий кончик x0 → основание x1


def rot(axis, a):
    """Поворот на угол a вокруг единичной оси axis."""
    x, y, z = axis
    c, s = math.cos(a), math.sin(a)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def orthonormal(R):
    u, _, vt = np.linalg.svd(R)
    return u @ vt


def horn_r(x):
    k = min(1.0, max(0.0, (x - HORN["x0"]) / (HORN["x1"] - HORN["x0"])))
    return HORN["r0"] + (HORN["r1"] - HORN["r0"]) * k


def principal_axes(p, w=None):
    """Главные оси облака точек (столбцы по убыванию разброса), правая тройка."""
    w = np.ones(len(p)) if w is None else w
    cov = (p * w[:, None]).T @ p / w.sum()
    ev, v = np.linalg.eigh(cov)
    v = v[:, np.argsort(ev)[::-1]]
    if np.linalg.det(v) < 0:
        v[:, 2] *= -1
    return v


# ---------- цели: функция расстояния + параметрическая сетка для призрака ----------

def _box(p, half):
    q = np.abs(p) - half
    return np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(q.max(-1), 0)


def _cyl_x(p, r, half_len):
    d = np.stack([np.linalg.norm(p[..., 1:], axis=-1) - r, np.abs(p[..., 0]) - half_len], -1)
    return np.minimum(d.max(-1), 0) + np.linalg.norm(np.maximum(d, 0), axis=-1)


def _torus_z(p, R, r):
    q = np.stack([np.linalg.norm(p[..., :2], axis=-1) - R, p[..., 2]], -1)
    return np.linalg.norm(q, axis=-1) - r


def _shell_x(p, R, t, half_len):
    """Полуцилиндрическая скорлупа (наруч): ось x, радиус R, толщина t, верхняя половина (z ≥ 0)."""
    rr = np.linalg.norm(p[..., 1:], axis=-1)
    return np.maximum(np.maximum(np.abs(rr - R) - t / 2, -p[..., 2]), np.abs(p[..., 0]) - half_len)


def _mesh_grid(fn, nu, nv, closed_u=False, closed_v=False):
    """Параметрическая поверхность fn(u, v) → (вершины, треугольники)."""
    us = np.linspace(0, 1, nu, endpoint=not closed_u)
    vs = np.linspace(0, 1, nv, endpoint=not closed_v)
    U, V = np.meshgrid(us, vs, indexing="ij")
    P = fn(U, V).reshape(-1, 3)
    tris = []
    for a in range(nu if closed_u else nu - 1):
        for b in range(nv if closed_v else nv - 1):
            a2, b2 = (a + 1) % nu, (b + 1) % nv
            i00, i01, i10, i11 = a * nv + b, a * nv + b2, a2 * nv + b, a2 * nv + b2
            tris += [(i00, i10, i11), (i00, i11, i01)]
    return P, np.array(tris, np.int32)


def _merge(*meshes):
    vs, ts, off = [], [], 0
    for v, t in meshes:
        vs.append(v)
        ts.append(t + off)
        off += len(v)
    return np.concatenate(vs), np.concatenate(ts)


def _mesh_box(half, c=(0, 0, 0)):
    out = []
    for ax in range(3):
        for sgn in (-1, 1):
            a, b = [k for k in range(3) if k != ax]

            def f(U, V, ax=ax, sgn=sgn, a=a, b=b):
                P = np.zeros(U.shape + (3,))
                P[..., ax] = sgn * half[ax]
                P[..., a] = (U * 2 - 1) * half[a]
                P[..., b] = (V * 2 - 1) * half[b] * sgn
                return P + np.asarray(c)
            out.append(_mesh_grid(f, 2, 2))
    return _merge(*out)


def _mesh_cyl_x(r, half_len):
    side = _mesh_grid(lambda U, V: np.stack([(U * 2 - 1) * half_len, r * np.cos(V * 2 * math.pi),
                                             r * np.sin(V * 2 * math.pi)], -1), 2, 32, closed_v=True)
    caps = [_mesh_grid(lambda U, V, s=s: np.stack([np.full_like(U, s * half_len), U * r * np.cos(V * 2 * math.pi),
                                                   U * r * np.sin(V * 2 * math.pi)], -1), 2, 32, closed_v=True)
            for s in (-1, 1)]
    return _merge(side, *caps)


def _mesh_torus_z(R, r, c=(0, 0, 0)):
    return _mesh_grid(lambda U, V: np.stack([(R + r * np.cos(V * 2 * math.pi)) * np.cos(U * 2 * math.pi) + c[0],
                                             (R + r * np.cos(V * 2 * math.pi)) * np.sin(U * 2 * math.pi) + c[1],
                                             r * np.sin(V * 2 * math.pi) + c[2]], -1), 48, 16, True, True)


def _mesh_shell_x(R, t, half_len, dz):
    out = []
    for rr in (R - t / 2, R + t / 2):
        out.append(_mesh_grid(lambda U, V, rr=rr: np.stack([(U * 2 - 1) * half_len, rr * np.cos(V * math.pi),
                                                            rr * np.sin(V * math.pi) + dz], -1), 2, 24))
    return _merge(*out)


def _mesh_disc_z(Rd, t):
    side = _mesh_grid(lambda U, V: np.stack([Rd * np.cos(V * 2 * math.pi), Rd * np.sin(V * 2 * math.pi),
                                             (U - 0.5) * t], -1), 2, 40, closed_v=True)
    caps = [_mesh_grid(lambda U, V, s=s: np.stack([U * Rd * np.cos(V * 2 * math.pi), U * Rd * np.sin(V * 2 * math.pi),
                                                   np.full_like(U, s * t / 2)], -1), 2, 40, closed_v=True)
            for s in (-1, 1)]
    return _merge(side, *caps)


def target_shape(kind, mass, item=False):
    """(функция расстояния, полуразмеры, сетка призрака) цели в её системе (длинная ось — x)."""
    v = mass * MM3_PER_G
    if not item:
        if kind in ("rod", "wire"):
            L = 160.0 if kind == "rod" else 340.0
            r = math.sqrt(v / L / math.pi)
            return (lambda p: _cyl_x(p, r, L / 2)), np.array([L / 2, r, r]), _mesh_cyl_x(r, L / 2)
        L, aspect = (260.0, 2.0) if kind == "strip" else (300.0, 12.0)
        t = math.sqrt(v / L / aspect)
        half = np.array([L / 2, t * aspect / 2, t / 2])
        return (lambda p: _box(p, half)), half, _mesh_box(half)
    if kind == "bracers":                      # согнутая пластина: полуцилиндр
        R, L = 36.0, 110.0
        t = v / (math.pi * R * L)
        dz = -R * 0.36
        return (lambda p: _shell_x(p - np.array([0, 0, dz]), R, t, L / 2)), np.array([L / 2, R + t, R * 0.7]), \
            _mesh_shell_x(R, t, L / 2, dz)
    if kind == "ring":                         # кольцо: тор
        R = 11.0
        r = math.sqrt(v / (2 * math.pi ** 2 * R))
        return (lambda p: _torus_z(p, R, r)), np.array([R + r, R + r, r]), _mesh_torus_z(R, r)
    if kind == "amulet":                       # диск с петлёй
        Rd = 30.0
        t = v * 0.9 / (math.pi * Rd * Rd)
        lr = max(1.6, t * 0.5)
        lc = (Rd + 5.0, 0.0, 0.0)
        return (lambda p: np.minimum(np.maximum(np.linalg.norm(p[..., :2], axis=-1) - Rd, np.abs(p[..., 2]) - t / 2),
                                     _torus_z(p - np.array(lc), 5.0, lr))), np.array([Rd + 7, Rd, t / 2 + 1]), \
            _merge(_mesh_disc_z(Rd, t), _mesh_torus_z(5.0, lr, lc))
    L = 420.0                                  # пояс: длинная полоса с утолщённой пряжкой
    t = math.sqrt(v * 0.85 / L / 3)
    half = np.array([L / 2, 1.5 * t, t / 2])
    bc, bh = np.array([L / 2 - 14, 0, 0]), np.array([14.0, 2.4 * t, 1.6 * t])
    return (lambda p: np.minimum(_box(p, half), _box(p - bc, bh))), np.array([L / 2, 2.4 * t, 1.6 * t]), \
        _merge(_mesh_box(half), _mesh_box(bh, bc))


class Target:
    """Цель: функция расстояния, объём, главные оси, сетка призрака."""

    def __init__(self, kind, mass, item=False):
        self.kind, self.item, self.mass = kind, item, mass
        self.sdf, self.half, self.mesh = target_shape(kind, mass, item)
        self.length = float(self.half.max() * 2)
        rng = np.random.default_rng(7)
        pts = (rng.random((60000, 3)) * 2 - 1) * self.half * 1.05
        inside = pts[self.sdf(pts) <= 0]
        self.volume = float(len(inside) / len(pts) * np.prod(self.half * 2.1))
        self.center = inside.mean(0)
        self.axes = principal_axes(inside - self.center)


# ---------- деталь ----------

class TopMap:
    """Высота верха металла над столом: растр 2 мм по узлам (с расширением — между узлами нет дыр),
    билинейное чтение в любой точке."""

    def __init__(self, pts, cell=2.0):
        self.lo = pts[:, :2].min(0) - 3 * cell
        self.cell = cell
        n = np.ceil((pts[:, :2].max(0) + 3 * cell - self.lo) / cell).astype(int) + 1
        g = np.zeros(n)
        idx = np.floor((pts[:, :2] - self.lo) / cell).astype(int)
        np.maximum.at(g, (idx[:, 0], idx[:, 1]), pts[:, 2])
        for _ in range(2):                                 # заполнить промежутки между узлами
            p_ = np.pad(g, 1)
            g = np.max([p_[1:-1, 1:-1], p_[:-2, 1:-1], p_[2:, 1:-1], p_[1:-1, :-2], p_[1:-1, 2:]], axis=0)
        self.g = g

    def grid_points(self):
        """Центры клеток растра (nx×ny×2)."""
        xs = self.lo[0] + (np.arange(self.g.shape[0]) + 0.5) * self.cell
        ys = self.lo[1] + (np.arange(self.g.shape[1]) + 0.5) * self.cell
        return np.stack(np.meshgrid(xs, ys, indexing="ij"), -1)

    def read(self, grid, x, y):
        """Билинейно значение любого растра той же сетки в точках (x, y)."""
        g0 = self.g
        self.g = grid
        try:
            return self(x, y)
        finally:
            self.g = g0

    def __call__(self, x, y):
        u = (x - self.lo[0]) / self.cell - 0.5
        v = (y - self.lo[1]) / self.cell - 0.5
        i0 = np.clip(np.floor(u).astype(int), 0, self.g.shape[0] - 2)
        j0 = np.clip(np.floor(v).astype(int), 0, self.g.shape[1] - 2)
        fu = np.clip(u - i0, 0, 1)
        fv = np.clip(v - j0, 0, 1)
        g = self.g
        return ((1 - fu) * (1 - fv) * g[i0, j0] + fu * (1 - fv) * g[i0 + 1, j0] + (1 - fu) * fv * g[i0, j0 + 1]
                + fu * fv * g[i0 + 1, j0 + 1])



class Piece:
    """Решётка узлов X (ni×nj×nk×3, в осях детали; i — вдоль бруска), поворот R (деталь → мир), сдвиг t.
    Слиток ничем не держится — крутится как угодно и куётся весь (grip_i = 0; поле оставлено для совместимости)."""

    def __init__(self, mass_g, n=(13, 9, 9), grip_frac=0.0):
        v = mass_g * MM3_PER_G
        s = (v / 1.2) ** (1 / 3)
        size = np.array([1.2 * s, s, s])
        g = [np.linspace(-size[k] / 2, size[k] / 2, n[k]) for k in range(3)]
        self.X = np.stack(np.meshgrid(*g, indexing="ij"), -1).astype(float)
        self.grip_i = max(2, int(round(grip_frac * (n[0] - 1)))) if grip_frac > 0 else 0
        self.R = np.eye(3)
        self.t = np.zeros(3)
        self.on_horn = False
        self.slide = 0.0
        self.shift_x = 0.0                               # подача под автомолот (сдвиг по x мира)
        self.vol0 = self.volume()

    # ----- геометрия -----

    def world(self):
        return self.X @ self.R.T + self.t

    def cells(self):
        """Центры и объёмы ячеек (по средним рёбрам — трилинейный якобиан в центре)."""
        X = self.X
        a = (X[1:, :-1, :-1] + X[1:, 1:, :-1] + X[1:, :-1, 1:] + X[1:, 1:, 1:]
             - X[:-1, :-1, :-1] - X[:-1, 1:, :-1] - X[:-1, :-1, 1:] - X[:-1, 1:, 1:]) / 4
        b = (X[:-1, 1:, :-1] + X[1:, 1:, :-1] + X[:-1, 1:, 1:] + X[1:, 1:, 1:]
             - X[:-1, :-1, :-1] - X[1:, :-1, :-1] - X[:-1, :-1, 1:] - X[1:, :-1, 1:]) / 4
        c = (X[:-1, :-1, 1:] + X[1:, :-1, 1:] + X[:-1, 1:, 1:] + X[1:, 1:, 1:]
             - X[:-1, :-1, :-1] - X[1:, :-1, :-1] - X[:-1, 1:, :-1] - X[1:, 1:, :-1]) / 4
        vol = np.abs(np.einsum("...i,...i", a, np.cross(b, c)))
        cen = (X[1:, 1:, 1:] + X[:-1, :-1, :-1] + X[1:, :-1, :-1] + X[:-1, 1:, :-1] + X[:-1, :-1, 1:]
               + X[1:, 1:, :-1] + X[1:, :-1, 1:] + X[:-1, 1:, 1:]) / 8
        return cen, vol

    def volume(self):
        return float(self.cells()[1].sum())

    def bad_cells(self):
        X = self.X
        a, b, c = X[1:, :-1, :-1] - X[:-1, :-1, :-1], X[:-1, 1:, :-1] - X[:-1, :-1, :-1], X[:-1, :-1, 1:] - X[:-1, :-1, :-1]
        return np.einsum("...i,...i", a, np.cross(b, c)) <= 0

    def untangle(self, iters=6):
        """Вывернутые ячейки (редкий излом на гребне): их узлы — к среднему соседей, пока не выправятся."""
        for _ in range(iters):
            bad = self.bad_cells()
            if not bad.any():
                return
            m = np.zeros(self.X.shape[:3], bool)
            for di in (0, 1):
                for dj in (0, 1):
                    for dk in (0, 1):
                        m[di:di + bad.shape[0], dj:dj + bad.shape[1], dk:dk + bad.shape[2]] |= bad
            P = np.pad(self.X, ((1, 1), (1, 1), (1, 1), (0, 0)), mode="edge")
            avg = (P[:-2, 1:-1, 1:-1] + P[2:, 1:-1, 1:-1] + P[1:-1, :-2, 1:-1] + P[1:-1, 2:, 1:-1]
                   + P[1:-1, 1:-1, :-2] + P[1:-1, 1:-1, 2:]) / 6
            self.X[m] = self.X[m] * 0.5 + avg[m] * 0.5

    def inverted(self):
        """Доля вывернутых ячеек (решётка сложилась) — для проверки модели."""
        X = self.X
        a, b, c = X[1:, :-1, :-1] - X[:-1, :-1, :-1], X[:-1, 1:, :-1] - X[:-1, :-1, :-1], X[:-1, :-1, 1:] - X[:-1, :-1, :-1]
        return float((np.einsum("...i,...i", a, np.cross(b, c)) <= 0).mean())

    def free_mask(self):
        """Узлы, которые куются (не в клещах)."""
        m = np.ones(self.X.shape[:3], bool)
        m[:self.grip_i] = False
        return m

    def free_weight(self, fade=6.0):
        """Насколько узел куётся: 0 в клещах, плавно до 1 на первых fade мм от губок (у губок не плющится)."""
        if self.grip_i == 0:
            return np.ones(self.X.shape[:3])
        mid = self.X[:, self.X.shape[1] // 2, self.X.shape[2] // 2]
        seg = np.linalg.norm(np.diff(mid, axis=0), axis=1)
        dist = np.concatenate([[0.0], np.cumsum(seg)])
        d = dist - dist[self.grip_i - 1]
        k = np.clip(d / fade, 0, 1)
        w = k * k * (3 - 2 * k)
        w[:self.grip_i] = 0.0
        return np.broadcast_to(w[:, None, None], self.X.shape[:3])

    def settle(self):
        """Положить деталь: на наковальне — нижней точкой на z = 0 над серединой лица; на роге — на вершину рога
        (сдвиг slide поперёк рога)."""
        self.t = np.zeros(3)
        W = self.world().reshape(-1, 3)
        cx, cy = W[:, 0].mean(), W[:, 1].mean()
        if self.on_horn:
            near = np.abs(W[:, 1] - cy - self.slide) < 6.0
            base = W[near, 2].min() if near.any() else W[:, 2].min()
            self.t = np.array([-cx + (HORN["x0"] + HORN["x1"]) / 2, -cy - self.slide + HORN["y"], -base])
        else:
            self.t = np.array([-cx + self.shift_x, -cy, -W[:, 2].min()])

    def turn(self, Rw):
        """Повернуть деталь в клещах поворотом мира Rw, снова положить."""
        self.R = orthonormal(Rw @ self.R)
        self.settle()

    # ----- удар и изгиб -----

    def strike(self, px, py, power, hammer="hand"):
        """Удар плоским бойком сверху в точку (px, py) мира. Боёк опускается до высоты H — на долю ниже самой
        высокой точки под ним — и прижимает к ней всё, что выше (высокое сминается сильнее: углы срубаются,
        края подтягиваются); вытесненный металл течёт вбок и вдоль (туда, где пятно уже). → доля сжатия."""
        if self.on_horn:
            return self._bend(px, py, power)
        c0, hx, hy = HAMMERS[hammer]
        W = self.world()
        flat = W.reshape(-1, 3)
        fr = self.free_weight().ravel().astype(float)

        def foot(x, y):
            return np.exp(-(np.abs(x - px) / hx) ** 4) * np.exp(-(np.abs(y - py) / hy) ** 4)
        w = foot(flat[:, 0], flat[:, 1]) * fr
        hit = w > 0.5
        if not hit.any():
            return 0.0
        span = min(np.ptp(flat[:, 0]), np.ptp(flat[:, 1]))
        top = TopMap(flat, float(np.clip(span / 12, 0.4, 2.0)))   # верх металла над столом (растр по толщине)
        H = flat[hit, 2].max() * (1 - c0 * power)

        def squeeze(x, y):
            """Доля сжатия столбца металла в точке (x, y): прижать верх к бойку."""
            ww = foot(x, y)
            tp = np.maximum(top(x, y), 1e-3)
            cap = H * ww + tp * (1 - ww)
            return np.clip(1 - np.minimum(1.0, cap / tp), 0, 0.6)
        g = top.grid_points()
        cg = squeeze(g[..., 0], g[..., 1])
        for _ in range(2):                                 # сгладить излом на гребне (иначе ячейки выворачиваются)
            q = np.pad(cg, 1, mode="edge")
            cg = (q[1:-1, 1:-1] * 4 + q[:-2, 1:-1] + q[2:, 1:-1] + q[1:-1, :-2] + q[1:-1, 2:]) / 8
        c = top.read(cg, flat[:, 0], flat[:, 1]) * fr
        pressed = c > 0.02
        if not pressed.any():
            return 0.0
        lx = min(np.ptp(flat[pressed, 0]) if pressed.sum() > 1 else hx, 2 * hx) + 1.0
        ly = min(np.ptp(flat[pressed, 1]) if pressed.sum() > 1 else hy, 2 * hy) + 1.0
        fx, fy = ly / (lx + ly), lx / (lx + ly)            # металл течёт туда, где пятно уже

        # вдоль x — одна функция растяжения x' = f(x) (металл тянется, дальние части сдвигаются целиком);
        # поперёк — ширина каждого сечения x масштабируется своим s(x) около py. Якобиан в плоскости стола
        # треугольный и положительный — ячейки не перекручиваются, а вширь раздаётся только там, где сжали
        cell = top.cell
        metal = top.g > 1e-3
        n_col = np.maximum(metal.sum(1), 1)
        c_col = np.clip((cg * metal).sum(1) / n_col, 0, 0.6)          # средняя доля сжатия сечения x
        kx = (1 - c_col) ** (-fx)
        s_col = (1 - c_col) ** (-fy)
        xs = top.lo[0] + (np.arange(len(kx)) + 0.5) * cell
        Sx = np.concatenate([[0.0], np.cumsum((kx[1:] + kx[:-1]) / 2 * cell)])
        Sx -= np.interp(px, xs, Sx)
        x0 = flat[:, 0]
        dx = np.interp(x0, xs, Sx)
        dx = np.where(x0 < xs[0], Sx[0] - (xs[0] - x0), dx)
        dx = np.where(x0 > xs[-1], Sx[-1] + (x0 - xs[-1]), dx)
        dy = (flat[:, 1] - py) * np.interp(x0, xs, s_col)
        # молот сверху и наковальня снизу плющат столбец симметрично — к его середине (низ тоже срубается),
        # потом деталь снова ложится на наковальню
        zc = flat[:, 2].max() + 1.0                        # низ металла: та же карта по перевёрнутой высоте
        bot = TopMap(np.stack([flat[:, 0], flat[:, 1], zc - flat[:, 2]], -1), top.cell)
        low = zc - bot(flat[:, 0], flat[:, 1])
        mid = (top(flat[:, 0], flat[:, 1]) + low) / 2
        W1 = np.stack([px + dx, py + dy, mid + (flat[:, 2] - mid) * (1 - c)], -1)
        self._set_world(W1.reshape(W.shape))
        return float(c.max())

    def swage(self, px, power, half=10.0):
        """Обжимка автомолота: сечения под бойком (по x мира ± half) — к кругу той же площади (полукруглые бойки
        скругляют, как ни поверни)."""
        W = self.world()
        cl = W[:, W.shape[1] // 2, W.shape[2] // 2]
        w = np.exp(-(np.abs(cl[:, 0] - px) / half) ** 4) * power * 0.35
        idx = np.nonzero(w > 0.01)[0]
        if not len(idx):
            return 0.0
        nj, nk = W.shape[1:3]
        u = np.linspace(-1, 1, nj)[:, None]
        v = np.linspace(-1, 1, nk)[None, :]
        du, dv = u * np.sqrt(1 - v ** 2 / 2), v * np.sqrt(1 - u ** 2 / 2)       # квадрат решётки → круг
        W1 = W.copy()
        for i in idx:
            S = W[i]
            c = S.reshape(-1, 3).mean(0)
            ej = (S[-1, :] - S[0, :]).mean(0)
            ej /= max(1e-9, np.linalg.norm(ej))
            ek = (S[:, -1] - S[:, 0]).mean(0)
            ek -= ej * (ek @ ej)
            ek /= max(1e-9, np.linalg.norm(ek))
            ring = np.concatenate([S[0, :], S[:, -1], S[-1, ::-1], S[::-1, 0]])
            q = np.stack([(ring - c) @ ej, (ring - c) @ ek], -1)
            area = 0.5 * abs(float((q[:, 0] * np.roll(q[:, 1], -1) - np.roll(q[:, 0], -1) * q[:, 1]).sum()))
            R = np.sqrt(area / np.pi)
            target = c + R * (du[..., None] * ej + dv[..., None] * ek)
            W1[i] = S + (target - S) * min(1.0, w[i])
        self._set_world(W1)
        return float(w.max())

    def _bend(self, px, py, power):
        """На роге: часть детали со стороны удара (вдоль металла от точки опоры) поворачивается вокруг оси рога
        вниз. Каждый поперечный слой — целиком (сечения не мнутся), угол плавно нарастает на длине ~радиуса
        рога: так металл обтекает рог. Сдвигая деталь поперёк рога (Q/E), гнут дугу — кольцо, наруч."""
        W = self.world()
        cl = W[:, W.shape[1] // 2, W.shape[2] // 2]                       # средняя линия бруска
        r = horn_r(px)
        yc, zc = HORN["y"], -r
        ic = int(np.argmin(np.hypot(cl[:, 1] - yc, cl[:, 2])))           # слой, лежащий на вершине рога
        ip = int(np.argmin(np.hypot(cl[:, 0] - px, cl[:, 1] - py)))     # куда пришёлся удар
        if ip == ic:
            return 0.0
        seg = np.linalg.norm(np.diff(cl, axis=0), axis=1)
        u = np.concatenate([[0.0], np.cumsum(seg)])
        side = np.arange(len(cl)) > ic if ip > ic else np.arange(len(cl)) < ic
        d = np.abs(u - u[ic]) * side
        k = np.clip(d / max(2.0, r * 0.9), 0, 1)
        theta = 0.28 * power
        sgn = 1.0 if cl[side, 1].mean() > yc else -1.0
        a = -theta * k * k * (3 - 2 * k) * sgn                          # конец со стороны удара — вниз
        ca, sa = np.cos(a)[:, None, None], np.sin(a)[:, None, None]
        y0, z0 = W[..., 1] - yc, W[..., 2] - zc
        W1 = W.copy()
        W1[..., 1] = yc + y0 * ca - z0 * sa
        W1[..., 2] = zc + y0 * sa + z0 * ca
        self._set_world(W1)
        return float(theta)

    def _set_world(self, W1):
        """Новые мировые координаты узлов → оси детали; деление растянутых ячеек, поправка объёма, положить."""
        self.X = (W1 - self.t) @ self.R
        self.untangle()
        self.refine()
        v = self.volume()
        if v > 0:                                  # отображение сохраняет объём не идеально — малый дрейф
            cen = self.X.reshape(-1, 3).mean(0)
            self.X = cen + (self.X - cen) * (self.vol0 / v) ** (1 / 3)
        self.settle()

    def coarsen(self):
        """Убрать лишние слои, где ячейки стали короче LMAX/2 (металл сжали поперёк): узлов по оси не меньше
        5 (поперёк) и 6 (вдоль); слои клещей не трогаем."""
        for ax in (0,):                               # поперёк сетка постоянная (9×9) — уплотняем вдоль
            X = np.moveaxis(self.X, ax, 0)
            n = X.shape[0]
            keep_min = 6
            if n <= keep_min:
                continue
            span = np.linalg.norm(X[2:] - X[:-2], axis=-1).max(axis=(1, 2))      # длина ячейки без слоя m
            cand = np.nonzero(span < LMAX * 0.5)[0] + 1
            if ax == 0:
                cand = cand[cand > self.grip_i]
            drop, last = [], -5
            for m in cand:                             # не подряд, и не больше, чем можно
                if m - last >= 2 and n - len(drop) > keep_min:
                    drop.append(m)
                    last = m
            if drop:
                X = np.delete(X, drop, axis=0)
                self.X = np.moveaxis(X, 0, ax)

    def refine(self):
        """Вставить слой узлов посередине, где ячейки вдоль оси длиннее LMAX (по всем трём направлениям)."""
        self.coarsen()
        for ax in (0,):
            for _ in range(6):
                X = np.moveaxis(self.X, ax, 0)
                d = np.linalg.norm(X[1:] - X[:-1], axis=-1).max(axis=(1, 2))
                long = np.nonzero(d > LMAX)[0]
                if not len(long) or X.shape[0] > 400:
                    break
                mids = (X[long] + X[long + 1]) / 2
                X = np.insert(X, long + 1, mids, axis=0)
                if ax == 0:                              # слои клещей — те же (вставка за ними сдвигает индекс)
                    self.grip_i += int((long < self.grip_i - 1).sum())
                self.X = np.moveaxis(X, 0, ax)

    # ----- поверхность -----

    def surface(self):
        """Внешние грани решётки в мире: (вершины n×3, треугольники m×3, нормали n×3, свободна ли вершина)."""
        W = self.world()
        free = self.free_mask()
        verts, tris, fl = [], [], []
        off = 0
        ni, nj, nk = W.shape[:3]
        faces = [(0, 0, False), (0, ni - 1, True), (1, 0, True), (1, nj - 1, False), (2, 0, False), (2, nk - 1, True)]
        for ax, idx, flip in faces:
            G = np.take(W, idx, axis=ax)                       # 2D сетка узлов грани
            Fm = np.take(free, idx, axis=ax)
            a, b = G.shape[:2]
            verts.append(G.reshape(-1, 3))
            fl.append(Fm.ravel())
            I = np.arange(a * b).reshape(a, b) + off
            t1 = np.stack([I[:-1, :-1], I[1:, :-1], I[1:, 1:]], -1).reshape(-1, 3)
            t2 = np.stack([I[:-1, :-1], I[1:, 1:], I[:-1, 1:]], -1).reshape(-1, 3)
            t = np.concatenate([t1, t2])
            if flip:
                t = t[:, ::-1]
            tris.append(t)
            off += a * b
        V = np.concatenate(verts)
        T = np.concatenate(tris)
        nrm = np.zeros_like(V)
        fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
        for k in range(3):
            np.add.at(nrm, T[:, k], fn)
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
        return V, T, nrm, np.concatenate(fl)

    # ----- оценка -----

    def samples(self):
        """Точки металла (по 8 на ячейку) с объёмами — без клещей."""
        X = self.X[self.grip_i:]
        out_p, out_v = [], []
        for fu in (0.25, 0.75):
            for fv in (0.25, 0.75):
                for fw in (0.25, 0.75):
                    P = ((1 - fu) * (1 - fv) * (1 - fw) * X[:-1, :-1, :-1] + fu * (1 - fv) * (1 - fw) * X[1:, :-1, :-1]
                         + (1 - fu) * fv * (1 - fw) * X[:-1, 1:, :-1] + (1 - fu) * (1 - fv) * fw * X[:-1, :-1, 1:]
                         + fu * fv * (1 - fw) * X[1:, 1:, :-1] + fu * (1 - fv) * fw * X[1:, :-1, 1:]
                         + (1 - fu) * fv * fw * X[:-1, 1:, 1:] + fu * fv * fw * X[1:, 1:, 1:])
                    out_p.append(P.reshape(-1, 3))
        sub = Piece.__new__(Piece)
        sub.X = X
        vol = sub.cells()[1].ravel() / 8
        return np.concatenate(out_p), np.tile(vol, 8)

    def align(self, target):
        """Варианты совмещения цели с деталью по главным осям: (центр детали, Q), x_дет = центр + Q·(x_цели − центр)."""
        P, w = self.samples()
        cen = (P * w[:, None]).sum(0) / w.sum()
        Ep = principal_axes(P - cen, w)
        return [(cen, Ep @ np.diag([sx, sy, sx * sy]) @ target.axes.T) for sx in (1, -1) for sy in (1, -1)]

    def score(self, target):
        """Совпадение 0–1: объём металла внутри цели к объединению (лучшее совмещение запоминается)."""
        P, w = self.samples()
        vp = w.sum()
        best, self.best_align = 0.0, None
        for cen, Q in self.align(target):
            pt = (P - cen) @ Q + target.center                 # точки детали в системе цели
            inter = w[target.sdf(pt) <= 0].sum()
            v = inter / (vp + target.volume - inter)
            if v > best:
                best, self.best_align = float(v), (cen, Q)
        return best

    def to_target(self, pts_world, target):
        """Мировые точки → система цели (для подсветки лишнего металла)."""
        if not getattr(self, "best_align", None):
            self.score(target)
        cen, Q = self.best_align
        local = (pts_world - self.t) @ self.R
        return (local - cen) @ Q + target.center

    def target_to_world(self, pts_target, target):
        cen, Q = self.best_align
        local = cen + (pts_target - target.center) @ Q.T
        return local @ self.R.T + self.t

    def length(self):
        P, w = self.samples()
        cen = (P * w[:, None]).sum(0) / w.sum()
        ax = principal_axes(P - cen, w)[:, 0]
        q = (P - cen) @ ax
        return float(np.ptp(q) * 1.06)                   # точки — внутри ячеек; до края чуть дальше


def forged_score(match, cracks=0, burn=0.0):
    """Оценка ковки 0–1: 85% совпадения — идеал, трещины и окалина снижают."""
    return round(max(0.0, min(1.0, (match - 0.25) / 0.6)) * (0.85 ** cracks) * (1 - burn), 3)
