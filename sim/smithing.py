"""Ковка (Горн мастера) — логика этапов: плавка → пакет → сварка и складывание → разделка → ковка и закалка.

Кусок металла: {"uid", "metal", "cells": [[x, y]], "purity"} — клетка = cell_g граммов. Пакет: {"uid", "grid":
[[металл|None]] (строки — слои), "layers", "purity", "voids", "weld", "burn", "folds", "pattern", "twist"}.
Часть: {"uid", "mass", "props": свойства металла, "q0": качество подготовки}. Свойства металла (props):
{"hard", "tough", "layers", "pattern"} — переходят в артефакт (sim/artifacts.py: metal_mods) и дают статы.
Данные — expedition.json "smithing"."""
import math


def cfg(xd):
    return xd["smithing"]


# ---------- формы кусков ----------

def rotate(cells):
    """Поворот формы на 90° (и сдвиг к нулю)."""
    out = [(-y, x) for x, y in cells]
    mx, my = min(x for x, _ in out), min(y for _, y in out)
    return [[x - mx, y - my] for x, y in out]


def norm_cells(cells):
    mx, my = min(x for x, _ in cells), min(y for _, y in cells)
    return [[x - mx, y - my] for x, y in cells]


def piece_mass(xd, p):
    return len(p["cells"]) * cfg(xd)["cell_g"]


def new_piece(xd, uid, metal, rng, purity=None, shape=None):
    sh = shape or rng.choice(sorted(cfg(xd)["shapes"]))
    cells = cfg(xd)["shapes"][sh]
    for _ in range(rng.randrange(4)):
        cells = rotate(cells)
    lo, hi = cfg(xd)["metals"][metal].get("purity", [0.7, 0.9])
    return {"uid": uid, "metal": metal, "cells": norm_cells(cells),
            "purity": round(purity if purity is not None else rng.uniform(lo, hi), 3)}


# ---------- плавка ----------

def smelt_result(xd, carbon, heat_ok, slag, rng, uid_fn):
    """Итог плавки: углерод (0–1) → железо / сталь; держали жар (0–1), сняли шлак (0–1) → чистота; число кусков."""
    c = cfg(xd)["smelt"]
    metal = "steel" if carbon >= c["steel_carbon"] else "iron"
    purity = max(0.4, min(0.98, 0.45 + 0.3 * heat_ok + 0.25 * slag))
    n = c["pieces"][0] + (1 if heat_ok > 0.7 else 0)
    if carbon > c["cast_carbon"]:                      # чугун — хрупкий, куски мельче и грязнее
        purity *= 0.75
    return [new_piece(xd, uid_fn(), metal, rng, purity) for _ in range(n)]


# ---------- пакет ----------

def frame_size(xd, kind):
    """Рамка пакета: заготовка по id (малая, средняя, длинная…) или по рецепту вещи."""
    fr = cfg(xd).get("frames", {})
    if kind in fr:
        return tuple(fr[kind]["size"])
    return tuple(cfg(xd)["recipes"][kind]["frame"])


def place_ok(grid, cells, ox, oy):
    h, w = len(grid), len(grid[0])
    for x, y in cells:
        X, Y = ox + x, oy + y
        if not (0 <= X < w and 0 <= Y < h) or grid[Y][X] is not None:
            return False
    return True


