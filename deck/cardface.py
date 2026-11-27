"""Лицо карты «Спуска» (docs/descent.md, итерация 4): большой рисунок + лента с именем + текст действия +
полоса простого применения вверх ногами (повернул карту ПКМ — она сверху).

Карта рисуется один раз в высоком разрешении (FW×FH, сглаженные края) и только уменьшается/поворачивается —
так в руке, при наклоне и увеличении она остаётся чёткой. Текст — как в Slay the Spire: «Нанести 6 урона.
Толчок 1.» — числа крупно белым, ключевые слова золотом. Рисунок — фрагмент иллюстрации игры
(data/deck/cards.json → ill), потом свои иллюстрации (prompts_expedition.md, лист DC1).
"""
import os
from itertools import groupby

import pygame

from ui import theme as T
from ui import settings

from . import gfx as G
from .model import CARD_RARITY_COLOR, card_extras, phrase

FW, FH = 512, 768                 # лицо в высоком разрешении (пиксельные рамки: 2×2 на пиксель арта)
OW, OH = 300, 440                 # старое лицо (рисуется кодом, если нет картинок рамок)
DW, DH = 184, 276                 # размер в руке
W, H = DW, DH                     # для экранов: «обычный» размер карты
ILL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "illustrations", "hd")
ART = pygame.Rect(16, 16, OW - 32, 196)       # окно рисунка (старое лицо)
RIBBON_Y = 192                                # лента с именем — на нижнем крае рисунка
TEXT = pygame.Rect(22, 262, OW - 44, 102)     # текст основного применения (старое лицо)
ALT_H = 58                                    # полоса простого применения (внизу, вверх ногами)
STYLE = {   # рамка (светлая, тёмная), лента, свечение текста
    "attack": ((196, 96, 64), (92, 34, 22), (130, 44, 30), (255, 150, 100)),
    "skill": ((96, 150, 214), (30, 52, 92), (40, 70, 120), (150, 200, 255)),
    "power": ((176, 120, 230), (60, 30, 96), (86, 46, 130), (220, 170, 255)),
}
TYPE_NAME = {"attack": "Атака", "skill": "Умение", "power": "Сила"}
GOLD = (255, 214, 120)
LIT = (140, 255, 130)       # выполненное условие
TAG = (150, 205, 255)       # тег
NUM = (255, 255, 255)
DMG = (135, 255, 125)       # реальный урон с баффами — зелёным
_cache = {}
_ill = {}
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
_fonts = {}


class FontWithSymbols:
    """Основной шрифт и запасные глифы для стрелок и знаков интерфейса."""

    def __init__(self, primary, symbols):
        self.primary = primary
        self.symbols = symbols
        self._glyphs = {}
        self.get_height = primary.get_height

    def _face(self, char):
        face = self._glyphs.get(char)
        if face is None:
            metrics = self.primary.metrics(char)[0]
            face = self.primary if char.isspace() or (metrics and any(metrics[:4])) else self.symbols
            self._glyphs[char] = face
        return face

    def _runs(self, text):
        return [(face, "".join(chars)) for face, chars in groupby(text, self._face)]

    def size(self, text):
        runs = self._runs(text)
        if not runs:
            return self.primary.size(text)
        return sum(face.size(part)[0] for face, part in runs), self.primary.get_height()

    def render(self, text, antialias, color):
        runs = self._runs(text)
        if not runs or (len(runs) == 1 and runs[0][0] is self.primary):
            return self.primary.render(text, antialias, color)
        images = [(face, face.render(part, antialias, color)) for face, part in runs]
        ascent = self.primary.get_ascent()
        out = pygame.Surface((sum(img.get_width() for _, img in images), self.primary.get_height()),
                             pygame.SRCALPHA)
        x = 0
        for face, img in images:
            out.blit(img, (x, ascent - face.get_ascent()))
            x += img.get_width()
        return out


