"""Пиксельные эффекты по запросам после архетипов (ui/pix_arch.py):

  гроза      — пока идёт каст, над площадью собирается туча (клубы, внутри вспыхивает); удар — серия молний из тучи
               в землю по площади; ветка «Ливень» и вражеская Буря — ещё и косой дождь;
  молния     — одиночный ломаный разряд (атака тотема грозы, аура тотема бури — в каждого врага рядом);
  газ        — ядовитое облако как настоящая дымовая граната: плотные клубы растут, крутятся, медленно тянутся
               вверх и по ветру, к краю редеют; облако живёт, пока на клетке опасность «Яд»;
  барьер     — щит пиксельной фигурой вокруг юнита: сфера, куб или октаэдр, медленно вращается (вид — по классу,
               кто наложил щит);
  часы       — стазис: юнит в песочных часах (рамка, колбы, песок сыплется), пока он вне времени;
  выстрел    — ловчий стреляет пулей: вспышка у ствола и дымок, быстрый короткий трассер.
"""
import math

import numpy as np

from ui import projection as P
from ui.pixsim import DIE

G = 9.0
BARRIER_SHAPE = {"guardian": "cube", "warrior": "cube", "tactician": "cube", "ram": "cube", "bloodrager": "cube",
                 "priest": "octa", "druid": "octa", "bard": "octa", "shaman": "octa", "binder": "octa",
                 "trapper": "octa", "archer": "octa"}
BARRIER_PAL = {"priest": "light", "tactician": "light", "binder": "spirit", "cryo": "ice", "druid": "nature",
               "shaman": "storm", "bard": "sound", "necro": "bone", "chrono": "time", "gravity": "gravity",
               "bloodrager": "blood"}


