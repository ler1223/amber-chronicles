"""Пиксельные эффекты (art_style.md, «физика → пиксель»): запечённые кадры симуляторов ui/pixfx_sim.py и их
экземпляры в бою.

Пиксель эффекта = 2 экранных × масштаб глубины (как у фигурок), увеличение только «ближайшим соседом», 12 кадров
в секунду. Воздушные эффекты (пламя, взрывы, кристаллы) рисуются на слое юнитов в порядке глубины, наземные
(иней, подпалины) — на плоской карте земли. Яркие пиксели (два верхних цвета палитры) идут ещё и в слой свечения.
"""
import math
import random

import numpy as np
import pygame

from ui import pixfx_sim as S
from ui import projection as P

FPS = 12
PX = 2                 # экранных пикселей на пиксель эффекта (в масштабе глубины 1)
GROUND_PX = 2          # пикселей плоской карты на пиксель наземного эффекта (клетка 64 = 32 пикселя эффекта)
VARIANTS = 3           # вариантов зерна на эффект — чтобы соседние взрывы не повторялись

# имя → (симулятор(зерно) → кадры, петля)
RECIPES = {
    "flame": (lambda s: S.flame(14, 22, 8, s, width=0.3), True),
    "flamelet": (lambda s: S.flame(8, 12, 8, s, width=0.3, warm=16), True),  # огонёк на модельке горящего
    "flame_cell": (lambda s: S.flame(22, 30, 8, s), True),                 # горящая клетка
    "flame_pillar": (lambda s: S.flame(26, 44, 10, s, strength=0.85, width=0.24), False),
    "orb": (lambda s: S.orb(14, 6, s), True),
    "core": (lambda s: S.core(9, 4, s), True),                               # голова огненного снаряда
    "core_big": (lambda s: S.core(17, 4, s), True),                          # метеор
    "orb_big": (lambda s: S.orb(24, 6, s), True),
    "ember": (lambda s: S.cloud(12, 5, s, pal="fire", rise=0.8), False),   # клуб жара за снарядом
    "spark": (lambda s: S.blast(22, 6, s, smoke=False), False),            # попадание огнём
    "blast_s": (lambda s: S.blast(36, 8, s), False),
    "blast_m": (lambda s: S.blast(60, 10, s), False),
    "blast_l": (lambda s: S.blast(92, 12, s), False),
    "scorch": (lambda s: [S.scorch(30, s)], False),
    "scorch_big": (lambda s: [S.scorch(54, s)], False),
    "shard": (lambda s: S.shard(14, 6), True),
    "chip": (lambda s: S.shatter(22, 6, s), False),                        # попадание льдом
    "shatter": (lambda s: S.shatter(44, 8, s), False),
    "bloom_s": (lambda s: S.ice_bloom(30, 7, s), False),
    "bloom_m": (lambda s: S.ice_bloom(56, 9, s), False),
    "bloom_l": (lambda s: S.ice_bloom(84, 10, s), False),
    "spikes": (lambda s: S.spikes(30, 30, 10, s, count=4), False),
    "spikes_big": (lambda s: S.spikes(40, 44, 12, s, count=5), False),
    "crust": (lambda s: S.crust(24, 34, 6, s), True),
    "ice_core": (lambda s: S.crust(14, 18, 6, s), True),                   # кристалл копится над головой при касте
    "frost": (lambda s: [S.frost(32, s)], False),
    "steam": (lambda s: S.cloud(40, 9, s), False),
    "smoke": (lambda s: S.cloud(36, 9, s, pal="dust", rise=0.6), False),
}

# яркие цвета (два верхних каждой палитры) — источник свечения
_GLOW = np.array([r << 16 | g << 8 | b for pal in S.PAL.values() for (r, g, b) in pal[4:]], np.int64)


def _surfaces(rgba):
    """Кадр RGBA → (картинка, только яркие пиксели или None)."""
    h, w = rgba.shape[:2]
    a = np.ascontiguousarray(rgba)
    img = pygame.image.frombuffer(a.tobytes(), (w, h), "RGBA").copy()
    packed = a[..., 0].astype(np.int64) << 16 | a[..., 1].astype(np.int64) << 8 | a[..., 2]
    mask = np.isin(packed, _GLOW) & (a[..., 3] > 0)
    if not mask.any():
        return img, None
    g = np.where(mask[..., None], a, 0).astype(np.uint8)
    return img, pygame.image.frombuffer(np.ascontiguousarray(g).tobytes(), (w, h), "RGBA").copy()


