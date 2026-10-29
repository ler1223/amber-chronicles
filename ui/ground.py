"""Земля поля для HD-2D: плоская карта «строго сверху» (ui/projection.py) и объёмные билборды на ней.

Плоская карта собирается один раз на бой (numpy): пиксель-арт 32×32 на клетку, увеличенный ×2.
  материал главы — трава, пепел, земля склепа, снег, сухая степь, песок, мох, мокрый камень, мрамор;
  стыки рельефа слегка «плывут» по шуму — без ровных квадратов;
  вода, лава и пропасть ниже земли: у дальнего края виден обрыв-берег, по кромке — светлая губа;
  мягкая сетка — шов в один пиксель только на доске; вокруг доски — местность главы, реки и пропасти тянутся
  за край поля.
Укрытия, деревья и декор вокруг доски — стоячие билборды (рисуются вместе с юнитами, по глубине).
Без OpenGL плоская карта кладётся на плоскость здесь же (warp, numpy).
"""
import math

import numpy as np
import pygame

from ui import projection as P

L = 32                                   # логических пикселей на клетку
K = P.FLAT // L                          # во сколько раз увеличиваем


def dims():
    """Плоская карта в логических пикселях — под текущий размер доски (ui/projection.set_board)."""
    return P.FLAT_W // K, P.FLAT_H // K

STYLE = {"swamp": "grass", "forge": "ash", "crypt": "dirt", "pass": "snow", "steppe": "dry", "tomb": "sand",
         "fae": "moss", "sunken": "wet", "citadel": "marble"}
DECOR = {"grass": ["tree", "bush", "rock", "tree"], "ash": ["rock", "deadtree", "rock"],
         "dirt": ["tombstone", "deadtree", "rock"], "snow": ["pine", "rock", "pine"], "dry": ["bush", "rock"],
         "sand": ["column", "rock"], "moss": ["mushroom", "tree", "mushroom"], "wet": ["column", "rock"],
         "marble": ["column", "column", "rock"]}
LOWERED = {"water": 5, "lava": 4, "chasm": 16}       # высота обрыва-берега, логических пикселей


def _rng(seed):
    return np.random.default_rng(seed)


