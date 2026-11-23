"""Новый архетип Охотницы «Снайпер»: линейные выстрелы и заряжающиеся стрелы.

Все карты проходят аудит: без альтернативного применения, стоимость по общей
политике. Линейные карты стреляют только по горизонтали/вертикали.
"""
import copy
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "deck")
P_CARDS = os.path.join(D, "cards.json")
P_HEROES = os.path.join(D, "heroes.json")
P_CZN = os.path.join(ROOT, "data", "czn", "cards.json")
SEQ = 0


def op(name, n=None, **kw):
    o = {"op": name}
    if n is not None:
        o["n"] = n
    o.update(kw)
    return o


def shot(rng, *do, line=False, pierce=False):
    u = {"target": "enemy", "range": rng, "los": True, "ranged": True, "do": list(do)}
    if line:
        u["line"] = True
    if pierce:
        u["pierce"] = True
    return u


def bump(x, f=0.35):
    x = copy.deepcopy(x)

    def walk(o):
        if isinstance(o, dict):
            if o.get("op") in {"damage", "block", "draw", "mark", "vulnerable", "bleed", "push",
                               "ranged_bonus", "energy"} and o.get("n") is not None:
                o["n"] = max(1, o["n"] + max(1, round(o["n"] * f)))
            if "plus" in o:
                o["plus"] += max(1, round(o["plus"] * f))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(x)
    return x


def add_op(use, *ops):
    x = copy.deepcopy(use)
    x["do"] = list(x.get("do", [])) + list(ops)
    return x


def options(main):
    return [
        {"label": "Сильнее", "main": bump(main)},
        {"label": "С добором", "name": "Дыхание", "main": add_op(main, op("draw", 1))},
        {"label": "С защитой", "main": add_op(main, op("block", 3))},
        {"label": "С меткой", "name": "Метка", "main": add_op(main, op("mark", 1))},
        {"label": "С энергией", "name": "Второе дыхание", "main": add_op(main, op("energy", 1))},
    ]


def ill_from(cards, cid, dx, dy):
    global SEQ
    SEQ += 1
    i = SEQ
    src = list(cards[cid]["ill"])
    return [src[0], round(min(0.98, max(0.02, src[1] + dx + (i % 8) * 0.007)), 4),
            round(min(0.98, max(0.02, src[2] + dy + (i // 8) * 0.009)), 4), src[3]]


def add(cards, cid, src, name, main, tags, *, typ, cost, rarity, **extra):
    c = copy.deepcopy(cards[src])
    for field in ("levels", "react", "echo", "chain", "keep", "temper", "exhaust", "trap",
                  "auto_end", "source", "x_cost", "grow_end", "retain"):
        c.pop(field, None)
    c.update({"name": name, "main": main, "alt": {"target": "none", "do": []},
              "type": typ, "cost": cost, "tags": list(tags), "category": "hero",
              "owner": "hunter", "rarity": rarity, "ill": ill_from(cards, src, 0.04, 0.02)})
    c.update(extra)
    if "growth" in c:
        c["growth"][0]["options"] = options(main)
    cards[cid] = c


def main():
    data = json.load(open(P_CARDS, encoding="utf-8"))
    cards = data["cards"]
    ids = []

    # Линейные выстрелы: только горизонталь/вертикаль.
    add(cards, "h_sniper_line", "h_snipe", "Выстрел в линию",
        shot(6, op("damage", 12), line=True), ["Выстрел"], typ="attack", cost=2, rarity=2)
    ids.append("h_sniper_line")

    add(cards, "h_sniper_pierce", "h_rng_pale_star", "Сквозной выстрел",
        shot(7, op("damage", 12), line=True, pierce=True), ["Выстрел", "Область"],
        typ="attack", cost=3, rarity=4)
    ids.append("h_sniper_pierce")

    add(cards, "h_sniper_expose", "h_dmg_expose", "Выстрел в уязвимость",
        shot(6, op("damage", 9), op("vulnerable", 2), line=True), ["Выстрел", "Клич"],
        typ="attack", cost=2, rarity=3)
    ids.append("h_sniper_expose")

    # Заряжающиеся стрелы.
    add(cards, "h_sniper_grow", "h_patient_shot", "Растущая стрела",
        shot(6, op("damage", 5)), ["Выстрел", "Сохранение"],
        typ="attack", cost=1, rarity=2, retain=True, grow_end={"n": 2})
    ids.append("h_sniper_grow")

    add(cards, "h_sniper_fate", "h_rng_pale_star", "Стрела судьбы",
        shot(6, op("damage", 8), line=True), ["Выстрел", "Сохранение"],
        typ="attack", cost=2, rarity=4, retain=True, grow_end={"n": 3})
    ids.append("h_sniper_fate")

    # Усилитель: первые две атаки — двойной урон.
    add(cards, "h_sniper_double", "h_focus", "Двойной залп",
        {"target": "self", "do": [op("double_attacks", 2)]}, ["Комбо", "Выстрел"],
        typ="skill", cost=2, rarity=4)
    cards["h_sniper_double"]["source"] = {
        "game": "CZN", "character": "Luke", "name": "Seize the Opportunity",
        "effect": "100% Shield · +120% Damage Amount to the next Bullet card activated",
    }
    ids.append("h_sniper_double")

    # X-стоимость: вся доступная энергия.
    add(cards, "h_sniper_allin", "h_deadeye", "Выстрел на всю энергию",
        shot(6, op("damage", 6, x=4), line=True), ["Выстрел"],
        typ="attack", cost=0, rarity=4, x_cost=True)
    cards["h_sniper_allin"]["source"] = {
        "game": "CZN", "character": "Lucas", "name": "Last-Ditch Assault",
        "effect": "300% Damage; discard Dirge Bullets for +50%",
    }
    ids.append("h_sniper_allin")

    heroes = json.load(open(P_HEROES, encoding="utf-8"))
    h = heroes["heroes"]["hunter"]
    h["rewards"] = list(dict.fromkeys(h.get("rewards", []) + ids))
    by_var = {
        "range": ["h_sniper_line", "h_sniper_pierce", "h_sniper_expose", "h_sniper_allin"],
        "mark": ["h_sniper_expose", "h_sniper_pierce", "h_sniper_allin"],
        "quiver": ["h_sniper_grow", "h_sniper_fate", "h_sniper_double"],
        "chain": ["h_sniper_grow", "h_sniper_fate", "h_sniper_double"],
    }
    for variant, add_ids in by_var.items():
        pool = h.setdefault("rewards_by_variant", {}).setdefault(variant, [])
        pool[:] = list(dict.fromkeys(pool + add_ids))

    czn = json.load(open(P_CZN, encoding="utf-8"))
    for cid, source in (("h_sniper_double", ("Luke", "Seize the Opportunity")),
                        ("h_sniper_allin", ("Lucas", "Last-Ditch Assault"))):
        for row in czn["cards"]:
            if row["variant"] == "Base" and row["character"] == source[0] and row["name"] == source[1]:
                row["adapted_as"] = list(dict.fromkeys(row.get("adapted_as", []) + [cid]))
                break

    json.dump(data, open(P_CARDS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(heroes, open(P_HEROES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(czn, open(P_CZN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Карты снайпера:", ", ".join(ids))


if __name__ == "__main__":
    main()
