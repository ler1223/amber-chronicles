"""Оформление интерфейса боя «Спуска» — своё у каждого героя (квиз 2026-11-20).

Всё рисуется сразу в родном разрешении экрана, со сглаживанием (фигуры строятся вдвое крупнее и уменьшаются):
панели со скошенными углами, металлической каймой, фаской и заклёпками; кнопка-плашка; стеклянный шар энергии в
кольце; медальоны намерений; значки состояний; ленты заголовков. Материал — у героя свой (SKINS). Если есть
нарисованный набор (assets/ui/<герой>/, tools/import_ui_art.py, prompts_expedition.md DC4) — уголки, кайма,
фон панели, кольцо шара, медальон и значки берутся из него.

Координаты — логические (1280×800), как у сцен; на холсте (deck/gfx.Canvas) — пересчёт в родные пиксели.
Готовые картинки кэшируются по размеру: панели не перестраиваются каждый кадр.
"""
import math
import os
import random

import pygame

from ui import theme as T

from . import cardface as CF
from . import gfx as G

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "assets", "ui")
CARD_ICONS = os.path.join(ROOT, "assets", "cards", "icons")
SS = 2                                    # сглаживание: строим вдвое крупнее

# материал героя: металл каймы (светлый, средний, тёмный), кожа/дерево панели (верх, низ), акцент, заголовки,
# энергия (блик, середина, край)
SKINS = {
    "merc": {"metal": ((176, 132, 76), (112, 78, 42), (48, 32, 18)), "fill": ((50, 36, 26), (24, 17, 12)),
             "accent": (255, 186, 92), "title": (255, 216, 158), "text": (236, 222, 198), "dim": (176, 158, 132),
             "energy": ((255, 238, 180), (240, 156, 50), (120, 58, 12)), "grain": 0.10},
    "hunter": {"metal": ((150, 128, 92), (92, 74, 50), (40, 32, 22)), "fill": ((34, 44, 32), (16, 22, 15)),
               "accent": (168, 226, 120), "title": (214, 240, 186), "text": (226, 234, 214), "dim": (160, 176, 148),
               "energy": ((226, 255, 196), (118, 206, 92), (28, 84, 30)), "grain": 0.14},
    "pyro": {"metal": ((112, 104, 102), (60, 54, 54), (22, 18, 18)), "fill": ((44, 28, 24), (20, 12, 10)),
             "accent": (255, 132, 62), "title": (255, 198, 150), "text": (240, 220, 206), "dim": (186, 150, 134),
             "energy": ((255, 236, 170), (255, 122, 40), (128, 28, 8)), "grain": 0.12},
}
# значки: нарисованные (assets/ui/icons) или, пока их нет, значки тегов карт
ICON_FALLBACK = {
    "i_melee": "Удар", "i_shot": "Выстрел", "i_zone": "Огонь", "i_block": "Защита", "i_aim": "Метка",
    "i_heal": "Кровь", "i_roar": "Клич", "i_charge": "Шаг", "i_pull": "Толчок", "i_guard": "Защита",
    "i_rally": "Клич", "i_veil": "Ловушка", "i_curse": "Яд", "i_hex": "Метка", "i_drown": "Яд",
    "i_summon": "Клич",
    "s_burn": "Огонь", "s_poison": "Яд", "s_weak": "Удар", "s_vulnerable": "Защита", "s_wet": "Яд",
    "s_stun": "Толчок", "s_strength": "Удар", "s_thorns": "Шипы", "s_momentum": "Шаг", "s_rage": "Кровь",
    "s_heat": "Огонь", "s_frost": "Защита", "s_mark": "Метка", "s_veil": "Ловушка", "s_focus": "Метка",
    "s_shield": "Защита", "s_bleed": "Кровь", "s_counter": "Шипы", "s_power": "Клич",
}
_cache = {}
_imgs = {}
_skins = {}


def _remember(key, make):
    v = _cache.get(key)
    if v is None:
        if len(_cache) > 600:
            _cache.clear()
        v = _cache[key] = make()
    return v


def _load(path):
    if path not in _imgs:
        try:
            im = pygame.image.load(path)
            _imgs[path] = im.convert_alpha() if pygame.display.get_surface() else im
        except (pygame.error, FileNotFoundError):
            _imgs[path] = None
    return _imgs[path]


def ctx(surf):
    """(поверхность в родных пикселях, масштаб, пересчёт точки)."""
    if G.is_canvas(surf):
        return surf.native, surf.S, surf.pt
    return surf, 1.0, (lambda p: p)


