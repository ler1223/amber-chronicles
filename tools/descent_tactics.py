"""CZN-волна для «Спуска»: тактические теги, колоды Наёмника и Пиромантки.

Запускать после остальных генераторов:
    python tools/descent_epiphanies.py
    python tools/descent_survival.py
    python tools/descent_cards_czn.py
    python tools/descent_priest.py
    python tools/descent_builds.py
    python tools/descent_tactics.py

Что добавляет:
- Преследование: запас дополнительных выстрелов после одноцелевых атак с тегом [Преследование].
- Область: автоматический тег для area / aoe_adjacent / detonate.
- Сохранение и Изгнание: теги для Retain/Exhaust.
- Школу Наёмника «Натиск»: толчки дают Разгон, столкновения бьют сильнее.
- Школу Пиромантки «Пепел»: [Область] бьёт сильнее.
- Карты-мосты для Охотницы, Наёмника и Пиромантки.
"""
import copy
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "deck")
P_CARDS = os.path.join(D, "cards.json")
P_HEROES = os.path.join(D, "heroes.json")

SCALE = {"damage", "block", "draw", "mark", "bleed", "burn", "poison", "weak", "vulnerable", "ranged_bonus",
         "heal", "energy", "hunt", "push", "pull"}


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
    if "if_" in kw:
        kw["if"] = kw.pop("if_")
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
            if o.get("op") in SCALE and o.get("n") is not None:
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


def ill_from(cards, cid, dx=0.01, dy=0.02):
    src = list(cards[cid]["ill"])
    return [src[0], round(min(0.98, max(0.02, src[1] + dx)), 3),
            round(min(0.98, max(0.02, src[2] + dy)), 3), src[3]]


def add_new(cards, cid, src, name, main, tags, *, alt=None, dx=0.03, dy=0.01, art=None, options=None):
    c = copy.deepcopy(cards[src])
    c["name"] = name
    c["main"] = main
    c["tags"] = list(tags)
    if alt is not None:
        c["alt"] = alt
    if art:
        c["art"] = art
    c["ill"] = ill_from(cards, src, dx, dy)
    c.pop("levels", None)                                       # новые карты этой волны — без уровней жара
    for field in ("chain", "echo", "keep"):                      # не наследуем автосвойства исходной карты
        c.pop(field, None)
    if options:
        c["growth"][0]["options"] = options
    cards[cid] = c
    return c


