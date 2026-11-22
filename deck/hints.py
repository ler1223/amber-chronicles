"""Подсказки на поле «Спуска» — чёткие, в родном разрешении экрана (квиз 2026-11-20: «светящийся контур»).

Земля и фигурки пиксельные (кадр 1280×800, растянут), а зоны, клетки, линии и кольца под ногами рисуются
поверх земли, но под фигурками, прямо в полном разрешении: сглаженный контур, у зоны — один общий по краю
(а не рамка на каждой клетке), мягкое свечение и лёгкая заливка.

Координаты — клетки земли (как P.project): клетка (x, y) — квадрат от (x, y) до (x+1, y+1).
Использование: h.clear(); h.zone(...); h.line(...); …; h.draw(canvas).
"""
import math

import pygame

from ui import projection as P

GLOW = 4                 # свечение рисуется в 4 раза мельче и растягивается — мягкое и дешёвое


def _rgba(col, a=None):
    if len(col) == 4 and a is None:
        return tuple(int(v) for v in col)
    return (int(col[0]), int(col[1]), int(col[2]), int(255 if a is None else max(0, min(255, a))))


class Plain:
    """Обычная поверхность вместо холста (тесты, снимки): масштаб 1, без сдвига."""

    def __init__(self, surf):
        self.native, self.S, self.ox, self.oy = surf, 1.0, 0.0, 0.0

    def pt(self, p):
        return p


