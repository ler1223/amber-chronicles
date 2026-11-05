"""Свет — навыки жреца в пиксельном стиле (образец — Освящение воина, ui/pix_weapons.py).

Обет: над союзником загорается золотая руна-кольцо, медленно вращается и сжимается всё время обета, затем сверху
бьёт столб света, золотые искры вверх.
Очищение: луч света от руки жреца к союзнику, с союзника слетает «шелуха» цвета снятых состояний и рассыпается,
белая вспышка.
Святая вода: склянка летит дугой и разбивается — брызги воды с золотыми искрами, рябь по земле (преломление, как
у волны разлома), над горящим — шипит пар.
Приговор: с неба падает узкое копьё света в цель, золотая вспышка и кольцо по земле; добивание (мало HP) — копьё
вдвое толще и стоп-кадр.
Воскрешение: пока идёт каст — под павшим раскрывается золотой круг с рунами, сверху падают перья света; на подъёме —
широкий столб света вверх и волна тепла по земле.
Время удара — из боя (config.hit), как у всего пиксельного стиля.
"""
import math

import numpy as np

from ui import projection as P
from ui.pixsim import DIE

LIGHT_SKILLS = {"vow", "purify", "holy_water", "judgment", "revive"}
G = 9.0
TAG_PAL = {"fire": "fire", "ice": "ice", "water": "water", "storm": "storm", "poison": "poison", "oil": "dust"}


