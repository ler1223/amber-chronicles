"""Мини-игры мастерских: результат — качество работы 0.7–1.3 (рецепт задаёт сет и редкость, игра — качество).

Кузня — ритм-ковка: бить молотом (Пробел / клик), когда метка в раскалённой зоне.
Ювелирная — огранка: держать Пробел, давление растёт; отпустить в зелёной зоне; пережал — трещина.
Алхимия — смешивание: держать Пробел — нагрев, отпустить — остывание; держать смесь в зелёной полосе.
Кожевня — раскрой: вести нож (мышь или ↑↓) по линии лекала, пока полотно движется."""
import math
import random

import pygame

from game import gem3d as G3
from game import jewel_view as JW
from ui import theme as T

Q_LO, Q_HI = 0.7, 1.3


def quality(score):
    return round(Q_LO + (Q_HI - Q_LO) * max(0.0, min(1.0, score)), 3)


class Game:
    title = ""
    hint = ""

    def __init__(self, seed=None, diff=1):
        self.rng = random.Random(seed)
        self.done = False
        self.t = 0.0
        self.scores = []
        self.flash = []                       # всплывающие оценки: [текст, цвет, время]

    @property
    def score(self):
        return sum(self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def quality(self):
        return quality(self.score)

    def grade(self, s):
        self.scores.append(s)
        word, col = ("Идеально!", (255, 220, 120)) if s >= 0.9 else ("Хорошо", (150, 230, 150)) if s >= 0.65 else \
            ("Сносно", (220, 200, 160)) if s >= 0.35 else ("Мимо", (240, 110, 100))
        self.flash.append([word, col, 0.9])

    def update(self, dt):
        self.t += dt
        for f in self.flash:
            f[2] -= dt
        self.flash = [f for f in self.flash if f[2] > 0]

    def press(self):
        pass

    def release(self):
        pass

    def mouse(self, pos, rect):
        self.mpos = pos

    def draw_flash(self, surf, rect):
        if self.flash:                            # только последняя оценка
            word, col, left = self.flash[-1]
            a = min(1.0, left / 0.4)
            T.text(surf, word, (rect.centerx, rect.y + 40 - int((0.9 - left) * 30)), 26,
                   T.mix((20, 16, 12), col, a), True, center=True, shadow=True)


class ForgeRhythm(Game):
    title = "Ритм-ковка"
    hint = "Бейте молотом (Пробел или клик), когда метка в раскалённой зоне. 6 ударов — зона сужается."
    STRIKES = 6

    def __init__(self, seed=None, diff=1):
        super().__init__(seed)
        self.pos = 0.0
        self.dir = 1
        self.speed = 0.9
        self.zone = 0.16
        self.sparks = []

    def update(self, dt):
        super().update(dt)
        if self.done:
            return
        self.pos += self.dir * self.speed * dt
        if self.pos > 1:
            self.pos, self.dir = 2 - self.pos, -1
        elif self.pos < 0:
            self.pos, self.dir = -self.pos, 1
        for s in self.sparks:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[3] += 600 * dt
            s[4] -= dt
        self.sparks = [s for s in self.sparks if s[4] > 0]

    def press(self):
        if self.done:
            return
        d = abs(self.pos - 0.5)
        s = 1.0 if d <= self.zone / 2 else max(0.0, 1 - (d - self.zone / 2) / 0.25)
        self.grade(s)
        for _ in range(int(6 + 18 * s)):
            a = self.rng.uniform(-math.pi, 0)
            v = self.rng.uniform(120, 360)
            self.sparks.append([0, 0, math.cos(a) * v, math.sin(a) * v, self.rng.uniform(0.3, 0.7)])
        self.speed *= 1.13
        self.zone *= 0.86
        self.pos = self.rng.random()
        if len(self.scores) >= self.STRIKES:
            self.done = True

    def draw(self, surf, rect):
        heat = 0.5 + 0.5 * math.sin(self.t * 3)
        anvil = pygame.Rect(0, 0, 300, 60)
        anvil.midbottom = (rect.centerx, rect.y + 250)
        pygame.draw.rect(surf, (60, 60, 68), anvil, border_radius=6)
        pygame.draw.rect(surf, (60, 60, 68), (anvil.centerx - 40, anvil.bottom, 80, 50))
        ingot = pygame.Rect(0, 0, 180, 26)
        ingot.midbottom = anvil.midtop
        glow = len(self.scores) / self.STRIKES
        pygame.draw.rect(surf, T.mix((255, 120, 40), (255, 230, 150), 0.3 * heat + 0.3 * glow), ingot, border_radius=5)
        for s in self.sparks:
            pygame.draw.circle(surf, (255, 200, 90), (int(ingot.centerx + s[0]), int(ingot.y + s[1])), 2)
        bar = pygame.Rect(rect.x + 80, rect.y + 300, rect.w - 160, 30)
        pygame.draw.rect(surf, (36, 30, 28), bar, border_radius=8)
        zw = int(bar.w * self.zone)
        z = pygame.Rect(bar.centerx - zw // 2, bar.y, zw, bar.h)
        pygame.draw.rect(surf, T.mix((200, 80, 30), (255, 200, 80), heat), z, border_radius=6)
        mx = bar.x + int(bar.w * self.pos)
        pygame.draw.rect(surf, (240, 240, 240), (mx - 3, bar.y - 8, 6, bar.h + 16), border_radius=3)
        pygame.draw.rect(surf, T.PANEL_EDGE, bar, 2, border_radius=8)
        T.text(surf, f"Удар {min(len(self.scores) + 1, self.STRIKES)} из {self.STRIKES}", (rect.centerx, bar.bottom + 16),
               16, T.TEXT, True, center=True)
        self.draw_flash(surf, rect)


def _clip(poly, n, h):
    """Выпуклый многоугольник, обрезанный полуплоскостью p·n ≤ h (то, что ушло ниже круга, сточено)."""
    out = []
    k = len(poly)
    for i in range(k):
        a, b = poly[i], poly[(i + 1) % k]
        da = a[0] * n[0] + a[1] * n[1] - h
        db = b[0] * n[0] + b[1] * n[1] - h
        if da <= 0:
            out.append(a)
        if (da < 0 < db) or (db < 0 < da):
            t = da / (da - db)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def _area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2 if len(poly) > 2 else 0.0


def _hull(pts):
    pts = sorted(set(pts))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p_ in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p_) <= 0:
            lo.pop()
        lo.append(p_)
    for p_ in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p_) <= 0:
            hi.pop()
        hi.append(p_)
    return lo[:-1] + hi[:-1]


