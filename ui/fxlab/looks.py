"""Стили эффектов: что рисовать на каждом шаге хореографии (ui/fxlab/pilot.py). Без пикселизации.

Общее для всех стилей: земля под огнём и наледь — сеткой клеток на видеокарте (край только там, где нет
соседа — горящие и ледяные клетки сливаются в одну поверхность), ледяная стена — 3D-модель из Blender гладким
затенением (у флипбуков — отрендеренная Blender картинка), след удара — гладкая копоть.
"""
import math

import numpy as np
import pygame

from ui import projection as P
from ui.pixsim import project_many

FIRE_RGB = (1.0, 0.55, 0.2)
SMOKE = (0.16, 0.13, 0.12)
VIEW = np.array([0.0, math.cos(P.PITCH), math.sin(P.PITCH)])


def make(name, pilot):
    return {"flipbook": Flipbook, "shader": Shader, "mesh": Mesh, "fluid": FluidLook}[name](pilot)


def cell_px(gx, gy):
    """Ширина клетки на экране в этой точке земли."""
    return P.project(gx, gy)[2] * P.BASE_PX


def cell_mesh(cells, mode, k=1.0, seed=0.0):
    """Клетки земли треугольниками по их настоящим углам; uv −1..1, биты соседей — в «свет»."""
    s = set(cells)
    rows = []
    for (x, y) in cells:
        bits = (1 if (x - 1, y) in s else 0) | (2 if (x + 1, y) in s else 0) | (4 if (x, y - 1) in s else 0) \
            | (8 if (x, y + 1) in s else 0)
        c = P.cell_corners((x, y))                  # дальний левый, дальний правый, ближний правый, ближний левый
        uv = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
        for tri in ((0, 1, 2), (0, 2, 3)):
            for i in tri:
                rows.append((c[i][0], c[i][1], uv[i][0], uv[i][1], 1, 1, 1, 1, mode, bits, k, seed))
    return np.array(rows, np.float32)


class Look:
    def __init__(self, pilot):
        self.pil = pilot
        self.rng = np.random.default_rng(3)
        self._ui = {}

    def reset(self):
        pass

    def update(self, dt):
        pass

    def frame_extra(self, F):
        pass

    # ---------- общее ----------

    def ice_cells(self, F, cells):
        F.mesh("ground", cell_mesh(cells, 5, 1.0, 0.3))

    def ground_heat(self, F, cells):
        F.mesh("ground", cell_mesh(cells, 6, 1.0, 0.7), blend="alpha")

    def wall_image(self, axis, run, side, variant):
        from ui import pixmesh as M
        r = M.wall(axis, run, variant, side, smooth=True)
        if r is None:
            return None
        img, (x, y) = r
        last = run[-1]
        base = P.project(last[0] + 0.5, last[1] + (1.0 if axis == "y" else 0.8))[1]
        return img, (x, y), base

    def wall_rise(self, cx, cy, axis):
        x, y, k = P.project(cx, cy)
        w = k * P.BASE_PX * 1.6

        def burst(F, f, sec):
            F.quad("air", 5, x, y - w * 0.15, w, w * 0.7, p=(f, cx, 0, 0), blend="add")
        self.pil.add(0.5, burst)

    def wall_break(self, u):
        cx, cy = u.cell[0] + 0.5, u.cell[1] + 0.5
        x, y, k = P.project(cx, cy, 0.5)
        w = k * P.BASE_PX * 2.2

        def burst(F, f, sec):
            F.quad("air", 5, x, y, w, w * 0.8, p=(f, cx, 0, 0), blend="add")
            F.quad("air", 6, x, y + w * 0.1, w * 1.1, w * 0.6, color=(1, 1, 1, 0.7), p=(f, cy, 1 - f, 0))
        self.pil.add(0.7, burst)
        self.pil.view.vfx.screen_fx(shake=5, hitstop=0.04)

    def launch(self, kind, a, d, scale):
        x, y, k = P.project(*a)
        w = k * P.BASE_PX * 0.7 * scale

        def flash(F, f, sec):
            F.quad("air", 10, x, y, w, w, color=(1.0, 0.7, 0.35, 1), p=(f, 0, 1 - f, 0), blend="add")
        self.pil.add(0.15, flash)

    def ring(self, b, R, f, col=FIRE_RGB):
        return

    def shock(self, b, R, dur=0.45, col=FIRE_RGB):
        x, y, k = P.project(b[0], b[1])
        w = k * P.BASE_PX * (R + 0.4) * 2.4

        def ring(F, f, sec):
            F.quad("ground", 2, x, y, w, w * math.sin(P.PITCH) * 0.82, color=(*col, 1), p=(f, b[0], 0, 0),
                   blend="add")
        self.pil.add(dur, ring)

    def scorch(self, b, R, d, crater):
        self.pil.spells.scorch_mark(b[0], b[1], R, d, (), crater=crater, smooth=True)

    def flash(self, b, size, col=(1.0, 0.85, 0.6), dur=0.18):
        x, y, k = P.project(*b)
        w = k * P.BASE_PX * size

        def fl(F, f, sec):
            F.quad("air", 10, x, y, w, w, color=(*col, 1), p=(f, 0, (1 - f) ** 2 * 2.5, 0), blend="add")
        self.pil.add(dur, fl)


