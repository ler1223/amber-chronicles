"""Обдирка: грубый круг снимает с куска всё лишнее до контура будущего камня.

docs/rough_to_gem_reality.md, §4 и §7: камень на допе у грубого круга, внутри —
контур будущего камня. Игрок поворачивает кусок (ЛКМ) и прижимает его к кругу
(Пробел): круг снимает слой с нижней стороны. Корка, порода и налёт уходят
по-настоящему; сошлифованное становится матовым — получается преформа.
Заход за контур уменьшает будущий камень, у трещины с нажимом — скол.
"""
from __future__ import annotations

import math
import random

import pygame

from game import gem3d as G3
from game import jewel_view as JV
from ui import aa as AA
from ui import theme as T

GRIT = 1.0                  # грубый круг: сошлифованное — белёсое, матовое
RATE = 34.0                 # единиц камня в секунду при обычном нажиме
ROCK_RATE = 3.0             # порода мягче и сходит кусками
DONE_LEFT = 0.25            # можно на станок: у скруглённого контура остаются клинья — их снимут грани
CLEAN_LEFT = 0.03           # обдирка закончена совсем


def _vol(faces):
    return G3.volume(faces) if faces else 0.0


def _verts(faces):
    return [p for f in faces or () for p in f["pts"]]


class Grind:
    """Состояние обдирки: кусок, порода и контур будущего камня — в осях будущего камня."""

    def __init__(self, stone, rock, target, incl, seed=None):
        self.stone = stone                      # кусок с родной поверхностью
        self.rock = rock                        # порода (или None)
        self.target = target                    # контур будущего камня (заготовка)
        self.incl = incl                        # правда о включениях: для риска скола
        self.rng = random.Random(seed)
        self.m = JV._mm(JV._rot("x", -0.5), ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        self.drag = None
        self.hold = False
        self.contact = 0.0
        self.sparks = []
        self.flash = []
        self.overcut = 0.0                      # сколько массы ушло за контур (доля)
        self.chips = 0
        self.touched = False
        self.spin = 0.0
        self._over_note = False
        self.vol_target0 = _vol(target)
        self.excess0 = max(1e-6, _vol(stone) + _vol(rock) - self.vol_target0)
        self.vol_rock0 = _vol(rock)
        self.far = self._far()                  # масштаб вида: плавно приближается по мере обдирки

    def _far(self):
        return max((math.sqrt(G3.dot(p, p)) for p in _verts(self.stone) + _verts(self.rock)), default=100.0)

    # ---------- виды ----------
    def to_world(self, p):
        m = self.m
        return (m[0][0] * p[0] + m[0][1] * p[1] + m[0][2] * p[2],
                m[1][0] * p[0] + m[1][1] * p[1] + m[1][2] * p[2],
                m[2][0] * p[0] + m[2][1] * p[1] + m[2][2] * p[2])

    def to_stone(self, p):
        m = self.m
        return (m[0][0] * p[0] + m[1][0] * p[1] + m[2][0] * p[2],
                m[0][1] * p[0] + m[1][1] * p[1] + m[2][1] * p[2],
                m[0][2] * p[0] + m[1][2] * p[1] + m[2][2] * p[2])

    def turn(self, dx, dy):
        self.m = JV._mm(JV._rot("y", dx * 0.012), JV._mm(JV._rot("x", -dy * 0.012), self.m))

    def down(self):
        """Сторона куска, обращённая к кругу (вниз по экрану), — в осях камня."""
        return G3.norm(self.to_stone((0.0, 1.0, 0.0)))

    # ---------- состояние ----------
    def left(self):
        """Доля лишнего, которое ещё не снято."""
        return max(0.0, (_vol(self.stone) + _vol(self.rock) - _vol(self.target)) / self.excess0)

    def can_finish(self):
        return self.left() <= DONE_LEFT

    def mass_k(self):
        return _vol(self.target) / max(1e-6, self.vol_target0)

    def update(self, dt, gentle=False):
        self.spin += dt * 8
        self.far += (self._far() - self.far) * min(1.0, dt * 1.5)
        for s in self.sparks:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[3] += 600 * dt
            s[4] -= dt
        self.sparks = [s for s in self.sparks if s[4] > 0]
        for f in self.flash:
            f[2] -= dt
        self.flash = [f for f in self.flash if f[2] > 0]
        if not self.hold:
            self.contact = max(0.0, self.contact - dt * 4)
            return
        n = self.down()
        es = G3.extent(self.stone, n)
        er = G3.extent(self.rock, n) if self.rock else -1e9
        top = max(es, er)
        rate = RATE * (0.35 if gentle else 1.0) * (ROCK_RATE if er > es + 0.5 else 1.0)
        h = top - rate * dt
        self.contact = min(1.0, self.contact + dt * 6)
        self.touched = True
        if self.rock:
            cut = G3.clip(self.rock, n, h, "rough")
            self.rock = cut if cut and _vol(cut) > 0.03 * self.vol_rock0 else None   # крошка отваливается
        if es > h:
            et = G3.extent(self.target, n)
            if h < et - 0.3:                      # круг зашёл за контур — будущий камень меньше
                before = _vol(self.target)
                t2 = G3.clip(self.target, n, h, "frost", grit=GRIT)
                if t2:
                    self.target = t2
                    self.overcut += (before - _vol(t2)) / max(1e-6, self.vol_target0)
                if not self._over_note:
                    self.flash.append(["За контур! Будущий камень стал меньше", (240, 120, 100), 1.6])
                    self._over_note = True
            else:
                self._over_note = False
            if self._chip(n, h, gentle, dt):
                return
            self.stone = G3.clip(self.stone, n, h, "frost", grit=GRIT) or self.stone
        for _ in range(3):
            self.sparks.append([self.rng.uniform(-30, 30), 0.0, self.rng.uniform(-220, 220),
                                self.rng.uniform(-260, -80), self.rng.uniform(0.2, 0.5)])

    def _chip(self, n, h, gentle, dt):
        """Круг идёт по трещине с нажимом — от куска отлетает скол (в глубину, мимо контура)."""
        if gentle:
            return False
        for i in self.incl:
            if i["k"] not in ("feather", "cleavage"):
                continue
            d = G3.dot(n, i["p"])
            if abs(d - h) < i["r"] * 1.2 + 2 and self.rng.random() < dt * 0.7:
                depth = d - i["r"] * 0.8
                before = _vol(self.target)
                self.stone = G3.clip(self.stone, n, depth, "conch") or self.stone
                t2 = G3.clip(self.target, n, depth, "conch")
                if t2:
                    self.target = t2
                    self.overcut += (before - _vol(t2)) / max(1e-6, self.vol_target0)
                self.chips += 1
                self.hold = False
                self.flash.append(["Скол по трещине! Shift — бережно", (240, 110, 100), 2.0])
                return True
        return False

    def result(self):
        """Заготовка для станка: контур будущего камня (с тем, что ушло за контур)."""
        return self.target

    # ---------- рисование ----------
    def draw(self, g, surf, rect):
        view = pygame.Rect(rect.x + 16, rect.y + 16, rect.w - 380, rect.h - 32)
        pygame.draw.rect(surf, (12, 10, 10), view, border_radius=10)
        surf.blit(JV._glow(view.size), view, special_flags=pygame.BLEND_RGB_ADD)
        pygame.draw.rect(surf, (90, 70, 46), view, 2, border_radius=10)
        clip = surf.get_clip()
        surf.set_clip(view)
        scale = min(view.w, view.h) / (2 * self.far * 1.25)
        wheel_y = view.bottom - 78
        low = max((self.to_world(p)[1] for p in _verts(self.stone) + _verts(self.rock)), default=0.0)
        lift = 0 if self.hold else 14
        C = (view.centerx, wheel_y - lift - low * scale)
        look = {"stain": float(g.rough.get("stain", 0.0)), "roughness": 0.85,
                "round": JV.rough_round(g.rough) / max(1e-6, g.grind_s)}
        if self.rock:
            look["matrix"] = {"faces": self.rock, "rock": g.grind_rock_kind}
        JV.stone(surf, self.stone, self.to_world, C, scale, g.color, g.t, incl=g.incl, axis=g.caxis,
                 cfield=g.cfield(), light={"on": False}, surface=look, env=2.4,
                 ior=JV._profile_ior(g.rough["id"]))
        # контур будущего камня: ближние рёбра ярче
        for f in self.target:
            pts = f["pts"]
            if len(pts) < 2:
                continue
            front = self.to_world(f["n"])[2] > 0
            col = (255, 214, 110) if front else (120, 96, 52)
            scr = [(C[0] + self.to_world(p)[0] * scale, C[1] + self.to_world(p)[1] * scale) for p in pts]
            AA.lines(surf, col, True, scr, 2 if front else 1)
        # грубый круг
        lap = JV.lap_sprite("lap_coarse", view.w - 120, 54)
        wx = view.centerx
        if lap is not None:
            surf.blit(lap, (wx - lap.get_width() // 2, wheel_y))
        else:
            pygame.draw.rect(surf, (90, 76, 64), (view.x + 60, wheel_y, view.w - 120, 30), border_radius=6)
        for j in range(16):
            x = view.x + 60 + ((j * 37 + self.spin * 90) % (view.w - 120))
            AA.line(surf, (220, 210, 200), (x, wheel_y + 4), (x + 6, wheel_y + 4), 1)
        for s in self.sparks:
            AA.circle(surf, (255, 220, 140), (int(wx + s[0]), int(wheel_y + s[1])), 2)
        surf.set_clip(clip)
        self._panel(g, surf, pygame.Rect(view.right + 16, rect.y + 16, rect.right - view.right - 32, rect.h - 32))
        y = view.y + 14
        for txt, col, life in self.flash:
            T.text(surf, txt, (view.x + 18, y), 16, col, True)
            y += 24

    def _panel(self, g, surf, panel):
        T.frame(surf, panel, 230)
        x, y = panel.x + 16, panel.y + 14
        T.text(surf, "Обдирка", (x, y), 22, (255, 210, 120), True)
        T.text(surf, "грубый круг · преформа", (x, y + 32), 14, T.TEXT_DIM)
        left = self.left()
        done = 1.0 - min(1.0, left)
        bar = pygame.Rect(x, y + 66, panel.w - 32, 14)
        pygame.draw.rect(surf, (40, 32, 26), bar, border_radius=5)
        pygame.draw.rect(surf, (150, 210, 140) if self.can_finish() else (230, 180, 100),
                         (bar.x, bar.y, int(bar.w * done), bar.h), border_radius=5)
        T.text(surf, f"лишнее снято: {done * 100:.0f}%", (x, y + 86), 14, T.TEXT)
        ct = g.rough["size"] * _vol(self.target) / max(1e-6, g.vol_rough) if g.vol_rough else 0.0
        T.text(surf, f"будущий камень ≈ {ct:.2f} кар.", (x, y + 108), 14, T.TEXT)
        if self.overcut > 0.005:
            T.text(surf, f"за контур ушло: {self.overcut * 100:.0f}% массы", (x, y + 130), 14, (240, 130, 110))
        if self.chips:
            T.text(surf, f"сколов: {self.chips}", (x, y + 152), 14, (240, 130, 110))
        if self.rock:
            T.text(surf, "порода ещё держится", (x, y + 174), 14, (220, 200, 160))
        tips = ("ЛКМ — повернуть кусок", "Пробел — прижать к кругу (снимает снизу)",
                "Shift — бережно: медленно, без сколов", "золотой каркас — будущий камень",
                "Enter — на станок (когда лишнее снято)")
        for i, txt in enumerate(tips):
            T.text(surf, txt, (x, panel.bottom - 170 + i * 19), 12, T.TEXT_DIM)
        ib = pygame.Rect(panel.x + 16, panel.bottom - 56, panel.w - 32, 40)
        ok = self.can_finish()
        pygame.draw.rect(surf, (90, 66, 36) if ok else (50, 40, 32), ib, border_radius=7)
        pygame.draw.rect(surf, (230, 180, 100) if ok else (90, 80, 70), ib, 1, border_radius=7)
        T.text(surf, "На станок (Enter)" if ok else "Снимите лишнее", ib.center, 15,
               (250, 235, 205) if ok else T.TEXT_DIM, True, center=True)
        g.grind_btn = ib
