"""Оформление огранки: гранильный станок (диск, мачта с квадрантом, оправка, делительное колесо), лупа, схема огранки,
панель и подсказки клавиш; экран выбора огранки с живым превью камня; камни для инвентаря (сундук, вставка, витрина).

Камень рисуется трассировкой лучей (game/gem_gl.py), без видеокарты — полигонами (game/gem3d.py). Детали станка —
спрайты assets/sprites/facet_*.png (лист J промптов), фон — иллюстрация ws_bench_jewel (лист 36); пока их нет —
рисуются простые формы."""
import math
import os

import pygame

from game import gem3d as G3
from game import gem_gl as GG
from sim import gems as GM
from ui import aa as AA
from ui import theme as T

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRASS, BRASS_D, STEEL = (200, 160, 90), (120, 90, 50), (150, 150, 162)
_SPR = {}


def spr(name, w=None, h=None):
    """Спрайт станка (лист J) по размеру или None."""
    key = (name, w, h)
    if key not in _SPR:
        path = os.path.join(ROOT, "assets", "sprites", f"{name}.png")
        img = None
        if os.path.exists(path):
            try:
                img = pygame.image.load(path)
                r = img.get_bounding_rect()
                img = img.subsurface(r).copy() if r.w and r.h else img
                if w and h:
                    img = pygame.transform.smoothscale(img, (w, h))
                elif w:
                    img = pygame.transform.smoothscale(img, (w, max(1, round(img.get_height() * w / img.get_width()))))
                elif h:                                           # только высота — по высоте с пропорциями
                    img = pygame.transform.smoothscale(img, (max(1, round(img.get_width() * h / img.get_height())), h))
            except pygame.error:
                img = None
        _SPR[key] = img
    return _SPR[key]


def stone(surf, faces, to_world, center, scale, color, t, incl=None, star=0.0, axis=None, cfield=None):
    if not GG.draw(surf, faces, to_world, center, scale, color, t, incl=incl, star=star, axis=axis, cfield=cfield):
        G3.render(surf, faces, to_world, center, scale, color, t)
        for i in incl or []:                          # без видеокарты — примеси точками
            if i["k"] == "silk":
                continue
            w = to_world(i["p"])
            AA.circle(surf, (40, 34, 30) if i["k"] == "crystal" else (230, 230, 240),
                               (int(center[0] + w[0] * scale), int(center[1] + w[1] * scale)),
                               max(1, int(i["r"] * scale)), 0 if i["k"] == "crystal" else 1)


