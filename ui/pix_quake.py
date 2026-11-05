"""Разлом земли и волна по жидкости — преломлением самой земли поля (работает на любом рельефе).

Разлом (Прыжок драгуна, усиленный Мощный удар): вокруг точки удара земля бьётся на плиты. Каждая плита — это та же
земля плоской карты (трава, камень, песок, снег — что угодно), сдвинутая и наклонённая: пиксели берутся со
смещением, освещение плиты — по её наклону, на освещённом краю — светлая кромка, между плитами — тёмные щели,
в центре — провал. От плит расходятся тонкие трещины. Плиты вздымаются за 0.15 с, держатся и оседают.
Вода и лава не трескаются: по ним расходятся кольца ряби (смещение пикселей по радиусу + блик на гребне);
на лаве гребень ярче и медленнее. Пропасть не трогаем.

Считается на плоской карте (numpy) раз в кадр, поэтому одинаково выглядит и с видеокартой, и без неё.
Сетка эффекта — пиксель арта (2 пикселя плоской карты), как у всего пиксельного стиля.
"""
import math

import numpy as np
import pygame

from ui import projection as P

LIQUID = ("water", "lava", "swamp_water", "deep_water")
NO_EFFECT = ("chasm",)
RISE, SETTLE = 0.15, 1.0
LIGHT = np.array([-0.55, -0.75])            # свет сверху-слева (на плоской карте)
LIGHT = LIGHT / np.linalg.norm(LIGHT)


STYLES = ("ring", "shards", "slabs", "double", "furrow", "wedge")


def _sites(style, R, rng, dirv):
    """Центры плит и их наклон для вида разлома. Возвращает (sx, sy, угол наружу, наклон, провал, рваность края).
    ring — кольцо 7–9 плит; shards — много мелких осколков; slabs — 4–5 крупных плит; double — два кольца
    (внутренние выше); furrow — борозда вдоль удара; wedge — плиты веером вперёд, позади — мелкие осколки.
    Внутри каждого вида всё случайно: число плит, углы, радиусы, наклоны, форма края, трещины."""
    if style == "shards":
        k = int(rng.integers(13, 19))
        rad = R * np.sqrt(rng.uniform(0.06, 0.85, k))
        ang = rng.uniform(0, math.tau, k)
        tilt = rng.uniform(0.35, 0.9, k)
        hole, jag = 0.12, 0.22
    elif style == "slabs":
        k = int(rng.integers(4, 6))
        ang = np.sort(rng.uniform(0, math.tau, k)) + rng.uniform(-0.3, 0.3, k)
        rad = R * rng.uniform(0.45, 0.62, k)
        tilt = rng.uniform(0.85, 1.25, k)
        hole, jag = 0.22, 0.12
    elif style == "double":
        k1, k2 = int(rng.integers(5, 7)), int(rng.integers(8, 11))
        ang = np.r_[np.sort(rng.uniform(0, math.tau, k1)), np.sort(rng.uniform(0, math.tau, k2))]
        rad = np.r_[R * rng.uniform(0.28, 0.4, k1), R * rng.uniform(0.66, 0.82, k2)]
        tilt = np.r_[rng.uniform(0.9, 1.2, k1), rng.uniform(0.4, 0.7, k2)]
        hole, jag = 0.14, 0.16
    elif style == "furrow":
        base = math.atan2(dirv[1], dirv[0]) if dirv is not None else rng.uniform(0, math.tau)
        k = int(rng.integers(6, 9))
        side = np.where(np.arange(k) % 2 == 0, 1.0, -1.0)
        t = np.linspace(-0.9, 0.9, k) + rng.uniform(-0.1, 0.1, k)
        px = math.cos(base) * t * R - math.sin(base) * side * R * 0.32
        py = math.sin(base) * t * R + math.cos(base) * side * R * 0.32
        ang = np.arctan2(py, px)
        rad = np.hypot(px, py)
        tilt = rng.uniform(0.7, 1.1, k)
        hole, jag = 0.1, 0.1
    elif style == "wedge":
        base = math.atan2(dirv[1], dirv[0]) if dirv is not None else rng.uniform(0, math.tau)
        k = int(rng.integers(6, 9))
        back = int(rng.integers(3, 6))
        ang = np.r_[base + np.linspace(-1.1, 1.1, k) + rng.uniform(-0.12, 0.12, k),
                    base + math.pi + rng.uniform(-0.9, 0.9, back)]
        rad = np.r_[R * rng.uniform(0.45, 0.75, k), R * rng.uniform(0.25, 0.55, back)]
        tilt = np.r_[rng.uniform(0.8, 1.2, k), rng.uniform(0.25, 0.5, back)]
        hole, jag = 0.15, 0.18
    else:
        k = int(rng.integers(7, 10))
        ang = np.sort(rng.uniform(0, math.tau, k)) + rng.uniform(-0.2, 0.2, k)
        rad = R * rng.uniform(0.38, 0.72, k)
        tilt = rng.uniform(0.6, 1.0, k)
        hole, jag = 0.17, 0.18
    return np.cos(ang) * rad, np.sin(ang) * rad, ang, tilt, hole, jag