def _angdiff(a, b):
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


# огранки на выбор: ярусы — (сторона P низ / C верх, граней, угол °, доля радиуса, сдвиг индекса);
# угол 0 — площадка. Предел качества и секунд на грань (таймер)
CUTS = (
    {"id": "baguette", "name": "Багет", "cap": 1.04, "per": None,
     "tiers": (("P", 4, 45, 1.0, 0), ("P", 4, 30, 0.5, 0), ("C", 4, 38, 1.0, 0), ("C", 1, 0, 0.6, 0))},
    {"id": "emerald", "name": "Изумрудная", "cap": 1.12, "per": None,
     "tiers": (("P", 4, 48, 1.0, 0), ("P", 4, 38, 0.62, 0), ("C", 4, 42, 1.0, 0), ("C", 4, 28, 0.72, 0),
               ("C", 1, 0, 0.55, 0))},
    {"id": "cushion", "name": "Кушон", "cap": 1.19, "per": None,
     "tiers": (("P", 8, 42, 1.0, 0), ("P", 4, 30, 0.45, 6), ("C", 8, 36, 1.0, 6), ("C", 1, 0, 0.55, 0))},
    {"id": "oval", "name": "Овал", "cap": 1.25, "per": 11.0,
     "tiers": (("P", 8, 41, 1.0, 0), ("P", 8, 45, 1.0, 6), ("C", 8, 35, 1.0, 0), ("C", 4, 22, 0.55, 6),
               ("C", 1, 0, 0.56, 0))},
    {"id": "brilliant", "name": "Круглая бриллиантовая", "cap": 1.30, "per": 9.5,
     "tiers": (("P", 8, 41, 1.0, 0), ("P", 8, 44, 1.0, 6), ("C", 8, 35, 1.0, 0), ("C", 8, 22, 0.56, 6),
               ("C", 1, 0, 0.56, 0))},
)
NOTCHES = 96                                   # делительное колесо: 96 зубцов


