"""Этапы ковки как игры (экран — MiniGameScene): плавка, пакет (тетрис), сварка и складывание, разделка клином,
ковка по контуру с закалкой. Каждая игра в конце заполняет self.result — его забирает Горн мастера
(game/tavern_rooms.py → SmithOverlay) и передаёт в профиль (sim/expedition.py, sim/smithing.py)."""
import math

import pygame

from game import metal_view as MV
from game.workshop_games import Game, quality
from sim import smithing as SM
from ui import theme as T

DIM = T.TEXT_DIM


def heat_color(t):
    """Цвет каления: тёмный металл → вишнёвый → оранжевый → жёлтый → белый (°C)."""
    stops = ((500, (70, 64, 66)), (700, (120, 30, 22)), (850, (200, 50, 25)), (1000, (240, 110, 30)),
             (1150, (255, 180, 60)), (1300, (255, 235, 150)), (1450, (255, 250, 235)))
    if t <= stops[0][0]:
        return stops[0][1]
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if t <= b:
            return T.mix(ca, cb, (t - a) / (b - a))
    return stops[-1][1]


def metal_col(xd, m):
    return tuple(SM.cfg(xd)["metals"][m]["color"]) if m else (40, 34, 30)


def bar(surf, x, y, w, label, v, band=None, col=(240, 160, 80), lo=0.0, hi=1.0, txt=None):
    """Шкала с подписью и окном нужного значения."""
    T.text(surf, label, (x, y), 13, DIM)
    r = pygame.Rect(x, y + 18, w, 14)
    pygame.draw.rect(surf, (36, 30, 26), r, border_radius=5)
    if band:
        a, b = (band[0] - lo) / (hi - lo), (band[1] - lo) / (hi - lo)
        pygame.draw.rect(surf, (60, 120, 70), (r.x + int(r.w * a), r.y, int(r.w * (b - a)), r.h), border_radius=4)
    k = max(0.0, min(1.0, (v - lo) / (hi - lo)))
    pygame.draw.rect(surf, col, (r.x, r.y + 3, int(r.w * k), r.h - 6), border_radius=3)
    pygame.draw.line(surf, (255, 255, 255), (r.x + int(r.w * k), r.y - 2), (r.x + int(r.w * k), r.bottom + 2), 2)
    pygame.draw.rect(surf, (90, 70, 46), r, 1, border_radius=5)
    if txt:
        T.text(surf, txt, (r.right + 8, r.y - 1), 13, T.TEXT)


def badges(surf, x, y, items):
    from game.jewel_view import badge
    for k, label in items:
        x = badge(surf, k, label, x, y)