class Lib:
    """Запечённые кадры (по VARIANTS вариантов зерна) и их увеличенные копии."""

    def __init__(self):
        self.frames = {}
        self.cache = {}

    def get(self, name, var=0):
        key = (name, var % VARIANTS)
        fr = self.frames.get(key)
        if fr is None:
            fr = self.frames[key] = [_surfaces(a) for a in RECIPES[name][0](17 + 31 * key[1])]
        return fr

    def loop(self, name):
        return RECIPES[name][1]

    def count(self, name):
        return len(self.get(name))

    def warm(self, names=None):
        for n in names or RECIPES:
            for v in range(VARIANTS):
                self.get(n, v)

    def img(self, name, var, i, scale, glow=False, rot=0, flip=False):
        """Кадр i, увеличенный в scale раз (ступени 0.25 — пиксели остаются чёткими), повёрнутый на rot·45°."""
        q = max(1.0, round(scale * 4) / 4)
        key = (name, var % VARIANTS, i, q, glow, rot % 8, flip)
        out = self.cache.get(key)
        if out is None:
            src = self.get(name, var)[i][1 if glow else 0]
            if src is None:
                return None
            if flip:
                src = pygame.transform.flip(src, True, False)
            if rot % 8:                    # поворот в малом разрешении: ступени пикселей сохраняются
                src = pygame.transform.rotate(src, -45 * (rot % 8))
            w, h = src.get_size()
            out = pygame.transform.scale(src, (max(1, round(w * q)), max(1, round(h * q))))
            if len(self.cache) > 4000:
                self.cache.clear()
            self.cache[key] = out
        return out


class Fx:
    """Экземпляр: кадры name играют с 12 к/с. pos — экранная точка или функция; depth — экранная y точки земли
    (по ней порядок отрисовки и масштаб), anchor — 'center' или 'bottom'. fade — за сколько секунд до конца
    начинает таять."""

    def __init__(self, name, pos, var=0, ttl=None, alive=None, anchor="center", depth=None, scale=1.0, alpha=255,
                 flip=False, rot=0, ground=False, path=None, fps=FPS, fade=0.0):
        self.fade = fade
        self.name, self.pos, self.var, self.anchor = name, pos, var, anchor
        self.depth, self.scale, self.alpha, self.flip, self.rot = depth, scale, alpha, flip, rot
        self.ttl, self.alive_fn, self.ground, self.path, self.fps = ttl, alive, ground, path, fps
        self.age = 0.0

    def point(self):
        if self.path is not None:
            a, b, dur, arc = self.path
            t = min(1.0, self.age / dur)
            return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t - math.sin(math.pi * t) * arc
        return self.pos() if callable(self.pos) else self.pos

    def opacity(self):
        if self.fade and self.ttl is not None:
            return int(self.alpha * max(0.0, min(1.0, (self.ttl - self.age) / self.fade)))
        return self.alpha

    def ground_y(self):
        if self.depth is None:
            return self.point()[1]
        return self.depth() if callable(self.depth) else self.depth


