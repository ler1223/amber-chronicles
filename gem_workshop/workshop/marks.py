"""Метки игрока на сырье, окошко и разбор (docs/design_reading_progress.md, §3).

Метка — прогноз игрока: «здесь перо», «здесь цветное пятно», «здесь чисто».
Игрок видит камень в проекции и не знает глубину, поэтому метка — это луч
взгляда сквозь камень (отрезок a→b в осях сырья). Сверка с правдой идёт по
расстоянию от включения до этого отрезка.

Окошко — маленькая полированная площадка, сошлифованная лицом к игроку.
Сквозь неё видно нутро без размытия корки; масса немного теряется.
"""
from __future__ import annotations

import math

from game import gem3d as G3
from game import jewel_view as JV
from sim import gems as GM

# (тип, подпись, короткая подпись на камне, цвет)
KINDS = (
    ("feather", "Перо", "П", (240, 120, 100)),
    ("fingerprint", "Отпечаток", "О", (235, 195, 120)),
    ("cloud", "Облако", "Об", (205, 205, 220)),
    ("silk", "Шёлк", "Ш", (175, 210, 255)),
    ("crystal", "Кристалл", "К", (150, 230, 150)),
    ("two_phase", "Полость", "Пз", (120, 205, 235)),
    ("color", "Цвет", "Ц", (210, 145, 250)),
    ("clean", "Чисто", "Ч", (175, 175, 155)),
)
KIND = {k: (label, short, col) for k, label, short, col in KINDS}

# Что считается «тем же самым» при сверке: спайность — тоже трещина, пузырь — полость.
CATEGORY = {"feather": "crack", "cleavage": "crack", "fingerprint": "print", "cloud": "cloud",
            "graining": "cloud", "milky": "cloud", "silk": "silk", "crystal": "crystal", "two_phase": "cavity",
            "bubble": "cavity", "cavity": "cavity"}

# Тип метки для настоящего включения (цвет на «ответе мастера»).
CATEGORY_KIND = {"feather": "feather", "cleavage": "feather", "fingerprint": "fingerprint", "cloud": "cloud",
                 "graining": "cloud", "milky": "cloud", "crystal": "crystal", "two_phase": "two_phase",
                 "bubble": "two_phase", "cavity": "two_phase", "silk": "silk"}

MAX_WINDOWS = 2
WINDOW_DEPTH = 0.035          # глубина окошка — доля радиуса кристалла


# ---------- геометрия ----------

def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b, k=1.0):
    return (a[0] + b[0] * k, a[1] + b[1] * k, a[2] + b[2] * k)


def mid(mark):
    a, b = mark["a"], mark["b"]
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)


def view_scale(rect, zoom, mm):
    """Пикселей на единицу камня — так же, как рисует Inspector.draw."""
    return min(rect.w, rect.h) / 12.0 * zoom * mm


def pick(insp, rect, faces, mm, pos):
    """Луч взгляда через точку экрана → отрезок внутри камня (оси камня) или None."""
    scale = view_scale(rect, insp.zoom, mm)
    if scale <= 0:
        return None
    wx = (pos[0] - rect.centerx) / scale
    wy = (pos[1] - rect.centery) / scale
    o = insp.to_stone((wx, wy, 0.0))
    d = insp.to_stone((0.0, 0.0, -1.0))
    t0, t1, fi = -1e9, 1e9, -1
    for i, f in enumerate(faces):
        if not f["pts"]:
            continue
        n = f["n"]
        dn = _dot(n, d)
        dist = _dot(n, f["pts"][0]) - _dot(n, o)
        if abs(dn) < 1e-9:
            if dist < 0:
                return None
            continue
        t = dist / dn
        if dn < 0:
            if t > t0:
                t0, fi = t, i
        else:
            t1 = min(t1, t)
    if fi < 0 or t0 >= t1:
        return None
    return {"a": _add(o, d, t0), "b": _add(o, d, t1), "d": d, "face": fi}


def project(insp, rect, mm, p):
    scale = view_scale(rect, insp.zoom, mm)
    w = insp.to_world(p)
    return (rect.centerx + w[0] * scale, rect.centery + w[1] * scale)


def ray_dist(mark, p):
    """Расстояние от точки до отрезка-луча метки."""
    a, b = mark["a"], mark["b"]
    ab = _sub(b, a)
    ln2 = _dot(ab, ab) or 1e-9
    t = max(0.0, min(1.0, _dot(_sub(p, a), ab) / ln2))
    q = _add(a, ab, t)
    v = _sub(p, q)
    return math.sqrt(_dot(v, v))


# ---------- метки ----------

def marks(stone):
    return stone.setdefault("marks", [])


def add_mark(stone, kind, ray):
    m = {"k": kind, "a": [round(v, 2) for v in ray["a"]], "b": [round(v, 2) for v in ray["b"]]}
    marks(stone).append(m)
    return m


