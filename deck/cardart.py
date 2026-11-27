"""Пиксельное оформление карт «Спуска» с объёмом (prompts_expedition.md, DC2; tools/import_card_art.py).

Лицо карты 512×768 собирается из слоёв на разной глубине — при наклоне (мышь над картой, тянут, просмотр
по Shift) они сдвигаются по-разному, как будто смотришь в окно:
  картинка (DC1) — глубже окна, сдвигается против наклона; поверх неё — блик стекла;
  основа: плашки текста и простого, тень окна, рамка по типу карты (атака / умение / сила / реакция);
  содержимое: имя на ленте, теги со значками, текст, простое вверх ногами, цена в гнезде, флажок бога;
  накладки (уголки, навершие, кольцо цены, планка) — ближе, сдвигаются по наклону.
Без наклона лицо кэшируется целиком; с наклоном собирается из готовых слоёв (дёшево).
"""
import json
import os

import pygame

from ui import theme as T

from . import gfx as G
from . import model as M

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "assets", "cards")
FW, FH = 512, 768
PAD = 22                      # запас картинки за краем окна (для сдвига)
DEPTH_ART = (-16, -12)        # сдвиг картинки при наклоне 1.0 (x, y)
DEPTH_NEAR = (8, 6)           # сдвиг накладок
INK = (52, 32, 16)            # чернила на пергаменте ленты
TAG_TEXT = (214, 230, 255)
ALT_TEXT = (226, 246, 222)
_img = {}
_layers = {}
_faces = {}
_meta = None


def available():
    return os.path.exists(os.path.join(DIR, "frames.json")) and os.path.exists(os.path.join(DIR, "frame_attack.png"))


def meta():
    global _meta
    if _meta is None:
        with open(os.path.join(DIR, "frames.json"), encoding="utf-8") as f:
            _meta = json.load(f)["frames"]
    return _meta


def img(*path):
    key = path
    if key not in _img:
        p = os.path.join(DIR, *path)
        try:
            _img[key] = pygame.image.load(p).convert_alpha() if pygame.display.get_surface() else pygame.image.load(p)
        except (pygame.error, FileNotFoundError):
            _img[key] = None
    return _img[key]


def icon(name, size):
    key = ("icon", name, size)
    if key not in _img:
        src = img("icons", f"{name}.png")
        if src is None:
            _img[key] = None
        else:
            w, h = src.get_size()
            k = size / max(w, h)
            _img[key] = pygame.transform.smoothscale(src, (max(1, round(w * k)), max(1, round(h * k))))
    return _img[key]


def kind(card):
    d = card.d
    if d.get("react"):
        return "reaction"
    return d["type"] if d["type"] in ("attack", "skill", "power") else "skill"


def back(hero):
    """Рубашка героя; у эльфа пока общая лесная (back_hunter)."""
    return img(f"back_{hero}.png") or img("back_hunter.png")


# ---------- слои по типу карты (кэш) ----------

def _fit(src, rect):
    return pygame.transform.smoothscale(src, (rect.w, rect.h))


def base_layer(t):
    """Плашки, тень окна, рамка."""
    key = ("base", t)
    if key in _layers:
        return _layers[key]
    m = meta()[t]
    s = pygame.Surface((FW, FH), pygame.SRCALPHA)
    text, alt, win = pygame.Rect(m["text"]), pygame.Rect(m["alt"]), pygame.Rect(m["window"])
    for name, r in (("text", text.inflate(14, 14)), ("alt", alt.inflate(12, 12))):
        p = img("ui", f"{name}.png")
        if p is not None:
            s.blit(_fit(p, r), r.topleft)
        else:
            pygame.draw.rect(s, (24, 22, 28), r)
    for k in range(18):                                   # тень окна — картинка «глубже» рамки
        a = int(150 * (1 - k / 18) ** 2)
        pygame.draw.rect(s, (0, 0, 0, a), win.inflate(-2 * k, -2 * k), 1)
    s.blit(img(f"frame_{t}.png"), (0, 0))
    _layers[key] = s
    return s