# ---------- флипбуки из Blender ----------

class Flipbook(Look):
    """Кадры настоящей симуляции огня и дыма (Mantaflow) и физики осколков, отрендеренные Blender."""

    def __init__(self, pilot):
        super().__init__(pilot)
        self.info = {}

    def sheet(self, name):
        inf = self.info.get(name)
        if inf is None:
            from ui.fxlab.gl import sheet_info
            try:
                inf = self.info[name] = sheet_info(name)
            except OSError:
                inf = self.info[name] = None
        return inf

    def play(self, F, layer, name, x, y, size, age, loop=False, rot=0.0, alpha=1.0, smoke=SMOKE, fps=None):
        """Кадр флипбука name в точке (x, y) экрана — там, где якорь кадра. size — ширина кадра на экране."""
        inf = self.sheet(name)
        if inf is None:
            return
        n, cols = inf["frames"], inf["cols"]
        fw, fh = inf["frame"]
        rows = (n + cols - 1) // cols
        i = int(age * (fps or inf["fps"]))
        i = i % n if loop else min(i, n - 1)
        u0, v0 = (i % cols) / cols, (i // cols) / rows
        uv = (u0, v0, u0 + 1 / cols, v0 + 1 / rows)
        w, h = size, size * fh / fw
        ax, ay = inf["anchor"]
        cx, cy = x + (0.5 - ax) * w, y + (0.5 - ay) * h
        if rot:
            c, s = math.cos(rot), math.sin(rot)
            ox, oy = (0.5 - ax) * w, (0.5 - ay) * h
            cx, cy = x + ox * c - oy * s, y + ox * s + oy * c
        if inf.get("mode") == "fire":
            F.sprite(layer, name, uv, cx, cy, w, h, rot, (*smoke, alpha), mode=1, blend="alpha")
            F.sprite(layer, name, uv, cx, cy, w, h, rot, (1, 1, 1, alpha), mode=2, blend="add")
        else:
            F.sprite(layer, name, uv, cx, cy, w, h, rot, (1, 1, 1, alpha), mode=0, blend="alpha")

    def projectile(self, F, kind, p, d, sec, scale):
        x, y, k = P.project(*p)
        q = P.project(p[0] - d[0], p[1] - d[1], p[2] - d[2])
        rot = math.atan2(y - q[1], x - q[0])
        size = k * P.BASE_PX * (1.9 if kind == "meteor" else 1.15) * scale
        self.play(F, "air", "fire_head", x, y, size, sec, loop=True, rot=rot)

    def impact_fire(self, b, d, scale, R, ground, wet, big):
        name = "explosion_big" if big or R > 1.2 else "explosion"
        x, y, k = P.project(b[0], b[1], 0.0 if ground else b[2] - 0.35)
        size = k * P.BASE_PX * (R * 1.6 + 1.3) * (1.25 if big else 1.0)
        self.pil.add(1.4, lambda F, f, sec: self.play(F, "air", name, x, y, size, sec))
        self.shock(b, R)
        self.flash(b, 1.4 * scale)
        if not wet:
            self.scorch(b, R, d, 0.4 if ground else 0.0)

    def burning(self, F, cells):
        self.ground_heat(F, cells)
        t = self.pil.time
        for (cx, cy) in cells:
            for j, (ox, oy) in enumerate(((-0.2, -0.15), (0.22, 0.05), (-0.05, 0.25))):
                gx, gy = cx + 0.5 + ox, cy + 0.5 + oy
                x, y, k = P.project(gx, gy)
                ph = (cx * 7 + cy * 13 + j * 5) * 0.37
                self.play(F, "air", "fire_loop", x, y, k * P.BASE_PX * 0.95, t + ph, loop=True, alpha=0.9)

    def unit_fire(self, F, u, rect):
        t = self.pil.time
        for j, (ox, oy) in enumerate(((-0.25, 0.75), (0.25, 0.6), (0.0, 0.35))):
            x, y = rect.x + rect.w * (0.5 + ox), rect.y + rect.h * oy
            self.play(F, "air", "fire_loop", x, y, rect.w * 0.7, t + j * 0.31 + u.id * 0.17, loop=True, alpha=0.85)

    def cloud(self, F, x, y, R, k):
        sx, sy, kk = P.project(x, y, 1.7)
        size = kk * P.BASE_PX * R * 2.6
        self.play(F, "air", "snow_cloud", sx, sy, size, self.pil.time, loop=True, alpha=k * 0.95)

    def squall(self, F, x, y, R, f, sec):
        sx, sy, k = P.project(x, y)
        w = k * P.BASE_PX * R * 2.2
        F.quad("air", 7, sx, sy - w * 0.25, w, w * 0.9, p=(f, x, 1 - f * 0.5, 0), blend="add")

    def frost(self, x, y, R):
        sx, sy, k = P.project(x, y)
        size = k * P.BASE_PX * (R * 1.8 + 1.0)
        self.pil.add(1.0, lambda F, f, sec: self.play(F, "air", "ice_burst_big", sx, sy, size, sec))
        for i in range(int(3 + 4 * R)):
            a, r = self.rng.uniform(0, math.tau), R * math.sqrt(self.rng.random())
            px, py, kk = P.project(x + math.cos(a) * r, y + math.sin(a) * r)
            dl = 0.05 + r * 0.12
            self.pil.add(0.85, lambda F, f, sec, px=px, py=py, kk=kk: self.play(
                F, "air", "ice_burst", px, py, kk * P.BASE_PX * 1.2, sec), delay=dl)

    def wall_image(self, axis, run, side, variant):
        """Отрендеренная Blender стена (настоящий лёд: просвет, преломление). Длиннее 5 — кусками."""
        inf = self.sheet("ice_wall")
        if inf is None:
            return super().wall_image(axis, run, side, variant)
        import os
        from ui.fxlab.gl import FLIP_DIR
        n = len(run)
        path = os.path.join(FLIP_DIR, f"ice_wall_{axis}{min(5, n)}.png")
        if not os.path.exists(path):
            return super().wall_image(axis, run, side, variant)
        img = pygame.image.load(path)
        a, b = run[0], run[-1]
        cx, cy = (a[0] + b[0]) / 2 + 0.5, (a[1] + b[1]) / 2 + 0.5
        x, y, k = P.project(cx, cy, inf["anchor_z"])
        sc = k * P.BASE_PX / inf["px_per_cell"]
        if axis == "y" and side < 0:
            img = pygame.transform.flip(img, True, False)
        img = pygame.transform.smoothscale(img, (max(1, int(img.get_width() * sc)), max(1, int(img.get_height() * sc))))
        base = P.project(b[0] + 0.5, b[1] + (1.0 if axis == "y" else 0.8))[1]
        return img, (x - img.get_width() / 2, y - img.get_height() / 2), base

    def wall_break(self, u):
        x, y, k = P.project(u.cell[0] + 0.5, u.cell[1] + 0.5)
        size = k * P.BASE_PX * 2.4
        self.pil.add(1.0, lambda F, f, sec: self.play(F, "air", "ice_burst_big", x, y, size, sec))
        self.pil.view.vfx.screen_fx(shake=5, hitstop=0.04)


# ---------- шейдеры на шуме ----------

class Shader(Look):
    """Всё рисует фрагментный шейдер из анимированного шума: комета, огненный шар, пламя, мороз, туча."""

    def projectile(self, F, kind, p, d, sec, scale):
        x, y, k = P.project(*p)
        q = P.project(p[0] - d[0], p[1] - d[1], p[2] - d[2])
        rot = math.atan2(y - q[1], x - q[0])
        size = k * P.BASE_PX * (1.4 if kind == "meteor" else 0.8) * scale
        F.quad("air", 0, x - math.cos(rot) * size * 0.55, y - math.sin(rot) * size * 0.55, size * 2.6, size * 0.9,
               rot, p=(0, sec * 0.0 + scale, 0, 0), blend="alpha")

    def impact_fire(self, b, d, scale, R, ground, wet, big):
        x, y, k = P.project(b[0], b[1], 0.35 if ground else b[2])
        size = k * P.BASE_PX * (R * 1.9 + 1.1) * (1.25 if big else 1.0)
        seed = float(self.rng.random() * 10)
        self.pil.add(1.5 if big else 1.15, lambda F, f, sec: F.quad("air", 1, x, y - size * 0.15 * f, size, size,
                                                                       p=(f, seed, 0, 0), blend="alpha"))
        self.shock(b, R)
        self.flash(b, 1.6 * scale)
        if not wet:
            self.scorch(b, R, d, 0.4 if ground else 0.0)

    def burning(self, F, cells):
        self.ground_heat(F, cells)
        for (cx, cy) in sorted(cells, key=lambda c: c[1]):
            x, y, k = P.project(cx + 0.5, cy + 0.55)
            w = k * P.BASE_PX
            F.quad("air", 3, x, y - w * 0.42, w * 1.25, w * 1.0, p=(0, cy * 0.37, 1.0, 0), blend="alpha")

    def unit_fire(self, F, u, rect):
        F.quad("air", 4, rect.centerx, rect.centery + rect.h * 0.05, rect.w * 1.15, rect.h * 1.1,
               p=(0, u.id * 0.37, 0, 0), blend="add")

    def cloud(self, F, x, y, R, k):
        sx, sy, kk = P.project(x, y, 1.7)
        w = kk * P.BASE_PX * R * 2.6
        F.quad("air", 6, sx, sy, w, w * 0.6, p=(0, x, k, 0), color=(1, 1, 1, 0.95), blend="alpha")

    def squall(self, F, x, y, R, f, sec):
        sx, sy, k = P.project(x, y)
        w = k * P.BASE_PX * R * 2.2
        F.quad("air", 7, sx, sy - w * 0.25, w, w * 0.9, p=(f, x, 1 - f * 0.5, 0), blend="add")

    def frost(self, x, y, R):
        sx, sy, k = P.project(x, y)
        w = k * P.BASE_PX * (R * 2.2 + 0.8)
        self.pil.add(0.9, lambda F, f, sec: F.quad("ground", 5, sx, sy, w, w * math.sin(P.PITCH), p=(f, x, 0, 0),
                                                     blend="alpha"))
        self.pil.add(0.6, lambda F, f, sec: F.quad("air", 5, sx, sy - w * 0.15, w * 0.8, w * 0.7, p=(f, y, 0, 0),
                                                     blend="add"))


# ---------- меш-эффекты ----------

def icosphere(sub=2):
    t = (1 + 5 ** 0.5) / 2
    v = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
         (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
         (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
         (8, 6, 7), (9, 8, 1)]
    v = [np.array(p, float) / np.linalg.norm(p) for p in v]
    for _ in range(sub):
        cache, nf = {}, []

        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in cache:
                m = (v[a] + v[b]) / 2
                v.append(m / np.linalg.norm(m))
                cache[key] = len(v) - 1
            return cache[key]
        for a, b, c in f:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        f = nf
    return np.array(v), np.array(f)


SPHERE = icosphere(2)


class Mesh(Look):
    """Объёмные формы с бегущими текстурами: оболочка взрыва, лента хвоста, конусы пламени, кристаллы льда."""

    @staticmethod
    def tris(pts, faces, uv, mode, light, age, seed, color=(1, 1, 1, 1)):
        """3D-точки (клетки) → треугольники экрана, дальние первыми."""
        sx, sy, _ = project_many(pts[:, 0], pts[:, 1], pts[:, 2])
        depth = pts[:, 1] * math.cos(P.PITCH) + pts[:, 2] * math.sin(P.PITCH)
        order = np.argsort(depth[faces].mean(1))
        f = faces[order].ravel()
        n = len(f)
        out = np.empty((n, 12), np.float32)
        out[:, 0], out[:, 1] = sx[f], sy[f]
        out[:, 2], out[:, 3] = uv[f, 0], uv[f, 1]
        out[:, 4:8] = color
        out[:, 8], out[:, 9] = mode, light[f]
        out[:, 10], out[:, 11] = age, seed
        return out

    def sphere(self, c, r, mode, age, seed, squash=1.0, color=(1, 1, 1, 1)):
        v, f = SPHERE
        pts = v * [r, r, r * squash] + c
        light = np.clip(v @ VIEW, 0, 1)                     # к камере — ярче, край — «оболочка»
        uv = np.stack([np.arctan2(v[:, 1], v[:, 0]) / math.tau + 0.5, v[:, 2] * 0.5 + 0.5], -1)
        return self.tris(pts, f, uv, mode, light, age, seed, color)

    def projectile(self, F, kind, p, d, sec, scale):
        r = (0.28 if kind == "meteor" else 0.14) * scale
        F.mesh("air", self.sphere(np.array(p), r, 0, 0.0, 1.3), blend="alpha")
        x, y, k = P.project(*p)
        q = P.project(p[0] - d[0] * 1.6 * scale, p[1] - d[1] * 1.6 * scale, p[2] - d[2] * 1.6 * scale)
        L = min(1.0, sec * 6)
        tx, ty = x + (q[0] - x) * L, y + (q[1] - y) * L
        ln = math.hypot(tx - x, ty - y) or 1
        nx, ny = -(ty - y) / ln, (tx - x) / ln
        wd = k * P.BASE_PX * r * 1.3
        quad = [(x + nx * wd, y + ny * wd, 0, 0), (x - nx * wd, y - ny * wd, 0, 1),
                (tx - nx * wd * 0.2, ty - ny * wd * 0.2, 1, 1), (tx + nx * wd * 0.2, ty + ny * wd * 0.2, 1, 0)]
        rows = [(*quad[i][:2], *quad[i][2:], 1, 1, 1, 1, 1, 0, 0, 0.5) for i in (0, 1, 2, 0, 2, 3)]
        F.mesh("air", np.array(rows, np.float32), blend="add")

    def impact_fire(self, b, d, scale, R, ground, wet, big):
        c = np.array([b[0], b[1], 0.3 if ground else b[2]])
        rr = (0.45 + 0.55 * R) * (1.3 if big else 1.0)
        seed = float(self.rng.random() * 10)

        def shell(F, f, sec):
            g = 1 - (1 - min(1.0, f * 1.8)) ** 3
            F.mesh("air", self.sphere(c + [0, 0, f * 0.5], rr * (0.3 + 0.8 * g), 0, f, seed,
                                      squash=0.85), blend="alpha")
            F.mesh("air", self.sphere(c + [0, 0, f * 0.3], rr * (0.2 + 0.5 * g), 0, min(1.0, f * 1.3), seed + 3.1,
                                      squash=0.9, color=(1, 1, 1, 0.3)), blend="add")
        self.pil.add(1.2 if big else 1.0, shell)
        self.shock(b, R)
        self.flash(b, 1.3 * scale)
        if not wet:
            self.scorch(b, R, d, 0.4 if ground else 0.0)

    def cone(self, x, y, r, h, seed, k):
        n = 8
        a = np.linspace(0, math.tau, n, endpoint=False)
        base = np.stack([x + np.cos(a) * r, y + np.sin(a) * r * 0.7, np.zeros(n)], -1)
        tip = np.array([[x + math.sin(seed * 3 + self.pil.time * 3) * r * 0.4, y, h]])
        pts = np.concatenate([base, tip])
        faces = np.array([(i, (i + 1) % n, n) for i in range(n)])
        uv = np.concatenate([np.stack([np.arange(n) / n, np.zeros(n)], -1), [[0.5, 1.0]]])
        light = np.ones(n + 1)
        return self.tris(pts, faces, uv, 2, light, k, seed)

    def burning(self, F, cells):
        self.ground_heat(F, cells)
        parts = []
        for (cx, cy) in sorted(cells, key=lambda c: c[1]):
            for j in range(3):
                h = (cx * 7 + cy * 3 + j * 5) % 11 / 11
                parts.append(self.cone(cx + 0.25 + 0.25 * j, cy + 0.3 + 0.4 * h, 0.17,
                                       0.55 + 0.35 * math.sin(self.pil.time * 4 + h * 9), h * 7 + j, 1.0))
        if parts:
            F.mesh("air", np.concatenate(parts), blend="add")

    def unit_fire(self, F, u, rect):
        gx, gy = self.pil.view.ground_pos(u)
        parts = [self.cone(gx + ox, gy + 0.1, 0.1, 0.55 + 0.15 * math.sin(self.pil.time * 5 + j), u.id + j, 0.9)
                 for j, ox in enumerate((-0.15, 0.0, 0.15))]
        F.mesh("air", np.concatenate(parts), blend="add")

    def cloud(self, F, x, y, R, k):
        sx, sy, kk = P.project(x, y, 1.7)
        w = kk * P.BASE_PX * R * 2.6
        F.quad("air", 6, sx, sy, w, w * 0.6, p=(0, x, k, 0), color=(1, 1, 1, 0.95), blend="alpha")

    def crystal(self, x, y, h, r, seed, light_k=1.0):
        n = 6
        a = np.linspace(0, math.tau, n, endpoint=False) + seed
        lean = np.array([math.sin(seed * 5) * 0.2, math.cos(seed * 3) * 0.15])
        base = np.stack([x + np.cos(a) * r, y + np.sin(a) * r, np.zeros(n)], -1)
        mid = np.stack([x + np.cos(a) * r * 0.8 + lean[0] * h * 0.6, y + np.sin(a) * r * 0.8 + lean[1] * h * 0.6,
                        np.full(n, h * 0.7)], -1)
        tip = np.array([[x + lean[0] * h, y + lean[1] * h, h]])
        pts = np.concatenate([base, mid, tip])
        faces = []
        for i in range(n):
            j = (i + 1) % n
            faces += [(i, j, n + j), (i, n + j, n + i), (n + i, n + j, 2 * n)]
        faces = np.array(faces)
        normals = np.concatenate([np.stack([np.cos(a), np.sin(a), np.zeros(n)], -1)] * 2 + [[[0, 0, 1]]])
        light = np.clip(normals @ np.array([-0.5, 0.5, 0.7]), 0, 1) * light_k
        uv = np.stack([pts[:, 0], pts[:, 2]], -1)
        return self.tris(pts, faces, uv, 3, light, 0, seed, color=(0.45, 0.72, 0.98, 0.95))

    def squall(self, F, x, y, R, f, sec):
        sx, sy, k = P.project(x, y)
        w = k * P.BASE_PX * R * 2.2
        F.quad("air", 7, sx, sy - w * 0.25, w, w * 0.9, p=(f, x, 1 - f * 0.5, 0), blend="add")

    def frost(self, x, y, R):
        spikes = []
        for i in range(int(5 + 5 * R * R)):
            a, r = self.rng.uniform(0, math.tau), R * math.sqrt(self.rng.random())
            spikes.append((x + math.cos(a) * r, y + math.sin(a) * r, self.rng.uniform(0.35, 0.8) * (1.3 - r / R * 0.5),
                           self.rng.uniform(0.06, 0.12), float(self.rng.random() * 6), r))

        def grow(F, f, sec):
            parts = []
            for (cx, cy, h, r, seed, d) in sorted(spikes, key=lambda s: s[1]):
                g = min(1.0, max(0.0, (sec - d * 0.12) / 0.18))
                melt = min(1.0, max(0.0, (4.0 - sec) / 0.8))
                if g > 0:
                    parts.append(self.crystal(cx, cy, h * g * melt, r, seed))
            if parts:
                F.mesh("air", np.concatenate(parts), blend="alpha")
        self.pil.add(4.0, grow)
        sx, sy, k = P.project(x, y)
        w = k * P.BASE_PX * (R * 2.2 + 0.8)
        self.pil.add(0.6, lambda F, f, sec: F.quad("air", 5, sx, sy - w * 0.15, w * 0.8, w * 0.7, p=(f, y, 0, 0),
                                                     blend="add"))


# ---------- живая симуляция ----------

class FluidLook(Look):
    """Дым, огонь и морозный туман — сеткой жидкости в реальном времени (ui/fxlab/fluid.py)."""

    def __init__(self, pilot):
        super().__init__(pilot)
        from ui.fxlab.fluid import Fluid
        from ui import theme as T
        self.sim = Fluid(T.SCREEN_W, T.SCREEN_H)
        self.size = (T.SCREEN_W, T.SCREEN_H)
        self.sources = []

    def reset(self):
        self.sim.clear()

    def update(self, dt):
        for fn in self.sources:
            fn(dt)
        self.sources.clear()
        self.sim.step(dt, wind=1.0)

    def frame_extra(self, F):
        if self.sim.active > 0:
            F.texture("air", "fluid", self.sim.image(), (0, 0, *self.size), blend="alpha")

    def _splat(self, *a, **kw):
        self.sim.splat(*a, **kw)

    def projectile(self, F, kind, p, d, sec, scale):
        x, y, k = P.project(*p)
        r = k * P.BASE_PX * (0.28 if kind == "meteor" else 0.14) * scale
        self._splat(x, y, r * 1.2, heat=0.9, smoke=0.15)
        F.quad("air", 10, x, y, r * 4, r * 4, color=(1.0, 0.75, 0.4, 1), p=(0, 0, 1.6, 0), blend="add")

    def impact_fire(self, b, d, scale, R, ground, wet, big):
        x, y, k = P.project(b[0], b[1], 0.3 if ground else b[2])
        r = k * P.BASE_PX * (0.35 + 0.35 * R) * (1.3 if big else 1.0)
        for i in range(10):
            a = i / 10 * math.tau
            self._splat(x + math.cos(a) * r * 0.4, y + math.sin(a) * r * 0.3, r * 0.5, heat=0.55, smoke=0.5,
                        vx=math.cos(a) * 9, vy=math.sin(a) * 6 - 4)
        self._splat(x, y, r * 0.8, heat=0.6, smoke=0.3)
        self.shock(b, R)
        self.flash(b, 1.5 * scale)
        if not wet:
            self.scorch(b, R, d, 0.4 if ground else 0.0)

    def burning(self, F, cells):
        self.ground_heat(F, cells)
        for (cx, cy) in cells:
            for j in range(2):
                x, y, k = P.project(cx + 0.3 + 0.4 * j, cy + 0.5)
                self._splat(x, y - 6, k * P.BASE_PX * 0.13, heat=0.18, smoke=0.035)

    def unit_fire(self, F, u, rect):
        self._splat(rect.centerx, rect.y + rect.h * 0.6, rect.w * 0.25, heat=0.16, smoke=0.03)

    def cloud(self, F, x, y, R, k):
        if k <= 0.05:
            return
        sx, sy, kk = P.project(x, y, 1.7)
        w = kk * P.BASE_PX * R
        a = self.rng.uniform(0, math.tau)
        for _ in range(2):                    # туча — морозный туман закручивается над площадью
            a = self.rng.uniform(0, math.tau)
            self._splat(sx + math.cos(a) * w * 0.8, sy + math.sin(a) * w * 0.35, w * 0.45, cold=0.35 * k,
                        vx=-math.sin(a) * 6, vy=math.cos(a) * 3)

    def squall(self, F, x, y, R, f, sec):
        sx, sy, k = P.project(x, y)
        w = k * P.BASE_PX * R * 2.2
        F.quad("air", 7, sx, sy - w * 0.25, w, w * 0.9, p=(f, x, 1 - f * 0.5, 0), blend="add")
        for _ in range(3):
            a, r = self.rng.uniform(0, math.tau), R * math.sqrt(self.rng.random())
            px, py, kk = P.project(x + math.cos(a) * r, y + math.sin(a) * r)
            self._splat(px, py, kk * P.BASE_PX * 0.2, cold=0.3, vx=6, vy=3)

    def frost(self, x, y, R):
        sx, sy, k = P.project(x, y)
        r = k * P.BASE_PX * (0.4 + 0.4 * R)
        for i in range(12):
            a = i / 12 * math.tau
            self._splat(sx + math.cos(a) * r * 0.3, sy + math.sin(a) * r * 0.2, r * 0.5, cold=0.9,
                        vx=math.cos(a) * 10, vy=math.sin(a) * 5)
        w = k * P.BASE_PX * (R * 2.2 + 0.8)
        self.pil.add(0.6, lambda F, f, sec: F.quad("air", 5, sx, sy - w * 0.15, w * 0.8, w * 0.7, p=(f, y, 0, 0),
                                                     blend="add"))