def mark_at(insp, rect, mm, stone, pos, radius=13):
    """Метка под курсором (по экрану) или None."""
    best, bd = None, radius
    for m in stone.get("marks", []):
        sx, sy = project(insp, rect, mm, mid(m))
        d = math.hypot(sx - pos[0], sy - pos[1])
        if d <= bd:
            best, bd = m, d
    return best


def summary(stone):
    ms = stone.get("marks") or []
    if not ms:
        return "меток нет"
    count = {}
    for m in ms:
        count[m["k"]] = count.get(m["k"], 0) + 1
    parts = [f"{KIND[k][0].lower()}{' ×' + str(n) if n > 1 else ''}" for k, n in count.items() if k in KIND]
    return "метки: " + ", ".join(parts)


# ---------- окошко ----------

def window_count(stone):
    return len(stone.get("windows") or [])


def add_window(stone, ray):
    """Сошлифовать окошко в точке входа луча (лицом к зрителю). → доля потерянной массы или None."""
    if window_count(stone) >= MAX_WINDOWS:
        return None
    faces, R, _ = JV.rough_geom(stone)
    vol0 = G3.volume(faces)
    d = ray["d"]
    n = (-d[0], -d[1], -d[2])
    h = _dot(n, ray["a"]) - WINDOW_DEPTH * R
    stone.setdefault("size0", stone.get("size", 1.0))
    stone.setdefault("windows", []).append({"n": [round(v, 5) for v in n], "h": round(h / R, 5)})
    vol1 = G3.volume(JV.rough_geom(stone)[0])
    k = max(0.5, min(1.0, vol1 / max(1e-9, vol0)))
    stone["size"] = round(stone["size"] * k, 3)
    return 1.0 - k


# ---------- распил ----------

SAW_KERF = 0.012            # пропил — доля радиуса с каждой стороны
MIN_PIECE_CT = 0.1


def saw_plane(insp, rect, faces, mm, pos):
    """Пила идёт вертикально по экрану через точку клика: → (нормаль, отступ) в осях камня или None."""
    ray = pick(insp, rect, faces, mm, pos)
    if ray is None:
        return None
    n = insp.to_stone((1.0, 0.0, 0.0))
    p = mid(ray)
    return n, _dot(n, p)


def saw_split(stone, plane):
    """Распилить кусок плоскостью → два новых куска (или None, если какой-то слишком мал)."""
    import copy
    n, h = plane
    faces, R, _ = JV.rough_geom(stone)
    vol0 = G3.volume(faces)
    pieces = []
    for side, tag in ((1.0, "a"), (-1.0, "b")):
        piece = copy.deepcopy(stone)
        piece["uid"] = f"{stone['uid']}{tag}"
        piece.setdefault("size0", stone.get("size", 1.0))
        nn = [round(side * v, 5) for v in n]
        piece.setdefault("saws", []).append({"n": nn, "h": round((side * h - SAW_KERF * R) / R, 5)})
        pieces.append(piece)
    vols = [G3.volume(JV.rough_geom(p)[0]) for p in pieces]
    if min(vols) <= 0:
        return None
    for p, v in zip(pieces, vols):
        k = v / max(1e-9, vol0)
        p["size"] = round(stone["size"] * k, 3)
        if stone.get("cost"):
            p["cost"] = round(stone["cost"] * k)
        side = 1.0 if p["uid"].endswith("a") else -1.0
        p["marks"] = [m for m in stone.get("marks") or [] if side * (_dot(n, mid(m)) - h) < 0]
    if min(p["size"] for p in pieces) < MIN_PIECE_CT:
        return None
    return pieces


# ---------- разбор ----------

def _tol(R):
    return 0.07 * R


def _stone_median_t(stone, xd):
    import numpy as np
    o = stone["cf"]["o"]
    rad = GM.stone_mm_radius(xd, stone["id"], stone["size"])
    pts = [(o[0] + x * rad, o[1] + y * rad, o[2] + z * rad) for x, y, z in GM.unit_ball()]
    return float(np.median(GM.field_t(stone["id"], pts, o)))


def _color_true(stone, xd, mark, med):
    """Цветная зона на луче: оттенок заметно отличается от основного тона камня."""
    faces = JV.rough_faces(stone)
    mmr = JV.mm_per_unit(stone, faces, xd)
    o = stone["cf"]["o"]
    a, b = mark["a"], mark["b"]
    pts = []
    for k in range(9):
        t = (k + 0.5) / 9
        p = _add(a, _sub(b, a), t)
        pts.append((p[0] * mmr + o[0], p[1] * mmr + o[1], p[2] * mmr + o[2]))
    ts = GM.field_t(stone["id"], pts, o)
    return float(max(abs(ts - med))) > 0.10


