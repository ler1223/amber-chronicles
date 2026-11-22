"""Живое поле боя (prompts_expedition.md, DC3; квиз 2026-11-19): детали болота и движение вокруг.

Включается сценой (сейчас — карточный «Спуск», deck/ui.py): view.life = FieldLife(seed); без него поле
рисуется как раньше. Арт — assets/field/ (tools/import_field_art.py), 1 пиксель арта = 1 пиксель плоской карты
(64 на клетку).

  сор на земле, кувшинки, ряска, кромки берега — один раз «впекаются» в плоскую карту земли боя;
  трава, цветы, камыши — стоят на земле (билборды по глубине) и качаются от ветра с порывами;
  вороны сидят у поля и взлетают от шума боя рядом; лягушки на кувшинках; рыба выпрыгивает из воды;
  стрекозы, мотыльки, мошкара над водой, светлячки, листья с деревьев, пролетающие стайки птиц;
  тени облаков и птиц ползут по земле, круги расходятся по воде, над дальним краем дрейфует туман.
Ничего из этого не влияет на игру.
"""
import math
import os
import random

import pygame

from ui import projection as P

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "assets", "field")
WET = ("water",)
BLOCK = ("chasm", "lava")
LAND_DECALS = ["pebbles", "gravel", "mossy_stone", "two_stones", "tiny_pebbles", "branch", "twigs", "log_chunk",
               "chips", "skull", "bones", "moss", "moss", "clover", "leaves_rust", "leaves_green", "roots",
               "mushroom_ring", "mud", "puddle", "peat", "dry_sedge", "feathers", "footprints", "slab"]
BOARD_DECALS = ["pebbles", "tiny_pebbles", "twigs", "chips", "moss", "clover", "leaves_rust", "leaves_green",
                "feathers", "gravel"]
WATER_DECALS = ["lily", "lily_two", "lily_white", "lily_pink", "duckweed", "duckweed_trail", "leaves_float",
                "algae", "bubbles", "reed_stubs", "log_float", "drowned_branch", "stone_sunk"]
SHORE_DECALS = ["shore_mud", "shore_roots", "stone_moss"]
GRASS = ["grass_s", "grass_m", "grass_s", "grass_m", "grass_dry", "grass_wide", "blades", "weed", "clover"]
TALL = ["grass_tall", "sedge", "fern_young", "fern", "horsetail", "thistle", "bush_round", "bush_dead"]
FLOWERS = ["flowers_white", "marigold", "loosestrife", "bell", "forgetmenot", "berries"]
REEDS = ["reeds", "cattails", "reeds_bent", "reeds_tall", "sedge"]
ANIMS = {"crow_fly": 6, "crow_takeoff": 4, "bird": 4, "dragonfly": 2, "moth": 3, "frog": 2, "fish": 4}
_imgs = {}


def img(kind, name):
    key = (kind, name)
    if key not in _imgs:
        p = os.path.join(DIR, kind, f"{name}.png")
        try:
            _imgs[key] = pygame.image.load(p).convert_alpha() if pygame.display.get_surface() else pygame.image.load(p)
        except (pygame.error, FileNotFoundError):
            _imgs[key] = None
    return _imgs[key]


def frames(anim):
    return [f for f in (img("critters", f"{anim}_{k}") for k in range(ANIMS[anim])) if f is not None]


def available():
    return os.path.isdir(os.path.join(DIR, "plants"))


def sway_frames(src, n=7, amp=3):
    """Кадры покачивания: верх смещается сильнее низа (основание стоит)."""
    w, h = src.get_size()
    out = []
    for i in range(n):
        s = (i - (n - 1) / 2) / ((n - 1) / 2) * amp
        f = pygame.Surface((w + 2 * amp, h), pygame.SRCALPHA)
        for y in range(h):
            dx = round(s * (1 - y / max(1, h - 1)) ** 1.5)
            f.blit(src, (amp + dx, y), (0, y, w, 1))
        out.append(f)
    return out


