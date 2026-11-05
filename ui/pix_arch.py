"""Архетипы пиксельных навыков: один набор приёмов на все навыки, которые не нарисованы вручную
(огонь и лёд — ui/pix_spells.py, оружие — ui/pix_weapons.py, свет жреца — ui/pix_light.py).

Архетип выбирается по эффектам навыка, цвет — по стихии навыка или по классу:
  shot    — снаряд от руки в цель (стрела у лучников — тонкий длинный штрих), удар — вспышка и брызги;
  chain   — молния в цель и скачки на соседних врагов;
  flask   — склянка дугой в клетку, разбивается: брызги, лужица-рябь;
  sky     — удары с неба по площади (гроза, камнепад, залп стрел);
  area    — метка площади: кольцо сходится, вспыхивает купол (сон, стяжка, замедление, перестроение);
  line    — разлом/волна по линии от героя;
  nova    — волна от себя кольцом (удар вокруг, отталкивание, звуковая волна);
  aura    — бафф на себя: вихрь частиц вверх по фигурке и кольцо у ног (облики, ярость, невидимость, песня);
  ally    — луч от героя к союзнику и аура на нём (щиты, бафы, перемотка, связь);
  dash    — рывок: шлейф-послеобраз по пути, вспышка в конце;
  melee   — дуга удара по цели вплотную;
  summon  — круг-руна на земле, вспышка, из земли поднимается дымка (призывы, ловушки, постройки, трупы).
Время удара — из боя (config.hit), визуал растягивается ровно на него.
"""
import math

import numpy as np

from ui import projection as P
from ui.pix_motif import GHOST_TINT as GHOSTS, MOTIF_CLASSES
from ui.pixsim import DIE

G = 9.0
TAG_PAL = {"fire": "fire", "ice": "ice", "water": "water", "storm": "storm", "poison": "poison", "oil": "dust"}
CLASS_PAL = {"archer": "steel", "trapper": "steel", "assassin": "shadow", "druid": "nature", "shaman": "storm",
             "bard": "sound", "alchemist": "fire", "ram": "dust", "necro": "bone", "chrono": "time",
             "gravity": "gravity", "geomancer": "stone", "brewer": "poison", "bloodrager": "blood",
             "tactician": "light", "binder": "spirit", "cryo": "ice", "mage": "shadow", "warrior": "steel",
             "guardian": "steel", "priest": "light"}
ARROW = {"archer", "trapper"}
FLASK = {"alchemist", "brewer"}
SKY = {"volley", "thunderstorm", "rockfall", "e_meteor", "e_avalanche", "e_thunderstorm", "meteor_rain", "arrow_rain",
       "meteor"}
SELF_ONLY = {"form", "stealth", "song", "fuse", "merge", "focus"}
MOVE = {"leap_to", "rush", "teleport", "swap", "regroup", "toss"}
SUMMON = {"summon", "place_object", "trap", "corpse", "revive", "wall", "watch", "terrain", "terrain_cast"}


def classify(sid, sk, cls=None):
    """Архетип навыка по его эффектам."""
    types = {e["type"] for e in sk.get("effects", [])}
    tgt, rng_, rad = sk.get("target"), sk.get("range", 0), sk.get("radius", 0) or max(
        [e.get("radius", 0) for e in sk.get("effects", [])] + [0])
    if sid in SKY:
        return "sky"
    if "chain" in types:
        return "chain"
    if "line" in types:
        return "line"
    if types & MOVE:
        return "dash"
    if tgt == "enemy":
        if rng_ <= 1:
            return "melee"
        return "shot"
    if tgt == "ally":
        return "ally"
    if tgt == "self":
        if rad and types & {"damage", "push", "knockback", "stun", "sleep", "taunt", "status", "pull", "gather"}:
            return "nova"
        return "aura"
    # клетка
    if types & SUMMON or types & {"hazard"} and "damage" not in types and cls not in FLASK:
        return "summon"
    if cls in FLASK or types & {"status"} and rng_ > 1:
        return "flask"
    if "damage" in types and rad:
        return "sky" if rng_ >= 3 and cls in ("shaman", "geomancer") else "area"
    return "area"