def cut_counts(cut):
    low = sum(t[1] for t in cut["tiers"] if t[0] == "P")
    return low, sum(t[1] for t in cut["tiers"]) - low


class JewelCut(Game):
    """Огранка на гранильном станке (вид сбоку): шлифовальный диск, камень на оправке, мачта с квадрантом.
    Сначала низ камня (павильон), затем камень переворачивают на оправке (F) и гранят верх: грани короны и
    площадку. Угол оправки — на глаз (W/S, колесо; Shift — точнее), индекс — делительное колесо (A/D, держать —
    крутится), опускать — Пробел/ЛКМ (держать): касание — сопротивление и стачивание. Пунктир — цель: при верных
    угле и индексе ложится вдоль диска. Enter/ПКМ — грань готова. Справа — лупа (видна гранимая сторона)
    и схема огранки. Сложность — число граней; сложнее — выше предел качества (у самых сложных — таймер)."""
    title = "Огранка"
    hint = "W/S — угол, A/D — индекс, Пробел/ЛКМ — к диску, Enter/ПКМ — грань готова, F — перевернуть"
    area_size = (1120, 520)
    TOL_ANG, TOL_DEPTH, GRIND = 4.5, 6.0, 26.0
    R = 100.0

    def __init__(self, seed=None, diff=1):
        super().__init__(seed)
        self.diff = max(0, min(3, diff))
        self.color = (110, 170, 240)
        self.phase = "choose"
        self.cut = None
        self.time_left = None
        self.note = ""
        self.theta = 40.0
        self.index = 0
        self.h = 175.0
        self.h_max = 175.0
        self.hold = False
        self.contact = 0.0
        self.spin = 0.0
        self.sparks = []
        self.choice_rects = []
        self.rep_dir, self.rep_t = 0, 0.0
        self.side = 1                           # 1 — гранится низ (павильон), -1 — верх (корона)
        self.flip_a = 0.0                       # угол переворота камня на оправке (анимация)
        self.facets = []
        self.n = 0
        self.scores = []
        self.active = 0
        self._mass = 1.0
        self._mass_t = 0.0
        self.inspect = None                     # осмотр снятого камня (Tab): свободное вращение
        self.inspect_btn = None

    # --- выбор огранки ---
    def choose(self, i):
        c = CUTS[i]
        self.cut = c
        self.facets = []
        main_ang = {"P": 41.0, "C": 35.0}
        for side in ("P", "C"):
            mains = [t for t in c["tiers"] if t[0] == side and t[2] > 0]
            if mains:
                main_ang[side] = float(mains[0][2])
        for t, (side, n, ang, ratio, off) in enumerate(c["tiers"]):
            for k in range(n):
                idx = (off + k * NOTCHES // n) % NOTCHES
                self.facets.append({"tier": t, "side": 1 if side == "P" else -1, "index": idx, "ang": float(ang),
                                    "ratio": ratio, "n": n, "main": main_ang[side],
                                    "dial": idx if side == "P" else (-idx) % NOTCHES})
        self.n = len(self.facets)
        self.scores = [None] * self.n
        self.stone = G3.make_stone(self.rng, self.R)
        ideal = self.stone
        for f in self.facets:                    # цель каждой грани — достижима: плоскость касается камня
            n, off = self.target(f)
            ext = G3.extent(ideal, n)
            if ext < off + 4:
                f["off"] = ext - 4
            ideal = G3.clip(ideal, *self.target(f))
        self.ideal = ideal
        self.vol0 = max(1.0, G3.volume(ideal))
        self._mass = 1.0
        self.active = 0
        per = c["per"]
        self.time_left = per * self.n * (1 - 0.08 * self.diff) if per else None
        self.theta = self.facets[0]["ang"] + self.rng.choice((-7, 7))
        self.phase = "cut"

    def normal(self, theta, dial, side):
        """Нормаль плоскости, которую сточит диск, — в осях камня (с учётом переворота)."""
        th = math.radians(theta)
        ph = math.tau * dial / NOTCHES
        L = (math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th))
        return L if side > 0 else (L[0], -L[1], -L[2])

    def target(self, f):
        """Цель грани: плоскость через точку на рундисте (или на склоне главных граней — для звёзд и низа)."""
        if "off" in f:
            n = self.normal(f["ang"], f["dial"], f["side"])
            return n, f["off"]
        n = self.normal(f["ang"], f["dial"], f["side"])
        R, g = self.R, G3.GIRDLE * self.R
        if f["ang"] == 0:                        # площадка
            h = g + (1 - f["ratio"]) * R * math.tan(math.radians(f["main"]))
            return n, h
        ph = math.tau * f["index"] / NOTCHES
        r = R * f["ratio"]
        z = g + (1 - f["ratio"]) * R * math.tan(math.radians(f["main"]))
        pt = (r * math.cos(ph), r * math.sin(ph), f["side"] * z)
        return n, G3.dot(n, pt)

    def click(self, pos):
        if self.phase == "choose":
            for i, r in enumerate(self.choice_rects):
                if r.collidepoint(pos):
                    self.choose(i)
                    return True
        return False

    # --- управление ---
    def press(self):
        if self.inspect is None and not self.done and self.phase == "cut" and \
                self.flip_a == (0.0 if self.side > 0 else math.pi):
            self.hold = True

    def toggle_inspect(self):
        """Снять камень с оправки и рассмотреть (Tab / V), вернуть — так же."""
        if self.phase != "cut":
            return
        self.hold = False
        self.inspect = None if self.inspect else JW.Inspector()

    def pointer(self, ev, rect):
        """Мышь в осмотре — вращать камень; клик по кнопке «Осмотреть» — снять камень."""
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.inspect_btn and \
                self.inspect_btn.collidepoint(ev.pos):
            self.toggle_inspect()
            return True
        if self.inspect is not None:
            if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_TAB, pygame.K_v):
                self.toggle_inspect()
                return True
            return self.inspect.pointer(ev, rect)
        return False

    def release(self):
        self.hold = False

    def wheel(self, dy):
        if self.inspect is not None:
            self.inspect.wheel(dy)
            return
        if self.phase == "cut" and not self.done:
            self.theta = max(0.0, min(80.0, self.theta + dy * (0.25 if self._fine() else 1.0)))

    def key(self, k):
        if self.phase == "choose":
            if pygame.K_1 <= k <= pygame.K_1 + len(CUTS) - 1:
                self.choose(k - pygame.K_1)
                return True
            return False
        if k in (pygame.K_TAB, pygame.K_v):
            self.toggle_inspect()
            return True
        if self.inspect is not None:
            return True
        if self.done:
            return False
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.accept()
            return True
        if k == pygame.K_f:
            self.flip()
            return True
        if k in (pygame.K_a, pygame.K_LEFT, pygame.K_q):
            self.step_index(-1)
            return True
        if k in (pygame.K_d, pygame.K_RIGHT, pygame.K_e):
            self.step_index(1)
            return True
        return False

    def step_index(self, d, first=True):
        self.index = (self.index + d) % NOTCHES
        if first:                                # зажал — после паузы индекс крутится сам
            self.rep_dir, self.rep_t = d, -0.28

    def flip(self):
        """Перевернуть камень на оправке: низ ↔ верх."""
        self.side = -self.side
        self.hold = False
        self.h = self.h_max
        self.note = ""
        self.pick_active()

    def side_left(self, side):
        return [i for i, f in enumerate(self.facets) if f["side"] == side and self.scores[i] is None]

    def pick_active(self):
        here = self.side_left(self.side)
        if here:
            self.active = here[0]
        else:
            rest = [i for i in range(self.n) if self.scores[i] is None]
            self.active = rest[0] if rest else self.active

    def need_flip(self):
        return self.phase == "cut" and not self.done and not self.side_left(self.side)

    def _fine(self):
        try:
            return bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        except pygame.error:
            return False

    def stop(self):
        if self.phase == "choose":
            self.choose(0)
        self.scores = [x if x is not None else 0.0 for x in self.scores]
        self.done = True

    def n_vec(self):
        return self.normal(self.theta, self.index, self.side)

    def extent(self):
        return G3.extent(self.stone, self.n_vec())

    def index_err(self, f):
        d = abs(self.index - f["dial"]) % NOTCHES
        return min(d, NOTCHES - d) * 360.0 / NOTCHES

    def accept(self):
        if self.need_flip():
            self.flash.append(["Сначала переверните камень (F)", (240, 200, 120), 1.2])
            return
        k = self.active
        f = self.facets[k]
        sc = self.facet_score(k)
        ie = self.index_err(f)
        sc *= max(0.0, 1 - ie / (180.0 / f["n"]))           # не тот индекс — грань не на месте
        self.scores[k] = round(sc, 3)
        self.flash.append([f"Грань {k + 1}: {sc * 100:.0f}%" + (" · не тот индекс" if ie else ""),
                           (150, 230, 150) if sc >= 0.6 else (240, 170, 110), 1.2])
        self.h = self.h_max
        self.stone = G3.polished(self.stone)       # грань готова — полировка: начинает играть светом
        self._mass = self.calc_mass()
        if all(x is not None for x in self.scores):
            self.done = True
        else:
            self.pick_active()
            if self.need_flip():
                self.flash.append(["Сторона готова — переверните камень (F)", (255, 220, 130), 2.0])

    def calc_mass(self):
        cur = self.stone
        for f in self.facets:
            cur = G3.clip(cur, *self.target(f))
        return min(1.0, G3.volume(cur) / self.vol0)

    def facet_score(self, k):
        """Грань камня, ближайшая к цели по направлению: ошибка угла (3D) и глубины."""
        f = self.facets[k]
        n, off = self.target(f)
        best = None
        for face in self.stone:
            if face["kind"] not in ("frost", "polish") or G3.face_area(face) < 12:
                continue
            ang = math.acos(max(-1.0, min(1.0, G3.dot(face["n"], n))))
            if ang < math.radians(15) and (best is None or ang < best[0]):
                best = (ang, face)
        if best is None:
            return 0.0
        ang, face = best
        ea = math.degrees(ang)
        ed = G3.dot(face["n"], face["pts"][0]) - off
        sa = max(0.0, 1 - ea / (self.TOL_ANG * 2.5))
        sd = max(0.0, 1 - abs(ed) / (self.TOL_DEPTH * (2.5 if ed > 0 else 1.6)))
        return sa * sd

    def mass(self):
        return self._mass if self.phase == "cut" else 1.0

    @property
    def score(self):
        if self.phase != "cut":
            return 0.0
        done = [x for x in self.scores if x is not None]
        if not done:
            return 0.0
        return sum(done) / self.n * (0.6 + 0.4 * self.mass() ** 2)

    @property
    def quality(self):
        cap = self.cut["cap"] if self.cut else Q_HI
        return round(Q_LO + (cap - Q_LO) * max(0.0, min(1.0, self.score)), 3)

    def shape(self):
        """Форма готового камня для инвентаря."""
        return G3.planes(G3.polished(self.stone))

    def update(self, dt):
        super().update(dt)
        self.spin += dt * 10
        want_a = 0.0 if self.side > 0 else math.pi      # переворот — плавный поворот на оправке
        if self.flip_a != want_a:
            step = dt * 4.0
            self.flip_a = want_a if abs(want_a - self.flip_a) <= step else \
                self.flip_a + (step if want_a > self.flip_a else -step)
        if self.inspect is not None:
            self.inspect.update(dt)
        if self.done or self.phase != "cut":
            return
        if self.time_left is not None:
            self.time_left -= dt
            if self.time_left <= 0:
                self.time_left = 0
                self.note = "Время вышло"
                self.stop()
                return
        try:
            keys = pygame.key.get_pressed() if self.inspect is None else None
        except pygame.error:
            keys = None
        if keys:
            sp = (4 if self._fine() else 18) * dt
            if keys[pygame.K_w] or keys[pygame.K_UP]:
                self.theta = min(80.0, self.theta + sp)
            if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                self.theta = max(0.0, self.theta - sp)
            held = (-1 if keys[pygame.K_a] or keys[pygame.K_LEFT] or keys[pygame.K_q] else 0) + \
                (1 if keys[pygame.K_d] or keys[pygame.K_RIGHT] or keys[pygame.K_e] else 0)
            if held and held == self.rep_dir:
                self.rep_t += dt
                step = 0.13 if self._fine() else 0.045
                while self.rep_t >= step:
                    self.rep_t -= step
                    self.step_index(held, first=False)
            else:
                self.rep_dir = 0
        ext = self.extent()
        if self.hold:
            want = self.h - 150 * dt
            if want < ext:
                self.contact = min(1.0, self.contact + dt * 6)
                want = max(want, min(self.h, ext) - self.GRIND * dt)
                f = self.facets[self.active]
                self.stone = G3.clip(self.stone, self.n_vec(), want, "frost") or self.stone
                self._mass_t += dt
                if self._mass_t > 0.25:
                    self._mass_t = 0.0
                    self._mass = self.calc_mass()
                for _ in range(3):
                    self.sparks.append([self.rng.uniform(-20, 20), 0.0, self.rng.uniform(-200, 60),
                                        self.rng.uniform(-200, -60), self.rng.uniform(0.2, 0.45)])
                n, off = self.target(f)
                if off - want > self.TOL_DEPTH * 1.6 and abs(self.theta - f["ang"]) < 10 and \
                        self.index_err(f) < 8 and not self.note:
                    self.note = "Пережал — камень стал меньше"
                    self.flash.append(["Слишком глубоко!", (240, 110, 100), 0.9])
            else:
                self.contact = max(0.0, self.contact - dt * 4)
            self.h = max(0.0, want)
        else:
            self.contact = max(0.0, self.contact - dt * 4)
            self.h = min(self.h_max, self.h + 170 * dt)
        for s_ in self.sparks:
            s_[0] += s_[2] * dt
            s_[1] += s_[3] * dt
            s_[3] += 700 * dt
            s_[4] -= dt
        self.sparks = [s_ for s_ in self.sparks if s_[4] > 0]

    # --- проекции ---
    def machine_world(self, p_):
        """Оси камня → мир станка (вид сбоку): переворот на оправке, индекс, наклон оправки; Z — к зрителю."""
        a = self.flip_a
        ca, sa = math.cos(a), math.sin(a)
        p_ = (p_[0], p_[1] * ca - p_[2] * sa, p_[1] * sa + p_[2] * ca)
        ps = math.tau * self.index / NOTCHES
        cp, sp = math.cos(ps), math.sin(ps)
        x, y, z = p_[0] * cp + p_[1] * sp, -p_[0] * sp + p_[1] * cp, p_[2]
        th = math.radians(self.theta)
        st, ct = math.sin(th), math.cos(th)
        return (-(-ct * x + st * z), st * x + ct * z, -y)

    def loupe_world(self, p_):
        """Лупа: видна гранимая сторона (низ — снизу, верх — сверху), камень медленно поворачивается."""
        a = self.t * 0.35
        ca, sa = math.cos(a), math.sin(a)
        x, y, z = p_[0] * ca - p_[1] * sa, p_[0] * sa + p_[1] * ca, p_[2]
        z = -z if self.side < 0 else z
        if self.side > 0:
            y = -y
        b = 0.22 * math.sin(self.t * 0.8)
        cb, sb = math.cos(b), math.sin(b)
        return (x, y * cb - z * sb, y * sb + z * cb)

    # --- рисование ---
    def draw(self, surf, rect):
        clip = surf.get_clip()
        surf.set_clip(rect)
        if self.phase == "choose":
            self.draw_choose(surf, rect)
        elif self.inspect is not None:
            JW.draw_inspect(self, surf, rect)
        else:
            JW.draw_scene(self, surf, rect)
        surf.set_clip(clip)
        self.draw_flash(surf, rect)

    def draw_choose(self, surf, rect):
        JW.draw_choose(self, surf, rect)


