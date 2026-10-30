"""Пилот стилей эффектов: хореография навыков общая, рисует выбранный стиль (looks.py).

Навыки: Огненный шар (и ветки: Метеор, Огненные стрелы), Буран, Ледяная стена; горящие клетки, горящие юниты,
ледяные клетки. Остальные навыки в этих стилях — старые эффекты.

Наследует PixelPilot: та же логика «что видно, то и случилось» (клетки и фигурки загораются / замерзают, когда
до них долетело), события и площадь навыка — общие; переопределено только рисование.
"""
import math

import numpy as np
import pygame

from ui import projection as P
from ui.fxlab import LOOKS
from ui.fxlab.frame import LabFrame
from ui.pix_battle import PixelPilot
from ui.settings import SETTINGS

BODY = 0.45


class Item:
    __slots__ = ("t0", "dur", "fn", "alive")

    def __init__(self, t0, dur, fn, alive=None):
        self.t0, self.dur, self.fn, self.alive = t0, dur, fn, alive


class LabPilot(PixelPilot):
    def __init__(self, view):
        super().__init__(view)
        self.frame = LabFrame()
        self.items = []
        self._looks = {}
        self.ice_born = {}

    # ---------- стиль ----------

    @property
    def style(self):
        return SETTINGS.get("fx_style", "pixel")

    @property
    def on(self):
        return self.style in LOOKS

    @property
    def look(self):
        lk = self._looks.get(self.style)
        if lk is None:
            from ui.fxlab import looks
            lk = self._looks[self.style] = looks.make(self.style, self)
        return lk

    def reset(self):
        super().reset()
        self.items.clear()
        self.ice_born.clear()
        for lk in self._looks.values():
            lk.reset()

    def toggle(self):
        self.items.clear()
        for lk in self._looks.values():
            lk.reset()
        return super().toggle()

    def add(self, dur, fn, delay=0.0, alive=None):
        """Эффект на время dur: fn(кадр, доля 0..1, секунды) каждый кадр."""
        self.items.append(Item(self.time + delay, dur, fn, alive))

    def update(self, dt):
        if dt <= 0:
            return
        self.time += dt
        self.spells.update(dt)                 # отложенные действия и удержания («загорится, когда долетит»)
        if self.on and self.view.combat is not None:
            self.look.update(dt)

    # ---------- кадр ----------

    def lab_frame(self):
        if not self.on or self.view.combat is None:
            return None
        F = self.frame
        F.clear()
        c = self.view.combat
        lk = self.look
        S = self.spells
        burning = [p for p, cell in c.grid.cells.items() if cell.hazard == "fire" and not S.held(p)]
        icy = [p for p, cell in c.grid.cells.items() if cell.hazard == "ice" and not S.held(p)]
        for p in icy:
            self.ice_born.setdefault(p, self.time)
        for p in list(self.ice_born):
            if p not in icy:
                del self.ice_born[p]
        if icy:
            lk.ice_cells(F, icy)
        if burning:
            lk.burning(F, burning)
        rects = {u.id: r for r, u in self.view.sprite_rects}
        for u in c.alive():
            if "fire" in u.statuses and not S.unit_held(u) and u.id in rects:
                lk.unit_fire(F, u, rects[u.id])
        keep = []
        for it in self.items:
            age = self.time - it.t0
            if age < 0:
                keep.append(it)
                continue
            if it.alive is not None and not it.alive():
                continue
            if age > it.dur:
                continue
            it.fn(F, age / it.dur, age)
            keep.append(it)
        self.items = keep
        lk.frame_extra(F)
        return F

    def world_items(self, c):
        if not self.on:
            return []
        self.burning = {pos for pos, cell in c.grid.cells.items() if cell.hazard == "fire"}
        self.burning_units = {u.id for u in c.units if "fire" in u.statuses and not self.spells.unit_held(u)}
        self.icy = {pos for pos, cell in c.grid.cells.items() if cell.hazard == "ice"}
        return []

    def ground(self, flat, c):
        pass                                   # земля стилей — в кадре видеокарты (lab_frame)

    def begin_frame(self, gl):
        self.glow_used = False

    def glow_layer(self):
        return None

    def on_unit(self, surf, u, rect, look, k):
        return False

    def cast_orb(self, u, sk, head, alive, tier):
        return False

    def own_release(self, sid):
        return self.on and sid in ("blizzard", "ice_wall")

    # ---------- точки ----------

    @staticmethod
    def scr(p):
        x, y, k = P.project(*p)
        return x, y, k

    def hand(self, u, toward):
        gx, gy = self.view.ground_pos(u)
        dx, dy = toward[0] - gx, toward[1] - gy
        d = math.hypot(dx, dy) or 1.0
        return gx + dx / d * 0.25, gy + dy / d * 0.25, 0.55

    def contact(self, a, u):
        bx, by = self.view.ground_pos(u)
        dx, dy = a[0] - bx, a[1] - by
        d = math.hypot(dx, dy) or 1.0
        return bx + dx / d * 0.18, by + dy / d * 0.18, BODY

    # ---------- навыки ----------

    def skill(self, u, sk, spec, ctx, color, far, radius, tier, sid=None):
        if not self.on or sid not in ("fireball", "blizzard", "ice_wall"):
            return None
        if sid == "ice_wall":
            return 0.0
        tr = spec.get("travel") if far else None
        g = P.unproject(*ctx["target_ground"]) if ctx.get("target_ground") else None
        if g is None:
            return None
        if sid == "blizzard":
            if tr:
                return None                   # ветка B2 (Ледяная игла) — старым видом
            return self._blizzard(u, ctx, g, radius)
        return self._fireball(u, tr or {}, ctx, g, radius, tier)

    def _fireball(self, u, tr, ctx, g, radius, tier):
        S = self.spells
        tgt = ctx.get("target_unit")
        area = self._area(ctx)
        cells = {pos for _, pos in area} | {(int(g[0]), int(g[1]))}
        S.hold_cells(cells, 3.0)
        S.hold_units([w for w in self.view.combat.units if w.cell in cells or w is tgt], 3.0)
        s = 1.0 + 0.14 * tier
        if tgt is None and tr.get("from") != "sky":
            center = (int(g[0]), int(g[1]))
            tgt = next((w for w in self.view.combat.units if w.alive and w.cell == center and w is not u
                        and not w.obj), None)
        if tr.get("from") == "sky":
            b = (g[0], g[1], 0.0)
            a = (g[0] - 1.4, g[1] - 2.2, 7.5)
            kind, speed, scale = "meteor", 15.0, (1.6 + 0.2 * radius) * s
            ground_hit = True
        else:
            dart = (tr.get("speed", 0) or 0) >= 1400
            aim = self.view.ground_pos(tgt) if tgt is not None else g
            a = self.hand(u, aim)
            b = self.contact(a, tgt) if tgt is not None else (g[0], g[1], 0.0)
            kind = "dart" if dart else "fire"
            speed, scale = (13.0, 0.7 * s) if dart else (7.5, (1.0 + 0.25 * radius) * s)
            ground_hit = tgt is None
        dur = max(0.08, math.dist(a, b) / speed)
        d = tuple((b[i] - a[i]) / (math.dist(a, b) or 1) for i in range(3))
        lk = self.look

        def fly(F, f, sec):
            p = tuple(a[i] + (b[i] - a[i]) * f for i in range(3))
            lk.projectile(F, kind, p, d, sec, scale)
        self.add(dur, fly)
        lk.launch(kind, a, d, scale)
        self._follow(lambda: tuple(a[i] + (b[i] - a[i]) * min(1.0, (self.time - t0) / dur) for i in range(3)),
                     (255, 140, 50), 130 if kind == "meteor" else 80, dur)
        t0 = self.time

        def hit():
            big = kind == "meteor"
            R = (radius + 0.5) if radius else 0.45
            for (cx, cy), pos in sorted(area, key=lambda q: math.hypot(q[0][0] - b[0], q[0][1] - b[1])):
                dd = math.hypot(cx - b[0], cy - b[1])
                self.view.vfx.after(0.05 + dd * 0.08, lambda pos=pos: S.release(pos))   # огонь разбегается
            S.release((int(b[0]), int(b[1])))
            if tgt is not None:
                S.release(tgt.cell)
            wet = S.terrain_at(np.array([b[0]]), np.array([b[1]]))[0] == "water"
            lk.impact_fire(b, d, scale, R, ground_hit or big, wet, big)
            if not wet:
                S.scorch_mark(b[0], b[1], R, d, (), crater=0.4 if (ground_hit or big) else 0.0)
            V = self.view.vfx
            sp = P.project(*b)[:2]
            V.add_light({"radius": 170 + 90 * R, "intensity": 1.8, "life": 0.5, "color": "tag", "fadein": 0.0},
                        sp, (255, 150, 60))
            V.screen_fx(shake=4 + 4 * R + (7 if big else 0), hitstop=0.04 + (0.03 if big else 0),
                        flash=0.08 + (0.1 if big else 0), color=(255, 140, 50))
        self.view.vfx.after(dur, hit)
        return dur

    def cast_area(self, u, sid, sk, alive):
        if not self.on or sid != "blizzard" or sk.get("target") != "cell" or u.cast is None:
            return False
        tgt = u.cast.get("target")
        if not isinstance(tgt, tuple):
            return False
        x, y, R = tgt[0] + 0.5, tgt[1] + 0.5, sk.get("radius", 1) + 0.6
        lk = self.look

        def cloud(F, f, sec):
            lk.cloud(F, x, y, R, min(1.0, sec / 0.6))
        self.add(60.0, cloud, alive=alive)
        return True

    def _blizzard(self, u, ctx, g, radius):
        S = self.spells
        area = self._area(ctx)
        cells = {pos for _, pos in area} | {(int(g[0]), int(g[1]))}
        S.hold_cells(cells, 3.0, "ice")
        S.hold_units([w for w in self.view.combat.units if w.cell in cells], 3.0)
        x, y, R = g[0], g[1], radius + 0.5
        lk = self.look

        def tail(F, f, sec):                   # туча прорывается шквалом и рассеивается
            lk.cloud(F, x, y, R + 0.1, 1.0 - f)
        self.add(1.2, tail)

        def squall(F, f, sec):
            lk.squall(F, x, y, R, f, sec)
        self.add(0.9, squall)

        def hit():
            for _, pos in area:
                S.release(pos)
            S.release((int(x), int(y)))
            lk.frost(x, y, R)
            V = self.view.vfx
            V.add_light({"radius": 220, "intensity": 1.3, "life": 0.7, "color": "tag", "fadein": 0.0},
                        P.project(x, y)[:2], (150, 210, 255))
            V.screen_fx(shake=5, hitstop=0.03, flash=0.06, color=(150, 210, 255))
        self.view.vfx.after(0.32, hit)
        return 0.32

    # ---------- события ----------

    def event(self, e):
        if not self.on:
            return False
        t = e["t"]
        if t == "damage" and e.get("tag") == "fire" and e["kind"] in ("dot", "hazard"):
            return True                        # горение видно огнём на фигурке
        if t == "status" and e["tag"] == "fire":
            return True
        if t == "wall":
            return False
        if t == "object_break" and e["unit"].obj.get("id") == "ice_wall":
            self.look.wall_break(e["unit"])
            return True
        return False

    # ---------- ледяная стена ----------

    def draw_object(self, surf, u):
        if not self.on or not u.obj or u.obj.get("id") != "ice_wall":
            return None
        w = self._walls().get(u.id)
        if w is None:
            return None
        axis, run, i, side, variant, lead, units = w
        self._wall_events(u, axis, run, i)
        if u.id != lead:
            r = self._wall_rects.get(tuple(run))
            return r.copy() if r is not None else pygame.Rect(0, 0, 0, 0)
        g = min(self._wall_grow(q) for q in units)
        key = (self.style, tuple(run), variant, side, P.view_key())
        hit = self._wall_cache.get(key)
        if hit is None:
            if len(self._wall_cache) > 60:
                self._wall_cache.clear()
            hit = self._wall_cache[key] = self.look.wall_image(axis, run, side, variant)
        if hit is None:
            return pygame.Rect(0, 0, 0, 0)
        img, (x, y), base = hit
        if g < 1.0:                            # растёт из-под земли / тает в землю: показываем верх, сдвинутый вниз
            h = img.get_height()
            vis = max(1, int((base - y) * g) + max(0, h - int(base - y)))
            sub = img.subsurface((0, 0, img.get_width(), min(h, vis)))
            surf.blit(sub, (round(x), round(y + (base - y) * (1 - g))))
        else:
            if any(self.view.anim(q).hit > 0 for q in units):
                x += math.sin(self.view.clock * 90) * 1.5
            surf.blit(img, (round(x), round(y)))
        r = pygame.Rect(round(x), round(y), img.get_width(), img.get_height())
        self._wall_rects[tuple(run)] = r
        return r

    def _wall_events(self, u, axis, run, i):
        if u.id not in self._born:
            self._born[u.id] = self.time
            cx, cy = run[i][0] + 0.5, run[i][1] + 0.5
            self.look.wall_rise(cx, cy, axis)
        self._wall_hp[u.id] = u.hp
