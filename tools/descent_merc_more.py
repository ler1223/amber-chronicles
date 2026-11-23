"""Наёмник: новые карты «Осадная стойка» и «Столкновение».

Использует существующие теги (Удар, Защита, Толчок, Кровь, Комбо) и добавляет
условие not_walked — «не двигался в этот ход». Запускать после генераторов
карт и перед descent_tiers.py.
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


def damage(n):
    return op("damage", n)


def block(n):
    return op("block", n)


def alt_step(n=1):
    return {"target": "cell_step", "step": n, "do": []}


def alt_block(n=2):
    return {"target": "self", "do": [block(n)]}


def alt_push(n=1):
    return {"target": "enemy", "range": 1, "do": [op("push", n)]}


def bump(x, fac=0.35):
    x = copy.deepcopy(x)

    def walk(o):
        if isinstance(o, dict):
            if o.get("op") in ("damage", "block", "bleed", "push", "pull", "root", "vulnerable", "counter",
                               "momentum", "empower") and o.get("n") is not None:
                o["n"] = max(1, o["n"] + max(1, round(o["n"] * fac)))
            if "plus" in o:
                o["plus"] += max(1, round(o["plus"] * fac))
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
        {"label": "С защитой", "main": add_op(main, block(3))},
        {"label": "С толчком", "name": "Сдвиг", "main": add_op(main, op("push", 1))},
        {"label": "С разгоном", "name": "Разгон", "main": add_op(main, op("momentum", 1))},
    ]


def ill_from(cards, cid, dx, dy):
    global SEQ
    SEQ += 1
    i = SEQ
    src = list(cards[cid]["ill"])
    return [src[0], round(min(0.98, max(0.02, src[1] + dx + (i % 9) * 0.007)), 4),
            round(min(0.98, max(0.02, src[2] + dy + (i // 9) * 0.009)), 4), src[3]]


def add(cards, cid, src, name, main, tags, *, typ, cost, rarity, alt):
    c = copy.deepcopy(cards[src])
    for field in ("levels", "react", "echo", "chain", "keep", "temper", "exhaust", "trap"):
        c.pop(field, None)
    c.update({
        "name": name, "main": main, "alt": alt, "type": typ, "cost": cost,
        "tags": list(tags), "category": "hero", "owner": "merc", "rarity": rarity,
        "ill": ill_from(cards, src, 0.05, 0.02),
    })
    if "growth" in c:
        c["growth"][0]["options"] = options(main)
    cards[cid] = c


def main():
    data = json.load(open(P_CARDS, encoding="utf-8"))
    cards = data["cards"]
    ids = []

    # --- Осадная стойка: ветка «не двигался» ---
    add(cards, "m_stand", "m_bastion", "Осадная стойка",
        {"target": "self", "do": [block(6)],
         "if": [{"when": {"k": "not_walked"}, "do": [op("empower", 5, tag="Удар")]}]},
        ["Защита", "Комбо"], typ="skill", cost=1, rarity=2, alt=alt_block(2))
    ids.append("m_stand")

    add(cards, "m_hammer", "m_crush", "Молот судьбы",
        {"target": "enemy", "range": 1, "do": [damage(8)],
         "if": [{"when": {"k": "not_walked"}, "plus": 4, "do": [op("stun")]}]},
        ["Удар"], typ="attack", cost=2, rarity=3, alt=alt_step(1))
    ids.append("m_hammer")

    add(cards, "m_receive", "m_duelist", "Принять удар",
        {"target": "self", "do": [block(5), op("counter", 2)],
         "if": [{"when": {"k": "not_walked"}, "do": [block(4)]}]},
        ["Защита", "Шипы"], typ="skill", cost=1, rarity=2, alt=alt_block(2))
    ids.append("m_receive")

    # --- Столкновение: толчок как урон ---
    add(cards, "m_kegel", "m_hit_back", "Кегельбан",
        {"target": "enemy", "range": 1, "do": [damage(5), op("collide_x2"), op("push", 2)]},
        ["Удар", "Толчок"], typ="attack", cost=2, rarity=3, alt=alt_push(1))
    ids.append("m_kegel")

    add(cards, "m_pin", "m_grapple", "Прижать",
        {"target": "enemy", "range": 1,
         "do": [damage(4), op("push", 2), op("root", 1), op("vulnerable", 1)]},
        ["Удар", "Толчок", "Клич"], typ="attack", cost=2, rarity=2, alt=alt_step(1))
    ids.append("m_pin")

    # --- Кровь + движение ---
    add(cards, "m_blood_rush", "m_break", "Кровавый натиск",
        {"target": "reach", "reach": 3, "do": [damage(4), op("bleed", 2)]},
        ["Удар", "Кровь", "Шаг"], typ="attack", cost=2, rarity=2, alt=alt_step(1))
    ids.append("m_blood_rush")

    heroes = json.load(open(P_HEROES, encoding="utf-8"))
    h = heroes["heroes"]["merc"]
    h["rewards"] = list(dict.fromkeys(h.get("rewards", []) + ids))
    pool = h.setdefault("rewards_by_variant", {}).setdefault("press", [])
    pool[:] = list(dict.fromkeys(pool + ids))

    json.dump(data, open(P_CARDS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(heroes, open(P_HEROES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("карт Наёмника:", len(ids), "—", ", ".join(ids))


if __name__ == "__main__":
    main()