def bench(surf, rect, iid="ws_bench_forge"):
    """Фон: верстак кузнеца (лист 36), притушенный."""
    from ui import illustrations as IL
    import os
    if os.path.exists(os.path.join(IL.DIR, "hd", f"{iid}.png")):
        img = IL.get(iid, "tavern", (rect.w, rect.w * 2 // 3), hd=True)
        surf.blit(img, (rect.x, rect.bottom - img.get_height()))
        sh = pygame.Surface(rect.size, pygame.SRCALPHA)
        sh.fill((6, 4, 3, 150))
        surf.blit(sh, rect)
    else:
        pygame.draw.rect(surf, (26, 20, 16), rect)


def billet_props_of(xd, b):
    return SM.billet_props(xd, b)


def gauge(surf, x, y, w, label, v, lo_word, hi_word, col, effect):
    """Шкала свойства: подпись и значение, полоса с делениями, слова по краям, что даёт вещи."""
    T.text(surf, label, (x, y), 14, T.TEXT, True)
    T.text(surf, f"{v * 100:.0f}%", (x + w - T.font(14, True).size(f"{v * 100:.0f}%")[0], y), 14, col, True)
    r = pygame.Rect(x, y + 20, w, 12)
    pygame.draw.rect(surf, (30, 26, 24), r, border_radius=6)
    pygame.draw.rect(surf, col, (r.x, r.y, int(r.w * max(0.0, min(1.0, v))), r.h), border_radius=6)
    for k in range(1, 4):
        pygame.draw.line(surf, (60, 52, 46), (r.x + r.w * k // 4, r.y + 2), (r.x + r.w * k // 4, r.bottom - 3))
    pygame.draw.rect(surf, (90, 70, 46), r, 1, border_radius=6)
    T.text(surf, lo_word, (x, y + 34), 11, DIM)
    T.text(surf, hi_word, (x + w - T.font(11).size(hi_word)[0], y + 34), 11, DIM)
    T.text(surf, effect, (x + w // 2, y + 34), 11, (150, 230, 150), center=True)


def props_panel(surf, xd, x, y, w, pr, mass, title="Металл"):
    """Свойства металла понятно: масса, твёрдость (урон), вязкость (здоровье), дамаск (крит)."""
    from sim import artifacts as AR
    mods = {m.get("stat") or m.get("extra"): m.get("mult", m.get("add")) for m in AR.metal_mods(pr)}
    T.text(surf, title, (x, y), 15, (255, 210, 120), True)
    T.text(surf, f"{mass:.0f} г", (x + w - T.font(18, True).size(f"{mass:.0f} г")[0], y - 2), 18, T.TEXT, True)
    gauge(surf, x, y + 24, w, "Твёрдость", pr["hard"], "мягкий", "твёрдый", (150, 180, 230),
          f"урон {(mods.get('atk_damage', 1) - 1) * 100:+.1f}%")
    gauge(surf, x, y + 74, w, "Вязкость", pr["tough"], "хрупкий", "вязкий", (220, 170, 110),
          f"здоровье {(mods.get('hp', 1) - 1) * 100:+.1f}%")
    dam = f"Дамаск: {pr['layers']} слоёв, узор {pr['pattern'] * 100:.0f}%"
    if mods.get("crit"):
        dam += f" → крит +{mods['crit'] * 100:.1f}%"
    T.text(surf, dam, (x, y + 124), 12, T.TEXT if pr["pattern"] else DIM)


def mini_props(surf, x, y, w, pr):
    """Короткие полосы твёрдости и вязкости (списки)."""
    for i, (v, col) in enumerate(((pr["hard"], (150, 180, 230)), (pr["tough"], (220, 170, 110)))):
        r = pygame.Rect(x, y + i * 9, w, 6)
        pygame.draw.rect(surf, (30, 26, 24), r, border_radius=3)
        pygame.draw.rect(surf, col, (r.x, r.y, int(r.w * v), r.h), border_radius=3)


SWING = 0.4                       # взмах: замах-удар 0.12 с, возврат — остальное


def swing_angle(timer):
    """Угол руки с молотом (0 — удар, 1 — замах): быстро вниз, медленнее назад, в покое — приподнят."""
    if timer <= 0:
        return 0.55
    t = SWING - timer
    if t < 0.12:
        k = t / 0.12
        return 1.0 - k * k                          # разгон к удару
    k = (t - 0.12) / (SWING - 0.12)
    return 0.55 * (1 - (1 - k) ** 2)                # отскок и подъём в покой


def draw_swing(surf, name, hit, length, timer, fallback_col=(90, 92, 100)):
    """Молот бьёт по дуге: кисть — над и справа от точки удара, головка описывает дугу и приходит в hit."""
    a = swing_angle(timer)
    spark_at = hit
    hit = (hit[0], hit[1] - length * 0.13)          # центр головки — над поверхностью: боёк ложится на металл
    pivot = (hit[0] + length * 0.95, hit[1] - length * 0.25)
    th = math.radians(-12 + 128 * a)                # 0 — головка у наковальни, 1 — головка над плечом
    base = math.atan2(hit[1] - pivot[1], hit[0] - pivot[0])
    ang = base + th                                 # по часовой (экранные оси): от наковальни вверх, над плечо
    head = (pivot[0] + math.cos(ang) * length, pivot[1] + math.sin(ang) * length)
    img = MV.prop(name, None, int(length * 1.08))
    vx, vy = head[0] - pivot[0], head[1] - pivot[1]
    if img is not None:
        rot = pygame.transform.rotate(img, math.degrees(math.atan2(-vx, -vy)))
        mid = ((pivot[0] + head[0]) / 2, (pivot[1] + head[1]) / 2)
        surf.blit(rot, (mid[0] - rot.get_width() / 2, mid[1] - rot.get_height() / 2))
    else:
        pygame.draw.line(surf, (110, 80, 50), pivot, head, 8)
        pygame.draw.circle(surf, fallback_col, (int(head[0]), int(head[1])), 16)
    if timer > 0 and SWING - timer < 0.16:          # искры в момент удара
        for k in range(12):
            q = k * 0.53
            pygame.draw.circle(surf, (255, 210, 120), (int(spark_at[0] + math.cos(q) * 50),
                                                       int(spark_at[1] - abs(math.sin(q)) * 34)), 2)


def draw_piece(surf, xd, p, x, y, cell):
    """Кусок металла: клетки — образец металла (цвет, блеск), тёмная кромка."""
    img = MV.swatch(xd, p["metal"], cell - 1, cell - 1, seed=len(p["cells"]))
    for cx, cy in p["cells"]:
        r = pygame.Rect(x + cx * cell, y + cy * cell, cell - 1, cell - 1)
        surf.blit(img, r)
        pygame.draw.rect(surf, (18, 16, 16), r, 1)


class SmithGame(Game):
    area_size = (1120, 520)

    def __init__(self, seed=None, xd=None, tools=()):
        super().__init__(seed)
        self.xd = xd
        self.tools = set(tools)
        self.result = None
        self.mpos = (-1, -1)

    def cool_k(self):
        return 0.6 if "bellows" in self.tools else 1.0

    def stop(self):
        self.done = True

    def mouse(self, pos, rect):
        self.mpos = pos

    def keys(self):
        try:
            return pygame.key.get_pressed()
        except pygame.error:
            return None


# ---------- 1. плавка ----------

class SmeltGame(SmithGame):
    """Плавка руды в тигле: держи жар в окне (Пробел — мехи), уголь (C) — углерод: мало — железо, больше — сталь,
    слишком много — хрупкий чугун. Шлак всплывает — снимай кликом. 20 секунд."""
    title = "Плавка"
    hint = "Пробел — мехи (жар), C — уголь (углерод), клик по шлаку — снять"

    def __init__(self, seed=None, xd=None, tools=()):
        super().__init__(seed, xd, tools)
        c = SM.cfg(xd)["smelt"]
        self.dur = c["time"]
        self.temp = 1200.0
        self.carbon = 0.1
        self.hold = False
        self.in_band = 0.0
        self.slag = []                         # [x, y, r]
        self.slag_total = 0
        self.slag_off = 0
        self.band = (1450, 1560)

    def press(self):
        self.hold = True

    def release(self):
        self.hold = False

    def key(self, k):
        if self.done:
            return False
        if k == pygame.K_c:
            self.carbon = min(1.0, self.carbon + 0.08)
            self.temp -= 25
            self.flash.append(["+ уголь", (200, 200, 200), 0.5])
            return True
        return False

    def pointer(self, ev, rect):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and not self.done:
            for s_ in self.slag:
                if math.dist(ev.pos, (rect.x + s_[0], rect.y + s_[1])) <= s_[2] + 6:
                    self.slag.remove(s_)
                    self.slag_off += 1
                    return True
        return False

    def update(self, dt):
        super().update(dt)
        if self.done:
            return
        self.temp += (240 if self.hold else -110 * self.cool_k()) * dt
        self.temp = max(900.0, min(1700.0, self.temp))
        if self.band[0] <= self.temp <= self.band[1]:
            self.in_band += dt
        if self.temp > 1350 and self.rng.random() < dt * 0.9:
            self.slag.append([self.rng.uniform(300, 520), self.rng.uniform(250, 300), self.rng.uniform(8, 14)])
            self.slag_total += 1
        if self.t >= self.dur:
            self.finish()

    def finish(self):
        self.done = True
        self.result = {"carbon": self.carbon, "heat_ok": self.in_band / self.dur,
                       "slag": self.slag_off / max(1, self.slag_total)}

    def stop(self):
        if not self.done:
            self.finish()

    @property
    def score(self):
        return 0.6 * min(1.0, self.in_band / self.dur) + 0.4 * self.slag_off / max(1, self.slag_total)

    def metal_now(self):
        c = SM.cfg(self.xd)["smelt"]
        return "чугун (хрупкий)" if self.carbon > c["cast_carbon"] else "сталь" if self.carbon >= c["steel_carbon"] \
            else "железо"

    def draw(self, surf, rect):
        bench(surf, rect)
        cx, cy = rect.x + 410, rect.y + 290
        melt = heat_color(self.temp)
        cimg = MV.prop("frg_crucible", 320)
        if cimg is not None:
            pygame.draw.ellipse(surf, melt, (cx - 130, cy - 92, 260, 46))
            surf.blit(cimg, (cx - cimg.get_width() // 2, cy - 90))
        else:
            pygame.draw.polygon(surf, (70, 60, 56), [(cx - 150, cy - 70), (cx + 150, cy - 70), (cx + 110, cy + 120),
                                                    (cx - 110, cy + 120)])
            pygame.draw.ellipse(surf, melt, (cx - 140, cy - 90, 280, 50))
        for s_ in self.slag:
            pygame.draw.circle(surf, (60, 50, 44), (int(rect.x + s_[0]), int(rect.y + s_[1])), int(s_[2]))
            pygame.draw.circle(surf, (110, 96, 80), (int(rect.x + s_[0]), int(rect.y + s_[1])), int(s_[2]), 2)
        for k in range(6 if self.hold else 2):                 # искры над тиглем
            a = self.t * 7 + k
            pygame.draw.circle(surf, (255, 200, 100), (int(cx + math.sin(a * 3.1) * 90),
                                                       int(cy - 110 - (a * 40) % 70)), 2)
        bimg = MV.prop("frg_bellows", 150)
        if bimg is not None:
            b2 = pygame.transform.scale(bimg, (bimg.get_width(), int(bimg.get_height() * (0.75 if self.hold else 1.0))))
            surf.blit(b2, (cx - 330, cy + 60 - b2.get_height()))
        elif self.hold:
            pygame.draw.polygon(surf, (110, 80, 50), [(cx - 260, cy + 20), (cx - 170, cy - 10), (cx - 170, cy + 50)])
        x = rect.right - 330
        T.text(surf, "Плавка руды", (x, rect.y + 20), 22, (255, 210, 120), True)
        bar(surf, x, rect.y + 60, 280, "Жар тигля (окно — плавка без шлака)", self.temp, self.band, heat_color(self.temp),
            900, 1700, f"{self.temp:.0f}°")
        c = SM.cfg(self.xd)["smelt"]
        bar(surf, x, rect.y + 110, 280, "Углерод: железо · сталь · чугун", self.carbon,
            (c["steel_carbon"], c["cast_carbon"]), (90, 90, 96), 0, 1, self.metal_now())
        T.text(surf, f"Шлак снят: {self.slag_off}/{max(self.slag_total, 0)}", (x, rect.y + 162), 15, T.TEXT)
        T.text(surf, f"Время: {max(0.0, self.dur - self.t):.0f} с", (x, rect.y + 186), 17, T.TEXT, True)
        tips = ("Держи жар в зелёном окне — металл чище.", "Уголь: до зелёного окна — железо (вязкое),",
                "в окне — сталь (твёрдая), выше — чугун.", "Шлак всплывает — снимай кликом.")
        for i, ln in enumerate(tips):
            T.text(surf, ln, (x, rect.y + 226 + i * 18), 13, DIM)
        badges(surf, x, rect.bottom - 40, (("Пробел", "мехи"), ("C", "уголь"), ("ЛКМ", "шлак")))
        self.draw_flash(surf, rect)


# ---------- 2. пакет ----------

class StackGame(SmithGame):
    """Пакет: выкладывай куски на рамку (тетрис). Строки — слои: чередуй твёрдые и мягкие — будет дамаск.
    Пустые клетки — поры. ЛКМ — взять/положить, R или ПКМ — повернуть, Enter — собрать пакет."""
    title = "Пакет"
    hint = "ЛКМ — взять и положить кусок, R / ПКМ — повернуть, клик по куску на рамке — снять, Enter — собрать"
    CELL = 66

    def __init__(self, seed=None, xd=None, tools=(), pieces=(), frame=(4, 3)):
        super().__init__(seed, xd, tools)
        self.w, self.h = frame
        self.grid = [[None] * self.w for _ in range(self.h)]
        self.owner = [[None] * self.w for _ in range(self.h)]
        self.free = [dict(p, cells=[list(c) for c in p["cells"]]) for p in pieces]
        self.placed = []                       # [(кусок, ox, oy)]
        self.held = None
        self.scroll = 0
        self.inv_rects = []

    def origin(self, rect):
        return (rect.x + 60, rect.y + 120)

    def cell_at(self, pos, rect, cells=None):
        ox, oy = self.origin(rect)
        gx = (pos[0] - ox) // self.CELL
        gy = (pos[1] - oy) // self.CELL
        return int(gx), int(gy)

    def key(self, k):
        if self.done:
            return False
        if k == pygame.K_r and self.held:
            self.held["cells"] = SM.rotate(self.held["cells"])
            return True
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.finish()
            return True
        return False

    def press(self):
        pass

    def pointer(self, ev, rect):
        if self.done:
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
            if self.held:
                self.held["cells"] = SM.rotate(self.held["cells"])
            return True
        if ev.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, min(max(0, len(self.free) - 5), self.scroll - ev.y))
            return True
        if ev.type != pygame.MOUSEBUTTONDOWN or ev.button != 1:
            return False
        if self.held:
            gx, gy = self.cell_at(ev.pos, rect)
            if SM.place_ok(self.grid, self.held["cells"], gx, gy):
                for x, y in self.held["cells"]:
                    self.grid[gy + y][gx + x] = self.held["metal"]
                    self.owner[gy + y][gx + x] = self.held["uid"]
                self.placed.append((self.held, gx, gy))
                self.held = None
                return True
            for r_, p in self.inv_rects:              # вернуть на полку
                if r_.collidepoint(ev.pos):
                    self.free.append(self.held)
                    self.held = None
                    return True
            return True
        for r_, p in self.inv_rects:
            if r_.collidepoint(ev.pos):
                self.free.remove(p)
                self.held = p
                return True
        gx, gy = self.cell_at(ev.pos, rect)
        if 0 <= gx < self.w and 0 <= gy < self.h and self.owner[gy][gx]:
            uid = self.owner[gy][gx]
            p, ox, oy = next(x for x in self.placed if x[0]["uid"] == uid)
            for x, y in p["cells"]:
                self.grid[oy + y][ox + x] = None
                self.owner[oy + y][ox + x] = None
            self.placed = [x for x in self.placed if x[0]["uid"] != uid]
            self.held = p
            return True
        return False

    def finish(self):
        if not self.placed:
            self.flash.append(["Положите хотя бы один кусок", (240, 170, 110), 1.0])
            return
        self.done = True
        self.result = {"grid": self.grid, "used": [p["uid"] for p, _, _ in self.placed]}

    def stop(self):
        self.done = True
        self.result = None

    def preview(self):
        b = SM.billet_from(self.xd, "x", self.grid, [p for p, _, _ in self.placed] or [{"purity": 0, "cells": []}])
        return b, SM.billet_props(self.xd, b)

    @property
    def score(self):
        if not self.placed:
            return 0.0
        b, pr = self.preview()
        return 0.5 * b["purity"] + 0.5 * pr["pattern"]

    def draw_piece(self, surf, p, x, y, cell, alpha=255):
        draw_piece(surf, self.xd, p, x, y, cell)

    def draw(self, surf, rect):
        bench(surf, rect)
        ox, oy = self.origin(rect)
        C = self.CELL
        T.text(surf, f"Рамка пакета {self.w}×{self.h} ({self.w * self.h * SM.cfg(self.xd)['cell_g']} г) — строки = слои",
               (ox, rect.y + 20), 20, (255, 210, 120), True)
        T.text(surf, "Чередуйте твёрдые (сталь) и мягкие (железо) слои — выйдет дамаск. Пустые клетки — просто легче.",
               (ox, rect.y + 50), 14, DIM)
        frame = pygame.Rect(ox - 6, oy - 6, self.w * C + 10, self.h * C + 10)
        pygame.draw.rect(surf, (40, 34, 30), frame, border_radius=6)
        pygame.draw.rect(surf, (150, 120, 80), frame, 3, border_radius=6)
        for y in range(self.h):
            for x in range(self.w):
                r = pygame.Rect(ox + x * C, oy + y * C, C - 2, C - 2)
                m = self.grid[y][x]
                if m:
                    surf.blit(MV.swatch(self.xd, m, C - 2, C - 2, seed=x * 7 + y), r)
                    pygame.draw.rect(surf, (20, 18, 18), r, 1)
                else:
                    pygame.draw.rect(surf, (28, 24, 22), r, 1, border_radius=4)
            T.text(surf, f"слой {y + 1}", (frame.right + 8, oy + y * C + C // 2 - 8), 12, DIM)
        if self.held:                                 # кусок в руке: тень на рамке
            gx, gy = self.cell_at(self.mpos, rect)
            ok = SM.place_ok(self.grid, self.held["cells"], gx, gy)
            if 0 <= gx < self.w + 1 and 0 <= gy < self.h + 1:
                for x, y in self.held["cells"]:
                    r = pygame.Rect(ox + (gx + x) * C, oy + (gy + y) * C, C - 2, C - 2)
                    pygame.draw.rect(surf, (120, 220, 130) if ok else (230, 90, 80), r, 3, border_radius=4)
            self.draw_piece(surf, self.held, self.mpos[0] - C // 4, self.mpos[1] - C // 4, C // 2)
        # полка кусков
        sx = ox + self.w * C + 70
        T.text(surf, f"Куски: {len(self.free)}", (sx, rect.y + 110), 16, T.TEXT, True)
        self.inv_rects = []
        y = rect.y + 136
        for p in self.free[self.scroll:self.scroll + 5]:
            r = pygame.Rect(sx, y, 300, 66)
            hot = r.collidepoint(self.mpos)
            pygame.draw.rect(surf, (54, 40, 26) if hot else (32, 24, 17), r, border_radius=8)
            pygame.draw.rect(surf, metal_col(self.xd, p["metal"]), r, 1, border_radius=8)
            self.draw_piece(surf, p, r.x + 8, r.y + 8, 14)
            m = SM.cfg(self.xd)["metals"][p["metal"]]
            T.text(surf, f"{m['name']} · {SM.piece_mass(self.xd, p)} г", (r.x + 80, r.y + 10), 15, T.TEXT, True)
            T.text(surf, f"чистота {p['purity'] * 100:.0f}% · тв. {m['hard'] * 100:.0f}% · вяз. {m['tough'] * 100:.0f}%",
                   (r.x + 80, r.y + 34), 12, DIM)
            self.inv_rects.append((r, p))
            y += 72
        if len(self.free) > 5:
            T.text(surf, f"колесо — ещё ({self.scroll + 1}–{min(len(self.free), self.scroll + 5)} из {len(self.free)})",
                   (sx, y), 12, DIM)
        # прогноз
        x = rect.right - 300
        if self.placed:
            b, pr = self.preview()
            props_panel(surf, self.xd, x, rect.y + 140, 270, pr, b["mass"], "Будущий слиток")
            T.text(surf, f"Чистота {b['purity'] * 100:.0f}% · слоёв {b['layers']}", (x, rect.y + 290), 13, DIM)
            T.text(surf, "Пустые клетки не страшны: слиток", (x, rect.y + 310), 12, DIM)
            T.text(surf, "сварится цельным, просто легче.", (x, rect.y + 326), 12, DIM)
        badges(surf, x, rect.bottom - 70, (("ЛКМ", "взять"), ("R", "повернуть")))
        badges(surf, x, rect.bottom - 40, (("Enter", "собрать пакет"),))
        self.draw_flash(surf, rect)


# ---------- 3. сварка и складывание ----------

class WeldGame(SmithGame):
    """Кузнечная сварка: Пробел (держать) — пакет в горне, отпустил — на наковальне; ЛКМ — удар. Удары в
    сварочном жару сращивают слои; холодный — трещит, перегрев — выжигает. F — сложить (слоёв вдвое больше),
    T — скрутка (урок), Enter — готово."""
    title = "Сварка и складывание"
    hint = "Пробел (держать) — в горн, ЛКМ — удар молотом, F — сложить пакет, T — скрутка, Enter — готово"

    def __init__(self, seed=None, xd=None, tools=(), billet=None, fold_max=2):
        super().__init__(seed, xd, tools)
        self.b = dict(billet, grid=[list(r) for r in billet["grid"]])
        self.c = SM.cfg(xd)["weld"]
        self.fold_max = fold_max
        self.temp = 800.0
        self.in_forge = False
        self.hits = 0
        self.cracks = 0
        self.anim = 0.0

    def press(self):
        self.in_forge = True

    def release(self):
        self.in_forge = False

    def strike(self):
        if self.in_forge or self.done:
            return
        self.anim = SWING
        lo, hi = self.c["weld_t"]
        self.temp -= 22
        if self.temp < self.c["cold_t"]:
            self.cracks += 1
            self.b["weld"] = max(0.0, self.b["weld"] - 0.06)
            self.flash.append(["Холодный — трещина!", (240, 110, 100), 0.8])
        elif lo <= self.temp:
            self.b["weld"] = min(1.0, self.b["weld"] + 1.0 / self.c["strikes"])
            self.flash.append(["Сваривается", (255, 220, 140), 0.4])
        else:
            self.b["weld"] = min(1.0, self.b["weld"] + 0.3 / self.c["strikes"])

    def pointer(self, ev, rect):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and not self.done:
            self.strike()
            return True
        return False

    def key(self, k):
        if self.done:
            return False
        if k == pygame.K_f:
            if self.b["weld"] < 0.8:
                self.flash.append(["Сначала сварите слои", (240, 200, 120), 1.0])
            elif self.b["folds"] >= self.fold_max:
                self.flash.append(["Больше не сложить (нужны клещи длиннее)", (240, 200, 120), 1.2])
            else:
                SM.fold(self.xd, self.b)
                self.b["weld"] = 0.35
                self.flash.append([f"Сложено: {SM.billet_props(self.xd, self.b)['layers']} слоёв", (150, 230, 150), 1.2])
            return True
        if k == pygame.K_t:
            if "twist" not in self.tools:
                self.flash.append(["Скрутке учат бродячие кузнецы", (240, 200, 120), 1.0])
            elif self.b["weld"] < 0.8 or self.b.get("twist", 0) >= 2:
                self.flash.append(["Сначала сварите; больше двух скруток нельзя", (240, 200, 120), 1.0])
            else:
                self.b["twist"] = self.b.get("twist", 0) + 1
                self.b["weld"] = 0.6
                self.flash.append(["Скрутка: узор ярче", (150, 230, 150), 1.0])
            return True
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.finish()
            return True
        return False

    def finish(self):
        self.done = True
        self.b["welded"] = True
        self.result = self.b

    def stop(self):
        self.finish()

    def update(self, dt):
        super().update(dt)
        self.anim = max(0.0, self.anim - dt)
        if self.done:
            return
        if self.in_forge:
            self.temp = min(1420.0, self.temp + 260 * dt)
            if self.temp > self.c["burn_t"]:
                self.b["burn"] = min(0.5, self.b["burn"] + 0.06 * dt)
                self.b["mass"] = int(self.b["mass"] * (1 - 0.01 * dt))
        else:
            self.temp = max(400.0, self.temp - 70 * self.cool_k() * dt)

    @property
    def score(self):
        return SM.prep_quality(self.xd, self.b)

    def draw(self, surf, rect):
        bench(surf, rect)
        pr = SM.billet_props(self.xd, self.b)
        forge = pygame.Rect(rect.x + 40, rect.y + 150, 220, 200)
        fimg = MV.prop("frg_forge", 240)
        if fimg is not None:
            surf.blit(fimg, (forge.centerx - fimg.get_width() // 2, forge.bottom - fimg.get_height()))
            mouth = pygame.Rect(forge.x + 30, forge.bottom - fimg.get_height() * 55 // 100, 160, 70)
        else:
            pygame.draw.rect(surf, (70, 60, 56), forge, border_radius=12)
            mouth = pygame.Rect(forge.x + 30, forge.y + 60, 160, 90)
            pygame.draw.rect(surf, (255, 130, 40), mouth, border_radius=10)
            pygame.draw.rect(surf, (255, 200, 90), mouth.inflate(-30, -30), border_radius=8)
        T.text(surf, "горн", (forge.centerx, forge.bottom + 6), 13, DIM, center=True)
        anvil = pygame.Rect(rect.x + 380, rect.y + 330, 300, 60)
        aimg = MV.prop("frg_anvil", 280)
        if aimg is not None:
            surf.blit(aimg, (anvil.centerx - aimg.get_width() // 2, anvil.y - 6))
        else:
            pygame.draw.rect(surf, (70, 72, 80), anvil, border_radius=6)
            pygame.draw.polygon(surf, (70, 72, 80), [(anvil.x - 50, anvil.y), (anvil.x, anvil.y), (anvil.x, anvil.y + 30)])
            pygame.draw.rect(surf, (50, 52, 58), (anvil.centerx - 40, anvil.bottom, 80, 60))
        bar_r = pygame.Rect(mouth.x + 10, mouth.centery - 22, 150, 44) if self.in_forge else \
            pygame.Rect(anvil.x + 30, anvil.y - 46, 240, 46)
        img = MV.bar(self.xd, self.b["grid"], self.b.get("folds", 0), self.b.get("twist", 0), bar_r.w, bar_r.h,
                     self.temp, seed=3)
        surf.blit(img, bar_r)
        hot = heat_color(self.temp)
        pygame.draw.rect(surf, (30, 24, 20), bar_r, 2)
        if not self.in_forge:                        # молот: взмах по дуге
            draw_swing(surf, "frg_hammer_sledge", (bar_r.centerx, bar_r.y + 4), 150, self.anim)
        x = rect.right - 330
        T.text(surf, "Сварка пакета", (x, rect.y + 20), 22, (255, 210, 120), True)
        if not self.in_forge:                         # срез пакета крупно: видно, какие металлы внутри
            cut = MV.bar(self.xd, self.b["grid"], self.b.get("folds", 0), self.b.get("twist", 0), 260, 80, 20,
                         seed=3)
            surf.blit(cut, (rect.x + 40, rect.y + 24))                    # в углу, над горном
            pygame.draw.rect(surf, (20, 16, 14), (rect.x + 40, rect.y + 24, 260, 80), 2)
            T.text(surf, "узор слоёв (после травления)", (rect.x + 170, rect.y + 108), 12, DIM, center=True)
        bar(surf, x, rect.y + 60, 280, "Жар (зелёное — сварочный)", self.temp, self.c["weld_t"], hot, 400, 1420,
            f"{self.temp:.0f}°")
        bar(surf, x, rect.y + 110, 280, "Сварка слоёв", self.b["weld"], None, (150, 220, 150), 0, 1,
            f"{self.b['weld'] * 100:.0f}%")
        props_panel(surf, self.xd, x, rect.y + 156, 290, pr, self.b["mass"], "Слиток")
        T.text(surf, f"Сложено {self.b['folds']}/{self.fold_max}" + (f" · скрутка ×{self.b['twist']}"
                                                                     if self.b.get("twist") else "")
               + f" · чистота {self.b['purity'] * 100:.0f}%", (x, rect.y + 300), 12, T.TEXT)
        T.text(surf, f"Выгорание {self.b['burn'] * 100:.0f}% · трещин {self.cracks}", (x, rect.y + 318), 12,
               (240, 150, 110) if self.b["burn"] or self.cracks else DIM)
        tips = ("Сварочный жар — светло-жёлтый; перегрев выжигает.", "Складывание: слоёв ×2, чище, −5% массы.")
        for i, ln in enumerate(tips):
            T.text(surf, ln, (x, rect.y + 340 + i * 16), 11, DIM)
        badges(surf, x, rect.bottom - 70, (("Пробел", "в горн"), ("ЛКМ", "удар")))
        badges(surf, x, rect.bottom - 40, (("F", "сложить"), ("T", "скрутка"), ("Enter", "готово")))
        self.draw_flash(surf, rect)


# ---------- 4. разделка ----------

class CutGame(SmithGame):
    """Разделка: брусок на наковальне, клин — за мышью. ЛКМ — отсечь от левого края кусок любой массы на глаз;
    Enter — закончить (остаток — последней частью). Пробел (держать) — подогреть: холодный режется хуже.
    Масса части видна только после удара."""
    title = "Разделка"
    hint = "Мышь — клин, ЛКМ — отсечь, Enter — закончить (остаток — часть), Пробел — подогреть"
    MIN_G = 20

    def __init__(self, seed=None, xd=None, tools=(), billet=None, targets=()):
        super().__init__(seed, xd, tools)
        self.b = billet
        self.left = float(billet["mass"])
        self.cuts = []                              # массы отсечённых частей
        self.temp = 1100.0
        self.heating = False
        self.cold = False
        self.anim = 0.0
        self.px_per_g = min(1.6, 560.0 / max(1.0, self.left))

    def press(self):
        self.heating = True

    def release(self):
        self.heating = False

    def bar_rect(self, rect):
        w = int(self.left * self.px_per_g)
        return pygame.Rect(rect.x + 100, rect.y + 270, max(2, w), 46)

    def pointer(self, ev, rect):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and not self.done and not self.heating:
            br = self.bar_rect(rect)
            if br.inflate(40, 160).collidepoint(ev.pos):
                x = max(br.x + 2, min(br.right - 2, ev.pos[0]))
                self.cut((x - br.x) / self.px_per_g)
            return True
        return False

    def key(self, k):
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER) and not self.done:
            self.finish()
            return True
        return False

    def cut(self, mass):
        mass = max(1.0, min(self.left, mass + self.rng.uniform(-2, 2)))
        if mass < self.MIN_G or self.left - mass < self.MIN_G:
            self.flash.append(["Слишком маленький кусок", (240, 170, 110), 0.9])
            return
        if self.temp < 800:
            self.cold = True
            self.flash.append(["Холодный — рвётся неровно", (240, 120, 100), 0.9])
        self.cuts.append(mass)
        self.left -= mass
        self.temp -= 60
        self.anim = SWING
        self.flash.append([f"Отсечено: {mass:.0f} г", (150, 230, 150), 1.1])

    def finish(self):
        self.done = True
        parts = list(self.cuts) + ([self.left] if self.left >= 5 else [])
        self.result = {"cuts": parts, "cold": self.cold, "wide": "scales" in self.tools}

    def stop(self):
        self.finish()

    def update(self, dt):
        super().update(dt)
        self.anim = max(0.0, self.anim - dt)
        if self.done:
            return
        self.temp = min(1250.0, self.temp + 240 * dt) if self.heating else max(400.0, self.temp - 45 * self.cool_k() * dt)

    @property
    def score(self):
        return 0.0 if self.cold else 1.0

    def draw(self, surf, rect):
        bench(surf, rect)
        br = self.bar_rect(rect)
        anv = MV.prop("frg_anvil", 640)
        if anv is not None:
            surf.blit(anv, (rect.x + 60, br.bottom - 6))
        else:
            anvil = pygame.Rect(rect.x + 60, br.bottom, 640, 60)
            pygame.draw.rect(surf, (70, 72, 80), anvil, border_radius=6)
            pygame.draw.rect(surf, (50, 52, 58), (anvil.centerx - 50, anvil.bottom, 100, 70))
        hot = heat_color(self.temp)
        if br.w > 2:
            surf.blit(MV.bar(self.xd, self.b["grid"], self.b.get("folds", 0), self.b.get("twist", 0), br.w, br.h,
                             self.temp, seed=5), br)
        x = max(br.x + 2, min(br.right - 2, self.mpos[0]))   # клин
        drop = 8 if self.anim > SWING - 0.16 else 0
        ch = MV.prop("frg_chisel", None, 150)
        if ch is not None:
            surf.blit(ch, (x - ch.get_width() // 2, br.y - ch.get_height() + 6 + drop))
        else:
            pygame.draw.polygon(surf, (180, 182, 192), [(x, br.y - 4 + drop), (x - 10, br.y - 60 + drop),
                                                        (x + 10, br.y - 60 + drop)])
            pygame.draw.rect(surf, (110, 80, 50), (x - 6, br.y - 140 + drop, 12, 80))
        top = br.y - (ch.get_height() - 6 if ch is not None else 140) + drop
        draw_swing(surf, "frg_hammer_hand", (x, top), 120, self.anim)
        cx = rect.x + 100                              # отсечённые части — внизу
        for m in self.cuts:
            w = max(8, int(m * self.px_per_g * 0.45))
            r = pygame.Rect(cx, rect.bottom - 64, w, 22)
            surf.blit(MV.bar(self.xd, self.b["grid"], self.b.get("folds", 0), self.b.get("twist", 0), r.w, r.h,
                             max(20.0, self.temp - 300), seed=7), r)
            T.text(surf, f"{m:.0f} г", (r.centerx, r.bottom + 4), 12, T.TEXT, center=True)
            cx += w + 14
        px = rect.right - 330
        T.text(surf, "Разделка", (px, rect.y + 20), 22, (255, 210, 120), True)
        props_panel(surf, self.xd, px, rect.y + 54, 300, billet_props_of(self.xd, self.b), self.left, "Брусок")
        bar(surf, px, rect.y + 214, 280, "Жар (холодный режется неровно)", self.temp, (850, 1250), hot, 400, 1250,
            f"{self.temp:.0f}°")
        recipes = SM.cfg(self.xd)["recipes"]
        names = self.xd["artifacts"]["kinds"]
        lines = ["Кусок — любой массы, на глаз.", "Под вещи нужны части:"] + \
            [f"  {names[k]['name']}: " + " + ".join(f"{m} г" for m in v["parts"]) for k, v in recipes.items()]
        for i, ln in enumerate(lines):
            T.text(surf, ln, (px, rect.y + 266 + i * 18), 12, DIM)
        badges(surf, px, rect.bottom - 70, (("ЛКМ", "отсечь"), ("Пробел", "подогреть")))
        badges(surf, px, rect.bottom - 40, (("Enter", "закончить"),))
        self.draw_flash(surf, rect)


# ---------- 5. ковка и закалка ----------

def target_mask(kind, gw, gh):
    """Контур части: наручи — выгнутая пластина, пояс — пластина-звено с вырезами."""
    m = [[False] * gw for _ in range(gh)]
    for y in range(gh):
        for x in range(gw):
            u, v = (x + 0.5) / gw * 2 - 1, (y + 0.5) / gh * 2 - 1
            if kind == "bracers":
                ok = abs(u) < 0.86 and abs(v + 0.18 * u * u) < 0.62
            else:
                ok = abs(u) < 0.6 and abs(v) < 0.7 and not (abs(u) < 0.2 and abs(v) < 0.25)
            m[y][x] = ok
    return m


class ShapeGame(SmithGame):
    """Ковка частей по контуру. Удар: нажми ЛКМ на поковке и протяни мышь — металл уйдёт по стрелке (так гонят к
    краю); короткий клик — металл расходится во все стороны. Удар по вылезшему за пунктир — осаживает назад.
    Молоты (1–4): ручник, кувалда, клиновой (узкая полоса по стрелке), гладилка (ровняет толщину).
    Пробел — в горн, холодный металл трещит. Enter — часть готова; в конце — закалка."""
    title = "Ковка"
    hint = "ЛКМ: нажать и протянуть — металл по стрелке; 1–4 — молот; Пробел — в горн; Enter — часть готова"
    GW, GH, CELL = 28, 16, 17

    def __init__(self, seed=None, xd=None, tools=(), parts=(), kind="bracers"):
        super().__init__(seed, xd, tools)
        self.parts = list(parts)
        self.kind = kind
        self.mask = target_mask(kind, self.GW, self.GH)
        self.tarea = sum(sum(r) for r in self.mask)
        self.i = 0
        self.scores = []
        self.phase = "shape"
        self.quench = {}
        self.anim = 0.0
        H = SM.cfg(xd).get("hammers", {})
        self.hammers = [h for h, v in H.items() if not v.get("tool") or v["tool"] in self.tools]
        self.hammer = self.hammers[0] if self.hammers else "hand"
        self.drag = None                              # (клетка удара, экранная точка)
        self.hit_pos = None
        self.new_part()

    def hcfg(self):
        return SM.cfg(self.xd).get("hammers", {}).get(self.hammer, {"r": 1.5, "power": 0.45, "cool": 12})

    def need(self):
        need = SM.parts_for(self.xd, self.kind) if self.kind in SM.cfg(self.xd)["recipes"] else []
        return need[self.i] if self.i < len(need) else self.parts[self.i].get("mass", 100)

    def new_part(self):
        """Новая часть на наковальне: металла столько, сколько весит часть (тяжелее нужного — толще и шире)."""
        self.th = [[0.0] * self.GW for _ in range(self.GH)]
        k = max(0.85, self.parts[self.i].get("mass", 100) / max(1, self.need())) if self.parts else 1.0
        self.mass_k = k
        w = min(self.GW - 4, int(round(8 * k ** 0.5)))
        h = min(self.GH - 4, int(round(6 * k ** 0.5)))
        x0, y0 = self.GW // 2 - w // 2, self.GH // 2 - h // 2
        t = self.tarea * k / (w * h)                # объём: контур толщиной 1 × (масса / нужная масса)
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                self.th[y][x] = t
        self.temp = 1150.0
        self.in_forge = False
        self.cracks = 0

    def origin(self, rect):
        return (rect.x + 40, rect.y + 70)

    def press(self):
        if self.phase == "quench":
            self.do_quench()
        else:
            self.in_forge = True

    def release(self):
        self.in_forge = False

    def wheel(self, dy):
        if self.hammers:
            i = self.hammers.index(self.hammer) if self.hammer in self.hammers else 0
            self.hammer = self.hammers[(i - (1 if dy > 0 else -1)) % len(self.hammers)]

    def cell_of(self, pos, rect):
        ox, oy = self.origin(rect)
        return ((pos[0] - ox) / self.CELL, (pos[1] - oy) / self.CELL)

    def pointer(self, ev, rect):
        if self.done or self.phase != "shape":
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            gx, gy = self.cell_of(ev.pos, rect)
            if 0 <= gx < self.GW and 0 <= gy < self.GH:
                self.drag = ((gx, gy), ev.pos)
            return True
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.drag:
            (gx, gy), p0 = self.drag
            self.drag = None
            dx, dy = ev.pos[0] - p0[0], ev.pos[1] - p0[1]
            d = math.hypot(dx, dy)
            self.hit_pos = p0
            self.strike(gx, gy, (dx / d, dy / d) if d > 12 else None)
            return True
        return False

    def centroid(self):
        s = sx = sy = 0.0
        for y in range(self.GH):
            for x in range(self.GW):
                v = self.th[y][x]
                s += v
                sx += v * x
                sy += v * y
        return (sx / s, sy / s) if s else (self.GW / 2, self.GH / 2)

    def strike(self, gx, gy, direction=None):
        """Удар молотом в (gx, gy): direction — куда гнать металл (протяжка мышью); None — во все стороны
        (внутри контура — наружу, за контуром — внутрь)."""
        if self.in_forge:
            return
        hc = self.hcfg()
        self.anim = SWING
        hot = max(0.0, min(1.0, (self.temp - 650) / 450))
        self.temp -= hc.get("cool", 12)
        if self.temp < 720:
            self.cracks += 1
            self.flash.append(["Холодный — трещина", (240, 110, 100), 0.7])
            return
        r = hc["r"]
        cells = [(x, y) for y in range(max(0, int(gy - r)), min(self.GH, int(gy + r) + 1))
                 for x in range(max(0, int(gx - r)), min(self.GW, int(gx + r) + 1))
                 if math.hypot(x + 0.5 - gx, y + 0.5 - gy) <= r and self.th[y][x] > 0.02]
        if not cells:
            return
        if hc.get("flat"):                           # гладилка: ровняет толщину под бойком
            avg = sum(self.th[y][x] for x, y in cells) / len(cells)
            for x, y in cells:
                self.th[y][x] += (avg - self.th[y][x]) * 0.7 * hot
            return
        inside = self.mask[min(self.GH - 1, int(gy))][min(self.GW - 1, int(gx))]
        floor = 0.55 if inside else 0.0
        took = 0.0
        for x, y in cells:
            if self.th[y][x] > floor:
                d_ = (self.th[y][x] - floor) * hc["power"] * hot
                self.th[y][x] -= d_
                took += d_
        if took <= 0:
            return
        cxm, cym = self.centroid()
        if direction is None:                        # во все стороны: внутри — от центра, за контуром — к центру
            ox_, oy_ = gx - cxm, gy - cym
            n = math.hypot(ox_, oy_) or 1
            direction = (ox_ / n, oy_ / n) if inside else (-ox_ / n, -oy_ / n)
            spread = 0.45
        else:
            spread = 0.08 if hc.get("line") else 0.2
        dx, dy = direction
        ring = []
        reach = r + (2.6 if hc.get("line") else 1.8)
        for y in range(max(0, int(gy - reach - 1)), min(self.GH, int(gy + reach + 1) + 1)):
            for x in range(max(0, int(gx - reach - 1)), min(self.GW, int(gx + reach + 1) + 1)):
                vx, vy = x + 0.5 - gx, y + 0.5 - gy
                dist = math.hypot(vx, vy)
                if not (r * 0.6 < dist <= reach):
                    continue
                along = (vx * dx + vy * dy) / dist
                side = abs(vx * dy - vy * dx)
                if hc.get("line") and side > 1.0:
                    continue
                w = max(0.0, along) ** 2 + spread
                w *= 1.0 if self.mask[y][x] or not inside else 0.6      # за контур металл уходит неохотно
                ring.append((x, y, w))
        tot = sum(w for _, _, w in ring) or 1
        for x, y, w in ring:
            self.th[y][x] += took * w / tot

    def part_score(self):
        inter = uni = 0
        vals = []
        for y in range(self.GH):
            for x in range(self.GW):
                a = self.th[y][x] > 0.45 * min(1.0, getattr(self, "mass_k", 1.0))
                b = self.mask[y][x]
                inter += a and b
                uni += a or b
                if b:
                    vals.append(self.th[y][x])
        iou = inter / max(1, uni)
        mean = sum(vals) / max(1, len(vals))
        std = (sum((v - mean) ** 2 for v in vals) / max(1, len(vals))) ** 0.5
        even = max(0.0, 1 - std / max(0.3, mean))
        raw = iou * (0.6 + 0.4 * even) - 0.05 * self.cracks
        return max(0.0, min(1.0, raw / 0.8))           # 80% совпадения и ровности — уже отличная работа

    def key(self, k):
        if self.done:
            return False
        if pygame.K_1 <= k <= pygame.K_4 and self.phase == "shape":
            i = k - pygame.K_1
            if i < len(self.hammers):
                self.hammer = self.hammers[i]
            return True
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.phase == "shape":
            self.scores.append(round(self.part_score(), 3))
            self.flash.append([f"Часть {self.i + 1}: {self.scores[-1] * 100:.0f}%", (150, 230, 150), 1.2])
            self.i += 1
            if self.i >= len(self.parts):
                self.phase = "quench"
                self.temp = 1100.0
            else:
                self.new_part()
            return True
        return False

    def do_quench(self):
        lo, hi = SM.cfg(self.xd)["shape"]["quench_t"]
        if "oil" in self.tools:
            lo, hi = lo - 40, hi + 40
        if self.temp > hi:
            self.quench = {"hard": 0.06, "tough": -0.08}
            self.flash.append(["Слишком горячо — хрупкая закалка", (240, 150, 110), 1.2])
        elif self.temp < lo:
            self.quench = {"hard": -0.05, "tough": 0.02}
            self.flash.append(["Остыло — закалка слабая", (240, 180, 110), 1.2])
        else:
            self.quench = {"hard": 0.08, "tough": 0.02}
            self.flash.append(["Закалка в самый раз!", (150, 230, 150), 1.2])
        self.finish()

    def finish(self):
        while len(self.scores) < len(self.parts):
            self.scores.append(0.0)
        self.done = True
        self.result = {"scores": self.scores, "quench": self.quench}

    def stop(self):
        self.finish()

    def update(self, dt):
        super().update(dt)
        self.anim = max(0.0, self.anim - dt)
        if self.done:
            return
        if self.phase == "quench":
            self.temp = max(500.0, self.temp - 90 * dt)
            if self.temp <= 500:
                self.do_quench()
            return
        if self.in_forge:
            self.temp = min(1250.0, self.temp + 300 * dt)
        else:
            self.temp = max(450.0, self.temp - 55 * self.cool_k() * dt)

    @property
    def score(self):
        s = list(self.scores) + ([self.part_score()] if self.phase == "shape" else [])
        return sum(s) / max(1, len(self.parts))

    def look(self):
        p = self.parts[min(self.i, len(self.parts) - 1)] if self.parts else {}
        lk = p.get("look") or {"rows": [["iron"]], "folds": 0, "twist": 0}
        return lk["rows"], lk.get("folds", 0), lk.get("twist", 0)

    def draw(self, surf, rect):
        bench(surf, rect)
        ox, oy = self.origin(rect)
        C = self.CELL
        table = pygame.Rect(ox - 8, oy - 8, self.GW * C + 16, self.GH * C + 16)
        pygame.draw.rect(surf, (52, 54, 62), table, border_radius=8)       # наковальня (плита)
        pygame.draw.rect(surf, (90, 94, 104), (table.x + 4, table.y + 4, table.w - 8, 6), border_radius=3)
        pygame.draw.rect(surf, (30, 32, 38), table, 3, border_radius=8)
        rows, folds, twist = self.look()
        img = MV.forging(self.xd, rows, folds, twist, self.th, C, self.temp if self.phase == "shape" else self.temp,
                         seed=self.i)
        surf.blit(img, (ox, oy))
        for y in range(self.GH):                       # пунктир контура
            for x in range(self.GW):
                if not self.mask[y][x]:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if (not (0 <= nx < self.GW and 0 <= ny < self.GH) or not self.mask[ny][nx]) and (x + y) % 2 == 0:
                        ax = ox + x * C + (C if dx > 0 else 0)
                        ay = oy + y * C + (C if dy > 0 else 0)
                        end = (ax, ay + C) if dx else (ax + C, ay)
                        pygame.draw.line(surf, (255, 210, 90), (ax, ay), end, 2)
        hc = self.hcfg()
        if self.phase == "shape" and self.drag:          # протяжка: стрелка — куда уйдёт металл
            (gx, gy), p0 = self.drag
            pygame.draw.circle(surf, (255, 240, 200), p0, int(hc["r"] * C), 2)
            vx, vy = self.mpos[0] - p0[0], self.mpos[1] - p0[1]
            d = math.hypot(vx, vy)
            if d > 12:
                L = (hc["r"] + (2.6 if hc.get("line") else 1.8)) * C
                e = (p0[0] + vx / d * L, p0[1] + vy / d * L)
                pygame.draw.line(surf, (255, 230, 150), p0, e, 4)
                a = math.atan2(vy, vx)
                pygame.draw.polygon(surf, (255, 230, 150), [e, (e[0] - 14 * math.cos(a - 0.5), e[1] - 14 * math.sin(a - 0.5)),
                                                            (e[0] - 14 * math.cos(a + 0.5), e[1] - 14 * math.sin(a + 0.5))])
            else:
                T.text(surf, "протяните мышь — металл пойдёт по стрелке", (p0[0], p0[1] - hc["r"] * C - 18), 12,
                       (255, 230, 150), True, center=True, shadow=True)
        elif self.phase == "shape" and table.collidepoint(self.mpos):
            pygame.draw.circle(surf, (255, 240, 200), self.mpos, int(hc["r"] * C), 1)
        if self.phase == "shape" and not self.drag:      # молот: замах в покое у курсора, удар — по дуге в точку
            at = self.hit_pos if self.anim > 0 and self.hit_pos else self.mpos
            if self.anim > 0 or table.collidepoint(self.mpos):
                draw_swing(surf, f"frg_hammer_{self.hammer}", at, 96, self.anim)
        hot = heat_color(self.temp)
        px = rect.right - 330
        T.text(surf, "Ковка" if self.phase == "shape" else "Закалка", (px, rect.y + 20), 22, (255, 210, 120), True)
        if self.phase == "shape":
            p = self.parts[self.i]
            nd = self.need()
            T.text(surf, f"Часть {self.i + 1} из {len(self.parts)} · {p['mass']} г" + (f" (нужно {nd} — массивнее)"
                                                                                         if p["mass"] > nd * 1.05 else ""),
                   (px, rect.y + 56), 15, T.TEXT, True)
            bar(surf, px, rect.y + 82, 280, "Жар (холодный трещит)", self.temp, (800, 1250), hot, 450, 1250,
                f"{self.temp:.0f}°")
            T.text(surf, f"Форма: {self.part_score() * 100:.0f}% · трещин {self.cracks}", (px, rect.y + 128), 15, T.TEXT)
            H = SM.cfg(self.xd).get("hammers", {})
            y = rect.y + 154
            for i, hid in enumerate(self.hammers):        # молоты
                on = hid == self.hammer
                hr = pygame.Rect(px, y, 300, 40)
                pygame.draw.rect(surf, (74, 54, 32) if on else (32, 24, 17), hr, border_radius=6)
                pygame.draw.rect(surf, (255, 210, 90) if on else (90, 70, 46), hr, 2 if on else 1, border_radius=6)
                hi = MV.prop(f"frg_hammer_{hid}", None, 34)
                tx = hr.x + 10
                if hi is not None:
                    surf.blit(hi, (hr.x + 6, hr.y + 3))
                    tx = hr.x + 12 + hi.get_width()
                T.text(surf, f"{i + 1}  {H[hid]['name']}", (tx, hr.y + 4), 14, T.TEXT, True)
                T.text(surf, H[hid]["desc"], (tx, hr.y + 22), 11, DIM)
                y += 44
            badges(surf, px, rect.bottom - 70, (("ЛКМ+тянуть", "удар"), ("Пробел", "горн")))
            badges(surf, px, rect.bottom - 40, (("1–4", "молот"), ("Enter", "часть готова")))
        else:
            lo, hi = SM.cfg(self.xd)["shape"]["quench_t"]
            if "oil" in self.tools:
                lo, hi = lo - 40, hi + 40
            bar(surf, px, rect.y + 70, 280, "Остывает — закалить в окне", self.temp, (lo, hi), hot, 500, 1100,
                f"{self.temp:.0f}°")
            T.text(surf, "Пробел — опустить в воду", (px, rect.y + 120), 17, (255, 220, 140), True)
            T.text(surf, "Горячее окна — хрупко, холоднее — мягко.", (px, rect.y + 148), 12, DIM)
            barrel = MV.prop("frg_barrel", 180)
            if barrel is not None:
                surf.blit(barrel, (px, rect.y + 190))
            else:
                pygame.draw.rect(surf, (60, 80, 110), (px, rect.y + 200, 200, 120), border_radius=10)
                pygame.draw.rect(surf, (30, 40, 60), (px, rect.y + 200, 200, 120), 3, border_radius=10)
        self.draw_flash(surf, rect)

    @property
    def quality(self):
        return quality(self.score)