def mix(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def lighter(c, k):
    return mix(c, (255, 255, 255), k)


def darker(c, k):
    return mix(c, (0, 0, 0), k)


# ---------- примитивы (в родных пикселях) ----------

def chamfer(w, h, c, x=0.0, y=0.0):
    return [(x + c, y), (x + w - c, y), (x + w, y + c), (x + w, y + h - c), (x + w - c, y + h), (x + c, y + h),
            (x, y + h - c), (x, y + c)]


def mask(size, pts=None, circle=None, ellipse=None):
    """Сглаженная белая маска фигуры (альфа — покрытие)."""
    w, h = size
    m = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
    if pts:
        pygame.draw.polygon(m, (255, 255, 255, 255), [(px * SS, py * SS) for px, py in pts])
    if circle:
        (cx, cy), r = circle
        pygame.draw.circle(m, (255, 255, 255, 255), (cx * SS, cy * SS), r * SS)
    if ellipse:
        pygame.draw.ellipse(m, (255, 255, 255, 255), pygame.Rect([v * SS for v in ellipse]))
    return pygame.transform.smoothscale(m, (w, h))


def vgrad(w, h, stops, alpha=255):
    """Вертикальный градиент: stops — [(доля 0..1, цвет)]."""
    h = max(2, h)
    s = pygame.Surface((1, h), pygame.SRCALPHA)
    for y in range(h):
        t = y / (h - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                c = mix(c0, c1, (t - t0) / max(1e-6, t1 - t0))
                break
        else:
            c = stops[-1][1]
        s.set_at((0, y), (*c, alpha))
    return pygame.transform.scale(s, (max(1, w), h))


def rgrad(r, stops, center=(0.5, 0.5)):
    """Круговой градиент радиуса r (центр смещается — объём шара)."""
    n = 64
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    cx, cy = center[0] * n, center[1] * n
    for y in range(n):
        for x in range(n):
            t = min(1.0, math.hypot(x + 0.5 - cx, y + 0.5 - cy) / (n * 0.62))
            for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
                if t0 <= t <= t1:
                    c = mix(c0, c1, (t - t0) / max(1e-6, t1 - t0))
                    break
            else:
                c = stops[-1][1]
            s.set_at((x, y), (*c, 255))
    return pygame.transform.smoothscale(s, (2 * r, 2 * r))


def apply_mask(img, m):
    out = img.copy()
    out.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return out


def blur(img, k=6):
    w, h = img.get_size()
    small = pygame.transform.smoothscale(img, (max(1, w // k), max(1, h // k)))
    return pygame.transform.smoothscale(small, (w, h))


def grain(w, h, amount, seed=3):
    """Зерно кожи/дерева: мелкий шум и волокна (множитель цвета ~ 1 − amount…1)."""
    def make():
        rng = random.Random(seed)
        n = 128
        s = pygame.Surface((n, n))
        for y in range(n):
            band = 0.5 + 0.5 * math.sin(y * 0.21 + rng.random() * 0.4)
            for x in range(n):
                v = 1 - amount * (0.55 * rng.random() + 0.45 * band)
                c = int(255 * v)
                s.set_at((x, y), (c, c, c))
        return s
    tile = _remember(("grain", amount, seed), make)
    out = pygame.Surface((w, h))
    for y in range(0, h, tile.get_height()):
        for x in range(0, w, tile.get_width()):
            out.blit(tile, (x, y))
    return out


def outlined(text, px, color, outline=(10, 6, 4), title=False, width=None):
    """Надпись шрифтом карт (Alegreya SC — заголовки, PT Serif — текст) с тёмной обводкой — читается на любом
    фоне."""
    def make():
        f = CF.title_font(px) if title else CF.font(px, True)
        main = f.render(text, True, color)
        o = width if width is not None else max(1, px // 12)
        dark = f.render(text, True, outline)
        out = pygame.Surface((main.get_width() + 2 * o, main.get_height() + 2 * o), pygame.SRCALPHA)
        for dx in range(-o, o + 1):
            for dy in range(-o, o + 1):
                if dx * dx + dy * dy <= o * o + 1:
                    out.blit(dark, (o + dx, o + dy))
        out.blit(main, (o, o))
        return out
    return _remember(("txt", text, px, tuple(color), tuple(outline), title, width), make)


def slice3(art, w, h, cap=0.3):
    """Плашка из картинки на любую ширину: концы (cap ширины картинки) — без искажений, середина тянется."""
    k = h / art.get_height()
    aw = art.get_width()
    cw = int(aw * cap)
    left = pygame.transform.smoothscale(art.subsurface((0, 0, cw, art.get_height())), (max(1, round(cw * k)), h))
    right = pygame.transform.smoothscale(art.subsurface((aw - cw, 0, cw, art.get_height())),
                                         (max(1, round(cw * k)), h))
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    lw = min(left.get_width(), w // 2)
    mid_w = w - 2 * lw
    if mid_w > 0:
        mid = art.subsurface((cw, 0, aw - 2 * cw, art.get_height()))
        out.blit(pygame.transform.smoothscale(mid, (mid_w, h)), (lw, 0))
    out.blit(left, (0, 0), (0, 0, lw, h))
    out.blit(right, (w - lw, 0), (right.get_width() - lw, 0, lw, h))
    return out


def ring_hole(art):
    """Радиус пустого центра кольца (доля ширины картинки) — по прозрачности на средней строке."""
    def make():
        w, h = art.get_size()
        y = h // 2
        x = w // 2
        while x < w - 1 and art.get_at((x, y))[3] < 60:
            x += 1
        return max(0.2, (x - w / 2) / w)
    return _remember(("hole", id(art)), make)


class Skin:
    def __init__(self, hero):
        self.id = hero if hero in SKINS else "merc"
        self.p = SKINS[self.id]
        self.dir = os.path.join(ART, self.id)

    def art(self, name):
        return _load(os.path.join(self.dir, f"{name}.png"))

    # ---------- текст ----------

    def text(self, surf, s, pos, size=16, color=None, center=False, title=False, outline=True, right=False):
        """Чёткая надпись с обводкой; pos — логические координаты. Возвращает логическую ширину."""
        native, S, pt = ctx(surf)
        px = max(6, round(size * S))
        col = color or self.p["text"]
        img = outlined(s, px, col, title=title) if outline else _remember(
            ("plain", s, px, tuple(col), title),
            lambda: (CF.title_font(px) if title else CF.font(px, True)).render(s, True, col))
        x, y = pt(pos)
        if center:
            x, y = x - img.get_width() / 2, y - img.get_height() / 2
        elif right:
            x = x - img.get_width()
        native.blit(img, (round(x), round(y)))
        return img.get_width() / S

    def size(self, s, size, title=False):
        f = CF.title_font(size) if title else CF.font(size, True)
        return f.size(s)

    # ---------- панель ----------

    def panel(self, surf, rect, alpha=236, accent=False, cut=10):
        """Панель: тень, металлическая кайма с фаской, фон-кожа с зерном, тонкая линия акцента, заклёпки."""
        native, S, pt = ctx(surf)
        r = pygame.Rect(rect)
        w, h = max(8, round(r.w * S)), max(8, round(r.h * S))
        img = _remember(("panel", self.id, w, h, alpha, accent, cut, round(S, 3)),
                        lambda: self._panel(w, h, S, alpha, accent, cut))
        x, y = pt(r.topleft)
        sh = round(10 * S)
        native.blit(img, (round(x) - sh, round(y) - sh))
        return r

    def _panel(self, w, h, S, alpha, accent, cut):
        if self.art("edge") is not None and self.art("fill") is not None and self.art("corner") is not None:
            return self._panel_art(w, h, S, alpha, accent)
        p = self.p
        hi, mid, lo = p["metal"]
        sh = round(10 * S)
        out = pygame.Surface((w + 2 * sh, h + 2 * sh), pygame.SRCALPHA)
        c = max(3, round(cut * S))
        b = max(2, round(4 * S))
        # тень
        shadow = apply_mask(pygame.Surface((w + 2 * sh, h + 2 * sh), pygame.SRCALPHA),
                            mask((w + 2 * sh, h + 2 * sh), chamfer(w, h, c, sh + 2 * S, sh + 4 * S)))
        shadow.fill((0, 0, 0, 150), special_flags=pygame.BLEND_RGBA_MULT)
        out.blit(blur(shadow, 5), (0, 0))
        # кайма: металл сверху светлее
        band = apply_mask(vgrad(w, h, [(0, lighter(hi, 0.1)), (0.45, mid), (1, lo)]), mask((w, h), chamfer(w, h, c)))
        out.blit(band, (sh, sh))
        # фон панели
        iw, ih = w - 2 * b, h - 2 * b
        fill_art = self.art("fill")
        if fill_art is not None:
            k = max(0.2, min(1.0, 160 * S / fill_art.get_width()))
            tile = pygame.transform.smoothscale(fill_art, (max(1, int(fill_art.get_width() * k)),
                                                           max(1, int(fill_art.get_height() * k))))
            body = pygame.Surface((iw, ih), pygame.SRCALPHA)
            for yy in range(0, ih, tile.get_height()):
                for xx in range(0, iw, tile.get_width()):
                    body.blit(tile, (xx, yy))
            body.blit(vgrad(iw, ih, [(0, (255, 255, 255)), (1, (150, 150, 150))]), (0, 0),
                      special_flags=pygame.BLEND_RGB_MULT)
        else:
            body = vgrad(iw, ih, [(0, p["fill"][0]), (1, p["fill"][1])])
            body.blit(grain(iw, ih, p["grain"]), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        body.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        body = apply_mask(body, mask((iw, ih), chamfer(iw, ih, max(2, c - b * 0.6))))
        out.blit(body, (sh + b, sh + b))
        # фаска: светлый верх-лево, тёмный низ-право; внутренняя тень у каймы
        o = chamfer(w - 1, h - 1, c, sh, sh)
        L = lighter(hi, 0.35)
        for a_, b_ in zip(o, o[1:] + o[:1]):
            col = L if (a_[1] <= sh + c + 1 and b_[1] <= sh + c + 1) or (a_[0] <= sh + c + 1 and b_[0] <= sh + c + 1) \
                else darker(lo, 0.4)
            pygame.draw.aaline(out, col, a_, b_, max(1, round(S)))
        inner = chamfer(iw - 1, ih - 1, max(2, c - b * 0.6), sh + b, sh + b)
        for a_, b_ in zip(inner, inner[1:] + inner[:1]):
            pygame.draw.aaline(out, darker(lo, 0.5), a_, b_, max(1, round(S)))
        ac = p["accent"]
        line = chamfer(iw - 1 - 4 * S, ih - 1 - 4 * S, max(2, c - b), sh + b + 2 * S, sh + b + 2 * S)
        ln = pygame.Surface(out.get_size(), pygame.SRCALPHA)
        for a_, b_ in zip(line, line[1:] + line[:1]):
            pygame.draw.aaline(ln, (*ac, 255), a_, b_, 1)
        ln.fill((255, 255, 255, 120 if accent else 55), special_flags=pygame.BLEND_RGBA_MULT)
        out.blit(ln, (0, 0))
        # уголки: нарисованные или заклёпки с ромбом
        corner = self.art("corner")
        if corner is not None:
            cs = round(min(34 * S, w * 0.4, h * 0.6))
            cimg = pygame.transform.smoothscale(corner, (cs, round(cs * corner.get_height() / corner.get_width())))
            out.blit(cimg, (sh - 2 * S, sh - 2 * S))
            out.blit(pygame.transform.flip(cimg, True, False), (sh + w - cimg.get_width() + 2 * S, sh - 2 * S))
            out.blit(pygame.transform.flip(cimg, False, True), (sh - 2 * S, sh + h - cimg.get_height() + 2 * S))
            out.blit(pygame.transform.flip(cimg, True, True),
                     (sh + w - cimg.get_width() + 2 * S, sh + h - cimg.get_height() + 2 * S))
        else:
            rr = max(2, round(2.6 * S))
            for cx, cy in ((c * 0.75, c * 0.75), (w - c * 0.75, c * 0.75), (c * 0.75, h - c * 0.75),
                           (w - c * 0.75, h - c * 0.75)):
                self._rivet(out, sh + cx, sh + cy, rr)
            if accent and w > 120 * S:
                self._gem(out, sh + w / 2, sh + b / 2 + 0.5, max(3, round(4 * S)), ac)
        return out

    def _panel_art(self, w, h, S, alpha, accent):
        """Панель из набора героя: фон — середина нарисованной панели, по краям — кайма, в углах — орнамент."""
        sh = round(10 * S)
        out = pygame.Surface((w + 2 * sh, h + 2 * sh), pygame.SRCALPHA)
        t = round(max(5, min(11, h * 0.2)) * S)               # толщина каймы
        cs = round(max(16, min(44, min(w, h) * 0.8 / S, 44)) * S)   # уголок
        c = max(3, round(6 * S))
        shadow = apply_mask(pygame.Surface(out.get_size(), pygame.SRCALPHA),
                            mask(out.get_size(), chamfer(w, h, c, sh + 2 * S, sh + 4 * S)))
        shadow.fill((0, 0, 0, 160), special_flags=pygame.BLEND_RGBA_MULT)
        out.blit(blur(shadow, 5), (0, 0))
        fill = self.art("fill")
        fw, fh = fill.get_size()
        core = fill.subsurface((int(fw * 0.16), int(fh * 0.16), int(fw * 0.68), int(fh * 0.68)))
        body = pygame.transform.smoothscale(core, (w - 2, h - 2))
        body.blit(vgrad(w - 2, h - 2, [(0, (255, 255, 255)), (1, (165, 160, 155))]), (0, 0),
                  special_flags=pygame.BLEND_RGB_MULT)
        body.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        out.blit(apply_mask(body, mask((w - 2, h - 2), chamfer(w - 2, h - 2, c))), (sh + 1, sh + 1))
        edge = self.art("edge")
        ek = t / edge.get_height()
        tile = pygame.transform.smoothscale(edge, (max(4, round(edge.get_width() * ek)), t))
        tile = tile.subsurface((tile.get_width() // 8, 0, tile.get_width() * 3 // 4, t)).copy()  # без торцов
        horiz = pygame.Surface((w, t), pygame.SRCALPHA)
        for x in range(0, w, tile.get_width()):
            horiz.blit(tile, (x, 0))
        vert = pygame.transform.rotate(pygame.transform.scale(horiz, (h, t)) if h != w else horiz, 90)
        out.blit(horiz, (sh, sh))
        out.blit(pygame.transform.flip(horiz, False, True), (sh, sh + h - t))
        out.blit(vert, (sh, sh))
        out.blit(pygame.transform.flip(vert, True, False), (sh + w - t, sh))
        corner = self.art("corner")
        ck = cs / max(corner.get_size())
        cimg = pygame.transform.smoothscale(corner, (max(1, round(corner.get_width() * ck)),
                                                     max(1, round(corner.get_height() * ck))))
        o = round(3 * S)
        out.blit(cimg, (sh - o, sh - o))
        out.blit(pygame.transform.flip(cimg, True, False), (sh + w - cimg.get_width() + o, sh - o))
        out.blit(pygame.transform.flip(cimg, False, True), (sh - o, sh + h - cimg.get_height() + o))
        out.blit(pygame.transform.flip(cimg, True, True), (sh + w - cimg.get_width() + o, sh + h - cimg.get_height() + o))
        return out

    def _rivet(self, out, x, y, r):
        hi, mid, lo = self.p["metal"]
        pygame.draw.aacircle(out, darker(lo, 0.5), (x + 0.6, y + 0.8), r + 1)
        pygame.draw.aacircle(out, mid, (x, y), r)
        pygame.draw.aacircle(out, lighter(hi, 0.45), (x - r * 0.3, y - r * 0.35), max(1, r * 0.45))

    def _gem(self, out, x, y, r, col):
        pts = [(x, y - r), (x + r, y), (x, y + r), (x - r, y)]
        pygame.draw.polygon(out, darker(self.p["metal"][2], 0.4), [(px * 1.0, py) for px, py in
                                                                    [(x, y - r - 2), (x + r + 2, y), (x, y + r + 2), (x - r - 2, y)]])
        pygame.draw.polygon(out, col, pts)
        pygame.draw.polygon(out, lighter(col, 0.6), [(x, y - r), (x + r * 0.5, y - r * 0.2), (x, y), (x - r * 0.5, y - r * 0.2)])

    # ---------- кнопка ----------

    def button(self, surf, rect, label, hover=False, on=True, primary=False, t=0.0, size=18):
        """Плашка с острыми концами: металл, внутри кожа; доступная главная — дышит светом акцента."""
        native, S, pt = ctx(surf)
        r = pygame.Rect(rect)
        w, h = round(r.w * S), round(r.h * S)
        state = "off" if not on else ("hot" if hover else ("main" if primary else "on"))
        img = _remember(("btn", self.id, w, h, state, round(S, 3)), lambda: self._button(w, h, S, state))
        x, y = pt(r.topleft)
        g = round(14 * S)
        if on and (primary or hover):                       # свечение вокруг — пульс
            glow = _remember(("btn_glow", self.id, w, h, round(S, 3)), lambda: self._glow(w, h, S, g))
            k = 0.55 + 0.45 * math.sin(t * 3.2) if not hover else 1.0
            glow.set_alpha(int(255 * k))
            native.blit(glow, (round(x) - g, round(y) - g))
        native.blit(img, (round(x), round(y)))
        col = self.p["title"] if on else (140, 128, 116)
        if hover and on:
            col = lighter(col, 0.4)
        self.text(surf, label, r.center, size, col, center=True, title=True)
        return r

    def _shape(self, w, h, inset=0):
        k = h / 2
        i = inset
        return [(k * 0.55 + i, i), (w - k * 0.55 - i, i), (w - i, h / 2), (w - k * 0.55 - i, h - i),
                (k * 0.55 + i, h - i), (i, h / 2)]

    def _button(self, w, h, S, state):
        p = self.p
        hi, mid, lo = p["metal"]
        out = pygame.Surface((w, h), pygame.SRCALPHA)
        art = self.art("button")
        if art is not None:
            img = slice3(art, w, h, 0.22)
            if state == "off":
                img.fill((120, 120, 120), special_flags=pygame.BLEND_RGB_MULT)
            elif state == "hot":
                img.fill((36, 28, 18), special_flags=pygame.BLEND_RGB_ADD)
            elif state == "main":
                img.fill((18, 12, 4), special_flags=pygame.BLEND_RGB_ADD)
            return img
        band = apply_mask(vgrad(w, h, [(0, lighter(hi, 0.15)), (0.5, mid), (1, lo)]), mask((w, h), self._shape(w, h)))
        out.blit(band, (0, 0))
        b = max(2, round(4 * S))
        top, bot = p["fill"]
        if state == "hot":
            top, bot = lighter(top, 0.18), lighter(bot, 0.1)
        elif state == "main":
            top, bot = mix(top, p["accent"], 0.18), bot
        elif state == "off":
            top, bot = darker(top, 0.3), darker(bot, 0.3)
        body = vgrad(w, h, [(0, top), (1, bot)])
        body.blit(grain(w, h, p["grain"]), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        out.blit(apply_mask(body, mask((w, h), self._shape(w, h, b))), (0, 0))
        pts = self._shape(w - 1, h - 1, 0.5)
        for a_, b_ in zip(pts, pts[1:] + pts[:1]):
            col = lighter(hi, 0.35) if min(a_[1], b_[1]) < h / 2 - 1 and max(a_[1], b_[1]) <= h / 2 + 1 else darker(lo, 0.4)
            pygame.draw.aaline(out, col, a_, b_, max(1, round(S)))
        ins = self._shape(w - 1, h - 1, b + 2 * S)
        ac = p["accent"] if state in ("main", "hot") else lighter(lo, 0.25)
        for a_, b_ in zip(ins, ins[1:] + ins[:1]):
            pygame.draw.aaline(out, ac, a_, b_, 1)
        for x in (h * 0.3, w - h * 0.3):
            self._rivet(out, x, h / 2, max(2, round(2.6 * S)))
        return out

    def _glow(self, w, h, S, g):
        s = pygame.Surface((w + 2 * g, h + 2 * g), pygame.SRCALPHA)
        m = mask((w + 2 * g, h + 2 * g), [(x + g, y + g) for x, y in self._shape(w, h, -g * 0.35)])
        col = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        col.fill((*self.p["accent"], 150))
        return blur(apply_mask(col, m), 6)

    # ---------- шар энергии ----------

    def orb(self, surf, center, r, value, maxv, t=0.0, label=None, colors=None, pips=True):
        """Стеклянный шар в металлическом кольце, деления по кругу — по максимуму, горят доступные."""
        native, S, pt = ctx(surf)
        R = round(r * S)
        cols = colors or self.p["energy"]
        empty = not value
        key_cols = tuple(map(tuple, cols))
        glass = _remember(("orb", self.id, R, key_cols, empty), lambda: self._orb(R, cols, empty))
        ring = _remember(("ring", self.id, R, round(S, 3)), lambda: self._ring(R, S))
        x, y = pt(center)
        if not empty:                                       # мягкое свечение дышит
            halo = _remember(("halo", R, key_cols), lambda: self._halo(R, cols[1]))
            halo.set_alpha(int(150 + 90 * math.sin(t * 2.6)))
            native.blit(halo, (round(x - halo.get_width() / 2), round(y - halo.get_height() / 2)))
        native.blit(glass, (round(x - R), round(y - R)))
        native.blit(ring, (round(x - ring.get_width() / 2), round(y - ring.get_height() / 2)))
        if pips and maxv:
            for i in range(maxv):                           # деления — по верхней дуге
                a = math.pi * (1.15 + 0.7 * (i + 0.5) / maxv) if maxv > 1 else math.pi * 1.5
                rr = ring.get_width() / 2 + 2 * S if self.art("orb") is not None else R + 9 * S
                px, py = x + math.cos(a) * rr, y + math.sin(a) * rr
                lit = i < value
                pygame.draw.aacircle(native, darker(self.p["metal"][2], 0.4), (px, py), 5.2 * S)
                pygame.draw.aacircle(native, cols[1] if lit else (60, 50, 44), (px, py), 3.8 * S)
                if lit:
                    pygame.draw.aacircle(native, cols[0], (px - S, py - S), 1.6 * S)
        self.text(surf, label if label is not None else f"{value}/{maxv}", center, max(14, r * 0.62),
                  (255, 250, 238) if not empty else (170, 160, 150), center=True, title=True)

    def _orb(self, R, cols, empty):
        hi, midc, edge = cols
        if empty:
            hi, midc, edge = (110, 104, 100), (58, 52, 50), (22, 20, 20)
        g = rgrad(R, [(0, hi), (0.45, midc), (1, edge)], center=(0.4, 0.36))
        m = mask((2 * R, 2 * R), circle=((R, R), R - 0.5))
        out = apply_mask(g, m)
        hl = pygame.Surface((2 * R, 2 * R), pygame.SRCALPHA)       # блик стекла
        pygame.draw.ellipse(hl, (255, 255, 255, 120), (R * 0.42, R * 0.22, R * 0.75, R * 0.42))
        out.blit(blur(hl, 4), (0, 0))
        sh = pygame.Surface((2 * R, 2 * R), pygame.SRCALPHA)       # тень по нижнему краю
        pygame.draw.circle(sh, (0, 0, 0, 0), (R, R), R)
        return out

    def _ring(self, R, S):
        art = self.art("orb")
        if art is not None:
            k = (R + 1) / (ring_hole(art) * art.get_width())
            return pygame.transform.smoothscale(art, (round(art.get_width() * k), round(art.get_height() * k)))
        hi, mid, lo = self.p["metal"]
        th = max(3, round(6 * S))
        size = 2 * (R + th) + 2
        c = size / 2
        band = rgrad(size // 2, [(0, hi), (0.8, lighter(hi, 0.1)), (0.9, mid), (1, lo)], center=(0.42, 0.38))
        band = pygame.transform.smoothscale(band, (size, size))
        m = mask((size, size), circle=((c, c), R + th))
        hole = mask((size, size), circle=((c, c), R - 1))
        m.blit(hole, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        out = apply_mask(band, m)
        pygame.draw.aacircle(out, darker(lo, 0.5), (c, c), R + th, max(1, round(S)))
        pygame.draw.aacircle(out, lighter(hi, 0.4), (c - 0.5, c - 0.5), R + 0.5, max(1, round(S * 0.8)))
        for i in range(8):                                   # насечки по кольцу
            a = i * math.pi / 4 + math.pi / 8
            pygame.draw.aaline(out, darker(lo, 0.3), (c + math.cos(a) * (R + 1), c + math.sin(a) * (R + 1)),
                               (c + math.cos(a) * (R + th - 1), c + math.sin(a) * (R + th - 1)), max(1, round(S)))
        return out

    def _halo(self, R, col):
        g = round(R * 0.7)
        s = pygame.Surface((2 * (R + g), 2 * (R + g)), pygame.SRCALPHA)
        pygame.draw.circle(s, (*col, 110), (R + g, R + g), R + g * 0.6)
        return blur(s, 8)

    # ---------- медальоны и значки ----------

    def icon(self, key, px):
        """Значок key (i_melee, s_burn…) размером px родных пикселей."""
        def make():
            im = _load(os.path.join(ART, "icons", f"{key}.png"))
            if im is None:
                fb = ICON_FALLBACK.get(key)
                im = _load(os.path.join(CARD_ICONS, f"{fb}.png")) if fb else None
            if im is None:
                return None
            k = px / max(im.get_size())
            return pygame.transform.smoothscale(im, (max(1, round(im.get_width() * k)), max(1, round(im.get_height() * k))))
        return _remember(("icon", key, px), make)

    def medallion(self, surf, center, r, key, col, value=None, t=0.0, active=True):
        """Медальон намерения: диск с кольцом цвета намерения, значок, ниже — табличка с числом."""
        native, S, pt = ctx(surf)
        R = round(r * S)
        if self.art("medallion") is not None:
            return self._medallion_art(surf, center, r, key, col, value)
        img = _remember(("med", self.id, R, tuple(col)), lambda: self._medal(R, S, col))
        x, y = pt(center)
        native.blit(img, (round(x - img.get_width() / 2), round(y - img.get_height() / 2)))
        ic = self.icon(key, round(R * 1.15))
        if ic is not None:
            native.blit(ic, (round(x - ic.get_width() / 2), round(y - ic.get_height() / 2)))
        if value is not None and value != "":
            s = str(value)
            tw = max(R * 1.1, (self.size(s, max(10, round(r * 0.72)), True)[0] + 10) * S)
            tab = pygame.Rect(0, 0, round(tw), round(r * 0.78 * S))
            tab.center = (round(x), round(y + R * 0.98))
            timg = _remember(("tab", self.id, tab.size, tuple(col)), lambda: self._tab(tab.w, tab.h, S, col))
            native.blit(timg, tab.topleft)
            lx, ly = (tab.centerx - (surf.ox if G.is_canvas(surf) else 0)) / S, \
                     (tab.centery - (surf.oy if G.is_canvas(surf) else 0)) / S
            self.text(surf, s, (lx, ly), max(10, r * 0.72), (255, 246, 232), center=True, title=True)

    MED_CY, MED_TAB, MED_R = 0.41, 0.9, 0.34      # нарисованный медальон: центр диска, табличка, радиус диска

    def _medallion_art(self, surf, center, r, key, col, value):
        native, S, pt = ctx(surf)
        art = self.art("medallion")
        R = r * S
        k = R / (self.MED_R * art.get_width())
        size = (round(art.get_width() * k), round(art.get_height() * k))

        def make():
            out = pygame.Surface(size, pygame.SRCALPHA)
            out.blit(pygame.transform.smoothscale(art, size), (0, 0))
            glow = pygame.Surface(size, pygame.SRCALPHA)           # подсветка диска цветом намерения
            cx, cy = size[0] / 2, size[1] * self.MED_CY
            pygame.draw.circle(glow, (*col, 120), (cx, cy), R * 0.95)
            out.blit(blur(glow, 4), (0, 0))
            return out
        img = _remember(("medart", self.id, size, tuple(col)), make)
        x, y = pt(center)
        x0, y0 = x - size[0] / 2, y - size[1] * self.MED_CY
        native.blit(img, (round(x0), round(y0)))
        ic = self.icon(key, round(R * 1.5))
        if ic is not None:
            native.blit(ic, (round(x - ic.get_width() / 2), round(y - ic.get_height() / 2)))
        if value is not None and value != "":
            ty = (y0 + size[1] * self.MED_TAB - (surf.oy if G.is_canvas(surf) else 0)) / S
            self.text(surf, str(value), (center[0], ty), max(10, r * 0.7), (255, 246, 232), center=True, title=True)

    def _medal(self, R, S, col):
        hi, mid, lo = self.p["metal"]
        art = self.art("medallion")
        th = max(2, round(R * 0.2))
        size = 2 * (R + th) + 4
        c = size / 2
        out = pygame.Surface((size, size), pygame.SRCALPHA)
        sh = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(sh, (0, 0, 0, 140), (c + 1.5 * S, c + 2.5 * S), R + th)
        out.blit(blur(sh, 4), (0, 0))
        disc = rgrad(R, [(0, mix(darker(col, 0.55), (30, 22, 18), 0.4)), (1, (12, 9, 8))], center=(0.45, 0.4))
        out.blit(apply_mask(disc, mask((2 * R, 2 * R), circle=((R, R), R))), (c - R, c - R))
        if art is not None:
            a = pygame.transform.smoothscale(art, (size - 4, round((size - 4) * art.get_height() / art.get_width())))
            out.blit(a, (2, 2))
            return out
        ring_c = mix(mid, col, 0.55)
        pygame.draw.aacircle(out, darker(lo, 0.5), (c, c), R + th, max(1, round(S)))
        pygame.draw.aacircle(out, ring_c, (c, c), R + th - 1, th)
        pygame.draw.aacircle(out, lighter(ring_c, 0.45), (c - 0.4, c - 0.6), R + th - 1, max(1, round(S * 0.8)))
        pygame.draw.aacircle(out, darker(lo, 0.3), (c, c), R, max(1, round(S)))
        return out

    def _tab(self, w, h, S, col):
        hi, mid, lo = self.p["metal"]
        out = pygame.Surface((w, h), pygame.SRCALPHA)
        c = max(2, round(h * 0.35))
        band = apply_mask(vgrad(w, h, [(0, mix(mid, col, 0.4)), (1, darker(mix(lo, col, 0.3), 0.2))]),
                          mask((w, h), chamfer(w, h, c)))
        out.blit(band, (0, 0))
        b = max(1, round(2 * S))
        body = apply_mask(vgrad(w - 2 * b, h - 2 * b, [(0, (34, 24, 20)), (1, (14, 10, 9))]),
                          mask((w - 2 * b, h - 2 * b), chamfer(w - 2 * b, h - 2 * b, max(1, c - b))))
        out.blit(body, (b, b))
        return out

    def badge(self, surf, center, r, key, col, value=None):
        """Значок состояния: кружок с каймой цвета состояния, значок, число в углу."""
        native, S, pt = ctx(surf)
        R = round(r * S)
        img = _remember(("badge", self.id, R, tuple(col)), lambda: self._badge(R, S, col))
        x, y = pt(center)
        native.blit(img, (round(x - img.get_width() / 2), round(y - img.get_height() / 2)))
        ic = self.icon(key, round(R * (1.45 if self.art("badge") is not None else 1.3)))
        if ic is not None:
            native.blit(ic, (round(x - ic.get_width() / 2), round(y - ic.get_height() / 2)))
        if value not in (None, ""):
            self.text(surf, str(value), (center[0] + r * 0.62, center[1] + r * 0.5), max(10, r * 0.8),
                      (255, 248, 236), center=True, title=True)

    def _badge(self, R, S, col):
        art = self.art("badge")
        th = max(2, round(R * 0.16))
        size = 2 * (R + th) + 4
        c = size / 2
        out = pygame.Surface((size, size), pygame.SRCALPHA)
        disc = rgrad(R, [(0, mix(darker(col, 0.6), (26, 20, 16), 0.3)), (1, (10, 8, 7))], center=(0.45, 0.4))
        out.blit(apply_mask(disc, mask((2 * R, 2 * R), circle=((R, R), R))), (c - R, c - R))
        if art is not None:
            s2 = round(R / 0.35)                                # внутренний диск картинки ~0.35 ширины
            out = pygame.Surface((s2, s2), pygame.SRCALPHA)
            out.blit(pygame.transform.smoothscale(art, (s2, s2)), (0, 0))
            glow = pygame.Surface((s2, s2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*col, 110), (s2 / 2, s2 / 2), R * 0.95)
            out.blit(blur(glow, 4), (0, 0))
            return out
        pygame.draw.aacircle(out, darker(self.p["metal"][2], 0.5), (c, c), R + th, max(1, round(S)))
        pygame.draw.aacircle(out, mix(self.p["metal"][1], col, 0.6), (c, c), R + th - 1, th)
        pygame.draw.aacircle(out, lighter(col, 0.35), (c - 0.4, c - 0.6), R + th - 1, 1)
        return out

    # ---------- лента, деления, поднос ----------

    def ribbon(self, surf, rect, text, size=20, color=None):
        """Лента заголовка: плашка с вырезом «ласточкин хвост» на концах."""
        native, S, pt = ctx(surf)
        r = pygame.Rect(rect)
        w, h = round(r.w * S), round(r.h * S)
        img = _remember(("ribbon", self.id, w, h, round(S, 3)), lambda: self._ribbon(w, h, S))
        x, y = pt(r.topleft)
        native.blit(img, (round(x), round(y)))
        if text:
            self.text(surf, text, r.center, size, color or self.p["title"], center=True, title=True)
        return r

    def _ribbon(self, w, h, S):
        art = self.art("ribbon")
        if art is not None:
            return slice3(art, w, round(h * 1.0), 0.2)
        hi, mid, lo = self.p["metal"]
        n = h * 0.45
        pts = [(0, 0), (w, 0), (w - n, h / 2), (w, h), (0, h), (n, h / 2)]
        out = pygame.Surface((w, h), pygame.SRCALPHA)
        sh = apply_mask(pygame.Surface((w, h), pygame.SRCALPHA), mask((w, h), pts))
        band = apply_mask(vgrad(w, h, [(0, lighter(hi, 0.1)), (0.5, mid), (1, lo)]), mask((w, h), pts))
        out.blit(band, (0, 0))
        b = max(2, round(3 * S))
        inner = [(n + b * 0.5, b), (w - n - b * 0.5, b), (w - n - b * 0.5, h - b), (n + b * 0.5, h - b)]
        body = vgrad(w, h, [(0, self.p["fill"][0]), (1, self.p["fill"][1])])
        body.blit(grain(w, h, self.p["grain"]), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        out.blit(apply_mask(body, mask((w, h), inner)), (0, 0))
        for a_, b_ in zip(inner, inner[1:] + inner[:1]):
            pygame.draw.aaline(out, (*self.p["accent"], 255), a_, b_, 1)
        del sh
        return out

    def pips(self, surf, x, y, n, lit, w=30, h=10, gap=6, col=None):
        """Ряд делений-самоцветов (разгон, счётчики): горящие — цветом акцента."""
        native, S, pt = ctx(surf)
        col = col or self.p["accent"]
        on = self.art("pip_on")
        off = self.art("pip_off")
        if on is not None and off is not None:                 # самоцветы: ромбы по высоте, в ряд
            d = min(w + gap, h * 2.4)
            for i in range(n):
                art = on if i < lit else off
                c = (x + i * (w + gap) + w / 2, y + h / 2)
                ps = round(d * S)
                img = _remember(("pipart", id(art), ps), lambda a=art: pygame.transform.smoothscale(a, (ps, ps)))
                px, py = pt(c)
                native.blit(img, (round(px - ps / 2), round(py - ps / 2)))
            return
        for i in range(n):
            r = pygame.Rect(x + i * (w + gap), y, w, h)
            nr = pygame.Rect(*[round(v) for v in pt(r.topleft)], round(w * S), round(h * S))
            art = on if i < lit else off
            if art is not None:
                native.blit(_remember(("pipart", id(art), nr.size), lambda a=art: pygame.transform.smoothscale(a, nr.size)),
                            nr.topleft)
                continue
            img = _remember(("pip", self.id, nr.size, i < lit, tuple(col)), lambda lt=i < lit: self._pip(nr.w, nr.h, S, lt, col))
            native.blit(img, nr.topleft)

    def _pip(self, w, h, S, lit, col):
        c = max(1, round(h * 0.45))
        out = pygame.Surface((w, h), pygame.SRCALPHA)
        lo = self.p["metal"][2]
        out.blit(apply_mask(vgrad(w, h, [(0, darker(lo, 0.2)), (1, darker(lo, 0.6))]), mask((w, h), chamfer(w, h, c))),
                 (0, 0))
        if lit:
            b = max(1, round(1.5 * S))
            g = apply_mask(vgrad(w - 2 * b, h - 2 * b, [(0, lighter(col, 0.45)), (0.5, col), (1, darker(col, 0.35))]),
                           mask((w - 2 * b, h - 2 * b), chamfer(w - 2 * b, h - 2 * b, max(1, c - b))))
            out.blit(g, (b, b))
        return out

    def tray(self, surf, y0, y1, alpha=235):
        """Поднос под рукой: от прозрачного (y0) к плотному тёмному (y1 и ниже) — край земли не виден."""
        native, S, pt = ctx(surf)
        _, ya = pt((0, y0))
        _, yb = pt((0, y1))
        w = native.get_width()
        h = native.get_height() - round(ya)
        if h <= 0:
            return
        f = max(0.05, min(1.0, (yb - ya) / h))
        key = ("tray", self.id, w, h, round(f, 3), alpha)

        def make():
            img = vgrad(w, h, [(0, darker(self.p["fill"][1], 0.2)), (1, darker(self.p["fill"][1], 0.6))])
            s = pygame.Surface((1, h), pygame.SRCALPHA)
            for yy in range(h):
                k = min(1.0, (yy / max(1, h - 1)) / f)
                s.set_at((0, yy), (255, 255, 255, int(alpha * k ** 1.6)))
            return apply_mask(img, pygame.transform.scale(s, (w, h)))
        native.blit(_remember(key, make), (0, round(ya)))


def use(hero):
    if hero not in _skins:
        _skins[hero] = Skin(hero)
    return _skins[hero]
