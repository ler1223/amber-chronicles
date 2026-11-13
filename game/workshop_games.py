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
from sim import gems as GM
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


# огранки (sim/gems.py): ярусы — (сторона P низ / C верх, граней, угол °, доля радиуса, сдвиг индекса);
# угол 0 — площадка (у низа — плоское дно или калетта). Контур рундиста, предел качества, книга
CUTS = GM.CUTS
NOTCHES = 96                                   # делительное колесо: 96 зубцов


def cut_counts(cut):
    low = sum(t[1] for t in cut["tiers"] if t[0] == "P")
    return low, sum(t[1] for t in cut["tiers"]) - low


def _mv(m, p):
    return (m[0][0] * p[0] + m[0][1] * p[1] + m[0][2] * p[2],
            m[1][0] * p[0] + m[1][1] * p[1] + m[1][2] * p[2],
            m[2][0] * p[0] + m[2][1] * p[1] + m[2][2] * p[2])


def inside_points(faces, n=200, seed=7):
    """Случайные точки внутри многогранника (отбор из ограничивающего бруска)."""
    planes = [(f["n"], G3.dot(f["n"], f["pts"][0])) for f in faces if f["pts"]]
    pts = [p_ for f in faces for p_ in f["pts"]]
    lo = [min(p_[i] for p_ in pts) for i in range(3)]
    hi = [max(p_[i] for p_ in pts) for i in range(3)]
    rng = random.Random(seed)
    out = []
    for _ in range(n * 20):
        p_ = tuple(rng.uniform(lo[i], hi[i]) for i in range(3))
        if all(G3.dot(nv, p_) <= off for nv, off in planes):
            out.append(p_)
            if len(out) >= n:
                break
    return out


def cf_stats(gid, cf, pts):
    """Состав оттенков точек камня (оси камня) по его окну в карте вида."""
    A = cf["A"]
    q = [(A[0] * x + A[1] * y + A[2] * z + cf["b"][0], A[3] * x + A[4] * y + A[5] * z + cf["b"][1],
          A[6] * x + A[7] * y + A[8] * z + cf["b"][2]) for x, y, z in pts]
    return GM.color_stats(gid, GM.field_t(gid, q))


