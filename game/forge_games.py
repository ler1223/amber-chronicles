"""Игры кузни v2 (sim/forge.py): тигель (весы и жар), ковка примитива (профиль сбоку), закалка и отпуск.
Без пикселей: гладкие линии (ui/aa), металл — цветом каления; спрайты горна и наковальни — если есть (лист K).

Каждая игра: update/draw/key/pointer/press/release, done, quality (для полосы «качество сейчас»), result."""
import math
import random

import numpy as np
import pygame

from game import metal_view as MV
from sim import forge as FG
from ui import aa as AA
from ui import theme as T

DIM, OK, BAD, GOLD = (150, 140, 125), (150, 230, 150), (240, 130, 110), (255, 210, 120)


def heat_color(t):
    return tuple(int(c) for c in MV.heat_rgb(t))


def gauge(surf, rect, temp, tmax, window=None, numeric=False, label="жар"):
    """Шкала жара: без пирометра — только свечение (цвет), с ним — цифра и окно."""
    pygame.draw.rect(surf, (24, 20, 18), rect, border_radius=8)
    for i in range(rect.h - 4):
        t = tmax * (1 - i / (rect.h - 4))
        pygame.draw.line(surf, heat_color(t), (rect.x + 3, rect.y + 2 + i), (rect.right - 4, rect.y + 2 + i))
    y = rect.bottom - 2 - (rect.h - 4) * max(0.0, min(1.0, temp / tmax))
    if window and numeric:
        y0 = rect.bottom - 2 - (rect.h - 4) * window[1] / tmax
        y1 = rect.bottom - 2 - (rect.h - 4) * window[0] / tmax
        pygame.draw.rect(surf, (150, 230, 150), (rect.x - 6, y0, rect.w + 12, y1 - y0), 2, border_radius=4)
    AA.polygon(surf, (255, 255, 255), [(rect.right + 4, y), (rect.right + 16, y - 7), (rect.right + 16, y + 7)])
    pygame.draw.rect(surf, (120, 96, 60), rect, 1, border_radius=8)
    T.text(surf, f"{temp:.0f} °C" if numeric else label, (rect.centerx, rect.bottom + 8), 14,
           (255, 230, 190) if numeric else DIM, True, center=True)


def button(surf, rect, label, on=True, hot=False):
    pygame.draw.rect(surf, (90, 66, 36) if on and hot else (64, 48, 30) if on else (40, 32, 26), rect, border_radius=8)
    pygame.draw.rect(surf, (230, 180, 100) if on else (90, 76, 60), rect, 1, border_radius=8)
    T.text(surf, label, rect.center, 15, (250, 235, 205) if on else DIM, True, center=True)


class FGame:
    title = ""
    hint = ""
    area_size = (1120, 520)
    wide = True
    click_press = False

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.done = False
        self.t = 0.0
        self.flash = []
        self.mpos = (0, 0)
        self.rect = pygame.Rect(0, 0, 1120, 520)
        self.result = None

    def say(self, text, col=GOLD, t=1.4):
        self.flash.append([text, col, t])

    def update(self, dt):
        self.t += dt
        for f in self.flash:
            f[2] -= dt
        self.flash = [f for f in self.flash if f[2] > 0]

    def mouse(self, pos, rect):
        self.mpos = pos

    def press(self):
        pass

    def release(self):
        pass

    def wheel(self, dy):
        pass

    def key(self, k):
        return False

    def draw_flash(self, surf, rect):
        if self.flash:
            word, col, left = self.flash[-1]
            T.text(surf, word, (rect.centerx, rect.y + 34), 24, col, True, center=True, shadow=True)

    def _held(self, *keys):
        try:
            p = pygame.key.get_pressed()
            return any(p[k] for k in keys)
        except pygame.error:
            return False


# ---------- тигель ----------

