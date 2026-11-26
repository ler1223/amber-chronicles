"""Ещё карты Наёмника и Охотницы: стойка, кровь, метки и яд.

Наёмник получает продолжение ветки «без шага» и обмена кровью.
Охотница — точный выстрел с колена, скрытный шаг и метки с ядом/кровью.
Запускать после tools/descent_merc_more.py.
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


def D(n):
    return op("damage", n)


def B(n):
    return op("block", n)


def step(n=1):
    return {"target": "cell_step", "step": n, "do": []}


def self_block(n=2):
    return {"target": "self", "do": [B(n)]}


def shot(rng, *do):
    return {"target": "enemy", "range": rng, "los": True, "ranged": True, "do": list(do)}


def bump(x, f=0.35):
    x = copy.deepcopy(x)

    def walk(o):
        if isinstance(o, dict):
            if o.get("op") in {"damage", "block", "draw", "bleed", "poison", "mark", "vulnerable", "weak",
                               "counter", "thorns", "push", "pull", "root", "empower"} and o.get("n") is not None:
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
        {"label": "С защитой", "main": add_op(main, B(3))},
        {"label": "С меткой", "name": "Метка", "main": add_op(main, op("mark", 1))},
        {"label": "С энергией", "name": "Второе дыхание", "main": add_op(main, op("energy", 1))},
    ]


def ill_from(cards, cid, dx, dy):
    global SEQ
    SEQ += 1
    i = SEQ
    src = list(cards[cid]["ill"])
    return [src[0], round(min(0.98, max(0.02, src[1] + dx + (i % 7) * 0.008)), 4),
            round(min(0.98, max(0.02, src[2] + dy + (i // 7) * 0.01)), 4), src[3]]


def add(cards, cid, src, name, main, tags, *, typ, cost, rarity, alt, owner):
    c = copy.deepcopy(cards[src])
    for field in ("levels", "react", "echo", "chain", "keep", "temper", "exhaust", "trap", "source"):
        c.pop(field, None)
    c.update({"name": name, "main": main, "alt": alt, "type": typ, "cost": cost, "tags": list(tags),
              "category": "hero", "owner": owner, "rarity": rarity,
              "ill": ill_from(cards, src, 0.04, 0.02)})
    if "growth" in c:
        c["growth"][0]["options"] = options(main)
    cards[cid] = c


def main():
    data = json.load(open(P_CARDS, encoding="utf-8"))
    cards = data["cards"]
    heroes = json.load(open(P_HEROES, encoding="utf-8"))
    merc_ids, hunter_ids = [], []

    # --- Наёмник ---
    add(cards, "m_brace", "m_receive", "Упереться",
        {"target": "self", "do": [B(5)],
         "if": [{"when": {"k": "not_walked"}, "do": [B(4), op("counter", 2)]}]},
        ["Защита", "Шипы"], typ="skill", cost=1, rarity=2, alt=self_block(), owner="merc")
    merc_ids.append("m_brace")

    add(cards, "m_rampart", "m_unbreak", "Осадный вал",
        {"target": "self", "do": [B(9)],
         "if": [{"when": {"k": "not_walked"}, "do": [B(4), op("thorns", 4), op("fort")]}]},
        ["Защита", "Шипы"], typ="skill", cost=2, rarity=3, alt=self_block(3), owner="merc")
    merc_ids.append("m_rampart")

    add(cards, "m_battle_plan", "m_rally", "План боя",
        {"target": "self", "do": [op("draw", 1), op("empower", 4, tag="Толчок")]},
        ["Комбо", "Толчок"], typ="skill", cost=0, rarity=1, alt=step(), owner="merc")
    merc_ids.append("m_battle_plan")

    add(cards, "m_blood_exchange", "m_rend", "Кровавый обмен",
        {"target": "enemy", "range": 1, "do": [D(4), op("bleed", 2), op("draw", 1)]},
        ["Удар", "Кровь", "Комбо"], typ="attack", cost=1, rarity=2, alt=step(), owner="merc")
    merc_ids.append("m_blood_exchange")

    # --- Охотница ---
    add(cards, "h_kneel", "h_snipe", "Выстрел с колена",
        {"target": "enemy", "range": 6, "los": True, "ranged": True, "do": [D(8)],
         "if": [{"when": {"k": "not_walked"}, "plus": 4, "do": [op("mark", 1)]}]},
        ["Выстрел", "Метка"], typ="attack", cost=2, rarity=3, alt=step(), owner="hunter")
    hunter_ids.append("h_kneel")

    add(cards, "h_shadow_step", "h_evade", "Тень охотника",
        {"target": "cell_step", "step": 2, "do": [B(4), op("draw", 1)]},
        ["Шаг", "Комбо", "Защита"], typ="skill", cost=1, rarity=2, alt=step(), owner="hunter")
    hunter_ids.append("h_shadow_step")

    add(cards, "h_venom_tip", "h_poison", "Ядовитый наконечник",
        shot(6, D(3), op("poison", 3), op("draw", 1)),
        ["Выстрел", "Яд", "Комбо"], typ="attack", cost=1, rarity=2, alt=step(), owner="hunter")
    hunter_ids.append("h_venom_tip")

    add(cards, "h_blood_moon", "h_blood_rite", "Кровавая луна",
        {"target": "self", "do": [],
         "power": {"on": "play", "tag": "Метка", "aim": "nearest", "do": [op("bleed", 2)]}},
        ["Метка", "Кровь"], typ="power", cost=2, rarity=3, alt=step(), owner="hunter")
    hunter_ids.append("h_blood_moon")

    add(cards, "h_beacon", "h_czn_high_scope", "Стрела-маяк",
        shot(6, D(4), op("mark", 2), op("draw", 1)),
        ["Выстрел", "Метка", "Комбо"], typ="attack", cost=1, rarity=2, alt=step(), owner="hunter")
    hunter_ids.append("h_beacon")

    mh = heroes["heroes"]["merc"]
    mh["rewards"] = list(dict.fromkeys(mh.get("rewards", []) + merc_ids))
    mh.setdefault("rewards_by_variant", {}).setdefault("press", [])
    mh["rewards_by_variant"]["press"] = list(dict.fromkeys(mh["rewards_by_variant"]["press"] + merc_ids))

    hh = heroes["heroes"]["hunter"]
    hh["rewards"] = list(dict.fromkeys(hh.get("rewards", []) + hunter_ids))
    by_var = {
        "range": ["h_kneel", "h_shadow_step"],
        "mark": ["h_kneel", "h_blood_moon", "h_beacon"],
        "quiver": ["h_venom_tip", "h_beacon"],
        "chain": ["h_shadow_step", "h_beacon"],
    }
    for variant, ids in by_var.items():
        pool = hh.setdefault("rewards_by_variant", {}).setdefault(variant, [])
        pool[:] = list(dict.fromkeys(pool + ids))

    json.dump(data, open(P_CARDS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(heroes, open(P_HEROES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Наёмник:", ", ".join(merc_ids))
    print("Охотница:", ", ".join(hunter_ids))


if __name__ == "__main__":
    main()