class Light:
    def __init__(self, pilot):
        self.pilot = pilot
        self.rng = np.random.default_rng(23)

    @property
    def ps(self):
        return self.pilot.spells.ps

    @property
    def view(self):
        return self.pilot.view

    def skill(self, sid, u, sk, ctx, hit):
        if sid == "vow":
            return self.vow(u, ctx, sk)
        if sid == "purify":
            return self.purify(u, ctx, hit or 0.35)
        if sid == "holy_water":
            return self.holy_water(u, ctx, sk, hit or 0.5)
        if sid == "judgment":
            return self.judgment(u, ctx, hit or 0.4)
        if sid == "revive":
            return 0.0                                     # подъём рисует событие revive (ui/battle_view.py)
        return None

    # ---------- общее ----------

    def pillar(self, x, y, h=2.2, n=60, width=0.12, life=0.7):
        """Столб света: частицы по высоте, поднимаются, у земли — ярче."""
        z = self.rng.uniform(0, h, n)
        self.ps.spawn(n, (x + self.rng.normal(0, width, n), y + self.rng.normal(0, width * 0.6, n), z),
                      (np.zeros(n), np.zeros(n), np.full(n, 1.4)), life=self.rng.uniform(life * 0.5, life, n),
                      temp=np.clip(1.0 - z / h * 0.35, 0, 1), cool=1.2, pal="light", smoke=None, size=1.2,
                      life_var=0.0)

    def ring(self, x, y, R, n=160, z=0.04, life=0.9, speed=None):
        ang = np.linspace(0, math.tau, n, endpoint=False)
        if speed is None:
            pos = (x + np.cos(ang) * R, y + np.sin(ang) * R, np.full(n, z))
            vel = (0, 0, 0)
        else:
            pos = (x + np.cos(ang) * 0.2, y + np.sin(ang) * 0.2, np.full(n, z))
            vel = (np.cos(ang) * speed, np.sin(ang) * speed, np.zeros(n))
        self.ps.spawn(n, pos, vel, life=life, temp=0.62, cool=0.4, drag=3.0 if speed else 0.0, pal="light",
                      smoke=None, size=1.3, life_var=0.05)

    def _follow(self, unit, fn, dur):
        """Каждый кадр fn(dt, доля, x, y) у ног юнита, пока не выйдет время."""
        st = [0.0]

        def step(dt):
            st[0] += dt
            if not unit.alive and st[0] < dur:
                return False
            x, y = self.view.ground_pos(unit)
            fn(dt, min(1.0, st[0] / dur), x, y)
            return st[0] < dur
        self.pilot.spells.emitters.append(step)

    # ---------- Обет ----------

    def vow(self, u, ctx, sk):
        ally = ctx.get("target_unit") or u
        dur = next((e.get("time", 2.2) for e in sk.get("effects", []) if e["type"] == "delay"), 2.2)
        acc = [0.0]

        def rune(dt, k, x, y):
            acc[0] += dt
            if acc[0] < 0.04:
                return
            acc[0] = 0.0
            R = 0.8 - 0.45 * k
            spin = k * 4.0
            n = 64
            ang = np.linspace(0, math.tau, n, endpoint=False) + spin
            z = 1.55 + 0.1 * math.sin(k * 9)
            self.ps.spawn(n, (x + np.cos(ang) * R, y + np.sin(ang) * R * 0.5, np.full(n, z)), (0, 0, 0),
                          life=0.06, temp=0.55 + 0.12 * k, cool=0.0, pal="light", smoke=None, size=1.3, life_var=0.0)
            m = 6                                          # знаки руны — яркие засечки по кругу
            a2 = np.linspace(0, math.tau, m, endpoint=False) - spin * 1.5
            self.ps.spawn(m, (x + np.cos(a2) * R * 0.75, y + np.sin(a2) * R * 0.375, np.full(m, z)), (0, 0, 0),
                          life=0.06, temp=1.0, cool=0.0, pal="light", smoke=None, size=1.4, life_var=0.0)
        self._follow(ally, rune, dur)

        def land():
            if not ally.alive:
                return
            x, y = self.view.ground_pos(ally)
            self.pillar(x, y, h=2.6, n=90, width=0.14, life=0.8)
            self.ps.spawn(30, (x, y, 0.6), (0, 0, 1.6), life=0.8, temp=1.0, cool=1.0, grav=1.5, pal="light",
                          smoke=None, spread=1.2, land=DIE)
            self.ring(x, y, 0.5, n=60, life=0.5)
        self.view.vfx.after(dur, land)
        return 0.0

    # ---------- Очищение ----------

    def purify(self, u, ctx, hit):
        ally = ctx.get("target_unit") or u
        S = self.pilot.spells
        a = S.hand(u, self.view.ground_pos(ally))
        b = S.contact(a, ally)
        n = max(8, int(math.dist(a[:2], b[:2]) / 0.05))
        t = np.linspace(0, 1, n)
        self.ps.spawn(n, (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t),
                      (0, 0, 0), life=hit * (0.5 + 0.5 * t) + 0.1, temp=1.0, cool=1.5, pal="light", smoke=None,
                      size=1.2, life_var=0.0)
        tags = [tg for tg in ally.statuses if tg in TAG_PAL]

        def clean():
            if not ally.alive:
                return
            x, y = self.view.ground_pos(ally)
            pals = [TAG_PAL[tg] for tg in tags] or ["steam"]
            for pal in pals:                               # шелуха снятого слетает и осыпается
                k = 26
                self.ps.spawn(k, (x + self.rng.normal(0, 0.15, k), y + self.rng.normal(0, 0.08, k),
                                  self.rng.uniform(0.2, 1.2, k)),
                              (self.rng.normal(0, 0.8, k), self.rng.normal(0, 0.4, k), self.rng.uniform(0.2, 1.0, k)),
                              life=0.8, temp=0.6, cool=0.4, grav=G * 0.4, drag=1.5, pal=pal, smoke=None, land=DIE,
                              life_var=0.3)
            self.ps.spawn(20, (x, y, 0.7), (0, 0, 0), life=0.18, temp=1.0, cool=4.0, pal="light", smoke=None,
                          spread=1.8)
        self.view.vfx.after(hit, clean)
        return hit

    # ---------- Святая вода ----------

    def holy_water(self, u, ctx, sk, hit):
        g = ctx.get("target_ground")
        dst = P.unproject(*g) if g else None
        if dst is None:
            return hit
        S = self.pilot.spells
        a = S.hand(u, dst)
        b = (dst[0], dst[1], 0.1)
        st = [0.0]
        dur = max(0.2, hit)

        def fly(dt):
            st[0] += dt
            k = min(1.0, st[0] / dur)
            p = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k,
                 a[2] + (b[2] - a[2]) * k + math.sin(math.pi * k) * 1.1)
            self.ps.spawn(3, p, (0, 0, 0), life=0.05, temp=0.55, cool=0.0, pal="water", smoke=None, size=1.2,
                          life_var=0.0, jitter=0.02)
            self.ps.spawn(1, (p[0] - 0.02, p[1], p[2] + 0.05), (0, 0, 0), life=0.05, temp=1.0, cool=0.0,
                          pal="water", smoke=None, life_var=0.0)
            if self.rng.random() < 0.5:
                self.ps.spawn(1, p, (0, 0, -0.3), life=0.4, temp=0.9, cool=1.5, pal="light", smoke=None,
                              life_var=0.2)
            if st[0] >= dur:
                self.splash(b[0], b[1], (sk.get("radius", 1) or 1) + 0.4)
                return False
            return True
        S.emitters.append(fly)
        return hit

    def splash(self, x, y, R):
        n = 90
        ang = self.rng.uniform(0, math.tau, n)
        sp = self.rng.uniform(1.0, 2.6, n)
        self.ps.spawn(n, (np.full(n, x), np.full(n, y), np.full(n, 0.15)),
                      (np.cos(ang) * sp, np.sin(ang) * sp, self.rng.uniform(1.5, 3.2, n)), life=0.8, temp=0.7,
                      cool=0.4, grav=G, pal="water", smoke=None, land=DIE, life_var=0.25)
        self.ps.spawn(30, (x, y, 0.3), (0, 0, 1.0), life=0.7, temp=1.0, cool=1.2, grav=G * 0.3, pal="light",
                      smoke=None, spread=1.6, land=DIE)
        from ui.pix_quake import Quake                 # рябь по любой поверхности: святая вода растекается
        self.pilot.quakes.append(Quake(x, y, 0.0, self.pilot.spells.terrain_at,
                                       seed=int(self.rng.integers(1 << 30)), life=1.5, ripple_r=R, ripple_all=True))
        c = self.view.combat
        if c is not None:                              # горевшее шипит паром
            for (cx, cy), cell in c.grid.cells.items():
                if cell.hazard == "fire" and abs(cx + 0.5 - x) <= R and abs(cy + 0.5 - y) <= R:
                    self.ps.spawn(14, (cx + 0.5, cy + 0.5, 0.1), (0, 0, 1.0), life=1.0, temp=0.5, cool=0.2,
                                  buoy=0.8, drag=2.0, size=1.6, grow=1.2, pal="steam", smoke=None, spread=0.4,
                                  jitter=0.3)

    # ---------- Приговор ----------

    def judgment(self, u, ctx, hit):
        tgt = ctx.get("target_unit")
        if tgt is None:
            return hit
        execute = tgt.hp < tgt.max_hp * 0.4
        st = [0.0]
        dur = max(0.15, hit)
        w = 0.09 if execute else 0.045

        def fall(dt):
            st[0] += dt
            x, y = self.view.ground_pos(tgt)
            k = min(1.0, st[0] / dur)
            top = 4.0
            z = top * (1 - k)
            seg = np.linspace(z, min(top, z + 1.4), 16)          # копьё: древко света сверху вниз
            for dx in (-w, 0.0, w) if execute else (0.0, w):
                self.ps.spawn(16, (np.full(16, x + dx), np.full(16, y), seg), (0, 0, 0), life=0.05,
                              temp=np.linspace(1.0, 0.8, 16), cool=0.0, pal="light", smoke=None, size=1.5,
                              life_var=0.0)
            if st[0] >= dur:
                self.ring(x, y, 0.2, n=90, life=0.45, speed=4.0)
                self.ps.spawn(40 if execute else 24, (x, y, 0.5), (0, 0, 1.0), life=0.4, temp=1.0, cool=2.0,
                              grav=G * 0.5, pal="light", smoke=None, spread=2.0, land=DIE)
                self.pillar(x, y, h=1.6, n=30, width=0.08, life=0.4)
                self.view.vfx.screen_fx(shake=5 if execute else 2, hitstop=0.06 if execute else 0.0,
                                        flash=0.05 if execute else 0.0)
                return False
            return True
        self.pilot.spells.emitters.append(fall)
        return hit

    # ---------- Воскрешение ----------

    def revive_cast(self, u, alive):
        """Пока идёт каст: золотой круг с рунами под павшим, падающие перья света."""
        c = self.view.combat
        if u.cast is None or c is None:
            return False
        tgt = u.cast.get("target")
        cell = tuple(tgt) if isinstance(tgt, (tuple, list)) else getattr(tgt, "cell", None)
        if cell is None:
            return False
        x, y = cell[0] + 0.5, cell[1] + 0.5
        st, acc = [0.0], [0.0]
        total = max(0.5, u.cast.get("total", 2.0) if isinstance(u.cast, dict) else 2.0)

        def step(dt):
            st[0] += dt
            acc[0] += dt
            if acc[0] >= 0.04:
                acc[0] = 0.0
                k = min(1.0, st[0] / total)
                R = 0.25 + 0.75 * min(1.0, k * 1.6)
                n = 96
                ang = np.linspace(0, math.tau, n, endpoint=False) + st[0] * 0.8
                for rr in (R, R * 0.92):
                    self.ps.spawn(n, (x + np.cos(ang) * rr, y + np.sin(ang) * rr, np.full(n, 0.05)), (0, 0, 0),
                                  life=0.07, temp=0.6, cool=0.0, pal="light", smoke=None, size=1.4, life_var=0.0)
                m = 8
                a2 = np.linspace(0, math.tau, m, endpoint=False) - st[0] * 1.2
                self.ps.spawn(m, (x + np.cos(a2) * R * 0.65, y + np.sin(a2) * R * 0.65, np.full(m, 0.04)), (0, 0, 0),
                              life=0.06, temp=0.75, cool=0.0, pal="light", smoke=None, size=1.4, life_var=0.0)
                for _ in range(2 if self.rng.random() < 0.7 else 1):   # перо света: медленно падает, покачиваясь
                    self.ps.spawn(1, (x + self.rng.normal(0, 0.4), y + self.rng.normal(0, 0.25), 2.4),
                                  (self.rng.normal(0, 0.15), 0, -0.6), life=2.0, temp=0.95, cool=0.3, drag=0.5,
                                  pal="light", smoke=None, size=1.0, tall=1.0, life_var=0.2)
            return alive()
        self.pilot.spells.emitters.append(step)
        return True

    def revived(self, unit):
        x, y = self.view.ground_pos(unit)
        self.pillar(x, y, h=3.2, n=160, width=0.28, life=1.0)
        self.ring(x, y, 0.2, n=140, life=0.8, speed=3.0)
        self.ps.spawn(60, (x, y, 0.1), (0, 0, 0.6), life=0.9, temp=0.85, cool=0.6, buoy=0.6, drag=2.0, pal="light",
                      smoke=None, spread=1.4, jitter=0.4)
        self.view.vfx.screen_fx(flash=0.08, shake=2)
