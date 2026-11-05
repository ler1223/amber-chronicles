"""Оружие в пиксельном стиле (по образцу огня и льда, ui/pix_spells.py): прототип — Мощный удар и Прыжок драгуна.

Мощный удар (минимально): замах — фигурка отклоняется назад, на клинке короткий блик; удар — чёткая пиксельная
дуга следа клинка (белое → сталь, гаснет 0.3 с) по цели и выпад. Без искр и пыли. Отброс — сам бой.
Усиленный (ветки A «Сокрушение», B «Казнь»): замах 0.45 с двумя руками над головой, дуга вдвое больше и толще,
клинок доходит до земли — под целью малый разлом (ui/pix_quake.py), кольцо воздуха, тряска и стоп-кадр;
у Сокрушения ещё кольцо пыли на врагов вокруг.
Прыжок драгуна: на месте приземления — метка 3×3; страж приседает и уходит высокой дугой (тень бежит по земле),
падает копьём вниз: кольцо пыли по земле, камешки разлетаются и скачут, радиальные трещины на земле (гаснут сами,
как подпалины), лёгкая тряска.
Время до удара — из боя (sim/combat.py, hit_delay; config.hit: power_strike, jump_strike).
"""
import math

import numpy as np
import pygame

from ui import projection as P
from ui.pixsim import BOUNCE, DIE

WEAPON_SKILLS = {"power_strike", "jump_strike", "whirlwind", "lunge", "hook", "guard_ally", "taunt", "shield_wall",
                 "brace", "consecrate",
                 "vow", "purify", "holy_water", "judgment", "revive"}   # свет жреца — ui/pix_light.py
G = 9.0
STEEL = (236, 240, 248)


def _dir(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy) or 1.0
    return dx / d, dy / d


