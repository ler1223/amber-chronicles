"""Почерк класса: у каждого героя свои детали поверх архетипа навыка (ui/pix_arch.py).

Три места, где виден мотив:
  cast  — пока герой кастует: аура с мотивом (перья, ноты, песок, листья…);
  trail — след летящего снаряда;
  hit   — вспышка попадания + 1–2 детали мотива.

  лучник     — перья-искры и щепки;            ловчий    — пороховой дым, латунная гильза, блеск железа;
  убийца     — фиолетовый дым, послеобраз, косой тёмный разрез;
  алхимик    — искры фитиля, сажа, осколки стекла;
  друид      — листья, лепестки, корни, светлячки;   шаман — спирали ветра, искры статики;
  связующий  — нити духа и бегущие по ним огоньки;   некромант — костяные осколки, души тянутся к нему;
  хрономант  — золотой песок, кольцо-циферблат, послеобраз перемотки;
  гравитант  — кольца искажения, парящие камешки, спираль внутрь;
  геомант    — каменная крошка, пыль, кристаллы;     бард — ноты-глифы и звуковые кольца в такт;
  зельевар   — пузыри, капли, зелёные испарения;     берсерк крови — капли крови, штрихи ярости, пар;
  тактик     — золотые стрелки-приказы, флажок;      таран — пыль, крошка, ударная волна.
У воина, стража, жреца, мага и криоманта — свои ручные эффекты (pix_weapons, pix_light, pix_spells).
"""
import math

import numpy as np

from ui.pixsim import BOUNCE, DIE

G = 9.0
PX = 0.026                       # пиксель частицы (size 1) в клетках по горизонтали
ZPX = PX * 1.3                   # и по высоте

NOTE = ["..##",
        "..#.",
        "..#.",
        "###.",
        "##.."]
NOTE2 = ["####",
         "#..#",
         "#..#",
         "#.##",
         "#.##"]
FLAG = ["#...",
        "###.",
        "####",
        "#...",
        "#..."]
CHEVRON = ["#...#",
           ".#.#.",
           "..#.."]
FEATHER = [".#.",
           "###",
           ".#.",
           ".#."]

MOTIF_CLASSES = {"archer", "trapper", "assassin", "alchemist", "druid", "shaman", "binder", "necro", "chrono",
                 "gravity", "geomancer", "bard", "brewer", "bloodrager", "tactician", "ram"}
GHOST_TINT = {"assassin": (150, 90, 220), "chrono": (255, 215, 120)}


