"""Ковка по техкарте (sim/forge_card.py; квиз 2026-11-13, вариант 4): сверху — этапы техкарты, в центре — брусок
«в двух видах» (сверху — ширина, сбоку — толщина) с призраком цели этапа и цветом каления, справа — маленькое
3D, жар с окном этапа, молоты.

Удар — ЛКМ: держать — замах сильнее, отпустить — удар в точку под курсором. По виду сверху — сжимает ширину,
по виду сбоку — толщину (объём тот же: брусок длиннее). 1–4 — молоток, клин, кувалда, гладилка. Осадка — удар
у торца. Скругление — обжимкой (без неё — удары «на угол»). Гибка: вид сбоку — рог; тяните свободный конец ЛКМ
вокруг рога, колесо — подать брусок по рогу. Пробивка — удары по меткам на виде сверху. Пробел — в горн (держать).
Автомолот (M, если куплен): держите ЛКМ — бьёт сам по точке под курсором. Enter — следующий этап / готово."""
import math

import numpy as np
import pygame

from game.forge_games import FGame, heat_color, gauge, BAD, DIM, GOLD, OK
from sim import forge as FG
from sim import forge_bar as FB
from sim import forge_card as FC
from ui import aa as AA
from ui import theme as T

HAMMERS = ["hand", "peen", "sledge", "flatter"]
NAMES = {"hand": "молоток", "peen": "клин", "sledge": "кувалда", "flatter": "гладилка"}
TOOL_OF = {"sledge": "hammer_sledge", "flatter": "flatter"}