class AlchemyMix(Game):
    title = "Смешивание"
    hint = "Держите Пробел — нагрев, отпустите — остывание. Держите смесь в зелёной полосе до конца варки."
    DURATION = 8.0

    def __init__(self, seed=None, diff=1):
        super().__init__(seed)
        self.temp = 0.3
        self.hold = False
        self.good = 0.0
        self.total = 0.0
        self.noise = 0.0
        self.bubbles = []

    def band(self):
        c = 0.5 + 0.22 * math.sin(self.t * 0.9 + 1.3) + 0.08 * math.sin(self.t * 2.3)
        return c, 0.16

    def update(self, dt):
        super().update(dt)
        if self.done:
            return
        self.noise += (self.rng.uniform(-1, 1) * 0.6 - self.noise) * dt
        self.temp += ((0.55 if self.hold else -0.4) + self.noise * 0.3) * dt
        self.temp = max(0.0, min(1.0, self.temp))
        c, w = self.band()
        d = abs(self.temp - c)
        self.good += dt * (1.0 if d <= w / 2 else max(0.0, 1 - (d - w / 2) / 0.12))
        self.total += dt
        if self.rng.random() < dt * (4 + 14 * self.temp):
            self.bubbles.append([self.rng.uniform(-40, 40), 0.0, self.rng.uniform(2, 6)])
        for b in self.bubbles:
            b[1] += dt * (40 + 80 * self.temp)
        self.bubbles = [b for b in self.bubbles if b[1] < 120]
        if self.t >= self.DURATION:
            self.done = True
            self.scores = [self.good / max(0.01, self.total)]

    @property
    def score(self):
        return self.good / max(0.01, self.total) if self.total else 0.0

    def press(self):
        self.hold = True

    def release(self):
        self.hold = False

    def draw(self, surf, rect):
        cx, cy = rect.centerx - 60, rect.y + 200
        c, w = self.band()
        ok = abs(self.temp - c) <= w / 2
        liquid = T.mix((80, 200, 120), (240, 120, 60), self.temp) if ok else T.mix((120, 110, 140), (240, 90, 60), self.temp)
        pygame.draw.circle(surf, liquid, (cx, cy), 80)
        pygame.draw.rect(surf, liquid, (cx - 22, cy - 140, 44, 80))
        for b in self.bubbles:
            pygame.draw.circle(surf, (240, 250, 240), (int(cx + b[0]), int(cy + 40 - b[1])), int(b[2]), 1)
        pygame.draw.circle(surf, (220, 230, 240), (cx, cy), 80, 3)
        if self.hold:
            for i in range(5):
                fx = cx - 50 + i * 25
                pygame.draw.polygon(surf, (255, 150 + int(60 * math.sin(self.t * 12 + i)), 50),
                                    [(fx - 8, cy + 100), (fx + 8, cy + 100), (fx, cy + 72 - 8 * math.sin(self.t * 9 + i))])
        bar = pygame.Rect(rect.right - 140, rect.y + 50, 34, 280)
        pygame.draw.rect(surf, (36, 30, 28), bar, border_radius=8)
        zy = bar.bottom - int(bar.h * (c + w / 2))
        pygame.draw.rect(surf, (90, 210, 120), (bar.x, zy, bar.w, int(bar.h * w)), border_radius=4)
        ty = bar.bottom - int(bar.h * self.temp)
        pygame.draw.rect(surf, (255, 240, 220), (bar.x - 8, ty - 3, bar.w + 16, 6), border_radius=3)
        pygame.draw.rect(surf, T.PANEL_EDGE, bar, 2, border_radius=8)
        T.text(surf, "жар", (bar.centerx, bar.bottom + 8), 13, T.TEXT_DIM, center=True)
        left = max(0.0, self.DURATION - self.t)
        T.text(surf, f"Варка: {left:.1f} с · в полосе {self.score * 100:.0f}%", (rect.centerx, rect.y + 330), 16,
               T.TEXT, True, center=True)