def font(size, bold=False, *, style=None):
    """Шрифт интерфейса и лиц карт, в том числе для предпросмотра."""
    style = title_style() if style is None else style
    key = (style, size, bold)
    if key not in _fonts:
        file = settings.DESCENT_FONTS[style][1]
        if style == "pt_serif" and bold:
            file = "PTSerif-Bold.ttf"
        p = os.path.join(FONT_DIR, file)
        if os.path.exists(p):
            face = pygame.font.Font(p, size)
            if bold and style not in ("pt_serif", "alegreya_sc"):
                face.set_bold(True)
            _fonts[key] = FontWithSymbols(face, T.system_font(size, bold))
        else:
            _fonts[key] = T.system_font(size, bold)
    return _fonts[key]


def title_style():
    key = settings.SETTINGS.get("descent_font")
    return key if key in settings.DESCENT_FONTS else settings.DEFAULTS["descent_font"]


def title_font(size):
    return font(size, True)


# ---------- текст действия ----------

def _tokens(s):
    """Разметка → слова со стилем: (слово, «n» число | «k» ключевое | «t» текст)."""
    out = []
    for word in s.split():
        style = "t"
        core = word
        if word.startswith("@") and "{" in word:            # реальный урон с баффами
            style = "d"
            core = word.replace("@", "").replace("{", "").replace("}", "")
        elif "{" in word:
            style = "n"
            core = word.replace("{", "").replace("}", "")
        elif "~" in word:                                 # выполненное условие
            style = "l"
            core = word.replace("~", "")
        elif "*" in word:
            style = "k"
            core = word.replace("*", "")
        elif "[" in word:                                 # тег
            style = "g"
            core = word.replace("[", "").replace("]", "")
        elif word.startswith("^"):                        # феи: ^+2 / ^-1 / ^все
            style = "f"
            core = word[1:]
        out.append((core, style))
    return out


_FAE_ICONS = {}


