"""Карта этажа «Спуска» (docs/descent.md §6): ряды узлов с развилками, в последнем ряду — страж лестницы.

Узел: {"id", "layer", "idx", "count", "type", "next": [id], "fight"?}. Типы: battle, elite, camp, shop, boss —
те же, что у карты похода (рисуется её же медальонами, ui/map_art.py). Первый ряд — только бои, предпоследний —
костёр и торговец, элита — не раньше третьего ряда.
"""


def make_fight(cfg, kind, rng):
    pool = cfg["pools"][kind]
    p = rng.choice(pool)
    return {"name": p["name"], "map": rng.choice(p["maps"]), "enemies": list(p["enemies"]),
            "elite": kind == "elite", "boss": kind == "boss"}


def generate(cfg, rng):
    rows = cfg["rows"]
    lo, hi = cfg["width"]
    layers = []
    for i in range(rows):
        if i == rows - 1:
            n = 1
        elif i == rows - 2:
            n = 2
        else:
            n = rng.randint(lo, hi)
        layers.append(n)
    nodes = {}
    for i, n in enumerate(layers):
        for k in range(n):
            if i == rows - 1:
                t = "boss"
            elif i == rows - 2:
                t = "camp" if k == 0 else "shop"
            elif i == 0:
                t = "battle"
            else:
                w = dict(cfg["weights"])
                if i < 2:
                    w.pop("elite", None)
                    w.pop("altar", None)
                    w.pop("chest", None)
                    w.pop("workshop", None)
                if i == 1:
                    w.pop("camp", None)
                kinds, weights = zip(*w.items())
                t = rng.choices(kinds, weights)[0]
            nid = f"n{i}_{k}"
            nodes[nid] = {"id": nid, "layer": i, "idx": k, "count": n, "type": t, "next": []}
            if t in ("battle", "elite", "boss"):
                nodes[nid]["fight"] = make_fight(cfg, t, rng)
    for i in range(rows - 1):                       # тропы: к 1–2 ближайшим в следующем ряду, без «сирот»
        cur = [nodes[f"n{i}_{k}"] for k in range(layers[i])]
        nxt = [nodes[f"n{i + 1}_{k}"] for k in range(layers[i + 1])]
        for a in cur:
            pos = (a["idx"] + 0.5) / a["count"]
            near = sorted(nxt, key=lambda b: abs((b["idx"] + 0.5) / b["count"] - pos))
            a["next"].append(near[0]["id"])
            if len(near) > 1 and rng.random() < 0.45:
                a["next"].append(near[1]["id"])
        for b in nxt:
            if not any(b["id"] in a["next"] for a in cur):
                pos = (b["idx"] + 0.5) / b["count"]
                a = min(cur, key=lambda a: abs((a["idx"] + 0.5) / a["count"] - pos))
                a["next"].append(b["id"])
    return nodes


class Floor:
    def __init__(self, cfg, rng, depth):
        self.depth = depth
        self.nodes = generate(cfg, rng)
        self.node = None                             # где стоит герой (None — у входа)
        self.path = []

    def available(self):
        if self.node is None:
            return [nid for nid, n in self.nodes.items() if n["layer"] == 0]
        return list(self.nodes[self.node]["next"])

    def enter(self, nid):
        self.node = nid
        self.path.append(nid)
        return self.nodes[nid]
