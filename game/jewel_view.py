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
                    img = pygame.transform.scale(img, (w, h))
                elif w:
                    img = pygame.transform.scale(img, (w, max(1, round(img.get_height() * w / img.get_width()))))
            except pygame.error:
                img = None
        _SPR[key] = img
    return _SPR[key]


def stone(surf, faces, to_world, center, scale, color, t):
    if not GG.draw(surf, faces, to_world, center, scale, color, t):
        G3.render(surf, faces, to_world, center, scale, color, t)


def badge(surf, key, label, x, y):
    """Подсказка клавиши: плашка с клавишей и подпись. Возвращает правый край."""
    w = max(26, T.font(13, True).size(key)[0] + 12)
    r = pygame.Rect(x, y, w, 24)
    pygame.draw.rect(surf, (58, 46, 34), r, border_radius=5)
    pygame.draw.rect(surf, (150, 120, 80), r, 1, border_radius=5)
    pygame.draw.line(surf, (30, 22, 16), (r.x + 2, r.bottom - 1), (r.right - 2, r.bottom - 1), 2)
    T.text(surf, key, r.center, 13, (250, 235, 205), True, center=True)
    return T.text(surf, label, (r.right + 6, y + 4), 13, T.TEXT_DIM).right + 14


def dashed(surf, a, b, col, width=3, n=12):
    for j in range(0, n, 2):
        p0 = (a[0] + (b[0] - a[0]) * j / n, a[1] + (b[1] - a[1]) * j / n)
        p1 = (a[0] + (b[0] - a[0]) * (j + 1) / n, a[1] + (b[1] - a[1]) * (j + 1) / n)
        pygame.draw.line(surf, col, p0, p1, width)


# ---------- сцена огранки ----------

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
            pygame.draw.line(surf, T.mix((34, 26, 20), (18, 14, 11), k), (rect.x, rect.y + i), (rect.right, rect.y + i))
    draw_machine(g, surf, rect)
    draw_panel(g, surf, rect)
    if g.need_flip() or g.flip_a not in (0.0, math.pi):
        draw_flip_banner(g, surf, rect)