class CrucibleGame(FGame):
    """Тигель: на весах набрать смесь по рецепту (+10 г за клик, Shift — +50), в горн — держать Пробел (меха),
    держать жар в окне плавки, снимать шлак кликом, разлить в изложницу или форму (Enter)."""
    title = "Тигель"
    HINTS = {"charge": "клик по «+» / «−» — 10 г (Shift — 50 г), Enter — в горн",
             "melt": "Пробел — меха; зажмите ЛКМ — лопатка: сгоните шлак к стенке и поднимите над краем, не расплескайте",
             "pour": "выберите формы («+»), Enter — к разливке (без форм — всё в изложницу); Пробел — держать жар",
             "cast": "зажмите ЛКМ и ведите мышь вверх — тигель наклоняется; наполните формы до краёв, не перелейте; "
                     "Enter — остаток в изложницу"}

    @property
    def hint(self):
        return self.HINTS[self.phase]

    def __init__(self, aid, stock, tools, forge_level, seed=None):
        super().__init__(seed)
        self.aid, self.a = aid, FG.ALLOYS[aid]
        self.stock = dict(stock)
        self.tools = set(tools)
        self.tmax = FG.max_temp(forge_level)
        self.phase = "charge"
        mats = list(self.a["mix"]) + (["coal"] if self.a["coal"] else [])
        self.charge = {m: 0 for m in mats}
        self.temp = 20.0
        self.prog = 0.0
        self.purity = 1.0
        self.in_win = self.melt_t = 0.0
        self.slag = []                      # шлак: [x, y, vx, vy, r] — плавает на расплаве
        self.slag_left = 6
        self.slag_t = 2.0
        self.removed = 0
        self.hold = False
        n = 64
        self.wh = [0.0] * n                 # поверхность расплава: отклонение по столбцам и скорость (волны)
        self.wv = [0.0] * n
        self.spat = [0.0, 0.0]              # лопатка: положение, скорость, захват мышью
        self.spat_v = [0.0, 0.0]
        self.grab = False
        self.spill_cd = 0.0
        self.drops = []
        self.molds = [k for k in FG.PRIMS if ("mold_" + k) in self.tools]
        self.mold = None
        self.rects = {}
        self.queue = []                     # разливка: формы по порядку на ленте
        self.cast = []                      # [{kind, mass, over, tsum}] — что налито в каждую форму
        self.tilt = self.tilt_v = 0.0       # наклон тигля (рад) и его скорость
        self.tilt_anchor = None             # где зажали ЛКМ (по вертикали) — от неё считается наклон
        self.metal = 0.0                    # г расплава в тигле
        self.metal0 = 1.0
        self.conv = 0.0                     # сдвиг ленты с формами
        self.stream = []                    # капли струи: [x, y, vx, vy, г]
        self.spilt = 0.0
        self.flow = 0.0

    def spat_on(self):
        """Лопатка нужна, пока есть шлак (всплывёт или плавает); потом её убирают."""
        return self.phase == "melt" and (self.slag_left > 0 or bool(self.slag))

    KV, KH = 10.0, 11.0                     # связь лопатки с расплавом: подъём/спуск и толчок вбок

    @property
    def numeric(self):
        return "pyrometer" in self.tools

    def can_abort(self):
        return self.phase == "charge"

    def stop(self):
        self.done = True
        self.result = None

    @property
    def quality(self):
        acc = FG.mix_accuracy(self.aid, self.charge) if any(self.charge.values()) else 0.0
        heat = self.in_win / self.melt_t if self.melt_t else 0.0
        return round(0.7 + 0.6 * FG.ingot_q(acc, self.purity, heat), 3)

    def press(self):
        self.hold = True

    def release(self):
        self.hold = False

    def key(self, k):
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.phase == "charge" and FG.charge_mass(self.charge) >= 50:
                self.phase = "melt"
            elif self.phase == "pour":
                if self.queue:
                    self.start_cast()
                else:
                    self.pour()
            elif self.phase == "cast":
                self.finish_cast()
            return True
        if self.phase == "pour" and pygame.K_1 <= k <= pygame.K_4:
            i = k - pygame.K_1
            if i < len(self.molds):
                self.add_mold(self.molds[i])
            return True
        return False

    def queue_mass(self):
        return sum(FG.PRIMS[m]["mass"] for m in self.queue)

    def add_mold(self, m):
        if self.queue_mass() + FG.PRIMS[m]["mass"] <= FG.charge_mass(self.charge) and len(self.queue) < 8:
            self.queue.append(m)
        else:
            self.say("Металла не хватит на ещё одну форму", BAD)

    def pointer(self, ev, rect):
        """Лопатка: зажать ЛКМ над тиглем — взять, тянуть — двигается с инерцией, отпустить — оставить.
        Разливка: зажать ЛКМ и вести мышь вверх — тигель наклоняется, отпустить — встаёт обратно."""
        if self.phase == "cast":
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                self.tilt_anchor = ev.pos[1]
                return True
            if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                self.tilt_anchor = None
                return True
            return False
        if not self.spat_on():
            self.grab = False
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            x0, x1, rim, floor = self.bowl()
            if x0 - 60 < ev.pos[0] < x1 + 60 and rim - 220 < ev.pos[1] < floor + 20:
                self.grab = True
                return True
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.grab:
            self.grab = False
            return True
        return False

    def bowl(self):
        """Тигель в разрезе: левая и правая стенки, край, дно (экран)."""
        cx, cy = self.center()
        return cx - 170, cx + 170, cy, cy + 230

    def level(self):
        return self.bowl()[2] + 40                     # зеркало расплава в покое (на 40 пикс. ниже края)

    def surf_y(self, x):
        x0, x1, rim, floor = self.bowl()
        i = int((x - x0) / (x1 - x0) * (len(self.wh) - 1))
        i = max(0, min(len(self.wh) - 1, i))
        return self.level() - self.wh[i]

    def click(self, pos):
        big = self._held(pygame.K_LSHIFT, pygame.K_RSHIFT)
        for key, r in self.rects.items():
            if not r.collidepoint(pos):
                continue
            kind, m = key
            if kind == "+" and self.phase == "charge":
                add = 5 if big else 1
                self.charge[m] = min(self.stock.get(m, 0), self.charge[m] + add)
            elif kind == "-" and self.phase == "charge":
                self.charge[m] = max(0, self.charge[m] - (5 if big else 1))
            elif kind == "go" and self.phase == "charge" and FG.charge_mass(self.charge) >= 50:
                self.phase = "melt"
            elif kind == "mold" and self.phase == "pour":
                self.add_mold(m)
            elif kind == "unmold" and self.phase == "pour" and m in self.queue:
                del self.queue[len(self.queue) - 1 - self.queue[::-1].index(m)]
            elif kind == "pour" and self.phase == "pour":
                self.key(pygame.K_RETURN)
            return True
        return self.phase in ("charge", "pour", "melt", "cast")

    # ---------- разливка наклоном (ряд форм на ленте) ----------

    MOLD_W = {"sheet": 150, "strip": 118, "rod": 90, "wire": 70}
    MOLD_GAP = 70
    CONV_V = 28.0                                       # пикс./с — лента везёт формы под носик

    def start_cast(self):
        self.phase = "cast"
        self.metal0 = self.metal = float(FG.charge_mass(self.charge))
        self.cast = [dict(kind=m, mass=0.0, over=0.0, tsum=0.0) for m in self.queue]
        self.conv = 0.0
        self.tilt = self.tilt_v = 0.0
        self.purity = max(0.3, self.purity - 0.05 * len(self.slag) - 0.05 * self.slag_left)   # шлак в металле
        self.slag, self.slag_left = [], 0
        self.say("Наклоняйте тигель: ЛКМ и мышь вверх", GOLD)

    def cast_geom(self):
        """Разливка: ось наклона — носик (правый край тигля), лента с формами внизу."""
        r = self.rect
        return (r.x + r.w * 0.36, r.y + r.h * 0.42), r.y + r.h * 0.86

    def mold_rects(self):
        """Формы на ленте: (x0, x1) отверстия; едут справа налево под носик."""
        (px, _), _ = self.cast_geom()
        out, x = [], px + 80 - self.conv
        for c in self.cast:
            w = self.MOLD_W[c["kind"]]
            out.append((x, x + w))
            x += w + self.MOLD_GAP
        return out

    def mold_depth(self, kind):
        return 54

    def bowl_local(self):
        return -280.0, 0.0, 0.0, 190.0                              # тигель в своих осях: носик в (0, 0)

    def cast_update(self, dt):
        mt = self.a["melt"]
        self.temp = max(20.0, self.temp - dt * 4)                     # вне горна остывает
        target = 0.0
        if self.tilt_anchor is not None:
            target = max(0.0, min(1.0, (self.tilt_anchor - self.mpos[1]) / 240)) * 1.75
        self.tilt_v += ((target - self.tilt) * 16 - self.tilt_v * 7.0) * dt       # тигель тяжёлый — с инерцией
        self.tilt = max(0.0, min(1.8, self.tilt + self.tilt_v * dt))
        (px, py), belt = self.cast_geom()
        ex = py - self.cast_bowl()[4] if self.metal > 0.5 else 0.0     # пикс. зеркала выше носика
        self.flow = min(240.0, 0.9 * max(0.0, ex) ** 1.4) if self.metal > 0 else 0.0
        m_ = min(self.metal, self.flow * dt)
        self.metal -= m_
        if m_ > 0:
            acc = max(0.0, 1 - abs(self.temp - (mt + 70)) / 110)
            self.stream.append([px + 4, py + 2, 25 + min(30.0, max(0.0, ex)) * 2.0, 10.0, m_, acc])
        self.conv += self.CONV_V * dt
        rects = self.mold_rects()
        for s_ in list(self.stream):
            s_[0] += s_[2] * dt
            s_[3] += 1500 * dt
            s_[1] += s_[3] * dt
            if s_[1] >= belt - 2:
                self.stream.remove(s_)
                hit = next((i for i, (a, b) in enumerate(rects) if a + 4 <= s_[0] <= b - 4), None)
                if hit is None:
                    self.spilt += s_[4]
                    self.drops.append([s_[0], belt, self.rng.uniform(-80, 80), self.rng.uniform(-160, -60), 0.6])
                    continue
                c = self.cast[hit]
                cap = FG.PRIMS[c["kind"]]["mass"]
                room = max(0.0, cap - c["mass"])
                put = min(room, s_[4])
                c["mass"] += put
                c["tsum"] += put * s_[5]
                if s_[4] > put:                                       # перелив — облой, металл в лом
                    c["over"] += s_[4] - put
                    if self.rng.random() < 0.3:
                        self.drops.append([s_[0], belt - self.mold_depth(c["kind"]), self.rng.uniform(-90, 90),
                                           self.rng.uniform(-200, -80), 0.6])
        for d in self.drops:
            d[0] += d[2] * dt
            d[1] += d[3] * dt
            d[3] += 900 * dt
            d[4] -= dt
        self.drops = [d for d in self.drops if d[4] > 0]
        if rects and rects[-1][1] < px - 140 and not self.stream:   # все формы проехали
            self.finish_cast()
        elif self.metal <= 0.5 and not self.stream:
            self.finish_cast()

    def cast_fills(self):
        out = []
        for c in self.cast:
            cap = FG.PRIMS[c["kind"]]["mass"]
            out.append(dict(kind=c["kind"], mass=round(c["mass"] + c["over"]), fill=round(c["mass"] / cap, 3),
                            over=round(c["over"] / cap, 3), temp=round(c["tsum"] / max(1e-6, c["mass"]), 3)))
        return out

    def finish_cast(self):
        if self.done:
            return
        fills = self.cast_fills()
        good = [f for f in fills if f["fill"] >= 0.5]
        acc = sum(f["temp"] for f in good) / len(good) if good else 0.0
        self.result = {"alloy": self.aid, "charge": dict(self.charge), "purity": round(self.purity, 3),
                       "heat": round(self.in_win / max(0.01, self.melt_t), 3), "mold": None, "pour": round(acc, 3),
                       "casts": fills, "spilt": round(self.spilt)}
        self.done = True
        self.say(f"Отлито форм: {len(good)} из {len(fills)}", OK if len(good) == len(fills) else BAD)

    def pour(self):
        mt = self.a["melt"]
        acc = max(0.0, 1 - abs(self.temp - (mt + 70)) / 110)
        self.purity = max(0.3, self.purity - 0.05 * len(self.slag) - 0.05 * self.slag_left)   # шлак в металле
        self.result = {"alloy": self.aid, "charge": dict(self.charge), "purity": round(self.purity, 3),
                       "heat": round(self.in_win / max(0.01, self.melt_t), 3), "mold": self.mold, "pour": round(acc, 3)}
        self.done = True
        self.say("Разлито!" if acc > 0.6 else "Разлито — холодно или перегрето", OK if acc > 0.6 else BAD)

    def update(self, dt):
        super().update(dt)
        if self.phase == "charge" or self.done:
            return
        if self.phase == "cast":
            self.cast_update(dt)
            return
        k = 0.9 if "bellows" in self.tools else 0.45
        target = self.tmax if self.hold else self.tmax * 0.45
        self.temp += (target - self.temp) * min(1.0, dt * k)
        mt = self.a["melt"]
        if self.phase == "melt":
            self.melt_t += dt
            if mt <= self.temp <= mt + 150:
                self.in_win += dt
                self.prog += dt * 0.11
            elif self.temp > mt + 150:
                self.prog += dt * 0.11
                self.purity = max(0.3, self.purity - dt * 0.04)      # перегрев — угар и окалина
            self.slag_t -= dt
            if self.temp >= mt - 40 and self.slag_t <= 0 and self.slag_left > 0:   # шлак всплывает
                self.slag_t = self.rng.uniform(1.8, 3.2)
                self.slag_left -= 1
                x0, x1, rim, floor = self.bowl()
                x = self.rng.uniform(x0 + 60, x1 - 60)
                self.slag.append([x, self.level(), 0.0, 0.0, self.rng.uniform(11, 17)])
            self.physics(dt)
            if self.prog >= 1:
                self.phase = "pour"
                self.grab = False
                self.say("Расплав готов — выберите формы и разливайте (Enter)", OK)
        if self.phase == "pour":
            self.physics(dt)

    def physics(self, dt):
        """Расплав — волны по столбцам (как струна), лопатка — пружина с инерцией, шлак плавает и толкается."""
        x0, x1, rim, floor = self.bowl()
        n = len(self.wh)
        col_w = (x1 - x0) / (n - 1)
        sx, sy = self.spat
        if self.spat == [0.0, 0.0]:
            sx, sy = self.spat[:] = [x1 - 60, rim - 120]
        steps = 4
        h = dt / steps
        spat = self.spat_on()
        if not spat:
            self.grab = False
        for _ in range(steps):
            # лопатка: тянется к мыши (взята) с инерцией; в расплаве — вязко
            if self.grab:
                tx = max(x0 + 40, min(x1 - 40, self.mpos[0]))
                ty = max(rim - 230, min(floor - 16, self.mpos[1]))
                ax, ay = (tx - sx) * 70 - self.spat_v[0] * 11, (ty - sy) * 70 - self.spat_v[1] * 11
            else:
                ax, ay = -self.spat_v[0] * 6, -self.spat_v[1] * 6
            self.spat_v[0] += ax * h
            self.spat_v[1] += ay * h
            in_liq = spat and sy > self.surf_y(sx)       # убранная лопатка волн не гонит
            if in_liq:
                self.spat_v[0] *= 1 - 3.5 * h
                self.spat_v[1] *= 1 - 3.5 * h
            sx += self.spat_v[0] * h
            sy += self.spat_v[1] * h
            sx = max(x0 + 40, min(x1 - 40, sx))
            sy = max(rim - 240, min(floor - 16, sy))
            # лопатка в расплаве гонит волну
            if in_liq:                                   # впереди лопатки расплав вспучивается, позади — проседает
                i = int((sx - x0) / col_w)
                depth = min(1.0, (sy - self.surf_y(sx)) / 40)
                for k in range(max(0, i - 4), min(n, i + 5)):
                    self.wv[k] += -self.spat_v[1] * self.KV * h * depth
                d_ = 1 if self.spat_v[0] > 0 else -1
                for j in range(1, 4):
                    for k, sg in ((i + d_ * (4 + j), 1), (i - d_ * (4 + j), -1)):
                        if 0 <= k < n:
                            self.wv[k] += sg * abs(self.spat_v[0]) * self.KH * h * depth
            # волны
            new = self.wv[:]
            for k in range(n):
                left = self.wh[k - 1] if k > 0 else self.wh[k]
                right = self.wh[k + 1] if k < n - 1 else self.wh[k]
                new[k] += ((left + right - 2 * self.wh[k]) * 1400 - self.wv[k] * 2.0) * h
            self.wv = new
            mean = sum(self.wh) / n
            self.wh = [w + v * h - mean for w, v in zip(self.wh, self.wv)]
        self.spat = [sx, sy]
        # пролив: волна у стенки выше края
        self.spill_cd = max(0.0, self.spill_cd - dt)
        for edge, wx in ((0, x0), (n - 1, x1)):
            if self.level() - self.wh[edge] < rim - 2 and self.spill_cd <= 0:
                self.spill_cd = 0.8
                self.purity = max(0.3, self.purity - 0.04)
                self.prog = max(0.0, self.prog - 0.03)
                self.wh[edge] *= 0.3
                self.say("Пролито через край!", BAD)
                for _ in range(10):
                    self.drops.append([wx, rim, self.rng.uniform(-120, 120), self.rng.uniform(-260, -80), 0.9])
        for d in self.drops:
            d[0] += d[2] * dt
            d[1] += d[3] * dt
            d[3] += 900 * dt
            d[4] -= dt
        self.drops = [d for d in self.drops if d[4] > 0]
        # шлак: плавает на поверхности, сползает по уклону, его толкает и поднимает лопатка
        blade_half = 38
        for s_ in list(self.slag):
            x, y, vx, vy, r = s_
            i = max(1, min(n - 2, int((x - x0) / col_w)))
            surf = self.level() - self.wh[i]
            on_blade = abs(x - sx) < blade_half and sy - r - 8 <= y <= sy + 2
            if on_blade and abs(self.spat_v[0]) < 520:          # лежит на лопатке — едет вместе с ней
                x += (sx - x) * min(1.0, dt * 10)
                y = sy - r * 0.8
                vx, vy = self.spat_v
                if y < rim - 26:                                # поднят над краем — снят
                    self.slag.remove(s_)
                    self.removed += 1
                    self.say(f"Шлак снят ({self.removed})", OK)
                    continue
            else:
                slope = (self.wh[i + 1] - self.wh[i - 1]) / (2 * col_w)
                vx += slope * 900 * dt - vx * 1.2 * dt
                target = surf - r * 0.35
                vy += ((target - y) * 40 - vy * 6) * dt
                if abs(x - sx) < blade_half + r and abs(y - sy) < r + 6:   # толкнула лопатка
                    vx = self.spat_v[0] * 0.9 + (r if x > sx else -r)
                x += vx * dt
                y += vy * dt
            x = max(x0 + r, min(x1 - r, x))
            s_[:] = [x, y, vx, vy, r]

    def draw(self, surf, rect):
        self.rect = rect
        self.rects = {}
        pygame.draw.rect(surf, (22, 18, 16), rect, border_radius=10)
        a = self.a
        T.text(surf, f"{a['name']}", (rect.x + 24, rect.y + 16), 24, GOLD, True)
        mix = " · ".join(f"{FG_name(m)} {s * 100:.1f}%" for m, s in a["mix"].items())
        if a["coal"]:
            mix += f" · уголь ≈ {a['coal'] * 250:.0f}% к руде (углерод)"
        T.text(surf, "по книге: " + mix, (rect.x + 24, rect.y + 48), 14, DIM)
        if self.phase != "cast":
            T.text(surf, f"плавится при {a['melt']} °C · горн даёт до {self.tmax} °C", (rect.x + 24, rect.y + 68), 14,
                   DIM)
            self.draw_charge(surf, rect)
        self.draw_crucible(surf, rect)
        self.draw_flash(surf, rect)

    def draw_charge(self, surf, rect):
        x, y = rect.x + 24, rect.y + 104
        T.text(surf, "Весы", (x, y), 18, (230, 210, 170), True)
        y += 30
        metal = sum(v for m, v in self.charge.items() if m != "coal") or 1
        for m, v in self.charge.items():
            row = pygame.Rect(x, y, 330, 46)
            pygame.draw.rect(surf, (34, 27, 21), row, border_radius=8)
            T.text(surf, FG_name(m), (row.x + 10, row.y + 6), 15, T.TEXT, True)
            want = a_share(self.a, m)
            have = v / metal
            T.text(surf, f"{v * 10} г · {have * 100:.1f}% (нужно {want * 100:.1f}%) · есть {self.stock.get(m, 0) * 10} г",
                   (row.x + 10, row.y + 26), 12, OK if abs(have - want) < max(0.01, want * 0.08) else DIM)
            for i, sign in enumerate(("-", "+")):
                b = pygame.Rect(row.right - 70 + i * 36, row.y + 8, 30, 30)
                self.rects[(sign, m)] = b
                button(surf, b, "−" if sign == "-" else "+", self.phase == "charge", b.collidepoint(self.mpos))
            y += 52
        acc = FG.mix_accuracy(self.aid, self.charge) if any(self.charge.values()) else 0.0
        T.text(surf, f"Слиток: {FG.charge_mass(self.charge)} г · точность смеси {acc * 100:.0f}%", (x, y + 6), 16,
               OK if acc > 0.9 else T.TEXT, True)
        self.panel_y = y + 44                                     # ниже весов — панель форм
        if self.phase == "charge":
            b = pygame.Rect(x, y + 36, 220, 44)
            self.rects[("go", None)] = b
            button(surf, b, "В горн (Enter)", FG.charge_mass(self.charge) >= 50, b.collidepoint(self.mpos))

    def center(self):
        return self.rect.x + self.rect.w * 0.56, self.rect.y + self.rect.h * 0.36

    def draw_bowl(self, surf):
        draw_bowl_into(self, surf)

    def draw_crucible(self, surf, rect):
        if self.phase == "cast":
            return self.draw_cast(surf, rect)
        cx, cy = self.center()
        floor = self.bowl()[3]
        fh = int(rect.bottom - 8 - floor)                       # горн под тигелем — целиком в панели
        forge = MV.prop("frg_forge", None, max(60, min(260, fh))) if fh > 60 else None
        if forge is not None:                                   # тигель стоит над горном
            surf.blit(forge, (cx - forge.get_width() // 2, rect.bottom - 8 - forge.get_height()))
        self.draw_bowl(surf)
        if self.phase == "melt":
            bar = pygame.Rect(cx - 120, cy - 120, 240, 12)
            pygame.draw.rect(surf, (40, 34, 30), bar, border_radius=5)
            pygame.draw.rect(surf, (240, 170, 80), (bar.x, bar.y, int(bar.w * min(1, self.prog)), bar.h), border_radius=5)
            T.text(surf, f"плавка · чистота {self.purity * 100:.0f}% · шлак снят {self.removed}", (bar.centerx,
                   bar.bottom + 8), 13, DIM, center=True)
        if self.phase in ("melt", "pour"):
            g = pygame.Rect(rect.right - 210, rect.y + 90, 30, rect.h - 160)
            mt = self.a["melt"]
            win = (mt, mt + 150) if self.phase == "melt" else (mt + 20, mt + 120)
            gauge(surf, g, self.temp, self.tmax, win, self.numeric)
            if not self.numeric:
                T.text(surf, "без пирометра —", (g.centerx, g.bottom + 30), 12, DIM, center=True)
                T.text(surf, "на глаз по свечению", (g.centerx, g.bottom + 46), 12, DIM, center=True)
        if self.phase == "pour":
            x, y0 = rect.x + 24, getattr(self, "panel_y", rect.y + 300)
            T.text(surf, "Формы на ленту:", (x, y0), 18, (230, 210, 170), True)
            if not self.molds:
                T.text(surf, "форм нет — всё в изложницу (слиток для ковки)", (x, y0 + 30), 13, DIM)
            for i, m in enumerate(self.molds):
                row = pygame.Rect(x, y0 + 30 + i * 48, 330, 42)
                pygame.draw.rect(surf, (34, 27, 21), row, border_radius=8)
                n = self.queue.count(m)
                T.text(surf, f"{i + 1}  {FG.PRIMS[m]['name']} · {FG.PRIMS[m]['mass']} г", (row.x + 10, row.y + 11), 15,
                       T.TEXT, True)
                b1 = pygame.Rect(row.right - 108, row.y + 6, 30, 30)
                b2 = pygame.Rect(row.right - 36, row.y + 6, 30, 30)
                self.rects[("unmold", m)] = b1
                self.rects[("mold", m)] = b2
                button(surf, b1, "−", n > 0, b1.collidepoint(self.mpos))
                T.text(surf, str(n), (row.right - 57, row.centery), 16, GOLD if n else DIM, True, center=True)
                button(surf, b2, "+", True, b2.collidepoint(self.mpos))
            y = y0 + 40 + 48 * max(1, len(self.molds))
            mass = FG.charge_mass(self.charge)
            T.text(surf, f"в формы {self.queue_mass()} г из {mass} г · остаток — в слиток", (x, y), 13, DIM)
            b = pygame.Rect(x, y + 26, 330, 44)
            self.rects[("pour", None)] = b
            button(surf, b, "К разливке (Enter)" if self.queue else "В изложницу (Enter)", True,
                   b.collidepoint(self.mpos))

    # ---------- разливка: рисунок ----------

    def cast_bowl(self):
        """Тигель на разливке в экранных координатах: стенки, полость и расплав (горизонтальное зеркало)."""
        (px, py), _ = self.cast_geom()
        c, s_ = math.cos(self.tilt), math.sin(self.tilt)

        def rot(p_):
            return (px + p_[0] * c - p_[1] * s_, py + p_[0] * s_ + p_[1] * c)
        x0, x1, rim, floor = self.bowl_local()
        wall = [rot(p_) for p_ in _bowl_poly(x0 - 22, x1 + 22, rim - 6, floor + 22)]
        inner = [rot(p_) for p_ in _bowl_poly(x0, x1, rim, floor)]
        need = _area(inner) * 0.83 * self.metal / max(1.0, self.metal0)
        lo, hi = min(p_[1] for p_ in inner), max(p_[1] for p_ in inner)
        for _ in range(28):                                         # уровень зеркала: площадь = объём металла
            mid = (lo + hi) / 2
            if _area(_clip_below(inner, mid)) > need:
                lo = mid
            else:
                hi = mid
        liquid = _clip_below(inner, hi) if need > 1 else []
        return wall, inner, liquid, rot, hi

    def draw_cast(self, surf, rect):
        (px, py), belt = self.cast_geom()
        glow = heat_color(min(self.temp, 1150))
        # лента и формы в разрезе
        pygame.draw.rect(surf, (52, 44, 38), (rect.x + 20, belt + 18, rect.w - 270, 14), border_radius=6)
        for k in range(int((rect.w - 270) / 40) + 1):
            xr = rect.x + 30 + ((k * 40 - self.conv) % (rect.w - 280))
            AA.circle(surf, (90, 80, 70), (xr, belt + 25), 5)
        for (a, b), c in zip(self.mold_rects(), self.cast):
            if b < rect.x + 10 or a > rect.right - 240:
                continue
            d = self.mold_depth(c["kind"])
            cap = FG.PRIMS[c["kind"]]["mass"]
            pygame.draw.rect(surf, (96, 84, 72), (a - 12, belt - d - 8, b - a + 24, d + 26), border_radius=4)
            pygame.draw.rect(surf, (38, 32, 28), (a, belt - d, b - a, d))
            f = min(1.0, c["mass"] / cap)
            if f > 0:
                AA.polygon(surf, glow, [(a, belt), (b, belt), (b, belt - d * f), (a, belt - d * f)])
            if c["over"] > 0:                                       # облой: металл на кромках формы
                w_ = min(26, 6 + c["over"] / cap * 60)
                AA.polygon(surf, glow, [(a - w_, belt - d - 8), (b + w_, belt - d - 8), (b + w_ * 0.6, belt - d - 2),
                                        (a - w_ * 0.6, belt - d - 2)])
            AA.line(surf, (200, 180, 140), (a - 12, belt - d - 8), (b + 12, belt - d - 8), 2)   # край = метка
            col = OK if 0.95 <= f and c["over"] < cap * 0.05 else BAD if c["over"] >= cap * 0.05 else DIM
            T.text(surf, f"{FG.PRIMS[c['kind']]['name']} {f * 100:.0f}%" + (" · перелив" if c["over"] >= cap * 0.05
                                                                            else ""), ((a + b) / 2, belt + 44), 13,
                   col, True, center=True)
        # тигель: стенки, полость, расплав
        wall, inner, liquid, rot, _ = self.cast_bowl()
        AA.polygon(surf, (92, 70, 56), wall)
        AA.polygon(surf, (60, 46, 38), inner)
        if len(liquid) >= 3:
            AA.polygon(surf, glow, liquid)
            top = [p_ for p_ in liquid if abs(p_[1] - min(q[1] for q in liquid)) < 0.5]
            if len(top) >= 2:
                AA.line(surf, heat_color(min(self.temp, 1450)), min(top), max(top), 4)
        AA.line(surf, (150, 120, 96), rot((-302, -6)), rot((22, -6)), 6)
        # струя
        pts = sorted(((s_[0], s_[1]) for s_ in self.stream), key=lambda p_: p_[1])
        if len(pts) >= 2:
            AA.lines(surf, glow, False, pts, max(3, min(10, int(3 + self.flow / 40))))
        for s_ in self.stream[-1:]:
            AA.circle(surf, glow, (s_[0], s_[1]), 4)
        for d_ in self.drops:
            AA.circle(surf, glow, (d_[0], d_[1]), 3)
        T.text(surf, f"в тигле {self.metal:.0f} г · пролито {self.spilt:.0f} г · наклон {math.degrees(self.tilt):.0f}°",
               (rect.x + 24, rect.y + 72), 15, T.TEXT, True)
        g = pygame.Rect(rect.right - 70, rect.y + 90, 30, rect.h - 170)
        mt = self.a["melt"]
        gauge(surf, g, self.temp, self.tmax, (mt + 20, mt + 120), self.numeric)
        if self.tilt_anchor is not None:
            AA.line(surf, (255, 220, 150), (self.mpos[0] - 30, self.tilt_anchor), (self.mpos[0] + 30, self.tilt_anchor),
                    1)


def _area(poly):
    if len(poly) < 3:
        return 0.0
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2


def _clip_below(poly, y):
    """Часть многоугольника ниже горизонтали y (экран: y растёт вниз)."""
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ia, ib = a[1] >= y, b[1] >= y
        if ia:
            out.append(a)
        if ia != ib:
            t = (y - a[1]) / (b[1] - a[1])
            out.append((a[0] + (b[0] - a[0]) * t, y))
    return out


def _bowl_poly(x0, x1, rim, floor, inset=0):
    k = 28
    return [(x0 + inset, rim), (x1 - inset, rim), (x1 - k - inset, floor - inset), (x0 + k + inset, floor - inset)]


def draw_bowl_into(game, surf):
    """Тигель в разрезе: толстые глиняные стенки, расплав с волнующейся поверхностью, шлак, лопатка, брызги."""
    x0, x1, rim, floor = game.bowl()
    AA.polygon(surf, (92, 70, 56), _bowl_poly(x0 - 22, x1 + 22, rim - 6, floor + 22))      # стенки
    AA.polygon(surf, (60, 46, 38), _bowl_poly(x0, x1, rim, floor))
    n = len(game.wh)
    hot = game.phase != "charge"
    # расплав: тело — оранжево-жёлтое (не выгорает в белое), поверхность — ярче, глубже — темнее
    glow = heat_color(min(game.temp, 1150)) if hot else (60, 52, 48)
    if hot or any(game.charge.values()):
        pts = []
        for k in range(n):
            x = x0 + (x1 - x0) * k / (n - 1)
            pts.append((x, game.level() - game.wh[k]))
        k_ = 28
        poly = pts + [(x1 - k_, floor), (x0 + k_, floor)]
        AA.polygon(surf, glow, poly)
        if hot:
            y_top = max(p_[1] for p_ in pts) + 10
            for j in range(6):                                   # глубже — темнее
                ya = y_top + (floor - y_top) * j / 6
                ka = (ya - rim) / max(1, floor - rim)
                xa0 = x0 + k_ * ka
                kb = (floor - rim)
                yb = y_top + (floor - y_top) * (j + 1) / 6
                xb0 = x0 + k_ * (yb - rim) / kb
                c = tuple(int(v * (1 - 0.07 * (j + 1))) for v in glow)
                AA.polygon(surf, c, [(xa0, ya), (x1 - (xa0 - x0), ya), (x1 - (xb0 - x0), yb), (xb0, yb)])
        top_c = heat_color(min(game.temp, 1450)) if hot else tuple(min(255, c + 40) for c in glow)
        AA.lines(surf, top_c, False, pts, 4)
    for i, s_ in enumerate(game.slag):                           # шлак — комковатые тёмные корки на расплаве
        r_ = s_[4]
        blob = [(s_[0] + math.cos(j * 0.785) * r_ * (1.25 if j in (0, 4) else 0.8 + 0.2 * ((i * 7 + j * 3) % 3)),
                 s_[1] + math.sin(j * 0.785) * r_ * 0.7) for j in range(8)]
        AA.polygon(surf, (50, 40, 34), blob)
        AA.lines(surf, (120, 70, 40), True, blob, 1)
        AA.circle(surf, (96, 82, 70), (s_[0] - r_ * 0.35, s_[1] - r_ * 0.2), r_ * 0.3)
    AA.line(surf, (150, 120, 96), (x0 - 22, rim - 6), (x1 + 22, rim - 6), 6)                 # край
    if game.spat_on():                                           # лопатка: черенок вверх, плоское лезвие
        sx, sy = game.spat
        tilt = max(-0.4, min(0.4, game.spat_v[0] / 900))
        dx, dy = math.cos(tilt) * 38, math.sin(tilt) * 38
        AA.line(surf, (110, 76, 46), (sx, sy - 4), (sx + 30 + tilt * 60, sy - 230), 8)
        AA.line(surf, (190, 190, 200), (sx - dx, sy - dy), (sx + dx, sy + dy), 7)
        AA.line(surf, (235, 235, 245), (sx - dx, sy - dy - 3), (sx + dx, sy + dy - 3), 2)
    for d in game.drops:
        AA.circle(surf, glow, (d[0], d[1]), 4)


def FG_name(m):
    return {"ore": "Железная руда", "coal": "Уголь", "copper": "Медь", "tin": "Олово", "silver": "Серебро",
            "gold": "Золото", "meteor": "Метеоритное железо", "embersteel": "Эмбер-руда"}.get(m, m)


def a_share(a, m):
    if m == "coal":
        return a["coal"] * 2.5
    return a["mix"].get(m, 0.0)


# ---------- ковка примитива ----------

ITEM_SHAPES = {"bracers": "наруч", "belt": "пояс", "ring": "кольцо", "amulet": "амулет"}
LIQ_COLOR = {"water": (70, 120, 170), "oil": (120, 84, 30), "brine": (120, 140, 150), "salamander": (150, 40, 30),
             "glacier": (120, 190, 220)}


class TemperGame(FGame):
    """Термообработка: деталь лежит в горне (Пробел — меха), клещами (ЛКМ, с инерцией) её несут в бочку и держат
    в жидкости; жидкость подогревают (E), её греет и сама деталь. Важны жар детали при погружении, при выемке и
    температура ванны. Затем отпуск по цвету побежалости. Не закаливаемые металлы — только отжиг."""
    title = "Закалка"
    HINTS = {"heat": "ЛКМ — клещи: деталь из горна (Пробел — меха) в бочку, выньте вовремя; E — подогрев жидкости, "
                     "1–5 — жидкость",
             "temper": "Пробел — нагрев для отпуска, следите за цветом, Enter — остановить",
             "anneal": "Enter — отжечь и отполировать"}

    @property
    def hint(self):
        return self.HINTS.get(self.phase, "")

    def __init__(self, item_kind, prims, tools, forge_level, seed=None):
        super().__init__(seed)
        self.kind = item_kind
        self.prims = prims
        self.tools = set(tools)
        self.tmax = FG.max_temp(forge_level)
        hard = [p for p in prims if FG.ALLOYS[p["alloy"]].get("quench")]
        self.aid = max(hard, key=lambda p: p["mass"])["alloy"] if hard else prims[0]["alloy"]
        self.a = FG.ALLOYS[self.aid]
        self.phase = "heat" if hard else "anneal"
        self.temp = 20.0                     # жар детали
        self.hold = False
        self.liquids = [l_ for l_ in FG.LIQUIDS if l_ in self.tools] or ["water"]
        self.liquid = self.liquids[0]
        self.bath_t = float(FG.bath_start(self.liquid))
        self.quench_hard, self.crack, self.temper_acc = 1.0, False, 1.0
        self.report = {}
        self.steam = 0.0
        self.bubbles = []
        self.where = "forge"                 # forge | tongs | air | bath
        self.ipos = None                     # деталь: положение и скорость (экран)
        self.ivel = [0.0, 0.0]
        self.tong = None                     # клещи: губки — положение, скорость; grab — ЛКМ зажата
        self.tong_v = [0.0, 0.0]
        self.grab = False
        self.in_bath = False
        self.t_in = None                     # жар при погружении
        self.started = False                 # деталь в ванне остыла ниже 500 °C — закалка пошла
        self.bath_time = 0.0

    @property
    def book(self):
        return "b_quench" in self.tools

    # ---------- геометрия сцены ----------

    def hearth(self):
        r = self.rect
        return r.x + r.w * 0.16, r.bottom - 10 - self.forge_h() * 0.27

    def forge_h(self):
        return min(300, self.rect.h * 0.5)

    def bath(self):
        """Бочка в разрезе: (x0, x1, зеркало, дно)."""
        r = self.rect
        x0 = r.x + r.w * 0.48
        return x0, x0 + 230, r.y + r.h * 0.5, r.bottom - 24

    def floor_y(self):
        return self.rect.bottom - 22

    def place(self):
        if self.ipos is None:
            self.ipos = list(self.hearth())
        if self.tong is None:
            hx, hy = self.hearth()
            self.tong = [hx + 140, hy - 120]

    def in_liquid(self, p_):
        x0, x1, sy, by = self.bath()
        return x0 + 6 < p_[0] < x1 - 6 and sy < p_[1] < by

    # ---------- ввод ----------

    def can_abort(self):
        return self.phase in ("heat", "anneal") and self.t_in is None and self.temp < 100

    def stop(self):
        self.finish()

    def finish(self):
        self.done = True
        heat = (0.6 * self.quench_hard + 0.4 * self.temper_acc) * (0.4 if self.crack else 1.0) \
            if self.phase != "anneal" else 0.85
        self.result = {"heat": round(heat, 3), "quench_hard": self.quench_hard, "temper_acc": self.temper_acc,
                       "crack": self.crack}

    @property
    def quality(self):
        heat = (0.6 * self.quench_hard + 0.4 * self.temper_acc) * (0.4 if self.crack else 1.0)
        return round(0.7 + 0.6 * min(heat, FG.gauge_cap(self.tools)), 3)

    def press(self):
        self.hold = True

    def release(self):
        self.hold = False

    def pointer(self, ev, rect):
        if self.phase != "heat" or self.done:
            return False
        self.place()
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.grab = True
            if math.hypot(self.tong[0] - self.ipos[0], self.tong[1] - self.ipos[1]) < 46:
                self.where = "tongs"                     # губки сомкнулись на детали
            return True
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.grab:
            self.grab = False
            if self.where == "tongs":
                hx, hy = self.hearth()
                if self.in_liquid(self.ipos):
                    self.where = "bath"                  # отпустили в бочке — тонет
                elif math.hypot(self.ipos[0] - hx, self.ipos[1] - hy) < 80:
                    self.where = "forge"
                    self.ipos = [hx, hy]
                else:
                    self.where = "air"                   # падает на пол
                self.ivel = list(self.tong_v)
            return True
        return False

    def key(self, k):
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.phase == "heat":
                self.say("Клещами — в бочку: погрузите и выньте вовремя", GOLD)
            elif self.phase == "temper":
                self.temper_acc = FG.temper_result(self.aid, self.temp)
                self.finish()
            elif self.phase == "anneal":
                self.finish()
            return True
        if self.phase == "heat" and pygame.K_1 <= k <= pygame.K_5:
            i = k - pygame.K_1
            if i < len(self.liquids) and self.t_in is None and not self.in_bath:
                self.liquid = self.liquids[i]
                self.bath_t = float(FG.bath_start(self.liquid))
            return True
        return False

    # ---------- физика ----------

    def update(self, dt):
        super().update(dt)
        self.steam = max(0.0, self.steam - dt)
        for b in self.bubbles:
            b[1] -= b[2] * dt
            b[3] -= dt
        self.bubbles = [b for b in self.bubbles if b[3] > 0]
        if self.done:
            return
        if self.phase == "heat":
            self.heat_update(dt)
        elif self.phase == "temper":
            if self.hold:
                self.temp = min(420.0, self.temp + dt * 45)     # отпуск — медленно, по цвету

    def heat_update(self, dt):
        self.place()
        room = FG.bath_start(self.liquid)
        if self._held(pygame.K_e):                            # жаровня под бочкой
            self.bath_t = min(260.0, self.bath_t + dt * 9)
        else:
            self.bath_t += (room - self.bath_t) * min(1.0, dt * 0.01)
        # клещи: тянутся к мыши с инерцией; в жидкости — вязко
        tx, ty = self.tong
        if self.grab:
            r = self.rect
            mx = max(r.x + 20, min(r.right - 120, self.mpos[0]))
            my = max(r.y + 60, min(self.floor_y() - 6, self.mpos[1]))
            ax, ay = (mx - tx) * 60 - self.tong_v[0] * 10, (my - ty) * 60 - self.tong_v[1] * 10
        else:
            ax, ay = -self.tong_v[0] * 6, -self.tong_v[1] * 6
        self.tong_v[0] += ax * dt
        self.tong_v[1] += ay * dt
        if self.in_liquid(self.tong):
            self.tong_v[0] *= max(0.0, 1 - 4 * dt)
            self.tong_v[1] *= max(0.0, 1 - 4 * dt)
        self.tong = [tx + self.tong_v[0] * dt, ty + self.tong_v[1] * dt]
        # деталь
        if self.where == "tongs":
            self.ipos = list(self.tong)
        elif self.where == "air":
            self.ivel[1] += 1400 * dt
            self.ipos[0] += self.ivel[0] * dt
            self.ipos[1] += self.ivel[1] * dt
            if self.in_liquid(self.ipos):
                self.where = "bath"
            elif self.ipos[1] >= self.floor_y():
                self.ipos[1] = self.floor_y()
                self.ivel = [0.0, 0.0]
        elif self.where == "bath":
            x0, x1, sy, by = self.bath()
            self.ipos[1] = min(by - 14, self.ipos[1] + 60 * dt)       # тонет
            self.ipos[0] = max(x0 + 20, min(x1 - 20, self.ipos[0]))
        # жар
        if self.where == "forge":
            k = (1.2 if "bellows" in self.tools else 0.6) if self.hold else 0.3
            target = self.tmax * (0.95 if self.hold else 0.62)
            self.temp += (target - self.temp) * min(1.0, dt * k)
        elif self.in_liquid(self.ipos):
            rate = FG.bath_rate(self.liquid, self.bath_t)
            if not self.in_bath:                                      # вошла в жидкость
                self.in_bath = True
                if self.t_in is None:
                    self.t_in = self.temp
                    self.bath_time = 0.0
                sp = math.hypot(*self.tong_v) if self.where == "tongs" else math.hypot(*self.ivel)
                if sp > 700:
                    self.say("Брызги!", BAD, 0.6)
                self.steam = 1.2 if self.temp > 300 else 0.3
            new = self.bath_t + (self.temp - self.bath_t) * math.exp(-rate * dt)
            self.bath_t += (self.temp - new) * 0.012                  # жидкость греется от детали
            self.temp = new
            self.bath_time += dt
            if self.temp < 500:
                self.started = True
            if self.temp > 120 and self.rng.random() < dt * 30:
                self.bubbles.append([self.ipos[0] + self.rng.uniform(-18, 18), self.ipos[1], self.rng.uniform(60, 140),
                                     0.8])
            if self.where == "bath" and self.started and self.temp < self.bath_t + 8:
                self.quench_done()                                    # бросили в бочке — остыла до конца
        else:
            if self.in_bath:                                          # вынули из жидкости
                self.in_bath = False
                if self.started:
                    self.quench_done()
                    return
                self.t_in = None                                      # только окунули — не в счёт
            self.temp -= (self.temp - 20) * min(1.0, dt * 0.12)       # остывает на воздухе

    def quench_done(self):
        hard, crack, rep = FG.quench_eval(self.aid, self.t_in or self.temp, self.liquid, self.bath_t, self.temp, self.rng)
        self.quench_hard, self.crack, self.report = hard, crack, rep
        self.t_out = self.temp
        self.say("Трещина при закалке!" if crack else f"Закалено: {hard * 100:.0f}%", BAD if crack else OK, 2.0)
        self.phase = "temper"
        self.temp = 20.0
        self.grab = False

    # ---------- рисунок ----------

    def item_color(self):
        if self.phase == "temper":
            return FG.temper_color(self.temp)
        return heat_color(self.temp) if self.temp > 520 else self.a["color"]

    def draw_item(self, surf, c, size):
        col = self.item_color()
        if self.kind == "ring":
            AA.circle(surf, col, c, size * 0.45, max(4, int(size * 0.1)))
        elif self.kind == "amulet":
            AA.circle(surf, col, c, size * 0.35)
            AA.line(surf, col, (c[0] - size * 0.3, c[1] - size * 0.6), (c[0], c[1] - size * 0.35), 3)
            AA.line(surf, col, (c[0] + size * 0.3, c[1] - size * 0.6), (c[0], c[1] - size * 0.35), 3)
        elif self.kind == "belt":
            AA.polygon(surf, col, [(c[0] - size, c[1] - size * 0.12), (c[0] + size, c[1] - size * 0.12),
                                   (c[0] + size, c[1] + size * 0.12), (c[0] - size, c[1] + size * 0.12)])
            AA.circle(surf, col, (c[0] + size * 0.8, c[1]), size * 0.2, 4)
        else:
            pts = [(c[0] - size * 0.6, c[1] - size * 0.5), (c[0] + size * 0.6, c[1] - size * 0.45),
                   (c[0] + size * 0.7, c[1] + size * 0.45), (c[0] - size * 0.7, c[1] + size * 0.5)]
            AA.polygon(surf, col, pts)
            AA.lines(surf, (40, 30, 24), True, pts, 2)

    def head(self, surf, rect):
        a = self.a
        T.text(surf, f"{ITEM_SHAPES.get(self.kind, self.kind).capitalize()} · {a['name']}", (rect.x + 24, rect.y + 16),
               24, GOLD, True)
        if self.phase == "anneal":
            T.text(surf, f"{a['name']} не закаливается — отжечь и отполировать", (rect.x + 24, rect.y + 50), 14, DIM)
        elif self.book:
            tc = FG.TEMPER[a["temper"]]
            T.text(surf, f"по книге: погрузить при {a['quench']} °C в «{FG.LIQUIDS[a['liquid']][0]}» (ванна "
                         f"≈{FG.BATH[a['liquid']]} °C), вынуть при ≈{FG.quench_out(self.aid)} °C; отпуск — "
                         f"«{tc[0]}» ({tc[1]} °C)", (rect.x + 24, rect.y + 50), 14, DIM)
        else:
            T.text(surf, "без книги «Закалка и отпуск» — наугад: цвет каления, магнит, побежалость",
                   (rect.x + 24, rect.y + 50), 14, DIM)

    def draw(self, surf, rect):
        self.rect = rect
        pygame.draw.rect(surf, (22, 18, 16), rect, border_radius=10)
        self.head(surf, rect)
        if self.phase == "heat":
            self.draw_quench(surf, rect)
        else:
            c = (rect.x + rect.w * 0.4, rect.y + rect.h * 0.5)
            self.draw_item(surf, c, rect.h * 0.28)
            if self.phase == "temper":
                T.text(surf, f"побежалость: {self.temper_word()}", (rect.x + 24, rect.bottom - 70), 18,
                       FG.temper_color(self.temp), True)
                if "hardness" in self.tools:
                    T.text(surf, f"твердомер: закалка {self.quench_hard * 100:.0f}%", (rect.x + 24, rect.bottom - 44),
                           14, DIM)
                if "pyrometer" in self.tools:
                    T.text(surf, f"{self.temp:.0f} °C", (rect.right - 120, rect.y + 90), 20, (255, 230, 190), True)
        self.draw_flash(surf, rect)

    def draw_quench(self, surf, rect):
        self.place()
        a = self.a
        fh = int(self.forge_h())
        forge = MV.prop("frg_forge", None, fh)
        hx, hy = self.hearth()
        if forge is not None:
            surf.blit(forge, (hx - forge.get_width() / 2, rect.bottom - 10 - forge.get_height()))
        pygame.draw.line(surf, (60, 50, 44), (rect.x + 16, self.floor_y() + 8), (rect.right - 100, self.floor_y() + 8), 2)
        # бочка в разрезе: клёпки-обручи, жидкость полупрозрачная — деталь видна внутри
        x0, x1, sy, by = self.bath()
        pygame.draw.rect(surf, (96, 66, 40), (x0 - 16, sy - 40, x1 - x0 + 32, by - sy + 52), border_radius=10)
        pygame.draw.rect(surf, (34, 26, 20), (x0, sy - 40, x1 - x0, by - sy + 40))
        for yy in (sy - 20, (sy + by) / 2, by - 10):
            pygame.draw.rect(surf, (70, 72, 78), (x0 - 18, yy - 4, x1 - x0 + 36, 8), border_radius=3)
        lc = LIQ_COLOR.get(self.liquid, (80, 120, 170))
        self.draw_item(surf, self.ipos, 46)
        liq = pygame.Surface((int(x1 - x0), int(by - sy)), pygame.SRCALPHA)
        liq.fill(lc + (115,))
        surf.blit(liq, (x0, sy))
        wob = 3 * math.sin(self.t * 6) if self.in_bath else 0
        AA.line(surf, tuple(min(255, c + 60) for c in lc), (x0, sy + wob), (x1, sy - wob), 3)
        for b in self.bubbles:
            if b[1] > sy:
                AA.circle(surf, (230, 235, 240), (b[0], b[1]), 3, 1)
        if self.steam > 0:
            for i in range(8):
                AA.circle(surf, (200, 200, 210), ((x0 + x1) / 2 + math.sin(self.t * 4 + i) * 30,
                                                  sy - 30 - (1.2 - self.steam) * 60 - i * 14), 9 - i * 0.8)
        # термометр ванны — всегда цифрой; по книге — нужная полоса
        tr = pygame.Rect(x1 + 30, sy - 30, 14, by - sy + 20)
        pygame.draw.rect(surf, (30, 26, 24), tr, border_radius=7)
        k = max(0.0, min(1.0, self.bath_t / 260))
        pygame.draw.rect(surf, (210, 70, 60), (tr.x + 3, tr.bottom - 3 - (tr.h - 6) * k, tr.w - 6, (tr.h - 6) * k),
                         border_radius=4)
        if self.book:
            want = FG.BATH[self.liquid]
            yy = tr.bottom - 3 - (tr.h - 6) * want / 260
            pygame.draw.rect(surf, OK, (tr.x - 5, yy - 6, tr.w + 10, 12), 1, border_radius=3)
        T.text(surf, f"{self.bath_t:.0f} °C", (tr.centerx, tr.bottom + 6), 13, T.TEXT, True, center=True)
        T.text(surf, f"{FG.LIQUIDS[self.liquid][0]}", ((x0 + x1) / 2, by + 6), 14, T.TEXT, True, center=True)
        # клещи: губки — в точке клещей, рукояти — вверх-влево
        spr = MV.prop("frg_tongs", 240)
        tx, ty = self.tong
        if spr is not None:
            rs = pygame.transform.rotozoom(spr, -32, 1.0)
            w = spr.get_width()
            c = (tx - w * 0.5 * math.cos(math.radians(32)), ty - w * 0.5 * math.sin(math.radians(32)))
            surf.blit(rs, (c[0] - rs.get_width() / 2, c[1] - rs.get_height() / 2))
        else:
            AA.line(surf, (90, 80, 76), (tx, ty), (tx - 180, ty - 110), 5)
        # подписи
        where = {"forge": "в горне", "tongs": "в клещах", "air": "на полу", "bath": "в бочке"}[self.where]
        T.text(surf, f"деталь: {where}" + (" · в жидкости" if self.in_bath else ""), (rect.x + 24, rect.y + 76), 15,
               T.TEXT, True)
        y = rect.y + 100
        if len(self.liquids) > 1:
            T.text(surf, "жидкость: " + "  ".join(f"[{i + 1}] {FG.LIQUIDS[l_][0]}" + (" ◄" if l_ == self.liquid else "")
                                                for i, l_ in enumerate(self.liquids)), (rect.x + 24, y), 14, DIM)
            y += 22
        if "magnet" in self.tools and self.where == "forge":
            stick = self.temp < 770
            T.text(surf, "магнит: " + ("держит" if stick else "не держит — точка Кюри пройдена"), (rect.x + 24, y), 14,
                   DIM if stick else OK, True)
            y += 22
        if "hourglass" in self.tools and self.t_in is not None:
            T.text(surf, f"песочные часы: в жидкости {self.bath_time:.1f} с", (rect.x + 24, y), 14, DIM, True)
        g = pygame.Rect(rect.right - 70, rect.y + 90, 30, rect.h - 170)
        win = (a["quench"] - 25, a["quench"] + 25) if self.book else None
        gauge(surf, g, self.temp, self.tmax, win, "pyrometer" in self.tools)

    def temper_word(self):
        best = min(FG.TEMPER.values(), key=lambda v: abs(v[1] - self.temp))
        return best[0] if self.temp > 190 else "металл светлый"


# ---------- изделие: сборка из примитивов, клёпка, испытание, затем закалка ----------

PIECE_PX = {"sheet": (150, 96), "strip": (232, 28), "rod": (170, 16), "wire": (210, 8)}
LAYOUT = {   # контур изделия: (вид, dx, dy, угол °) относительно центра стола
    "bracers": [("sheet", -66, 0, 0), ("sheet", 66, 0, 0), ("strip", 0, 0, 0)],
    "belt": [("strip", -100, 0, 0), ("strip", 100, 0, 0), ("rod", 205, 0, 90)],
    "ring": [("wire", 0, 0, 0)],
    "amulet": [("sheet", 0, 30, 0), ("wire", 0, -60, 90)],
}
MS = 0.5                                     # масштаб масок попадания


def point_in(p, poly, pad=0):
    """Точка внутри выпуклого многоугольника (с запасом pad пикселей)."""
    sign = None
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        ln = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        c = ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) / ln
        if abs(c) <= pad:
            continue
        s_ = c > 0
        if sign is None:
            sign = s_
        elif s_ != sign:
            return False
    return True


def edge_dist(p, poly):
    """Расстояние от точки внутри выпуклого многоугольника до его края (снаружи — 0)."""
    if not point_in(p, poly):
        return 0.0
    best = 1e9
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        ln = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        best = min(best, abs((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) / ln)
    return best


class ItemGame(TemperGame):
    """Изделие: выложить примитивы на пунктирный контур (тянуть мышью, R/колесо/ПКМ — повернуть; не прилипают —
    оценка по проценту попадания), склепать (места выбирает игрок), испытание на прочность по стыкам, затем
    термообработка (клещи и бочка, отпуск или отжиг)."""
    title = "Изделие"
    HINTS = dict(TemperGame.HINTS,
                 assemble="тяните детали на пунктир, R или колесо — повернуть, Enter — к клёпке",
                 join="клик по металлу — заклёпка (ещё клик — снять); ставьте в перекрытия деталей, Enter — испытание",
                 test="испытание на прочность — Enter: к термообработке")

    def __init__(self, item_kind, prims, tools, forge_level, seed=None):
        super().__init__(item_kind, prims, tools, forge_level, seed)
        self.after = self.phase
        self.phase = "assemble"
        self.slots = [dict(kind=k, dx=dx, dy=dy, ang=a) for k, dx, dy, a in LAYOUT[item_kind]]
        self.pieces = [dict(prim=p_, x=0.0, y=0.0, ang=0) for p_ in prims]
        self.held = None
        self.placed_once = False
        self.touched = False
        self.rivets = []
        self.rivet_max = 0
        self.strength = 0.0
        self.joint_res = []
        self.test_t = 0.0
        self._fit = (None, 0.0)
        self._target = None

    # ---------- геометрия ----------

    def table(self):
        r = self.rect
        return r.x + r.w * 0.42, r.y + r.h * 0.4

    def table_rect(self):
        cx, cy = self.table()
        return pygame.Rect(cx - 380, cy - 150, 760, 300)

    def tray_pos(self, i):
        r = self.rect
        n = len(self.pieces)
        return r.x + r.w * 0.42 + (i - (n - 1) / 2) * 250, r.bottom - 110

    def piece_size(self, pc):
        k = pc["prim"]["kind"]
        w, h = PIECE_PX[k]
        ln = pc["prim"].get("len") or FG.PRIMS[k]["len"]
        return w * ln / FG.PRIMS[k]["len"], h

    def piece_poly(self, pc, w=None):
        pw, h = self.piece_size(pc) if w is None else (w, PIECE_PX[pc["prim"]["kind"]][1])
        a = math.radians(pc["ang"])
        ca, sa = math.cos(a), math.sin(a)
        pts = [(-pw / 2, -h / 2), (pw / 2, -h / 2), (pw / 2, h / 2), (-pw / 2, h / 2)]
        x, y = pc["x"] + pc.get("ox", 0.0), pc["y"] + pc.get("oy", 0.0)
        return [(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in pts]

    def slot_poly(self, s_):
        cx, cy = self.table()
        ghost = dict(prim={"kind": s_["kind"]}, x=cx + s_["dx"], y=cy + s_["dy"], ang=s_["ang"])
        return self.piece_poly(ghost, PIECE_PX[s_["kind"]][0])

    def _mask(self, polys):
        r = self.rect
        s = pygame.Surface((int(r.w * MS) + 1, int(r.h * MS) + 1))
        s.fill((0, 0, 0))
        s.set_colorkey((0, 0, 0))
        for poly in polys:
            pygame.draw.polygon(s, (255, 255, 255), [((x - r.x) * MS, (y - r.y) * MS) for x, y in poly])
        return pygame.mask.from_surface(s)

    def fit(self):
        """Процент попадания: пересечение деталей с контуром к их объединению (как в ювелирке)."""
        key = (tuple(self.rect), tuple((round(p["x"], 1), round(p["y"], 1), p["ang"]) for p in self.pieces))
        if self._fit[0] == key:
            return self._fit[1]
        if self._target is None or self._target[0] != tuple(self.rect):
            self._target = (tuple(self.rect), self._mask([self.slot_poly(s_) for s_ in self.slots]))
        mt = self._target[1]
        mp = self._mask([self.piece_poly(p) for p in self.pieces])
        inter = mt.overlap_area(mp, (0, 0))
        union = mt.count() + mp.count() - inter
        v = round(inter / union, 3) if union else 0.0
        self._fit = (key, v)
        return v

    def joints(self, pieces=None):
        """Стыки: где детали перекрываются (у кольца — концы проволоки). need — сколько заклёпок держит стык."""
        pieces = self.pieces if pieces is None else pieces
        r = self.rect
        out = []
        if len(pieces) == 1:
            pc = pieces[0]
            w, h = self.piece_size(pc)
            band = self.piece_poly(dict(pc), w)[1:3]
            a = math.radians(pc["ang"])
            back = (-math.cos(a) * 18, -math.sin(a) * 18)
            poly = [band[0], band[1], (band[1][0] + back[0], band[1][1] + back[1]),
                    (band[0][0] + back[0], band[0][1] + back[1])]
            xs, ys = [p_[0] for p_ in poly], [p_[1] for p_ in poly]
            out.append(dict(a=0, b=0, polys=[poly], need=1,
                            box=pygame.Rect(min(xs), min(ys), max(1, max(xs) - min(xs)), max(1, max(ys) - min(ys)))))
            return out
        polys = [self.piece_poly(p) for p in pieces]
        masks = [self._mask([p_]) for p_ in polys]
        for i in range(len(pieces)):
            for j in range(i + 1, len(pieces)):
                if masks[i].overlap_area(masks[j], (0, 0)) < 12:
                    continue
                reg = masks[i].overlap_mask(masks[j], (0, 0))
                rects = reg.get_bounding_rects()
                if not rects:
                    continue
                bb = rects[0].unionall(rects[1:])
                box = pygame.Rect(r.x + bb.x / MS, r.y + bb.y / MS, bb.w / MS, bb.h / MS)
                out.append(dict(a=i, b=j, polys=[polys[i], polys[j]], box=box,
                                need=max(1, round(max(box.w, box.h) / 70))))
        return out

    def rivet_s(self, rv, jt):
        """Сила заклёпки в стыке: внутри перекрытия, не у края (край рвётся)."""
        e = min(edge_dist(rv, p_) for p_ in jt["polys"])
        if e <= 0:
            return None
        want = max(2.0, min(9.0, 0.3 * min(jt["box"].w, jt["box"].h)))
        return min(1.0, e / want)

    def test_strength(self):
        """Испытание: каждый стык тянут; держат заклёпки в перекрытии, у края — слабее, слишком тесно — слабее.
        Если какая-то деталь не связана с остальными — изделие разваливается."""
        for p in self.pieces:
            p["ox"] = p["oy"] = 0.0
        res = []
        for jt in self.joints():
            ss = sorted((s for s in ((self.rivet_s(rv, jt), rv) for rv in self.rivets) if s[0] is not None),
                        key=lambda s: -s[0])
            got, used = 0.0, []
            for s, rv in ss:
                if any(math.hypot(rv[0] - u[0], rv[1] - u[1]) < 14 for u in used):
                    s *= 0.4
                used.append(rv)
                got += s
            res.append(dict(jt, score=round(min(1.0, got / jt["need"]), 3)))
        par = list(range(len(self.pieces)))

        def root(i):
            while par[i] != i:
                i = par[i]
            return i
        for jr in res:
            if jr["score"] >= 0.3 and jr["a"] != jr["b"]:
                par[root(jr["a"])] = root(jr["b"])
        groups = {}
        for i in range(len(self.pieces)):
            groups.setdefault(root(i), []).append(i)
        main = max(groups.values(), key=len)
        self.loose = [i for i in range(len(self.pieces)) if i not in main]
        self.joint_res = res
        if not res:
            self.strength = 0.0
        else:
            self.strength = round(sum(j["score"] for j in res) / len(res) * (0.5 if self.loose else 1.0), 3)
        return self.strength

    def assembly_score(self):
        return 0.55 * self.fit() + 0.45 * self.strength

    def can_abort(self):
        return self.phase == "assemble" and not self.touched

    def finish(self):
        super().finish()
        if self.result:                                  # сборка входит в итог наравне с термообработкой
            self.result["assembly"] = round(self.assembly_score(), 3)
            self.result["fit"] = self.fit()
            self.result["strength"] = self.strength
            self.result["heat"] = round(self.result["heat"] * 0.6 + self.result["assembly"] * 0.4, 3)

    @property
    def quality(self):
        if self.phase in ("assemble", "join", "test"):
            return round(0.7 + 0.6 * self.assembly_score(), 3)
        return super().quality

    # ---------- ввод ----------

    def piece_at(self, pos):
        for pc in reversed(self.pieces):
            if point_in(pos, self.piece_poly(pc), pad=8):
                return pc
        return None

    def pointer(self, ev, rect):
        if self.phase == "assemble":
            if ev.type == pygame.MOUSEMOTION:
                self.mpos = ev.pos
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                pc = self.piece_at(ev.pos)
                if pc is not None:
                    self.held = pc
                    self.touched = True
                    self.pieces.remove(pc)
                    self.pieces.append(pc)                  # взятая — сверху
                    pc["grab"] = (pc["x"] - ev.pos[0], pc["y"] - ev.pos[1])
                    return True
            if ev.type == pygame.MOUSEMOTION and self.held is not None:
                self.held["x"] = ev.pos[0] + self.held["grab"][0]
                self.held["y"] = ev.pos[1] + self.held["grab"][1]
                return True
            if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.held is not None:
                self.held = None                            # не прилипает — лежит, где отпустили
                return True
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3 and self.held is not None:
                self.held["ang"] = (self.held["ang"] + 15) % 180
                return True
            return False
        if self.phase == "join" and ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            near = next((rv for rv in self.rivets if math.hypot(rv[0] - ev.pos[0], rv[1] - ev.pos[1]) < 9), None)
            if near is not None:
                self.rivets.remove(near)
                return True
            if self.piece_at(ev.pos) is None:
                self.say("Мимо металла", BAD, 0.6)
                return True
            if len(self.rivets) >= self.rivet_max:
                self.say("Заклёпки кончились — снимите лишнюю", BAD, 0.8)
                return True
            self.rivets.append((ev.pos[0], ev.pos[1]))
            return True
        if self.phase in ("assemble", "join", "test"):
            return False
        return super().pointer(ev, rect)

    def turn(self, d):
        pc = self.held or self.piece_at(self.mpos)
        if pc is not None:
            pc["ang"] = (pc["ang"] + d) % 180
            self.touched = True

    def wheel(self, dy):
        if self.phase == "assemble":
            self.turn(5 if dy > 0 else -5)

    def key(self, k):
        if self.phase == "assemble":
            if k == pygame.K_r:
                self.turn(15)
                return True
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                tr = self.table_rect()
                if all(tr.collidepoint(p["x"], p["y"]) for p in self.pieces):
                    self.start_join()
                else:
                    self.say("Положите все детали на стол", BAD)
                return True
            return False
        if self.phase == "join":
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.phase = "test"
                self.test_t = 0.0
                self.test_strength()
                return True
            return False
        if self.phase == "test":
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.test_t >= 1.2:
                for p in self.pieces:
                    p["ox"] = p["oy"] = 0.0
                self.phase = self.after
                self.say("Теперь — термообработка", GOLD)
            return True
        return super().key(k)

    def start_join(self):
        """Заклёпок — сколько держит идеальная сборка, и две про запас."""
        cx, cy = self.table()
        ideal = []
        for s_ in self.slots:
            ideal.append(dict(prim={"kind": s_["kind"]}, x=cx + s_["dx"], y=cy + s_["dy"], ang=s_["ang"]))
        self.rivet_max = sum(j["need"] for j in self.joints(ideal)) + 2
        self.phase = "join"
        self.held = None

    def update(self, dt):
        if self.phase in ("assemble", "join", "test"):
            FGame.update(self, dt)
            if not self.placed_once and self.rect.w > 100:
                for i, pc in enumerate(self.pieces):
                    pc["x"], pc["y"] = self.tray_pos(i)
                    pc["ang"] = (25, 160, 30, 150)[i % 4]               # лежат вкривь — повернуть самому
                self.placed_once = True
            if self.phase == "test":
                self.test_t += dt
                self.test_anim()
            return
        super().update(dt)

    def test_anim(self):
        """Нагрузка: слабые стыки разъезжаются, оторванные детали отлетают."""
        k = min(1.0, self.test_t / 1.2)
        cx = sum(p["x"] for p in self.pieces) / len(self.pieces)
        cy = sum(p["y"] for p in self.pieces) / len(self.pieces)
        for i, p in enumerate(self.pieces):
            dx, dy = p["x"] - cx, p["y"] - cy
            ln = math.hypot(dx, dy) or 1.0
            if i in getattr(self, "loose", []):
                d = 220 * k * k
            else:
                worst = min([j["score"] for j in self.joint_res if i in (j["a"], j["b"])] or [1.0])
                d = (1 - worst) * 16 * k + (1 - worst) * 3 * math.sin(self.test_t * 40)
            p["ox"], p["oy"] = dx / ln * d, dy / ln * d

    # ---------- рисунок ----------

    def draw(self, surf, rect):
        if self.phase not in ("assemble", "join", "test"):
            return super().draw(surf, rect)
        self.rect = rect
        pygame.draw.rect(surf, (22, 18, 16), rect, border_radius=10)
        name = ITEM_SHAPES.get(self.kind, self.kind).capitalize()
        sub = {"assemble": "сборка", "join": "клёпка", "test": "испытание"}[self.phase]
        T.text(surf, f"{name}: {sub}", (rect.x + 24, rect.y + 16), 24, GOLD, True)
        T.text(surf, {"assemble": "выложите детали по пунктиру — точность в процентах; детали не прилипают",
                      "join": "заклёпки — где детали перекрываются, не у самого края и не вплотную друг к другу",
                      "test": "стыки тянут: слабые разъезжаются"}[self.phase], (rect.x + 24, rect.y + 50), 14, DIM)
        table = self.table_rect()
        pygame.draw.rect(surf, (48, 40, 34), table, border_radius=14)
        pygame.draw.rect(surf, (90, 76, 60), table, 2, border_radius=14)
        for s_ in self.slots:                              # контур изделия — силуэт и пунктир
            AA.polygon(surf, (60, 51, 43), self.slot_poly(s_))
        for s_ in self.slots:
            poly = self.slot_poly(s_)
            for j in range(4):
                a, b = poly[j], poly[(j + 1) % 4]
                n = max(4, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 10))
                for t in range(0, n, 2):
                    AA.line(surf, (255, 210, 90), (a[0] + (b[0] - a[0]) * t / n, a[1] + (b[1] - a[1]) * t / n),
                            (a[0] + (b[0] - a[0]) * (t + 1) / n, a[1] + (b[1] - a[1]) * (t + 1) / n), 2)
        for pc in self.pieces:
            col = FG.ALLOYS[pc["prim"]["alloy"]]["color"]
            poly = self.piece_poly(pc)
            AA.polygon(surf, col, poly)
            AA.lines(surf, tuple(int(c * 0.55) for c in col), True, poly, 2)
            AA.line(surf, tuple(min(255, c + 50) for c in col), poly[0], poly[1], 2)
        tr = self.table_rect()
        for pc in self.pieces:                             # подписи у деталей вне стола
            if not tr.collidepoint(pc["x"], pc["y"]) and pc is not self.held:
                ln = pc["prim"].get("len") or FG.PRIMS[pc["prim"]["kind"]]["len"]
                lab = f"{FG.PRIMS[pc['prim']['kind']]['name']} · {FG.ALLOYS[pc['prim']['alloy']]['name']} · {ln} мм"
                T.text(surf, lab, (pc["x"], max(p_[1] for p_ in self.piece_poly(pc)) + 8), 13, DIM, center=True)
        weak = {}
        if self.phase == "test":
            for jr in self.joint_res:
                for rv in self.rivets:
                    if self.rivet_s(rv, jr) is not None:
                        weak[rv] = min(weak.get(rv, 1.0), jr["score"])
        for rv in self.rivets:
            s = weak.get(rv, 1.0)
            col = (200, 190, 175) if s >= 0.8 else (240, 190, 110) if s >= 0.5 else (240, 110, 90)
            AA.circle(surf, (90, 80, 72), rv, 6)
            AA.circle(surf, col, (rv[0] - 1.5, rv[1] - 1.5), 3.5)
        x = rect.right - 300
        T.text(surf, f"попадание {self.fit() * 100:.0f}%", (x, rect.y + 18), 18, T.TEXT, True)
        if self.phase in ("join", "test"):
            T.text(surf, f"заклёпок: {len(self.rivets)} / {self.rivet_max}", (x, rect.y + 44), 15, T.TEXT, True)
        if self.phase == "test" and self.test_t >= 1.2:
            col = OK if self.strength >= 0.8 else GOLD if self.strength >= 0.5 else BAD
            T.text(surf, f"прочность {self.strength * 100:.0f}%" + (" · деталь оторвалась" if self.loose else ""),
                   (x, rect.y + 68), 16, col, True)
            T.text(surf, "Enter — к термообработке", (table.centerx, table.bottom + 20), 15, T.TEXT, True, center=True)
        self.draw_flash(surf, rect)