class Hints:
    def __init__(self):
        self.fills = []          # (точки, цвет)
        self.edges = []          # (a, b, цвет, толщина, свечение)
        self.rings = []          # (точки, цвет, толщина, свечение) — замкнутые
        self.dots = []           # (точка, радиус, цвет)
        self.ovals = []          # кольца: (центр, rx, ry, цвет, толщина, свечение, заливка)
        self.blobs = []          # мягкие пятна: (центр, радиус x, радиус y в клетках, цвет, альфа) — тени
        self._layer = None
        self._soft = {}
        self._glow = None

    def clear(self):
        self.fills, self.edges, self.rings, self.dots, self.blobs, self.ovals = [], [], [], [], [], []

    # ---------- фигуры (в клетках земли) ----------

    @staticmethod
    def _corners(p, inset=0.0):
        x, y = p
        i = inset
        return [(x + i, y + i), (x + 1 - i, y + i), (x + 1 - i, y + 1 - i), (x + i, y + 1 - i)]

    def zone(self, cells, col, fill=40, edge=210, width=2.0, glow=True):
        """Набор клеток: заливка и общий контур по внешнему краю."""
        cells = set(map(tuple, cells))
        if not cells:
            return
        if fill:
            for p in cells:
                self.fills.append((self._corners(p), _rgba(col, fill)))
        if not edge:
            return
        for x, y in cells:
            for (dx, dy), a, b in (((0, -1), (x, y), (x + 1, y)), ((1, 0), (x + 1, y), (x + 1, y + 1)),
                                   ((0, 1), (x + 1, y + 1), (x, y + 1)), ((-1, 0), (x, y + 1), (x, y))):
                if (x + dx, y + dy) not in cells:
                    self.edges.append((a, b, _rgba(col, edge), width, glow))

    def cell(self, p, col, fill=0, edge=220, inset=0.0, width=2.0, glow=False):
        pts = self._corners(p, inset)
        if fill:
            self.fills.append((pts, _rgba(col, fill)))
        if edge:
            self.rings.append((pts, _rgba(col, edge), width, glow))

    def line(self, a, b, col, alpha=220, width=3.0, glow=True, dash=0.0):
        """Отрезок по земле (a, b — точки в клетках); dash — длина штриха в клетках."""
        c = _rgba(col, alpha)
        if not dash:
            self.edges.append((a, b, c, width, glow))
            return
        d = math.dist(a, b)
        n = max(1, int(d / dash))
        for k in range(0, n, 2):
            t0, t1 = k / n, min(1.0, (k + 1) / n)
            self.edges.append(((a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                               (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1), c, width, glow))

    def path(self, pts, col, alpha=220, width=3.0):
        for a, b in zip(pts, pts[1:]):
            self.edges.append((a, b, _rgba(col, alpha), width, True))
        for p in pts[1:-1]:
            self.dots.append((p, width * 0.9, _rgba(col, alpha)))
        if len(pts) > 1:
            self.ring(pts[-1], 0.2, col, alpha, width)

    def ring(self, c, r, col, alpha=220, width=2.0, glow=True, fill=0, squash=1.0):
        """Круг на земле радиусом r клеток (в перспективе — эллипс). Рисуется цельным сглаженным овалом
        (картинка, построенная вчетверо крупнее), а не отрезками: на стыках отрезков кольцо «рябило»."""
        self.ovals.append((c, r, r * squash, _rgba(col, alpha), width, glow, int(fill)))

    def blob(self, c, rx, ry, col=(0, 0, 0), alpha=120):
        """Мягкое пятно на земле (тень под фигуркой, тень облака): rx, ry — полуоси в клетках."""
        self.blobs.append((c, rx, ry, tuple(col), int(alpha)))

    def _soft_img(self, w, h, col, alpha):
        key = (w, h, col, alpha // 8)
        img = self._soft.get(key)
        if img is None:
            if len(self._soft) > 200:
                self._soft.clear()
            base = self._soft.get(("tex",))
            if base is None:
                n = 64
                base = pygame.Surface((n, n), pygame.SRCALPHA)
                for y in range(n):
                    for x in range(n):
                        d = math.hypot((x + 0.5) / n * 2 - 1, (y + 0.5) / n * 2 - 1)
                        base.set_at((x, y), (255, 255, 255, int(255 * max(0.0, 1 - d) ** 1.6)))
                self._soft[("tex",)] = base
            img = pygame.transform.smoothscale(base, (max(1, w), max(1, h)))
            img.fill((*col, (alpha // 8) * 8), special_flags=pygame.BLEND_RGBA_MULT)
            self._soft[key] = img
        return img

    def _oval_img(self, w, h, col, width, glow, fill):
        """Кольцо-овал w×h: строится в 4 раза крупнее и уменьшается — ровный сглаженный край."""
        key = ("oval", w, h, col, round(width * 2), glow, fill)
        img = self._soft.get(key)
        if img is None:
            if len(self._soft) > 300:
                self._soft.clear()
            k = 4
            g = 6 if glow else 0
            W, H = w + 2 * g, h + 2 * g
            big = pygame.Surface((W * k, H * k), pygame.SRCALPHA)
            r = pygame.Rect(g * k, g * k, w * k, h * k)
            if fill:
                pygame.draw.ellipse(big, (*col[:3], fill), r)
            if glow:
                gl = pygame.Surface((W * k, H * k), pygame.SRCALPHA)
                pygame.draw.ellipse(gl, (*col[:3], col[3] // 3), r.inflate(width * k * 2, width * k * 2),
                                    max(1, round(width * k * 3)))
                small = pygame.transform.smoothscale(gl, (max(1, W // 2), max(1, H // 2)))
                big.blit(pygame.transform.smoothscale(small, (W * k, H * k)), (0, 0))
            pygame.draw.ellipse(big, col, r, max(1, round(width * k)))
            img = pygame.transform.smoothscale(big, (W, H))
            self._soft[key] = img
        return img

    def dot(self, c, r, col, alpha=220):
        """Точка (r — пиксели логического кадра)."""
        self.dots.append((c, r, _rgba(col, alpha)))

    # ---------- рисование ----------

    def draw(self, canvas):
        if not (self.fills or self.edges or self.rings or self.dots or self.blobs or self.ovals):
            return
        S = canvas.S
        cache = {}

        def pt(g):
            q = cache.get(g)
            if q is None:
                x, y, _ = P.project(g[0], g[1])
                q = cache[g] = canvas.pt((x, y))
            return q

        fills = [([pt(g) for g in pts], col) for pts, col in self.fills]
        edges = [(pt(a), pt(b), col, w * S, glow) for a, b, col, w, glow in self.edges]
        rings = [([pt(g) for g in pts], col, w * S, glow) for pts, col, w, glow in self.rings]
        dots = [(pt(g), r * S, col) for g, r, col in self.dots]
        blobs = []
        for (cx, cy), rx, ry, col, a in self.blobs:
            l, r_ = pt((cx - rx, cy)), pt((cx + rx, cy))
            t_, b_ = pt((cx, cy - ry)), pt((cx, cy + ry))
            blobs.append((pygame.Rect(round(l[0]), round(t_[1]), max(1, round(r_[0] - l[0])),
                                      max(1, round(b_[1] - t_[1]))), col, a))
        ovals = []
        for (cx, cy), rx, ry, col, w, glow, fill in self.ovals:
            l, r_ = pt((cx - rx, cy)), pt((cx + rx, cy))
            t_, b_ = pt((cx, cy - ry)), pt((cx, cy + ry))
            ovals.append((pygame.Rect(round(l[0]), round(t_[1]), max(2, round(r_[0] - l[0])),
                                      max(2, round(b_[1] - t_[1]))), col, max(1.0, w * S), glow, fill))
        native = canvas.native
        for rr, col, a in blobs:                               # тени — затемнением прямо по экрану
            img = self._mult_img(rr.w, rr.h, col, a)
            native.blit(img, (rr.centerx - img.get_width() // 2, rr.centery - img.get_height() // 2),
                        special_flags=pygame.BLEND_RGB_MULT)
        xs, ys = [], []
        for pts, _ in fills:
            xs += [p[0] for p in pts]
            ys += [p[1] for p in pts]
        for a, b, *_ in edges:
            xs += [a[0], b[0]]
            ys += [a[1], b[1]]
        for pts, *_ in rings:
            xs += [p[0] for p in pts]
            ys += [p[1] for p in pts]
        for p, r, _ in dots:
            xs += [p[0] - r, p[0] + r]
            ys += [p[1] - r, p[1] + r]
        if xs:                                                 # зоны и линии — через прозрачный слой (только их рамка)
            self._layer_draw(native, S, fills, edges, rings, dots, xs, ys)
        for rr, col, w, glow, fill in ovals:                   # кольца — готовыми овалами, прямо по экрану
            img = self._oval_img(rr.w, rr.h, (*col[:3], 255), w, glow, fill)
            img.set_alpha(col[3])
            native.blit(img, (rr.centerx - img.get_width() // 2, rr.centery - img.get_height() // 2))
            img.set_alpha(None)

    def _mult_img(self, w, h, col, a):
        """Мягкая тень для умножения: белое с тёмной серединой (размер — шагом 4 пикселя: кэш не пухнет)."""
        w, h = max(4, (w + 2) // 4 * 4), max(4, (h + 2) // 4 * 4)
        key = ("mult", w, h, col, a // 8)
        img = self._soft.get(key)
        if img is None:
            img = pygame.Surface((w, h))
            img.fill((255, 255, 255))
            img.blit(self._soft_img(w, h, col, a), (0, 0))
            self._soft[key] = img
        return img

    def _layer_draw(self, native, S, fills, edges, rings, dots, xs, ys):
        pad = int(14 * S)
        box = pygame.Rect(int(min(xs)) - pad, int(min(ys)) - pad, int(max(xs) - min(xs)) + 2 * pad,
                          int(max(ys) - min(ys)) + 2 * pad).clip(native.get_rect())
        if box.w < 2 or box.h < 2:
            return
        if self._layer is None or self._layer.get_size() != native.get_size():
            self._layer = pygame.Surface(native.get_size(), pygame.SRCALPHA)
        L = self._layer
        L.fill((0, 0, 0, 0), box)
        ox, oy = box.topleft
        for pts, col in fills:                                 # заливка
            pygame.draw.polygon(L, col, [(x, y) for x, y in pts])
        # свечение: те же линии, толще, в мелком слое — растянуть со сглаживанием
        gw, gh = max(1, box.w // GLOW), max(1, box.h // GLOW)
        if self._glow is None or self._glow.get_size() != (gw, gh):
            self._glow = pygame.Surface((gw, gh), pygame.SRCALPHA)
        G = self._glow
        G.fill((0, 0, 0, 0))
        any_glow = False

        def g(p):
            return ((p[0] - ox) / GLOW, (p[1] - oy) / GLOW)
        for a, b, col, w, glow in edges:
            if glow:
                any_glow = True
                pygame.draw.line(G, (*col[:3], min(255, col[3] // 2)), g(a), g(b), max(2, int(w * 2.5 / GLOW) + 1))
        for pts, col, w, glow in rings:
            if glow:
                any_glow = True
                pygame.draw.lines(G, (*col[:3], min(255, col[3] // 2)), True, [g(p) for p in pts],
                                  max(2, int(w * 2.5 / GLOW) + 1))
        if any_glow:
            L.blit(pygame.transform.smoothscale(G, box.size), box.topleft)
        for a, b, col, w, _ in edges:                         # чёткий контур
            pygame.draw.aaline(L, col, a, b, max(1, round(w)))
            if w >= 2:
                pygame.draw.circle(L, col, a, w / 2)
                pygame.draw.circle(L, col, b, w / 2)
        for pts, col, w, _ in rings:
            for a, b in zip(pts, pts[1:] + pts[:1]):
                pygame.draw.aaline(L, col, a, b, max(1, round(w)))
        for p, r, col in dots:
            pygame.draw.aacircle(L, col, p, max(1, r), 0)
        native.blit(L, box.topleft, area=box)
