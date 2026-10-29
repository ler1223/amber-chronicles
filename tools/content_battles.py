"""Длинные бои: волны, цели боя, объекты поля и фазы боссов → data/battles.json (накладывается на encounters.json).

В каждой главе 10 боёв:
  обычные (4) и первый страж — короткие, 1 волна, на поле бочки и валуны;
  второй страж — «Удержать точку» 25 с (3 волны), третий — «Разрушить источники», четвёртый — «Защитить объект»
  (2 волны); элита — 2 волны; босс — 2 фазы: на 66% и 33% HP по подкреплению, события поля сразу.
  Следующие волны меньше первой, и один враг первой волны переходит во вторую: в передышку ничего не
  восстанавливается.
Элита, босс и «Разрушить источники» — на большом поле 14×8 (карта главы, продолженная вправо и по краям).
Перезапускаемый: python tools/content_battles.py
"""
import json
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# глава -> (точка удержания, источник врагов, охраняемый объект с названием по главе)
THEMES = {
    "swamp": ("Островок среди трясины", "nest", ("cart", "Застрявшая телега")),
    "forge": ("Плавильная площадка", "hearth", ("prisoner", None)),
    "crypt": ("Освящённый круг", "sarcophagus", ("ward_torch", None)),
    "pass": ("Перевал между лавинами", "ice_idol", ("cart", "Обоз")),
    "steppe": ("Курган", "raider_tent", ("lightning_rod", None)),
    "tomb": ("Тень обелиска", "hive", ("caravan", None)),
    "fae": ("Светлый круг грибов", "witch_ring", ("glow_tree", None)),
    "sunken": ("Возвышение до отлива", "conch", ("bell", None)),
    "citadel": ("Площадка над пропастью", "anchor", ("sky_bridge", None)),
}
BAD = ("lava", "chasm")


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


class Field:
    """Карта боя: какие клетки можно занять."""

    def __init__(self, enc, cfg):
        self.rows = enc["map"]
        self.legend = cfg["legend"]
        self.w, self.h = len(self.rows[0]), len(self.rows)
        self.taken = {tuple(e["pos"]) for e in enc["enemies"]} | {tuple(p) for p in enc["player_spawn"]}
        self.deploy_x = enc.get("deploy_max_x", cfg["deploy_max_x"])

    def ok(self, p):
        x, y = p
        if not (0 <= x < self.w and 0 <= y < self.h) or p in self.taken:
            return False
        d = self.legend[self.rows[y][x]]
        return d.get("passable", True) and d.get("terrain", "grass") not in BAD and not d.get("hazard") \
            and not d.get("portal")

    def take(self, p):
        self.taken.add(p)
        return [p[0], p[1]]

    def pick(self, rng, xs, ys=None):
        cells = [(x, y) for x in xs for y in (ys or range(self.h)) if self.ok((x, y))]
        return self.take(rng.choice(cells)) if cells else None


