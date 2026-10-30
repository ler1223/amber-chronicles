"""Живая симуляция дыма и огня: «стабильная жидкость» (Stam) на сетке в пространстве экрана (numpy).

Сетка покрывает экран с шагом CELL пикселей. Поля: скорость (u, v), дым (d), жар (h), холод (c — снег и
морозный туман). Шаг: силы (жар всплывает, холод оседает, ветер) → адвекция по полю скорости → проекция
(несжимаемость, итерации Якоби) → завихрённость (клубы не расплываются) → остывание и рассеяние.
Рисуется картинкой RGBA: жар — цветом огня (свет), дым — тёмной прозрачностью, холод — белёсым туманом.
"""
import numpy as np

CELL = 6


class Fluid:
    def __init__(self, w, h):
        self.W, self.H = w // CELL, h // CELL
        sh = (self.H, self.W)
        self.u, self.v = np.zeros(sh, np.float32), np.zeros(sh, np.float32)
        self.d, self.h, self.c = np.zeros(sh, np.float32), np.zeros(sh, np.float32), np.zeros(sh, np.float32)
        self.Y, self.X = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
        self.active = 0.0

    def clear(self):
        for a in (self.u, self.v, self.d, self.h, self.c):
            a[:] = 0
        self.active = 0.0

    def splat(self, x, y, r, heat=0.0, smoke=0.0, cold=0.0, vx=0.0, vy=0.0):
        """Источник в точке экрана (x, y) радиусом r пикселей."""
        gx, gy, gr = x / CELL, y / CELL, max(1.0, r / CELL)
        x0, x1 = int(max(0, gx - gr * 2)), int(min(self.W, gx + gr * 2 + 1))
        y0, y1 = int(max(0, gy - gr * 2)), int(min(self.H, gy + gr * 2 + 1))
        if x0 >= x1 or y0 >= y1:
            return
        Y, X = self.Y[y0:y1, x0:x1], self.X[y0:y1, x0:x1]
        g = np.exp(-((X - gx) ** 2 + (Y - gy) ** 2) / (gr * gr))
        if heat:
            self.h[y0:y1, x0:x1] = np.minimum(2.0, self.h[y0:y1, x0:x1] + g * heat)
        if smoke:
            self.d[y0:y1, x0:x1] = np.minimum(2.0, self.d[y0:y1, x0:x1] + g * smoke)
        if cold:
            self.c[y0:y1, x0:x1] = np.minimum(2.0, self.c[y0:y1, x0:x1] + g * cold)
        if vx or vy:
            self.u[y0:y1, x0:x1] += g * vx / CELL
            self.v[y0:y1, x0:x1] += g * vy / CELL
        self.active = 3.0

    def _advect(self, f, dt):
        x = np.clip(self.X - self.u * dt, 0, self.W - 1.001)
        y = np.clip(self.Y - self.v * dt, 0, self.H - 1.001)
        x0, y0 = x.astype(np.int32), y.astype(np.int32)
        fx, fy = x - x0, y - y0
        return ((f[y0, x0] * (1 - fx) + f[y0, x0 + 1] * fx) * (1 - fy)
                + (f[y0 + 1, x0] * (1 - fx) + f[y0 + 1, x0 + 1] * fx) * fy)

    def step(self, dt, wind=0.0):
        if self.active <= 0:
            return
        self.active -= dt
        dt = min(dt, 1 / 30) * 30                         # шаг в кадрах 30 к/с
        u, v = self.u, self.v
        v -= (self.h * 0.55 - self.c * 0.015 - self.d * 0.02) * dt  # жар всплывает (вверх — минус y), холод стелется
        u += wind * self.c * 0.05 * dt
        # завихрённость: возвращает мелкие клубы, которые съедает численная вязкость
        curl = (np.roll(v, -1, 1) - np.roll(v, 1, 1) - np.roll(u, -1, 0) + np.roll(u, 1, 0)) * 0.5
        ac = np.abs(curl)
        gx = (np.roll(ac, -1, 1) - np.roll(ac, 1, 1)) * 0.5
        gy = (np.roll(ac, -1, 0) - np.roll(ac, 1, 0)) * 0.5
        ln = np.sqrt(gx * gx + gy * gy) + 1e-5
        eps = 0.35
        u += eps * (gy / ln) * curl * dt
        v -= eps * (gx / ln) * curl * dt
        self.u, self.v = self._advect(u, dt), self._advect(v, dt)
        u, v = self.u, self.v
        div = (np.roll(u, -1, 1) - np.roll(u, 1, 1) + np.roll(v, -1, 0) - np.roll(v, 1, 0)) * 0.5
        p = np.zeros_like(div)
        for _ in range(14):
            p = (np.roll(p, 1, 0) + np.roll(p, -1, 0) + np.roll(p, 1, 1) + np.roll(p, -1, 1) - div) * 0.25
        u -= (np.roll(p, -1, 1) - np.roll(p, 1, 1)) * 0.5
        v -= (np.roll(p, -1, 0) - np.roll(p, 1, 0)) * 0.5
        for a in (u, v):
            a[0, :] = a[-1, :] = 0
            a[:, 0] = a[:, -1] = 0
            a *= 0.995
        self.d = self._advect(self.d, dt) * (1 - 0.012 * dt)
        self.h = self._advect(self.h, dt) * (1 - 0.06 * dt)
        self.c = self._advect(self.c, dt) * (1 - 0.03 * dt)
        burn = np.minimum(self.h, 0.04 * dt)               # горячее коптит: жар превращается в дым
        self.d += burn * 0.6

    def image(self):
        """RGBA uint8: дым и туман — прозрачностью, жар — цветом огня (предумножено для смешивания «alpha»)."""
        h = np.clip(self.h, 0, 1.3)
        d = np.clip(self.d, 0, 1.0)
        c = np.clip(self.c, 0, 1.0)
        fire = np.stack([np.clip(h * 1.5, 0, 1), np.clip(h * 1.0 - 0.15, 0, 1) ** 1.4 * 0.85,
                         np.clip(h - 0.75, 0, 1) * 1.2], -1)
        fire *= np.clip(h * 1.2, 0, 0.9)[..., None]
        smoke_a = np.clip(d * 0.85, 0, 0.85)
        fog_a = np.clip(c * 0.8, 0, 0.8)
        a = 1 - (1 - smoke_a) * (1 - fog_a)
        rgb = (np.array([0.13, 0.11, 0.1]) * smoke_a[..., None] * (1 - fog_a[..., None])
               + np.array([0.86, 0.92, 1.0]) * fog_a[..., None] + fire)
        out = np.concatenate([np.clip(rgb, 0, 1), a[..., None]], -1)
        return (out * 255).astype(np.uint8)
