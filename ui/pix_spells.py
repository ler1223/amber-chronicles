"""Эталонные заклинания на живых частицах (ui/pixsim.py): снаряд-комета летит прямо, хвост остаётся в мире
и остывает; удар — не шар в воздухе, а столкновение: вспышка в точке контакта, брызги и осколки летят от
поверхности по ходу удара, падают на землю. Брызги огня летят на клетки площади и поджигают их там, где упали.

Координаты — клетки поля и высота (x, y, z): z = 0 — земля, ~0.45 — пояс фигурки, ~0.9 — голова.
"""
import math

import numpy as np

from ui import projection as P
from ui.pixsim import BOUNCE, DIE, STICK, Particles

G = 9.0                 # гравитация, клеток/с²
BODY = 0.45             # высота центра тела
FIRE_LIGHT = (255, 140, 50)
ICE_LIGHT = (140, 200, 255)


def _norm(v):
    d = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / d for c in v)


def screen(p):
    x, y, _ = P.project(*p)
    return x, y


class Spells:
    def __init__(self, pilot):
        self.pilot = pilot
        self.ps = Particles()
        self.rng = np.random.default_rng(9)
        self.emitters = []          # [(функция(dt) → False, когда закончила)]
        self.on_land = {}           # метка частицы → что сделать, когда упадёт
        self.hold = {}              # клетка → до какого времени не показывать её пламя (брызги ещё летят)
        self.unit_hold = {}         # юнит → то же для пламени на фигурке
        self._tag = 0

    def clear(self):
        self.ps.clear()
        self.emitters.clear()
        self.on_land.clear()
        self.hold.clear()
        self.unit_hold.clear()

    def update(self, dt):
        for tag, x, y in self.ps.update(dt):
            fn = self.on_land.pop(tag, None)
            if fn:
                fn(x, y)
        self.emitters = [e for e in self.emitters if e(dt) is not False]

    def hold_cells(self, cells, until, kind="fire"):
        """Клетки загорятся (замёрзнут) по прилёте — симуляция ставит опасность сразу; до тех пор её не показываем."""
        was = self.pilot.burning if kind == "fire" else self.pilot.icy
        for pos in cells:
            if pos not in was:                      # уже горела (замёрзла) до выстрела — пусть остаётся
                self.hold[pos] = max(self.hold.get(pos, -1.0), self.pilot.time + until)

    def release(self, pos):
        self.hold.pop(pos, None)
        for u in self.pilot.view.combat.units if self.pilot.view.combat else []:
            if u.cell == pos:
                self.unit_hold.pop(u.id, None)

    def hold_units(self, units, until):
        """Статус «огонь» ставится при касте — пламя на фигурке показываем, когда огонь до неё долетит."""
        for u in units:
            if u.id not in self.pilot.burning_units:
                self.unit_hold[u.id] = self.pilot.time + until

    def unit_held(self, u):
        return self.unit_hold.get(u.id, -1.0) > self.pilot.time

    def held(self, pos):
        return self.hold.get(pos, -1.0) > self.pilot.time

    def _new_tag(self, fn):
        self._tag = self._tag % 30000 + 1
        self.on_land[self._tag] = fn
        return self._tag

    def emitter(self, dur, fn):
        """fn(dt, доля 0..1) каждый шаг в течение dur секунд."""
        st = [0.0]

        def step(dt):
            st[0] += dt
            fn(dt, min(1.0, st[0] / dur))
            return st[0] < dur
        self.emitters.append(step)

    # ---------- точки ----------

    def unit_point(self, u, z=BODY):
        gx, gy = self.pilot.view.ground_pos(u)
        return gx, gy, z

    def hand(self, u, toward):
        """Откуда вылетает снаряд: чуть впереди героя к цели, на уровне груди."""
        gx, gy = self.pilot.view.ground_pos(u)
        dx, dy = toward[0] - gx, toward[1] - gy
        d = math.hypot(dx, dy) or 1.0
        return gx + dx / d * 0.25, gy + dy / d * 0.25, 0.55

    def contact(self, a, u):
        """Точка удара о цель: передняя сторона тела, обращённая к летящему снаряду."""
        bx, by, bz = self.unit_point(u)
        dx, dy = a[0] - bx, a[1] - by
        d = math.hypot(dx, dy) or 1.0
        return bx + dx / d * 0.18, by + dy / d * 0.18, bz

    # ---------- снаряд ----------

    def comet(self, a, b, kind, on_hit, speed=9.0, scale=1.0):
        """Снаряд a → b по прямой. kind: fire, fire_big (метеор), ice. on_hit(b, направление). Возвращает время."""
        d = math.dist(a, b)
        dur = max(0.08, d / speed)
        dirv = _norm(tuple(b[i] - a[i] for i in range(3)))
        st = [0.0]

        def at():
            f = min(1.0, st[0] / dur)
            return tuple(a[i] + (b[i] - a[i]) * f for i in range(3))
        X = self.pilot.fx
        ground = (lambda: P.project(at()[0], at()[1])[1])
        if kind == "ice_big":                   # ледяная глыба: гранёный кристалл, блик бежит по граням
            X.add("ice_core", lambda: screen(at()), ttl=dur, depth=ground, scale=scale)
        elif kind == "ice":
            sa, sb = screen(a), screen(b)
            rot = round(math.atan2(sb[1] - sa[1], sb[0] - sa[0]) / (math.pi / 4)) % 8
            X.add("shard", lambda: screen(at()), ttl=dur, depth=ground, scale=scale, rot=rot)
        else:
            X.add("core_big" if kind == "fire_big" else "core", lambda: screen(at()), ttl=dur, depth=ground,
                  scale=scale)
        acc = [0.0]

        def step(dt):
            st[0] += dt
            p = at()
            acc[0] += dt
            if kind in ("ice", "ice_big"):      # холодная дымка оседает за осколком, редкие искорки инея
                rate = 160 if kind == "ice_big" else 70
                n, acc[0] = int(acc[0] * rate), acc[0] - int(acc[0] * rate) / rate
                self.ps.spawn(n, p, tuple(-c * 0.4 for c in dirv), life=0.7, temp=0.35, cool=0.1, grav=0.5,
                              drag=3.0, size=1.0 * scale, grow=1.0, alpha=0.7, pal="ice", smoke="steam",
                              smoke_at=0.5, spread=0.25, jitter=0.03)
                self.ps.spawn(n // 3, p, tuple(-c * 0.2 for c in dirv), life=0.35, temp=0.9, cool=0.6, grav=1.0,
                              drag=2.0, pal="ice", smoke=None, spread=0.4)
            else:                               # хвост кометы: жар отрывается, всплывает, остывает до дыма
                big = kind == "fire_big"
                rate = 1100 if big else 420
                n, acc[0] = int(acc[0] * rate), acc[0] - int(acc[0] * rate) / rate
                # хвост кометы: у головы толстый и жёлтый (белое — только ядро), к концу тоньше, краснее, в дым
                self.ps.spawn(n, p, tuple(-c * 0.5 for c in dirv), life=0.8 if big else 0.5,
                              temp=0.85, cool=1.5 if big else 2.0, buoy=1.2, drag=4.0,
                              size=2.0 if big else 1.6 * scale, grow=-1.6 if big else -2.2 * scale, pal="fire",
                              smoke="dust",
                              smoke_at=0.2, spread=0.25 if big else 0.15, jitter=(0.09 if big else 0.05) * scale)
                self.ps.spawn(max(0, n // 6), p, tuple(-c * 1.5 for c in dirv), life=0.5, temp=0.9, cool=1.0,
                              grav=G * 0.6, drag=1.0, pal="fire", smoke=None, spread=1.2, land=DIE)
            if st[0] >= dur:
                on_hit(b, dirv)
                return False
            return True
        self.emitters.append(step)
        self.pilot._follow(at, ICE_LIGHT if kind.startswith("ice") else FIRE_LIGHT,
                           130 if kind in ("fire_big", "ice_big") else 80, dur)
        return dur

    def muzzle(self, a, b, kind, s=1.0):
        """Выстрел: вспышка у руки и короткий конус искр к цели — снаряд вырывается, а не появляется."""
        d = _norm(tuple(b[i] - a[i] for i in range(3)))
        fire = kind != "ice"
        pal = "fire" if fire else "ice"
        self.ps.spawn(int(18 * s), a, life=0.06, temp=1.0, cool=0.0, size=1.4 * s, pal=pal, smoke=None, jitter=0.06)
        v = self._hemi(int(16 * s), d, 0.0)
        v = v * 0.4 + np.array(d) * 0.6
        sp = self.rng.uniform(3, 7, len(v))
        self.ps.spawn(len(v), a, (v[:, 0] * sp, v[:, 1] * sp, v[:, 2] * sp), life=0.14, temp=1.0, cool=3.0, drag=6.0,
                      pal=pal, smoke=None, streak=0.03, life_var=0.3)
        if fire:
            self._smoke(a, int(5 * s), life=0.9, buoy=0.8, size=1.2)
        self.pilot._light(screen(a), FIRE_LIGHT if fire else ICE_LIGHT, 90 * s, 1.2, 0.15)

    # ---------- огонь ----------

    def _flash(self, p, pal="fire", n=16, size=1.6):
        """Кадр удара: белое ядро в точке контакта — 1–2 кадра."""
        self.ps.spawn(n, p, life=0.07, temp=1.0, cool=0.0, size=size, pal=pal, smoke=None, spread=0.7,
                      jitter=0.04, life_var=0.2)

    def _flame_lick(self, x, y, n=16, h=1.0):
        """Пламя занялось на земле: языки поднимаются из точки и гаснут дымом."""
        self.ps.spawn(n, (x, y, 0.02), (0, 0, 0.4 * h), life=0.5 * h, temp=0.95, cool=2.0, buoy=2.2 * h, drag=3.0,
                      size=1.0, pal="fire", smoke="dust", smoke_at=0.15, spread=0.2, jitter=0.15, tall=1.5)

    def _smoke(self, p, n, life=1.4, buoy=1.0, size=1.6, spread=0.35):
        self.ps.spawn(n, p, (0, 0, 0.3), life=life, temp=0.0, cool=0.0, buoy=buoy, drag=1.8, size=size, grow=1.6,
                      alpha=0.85, pal="fire", smoke="dust", smoke_at=1.0, spread=spread, jitter=0.1)

    def _ignite(self, src, cells, flight=0.12):
        """Раскалённые осколки удара летят на клетки площади быстро и почти прямо (штрихами); где упали —
        занимается пламя (на воде — шипит паром, на лаве — плюхается, на льду — пар). Возвращает точки падения —
        они войдут в общий след удара (ui/pixmarks.py), а не оставят каждая свою отметину."""
        pil = self.pilot
        targets = []
        for (cx, cy), pos in cells:
            dist = math.hypot(cx - src[0], cy - src[1])
            T = flight + 0.05 * dist
            self.hold[pos] = pil.time + T + 0.4
            k = 3
            tx = cx + self.rng.normal(0, 0.15, k)
            ty = cy + self.rng.normal(0, 0.15, k)
            targets.append((float(tx.mean()), float(ty.mean())))

            def land(x, y, pos=pos):
                self.release(pos)
                kind = self.terrain_at(np.array([x]), np.array([y]))[0]
                if kind == "water":
                    self._splash(x, y, 0.5, steam=True)
                elif kind == "lava":
                    self._lava_plop(x, y)
                else:
                    self._flame_lick(x, y, 12, 0.8)
                    if kind == "ice_floor":
                        self._steam((x, y, 0.05), 6)
            tag = self._new_tag(land)
            vx = (tx - src[0]) / T
            vy = (ty - src[1]) / T
            vz = (0 - src[2] + 0.5 * G * T * T) / T
            self.ps.spawn(k, src, (vx, vy, np.full(k, vz)), life=T + 0.3, temp=1.0, cool=0.6, grav=G, size=1.2,
                          pal="fire", smoke=None, land=STICK, tag=tag, life_var=0.0, streak=0.025)
        return targets

    # ---------- поверхности: что под ударом ----------

    def terrain_at(self, xs, ys):
        """Рельеф под точками (клетки поля): grass, stone, water, lava, ice_floor, chasm; за доской — ground."""
        c = self.pilot.view.combat
        out = np.full(len(xs), "ground", dtype="U10")
        if c is None:
            return out
        g = c.grid
        names = np.array([[g.cells[(x, y)].terrain if (x, y) in g.cells else "ground" for x in range(g.w)]
                          for y in range(g.h)], dtype="U10")
        xi, yi = np.floor(xs).astype(int), np.floor(ys).astype(int)
        ok = (xi >= 0) & (xi < g.w) & (yi >= 0) & (yi < g.h)
        out[ok] = names[yi[ok], xi[ok]]
        return out

    def _steam(self, p, n, spread=0.35):
        self.ps.spawn(n, p, (0, 0, 0.5), life=1.4, temp=0.0, buoy=1.2, drag=2.0, size=1.6, grow=1.6, alpha=0.75,
                      pal="steam", smoke="steam", smoke_at=1.0, spread=spread, jitter=0.1)

    def _splash(self, x, y, s, steam=False):
        """Вода приняла удар: столб брызг, капли падают обратно, по воде расходятся круги; огонь — шипит паром.
        На воде следов не остаётся."""
        n = int(40 * s)
        self.ps.spawn(n, (x, y, 0.02), (0, 0, 3.5 * (0.6 + 0.4 * s)), life=1.3, temp=self.rng.uniform(0.45, 1.0, n),
                      cool=0.0, grav=G, drag=0.3, size=1.0, pal="water", smoke=None, spread=1.1 * s, land=DIE)
        for k, sp in ((60, 1.3), (40, 0.75)):   # круги по воде
            k = int(k * (0.5 + 0.5 * s))
            a = self.rng.uniform(0, math.tau, k)
            self.ps.spawn(k, (x + np.cos(a) * 0.1, y + np.sin(a) * 0.1, np.full(k, 0.01)),
                          (np.cos(a) * sp * (0.6 + 0.6 * s), np.sin(a) * sp * (0.6 + 0.6 * s), np.zeros(k)),
                          life=1.0, temp=0.85, cool=0.5, drag=1.2, size=1.0, pal="water", smoke=None, life_var=0.15)
        if steam:
            self._steam((x, y, 0.1), int(14 * s), 0.4 * s)

    def _lava_plop(self, x, y):
        """Лава приняла удар: тяжёлый плюх раскалённых капель, без следа."""
        self.ps.spawn(10, (x, y, 0.02), (0, 0, 2.2), life=0.9, temp=self.rng.uniform(0.6, 0.95, 10), cool=0.5,
                      grav=G, size=1.3, pal="fire", smoke=None, spread=0.8, land=DIE)

    def scorch_mark(self, x, y, R, dirv, embers=(), crater=0.35, smooth=False):
        """Один след на весь удар (ui/pixmarks.py): воронка, копоть, лучи выброса, пятна от осколков."""
        from ui.pixmarks import scar
        self._tag_seed = getattr(self, "_tag_seed", 0) + 1
        m = scar(x, y, R, self.terrain_at, dirv[:2], embers, seed=self._tag_seed, crater=crater, smooth=smooth)
        if m is not None:
            self.pilot.view.marks.stamp_surface(m[0], *m[1])

    def sparks(self, p, fire=True, n=8):
        """Попадание огнём или льдом (атака, удар): горсть искр или ледяной крошки от тела."""
        if fire:
            self.ps.spawn(n, p, (0, 0, 1.2), life=0.45, temp=0.95, cool=1.4, grav=G * 0.7, drag=1.0, pal="fire",
                          smoke=None, spread=1.6, land=DIE)
        else:
            self.ps.spawn(n, p, (0, 0, 1.0), life=0.8, temp=0.8, cool=0.0, grav=G, bounce=0.3, pal="ice", smoke=None,
                          spread=1.4, land=BOUNCE)

    def catch_fire(self, u):
        """Юнит загорелся: жар вспыхивает по телу снизу вверх."""
        x, y, _ = self.unit_point(u)
        self.ps.spawn(14, (x, y, 0.2), (0, 0, 0.8), life=0.45, temp=1.0, cool=2.0, buoy=2.0, drag=2.5, size=1.1,
                      pal="fire", smoke="dust", smoke_at=0.2, spread=0.3, jitter=0.12)

    def _hemi(self, n, normal, lift=0.2):
        """n направлений полусферой вокруг нормали поверхности (разлёт от того, во что попали)."""
        v = self.rng.normal(0, 1, (n, 3))
        v /= np.linalg.norm(v, axis=1, keepdims=True) + 1e-9
        nv = np.array(normal, float)
        v[v @ nv < 0] *= -1
        v += nv * 0.35 + np.array([0.0, 0.0, lift])
        return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)

    def _burst(self, p, normal, s=1.0, wet=False):
        """Удар как разрыв боевой части: вспышка, расширяющаяся раскалённая оболочка, осколки-искры с огромной
        скоростью (штрихами), огненный клуб — вырывается, тормозит, всплывает и коптит; кольцо ударной волны
        вокруг точки удара, тёмный дым, угли. normal — от поверхности (от цели к стрелку, от земли вверх).
        s — масштаб навыка (класс S/M/L/XL, art_style.md, раздел 6): размеры ~ s, количество ~ s^1.5."""
        ps, r = self.ps, self.rng
        q = s ** 1.5
        z = min(s, 1.6)                          # крупнее удар — больше частиц, а не крупнее пиксели
        smoke = "steam" if wet else "dust"       # над водой не копоть, а пар
        ps.spawn(int(50 * q), p, life=0.08, temp=1.0, cool=0.0, size=1.8 * z, pal="fire", smoke=None,
                 jitter=0.14 * s, life_var=0.3)
        n = int(40 * q)                          # раскалённая оболочка: белая, расширяется за пару кадров
        v = self._hemi(n, normal, 0.1)
        sp = 3.2 * s
        ps.spawn(n, p, (v[:, 0] * sp, v[:, 1] * sp, v[:, 2] * sp), life=0.13, temp=1.0, cool=1.8, drag=14.0,
                 size=1.7 * z, pal="fire", smoke=None, life_var=0.2)
        n = int(60 * q)                          # осколки: очень быстрые, белое → жёлтое → оранжевое
        v = self._hemi(n, normal)
        sp = r.uniform(8, 16, n) * (0.7 + 0.3 * s)
        ps.spawn(n, p, (v[:, 0] * sp, v[:, 1] * sp, v[:, 2] * sp), life=r.uniform(0.12, 0.32, n), temp=1.0, cool=3.0,
                 drag=5.0, grav=4.0, size=1.0 + 0.2 * z, pal="fire", smoke=None, streak=0.045, life_var=0.0)
        n = int(70 * q)                          # огненный клуб: крупный, тормозит, всплывает, уходит в копоть
        v = self._hemi(n, normal, 0.35)
        sp = r.uniform(2.0, 5.5, n) * (0.55 + 0.45 * s)
        ps.spawn(n, p, (v[:, 0] * sp, v[:, 1] * sp, v[:, 2] * sp), life=0.7, temp=1.0, cool=1.7, drag=7.0,
                 buoy=2.2, size=1.8 * z, grow=1.2, pal="fire", smoke=smoke, smoke_at=0.25, life_var=0.3)
        nv = np.array(normal, float)             # ударная волна — кольцо в плоскости поверхности
        u1 = np.cross(nv, [0.0, 0.0, 1.0]) if abs(nv[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        u1 /= np.linalg.norm(u1)
        u2 = np.cross(nv, u1)
        n = int(44 * s)
        a = r.uniform(0, np.pi * 2, n)
        d = np.outer(np.cos(a), u1) + np.outer(np.sin(a), u2)
        ps.spawn(n, p, (d[:, 0] * 7 * s, d[:, 1] * 7 * s, d[:, 2] * 7 * s), life=0.16, temp=0.9, cool=3.0,
                 drag=12.0, size=1.2 * z, pal="fire", smoke=None, life_var=0.2)
        if wet:
            self._steam(p, int(24 * q), 0.4 * s)
        else:
            self._smoke(p, int(20 * q), life=1.9, buoy=0.9, size=1.8 * z, spread=0.35 * s)
        n = int(14 * s)                          # угли падают и тлеют на земле
        v = self._hemi(n, normal, 0.5)
        sp = r.uniform(1.5, 3.5, n) * s
        ps.spawn(n, p, (v[:, 0] * sp, v[:, 1] * sp, v[:, 2] * sp), life=1.4, temp=0.9, cool=0.6, grav=G, drag=0.5,
                 pal="fire", smoke=None, land=STICK)

    def _ground_wave(self, x, y, R, s, dur=0.3):
        """Огонь стелется по земле до края площади, из фронта поднимаются языки; пыль ударной волны —
        впереди огня."""
        n = int(40 * s + 25 * R)
        ang = self.rng.uniform(0, math.tau, n)
        sp = 4.5 * (R + 0.6)
        wet = self.terrain_at(x + np.cos(ang) * 0.6 * R, y + np.sin(ang) * 0.6 * R) == "water"
        for m, pal, alpha in ((~wet, "dust", 0.55), (wet, "water", 0.8)):   # над водой волна гонит брызги
            k = int(m.sum())
            if k:
                self.ps.spawn(k, (x, y, 0.05), (np.cos(ang[m]) * sp, np.sin(ang[m]) * sp, np.full(k, 0.3)),
                              life=0.75, temp=0.0 if pal == "dust" else 0.8, cool=0.6, drag=3.5, size=1.2 * min(s, 1.6),
                              grow=1.0, alpha=alpha, pal=pal, smoke="dust" if pal == "dust" else None,
                              smoke_at=1.0, spread=0.3)

        def wave(dt, f):
            r = R * (1 - (1 - f) ** 2)
            k = int(dt * (260 + 300 * R) * s * (1 - f * 0.5)) + 1
            a = self.rng.uniform(0, math.tau, k)
            rr = r * self.rng.uniform(0.75, 1.0, k)
            px, py = x + np.cos(a) * rr, y + np.sin(a) * rr
            wet = self.terrain_at(px, py) == "water"
            dry = ~wet
            m = int(dry.sum())
            if m:                                   # по земле огонь стелется, языки из фронта
                self.ps.spawn(m, (px[dry], py[dry], np.full(m, 0.02)),
                              (np.cos(a[dry]) * 1.4, np.sin(a[dry]) * 1.4, np.full(m, 0.7)), life=0.6,
                              temp=self.rng.uniform(0.62, 0.86, m), cool=1.5,
                              buoy=2.0, drag=2.4, size=1.4 * min(s, 1.6), grow=-0.6, tall=1.2, pal="fire", smoke="dust",
                              smoke_at=0.2, spread=0.25)
            m = int(wet.sum()) // 2
            if m:                                   # по воде огонь не горит — шипит паром
                self.ps.spawn(m, (px[wet][:m], py[wet][:m], np.full(m, 0.05)), (0, 0, 0.5), life=1.2, temp=0.0,
                              buoy=1.1, drag=2.0, size=1.5 * min(s, 1.6), grow=1.4, alpha=0.7, pal="steam", smoke="steam",
                              smoke_at=1.0, spread=0.3)
        self.emitter(dur, wave)

    def _impact_fx(self, p, s, big=False):
        """Сила удара для глаза: свет на поле, тряска, стоп-кадр, вспышка экрана, толчок камеры к точке удара."""
        sp = screen(p)
        self.pilot._light((sp[0], sp[1] - 10), FIRE_LIGHT, 150 + 110 * s, 1.6 + 0.4 * s, 0.35 + 0.1 * s)
        self.pilot.view.vfx.screen_fx(shake=3 + 3.5 * s, hitstop=0.03 + 0.02 * s, flash=0.05 + 0.06 * s,
                                      color=FIRE_LIGHT, zoom=1.0 + 0.012 * s, zoom_time=0.18, center=sp,
                                      aberration=0.15 * s if big else 0.0)

    def fire_hit_unit(self, p, dirv, area=(), scale=1.0, radius=0):
        """Огненный снаряд врезался в цель: разрыв на теле (разлёт — от цели к стрелку и в стороны). С площадью —
        огонь стелется по земле до края площади, раскалённые осколки летят на клетки и поджигают их."""
        s = scale * (1 + 0.6 * radius)
        wet = self.terrain_at(np.array([p[0]]), np.array([p[1]]))[0] == "water"
        self._burst(p, (-dirv[0], -dirv[1], max(0.0, -dirv[2])), s, wet)
        if radius:
            self._ground_wave(p[0], p[1], radius + 0.45, s)
        embers = self._ignite(p, area) if area else []
        if wet:
            self._splash(p[0], p[1], 0.6 * s, steam=True)        # цель стоит в воде — вода отвечает на удар
        # один след на весь удар: под целью и до мест, куда упали осколки
        self.scorch_mark(p[0], p[1], (radius + 0.55) if radius else 0.45 * scale, dirv, embers, crater=0.0)
        self._impact_fx(p, s)

    def fire_hit_ground(self, p, dirv, area=(), big=False, radius=0):
        """Удар в землю: разрыв вверх от земли, огонь и пыль стелются до края площади, комья по дугам,
        воронка-подпалина; у метеора ещё раскалённые обломки и столб дыма."""
        x, y = p[0], p[1]
        self.release((int(x), int(y)))           # клетка удара и кто на ней — вспыхивают сейчас
        s = (2.0 if big else 1.15) * (1 + 0.35 * radius)
        wet = self.terrain_at(np.array([x]), np.array([y]))[0] == "water"
        self._burst((x, y, 0.08), (0.0, 0.0, 1.0), s, wet)
        self._ground_wave(x, y, radius + 0.5 + (0.4 if big else 0.0), s, 0.4 if big else 0.3)
        if wet:                                  # в воду: столб воды и пара, круги, без воронки и комьев
            self._splash(x, y, s, steam=True)
            embers = self._ignite((x, y, 0.15), area) if area else []
            self.scorch_mark(x, y, radius + 0.6 + (0.5 if big else 0.0), dirv, embers,
                             crater=0.45 if big else 0.3)
            self._impact_fx((x, y, 0.3), s, big)
            return
        n = int(16 * s)                          # комья земли и камни по дугам
        ang = self.rng.uniform(0, math.tau, n)
        sp = self.rng.uniform(1.0, 3.0, n) * (0.7 + 0.3 * s)
        self.ps.spawn(n, (x, y, 0.05), (np.cos(ang) * sp, np.sin(ang) * sp, self.rng.uniform(2.5, 5.5, n)), life=1.6,
                      temp=0.55, cool=0.0, grav=G * 1.3, bounce=0.3, size=1.0, pal="dust", smoke=None, land=BOUNCE)
        if big:
            n = 26                               # раскалённые обломки метеора
            ang = self.rng.uniform(0, math.tau, n)
            sp = self.rng.uniform(1.5, 4.0, n)
            self.ps.spawn(n, (x, y, 0.1), (np.cos(ang) * sp, np.sin(ang) * sp, self.rng.uniform(3, 7, n)), life=2.0,
                          temp=1.0, cool=0.4, grav=G * 1.2, bounce=0.25, size=1.5, pal="fire", smoke="dust",
                          smoke_at=0.15, land=BOUNCE)

            def column(dt, f):                   # гриб: столб дыма поднимается над воронкой
                self._smoke((x, y, 0.2 + f * 0.6), int(dt * 140) + 1, life=2.2, buoy=1.6, size=2.6, spread=0.4)
            self.emitter(1.1, column)
        embers = self._ignite((x, y, 0.15), area) if area else []
        self.scorch_mark(x, y, radius + 0.6 + (0.5 if big else 0.0), dirv, embers, crater=0.45 if big else 0.3)
        self._impact_fx((x, y, 0.3), s, big)

    # ---------- лёд ----------

    def _mist(self, p, n, out=0.6, life=1.2):
        """Холодный пар: оседает и расползается по земле."""
        self.ps.spawn(n, p, (0, 0, -0.2), life=life, temp=0.35, cool=0.0, grav=0.4, drag=2.0, size=1.4, grow=1.4,
                      alpha=0.65, pal="ice", smoke="steam", smoke_at=0.5, spread=out, jitter=0.08)

    def _shards(self, p, dirv, n, forward=True, speed=(1.0, 3.0)):
        d = dirv if forward else tuple(-c for c in dirv)
        sp = self.rng.uniform(*speed, n)
        self.ps.spawn(n, p, (d[0] * sp, d[1] * sp, self.rng.uniform(0.5, 2.4, n)), life=1.5, temp=self.rng.uniform(
            0.45, 1.0, n), cool=0.0, grav=G * 1.1, drag=0.4, bounce=0.35, size=1.0, pal="ice", smoke=None,
            spread=1.0, land=BOUNCE)

    def ice_hit_unit(self, p, dirv, u=None, scale=1.0, radius=0):
        """Осколок врезался: раскалывается по ходу удара, кристалл растёт из точки контакта, пар оседает."""
        s = scale * (1 + 0.5 * radius)
        q = s ** 1.5
        self._flash(p, "ice", n=int(30 * q), size=1.6 * s)
        self._shards(p, dirv, int(40 * q), speed=(1.5, 4.0 * (0.7 + 0.3 * s)))
        self._shards(p, dirv, int(14 * q), forward=False, speed=(0.8, 2.2))
        n = int(30 * q)                          # ледяная крошка — быстрые штрихи по ходу удара
        v = self._hemi(n, dirv, 0.2)
        sp = self.rng.uniform(6, 12, n)
        self.ps.spawn(n, p, (v[:, 0] * sp, v[:, 1] * sp, v[:, 2] * sp), life=self.rng.uniform(0.1, 0.25, n),
                      temp=0.95, cool=2.0, drag=5.0, grav=3.0, pal="ice", smoke=None, streak=0.04, life_var=0.0)
        self._mist(p, int(26 * q), out=0.6 * s)
        # кристалл растёт из точки контакта на теле, а не висит в воздухе посреди клетки
        self.pilot.fx.add("bloom_m" if s > 1.2 else "bloom_s", screen(p), depth=P.project(p[0], p[1])[1] + 1,
                          scale=0.9 * s)
        sp = screen(p)
        self.pilot._light(sp, ICE_LIGHT, 120 + 80 * s, 1.2 + 0.3 * s, 0.5)
        self.pilot.view.vfx.screen_fx(shake=2 + 2.5 * s, hitstop=0.02 + 0.015 * s, flash=0.04 * s,
                                      color=ICE_LIGHT, zoom=1.0 + 0.008 * s, zoom_time=0.15, center=sp)

    def ice_hit_ground(self, p, dirv, area=()):
        """Лёд в землю: раскол в точке удара, иней и шипы растут по земле волной от точки удара,
        холодный пар растекается по земле до края площади."""
        x, y = p[0], p[1]
        for _, pos in area:
            self.release(pos)
        R = max([math.hypot(cx - x, cy - y) for (cx, cy), _ in area] or [0.5])
        s = 1.2 + 0.4 * R
        self._flash((x, y, 0.1), "ice", n=int(30 * s), size=1.8 * s)
        self._shards((x, y, 0.1), dirv, int(30 * s), speed=(1.0, 3.2))
        n = int(70 * s)
        ang = self.rng.uniform(0, math.tau, n)
        sp = 2.4 * (R + 0.5)
        self.ps.spawn(n, (x, y, 0.05), (np.cos(ang) * sp, np.sin(ang) * sp, np.zeros(n)), life=1.6, temp=0.35,
                      grav=0.2, drag=2.2, size=1.7, grow=1.4, alpha=0.6, pal="ice", smoke="steam", smoke_at=0.5,
                      spread=0.3)
        pil = self.pilot
        for (cx, cy), pos in area or [((x, y), None)]:
            d = math.hypot(cx - x, cy - y)
            delay = 0.03 + d * 0.1
            gp = screen((cx, cy, 0))
            pil._at("spikes_big" if d < 0.3 else "spikes", gp, anchor="bottom", delay=delay, scale=1.0 + 0.15 * s)
            pil._frost(gp, delay=delay)
        sp = screen(p)
        pil._light((sp[0], sp[1] - 16), ICE_LIGHT, 160 + 60 * s, 1.3, 0.7)
        pil.view.vfx.screen_fx(shake=3 + 2 * s, hitstop=0.03, flash=0.05, color=ICE_LIGHT)

    # ---------- лёд по площади (пилот: Буран) ----------

    def big_snowflake(self, x, y, R):
        """Одна большая снежинка на всё заклинание: лежит на земле в центре, вырастает и раскалывается."""
        last = getattr(self, "_flake", None)
        if last and self.pilot.time - last[0] < 0.6 and math.hypot(x - last[1], y - last[2]) < 1.0:
            return                               # то же заклинание (удар + рельеф) — снежинка уже есть
        self._flake = (self.pilot.time, x, y)
        self.pilot.fx.add("bloom_l", P.ground_to_flat(x, y), ground=True, scale=max(0.6, 2 * R / 2.6), alpha=230)

    def _frost_burst(self, p, s):
        """Морозный разрыв у земли: вспышка, белая оболочка холода, ледяная крошка штрихами вверх и в стороны,
        куски льда скачут по земле, тяжёлый холодный пар оседает."""
        ps, r = self.ps, self.rng
        q, z = s ** 1.5, min(s, 1.6)
        ps.spawn(int(40 * q), p, life=0.08, temp=1.0, cool=0.0, size=1.8 * z, pal="ice", smoke=None,
                 jitter=0.13 * s, life_var=0.3)
        n = int(36 * q)
        v = self._hemi(n, (0.0, 0.0, 1.0), 0.0)
        ps.spawn(n, p, (v[:, 0] * 3 * s, v[:, 1] * 3 * s, v[:, 2] * 3 * s), life=0.13, temp=1.0, cool=1.5,
                 drag=14.0, size=1.6 * z, pal="ice", smoke=None, life_var=0.2)
        n = int(60 * q)
        v = self._hemi(n, (0.0, 0.0, 1.0), -0.15)
        sp = r.uniform(7, 14, n) * (0.7 + 0.3 * s)
        ps.spawn(n, p, (v[:, 0] * sp, v[:, 1] * sp, v[:, 2] * sp), life=r.uniform(0.14, 0.32, n),
                 temp=r.uniform(0.6, 1.0, n), cool=1.5, drag=5.0, grav=6.0, size=1.0 + 0.2 * z, pal="ice", smoke=None,
                 streak=0.045, life_var=0.0)
        n = int(26 * q)
        a = r.uniform(0, np.pi * 2, n)
        sp = r.uniform(1.0, 3.2, n) * (0.7 + 0.3 * s)
        ps.spawn(n, p, (np.cos(a) * sp, np.sin(a) * sp, r.uniform(1.0, 3.0, n)), life=1.6, temp=r.uniform(0.45, 1.0, n),
                 cool=0.0, grav=G * 1.1, drag=0.4, bounce=0.35, size=1.0 + 0.3 * z, pal="ice", smoke=None, land=BOUNCE)
        self.ps.spawn(int(30 * q), p, (0, 0, 0.3), life=1.8, temp=0.0, grav=0.3, drag=2.0, size=1.6 * z, grow=1.5,
                      alpha=0.7, pal="steam", smoke="steam", smoke_at=1.0, spread=0.9 * s, jitter=0.1)

    def _frost_wave(self, x, y, R, s, dur=0.4):
        """Мороз ползёт по земле до края площади: фронт оставляет ледяные кристаллы, холодный пар катится
        впереди и оседает; над лавой мороз не берёт — только пар."""
        n = int(50 * s + 30 * R)
        a = self.rng.uniform(0, math.tau, n)
        sp = 2.4 * (R + 0.5)
        self.ps.spawn(n, (x, y, 0.05), (np.cos(a) * sp, np.sin(a) * sp, np.zeros(n)), life=1.6, temp=0.0, grav=0.2,
                      drag=2.4, size=1.4 * min(s, 1.6), grow=1.4, alpha=0.6, pal="steam", smoke="steam", smoke_at=1.0,
                      spread=0.3)

        def wave(dt, f):
            rr = R * (1 - (1 - f) ** 2) * self.rng.uniform(0.85, 1.0, 1)[0]
            k = int(dt * (140 + 120 * R) * s) + 1
            a = self.rng.uniform(0, math.tau, k)
            px, py = x + np.cos(a) * rr * self.rng.uniform(0.9, 1.0, k), y + np.sin(a) * rr
            ter = self.terrain_at(px, py)
            ok = ~np.isin(ter, ["lava", "chasm"])
            m = int(ok.sum())
            if m:                                # кристаллы инея ложатся там, где прошёл фронт, и искрятся
                self.ps.spawn(m, (px[ok], py[ok], np.zeros(m)), life=self.rng.uniform(0.6, 1.4, m),
                              temp=self.rng.uniform(0.55, 1.0, m), cool=0.0, size=1.0, pal="ice", smoke=None,
                              land=STICK, life_var=0.0)
            hot = ter == "lava"
            m = int(hot.sum())
            if m:
                self._steam((float(px[hot].mean()), float(py[hot].mean()), 0.05), m)
        self.emitter(dur, wave)

    def _ice_spikes(self, x, y, R, s):
        """Шипы прорастают в случайных точках площади (не по клеткам), волной от точки удара; крупные — у центра."""
        k = int(4 + 3.5 * R * R)
        rad = np.sqrt(self.rng.random(k)) * R
        ang = self.rng.uniform(0, math.tau, k)
        px, py = x + np.cos(ang) * rad, y + np.sin(ang) * rad
        ter = self.terrain_at(px, py)
        for i in np.argsort(rad):
            if ter[i] in ("lava", "chasm"):
                continue
            d = float(rad[i])
            big = d < 0.35 * R
            self.pilot._at("spikes_big" if big else "spikes", screen((float(px[i]), float(py[i]), 0.0)),
                           anchor="bottom", delay=0.04 + d * 0.13, scale=(0.75 + 0.35 * self.rng.random()) * min(s, 1.4))

    def _flurry(self, x, y, R, dur=1.4):
        """Буран: снег крутит над площадью и сыплется ветром наискось."""
        def snow(dt, f):
            k = int(dt * 140 * (R + 0.5) * (1 - f * 0.6)) + 1
            a = self.rng.uniform(0, math.tau, k)
            rad = np.sqrt(self.rng.random(k)) * (R + 0.4)
            self.ps.spawn(k, (x + np.cos(a) * rad - 0.5, y + np.sin(a) * rad, self.rng.uniform(1.0, 1.8, k)),
                          (1.6, 0.4, -1.4), life=1.1, temp=self.rng.uniform(0.7, 1.0, k), cool=0.0, drag=0.5,
                          size=1.0, pal="ice", smoke=None, spread=0.5, land=DIE)
        self.emitter(dur, snow)

    def ice_hit_area(self, p, dirv, area=(), radius=1, scale=1.0, burst=True):
        """Ледяная глыба врезалась в землю: морозный разрыв, мороз ползёт по земле до края площади, шипы
        прорастают, буран крутит снег; один морозный след на весь удар (иней на земле, корка на воде) — тает."""
        x, y = p[0], p[1]
        for _, pos in area:
            self.release(pos)
        self.release((int(x), int(y)))
        R = radius + 0.5
        s = 1.2 * (1 + 0.35 * radius) * scale
        if burst:
            self._frost_burst((x, y, 0.1), s)
        else:                                    # шквал: удар — мягче, без белой оболочки
            self._flash((x, y, 0.1), "ice", n=int(20 * s), size=1.6)
            self._shards((x, y, 0.1), dirv, int(24 * s), speed=(0.8, 2.6))
        self.big_snowflake(x, y, R)
        self._frost_wave(x, y, R, s)
        self._ice_spikes(x, y, R, s)
        self._flurry(x, y, R)
        from ui.pixmarks import scar
        self._tag_seed = getattr(self, "_tag_seed", 0) + 1
        m = scar(x, y, R + 0.1, self.terrain_at, dirv[:2], (), seed=self._tag_seed, crater=0.0, style="frost")
        if m is not None:
            self.pilot.fx.add_surface(m[0], m[1], ttl=8.0, fade=3.0)
        sp = screen(p)
        self.pilot._light((sp[0], sp[1] - 16), ICE_LIGHT, 160 + 90 * s, 1.4 + 0.3 * s, 0.6)
        self.pilot.view.vfx.screen_fx(shake=3 + 3 * s, hitstop=0.03 + 0.015 * s, flash=0.05 + 0.04 * s,
                                      color=ICE_LIGHT, zoom=1.0 + 0.01 * s, zoom_time=0.18, center=sp)

    # ---------- Буран: туча и шквал ----------

    def storm_cloud(self, x, y, R, alive):
        """Каст Бурана: над площадью сгущается снежная туча (клубы стягиваются к центру и крутятся), на земле
        под ней — тень. Живёт, пока идёт каст."""
        pil = self.pilot

        def cloud(dt, f):
            if not alive():
                return
            k = int(dt * 90 * (R + 0.6)) + 1
            a = self.rng.uniform(0, math.tau, k)
            rad = (R + 0.6) * np.sqrt(self.rng.random(k))
            px, py = x + np.cos(a) * rad, y + np.sin(a) * rad * 0.8
            vx, vy = -np.sin(a) * 0.9 - np.cos(a) * 0.3, np.cos(a) * 0.9 - np.sin(a) * 0.3    # вихрь к центру
            self.ps.spawn(k * 2, (np.repeat(px, 2), np.repeat(py, 2), self.rng.uniform(1.7, 2.2, k * 2)),
                          (np.repeat(vx, 2), np.repeat(vy, 2), np.zeros(k * 2)), life=1.1, temp=0.0,
                          drag=0.6, size=2.6, grow=1.2, alpha=0.9, pal="steam", smoke="steam", smoke_at=1.0,
                          jitter=0.08)
            k = int(dt * 25) + 1                 # первые снежинки срываются вниз
            self.ps.spawn(k, (x + self.rng.normal(0, R * 0.6, k), y + self.rng.normal(0, R * 0.5, k),
                              np.full(k, 2.3)), (0.8, 0.2, -1.6), life=1.2, temp=0.9, drag=0.4, pal="ice",
                          smoke=None, spread=0.3, land=DIE)
        shade = pil.fx.add_surface(self._shade(R + 0.6), P.ground_to_flat(x, y), ttl=60.0, fade=0.6)

        def step(dt):
            if alive():
                cloud(dt, 0.0)
                return True
            shade.ttl = shade.age + 0.9          # туча прорвалась шквалом — тень ещё чуть держится и тает
            return False
        self.emitters.append(step)

    def _shade(self, R):
        """Тень тучи на земле: тёмный круг с дизерингом, гуще к центру."""
        from ui.pixfx_sim import BAYER
        n = int(R * 2 * 32)
        ys, xs = np.mgrid[0:n, 0:n]
        d = np.hypot(xs - n / 2, (ys - n / 2)) / (n / 2)
        a = np.clip(1 - d, 0, 1) * 0.55
        th = np.tile(BAYER, (n // 4 + 1, n // 4 + 1))[:n, :n]
        rgba = np.zeros((n, n, 4), np.uint8)
        rgba[..., :3] = (20, 26, 40)
        rgba[..., 3] = np.where(a > th, 130, 0)
        import pygame
        surf = pygame.image.frombuffer(np.ascontiguousarray(rgba).tobytes(), (n, n), "RGBA")
        return pygame.transform.scale(surf, (n * 2, n * 2))

    def squall(self, x, y, area, radius, s, delay=0.32):
        """Шквал: с неба наискось рушатся ледяные осколки-штрихи по всей площади; первые долетают через delay —
        тогда мороз, шипы, снег и одна большая снежинка (ice_hit_area)."""
        R = radius + 0.5
        st = [False]

        def rain(dt, f):
            k = int(dt * 260 * (R + 0.5)) + 1
            a = self.rng.uniform(0, math.tau, k)
            rad = R * np.sqrt(self.rng.random(k))
            tx, ty = x + np.cos(a) * rad, y + np.sin(a) * rad
            T = delay * self.rng.uniform(0.8, 1.2, k)
            sx, sy, sz = tx - 1.1, ty - 0.35, np.full(k, 2.6)
            self.ps.spawn(k, (sx, sy, sz), ((tx - sx) / T, (ty - sy) / T, -sz / T), life=T + 0.02,
                          temp=self.rng.uniform(0.6, 1.0, k), cool=0.0, pal="ice", smoke=None, streak=0.05,
                          land=DIE, life_var=0.0)
            if f > 0.4:                          # осколки бьются о землю: крошка и пыль
                m = k // 2
                self.ps.spawn(m, (tx[:m], ty[:m], np.full(m, 0.02)), (0, 0, 1.2), life=0.4,
                              temp=self.rng.uniform(0.5, 1.0, m), grav=8.0, pal="ice", smoke=None, spread=0.9,
                              land=DIE)
            if not st[0] and f * 0.9 >= delay:
                st[0] = True
        self.emitter(0.9, rain)
        self.pilot.view.vfx.after(delay, lambda: self.ice_hit_area((x, y, 0.0), (1.0, 0.3, -1.0), area, radius, s,
                                                                   burst=False))
        return delay