def edge_wave(rng, pool, n, field):
    """Волна выходит с правого края поля: клетки x = 8..9 (занятые сейчас врагами — не страшно, сдвинутся)."""
    ys = list(range(field.h))
    rng.shuffle(ys)
    out = []
    for i in range(n):
        y = ys[i % len(ys)]
        out.append({"type": rng.choice(pool), "pos": [field.w - 1 - (i // len(ys)), y]})
    return out


def props(rng, field, n):
    """Бочки и валуны в середине поля."""
    out = []
    for _ in range(n):
        p = field.pick(rng, range(field.deploy_x + 2, field.w - 3))
        if p:
            kind = rng.choices(["barrel_powder", "barrel_oil", "boulder"], [5, 2, 3])[0]
            out.append({"type": kind, "pos": p})
    return out


def split_first_wave(e, b, enemies, field):
    """Один обычный враг первой волны переходит во вторую (с края поля): длинный бой прибавляет одного врага,
    а не целую волну сверху."""
    first = list(e["enemies"])
    plain = [x for x in first if not enemies[x["type"]].get("elite") and not enemies[x["type"]].get("boss")]
    if len(first) < 4 or not plain:
        return
    moved = plain[-1]
    first.remove(moved)
    b["enemies"] = first
    y = moved["pos"][1]
    b["waves"][0] = [{"type": moved["type"], "pos": [field.w - 1, y]}] + b["waves"][0][:-1]


BIG_W, BIG_H = 14, 8          # большое поле: элита, босс, «Разрушить источники»


def enlarge(e, cfg, rng, pool):
    """Карта 10×6 → 14×8: исходная ложится слева (зона высадки та же), справа и по краям — продолжение рельефа
    (отражение карты главы, часть препятствий убрана, чтобы не запереть проходы). Враги — правее, +1 враг."""
    rows = e["map"]
    h, w = len(rows), len(rows[0])
    legend = cfg["legend"]

    def src(x, y):
        sx = x if x < w else 2 * w - 1 - x
        sy = min(max(y - 1, 0), h - 1)
        return rows[sy][max(0, min(w - 1, sx))]

    grid = []
    for y in range(BIG_H):
        line = ""
        for x in range(BIG_W):
            ch = src(x, y)
            fresh = x >= w or y in (0, BIG_H - 1)
            if fresh and not legend[ch].get("passable", True) and rng.random() < 0.5:
                ch = "."
            if fresh and legend[ch].get("portal"):
                ch = "."
            if x <= 2 and not legend[ch].get("passable", True):
                ch = "."                                   # зона высадки — свободна
            line += ch
        grid.append(line)

    def ok(p, taken):
        x, y = p
        d = legend[grid[y][x]]
        return d.get("passable", True) and d.get("terrain", "grass") not in BAD and p not in taken

    taken = set()
    spawns = []
    for x, y in e["player_spawn"]:
        p = (x, y + 1)
        if not ok(p, taken):
            p = next(q for q in ((a, b) for a in range(3) for b in range(BIG_H)) if ok(q, taken))
        spawns.append([p[0], p[1]])
        taken.add(p)
    foes = []
    for x in e["enemies"] + [{"type": rng.choice(pool), "pos": [9, rng.randrange(h)]}]:
        p = (min(BIG_W - 1, x["pos"][0] + 3), x["pos"][1] + 1)
        if not ok(p, taken):
            cand = [(a, b) for a in range(6, BIG_W) for b in range(BIG_H) if ok((a, b), taken)]
            p = min(cand, key=lambda q: abs(q[0] - p[0]) + abs(q[1] - p[1]))
        foes.append({"type": x["type"], "pos": [p[0], p[1]]})
        taken.add(p)
    return {"map": grid, "player_spawn": spawns, "enemies": foes}


def hold_cells(field):
    """Круг 2×2 в центре: ищем самый центральный квадрат из доступных клеток."""
    cx, cy = field.w / 2 - 0.5, field.h / 2 - 0.5
    best = None
    for x in range(field.deploy_x + 2, field.w - 3):
        for y in range(field.h - 1):
            sq = [(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)]
            n = sum(1 for p in sq if field.ok(p) or p in field.taken)
            d = abs(x + 0.5 - cx) + abs(y + 0.5 - cy)
            if n == 4 and (best is None or d < best[0]):
                best = (d, sq)
    return [list(p) for p in best[1]] if best else None


def build():
    cfg, encs, biomes = load("config.json"), load("encounters.json"), load("biomes.json")
    enemies = load("enemies.json")
    out = {}
    for cid, biome in biomes.items():
        mine = [e for e in encs if e.get("chapter", "swamp") == cid]
        normals = [e for e in mine if e["kind"] == "normal"]
        pool = sorted({x["type"] for e in normals for x in e["enemies"] if not enemies[x["type"]].get("elite")})
        melee = [t for t in pool if enemies[t]["attack"]["range"] <= 1] or pool
        guards = [r["guard"] for r in biome["regions"]
                  if next(e for e in mine if e["id"] == r["guard"])["kind"] == "guard"]
        hold_name, source, (guard_obj, guard_name) = THEMES[cid]
        for e in mine:
            rng = random.Random(e["id"])
            b = {}
            if e["kind"] in ("elite", "boss") or e["id"] in guards[2:3]:
                b.update(enlarge(e, cfg, rng, pool))       # большое поле
                e = dict(e, **b)
            f = Field(e, cfg)
            if e["kind"] == "normal" or (guards and e["id"] == guards[0]):
                b["objects"] = props(rng, f, rng.randint(1, 2))
            elif e["id"] in guards[1:2]:
                cells = hold_cells(f)
                f.taken.update(tuple(p) for p in cells or [])      # бочки не ставим в круг
                b["objective"] = {"type": "hold", "name": hold_name, "cells": cells, "time": 25.0}
                b["waves"] = [edge_wave(rng, pool, 2, f), edge_wave(rng, pool, 3, f)]
                b["wave_timeout"] = 18.0
                b["objects"] = props(rng, f, 1)
            elif e["id"] in guards[2:3]:
                b["objective"] = {"type": "destroy", "name": "Разрушить источники"}
                srcs = []
                for ys in (range(0, f.h // 2), range(f.h // 2, f.h)):
                    p = f.pick(rng, range(f.w - 3, f.w - 1), ys)
                    if p:
                        srcs.append({"type": source, "pos": p, "spawn": melee})
                b["objects"] = srcs + props(rng, f, 1)
            elif e["id"] in guards[3:4]:
                p = f.pick(rng, [0, 1], range(1, f.h - 1))        # в тылу, за спинами героев
                obj = {"type": guard_obj, "pos": p}
                if guard_name:
                    obj["name"] = guard_name
                b["objective"] = {"type": "defend", "name": f"Защитить: {guard_name or load_name(guard_obj)}"}
                b["waves"] = [edge_wave(rng, pool, 3, f)]
                b["objects"] = [obj] + props(rng, f, 1)
            elif e["kind"] == "elite":
                b["waves"] = [edge_wave(rng, pool, 2, f)]
                b["objects"] = props(rng, f, 1)
            elif e["kind"] == "boss":
                b["phases"] = [
                    {"at": 0.66, "name": "Гнев", "spawn": edge_wave(rng, pool, 1, f)},
                    {"at": 0.33, "name": "Последний рубеж", "spawn": edge_wave(rng, pool, 1, f)},
                ]
                b["objects"] = props(rng, f, 1)
            if b.get("waves"):
                split_first_wave(e, b, enemies, f)
            b = {k: v for k, v in b.items() if v}
            if b:
                out[e["id"]] = b
    return out


_OBJ = None


def load_name(oid):
    global _OBJ
    _OBJ = _OBJ or load("objects.json")
    return _OBJ[oid]["name"]


def main():
    battles = build()
    j = lambda v: json.dumps(v, ensure_ascii=False)  # noqa: E731
    lines = []
    for bid, b in battles.items():
        inner = ",\n".join(f"    {j(k)}: {j(v)}" for k, v in b.items())
        lines.append(f"  {j(bid)}: {{\n{inner}\n  }}")
    with open(os.path.join(DATA, "battles.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write("{\n" + ",\n".join(lines) + "\n}\n")
    kinds = {}
    for b in battles.values():
        k = b.get("objective", {}).get("type") or ("phases" if "phases" in b else "waves" if "waves" in b else "props")
        kinds[k] = kinds.get(k, 0) + 1
    print(f"battles.json: {len(battles)} боёв, {kinds}")


if __name__ == "__main__":
    main()
