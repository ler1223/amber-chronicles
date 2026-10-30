"""Следы на поле боя: выжженная земля, воронки, трещины, ледяная корка, лужи, воткнутые стрелы.

Штампуются на отдельный слой над землёй и остаются до конца боя. Текстуры процедурные (128×128),
на поле сплющиваются по вертикали (вид 3/4).
"""
import numpy as np
import pygame

from ui.vfx_textures import _smooth, fbm, voronoi_edges

SIZE = 128


def _surf(rgb, a):
    s = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    pygame.surfarray.pixels3d(s)[:] = (np.clip(rgb, 0, 1) * 255).astype(np.uint8).transpose(1, 0, 2)
    pygame.surfarray.pixels_alpha(s)[:] = (np.clip(a, 0, 1) * 255).astype(np.uint8).T
    return s


def make_marks(seed=5):
    rng = np.random.default_rng(seed)
    c = (np.arange(SIZE) + 0.5) / SIZE * 2 - 1
    x, y = np.meshgrid(c, c)
    r = np.sqrt(x * x + y * y)
    n = fbm([x * 3 + 3, y * 3 + 3], [12, 12], rng, 4)
    n2 = fbm([x * 7 + 7, y * 7 + 7], [28, 28], rng, 3)
    edges = voronoi_edges(SIZE, 6, rng)
    out = {}

    def col(v):
        return np.broadcast_to(np.array(v, np.float32) / 255, (SIZE, SIZE, 3))

    # выжженная земля: чёрное пятно с рваным краем и тлеющей серединой
    d = r + (n - 0.5) * 0.7
    a = _smooth(0.95, 0.45, d) * 0.85
    rgb = col((22, 16, 14)) * (0.7 + 0.6 * n2[..., None])
    out["scorch"] = _surf(rgb, a)
    # воронка: тёмная чаша и светлый вывороченный край
    bowl = _smooth(0.75, 0.2, d)
    rim = np.exp(-((d - 0.8) / 0.12) ** 2)
    rgb = col((30, 24, 20)) * (1 - rim[..., None]) + col((120, 100, 78)) * rim[..., None]
    a = np.clip(bowl * 0.85 + rim * 0.7, 0, 1) * _smooth(1, 0.85, r)
    out["crater"] = _surf(rgb * (0.8 + 0.4 * n2[..., None]), a)
    # трещины: границы вороного, гуще к центру
    cracks = _smooth(0.12, 0.0, edges) * _smooth(1.0, 0.2, r + (n - 0.5) * 0.4)
    out["cracks"] = _surf(col((20, 16, 14)), cracks * 0.9)
    # светящиеся трещины (лава/свет) — рисуются тем же слоем, свечение даёт эффект поверх
    out["cracks_hot"] = _surf(col((255, 150, 60)) * 0.9, cracks * 0.8)
    # ледяная корка: полупрозрачная с белыми гранями
    ice = _smooth(0.95, 0.6, r + (n - 0.5) * 0.5)
    facets = _smooth(0.08, 0.0, edges)
    rgb = col((170, 210, 240)) * (1 - facets[..., None]) + col((245, 252, 255)) * facets[..., None]
    out["ice"] = _surf(rgb, ice * (0.45 + 0.45 * facets))
    # иней: светлая крупа
    frost = _smooth(0.95, 0.3, r + (n - 0.5) * 0.6) * (n2 > 0.55)
    out["frost"] = _surf(col((230, 245, 255)), frost * 0.7)
    # лужа и грязь
    pud = _smooth(0.9, 0.7, r + (n - 0.5) * 0.45)
    hl = np.exp(-(((x + 0.3) / 0.25) ** 2 + ((y + 0.25) / 0.12) ** 2))
    out["puddle"] = _surf(col((60, 110, 170)) + col((180, 220, 255)) * hl[..., None], pud * 0.55 + hl * 0.3)
    splat = _smooth(0.85, 0.6, r + (n - 0.5) * 0.9) + _smooth(0.12, 0.0, np.abs(n2 - 0.7)) * _smooth(1, 0.5, r) * 0.6
    out["mud"] = _surf(col((88, 66, 44)) * (0.8 + 0.4 * n2[..., None]), np.clip(splat, 0, 1) * 0.8)
    # ожог-печать: тёмное кольцо со следами рун (святой огонь, приговор)
    ring = np.exp(-((r - 0.75) / 0.06) ** 2) + np.exp(-((r - 0.55) / 0.03) ** 2) * 0.7
    ang = np.arctan2(y, x)
    ticks = (np.cos(ang * 24) > 0.6) * np.exp(-((r - 0.65) / 0.05) ** 2)
    out["glyph"] = _surf(col((40, 30, 20)), np.clip(ring + ticks, 0, 1) * 0.75 * (0.7 + 0.3 * n2))
    # царапины-разрез (взмах)
    slash = np.exp(-((y + x * 0.25) / 0.05) ** 2) * _smooth(1, 0.3, np.abs(x)) * (0.6 + 0.4 * n2)
    out["gash"] = _surf(col((26, 20, 16)), slash * 0.8)
    return out


