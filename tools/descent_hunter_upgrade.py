"""CZN-улучшение Охотницы: постоянный колчан, создающий авто-стрелу.

Источник — Lucas «Extended Magazine»: в начале хода создаёт усиленный снаряд.
В «Спуске» это Стрела охоты: её нельзя играть вручную, она сама бьёт в конце хода.
"""
import copy
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "deck")
P_CARDS = os.path.join(D, "cards.json")
P_HEROES = os.path.join(D, "heroes.json")
P_CZN = os.path.join(ROOT, "data", "czn", "cards.json")


def op(name, n=None, **kw):
    o = {"op": name}
    if n is not None:
        o["n"] = n
    o.update(kw)
    return o


def add(cards, cid, src, name, main, tags, *, typ, cost, rarity, alt, **extra):
    c = copy.deepcopy(cards[src])
    for field in ("levels", "react", "echo", "chain", "keep", "temper", "exhaust", "trap",
                  "auto_end", "source", "token"):
        c.pop(field, None)
    c.update({"name": name, "main": main, "alt": alt, "type": typ, "cost": cost,
              "tags": list(tags), "category": "hero", "owner": "hunter", "rarity": rarity,
              "ill": [cards[src]["ill"][0], min(0.95, cards[src]["ill"][1] + 0.04),
                      min(0.95, cards[src]["ill"][2] + 0.02), cards[src]["ill"][3]]})
    c.update(extra)
    cards[cid] = c


def main():
    data = json.load(open(P_CARDS, encoding="utf-8"))
    cards = data["cards"]

    # Усиленная стрела: 5 урона вместо 3 у обычной; ручное применение запрещено.
    arrow = copy.deepcopy(cards["arrow"])
    arrow.update({
        "name": "Стрела охоты",
        "auto_end": True,
        "tags": ["Выстрел"],
        "main": {"target": "enemy", "range": 6, "los": True, "ranged": True,
                 "do": [op("damage", 5)]},
    })
    cards["arrow_auto"] = arrow

    noalt = {"target": "none", "do": []}
    add(cards, "h_upgrade_quiver", "h_master_quiver", "Улучшение: колчан охоты",
        {"target": "self", "do": [],
         "power": {"on": "turn", "do": [op("add_card", 1, card="arrow_auto",
                                           cname="Стрела охоты", force=True)]}},
        ["Создание", "Выстрел"], typ="power", cost=2, rarity=4, alt=copy.deepcopy(noalt))
    cards["h_upgrade_quiver"]["source"] = {
        "game": "CZN", "character": "Lucas", "name": "Extended Magazine",
        "effect": "At the start of the turn, create 1 Launcher Bullet",
    }
    cards["h_upgrade_quiver"]["growth"] = [{"uses": 3, "options": [
        {"label": "Больше стрел", "main": {"target": "self", "do": [],
                                           "power": {"on": "turn", "do": [op("add_card", 2, card="arrow_auto",
                                                                              cname="Стрела охоты", force=True)]}}},
        {"label": "Тугая тетива", "name": "Тугая тетива",
         "main": {"target": "self", "do": [op("ranged_bonus", 2)],
                  "power": {"on": "turn", "do": [op("add_card", 1, card="arrow_auto",
                                                     cname="Стрела охоты", force=True)]}}},
        {"label": "С добором", "name": "Взгляд вперёд",
         "main": {"target": "self", "do": [op("draw", 1)],
                  "power": {"on": "turn", "do": [op("add_card", 1, card="arrow_auto",
                                                     cname="Стрела охоты", force=True)]}}},
        {"label": "С защитой", "name": "Стрела в укрытии",
         "main": {"target": "self", "do": [op("block", 4)],
                  "power": {"on": "turn", "do": [op("add_card", 1, card="arrow_auto",
                                                     cname="Стрела охоты", force=True)]}}},
        {"label": "С меткой", "name": "Метка на тетиве",
         "main": {"target": "self", "do": [op("mark", 1)],
                  "power": {"on": "turn", "do": [op("add_card", 1, card="arrow_auto",
                                                     cname="Стрела охоты", force=True)]}}},
    ]}]

    heroes = json.load(open(P_HEROES, encoding="utf-8"))
    h = heroes["heroes"]["hunter"]
    h["rewards"] = list(dict.fromkeys(h.get("rewards", []) + ["h_upgrade_quiver"]))
    for variant in ("range", "mark", "quiver", "chain"):
        pool = h.setdefault("rewards_by_variant", {}).setdefault(variant, [])
        pool[:] = list(dict.fromkeys(pool + ["h_upgrade_quiver"]))

    # Отметить источник в полном каталоге CZN.
    czn = json.load(open(P_CZN, encoding="utf-8"))
    for row in czn["cards"]:
        if row["variant"] == "Base" and row["character"] == "Lucas" and row["name"] == "Extended Magazine":
            row["adapted_as"] = list(dict.fromkeys(row.get("adapted_as", []) + ["h_upgrade_quiver"]))
            break

    json.dump(data, open(P_CARDS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(heroes, open(P_HEROES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(czn, open(P_CZN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Добавлено: h_upgrade_quiver + arrow_auto")


if __name__ == "__main__":
    main()
