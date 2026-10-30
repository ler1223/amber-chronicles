"""Движок визуальных эффектов: частицы (numpy), декали, модельки предметов, ленты-следы, шейдерные эффекты,
свет, искажение, следы на поле, камера. Таймлайны и привязка к навыкам — в данных.

Данные: data/fx.json — пресеты частиц, data/vfx.json — эффекты (слои по времени), заготовки шейдерных
эффектов/лент/света и привязка к навыкам. Отрисовка: batches() и др. → GPU (ui/gl_renderer.py) или draw_cpu() —
упрощённо, без шейдеров. Время — игровое: на паузе всё замирает вместе с боем; стоп-кадр и замедление считаются
в реальном времени (real_update).

Пресет частиц (fx.json):
  shape — форма из ui/vfx_textures.NAMES или флипбук (fb_*: кадры по жизни частицы, "fps" — зациклить);
  blend "add" (свет) | "alpha" (дым, капли); under — под юнитами (круги, волны по земле);
  count, speed [от, до], angle (0 — вправо, -90 — вверх), spread, radial (от центра) / converge (к центру);
  life [от, до], size [в начале, в конце] — диаметр в px, jitter — разброс размера;
  colors [в начале, в конце]: [r,g,b] | "tag" | "tag_light" | "tag_dark" | "white"; alpha [в начале, в конце];
  hdr — яркость сверх 1 (питает свечение); fadein — доля жизни на появление;
  gravity, drag, floor (земля на столько px ниже точки выпуска) + bounce (отскок 0..1);
  spawn (радиус), spawn_shape "disc"|"ring"|"line"|"column", ground (сплющено как земля в 3/4);
  aspect (вытянутость), stretch (по скорости), orient (поворот по скорости), rot, spin (град/с).
"""
import json
import math
import os
import random

import numpy as np

from ui.projection import GROUND_YS  # круги на земле сплющены так же, как земля под камерой
from ui.settings import SETTINGS
from ui.vfx_textures import FLIP, FRAMES, INDEX

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CAP = 40000
FLOATS = 14     # частица: x, y, w, h, rot, yscale, r, g, b, a, u0, v0, u1, v1
SFX_FLOATS = 16     # шейдерный эффект: x, y, w, h, rot, yscale, r, g, b, a, t, seed, mode, extra, age, pad
RIB_FLOATS = 12     # вершина ленты: x, y, u, v, r, g, b, a, mode, seed, length, age
SFX_MODES = {"ring": 0, "vortex": 1, "pillar": 2, "orb": 3, "dome": 4, "disc": 5, "cracks": 6, "aura": 7,
             "wave": 8, "fireorb": 9, "rays": 10, "spikes": 11,
             "d_ring": 20, "d_haze": 21, "d_pinch": 22}
RIB_MODES = {"energy": 0, "slash": 1, "smoke": 2, "fire": 3, "water": 4, "lightning": 5}
GROUPS = ("under_alpha", "under_add", "air_alpha", "air_add")