def review(stone, xd):
    """Сверить метки с тем, что на самом деле внутри.

    → {"items": [(вид, текст, цвет)], "score": 0..1, "hits", "misses"}."""
    if "seed" not in stone or "q" in stone:
        return None
    faces, R, _ = JV.rough_geom(stone)
    mmr = JV.mm_per_unit(stone, faces, xd)
    incl = JV.rough_incl(stone)
    body = [i for i in incl if i["k"] != "silk"]
    silk = max((i.get("d", 0.0) for i in incl if i["k"] == "silk"), default=0.0)
    names = GM.cfg(xd)["incl_kinds"]
    ms = list(stone.get("marks") or [])
    items = []
    used = set()
    good = bad = 0
    med = None

    def nm(k):
        return names.get(k, {}).get("name", k)

    for m in ms:
        k = m["k"]
        label = KIND.get(k, (k,))[0].lower()
        if k == "silk":
            if silk >= 0.3:
                items.append(("hit", "шёлк — верно: иглы есть", (150, 220, 150)))
                good += 1
            else:
                items.append(("false", "шёлк — ошибка: игл нет", (230, 110, 100)))
                bad += 1
            continue
        if k == "color":
            if med is None:
                med = _stone_median_t(stone, xd)
            if _color_true(stone, xd, m, med):
                items.append(("hit", "цвет — верно: там зона другого оттенка", (150, 220, 150)))
                good += 1
            else:
                items.append(("false", "цвет — ошибка: там тон ровный", (230, 110, 100)))
                bad += 1
            continue
        near = [(ray_dist(m, i["p"]), j, i) for j, i in enumerate(body)
                if ray_dist(m, i["p"]) <= i["r"] * 1.2 + _tol(R)]
        if k == "clean":
            if near:
                i = min(near, key=lambda x: x[0])[2]
                items.append(("false", f"«чисто» — нет: там {nm(i['k'])}", (230, 110, 100)))
                bad += 1
            else:
                items.append(("hit", "«чисто» — верно", (150, 220, 150)))
                good += 1
            continue
        free = [x for x in near if x[1] not in used]
        if not free:
            items.append(("false", f"{label} — там ничего нет", (230, 110, 100)))
            bad += 1
            continue
        _, j, i = min(free, key=lambda x: (CATEGORY.get(i_k(x), "") != CATEGORY.get(k, "?"), x[0]))
        used.add(j)
        if CATEGORY.get(i["k"]) == CATEGORY.get(k):
            items.append(("hit", f"{label} — верно", (150, 220, 150)))
            good += 1
        else:
            items.append(("wrong", f"{label} — там оказалось: {nm(i['k'])}", (235, 190, 110)))
            bad += 1
    for j, i in enumerate(body):
        if j in used:
            continue
        size = 2 * i["r"] * mmr
        if size < 0.25:                     # совсем мелкое — не упрёк
            continue
        items.append(("miss", f"пропущено: {nm(i['k'])} · {size:.1f} мм", (200, 160, 150)))
        bad += 1
    if silk >= 0.3 and not any(m["k"] == "silk" for m in ms):
        items.append(("miss", "пропущено: шёлк (звезда в кабошоне)", (200, 160, 150)))
        bad += 1
    total = good + bad
    return {"items": items, "score": good / total if total else 1.0, "hits": good, "misses": bad,
            "marked": len(ms)}


def i_k(x):
    return x[2]["k"]


# ---------- разметка: оценка по меткам ----------

def plan_marks(pl, stone, s=None):
    """Метки в осях будущего камня: [(метка, точка, внутри ли контура)]."""
    s = s or pl.s()
    out = []
    for m in stone.get("marks") or []:
        p = pl.to_stone(mid(m), s)
        inside = all(_dot(n, p) - off <= 0.0 for n, off in pl.ideal_planes)
        out.append((m, p, inside))
    return out


def plan_estimate(pl, stone, xd, s=None):
    """Что игрок может ожидать по своим меткам: чистота, риск скола, шёлк."""
    s = s or pl.s()
    pseudo, risk = [], 0.0
    pm = plan_marks(pl, stone, s)
    for m, p, inside in pm:
        k = m["k"]
        if not inside or k in ("color", "clean"):
            continue
        if k == "silk":
            pseudo.append({"k": "silk", "p": [0, 0, 0], "r": 0.5, "d": 0.6})
            continue
        lo, hi = GM.INCL_SIZE.get(k, (0.04, 0.1))
        r = (lo + hi) / 2 * pl.Rr / max(1e-9, s)
        pseudo.append({"k": k, "p": list(p), "r": r})
        if k == "feather":
            near = min(off - _dot(n, p) for n, off in pl.ideal_planes)
            if near < r * 2.2:
                risk += 0.12
    body = [m for m, p, inside in pm if m["k"] not in ("color", "clean", "silk")]
    return {"clarity": GM.clarity(xd, pseudo, gid=stone["id"]) if xd else 1.0,
            "risk": min(1.0, risk),
            "inside": sum(1 for m, p, ok in pm if ok and m["k"] not in ("color", "clean", "silk")),
            "total": len(body),
            "silk": any(m["k"] == "silk" for m, p, ok in pm)}