def stone_alpha(surf, faces, to_world, center, scale, color, t, alpha, cfield=None):
    """Камень полупрозрачно (разметка: сквозь кристалл видны контур, примеси и цветовые зоны)."""
    far = max(math.sqrt(G3.dot(p_, p_)) for f in faces for p_ in f["pts"])
    size = int(2 * far * scale + 8)
    img = GG.render(faces, to_world, size, scale, color, t, cfield=cfield)
    if img is not None:
        k = int(255 * alpha)
        img.fill((k, k, k, k), special_flags=pygame.BLEND_RGBA_MULT)
        GG.blit(surf, img, center)
        return
    tmp = pygame.Surface((size, size), pygame.SRCALPHA)
    G3.render(tmp, faces, to_world, (size // 2, size // 2), scale, color, t)
    tmp.set_alpha(int(255 * alpha))
    surf.blit(tmp, (center[0] - size // 2, center[1] - size // 2))


def badge(surf, key, label, x, y):
    """Подсказка клавиши: плашка с клавишей и подпись. Возвращает правый край."""
    w = max(26, T.font(13, True).size(key)[0] + 12)
    r = pygame.Rect(x, y, w, 24)
    pygame.draw.rect(surf, (58, 46, 34), r, border_radius=5)
    pygame.draw.rect(surf, (150, 120, 80), r, 1, border_radius=5)
    AA.line(surf, (30, 22, 16), (r.x + 2, r.bottom - 1), (r.right - 2, r.bottom - 1), 2)
    T.text(surf, key, r.center, 13, (250, 235, 205), True, center=True)
    return T.text(surf, label, (r.right + 6, y + 4), 13, T.TEXT_DIM).right + 14


def dashed(surf, a, b, col, width=3, n=12):
    for j in range(0, n, 2):
        p0 = (a[0] + (b[0] - a[0]) * j / n, a[1] + (b[1] - a[1]) * j / n)
        p1 = (a[0] + (b[0] - a[0]) * (j + 1) / n, a[1] + (b[1] - a[1]) * (j + 1) / n)
        AA.line(surf, col, p0, p1, width)


# ---------- сцена огранки ----------

PANEL_W = 400                                    # панель справа (лупа-превью, схема, состояние, клавиши)
STONE_K = 1.3                                    # камень крупнее относительно станка


def layout(rect):
    """Поле станка и масштаб: станок задуман в 720×520 и растягивается на всё поле; если места больше (широкий
    экран), станок и панель стоят рядом по центру."""
    mw = rect.w - PANEL_W - 8
    k = max(0.8, min(mw / 720, rect.h / 520))
    used = int(720 * k) + 40
    if used < mw:
        x0 = rect.x + (rect.w - used - 8 - PANEL_W) // 2
        return pygame.Rect(x0, rect.y, used, rect.h), k, x0 + 20
    return pygame.Rect(rect.x, rect.y, mw, rect.h), k, rect.x + max(0, int((mw - 720 * k) / 2))


def draw_scene(g, surf, rect):
    from ui import illustrations as IL
    if os.path.exists(os.path.join(IL.DIR, "hd", "ws_bench_jewel.png")):
        img = IL.get("ws_bench_jewel", "tavern", (rect.w, rect.w * 2 // 3), hd=True)
        surf.blit(img, (rect.x, rect.bottom - img.get_height()))
        sh = pygame.Surface(rect.size, pygame.SRCALPHA)
        sh.fill((8, 6, 4, 120))
        surf.blit(sh, rect)
    else:
        for i in range(rect.h):
            k = i / rect.h
            AA.line(surf, T.mix((34, 26, 20), (18, 14, 11), k), (rect.x, rect.y + i), (rect.right, rect.y + i))
    mrect, k, ox = layout(rect)
    draw_machine(g, surf, mrect, k, ox, area=rect)
    draw_panel(g, surf, pygame.Rect(mrect.right + 8, rect.y + 8, min(PANEL_W, rect.right - mrect.right - 16),
                                    rect.h - 16))
    if g.need_flip() or g.flip_a not in (0.0, math.pi):
        draw_flip_banner(g, surf, mrect)


def draw_machine(g, surf, rect, k=1.0, ox=None, area=None):
    ox = rect.x if ox is None else ox
    area = area or rect               # лупа — в координатах всего поля игры (как мышь в JewelCut.loupe_pointer)
    sx = ox + 300 * k
    lap_y = rect.bottom - 128 * k
    mast_x = ox + 640 * k
    S = getattr(g, "S", 1.1) * k * STONE_K          # крупный камень на оправке — крупнее
    S = min(S, (lap_y - 8 - rect.y - 10) / (g.h_max + g.R * 1.15))
    K = lambda v: max(1, int(round(v * k)))          # noqa: E731 — размеры станка в масштабе
    # стойка и шлифовальный диск
    base = spr("facet_lap_base", K(300))
    if base is not None:
        surf.blit(base, (sx - base.get_width() // 2, lap_y + 26 * k))
    else:
        AA.polygon(surf, (40, 34, 30), [(sx - 190 * k, lap_y + 22 * k), (sx + 190 * k, lap_y + 22 * k),
                                                 (sx + 70 * k, lap_y + 80 * k), (sx - 70 * k, lap_y + 80 * k)])
        pygame.draw.rect(surf, (34, 28, 24), (sx - 160 * k, lap_y + 80 * k, 320 * k, 46 * k), border_radius=6)
    lap = lap_sprite(getattr(g, "disk", None), K(560), K(64))
    if lap is not None:
        surf.blit(lap, (sx - lap.get_width() // 2, lap_y - 12 * k))
        for j in range(18):                        # бег диска — блики по насечке
            x = sx - 270 * k + ((j * 31 + g.spin * 70) * k % (540 * k))
            AA.line(surf, (230, 230, 240), (x, lap_y - 2 * k), (x + 6 * k, lap_y - 2 * k), K(1))
    else:
        disk = pygame.Rect(sx - 280 * k, lap_y - 8 * k, 560 * k, 26 * k)
        pygame.draw.rect(surf, (74, 74, 84), disk, border_radius=6)
        for j in range(32):
            x = disk.x + ((j * 18 + g.spin * 60) * k % disk.w)
            AA.line(surf, (150, 150, 165), (x, disk.y + 5 * k), (x, disk.bottom - 5 * k), K(2))
        pygame.draw.rect(surf, (200, 200, 214), (disk.x + 4, disk.y, disk.w - 8, K(4)), border_radius=2)
        pygame.draw.rect(surf, (28, 28, 32), disk, 2, border_radius=6)
    # мачта
    mast = spr("facet_mast", None, None)
    if mast is not None:                          # мачта в своих пропорциях, выше — продолжение трубы
        m = spr("facet_mast", K(56))
        bottom = lap_y + 64 * k
        top = bottom - m.get_height()
        surf.blit(m, (mast_x - m.get_width() // 2, top))
        row = m.subsurface((0, int(m.get_height() * 0.8), m.get_width(), 1))
        tube = pygame.transform.scale(row, (m.get_width(), max(1, int(top + 2 - rect.y))))
        surf.blit(tube, (mast_x - m.get_width() // 2, rect.y))
    else:
        pygame.draw.rect(surf, (90, 90, 100), (mast_x - 10 * k, rect.y, 20 * k, lap_y + 60 * k - rect.y))
        pygame.draw.rect(surf, (140, 140, 150), (mast_x - 10 * k, rect.y, 4 * k, lap_y + 60 * k - rect.y))
    # камень
    C = (sx, lap_y - 8 * k - g.h * S)
    th = math.radians(g.theta)
    d = (math.sin(th), -math.cos(th))
    rod = g.R * S * 0.9 + 120 * k
    if C[1] + d[1] * rod < rect.y + 64 * k:      # оправка почти вертикальна — головка не уходит за край
        rod = max(g.R * S * 0.7, (C[1] - rect.y - 64 * k) / max(0.01, -d[1]))
    head = (C[0] + d[0] * rod, C[1] + d[1] * rod)
    # кронштейн: от головки к мачте, муфта на мачте
    AA.line(surf, (70, 70, 80), head, (mast_x, head[1]), K(12))
    AA.line(surf, (130, 130, 140), (head[0], head[1] - 4 * k), (mast_x, head[1] - 4 * k), K(2))
    mr = pygame.Rect(mast_x - 18 * k, head[1] - 22 * k, 36 * k, 44 * k)
    pygame.draw.rect(surf, (100, 100, 112), mr, border_radius=5)
    pygame.draw.rect(surf, (40, 40, 46), mr, 2, border_radius=5)
    # оправка (латунный стержень с чашечкой)
    tip = (C[0] + d[0] * g.R * S * 0.55, C[1] + d[1] * g.R * S * 0.55)
    AA.line(surf, BRASS_D, tip, head, K(9))
    AA.line(surf, BRASS, tip, head, K(5))
    AA.line(surf, (250, 220, 150), tip, head, K(1))
    stone(surf, g.stone, g.machine_world, C, S, g.color, g.t, incl=g.incl, axis=g.caxis, cfield=g.cfield())
    # цель грани — пунктир: след плоскости цели (при верных угле и индексе — вдоль диска)
    tgt = None
    if not g.need_flip() and g.flip_a in (0.0, math.pi):
        f = g.facets[g.active]
        n, off = g.target(f)
        o = g.machine_world((0.0, 0.0, 0.0))
        N = G3.sub(g.machine_world(n), o)
        k2 = N[0] * N[0] + N[1] * N[1]
        if k2 > 0.05:
            p0 = (N[0] * off / k2, N[1] * off / k2)
            dv = (-N[1] / math.sqrt(k2), N[0] / math.sqrt(k2))
            L = g.R * 0.95
            a = (C[0] + (p0[0] - dv[0] * L) * S, C[1] + (p0[1] - dv[1] * L) * S)
            b = (C[0] + (p0[0] + dv[0] * L) * S, C[1] + (p0[1] + dv[1] * L) * S)
            dashed(surf, a, b, (255, 210, 90), width=K(3))
            tgt = (a, b)
    # головка: квадрант с делениями (угол — на глаз) и делительное колесо
    quad = spr("facet_head", K(120))
    if quad is not None:                          # ось квадранта (≈30% ширины, 62% высоты) — на конце оправки
        surf.blit(quad, (head[0] - quad.get_width() * QUAD_PIVOT[0], head[1] - quad.get_height() * QUAD_PIVOT[1]))
    else:
        AA.circle(surf, (56, 50, 44), (int(head[0]), int(head[1])), K(46))
        AA.circle(surf, BRASS_D, (int(head[0]), int(head[1])), K(46), 3)
        for a_deg in range(0, 91, 5):
            a = math.radians(a_deg)
            r0 = (38 if a_deg % 15 else 32) * k
            p_out = (head[0] - math.sin(a) * 44 * k, head[1] + math.cos(a) * 44 * k)
            p_in = (head[0] - math.sin(a) * r0, head[1] + math.cos(a) * r0)
            AA.line(surf, BRASS, p_in, p_out, 2 if a_deg % 15 == 0 else 1)
        AA.line(surf, (255, 90, 70), head, (head[0] - d[0] * 44 * k, head[1] - d[1] * 44 * k), K(2))
    gear = spr("facet_gear", K(64))
    ang = -360.0 * g.index / 96
    gc = (head[0] + 30 * k, head[1] - 52 * k)
    if gear is not None:
        gi = pygame.transform.rotate(gear, ang)
        surf.blit(gi, (gc[0] - gi.get_width() // 2, gc[1] - gi.get_height() // 2))
    else:
        AA.circle(surf, BRASS, (int(gc[0]), int(gc[1])), K(26))
        for j in range(24):
            a = math.radians(ang) + math.tau * j / 24
            AA.line(surf, BRASS_D, (gc[0] + 22 * k * math.cos(a), gc[1] + 22 * k * math.sin(a)),
                             (gc[0] + 28 * k * math.cos(a), gc[1] + 28 * k * math.sin(a)), K(3))
        a = math.radians(ang)
        AA.line(surf, (60, 40, 20), gc, (gc[0] + 18 * k * math.cos(a), gc[1] + 18 * k * math.sin(a)), K(3))
    for s_ in g.sparks:                           # искры с диска
        AA.circle(surf, (255, 220, 130), (int(sx + s_[0] * k), int(lap_y - 8 * k + s_[1] * k)), K(2))
    if hasattr(g, "FEEDS"):
        draw_feed(g, surf, mast_x - 62 * k, lap_y - 120 * k, k)
    if getattr(g, "loupe_on", False):
        if g.loupe_xy is None:                     # лупа по умолчанию — левее камня, над диском
            r = 92 * 1.5 * k
            g.loupe_xy = (int(max(r + 24, ox - area.x + 110 * k)), int(max(r + 30, lap_y - area.y - 170 * k)))
        draw_loupe(g, surf, area, C, S, lap_y, sx, tgt, k * 1.5, m_k=k)


_MASKS = {}
_LAPS = {}
LAP_TINT = {"lap_coarse": ("mult", (170, 145, 120)), "lap_fine": ("add", (34, 34, 40)),
            "lap_diamond": ("mult", (175, 205, 255))}


def lap_sprite(disk, w, h):
    """Шлифовальный диск: грубый — темнее и рыжее, тонкий — светлее, алмазный — голубоватый."""
    base = spr("facet_lap", w, h)
    if base is None or disk not in LAP_TINT:
        return base
    key = (disk, w, h)
    if key not in _LAPS:
        img = base.copy()
        mode, col = LAP_TINT[disk]
        img.fill(col, special_flags=pygame.BLEND_RGB_MULT if mode == "mult" else pygame.BLEND_RGB_ADD)
        _LAPS[key] = img
    return _LAPS[key]


_TEX = {}


def lap_texture(disk, band_h):
    """Поверхность диска крупно (лист JD: бесшовная полоса высокого разрешения) под высоту полосы в лупе."""
    name = {"lap_coarse": "coarse", "lap_medium": "medium", "lap_fine": "fine", "lap_diamond": "diamond"}.get(disk)
    key = (name, int(band_h))
    if key not in _TEX:
        img = None
        path = os.path.join(ROOT, "assets", "sprites", f"lap_tex_{name}.png") if name else None
        if path and os.path.exists(path):
            try:
                src = _TEX.get((name, "src")) or pygame.image.load(path)
                _TEX[(name, "src")] = src
                h = max(4, int(band_h))
                img = pygame.transform.smoothscale(src, (max(4, src.get_width() * h // src.get_height()), h))
            except pygame.error:
                img = None
        _TEX[key] = img
    return _TEX[key]


def disc_icon(disk, size):
    """Значок диска (лист JT) или None."""
    name = {"lap_coarse": "disc_coarse", "lap_medium": "disc_medium", "lap_fine": "disc_fine",
            "lap_diamond": "disc_diamond"}.get(disk)
    return spr(name, size, size) if name else None


QUAD_PIVOT = (0.185, 0.65)          # ось квадранта на спрайте (лист J-HD): доли ширины и высоты
LEVER_NOTCH = (0.193, 0.793)        # первая и последняя зарубки на спрайте рычага (доля высоты)
GLASS = (0.646, 0.358, 0.525)        # стекло на спрайте лупы: центр (доли ширины/высоты), диаметр (доля ширины)


def draw_feed(g, surf, x, y, k):
    """Рычаг подачи у мачты: 5 положений (вверху — быстро); клик по положению или Z/X."""
    K = lambda v: max(1, int(round(v * k)))          # noqa: E731
    n = len(g.FEEDS)
    step = 24 * k
    plate = pygame.Rect(x - 24 * k, y - 26 * k, 48 * k, step * n + 34 * k)
    src = spr("facet_lever", None, None)                         # лист JT: пластина с прорезью и 5 зарубками
    if src is not None:                                          # зарубки спрайта: 19%…79% высоты — под шаг рычага
        hs = int(step * (n - 1) / (LEVER_NOTCH[1] - LEVER_NOTCH[0]))
        img = spr("facet_lever", max(4, hs * src.get_width() // src.get_height()), hs)
        plate = pygame.Rect(0, 0, img.get_width(), hs)
        plate.midtop = (int(x), int(y - LEVER_NOTCH[0] * hs))
        surf.blit(img, plate)
    else:
        pygame.draw.rect(surf, (52, 40, 30), plate, border_radius=K(8))
        pygame.draw.rect(surf, BRASS_D, plate, K(2), border_radius=K(8))
        AA.line(surf, (20, 16, 12), (x, y), (x, y + step * (n - 1)), K(5))
    T.text(surf, "подача", (x, plate.y - 4 * k), K(12), (230, 210, 170), True, center=True, shadow=True)
    g.feed_rects = []
    pivot = (x + 40 * k, y + step * (n - 1) + 14 * k)
    for i in range(n):
        cy = y + step * (n - 1 - i)
        if src is None:
            AA.line(surf, BRASS if i <= g.feed else (90, 70, 46), (x - 10 * k, cy), (x + 10 * k, cy), K(2))
        r = pygame.Rect(0, 0, K(56), K(22))
        r.center = (int(x), int(cy))
        g.feed_rects.append(r)
    cy = y + step * (n - 1 - g.feed)
    AA.line(surf, (120, 120, 132), pivot, (x, cy), K(4))
    AA.circle(surf, (190, 60, 40), (int(x), int(cy)), K(8))
    AA.circle(surf, (250, 160, 120), (int(x - 2 * k), int(cy - 2 * k)), K(3))


def draw_loupe(g, surf, rect, C, S, lap_y, sx, tgt, k=1.0, m_k=None):
    """Лупа между игроком и диском: под стеклом — то же место крупно (камень трассируется заново, без пикселей),
    не в фокусе — мутно. Ушки линз — вставить/вынуть, ручка — двигать. k — размер лупы, m_k — масштаб станка."""
    mk_ = k if m_k is None else m_k
    r = int(92 * k)
    K = lambda v: max(1, int(round(v * k)))          # noqa: E731
    P = (rect.x + g.loupe_xy[0], rect.y + g.loupe_xy[1])
    g.loupe_center = P                                       # где монокль нарисован (для проверок)
    m = g.mag()
    tmp = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
    tmp.fill((20, 18, 22, 255))

    def tr(X):
        return (r + (X[0] - P[0]) * m, r + (X[1] - P[1]) * m)
    ly = tr((0, lap_y - 8 * mk_))[1]                        # диск: край и насечка
    band = 26 * mk_ * m
    tex = lap_texture(getattr(g, "disk", None), band) if band < 4000 else None
    if tex is not None:                                     # настоящая поверхность диска — бежит по рычагу
        off = int(g.spin * 60 * mk_ * m) % tex.get_width()
        x = -off
        while x < 2 * r:
            tmp.blit(tex, (x, ly))
            x += tex.get_width()
    else:
        pygame.draw.rect(tmp, (74, 74, 84), (0, ly, 2 * r, band))
    for j in range(0 if tex is not None else 40):
        x = ((j * 23 + g.spin * 70 * m) * mk_ % (2 * r + 40)) - 20
        AA.line(tmp, (150, 150, 165), (x, ly + 4 * mk_), (x + 2 * m * mk_, ly + 4 * mk_),
                         max(1, int(m * mk_ // 2)))
    AA.line(tmp, (210, 210, 224), (0, ly), (2 * r, ly), max(1, int(m * mk_ // 3)))
    img = GG.render(g.stone, g.machine_world, 2 * r, S * m, g.color, g.t, incl=g.incl, axis=g.caxis,
                    offset=((C[0] - P[0]) * m, (C[1] - P[1]) * m), cfield=g.cfield())
    if img is not None:
        tmp.blit(img, (0, 0), special_flags=pygame.BLEND_PREMULTIPLIED)
    else:
        G3.render(tmp, g.stone, g.machine_world, tr(C), S * m, g.color, g.t)
    if tgt:
        dashed(tmp, tr(tgt[0]), tr(tgt[1]), (255, 210, 90), width=K(2), n=40)
    for s_ in g.sparks:
        p_ = tr((sx + s_[0] * mk_, lap_y - 8 * mk_ + s_[1] * mk_))
        AA.circle(tmp, (255, 220, 130), (int(p_[0]), int(p_[1])), max(2, int(m * mk_)))
    b = g.blur()
    if b > 0.04:                                             # не в фокусе — размыто
        kb = 1 + b * 12
        small = pygame.transform.smoothscale(tmp, (max(4, int(2 * r / kb)), max(4, int(2 * r / kb))))
        tmp = pygame.transform.smoothscale(small, (2 * r, 2 * r))
    if r not in _MASKS:
        mk = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
        AA.circle(mk, (255, 255, 255, 255), (r, r), r)
        _MASKS[r] = mk
    tmp.blit(_MASKS[r], (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(tmp, (P[0] - r, P[1] - r))
    glint = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)  # блик стекла
    pygame.draw.ellipse(glint, (255, 255, 255, 26), (r * 0.35, r * 0.2, r * 0.9, r * 0.45))
    surf.blit(glint, (P[0] - r, P[1] - r))
    # монокль: без ручки, тянут за оправу; ушки линз — на верхней дуге (у верхнего края — на нижней)
    low = P[1] - r - 60 * k < rect.y                        # у верхнего края: ушки вниз
    g.loupe_r = r
    g.loupe_handle = None
    frame = magnifier_frame()
    for i, ((t, mg), on) in enumerate(zip(g.lenses, g.lens_in)):        # кольца вставленных линз
        if on:
            AA.circle(surf, (170, 190, 210), P, r - K(4) - i * K(3), 1)
    if frame is not None:                         # оправа (лист JM): стекло измерено — по краю вида лупы
        name, (gx, gy, gd, go), (fw, fh) = frame
        wd = int(r * 1.94 / gd)
        hd = int(wd * fh / fw)
        surf.blit(magnifier_scaled(name, wd, hd, False, False), (P[0] - wd * gx, P[1] - hd * gy))
        g.loupe_rim = r * go / gd                 # внешний край оправы — за неё тянут
    else:
        AA.circle(surf, BRASS_D, P, r + K(10), K(14))
        AA.circle(surf, BRASS, P, r + K(6), K(5))
        g.loupe_rim = r + K(18)

    def ear_pos(i):
        an = -118 + i * 27
        an = -an if low else an
        an = math.radians(an)
        rr = max(r + 16 * k, g.loupe_rim + 6 * k)
        return (P[0] + math.cos(an) * rr, P[1] + math.sin(an) * rr)
    # ушки линз: клик или 1–4 — вставить/вынуть; последнее — автофокус (если куплен)
    g.loupe_ears = []
    for i, ((t, mg), on) in enumerate(zip(g.lenses, g.lens_in)):
        er = pygame.Rect(0, 0, K(40), K(24))
        er.center = tuple(int(v) for v in ear_pos(i))
        pygame.draw.rect(surf, (200, 160, 90) if on else (44, 34, 26), er, border_radius=7)
        pygame.draw.rect(surf, (250, 220, 150) if on else (120, 96, 60), er, 1, border_radius=7)
        T.text(surf, f"×{mg}", er.center, K(13), (40, 26, 14) if on else (150, 130, 100), True, center=True)
        g.loupe_ears.append(er)
    g.af_rect = None
    if getattr(g, "af", False):
        er = pygame.Rect(0, 0, K(44), K(24))
        er.center = tuple(int(v) for v in ear_pos(len(g.lenses)))
        on = g.af_on
        pygame.draw.rect(surf, (110, 190, 130) if on else (44, 34, 26), er, border_radius=7)
        pygame.draw.rect(surf, (200, 250, 200) if on else (120, 96, 60), er, 1, border_radius=7)
        T.text(surf, "АФ", er.center, K(13), (20, 40, 24) if on else (150, 130, 100), True, center=True)
        g.af_rect = er
    sharp = "резко" if b < 0.15 else "почти" if b < 0.5 else "мутно"
    label = f"×{m} · {g.loupe_d:.0f} мм · {sharp}" + (" · АФ" if getattr(g, "af_on", False) else "")
    col = (150, 230, 150) if b < 0.15 else (240, 190, 120)
    bottom = P[1] + g.loupe_rim + 18 * k > rect.bottom       # у диска внизу — подпись сбоку
    if bottom or low:                             # у диска или когда ушки снизу — подпись сбоку
        T.text(surf, label, (P[0] + g.loupe_rim + 14 * k, P[1] + r * 0.55), K(13), col, True, shadow=True)
    else:
        T.text(surf, label, (P[0], P[1] + g.loupe_rim + 8 * k), K(13), col, True, center=True, shadow=True)


_FRAMES = {}


def magnifier_frame():
    """Оправа лупы: HD-картинка (лист JM, монокль), иначе спрайт листа JT. → (имя, стекло (cx, cy, диаметр,
    внешний диаметр), размер)."""
    if "geom" not in _FRAMES:
        _FRAMES["geom"] = None
        for name in ("facet_magnifier_hd", "facet_magnifier"):
            img = spr(name, None, None)
            if img is not None:
                _FRAMES["geom"] = (name, glass_geom(img), img.get_size())
                break
    return _FRAMES["geom"]


def glass_geom(img):
    """Стекло на картинке оправы: прозрачная область, замкнутая рамкой → центр, диаметр стекла и внешний диаметр
    оправы (доли ширины)."""
    import numpy as np
    w, h = img.get_size()
    sc = min(1.0, 256 / max(w, h))
    small = pygame.transform.smoothscale(img, (max(2, int(w * sc)), max(2, int(h * sc))))
    a = pygame.surfarray.array_alpha(small).T < 60
    H, W = a.shape
    seen = np.zeros_like(a)
    stack = [(y, x) for x in range(W) for y in (0, H - 1) if a[y, x]] + \
            [(y, x) for y in range(H) for x in (0, W - 1) if a[y, x]]
    for y, x in stack:
        seen[y, x] = True
    while stack:
        y, x = stack.pop()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < H and 0 <= nx < W and a[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                stack.append((ny, nx))
    ys, xs = np.nonzero(a & ~seen)
    if len(xs) < 20:
        return GLASS + (GLASS[2] * 1.25,)
    solid = np.nonzero(~a)[1]
    outer = float(solid.max() - solid.min() + 1) / W
    return (float(xs.mean() + 0.5) / W, float(ys.mean() + 0.5) / H, float(xs.max() - xs.min() + 1) / W, outer)


def magnifier_scaled(name, w, h, hf, vf):
    key = (name, w, h, hf, vf)
    if key not in _FRAMES:
        src = spr(name, None, None)
        img = pygame.transform.smoothscale(src, (w, h))
        _FRAMES[key] = pygame.transform.flip(img, hf, vf)
        if len(_FRAMES) > 40:
            geom = _FRAMES["geom"]
            _FRAMES.clear()
            _FRAMES["geom"] = geom
            _FRAMES[key] = pygame.transform.flip(img, hf, vf)
    return _FRAMES[key]


def draw_panel(g, surf, panel):
    """Панель справа: лупа-превью гранимой стороны, схема огранки, состояние грани, клавиши."""
    T.frame(surf, panel, 230)
    # лупа: гранимая сторона крупно
    lc = (panel.x + 100, panel.y + 104)
    AA.circle(surf, (16, 14, 18), lc, 88)
    stone(surf, g.stone, g.loupe_world, lc, 0.7 * min(1.2, getattr(g, "S", 1.1) / 1.1), g.color, g.t + 1.7,
          incl=g.incl, axis=g.caxis, cfield=g.cfield())
    ring = spr("facet_loupe", 196)
    if ring is not None:
        surf.blit(ring, (lc[0] - ring.get_width() // 2, lc[1] - ring.get_height() // 2))
    else:
        AA.circle(surf, BRASS, lc, 88, 6)
        AA.circle(surf, BRASS_D, lc, 94, 2)
    T.text(surf, "лупа: " + ("низ" if g.side > 0 else "верх"), (lc[0], lc[1] + 98), 13, T.TEXT_DIM, center=True)
    # схема огранки: сторона, которая гранится
    dc = (panel.right - 100, panel.y + 104)
    plate = spr("facet_plate", 196)
    if plate is not None:
        surf.blit(plate, (dc[0] - plate.get_width() // 2, dc[1] - plate.get_height() // 2))
    draw_diagram(g, surf, dc, 84)
    T.text(surf, "схема: " + ("низ (павильон)" if g.side > 0 else "верх (корона)"), (dc[0], dc[1] + 98), 13,
           T.TEXT_DIM, center=True)
    x, y = panel.x + 16, panel.y + 222
    f = g.facets[g.active]
    low, top = sum(1 for q in g.facets if q["side"] > 0), sum(1 for q in g.facets if q["side"] < 0)
    done_low = sum(1 for i, q in enumerate(g.facets) if q["side"] > 0 and g.scores[i] is not None)
    done_top = sum(1 for i, q in enumerate(g.facets) if q["side"] < 0 and g.scores[i] is not None)
    T.text(surf, g.cut["name"], (x, y), 18, T.TEXT, True)
    T.text(surf, f"низ {done_low}/{low}  ·  верх {done_top}/{top}", (x, y + 26), 14, T.TEXT_DIM)
    if not g.need_flip():
        ok = g.index == f["dial"]
        what = "площадка" if f["ang"] == 0 else f"ярус {f['tier'] + 1}"
        T.text(surf, f"Грань: {what} · индекс {g.index} → {f['dial']}", (x, y + 50), 15,
               (150, 230, 150) if ok else (240, 190, 120), True)
        if g.diff == 0:
            err = g.theta - f["ang"]
            T.text(surf, "наклон: ровно" if abs(err) < 1 else f"наклон: {'круче' if err < 0 else 'положе'}",
                   (x, y + 72), 13, (200, 200, 210))
    else:
        T.text(surf, "Сторона готова — переверните камень", (x, y + 50), 15, (255, 220, 130), True)
    ct = g.ct_now() if hasattr(g, "ct_now") else None
    T.text(surf, f"Масса {g.mass() * 100:.0f}%" + (f" · {ct:.2f} кар." if ct else ""), (x, y + 98), 14, T.TEXT)
    if getattr(g, "mm", None):
        T.text(surf, f"Ø {2 * g.R * g.mm:.1f} мм", (panel.right - 16 - T.font(13).size(f"Ø {2 * g.R * g.mm:.1f} мм")[0],
                                                     y + 2), 13, T.TEXT_DIM)
    if getattr(g, "near_crack", False):
        T.text(surf, "Рядом трещина! Медленная подача (Z) или Shift", (x, y + 148), 14, (255, 120, 100), True)
    elif g.note:
        T.text(surf, g.note, (x, y + 148), 13, (240, 140, 110), True)
    bar = pygame.Rect(x + 150, y + 102, panel.right - x - 166, 10)
    pygame.draw.rect(surf, (40, 34, 30), bar, border_radius=4)
    pygame.draw.rect(surf, (240, 160, 80), (bar.x, bar.y, int(bar.w * g.contact), bar.h), border_radius=4)
    T.text(surf, "сопротивление", (bar.x, bar.y - 16), 11, T.TEXT_DIM)
    if hasattr(g, "FEEDS"):
        yy = y + 176
        T.text(surf, f"Подача: {g.FEED_NAMES[g.feed]}" + (" · Shift — медленно" if g._fine() else ""),
               (x, yy), 15, T.TEXT, True)
        fin = g.finish_of.get(g.active)
        T.text(surf, f"чистота грани: {fin * 100:.0f}%" if fin is not None else "грань ещё не тронута",
               (panel.right - 16 - T.font(13).size(f"чистота грани: {(fin or 0) * 100:.0f}%")[0], yy + 2), 13,
               (150, 230, 150) if fin and fin >= 0.97 else T.TEXT_DIM)
        yy += 26
        g.disk_rects = []
        for d in g.disks:
            info = GM.DISK_BY_ID[d]
            dr = pygame.Rect(x, yy, panel.right - x - 16, 28)
            on = d == g.disk
            pygame.draw.rect(surf, (74, 54, 32) if on else (34, 26, 20), dr, border_radius=6)
            pygame.draw.rect(surf, (230, 180, 100) if on else (90, 70, 46), dr, 1, border_radius=6)
            ic = disc_icon(d, 24)
            if ic is not None:
                surf.blit(ic, (dr.x + 4, dr.y + 2))
            T.text(surf, info[1], (dr.x + (32 if ic is not None else 10), dr.y + 6), 13, T.TEXT if on else T.TEXT_DIM, on)
            tail = f"×{info[2]:.2f} · {info[3] * 100:.0f}%"
            T.text(surf, tail, (dr.right - 10 - T.font(12).size(tail)[0], dr.y + 7), 12,
                   (250, 220, 150) if on else T.TEXT_DIM)
            g.disk_rects.append((d, dr))
            yy += 32
    # клавиши
    by = panel.bottom - 66
    bx = badge(surf, "W/S", "угол", x, by)
    bx = badge(surf, "A/D", "индекс", bx, by)
    badge(surf, "Shift", "точнее, бережно", bx, by)
    bx = badge(surf, "Пробел", "к диску", x, by + 30)
    bx = badge(surf, "Enter", "готово", bx, by + 30)
    badge(surf, "F", "перевернуть", bx, by + 30)
    if getattr(g, "lenses", None):
        bx = badge(surf, "Колесо", "фокус лупы", x, by - 30)
        bx = badge(surf, "1–4", "линзы", bx, by - 30)
        badge(surf, "L", "лупа", bx, by - 30)
    if hasattr(g, "FEEDS"):
        yb = by - (60 if getattr(g, "lenses", None) else 30)
        bx = badge(surf, "Z/X", "подача", x, yb)
        if len(g.disks) > 1:
            badge(surf, "C", "сменить диск", bx, yb)
    ib = pygame.Rect(panel.right - 150, panel.y + 334, 136, 34)        # снять камень и рассмотреть
    pygame.draw.rect(surf, (70, 52, 32), ib, border_radius=7)
    pygame.draw.rect(surf, (200, 160, 90), ib, 1, border_radius=7)
    T.text(surf, "Осмотреть (Tab)", ib.center, 14, (250, 235, 205), True, center=True)
    g.inspect_btn = ib


def draw_diagram(g, surf, c, r):
    """Схема огранки гранимой стороны: ярусы по кругу, активная — янтарём, индекс камня — стрелкой."""
    tiers = sorted({f["tier"] for f in g.facets if f["side"] == g.side})
    ring_w = r / (len(tiers) + 0.7)
    if spr("facet_plate", 196) is None:
        AA.circle(surf, (24, 22, 28), c, r)
    else:
        r = int(r * 0.86)
    for i, f in enumerate(g.facets):
        if f["side"] != g.side:
            continue
        lvl = tiers.index(f["tier"])
        sc = g.scores[i]
        on = i == g.active and not g.need_flip()
        fill = (90, 170, 100) if sc is not None and sc >= 0.6 else (190, 120, 70) if sc is not None else \
            (110, 90, 40) if on else None
        if f["ang"] == 0:                           # площадка — центр
            pts = [(c[0] + ring_w * 0.7 * math.cos(math.tau * k / 8), c[1] + ring_w * 0.7 * math.sin(math.tau * k / 8))
                   for k in range(8)]
        else:
            ro, ri = r - lvl * ring_w, r - (lvl + 1) * ring_w
            a_mid = math.tau * f["dial"] / 96 - math.pi / 2
            half = math.pi / f["n"] * 0.92
            pts = [(c[0] + ro * math.cos(a_mid - half + 2 * half * k / 4),
                    c[1] + ro * math.sin(a_mid - half + 2 * half * k / 4)) for k in range(5)]
            pts += [(c[0] + ri * math.cos(a_mid + half - 2 * half * k / 4),
                     c[1] + ri * math.sin(a_mid + half - 2 * half * k / 4)) for k in range(5)]
        if fill:
            AA.polygon(surf, fill, pts)
        AA.polygon(surf, (255, 210, 90) if on else (110, 110, 130), pts, 3 if on else 1)
    AA.circle(surf, (210, 220, 240), c, r, 1)
    a = math.tau * g.index / 96 - math.pi / 2
    e = (c[0] + (r + 10) * math.cos(a), c[1] + (r + 10) * math.sin(a))
    AA.line(surf, (255, 255, 255), c, e, 2)
    AA.circle(surf, (255, 255, 255), (int(e[0]), int(e[1])), 5)


def draw_flip_banner(g, surf, rect):
    r = pygame.Rect(rect.x + 90, rect.bottom - 64, 520, 46)
    T.frame(surf, r, 240, accent=(255, 210, 90), corner=(255, 210, 90))
    txt = "Камень переворачивается…" if g.flip_a not in (0.0, math.pi) else \
        "Низ огранён — переверните камень на оправке (F)" if g.side > 0 else \
        "Верх огранён — переверните камень (F)"
    T.text(surf, txt, r.center, 16, (255, 225, 150), True, center=True)


# ---------- выбор огранки ----------

_IDEAL = {}


def ideal(cut_i, seed=11):
    """Идеально огранённый камень этой огранки (превью и камни песочницы без своей формы)."""
    key = (cut_i, seed)
    if key not in _IDEAL:
        from game import workshop_games as WG
        g = WG.JewelCut(seed)
        g.choose(cut_i)                            # все огранки известны: индекс — в общем списке
        _IDEAL[key] = G3.polished(g.ideal)
    return _IDEAL[key]


def fit_text(text, size, w):
    if T.font(size, True).size(text)[0] <= w:
        return text
    while text and T.font(size, True).size(text + "…")[0] > w:
        text = text[:-1]
    return text + "…"


def preview(cut_i):
    """Превью огранки: идеальная форма (у кабошона — гладкий купол)."""
    from game import workshop_games as WG
    c = WG.CUTS[cut_i]
    if not c.get("dome"):
        return ideal(cut_i)
    key = ("dome", cut_i)
    if key not in _IDEAL:
        _IDEAL[key] = G3.dome(ideal(cut_i), 100.0, c.get("outline"))
    return _IDEAL[key]


def turntable(t, tilt=0.55):
    """Витрина: камень площадкой к зрителю с наклоном, медленно вращается."""
    def tw(p_):
        a = t * 0.5
        ca, sa = math.cos(a), math.sin(a)
        x, y, z = p_[0] * ca - p_[1] * sa, p_[0] * sa + p_[1] * ca, -p_[2]
        cb, sb = math.cos(tilt), math.sin(tilt)
        return (x, y * cb - z * sb, y * sb + z * cb)
    return tw


def draw_choose(g, surf, rect):
    """Известные огранки (ювелир научил «Столовой», остальные — книги бродячих ювелиров, авторские — свитки): живое
    превью, грани, предел качества. Много огранок — сетка прокручивается колесом (клавиши 1–9 — по видимым)."""
    from game import workshop_games as WG
    T.text(surf, "Выберите огранку — чем больше граней, тем сложнее и выше предел качества", (rect.centerx,
           rect.y + 22), 18, T.TEXT, True, center=True)
    cuts = g.cuts
    n = len(cuts)
    g.choice_rects = [pygame.Rect(0, 0, 0, 0) for _ in cuts]
    cols = min(n, 6) if n > 5 else n
    rows = (n + cols - 1) // cols
    gap = 12
    area = pygame.Rect(rect.x + 20, rect.y + 56, rect.w - 40, rect.h - 70)
    h = (area.h - (rows - 1) * gap) // rows
    vis = rows
    if h < 200:                                        # не влезают — карточки постоянной высоты и прокрутка
        h = 200
        vis = max(1, (area.h + gap) // (h + gap))
        area.w -= 14
    w = (area.w - (cols - 1) * gap) // cols
    g.choose_cols, g.choose_rows, g.choose_vis = cols, rows, vis
    g.choose_top = max(0, min(rows - vis, getattr(g, "choose_top", 0)))
    first = g.choose_top * cols
    mouse = getattr(g, "mpos", (-1, -1))           # мышь — в координатах экрана сцены (не окна)
    big = rows == 1
    for i, c in enumerate(cuts):
        row = i // cols - g.choose_top
        if not 0 <= row < vis:
            continue
        r = pygame.Rect(area.x + (i % cols) * (w + gap), area.y + row * (h + gap), w, h)
        g.choice_rects[i] = r
        hot = r.collidepoint(mouse)
        rare = c.get("rare")
        edge = (255, 210, 90) if hot else (230, 180, 70) if rare else T.AMBER_DIM
        pygame.draw.rect(surf, (52, 38, 26) if hot else (44, 32, 18) if rare else (36, 27, 20), r, border_radius=10)
        pygame.draw.rect(surf, edge, r, 3 if rare and not hot else 2, border_radius=10)
        if i - first < 9:
            T.text(surf, str(i - first + 1), (r.x + 10, r.y + 8), 14, T.TEXT_DIM, True)
        for k in range(4):                             # сложность — столбик точек слева (ярус книги)
            AA.circle(surf, (255, 200, 90) if k < c["tier"] else (80, 64, 46), (r.x + 14, r.y + 80 - k * 11), 4)
        T.text(surf, fit_text(c["name"], 17 if big else 14, w - 34), (r.centerx, r.y + (34 if big else 22)),
               17 if big else 14, (255, 215, 120) if rare else T.TEXT, True, center=True)
        low, top = WG.cut_counts(c)
        ci = WG.CUTS.index(c)
        if big:
            stone(surf, preview(ci), turntable(g.t + i), (r.centerx, r.y + 150), 0.58, g.color, g.t + i)
            T.text(surf, f"граней {low + top}: низ {low} · верх {top}", (r.centerx, r.y + 250), 14, T.TEXT, True,
                   center=True)
            T.text(surf, f"предел качества {c['cap'] * 100:.0f}%", (r.centerx, r.y + 276), 15, (150, 230, 150), True,
                   center=True)
            T.text(surf, c.get("desc", ""), (r.centerx, r.y + 304), 12, T.TEXT_DIM, center=True)
        else:
            sc = min(w - 30, h - 58 - (14 if rare else 0)) / 200
            stone(surf, preview(ci), turntable(g.t + i), (r.centerx, r.y + 34 + int(h - 58) // 2), sc, g.color,
                  g.t + i)
            if rare:
                T.text(surf, "авторская", (r.centerx, r.bottom - 36), 12, (255, 200, 90), True, center=True)
            T.text(surf, f"граней {low + top} · до {c['cap'] * 100:.0f}%",
                   (r.centerx, r.bottom - 20), 12, (150, 230, 150), center=True)
    if vis < rows:                                     # полоса прокрутки
        bar = pygame.Rect(area.right + 6, area.y, 8, area.h)
        pygame.draw.rect(surf, (40, 30, 22), bar, border_radius=4)
        th = max(30, bar.h * vis // rows)
        ty = bar.y + (bar.h - th) * g.choose_top // max(1, rows - vis)
        pygame.draw.rect(surf, (200, 160, 90), (bar.x, ty, bar.w, th), border_radius=4)
        lab = f"колесо — ещё огранки ({n})"
        T.text(surf, lab, (rect.right - 24 - T.font(13).size(lab)[0], rect.y + 14), 13, T.TEXT_DIM)


# ---------- камни в инвентаре ----------

def gem_faces(gem):
    """Форма камня: сохранённая при огранке или идеальная форма его огранки (камни с прилавка)."""
    if gem.get("shape"):
        key = ("shape", gem.get("uid"))
        if key not in _IDEAL:
            faces = G3.from_planes(gem["shape"])
            if GM.CUT_BY_ID.get(gem.get("cut"), {}).get("dome"):         # кабошон: кромки его граней скруглены
                faces = G3.smooth(faces)
            _IDEAL[key] = faces
        return _IDEAL[key]
    from game import workshop_games as WG
    ci = next((i for i, c in enumerate(WG.CUTS) if c["id"] == gem.get("cut")), WG.CUTS.index(GM.CUT_BY_ID["brilliant"]))
    if GM.CUT_BY_ID.get(gem.get("cut"), {}).get("dome"):
        return preview(ci)
    return ideal(ci, seed=sum(map(ord, str(gem.get("uid", "")))) % 97)


def gem_cfield(item, faces=None):
    """Оттенки камня для шейдера: огранённый — его окно (cf.A, cf.b); сырой — кристалл в мм."""
    if "cf" not in item:
        return None
    cf = item["cf"]
    if "A" in cf:
        return {"gid": item["id"], "col": item.get("col", 0.5), "A": cf["A"], "b": cf["b"]}
    faces = faces or rough_faces(item)
    from sim.expedition import load_expedition
    mmr = mm_per_unit(item, faces, _xd())
    return {"gid": item["id"], "col": item.get("col", 0.5), "A": [mmr, 0, 0, 0, mmr, 0, 0, 0, mmr], "b": cf["o"]}


_XD = {}


def _xd():
    if "xd" not in _XD:
        from sim.expedition import load_expedition
        _XD["xd"] = load_expedition()
    return _XD["xd"]


def gem_color(gem, color):
    """Цвет тела по насыщенности камня."""
    return GM.tint(color, gem.get("col", 0.5))


def mm_per_unit(item, faces, xd=None):
    """Миллиметров на единицу формы: масса (караты) и плотность вида (сапфир 4.0, изумруд 2.75…)."""
    sg = 3.5
    if xd:
        sg = GM.gem_def(xd, item["id"]).get("sg", 3.5)
    v = max(1e-6, G3.volume(faces))
    return (200.0 * item.get("size", 1.0) / sg / v) ** (1 / 3)


def phys_k(item, faces, xd, ref_mm):
    """Доля карточки по настоящему размеру камня: ref_mm — во всю карточку."""
    far = max(math.sqrt(G3.dot(p_, p_)) for f in faces for p_ in f["pts"])
    return max(0.35, min(1.0, 2 * far * mm_per_unit(item, faces, xd) / ref_mm))


def draw_gem(surf, gem, color, center, size, t=0.0, tilt=0.55, xd=None):
    """Камень в инвентаре: витрина с вращением, size — сторона квадрата (с xd — по настоящему размеру)."""
    faces = gem_faces(gem)
    far = max(math.sqrt(G3.dot(p_, p_)) for f in faces for p_ in f["pts"])
    scale = size / (2 * far * 1.04)
    if xd:
        scale *= phys_k(gem, faces, xd, 11.0)
    stone(surf, faces, turntable(t, tilt), center, scale, gem_color(gem, color), t, incl=gem.get("incl"),
          star=gem.get("star", 0.0), axis=gem.get("axis"), cfield=gem_cfield(gem))


# ---------- осмотр: свободное вращение ----------

def _rot(axis, a):
    c, s_ = math.cos(a), math.sin(a)
    if axis == "x":
        return ((1, 0, 0), (0, c, -s_), (0, s_, c))
    return ((c, 0, s_), (0, 1, 0), (-s_, 0, c))


def _mm(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


_GLOWS = {}


def _glow(size):
    if size not in _GLOWS:
        w, h = size
        g = pygame.Surface(size)
        g.fill((0, 0, 0))
        n = 18
        r = int(min(w, h) * 0.62)
        for k in range(n, 0, -1):
            v = (1 - (k - 1) / n) ** 2
            AA.circle(g, (int(40 * v), int(30 * v), int(26 * v)), (w // 2, h // 2), max(1, r * k // n))
        _GLOWS[size] = g
    return _GLOWS[size]


class Inspector:
    """Осмотр камня: зажать мышь и тянуть — вращение как угодно (трекбол), колесо — приближение;
    без касания камень медленно поворачивается сам."""

    def __init__(self, tilt=0.55):
        self.m = _mm(_rot("x", -tilt), ((1, 0, 0), (0, 1, 0), (0, 0, -1)))   # площадкой к зрителю, с наклоном
        self.zoom = 1.0
        self.drag = None
        self.idle = 0.0

    def to_world(self, p):
        m = self.m
        return (m[0][0] * p[0] + m[0][1] * p[1] + m[0][2] * p[2],
                m[1][0] * p[0] + m[1][1] * p[1] + m[1][2] * p[2],
                m[2][0] * p[0] + m[2][1] * p[1] + m[2][2] * p[2])

    def turn(self, dx, dy):
        self.m = _mm(_rot("y", dx * 0.012), _mm(_rot("x", -dy * 0.012), self.m))

    def pointer(self, ev, rect):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and rect.collidepoint(ev.pos):
            self.drag = ev.pos
            return True
        if ev.type == pygame.MOUSEMOTION and self.drag:
            self.turn(ev.pos[0] - self.drag[0], ev.pos[1] - self.drag[1])
            self.drag = ev.pos
            self.idle = 0.0
            return True
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.drag:
            self.drag = None
            return True
        if ev.type == pygame.MOUSEWHEEL:
            self.wheel(ev.y)
            return True
        return False

    def wheel(self, dy):
        self.zoom = max(0.5, min(6.0, self.zoom * (1.1 if dy > 0 else 1 / 1.1)))

    def update(self, dt):
        self.idle += dt
        if not self.drag and self.idle > 2.5:          # отпустили — сам медленно поворачивается
            self.m = _mm(_rot("y", dt * 0.4), self.m)

    def draw(self, surf, rect, faces, color, t, mm=None, incl=None, star=0.0, axis=None, cfield=None):
        """mm — миллиметров на единицу формы: камень в настоящем размере (поле зрения ≈ 24 мм) и линейка."""
        pygame.draw.rect(surf, (12, 10, 10), rect, border_radius=10)
        glow = _glow(rect.size)                          # тёмный бархат и мягкое пятно света под камнем
        surf.blit(glow, rect, special_flags=pygame.BLEND_RGB_ADD)
        pygame.draw.rect(surf, (90, 70, 46), rect, 2, border_radius=10)
        far = max((G3.dot(p, p) for f in faces for p in f["pts"]), default=1.0) ** 0.5
        if mm:                                           # поле зрения ≈ 12 мм (колесо — до 2 мм)
            px_mm = min(rect.w, rect.h) / 12.0 * self.zoom
            scale = px_mm * mm
        else:
            scale = min(rect.w, rect.h) / (2 * far * 1.06) * self.zoom
        clip = surf.get_clip()
        surf.set_clip(rect)
        stone(surf, faces, self.to_world, rect.center, scale, color, t, incl=incl, star=star, axis=axis,
              cfield=cfield)
        if mm:                                          # линейка: 5 мм
            L = int(5 * px_mm)
            x0, y0 = rect.x + 24, rect.bottom - 26
            AA.line(surf, (220, 200, 160), (x0, y0), (x0 + L, y0), 2)
            for k in range(6):
                xx = x0 + L * k // 5
                AA.line(surf, (220, 200, 160), (xx, y0 - (7 if k in (0, 5) else 4)), (xx, y0), 1)
            T.text(surf, f"5 мм · Ø {2 * far * mm:.1f} мм", (x0, y0 - 24), 13, (220, 200, 160))
        surf.set_clip(clip)


def draw_inspect(g, surf, rect):
    """Осмотр снятого камня: крупно, вращение мышью, колесо — приближение."""
    view = pygame.Rect(rect.x + 16, rect.y + 16, rect.w - 380, rect.h - 32)
    g.inspect.draw(surf, view, g.stone, g.color, g.t, mm=getattr(g, "mm", None), incl=g.incl, axis=g.caxis,
                   cfield=g.cfield())
    panel = pygame.Rect(view.right + 16, rect.y + 16, rect.right - view.right - 32, rect.h - 32)
    T.frame(surf, panel, 230)
    x, y = panel.x + 16, panel.y + 16
    T.text(surf, "Осмотр камня", (x, y), 22, (255, 210, 120), True)
    low = sum(1 for i, f in enumerate(g.facets) if f["side"] > 0 and g.scores[i] is not None)
    top = sum(1 for i, f in enumerate(g.facets) if f["side"] < 0 and g.scores[i] is not None)
    lines = [(g.cut["name"], T.TEXT), (f"огранено: низ {low}, верх {top} из {g.n}", T.TEXT_DIM),
             (f"масса камня {g.mass() * 100:.0f}%", T.TEXT_DIM), (f"качество сейчас {g.quality * 100:.0f}%", (150, 230, 150))]
    for i, (txt, col) in enumerate(lines):
        T.text(surf, txt, (x, y + 40 + i * 24), 15, col)
    tips = ("Зажмите мышь и тяните —", "вращайте камень как угодно.", "Колесо — приблизить.",
            "Матовые грани — сырые", "или ещё не отполированные.")
    for i, txt in enumerate(tips):
        T.text(surf, txt, (x, y + 190 + i * 20), 13, T.TEXT_DIM)
    ib = pygame.Rect(panel.x + 16, panel.bottom - 56, panel.w - 32, 40)
    pygame.draw.rect(surf, (70, 52, 32), ib, border_radius=7)
    pygame.draw.rect(surf, (200, 160, 90), ib, 1, border_radius=7)
    T.text(surf, "Вернуть на станок (Tab)", ib.center, 15, (250, 235, 205), True, center=True)
    g.inspect_btn = ib


def rough_geom(rough):
    """Необработанный камень — природный кристалл из своего seed: шестигранная призма с вершинами и сколами.
    Возвращает (грани, радиус призмы R, полудлина L); размер — по каратам."""
    import random
    key = ("rough", rough["uid"], rough["seed"], rough.get("size"))
    if key not in _IDEAL:
        rng = random.Random(rough["seed"])
        R = 62.0 * (rough.get("size", 1.0) / 2.2) ** (1 / 3)
        L = R * rng.uniform(1.0, 1.45)
        faces = G3.box(R * 3, -L * 2, L * 2)
        tw = rng.uniform(0, math.pi / 3)
        for k in range(6):                                 # грани призмы, слегка неровные
            a = tw + math.pi / 3 * k
            faces = G3.clip(faces, (math.cos(a), math.sin(a), 0.0), R * rng.uniform(0.85, 1.05), "rough")
        for side in (1, -1):                               # вершины кристалла
            tip = L * rng.uniform(0.8, 1.15)
            for k in range(6):
                a = tw + math.pi / 3 * k
                th = math.radians(rng.uniform(45, 62))
                n = (math.sin(th) * math.cos(a), math.sin(th) * math.sin(a), side * math.cos(th))
                faces = G3.clip(faces, n, G3.dot(n, (0.0, 0.0, side * tip)) * rng.uniform(0.9, 1.0), "rough")
        for _ in range(rng.randint(2, 5)):                 # сколы
            u = G3.norm((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
            faces = G3.clip(faces, u, G3.extent(faces, u) * rng.uniform(0.78, 0.92), "rough")
        _IDEAL[key] = (faces, R, L)
    return _IDEAL[key]


def rough_faces(rough):
    return rough_geom(rough)[0]


def rough_incl(rough):
    """Примеси кристалла в его осях (доли призмы → единицы); вне кристалла (ушли со сколом) — нет."""
    faces, R, L = rough_geom(rough)
    planes = [(f["n"], G3.dot(f["n"], f["pts"][0])) for f in faces if f["pts"]]
    out = []
    for k, i in enumerate(rough.get("incl", [])):
        p_ = (i["p"][0] * R, i["p"][1] * R, i["p"][2] * L)
        r = i["r"] * R
        if i["k"] != "silk" and not all(G3.dot(n, p_) <= off - r * 0.3 for n, off in planes):
            continue
        out.append(dict(i, p=p_, r=r, i=k))                 # i — номер примеси в камне (раскол убирает её)
    return out


def stone_faces(item):
    return rough_faces(item) if "seed" in item and "q" not in item else gem_faces(item)


def draw_rough(surf, rough, color, center, size, t=0.0, tilt=1.25, xd=None):
    """Сырой кристалл на карточке (с xd — по настоящему размеру: 16 мм — во всю карточку)."""
    faces = rough_faces(rough)
    far = max(G3.dot(p, p) for f in faces for p in f["pts"]) ** 0.5
    scale = size / (2 * far)
    if xd:
        scale *= phys_k(rough, faces, xd, 16.0)
    stone(surf, faces, turntable(t, tilt), center, scale, gem_color(rough, color), t, cfield=gem_cfield(rough, faces))


# ---------- разметка сырого камня ----------

def draw_plan(g, surf, rect):
    """Разметка: кристалл полупрозрачен, внутри — контур будущего камня (янтарный каркас), примеси — красные
    (останутся в камне) и серые (уйдут в отход). Справа — масса, чистота, цвет, примерная цена."""
    pl = g.plan
    xd = g.xd
    view = pygame.Rect(rect.x + 16, rect.y + 16, rect.w - 380, rect.h - 32)
    pygame.draw.rect(surf, (12, 10, 10), view, border_radius=10)
    surf.blit(_glow(view.size), view, special_flags=pygame.BLEND_RGB_ADD)
    pygame.draw.rect(surf, (90, 70, 46), view, 2, border_radius=10)
    far = max(math.sqrt(G3.dot(p_, p_)) for f in pl.faces for p_ in f["pts"])
    scale = min(view.w, view.h) / (2 * far * 1.08)
    c = view.center
    clip = surf.get_clip()
    surf.set_clip(view)
    m = pl.m
    to_view = lambda p_: (m[0][0] * p_[0] + m[0][1] * p_[1] + m[0][2] * p_[2],          # noqa: E731
                          m[1][0] * p_[0] + m[1][1] * p_[1] + m[1][2] * p_[2],
                          m[2][0] * p_[0] + m[2][1] * p_[1] + m[2][2] * p_[2])
    stone_alpha(surf, pl.faces, to_view, c, scale, g.color, g.t, 0.55,
                cfield={"gid": g.rough["id"], "col": g.rough.get("col", 0.5), **pl.cf_rough()})
    s_ = pl.s()
    # контур будущего камня: каркас граней (дальние — тусклее)
    for f in g.ideal:
        pts = f["pts"]
        if len(pts) < 2:
            continue
        nv = pl.q(f["n"])
        col = (255, 210, 90) if nv[2] < 0 else (130, 100, 50)
        scr = []
        for p_ in pts:
            v = pl.q(p_)
            scr.append((c[0] + (v[0] * s_ + pl.o[0]) * scale, c[1] + (v[1] * s_ + pl.o[1]) * scale))
        AA.lines(surf, col, True, scr, 2 if nv[2] < 0 else 1)
    # примеси
    for (si, inside), inc in zip(pl.stone_incl(s_), pl.incl):
        v = to_view(inc["p"])
        pos = (int(c[0] + v[0] * scale), int(c[1] + v[1] * scale))
        rr = max(2, int(inc["r"] * scale))
        if inc["k"] == "silk":
            ax = to_view((0.0, 0.0, 1.0))
            for k in range(3):                              # шёлк: иглы поперёк оси кристалла
                a = math.atan2(ax[1], ax[0]) + math.pi / 2 + (k - 1) * 0.5
                d = (math.cos(a) * rr * 0.5, math.sin(a) * rr * 0.5)
                AA.line(surf, (200, 200, 220), (c[0] - d[0], c[1] - d[1]), (c[0] + d[0], c[1] + d[1]), 1)
            continue
        col = (255, 90, 80) if inside else (120, 116, 120)
        if inc["k"] == "feather":
            n = to_view(inc["n"])
            t_ = (-n[1], n[0])
            ln = math.hypot(*t_) or 1.0
            a = (pos[0] - t_[0] / ln * rr, pos[1] - t_[1] / ln * rr)
            b = (pos[0] + t_[0] / ln * rr, pos[1] + t_[1] / ln * rr)
            AA.line(surf, col, a, b, 3)
        elif inc["k"] == "bubble":
            AA.circle(surf, col, pos, rr, 1)
        elif inc["k"] == "cloud":
            for k in range(5):
                AA.circle(surf, col, (pos[0] + int(rr * 0.6 * math.cos(k * 1.3)),
                                               pos[1] + int(rr * 0.6 * math.sin(k * 1.7))), max(1, rr // 3))
        else:
            AA.circle(surf, col, pos, rr)
    if g.cut.get("dome") and pl.silk() > 0:                 # ось кристалла: для звезды — вверх
        ax = to_view((0.0, 0.0, 1.0))
        e = (c[0] + ax[0] * far * scale * 0.9, c[1] + ax[1] * far * scale * 0.9)
        AA.line(surf, (200, 220, 255), c, e, 2)
        AA.circle(surf, (200, 220, 255), (int(e[0]), int(e[1])), 5)
    surf.set_clip(clip)
    # панель
    panel = pygame.Rect(view.right + 16, rect.y + 16, rect.right - view.right - 32, rect.h - 32)
    T.frame(surf, panel, 230)
    x, y = panel.x + 16, panel.y + 14
    T.text(surf, "Разметка камня", (x, y), 22, (255, 210, 120), True)
    T.text(surf, g.cut["name"], (x, y + 32), 15, T.TEXT)
    ct = pl.est_ct()
    cl = pl.est_clarity()
    inside = sum(1 for si, ok in pl.stone_incl(s_) if ok and si["k"] != "silk")
    total = sum(1 for i in pl.incl if i["k"] != "silk")
    lines = [(f"сырьё {g.rough['size']:.2f} кар. → камень ≈ {ct:.2f} кар.", T.TEXT),
             (f"выход {ct / max(0.01, g.rough['size']) * 100:.0f}% · размер {pl.frac * 100:.0f}%", T.TEXT_DIM)]
    if xd:
        lines += [(f"примеси: {inside} из {total} останутся", (255, 140, 120) if inside else (150, 230, 150)),
                  (f"чистота: {GM.grade(xd, cl).lower()}", T.TEXT),
                  (f"цвет: {GM.color_word(xd, g.rough.get('col', 0.5))}", T.TEXT)]
        star = pl.star()
        if g.cut.get("dome"):
            lines.append((f"звезда: {star * 100:.0f}%" if pl.silk() else "звезды не будет (нет шёлка)",
                          (200, 220, 255) if star > 0.3 else T.TEXT_DIM))
        cz = pl.est_colors()
        txt = GM.colors_text(g.rough["id"], cz)
        if txt:
            lines.append((fit_text(txt, 14, panel.w - 32), (220, 210, 250)))
        est = GM.estimate(xd, g.rough["id"], ct, g.rough.get("col", 0.5), cl, 1.0, g.cut["id"], star, cz)
        lines.append((f"цена при работе 100% ≈ {est}", (255, 210, 120)))
    for i, (txt, col) in enumerate(lines):
        T.text(surf, txt, (x, y + 62 + i * 22), 14, col)
    tips = ("мышь — крутить кристалл (и цветовые зоны)", "колесо — размер камня", "WASD — сдвиг · R — сброс",
            "красные примеси останутся,", "серые — уйдут в отход", "Backspace — другая огранка")
    for i, txt in enumerate(tips):
        T.text(surf, txt, (x, panel.bottom - 186 + i * 19), 12, T.TEXT_DIM)
    ib = pygame.Rect(panel.x + 16, panel.bottom - 56, panel.w - 32, 40)
    ok = s_ > 1e-6
    pygame.draw.rect(surf, (90, 66, 36) if ok else (50, 40, 32), ib, border_radius=7)
    pygame.draw.rect(surf, (230, 180, 100) if ok else (90, 80, 70), ib, 1, border_radius=7)
    T.text(surf, "На станок (Enter)" if ok else "Контур не помещается", ib.center, 15,
           (250, 235, 205) if ok else T.TEXT_DIM, True, center=True)
    g.plan_btn = ib