def _load(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def resolve_color(spec, tag):
    tag = tuple(tag) if tag is not None and not isinstance(tag, str) else (255, 255, 255)
    if spec == "tag":
        c = tag
    elif spec == "tag_light":
        c = tuple(t + (255 - t) * 0.55 for t in tag)
    elif spec == "tag_dark":
        c = tuple(t * 0.35 for t in tag)
    elif spec == "white" or spec is None:
        c = (255, 255, 255)
    else:
        c = spec
    return np.array(c, np.float32) / 255.0


def _rng_val(v, prng):
    return prng.uniform(*v) if isinstance(v, (list, tuple)) else v


def _ease_out(t):
    return 1 - (1 - t) ** 3


def _point(p):
    return p() if callable(p) else p


class Decal:
    """Одиночный спрайт с жизнью: магический круг, луч, купол щита. pos — точка или функция (следует за юнитом)."""

    def __init__(self, shape, pos, size, color, life=None, alive=None, alpha=(1.0, 0.0), grow=(1.0, 1.0),
                 spin=0.0, rot=0.0, ground=False, aspect=1.0, hdr=1.0, fade=0.15, pulse=0.0, add=True, under=False):
        self.shape = INDEX[shape]
        self.pos, self.size, self.color = pos, size, color
        self.life, self.alive_fn = life, alive
        self.alpha, self.grow = alpha, grow
        self.spin, self.rot = math.radians(spin), math.radians(rot)
        self.yscale = 0.5 if ground else 1.0
        self.aspect, self.hdr, self.fade, self.pulse, self.add = aspect, hdr, fade, pulse, add
        self.under = under
        self.age = 0.0
        self.dying = None      # когда alive() стал ложным — плавно гаснем

    def point(self):
        return _point(self.pos)


class Emitter:
    """Непрерывный источник: следует за точкой (функция) или летит снарядом a → b."""

    def __init__(self, preset, rate, pos, color, scale=1.0, duration=None, alive=None, on_end=None, angle=None):
        self.preset, self.rate, self.pos, self.color, self.scale = preset, rate, pos, color, scale
        self.angle = angle
        self.duration, self.alive_fn, self.on_end = duration, alive, on_end
        self.age, self.acc = 0.0, 0.0


class Prop:
    """Моделька предмета: летит по дуге a → b (path) или свободно (скорость, гравитация, отскок от земли)."""

    def __init__(self, idx, name, x, y, scale=2.0, rot=0.0, vx=0.0, vy=0.0, g=0.0, spin=0.0, orient=False,
                 life=2.0, floor=None, bounce=0.0, stick=False, path=None, on_end=None, alive=None, follow=None,
                 grow=(1.0, 1.0), grow_time=0.15, fade=0.25, flip=False):
        self.idx, self.name = idx, name
        self.x, self.y, self.vx, self.vy, self.g = x, y, vx, vy, g
        self.rot, self.spin, self.orient = rot, spin, orient
        self.scale, self.grow, self.grow_time = scale, grow, grow_time
        self.life, self.floor, self.bounce, self.stick = life, floor, bounce, stick
        self.path, self.on_end, self.alive_fn, self.follow = path, on_end, alive, follow
        self.fade, self.flip = fade, flip
        self.age = 0.0
        self.rest = None           # время, когда улеглась
        self.dying = None
        self.done = False


class Sfx:
    """Шейдерный эффект — квад, который рисует фрагментный шейдер по режиму (волна, вихрь, столп, сфера...)."""

    def __init__(self, mode, pos, size, color, life=None, alive=None, alpha=(1.0, 0.0), grow=(1.0, 1.0),
                 rot=0.0, spin=0.0, ys=1.0, hdr=1.0, add=True, under=False, seed=0.0, extra=0.0, fade=0.15,
                 aspect=1.0, distort=False, fadein=0.0):
        self.mode = SFX_MODES[mode]
        self.pos, self.size, self.color = pos, size, color
        self.life, self.alive_fn = life, alive
        self.alpha, self.grow = alpha, grow
        self.rot, self.spin = math.radians(rot), math.radians(spin)
        self.ys, self.hdr, self.add, self.under = ys, hdr, add, under
        self.seed, self.extra, self.fade, self.aspect = seed, extra, fade, aspect
        self.distort = distort or self.mode >= 20
        self.fadein = fadein
        self.age = 0.0
        self.dying = None


class Ribbon:
    """Лента-след: точки пути источника за последние life секунд → полоса треугольников с текстурой по длине.
    src(t) — позиция в момент t от начала; источник «пишет» duration секунд (или пока alive())."""

    STEP = 1 / 240

    def __init__(self, src, life, width, color, hdr=1.5, mode=0, seed=0.0, duration=None, alive=None, add=True,
                 taper=1.0, under=False):
        self.src, self.life, self.width, self.color, self.hdr = src, life, width, color, hdr
        self.mode, self.seed, self.duration, self.alive_fn = mode, seed, duration, alive
        self.add, self.taper, self.under = add, taper, under
        self.pts = []
        self.age = 0.0
        self.last = 0.0
        self.stopped = None
        self.static = False        # молния: точки заданы сразу и гаснут вместе

    def writing(self):
        return self.stopped is None


class Light:
    """Точечный свет: подсвечивает землю и юнитов (не частицы). pos — точка или функция."""

    def __init__(self, pos, color, radius, intensity=1.0, life=None, alive=None, flicker=0.0, fadein=0.05,
                 curve=1.5, fade=0.2):
        self.pos, self.color, self.radius, self.intensity = pos, color, radius, intensity
        self.life, self.alive_fn, self.flicker = life, alive, flicker
        self.fadein, self.curve, self.fade = fadein, curve, fade
        self.age = 0.0
        self.dying = None
        self.seed = random.random() * 100


class Screen:
    """Экранные эффекты и камера. Стоп-кадр и замедление — в реальном времени, остальное — в игровом."""

    def __init__(self):
        self.shake = 0.0
        self.offset = (0.0, 0.0)
        self.flash = 0.0
        self.flash_color = (1.0, 1.0, 1.0)
        self.flash_decay = 4.0
        self.dim = 0.0
        self.calm = 0.0            # пауза: эффекты экрана гаснут, свечение приглушено (0..1)
        self.calm_target = 0.0
        self.dim_target = 0.0
        self.dim_hold = 0.0
        self.hitstop = 0.0
        self.slow_k, self.slow_time = 1.0, 0.0
        self.zoom, self.zoom_target, self.zoom_hold = 1.0, 1.0, 0.0
        self.center = (640.0, 360.0)
        self.aberration = 0.0
        self.radial = 0.0
        self.radial_center = (640.0, 360.0)
        self.bars, self.bars_target, self.bars_hold = 0.0, 0.0, 0.0

    def time_k(self):
        """Множитель хода игрового времени: 0 — стоп-кадр, <1 — замедление."""
        if self.hitstop > 0:
            return 0.0
        return self.slow_k if self.slow_time > 0 else 1.0


class VfxWorld:
    def __init__(self, presets=None, effects=None, seed=7, props=None):
        self.presets = presets if presets is not None else _load("fx.json")
        lib = effects if effects is not None else _load("vfx.json")
        self.effects = lib["effects"]
        self.lib = lib
        self.rng = np.random.default_rng(seed)
        self.prng = random.Random(seed)
        self.prop_index = props or {}        # имя модельки → номер в атласе (задаёт BattleView)
        self.n = 0
        f = np.float32
        self.x, self.y, self.vx, self.vy = (np.zeros(CAP, f) for _ in range(4))
        self.g, self.drag, self.age, self.life = (np.zeros(CAP, f) for _ in range(4))
        self.s0, self.s1, self.asp, self.stretch = (np.zeros(CAP, f) for _ in range(4))
        self.rot, self.spin, self.ys, self.fadein, self.hdr, self.roff = (np.zeros(CAP, f) for _ in range(6))
        self.floor, self.bounce, self.fps, self.f0 = (np.zeros(CAP, f) for _ in range(4))
        self.a0, self.a1 = np.zeros(CAP, f), np.zeros(CAP, f)
        self.c0, self.c1 = np.zeros((CAP, 3), f), np.zeros((CAP, 3), f)
        self.shape = np.zeros(CAP, np.int16)
        self.fbn = np.zeros(CAP, np.int16)
        self.add = np.zeros(CAP, bool)
        self.under = np.zeros(CAP, bool)
        self.orient = np.zeros(CAP, bool)
        self._arrays = [self.x, self.y, self.vx, self.vy, self.g, self.drag, self.age, self.life, self.s0, self.s1,
                        self.asp, self.stretch, self.rot, self.spin, self.ys, self.fadein, self.hdr, self.roff,
                        self.floor, self.bounce, self.fps, self.f0, self.a0, self.a1,
                        self.c0, self.c1, self.shape, self.fbn, self.add, self.under, self.orient]
        self.decals, self.emitters, self.props, self.sfx, self.ribbons, self.lights = [], [], [], [], [], []
        self.frame_lights = []      # свет на один кадр (горящие клетки, касты) — заполняет BattleView
        self.marks = []             # следы, которые BattleView впечатает в слой поля
        self.pending = []           # (время, функция)
        self.time = 0.0
        self.screen = Screen()

    def clear(self):
        self.n = 0
        for lst in (self.decals, self.emitters, self.props, self.sfx, self.ribbons, self.lights, self.frame_lights,
                    self.marks, self.pending):
            lst.clear()
        self.screen = Screen()

    def busy(self):
        return bool(self.n or self.decals or self.emitters or self.props or self.sfx or self.ribbons or self.lights
                    or self.pending)

    # ---------- частицы ----------

    def emit(self, name, x, y, color=None, scale=1.0, count=None, angle=None):
        p = self.presets[name]
        cnt = p.get("count", 1) if count is None else count
        if isinstance(cnt, list):
            cnt = self.prng.randint(*cnt)
        k = min(int(round(cnt)), CAP - self.n)
        if k <= 0:
            return
        rng = self.rng
        s = slice(self.n, self.n + k)
        ground = p.get("ground", False)
        flat = GROUND_YS if ground else 1.0
        spawn = p.get("spawn", 0) * scale
        shape = p.get("spawn_shape", "disc")
        aa = rng.uniform(0, math.tau, k)
        if shape == "ring":
            rr = np.full(k, spawn)
        else:
            rr = spawn * np.sqrt(rng.random(k))
        if shape == "line":
            px, py = rng.uniform(-spawn, spawn, k), np.zeros(k)
        elif shape == "column":
            px, py = rng.uniform(-spawn * 0.25, spawn * 0.25, k), -rng.uniform(0, spawn * 2, k)
        else:
            px, py = np.cos(aa) * rr, np.sin(aa) * rr * flat
        self.x[s], self.y[s] = x + px, y + py
        if p.get("radial") or p.get("converge"):
            dirs = aa + (math.pi if p.get("converge") else 0.0)
        else:
            base = math.radians(p.get("angle", 0) if angle is None else angle)
            spread = math.radians(p.get("spread", 360))
            dirs = base + rng.uniform(-spread / 2, spread / 2, k)
        sp = rng.uniform(*p.get("speed", [0, 0]), k) * scale
        self.vx[s] = np.cos(dirs) * sp
        self.vy[s] = np.sin(dirs) * sp * (flat if (p.get("radial") or p.get("converge")) else 1.0)
        self.g[s] = p.get("gravity", 0)
        self.drag[s] = p.get("drag", 0)
        self.age[s] = 0
        self.life[s] = rng.uniform(*p["life"], k)
        jit = p.get("jitter", 0.25)
        size = p.get("size", [8, 2])
        sj = rng.uniform(1 - jit, 1 + jit, k) * scale
        self.s0[s], self.s1[s] = size[0] * sj, size[1] * sj
        self.asp[s] = p.get("aspect", 1.0)
        self.stretch[s] = p.get("stretch", 0.0)
        sh = p.get("shape", "glow")
        rot = p.get("rot", [0, 360] if sh in ("star", "shard", "smoke", "snow", "pixel") or sh.startswith("fb_smoke")
                    else [0, 0])
        self.rot[s] = np.radians(rng.uniform(rot[0], rot[1], k))
        spin = p.get("spin", [0, 0])
        self.spin[s] = np.radians(rng.uniform(spin[0], spin[1], k)) * rng.choice([-1, 1], k)
        self.ys[s] = flat if p.get("flat_sprite", ground) else 1.0
        self.fadein[s] = p.get("fadein", 0.0)
        self.hdr[s] = p.get("hdr", 1.0)
        fl = p.get("floor")
        self.floor[s] = (self.y[s] + fl * scale) if fl is not None else np.inf
        self.bounce[s] = p.get("bounce", 0.0)
        al = p.get("alpha", [1.0, 0.0])
        self.a0[s], self.a1[s] = al[0], al[1]
        cols = p.get("colors", ["white", "white"])
        self.c0[s] = resolve_color(cols[0], color)
        self.c1[s] = resolve_color(cols[-1], color)
        self.shape[s] = INDEX[sh]
        if sh in FLIP:
            self.fbn[s] = FRAMES
            self.fps[s] = p.get("fps", 0.0)
            self.f0[s] = rng.integers(0, FRAMES, k) if p.get("fps") else 0
        else:
            self.fbn[s] = 0
        self.add[s] = p.get("blend", "add") == "add"
        self.under[s] = p.get("under", False)
        self.orient[s] = p.get("orient", False)
        self.roff[s] = math.radians(p.get("orient_offset", 0))
        if p.get("orient"):
            self.rot[s] = np.arctan2(self.vy[s], self.vx[s]) + self.roff[s]
        self.n += k

    def emit_line(self, name, a, b, color=None, step=10, scale=1.0):
        d = math.dist(a, b)
        n = max(1, int(d / step))
        for i in range(n + 1):
            t = i / n
            self.emit(name, a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, color, scale)

    def emit_sprite(self, surf, rect, name="dissolve", step=2, color_mul=1.0):
        """Рассыпать спрайт на частицы его же цветов (смерть)."""
        import pygame
        w, h = surf.get_size()
        px = pygame.surfarray.array3d(surf)
        al = pygame.surfarray.array_alpha(surf)
        xs, ys = np.nonzero(al[::step, ::step] > 40)
        if not len(xs):
            return
        xs, ys = xs * step, ys * step
        k = min(len(xs), CAP - self.n, 900)
        pick = self.rng.choice(len(xs), k, replace=False) if len(xs) > k else np.arange(len(xs))
        xs, ys = xs[pick], ys[pick]
        start = self.n
        self.emit(name, 0, 0, count=k)
        s = slice(start, start + k)
        sx, sy = rect.w / w, rect.h / h
        self.x[s] = rect.x + xs * sx
        self.y[s] = rect.y + ys * sy
        cols = px[xs, ys].astype(np.float32) / 255.0 * color_mul
        self.c0[s] = cols
        self.c1[s] = cols * 0.4
        # верхние пиксели улетают позже — спрайт «стирается» снизу вверх
        self.life[s] *= 0.6 + 0.8 * (1 - ys / h)

    # ---------- источники и объекты ----------

    def decal(self, **kw):
        d = Decal(**kw)
        self.decals.append(d)
        return d

    def emitter(self, preset, rate, pos, color=None, scale=1.0, duration=None, alive=None, on_end=None, angle=None):
        e = Emitter(preset, rate, pos, color, scale, duration, alive, on_end, angle)
        self.emitters.append(e)
        return e

    def prop(self, name, x, y, **kw):
        idx = self.prop_index.get(name)
        if idx is None:          # моделек нет (тесты без атласа) — всё равно ведём объект ради on_end
            idx = -1
        p = Prop(idx, name, x, y, **kw)
        self.props.append(p)
        return p

    def add_sfx(self, spec, pos, color=None, scale=1.0, alive=None, rot=None):
        """spec — имя заготовки из vfx.json["sfx"] или словарь. Размер [w, h] или число."""
        if isinstance(spec, str):
            spec = self.lib["sfx"][spec]
        size = spec.get("size", 100)
        w, h = (size, size) if not isinstance(size, list) else size
        col = resolve_color(spec.get("color", "tag"), color)
        r = spec.get("rot", 0) if rot is None else rot
        s = Sfx(spec["mode"], pos, (w * scale, h * scale), col, life=spec.get("life", 0.5), alive=alive,
                alpha=tuple(spec.get("alpha", [1, 0])), grow=tuple(spec.get("grow", [1, 1])),
                rot=r, spin=spec.get("spin", 0), ys=GROUND_YS if spec.get("ground") else spec.get("ys", 1.0),
                hdr=spec.get("hdr", 1.0), add=spec.get("blend", "add") == "add", under=spec.get("under", False),
                seed=self.prng.random() * 10, extra=spec.get("extra", 0.0), fade=spec.get("fade", 0.15),
                fadein=spec.get("fadein", 0.0))
        if alive is not None and spec.get("loop", True):
            s.life = spec.get("life", 0.5) if spec.get("life_fixed") else None
        self.sfx.append(s)
        return s

    def add_ribbon(self, spec, src, color=None, scale=1.0, duration=None, alive=None):
        if isinstance(spec, str):
            spec = self.lib["ribbons"][spec]
        col = resolve_color(spec.get("color", "tag"), color)
        r = Ribbon(src, spec.get("life", 0.2), spec.get("width", 20) * scale, col, spec.get("hdr", 1.5),
                   RIB_MODES[spec.get("mode", "energy")], self.prng.random() * 10, duration, alive,
                   spec.get("blend", "add") == "add", spec.get("taper", 1.0), spec.get("under", False))
        self.ribbons.append(r)
        return r

    def add_light(self, spec, pos, color=None, scale=1.0, alive=None):
        if isinstance(spec, str):
            spec = self.lib["lights"][spec]
        col = resolve_color(spec.get("color", "tag"), color)
        lt = Light(pos, col, spec.get("radius", 120) * scale, spec.get("intensity", 1.0),
                   None if alive else spec.get("life", 0.4), alive, spec.get("flicker", 0.0),
                   spec.get("fadein", 0.05), spec.get("curve", 1.5), spec.get("fade", 0.2))
        self.lights.append(lt)
        return lt

    def bolt(self, a, b, color=None, width=9, life=0.3, jag=0.18, forks=1, hdr=2.8):
        """Молния a → b: ломаная лента, появляется сразу и гаснет целиком; forks — отростки в стороны."""
        col = resolve_color(color if color is not None else (190, 200, 255), None)
        d = math.dist(a, b)
        n = max(3, int(d / 18))
        nx, ny = (-(b[1] - a[1]) / (d or 1), (b[0] - a[0]) / (d or 1))
        pts = []
        off = 0.0
        for i in range(n + 1):
            t = i / n
            if 0 < i < n:
                off = off * 0.4 + self.prng.uniform(-1, 1) * jag * d * 0.35
            else:
                off = 0.0
            pts.append((a[0] + (b[0] - a[0]) * t + nx * off, a[1] + (b[1] - a[1]) * t + ny * off))
        self._static_ribbon(pts, width, life, col, hdr)
        for _ in range(forks):
            k = self.prng.randint(1, max(1, n - 1))
            sx, sy = pts[k]
            ang = math.atan2(b[1] - a[1], b[0] - a[0]) + self.prng.uniform(-1.2, 1.2)
            ln = d * self.prng.uniform(0.15, 0.3)
            fpts = [(sx + math.cos(ang) * ln * t + self.prng.uniform(-6, 6), sy + math.sin(ang) * ln * t
                     + self.prng.uniform(-6, 6)) for t in (0, 0.35, 0.7, 1.0)]
            self._static_ribbon(fpts, width * 0.55, life * 0.8, col, hdr)

    def _static_ribbon(self, pts, width, life, col, hdr):
        r = Ribbon(None, life, width, col, hdr, RIB_MODES["lightning"], self.prng.random() * 10, 0.0)
        r.pts = [(x, y, 0.0) for x, y in pts]
        r.stopped = 0.0
        r.static = True
        self.ribbons.append(r)

    def mark(self, name, x, y, size=80, rot=0.0, alpha=1.0, flat=0.5):
        self.marks.append((name, x, y, size, rot, alpha, flat))

    def projectile(self, a, b, speed, head, trail, color, arc=0.0, scale=1.0, on_hit=None, trail_rate=150,
                   ribbon=None, prop=None, sfx=None, light=None, dur=None, stick=None, prop_scale=2.0, spin=0.0):
        """Снаряд a → b: голова (пресеты частиц), след, лента, моделька, шейдерная сфера, свет; on_hit — по прилёте.
        Возвращает время полёта."""
        dist = math.dist(a, b)
        if dur is None:
            dur = max(0.06, dist / speed)
        ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))

        def at(t):
            t = min(1.0, max(0.0, t / dur))
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t - math.sin(math.pi * t) * arc)

        def pos(e):
            return at(e.age)
        ender = [on_hit]          # on_hit вызывает первый объект, который «долетит»

        def take():
            fn, ender[0] = ender[0], None
            return fn
        if trail:
            self.emitter(trail, trail_rate, pos, color, scale, duration=dur, angle=ang)
        heads = [] if not head else ([head] if isinstance(head, str) else list(head))
        for i, h in enumerate(heads):
            self.emitter(h, 140, pos, color, scale, duration=dur, on_end=take() if i == 0 else None, angle=ang)
        if ribbon:
            for rb in ([ribbon] if isinstance(ribbon, (str, dict)) else ribbon):
                self.add_ribbon(rb, at, color, scale, duration=dur)
        start = self.time
        for sp in ([sfx] if isinstance(sfx, (str, dict)) else (sfx or [])):
            self.add_sfx(sp, lambda: at(self.time - start), color, scale, alive=lambda: self.time - start < dur)
        if light:
            self.add_light(light, lambda: at(self.time - start), color, scale, alive=lambda: self.time - start < dur)
        if prop:
            self.prop(prop, a[0], a[1], scale=prop_scale, path=(a, b, dur, arc), orient=not spin, spin=spin,
                      on_end=take(), stick=stick, life=dur + 0.01)
        fn = take()
        if fn:
            self.after(dur, fn)
        return dur

    def after(self, delay, fn):
        if delay <= 0:
            fn()
        else:
            self.pending.append((self.time + delay, fn))

    # ---------- эффекты из таймлайна ----------

    def play(self, name, ctx):
        """ctx: точки caster, caster_ground, target, target_ground, cells (список точек земли), color, dir (град),
        scale, tier (ступень ветки), *_unit (юниты — для «пока жив/оглушён»)."""
        layers = self.effects.get(name)
        if layers is None:
            return
        tier = ctx.get("tier", 0)
        for layer in layers:
            if layer.get("min_tier", 0) > tier:
                continue
            self.after(layer.get("t", 0.0), lambda layer=layer: self._layer(layer, ctx))

    def _points(self, at, ctx):
        if at == "cells":
            return ctx.get("cells") or [ctx.get("target_ground")]
        p = ctx.get(at)
        if callable(p):
            p = p()
        return [p] if p is not None else []

    def _ground_of(self, at, ctx, p):
        """Земля под точкой: для тела — ноги того же юнита."""
        g = {"target": "target_ground", "caster": "caster_ground"}.get(at)
        if g and ctx.get(g) is not None:
            return _point(ctx[g])[1]
        return p[1]

    def _angle(self, spec, ctx):
        if spec == "dir":
            return ctx.get("dir", 0)
        if spec == "back":
            return ctx.get("dir", 0) + 180
        return spec

    def _layer(self, layer, ctx):
        color = ctx.get("color")
        if "color" in layer and layer["color"] not in ("tag", "tag_light", "tag_dark"):
            color = layer["color"]
        scale = ctx.get("scale", 1.0) * layer.get("scale", 1.0)
        at = layer.get("at", "target")
        if "screen" in layer:
            pts = self._points(at, ctx)
            self.screen_fx(color=color, center=pts[0] if pts else None, **layer["screen"])
            return
        if "play" in layer:                       # вложенный эффект
            self.play(layer["play"], dict(ctx, scale=scale, color=color))
            return
        pts = self._points(at, ctx)
        dx, dy = layer.get("offset", [0, 0])
        dx, dy = dx * scale, dy * scale
        if "fx" in layer:
            angle = self._angle(layer.get("angle"), ctx)
            count = layer.get("count")
            if count is not None and at == "cells":
                count = max(1, count / max(1, len(pts)) * 2)
            for x, y in pts:
                self.emit(layer["fx"], x + dx, y + dy, color, scale, count, angle)
        elif "decal" in layer:
            d = layer["decal"]
            col = resolve_color(d.get("color", "tag"), color)
            size = d.get("size", 100) * scale
            rot = self._angle(d.get("rot", d.get("rot0", 0)), ctx) + d.get("rot_offset", 0)
            src = ctx.get(at + "_fn", ctx.get(at))
            for x, y in pts:
                pos = (x + dx, y + dy)
                if layer.get("follow") and callable(src):
                    pos = (lambda src=src: (src()[0] + dx, src()[1] + dy))
                self.decal(shape=d.get("shape", "glow"), pos=pos, size=size, color=col,
                           life=d.get("life", 0.6), alpha=tuple(d.get("alpha", [1, 0])),
                           grow=tuple(d.get("grow", [1, 1])),
                           spin=d.get("spin", 0), rot=rot, ground=d.get("ground", False),
                           aspect=d.get("aspect", 1.0), hdr=d.get("hdr", 1.0), fade=d.get("fade", 0.12),
                           pulse=d.get("pulse", 0.0), add=d.get("blend", "add") == "add", under=d.get("under", False))
        elif "sfx" in layer:
            spec = layer["sfx"]
            spec = self.lib["sfx"][spec] if isinstance(spec, str) else spec
            if "color" in layer:                  # цвет слоя главнее цвета заготовки
                spec = dict(spec, color="tag")
            rot = self._angle(spec.get("rot", 0), ctx) + spec.get("rot_offset", 0)
            alive = self._while(layer.get("while"), ctx)
            src = ctx.get(at + "_fn", ctx.get(at))
            for x, y in pts[:layer.get("max", 99)]:
                pos = (x + dx, y + dy)
                if layer.get("follow") and callable(src):
                    pos = (lambda src=src: (src()[0] + dx, src()[1] + dy))
                self.add_sfx(spec, pos, color, scale, alive=alive, rot=rot)
        elif "light" in layer:
            alive = self._while(layer.get("while"), ctx)
            for x, y in pts[:layer.get("max", 3)]:
                self.add_light(layer["light"], (x + dx, y + dy), color, scale, alive=alive)
        elif "mark" in layer:
            m = layer["mark"]
            m = {"name": m} if isinstance(m, str) else m
            for i, (x, y) in enumerate(pts):
                rot = self.prng.uniform(0, 360) if m.get("rot", "random") == "random" else m["rot"]
                if m["name"].startswith("prop:"):
                    rot = self.prng.uniform(0, 40)
                size = _rng_val(m.get("size", 80), self.prng) * scale
                self.mark(m["name"], x + dx + self.prng.uniform(-1, 1) * m.get("jitter", 0),
                          y + dy + self.prng.uniform(-0.5, 0.5) * m.get("jitter", 0), size, rot,
                          m.get("alpha", 1.0), m.get("flat", 0.5))
        elif "props" in layer:
            self._props_burst(layer["props"], pts, at, ctx, color, scale, dx, dy)
        elif "attach" in layer:                   # моделька на юните: сеть, капкан — пока он оглушён и т.п.
            spec = layer["attach"]
            src = ctx.get(at + "_fn")
            alive = self._while(layer.get("while"), ctx)
            for x, y in pts[:1]:
                follow = (lambda src=src: (src()[0] + dx, src()[1] + dy)) if src else None
                self.prop(spec["prop"], x + dx, y + dy, scale=spec.get("scale", 2.0) * scale, follow=follow,
                          alive=alive, life=spec.get("life", 1.5), grow=tuple(spec.get("grow", [1, 1])),
                          grow_time=spec.get("grow_time", 0.15), fade=spec.get("fade", 0.25),
                          rot=math.radians(spec.get("rot", 0)))
        elif "projectile" in layer:
            self._projectile_layer(layer["projectile"], pts, at, ctx, color, scale, dx, dy)
        elif "arc" in layer:
            for x, y in pts:
                self._arc(layer["arc"], (x + dx, y + dy), ctx, color, scale)
        elif "line" in layer:          # частицы вдоль линии кастер → цель
            a, b = self._points("caster", ctx), self._points("target", ctx)
            if a and b:
                self.emit_line(layer["line"], a[0], b[0], color, layer.get("step", 10) * scale, scale)
        elif "bolt" in layer:          # молния кастер → цель (или с неба в точку)
            spec = layer["bolt"]
            for x, y in pts[:layer.get("max", 6)]:
                if spec.get("from") == "sky":
                    a = (x + self.prng.uniform(-40, 40), y - spec.get("height", 420) * scale)
                else:
                    src = self._points(spec.get("from", "caster"), ctx)
                    if not src:
                        continue
                    a = src[0]
                self.bolt(a, (x + dx, y + dy), color, spec.get("width", 7) * scale, spec.get("life", 0.18),
                          spec.get("jag", 0.18), spec.get("forks", 1))
        elif "streak" in layer:        # лента, пролетающая кастер → цель (пронзающий выстрел, рывок)
            spec = layer["streak"]
            a, b = self._points(spec.get("from", "caster"), ctx), self._points(spec.get("to", "target"), ctx)
            if a and b:
                a, b = a[0], b[0]
                ext = spec.get("extend", 0)
                if ext:
                    d = math.dist(a, b) or 1
                    b = (b[0] + (b[0] - a[0]) / d * ext, b[1] + (b[1] - a[1]) / d * ext)
                dur = spec.get("time", 0.1)
                self.add_ribbon(spec["ribbon"], lambda t: (a[0] + (b[0] - a[0]) * min(1, t / dur),
                                                           a[1] + (b[1] - a[1]) * min(1, t / dur)),
                                color, scale, duration=dur)

    def _while(self, cond, ctx):
        if not cond:
            return None
        u = ctx.get(cond.split(":")[1] + "_unit") if ":" in cond else ctx.get("target_unit")
        if u is None:
            return None
        kind = cond.split(":")[0]
        if kind == "stun":
            return lambda: u.alive and u.stun > 0
        if kind == "alive":
            return lambda: u.alive
        if kind == "cast":
            return lambda: u.alive and u.cast is not None
        if kind == "shield":
            return lambda: u.alive and u.shield > 0
        return None

    def _props_burst(self, spec, pts, at, ctx, color, scale, dx, dy):
        """Обломки: модельки разлетаются, падают на землю, отскакивают и гаснут."""
        names = spec["name"] if isinstance(spec["name"], list) else [spec["name"]]
        for x, y in pts:
            floor = self._ground_of(at, ctx, (x, y)) + dy
            n = spec.get("count", 6)
            if at == "cells":
                n = max(1, round(n / max(1, len(pts)) * 2))
            for _ in range(n):
                ang = math.radians(self._angle(spec.get("angle", -90), ctx) + self.prng.uniform(-1, 1) *
                                   spec.get("spread", 120) / 2)
                sp = self.prng.uniform(*spec.get("speed", [150, 350])) * scale
                sx = x + dx + self.prng.uniform(-1, 1) * spec.get("spawn", 6) * scale
                sy = y + dy + self.prng.uniform(-1, 1) * spec.get("spawn", 6) * scale * 0.5
                self.prop(self.prng.choice(names), sx, sy, scale=spec.get("scale", 2.0),
                          vx=math.cos(ang) * sp, vy=math.sin(ang) * sp, g=spec.get("gravity", 900),
                          spin=math.radians(self.prng.uniform(*spec.get("spin", [180, 720])))
                          * self.prng.choice([-1, 1]),
                          rot=self.prng.uniform(0, math.tau), life=self.prng.uniform(*spec.get("life", [1.2, 2.0])),
                          floor=floor + self.prng.uniform(-6, 10), bounce=spec.get("bounce", 0.35),
                          stick=spec.get("stick", False), fade=spec.get("fade", 0.4))

    def _projectile_layer(self, spec, pts, at, ctx, color, scale, dx, dy):
        """Снаряды из таймлайна: метеор с неба, дождь стрел, склянка... from — "caster", "sky" или смещение
        от цели; count/stagger/spread — несколько штук вразброс; impact — эффект в точке попадания."""
        n = spec.get("count", 1)
        targets = pts if spec.get("per_point", at == "cells") else pts[:1]
        if spec.get("count_total"):
            targets = [self.prng.choice(pts) for _ in range(spec["count_total"])] if pts else []
            n = 1
        k = 0
        for x, y in targets:
            for i in range(n):
                spread = spec.get("spread", 0) * scale
                b = (x + dx + self.prng.uniform(-1, 1) * spread, y + dy + self.prng.uniform(-0.5, 0.5) * spread)
                src = spec.get("from", "caster")
                if src in ("caster", "target", "caster_ground", "target_ground"):
                    a = self._points(src, ctx)
                    if not a:
                        continue
                    a = a[0]
                elif src == "sky":
                    off = spec.get("sky", [-80, -480])
                    a = (b[0] + off[0] * scale + self.prng.uniform(-1, 1) * spec.get("sky_jitter", 30),
                         b[1] + off[1] * scale)
                else:
                    a = (b[0] + src[0], b[1] + src[1])
                delay = k * spec.get("stagger", 0.0) + self.prng.uniform(0, spec.get("jitter_t", 0.0))
                k += 1
                self.after(delay, lambda a=a, b=b: self._fire(spec, a, b, ctx, color, scale))

    def _fire(self, spec, a, b, ctx, color, scale):
        impact = spec.get("impact")
        sub = dict(ctx, target=b, target_ground=(b[0], b[1] + spec.get("ground_dy", 0)), cells=[b])
        stick = spec.get("stick")

        def hit():
            if impact:
                self.play(impact, sub)
            if stick:
                self.mark("prop:" + spec["prop"], b[0], b[1] + 2, 0, self.prng.uniform(0, 40))
        col = tuple(spec["color"]) if spec.get("color") else color
        self.projectile(a, b, spec.get("speed", 900) * scale, spec.get("head"), spec.get("trail"), col,
                        spec.get("arc", 0) * scale, spec.get("head_scale", 1.0) * scale, hit,
                        spec.get("trail_rate", 150), spec.get("ribbon"), spec.get("prop"), spec.get("sfx"),
                        spec.get("light"), spec.get("time"), None, spec.get("prop_scale", 2.0),
                        math.radians(spec.get("spin", 0)))

    def _arc(self, spec, c, ctx, color, scale):
        """Взмах: лента по дуге вокруг точки, повёрнутой по направлению удара."""
        R = spec.get("radius", 50) * scale
        a0, a1 = math.radians(spec.get("from", -70)), math.radians(spec.get("to", 70))
        if spec.get("flip") == "random" and self.prng.random() < 0.5 or spec.get("flip") is True:
            a0, a1 = a1, a0
        base = math.radians(self._angle(spec.get("rot", "dir"), ctx) + spec.get("rot_offset", 0))
        squash = spec.get("squash", 0.55)
        dur = spec.get("time", 0.1)
        cb, sb = math.cos(base), math.sin(base)

        def src(t):
            th = a0 + (a1 - a0) * _ease_out(min(1.0, t / dur))
            lx, ly = math.cos(th) * R, math.sin(th) * R * squash
            return c[0] + lx * cb - ly * sb, c[1] + lx * sb + ly * cb
        self.add_ribbon(spec.get("ribbon", "slash"), src, color, scale, duration=dur)

    def screen_fx(self, shake=0.0, flash=0.0, flash_time=0.25, dim=0.0, dim_time=0.6, color=None, flash_color=None,
                  hitstop=0.0, slowmo=None, zoom=0.0, zoom_time=0.4, center=None, aberration=0.0, radial=0.0,
                  bars=0.0, bars_time=0.8):
        sc = self.screen
        st = SETTINGS                 # настройки игрока ослабляют или выключают экранные эффекты
        shake *= st["shake"]
        flash *= st["flash"]
        aberration *= st["flash"]
        radial *= st["flash"]
        if not st["hitstop"]:
            hitstop, slowmo = 0.0, None
        if not st["zoom"]:
            zoom = 0.0
        sc.shake = max(sc.shake, shake)
        if flash:
            c = flash_color or color or (255, 255, 255)
            sc.flash = max(sc.flash, flash)
            sc.flash_color = tuple(v / 255 for v in (c if not isinstance(c, str) else (255, 255, 255)))
            sc.flash_decay = 1.0 / max(0.05, flash_time)
        if dim:
            sc.dim_target = max(sc.dim_target, dim)
            sc.dim_hold = max(sc.dim_hold, dim_time)
        if hitstop:
            sc.hitstop = max(sc.hitstop, hitstop)
        if slowmo:
            sc.slow_k = min(sc.slow_k if sc.slow_time > 0 else 1.0, slowmo[0])
            sc.slow_time = max(sc.slow_time, slowmo[1])
        if zoom:
            sc.zoom_target = max(sc.zoom_target, zoom)
            sc.zoom_hold = max(sc.zoom_hold, zoom_time)
            if center is not None:
                sc.center = tuple(center)
        if aberration:
            sc.aberration = max(sc.aberration, aberration)
        if radial:
            sc.radial = max(sc.radial, radial)
            if center is not None:
                sc.radial_center = tuple(center)
        if bars:
            sc.bars_target = max(sc.bars_target, bars)
            sc.bars_hold = max(sc.bars_hold, bars_time)

    # ---------- время ----------

    def real_update(self, dt):
        """Таймеры в реальном времени: стоп-кадр и замедление (иначе стоп-кадр не кончился бы никогда)."""
        sc = self.screen
        sc.hitstop = max(0.0, sc.hitstop - dt)
        sc.slow_time = max(0.0, sc.slow_time - dt)
        sc.calm += (sc.calm_target - sc.calm) * min(1.0, dt * 8)
        if sc.calm > 0.01:                 # на паузе затемнение, полосы, вспышки, зум и тряска уходят сразу
            k = min(1.0, dt * 8 * sc.calm)
            sc.dim -= sc.dim * k
            sc.bars -= sc.bars * k
            sc.flash -= sc.flash * k
            sc.aberration -= sc.aberration * k
            sc.radial -= sc.radial * k
            sc.zoom += (1.0 - sc.zoom) * k
            sc.shake, sc.offset = 0.0, (0.0, 0.0)

    def update(self, dt):
        if dt <= 0:
            return
        self.time += dt
        due = [p for p in self.pending if p[0] <= self.time]
        if due:
            self.pending = [p for p in self.pending if p[0] > self.time]
            for _, fn in sorted(due, key=lambda p: p[0]):
                fn()
        self._update_emitters(dt)
        self._update_particles(dt)
        self._update_props(dt)
        self._update_ribbons(dt)
        for lst in (self.decals, self.sfx, self.lights):
            for d in lst:
                d.age += dt
                if d.alive_fn and d.dying is None and not d.alive_fn():
                    d.dying = d.age
        self.decals = [d for d in self.decals if not self._done(d)]
        self.sfx = [d for d in self.sfx if not self._done(d)]
        self.lights = [d for d in self.lights if not self._done(d)]
        sc = self.screen
        sc.shake *= math.exp(-dt * 9)
        if sc.shake < 0.3:
            sc.shake = 0.0
        a = self.prng.uniform(0, math.tau)
        sc.offset = (math.cos(a) * sc.shake, math.sin(a) * sc.shake * 0.7)
        sc.flash = max(0.0, sc.flash - dt * sc.flash_decay * max(sc.flash, 0.2))
        sc.dim_hold = max(0.0, sc.dim_hold - dt)
        if sc.dim_hold <= 0:
            sc.dim_target = 0.0
        sc.dim += (sc.dim_target - sc.dim) * min(1.0, dt * 6)
        sc.zoom_hold = max(0.0, sc.zoom_hold - dt)
        if sc.zoom_hold <= 0:
            sc.zoom_target = 1.0
        sc.zoom += (sc.zoom_target - sc.zoom) * min(1.0, dt * (14 if sc.zoom_target > sc.zoom else 5))
        sc.bars_hold = max(0.0, sc.bars_hold - dt)
        if sc.bars_hold <= 0:
            sc.bars_target = 0.0
        sc.bars += (sc.bars_target - sc.bars) * min(1.0, dt * 7)
        sc.aberration *= math.exp(-dt * 6)
        sc.radial *= math.exp(-dt * 7)

    def _done(self, d):
        if d.dying is not None:
            return d.age - d.dying > d.fade
        return d.life is not None and d.alive_fn is None and d.age >= d.life

    def _update_emitters(self, dt):
        keep = []
        for e in self.emitters:
            e.age += dt
            done = (e.duration is not None and e.age >= e.duration) or (e.alive_fn is not None and not e.alive_fn())
            if not done:
                e.acc += e.rate * dt
                k = int(e.acc)
                e.acc -= k
                if k:
                    x, y = e.pos(e) if callable(e.pos) else e.pos
                    self.emit(e.preset, x, y, e.color, e.scale, count=k, angle=e.angle)
                keep.append(e)
            elif e.on_end:
                e.on_end()
        self.emitters = keep

    def _update_particles(self, dt):
        n = self.n
        if not n:
            return
        self.age[:n] += dt
        alive = self.age[:n] < self.life[:n]
        if not alive.all():
            idx = np.nonzero(alive)[0]
            m = len(idx)
            for arr in self._arrays:
                arr[:m] = arr[idx]
            n = self.n = m
        if not n:
            return
        sl = slice(0, n)
        self.vy[sl] += self.g[sl] * dt
        k = np.maximum(0.0, 1.0 - self.drag[sl] * dt)
        self.vx[sl] *= k
        self.vy[sl] *= k
        self.x[sl] += self.vx[sl] * dt
        self.y[sl] += self.vy[sl] * dt
        hit = (self.y[sl] > self.floor[sl]) & (self.vy[sl] > 0)
        if hit.any():                         # удар о землю: отскок с потерей скорости
            idx = np.nonzero(hit)[0]
            self.y[idx] = self.floor[idx]
            self.vy[idx] *= -self.bounce[idx]
            self.vx[idx] *= 0.6
            self.spin[idx] *= 0.5
        self.rot[sl] += self.spin[sl] * dt
        o = self.orient[sl]
        if o.any():
            self.rot[sl][o] = np.arctan2(self.vy[sl][o], self.vx[sl][o]) + self.roff[sl][o]

    def _update_props(self, dt):
        keep = []
        for p in self.props:
            p.age += dt
            if p.follow:
                p.x, p.y = p.follow()
            elif p.path:
                a, b, dur, arc = p.path
                t = min(1.0, p.age / dur)
                p.x = a[0] + (b[0] - a[0]) * t
                p.y = a[1] + (b[1] - a[1]) * t - math.sin(math.pi * t) * arc
                if p.orient:
                    p.rot = math.atan2((b[1] - a[1]) - math.cos(math.pi * t) * math.pi * arc, b[0] - a[0])
                else:
                    p.rot += p.spin * dt
                if t >= 1.0:
                    if p.on_end:
                        p.on_end()
                    if p.stick:
                        self.mark("prop:" + p.name, b[0], b[1] + 2, 0, math.degrees(p.rot) % 40)
                    continue
            else:
                if p.rest is None:
                    p.vy += p.g * dt
                    p.x += p.vx * dt
                    p.y += p.vy * dt
                    if p.orient:
                        p.rot = math.atan2(p.vy, p.vx)
                    else:
                        p.rot += p.spin * dt
                    if p.floor is not None and p.y >= p.floor and p.vy > 0:
                        p.y = p.floor
                        if p.stick:
                            self.mark("prop:" + p.name, p.x, p.y + 2, 0, self.prng.uniform(0, 40))
                            continue
                        p.vy *= -p.bounce
                        p.vx *= 0.6
                        p.spin *= 0.55
                        if abs(p.vy) < 60:
                            p.rest = p.age
            if p.alive_fn is not None:
                if p.dying is None and not p.alive_fn():
                    p.dying = p.age
                if p.dying is not None and p.age - p.dying > p.fade:
                    continue
            elif p.age >= p.life:
                continue
            keep.append(p)
        self.props = keep

    def _update_ribbons(self, dt):
        keep = []
        for r in self.ribbons:
            r.age += dt
            if r.stopped is None and ((r.duration is not None and r.age >= r.duration) or
                                      (r.alive_fn is not None and not r.alive_fn())):
                r.stopped = min(r.age, r.duration) if r.duration is not None else r.age
            if r.static:
                if r.age < r.life:
                    keep.append(r)
                continue
            until = r.age if r.stopped is None else r.stopped
            while r.last + r.STEP <= until:
                r.last += r.STEP
                x, y = r.src(r.last)
                r.pts.append((x, y, r.last))
            cut = r.age - r.life
            if r.pts and r.pts[0][2] < cut:
                r.pts = [p for p in r.pts if p[2] >= cut]
            if r.stopped is not None and not r.pts:
                continue
            keep.append(r)
        self.ribbons = keep

    # ---------- данные для отрисовки ----------

    def _alpha_of(self, d):
        t = min(1.0, d.age / d.life) if d.life else 0.0
        a = d.alpha[0] + (d.alpha[1] - d.alpha[0]) * t
        a *= min(1.0, d.age / max(0.01, getattr(d, "fadein", 0.0) or d.fade))
        if d.dying is not None:
            a *= max(0.0, 1 - (d.age - d.dying) / max(0.01, d.fade))
        return t, a

    def _decal_rows(self, under, add):
        rows = []
        for d in self.decals:
            if d.add != add or d.under != under:
                continue
            x, y = d.point()
            t, a = self._alpha_of(d)
            if d.pulse:
                a *= 1 - d.pulse * 0.5 * (1 + math.sin(d.age * 8))
            size = d.size * (d.grow[0] + (d.grow[1] - d.grow[0]) * (1 - (1 - t) ** 3))
            rot = d.rot + d.spin * d.age
            c = d.color * d.hdr
            rows.append((x, y, size * d.aspect / 2, size / 2, rot, d.yscale, c[0], c[1], c[2], max(0.0, a), d.shape))
        return rows

    def batches(self, uvs):
        """Частицы и декали по группам: {"under_alpha", "under_add", "air_alpha", "air_add"} → float32 [N, 14]."""
        n = self.n
        sl = slice(0, n)
        t = self.age[sl] / self.life[sl]
        size = self.s0[sl] + (self.s1[sl] - self.s0[sl]) * t
        speed = np.hypot(self.vx[sl], self.vy[sl])
        h = size / 2
        w = h * self.asp[sl] * (1 + self.stretch[sl] * speed / 100.0)
        a = self.a0[sl] + (self.a1[sl] - self.a0[sl]) * t
        fi = self.fadein[sl]
        a = np.where(fi > 0, a * np.clip(t / np.maximum(fi, 1e-3), 0, 1), a)
        col = (self.c0[sl] + (self.c1[sl] - self.c0[sl]) * t[:, None]) * self.hdr[sl, None]
        idx = self.shape[sl].astype(np.int32)
        fbn = self.fbn[sl]
        if fbn.any():
            loop = (self.f0[sl] + self.age[sl] * self.fps[sl]).astype(np.int32) % np.maximum(fbn, 1)
            once = np.minimum(fbn - 1, (t * fbn).astype(np.int32))
            idx = idx + np.where(fbn > 0, np.where(self.fps[sl] > 0, loop, once), 0)
        data = np.empty((n, FLOATS), np.float32)
        data[:, 0] = self.x[sl]
        data[:, 1] = self.y[sl]
        data[:, 2] = w
        data[:, 3] = h
        data[:, 4] = self.rot[sl]
        data[:, 5] = self.ys[sl]
        data[:, 6:9] = col
        data[:, 9] = np.clip(a, 0, 1)
        data[:, 10:14] = uvs[idx]
        add, under = self.add[sl], self.under[sl]
        out = {}
        for name, u_flag, a_flag in (("under_alpha", True, False), ("under_add", True, True),
                                     ("air_alpha", False, False), ("air_add", False, True)):
            part = data[(add == a_flag) & (under == u_flag)]
            rows = self._decal_rows(u_flag, a_flag)
            if rows:
                dr = np.array([r[:10] for r in rows], np.float32)
                uv = uvs[[r[10] for r in rows]]
                drows = np.concatenate([dr, uv], axis=1)
                # декали (круги, лучи) — под частицами в своём слое
                part = np.concatenate([drows, part])
            out[name] = np.ascontiguousarray(part, np.float32)
        return out

    def prop_rows(self, uvs, dims):
        """Модельки: float32 [N, 14] (формат частиц), uv — из атласа моделек."""
        rows = []
        for p in self.props:
            if p.idx < 0:
                continue
            w, h = dims[p.idx]
            gt = min(1.0, p.age / p.grow_time) if p.grow_time else 1.0
            s = p.scale * (p.grow[0] + (p.grow[1] - p.grow[0]) * _ease_out(gt))
            a = 1.0
            if p.dying is not None:
                a = max(0.0, 1 - (p.age - p.dying) / p.fade)
            elif p.alive_fn is None and p.life - p.age < p.fade:
                a = max(0.0, (p.life - p.age) / p.fade)
            u0, v0, u1, v1 = uvs[p.idx]
            if p.flip:
                u0, u1 = u1, u0
            rows.append((p.x, p.y, w * s / 2, h * s / 2, p.rot, 1.0, a, a, a, a, u0, v0, u1, v1))
        return np.array(rows, np.float32).reshape(-1, FLOATS)

    def sfx_rows(self):
        """Шейдерные эффекты: {"under_alpha", "under_add", "air_alpha", "air_add", "distort"} → float32 [N, 16]."""
        groups = {k: [] for k in GROUPS + ("distort",)}
        for s in self.sfx:
            x, y = _point(s.pos)
            t, a = self._alpha_of(s)
            if s.life is None:                       # «пока жив» — прогресс крутится, эффект держится
                t = min(1.0, s.age / 0.35) * 0.5
            g = s.grow[0] + (s.grow[1] - s.grow[0]) * _ease_out(t)
            w, h = s.size[0] * g / 2, s.size[1] * g / 2
            c = s.color * s.hdr
            row = (x, y, w, h, s.rot + s.spin * s.age, s.ys, c[0], c[1], c[2], max(0.0, a), t, s.seed, s.mode,
                   s.extra, s.age, 0.0)
            key = "distort" if s.distort else ("under_" if s.under else "air_") + ("add" if s.add else "alpha")
            groups[key].append(row)
        return {k: np.array(v, np.float32).reshape(-1, SFX_FLOATS) for k, v in groups.items()}

    def ribbon_verts(self):
        """Ленты: {"alpha", "add"} → float32 [вершины, 12], по 6 вершин на отрезок."""
        out = {"alpha": [], "add": []}
        for r in self.ribbons:
            pts = list(r.pts)
            head_t = r.age if r.stopped is None else r.stopped
            if r.stopped is None and not r.static:
                hx, hy = r.src(head_t)
                pts.append((hx, hy, head_t))
            if len(pts) < 2:
                continue
            p = np.array(pts, np.float32)
            xy = p[:, :2]
            u = np.clip((r.age - p[:, 2]) / r.life, 0, 1)
            if r.static:                              # молния: по длине — от начала к концу, гаснет целиком
                u = np.linspace(0, 0.2, len(p)).astype(np.float32) + min(1.0, r.age / r.life) * 0.8
            tang = np.gradient(xy, axis=0)
            ln = np.maximum(np.hypot(tang[:, 0], tang[:, 1]), 1e-4)
            nrm = np.stack([-tang[:, 1] / ln, tang[:, 0] / ln], 1)
            seg = np.hypot(*np.diff(xy, axis=0).T)
            dist = np.concatenate([[0], np.cumsum(seg)])
            length = dist[-1] - dist + 0.0         # расстояние от головы — для текстуры, бегущей по ленте
            wid = r.width * (1 - u) ** (0.5 * r.taper)
            head = np.clip((head_t - p[:, 2]) / 0.02 + 0.3, 0, 1)        # голова чуть сужается
            wid = wid * (1.0 if r.static else head)
            L = xy + nrm * (wid / 2)[:, None]
            R = xy - nrm * (wid / 2)[:, None]
            m = len(xy) - 1
            verts = np.zeros((m * 6, RIB_FLOATS), np.float32)

            def put(k, side, i, vv):
                pos = (L if side == 0 else R)[i]
                verts[k::6, 0:2] = pos
                verts[k::6, 2] = u[i]
                verts[k::6, 3] = vv
            i0, i1 = np.arange(m), np.arange(1, m + 1)
            put(0, 0, i0, 0.0)
            put(1, 1, i0, 1.0)
            put(2, 0, i1, 0.0)
            put(3, 1, i0, 1.0)
            put(4, 1, i1, 1.0)
            put(5, 0, i1, 0.0)
            # длина для шума по ленте: у каждой вершины — расстояние её точки от головы
            dl = np.stack([length[i0], length[i0], length[i1], length[i0], length[i1], length[i1]], 1).reshape(-1)
            c = r.color * r.hdr
            verts[:, 4:7] = c
            verts[:, 7] = 1.0
            verts[:, 8] = r.mode
            verts[:, 9] = r.seed
            verts[:, 10] = dl
            verts[:, 11] = r.age
            out["add" if r.add else "alpha"].append(verts)
        return {k: (np.concatenate(v) if v else np.zeros((0, RIB_FLOATS), np.float32)) for k, v in out.items()}

    def light_rows(self, uv):
        """Свет: float32 [N, 14] в формате частиц (круглое пятно uv «glow», сплющено по земле)."""
        rows = []
        for lt in list(self.lights) + self.frame_lights:
            x, y = _point(lt.pos)
            if lt.life:
                t = min(1.0, lt.age / lt.life)
                k = (1 - t) ** lt.curve
            else:
                k = 1.0
            k *= min(1.0, lt.age / max(0.01, lt.fadein)) if lt.fadein else 1.0
            if lt.dying is not None:
                k *= max(0.0, 1 - (lt.age - lt.dying) / lt.fade)
            if lt.flicker:
                wave = math.sin(self.time * 23 + lt.seed) * math.sin(self.time * 7.3 + lt.seed)
                k *= 1 - lt.flicker * (0.5 + 0.5 * wave)
            c = lt.color * lt.intensity * k
            rows.append((x, y, lt.radius, lt.radius, 0.0, 0.62, c[0], c[1], c[2], 1.0, *uv))
        return np.array(rows, np.float32).reshape(-1, FLOATS)

    # ---------- упрощённая отрисовка на CPU (без OpenGL: тесты, --cpu) ----------

    def draw_cpu(self, surf, textures, cache, offset=(0, 0), limit=2500, props=None):
        import pygame
        from ui.vfx_textures import NAMES, cpu_ids
        groups = self.batches(cpu_ids())
        if props:
            for p in self.props:
                img = props.get(p.name)
                if img is None:
                    continue
                img = pygame.transform.rotozoom(img, -math.degrees(p.rot), p.scale)
                surf.blit(img, (p.x - img.get_width() / 2 + offset[0], p.y - img.get_height() / 2 + offset[1]))
        for gname in GROUPS:
            rows, add = groups[gname], gname.endswith("add")
            for r in rows[:limit]:
                w, h = int(r[2] * 2), int(r[3] * 2 * r[5])
                if w < 1 or h < 1 or r[9] <= 0.02:
                    continue
                col = tuple(int(min(1.0, c) * 255) // 32 * 32 for c in r[6:9])
                lvl = int(r[9] * 8)
                key = (int(r[10]), min(w, 400) // 4, min(h, 400) // 4, col, lvl, int(math.degrees(r[4])) // 30 % 12)
                img = cache.get(key)
                if img is None:
                    shape = textures[NAMES[int(r[10])]]
                    img = pygame.transform.smoothscale(shape, (max(1, min(w, 400)), max(1, min(h, 400))))
                    if key[5]:
                        img = pygame.transform.rotate(img, -key[5] * 30)
                    img = img.copy()
                    k = lvl / 8
                    if add:
                        tinted = pygame.Surface(img.get_size())
                        tinted.fill((0, 0, 0))
                        mask = img.copy()
                        mask.fill((int(col[0] * k), int(col[1] * k), int(col[2] * k), 255),
                                  special_flags=pygame.BLEND_RGBA_MULT)
                        tinted.blit(mask, (0, 0))
                        img = tinted
                    else:
                        img.fill((*col, int(255 * k)), special_flags=pygame.BLEND_RGBA_MULT)
                    if len(cache) > 3000:
                        cache.clear()
                    cache[key] = img
                pos = (float(r[0]) - img.get_width() / 2 + offset[0], float(r[1]) - img.get_height() / 2 + offset[1])
                surf.blit(img, pos, special_flags=pygame.BLEND_RGB_ADD if add else 0)