def solid_rows(grid):
    """Сварка сжимает пакет в цельный слиток: пустые клетки уходят, слои — непустые строки, каждая растянута
    на общую длину (поров нет — слиток просто легче)."""
    rows = [[m for m in r if m] for r in grid]
    rows = [r for r in rows if r]
    if not rows:
        return [[None]]
    n = max(len(r) for r in rows)
    return [[r[min(len(r) - 1, i * len(r) // n)] for i in range(n)] for r in rows]


def billet_from(xd, uid, grid, pieces):
    """Пакет со стола: слои — непустые строки (пустые клетки не поры: при сварке слиток цельный).
    pieces — положенные куски (для чистоты)."""
    filled = [m for row in grid for m in row if m]
    pur = sum(p["purity"] * len(p["cells"]) for p in pieces) / max(1, sum(len(p["cells"]) for p in pieces))
    rows = solid_rows(grid)
    return {"uid": uid, "grid": rows, "layers": len(rows), "purity": round(pur, 3), "voids": 0.0, "weld": 0.0,
            "burn": 0.0, "folds": 0, "twist": 0, "mass": len(filled) * cfg(xd)["cell_g"], "welded": False}


def pattern_score(xd, grid):
    """Узор дамаска: доля соседних слоёв, где твёрдость заметно разная (чередование твёрдых и мягких)."""
    M = cfg(xd)["metals"]

    def row_hard(row):
        ms = [m for m in row if m]
        return sum(M[m]["hard"] for m in ms) / len(ms) if ms else 0.0
    hs = [row_hard(r) for r in grid if any(r)]
    if len(hs) < 2:
        return 0.0
    return sum(1 for a, b in zip(hs, hs[1:]) if abs(a - b) >= 0.25) / (len(hs) - 1)


def billet_props(xd, b):
    """Свойства металла пакета: средние твёрдость и вязкость по массе + дамаск (слои × узор), выгорание, поры."""
    M = cfg(xd)["metals"]
    ms = [m for row in b["grid"] for m in row if m]
    if not ms:
        return {"hard": 0.0, "tough": 0.0, "layers": 0, "pattern": 0.0}
    hard = sum(M[m]["hard"] for m in ms) / len(ms)
    tough = sum(M[m]["tough"] for m in ms) / len(ms)
    pat = pattern_score(xd, b["grid"]) * (1 + 0.25 * b.get("twist", 0))
    layers = b["layers"] * 2 ** b.get("folds", 0)
    if pat > 0 and layers >= 8:                         # дамаск: твёрдые слои режут, мягкие держат
        k = min(1.0, math.log2(layers / 4) / 6) * min(1.0, pat)
        tough += 0.25 * k * (1 - tough)
        hard += 0.08 * k
    hard -= 0.35 * b.get("burn", 0)                     # перегрев выжигает твёрдость
    tough -= 0.25 * (1 - b.get("weld", 1.0)) if b.get("welded") else 0.0     # недоваренные слои расслаиваются
    return {"hard": round(max(0, min(1, hard)), 3), "tough": round(max(0, min(1, tough)), 3),
            "layers": int(layers), "pattern": round(min(1.0, pat), 3)}


def fold(xd, b):
    """Складывание: слоёв вдвое больше, металл чище, но часть массы уходит в окалину."""
    c = cfg(xd)["weld"]
    b["folds"] += 1
    b["purity"] = round(min(0.99, b["purity"] + c["fold_purity"]), 3)
    b["mass"] = int(b["mass"] * (1 - c["fold_loss"]))
    return b


def prep_quality(xd, b):
    """Качество подготовки металла (0–1): чистота, сварка слоёв, выгорание."""
    return max(0.0, min(1.0, 0.45 * b["purity"] + 0.45 * b["weld"] + 0.1 * (1 - b.get("burn", 0) * 2)))


# ---------- разделка ----------

def cut_part(xd, uid, b, mass, cold, wide=False):
    """Отсечённая часть любой массы: свойства пакета, качество подготовки (холодный рез — хуже).
    wide — точные весы: при ковке допуск массы шире."""
    q0 = prep_quality(xd, b) * (0.85 if cold else 1.0)
    return {"uid": uid, "mass": int(round(mass)), "props": billet_props(xd, b), "q0": round(q0, 3), "wide": wide,
            "look": {"rows": [list(r) for r in b["grid"]], "folds": b.get("folds", 0), "twist": b.get("twist", 0)}}


def parts_for(xd, kind):
    return list(cfg(xd)["recipes"][kind]["parts"])


def mass_fit(xd, part, need):
    """Хватает ли массы (1 — хватает или больше, 0 — сильно легче): лишний металл не штраф — вещь массивнее."""
    c = cfg(xd)["cut"]
    tol = c.get("tol_scales", c["tol"]) if part.get("wide") else c["tol"]
    short = max(0.0, need - part["mass"]) / need
    return max(0.0, 1 - short / (tol * 3))


def match_parts(xd, kind, parts):
    """Части под вещь: на каждую нужную массу — часть не легче 85% от неё (тяжелее — можно: вещь выйдет
    массивнее); берётся ближайшая по массе, при равенстве — лучшая. Сначала — самые тяжёлые нужды."""
    need = parts_for(xd, kind)
    out = [None] * len(need)
    used = []
    for i in sorted(range(len(need)), key=lambda k: -need[k]):
        m = need[i]
        cands = [p for p in parts if p not in used and p["mass"] >= 0.85 * m]
        if not cands:
            return None
        p = min(cands, key=lambda x: (abs(x["mass"] - m), -x["q0"]))
        out[i] = p
        used.append(p)
    return out


def final_quality(xd, parts, shape_scores, kind=None):
    """Качество вещи (0.7–1.3): подготовка металла частей, попадание в нужную массу и ковка каждой части."""
    lo, hi = xd["artifacts"]["quality"]
    need = parts_for(xd, kind) if kind else [p["mass"] for p in parts]
    s = sum((0.3 * p["q0"] + 0.15 * mass_fit(xd, p, m) + 0.55 * sc)
            for p, m, sc in zip(parts, need, shape_scores)) / max(1, len(parts))
    return round(lo + (hi - lo) * max(0.0, min(1.0, s)), 3)


def mass_bonus(parts, kind_need):
    """Массивность вещи: лишний металл частей (сверх нужного) — немного здоровья (не больше +4%)."""
    extra = sum(max(0, p["mass"] - m) for p, m in zip(parts, kind_need)) / max(1, sum(kind_need))
    return round(min(0.04, 0.05 * extra), 4)


def merge_props(parts, quench):
    """Свойства металла вещи: среднее по частям, закалка правит твёрдость и вязкость."""
    n = max(1, len(parts))
    hard = sum(p["props"]["hard"] for p in parts) / n + quench.get("hard", 0)
    tough = sum(p["props"]["tough"] for p in parts) / n + quench.get("tough", 0)
    return {"hard": round(max(0, min(1, hard)), 3), "tough": round(max(0, min(1, tough)), 3),
            "layers": min(p["props"]["layers"] for p in parts), "pattern": round(sum(p["props"]["pattern"]
                                                                                 for p in parts) / n, 3)}


# ---------- заказы и бродячие кузнецы ----------

def roll_orders(xd, rng, n=2):
    c = cfg(xd)["orders"]
    out = []
    for k in range(n):
        t = rng.choice(c["templates"])
        out.append({"id": f"o{rng.randrange(10 ** 6)}", "kind": t["kind"], "text": t["text"], "req": dict(t["req"]),
                    "q": t.get("q", 0.9), "gold": rng.randint(*t["gold"]), "mats": dict(t.get("mats", {}))})
    return out


def order_ok(xd, order, art):
    """Подходит ли вещь под заказ: вид, качество, свойства металла."""
    if art["kind"] != order["kind"] or art["q"] < order["q"] or not art.get("metal"):
        return False
    m = art["metal"]
    return all(m.get(k, 0) >= v for k, v in order["req"].items())


def roll_wanderer(xd, rng, owned_tools, uid_fn):
    """Бродячий кузнец на рынке (иногда): редкие куски металла, инструменты, приёмы."""
    c = cfg(xd)
    if rng.random() >= c["wanderer"]["chance"]:
        return None
    rare = [m for m, v in c["metals"].items() if v.get("rare")]
    pieces = [dict(new_piece(xd, uid_fn(), rng.choice(rare), rng), price=rng.randint(*c["wanderer"]["piece_price"]))
              for _ in range(rng.randint(2, 4))] if rare else []
    tools = [t for t in sorted(c["tools"]) if t not in owned_tools]
    rng.shuffle(tools)
    return {"name": rng.choice(c["wanderer"]["names"]), "pieces": pieces, "tools": tools[:2]}