def main():
    data = json.load(open(P_CARDS, encoding="utf-8"))
    cards = data["cards"]
    out = {}

    # ---------- Охотница: Преследование, загон и область ----------
    add_new(cards, "h_beat", "h_shot", "Загон",
            shot(6, D(4), op("push", 1), op("mark", 1)),
            ["Выстрел", "Преследование", "Толчок", "Метка"], dx=0.07, dy=0.02,
            options=[
                V("Сильнее", shot(6, D(6), op("push", 1), op("mark", 1))),
                V("С добором", shot(6, D(4), op("push", 1), op("mark", 1), op("draw", 1)), "Загон и дыхание"),
                V("С меткой", shot(6, D(4), op("push", 2), op("mark", 2)), "Загон и метка"),
                V("У стены", shot(6, D(4), op("push", 1), op("mark", 1),
                                 if_=[{"when": {"k": "wall"}, "plus": 4}]), "Загон у стены"),
                V("С разбега", shot(6, D(5), op("push", 1), op("mark", 1),
                                    if_=[{"when": {"k": "run", "n": 2}, "do": [op("draw", 1)]}]), "Загон с ходу"),
            ])

    add_new(cards, "h_stalk", "h_trail", "Преследование",
            {"target": "cell_step", "step": 2, "do": [op("block", 3), op("hunt", 2), op("draw", 1)]},
            ["Шаг", "Преследование"], dx=0.04, dy=0.04,
            options=[
                V("Дальше", {"target": "cell_step", "step": 3,
                              "do": [op("block", 3), op("hunt", 2), op("draw", 1)]}),
                V("Больше преследования", {"target": "cell_step", "step": 2,
                                     "do": [op("block", 3), op("hunt", 3), op("draw", 1)]}, "Преследование"),
                V("С защитой", {"target": "cell_step", "step": 2,
                                 "do": [op("block", 6), op("hunt", 2), op("draw", 1)]}, "Преследование и щит"),
                V("С меткой", {"target": "cell_step", "step": 2,
                                "do": [op("block", 3), op("hunt", 2), op("draw", 1), op("mark", 1)]}, "Преследование и метка"),
                V("С разбега", {"target": "cell_step", "step": 2,
                                 "do": [op("block", 3), op("hunt", 2), op("draw", 1)],
                                 "if": [{"when": {"k": "run", "n": 2}, "do": [op("energy", 1)]}]}, "Преследование с ходу"),
            ])

    add_new(cards, "h_mark_hunt", "h_marking", "Гон по метке",
            shot(6, D(5, per={"what": "mark", "k": 2})),
            ["Выстрел", "Преследование", "Метка"], dx=0.08, dy=0.03,
            options=[
                V("Сильнее", shot(6, D(7, per={"what": "mark", "k": 2}))),
                V("Глубже", shot(7, D(5, per={"what": "mark", "k": 3})), "Гон по метке"),
                V("С добором", shot(6, D(5, per={"what": "mark", "k": 2}), op("draw", 1)), "Гон и дыхание"),
                V("С уязвимостью", shot(6, D(5, per={"what": "mark", "k": 2}), op("vulnerable", 1)), "Гон и брешь"),
                V("Издалека", shot(7, D(5, per={"what": "mark", "k": 2}),
                                    if_=[{"when": {"k": "far", "n": 5}, "plus": 3}]), "Далёкий гон"),
            ])

    add_new(cards, "h_area_hunt", "h_volley", "Веерный обстрел",
            {"target": "area", "range": 5, "radius": 1,
             "do": [op("damage", 4), op("mark", 1)], "ranged": True, "vfx": "rain_of_arrows"},
            ["Выстрел", "Область", "Метка"], dx=0.09, dy=0.04,
            options=[
                V("Сильнее", {"target": "area", "range": 5, "radius": 1,
                               "do": [op("damage", 6), op("mark", 1)], "ranged": True, "vfx": "rain_of_arrows"}),
                V("Шире", {"target": "area", "range": 5, "radius": 2,
                            "do": [op("damage", 4), op("mark", 1)], "ranged": True, "vfx": "rain_of_arrows"}),
                V("С добором", {"target": "area", "range": 5, "radius": 1,
                                 "do": [op("damage", 4), op("mark", 1), op("draw", 1)],
                                 "ranged": True, "vfx": "rain_of_arrows"}, "Веер и дыхание"),
                V("С уязвимостью", {"target": "area", "range": 5, "radius": 1,
                                     "do": [op("damage", 4), op("mark", 1), op("vulnerable", 1)],
                                     "ranged": True, "vfx": "rain_of_arrows"}, "Веер и брешь"),
                V("С меткой", {"target": "area", "range": 5, "radius": 1,
                                "do": [op("damage", 4), op("mark", 2)], "ranged": True, "vfx": "rain_of_arrows"}),
            ])

    add_new(cards, "h_hunt_final", "h_shot", "Завершение гона",
            shot(6, D(6, per={"what": "hunt", "k": 2})),
            ["Выстрел", "Преследование", "Комбо"], dx=0.11, dy=0.05,
            options=[
                V("Сильнее", shot(6, D(9, per={"what": "hunt", "k": 2}))),
                V("Глубже", shot(7, D(6, per={"what": "hunt", "k": 3})), "Завершение гона"),
                V("С добором", shot(6, D(6, per={"what": "hunt", "k": 2}), op("draw", 1)), "Гон и дыхание"),
                V("С меткой", shot(6, D(6, per={"what": "hunt", "k": 2}), op("mark", 2)), "Гон и метка"),
                V("По раненому", shot(6, D(6, per={"what": "hunt", "k": 2}),
                                       if_=[{"when": {"k": "wounded"}, "plus": 3}]), "Добить загнанного"),
            ])
    out.update({k: k for k in ("h_beat", "h_stalk", "h_mark_hunt", "h_area_hunt", "h_hunt_final")})

    # Старый «Охотничий азарт» становится источником преследования.
    hh = cards["h_hunt"]
    hh["tags"] = [t for t in hh.get("tags", []) if t not in ("Травля", "Преследование")] + ["Преследование"]
    pw = hh["main"].setdefault("power", {})
    pw["do"] = [o for o in pw.get("do", []) if o.get("op") != "hunt"] + [op("hunt", 1)]
    out["h_hunt"] = "h_hunt"

    # ---------- Наёмник: сдвиг, область и столкновения ----------
    add_new(cards, "m_bulldoze", "charge", "Снести",
            {"target": "reach", "reach": 2, "do": [op("damage", 6), op("push", 1)],
             "vfx": "charge", "if": [{"when": {"k": "wall"}, "plus": 3}]},
            ["Удар", "Толчок", "Шаг"], dx=0.05, dy=0.03,
            options=[
                V("Сильнее", {"target": "reach", "reach": 2, "do": [op("damage", 9), op("push", 1)],
                               "vfx": "charge", "if": [{"when": {"k": "wall"}, "plus": 3}]}),
                V("Дальше", {"target": "reach", "reach": 3, "do": [op("damage", 6), op("push", 2)],
                              "vfx": "charge", "if": [{"when": {"k": "wall"}, "plus": 3}]}, "Снести с пути"),
                V("С разгоном", {"target": "reach", "reach": 2, "do": [op("damage", 5, mom_k=1), op("push", 1)],
                                  "vfx": "charge", "if": [{"when": {"k": "wall"}, "plus": 3}]}, "Снести с разгона"),
                V("С щитом", {"target": "reach", "reach": 2, "do": [op("block", 4), op("damage", 6), op("push", 1)],
                               "vfx": "charge", "if": [{"when": {"k": "wall"}, "plus": 3}]}, "Снести и устоять"),
                V("С уязвимостью", {"target": "reach", "reach": 2, "do": [op("damage", 6), op("push", 1), op("vulnerable", 1)],
                                     "vfx": "charge", "if": [{"when": {"k": "wall"}, "plus": 3}]}, "Снести и пробить"),
            ])

    add_new(cards, "m_ring", "sweep", "Круговая стойка",
            {"target": "self", "do": [op("aoe_adjacent", do=[op("damage", 5), op("push", 1)])],
             "vfx": "whirlwind", "if": [{"when": {"k": "surrounded"}, "plus": 3}]},
            ["Удар", "Толчок", "Область"], dx=0.07, dy=0.04,
            options=[
                V("Сильнее", {"target": "self", "do": [op("aoe_adjacent", do=[op("damage", 7), op("push", 1)])],
                               "vfx": "whirlwind", "if": [{"when": {"k": "surrounded"}, "plus": 3}]}),
                V("Шире", {"target": "self", "do": [op("aoe_adjacent", do=[op("damage", 5), op("push", 2)])],
                            "vfx": "whirlwind", "if": [{"when": {"k": "surrounded"}, "plus": 3}]}, "Круговая стойка"),
                V("С щитом", {"target": "self", "do": [op("block", 5), op("aoe_adjacent", do=[op("damage", 5), op("push", 1)])],
                               "vfx": "whirlwind", "if": [{"when": {"k": "surrounded"}, "plus": 3}]}, "Стойка и щит"),
                V("С уязвимостью", {"target": "self", "do": [op("aoe_adjacent", do=[op("damage", 5), op("push", 1), op("vulnerable", 1)])],
                                     "vfx": "whirlwind", "if": [{"when": {"k": "surrounded"}, "plus": 3}]}, "Стойка и брешь"),
                V("С разгоном", {"target": "self", "do": [op("aoe_adjacent", do=[op("damage", 4), op("push", 1)])],
                                  "vfx": "whirlwind", "if": [{"when": {"k": "surrounded"}, "plus": 3}],
                                  "plus": 0}, "Стойка с разгоном"),
            ])

    add_new(cards, "m_grapple", "hook", "Зацеп",
            {"target": "enemy", "range": 4, "los": True,
             "do": [op("pull", 2), op("damage", 4), op("vulnerable", 1)], "vfx": "hook"},
            ["Удар", "Толчок", "Клич"], dx=0.08, dy=0.05,
            options=[
                V("Сильнее", {"target": "enemy", "range": 4, "los": True,
                               "do": [op("pull", 2), op("damage", 7), op("vulnerable", 1)], "vfx": "hook"}),
                V("Ближе", {"target": "enemy", "range": 5, "los": True,
                              "do": [op("pull", 3), op("damage", 4), op("vulnerable", 1)], "vfx": "hook"}),
                V("С меткой", {"target": "enemy", "range": 4, "los": True,
                                "do": [op("pull", 2), op("damage", 4), op("vulnerable", 1), op("mark", 1)], "vfx": "hook"}),
                V("С щитом", {"target": "enemy", "range": 4, "los": True,
                               "do": [op("block", 4), op("pull", 2), op("damage", 4), op("vulnerable", 1)], "vfx": "hook"}),
                V("С разгоном", {"target": "enemy", "range": 4, "los": True,
                                  "do": [op("pull", 2), op("damage", 4, mom_k=1), op("vulnerable", 1)], "vfx": "hook"}),
            ])

    add_new(cards, "m_break", "charge", "Прорыв строя",
            {"target": "reach", "reach": 3, "do": [op("damage", 8), op("push", 2)],
             "vfx": "charge", "if": [{"when": {"k": "momentum", "n": 3}, "do": [op("stun")]}]},
            ["Удар", "Толчок", "Шаг"], dx=0.10, dy=0.06,
            options=[
                V("Сильнее", {"target": "reach", "reach": 3, "do": [op("damage", 11), op("push", 2)],
                               "vfx": "charge", "if": [{"when": {"k": "momentum", "n": 3}, "do": [op("stun")]}]}),
                V("Дальше", {"target": "reach", "reach": 4, "do": [op("damage", 8), op("push", 3)],
                              "vfx": "charge", "if": [{"when": {"k": "momentum", "n": 3}, "do": [op("stun")]}]}),
                V("С щитом", {"target": "reach", "reach": 3, "do": [op("block", 6), op("damage", 8), op("push", 2)],
                               "vfx": "charge", "if": [{"when": {"k": "momentum", "n": 3}, "do": [op("stun")]}]}),
                V("С уязвимостью", {"target": "reach", "reach": 3, "do": [op("damage", 8), op("push", 2), op("vulnerable", 2)],
                                     "vfx": "charge", "if": [{"when": {"k": "momentum", "n": 3}, "do": [op("stun")]}]}),
                V("С разгоном", {"target": "reach", "reach": 3, "do": [op("damage", 7, mom_k=2), op("push", 2)],
                                  "vfx": "charge", "if": [{"when": {"k": "momentum", "n": 3}, "do": [op("stun")]}]}),
            ])

    add_new(cards, "m_quake", "h_volley", "Землетряс",
            {"target": "area", "range": 4, "radius": 1,
             "do": [op("damage", 5), op("push", 1)], "vfx": "quake"},
            ["Удар", "Толчок", "Область"], art="fx_fire_wall", dx=0.12, dy=0.07,
            options=[
                V("Сильнее", {"target": "area", "range": 4, "radius": 1,
                               "do": [op("damage", 8), op("push", 1)], "vfx": "quake"}),
                V("Шире", {"target": "area", "range": 4, "radius": 2,
                            "do": [op("damage", 5), op("push", 1)], "vfx": "quake"}),
                V("С щитом", {"target": "area", "range": 4, "radius": 1,
                               "do": [op("block", 5), op("damage", 5), op("push", 1)], "vfx": "quake"}),
                V("С уязвимостью", {"target": "area", "range": 4, "radius": 1,
                                     "do": [op("damage", 5), op("push", 1), op("vulnerable", 1)], "vfx": "quake"}),
                V("С разгоном", {"target": "area", "range": 4, "radius": 1,
                                  "do": [op("damage", 4, mom_k=1), op("push", 1)], "vfx": "quake"}),
            ])
    out.update({k: k for k in ("m_bulldoze", "m_ring", "m_grapple", "m_break", "m_quake")})

    # ---------- герои: школы Наёмника и Пиромантки ----------
    heroes = json.load(open(P_HEROES, encoding="utf-8"))
    hh = heroes["heroes"]

    merc = hh["merc"]
    merc["passives"] = {
        "press": {"name": "Натиск",
                  "desc": "Толчок даёт +1 Разгон; столкновения бьют сильнее на 2. Колода: сдвиг и область."}
    }
    merc["starter_by_variant"] = {
        "press": ["strike", "strike", "strike", "defend", "defend", "lunge_rush", "lunge_rush",
                  "shield_ram", "shield_ram", "sweep", "m_bulldoze", "m_ring"],
    }
    merc["rewards_by_variant"] = {
        "press": ["sweep", "wall_smash", "charge", "hook", "m_ram", "m_wallbash", "m_stomp",
                  "m_blade_storm", "m_runner", "m_crush", "m_bulldoze", "m_ring", "m_grapple",
                  "m_break", "m_quake"],
    }
    merc["reward_guarantee"] = {"press": ["m_bulldoze", "m_ring", "m_quake"]}

    pyro = hh["pyro"]
    pyro["passives"] = {
        "ash": {"name": "Пепел",
                "desc": "[Область] наносит +2 урона. Колода: огонь, зоны и сдвиг врагов."}
    }
    pyro["starter_by_variant"] = {
        "ash": ["p_bolt", "p_bolt", "p_bolt", "p_ward", "p_ward", "p_stride", "p_stride",
                "p_fireball", "p_grenade", "p_oil", "p_ashstep"],
    }
    pyro["rewards_by_variant"] = {
        "ash": ["p_grenade", "p_oil", "p_fireball", "p_fire_rain", "p_geyser", "p_meteor",
                "p_sun", "p_keg", "p_smoke", "p_barrier", "p_lance", "p_chain", "p_stride"],
    }
    pyro["reward_guarantee"] = {"ash": ["p_grenade", "p_oil", "p_fireball"]}

    for hero in (merc, pyro):
        for ids in hero["rewards_by_variant"].values():
            hero["rewards"] = list(dict.fromkeys(hero.get("rewards", []) + ids))
    # Новые карты Охотницы — в школу mark и общий пул.
    hunter = hh["hunter"]
    hunter["rewards_by_variant"]["mark"] = list(dict.fromkeys(
        hunter["rewards_by_variant"].get("mark", []) +
        ["h_beat", "h_stalk", "h_mark_hunt", "h_area_hunt", "h_hunt_final", "h_hunt"]))
    hunter["starter_by_variant"]["mark"] = ["h_shot", "h_shot", "h_marking", "h_marking", "h_mark_burst",
                                            "h_beat", "h_stalk", "h_dodge", "h_dodge", "h_trail", "h_net"]
    hunter["reward_guarantee"] = dict(hunter.get("reward_guarantee") or {}, mark=["h_beat", "h_stalk", "h_mark_hunt"])
    hunter["rewards"] = list(dict.fromkeys(hunter.get("rewards", []) + [
        "h_beat", "h_stalk", "h_mark_hunt", "h_area_hunt", "h_hunt_final"]))

    # New cards — в общий пул героев, чтобы их можно было встретить и в свободной награде.
    hh["merc"]["rewards"] = list(dict.fromkeys(hh["merc"]["rewards"] +
                                               ["m_bulldoze", "m_ring", "m_grapple", "m_break", "m_quake"]))
    hh["pyro"]["rewards"] = list(dict.fromkeys(hh["pyro"]["rewards"]))

    with open(P_CARDS, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    with open(P_HEROES, "w", encoding="utf-8") as f:
        json.dump(heroes, f, ensure_ascii=False, indent=1)
    print("тактических карт:", len(out), "—", ", ".join(out))


if __name__ == "__main__":
    main()