class CardGame(FGame):
    title = "Ковка по техкарте"
    SWING_T = 0.14

    def __init__(self, aid, kind, tools, forge_level, seed=None, mass=None, card=None):
        super().__init__(seed)
        self.aid, self.a = aid, FG.ALLOYS[aid]
        self.kind = kind
        self.tools = set(tools)
        self.card_key = card or FC.card_for(kind, self.tools)
        self.card = FC.CARDS[self.card_key]
        self.stages = self.card["stages"]
        self.mass = mass or FG.PRIMS[kind]["mass"]
        self.bar = FC.CardBar(self.mass * 1.02)
        self.bar.x0 = None
        self.si = 0
        self.scores = []
        self.tmax = FG.max_temp(forge_level)
        self.temp = self.a["work"][1]
        self.heating = False
        self.hammer = "hand"
        self.hammers = ["hand", "peen"] + [h for h in ("sledge", "flatter") if TOOL_OF[h] in self.tools]
        self.charge = None                    # замах: (вид, время)
        self.swing = None
        self.cracks = 0
        self.burn = 0.0
        self.hits = 0
        self.auto = False
        self.auto_t = 0.0
        self.horn_x = 0.0                     # гибка: точка бруска на роге (мм от левого конца)
        self.bend_drag = None
        self.views = {}
        self.scene = None
        self.numeric = "pyrometer" in self.tools
        self.calipers = "calipers" in self.tools
        self.cur = self.stage_score()

    # ---------- этап ----------

    @property
    def stage(self):
        return self.stages[self.si]

    @property
    def op(self):
        return self.stage["op"]

    def window(self):
        return FC.heat_window(self.op, self.a)

    def target(self):
        return FC.stage_target(self.stage, self.bar, self.stages)

    def stage_score(self):
        return FC.stage_score(self.stage, self.bar, self.stages)

    def next_stage(self):
        """Enter: этап закончен (оценка запомнена) — следующий; после последнего — готово."""
        self.scores.append(round(self.stage_score(), 3))
        if self.si + 1 >= len(self.stages):
            self.finish()
            return
        self.si += 1
        self.charge = self.swing = None
        if self.op == "bend":
            u0 = self.stage["bend"][0]
            self.horn_x = self.bar.length() * u0
        self.cur = self.stage_score()
        name = FC.OPS[self.op][0]
        self.say(f"Этап {self.si + 1}: {name}", GOLD, 1.2)

    def score(self):
        sc = self.scores + [self.stage_score()] * (len(self.stages) - len(self.scores))
        return FC.final_score(self.card_key, self.bar, sc[:len(self.stages)], self.cracks, self.burn)

    @property
    def quality(self):
        return round(0.7 + 0.6 * self.score(), 3)

    def can_abort(self):
        return self.hits == 0 and self.cracks == 0

    def stop(self):
        self.finish()

    def finish(self):
        while len(self.scores) < len(self.stages):
            self.scores.append(round(FC.stage_score(self.stages[len(self.scores)], self.bar, self.stages), 3))
        self.done = True
        self.result = {"score": FC.final_score(self.card_key, self.bar, self.scores, self.cracks, self.burn),
                       "stages": list(self.scores), "card": self.card_key, "len": round(self.bar.length()),
                       "cracks": self.cracks, "match": round(self.scores[-1], 3) if self.scores else 0.0}

    # ---------- ввод ----------

    def press(self):
        self.heating = True

    def release(self):
        self.heating = False

    def key(self, k):
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.next_stage()
            return True
        if pygame.K_1 <= k <= pygame.K_4:
            h = HAMMERS[k - pygame.K_1]
            if h in self.hammers:
                self.hammer = h
                self.say(NAMES[h].capitalize(), GOLD, 0.6)
            else:
                self.say(f"{NAMES[h].capitalize()} — нет: купите у бродячего кузнеца", BAD, 1.0)
            return True
        if k == pygame.K_m:
            if "power_hammer" not in self.tools:
                self.say("Нужен автомолот (бродячий кузнец)", BAD, 0.9)
            else:
                self.auto = not self.auto
                self.say("Автомолот: держите ЛКМ — бьёт сам" if self.auto else "Ручная ковка", GOLD, 1.0)
            return True
        return False

    def wheel(self, dy):
        if self.op == "bend":                                       # подать брусок по рогу
            self.horn_x = max(0.0, min(self.bar.length(), self.horn_x - dy * 4.0))

    def view_at(self, pos):
        for name, (r, _, _) in self.views.items():
            if r.collidepoint(pos):
                return name
        return None

    def x_at(self, view, pos):
        """Мм от левого конца бруска под курсором в виде."""
        r, x0, ppm = self.views[view]
        return (pos[0] - x0) / ppm

    def pointer(self, ev, rect):
        if self.done:
            return False
        if ev.type == pygame.MOUSEMOTION:
            self.mpos = ev.pos
            if self.bend_drag is not None:
                self.drag_bend(ev.pos)
                return True
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            v = self.view_at(ev.pos)
            if v is None:
                return False
            if self.op == "bend" and v == "side":
                self.bend_drag = self.horn_angle(ev.pos)
                return True
            self.charge = [v, 0.0]
            return True
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            if self.bend_drag is not None:
                self.bend_drag = None
                return True
            if self.charge is not None:
                v, t = self.charge
                self.charge = None
                if not self.auto:
                    self.swing = [0.0, v, ev.pos, 0.3 + 0.7 * min(1.0, t / 0.6)]
                return True
        return False

    # ---------- удары ----------

    def cold(self, power):
        """Удар по холодному металлу — трещина (окно этапа ниже на 40 °C ещё терпит)."""
        lo, _ = self.window()
        if self.temp < lo - 40:
            self.cracks += 1
            self.say("Холодно — трещина!", BAD)
            return power * 0.3
        return power

    def strike(self, view, pos, power):
        x = self.x_at(view, pos)
        L = self.bar.length()
        if x < -4 or x > L + 4:
            self.say("Мимо металла", BAD, 0.6)
            return
        power = self.cold(power)
        x = max(0.0, min(L, x))
        if self.op == "punch" and view == "top":
            d = 5.0
            if self.stage.get("holes"):
                u = x / L
                d = min(self.stage["holes"], key=lambda h: abs(h[0] - u))[1]
            got = self.bar.punch(x, d, power, rough="punch" not in self.tools)
            if got >= 1.0:
                self.say("Пробито", OK, 0.5)
        elif self.op == "upset" and min(x, L - x) < 0.12 * L:
            got = self.bar.upset(0 if x < L / 2 else 1, power)
        elif self.op == "round":
            if "swage" in self.tools:
                got = self.bar.swage(x, power)
            else:
                self.bar.orient = 45
                got = self.bar.strike(x, power * 0.8, "hand")
        elif self.op == "spread" and view == "side":            # разгонка: металл — вширь
            got = self.bar.spread(x, power, self.hammer)
        else:
            self.bar.orient = 90 if view == "top" else 0
            got = self.bar.strike(x, power, self.hammer)
        if got:
            self.hits += 1
            self.temp -= 8
            self.cur = self.stage_score()

    # ---------- гибка ----------

    def horn(self):
        """Рог на виде сбоку: центр (экран), радиус (пиксели)."""
        r, x0, ppm = self.views["side"]
        return (r.x + r.w * 0.32, r.y + r.h * 0.42), max(10, int(r.h * 0.14))

    def horn_angle(self, pos):
        (cx, cy), _ = self.horn()
        return math.atan2(pos[1] - cy, pos[0] - cx)

    def drag_bend(self, pos):
        """Свободный конец тянут вокруг рога: угол поворота мыши вокруг рога — угол гибки у точки на роге."""
        a = self.horn_angle(pos)
        d = (a - self.bend_drag + math.pi) % (2 * math.pi) - math.pi
        self.bend_drag = a
        dang = math.degrees(d)
        if abs(dang) < 0.05:
            return
        lo, _ = self.window()
        if self.temp < lo - 40 and abs(dang) > 0.5:
            if self.rng.random() < abs(dang) / 60:
                self.cracks += 1
                self.say("Холодно гнуть — трещина!", BAD)
        th = float(np.interp(self.horn_x, self.bar.centers(), self.bar.t))
        self.bar.bend(self.horn_x, dang, 3.0 + 0.6 * th)
        self.hits += 1
        self.cur = self.stage_score()

    # ---------- время ----------

    def update(self, dt):
        super().update(dt)
        if self.done:
            return
        if self.charge is not None:
            self.charge[1] += dt
            if self.auto and self.op in ("draw", "spread", "round", "upset"):    # автомолот: бьёт сам
                self.auto_t -= dt
                if self.auto_t <= 0:
                    self.auto_t = 1 / 3
                    self.strike(self.charge[0], self.mpos, 0.8)
        if self.swing is not None:
            self.swing[0] += dt
            if self.swing[0] >= self.SWING_T:
                _, v, pos, pw = self.swing
                self.swing = None
                self.strike(v, pos, pw)
        lo, hi = self.a["work"]
        if self.heating:
            k = 1.6 if "bellows" in self.tools else 0.8
            self.temp += (self.tmax - self.temp) * min(1.0, dt * k)
            if self.temp > hi + 60:
                self.burn = min(0.4, self.burn + dt * 0.03)
        else:
            thick = math.sqrt(max(1.0, float(np.median(self.bar.area()))))
            self.temp -= dt * (30 + 140 / max(1.0, thick))
        self.temp = max(20.0, self.temp)

    @property
    def hint(self):
        if self.op == "bend":
            return "Тяните свободный конец ЛКМ вокруг рога · колесо — подать по рогу · Пробел — горн · Enter — дальше"
        if self.op == "punch":
            return "Бейте по меткам на виде сверху (держать ЛКМ — сильнее) · Пробел — горн · Enter — дальше"
        return ("ЛКМ по виду — удар (держать — сильнее): сверху — уже, сбоку — тоньше · 1–4 — молот · "
                "Пробел — горн · Enter — дальше")

    # ---------- рисунок ----------

    def metal_col(self):
        return heat_color(self.temp) if self.temp > 520 else self.a["color"]

    def draw(self, surf, rect):
        self.rect = rect
        pygame.draw.rect(surf, (16, 12, 10), rect, border_radius=10)
        self.draw_stages(surf, pygame.Rect(rect.x + 10, rect.y + 8, rect.w - 20, 64))
        main = pygame.Rect(rect.x + 10, rect.y + 80, int(rect.w * 0.72), rect.h - 90)
        side = pygame.Rect(main.right + 10, main.y, rect.right - main.right - 20, main.h)
        L = max(self.bar.length(), (self.target().length if self.target() is not None else 0)) * 1.08
        ppm = (main.w - 40) / max(20.0, L)
        hgt = (main.h - 12) // 2
        top = pygame.Rect(main.x, main.y, main.w, hgt)
        sv = pygame.Rect(main.x, main.y + hgt + 12, main.w, hgt)
        x0 = main.x + 20
        self.views = {"top": (top, x0, ppm), "side": (sv, x0, ppm)}
        self.draw_top(surf, top, x0, ppm)
        if self.op == "bend":
            self.draw_bend(surf, sv)
        else:
            self.draw_side(surf, sv, x0, ppm)
        self.draw_side_panel(surf, side)
        self.draw_flash(surf, rect)

    def draw_stages(self, surf, r):
        n = len(self.stages)
        w = (r.w - 8 * (n - 1)) // n
        for i, st in enumerate(self.stages):
            cr = pygame.Rect(r.x + i * (w + 8), r.y, w, 30)
            cur = i == self.si
            done = i < len(self.scores)
            pygame.draw.rect(surf, (70, 50, 28) if cur else (34, 26, 20), cr, border_radius=6)
            pygame.draw.rect(surf, GOLD if cur else (90, 70, 50), cr, 2 if cur else 1, border_radius=6)
            lab = f"{i + 1}. {FC.OPS[st['op']][0]}"
            if done:
                lab += f" · {self.scores[i] * 100:.0f}%"
            T.text(surf, lab, cr.center, 13, T.TEXT if cur or done else DIM, True, center=True)
        st = self.stage
        lo, hi = self.window()
        tool = FC.OPS[self.op][3]
        extra = ""
        if tool and tool not in self.tools:
            extra = " · без инструмента — грубее" if self.op != "round" else " · без обжимки — удары «на угол»"
        T.text(surf, f"{st['name']} — {FC.OPS[self.op][1]}{extra}", (r.x, r.y + 38), 15, (255, 225, 160), True)
        T.text(surf, f"окно жара: {lo:.0f}–{hi:.0f} °C · этап сейчас {self.cur * 100:.0f}%",
               (r.right - 300, r.y + 40), 13, DIM)

    def draw_flash(self, surf, rect):
        if self.flash:
            word, col, left = self.flash[-1]
            T.text(surf, word, (rect.x + int(rect.w * 0.37), rect.y + 128), 22, col, True, center=True, shadow=True)

    def heat_fill(self, x):
        """Цвет металла (одинаковый жар по всей длине)."""
        return self.metal_col()

    def draw_top(self, surf, r, x0, ppm):
        pygame.draw.rect(surf, (26, 22, 20), r, border_radius=8)
        T.text(surf, "вид сверху — ширина", (r.x + 8, r.y + 6), 12, DIM)
        cy = r.centery
        cen, dx = self.bar.centers(), self.bar.dx
        tgt = self.target()
        tw = tgt.profile(60)[1][:, 0].max() if tgt is not None else 0.0
        k = (r.h * 0.76) / max(1.0, float(self.bar.w.max()), tw)        # свой масштаб: ширина во весь вид
        if tgt is not None:                                          # призрак цели
            xs, prof = tgt.profile(80)
            pts = [(x0 + x * ppm, cy - p[0] / 2 * k) for x, p in zip(xs, prof)] + \
                  [(x0 + x * ppm, cy + p[0] / 2 * k) for x, p in zip(xs[::-1], prof[::-1])]
            AA.polygon(surf, (255, 225, 140), pts, 2)
        xs = np.concatenate([[0.0], cen, [self.bar.length()]])
        ws = np.concatenate([[self.bar.w[0]], self.bar.w, [self.bar.w[-1]]])
        pts = [(x0 + x * ppm, cy - w / 2 * k) for x, w in zip(xs, ws)] + \
              [(x0 + x * ppm, cy + w / 2 * k) for x, w in zip(xs[::-1], ws[::-1])]
        pygame.draw.polygon(surf, self.metal_col(), pts)
        AA.polygon(surf, (40, 30, 24), pts, 1)
        if self.op == "punch":                                       # метки отверстий и пробитые
            L = self.bar.length()
            for u, d in self.stage.get("holes", []):
                AA.circle(surf, (255, 230, 150), (int(x0 + u * L * ppm), cy), max(3, int(d / 2 * k)), 2)
        for h in self.bar.holes:
            hx = x0 + self.bar.x_of_m(h["m"]) * ppm
            rr = max(2, int(h["d"] / 2 * k))
            if h["depth"] >= 1:
                pygame.draw.circle(surf, (14, 10, 8), (int(hx), cy), rr)
            else:
                AA.circle(surf, (30, 22, 18), (int(hx), cy), rr, max(1, int(rr * h["depth"])))
        if self.op == "bend":                                        # участок гибки и точка на роге
            u0, u1, _ = self.stage["bend"]
            L = self.bar.length()
            pygame.draw.line(surf, (255, 225, 140), (x0 + u0 * L * ppm, r.bottom - 10), (x0 + u1 * L * ppm, r.bottom - 10), 3)
            hx = x0 + self.horn_x * ppm
            AA.polygon(surf, (255, 255, 255), [(hx, r.bottom - 22), (hx - 6, r.bottom - 12), (hx + 6, r.bottom - 12)])
        self.draw_cursor(surf, r, "top", x0, ppm, k)
        if self.calipers:
            x = self.x_at("top", self.mpos) if r.collidepoint(self.mpos) else None
            if x is not None and 0 <= x <= self.bar.length():
                w, t, rr, _ = self.bar.at_x(x)
                T.text(surf, f"ш {w:.1f} · т {t:.1f} мм", (r.right - 140, r.y + 6), 13, (255, 230, 190), True)
        T.text(surf, f"длина {self.bar.length():.0f} мм" + (f" / цель {tgt.length:.0f}" if tgt is not None else ""),
               (r.right - 230, r.bottom - 22), 13, DIM)

    def draw_side(self, surf, r, x0, ppm):
        pygame.draw.rect(surf, (26, 22, 20), r, border_radius=8)
        T.text(surf, "вид сбоку — толщина (на наковальне)", (r.x + 8, r.y + 6), 12, DIM)
        base = r.bottom - 26
        pygame.draw.rect(surf, (70, 72, 80), (r.x + 10, base, r.w - 20, 10), border_radius=3)    # наковальня
        cen = self.bar.centers()
        tgt = self.target()
        tt = tgt.profile(60)[1][:, 1].max() if tgt is not None else 0.0
        k = (r.h * 0.62) / max(1.0, float(self.bar.t.max()), tt)        # свой масштаб: толщина крупно
        if tgt is not None:
            xs, prof = tgt.profile(80)
            pts = [(x0, base)] + [(x0 + x * ppm, base - p[1] * k) for x, p in zip(xs, prof)] + \
                  [(x0 + tgt.length * ppm, base)]
            AA.polygon(surf, (255, 225, 140), pts, 2)
        xs = np.concatenate([[0.0], cen, [self.bar.length()]])
        ts = np.concatenate([[self.bar.t[0]], self.bar.t, [self.bar.t[-1]]])
        pts = [(x0, base)] + [(x0 + x * ppm, base - t * k) for x, t in zip(xs, ts)] + \
              [(x0 + self.bar.length() * ppm, base)]
        pygame.draw.polygon(surf, self.metal_col(), pts)
        AA.polygon(surf, (40, 30, 24), pts, 1)
        if self.op == "upset":                                       # торцы — куда бить
            L = self.bar.length()
            for xe in (0.0, L):
                AA.line(surf, (255, 225, 140), (x0 + xe * ppm, base - 6), (x0 + xe * ppm, r.y + 24), 2)
        self.draw_cursor(surf, r, "side", x0, ppm, k)

    def draw_cursor(self, surf, r, view, x0, ppm, k):
        """Пятно удара под курсором (ширина бойка) и замах."""
        if not r.collidepoint(self.mpos) or self.op == "bend":
            return
        hx = FB.HAMMERS.get(self.hammer, (0, 9))[1]
        if self.op == "punch":
            hx = 3.0
        x = self.mpos[0]
        band = pygame.Surface((max(2, int(2 * hx * ppm)), r.h - 30), pygame.SRCALPHA)
        band.fill((255, 230, 160, 40))
        surf.blit(band, (x - band.get_width() // 2, r.y + 22))
        if self.charge is not None and self.charge[0] == view:
            p = min(1.0, self.charge[1] / 0.6)
            AA.circle(surf, (255, 200, 120), (x, self.mpos[1]), int(10 + 26 * (1 - p)), 2)
            T.text(surf, f"{(0.3 + 0.7 * p) * 100:.0f}%", (x + 16, self.mpos[1] - 26), 13, GOLD, True)

    def draw_bend(self, surf, r):
        """Гибка: вид сбоку — рог и брусок по средней линии (с изгибами); призрак — нужная дуга."""
        pygame.draw.rect(surf, (26, 22, 20), r, border_radius=8)
        T.text(surf, "гибка на роге — тяните конец ЛКМ вокруг рога", (r.x + 8, r.y + 6), 12, DIM)
        (cx, cy), hr = self.horn()
        pygame.draw.circle(surf, (78, 80, 90), (int(cx), int(cy)), hr)
        pygame.draw.circle(surf, (120, 124, 136), (int(cx), int(cy)), hr, 2)
        ppm = min(self.views["top"][2], (r.h * 0.8) / max(30.0, self.bar.length() * 0.45))
        x, y, h = self.bar.path()
        hx, hy = np.interp(self.horn_x, self.bar.centers(), x), np.interp(self.horn_x, self.bar.centers(), y)
        hh = float(np.interp(self.horn_x, self.bar.centers(), h))
        c, s = math.cos(-hh), math.sin(-hh)                     # точка на роге — на макушке рога, касательно
        px = (x - hx) * c - (y - hy) * s
        py = (x - hx) * s + (y - hy) * c
        sx = cx + px * ppm
        sy = cy - hr + py * ppm                                   # гнётся вниз — вокруг рога
        u0, u1, deg = self.stage["bend"]
        ghost = FC.CardBar.__new__(FC.CardBar)                   # призрак: нужная дуга на том же бруске
        ghost.dx, ghost.ang = self.bar.dx.copy(), np.zeros_like(self.bar.dx)
        uu = self.bar.centers() / self.bar.length()
        sel = (uu >= u0) & (uu <= u1)
        if sel.any():
            ghost.ang[sel] = deg * ghost.dx[sel] / ghost.dx[sel].sum()
        gx, gy, gh = ghost.path()
        ghx, ghy = np.interp(self.horn_x, self.bar.centers(), gx), np.interp(self.horn_x, self.bar.centers(), gy)
        ghh = float(np.interp(self.horn_x, self.bar.centers(), gh))
        c2, s2 = math.cos(-ghh), math.sin(-ghh)
        gpx = (gx - ghx) * c2 - (gy - ghy) * s2
        gpy = (gx - ghx) * s2 + (gy - ghy) * c2
        clip = surf.get_clip()
        surf.set_clip(r.inflate(-4, -4))
        AA.lines(surf, (255, 225, 140), False, list(zip(cx + gpx * ppm, cy - hr + gpy * ppm)), 2)
        th = max(3, int(float(np.median(self.bar.t)) * ppm))
        pts = list(zip(sx, sy))
        if len(pts) > 1:
            pygame.draw.lines(surf, self.metal_col(), False, pts, th)
        surf.set_clip(clip)
        uu = self.bar.centers() / self.bar.length()
        total = float(self.bar.ang[(uu >= u0 - 0.02) & (uu <= u1 + 0.02)].sum())
        T.text(surf, f"согнуто {total:.0f}° из {deg:.0f}°", (r.right - 200, r.y + 6), 14,
               OK if abs(total - deg) < deg * 0.08 else (255, 225, 160), True)

    def draw_side_panel(self, surf, r):
        pygame.draw.rect(surf, (22, 18, 16), r, border_radius=8)
        if self.scene is None:
            from game import forge_gl as GL
            self.scene = GL.Scene()
        size = (r.w - 16, int(r.h * 0.34))
        try:
            img = self.scene.render(size, self.bar, tuple(c / 255 for c in self.metal_col()),
                                    max(0.0, min(1.0, (self.temp - 550) / 600)) if self.temp > 520 else 0.0,
                                    extent=max(60.0, self.bar.length() * 0.6))
            if img is not None:
                surf.blit(img, (r.x + 8, r.y + 8))
        except Exception:
            pass
        y = r.y + size[1] + 18
        g = pygame.Rect(r.x + 16, y, 26, r.bottom - y - 150)
        gauge(surf, g, self.temp, self.tmax, self.window(), self.numeric)
        lo, hi = self.window()
        state = "горит!" if self.temp > self.a["work"][1] + 60 else "в окне" if lo - 40 <= self.temp <= hi + 30 \
            else "холодно" if self.temp < lo - 40 else "горячо"
        T.text(surf, f"жар: {state}" + (" · в горне" if self.heating else ""), (g.right + 24, y), 14,
               OK if state == "в окне" else BAD, True)
        T.text(surf, "Пробел — держать в горне", (g.right + 24, y + 22), 12, DIM)
        yy = y + 52
        T.text(surf, "Молот (1–4):", (g.right + 24, yy), 13, T.TEXT, True)
        for i, h in enumerate(HAMMERS):
            on = h in self.hammers
            col = GOLD if h == self.hammer else T.TEXT if on else (90, 80, 70)
            T.text(surf, f"{i + 1} {NAMES[h]}" + ("" if on else " — нет"), (g.right + 34, yy + 20 + i * 18), 13, col,
                   h == self.hammer)
        yy += 20 + 4 * 18 + 8
        if "power_hammer" in self.tools:
            T.text(surf, "M — автомолот: " + ("вкл (держите ЛКМ)" if self.auto else "выкл"), (g.right + 24, yy), 12,
                   OK if self.auto else DIM)
            yy += 18
        T.text(surf, f"трещины: {self.cracks}" + (f" · окалина {self.burn * 100:.0f}%" if self.burn > 0.005 else ""),
               (g.right + 24, yy), 12, BAD if self.cracks else DIM)
        T.text(surf, f"итог сейчас ≈ {self.score() * 100:.0f}%", (r.x + 16, r.bottom - 52), 15, GOLD, True)
        last = self.si + 1 >= len(self.stages)
        T.text(surf, "Enter — готово" if last else "Enter — следующий этап", (r.x + 16, r.bottom - 28), 13,
               (255, 225, 160), True)