class Motif:
    def __init__(self, pilot):
        self.pilot = pilot
        self.rng = np.random.default_rng(23)

    @property
    def ps(self):
        return self.pilot.spells.ps

    @property
    def view(self):
        return self.pilot.view

    def _rate(self, r, dt):
        """Сколько частиц за кадр при r в секунду (дробная часть — случайно)."""
        x = r * dt
        return int(x) + (1 if self.rng.random() < x - int(x) else 0)

    # ---------- приёмы ----------

    def glyph(self, rows, x, y, z, pal, vel=(0, 0, 0.5), life=0.8, temp=0.85, size=1.6, cool=0.5):
        """Значок из пикселей (нота, флажок, стрелка): летит целиком, не рассыпаясь."""
        pts = [(c, r) for r, row in enumerate(rows) for c, ch in enumerate(row) if ch == "#"]
        n = len(pts)
        cx = np.array([p[0] for p in pts], float) - len(rows[0]) / 2
        cz = len(rows) - np.array([p[1] for p in pts], float)
        self.ps.spawn(n, (x + cx * PX * size, np.full(n, y), z + cz * ZPX * size), vel, life=life, temp=temp,
                      cool=cool, pal=pal, smoke=None, size=size, life_var=0.0)

    def shards(self, x, y, z, pal, n=10, speed=1.6, temp=0.8, size=1.2, life=0.8):
        """Осколки: летят и прыгают по земле."""
        self.ps.spawn(n, (x, y, z), (0, 0, 1.2), life=life, temp=temp, cool=0.3, grav=G, bounce=0.35, drag=0.4,
                      pal=pal, smoke=None, spread=speed, size=size, land=BOUNCE, life_var=0.3)

    def puff(self, x, y, z, pal, n=10, size=2.0, life=0.8, temp=0.5, up=0.5, spread=0.4):
        self.ps.spawn(n, (x, y, z), (0, 0, up), life=life, temp=temp, cool=0.2, buoy=0.3, drag=2.5, size=size,
                      grow=1.2, alpha=0.8, pal=pal, smoke=None, spread=spread, jitter=0.08, life_var=0.3)

    def tick_ring(self, x, y, z, R, pal, ticks=12, life=0.35, rot=0.0, temp=0.9):
        """Циферблат: деления по кругу и одна стрелка."""
        a = np.linspace(0, math.tau, ticks, endpoint=False) + rot
        for k in (1.0, 0.86):
            self.ps.spawn(ticks, (x + np.cos(a) * R * k, y + np.sin(a) * R * k * 0.6, np.full(ticks, z)), (0, 0, 0),
                          life=life, temp=temp, cool=0.8, pal=pal, smoke=None, size=1.2, life_var=0.0)
        t = np.linspace(0.1, 0.8, 8)
        self.ps.spawn(8, (x + math.cos(rot * 3) * R * t, y + math.sin(rot * 3) * R * t * 0.6, np.full(8, z)),
                      (0, 0, 0), life=life * 0.6, temp=temp, cool=0.8, pal=pal, smoke=None, life_var=0.0)

    def ghost(self, u, life=0.45, cls=None):
        cls = cls or u.proto_id
        self.view.add_ghost(u, life, GHOST_TINT.get(cls, (200, 200, 255)))

    # ---------- вход ----------

    def start_cast(self, u, alive):
        """Аура каста с мотивом класса (поверх пентаграммы у магов или ауры силы у остальных)."""
        fn = getattr(self, "_cast_" + str(u.proto_id), None)
        if fn is None:
            return
        st = [0.0]

        def step(dt):
            if not alive() or not u.alive:
                return False
            st[0] += dt
            gx, gy = self.view.ground_pos(u)
            fn(u, gx, gy, dt, st[0])
            return True
        self.pilot.spells.emitters.append(step)

    def trail(self, cls, p, dirv, dt, t):
        fn = getattr(self, "_trail_" + str(cls), None)
        if fn is not None:
            fn(p, dirv, dt, t)

    def hit(self, cls, x, y, z):
        fn = getattr(self, "_hit_" + str(cls), None)
        if fn is not None:
            fn(x, y, z)

    # ---------- лучник ----------

    def _cast_archer(self, u, gx, gy, dt, t):
        if self._rate(3, dt):                                  # пёрышко слетает с оперения
            self.glyph(FEATHER, gx + self.rng.normal(0, 0.2), gy, 0.9, "dust", vel=(0.15, 0, -0.25),
                       life=0.9, temp=0.95, size=1.3, cool=0.4)
        k = self._rate(10, dt)
        if k:
            self.ps.spawn(k, (gx, gy, 0.6), (0, 0, 0), life=0.15, temp=1.0, cool=2.0, pal="steel", smoke=None,
                          jitter=0.25)

    def _trail_archer(self, p, dirv, dt, t):
        if self.rng.random() < 0.25:
            self.ps.spawn(1, p, (-dirv[0] * 0.3, -dirv[1] * 0.3, -0.2), life=0.4, temp=0.9, cool=1.0, grav=1.0,
                          drag=2.0, pal="dust", smoke=None, life_var=0.3)

    def _hit_archer(self, x, y, z):
        self.shards(x, y, z, "oil", n=14, speed=1.4, temp=0.7, size=1.4)        # щепки
        for _ in range(2):
            self.glyph(FEATHER, x + self.rng.normal(0, 0.15), y, z + 0.1, "dust",
                       vel=(self.rng.normal(0, 0.4), 0, 0.4), life=0.9, temp=0.95, size=1.3)

    # ---------- ловчий ----------

    def _cast_trapper(self, u, gx, gy, dt, t):
        k = self._rate(6, dt)
        if k:
            self.puff(gx + 0.15, gy, 0.55, "steam", n=k, size=1.6, life=0.9, temp=0.45, up=0.4, spread=0.2)
        if self._rate(5, dt):
            self.ps.spawn(2, (gx, gy, 0.5), (0, 0, 0), life=0.12, temp=1.0, cool=1.0, pal="brass", smoke=None,
                          jitter=0.3)

    def _hit_trapper(self, x, y, z):
        self.ps.spawn(10, (x, y, z), (0, 0, 0.5), life=0.25, temp=1.0, cool=2.5, grav=G * 0.5, pal="steel",
                      smoke=None, spread=1.8, streak=0.03, land=DIE)

    def gun_smoke(self, a, u_dir, src):
        """Пороховой дым кольцом у ствола и латунная гильза к ногам."""
        n = 18
        ang = np.linspace(0, math.tau, n, endpoint=False)
        self.ps.spawn(n, (a[0] + u_dir[0] * 0.08, a[1] + u_dir[1] * 0.08, a[2]),
                      (np.cos(ang) * 0.5 + u_dir[0] * 0.6, np.sin(ang) * 0.25 + u_dir[1] * 0.6, np.sin(ang) * 0.4),
                      life=1.0, temp=0.5, cool=0.15, drag=3.0, buoy=0.3, size=1.6, grow=1.4, alpha=0.8, pal="steam",
                      smoke=None, life_var=0.25)
        self.ps.spawn(1, a, (-u_dir[0] * 0.6 + self.rng.normal(0, 0.3), -u_dir[1] * 0.6, 1.2), life=1.4, temp=0.9,
                      cool=0.2, grav=G, bounce=0.4, drag=0.3, pal="brass", smoke=None, size=1.2, land=BOUNCE,
                      life_var=0.0)

    # ---------- убийца ----------

    def _cast_assassin(self, u, gx, gy, dt, t):
        k = self._rate(26, dt)
        if k:
            a = self.rng.uniform(0, math.tau, k)
            self.ps.spawn(k, (gx + np.cos(a) * 0.35, gy + np.sin(a) * 0.2, self.rng.uniform(0, 0.3, k)),
                          (np.zeros(k), np.zeros(k), np.full(k, 0.5)), life=0.8, temp=self.rng.uniform(0.3, 0.6, k),
                          cool=0.3, buoy=0.2, drag=2.0, size=2.0, grow=1.0, alpha=0.8, pal="shadow", smoke=None,
                          life_var=0.3)

    def _trail_assassin(self, p, dirv, dt, t):
        self.puff(*p, "shadow", n=2, size=1.6, life=0.5, temp=0.45, up=0.1, spread=0.1)

    def _hit_assassin(self, x, y, z):
        a, b = (x - 0.28, y, z + 0.32), (x + 0.28, y, z - 0.3)                 # косой тёмный разрез
        t = np.linspace(0, 1, 30)
        w = np.sin(t * math.pi)
        self.ps.spawn(30, tuple(a[i] + (b[i] - a[i]) * t for i in range(3)), (0, 0, 0), life=0.22 + 0.12 * w,
                      temp=0.55 + 0.4 * w, cool=1.2, pal="shadow", smoke=None, size=1.0 + 1.2 * w, life_var=0.0)
        self.puff(x, y, z, "shadow", n=10, size=2.0, life=0.6, temp=0.45)

    # ---------- алхимик ----------

    def _cast_alchemist(self, u, gx, gy, dt, t):
        k = self._rate(22, dt)                                    # фитиль искрит
        if k:
            self.ps.spawn(k, (gx + 0.18, gy, 0.6), (0, 0, 0.8), life=0.3, temp=1.0, cool=2.5, grav=G * 0.4,
                          pal="fire", smoke=None, spread=1.4, streak=0.03, land=DIE)
        k = self._rate(5, dt)
        if k:
            self.puff(gx + 0.18, gy, 0.7, "scorch", n=k, size=1.6, life=0.9, temp=0.15, up=0.6, spread=0.1)

    def _trail_alchemist(self, p, dirv, dt, t):
        self.ps.spawn(2, p, (0, 0, 0.3), life=0.2, temp=1.0, cool=3.0, pal="fire", smoke=None, spread=0.8,
                      streak=0.02)

    def _hit_alchemist(self, x, y, z):
        self.shards(x, y, max(0.1, z), "glass", n=14, speed=1.8, temp=0.95, size=1.0, life=0.6)   # стекло
        self.puff(x, y, z + 0.1, "scorch", n=8, size=2.0, life=0.9, temp=0.12, up=0.7)

    # ---------- друид ----------

    def _cast_druid(self, u, gx, gy, dt, t):
        k = self._rate(22, dt)                                    # листья кружат вокруг
        if k:
            a = self.rng.uniform(0, math.tau, k)
            r = self.rng.uniform(0.35, 0.55, k)
            pal = "petal" if self.rng.random() < 0.3 else "nature"
            self.ps.spawn(k, (gx + np.cos(a) * r, gy + np.sin(a) * r * 0.6, self.rng.uniform(0.1, 0.8, k)),
                          (-np.sin(a) * 1.0, np.cos(a) * 0.6, np.full(k, 0.3)), life=0.8,
                          temp=self.rng.uniform(0.45, 0.85, k), cool=0.2, drag=0.8, size=2.0, pal=pal, smoke=None,
                          life_var=0.3)
        if self._rate(3, dt):                                     # светлячок
            self.ps.spawn(1, (gx + self.rng.normal(0, 0.4), gy + self.rng.normal(0, 0.2), self.rng.uniform(0.2, 1.0)),
                          (self.rng.normal(0, 0.2), 0, 0.15), life=1.2, temp=1.0, cool=0.3, pal="nature", smoke=None,
                          life_var=0.2)

    def _trail_druid(self, p, dirv, dt, t):
        if self.rng.random() < 0.4:
            self.ps.spawn(1, p, (self.rng.normal(0, 0.3), self.rng.normal(0, 0.3), -0.2), life=0.7, temp=0.7,
                          cool=0.3, grav=1.2, drag=2.5, size=1.3, pal="nature" if self.rng.random() < 0.7 else "petal",
                          smoke=None, land=DIE)

    def _hit_druid(self, x, y, z):
        self.ps.spawn(14, (x, y, z), (0, 0, 0.8), life=1.0, temp=self.rng.uniform(0.45, 0.85, 14), cool=0.2,
                      grav=1.5, drag=2.0, size=1.4, pal="nature", smoke=None, spread=1.2, land=DIE)
        self.ps.spawn(6, (x, y, z), (0, 0, 0.8), life=1.0, temp=0.8, cool=0.2, grav=1.5, drag=2.0, size=1.3,
                      pal="petal", smoke=None, spread=1.0, land=DIE)
        for _ in range(4):                                        # корни пробиваются из земли
            a = self.rng.uniform(0, math.tau)
            t = np.linspace(0, 1, 12)
            L = self.rng.uniform(0.25, 0.45)
            self.ps.spawn(12, (x + np.cos(a) * L * t, y + np.sin(a) * L * t * 0.6, 0.02 + 0.12 * np.sin(t * 3)),
                          (0, 0, 0), life=0.7 * (1.2 - 0.4 * t), temp=0.35, cool=0.2, pal="oil", smoke=None,
                          size=1.3 - 0.4 * t, life_var=0.0)

    # ---------- шаман ----------

    def _cast_shaman(self, u, gx, gy, dt, t):
        k = self._rate(26, dt)                                    # спираль ветра вверх по телу
        if k:
            a = t * 7 + self.rng.uniform(0, 0.6, k)
            h = (t * 1.3 + self.rng.random(k) * 0.2) % 1.1
            r = 0.45 - 0.15 * h
            self.ps.spawn(k, (gx + np.cos(a) * r, gy + np.sin(a) * r * 0.6, h), (-np.sin(a) * 1.5, np.cos(a), 0.6),
                          life=0.3, temp=0.6, cool=0.6, drag=1.0, pal="steam", smoke=None, alpha=0.7, streak=0.05,
                          life_var=0.2)
        if self._rate(5, dt):                                     # искра статики бежит по телу
            z = self.rng.uniform(0.2, 0.9)
            p = (gx + self.rng.normal(0, 0.15), gy, z)
            q = (p[0] + self.rng.normal(0, 0.1), gy, z + self.rng.normal(0, 0.12))
            self.pilot.arch.streak(p, q, "storm", life=0.08, n=6, size=1.0, temp=1.0)

    def _trail_shaman(self, p, dirv, dt, t):
        if self.rng.random() < 0.3:
            self.ps.spawn(2, p, (0, 0, 0), life=0.1, temp=1.0, cool=2.0, pal="storm", smoke=None, spread=1.2,
                          streak=0.03)

    def _hit_shaman(self, x, y, z):
        for _ in range(2):                                        # короткие разряды в стороны
            q = (x + self.rng.normal(0, 0.3), y + self.rng.normal(0, 0.15), max(0.05, z + self.rng.normal(-0.2, 0.15)))
            self.pilot.extra.bolt((x, y, z), q, life=0.1, wiggle=0.05, branches=False)

    # ---------- связующий ----------

    def _cast_binder(self, u, gx, gy, dt, t):
        n = 3                                                     # три нити обвивают фигурку, по ним бегут огоньки
        for i in range(n):
            a = t * 3 + i * math.tau / n
            for j in range(3):
                b = a + j * 0.18
                h = 0.15 + 0.3 * (i + j * 0.3) % 0.9
                self.ps.spawn(1, (gx + math.cos(b) * 0.42, gy + math.sin(b) * 0.25, h + 0.25 * math.sin(b * 2)),
                              (0, 0, 0), life=0.25, temp=0.6 if j else 1.0, cool=1.5, pal="spirit", smoke=None,
                              life_var=0.0)

    def _trail_binder(self, p, dirv, dt, t):                     # нить остаётся висеть за снарядом
        self.ps.spawn(2, p, (0, 0, 0), life=0.55, temp=0.7, cool=1.0, pal="spirit", smoke=None, jitter=0.01,
                      life_var=0.2)

    def _hit_binder(self, x, y, z):
        self.pilot.arch.ring(x, y, 0.35, "spirit", n=40, z=z, life=0.4, out=False, temp=0.9)
        self.ps.spawn(6, (x, y, z), (0, 0, 0.3), life=0.9, temp=1.0, cool=0.5, drag=2.0, pal="spirit", smoke=None,
                      spread=0.5)

    # ---------- некромант ----------

    def _cast_necro(self, u, gx, gy, dt, t):
        k = self._rate(12, dt)                                    # души стягиваются к некроманту
        if k:
            a = self.rng.uniform(0, math.tau, k)
            r = self.rng.uniform(0.9, 1.3, k)
            life = 0.7
            self.ps.spawn(k, (gx + np.cos(a) * r, gy + np.sin(a) * r * 0.7, self.rng.uniform(0.1, 0.4, k)),
                          (-np.cos(a) * r / life, -np.sin(a) * r * 0.7 / life, np.full(k, 0.5)), life=life,
                          temp=0.9, cool=0.5, pal="soul", smoke=None, size=1.8, streak=0.06, life_var=0.0)
        k = self._rate(6, dt)
        if k:
            self.ps.spawn(k, (gx, gy, 0.05), (0, 0, 0.3), life=0.5, temp=0.6, cool=0.4, pal="bone", smoke=None,
                          jitter=0.3)

    def _trail_necro(self, p, dirv, dt, t):
        self.ps.spawn(2, p, (0, 0, 0.4), life=0.45, temp=0.85, cool=0.8, drag=1.5, pal="soul", smoke=None,
                      spread=0.2, life_var=0.3)

    def _hit_necro(self, x, y, z):
        self.shards(x, y, z, "bone", n=12, speed=1.6, temp=0.8, size=1.2)       # костяные осколки
        self.ps.spawn(5, (x, y, z), (0, 0, 0.9), life=1.0, temp=0.9, cool=0.4, drag=1.5, buoy=0.3, pal="soul",
                      smoke=None, spread=0.4, streak=0.08)

    # ---------- хрономант ----------

    def _cast_chrono(self, u, gx, gy, dt, t):
        if int(t * 8) != int((t - dt) * 8):                      # циферблат под ногами, стрелка идёт
            self.tick_ring(gx, gy, 0.05, 0.6, "time", life=0.14, rot=t * 2)
        k = self._rate(30, dt)                                    # золотой песок сыплется сверху
        if k:
            self.ps.spawn(k, (gx + self.rng.normal(0, 0.2, k), gy + self.rng.normal(0, 0.1, k), np.full(k, 1.25)),
                          (0, 0, -1.2), life=0.7, temp=self.rng.uniform(0.6, 0.9, k), cool=0.3, grav=2.0,
                          pal="time", smoke=None, land=DIE, life_var=0.2)

    def _trail_chrono(self, p, dirv, dt, t):
        self.ps.spawn(2, p, (0, 0, -0.3), life=0.5, temp=0.8, cool=0.5, grav=2.0, pal="time", smoke=None,
                      spread=0.2, land=DIE)

    def _hit_chrono(self, x, y, z):
        self.tick_ring(x, y, max(0.05, z - 0.3), 0.4, "time", life=0.45, rot=self.rng.uniform(0, math.tau))
        self.ps.spawn(16, (x, y, z), (0, 0, 0.6), life=0.8, temp=0.8, cool=0.3, grav=3.0, drag=1.0, pal="time",
                      smoke=None, spread=1.0, land=DIE)

    # ---------- гравитант ----------

    def _cast_gravity(self, u, gx, gy, dt, t):
        k = self._rate(24, dt)                                    # спираль внутрь к фигурке
        if k:
            a = self.rng.uniform(0, math.tau, k)
            r = 0.75
            self.ps.spawn(k, (gx + np.cos(a) * r, gy + np.sin(a) * r * 0.6, self.rng.uniform(0.1, 0.7, k)),
                          (-np.cos(a) * 1.0 - np.sin(a) * 1.4, (-np.sin(a) * 1.0 + np.cos(a) * 1.4) * 0.6,
                           np.zeros(k)), life=0.45, temp=0.85, cool=0.6, drag=1.0, pal="gravity", smoke=None,
                          life_var=0.0)
        if self._rate(4, dt):                                     # камешек поднимается с земли и парит
            self.ps.spawn(1, (gx + self.rng.normal(0, 0.4), gy + self.rng.normal(0, 0.25), 0.02), (0, 0, 0.35),
                          life=1.2, temp=0.6, cool=0.1, drag=0.5, size=1.5, pal="stone", smoke=None, life_var=0.2)

    def _trail_gravity(self, p, dirv, dt, t):
        a = t * 22
        for s in (0, math.pi):
            self.ps.spawn(1, (p[0] - dirv[1] * 0.1 * math.cos(a + s), p[1] + dirv[0] * 0.1 * math.cos(a + s),
                              p[2] + 0.1 * math.sin(a + s)), (0, 0, 0), life=0.3, temp=0.85, cool=1.0,
                          pal="gravity", smoke=None, life_var=0.0)

    def _hit_gravity(self, x, y, z):
        self.pilot.arch.ring(x, y, 0.6, "gravity", n=60, z=max(0.05, z - 0.3), life=0.35, out=False, temp=0.9)
        self.ps.spawn(6, (x, y, 0.02), (0, 0, 0.6), life=0.9, temp=0.6, cool=0.1, drag=1.0, size=1.4, pal="stone",
                      smoke=None, spread=0.4, jitter=0.25)

    # ---------- геомант ----------

    def _cast_geomancer(self, u, gx, gy, dt, t):
        if self._rate(5, dt):
            self.ps.spawn(1, (gx + self.rng.normal(0, 0.35), gy + self.rng.normal(0, 0.2), 0.02), (0, 0, 0.5),
                          life=0.9, temp=0.6, cool=0.1, drag=0.8, size=1.5, pal="stone", smoke=None, life_var=0.2)
        k = self._rate(10, dt)
        if k:
            self.puff(gx, gy, 0.05, "dust", n=k, size=1.6, life=0.7, temp=0.45, up=0.15, spread=0.5)

    def _trail_geomancer(self, p, dirv, dt, t):
        if self.rng.random() < 0.4:
            self.ps.spawn(1, p, (0, 0, 0), life=0.5, temp=0.6, cool=0.2, grav=G, pal="stone", smoke=None,
                          land=DIE)

    def _hit_geomancer(self, x, y, z):
        self.shards(x, y, z, "stone", n=12, speed=1.5, temp=0.65, size=1.4)
        self.puff(x, y, 0.05, "dust", n=10, size=2.0, life=0.8, temp=0.45, up=0.3, spread=0.7)
        self.ps.spawn(5, (x, y, z), (0, 0, 0.6), life=0.5, temp=1.0, cool=1.0, grav=G * 0.6, pal="glass",
                      smoke=None, spread=1.0, land=DIE)              # кристаллики блестят

    # ---------- бард ----------

    def _cast_bard(self, u, gx, gy, dt, t):
        if self._rate(4, dt):                                     # нота поднимается и уплывает
            self.glyph(NOTE if self.rng.random() < 0.6 else NOTE2, gx + self.rng.normal(0, 0.3),
                       gy + self.rng.normal(0, 0.1), self.rng.uniform(0.6, 1.0), "sound",
                       vel=(self.rng.normal(0, 0.25), 0, 0.5), life=1.0, temp=0.95)
        if int(t * 2) != int((t - dt) * 2):                      # кольцо звука в такт
            self.pilot.arch.ring(gx, gy, 0.7, "sound", n=60, z=0.05, life=0.35, out=True, temp=0.75)

    def _trail_bard(self, p, dirv, dt, t):
        if int(t * 8) != int((t - dt) * 8):
            self.glyph(NOTE, p[0], p[1], p[2], "sound", vel=(0, 0, 0.3), life=0.5, temp=0.9, size=1.2)

    def _hit_bard(self, x, y, z):
        for k in range(3):
            a = -0.9 + 0.9 * k
            self.glyph(NOTE if k != 1 else NOTE2, x, y, z, "sound", vel=(math.sin(a) * 0.6, 0, 0.6 + 0.2 * math.cos(a)),
                       life=0.8, temp=0.95)
        self.pilot.arch.ring(x, y, 0.45, "sound", n=50, z=max(0.05, z - 0.3), life=0.3, out=True, temp=0.85)

    # ---------- зельевар ----------

    def _cast_brewer(self, u, gx, gy, dt, t):
        k = self._rate(9, dt)                                     # пузыри
        if k:
            self.ps.spawn(k, (gx + self.rng.normal(0, 0.25, k), gy + self.rng.normal(0, 0.12, k), np.full(k, 0.2)),
                          (0, 0, 0.6), life=0.8, temp=0.9, cool=0.5, buoy=0.3, drag=1.0, size=1.4, pal="poison",
                          smoke=None, jitter=0.03, life_var=0.3)
        k = self._rate(6, dt)
        if k:
            self.puff(gx, gy, 0.6, "gas", n=k, size=1.8, life=1.0, temp=0.6, up=0.4, spread=0.25)

    def _trail_brewer(self, p, dirv, dt, t):
        if self.rng.random() < 0.4:                               # капли падают с летящей склянки
            self.ps.spawn(1, p, (0, 0, 0), life=0.6, temp=0.8, cool=0.2, grav=G, pal="poison", smoke=None, land=DIE)

    def _hit_brewer(self, x, y, z):
        self.ps.spawn(14, (x, y, max(0.1, z)), (0, 0, 1.4), life=0.6, temp=0.85, cool=0.3, grav=G, drag=0.4,
                      pal="poison", smoke=None, spread=1.4, land=DIE)
        self.ps.spawn(8, (x, y, 0.1), (0, 0, 0.5), life=0.9, temp=0.9, cool=0.4, buoy=0.3, drag=1.5, size=1.4,
                      pal="poison", smoke=None, jitter=0.25)
        self.puff(x, y, 0.2, "gas", n=8, size=2.2, life=1.1, temp=0.6, up=0.3, spread=0.4)

    # ---------- берсерк крови ----------

    def _cast_bloodrager(self, u, gx, gy, dt, t):
        k = self._rate(10, dt)                                    # пар от разгорячённого тела
        if k:
            self.puff(gx, gy, self.rng.uniform(0.4, 0.9), "steam", n=k, size=1.6, life=0.8, temp=0.5, up=0.7,
                      spread=0.25)
        k = self._rate(10, dt)                                    # штрихи ярости вверх
        if k:
            a = self.rng.uniform(0, math.tau, k)
            self.ps.spawn(k, (gx + np.cos(a) * 0.35, gy + np.sin(a) * 0.2, np.full(k, 0.1)), (0, 0, 2.2), life=0.3,
                          temp=0.9, cool=1.5, drag=1.0, pal="rage", smoke=None, streak=0.08, life_var=0.3)

    def _trail_bloodrager(self, p, dirv, dt, t):
        if self.rng.random() < 0.5:
            self.ps.spawn(1, p, (0, 0, 0), life=0.6, temp=0.7, cool=0.2, grav=G, pal="blood", smoke=None, land=DIE)

    def _hit_bloodrager(self, x, y, z):
        self.ps.spawn(16, (x, y, z), (0, 0, 1.0), life=0.9, temp=self.rng.uniform(0.4, 0.8, 16), cool=0.1, grav=G,
                      drag=0.3, pal="blood", smoke=None, spread=1.6, land=DIE)
        for k in (-1, 1):                                          # два красных росчерка крест-накрест
            a, b = (x - 0.25, y, z + 0.25 * k), (x + 0.25, y, z - 0.25 * k)
            self.pilot.arch.streak(a, b, "rage", life=0.2, n=24, size=1.4, temp=1.0)

    # ---------- тактик ----------

    def _cast_tactician(self, u, gx, gy, dt, t):
        if int(t * 1.6) != int((t - dt) * 1.6):                  # флажок вспыхивает над головой
            self.glyph(FLAG, gx + 0.05, gy, 1.15, "light", vel=(0, 0, 0.15), life=0.6, temp=1.0)
        k = self._rate(8, dt)
        if k:
            self.ps.spawn(k, (gx, gy, 0.6), (0, 0, 0.3), life=0.3, temp=1.0, cool=2.0, pal="light", smoke=None,
                          jitter=0.35)

    def _trail_tactician(self, p, dirv, dt, t):
        if self.rng.random() < 0.4:
            self.ps.spawn(1, p, (0, 0, 0), life=0.3, temp=1.0, cool=1.5, pal="light", smoke=None)

    def _hit_tactician(self, x, y, z):
        for k in range(2):                                        # стрелки-приказы спускаются на цель
            self.view.vfx.after(0.08 * k, lambda k=k: self.glyph(CHEVRON, x, y, z + 0.75 - 0.12 * k, "light",
                                                                  vel=(0, 0, -0.6), life=0.45, temp=1.0))
        self.pilot.arch.ring(x, y, 0.4, "light", n=50, z=0.05, life=0.35, out=False, temp=0.9)

    # ---------- таран ----------

    def _cast_ram(self, u, gx, gy, dt, t):
        k = self._rate(14, dt)                                    # копыта роют землю
        if k:
            self.ps.spawn(k, (gx + self.rng.normal(0, 0.2, k), gy + self.rng.normal(0, 0.1, k), np.full(k, 0.03)),
                          (0, 0, 0.8), life=0.6, temp=0.5, cool=0.3, grav=G * 0.5, drag=1.0, size=1.4, pal="dust",
                          smoke=None, spread=0.6, land=DIE)

    def _trail_ram(self, p, dirv, dt, t):
        self.puff(p[0], p[1], 0.05, "dust", n=1, size=1.6, life=0.6, temp=0.45, up=0.2, spread=0.3)

    def _hit_ram(self, x, y, z):
        self.pilot.arch.ring(x, y, 0.8, "dust", n=80, z=0.05, life=0.45, out=True, temp=0.55)
        self.shards(x, y, 0.1, "stone", n=10, speed=1.4, temp=0.6, size=1.3)