class LeatherTrace(Game):
    title = "Раскрой"
    hint = "Ведите нож по линии лекала — мышью или ↑ ↓. Чем ближе к линии, тем чище раскрой."
    DURATION = 7.0

    def __init__(self, seed=None, diff=1):
        super().__init__(seed)
        self.y = 0.5
        self.v = 0
        self.err = 0.0
        self.total = 0.0
        self.trail = []
        self.ph = [self.rng.uniform(0, 6) for _ in range(3)]
        self.mouse_y = None

    def line(self, x):
        p = self.ph
        return 0.5 + 0.22 * math.sin(x * 2.1 + p[0]) + 0.12 * math.sin(x * 4.7 + p[1]) + 0.05 * math.sin(x * 9 + p[2])

    def update(self, dt):
        super().update(dt)
        if self.done:
            return
        keys = pygame.key.get_pressed() if pygame.get_init() and pygame.display.get_init() else None
        if keys and (keys[pygame.K_UP] or keys[pygame.K_DOWN]):
            self.mouse_y = None
            self.y += (0.7 if keys[pygame.K_DOWN] else -0.7) * dt
        elif self.mouse_y is not None:
            self.y += (self.mouse_y - self.y) * min(1.0, dt * 12)
        self.y = max(0.0, min(1.0, self.y))
        x = self.t * 1.2
        d = abs(self.y - self.line(x))
        self.err += dt * max(0.0, 1 - d / 0.12)
        self.total += dt
        self.trail.append((self.t, self.y))
        self.trail = self.trail[-200:]
        if self.t >= self.DURATION:
            self.done = True
            self.scores = [self.err / max(0.01, self.total)]

    @property
    def score(self):
        return self.err / max(0.01, self.total) if self.total else 0.0

    def mouse(self, pos, rect):
        area = self.area(rect)
        if area.collidepoint(pos):
            self.mouse_y = (pos[1] - area.y) / area.h

    def area(self, rect):
        return pygame.Rect(rect.x + 40, rect.y + 40, rect.w - 80, 260)

    def draw(self, surf, rect):
        a = self.area(rect)
        pygame.draw.rect(surf, (120, 82, 52), a, border_radius=12)
        pygame.draw.rect(surf, (80, 54, 34), a, 3, border_radius=12)
        kx = a.x + a.w // 3                       # нож стоит, полотно уезжает влево
        span = a.w / 3.0                          # пикселей на единицу лекала
        for i in range(0, a.w, 12):
            wx = self.t * 1.2 + (a.x + i - kx) / span
            pygame.draw.circle(surf, (250, 230, 190), (a.x + i, int(a.y + a.h * self.line(wx))), 2)
        for t, y in self.trail:
            px = kx + (t - self.t) * 1.2 * span
            if px > a.x:
                pygame.draw.circle(surf, (60, 34, 20), (int(px), int(a.y + a.h * y)), 2)
        ky = a.y + a.h * self.y
        pygame.draw.polygon(surf, (220, 225, 235), [(kx, ky), (kx - 26, ky - 10), (kx - 26, ky + 4)])
        pygame.draw.rect(surf, (90, 60, 40), (kx - 46, ky - 8, 20, 10))
        left = max(0.0, self.DURATION - self.t)
        T.text(surf, f"Раскрой: {left:.1f} с · точность {self.score * 100:.0f}%", (rect.centerx, rect.y + 320), 16,
               T.TEXT, True, center=True)


GAMES = {"ws_forge": ForgeRhythm, "ws_jewel": JewelCut, "ws_alchemy": AlchemyMix, "ws_leather": LeatherTrace}