class Weapons:
    def __init__(self, pilot):
        self.pilot = pilot
        self.rng = np.random.default_rng(11)

    @property
    def ps(self):
        return self.pilot.spells.ps

    @property
    def view(self):
        return self.pilot.view

    def skill(self, sid, u, sk, ctx, hit):
        """Визуал навыка оружия. Возвращает время до удара."""
        if sid == "power_strike":
            br = sk.get("branch") if sk else None
            if br:
                return self.heavy_strike(u, ctx.get("target_unit"), hit or 0.45, br[0])
            return self.power_strike(u, ctx.get("target_unit"), hit or 0.3)
        if sid == "jump_strike":
            return self.jump_strike(u, ctx, hit or 0.62)
        if sid == "whirlwind":
            return self.whirlwind(u, sk, hit or 0.4)
        if sid == "lunge":
            return self.lunge(u, ctx, sk, hit or 0.3)
        if sid == "hook":
            return self.hook(u, ctx, sk, hit or 0.4)
        if sid == "guard_ally":
            return self.guard_leap(u, ctx, hit or 0.45)
        if sid == "taunt":
            return self.taunt(u, sk, hit or 0.25)
        if sid == "shield_wall":
            return self.shield_wall(u, sk, hit or 0.3)
        if sid == "brace":
            return self.brace(u, hit or 0.25)
        if sid == "consecrate":
            return self.consecrate(u, sk, hit or 0.45)
        from ui.pix_light import LIGHT_SKILLS
        if sid in LIGHT_SKILLS:
            return self.pilot.light.skill(sid, u, sk, ctx, hit)
        return None

    # ---------- Мощный удар ----------

    def power_strike(self, u, target, hit):
        view = self.view
        a = view.anim(u)
        a.windup, a.windup_total = hit, hit                  # замах: отклоняется назад (ui/battle_view.py)
        gx, gy = view.ground_pos(u)
        tgt = view.ground_pos(target) if target is not None else (gx + a.facing, gy)
        d = _dir((gx, gy), tgt)
        # блик на клинке в верхней точке замаха
        view.vfx.after(hit * 0.45, lambda: self.ps.spawn(
            5, (gx - d[0] * 0.25, gy - d[1] * 0.1, 1.15), (0, 0, 0), life=0.16, temp=1.0, cool=3.0, pal="steel",
            smoke=None, jitter=0.04, size=1.0))

        def strike():
            tx, ty = view.ground_pos(target) if target is not None and target.alive else tgt
            a.lunge, a.lunge_dir = 0.18, d
            self.slash(tx - d[0] * 0.1, ty - d[1] * 0.1, d, 0.85)
        view.vfx.after(hit, strike)
        return hit

    def heavy_strike(self, u, target, hit, branch):
        """Усиленный удар: долгий замах над головой, клинок до земли — разлом под целью, волна воздуха."""
        view = self.view
        a = view.anim(u)
        a.windup, a.windup_total, a.heavy = hit, hit, True
        gx, gy = view.ground_pos(u)
        tgt = view.ground_pos(target) if target is not None else (gx + a.facing, gy)
        d = _dir((gx, gy), tgt)
        view.vfx.after(hit * 0.55, lambda: self.ps.spawn(
            9, (gx - d[0] * 0.2, gy - d[1] * 0.1, 1.55), (0, 0, 0), life=0.22, temp=1.0, cool=2.5, pal="steel",
            smoke=None, jitter=0.06, size=1.0))

        def strike():
            tx, ty = view.ground_pos(target) if target is not None and target.alive else tgt
            a.lunge, a.lunge_dir = 0.2, d
            self.slash(tx - d[0] * 0.05, ty - d[1] * 0.05, d, 1.25, n=80, low=0.05)
            self.slash(tx + d[0] * 0.05, ty + d[1] * 0.05, d, 1.05, n=60, low=0.05)
            from ui.pix_quake import Quake
            self.pilot.quakes.append(Quake(tx + d[0] * 0.15, ty + d[1] * 0.15, 0.75, self.pilot.spells.terrain_at,
                                           seed=int(self.rng.integers(1 << 30)), life=3.0, ripple_r=2.0,
                                           dirv=d))
            self.air_ring(tx, ty, 0.45)
            if branch == "A":
                self.dust_ring(tx, ty, 120, 3.0)
            view.vfx.screen_fx(shake=7, hitstop=0.06)
        view.vfx.after(hit, strike)
        return hit

    def air_ring(self, x, y, z):
        """Волна воздуха: светлое кольцо быстро расходится и тает."""
        n = 64
        ang = np.linspace(0, math.tau, n, endpoint=False)
        self.ps.spawn(n, (x + np.cos(ang) * 0.15, y + np.sin(ang) * 0.15, np.full(n, z)),
                      (np.cos(ang) * 5.5, np.sin(ang) * 5.5, np.zeros(n)), life=0.22, temp=0.75, cool=2.5,
                      drag=6.0, pal="steam", smoke=None, size=1.0, life_var=0.1)

    def dust_ring(self, x, y, n, speed):
        ang = self.rng.uniform(0, math.tau, n)
        sp = self.rng.uniform(speed * 0.6, speed, n)
        self.ps.spawn(n, (x + np.cos(ang) * 0.3, y + np.sin(ang) * 0.3, self.rng.uniform(0.04, 0.3, n)),
                      (np.cos(ang) * sp, np.sin(ang) * sp, self.rng.uniform(0.2, 0.8, n)),
                      life=0.75, temp=self.rng.uniform(0.5, 0.7, n), cool=0.35, drag=3.6, grav=1.2, size=1.6,
                      grow=0.6, pal="dust", smoke=None, land=DIE, life_var=0.25)

    def slash(self, x, y, d, r, n=48, low=None, pal="steel"):
        """Дуга следа клинка по цели: сверху-сзади вниз-вперёд, в вертикальной плоскости вдоль удара."""
        ang = np.linspace(math.radians(120), math.radians(-35 if low is None else -62), n)
        lag = np.linspace(0.0, 1.0, n)                        # дуга рисуется за клинком — хвост гаснет раньше
        px = x + np.cos(ang) * r * 0.55 * d[0] - d[0] * 0.1
        py = y + np.cos(ang) * r * 0.55 * d[1] + 0.02
        pz = 0.55 + np.sin(ang) * r
        life = 0.12 + 0.2 * lag
        self.ps.spawn(n, (px, py, np.maximum(0.05, pz)), (np.full(n, d[0] * 0.6), np.full(n, d[1] * 0.6),
                                                           np.zeros(n)),
                      life=life, temp=np.linspace(0.7, 1.0, n), cool=2.6, pal=pal, smoke=None, size=1.0,
                      life_var=0.0, drag=4.0)
        # второй, толще — ядро дуги
        k = n // 2
        self.ps.spawn(k, (px[::2] + d[0] * 0.04, py[::2] + d[1] * 0.04, np.maximum(0.05, pz[::2] - 0.04)),
                      (0, 0, 0), life=(life[::2] * 0.8), temp=1.0, cool=3.2, pal=pal, smoke=None, size=1.0,
                      life_var=0.0)

    # ---------- Прыжок драгуна ----------

    def jump_strike(self, u, ctx, hit):
        view = self.view
        g = ctx.get("target_ground")
        dst = P.unproject(*g) if g else None
        if dst is None:
            return hit
        cx, cy = int(dst[0]), int(dst[1])
        bx, by = cx + 0.5, cy + 0.5
        a = view.anim(u)
        self._dir = _dir(view.ground_pos(u), (bx, by))          # направление прыжка — для «борозды» и «клина»
        a.leap = {"a": view.ground_pos(u), "b": (bx, by), "t": 0.0, "dur": hit, "h": 1.9}
        from ui.battle_view import Fx
        col = (255, 220, 150)
        for x in range(cx - 1, cx + 2):                        # метка 3×3 — куда приземлится
            for y in range(cy - 1, cy + 2):
                view.fx.append(Fx("tele", hit, pos=(x, y), color=col))

        def land():
            self.ground_slam(bx, by, 1.4)
        view.vfx.after(hit, land)
        return hit

    def ground_slam(self, x, y, R):
        """Приземление: кольцо пыли, камешки, трещины на земле, тряска."""
        n = 170                                                  # кольцо пыли бежит по земле от точки удара
        ang = self.rng.uniform(0, math.tau, n)
        sp = self.rng.uniform(2.6, 4.4, n)
        self.ps.spawn(n, (x + np.cos(ang) * 0.3, y + np.sin(ang) * 0.3, self.rng.uniform(0.04, 0.3, n)),
                      (np.cos(ang) * sp, np.sin(ang) * sp, self.rng.uniform(0.2, 0.8, n)),
                      life=0.75, temp=self.rng.uniform(0.5, 0.7, n), cool=0.35, drag=3.6, grav=1.2, size=1.6,
                      grow=0.6, pal="dust", smoke=None, land=DIE, life_var=0.25)
        m = 40                                                   # облачко над точкой удара
        self.ps.spawn(m, (x, y, 0.15), (0, 0, 0.6), life=1.1, temp=0.45, cool=0.2, drag=2.0, buoy=0.3, size=2.0,
                      grow=1.0, pal="dust", smoke=None, spread=0.9, jitter=0.2, land=DIE)
        k = 22                                                  # камешки: подлетают и скачут
        ang = self.rng.uniform(0, math.tau, k)
        sp = self.rng.uniform(0.8, 2.2, k)
        self.ps.spawn(k, (np.full(k, x), np.full(k, y), np.full(k, 0.1)),
                      (np.cos(ang) * sp, np.sin(ang) * sp, self.rng.uniform(2.0, 3.6, k)),
                      life=1.4, temp=0.5, cool=0.0, grav=G, bounce=0.35, size=1.0, pal="stone", smoke=None,
                      land=BOUNCE, life_var=0.2)
        from ui.pix_quake import Quake          # разлом — плиты из самой земли, по воде и лаве — рябь
        self.pilot.quakes.append(Quake(x, y, R, self.pilot.spells.terrain_at, seed=int(self.rng.integers(1 << 30)),
                                       dirv=getattr(self, "_dir", None)))
        self.view.vfx.screen_fx(shake=6, hitstop=0.04)

    # ---------- Вихрь ----------

    def whirlwind(self, u, sk, hit):
        """Замах, затем воин крутится (фигурка разворачивается туда-обратно), кольцо следа клинка вокруг, пыль."""
        view = self.view
        a = view.anim(u)
        a.windup, a.windup_total = hit * 0.6, hit * 0.6
        r = (sk.get("radius", 1) or 1) * 0.9 + 0.25

        def flip():
            a.facing *= -1
        for k in range(4):                                     # оборот: разворот каждые 0.06 с
            view.vfx.after(hit * 0.6 + k * 0.06, flip)

        def strike():
            gx, gy = view.ground_pos(u)
            for part in range(4):                              # кольцо рисуется четвертями — видно вращение
                view.vfx.after(part * 0.035, lambda p=part: self._ring_slash(gx, gy, r, p))
            self.dust_ring(gx, gy, 50, 1.8)
            view.vfx.screen_fx(shake=3)
        view.vfx.after(hit, strike)
        return hit

    def _ring_slash(self, x, y, r, part, n=60):
        a0 = part * math.pi / 2
        ang = np.linspace(a0, a0 + math.pi / 2, n)
        tang = np.stack([-np.sin(ang), np.cos(ang)])
        self.ps.spawn(n, (x + np.cos(ang) * r, y + np.sin(ang) * r, np.full(n, 0.5) + 0.08 * np.sin(ang * 2)),
                      (tang[0] * 1.6, tang[1] * 1.6, np.zeros(n)), life=np.linspace(0.18, 0.38, n), temp=1.0, cool=2.4,
                      drag=5.0, pal="steel", smoke=None, size=1.5, life_var=0.0)
        self.ps.spawn(n, (x + np.cos(ang) * r * 0.9, y + np.sin(ang) * r * 0.9, np.full(n, 0.42)), (0, 0, 0),
                      life=np.linspace(0.12, 0.28, n), temp=0.75, cool=2.0, pal="steel", smoke=None, size=1.2,
                      life_var=0.0)

    # ---------- Выпад ----------

    def lunge(self, u, ctx, sk, hit):
        """Копьё отведено назад — рывок: прямая струя на 3 клетки (белая сердцевина, стальной след), волна воздуха."""
        view = self.view
        a = view.anim(u)
        a.windup, a.windup_total = hit, hit
        g = ctx.get("target_ground")
        tgt = P.unproject(*g) if g else None
        gx, gy = view.ground_pos(u)
        tx, ty = (tgt[0], tgt[1]) if tgt else (gx + a.facing, gy)
        d = _dir((gx, gy), (tx, ty))
        L = next((e.get("length", 3) for e in sk.get("effects", []) if e["type"] == "line"), 3) + 0.4

        def strike():
            x0, y0 = view.ground_pos(u)
            a.lunge, a.lunge_dir = 0.2, d
            n = int(26 * L)
            t = np.linspace(0.3, L, n)
            px, py = x0 + d[0] * t, y0 + d[1] * t
            self.ps.spawn(n, (px, py, np.full(n, 0.55)), (np.full(n, d[0] * 2.0), np.full(n, d[1] * 2.0), np.zeros(n)),
                          life=0.14 + 0.26 * t / L, temp=1.0, cool=2.2, drag=5.0, pal="steel", smoke=None,
                          size=1.6, life_var=0.0)
            m = n // 2
            self.ps.spawn(m, (px[::2], py[::2], np.full(m, 0.62)), (0, 0, 0), life=0.18 + 0.2 * t[::2] / L,
                          temp=0.8, cool=2.0, pal="steel", smoke=None, life_var=0.0, jitter=0.03)
            self.air_ring(x0 + d[0] * L, y0 + d[1] * L, 0.55)
            view.vfx.screen_fx(shake=3)
        view.vfx.after(hit, strike)
        return hit

    # ---------- Крюк ----------

    def hook(self, u, ctx, sk, hit):
        """Крюк на цепи летит к цели (цепь натянута от руки), зацепил — цель тащится по земле, цепь сматывается.
        Подсечка (ветка без притяжения) — низкая дуга по ногам."""
        view = self.view
        target = ctx.get("target_unit")
        S = self.pilot.spells
        if target is None:
            return hit
        if not any(e["type"] == "pull" for e in sk.get("effects", [])):
            gx, gy = view.ground_pos(target)
            d = _dir(view.ground_pos(u), (gx, gy))
            view.vfx.after(hit, lambda: self.slash(gx, gy, d, 0.8, n=56, low=0.0))
            return hit
        st = [0.0]
        dur = max(0.15, hit)
        tail = 0.4

        def head():
            a = S.hand(u, view.ground_pos(target))
            b = S.contact(a, target)
            k = min(1.0, st[0] / dur)
            if st[0] > dur:                                   # тащим: цепь — от руки до цели
                b = S.contact(a, target)
                k = 1.0
            return a, tuple(a[i] + (b[i] - a[i]) * k for i in range(3))

        def step(dt):
            st[0] += dt
            a, h = head()
            L = math.dist(a[:2], h[:2]) + abs(a[2] - h[2])
            n = max(2, int(L / 0.06))
            t = np.linspace(0, 1, n)
            sag = np.sin(t * math.pi) * (0.06 if st[0] <= dur else 0.0)
            # кованая цепь: тёмные звенья через одно с тусклым бликом, крюк — тёмный с одной искрой на острие
            self.ps.spawn(n, (a[0] + (h[0] - a[0]) * t, a[1] + (h[1] - a[1]) * t, a[2] + (h[2] - a[2]) * t - sag),
                          (0, 0, 0), life=0.05, temp=np.where(np.arange(n) % 3 == 0, 0.5, 0.3), cool=0.0,
                          pal="steel", smoke=None, size=1.3, life_var=0.0)
            self.ps.spawn(5, h, (0, 0, 0), life=0.05, temp=0.22, cool=0.0, pal="steel", smoke=None, jitter=0.05,
                          life_var=0.0)
            self.ps.spawn(1, h, (0, 0, 0), life=0.05, temp=0.6, cool=0.0, pal="steel", smoke=None, life_var=0.0)
            if st[0] > dur:                                   # цель волочится — пыль из-под ног
                gx, gy = view.ground_pos(target)
                self.ps.spawn(3, (gx, gy, 0.05), (0, 0, 0.4), life=0.5, temp=0.55, cool=0.3, drag=2.0, size=1.4,
                              grow=0.8, pal="dust", smoke=None, spread=0.4, jitter=0.1)
            return st[0] < dur + tail and target.alive
        S.emitters.append(step)
        return hit

    # ---------- Под защиту ----------

    def guard_leap(self, u, ctx, hit):
        """Низкий прыжок дугой к союзнику, приземление с пылью."""
        view = self.view
        ally = ctx.get("target_unit")
        if ally is None:
            return hit
        a = view.anim(u)
        x0, y0 = view.ground_pos(u)
        ax, ay = view.ground_pos(ally)
        d = _dir((x0, y0), (ax, ay))
        bx, by = ax - d[0] * 0.85, ay - d[1] * 0.85
        a.leap = {"a": (x0, y0), "b": (bx, by), "t": 0.0, "dur": hit, "h": 0.9}
        view.vfx.after(hit, lambda: (self.dust_ring(bx, by, 60, 2.2), view.vfx.screen_fx(shake=2)))
        return hit

    # ---------- Провокация, Стена щитов, Упор ----------

    def taunt(self, u, sk, hit):
        """Удар оружием о щит: вспышка у щита и красное кольцо по земле. Провокация — кольцо сходится к воину
        (враги стянуты на него), Боевой клич (ветка B) — расходится наружу."""
        view = self.view
        a = view.anim(u)
        a.windup, a.windup_total = hit, hit
        R = next((e.get("radius", 2) for e in sk.get("effects", []) if e["type"] == "taunt"), 2)

        def bang():
            gx, gy = view.ground_pos(u)
            a.lunge, a.lunge_dir = 0.12, (a.facing * 0.3, 0.0)
            self.ps.spawn(10, (gx + a.facing * 0.25, gy, 0.6), (0, 0, 0), life=0.14, temp=1.0, cool=3.0, pal="steel",
                          smoke=None, spread=0.8)
            n = 220
            ang = np.linspace(0, math.tau, n, endpoint=False)
            br = sk.get("branch")
            out = bool(br and br[0] == "B")
            if out:                                       # боевой клич: расходится
                r0, sp, life, drag = 0.3, (R + 0.4) * 3.2, 0.6, 3.0
            else:                                         # провокация: с края радиуса сходится к воину
                r0, life, drag = R + 0.5, 0.5, 0.0
                sp = -(r0 - 0.35) / life
            self.ps.spawn(n, (gx + np.cos(ang) * r0, gy + np.sin(ang) * r0, np.full(n, 0.06)),
                          (np.cos(ang) * sp, np.sin(ang) * sp, np.zeros(n)), life=life, temp=1.0, cool=1.2,
                          drag=drag, pal="rage", smoke=None, size=1.4, life_var=0.0)
            m = n // 2
            r1 = r0 * (0.8 if not out else 1.0)
            self.ps.spawn(m, (gx + np.cos(ang[::2]) * r1, gy + np.sin(ang[::2]) * r1, np.full(m, 0.3)),
                          (np.cos(ang[::2]) * sp * 0.8, np.sin(ang[::2]) * sp * 0.8, np.zeros(m)),
                          life=life * 0.8, temp=0.7, cool=1.6, drag=drag, pal="rage", smoke=None, size=1.0,
                          life_var=0.0)
            view.vfx.screen_fx(shake=2)
        view.vfx.after(hit, bang)
        return hit

    def shield_wall(self, u, sk, hit):
        """Щит — удар о землю (без разлома): пыль перед стражем, стальная полупрозрачная стенка по фронту."""
        view = self.view
        a = view.anim(u)
        a.windup, a.windup_total = hit, hit

        def plant():
            gx, gy = view.ground_pos(u)
            f = a.facing
            a.lunge, a.lunge_dir = 0.12, (f * 0.4, 0.0)
            fx = gx + f * 0.45
            self.ps.spawn(36, (fx, gy, 0.05), (f * 1.2, 0, 0.6), life=0.6, temp=0.6, cool=0.3, drag=3.0, size=1.5,
                          grow=0.6, pal="dust", smoke=None, spread=1.0, jitter=0.15)
            ys = np.linspace(-0.75, 0.75, 16)
            zs = np.linspace(0.05, 1.0, 9)
            Y, Z = np.meshgrid(ys, zs)
            n = Y.size
            self.ps.spawn(n, (np.full(n, fx), gy + Y.ravel(), Z.ravel()), (np.full(n, f * 0.15), np.zeros(n),
                                                                           np.zeros(n)),
                          life=0.55 + 0.25 * self.rng.random(n), temp=0.62, cool=0.4, pal="steel", smoke=None,
                          alpha=0.55, size=1.0, life_var=0.0)
            self.ps.spawn(16, (np.full(16, fx), gy + ys, np.full(16, 1.0)), (0, 0, 0), life=0.4, temp=1.0, cool=2.0,
                          pal="steel", smoke=None, life_var=0.0)
            view.vfx.screen_fx(shake=3)
        view.vfx.after(hit, plant)
        return hit

    def brace(self, u, hit):
        """Упор: страж приседает, у ног вдавливается кольцо пыли, блик бежит вверх по доспеху."""
        view = self.view
        a = view.anim(u)
        a.windup, a.windup_total = hit, hit

        def press():
            gx, gy = view.ground_pos(u)
            n = 40
            ang = np.linspace(0, math.tau, n, endpoint=False)
            self.ps.spawn(n, (gx + np.cos(ang) * 0.55, gy + np.sin(ang) * 0.55, np.full(n, 0.04)),
                          (-np.cos(ang) * 0.6, -np.sin(ang) * 0.6, np.full(n, 0.3)), life=0.6, temp=0.6, cool=0.3,
                          drag=2.0, size=1.4, grow=0.5, pal="dust", smoke=None, life_var=0.2)
            self.ps.spawn(12, (np.full(12, gx), np.full(12, gy), np.linspace(0.1, 1.1, 12)), (0, 0, 0),
                          life=np.linspace(0.08, 0.3, 12), temp=1.0, cool=2.5, pal="steel", smoke=None,
                          life_var=0.0, jitter=0.05)
        view.vfx.after(hit, press)
        return hit

    # ---------- Освящение (свет) ----------

    def consecrate(self, u, sk, hit):
        """Клинок в землю: золотой круг расходится по земле на радиус, держится; столбы света над союзниками,
        у врагов — золотые искры."""
        view = self.view
        a = view.anim(u)
        a.windup, a.windup_total, a.heavy = hit, hit, True
        R = max((e.get("radius", 0) for e in sk.get("effects", [])), default=2) or 2

        def plant():
            gx, gy = view.ground_pos(u)
            a.lunge, a.lunge_dir = 0.12, (0.0, 0.3)
            n = 260
            ang = np.linspace(0, math.tau, n, endpoint=False)
            v = (R + 0.35) * 3.0
            for z, life in ((0.03, 1.2), (0.06, 1.0)):
                self.ps.spawn(n, (gx + np.cos(ang) * 0.2, gy + np.sin(ang) * 0.2, np.full(n, z)),
                              (np.cos(ang) * v, np.sin(ang) * v, np.zeros(n)), life=life, temp=0.95, cool=0.6,
                              drag=3.0, pal="light", smoke=None, size=1.4, life_var=0.05)
            m = 60                                                 # руны и искорки внутри круга
            rr = R * np.sqrt(self.rng.random(m))
            aa = self.rng.uniform(0, math.tau, m)
            self.ps.spawn(m, (gx + np.cos(aa) * rr, gy + np.sin(aa) * rr, np.full(m, 0.04)), (0, 0, 0.25),
                          life=self.rng.uniform(0.5, 1.0, m), temp=0.9, cool=0.8, pal="light", smoke=None,
                          life_var=0.0)
            self.ps.spawn(16, (gx, gy, 0.5), (0, 0, 2.5), life=0.5, temp=1.0, cool=1.5, pal="light", smoke=None,
                          spread=0.4, tall=1.0)
            c = view.combat
            if c is not None:
                from sim.grid import cheb
                for v_ in c.alive():
                    if v_ is u or v_.obj or cheb(v_.cell, u.cell) > R:
                        continue
                    vx, vy = view.ground_pos(v_)
                    if v_.team == u.team:                        # столб света над союзником
                        k = 22
                        self.ps.spawn(k, (np.full(k, vx), np.full(k, vy), np.linspace(0.0, 1.6, k)), (0, 0, 1.2),
                                      life=np.linspace(0.3, 0.7, k), temp=0.95, cool=1.0, pal="light", smoke=None,
                                      jitter=0.06, life_var=0.0)
                    else:                                        # враг: вспышка и искры
                        self.ps.spawn(14, (vx, vy, 0.6), (0, 0, 1.0), life=0.45, temp=1.0, cool=1.8, grav=G * 0.5,
                                      pal="light", smoke=None, spread=1.6, land=DIE)
            view.vfx.screen_fx(shake=3, flash=0.06)
        view.vfx.after(hit, plant)
        return hit