def vnoise(shape, cell, seed):
    """Плавный шум 0..1: случайная сетка с шагом cell, билинейно."""
    h, w = shape
    g = _rng(seed).random((h // cell + 3, w // cell + 3))
    y = np.arange(h) / cell
    x = np.arange(w) / cell
    y0, x0 = y.astype(int), x.astype(int)
    fy, fx = (y - y0)[:, None], (x - x0)[None, :]
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    c = g[y0 + 1][:, x0]
    d = g[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def _h(*v):
    """Детерминированный хэш 0..1."""
    x = 0
    for k in v:
        x = (x * 1103515245 + int(k) * 2654435761 + 12345) & 0xFFFFFFFF
    x ^= x >> 13
    x = (x * 0x5bd1e995) & 0xFFFFFFFF
    return (x ^ (x >> 15)) / 0xFFFFFFFF


class GroundPainter:
    def __init__(self, data):
        self.data = data
        self._key = None
        self._surf = None
        self._props = []
        self._warp = None
        self._water = None

    # ---------- цвета главы ----------

    def palette(self, combat):
        cfg = self.data.config["terrain"]
        pal = dict(getattr(combat, "chapter", {}).get("palette", {}))
        out = {k: np.array(pal.get(k) or v["color"], float) for k, v in cfg.items()}
        out["tree"] = np.array(pal.get("tree", (64, 104, 60)), float)
        return out

    def style(self, combat):
        return STYLE.get(combat.enc.get("chapter", "swamp"), "grass")

    def fog(self, combat):
        """Цвет дымки вдали: земля главы, разбавленная светлым воздухом."""
        g = self.palette(combat)["grass"]
        fog = g * 0.45 + np.array((150, 165, 190)) * 0.55
        if self.style(combat) in ("ash",):
            fog = g * 0.5 + np.array((120, 70, 60)) * 0.5
        if self.style(combat) in ("dirt", "moss"):
            fog = g * 0.5 + np.array((70, 70, 100)) * 0.5
        return tuple(float(v) / 255 for v in np.clip(fog, 0, 255))

    # ---------- плоская карта ----------

    def base(self, combat):
        grid = combat.grid
        # прилив временно топит клетки (base_terrain) — землю не пересобираем, вода кладётся поверх (water_layer)
        key = (combat.enc["id"], getattr(combat, "chapter", {}).get("palette") and combat.enc.get("chapter"),
               tuple(c.base_terrain or c.terrain for c in grid.cells.values()))
        if key != self._key:
            self._key = key
            self._water = None
            self._surf, self._props = self._build(combat)
        return self._surf

    def water_layer(self, combat, terrain="water"):
        """Рельеф на всю плоскую карту — для клеток, которые временно изменились: прилив (вода), каток (лёд)."""
        LW, LH = dims()
        self.base(combat)
        if self._water is None:
            self._water = {}
        if terrain not in self._water:
            n1 = vnoise((LH, LW), 24, 77)
            n3 = _rng(78).random((LH, LW))
            pal = self.palette(combat)
            Y, X = np.mgrid[0:LH, 0:LW]
            if terrain == "ice_floor":
                img = self._ice(pal["ice_floor"], n1, n3, X, Y)
            elif terrain == "lava":
                img = self._lava(n1, vnoise((LH, LW), 7, 79), n3)
            elif terrain == "stone":
                img = self._pavers(pal["stone"], n1, n3, X, Y, X % L, Y % L)
            elif terrain == "grass":
                img = self._ground(self.style(combat), pal["grass"], n1, vnoise((LH, LW), 7, 80), n3, X, Y,
                                   X % L, Y % L, 81)
            else:
                img = self._water_mat(pal["water"], n1, n3, None)
            arr = np.clip(img, 0, 255).astype(np.uint8)
            self._water[terrain] = pygame.transform.scale(pygame.surfarray.make_surface(arr.swapaxes(0, 1)),
                                                          (P.FLAT_W, P.FLAT_H))
        return self._water[terrain]

    def props(self, combat):
        self.base(combat)
        return self._props

    def _terrain_map(self, combat):
        """Рельеф всех клеток плоской карты: доска как есть, вокруг — земля главы; реки и пропасти с края доски
        тянутся за поле на пару клеток."""
        LW, LH = dims()
        grid = combat.grid
        cw, ch = LW // L, LH // L
        names = list(self.data.config["terrain"])
        idx = {n: i for i, n in enumerate(names)}
        tm = np.full((ch, cw), idx["grass"], int)
        for (x, y), c in grid.cells.items():
            t = c.base_terrain or c.terrain
            tm[y + P.MARGIN_T, x + P.MARGIN_L] = idx[t if t in idx else "grass"]
        for cy in range(ch):
            for cx in range(cw):
                bx, by = cx - P.MARGIN_L, cy - P.MARGIN_T
                if 0 <= bx < grid.w and 0 <= by < grid.h:
                    continue
                nx, ny = min(max(bx, 0), grid.w - 1), min(max(by, 0), grid.h - 1)
                d = max(abs(nx - bx), abs(ny - by))
                t = grid.cells[(nx, ny)].base_terrain or grid.cells[(nx, ny)].terrain
                if t in ("water", "chasm", "lava") and d <= 3 and _h(cx, cy, 7) < 0.85 - 0.2 * d:
                    tm[cy, cx] = idx[t]
        return tm, names

    def _build(self, combat):
        LW, LH = dims()
        pal = self.palette(combat)
        style = self.style(combat)
        tm, names = self._terrain_map(combat)
        seed = sum(ord(ch) for ch in combat.enc["id"])
        Y, X = np.mgrid[0:LH, 0:LW]
        n1 = vnoise((LH, LW), 24, seed)
        n2 = vnoise((LH, LW), 7, seed + 1)
        n3 = _rng(seed + 2).random((LH, LW))
        # стыки рельефа плывут по шуму на ±3 пикселя
        jx = ((vnoise((LH, LW), 6, seed + 3) - 0.5) * 7).astype(int)
        jy = ((vnoise((LH, LW), 6, seed + 4) - 0.5) * 7).astype(int)
        cx = np.clip((X + jx) // L, 0, tm.shape[1] - 1)
        cy = np.clip((Y + jy) // L, 0, tm.shape[0] - 1)
        ter = tm[cy, cx]
        img = np.zeros((LH, LW, 3), float)
        lx, ly = X % L, Y % L
        for i, name in enumerate(names):
            m = ter == i
            if not m.any():
                continue
            base = pal.get(name, pal["grass"])
            if name == "grass":
                img[m] = self._ground(style, base, n1, n2, n3, X, Y, lx, ly, seed)[m]
            elif name == "stone":
                img[m] = self._pavers(base, n1, n3, X, Y, lx, ly, marble=style == "marble")[m]
            elif name == "water":
                img[m] = self._water_mat(base, n1, n3, Y)[m]
            elif name == "lava":
                img[m] = self._lava(n1, n2, n3)[m]
            elif name == "ice_floor":
                img[m] = self._ice(base, n1, n3, X, Y)[m]
            elif name == "chasm":
                img[m] = self._chasm(base, n1, Y)[m]
        # обрыв-берег у дальнего края низин и светлая губа земли над ним
        ground_col = pal["grass"]
        for name, hgt in LOWERED.items():
            if name not in names:
                continue
            low = ter == names.index(name)
            if not low.any():
                continue
            land = ~low
            wall = np.zeros_like(low)
            for k in range(1, hgt + 1):
                above = np.zeros_like(land)
                above[k:] = land[:-k]
                wall |= low & above
            depth = np.zeros((LH, LW), float)
            for k in range(1, hgt + 1):
                above = np.zeros_like(land)
                above[k:] = land[:-k]
                depth = np.where(low & above & (depth == 0), k, depth)
            shade = 0.62 - 0.25 * (depth / hgt) + 0.08 * (n3 > 0.6)
            stripes = 0.9 + 0.1 * np.sin(X * 1.7 + n2 * 4)
            wall_col = (ground_col * 0.55 + np.array((40, 30, 24)) * 0.45)[None, None, :] * \
                (shade * stripes)[..., None]
            if name == "lava":
                wall_col = wall_col * 0.8 + np.array((90, 30, 10)) * (depth / hgt)[..., None] * 0.6
            img[wall] = wall_col[wall]
            lip = np.zeros_like(land)
            lip[:-1] = land[:-1] & low[1:]
            img[lip] = np.clip(img[lip] * 1.3 + 12, 0, 255)
            near = np.zeros_like(land)
            near[1:] = land[1:] & low[:-1]
            img[near] = img[near] * 0.72
        # тени укрытий и деревьев на земле
        for (x, y), c in combat.grid.cells.items():
            if c.cover:
                ox, oy = (P.MARGIN_L + x) * L + L // 2, (P.MARGIN_T + y) * L + L // 2 + 3
                d = ((X - ox) / 13.0) ** 2 + ((Y - oy) / 8.0) ** 2
                sh = np.clip(1.2 - d, 0, 1) * 0.45
                img *= (1 - sh)[..., None]
        # мягкая сетка: шов в пиксель только на доске, край доски чуть темнее; вокруг — темнее с расстоянием
        bx0, by0 = P.MARGIN_L * L, P.MARGIN_T * L
        bx1, by1 = bx0 + combat.grid.w * L, by0 + combat.grid.h * L
        on_board = (X >= bx0) & (X < bx1) & (Y >= by0) & (Y < by1)
        seam = on_board & ((lx == 0) | (ly == 0))
        img[seam] *= 0.86
        edge = on_board & ((X == bx0) | (X == bx1 - 1) | (Y == by0) | (Y == by1 - 1))
        img[edge] *= 0.8
        dx = np.maximum(np.maximum(bx0 - X, X - bx1 + 1), 0) / L
        dy = np.maximum(np.maximum(by0 - Y, Y - by1 + 1), 0) / L
        dist = np.sqrt(dx * dx + dy * dy)
        img *= (1 - np.clip(dist * 0.07, 0, 0.35))[..., None]
        # порталы цитадели
        for (x, y), c in combat.grid.cells.items():
            if c.portal:
                ox, oy = (P.MARGIN_L + x) * L + L // 2, (P.MARGIN_T + y) * L + L // 2
                d = np.sqrt(((X - ox) / 12.0) ** 2 + ((Y - oy) / 10.0) ** 2)
                ring = (d < 1) & (d > 0.75)
                img[d < 0.75] = img[d < 0.75] * 0.3 + np.array((70, 40, 130)) * 0.7
                img[ring] = (190, 150, 255)
        arr = np.clip(img, 0, 255).astype(np.uint8)
        surf = pygame.surfarray.make_surface(arr.swapaxes(0, 1))
        surf = pygame.transform.scale(surf, (P.FLAT_W, P.FLAT_H))
        return surf, self._place_props(combat, tm, names, style, pal)

    # ---------- материалы ----------

    def _ground(self, style, base, n1, n2, n3, X, Y, lx, ly, seed):
        b = base[None, None, :]
        big = vnoise(n1.shape, 64, seed + 9)
        if style in ("grass", "moss", "dry"):
            # крупные пятна (светлее/темнее), кочки — тёмные пятна со светлой верхушкой, редкие травинки
            img = b * (0.8 + 0.4 * big)[..., None] * (0.93 + 0.14 * n1)[..., None]
            tuft = vnoise(n1.shape, 4, seed + 5) > 0.74
            top = np.zeros_like(tuft)
            top[:-2] = tuft[2:] & ~tuft[:-2]
            img[tuft] *= 0.84
            img[top] *= 1.22
            blade = (n3 > (0.985 if style == "moss" else 0.965)) & (n2 > 0.45)
            img[blade] *= 1.3
            if style == "dry" or style == "grass":
                dirt = (big < 0.22) & (n1 < 0.45)
                dc = np.array((120, 100, 70)) if style == "dry" else np.array((92, 78, 56))
                img[dirt] = img[dirt] * 0.35 + dc * 0.65 * (0.9 + 0.2 * n3[dirt])[:, None]
            if style == "grass":
                fl = (n3 > 0.997) & (n2 > 0.5)
                img[fl] = (235, 225, 140)
            if style == "moss":
                glow = n3 > 0.996
                img[glow] = (200, 170, 255)
            return img
        if style in ("wet", "marble"):
            return self._pavers(base, n1, n3, X, Y, lx, ly, marble=style == "marble", wet=style == "wet", slab=True)
        img = b * (0.86 + 0.28 * big)[..., None] * (0.94 + 0.12 * n1)[..., None]
        img[n3 > 0.93] *= 1.1
        img[n3 < 0.06] *= 0.88
        if style == "sand":
            img *= (1 + 0.045 * np.sin((Y + n1 * 30 + big * 20) * 0.5))[..., None]
        if style == "snow":
            img = img * (0.9 + 0.1 * n2)[..., None] + np.array((-8, -2, 10)) * (big < 0.4)[..., None]
            img[n3 > 0.996] = (255, 255, 255)
        if style == "ash":
            img[n3 > 0.9975] = (255, 130, 50)
            img[(n2 > 0.72)] *= 0.85
        if style == "dirt":
            img[n3 > 0.998] = (215, 205, 185)            # косточки
        return img

    def _pavers(self, base, n1, n3, X, Y, lx, ly, marble=False, wet=False, slab=False):
        """Плитка: на клетке 2×2 камня со сдвигом рядов (камень) или одна плита (мрамор, мокрый камень)."""
        size = 32 if slab else 16
        row = (Y // size)
        off = np.where(row % 2 == 1, size // 2, 0) if not slab else 0
        col = (X + off) // size
        sid = (col * 7919 + row * 104729).astype(np.float64)
        tint = 0.88 + 0.22 * (np.sin(sid * 12.9898) * 43758.5453 % 1.0)
        img = base[None, None, :] * (tint * (0.95 + 0.1 * n1))[..., None]
        mortar = (Y % size == 0) | ((X + off) % size == 0)
        img[mortar] *= 0.6
        img[(Y % size == 1) & ~mortar] *= 1.1
        img[((X + off) % size == 1) & ~mortar] *= 1.05
        if marble:
            vein = np.abs(np.sin(X * 0.21 + Y * 0.07 + n1 * 9)) < 0.04
            img[vein & ~mortar] *= 0.8
        if wet:
            img[(n1 > 0.7) & ~mortar] = img[(n1 > 0.7) & ~mortar] * 0.7 + np.array((60, 90, 110)) * 0.3
            img[(n3 > 0.993) & ~mortar] = (200, 225, 240)
        return img

    def _water_mat(self, base, n1, n3, Y):
        img = base[None, None, :] * (0.78 + 0.25 * n1)[..., None]
        img[n3 > 0.994] = np.clip(base * 1.9 + 40, 0, 255)
        return img

    def _lava(self, n1, n2, n3):
        crust = np.array((70, 34, 26))[None, None, :] * (0.8 + 0.4 * n1)[..., None]
        crack = np.abs(n2 - 0.5)
        img = crust.copy()
        glow = crack < 0.12
        img[glow] = crust[glow] * 0.4 + np.array((200, 70, 20)) * 0.6
        hot = crack < 0.05
        img[hot] = (255, 170, 60)
        img[n3 > 0.997] = (255, 230, 140)
        return img

    def _ice(self, base, n1, n3, X, Y):
        img = base[None, None, :] * (0.92 + 0.14 * n1)[..., None]
        facet = np.abs(np.sin(X * 0.31 + Y * 0.19 + n1 * 5)) < 0.04
        img[facet] = np.clip(base * 1.25, 0, 255)
        img[n3 > 0.995] = (255, 255, 255)
        return img

    def _chasm(self, base, n1, Y):
        img = np.zeros(n1.shape + (3,))
        img[:] = np.array((10, 8, 20))
        img += np.array((40, 26, 70))[None, None, :] * (n1 * 0.6)[..., None]
        return img

    # ---------- билборды ----------

    def _place_props(self, combat, tm, names, style, pal):
        """Укрытия доски и декор вокруг неё: [(gx, gy, вид, цвет)] — gx, gy в клетках, у ног."""
        out = []
        tree = tuple(int(v) for v in pal["tree"])
        stone = tuple(int(v) for v in pal["stone"])
        for (x, y), c in combat.grid.cells.items():
            if c.deco == "tree":
                out.append((x + 0.5, y + 0.62, "tree", tree))
            elif c.cover == "full":
                out.append((x + 0.5, y + 0.62, "block", stone))
            elif c.cover == "half":
                out.append((x + 0.5, y + 0.62, "log", (120, 88, 58)))
        low = {names.index(n) for n in LOWERED if n in names}
        kinds = DECOR.get(style, DECOR["grass"])
        ch, cw = tm.shape
        for cy in range(ch):
            for cx in range(cw):
                bx, by = cx - P.MARGIN_L, cy - P.MARGIN_T
                if -1 <= bx <= combat.grid.w and -1 <= by <= combat.grid.h:
                    continue                    # у самой доски не ставим — не загораживать
                if by > combat.grid.h + 1 or tm[cy, cx] in low:
                    continue                    # перед доской — пусто: вид на поле важнее
                if _h(cx, cy, 11) > 0.22:
                    continue
                kind = kinds[int(_h(cx, cy, 13) * len(kinds)) % len(kinds)]
                col = tree if kind in ("tree", "bush", "mushroom", "pine") else stone
                out.append((bx + 0.25 + 0.5 * _h(cx, cy, 17), by + 0.3 + 0.5 * _h(cx, cy, 19), kind, col))
        return out

    # ---------- без OpenGL ----------

    def warp(self, flat, dest, fog):
        """Плоская карта → наклонная плоскость на экране (без OpenGL): заранее посчитанный индекс пикселя плоской
        карты для каждого пикселя экрана и готовый слой дымки поверх."""
        w, h = dest.get_size()
        if self._warp is None or self._warp[0] != (w, h, P.view_key()):
            sy, sx = np.mgrid[0:h, 0:w].astype(float)
            u = (sx - P.CENTER_SCREEN[0]) / P.FOCAL
            v = (sy - P.CENTER_SCREEN[1]) / P.FOCAL
            den = P.SIN + v * P.COS
            ok = den > 1e-4
            t = np.where(ok, v * P.DIST / np.where(ok, den, 1), -99)
            zc = P.DIST - t * P.COS
            gy = P.CY + t
            fx = ((P.CX + u * zc + P.MARGIN_L) * P.FLAT).astype(int)
            fy = ((gy + P.MARGIN_T) * P.FLAT).astype(int)
            ok &= (fx >= 0) & (fx < P.FLAT_W) & (fy >= 0) & (fy < P.FLAT_H)
            index = np.clip(fy, 0, P.FLAT_H - 1) * P.FLAT_W + np.clip(fx, 0, P.FLAT_W - 1)
            fogk = np.where(ok, np.clip(-gy / 8.0, 0, 0.85), 1.0)
            self._warp = ((w, h, P.view_key()), index.T.copy(), (fogk.T * 255).astype(np.uint8), {})
        _, index, alpha, fog_layers = self._warp
        if flat.get_bytesize() == 4 and dest.get_bytesize() == 4 and flat.get_masks() == dest.get_masks():
            src = pygame.surfarray.pixels2d(flat)
            row_major = src.T.ravel()
            del src
            pygame.surfarray.blit_array(dest, row_major[index])
        else:
            src = pygame.surfarray.pixels3d(flat)
            rgb = src.transpose(1, 0, 2).reshape(-1, 3)[index]
            del src
            pygame.surfarray.blit_array(dest, rgb)
        key = tuple(int(c * 255) for c in fog)
        layer = fog_layers.get(key)
        if layer is None:
            layer = pygame.Surface((w, h), pygame.SRCALPHA)
            layer.fill((*key, 0))
            pygame.surfarray.pixels_alpha(layer)[:] = alpha
            fog_layers[key] = layer
        dest.blit(layer, (0, 0))


# ---------- рисунки билбордов: холст в логических пикселях, ноги — внизу по центру ----------

def _shade(c, k):
    t = (0, 0, 0) if k < 0 else (255, 255, 255)
    k = abs(k)
    return tuple(int(c[i] + (t[i] - c[i]) * k) for i in range(3))


def prop_image(kind, color):
    """Билборд 32×N логических пикселей → ×2, контур в пиксель."""
    size = {"tree": (32, 46), "pine": (28, 48), "deadtree": (28, 40), "column": (20, 46), "block": (36, 34),
            "log": (34, 18), "bush": (24, 16), "rock": (24, 18), "tombstone": (16, 20), "mushroom": (22, 26)}
    w, h = size.get(kind, (24, 24))
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    c = color
    if kind == "tree":
        pygame.draw.rect(s, (74, 54, 40), (w // 2 - 3, h - 18, 6, 18))
        for dx, dy, r in ((-7, -24, 9), (7, -23, 9), (0, -31, 10), (0, -21, 10)):
            pygame.draw.circle(s, _shade(c, -0.3), (w // 2 + dx, h + dy + 1), r)
            pygame.draw.circle(s, c, (w // 2 + dx - 1, h + dy - 1), r - 2)
            pygame.draw.circle(s, _shade(c, 0.2), (w // 2 + dx - 3, h + dy - 4), max(2, r - 6))
    elif kind == "pine":
        pygame.draw.rect(s, (74, 54, 40), (w // 2 - 2, h - 8, 4, 8))
        for i, (y0, half) in enumerate(((h - 8, 12), (h - 20, 10), (h - 31, 8), (h - 41, 5))):
            pygame.draw.polygon(s, _shade(c, -0.2), [(w // 2 - half, y0), (w // 2, y0 - 14), (w // 2 + half, y0)])
            pygame.draw.polygon(s, (235, 240, 250), [(w // 2 - half + 3, y0 - 3), (w // 2, y0 - 14),
                                                     (w // 2 - 1, y0 - 5)])
    elif kind == "deadtree":
        col = (78, 64, 56)
        pygame.draw.line(s, col, (w // 2, h), (w // 2, h - 26), 4)
        for a, b in (((w // 2, h - 18), (w // 2 - 9, h - 30)), ((w // 2, h - 22), (w // 2 + 8, h - 34)),
                     ((w // 2 - 6, h - 26), (w // 2 - 4, h - 38))):
            pygame.draw.line(s, col, a, b, 2)
    elif kind == "column":
        pygame.draw.rect(s, _shade(c, 0.15), (3, h - 6, w - 6, 6))
        pygame.draw.rect(s, c, (5, 8, w - 10, h - 13))
        for x in range(7, w - 6, 3):
            pygame.draw.line(s, _shade(c, -0.18), (x, 9), (x, h - 7))
        pygame.draw.rect(s, _shade(c, 0.2), (3, 3, w - 6, 6))
        pygame.draw.polygon(s, (0, 0, 0, 0), [(w - 6, 0), (w, 0), (w, 12)])
    elif kind == "block":
        top = pygame.Rect(2, 2, w - 4, 12)
        front = pygame.Rect(2, 12, w - 4, h - 14)
        pygame.draw.rect(s, _shade(c, -0.15), front)
        pygame.draw.rect(s, _shade(c, 0.22), top)
        pygame.draw.line(s, _shade(c, -0.35), (w // 2, 14), (w // 2 - 3, h - 3))
        pygame.draw.line(s, _shade(c, -0.35), (8, 22), (14, 22))
        pygame.draw.line(s, _shade(c, 0.35), (3, 12), (w - 4, 12))
    elif kind == "log":
        pygame.draw.rect(s, _shade(c, -0.2), (2, 7, w - 6, 10), border_radius=4)
        pygame.draw.rect(s, c, (2, 5, w - 6, 9), border_radius=4)
        pygame.draw.ellipse(s, (180, 150, 110), (w - 9, 5, 7, 11))
        pygame.draw.ellipse(s, (130, 100, 70), (w - 8, 8, 4, 5))
        pygame.draw.line(s, _shade(c, 0.25), (5, 7), (w - 12, 7))
    elif kind == "bush":
        for dx, r in ((-5, 6), (5, 6), (0, 8)):
            pygame.draw.circle(s, _shade(c, -0.2), (w // 2 + dx, h - 6), r)
            pygame.draw.circle(s, c, (w // 2 + dx - 1, h - 7), r - 2)
    elif kind == "rock":
        st = (120, 116, 110) if c is None else c
        pygame.draw.polygon(s, _shade(st, -0.25), [(2, h), (4, 8), (12, 2), (21, 6), (23, h)])
        pygame.draw.polygon(s, st, [(4, h - 2), (6, 9), (12, 4), (19, 8), (20, h - 2)])
        pygame.draw.line(s, _shade(st, 0.3), (7, 9), (12, 5))
    elif kind == "tombstone":
        g = (130, 130, 140)
        pygame.draw.rect(s, _shade(g, -0.25), (2, 4, w - 4, h - 4), border_top_left_radius=6,
                         border_top_right_radius=6)
        pygame.draw.rect(s, g, (3, 5, w - 7, h - 6), border_top_left_radius=5, border_top_right_radius=5)
        pygame.draw.line(s, _shade(g, -0.4), (w // 2, 8), (w // 2, 14))
        pygame.draw.line(s, _shade(g, -0.4), (w // 2 - 3, 10), (w // 2 + 3, 10))
    elif kind == "mushroom":
        pygame.draw.rect(s, (220, 210, 200), (w // 2 - 3, h - 14, 6, 14))
        pygame.draw.ellipse(s, _shade(c, -0.25), (1, 2, w - 2, 14))
        pygame.draw.ellipse(s, c, (2, 1, w - 4, 12))
        for x, y in ((6, 5), (14, 4), (10, 9)):
            pygame.draw.circle(s, (240, 220, 255), (x, y), 1)
    s = pygame.transform.scale(s, (w * 2, h * 2))
    mask = pygame.mask.from_surface(s)
    out = pygame.Surface((w * 2 + 2, h * 2 + 2), pygame.SRCALPHA)
    sil = mask.to_surface(setcolor=(22, 18, 24, 255), unsetcolor=(0, 0, 0, 0))
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
        out.blit(sil, (dx, dy))
    out.blit(s, (1, 1))
    return out


def lit(color, k):
    return tuple(int(min(255, max(0, v * k))) for v in color)


def angle_deg(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