class Plan:
    """Разметка сырого кристалла: камень крутится мышью (как в осмотре), внутри — неподвижный контур будущего
    камня; колесо — его размер (доля наибольшего, что влезает), WASD/стрелки — сдвиг. Примеси внутри контура
    останутся в камне, снаружи — уйдут в отход. Видно: массу, чистоту, примерную цену (и звезду для кабошона)."""
    TILT = 0.3

    def __init__(self, game, rough):
        self.g = game
        self.rough = rough
        self.faces, self.Rr, self.Lr = JW.rough_geom(rough)
        self.vol = max(1e-6, G3.volume(self.faces))
        self.planes = [(f["n"], G3.dot(f["n"], f["pts"][0])) for f in self.faces if f["pts"]]
        self.incl = JW.rough_incl(rough)
        self.m = self.upright()                          # ось кристалла — вдоль оси будущего камня
        self.o = [0.0, 0.0, 0.0]
        self.frac = 1.0
        self.drag = None
        verts = {tuple(round(c, 4) for c in p_) for f in game.ideal for p_ in f["pts"]}
        self.qv = [self.q(v) for v in verts]
        self.ideal_planes = [(f["n"], G3.dot(f["n"], f["pts"][0])) for f in game.ideal if f["pts"]]
        self.ideal_vol = G3.volume(game.ideal)

    def upright(self):
        return JW._rot("x", self.TILT - math.pi / 2)

    # контур будущего камня: оси камня → вид (на станке корона — в −z: она вверх по экрану, слегка к зрителю)
    def q(self, p_):
        x, y, z = p_
        v1, v2 = z, -y
        c, s_ = math.cos(self.TILT), math.sin(self.TILT)
        return (x, v1 * c - v2 * s_, v1 * s_ + v2 * c)

    def qt(self, v):
        c, s_ = math.cos(self.TILT), math.sin(self.TILT)
        v1 = v[1] * c + v[2] * s_
        v2 = -v[1] * s_ + v[2] * c
        return (v[0], -v2, v1)

    def turn(self, dx, dy):
        self.m = JW._mm(JW._rot("y", dx * 0.012), JW._mm(JW._rot("x", -dy * 0.012), self.m))

    def s_max(self):
        best = 1e9
        for n, d in self.planes:
            mn = _mv(self.m, n)
            lim = d - G3.dot(mn, self.o)
            if lim <= 0:
                return 0.0
            for v in self.qv:
                den = G3.dot(mn, v)
                if den > 1e-9:
                    best = min(best, lim / den)
        return 0.0 if best >= 1e9 else best

    def s(self):
        return self.frac * self.s_max()

    def to_stone(self, p_, s=None):
        s = s or self.s()
        v = _mv(self.m, p_)
        return tuple(x / max(1e-9, s) for x in self.qt((v[0] - self.o[0], v[1] - self.o[1], v[2] - self.o[2])))

    def normal_to_stone(self, n):
        return self.qt(_mv(self.m, n))

    def stone_incl(self, s=None):
        """Примеси в осях будущего камня: [(примесь, внутри ли контура)]."""
        s = s or self.s()
        out = []
        for inc in self.incl:
            p_ = self.to_stone(inc["p"], s)
            si = dict(inc, p=[round(c, 2) for c in p_], r=round(inc["r"] / max(1e-9, s), 2))
            if "n" in inc:
                si["n"] = [round(c, 4) for c in self.normal_to_stone(inc["n"])]
            if inc["k"] == "silk":
                si["p"] = [0.0, 0.0, 0.0]
                inside = True
            else:
                inside = all(G3.dot(n, p_) - off <= si["r"] * 0.5 for n, off in self.ideal_planes)
            out.append((si, inside))
        return out

    def axis(self):
        """Ось кристалла (шёлк — поперёк неё) в осях будущего камня: для звезды должна смотреть вверх."""
        return self.normal_to_stone((0.0, 0.0, 1.0))

    def silk(self):
        return max((i.get("d", 0.0) for i in self.incl if i["k"] == "silk"), default=0.0)

    def star(self):
        if not self.g.cut.get("dome"):
            return 0.0
        return round(self.silk() * abs(self.axis()[2]) ** 6, 3)

    def est_ct(self):
        s = self.s()
        return self.rough["size"] * s ** 3 * self.ideal_vol / self.vol

    def est_clarity(self):
        xd = self.g.xd
        inside = [si for si, ok in self.stone_incl() if ok]
        return GM.clarity(xd, inside) if xd else 1.0

    def cf_rough(self):
        """Кристалл в карте оттенков: мм = mmr·p + окно камня."""
        mmr = self.mm_per_unit()
        return {"A": [mmr, 0, 0, 0, mmr, 0, 0, 0, mmr], "b": list(self.rough["cf"]["o"])}

    def cf_stone(self, s=None):
        """Будущий камень в карте оттенков: p_кристалла = Mᵀ(s·Q·p + o) → мм = A·p + b."""
        s = s or self.s()
        mmr = self.mm_per_unit()
        m = self.m
        mt = [[m[j][i] for j in range(3)] for i in range(3)]
        qc = [self.q(e) for e in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]          # столбцы Q
        A = [[mmr * s * sum(mt[i][k] * qc[j][k] for k in range(3)) for j in range(3)] for i in range(3)]
        mo = _mv(mt, self.o)
        b = [mmr * mo[i] + self.rough["cf"]["o"][i] for i in range(3)]
        return {"A": [v for row in A for v in row], "b": b}

    def ideal_points(self):
        """Точки внутри будущего камня (оси камня) — для оценки оттенков."""
        if not hasattr(self, "_ipts"):
            self._ipts = inside_points(self.g.ideal, 180)
        return self._ipts

    def est_colors(self):
        return cf_stats(self.rough["id"], self.cf_stone(), self.ideal_points())

    def mm_per_unit(self):
        """Миллиметров на единицу кристалла (масса и плотность вида)."""
        sg = GM.gem_def(self.g.xd, self.rough["id"]).get("sg", 3.5) if self.g.xd else 3.5
        return (200.0 * self.rough["size"] / sg / self.vol) ** (1 / 3)

    def move(self, dx, dy):
        step = 0.03 * self.Rr
        self.o[0] = max(-self.Rr, min(self.Rr, self.o[0] + dx * step))
        self.o[1] = max(-self.Lr, min(self.Lr, self.o[1] + dy * step))

    def wheel(self, dy):
        self.frac = max(0.3, min(1.0, self.frac + 0.04 * dy))