class Arch:
    def __init__(self, pilot):
        self.pilot = pilot
        self.rng = np.random.default_rng(31)
        self.cur = None             # класс героя, чей навык сейчас рисуется (почерк, ui/pix_motif.py)

    @property
    def ps(self):
        return self.pilot.spells.ps

    @property
    def view(self):
        return self.pilot.view

    # ---------- вход ----------

    def palette(self, sk, u):
        tag = next((e.get("tag") for e in sk.get("effects", []) if e.get("tag")), None)
        if tag in TAG_PAL:
            return TAG_PAL[tag]
        cls = u.proto_id if u.proto_id in CLASS_PAL else None
        return CLASS_PAL.get(cls, "shadow" if u.team != "player" else "light")

    def skill(self, sid, u, sk, ctx, hit):
        kind = classify(sid, sk, u.proto_id)
        pal = self.palette(sk, u)
        hit = hit or 0.0
        fn = getattr(self, "_" + kind)
        cls = u.proto_id if u.proto_id in MOTIF_CLASSES and u.team == "player" else None
        return self.scoped(cls, fn)(u, sk, ctx, max(0.0, hit), pal, sid)

    def scoped(self, cls, fn):
        """fn и всё, что она отложит (vfx.after, эмиттеры), видят класс героя — для почерка (ui/pix_motif.py)."""
        if cls is None:
            return fn

        def run(*a):
            em, V = self.pilot.spells.emitters, self.view.vfx
            n1, n2 = len(em), len(V.pending)
            prev, self.cur = self.cur, cls
            try:
                return fn(*a)
            finally:
                self.cur = prev
                for i in range(n1, len(em)):
                    em[i] = self.scoped(cls, em[i])
                for i in range(n2, len(V.pending)):
                    t, f = V.pending[i]
                    V.pending[i] = (t, self.scoped(cls, f))
        return run

    # ---------- приёмы ----------

    def _ground(self, ctx):
        g = ctx.get("target_ground")
        return P.unproject(*g) if g else None

    def burst(self, x, y, z, pal, n=30, speed=1.6, life=0.5, up=0.8):
        if self.cur:
            self.pilot.motif.hit(self.cur, x, y, z)
        self.ps.spawn(n, (x, y, z), (0, 0, up), life=life, temp=0.85, cool=1.6, grav=G * 0.4, drag=1.5, pal=pal,
                      smoke=None, spread=speed, land=DIE, life_var=0.3)
        self.ps.spawn(max(4, n // 3), (x, y, z), (0, 0, 0), life=0.15, temp=1.0, cool=4.0, pal=pal, smoke=None,
                      spread=speed * 0.6)

    def ring(self, x, y, R, pal, n=140, z=0.05, life=0.5, out=True, temp=0.7):
        ang = np.linspace(0, math.tau, n, endpoint=False)
        if out:
            pos = (x + np.cos(ang) * 0.2, y + np.sin(ang) * 0.2, np.full(n, z))
            sp = (R + 0.2) * 3.0
            drag = 3.0
        else:
            pos = (x + np.cos(ang) * R, y + np.sin(ang) * R, np.full(n, z))
            sp = -(R - 0.15) / life
            drag = 0.0
        self.ps.spawn(n, pos, (np.cos(ang) * sp, np.sin(ang) * sp, np.zeros(n)), life=life, temp=temp, cool=0.8,
                      drag=drag, pal=pal, smoke=None, size=1.3, life_var=0.0)

    def _motif_area(self, x, y, R, src):
        """Почерк класса на каждой фигурке в площади (или в центре, если там пусто)."""
        if not self.cur or self.view.combat is None:
            return
        hit = False
        for f in self.view.combat.alive():
            if f is src or f.obj:
                continue
            fx, fy = self.view.ground_pos(f)
            if math.hypot(fx - x, fy - y) <= R:
                self.pilot.motif.hit(self.cur, fx, fy, 0.5)
                hit = True
        if not hit:
            self.pilot.motif.hit(self.cur, x, y, 0.3)

    def streak(self, a, b, pal, life=0.2, n=None, size=1.2, temp=0.8):
        d = math.dist(a, b)
        n = n or max(6, int(d / 0.05))
        t = np.linspace(0, 1, n)
        self.ps.spawn(n, tuple(a[i] + (b[i] - a[i]) * t for i in range(3)), (0, 0, 0), life=life * (0.5 + 0.5 * t),
                      temp=temp, cool=1.5, pal=pal, smoke=None, size=size, life_var=0.0)

    def mover(self, a, b, dur, pal, arc=0.0, kind="orb", on_hit=None):
        """Снаряд a → b за dur: голова и хвост; on_hit — в конце."""
        st = [0.0]
        d = math.dist(a[:2], b[:2]) or 1.0
        dirv = tuple((b[i] - a[i]) / d for i in range(3))
        cls = self.cur

        def at(k):
            return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k,
                    a[2] + (b[2] - a[2]) * k + math.sin(math.pi * k) * arc)

        def step(dt):
            st[0] += dt
            k = min(1.0, st[0] / max(dur, 1e-3))
            p = at(k)
            if cls:
                self.pilot.motif.trail(cls, p, dirv, dt, st[0])
            if kind == "farrow":                   # горящая стрела: древко и огненный хвост
                q = at(max(0.0, k - 0.05))
                self.streak(q, p, "dust", life=0.05, n=6, size=1.0, temp=0.55)
                self.ps.spawn(3, p, tuple(-c * 0.4 for c in dirv), life=0.3, temp=0.95, cool=2.0, buoy=0.8,
                              drag=2.0, pal="fire", smoke="dust", smoke_at=0.3, spread=0.15, life_var=0.3)
            elif kind == "arrow":                  # стрела: тонкий длинный штрих по ходу полёта
                q = at(max(0.0, k - 0.06))
                self.streak(q, p, pal, life=0.05, n=8, size=1.0, temp=0.6)
                self.ps.spawn(1, p, (0, 0, 0), life=0.05, temp=0.95, cool=0.0, pal=pal, smoke=None, life_var=0.0)
            elif kind == "flask":
                self.ps.spawn(3, p, (0, 0, 0), life=0.05, temp=0.55, cool=0.0, pal=pal, smoke=None, size=1.2,
                              jitter=0.02, life_var=0.0)
                self.ps.spawn(1, (p[0] - 0.02, p[1], p[2] + 0.05), (0, 0, 0), life=0.05, temp=1.0, cool=0.0,
                              pal="steam", smoke=None, life_var=0.0)
            else:
                self.ps.spawn(6, p, (0, 0, 0), life=0.06, temp=0.9, cool=0.0, pal=pal, smoke=None, size=1.4,
                              jitter=0.04, life_var=0.0)
                self.ps.spawn(4, p, tuple(-c * 0.5 for c in dirv), life=0.35, temp=0.7, cool=1.6, drag=2.0,
                              pal=pal, smoke=None, spread=0.25, life_var=0.2)
            if st[0] >= dur:
                if on_hit:
                    on_hit(b)
                return False
            return True
        self.pilot.spells.emitters.append(step)

    # ---------- архетипы ----------

    def _shot(self, u, sk, ctx, hit, pal, sid):
        S = self.pilot.spells
        tgt = ctx.get("target_unit")
        g = self._ground(ctx)
        if tgt is None and g is None:
            return hit
        a = S.hand(u, self.view.ground_pos(tgt) if tgt is not None else g)
        b = S.contact(a, tgt) if tgt is not None else (g[0], g[1], 0.5)
        if u.proto_id == "trapper" and tgt is not None:          # ловчий стреляет пулей
            return self.pilot.extra.gunshot(u, tgt, max(0.06, hit))
        arrow = u.proto_id in ARROW
        big = any(e.get("amount", 0) >= 40 for e in sk.get("effects", []))

        def hit_fx(p):
            self.burst(p[0], p[1], p[2], pal, n=40 if big else 24, speed=1.8 if big else 1.2)
            if big:
                self.view.vfx.screen_fx(shake=3)
        self.mover(a, b, max(0.12, hit), pal, arc=0.15 if not arrow else 0.05, kind="arrow" if arrow else "orb",
                   on_hit=hit_fx)
        return hit

    def _chain(self, u, sk, ctx, hit, pal, sid):
        S = self.pilot.spells
        tgt = ctx.get("target_unit")
        if tgt is None:
            return hit
        jumps = next((e.get("jumps", 2) for e in sk.get("effects", []) if e["type"] == "chain"), 2)

        def zap(a, b):                          # ломаная молния: середина уходит вбок
            pts = [a]
            for k in range(1, 6):
                f = k / 6
                pts.append(tuple(a[i] + (b[i] - a[i]) * f + (self.rng.normal(0, 0.12) if i < 2 else
                                                              self.rng.normal(0, 0.1)) for i in range(3)))
            pts.append(b)
            for p, q in zip(pts, pts[1:]):
                self.streak(p, q, pal, life=0.18, size=1.3, temp=1.0)

        def strike():
            a = S.hand(u, self.view.ground_pos(tgt))
            b = S.contact(a, tgt)
            zap(a, b)
            self.burst(*b, pal, n=20)
            c = self.view.combat
            if c is None:
                return
            from sim.grid import cheb
            prev, seen = tgt, {tgt.id}
            for j in range(jumps):
                near = [v for v in c.alive() if v.id not in seen and not v.obj and v.is_enemy(u)
                        and cheb(v.cell, prev.cell) <= 3]
                if not near:
                    break
                nxt = min(near, key=lambda v: cheb(v.cell, prev.cell))
                seen.add(nxt.id)
                pa, pb = S.unit_point(prev), S.unit_point(nxt)
                self.view.vfx.after(0.07 * (j + 1), lambda pa=pa, pb=pb: (zap(pa, pb), self.burst(*pb, pal, n=14)))
                prev = nxt
        self.view.vfx.after(min(hit, 0.15), strike)
        return hit

    def _flask(self, u, sk, ctx, hit, pal, sid):
        g = self._ground(ctx)
        if g is None:
            return hit
        S = self.pilot.spells
        a = S.hand(u, g)
        b = (g[0], g[1], 0.1)
        R = (sk.get("radius", 1) or 1) + 0.4

        def smash(p):
            n = 80
            ang = self.rng.uniform(0, math.tau, n)
            sp = self.rng.uniform(1.0, 2.4, n)
            self.ps.spawn(n, (np.full(n, p[0]), np.full(n, p[1]), np.full(n, 0.15)),
                          (np.cos(ang) * sp, np.sin(ang) * sp, self.rng.uniform(1.4, 3.0, n)), life=0.8, temp=0.7,
                          cool=0.4, grav=G, pal=pal, smoke=None, land=DIE, life_var=0.25)
            self.ps.spawn(24, (p[0], p[1], 0.2), (0, 0, 0.5), life=1.0, temp=0.5, cool=0.2, buoy=0.6, drag=2.0,
                          size=1.8, grow=1.2, pal=pal, smoke=None, spread=0.8, jitter=0.25)
            from ui.pix_quake import Quake
            self.pilot.quakes.append(Quake(p[0], p[1], 0.0, S.terrain_at, seed=int(self.rng.integers(1 << 30)),
                                           life=1.3, ripple_r=R, ripple_all=True))
        self.mover(a, b, max(0.2, hit), pal, arc=1.1, kind="flask", on_hit=smash)
        return hit

    def _sky(self, u, sk, ctx, hit, pal, sid):
        g = self._ground(ctx)
        if g is None:
            return hit
        R = (sk.get("radius", 1) or 1) + 0.4
        n = 9 if sid != "volley" else 16
        dur = max(0.3, hit)
        arrow = u.proto_id in ARROW or sid in ("volley", "arrow_rain")
        fire = any(e.get("tag") == "fire" for e in sk.get("effects", []))
        if sid in ("volley", "arrow_rain"):
            pal = "fire" if fire else "steel"                       # огненный залп — горящие стрелы
        for i in range(n):                                  # удары по площади вразнобой, последние — к удару боя
            ang, rr = self.rng.uniform(0, math.tau), R * math.sqrt(self.rng.random())
            x, y = g[0] + math.cos(ang) * rr, g[1] + math.sin(ang) * rr
            t0 = dur * (0.35 + 0.65 * i / n)
            top = (x - 0.5, y - 0.2, 3.2)

            def go(x=x, y=y, top=top):
                def land(p):
                    self.burst(p[0], p[1], 0.1, pal if not arrow or fire else "dust", n=10, speed=1.0, life=0.4)
                    if fire:                                      # горящая стрела торчит и тлеет
                        self.ps.spawn(14, (p[0], p[1], 0.15), (0, 0, 0.8), life=0.6, temp=0.9, cool=1.2, buoy=1.0,
                                      drag=2.0, pal="fire", smoke="dust", smoke_at=0.25, spread=0.15, tall=1.0)
                self.mover(top, (x, y, 0.05), 0.18, pal, kind="farrow" if fire else ("arrow" if arrow else "orb"),
                           on_hit=land)
            self.view.vfx.after(max(0.0, t0 - 0.18), go)
        self.view.vfx.after(dur, lambda: self.view.vfx.screen_fx(shake=3))
        return hit

    def _area(self, u, sk, ctx, hit, pal, sid):
        g = self._ground(ctx)
        if g is None:
            return hit
        R = (sk.get("radius", 1) or 1) + 0.4
        dur = max(0.25, hit)
        self.ring(g[0], g[1], R, pal, life=dur, out=False)

        def pop():
            self.ring(g[0], g[1], 0.3, pal, n=120, life=0.45, out=True, temp=0.85)
            m = 50
            rr = R * np.sqrt(self.rng.random(m))
            aa = self.rng.uniform(0, math.tau, m)
            self.ps.spawn(m, (g[0] + np.cos(aa) * rr, g[1] + np.sin(aa) * rr, np.full(m, 0.05)), (0, 0, 1.2),
                          life=self.rng.uniform(0.4, 0.9, m), temp=0.8, cool=1.0, pal=pal, smoke=None, drag=1.0,
                          life_var=0.0)
            self._motif_area(g[0], g[1], R, u)
        self.view.vfx.after(dur, pop)
        return hit

    def _line(self, u, sk, ctx, hit, pal, sid):
        g = self._ground(ctx)
        x0, y0 = self.view.ground_pos(u)
        if g is None:
            return hit
        d = (g[0] - x0, g[1] - y0)
        L = math.hypot(*d) or 1.0
        d = (d[0] / L, d[1] / L)
        length = next((e.get("length", 3) for e in sk.get("effects", []) if e["type"] == "line"), 3) + 0.5
        dur = max(0.2, hit)
        steps = 8
        for i in range(steps):
            t = 0.5 + length * i / steps
            x, y = x0 + d[0] * t, y0 + d[1] * t
            self.view.vfx.after(dur * i / steps, lambda x=x, y=y: self.burst(x, y, 0.05, pal, n=14, speed=0.9,
                                                                             life=0.5, up=1.4))
        if pal in ("dust", "stone", "steel"):
            from ui.pix_quake import Quake
            S = self.pilot.spells
            self.view.vfx.after(dur, lambda: self.pilot.quakes.append(
                Quake(x0 + d[0] * length * 0.55, y0 + d[1] * length * 0.55, 0.9, S.terrain_at,
                      seed=int(self.rng.integers(1 << 30)), style="furrow", dirv=d, life=3.0)))
        return hit

    def _nova(self, u, sk, ctx, hit, pal, sid):
        R = max([e.get("radius", 0) for e in sk.get("effects", [])] + [sk.get("radius", 1) or 1])
        a = self.view.anim(u)
        a.windup, a.windup_total = hit, max(hit, 0.01)

        def wave():
            x, y = self.view.ground_pos(u)
            self.ring(x, y, R, pal, n=200, life=0.5, out=True, temp=0.8)
            self.ring(x, y, R, pal, n=100, z=0.4, life=0.35, out=True, temp=0.6)
            self.view.vfx.screen_fx(shake=2)
            self._motif_area(x, y, R, u)
        self.view.vfx.after(hit, wave)
        return hit

    def _aura(self, u, sk, ctx, hit, pal, sid):
        st = [0.0]
        dur = 0.9

        def swirl(dt):
            st[0] += dt
            if not u.alive:
                return False
            x, y = self.view.ground_pos(u)
            k = st[0] / dur
            n = 10
            ang = self.rng.uniform(0, math.tau, n) + st[0] * 6
            r = 0.45 * (1 - 0.4 * k)
            self.ps.spawn(n, (x + np.cos(ang) * r, y + np.sin(ang) * r * 0.6, self.rng.uniform(0.0, 0.6, n)),
                          (-np.sin(ang) * 1.2, np.cos(ang) * 0.7, np.full(n, 1.4)), life=0.5, temp=0.8, cool=1.2,
                          drag=1.0, pal=pal, smoke=None, life_var=0.3)
            return st[0] < dur
        self.pilot.spells.emitters.append(swirl)
        x, y = self.view.ground_pos(u)
        self.ring(x, y, 0.6, pal, n=80, life=0.4, out=True)
        if self.cur:
            self.pilot.motif.hit(self.cur, x, y, 0.5)
        return hit

    def _ally(self, u, sk, ctx, hit, pal, sid):
        S = self.pilot.spells
        ally = ctx.get("target_unit") or u
        dur = max(0.15, hit)
        if ally is not u:
            a = S.hand(u, self.view.ground_pos(ally))
            b = S.contact(a, ally)
            self.mover(a, b, dur, pal, arc=0.3)
        if self.cur in GHOSTS:                  # хрономант: послеобраз «перемотки» на союзнике
            self.view.vfx.after(dur, lambda: self.pilot.motif.ghost(ally, 0.7, "chrono"))
        self.view.vfx.after(dur, lambda: self._aura(ally, sk, {}, 0.0, pal, sid))
        return hit

    def _dash(self, u, sk, ctx, hit, pal, sid):
        x0, y0 = self.view.ground_pos(u)
        st = [0.0]

        def trail(dt):                          # шлейф-послеобраз: пока герой летит, за ним — след
            st[0] += dt
            if self.cur in GHOSTS and int(st[0] * 14) != int((st[0] - dt) * 14):
                self.pilot.motif.ghost(u, cls=self.cur)
            x, y = self.view.ground_pos(u)
            self.ps.spawn(8, (x, y, 0.5), (0, 0, 0), life=0.3, temp=0.65, cool=1.5, pal=pal, smoke=None,
                          jitter=0.18, life_var=0.3)
            if st[0] > 0.6 or not u.alive:
                x, y = self.view.ground_pos(u)
                self.burst(x, y, 0.4, pal, n=26)
                return False
            return True
        self.view.vfx.after(hit, lambda: self.pilot.spells.emitters.append(trail))
        self.burst(x0, y0, 0.4, pal, n=16, speed=1.0)
        return hit

    def _melee(self, u, sk, ctx, hit, pal, sid):
        tgt = ctx.get("target_unit")
        a = self.view.anim(u)
        a.windup, a.windup_total = hit, max(hit, 0.01)
        if tgt is None:
            return hit
        W = self.pilot.weapons

        def strike():
            from ui.pix_weapons import _dir
            tx, ty = self.view.ground_pos(tgt)
            d = _dir(self.view.ground_pos(u), (tx, ty))
            a.lunge, a.lunge_dir = 0.18, d
            W.slash(tx - d[0] * 0.1, ty - d[1] * 0.1, d, 0.8, n=48, pal=pal)
            self.burst(tx, ty, 0.5, pal, n=14, speed=1.0)
        self.view.vfx.after(hit, strike)
        return hit

    def _summon(self, u, sk, ctx, hit, pal, sid):
        g = self._ground(ctx)
        if g is None:
            x, y = self.view.ground_pos(u)
        else:
            x, y = g
        dur = max(0.2, hit)
        self.ring(x, y, 0.8, pal, n=110, life=dur + 0.3, out=False, temp=0.65)

        def rise():
            self.ps.spawn(40, (x, y, 0.05), (0, 0, 1.2), life=0.9, temp=0.6, cool=0.5, buoy=0.5, drag=2.0, size=1.6,
                          grow=1.0, pal=pal, smoke=None, spread=0.6, jitter=0.3)
            self.burst(x, y, 0.3, pal, n=20, speed=1.2)
        self.view.vfx.after(dur, rise)
        return hit