def stuck(prop, angle=70):
    """Модель, воткнутая в землю: наконечник срезан (ушёл в землю), торчит под углом. Якорь — низ по центру."""
    w, h = prop.get_size()
    cut = prop.subsurface((0, 0, max(1, int(w * 0.72)), h)).copy()
    img = pygame.transform.rotate(cut, -angle)
    return img


class MarkLayer:
    """Слой следов: SRCALPHA-поверхность размером с экран, на неё штампуются следы."""

    def __init__(self, size, props=None):
        self.surf = pygame.Surface(size, pygame.SRCALPHA)
        self.tex = make_marks()
        self.props = props or {}
        self._cache = {}
        self.count = 0
        self._fade = 0.0

    def fade(self, dt, every=2.0, keep=245):
        """Следы медленно выцветают (за минуту — примерно вдвое), чтобы поле не заливало чернотой."""
        if not self.count:
            return
        self._fade += dt
        if self._fade >= every:
            self._fade = 0.0
            self.surf.fill((255, 255, 255, keep), special_flags=pygame.BLEND_RGBA_MULT)

    def clear(self):
        self.surf.fill((0, 0, 0, 0))
        self.count = 0

    def _img(self, name, size, rot, alpha, flat):
        key = (name, int(size) // 4, int(rot) // 15, int(alpha * 10), flat)
        img = self._cache.get(key)
        if img is None:
            if name.startswith("prop:"):
                base = self.props.get(name[5:])
                if base is None:
                    return None
                img = stuck(pygame.transform.scale(base, (base.get_width() * 2, base.get_height() * 2)), 50 + rot % 40)
            else:
                base = self.tex[name]
                if rot:                       # сначала поворот, потом сплющивание: пятно лежит на земле
                    base = pygame.transform.rotate(base, rot)
                k = max(2, int(size)) / 128
                w, h = base.get_size()
                img = pygame.transform.smoothscale(base, (max(2, int(w * k)), max(2, int(h * k * flat))))
            img = img.copy()
            if alpha < 1:
                img.fill((255, 255, 255, int(255 * alpha)), special_flags=pygame.BLEND_RGBA_MULT)
            if len(self._cache) > 400:
                self._cache.clear()
            self._cache[key] = img
        return img

    def stamp(self, name, x, y, size=80, rot=0.0, alpha=1.0, flat=0.5):
        img = self._img(name, size, rot, alpha, flat)
        if img is None:
            return
        if name.startswith("prop:"):         # воткнутое — якорь снизу
            self.surf.blit(img, (x - img.get_width() / 2, y - img.get_height() + 3))
        else:
            self.surf.blit(img, (x - img.get_width() / 2, y - img.get_height() / 2))
        self.count += 1

    def stamp_surface(self, img, x, y):
        """Готовая картинка (пиксельная подпалина, иней) центром в точку (x, y) плоской карты."""
        self.surf.blit(img, (round(x - img.get_width() / 2), round(y - img.get_height() / 2)))
        self.count += 1