class JewelCut(Game):
    """Огранка на гранильном станке (вид сбоку): шлифовальный диск, камень на оправке, мачта с квадрантом.
    Сначала низ камня (павильон), затем камень переворачивают на оправке (F) и гранят верх: грани короны и
    площадку. Угол оправки — на глаз (W/S, колесо; Shift — точнее), индекс — делительное колесо (A/D, держать —
    крутится), опускать — Пробел (держать; мышь — для лупы и кнопок): касание — сопротивление и стачивание. Пунктир — цель: при верных
    угле и индексе ложится вдоль диска. Enter/ПКМ — грань готова. Справа — лупа (видна гранимая сторона)
    и схема огранки. Сложность — число граней; сложнее — выше предел качества."""
    title = "Огранка"
    HINTS = {"choose": "выберите огранку: клик или клавиша 1–9 · колесо — прокрутка",
             "plan": "разметка: мышь — крутить кристалл, колесо — размер камня, WASD — сдвиг, Enter — на станок",
             "cut": "W/S — угол, A/D — индекс, Пробел — к диску, Enter/ПКМ — грань готова, F — перевернуть"}

    @property
    def hint(self):
        return self.HINTS.get(self.phase, self.HINTS["cut"])
    area_size = (1120, 520)
    wide = True                                 # сцена — на всю ширину и высоту окна (не колонка 1280×800)
    click_press = False                         # ЛКМ не опускает камень (только Пробел): мышь — для лупы и кнопок
    TOL_ANG, TOL_DEPTH, GRIND = 4.5, 6.0, 26.0
    R = 100.0

    FEEDS = (0.25, 0.5, 1.0, 1.6, 2.4)          # рычаг подачи: скорость опускания (и нажим)
    FEED_NAMES = ("очень медленно", "медленно", "обычно", "быстро", "очень быстро")

    def __init__(self, seed=None, diff=1, rough=None, known=None, xd=None, lenses=(), disks=None, autofocus=False):
        super().__init__(seed)
        self.diff = max(0, min(3, diff))
        self.color = (110, 170, 240)
        self.phase = "choose"
        self.cuts = [c for c in CUTS if known is None or c["id"] in known] or [CUTS[0]]
        self.rough = rough                      # свой камень: разметка, примеси, масса
        self.xd = xd
        self.plan = None
        self.incl = []                          # примеси в осях камня (на станке)
        self.S = 1.1                            # пикселей на единицу камня на станке (крупный камень — крупнее)
        self.mm = None                          # миллиметров на единицу камня
        self.vol_rough = None                   # объём кристалла в единицах камня (для карат)
        self.caxis = (0.0, 0.0, 1.0)
        self.silk = 0.0
        self.split = None                       # раскол по трещине: индекс трещины в камне
        self.cf = None                          # окно камня в карте оттенков вида (после разметки)
        self.near_crack = False
        # лупа между игроком и диском: линзы (кратности складываются), фокус — расстояние до камня
        self.lenses = [(t, GM.LOUPE_BY_ID[t][2]) for t in lenses if t in GM.LOUPE_BY_ID]
        self.lens_in = [True] * len(self.lenses)
        self.loupe_on = bool(self.lenses)
        self.loupe_xy = None                    # центр лупы относительно поля игры (двигают за ручку)
        self.loupe_d = 70.0                     # мм от камня
        self.loupe_drag = None
        self.loupe_flip = (False, False)        # ручка — от ближнего края (зеркально)
        self.loupe_r = 0
        self.loupe_rim = 0
        self.af = bool(autofocus and self.lenses)     # автофокус лупы (часовой механизм, у бродячего ювелира)
        self.af_on = self.af
        self.af_rect = None
        self.loupe_ears = []
        self.loupe_handle = None
        # подача (Z/X, рычаг) и шлифовальные диски (C, клик): грубый — быстро, но грань в царапинах
        self.feed = 2
        self.feed_rects = []
        self.disks = [d for d in (disks or [GM.START_DISK]) if d in GM.DISK_BY_ID] or [GM.START_DISK]
        self.disk = GM.START_DISK if GM.START_DISK in self.disks else self.disks[0]
        self.disk_rects = []
        self.finish_of = {}                     # грань → чистота диска, которым её доводили последним
        self._touch = 0.0
        self.cut = None
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
        c = self.cuts[i]
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
                                    "sup": GM.support(c.get("outline"), math.tau * idx / NOTCHES),
                                    "dial": idx if side == "P" else (-idx) % NOTCHES})
        self.n = len(self.facets)
        self.scores = [None] * self.n
        if self.rough is not None:               # свой камень: ровная заготовка, её режет форма кристалла
            self.stone = G3.make_stone(None, self.R, c.get("outline"), chips=False)
        else:
            self.stone = G3.make_stone(self.rng, self.R, c.get("outline"))
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
        self.theta = self.facets[0]["ang"] + self.rng.choice((-7, 7))
        if self.rough is not None:
            self.plan = Plan(self, self.rough)
            self.phase = "plan"
        else:
            self.phase = "cut"

    def start_cut(self):
        """Разметка готова: заготовка = ровная заготовка ∩ кристалл; примеси — в осях камня."""
        pl = self.plan
        s = pl.s()
        if s <= 1e-6:
            self.flash.append(["Контур не помещается в камень — сдвиньте его", (240, 170, 110), 1.4])
            return False
        stone = self.stone
        for n, d in pl.planes:
            mn = _mv(pl.m, n)
            stone = G3.clip(stone, pl.qt(mn), (d - G3.dot(mn, pl.o)) / s, "rough") or stone
        self.stone = stone
        planes = [(f["n"], G3.dot(f["n"], f["pts"][0])) for f in stone if f["pts"]]
        self.incl = []
        for k, (si, _) in enumerate(pl.stone_incl(s)):
            if all(G3.dot(n, si["p"]) - off <= si["r"] * 0.3 for n, off in planes):
                si["src"] = si.pop("i", k)
                self.incl.append(si)
        self.vol_rough = pl.vol / s ** 3
        self.cf = pl.cf_stone(s)
        self.caxis = pl.axis()
        self.silk = pl.silk()
        self.mm = pl.mm_per_unit() * s
        dia = 2 * self.R * self.mm
        self.S = 1.1 * max(0.6, min(1.35, dia / 6.5))
        self.phase = "cut"
        return True

    # --- лупа ---
    def mag(self):
        return sum(m for (t, m), on in zip(self.lenses, self.lens_in) if on) or 1

    def focal(self):
        """Фокусное расстояние набора линз, мм (лупа ×M — 250/M мм)."""
        return 250.0 / self.mag()

    def blur(self):
        """0 — резко, 1 — совсем мутно; сильнее стекло — уже зона резкости."""
        m = self.mag()
        if m <= 1:
            return 0.0
        return min(1.0, abs(self.loupe_d - self.focal()) / (40.0 / m))

    def toggle_lens(self, i):
        if 0 <= i < len(self.lenses):
            self.lens_in[i] = not self.lens_in[i]

    def focus(self, dy):
        self.af_on = False                     # крутят вручную — автофокус выключается (АФ — включить)
        step = (0.1 if self._fine() else max(0.3, self.loupe_d * 0.03))      # Shift — тонкая подстройка
        self.loupe_d = max(8.0, min(160.0, self.loupe_d - dy * step))

    def loupe_pointer(self, ev, rect):
        if not self.loupe_on or self.loupe_xy is None:
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, er in enumerate(self.loupe_ears):
                if er.collidepoint(ev.pos):
                    self.toggle_lens(i)
                    return True
            if self.af_rect and self.af_rect.collidepoint(ev.pos):
                self.af_on = not self.af_on
                return True
            cx, cy = rect.x + self.loupe_xy[0], rect.y + self.loupe_xy[1]
            dist = math.hypot(ev.pos[0] - cx, ev.pos[1] - cy)
            rim = getattr(self, "loupe_rim", 0) or self.loupe_r * 1.3
            on_rim = self.loupe_r and self.loupe_r * 0.94 <= dist <= rim         # монокль: за любую часть оправы
            if (self.loupe_handle and self.loupe_handle.collidepoint(ev.pos)) or on_rim:
                self.loupe_drag = (ev.pos[0] - cx, ev.pos[1] - cy)
                return True
        if ev.type == pygame.MOUSEMOTION and self.loupe_drag:
            x = max(40, min(rect.w - 40, ev.pos[0] - rect.x - self.loupe_drag[0]))
            y = max(40, min(rect.h - 40, ev.pos[1] - rect.y - self.loupe_drag[1]))
            self.loupe_xy = (x, y)
            return True
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.loupe_drag:
            self.loupe_drag = None
            return True
        return False

    # --- подача и диски ---
    def feed_k(self):
        """Скорость подачи: положение рычага; Shift — ещё в 10 раз медленнее (тонкая доводка под лупой)."""
        return self.FEEDS[self.feed] * (0.1 if self._fine() else 1.0)

    def set_feed(self, i):
        self.feed = max(0, min(len(self.FEEDS) - 1, i))

    def disk_info(self):
        return GM.DISK_BY_ID[self.disk]

    def next_disk(self):
        i = self.disks.index(self.disk)
        self.disk = self.disks[(i + 1) % len(self.disks)]
        self._touch = 0.0

    def back_to_choose(self):
        if self.phase == "plan":
            self.phase = "choose"
            self.plan = None

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
        if f["ang"] == 0:                        # площадка (у низа — плоское дно или калетта)
            h = g + (1 - f["ratio"]) * R * math.tan(math.radians(f["main"]))
            return n, h
        ph = math.tau * f["index"] / NOTCHES
        sup = f.get("sup", 1.0)                  # фигурный контур: рундист в этом направлении ближе
        r = R * f["ratio"] * sup
        z = g + (1 - f["ratio"]) * R * sup * math.tan(math.radians(f["main"]))
        pt = (r * math.cos(ph), r * math.sin(ph), f["side"] * z)
        return n, G3.dot(n, pt)

    def click(self, pos):
        if self.phase == "plan" and getattr(self, "plan_btn", None) and self.plan_btn.collidepoint(pos):
            self.start_cut()
            return True
        if self.phase == "plan":
            return True
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
        """Мышь в осмотре — вращать камень; клик по кнопке «Осмотреть» — снять камень; в разметке — крутить
        кристалл."""
        if self.phase == "plan" and self.plan is not None:
            pl = self.plan
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and rect.collidepoint(ev.pos):
                if getattr(self, "plan_btn", None) and self.plan_btn.collidepoint(ev.pos):
                    self.start_cut()
                    return True
                pl.drag = ev.pos
                return True
            if ev.type == pygame.MOUSEMOTION and pl.drag:
                pl.turn(ev.pos[0] - pl.drag[0], ev.pos[1] - pl.drag[1])
                pl.drag = ev.pos
                return True
            if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and pl.drag:
                pl.drag = None
                return True
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.inspect_btn and \
                self.inspect_btn.collidepoint(ev.pos):
            self.toggle_inspect()
            return True
        if self.inspect is None and self.phase == "cut" and self.loupe_pointer(ev, rect):
            return True
        if self.inspect is None and self.phase == "cut" and ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, fr in enumerate(self.feed_rects):          # рычаг подачи: клик по положению
                if fr.collidepoint(ev.pos):
                    self.set_feed(i)
                    return True
            for d, dr in self.disk_rects:                     # диск: клик в панели
                if dr.collidepoint(ev.pos):
                    self.disk = d
                    self._touch = 0.0
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
        if self.phase == "choose":                  # много огранок — прокрутка сетки
            rows, vis = getattr(self, "choose_rows", 1), getattr(self, "choose_vis", 1)
            self.choose_top = max(0, min(rows - vis, getattr(self, "choose_top", 0) - dy))
            return
        if self.phase == "plan" and self.plan is not None:
            self.plan.wheel(dy)
            return
        if self.inspect is not None:
            self.inspect.wheel(dy)
            return
        if self.phase == "cut" and not self.done:
            if self.loupe_on:                       # колесо — фокус лупы (угол — W/S)
                self.focus(dy)
            else:
                self.theta = max(0.0, min(80.0, self.theta + dy * (0.25 if self._fine() else 1.0)))

    def key(self, k):
        if self.phase == "choose":                  # 1–9 — по видимым карточкам (сетка прокручивается)
            i = getattr(self, "choose_top", 0) * getattr(self, "choose_cols", 1) + k - pygame.K_1
            if pygame.K_1 <= k <= pygame.K_9 and i < len(self.cuts):
                self.choose(i)
                return True
            if k in (pygame.K_DOWN, pygame.K_UP, pygame.K_PAGEDOWN, pygame.K_PAGEUP):
                self.wheel(1 if k in (pygame.K_UP, pygame.K_PAGEUP) else -1)
                return True
            return False
        if self.phase == "plan":
            mv = {pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0), pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
                  pygame.K_w: (0, -1), pygame.K_UP: (0, -1), pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1)}
            if k in mv:
                self.plan.move(*mv[k])
                return True
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.start_cut()
                return True
            if k == pygame.K_r:
                self.plan.m = self.plan.upright()
                self.plan.o = [0.0, 0.0, 0.0]
                return True
            if k == pygame.K_BACKSPACE:
                self.back_to_choose()
                return True
            return True
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
        if k == pygame.K_z:                                     # рычаг подачи
            self.set_feed(self.feed - 1)
            return True
        if k == pygame.K_x:
            self.set_feed(self.feed + 1)
            return True
        if k == pygame.K_c and len(self.disks) > 1:             # сменить диск
            self.next_disk()
            return True
        if pygame.K_1 <= k <= pygame.K_4 and self.lenses:      # линзы: вставить / вынуть
            self.toggle_lens(k - pygame.K_1)
            return True
        if k == pygame.K_l and self.lenses:
            self.loupe_on = not self.loupe_on
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

    def can_abort(self):
        """Ещё ни одной готовой грани — можно уйти, камень останется необработанным."""
        return self.split is None and (self.phase in ("choose", "plan") or all(x is None for x in self.scores))

    def stop(self):
        if self.phase == "choose":
            self.choose(0)
        if self.phase == "plan":
            self.start_cut()
            self.phase = "cut"
        self.scores = [x if x is not None else 0.0 for x in self.scores]
        self.finish()

    def finish(self):
        self.done = True
        if self.cut and self.cut.get("dome") and self.split is None:      # кабошон: та же форма, кромки
            self.stone = G3.smooth(G3.polished(self.stone))                # граней скруглены полировкой

    def inside(self, inc, margin=0.3):
        return all(G3.dot(f["n"], inc["p"]) - G3.dot(f["n"], f["pts"][0]) <= inc["r"] * margin
                   for f in self.stone if f["pts"])

    # --- итог: караты, примеси, звезда ---
    def final_ct(self):
        if self.vol_rough is None or not self.rough:
            return None
        return round(self.rough["size"] * G3.volume(self.stone) / self.vol_rough, 2)

    def final_incl(self):
        if self.rough is None:
            return None
        return [{k: v for k, v in i.items() if k not in ("src", "i")} for i in self.incl if self.inside(i)]

    def cfield(self):
        """Оттенки для отрисовки (None — однотонный камень без своего кристалла)."""
        if self.cf is None or self.rough is None:
            return None
        return {"gid": self.rough["id"], "col": self.rough.get("col", 0.5), **self.cf}

    def final_colors(self):
        if self.cf is None or self.rough is None:
            return None
        return cf_stats(self.rough["id"], self.cf, inside_points(self.stone, 240))

    def final_star(self):
        if not (self.cut and self.cut.get("dome")):
            return 0.0
        done = [x for x in self.scores if x is not None]
        q = sum(done) / max(1, self.n)
        return round(self.silk * abs(self.caxis[2]) ** 6 * q, 3)

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
        sc *= self.finish_of.get(k, GM.DISK_BY_ID[GM.START_DISK][3])   # царапины грубого диска
        self.scores[k] = round(sc, 3)
        self.flash.append([f"Грань {k + 1}: {sc * 100:.0f}%" + (" · не тот индекс" if ie else ""),
                           (150, 230, 150) if sc >= 0.6 else (240, 170, 110), 1.2])
        self.h = self.h_max
        self.stone = G3.polished(self.stone)       # грань готова — полировка: начинает играть светом
        self._mass = self.calc_mass()
        if all(x is not None for x in self.scores):
            self.finish()
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

    def ct_now(self):
        """Караты камня на станке сейчас (свой камень)."""
        if self.vol_rough is None:
            return None
        return self.rough["size"] * G3.volume(self.stone) / self.vol_rough

    @property
    def score(self):
        if self.phase != "cut" or self.split is not None:
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
        self.spin += dt * 10 * (0.3 + 0.7 * self.FEEDS[self.feed])   # диск крутится по рычагу подачи
        if self.af_on and self.loupe_on:                               # автофокус: лупа сама ловит резкость
            self.loupe_d += (self.focal() - self.loupe_d) * min(1.0, dt * 6)
        want_a = 0.0 if self.side > 0 else math.pi      # переворот — плавный поворот на оправке
        if self.flip_a != want_a:
            step = dt * 4.0
            self.flip_a = want_a if abs(want_a - self.flip_a) <= step else \
                self.flip_a + (step if want_a > self.flip_a else -step)
        if self.inspect is not None:
            self.inspect.update(dt)
        if self.done or self.phase != "cut":
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
        fk = self.feed_k()
        gentle = fk <= self.FEEDS[1]                 # медленная подача — бережно, трещине не страшно
        self.near_crack = False
        if self.hold:
            want = self.h - 150 * fk * dt
            if want < ext:
                self.contact = min(1.0, self.contact + dt * 6)
                press = 0.45 + 0.55 * min(fk, 1.6)       # нажим: быстрее подача — быстрее стачивает
                want = max(want, min(self.h, ext) - self.GRIND * self.disk_info()[2] * press * dt)
                self._touch += dt
                if self._touch > 0.12:                   # грань доведена этим диском
                    self.finish_of[self.active] = self.disk_info()[3]
                f = self.facets[self.active]
                if self.crack_check(want, gentle, dt):
                    return
                self.stone = G3.clip(self.stone, self.n_vec(), want, "frost",
                                     grit=GM.GRIT.get(self.disk, 0.4)) or self.stone
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
            self._touch = 0.0
        for s_ in self.sparks:
            s_[0] += s_[2] * dt
            s_[1] += s_[3] * dt
            s_[3] += 700 * dt
            s_[4] -= dt
        self.sparks = [s_ for s_ in self.sparks if s_[4] > 0]

    def crack_check(self, want, gentle, dt):
        """Диск идёт рядом с трещиной: с нажимом — камень может расколоться (Shift — бережно, без риска)."""
        n = self.n_vec()
        for i in self.incl:
            if i["k"] != "feather":
                continue
            if abs(G3.dot(n, i["p"]) - want) < i["r"] * 1.4 + 3:
                self.near_crack = True
                if not gentle and self.rng.random() < dt * 0.9 * max(0.5, self.feed_k() - 0.5):
                    self.split = i.get("src", 0)
                    self.hold = False
                    self.scores = [0.0 if x is None else x for x in self.scores]
                    self.flash.append(["Камень раскололся по трещине!", (240, 110, 100), 2.5])
                    self.note = "Раскол: остался меньший кусок"
                    self.done = True
                    return True
        return False

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
        elif self.phase == "plan":
            JW.draw_plan(self, surf, rect)
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