def draw_machine(g, surf, rect):
    S = 1.1
    sx = rect.x + 300
    lap_y = rect.bottom - 128
    mast_x = rect.x + 640
    # стойка и шлифовальный диск
    base = spr("facet_lap_base", 300)
    if base is not None:
        surf.blit(base, (sx - base.get_width() // 2, lap_y + 26))
    else:
        pygame.draw.polygon(surf, (40, 34, 30), [(sx - 190, lap_y + 22), (sx + 190, lap_y + 22), (sx + 70, lap_y + 80),
                                                 (sx - 70, lap_y + 80)])
        pygame.draw.rect(surf, (34, 28, 24), (sx - 160, lap_y + 80, 320, 46), border_radius=6)
    lap = spr("facet_lap", 560, 64)
    if lap is not None:
        surf.blit(lap, (sx - lap.get_width() // 2, lap_y - 12))
        for k in range(18):                        # бег диска — блики по насечке
            x = sx - 270 + ((k * 31 + g.spin * 70) % 540)
            pygame.draw.line(surf, (230, 230, 240), (x, lap_y - 2), (x + 6, lap_y - 2), 1)
    else:
        disk = pygame.Rect(sx - 280, lap_y - 8, 560, 26)
        pygame.draw.rect(surf, (74, 74, 84), disk, border_radius=6)
        for k in range(32):
            x = disk.x + ((k * 18 + g.spin * 60) % disk.w)
            pygame.draw.line(surf, (150, 150, 165), (x, disk.y + 5), (x, disk.bottom - 5), 2)
        pygame.draw.rect(surf, (200, 200, 214), (disk.x + 4, disk.y, disk.w - 8, 4), border_radius=2)
        pygame.draw.rect(surf, (28, 28, 32), disk, 2, border_radius=6)
    # мачта
    mast = spr("facet_mast", None, None)
    if mast is not None:                          # мачта в своих пропорциях, выше — продолжение трубы
        m = spr("facet_mast", 56)
        bottom = lap_y + 64
        top = bottom - m.get_height()
        surf.blit(m, (mast_x - m.get_width() // 2, top))
        row = m.subsurface((0, int(m.get_height() * 0.8), m.get_width(), 1))
        tube = pygame.transform.scale(row, (m.get_width(), max(1, top + 2 - rect.y)))
        surf.blit(tube, (mast_x - m.get_width() // 2, rect.y))
    else:
        pygame.draw.rect(surf, (90, 90, 100), (mast_x - 10, rect.y, 20, lap_y + 60 - rect.y))
        pygame.draw.rect(surf, (140, 140, 150), (mast_x - 10, rect.y, 4, lap_y + 60 - rect.y))
        for y in range(rect.y + 10, lap_y + 40, 18):
            pygame.draw.line(surf, (60, 60, 68), (mast_x - 10, y), (mast_x + 10, y), 1)
    # камень
    C = (sx, lap_y - 8 - g.h * S)
    th = math.radians(g.theta)
    d = (math.sin(th), -math.cos(th))
    rod = g.R * S * 0.9 + 120
    if C[1] + d[1] * rod < rect.y + 64:          # оправка почти вертикальна — головка не уходит за край
        rod = max(g.R * S * 0.7, (C[1] - rect.y - 64) / max(0.01, -d[1]))
    head = (C[0] + d[0] * rod, C[1] + d[1] * rod)
    # кронштейн: от головки к мачте, муфта на мачте
    pygame.draw.line(surf, (70, 70, 80), head, (mast_x, head[1]), 12)
    pygame.draw.line(surf, (130, 130, 140), (head[0], head[1] - 4), (mast_x, head[1] - 4), 2)
    pygame.draw.rect(surf, (100, 100, 112), (mast_x - 18, head[1] - 22, 36, 44), border_radius=5)
    pygame.draw.rect(surf, (40, 40, 46), (mast_x - 18, head[1] - 22, 36, 44), 2, border_radius=5)
    # оправка (латунный стержень с чашечкой)
    tip = (C[0] + d[0] * g.R * S * 0.55, C[1] + d[1] * g.R * S * 0.55)
    pygame.draw.line(surf, BRASS_D, tip, head, 9)
    pygame.draw.line(surf, BRASS, tip, head, 5)
    pygame.draw.line(surf, (250, 220, 150), tip, head, 1)
    stone(surf, g.stone, g.machine_world, C, S, g.color, g.t)
    # цель грани — пунктир: след плоскости цели (при верных угле и индексе — вдоль диска)
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
            dashed(surf, a, b, (255, 210, 90))
    # головка: квадрант с делениями (угол — на глаз) и делительное колесо
    quad = spr("facet_head", 120)
    if quad is not None:                          # ось квадранта (≈30% ширины, 62% высоты) — на конце оправки
        surf.blit(quad, (head[0] - quad.get_width() * 0.30, head[1] - quad.get_height() * 0.62))
    else:
        pygame.draw.circle(surf, (56, 50, 44), (int(head[0]), int(head[1])), 46)
        pygame.draw.circle(surf, BRASS_D, (int(head[0]), int(head[1])), 46, 3)
        for a_deg in range(0, 91, 5):
            a = math.radians(a_deg)
            r0 = 38 if a_deg % 15 else 32
            p_out = (head[0] - math.sin(a) * 44, head[1] + math.cos(a) * 44)
            p_in = (head[0] - math.sin(a) * r0, head[1] + math.cos(a) * r0)
            pygame.draw.line(surf, BRASS, p_in, p_out, 2 if a_deg % 15 == 0 else 1)
    if quad is None:
        pygame.draw.line(surf, (255, 90, 70), head, (head[0] - d[0] * 44, head[1] - d[1] * 44), 2)   # стрелка
    gear = spr("facet_gear", 64)
    ang = -360.0 * g.index / 96
    if gear is not None:
        gi = pygame.transform.rotate(gear, ang)
        surf.blit(gi, (head[0] + 30 - gi.get_width() // 2, head[1] - 52 - gi.get_height() // 2))
    else:
        c = (head[0] + 30, head[1] - 52)
        pygame.draw.circle(surf, BRASS, (int(c[0]), int(c[1])), 26)
        for k in range(24):
            a = math.radians(ang) + math.tau * k / 24
            pygame.draw.line(surf, BRASS_D, (c[0] + 22 * math.cos(a), c[1] + 22 * math.sin(a)),
                             (c[0] + 28 * math.cos(a), c[1] + 28 * math.sin(a)), 3)
        a = math.radians(ang)
        pygame.draw.line(surf, (60, 40, 20), c, (c[0] + 18 * math.cos(a), c[1] + 18 * math.sin(a)), 3)
        pygame.draw.circle(surf, (60, 40, 20), (int(c[0]), int(c[1])), 5)
    for s_ in g.sparks:                           # искры с диска
        pygame.draw.circle(surf, (255, 220, 130), (int(sx + s_[0]), int(lap_y - 8 + s_[1])), 2)


def draw_panel(g, surf, rect):
    px = rect.x + 720
    panel = pygame.Rect(px, rect.y + 8, rect.right - px - 8, rect.h - 16)
    T.frame(surf, panel, 230)
    # лупа: гранимая сторона крупно
    lc = (panel.x + 100, panel.y + 104)
    pygame.draw.circle(surf, (16, 14, 18), lc, 88)
    stone(surf, g.stone, g.loupe_world, lc, 0.7, g.color, g.t + 1.7)
    ring = spr("facet_loupe", 196)
    if ring is not None:
        surf.blit(ring, (lc[0] - ring.get_width() // 2, lc[1] - ring.get_height() // 2))
    else:
        pygame.draw.circle(surf, BRASS, lc, 88, 6)
        pygame.draw.circle(surf, BRASS_D, lc, 94, 2)
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
    T.text(surf, f"Масса камня {g.mass() * 100:.0f}%", (x, y + 98), 14, T.TEXT)
    bar = pygame.Rect(x + 150, y + 102, panel.right - x - 166, 10)
    pygame.draw.rect(surf, (40, 34, 30), bar, border_radius=4)
    pygame.draw.rect(surf, (240, 160, 80), (bar.x, bar.y, int(bar.w * g.contact), bar.h), border_radius=4)
    T.text(surf, "сопротивление", (bar.x, bar.y - 16), 11, T.TEXT_DIM)
    if g.time_left is not None:
        T.text(surf, f"Время: {g.time_left:.0f} с", (x, y + 124), 17,
               (240, 120, 100) if g.time_left < 20 else T.TEXT, True)
    if g.note:
        T.text(surf, g.note, (x + 150, y + 126), 13, (240, 140, 110), True)
    # клавиши
    by = panel.bottom - 66
    bx = badge(surf, "W/S", "угол", x, by)
    bx = badge(surf, "A/D", "индекс", bx, by)
    badge(surf, "Shift", "точнее", bx, by)
    bx = badge(surf, "Пробел", "к диску", x, by + 30)
    bx = badge(surf, "Enter", "готово", bx, by + 30)
    badge(surf, "F", "перевернуть", bx, by + 30)
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
        pygame.draw.circle(surf, (24, 22, 28), c, r)
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
            pygame.draw.polygon(surf, fill, pts)
        pygame.draw.polygon(surf, (255, 210, 90) if on else (110, 110, 130), pts, 3 if on else 1)
    pygame.draw.circle(surf, (210, 220, 240), c, r, 1)
    a = math.tau * g.index / 96 - math.pi / 2
    e = (c[0] + (r + 10) * math.cos(a), c[1] + (r + 10) * math.sin(a))
    pygame.draw.line(surf, (255, 255, 255), c, e, 2)
    pygame.draw.circle(surf, (255, 255, 255), (int(e[0]), int(e[1])), 5)


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
        g.choose(cut_i)
        _IDEAL[key] = G3.polished(g.ideal)
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
    from game import workshop_games as WG
    T.text(surf, "Выберите огранку — чем больше граней, тем сложнее и выше предел качества", (rect.centerx,
           rect.y + 22), 18, T.TEXT, True, center=True)
    g.choice_rects = []
    w = (rect.w - 40 - 4 * 12) // 5
    mouse = getattr(g, "mpos", (-1, -1))           # мышь — в координатах экрана сцены (не окна)
    for i, c in enumerate(WG.CUTS):
        r = pygame.Rect(rect.x + 20 + i * (w + 12), rect.y + 60, w, rect.h - 84)
        g.choice_rects.append(r)
        hot = r.collidepoint(mouse)
        pygame.draw.rect(surf, (52, 38, 26) if hot else (36, 27, 20), r, border_radius=10)
        pygame.draw.rect(surf, (255, 210, 90) if hot else T.AMBER_DIM, r, 2, border_radius=10)
        T.text(surf, str(i + 1), (r.x + 14, r.y + 10), 16, T.TEXT_DIM, True)
        T.text(surf, c["name"], (r.centerx, r.y + 38), 17, T.TEXT, True, center=True)
        stone(surf, ideal(i), turntable(g.t + i), (r.centerx, r.y + 160), 0.62, g.color, g.t + i)
        low, top = WG.cut_counts(c)
        T.text(surf, f"граней {low + top}: низ {low} · верх {top}", (r.centerx, r.y + 262), 14, T.TEXT, True,
               center=True)
        T.text(surf, f"предел качества {c['cap'] * 100:.0f}%", (r.centerx, r.y + 288), 15, (150, 230, 150), True,
               center=True)
        per = c["per"]
        T.text(surf, f"таймер {per * (low + top) * (1 - 0.08 * g.diff):.0f} с" if per else "без таймера",
               (r.centerx, r.y + 312), 14, (240, 160, 110) if per else T.TEXT_DIM, center=True)
        T.text(surf, "клик или клавиша " + str(i + 1), (r.centerx, r.bottom - 26), 12, T.TEXT_DIM, center=True)


# ---------- камни в инвентаре ----------

def gem_faces(gem):
    """Форма камня: сохранённая при огранке или идеальная бриллиантовая (камни без формы)."""
    if gem.get("shape"):
        key = ("shape", gem.get("uid"))
        if key not in _IDEAL:
            _IDEAL[key] = G3.from_planes(gem["shape"])
        return _IDEAL[key]
    return ideal(4, seed=sum(map(ord, str(gem.get("uid", "")))) % 97)


def draw_gem(surf, gem, color, center, size, t=0.0, tilt=0.55):
    """Камень в инвентаре: витрина с вращением, size — сторона квадрата."""
    faces = gem_faces(gem)
    scale = size / (2 * 100 * 1.08)
    stone(surf, faces, turntable(t, tilt), center, scale, color, t)


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
            pygame.draw.circle(g, (int(40 * v), int(30 * v), int(26 * v)), (w // 2, h // 2), max(1, r * k // n))
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
        self.zoom = max(0.5, min(2.2, self.zoom * (1.1 if dy > 0 else 1 / 1.1)))

    def update(self, dt):
        self.idle += dt
        if not self.drag and self.idle > 2.5:          # отпустили — сам медленно поворачивается
            self.m = _mm(_rot("y", dt * 0.4), self.m)

    def draw(self, surf, rect, faces, color, t):
        pygame.draw.rect(surf, (12, 10, 10), rect, border_radius=10)
        glow = _glow(rect.size)                          # тёмный бархат и мягкое пятно света под камнем
        surf.blit(glow, rect, special_flags=pygame.BLEND_RGB_ADD)
        pygame.draw.rect(surf, (90, 70, 46), rect, 2, border_radius=10)
        far = max((G3.dot(p, p) for f in faces for p in f["pts"]), default=1.0) ** 0.5
        scale = min(rect.w, rect.h) / (2 * far * 1.06) * self.zoom
        clip = surf.get_clip()
        surf.set_clip(rect)
        stone(surf, faces, self.to_world, rect.center, scale, color, t)
        surf.set_clip(clip)


def draw_inspect(g, surf, rect):
    """Осмотр снятого камня: крупно, вращение мышью, колесо — приближение; таймер идёт."""
    view = pygame.Rect(rect.x + 16, rect.y + 16, rect.w - 380, rect.h - 32)
    g.inspect.draw(surf, view, g.stone, g.color, g.t)
    panel = pygame.Rect(view.right + 16, rect.y + 16, rect.right - view.right - 32, rect.h - 32)
    T.frame(surf, panel, 230)
    x, y = panel.x + 16, panel.y + 16
    T.text(surf, "Осмотр камня", (x, y), 22, (255, 210, 120), True)
    low = sum(1 for i, f in enumerate(g.facets) if f["side"] > 0 and g.scores[i] is not None)
    top = sum(1 for i, f in enumerate(g.facets) if f["side"] < 0 and g.scores[i] is not None)
    lines = [(g.cut["name"], T.TEXT), (f"огранено: низ {low}, верх {top} из {g.n}", T.TEXT_DIM),
             (f"масса камня {g.mass() * 100:.0f}%", T.TEXT_DIM), (f"качество сейчас {g.quality * 100:.0f}%", (150, 230, 150))]
    if g.time_left is not None:
        lines.append((f"время идёт: {g.time_left:.0f} с", (240, 160, 110)))
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


def rough_faces(rough):
    """Необработанный камень — природный кристалл из своего seed: шестигранная призма с вершинами и сколами
    (у ювелира из него вытачивают заготовку). Размер — карат."""
    import random
    key = ("rough", rough["uid"])
    if key not in _IDEAL:
        rng = random.Random(rough["seed"])
        R = 62.0 * rough.get("size", 1.0) ** (1 / 3)
        L = R * rng.uniform(1.3, 1.9)
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
        _IDEAL[key] = faces
    return _IDEAL[key]


def stone_faces(item):
    return rough_faces(item) if "seed" in item and "q" not in item else gem_faces(item)


def draw_rough(surf, rough, color, center, size, t=0.0, tilt=1.25):
    faces = rough_faces(rough)
    far = max(G3.dot(p, p) for f in faces for p in f["pts"]) ** 0.5
    stone(surf, faces, turntable(t, tilt), center, size / (2 * far), color, t)