def _fae_icon(size, neg=False, all_=False):
    """Значок фей: светящийся зелёный огонёк с крыльями; знак показывает прибавку/трату."""
    key = (size, neg, all_)
    got = _FAE_ICONS.get(key)
    if got is not None:
        return got
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = (128, 232, 150) if not neg else (238, 148, 92)
    dark = (18, 44, 28) if not neg else (64, 28, 14)
    r = max(2, size // 3)
    cx, cy = size // 2, size // 2
    pygame.draw.polygon(s, dark, [(cx - r // 2, cy), (1, max(1, cy - r)), (max(1, cx - r), cy - r // 2)])
    pygame.draw.polygon(s, dark, [(cx + r // 2, cy), (size - 2, max(1, cy - r)), (min(size - 1, cx + r), cy - r // 2)])
    pygame.draw.circle(s, dark, (cx, cy), r + 2)
    pygame.draw.circle(s, c, (cx, cy), r)
    pygame.draw.circle(s, (235, 255, 225), (cx - r // 3, cy - r // 3), max(1, r // 3))
    _FAE_ICONS[key] = s
    return s


def rich(surf, s, rect, size, color, dim=False, left=False, boxes=None, clip=False):
    """Текст по центру rect с переносом: числа крупнее и белым, ключевые слова золотом. Возвращает высоту.
    boxes — сюда кладутся места выделенных слов (rect, слово, стиль) — для наведения в режиме чтения.
    clip — если текст не влез, оборвать его многоточием, а не рисовать за пределами rect."""
    if G.is_canvas(surf):                                 # холст — в родном разрешении
        c = surf
        return rich(c.native, s, c.rect(rect), max(6, round(size * c.S)), color, dim, left,
                    boxes=boxes, clip=clip) / c.S
    fonts = {"t": font(size), "k": font(size, True), "n": font(size + 4, True), "l": font(size, True),
             "g": font(size, True), "d": font(size + 4, True)}
    cols = {"t": color, "k": GOLD, "n": NUM, "l": LIT, "g": TAG, "d": DMG}
    if dim:
        cols = {k: T.mix(v, (40, 34, 28), 0.3) for k, v in cols.items()}       # тусклее, но читается
    space = fonts["t"].size(" ")[0]

    def metric(word, st):
        if st == "f":
            ic = max(10, round(size * 0.92))
            num = fonts["k"].render(word, True, (170, 235, 180))
            return ic + 3 + num.get_width()
        return fonts[st].size(word)[0]

    lines, cur, w = [], [], 0
    for word, st in _tokens(s):
        ww = metric(word, st)
        if cur and w + space + ww > rect.w:
            lines.append((cur, w))
            cur, w = [], 0
        cur.append((word, st, ww))
        w += (space if len(cur) > 1 else 0) + ww
    if cur:
        lines.append((cur, w))
    lh = fonts["n"].get_height() - 2
    if clip and lines:
        max_lines = max(1, rect.h // lh)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            words, lw = lines[-1]
            ell_w = fonts["t"].size("…")[0]
            while words and lw + space + ell_w > rect.w:
                _, _, ww = words.pop()
                lw -= ww + space
            words.append(("…", "t", ell_w))
            lines[-1] = (words, lw + space + ell_w)
    y = rect.y if left else rect.y + max(0, (rect.h - lh * len(lines)) // 2)
    for words, lw in lines:
        x = rect.x if left else rect.centerx - lw / 2
        for word, st, ww in words:
            if st == "f":
                neg = word.startswith("-")
                ic = _fae_icon(max(10, round(size * 0.92)), neg=neg, all_=word.lstrip("+-") == "все")
                yy = y + (lh - ic.get_height()) // 2 + 1
                surf.blit(ic, (round(x), yy))
                img = fonts["k"].render(word, True, (238, 148, 92) if neg else (170, 235, 180))
                surf.blit(img, (round(x) + ic.get_width() + 3, y + (lh - img.get_height()) // 2 + 1))
                if boxes is not None:
                    boxes.append((pygame.Rect(round(x), yy, ww, ic.get_height()), "Феи", "k"))
                x += ww + space
                continue
            img = fonts[st].render(word, True, cols[st])
            sh = fonts[st].render(word, True, (0, 0, 0))
            yy = y + (lh - img.get_height()) // 2 + (1 if st == "n" else 0)
            surf.blit(sh, (x + 1, yy + 1))
            surf.blit(img, (x, yy))
            if boxes is not None and st in ("k", "l", "g"):
                boxes.append((pygame.Rect(round(x), yy, ww, img.get_height()), word, st))
            x += ww + space
        y += lh
    return lh * len(lines)


# ---------- рисунок ----------

def illustration(spec, size):
    """Фрагмент иллюстрации: spec = [имя, центр x, центр y (доли), ширина (доля)]."""
    key = (tuple(spec), size)
    if key in _ill:
        return _ill[key]
    img = None
    try:
        src, fx, fy, z = spec
        full = pygame.image.load(os.path.join(ILL_DIR, src + ".png"))
        W0, H0 = full.get_size()
        cw = int(W0 * z)
        ch = int(cw * size[1] / size[0])
        x = int(min(max(0, fx * W0 - cw / 2), W0 - cw))
        y = int(min(max(0, fy * H0 - ch / 2), H0 - ch))
        img = pygame.transform.smoothscale(full.subsurface((x, y, cw, ch)), size)
    except (pygame.error, OSError, ValueError, TypeError):
        img = None
    _ill[key] = img
    return img


def _vgrad(surf, rect, top, bottom, radius=0):
    g = pygame.Surface(rect.size, pygame.SRCALPHA)
    for y in range(rect.h):
        pygame.draw.line(g, T.mix(top, bottom, y / max(1, rect.h - 1)), (0, y), (rect.w, y))
    if radius:
        mask = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
        g.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(g, rect.topleft)


HEAT = (255, 130, 50)


def _gem(surf, center, cost, ok, heat=False):
    """Цена: голубой кристалл энергии или раскалённый уголь жара (Пиромантка)."""
    x, y = center
    col = HEAT if heat else T.AP_COLOR
    pygame.draw.circle(surf, (14, 10, 8), (x, y), 27)
    pygame.draw.circle(surf, (200, 160, 90) if ok else (110, 100, 90), (x, y), 25)
    pygame.draw.circle(surf, col if ok else (88, 82, 76), (x, y), 21)
    pygame.draw.circle(surf, T.mix(col, (255, 255, 255), 0.55) if ok else (120, 112, 104), (x - 7, y - 8), 6)
    f = T.font(30, True)
    img = f.render(str(cost), True, (16, 10, 6))
    surf.blit(img, (x - img.get_width() / 2, y - img.get_height() / 2))


def _ribbon(surf, rect, color, name, frame):
    """Лента с именем: концы-ласточкины хвосты, тень, имя по центру (длинное — мельче)."""
    x, y, w, h = rect
    dark = T.mix(color, (0, 0, 0), 0.45)
    for side in (-1, 1):
        bx = x - 10 if side < 0 else x + w + 10
        ex = x + 8 if side < 0 else x + w - 8
        pts = [(ex, y + 6), (bx, y + 6), (bx + 8 * side * -1, y + h / 2 + 3), (bx, y + h + 3), (ex, y + h + 3)]
        pygame.draw.polygon(surf, dark, pts)
    body = pygame.Rect(x, y, w, h)
    _vgrad(surf, body, T.mix(color, (255, 255, 255), 0.18), T.mix(color, (0, 0, 0), 0.25))
    pygame.draw.line(surf, T.mix(frame, (255, 255, 255), 0.3), (x, y), (x + w, y), 2)
    pygame.draw.line(surf, (14, 10, 8), (x, y + h), (x + w, y + h), 2)
    size = 24
    while size > 15 and title_font(size).size(name)[0] > w - 18:
        size -= 1
    f = title_font(size)
    img = f.render(name, True, (250, 240, 220))
    sh = f.render(name, True, (10, 6, 4))
    cx, cy = x + w / 2 - img.get_width() / 2, y + h / 2 - img.get_height() / 2
    surf.blit(sh, (cx + 2, cy + 2))
    surf.blit(img, (cx, cy))


def _alt_strip(card, alt_ok, w):
    """Полоса простого применения — рисуется прямо и переворачивается целиком."""
    s = pygame.Surface((w, ALT_H), pygame.SRCALPHA)
    col = (150, 230, 160) if alt_ok else (120, 120, 110)
    body = s.get_rect().inflate(-4, -6)
    if card.d["alt"]["target"] == "none":                 # простого применения нет
        _vgrad(s, body, (26, 22, 20), (16, 14, 12), radius=10)
        pygame.draw.rect(s, (70, 60, 52), body, 2, border_radius=10)
        tag = T.font(14, True).render("БЕЗ ПРОСТОГО ПРИМЕНЕНИЯ", True, (120, 110, 100))
        s.blit(tag, (body.centerx - tag.get_width() // 2, body.centery - tag.get_height() // 2))
        return s
    _vgrad(s, body, (20, 34, 22), (12, 20, 14), radius=10)
    pygame.draw.rect(s, T.mix(col, (0, 0, 0), 0.35), body, 2, border_radius=10)
    tag = T.font(14, True).render("ПРОСТО · 0", True, col)
    s.blit(tag, (body.x + 12, body.y + 4))
    rich(s, phrase(card.d["alt"], preview=(card.preview or {}).get("alt")),
         pygame.Rect(body.x + 8, body.y + 18, body.w - 16, body.h - 20), 17,
         (215, 235, 215), dim=not alt_ok)
    return s


_MEASURE = pygame.Surface((1, 1))     # «рисовать» сюда — только чтобы узнать высоту текста


def _levels(s, card, rect, heat, lit=(), k=1.0, boxes=None):
    """Карта Пиромантки: три строки-уровня (жар → эффект), выбранная — подсвечена, недоступные — тусклые.
    k — масштаб (лицо 512×768 — 1.65)."""
    lv = card.levels
    n = len(lv)
    sel = min(card.lvl, n - 1)
    # сверху — уровни кружками (жар за уровень): выбранный крупнее и в оправе, недоступные — тусклые
    pr = round(10 * k)
    gap = round(30 * k)
    cy = rect.y + round(2 * k)                               # у верхней кромки плашки — место тексту
    x0 = rect.centerx - (n - 1) * gap / 2
    for i, L in enumerate(lv):
        ok = heat is None or L["heat"] <= heat
        cx = round(x0 + i * gap)
        R = round(pr * (1.25 if i == sel else 0.9))
        if i == sel:
            pygame.draw.circle(s, (255, 214, 150), (cx, cy), R + max(2, round(2 * k)))
        pygame.draw.circle(s, (14, 10, 8), (cx, cy), R + 1)
        pygame.draw.circle(s, HEAT if ok else (90, 80, 70), (cx, cy), R - 1)
        num = font(round((17 if i == sel else 13) * k), True).render(str(L["heat"]), True, (20, 10, 4))
        s.blit(num, (cx - num.get_width() / 2, cy - num.get_height() / 2))
    # ниже — только текст выбранного уровня, крупно
    L = lv[sel]
    ok = heat is None or L["heat"] <= heat
    top = cy + round(pr * 1.25) + round(5 * k)
    tr = pygame.Rect(rect.x, top, rect.w, rect.bottom - top)
    txt = phrase(L["main"], lit=lit, preview=(card.preview or {}).get("main"))
    size = round(21 * k)
    while size > round(9 * k) and rich(_MEASURE, txt, tr, size, (0, 0, 0)) > tr.h:
        size -= 1
    rich(s, txt, tr, size, (240, 226, 206), dim=not ok, boxes=boxes)


def _face_old(card, main_ok=True, alt_ok=True, hot=False, heat=None, lit=()):
    """Лицо карты OW×OH (кэш по состоянию). heat — жар героя: тусклые уровни, на которые не хватает;
    lit — выполненные сейчас условия (подсвечиваются зелёным)."""
    lit = frozenset(lit or ())
    key = (title_style(), card.cid, tuple(card.picks), card.uses, card.ready, card.insight_misses, main_ok, alt_ok, hot, card.lvl,
           card.spirit_rank, heat, lit,
           card.divine["id"] if card.divine else None, repr(card.alt_up), card.preview_key())
    if key in _cache:
        return _cache[key]
    d = card.d
    light, dark, band, glow = STYLE.get(d["type"], STYLE["skill"])
    s = pygame.Surface((OW, OH), pygame.SRCALPHA)
    body = s.get_rect()
    pygame.draw.rect(s, (12, 9, 7), body, border_radius=22)                    # контур
    _vgrad(s, body.inflate(-4, -4).move(0, 0), light, dark, radius=20)          # металл рамки
    inner = body.inflate(-16, -16)
    _vgrad(s, inner, (38, 30, 24), (22, 17, 13), radius=14)                     # поле карты
    pygame.draw.rect(s, T.mix(dark, (0, 0, 0), 0.3), inner, 2, border_radius=14)
    # рисунок
    art = pygame.Rect(ART)
    ill = illustration(d.get("ill"), art.size) if d.get("ill") else None
    if ill is not None:
        s.blit(ill, art)
    else:
        _vgrad(s, art, T.mix(band, (0, 0, 0), 0.3), (16, 12, 10))
    shade = pygame.Surface(art.size, pygame.SRCALPHA)                           # виньетка снизу под ленту
    for y in range(art.h):
        k = max(0.0, (y - art.h * 0.55) / (art.h * 0.45))
        pygame.draw.line(shade, (8, 6, 4, int(170 * k * k)), (0, y), (art.w, y))
    s.blit(shade, art)
    pygame.draw.rect(s, (12, 9, 7), art, 3, border_radius=6)
    pygame.draw.rect(s, T.mix(light, (255, 255, 255), 0.25), art.inflate(2, 2), 1, border_radius=7)
    if card.rarity:
        col = CARD_RARITY_COLOR.get(card.rarity, (220, 220, 220))
        for k in range(card.rarity):
            pygame.draw.circle(s, (18, 12, 8), (art.x + 16 + k * 14, art.bottom - 12), 6)
            pygame.draw.circle(s, col, (art.x + 16 + k * 14, art.bottom - 12), 4)
    # лента, тип, цена
    _ribbon(s, (28, RIBBON_Y, OW - 56, 40), band, card.name, light)
    tn = " · ".join(card.tags) or TYPE_NAME.get(d["type"], "")       # теги — по ним работают условия
    ti = T.font(13, True).render(tn.upper(), True, TAG)
    s.blit(ti, (OW / 2 - ti.get_width() / 2, RIBBON_Y + 44))
    react = bool(d.get("react"))
    if react:                                              # реакция: не играется — не тусклая
        main_ok = True
    _gem(s, (34, 34), "—" if react else card.cost_label, main_ok, heat=card.uses_heat)
    if card.divine:                                                             # дар бога — флажок под ценой
        col = tuple(card.divine.get("color", (200, 180, 255)))
        flag = [(18, 58), (50, 58), (50, 92), (34, 82), (18, 92)]
        pygame.draw.polygon(s, (12, 9, 7), [(x, y + 2) for x, y in flag])
        pygame.draw.polygon(s, col, flag)
        pygame.draw.polygon(s, T.mix(col, (255, 255, 255), 0.5), flag, 2)
        ch = T.font(16, True).render(card.divine["name"][0], True, (20, 14, 10))
        s.blit(ch, (34 - ch.get_width() / 2, 61))
    for k in range(card.tier):                                                  # ступени прозрения
        cx = OW - 34 - k * 22
        pygame.draw.circle(s, (14, 10, 8), (cx, 32), 10)
        pygame.draw.circle(s, GOLD, (cx, 32), 8)
    # текст основного применения
    tb = pygame.Rect(TEXT)
    _vgrad(s, tb.inflate(10, 8), (28, 22, 18), (20, 16, 12), radius=10)
    extra = card_extras(d, lit)
    if card.levels:
        top = tb.y - 14                                   # строки уровней — до полоски роста, не на неё
        bottom = OH - ALT_H - 16 - 4 - (18 if extra else 0)
        _levels(s, card, pygame.Rect(tb.x, top, tb.w, bottom - top), heat, lit)
        if extra:
            rich(s, extra, pygame.Rect(tb.x, bottom, tb.w, 16), 11, (220, 210, 190))
    else:
        txt = phrase(d["main"], d.get("exhaust"), lit, preview=(card.preview or {}).get("main")) + \
              (" " + extra if extra else "")
        size = 19
        while size > 12 and rich(_MEASURE, txt, tb, size, (0, 0, 0)) > tb.h + 6:
            size -= 1
        rich(s, txt, tb, size, (236, 226, 208), dim=not main_ok, clip=True)
    # путь к прозрению
    g = card.growth_next()
    py = OH - ALT_H - 16
    if g:
        k = card.insight_progress()
        bar = pygame.Rect(40, py, OW - 80, 6)
        pygame.draw.rect(s, (14, 10, 8), bar.inflate(4, 4), border_radius=4)
        pygame.draw.rect(s, (60, 48, 34), bar, border_radius=3)
        if k:
            pygame.draw.rect(s, GOLD if k >= 1 else (190, 150, 90), (bar.x, bar.y, int(bar.w * k), bar.h), border_radius=3)
    # простое — вверх ногами внизу
    strip = _alt_strip(card, alt_ok, OW - 28)
    s.blit(pygame.transform.rotate(strip, 180), (14, OH - ALT_H - 10))
    if lit and main_ok and not hot:                       # условие выполнено — зелёная кайма
        pygame.draw.rect(s, LIT, body.inflate(-2, -2), 3, border_radius=21)
    if hot:
        pygame.draw.rect(s, T.SELECT, body.inflate(-2, -2), 4, border_radius=21)
    if not main_ok and not alt_ok:
        dim = pygame.Surface((OW, OH), pygame.SRCALPHA)
        pygame.draw.rect(dim, (0, 0, 0, 110), dim.get_rect(), border_radius=22)
        s.blit(dim, (0, 0))
    if len(_cache) > 200:
        _cache.clear()
        G._rot.clear()                                     # повёрнутые копии — от старых лиц
    _cache[key] = s
    return s


def face(card, main_ok=True, alt_ok=True, hot=False, heat=None, lit=(), tilt=None, width=None):
    """Лицо карты FW×FH. С картинками рамок (assets/cards) — пиксельное оформление с объёмом (deck/cardart.py,
    tilt — наклон); без них — старое лицо, нарисованное кодом."""
    from . import cardart
    if cardart.available():
        return cardart.compose(card, main_ok, alt_ok, hot, heat, lit, tilt, width)
    lit = frozenset(lit or ())
    key = ("old", title_style(), card.cid, tuple(card.picks), card.uses, card.ready, card.insight_misses, main_ok, alt_ok, hot, card.lvl,
           card.spirit_rank, heat, lit,
           card.divine["id"] if card.divine else None, repr(card.alt_up), card.preview_key())
    if key not in _cache:
        _cache[key] = pygame.transform.smoothscale(_face_old(card, main_ok, alt_ok, hot, heat, lit), (FW, FH))
    return _cache[key]


def back(hero):
    """Рубашка героя (или None)."""
    from . import cardart
    return cardart.back(hero) if cardart.available() else None


def blit_card(surf, r, card, main_ok=True, alt_ok=True, hot=False, angle=0.0, alpha=255, heat=None, tilt=None,
              lit=()):
    """Карта в прямоугольник r (масштаб по ширине, по центру); angle — поворот (180 — простое сверху)."""
    if G.is_canvas(surf):                                 # лицо — сразу в размере на экране (текст чёткий)
        img = face(card, main_ok, alt_ok, hot, heat, lit, tilt=tilt, width=round(r.w * surf.S))
        if tilt:                                          # наклон — карта поворачивается вся, в 3D
            surf.blit_card3d(img, r.center, angle, r.w / img.get_width(), tilt, alpha=alpha)
        else:
            surf.blit_hd(img, r.center, angle, r.w / img.get_width(), alpha=alpha)
        return
    img = face(card, main_ok, alt_ok, hot, heat, lit, tilt=tilt)
    k = r.w / FW
    img = pygame.transform.rotozoom(img, angle, k) if angle else pygame.transform.smoothscale(img, (r.w, round(FH * k)))
    if alpha < 255:
        img.set_alpha(alpha)
    surf.blit(img, (r.centerx - img.get_width() // 2, r.centery - img.get_height() // 2))


def level_at(card, r, pos):
    """Кружок уровня карты Пиромантки под точкой pos (карта нарисована в r через blit_card) — номер или None."""
    if not card.levels:
        return None
    from . import cardart
    if not cardart.available():
        return None
    k = r.w / FW
    ox, oy = r.centerx - FW * k / 2, r.centery - FH * k / 2
    for i, (cx, cy), R in cardart.level_pips(card):
        if (pos[0] - (ox + cx * k)) ** 2 + (pos[1] - (oy + cy * k)) ** 2 <= (R * k + 4) ** 2:
            return i
    return None


def set_level(card, i):
    """Выбрать уровень (цену в жаре) вручную — вне боя и в бою."""
    if card.levels:
        card.manual = True
        card.lvl = max(0, min(len(card.levels) - 1, i))


def wheel_level(card, dy):
    """Колесо над картой с уровнями: вверх — дороже и сильнее. True — уровень сменился."""
    if not card or not card.levels:
        return False
    set_level(card, card.lvl + (1 if dy > 0 else -1))
    return True


def chips(u):
    """Совместимость (тесты, бот): действия применения списком (значок, число)."""
    out = []
    t = u["target"]
    if t == "cell_step":
        out.append(("step", str(u.get("step", 1))))
    elif t == "cell_dash":
        out.append(("dash", str(u.get("dash", 1))))
    elif t == "reach":
        out.append(("reach", str(u.get("reach", 1))))
    for op in u.get("do", []):
        out.append((op["op"], str(op.get("n", "")) if op.get("n") else ""))
    if u.get("power"):                                    # Сила до конца боя
        out.append(("power", ""))
    return out


def art(name, size):
    """Совместимость: иконка игры по имени (если иллюстрации нет)."""
    from ui import icons as IC
    img = IC.asset_icon(name, 32) if name else None
    return pygame.transform.scale(img, (size, size)) if img is not None else None