class FieldLife:
    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.seed = seed
        self.t = 0.0
        self.baked = set()
        self.ready = False
        self.plants = []          # (gx, gy, кадры, фаза)
        self.crows = []           # {"gx","gy","gz","st","t","dir","f"}
        self.frogs = []           # (gx, gy, фаза)
        self.flies = []           # стрекозы/мотыльки: {"kind","gx","gy","gz","tx","ty","t"}
        self.swarms = []          # мошкара: (gx, gy, [точки])
        self.bugs = []            # светлячки
        self.leaves = []
        self.trees = []
        self.water = []
        self.land = []
        self.flock = None
        self.next_flock = 6.0
        self.fish = None
        self.next_fish = 4.0
        self.ripples = []         # (gx, gy, возраст)
        self.clouds = []
        self.fog = []
        self._sway = {}
        self._cloud = None

    # ---------- расстановка ----------

    def noise(self, x, y, scale):
        """Плавный шум 0..1 (значения в узлах решётки, билинейно) — пятна травы и цветов."""
        def h(i, j):
            return random.Random(hash((i, j, self.seed)) & 0xFFFFFFFF).random()
        fx, fy = x / scale, y / scale
        i, j = math.floor(fx), math.floor(fy)
        u, v = fx - i, fy - j
        u, v = u * u * (3 - 2 * u), v * v * (3 - 2 * v)
        a = h(i, j) + (h(i + 1, j) - h(i, j)) * u
        b = h(i, j + 1) + (h(i + 1, j + 1) - h(i, j + 1)) * u
        return a + (b - a) * v

    def setup(self, view, combat):
        if not available():
            return
        painter = view.painter
        tm, names = painter._terrain_map(combat)
        ch, cw = tm.shape
        grid = combat.grid
        r = self.rng
        decals = []
        for cy in range(ch):
            for cx in range(cw):
                gx, gy = cx - P.MARGIN_L, cy - P.MARGIN_T
                t = names[tm[cy, cx]]
                on_board = 0 <= gx < grid.w and 0 <= gy < grid.h
                if t in BLOCK:
                    continue
                if on_board:
                    c = grid.cells[(gx, gy)]
                    if not c.passable or c.cover or c.deco:
                        continue
                if t in WET:
                    self.water.append((gx, gy))
                    if r.random() < (0.45 if not on_board else 0.25):
                        decals.append(("water", r.choice(WATER_DECALS), gx + r.uniform(0.2, 0.8), gy + r.uniform(0.2, 0.8)))
                    continue
                self.land.append((gx, gy, on_board))
                shore = any(0 <= cy + dy < ch and 0 <= cx + dx < cw and names[tm[cy + dy, cx + dx]] in WET
                            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                near = -1 <= gx <= grid.w and -1 <= gy <= grid.h
                if r.random() < (0.22 if on_board else 0.5):
                    pool = BOARD_DECALS if on_board else LAND_DECALS
                    decals.append(("ground", r.choice(pool), gx + r.uniform(0.15, 0.85), gy + r.uniform(0.15, 0.85)))
                # трава пятнами (низкочастотный шум): куртины и проплешины; на доске — редкие низкие кустики
                # по краям клеток (не мешать читать бой), у доски — пореже, дальше — гуще и выше
                dens = self.noise(gx, gy, 3.5)
                if on_board:
                    n = 1 if dens > 0.62 and r.random() < 0.5 else 0
                elif near:
                    n = 1 if dens > 0.5 and r.random() < 0.6 else 0
                else:
                    n = 0 if dens < 0.42 else (1 if dens < 0.6 else r.choice((1, 2, 2)))
                if shore and not on_board and r.random() < 0.7:
                    n = max(n, 1)
                flowers = self.noise(gx + 40, gy + 40, 2.5) > 0.7        # цветы — редкими полянками
                for _ in range(n):
                    if shore and r.random() < 0.7:
                        name = r.choice(REEDS)
                    elif on_board or near:
                        name = r.choice(GRASS)
                    elif flowers and r.random() < 0.6:
                        name = r.choice(FLOWERS)
                    else:
                        name = r.choice(GRASS + GRASS + TALL)
                    px, py = gx + r.uniform(0.05, 0.95), gy + r.uniform(0.15, 0.95)
                    if on_board:                                    # на доске — по краям клетки, не в центре
                        px, py = gx + r.choice((r.uniform(0.02, 0.2), r.uniform(0.8, 0.98))), gy + r.uniform(0.7, 0.98)
                    self.plants.append((px, py, name, r.uniform(0, 6.3), r.random() < 0.5))
        self.decals = decals
        self.trees = [(gx, gy) for gx, gy, kind, *_ in painter.props(combat) if kind in ("tree", "deadtree")]
        far = [p for p in self.land if not p[2] and -3 <= p[1] <= -1 and -2 <= p[0] <= grid.w + 1]
        for gx, gy, _ in r.sample(far, min(3, len(far))):          # вороны у дальнего края
            self.crows.append({"gx": gx + 0.5, "gy": gy + 0.6, "gz": 0.0, "st": "sit", "t": r.uniform(0, 5),
                               "dir": r.choice((-1, 1)), "f": False})
        lily = [(x, y) for kind, name, x, y in decals if name.startswith("lily")]
        for gx, gy in r.sample(lily, min(2, len(lily))):
            self.frogs.append((gx, gy, r.uniform(0, 10)))
        wl = self.water
        for _ in range(min(2, len(wl))):
            gx, gy = r.choice(wl)
            self.flies.append({"kind": "dragonfly", "gx": gx + 0.5, "gy": gy + 0.5, "gz": 0.6, "tx": gx, "ty": gy,
                               "t": r.uniform(0, 3)})
        for _ in range(min(3, len(wl))):
            gx, gy = r.choice(wl)
            pts = [(r.uniform(-0.3, 0.3), r.uniform(-0.2, 0.2), r.uniform(0.3, 0.9), r.uniform(0, 6.3))
                   for _ in range(14)]
            self.swarms.append((gx + 0.5, gy + 0.5, pts))
        margin = [p for p in self.land if not p[2]]
        for _ in range(2):
            if margin:
                gx, gy, _ = r.choice(margin)
                self.flies.append({"kind": "moth", "gx": gx + 0.5, "gy": gy + 0.5, "gz": 0.4, "tx": gx, "ty": gy,
                                   "t": r.uniform(0, 3)})
        for _ in range(10):
            if margin:
                gx, gy, _ = r.choice(margin)
                self.bugs.append([gx + r.random(), gy + r.random(), r.uniform(0.2, 0.8), r.uniform(0, 6.3)])
        for _ in range(3):
            self.clouds.append([r.uniform(0, P.FLAT_W), r.uniform(0, P.FLAT_H), r.uniform(18, 34), r.uniform(0.8, 1.4)])
        for _ in range(4):
            self.fog.append([r.uniform(-200, 1400), r.uniform(-2.8, -0.2), r.uniform(10, 22), r.uniform(220, 420)])
        self.ready = True

    def bake(self, view, combat):
        """Сор, кувшинки, кромки берега — в плоскую карту земли (один раз на построенную землю)."""
        if not self.ready:
            return
        base = view.painter.base(combat)
        if id(base) in self.baked:
            return
        self.baked.add(id(base))
        for kind, name, gx, gy in self.decals:
            im = img(kind, name)
            if im is None:
                continue
            fx, fy = P.ground_to_flat(gx, gy)
            k = P.FLAT / 64                                   # 64 пикселя арта на клетку
            if abs(k - 1) > 0.01:
                im = pygame.transform.scale(im, (max(1, round(im.get_width() * k)), max(1, round(im.get_height() * k))))
            base.blit(im, (round(fx - im.get_width() / 2), round(fy - im.get_height() / 2)))

    # ---------- время ----------

    def wind(self):
        """Ветер: плавное качание и редкие порывы."""
        t = self.t
        gust = max(0.0, math.sin(t * 0.23) * math.sin(t * 0.61 + 1.3)) ** 2
        return 0.35 * math.sin(t * 1.1) + 1.4 * gust

    def on_event(self, e, view):
        """Шум боя рядом: вороны поблизости взлетают."""
        if e.get("t") not in ("damage", "death", "collision"):
            return
        u = e.get("unit")
        if u is None:
            return
        gx, gy = view.ground_pos(u)
        for c in self.crows:
            if c["st"] == "sit" and math.hypot(c["gx"] - gx, c["gy"] - gy) < 5.5:
                c["st"], c["t"] = "takeoff", 0.0

    def update(self, dt, view, combat):
        if not self.ready:
            return
        self.bake(view, combat)
        self.t += dt
        r = self.rng
        for c in self.crows:
            c["t"] += dt
            if c["st"] == "sit" and c["t"] > 25 and r.random() < dt * 0.02:
                c["st"], c["t"] = "takeoff", 0.0                     # и сами иногда улетают
            elif c["st"] == "takeoff" and c["t"] > 0.45:
                c["st"], c["t"] = "fly", 0.0
            elif c["st"] == "fly":
                c["gx"] += c["dir"] * dt * 2.6
                c["gy"] -= dt * 0.9
                c["gz"] += dt * 1.4
                if c["gz"] > 7:
                    c["st"], c["t"] = "gone", 0.0
            elif c["st"] == "gone" and c["t"] > 18:                  # прилетела обратно — сидит
                c["gx"], c["gy"], c["gz"], c["st"], c["t"] = c["gx"] - c["dir"] * 18 * 0.0 + r.uniform(-2, 2), \
                    r.uniform(-2.6, -1.2), 0.0, "sit", 0.0
                c["gx"] = r.uniform(-1, combat.grid.w + 1)
        for f in self.flies:                                         # стрекозы и мотыльки — к случайным точкам
            f["t"] -= dt
            if f["t"] <= 0:
                pool = self.water if f["kind"] == "dragonfly" and self.water else [(x, y) for x, y, _ in self.land]
                if pool:
                    tx, ty = r.choice(pool)
                    f["tx"], f["ty"] = tx + r.random(), ty + r.random()
                f["t"] = r.uniform(1.5, 4.0) if f["kind"] == "dragonfly" else r.uniform(0.6, 1.6)
            sp = 2.2 if f["kind"] == "dragonfly" else 0.8
            dx, dy = f["tx"] - f["gx"], f["ty"] - f["gy"]
            d = math.hypot(dx, dy)
            if d > 0.05:
                f["gx"] += dx / d * min(d, sp * dt)
                f["gy"] += dy / d * min(d, sp * dt)
        self.next_flock -= dt
        if self.flock is None and self.next_flock <= 0 and r.random() < 0.6:
            d = r.choice((-1, 1))
            gy = r.uniform(-2.5, combat.grid.h - 1)
            self.flock = {"d": d, "gx": -6 if d > 0 else combat.grid.w + 6, "gy": gy,
                          "birds": [(r.uniform(-1.2, 0), r.uniform(-0.6, 0.6), r.uniform(0, 3)) for _ in range(r.randint(3, 6))]}
        if self.next_flock <= 0:
            self.next_flock = r.uniform(18, 40)
        if self.flock:
            self.flock["gx"] += self.flock["d"] * dt * 3.2
            if not -9 < self.flock["gx"] < combat.grid.w + 9:
                self.flock = None
        self.next_fish -= dt
        if self.fish is None and self.next_fish <= 0 and self.water:
            gx, gy = r.choice(self.water)
            self.fish = [gx + r.uniform(0.2, 0.8), gy + r.uniform(0.3, 0.8), 0.0]
            self.ripples.append([self.fish[0], self.fish[1], 0.0])
            self.next_fish = r.uniform(5, 12)
        if self.fish:
            self.fish[2] += dt
            if self.fish[2] > 0.7:
                self.ripples.append([self.fish[0] + 0.15, self.fish[1], 0.0])
                self.fish = None
        if self.water and r.random() < dt * 0.6:                     # капли, жучки — редкие круги на воде
            gx, gy = r.choice(self.water)
            self.ripples.append([gx + r.random(), gy + r.random(), 0.0])
        for rp in self.ripples:
            rp[2] += dt
        self.ripples = [rp for rp in self.ripples if rp[2] < 1.8]
        if self.trees and r.random() < dt * 0.5:                     # лист с дерева
            gx, gy = r.choice(self.trees)
            self.leaves.append([gx + r.uniform(-0.5, 0.5), gy, r.uniform(1.8, 2.8), r.uniform(0, 6.3),
                                r.choice(((176, 96, 40), (200, 150, 60), (120, 130, 50)))])
        for lf in self.leaves:
            lf[2] -= dt * 0.35
            lf[0] += dt * (0.25 + 0.3 * self.wind())
            lf[3] += dt
        self.leaves = [lf for lf in self.leaves if lf[2] > 0]
        for c in self.clouds:
            c[0] += dt * c[2]
            if c[0] > P.FLAT_W + 400:
                c[0] = -400
        for f in self.fog:
            f[0] += dt * f[2] * 0.4
            if f[0] > 1500:
                f[0] = -500

    # ---------- рисование ----------

    def draw_ground(self, ov):
        """На плоской карте (слой подсветок): тени облаков и птиц, круги на воде."""
        if not self.ready:
            return
        if self._cloud is None:
            w, h = 520, 330
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            for i in range(40, 0, -1):
                k = i / 40
                pygame.draw.ellipse(s, (8, 14, 10, int(44 * (1 - k) ** 0.8)),
                                    pygame.Rect(w * (1 - k) / 2, h * (1 - k) / 2, w * k, h * k))
            self._cloud = s
        for x, y, _, sc in self.clouds:
            im = self._cloud if abs(sc - 1) < 0.05 else pygame.transform.smoothscale(
                self._cloud, (int(520 * sc), int(330 * sc)))
            ov.blit(im, (x - im.get_width() / 2, y - im.get_height() / 2))
        if self.flock:
            for ox, oy, _ in self.flock["birds"]:
                fx, fy = P.ground_to_flat(self.flock["gx"] + ox + 1.2, self.flock["gy"] + oy + 1.5)
                pygame.draw.ellipse(ov, (0, 0, 0, 40), (fx - 9, fy - 4, 18, 8))
        for c in self.crows:
            if c["st"] == "fly":
                fx, fy = P.ground_to_flat(c["gx"], c["gy"] + c["gz"] * 0.3)
                pygame.draw.ellipse(ov, (0, 0, 0, max(0, 50 - int(c["gz"] * 6))), (fx - 12, fy - 5, 24, 10))
        for gx, gy, age in self.ripples:
            fx, fy = P.ground_to_flat(gx, gy)
            rr = 4 + age * 26
            a = int(150 * (1 - age / 1.8))
            pygame.draw.ellipse(ov, (210, 230, 235, a), (fx - rr, fy - rr * 0.6, 2 * rr, 1.2 * rr), 2)

    def decal_list(self):
        """Сор с земли для чёткой земли «Спуска» (deck/terrain.py): [(картинка, gx, gy)]."""
        if not self.ready:
            return []
        if getattr(self, "_decal_imgs", None) is None:
            self._decal_imgs = [(im, gx, gy) for im, gx, gy in
                                ((img(kind, name), gx, gy) for kind, name, gx, gy in self.decals) if im is not None]
        return self._decal_imgs

    def collect(self, h):
        """То же, что draw_ground, но в чёткий слой подсказок (deck/hints.py): тени облаков и птиц, круги."""
        if not self.ready:
            return
        for x, y, _, sc in self.clouds:
            gx, gy = x / P.FLAT - P.MARGIN_L, y / P.FLAT - P.MARGIN_T
            h.blob((gx, gy), 260 * sc / P.FLAT, 165 * sc / P.FLAT, (8, 14, 10), 60)
        if self.flock:
            for ox, oy, _ in self.flock["birds"]:
                h.blob((self.flock["gx"] + ox + 1.2, self.flock["gy"] + oy + 1.5), 0.14, 0.07, (0, 0, 0), 70)
        for c in self.crows:
            if c["st"] == "fly":
                h.blob((c["gx"], c["gy"] + c["gz"] * 0.3), 0.2, 0.09, (0, 0, 0), max(0, 90 - int(c["gz"] * 11)))
        for gx, gy, age in self.ripples:
            r = 0.06 + age * 0.4
            h.ring((gx, gy), r, (215, 232, 236), int(150 * (1 - age / 1.8)), 1.3, glow=False, squash=0.65)

    def world_items(self, view):
        """Стоящее на земле — в общий список по глубине: трава, вороны на земле, лягушки, рыба."""
        if not self.ready:
            return []
        out = []
        w = self.wind()
        hz = getattr(view, "height_at", None)
        if hz is not None and getattr(self, "_pz", None) is None:      # высота земли под травой — один раз
            self._pz = [hz(p[0], p[1]) for p in self.plants]
        pz = self._pz if hz is not None else None
        for i, (gx, gy, name, ph, flip) in enumerate(self.plants):
            x, y, k = P.project(gx, gy, pz[i] if pz else 0.0)
            if -60 < x < 1340 and -40 < y < 860:
                out.append((y, 0, "pix", (self._plant, (view, name, x, y, k, ph, flip, w))))
        for c in self.crows:
            if c["st"] in ("sit", "takeoff"):
                x, y, k = P.project(c["gx"], c["gy"], hz(c["gx"], c["gy"]) if hz else 0.0)
                out.append((y, 0, "pix", (self._crow_ground, (view, c, x, y, k))))
        for gx, gy, ph in self.frogs:
            x, y, k = P.project(gx, gy)
            out.append((y, 0, "pix", (self._sprite, (view, "frog", 1 if (self.t + ph) % 7 < 0.6 else 0, x, y, k, False))))
        if self.fish:
            gx, gy, a = self.fish
            x, y, k = P.project(gx, gy)
            out.append((y, 0, "pix", (self._sprite, (view, "fish", min(3, int(a / 0.7 * 4)), x, y, k, False))))
        return out

    def _plant(self, surf, view, name, x, y, k, ph, flip, w):
        key = (name, flip)
        fr = self._sway.get(key)
        if fr is None:
            src = img("plants", name)
            if src is None:
                self._sway[key] = []
                return
            if flip:
                src = pygame.transform.flip(src, True, False)
            fr = self._sway[key] = sway_frames(src)
        if not fr:
            return
        s = math.sin(self.t * 1.6 + ph) * 0.4 + w * 0.6 * (0.7 + 0.3 * math.sin(ph))
        i = max(0, min(len(fr) - 1, round((s + 1) / 2 * (len(fr) - 1))))
        im = view.scaled(fr[i], k * 80 / 64)
        surf.blit(im, (round(x - im.get_width() / 2), round(y - im.get_height() + 1)))

    def _sprite(self, surf, view, anim, i, x, y, k, flip, lift=0):
        fs = frames(anim)
        if not fs:
            return
        im = fs[i % len(fs)]
        if flip:
            im = pygame.transform.flip(im, True, False)
        im = view.scaled(im, k * 80 / 64)
        surf.blit(im, (round(x - im.get_width() / 2), round(y - im.get_height() + 1 - lift)))

    def _crow_ground(self, surf, view, c, x, y, k):
        if c["st"] == "sit":
            hop = 3 if (self.t + c["gx"]) % 6 < 0.12 else 0          # иногда подскакивает
            self._sprite(surf, view, "crow_takeoff", 0, x, y, k, c["dir"] < 0, hop)
        else:
            self._sprite(surf, view, "crow_takeoff", min(3, int(c["t"] / 0.45 * 4)), x, y, k, c["dir"] < 0)

    def draw_air(self, surf, view):
        """Поверх всего на поле: летающие, мошкара, светлячки, листья, туман."""
        if not self.ready:
            return
        t = self.t
        for c in self.crows:
            if c["st"] == "fly":
                x, y, k = P.project(c["gx"], c["gy"], c["gz"])
                self._sprite(surf, view, "crow_fly", int(t * 12), x, y, k, c["dir"] < 0)
        if self.flock:
            fs = frames("bird")
            for ox, oy, ph in self.flock["birds"]:
                x, y, k = P.project(self.flock["gx"] + ox, self.flock["gy"] + oy, 3.2 + 0.3 * math.sin(t + ph))
                if fs:
                    im = fs[int(t * 10 + ph * 3) % len(fs)]
                    if self.flock["d"] < 0:
                        im = pygame.transform.flip(im, True, False)
                    im = view.scaled(im, k * 80 / 64)
                    surf.blit(im, (round(x - im.get_width() / 2), round(y - im.get_height() / 2)))
        for f in self.flies:
            x, y, k = P.project(f["gx"], f["gy"], f["gz"] + 0.08 * math.sin(t * 7 + f["gx"]))
            anim = f["kind"]
            i = int(t * (24 if anim == "dragonfly" else 10)) % ANIMS[anim]
            self._sprite(surf, view, anim, i, x, y, k * (0.5 if anim == "dragonfly" else 0.7), f["tx"] < f["gx"])
        for gx, gy, pts in self.swarms:                               # мошкара столбиком над водой
            for ox, oy, oz, ph in pts:
                x, y, _ = P.project(gx + ox + 0.12 * math.sin(t * 3.1 + ph), gy + oy + 0.08 * math.cos(t * 2.3 + ph),
                                    oz + 0.12 * math.sin(t * 4.7 + ph * 2))
                surf.fill((24, 22, 18), (round(x), round(y), 2, 2))
        for b in self.bugs:                                           # светлячки
            b[3] += 0.016
            gx = b[0] + 0.3 * math.sin(t * 0.5 + b[3])
            gy = b[1] + 0.2 * math.cos(t * 0.4 + b[3])
            x, y, _ = P.project(gx, gy, b[2] + 0.15 * math.sin(t * 1.3 + b[3]))
            a = 0.5 + 0.5 * math.sin(t * 2.2 + b[3] * 3)
            if a > 0.25:
                g = pygame.Surface((10, 10), pygame.SRCALPHA)
                pygame.draw.circle(g, (190, 255, 120, int(70 * a)), (5, 5), 5)
                pygame.draw.circle(g, (230, 255, 170, int(230 * a)), (5, 5), 1)
                surf.blit(g, (round(x) - 5, round(y) - 5))
        for gx, gy, gz, ph, col in self.leaves:
            x, y, _ = P.project(gx + 0.15 * math.sin(ph * 2.5), gy, gz)
            surf.fill(col, (round(x), round(y), 3 if math.sin(ph * 4) > 0 else 2, 2))
        for fx, gy, a, w in self.fog:                                 # полосы тумана у дальнего края
            _, y, _ = P.project(5, gy)
            s = pygame.Surface((int(w), 26), pygame.SRCALPHA)
            for i in range(13, 0, -1):
                pygame.draw.ellipse(s, (200, 210, 205, int(a * 0.5 * (1 - i / 13))),
                                    pygame.Rect(w * (1 - i / 13) / 2, 13 * (1 - i / 13), w * i / 13, 26 * i / 13))
            surf.blit(s, (fx, y - 13))