def _shape(kind):
    """Рёбра фигуры барьера в единичных координатах: [(a, b)]."""
    if kind == "cube":
        v = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
        e = [(a, b) for i, a in enumerate(v) for b in v[i + 1:] if sum(p != q for p, q in zip(a, b)) == 1]
        return [(np.array(a) * 0.7, np.array(b) * 0.7) for a, b in e]
    if kind == "octa":
        v = [np.array(p, float) for p in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
        return [(a, b) for i, a in enumerate(v) for b in v[i + 1:] if abs(np.dot(a, b)) < 0.5]
    out = []                                      # сфера: 3 меридиана и экватор
    k = 24
    for m in range(4):
        for i in range(k):
            a0, a1 = i / k * math.tau, (i + 1) / k * math.tau
            if m == 3:
                p, q = (math.cos(a0), math.sin(a0), 0), (math.cos(a1), math.sin(a1), 0)
            else:
                ph = m * math.pi / 3
                p = (math.cos(a0) * math.cos(ph), math.cos(a0) * math.sin(ph), math.sin(a0))
                q = (math.cos(a1) * math.cos(ph), math.cos(a1) * math.sin(ph), math.sin(a1))
            out.append((np.array(p), np.array(q)))
    return out


SHAPES = {k: _shape(k) for k in ("sphere", "cube", "octa")}


class Extra:
    def __init__(self, pilot):
        self.pilot = pilot
        self.rng = np.random.default_rng(41)
        self.barriers = {}        # id юнита → (фигура, палитра, фаза)
        self.gas_acc = {}

    @property
    def ps(self):
        return self.pilot.spells.ps

    @property
    def view(self):
        return self.pilot.view

    # ---------- молния ----------

    def bolt(self, a, b, pal="storm", life=0.16, wiggle=0.14, branches=True):
        pts = [np.array(a, float)]
        n = 7
        for k in range(1, n):
            f = k / n
            p = np.array(a) + (np.array(b) - np.array(a)) * f
            p[:2] += self.rng.normal(0, wiggle, 2)
            pts.append(p)
        pts.append(np.array(b, float))
        A = self.pilot.arch
        for p, q in zip(pts, pts[1:]):                 # сплошной канал: белое ядро и синее свечение
            n = max(8, int(math.dist(p, q) / 0.012))
            A.streak(tuple(p), tuple(q), pal, life=life * 1.4, n=n // 2, size=3.2, temp=0.7)
            A.streak(tuple(p), tuple(q), pal, life=life, n=n, size=1.8, temp=1.0)
        if branches:
            for p in pts[2:-2:2]:
                q = p + np.array([self.rng.normal(0, 0.25), self.rng.normal(0, 0.18), -self.rng.uniform(0.1, 0.4)])
                A.streak(tuple(p), tuple(q), pal, life=life * 0.7, n=max(6, int(math.dist(p, q) / 0.015)),
                         size=1.2, temp=0.85)

    def zap(self, src, dst):
        """Атака тотема грозы: разряд из навершия в цель."""
        S = self.pilot.spells
        a = S.unit_point(src)
        a = (a[0], a[1], a[2] + 0.5)
        b = S.contact(a, dst)
        self.bolt(a, b, wiggle=0.1)
        self.pilot.arch.burst(*b, "storm", n=14, speed=1.0, life=0.3)

    # ---------- гроза ----------

    def storm_cast(self, cx, cy, R, alive, rain=False):
        """Пока идёт каст: туча над площадью (клубы тёмного пара, внутри — вспышки), при ливне — уже моросит."""
        st, acc = [0.0], [0.0]

        def step(dt):
            st[0] += dt
            acc[0] += dt
            grow = min(1.0, st[0] / 0.8)
            k = int(acc[0] * 160 * (R + 0.5))
            if k:
                acc[0] = 0.0
                a = self.rng.uniform(0, math.tau, k)
                r = (R + 0.3) * np.sqrt(self.rng.random(k)) * grow
                self.ps.spawn(k, (cx + np.cos(a) * r, cy + np.sin(a) * r, self.rng.uniform(2.3, 2.8, k)),
                              (self.rng.normal(0, 0.15, k), self.rng.normal(0, 0.1, k), self.rng.normal(0, 0.05, k)),
                              life=0.9, temp=self.rng.uniform(0.25, 0.75, k), cool=0.0, drag=1.0, size=4.0, grow=0.8,
                              alpha=1.0, pal="cloud", smoke=None, life_var=0.2)
            if self.rng.random() < 3.0 * dt:              # вспышка внутри тучи
                a, r = self.rng.uniform(0, math.tau), R * self.rng.random()
                self.ps.spawn(12, (cx + math.cos(a) * r, cy + math.sin(a) * r, 2.5), (0, 0, 0), life=0.08,
                              temp=1.0, cool=0.0, pal="storm", smoke=None, jitter=0.25, life_var=0.0)
            if rain:
                self.rain(cx, cy, R, dt, 0.6 * grow)
            return alive()
        self.pilot.spells.emitters.append(step)

    def rain(self, cx, cy, R, dt, k=1.0):
        n = int(dt * 160 * (R + 0.5) * k) + 1
        a = self.rng.uniform(0, math.tau, n)
        r = (R + 0.3) * np.sqrt(self.rng.random(n))
        self.ps.spawn(n, (cx + np.cos(a) * r + 0.3, cy + np.sin(a) * r, np.full(n, 2.4)),
                      (np.full(n, -0.8), np.zeros(n), np.full(n, -7.0)), life=0.36, temp=0.65, cool=0.0,
                      pal="water", smoke=None, streak=0.03, land=DIE, life_var=0.1)

    def storm_strike(self, cx, cy, R, dur, rain=False):
        """Удар: молнии из тучи в землю по площади, с землёй — вспышки и брызги искр; при ливне дождь идёт ещё 1.5 с."""
        n = int(4 + 3 * R)
        for i in range(n):
            a, r = self.rng.uniform(0, math.tau), R * math.sqrt(self.rng.random())
            x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
            t = dur * i / n

            def hit(x=x, y=y):
                self.bolt((x + self.rng.normal(0, 0.2), y - 0.15, 2.5), (x, y, 0.02), wiggle=0.18, life=0.22)
                self.pilot._light(self.view_ground(x, y), (170, 190, 255), 70, 1.6, 0.18)
                self.pilot.arch.burst(x, y, 0.05, "storm", n=16, speed=1.4, life=0.35)
                self.pilot.arch.ring(x, y, 0.5, "storm", n=40, life=0.25, out=True, temp=0.9)
            self.view.vfx.after(t, hit)
        self.view.vfx.after(0.0, lambda: self.view.vfx.screen_fx(shake=4, flash=0.08, color=(170, 190, 255)))
        if rain:
            st = [0.0]

            def drizzle(dt):
                st[0] += dt
                self.rain(cx, cy, R, dt, 1.0 - st[0] / 1.6)
                return st[0] < 1.5
            self.pilot.spells.emitters.append(drizzle)

    # ---------- газ ----------

    def gas(self, dt, c):
        """Газ над ядовитыми клетками: низкая стелющаяся дымка мелкими частицами — клубы медленно вращаются,
        земля сквозь газ видна; из лужи поднимаются пузырьки и лопаются."""
        cells = [p for p, cell in c.grid.cells.items() if cell.hazard == "poison"]
        live = set(cells)
        for p in list(self.gas_acc):
            if p not in live:
                del self.gas_acc[p]
        for p in cells:
            cell = c.grid.cells[p]
            fresh = p not in self.gas_acc
            a = self.gas_acc.get(p, 0.0) + dt * 18
            n = int(a)
            self.gas_acc[p] = a - n
            x, y = p[0] + 0.5, p[1] + 0.5
            if fresh:                                    # хлопок: газ вырывается и катится по земле
                k = 60
                ang = self.rng.uniform(0, math.tau, k)
                sp = self.rng.uniform(0.5, 1.5, k)
                self.ps.spawn(k, (np.full(k, x), np.full(k, y), np.full(k, 0.1)),
                              (np.cos(ang) * sp, np.sin(ang) * sp, self.rng.uniform(0.1, 0.5, k)),
                              life=1.8, temp=self.rng.uniform(0.3, 0.6, k), cool=0.1, drag=1.6, buoy=0.05,
                              size=1.6, grow=0.6, alpha=0.6, pal="gas", smoke=None, life_var=0.3)
            if n:
                left = cell.hazard_time if cell.hazard_time < 1e6 else 6.0
                fade = min(1.0, left / 1.5)               # к концу облако редеет
                ang = self.rng.uniform(0, math.tau, n)
                r = 0.55 * np.sqrt(self.rng.random(n))
                h = self.rng.uniform(0.02, 0.35, n) ** 1.3
                self.ps.spawn(n, (x + np.cos(ang) * r, y + np.sin(ang) * r, h),
                              (-np.sin(ang) * 0.3 + 0.05, np.cos(ang) * 0.18, self.rng.uniform(0.0, 0.12, n)),
                              life=self.rng.uniform(1.6, 2.6, n), temp=self.rng.uniform(0.2, 0.55, n), cool=0.08,
                              drag=1.0, buoy=0.03, size=self.rng.uniform(1.4, 2.0, n), grow=0.4,
                              alpha=0.45 * fade, pal="gas", smoke=None, life_var=0.2)
            if self.rng.random() < dt * 3:               # пузырёк: всплыл, вспыхнул, лопнул брызгами
                bx, by = x + self.rng.uniform(-0.4, 0.4), y + self.rng.uniform(-0.4, 0.4)
                self.ps.spawn(1, (bx, by, 0.02), (0, 0, 0.25), life=0.35, temp=1.0, cool=0.5, pal="poison",
                              smoke=None, size=1.6, life_var=0.0)
                self.view.vfx.after(0.35, lambda bx=bx, by=by: self.ps.spawn(
                    5, (bx, by, 0.1), (0, 0, 0.6), life=0.3, temp=0.9, cool=1.0, grav=G * 0.5, pal="poison",
                    smoke=None, spread=0.7, land=DIE))

    def status_fx(self, u, dt):
        """Отравлен — с фигурки поднимаются зелёные пузырьки и тонкий дымок; в масле — тёмные капли стекают и падают."""
        x, y = self.view.ground_pos(u)
        if "poison" in u.statuses:
            k = self.rng.poisson(9 * dt)
            if k:
                self.ps.spawn(k, (x + self.rng.normal(0, 0.15, k), y, self.rng.uniform(0.3, 0.8, k)), (0, 0, 0.45),
                              life=0.7, temp=self.rng.uniform(0.7, 1.0, k), cool=0.6, drag=1.5, pal="poison",
                              smoke=None, size=1.2, jitter=0.02, life_var=0.3)
            k = self.rng.poisson(5 * dt)
            if k:
                self.ps.spawn(k, (x, y, 0.6), (0, 0, 0.3), life=1.0, temp=0.6, cool=0.2, drag=2.0, buoy=0.1,
                              size=1.4, grow=0.5, alpha=0.6, pal="gas", smoke=None, jitter=0.15)
        if "oil" in u.statuses:
            k = self.rng.poisson(6 * dt)
            if k:
                self.ps.spawn(k, (x + self.rng.normal(0, 0.14, k), y, self.rng.uniform(0.3, 0.7, k)), (0, 0, -0.2),
                              life=0.9, temp=self.rng.uniform(0.15, 0.4, k), cool=0.0, grav=G * 0.35, drag=2.0,
                              pal="oil", smoke=None, size=1.3, land=DIE, life_var=0.2)
            if self.rng.random() < dt * 2:            # блик на масле
                self.ps.spawn(1, (x + self.rng.normal(0, 0.12), y, self.rng.uniform(0.3, 0.8)), (0, 0, 0), life=0.15,
                              temp=1.0, cool=0.0, pal="oil", smoke=None, life_var=0.0)

    # ---------- барьер ----------

    def add_barrier(self, unit, owner_cls=None):
        cls = owner_cls or unit.proto_id
        shape = BARRIER_SHAPE.get(cls, "sphere")
        pal = BARRIER_PAL.get(cls, "spirit")
        self.barriers[unit.id] = (shape, pal, self.rng.uniform(0, 6))

    def barriers_step(self, dt, c):
        t = self.pilot.time
        for u in c.alive():
            if u.shield <= 0 or u.obj:
                self.barriers.pop(u.id, None)
                continue
            if u.id not in self.barriers:
                self.add_barrier(u)
            shape, pal, ph = self.barriers[u.id]
            x, y = self.view.ground_pos(u)
            R = 0.62 if shape == "sphere" else 0.58
            ang = t * 0.9 + ph
            ca, sa = math.cos(ang), math.sin(ang)
            tilt = 0.35
            ct, st_ = math.cos(tilt), math.sin(tilt)
            pts, temps = [], []
            for a, b in SHAPES[shape]:
                seg = 4 if shape == "sphere" else 9
                for f in np.linspace(0, 1, seg, endpoint=False):
                    p = a + (b - a) * f
                    px, py, pz = p[0] * ca - p[1] * sa, p[0] * sa + p[1] * ca, p[2]
                    py, pz = py * ct - pz * st_, py * st_ + pz * ct          # наклон оси к камере
                    pts.append((x + px * R, y + py * R * 0.55, 0.62 + pz * R * 1.05))
                    temps.append(0.5 + 0.35 * (py > 0))                     # передняя сторона ярче
            pts = np.array(pts)
            m = len(pts)
            self.ps.spawn(m, (pts[:, 0], pts[:, 1], np.maximum(0.02, pts[:, 2])), (0, 0, 0), life=0.05,
                          temp=np.array(temps), cool=0.0, pal=pal, smoke=None, size=1.0, life_var=0.0)

    # ---------- песочные часы ----------

    def hourglass_step(self, c):
        if self.view._hourglass() is not None:              # есть рисунок часов — его кладёт ui/battle_view.py
            return
        t = self.pilot.time
        for u in c.alive():
            if getattr(u, "stasis", 0) <= 0:
                continue
            x, y = self.view.ground_pos(u)
            H, W = 1.45, 0.48
            frame = []
            for z in (0.0, H):                                  # крышки
                for f in np.linspace(-W, W, 12):
                    frame.append((x + f, y, z))
            for side in (-1, 1):                                 # стойки
                for z in np.linspace(0, H, 14):
                    frame.append((x + side * W * 1.05, y, z))
            glass = []
            for z in np.linspace(0.04, H - 0.04, 22):           # колбы: сужаются к середине
                w = W * 0.9 * abs(z - H / 2) / (H / 2) + 0.05
                glass += [(x - w, y, z), (x + w, y, z)]
            fr = np.array(frame)
            gl = np.array(glass)
            self.ps.spawn(len(fr), (fr[:, 0], fr[:, 1], fr[:, 2]), (0, 0, 0), life=0.05, temp=0.55, cool=0.0,
                          pal="time", smoke=None, size=1.2, life_var=0.0)
            self.ps.spawn(len(gl), (gl[:, 0], gl[:, 1], gl[:, 2]), (0, 0, 0), life=0.05, temp=0.88, cool=0.0,
                          pal="time", smoke=None, size=1.0, life_var=0.0, alpha=0.7)
            k = max(0.0, min(1.0, u.stasis / 3.0))               # песок: сверху убывает, снизу растёт
            top_h, bot_h = (H / 2 - 0.08) * k, (H / 2 - 0.08) * (1 - k)
            sand = []
            for z in np.linspace(H / 2 + 0.06, H / 2 + 0.06 + top_h, max(1, int(top_h * 14))):
                w = W * 0.8 * abs(z - H / 2) / (H / 2)
                sand += [(x + f, y, z) for f in np.linspace(-w, w, max(2, int(w * 20)))]
            for z in np.linspace(0.06, 0.06 + bot_h, max(1, int(bot_h * 14))):
                w = W * 0.8 * abs(z - H / 2) / (H / 2)
                sand += [(x + f, y, z) for f in np.linspace(-w, w, max(2, int(w * 20)))]
            if sand:
                s = np.array(sand)
                self.ps.spawn(len(s), (s[:, 0], s[:, 1], s[:, 2]), (0, 0, 0), life=0.05, temp=0.7, cool=0.0,
                              pal="time", smoke=None, size=1.0, life_var=0.0)
            if int(t * 20) % 2 == 0:                             # струйка в горлышке
                self.ps.spawn(3, (np.full(3, x), np.full(3, y), H / 2 - np.linspace(0, 0.2, 3)), (0, 0, 0),
                              life=0.05, temp=0.75, cool=0.0, pal="time", smoke=None, life_var=0.0)

    # ---------- выстрел ловчего ----------

    def view_ground(self, x, y):
        """Точка земли на экране для подсветки."""
        from ui import projection as P
        return P.project(x, y)[:2]

    def gunshot(self, src, dst, dur):
        S = self.pilot.spells
        a = S.hand(src, self.view.ground_pos(dst))
        b = S.contact(a, dst)
        d = np.array(b) - np.array(a)
        L = np.linalg.norm(d[:2]) or 1.0
        u = d / L
        self.ps.spawn(36, a, tuple(u * 3.0), life=0.09, temp=1.0, cool=2.5, pal="fire", smoke=None, spread=1.1,
                      size=2.2)                                    # дульная вспышка: конус огня по ходу выстрела
        self.ps.spawn(14, a, (0, 0, 0), life=0.05, temp=1.0, cool=0.0, pal="fire", smoke=None, jitter=0.07, size=3.0)
        self.pilot._light(self.view_ground(a[0], a[1]), (255, 200, 120), 60, 1.8, 0.12)
        self.pilot.motif.gun_smoke(a, u, src)
        self.ps.spawn(10, a, (u[0] * 0.6, u[1] * 0.6, 0.4), life=0.9, temp=0.35, cool=0.1, drag=2.0, buoy=0.4,
                      size=1.6, grow=1.0, pal="steam", smoke=None, spread=0.3, jitter=0.05)
        st = [0.0]
        dur = max(0.06, dur)

        def fly(dt):
            st[0] += dt
            k = min(1.0, st[0] / dur)
            p = np.array(a) + d * k
            q = np.array(a) + d * max(0.0, k - 0.12)
            self.pilot.arch.streak(tuple(q), tuple(p), "steel", life=0.04, n=6, size=1.0, temp=0.9)
            if st[0] >= dur:
                self.ps.spawn(8, tuple(b), (0, 0, 0.4), life=0.25, temp=0.9, cool=2.0, grav=G * 0.4, pal="steel",
                              smoke=None, spread=1.2, land=DIE)
                self.pilot.motif.hit("trapper", *b)
                return False
            return True
        self.pilot.spells.emitters.append(fly)
        return dur