class PixFx:
    def __init__(self):
        self.lib = Lib()
        self.items = []
        self.time = 0.0
        self.rng = random.Random(11)

    def clear(self):
        self.items.clear()

    def var(self):
        return self.rng.randrange(VARIANTS)

    def add(self, name, pos, delay=0.0, **kw):
        """Эффект в точке экрана (или на плоской карте при ground=True). delay — запуск позже."""
        kw.setdefault("var", self.var())
        fx = Fx(name, pos, **kw)
        if fx.ttl is None and not self.lib.loop(name):
            fx.ttl = self.lib.count(name) / fx.fps
        fx.age = -delay
        self.items.append(fx)
        return fx

    def add_surface(self, img, flat_pos, ttl, fade=2.0, alpha=255):
        """Готовая картинка на плоской карте (морозный след): живёт ttl секунд, последние fade — тает."""
        fx = Fx("_surface", flat_pos, ttl=ttl, ground=True, fade=fade, alpha=alpha)
        fx.img = img
        self.items.append(fx)
        return fx

    def projectile(self, name, a, b, speed=650.0, arc=0.0, dur=None, scale=1.0, trail=None, orient=False):
        """Снаряд a → b (экранные точки): сама форма покадровая, движение плавное. Возвращает экземпляр
        (fx.ttl — время полёта)."""
        d = math.dist(a, b)
        dur = dur or max(0.08, d / speed)
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        rot = round(ang / (math.pi / 4)) % 8 if orient else 0
        flip = not orient and b[0] < a[0]
        fx = self.add(name, a, ttl=dur, path=(a, b, dur, arc), scale=scale, rot=rot, flip=flip,
                      depth=lambda: b[1] if fx.age >= dur * 0.5 else a[1])
        fx.trail = trail
        fx.trail_acc = 0.0
        return fx

    def update(self, dt):
        if dt <= 0:
            return
        self.time += dt
        keep = []
        for fx in self.items:
            fx.age += dt
            if fx.age >= 0 and getattr(fx, "trail", None):
                fx.trail_acc += dt
                while fx.trail_acc > 1 / 30:
                    fx.trail_acc -= 1 / 30
                    x, y = fx.point()
                    self.add(fx.trail, (x + self.rng.uniform(-3, 3), y + self.rng.uniform(-3, 3)), scale=fx.scale,
                             depth=fx.ground_y())
            if fx.alive_fn is not None and not fx.alive_fn():
                continue
            if fx.ttl is not None and fx.age >= fx.ttl:
                continue
            keep.append(fx)
        self.items = keep

    def frame(self, fx):
        n = self.lib.count(fx.name)
        i = int(max(0.0, fx.age) * fx.fps)
        return i % n if self.lib.loop(fx.name) else min(i, n - 1)

    # ---------- отрисовка ----------

    def air(self):
        return [fx for fx in self.items if not fx.ground and fx.age >= 0]

    def blit(self, surf, glow, name, var, i, x, y, scale, anchor="center", alpha=255, flip=False, rot=0):
        """Один кадр в точке (x, y) экрана; scale — масштаб глубины. glow — слой свечения (или None)."""
        k = PX * scale
        img = self.lib.img(name, var, i, k, rot=rot, flip=flip)
        w, h = img.get_size()
        pos = (round(x - w / 2), round(y - h)) if anchor == "bottom" else (round(x - w / 2), round(y - h / 2))
        if alpha < 255:
            img.set_alpha(alpha)
            surf.blit(img, pos)
            img.set_alpha(255)
        else:
            surf.blit(img, pos)
        if glow is not None:
            g = self.lib.img(name, var, i, k, glow=True, rot=rot, flip=flip)
            if g is not None:
                glow.blit(g, pos)
        return pygame.Rect(pos, (w, h))

    def draw(self, surf, glow, fx, dim=1.0):
        x, y = fx.point()
        gy = fx.ground_y()
        g = P.unproject(x, gy)
        k = (P.scale_at(g[1]) if g is not None else 1.0) * fx.scale
        return self.blit(surf, glow, fx.name, fx.var, self.frame(fx), x, y, k, fx.anchor, int(fx.opacity() * dim),
                         fx.flip, fx.rot)

    def draw_ground(self, flat):
        """Наземные эффекты на плоской карте (pos — точка плоской карты)."""
        for fx in self.items:
            if fx.ground and fx.age >= 0:
                img = getattr(fx, "img", None) or self.lib.img(fx.name, fx.var, self.frame(fx), GROUND_PX * fx.scale)
                x, y = fx.point()
                a = fx.opacity()
                if a < 255:
                    img.set_alpha(a)
                flat.blit(img, (round(x - img.get_width() / 2), round(y - img.get_height() / 2)))
                img.set_alpha(255)

    def ground_img(self, name, var, scale=1.0):
        """Неподвижный наземный кадр (иней на клетке, подпалина) для плоской карты."""
        return self.lib.img(name, var, 0, GROUND_PX * scale)


def family(sk):
    """Стихия навыка для пиксельного пилота: 'fire', 'ice' или None (смотрит на эффекты, а не на название)."""
    if not sk:
        return None
    fire = ice = 0
    for e in sk.get("effects", []):
        t, tag = e.get("type"), e.get("tag")
        if tag == "fire" and t in ("damage", "cell_tag", "status") or e.get("hazard") == "fire" \
                or t in ("detonate", "spread_fire") or e.get("terrain") == "lava":
            fire += 1
        if tag == "ice" and t in ("damage", "cell_tag", "status", "shatter") or e.get("hazard") == "ice" \
                or t == "wall" or e.get("terrain") == "ice_floor":
            ice += 1
    if fire or ice:
        return "fire" if fire >= ice else "ice"
    return None