class Quake:
    def __init__(self, cx, cy, R, terrain_at, seed=0, life=4.0, ripple_r=3.0, style=None, dirv=None,
                 ripple_all=False):
        """cx, cy — точка удара (клетки), R — радиус плит (клетки; 0 — только рябь). style — вид (STYLES; по умолчанию случайный),
        dirv — направление удара (для «борозды» и «клина»)."""
        self.t = 0.0
        self.life = life
        plates = R > 0
        R = max(R, 0.3)
        rng = np.random.default_rng(seed)
        F = P.FLAT
        ext = max(R * 1.8, ripple_r) + 0.3
        half = int(math.ceil(ext * F / 2)) * 2
        self.half = half
        fx, fy = P.ground_to_flat(cx, cy)
        self.x0, self.y0 = int(fx) - half, int(fy) - half
        n = half                                  # сетка арта: шаг 2 пикселя плоской карты
        ys, xs = np.mgrid[0:n, 0:n]
        gx = cx + (xs * 2 + 1 - half) / F
        gy = cy + (ys * 2 + 1 - half) / F
        dx, dy = gx - cx, gy - cy
        d = np.hypot(dx, dy)
        theta = np.arctan2(dy, dx)
        ter = terrain_at(gx.ravel(), gy.ravel()).reshape(n, n)
        liquid = np.isin(ter, LIQUID)
        solid = ~liquid & ~np.isin(ter, NO_EFFECT)
        self.lava = (ter == "lava")
        # ---- плиты: ближайший центр (Вороной), центры кольцом вокруг удара ----
        style = style or STYLES[int(rng.integers(len(STYLES)))]
        self.style = style
        sx, sy, ang, tilt, hole_r, jag_k = _sites(style, R, rng, dirv)
        k = len(sx)
        dist = np.hypot(dx[..., None] - sx, dy[..., None] - sy)          # [n, n, k]
        order = np.argsort(dist, axis=-1)
        i1 = order[..., 0]
        d1 = np.take_along_axis(dist, order[..., :1], -1)[..., 0]
        d2 = np.take_along_axis(dist, order[..., 1:2], -1)[..., 0]
        f1, f2 = rng.integers(3, 8, 2)
        jag = 0.86 + jag_k * np.sin(theta * f1 + rng.uniform(0, 6)) * np.sin(theta * f2 + rng.uniform(0, 6))
        if style == "furrow":                          # борозда: вытянута вдоль удара
            b = math.atan2(dirv[1], dirv[0]) if dirv is not None else 0.0
            al = dx * math.cos(b) + dy * math.sin(b)
            ac = -dx * math.sin(b) + dy * math.cos(b)
            de = np.hypot(al / 1.45, ac / 0.62)
        else:
            de = d
        inside = (de < R * jag) & solid & plates
        hole = (de < R * hole_r) & plates
        gap_w = R * (0.014 + 0.01 * rng.random()) * (1.3 - d / (R * 1.2)).clip(0.5, 1.3)
        gap = inside & (d2 - d1 < gap_w)
        # наклон плиты: поднята у внутреннего края (к удару), уходит в землю наружу
        ux, uy = np.cos(ang), np.sin(ang)                             # наружу от центра, по плите
        along = (dx * ux[i1] + dy * uy[i1]) / R                         # 0 у центра → ~1 у края
        height = np.clip(1.0 - along, 0, 1) * tilt[i1] * inside         # высота плиты в точке
        # высота в пикселях сетки арта: поднятый край плиты на экране уходит вверх, под ним — боковая грань
        self.h = (height * 0.5 * F / 2).astype(np.float32)
        self.hmax = int(np.ceil(self.h.max())) + 1
        # освещение плиты: нормаль наклонена к центру; кромка у щели на освещённой стороне — светлее
        nx, ny = -ux[i1], -uy[i1]
        lit = nx * LIGHT[0] + ny * LIGHT[1]
        shade = 1.0 + 0.5 * lit * tilt[i1]
        rim = inside & ~gap & (d2 - d1 < gap_w * 2.3) & (lit > 0)
        shade = np.where(rim, shade + 0.4, shade)
        shade = np.where(inside, shade * (1.0 - 0.18 * np.clip(along - 0.7, 0, 1)), 1.0)
        self.shade = shade.astype(np.float32)
        self.inside = inside & ~gap & ~hole
        self.gap = (gap | hole) & solid
        # ---- тонкие трещины от плит наружу ----
        rays = int(rng.integers(6, 16))
        ra = rng.uniform(0, math.tau, rays)
        rl = R * rng.uniform(1.25, 1.75, rays)
        wob = rng.uniform(0, 6, rays)
        crack = np.zeros((n, n), bool)
        for a, L, w in zip(ra, rl, wob):
            aa = a + 0.18 * np.sin(d * 6 + w) + 0.06 * np.sin(d * 17 + w * 2)
            diff = np.angle(np.exp(1j * (theta - aa)))
            width = 0.012 * (1.0 - np.clip((d - R) / (L - R + 1e-6), 0, 1)) + 0.004
            crack |= (np.abs(diff) * d < width) & (d > R * 0.8) & (d < L)
        self.crack = crack & solid & ~inside & ~self.gap & plates
        # ---- рябь по жидкости ----
        self.liquid = (liquid | (solid if ripple_all else False)) & (d < ripple_r)   # святая вода: рябь везде
        self.d = d.astype(np.float32)
        with np.errstate(invalid="ignore", divide="ignore"):
            self.ux = np.where(d > 1e-4, dx / np.maximum(d, 1e-4), 0).astype(np.float32)
            self.uy = np.where(d > 1e-4, dy / np.maximum(d, 1e-4), 0).astype(np.float32)
        self.any_solid = bool(self.inside.any() or self.gap.any())

    @property
    def done(self):
        return self.t > max(self.life, 1.6)

    def update(self, dt):
        self.t += dt

    def draw(self, flat):
        """Преломить землю плоской карты на месте (flat — Surface плоской карты)."""
        W, H = flat.get_size()
        half = self.half
        x0, y0 = self.x0, self.y0
        if x0 < 0 or y0 < 0 or x0 + half * 2 > W or y0 + half * 2 > H:
            return
        arr = pygame.surfarray.pixels3d(flat)
        reg = arr[x0:x0 + half * 2, y0:y0 + half * 2].transpose(1, 0, 2)    # [y, x, 3], вид на flat
        src = reg[::2, ::2].astype(np.float32)                              # сетка арта
        n = half
        out = src.copy()
        touched = np.zeros((n, n), bool)
        t = self.t
        if self.any_solid and t < self.life:
            k = min(1.0, t / RISE)
            k = k * k * (3 - 2 * k)
            k *= min(1.0, (self.life - t) / SETTLE)
            gcol = np.array([18, 14, 12], np.float32)
            g = self.gap
            out[g] = out[g] * (1 - 0.92 * k) + gcol * 0.92 * k
            c = self.crack
            out[c] = out[c] * (1 - 0.7 * k) + gcol * 0.7 * k
            # карта высот: точка q плиты поднята на h(q) и видна в p = q - (0, h); ищем самую близкую к камере
            # (большее смещение s). Ровно на высоте — верх плиты, ниже — её боковая грань (земля в разрезе)
            h = self.h * k
            top = np.zeros((n, n), bool)
            side = np.zeros((n, n), bool)
            qy = np.zeros((n, n), int)
            ys = np.arange(n)[:, None]
            for sft in range(self.hmax, -1, -1):
                q = ys + sft
                ok = q < n
                hq = np.zeros((n, n), np.float32)
                hq[:n - sft] = h[sft:]
                ins = np.zeros((n, n), bool)
                ins[:n - sft] = self.inside[sft:]
                nxt = np.zeros((n, n), bool)            # плита продолжается к камере — значит это ещё её верх
                nxt[:n - sft - 1] = self.inside[sft + 1:]
                hit = ins & (hq >= sft) & ~(top | side) & ok
                is_top = hit & ((hq - sft < 1.0) | nxt)
                top |= is_top
                side |= hit & ~is_top
                qy = np.where(hit, q, qy)
            xs = np.arange(n)[None, :].repeat(n, 0)
            qy = np.clip(qy, 0, n - 1)
            seen = src[qy, xs]
            sh = (1 + (self.shade - 1) * k)[qy, xs]
            mt = top
            out[mt] = (seen * sh[..., None])[mt]
            wall = seen * 0.5 + np.array([40, 30, 22], np.float32) * 0.5          # разрез: земля темнее, бурее
            out[side] = (wall * 0.75)[side]
            under = self.inside & ~(top | side)                                     # плита ушла — видна щель
            out[under] = out[under] * 0.35 + gcol * 0.65
            touched |= top | side | under | g | c
        if t < 1.5 and self.liquid.any():                 # кольца ряби
            disp = np.zeros((n, n), np.float32)
            crest = np.zeros((n, n), np.float32)
            for j in range(3):
                speed = np.where(self.lava, 1.5, 2.6)
                r = speed * max(0.0, t - j * 0.16)
                band = np.exp(-((self.d - r) / 0.13) ** 2)
                amp = 0.6 * max(0.0, 1 - t / 1.5) * (1 - 0.25 * j)
                disp += np.sin((self.d - r) * 30) * band * amp
                crest += band * amp
            disp *= self.liquid
            crest *= self.liquid
            ys, xs = np.mgrid[0:n, 0:n]
            s = 0.11 * P.FLAT / 2
            sxp = np.clip(np.round(xs - self.ux * disp * s).astype(int), 0, n - 1)
            syp = np.clip(np.round(ys - self.uy * disp * s).astype(int), 0, n - 1)
            m = self.liquid & (crest > 0.02)
            rip = src[syp, sxp]
            glow = np.where(self.lava[..., None], np.array([255, 170, 60], np.float32),
                            np.array([230, 245, 255], np.float32))
            hi = np.clip(crest * 0.55, 0, 0.6)[..., None]
            rip = rip * (1 - hi) + glow * hi
            out[m] = rip[m]
            touched |= m
        if touched.any():
            big = np.repeat(np.repeat(out, 2, 0), 2, 1)
            tm = np.repeat(np.repeat(touched, 2, 0), 2, 1)
            reg[tm] = np.clip(big[tm], 0, 255).astype(np.uint8)
        del arr, reg