def cracks(cx, cy, R, seed=0, terrain_at=None):
    """Радиальные трещины от удара (картинка плоской карты, центр — точка удара): 7–9 ломаных лучей, к концу
    тоньше, у центра — тёмная вмятина. Вода и лава не трескаются."""
    rng = np.random.default_rng(seed)
    ppc = P.FLAT                                             # пикселей плоской карты на клетку
    half = int((R + 0.3) * ppc)
    size = 2 * half
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    dark, mid = (22, 16, 12, 245), (48, 38, 30, 215)
    pygame.draw.ellipse(surf, (40, 32, 26, 170), (half - 18, half - 14, 36, 28))
    pygame.draw.ellipse(surf, (28, 22, 18, 200), (half - 10, half - 8, 20, 16))
    rays = rng.integers(7, 10)
    base = rng.uniform(0, math.tau)
    for i in range(rays):
        a = base + i * math.tau / rays + rng.uniform(-0.25, 0.25)
        L = R * ppc * rng.uniform(0.55, 1.0)
        x, y = float(half), float(half)
        steps = 6
        for s in range(steps):
            a += rng.uniform(-0.45, 0.45)
            nx, ny = x + math.cos(a) * L / steps, y + math.sin(a) * L / steps
            w = max(2, int(7 * (1 - s / steps)) + 2)
            pygame.draw.line(surf, dark, (x, y), (nx, ny), w)
            if rng.random() < 0.35 and s < steps - 2:      # ответвление
                ba = a + rng.choice([-1, 1]) * rng.uniform(0.5, 0.9)
                bl = L / steps * rng.uniform(0.6, 1.1)
                pygame.draw.line(surf, mid, (nx, ny), (nx + math.cos(ba) * bl, ny + math.sin(ba) * bl), 1)
            x, y = nx, ny
    if terrain_at is not None:                               # на воде трещин нет
        ys, xs = np.mgrid[0:size:8, 0:size:8]
        gx = cx + (xs - half) / ppc
        gy = cy + (ys - half) / ppc
        ter = terrain_at(gx.ravel(), gy.ravel()).reshape(gx.shape)
        wet = np.isin(ter, ["water", "lava", "chasm"])
        for (j, i) in zip(*np.nonzero(wet)):
            surf.fill((0, 0, 0, 0), (i * 8 - 4, j * 8 - 4, 8, 8))
    return surf
