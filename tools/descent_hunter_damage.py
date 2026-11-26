"""Охотница: карты усиления урона и ослабления врагов.

Два пути усиления, как в CZN:
1) усилить свои удары (сила, дальний бонус, фокус, повторы);
2) ослабить цель (уязвимость, метка, кровотечение) и затем ударить.

Запускать после tools/descent_hunter_more.py.
"""
import copy
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "deck")
P_CARDS = os.path.join(D, "cards.json")
P_HEROES = os.path.join(D, "heroes.json")
SEQ = 0


def op(name, n=None, **kw):
    o = {"op": name}
    if n is not None:
        o["n"] = n
    o.update(kw)
    return o


def D(n, **kw):
    return op("damage", n, **kw)


def B(n):
    return op("block", n)


def shot(rng, *do, **kw):
    return dict({"target": "enemy", "range": rng, "los": True, "ranged": True, "do": list(do)}, **kw)


def me(*do, **kw):
    return dict({"target": "self", "do": list(do)}, **kw)


def V(label, main=None, name=None, **top):
    v = {"label": label}
    if name:
        v["name"] = name
    if main is not None:
        v["main"] = main
    v.update(top)
    return v


def bump(x, frac=0.35):
    x = copy.deepcopy(x)

    def walk(o):
        if isinstance(o, dict):
            if o.get("op") in {"damage", "block", "draw", "mark", "bleed", "burn", "energy", "heal",
                               "vulnerable", "weak", "strength", "ranged_bonus", "push", "hunt"} \
                    and o.get("n") is not None:
                o["n"] = max(1, o["n"] + max(1, round(o["n"] * frac)))
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


def opts(main):
    return [
        V("Сильнее", bump(main)),
        V("С добором", add_op(main, op("draw", 1)), "Дыхание"),
        V("С защитой", add_op(main, B(3))),
        V("С меткой", add_op(main, op("mark", 1)), "Метка"),
        V("С энергией", add_op(main, op("energy", 1)), "Второе дыхание"),
    ]


def ill_from(cards, cid, dx, dy):
    global SEQ
    SEQ += 1
    i = SEQ
    src = list(cards[cid]["ill"])
    return [src[0], round(min(0.98, max(0.02, src[1] + dx + (i % 11) * 0.006)), 4),
            round(min(0.98, max(0.02, src[2] + dy + (i // 11) * 0.009)), 4), src[3]]


def add(cards, cid, src, name, main, tags, *, typ="attack", cost=1, rarity=2, alt=None):
    c = copy.deepcopy(cards[src])
    c.update({"name": name, "main": main, "type": typ, "cost": cost, "tags": list(tags),
              "category": "hero", "owner": "hunter", "rarity": rarity,
              "ill": ill_from(cards, src, 0.04, 0.02)})
    if alt is not None:
        c["alt"] = alt
    c.pop("levels", None)
    for f in ("chain", "echo", "keep"):
        c.pop(f, None)
    if "growth" in c:
        c["growth"][0]["options"] = opts(main)
    cards[cid] = c


def main():
    data = json.load(open(P_CARDS, encoding="utf-8"))
    cards = data["cards"]
    ids = []

    # Ослабление цели.
    add(cards, "h_dmg_expose", "h_shot", "Уязвимая точка",
        shot(6, D(4), op("vulnerable", 2)), ["Выстрел", "Клич"], cost=1, rarity=2)
    add(cards, "h_dmg_cripple", "h_shot", "Подрезать",
        shot(5, D(3), op("weak", 2), op("root", 1)), ["Выстрел", "Клич", "Ловушка"], cost=1, rarity=2)
    add(cards, "h_dmg_pack_mark", "h_mark_web", "Метка стаи",
        {"target": "area", "range": 6, "radius": 1, "do": [op("mark", 2), op("vulnerable", 1)],
         "vfx": "hunter_mark"},
        ["Метка", "Область", "Клич"], typ="skill", cost=1, rarity=2)
    add(cards, "h_dmg_black_volley", "h_volley", "Чёрный залп",
        {"target": "area", "range": 6, "radius": 1,
         "do": [D(4), op("vulnerable", 1), op("weak", 1)], "ranged": True, "vfx": "rain_of_arrows"},
        ["Выстрел", "Область", "Клич"], cost=2, rarity=3)
    add(cards, "h_dmg_rupture", "h_shot", "Разрывная стрела",
        shot(6, D(6), op("bleed", 3), op("vulnerable", 1)),
        ["Выстрел", "Кровь", "Клич"], cost=2, rarity=3)

    # Усиление своих ударов.
    add(cards, "h_dmg_predator", "h_hunt", "Хищный прицел",
        me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                  "do": [op("ranged_bonus", 1)]}),
        ["Выстрел", "Комбо"], typ="power", cost=2, rarity=3)
    add(cards, "h_dmg_trophy", "h_hunt", "Ярость трофея",
        me(power={"on": "kill", "do": [op("strength", 1)]}),
        ["Кровь", "Клич"], typ="power", cost=2, rarity=3)
    add(cards, "h_dmg_ritual", "h_hunt", "Кровавый ритуал",
        me(power={"on": "turn", "do": [op("strength", 1)]}),
        ["Кровь", "Клич"], typ="power", cost=2, rarity=4)
    add(cards, "h_dmg_execute", "h_deadeye", "Казнь",
        shot(6, D(12), **{"if": [{"when": {"k": "wounded"}, "mult": 2}]}),
        ["Выстрел", "Клич"], cost=2, rarity=4)

    added = ["h_dmg_expose", "h_dmg_cripple", "h_dmg_pack_mark", "h_dmg_black_volley",
             "h_dmg_rupture", "h_dmg_predator", "h_dmg_trophy", "h_dmg_ritual", "h_dmg_execute"]
    heroes = json.load(open(P_HEROES, encoding="utf-8"))
    h = heroes["heroes"]["hunter"]
    h["rewards"] = list(dict.fromkeys(h.get("rewards", []) + added))
    for variant in ("mark", "quiver", "range", "chain"):
        pool = h.setdefault("rewards_by_variant", {}).setdefault(variant, [])
        pool[:] = list(dict.fromkeys(pool + added))
    json.dump(data, open(P_CARDS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(heroes, open(P_HEROES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("карт усиления/ослабления:", len(added), "—", ", ".join(added))


if __name__ == "__main__":
    main()