def near_layer(t):
    """Накладки: уголки, навершие, кольцо цены, планка — ближе к глазу."""
    key = ("near", t)
    if key in _layers:
        return _layers[key]
    m = meta()[t]
    s = pygame.Surface((FW, FH), pygame.SRCALPHA)
    corner = img("parts", f"{t}_corner.png")
    if corner is not None:
        cw, ch = corner.get_size()
        e = 4
        s.blit(pygame.transform.flip(corner, True, False), (FW - cw - e, e))
        s.blit(pygame.transform.flip(corner, False, True), (e, FH - ch - e))
        s.blit(pygame.transform.flip(corner, True, True), (FW - cw - e, FH - ch - e))
    crest = img("parts", f"{t}_crest.png")
    if crest is not None:
        s.blit(crest, (FW // 2 - crest.get_width() // 2, 2))
    bar = img("parts", f"{t}_bar.png")
    if bar is not None:
        s.blit(bar, (FW // 2 - bar.get_width() // 2, FH - bar.get_height() - 4))
    ring = img("parts", f"{t}_ring.png")
    cx, cy, r = m["socket"]
    if ring is not None:
        d = int(r * 2 + 22)
        s.blit(pygame.transform.smoothscale(ring, (d, d)), (cx - d // 2, cy - d // 2))
    _layers[key] = s
    return s


def glare():
    """Блик стекла: мягкая диагональная полоса (складывается со светом)."""
    key = ("glare",)
    if key not in _layers:
        s = pygame.Surface((FW * 2, FH), pygame.SRCALPHA)
        for x in range(FW * 2):
            d = abs(x - FW) / 140
            a = int(46 * max(0.0, 1 - d * d))
            if a:
                pygame.draw.line(s, (a, a, a), (x, 0), (x - FH * 0.35, FH))
        _layers[key] = s
    return _layers[key]


# ---------- карта ----------

def art_layer(card):
    m = meta()[kind(card)]
    win = pygame.Rect(m["window"])
    size = (win.w + 2 * PAD, win.h + 2 * PAD)
    from .cardface import illustration
    spec = card.d.get("ill")
    pic = illustration(spec, size) if spec else None
    if pic is None:
        pic = pygame.Surface(size)
        pic.fill((30, 26, 24))
    return pic


def _text_fit(s, size, width, height):
    """Кегль заголовка по ширине и высоте ленты."""
    from .cardface import title_font

    while size > 14:
        font = title_font(size)
        if font.size(s)[0] <= width and font.render(s, True, INK).get_bounding_rect().height <= height:
            break
        size -= 1
    return size


def _fits(rich, measure, txt, rect, size, sc):
    """Высота текста (логическая) — в том кегле, каким он будет написан (на холсте лица — ×sc): переносы
    совпадают с настоящими, текст не вылезает за плашку."""
    if sc == 1.0:
        return rich(measure, txt, rect, size, (0, 0, 0))
    return rich(measure, txt, pygame.Rect(0, 0, round(rect.w * sc), round(rect.h * sc)),
                max(6, round(size * sc)), (0, 0, 0)) / sc


_clip_cache = {}


def text_clipped(card, main_ok=True, alt_ok=True, hot=False, heat=None, lit=()):
    """Не обрежется ли основной текст карты на лице даже минимальным кеглем."""
    if not available() or card.levels:
        return False
    from .cardface import title_style

    lit = frozenset(lit or ())
    key = (title_style(), card.cid, id(card.d), tuple(card.picks), card.uses, card.ready, card.insight_misses,
           main_ok, alt_ok, card.lvl, card.spirit_rank, lit,
           card.divine["id"] if card.divine else None, repr(card.alt_up), card.preview_key())
    if key in _clip_cache:
        return _clip_cache[key]
    from . import model as M
    from .cardface import _MEASURE, rich
    d = card.d
    inner = pygame.Rect(meta()[kind(card)]["text"]).inflate(-44, -14)
    extra = M.card_extras(d, lit)
    preview = card.preview or {}
    txt = (M.phrase(d["main"], d.get("exhaust"), lit, preview=preview.get("main")) +
           (" " + extra if extra else "")).strip()
    size = 38
    while size > 18 and _fits(rich, _MEASURE, txt, inner, size, 1.0) > inner.h:
        size -= 1
    result = _fits(rich, _MEASURE, txt, inner, size, 1.0) > inner.h
    if not result and d["alt"].get("target") != "none":
        alt = pygame.Rect(meta()[kind(card)]["alt"])
        ar = pygame.Rect(12, 18, alt.w - 24, alt.h - 20)
        atxt = M.phrase(d["alt"], preview=preview.get("alt"))
        asize = 28
        while asize > 16 and _fits(rich, _MEASURE, atxt, ar, asize, 1.0) > ar.h:
            asize -= 1
        result = _fits(rich, _MEASURE, atxt, ar, asize, 1.0) > ar.h
    if len(_clip_cache) > 200:
        _clip_cache.clear()
    _clip_cache[key] = result
    return result


def _lab(s, make, size, text, color, center=None, topleft=None, shadow=None, offs=((2, 2),)):
    """Надпись на лице: на холсте лица (gfx.FaceCanvas) — сразу кеглем ×S, чётко. Возвращает логический rect."""
    sc = s.S if G.is_canvas(s) else 1.0
    tgt = s.native if G.is_canvas(s) else s
    f = make(max(6, round(size * sc)))
    a = f.render(text, True, color)
    r = a.get_rect()
    if center is not None:
        r.center = (round(center[0] * sc), round(center[1] * sc))
    else:
        r.topleft = (round(topleft[0] * sc), round(topleft[1] * sc))
    if shadow is not None:
        sh = f.render(text, True, shadow)
        for dx, dy in offs:
            tgt.blit(sh, r.move(round(dx * sc), round(dy * sc)))
    tgt.blit(a, r)
    return pygame.Rect(round(r.x / sc), round(r.y / sc), round(r.w / sc), round(r.h / sc))


def _shadowed(surf, font, s, color, center, shadow=(0, 0, 0)):
    a = font.render(s, True, color)
    sh = font.render(s, True, shadow)
    r = a.get_rect(center=center)
    for dx, dy in ((2, 2), (-1, 1), (1, -1)):
        surf.blit(sh, r.move(dx, dy))
    surf.blit(a, r)
    return r


def content_layer(card, main_ok, alt_ok, hot, heat, lit, S=1.0):
    """Имя, теги, текст, простое, цена, дар, прозрение — на плоскости рамки. Возвращает (слой, места слов).
    S ≠ 1 — слой сразу в размере FW·S × FH·S, текст — кеглем ×S (карта в руке и в окне осмотра читается чётко,
    а не уменьшается из большого лица); места слов — только при S = 1."""
    if S != 1.0:
        layer = pygame.Surface((round(FW * S), round(FH * S)), pygame.SRCALPHA)
        fc = G.FaceCanvas(layer, FW, FH)
        with G.native(fc):
            _content_draw(fc, card, main_ok, alt_ok, hot, heat, lit)
        return layer, []
    s = pygame.Surface((FW, FH), pygame.SRCALPHA)
    return s, _content_draw(s, card, main_ok, alt_ok, hot, heat, lit)


def _content_draw(s, card, main_ok, alt_ok, hot, heat, lit):
    from .cardface import _levels, font, rich, title_font
    boxes = []
    t = kind(card)
    m = meta()[t]
    d = card.d
    canvas = G.is_canvas(s)
    sc = s.S if canvas else 1.0
    text, alt = pygame.Rect(m["text"]), pygame.Rect(m["alt"])
    # имя — на ленте
    ban = pygame.Rect(m["banner"]) if m.get("banner") else pygame.Rect(40, m["window"][1] + m["window"][3], 432, 40)
    size = _text_fit(card.name, 40, int(ban.w * 0.7), max(12, ban.h - 8))
    _lab(s, title_font, size, card.name, (240, 222, 180), center=(ban.centerx, ban.centery + 2))
    _lab(s, title_font, size, card.name, INK, center=ban.center)
    # теги — значки и слова на гравированной планке
    tags = card.tags
    if tags:
        # 3–4 тега не должны вылезать за карту: сперва пробуем обычный размер, потом мельче.
        avail = FW - 80
        size = 21
        while True:
            icon_size = max(16, round(size * 1.43))
            gap = max(9, round(size * 1.05))
            f = font(size, True)
            parts = [(icon(tg, icon_size), tg.upper(), f.size(tg.upper())) for tg in tags]
            w = sum((p[0].get_width() + max(4, gap // 3) if p[0] else 0) + p[2][0] + gap
                    for p in parts) - gap
            if w <= avail or size <= 13:
                break
            size -= 1
        x = FW // 2 - w // 2
        y = m["tags_y"]
        for (ic, word, (tw, th)), tg in zip(parts, tags):
            if ic is not None:
                s.blit(ic, (x, y - ic.get_height() // 2))
                x += ic.get_width() + max(4, gap // 3)
            _lab(s, lambda z: font(z, True), size, word, TAG_TEXT, topleft=(x, y - th // 2), shadow=(0, 0, 0))
            boxes.append((pygame.Rect(x, y - th // 2, tw, th), tg, "g"))
            x += tw + gap
    # основной текст
    react = bool(d.get("react"))
    extra = M.card_extras(d, lit)
    inner = text.inflate(-44, -14)                               # с запасом от рамки плашки
    if card.levels:
        bottom = inner.bottom - (30 if extra else 0)
        _levels(s, card, pygame.Rect(inner.x, inner.y, inner.w, bottom - inner.y), heat, lit, k=1.85, boxes=boxes)
        if extra:
            rich(s, extra, pygame.Rect(inner.x, bottom, inner.w, 30), 21, (220, 210, 190), boxes=boxes)
    else:
        txt = (M.phrase(d["main"], d.get("exhaust"), lit, preview=(card.preview or {}).get("main")) +
               (" " + extra if extra else "")).strip()
        size = 38
        from .cardface import _MEASURE
        while size > 18 and _fits(rich, _MEASURE, txt, inner, size, sc) > inner.h:
            size -= 1
        rich(s, txt, inner, size, (236, 228, 212), dim=not main_ok and not react, boxes=boxes, clip=True)
    # простое — вверх ногами
    if canvas:
        strip_px = pygame.Surface((round(alt.w * sc), round(alt.h * sc)), pygame.SRCALPHA)
        strip = G.FaceCanvas(strip_px, alt.w, alt.h)
    else:
        strip = strip_px = pygame.Surface(alt.size, pygame.SRCALPHA)
    alt_boxes = []
    if d["alt"]["target"] == "none":
        _lab(strip, lambda z: font(z, True), 20, "БЕЗ ПРОСТОГО ПРИМЕНЕНИЯ", (150, 170, 150),
             center=(alt.w // 2, alt.h // 2))
    else:
        col = (190, 255, 190) if alt_ok else (150, 160, 150)
        _lab(strip, lambda z: font(z, True), 15, "ПРОСТО · 0 · МАСТЕР" if card.alt_up is not None else "ПРОСТО · 0", col, topleft=(14, 2), shadow=(0, 0, 0))
        txt = M.phrase(d["alt"], preview=(card.preview or {}).get("alt"))
        ar = pygame.Rect(12, 18, alt.w - 24, alt.h - 20)
        size = 28
        from .cardface import _MEASURE
        while size > 16 and _fits(rich, _MEASURE, txt, ar, size, sc) > ar.h:
            size -= 1
        rich(strip, txt, ar, size, ALT_TEXT, dim=not alt_ok, boxes=alt_boxes, clip=True)
    if canvas:
        s.native.blit(pygame.transform.rotate(strip_px, 180), (round(alt.x * sc), round(alt.y * sc)))
    else:
        s.blit(pygame.transform.rotate(strip, 180), alt.topleft)
    for r, w, st in alt_boxes:                                     # места слов — тоже перевёрнуты
        boxes.append((pygame.Rect(alt.x + alt.w - r.right, alt.y + alt.h - r.bottom, r.w, r.h), w, st))
    # цена — в гнезде
    cx, cy, rr = m["socket"]
    ic = icon("react" if react else "heat" if card.uses_heat else "energy", int(rr * 2.1))
    if ic is not None:
        if not main_ok and not react:
            ic = ic.copy()
            ic.fill((120, 120, 120, 255), special_flags=pygame.BLEND_RGBA_MULT)
        s.blit(ic, ic.get_rect(center=(cx, cy)))
    if not react:
        # Цена: белая цифра с толстым тёмным контуром — читается и на светлом, и на тёмном гнезде.
        _lab(s, lambda z: font(z, True), 50, str(card.cost_label), (255, 255, 255) if main_ok else (215, 205, 190),
             center=(cx, cy + 2), shadow=(8, 5, 3),
             offs=((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, -2), (-2, 2), (2, 2)))
    if d["main"].get("seal") and "seal" not in lit:                        # Печать: закрыта
        ch = icon("seal", 40)
        if ch is not None:
            s.blit(ch, (cx + rr - 14, cy + rr - 18))
    # прозрения и дар
    for k in range(card.tier):
        st = icon("insight", 34)
        if st is not None:
            s.blit(st, (m["window"][0] + m["window"][2] - 40 - k * 30, m["window"][1] + 8))
    if card.rarity:                                      # редкость: цветные точки на кромке рисунка
        col = M.CARD_RARITY_COLOR.get(card.rarity, (220, 220, 220))
        for k in range(card.rarity):
            pygame.draw.circle(s, (18, 12, 8), (m["window"][0] + 16 + k * 14,
                                                m["window"][1] + m["window"][3] - 12), 6)
            pygame.draw.circle(s, col, (m["window"][0] + 16 + k * 14,
                                        m["window"][1] + m["window"][3] - 12), 4)
    if card.divine:
        pen = icon(f"god_{card.divine['id']}", 64)
        if pen is not None:
            s.blit(pen, (cx - pen.get_width() // 2, cy + rr + 8))
    g = card.growth_next()
    if g:
        k = card.insight_progress()
        bar = pygame.Rect(text.x + 24, m["groove_y"] - 3, text.w - 48, 6)
        if k:
            fill = img("ui", "fill.png")
            w = max(6, int(bar.w * k))
            if fill is not None:
                s.blit(pygame.transform.smoothscale(fill, (w, bar.h + 2)), (bar.x, bar.y - 1))
            else:
                pygame.draw.rect(s, (240, 190, 70), (bar.x, bar.y, w, bar.h))
    # состояние: условие выполнено, выбор, недоступна
    body = pygame.Rect(0, 0, FW, FH).inflate(-6, -6)
    if hot:
        pygame.draw.rect(s, T.SELECT, body, 6, border_radius=34)
    return boxes


def _content(card, ck, main_ok, alt_ok, hot, heat, lit, S=1.0):
    got = _layers.get(("content", S) + ck)
    if got is None:
        got = content_layer(card, main_ok, alt_ok, hot, heat, lit, S)
        if len(_layers) > 300:
            for k_ in [k_ for k_ in _layers if k_[0] == "content"]:
                del _layers[k_]
        _layers[("content", S) + ck] = got
    return got


def level_pips(card):
    """Кружки уровней Пиромантки на лице карты (координаты лица FW×FH): [(уровень, центр, радиус)]."""
    lv = card.levels
    if not lv:
        return []
    m = meta()[kind(card)]
    inner = pygame.Rect(m["text"]).inflate(-44, -14)             # как в _content_draw → cardface._levels(k=1.85)
    k = 1.85
    gap = round(30 * k)
    n = len(lv)
    x0 = inner.centerx - (n - 1) * gap / 2
    cy = inner.y + round(2 * k)
    return [(i, (x0 + i * gap, cy), round(10 * k * 1.3)) for i in range(n)]


def word_boxes(card, main_ok=True, alt_ok=True, hot=False, heat=None, lit=()):
    """Где на лице 512×768 стоят выделенные слова: [(rect, слово, стиль)] — для наведения в режиме чтения."""
    from .cardface import title_style

    lit = frozenset(lit or ())
    ck = (title_style(), card.cid, tuple(card.picks), card.uses, card.ready, card.insight_misses, main_ok, alt_ok, hot, card.lvl,
          card.spirit_rank, heat, lit,
          card.divine["id"] if card.divine else None, repr(card.alt_up), card.preview_key())
    return _content(card, ck, main_ok, alt_ok, hot, heat, lit)[1]


def compose(card, main_ok=True, alt_ok=True, hot=False, heat=None, lit=(), tilt=None, width=None, _under=False):
    """Лицо 512×768 (или шириной width пикселей: рамки и рисунок уменьшаются, текст пишется сразу в этом
    размере — читается). tilt (x, y) в −1…1 — наклон: слои сдвигаются по глубине."""
    from .cardface import title_style

    lit = frozenset(lit or ())
    tx, ty = tilt or (0.0, 0.0)
    ox, oy = round(tx * 6) / 6, round(ty * 6) / 6                 # шаг наклона — для кэша
    S = round(width / FW, 3) if width and abs(width - FW) > 2 else 1.0
    # _under — отдельный слой: иначе готовое лицо с текстом может подменить «рамку без текста» и текст удвоится.
    key = (title_style(), card.cid, tuple(card.picks), card.uses, card.ready, card.insight_misses, main_ok, alt_ok, hot, card.lvl,
           card.spirit_rank, heat, lit,
           card.divine["id"] if card.divine else None, repr(card.alt_up), card.preview_key(), ox, oy, S, _under)
    if key in _faces:
        return _faces[key]
    t = kind(card)
    m = meta()[t]
    ck = key[:-4]
    if S != 1.0:                                                  # под размер на экране
        W, H = round(FW * S), round(FH * S)
        under = compose(card, main_ok, alt_ok, False, heat, lit, tilt, None, _under=True)
        s = pygame.transform.smoothscale(under, (W, H))
        s.blit(_content(card, ck, main_ok, alt_ok, hot, heat, lit, S)[0], (0, 0))
        nk = ("near_s", t, W)
        if nk not in _layers:
            _layers[nk] = pygame.transform.smoothscale(near_layer(t), (W, H))
        s.blit(_layers[nk], (round(ox * DEPTH_NEAR[0] * S), round(oy * DEPTH_NEAR[1] * S)))
        if not main_ok and not alt_ok and not card.d.get("react"):
            dim = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.rect(dim, (0, 0, 0, 80), dim.get_rect(), border_radius=round(36 * S))
            s.blit(dim, (0, 0))
        if len(_faces) > 160:
            _faces.clear()
            from . import gfx
            gfx._rot.clear()
        _faces[key] = s
        return s
    content = _content(card, ck, main_ok, alt_ok, hot, heat, lit)[0]
    s = pygame.Surface((FW, FH), pygame.SRCALPHA)
    win = pygame.Rect(m["window"])
    s.set_clip(win.inflate(8, 8))
    s.blit(art_layer(card), (win.x - PAD + round(ox * DEPTH_ART[0]), win.y - PAD + round(oy * DEPTH_ART[1])))
    if ox or oy:                                                  # блик стекла ходит по наклону
        s.blit(glare(), (round(-FW * 0.5 + ox * 220), 0), special_flags=pygame.BLEND_RGB_ADD)
    s.set_clip(None)
    s.blit(base_layer(t), (0, 0))
    if _under:                                                    # только рисунок и рамка — текст ляжет поверх
        return s
    s.blit(content, (0, 0))
    s.blit(near_layer(t), (round(ox * DEPTH_NEAR[0]), round(oy * DEPTH_NEAR[1])))
    if not main_ok and not alt_ok and not card.d.get("react"):
        dim = pygame.Surface((FW, FH), pygame.SRCALPHA)
        pygame.draw.rect(dim, (0, 0, 0, 80), dim.get_rect(), border_radius=36)
        s.blit(dim, (0, 0))
    if len(_faces) > 160:
        _faces.clear()
        from . import gfx
        gfx._rot.clear()
    _faces[key] = s
    return s
