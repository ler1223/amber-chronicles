"""Новые колоды «Спуска»: три школы Охотницы.

Патчит готовые data/deck/cards.json и heroes.json — запускать после генераторов карт:
    python tools/descent_epiphanies.py
    python tools/descent_survival.py
    python tools/descent_cards_czn.py
    python tools/descent_priest.py
    python tools/descent_builds.py

Школы Охотницы:
- range  — дальность, прицел, «Издалека»;
- mark   — метка, добыча, «за каждую метку»;
- quiver — стрелы, повторные выстрелы, серии.
"""
import copy
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "deck")
P_CARDS = os.path.join(D, "cards.json")
P_HEROES = os.path.join(D, "heroes.json")

SCALE = {"damage", "block", "draw", "mark", "bleed", "burn", "poison", "weak", "vulnerable", "ranged_bonus",
         "heal", "energy"}


def op(name, n=None, **kw):
    o = {"op": name}
    if n is not None:
        o["n"] = n
    o.update(kw)
    return o


def D(n, **kw):
    return op("damage", n, **kw)


def B(n, **kw):
    return op("block", n, **kw)


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
    """Усилить числа в применении/Силе — для вариантов прозрения."""
    x = copy.deepcopy(x)

    def walk(obj):
        if isinstance(obj, dict):
            if obj.get("op") in SCALE and obj.get("n") is not None:
                obj["n"] = max(1, obj["n"] + max(1, round(obj["n"] * frac)))
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
    walk(x)
    return x


def add_op(use, *ops):
    x = copy.deepcopy(use)
    x["do"] = list(x.get("do", [])) + list(ops)
    return x


def add_if(use, *conds):
    x = copy.deepcopy(use)
    x["if"] = list(x.get("if", [])) + list(conds)
    return x


def card(name, typ, cost, main, alt, art, ill, tags, options, vfx=None):
    if vfx and "vfx" not in main:
        main["vfx"] = vfx
    return {"ill": ill, "art": art, "name": name, "cost": cost, "type": typ, "main": main, "alt": alt,
            "tags": tags, "growth": [{"uses": 3, "options": options}]}


def ill_from(cards, cid, dx=0.01, dy=0.02, dz=0.0):
    src = list(cards[cid]["ill"])
    return [src[0], round(min(0.98, max(0.02, src[1] + dx)), 3),
            round(min(0.98, max(0.02, src[2] + dy)), 3), round(min(0.95, max(0.05, src[3] + dz)), 3)]


def adds(cards):
    """Новые карты Охотницы. art/ill берём у существующих карт, смещая кадр."""
    shot_art = cards["h_shot"]
    mark_art = cards["h_marking"]
    arrow_art = cards["h_fill"]
    out = {}

    # ---------- range: дальность и прицел ----------
    scope = me(op("ranged_bonus", 2))
    out["h_scope"] = card(
        "Дальний прицел", "skill", 1, scope, {"target": "cell_step", "step": 1, "do": []},
        shot_art["art"], ill_from(cards, "h_horn", 0.02, -0.03), ["Выстрел"], [
            V("Ещё дальше", me(op("ranged_bonus", 3))),
            V("С щитом", me(op("ranged_bonus", 2), B(4)), "Прицел под щитом"),
            V("С добором", me(op("ranged_bonus", 2), op("draw", 1)), "Прицел и дыхание"),
            V("С фокусом", me(op("ranged_bonus", 2), op("focus")), "Точный прицел"),
            V("С разбега", {"target": "cell_step", "step": 2, "do": [op("ranged_bonus", 1)]}, "Прицел на ходу"),
        ], vfx="focus")
    snipe = shot(8, D(8), **{"if": [{"when": {"k": "far", "n": 5}, "plus": 6}]})
    out["h_snipe"] = card(
        "Снайперский выстрел", "attack", 2, snipe, {"target": "cell_step", "step": 1, "do": []},
        shot_art["art"], ill_from(cards, "h_long", -0.02, 0.04), ["Выстрел"], [
            V("Сильнее", bump(snipe)),
            V("Ещё издалека", add_if(snipe, {"when": {"k": "far", "n": 4}, "plus": 8}), "Выстрел вдаль"),
            V("С кровью", add_op(snipe, op("bleed", 3)), "Снайперский порез"),
            V("По уязвимому", add_if(snipe, {"when": {"k": "vulnerable"}, "mult": 2}), "Выстрел в брешь"),
            V("С меткой", add_op(snipe, op("mark", 3)), "Снайперская метка"),
        ], vfx="headshot")
    steady = me(op("focus"), B(4))
    out["h_steady"] = card(
        "Твёрдая рука", "skill", 1, steady, {"target": "cell_step", "step": 1, "do": []},
        shot_art["art"], ill_from(cards, "h_focus", 0.03, 0.01), ["Выстрел"], [
            V("Крепче", me(op("focus"), B(6))),
            V("С добором", me(op("focus"), B(4), op("draw", 1)), "Дыхание и выстрел"),
            V("С прицелом", me(op("focus"), B(4), op("ranged_bonus", 1)), "Твёрдый прицел"),
            V("С шагом", {"target": "cell_step", "step": 1, "do": [op("focus"), B(3)]}, "Шаг и прицел"),
            V("С энергией", me(op("focus"), B(4), op("energy", 1)), "Второе дыхание"),
        ], vfx="focus")

    # ---------- mark: метка и добыча ----------
    burst = shot(5, D(4, per={"what": "mark", "k": 3}))
    out["h_mark_burst"] = card(
        "Финальный выстрел", "attack", 2, burst, {"target": "cell_step", "step": 1, "do": []},
        mark_art["art"], ill_from(cards, "h_marking", 0.02, 0.03), ["Выстрел", "Метка"], [
            V("Сильнее", bump(burst)),
            V("Глубже метка", shot(5, D(4, per={"what": "mark", "k": 4})), "Финальный выстрел"),
            V("С меткой", add_op(burst, op("mark", 2)), "Метка и выстрел"),
            V("По уязвимому", add_if(burst, {"when": {"k": "vulnerable"}, "plus": 5}), "Выстрел в брешь"),
            V("С добором", add_op(burst, op("draw", 1)), "Выстрел и взгляд"),
        ], vfx="headshot")
    web = {"target": "area", "range": 5, "radius": 1, "do": [op("mark", 2)], "vfx": "hunter_mark"}
    out["h_mark_web"] = card(
        "Паутина меток", "skill", 1, web, {"target": "cell_step", "step": 1, "do": []},
        mark_art["art"], ill_from(cards, "h_net", 0.02, -0.02), ["Метка"], [
            V("Сильнее", {"target": "area", "range": 5, "radius": 1, "do": [op("mark", 3)], "vfx": "hunter_mark"}),
            V("Шире", {"target": "area", "range": 5, "radius": 2, "do": [op("mark", 2)], "vfx": "hunter_mark"}),
            V("С слабостью", {"target": "area", "range": 5, "radius": 1,
                              "do": [op("mark", 2), op("weak", 2)], "vfx": "hunter_mark"}),
            V("С уязвимостью", {"target": "area", "range": 5, "radius": 1,
                                "do": [op("mark", 2), op("vulnerable", 1)], "vfx": "hunter_mark"}),
            V("С добором", {"target": "area", "range": 5, "radius": 1,
                            "do": [op("mark", 2), op("draw", 1)], "vfx": "hunter_mark"}),
        ])
    hunt = me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                     "do": [op("mark", 2)], "once": True})
    out["h_hunt"] = card(
        "Охотничий азарт", "power", 2, hunt, {"target": "cell_step", "step": 1, "do": []},
        mark_art["art"], ill_from(cards, "h_horn", -0.02, 0.02), ["Метка", "Выстрел"], [
            V("Сильнее", me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                                   "do": [op("mark", 3)], "once": True})),
            V("Каждый выстрел", me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                                          "do": [op("mark", 2)]}), "Неутомимая охота"),
            V("С добором", me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                                     "do": [op("mark", 2), op("draw", 1)], "once": True}), "Азарт и взгляд"),
            V("С уязвимостью", me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                                         "do": [op("mark", 2), op("vulnerable", 1)], "once": True}), "Азарт и брешь"),
            V("С мощью", me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                                   "do": [op("mark", 2), op("strength", 1)], "once": True}), "Азарт и сила"),
        ])

    # ---------- quiver: стрелы, повтор, серия ----------
    echo = shot(5, D(5), **{"if": [{"when": {"k": "resonance", "tag": "Выстрел", "n": 2}, "repeat": 1}]})
    out["h_echo_shot"] = card(
        "Эхо-стрела", "attack", 1, echo, {"target": "cell_step", "step": 1, "do": []},
        shot_art["art"], ill_from(cards, "h_barrage", 0.03, -0.01), ["Выстрел", "Повтор", "Комбо"], [
            V("Сильнее", bump(echo)),
            V("С меткой", add_op(echo, op("mark", 2)), "Эхо и метка"),
            V("С добором", add_op(echo, op("draw", 1)), "Эхо и взгляд"),
            V("Дальше", shot(7, D(5), **{"if": [{"when": {"k": "resonance", "tag": "Выстрел", "n": 2},
                                             "repeat": 1}]}), "Далёкое эхо"),
            V("С разбега", {"target": "reach", "reach": 2, "do": [
                D(4, per={"what": "tag:Выстрел", "k": 1}), op("draw", 1)]}, "Эхо на ходу"),
        ], vfx="aimed_shot")
    rapid = shot(5, D(3), op("draw", 1), **{"if": [{"when": {"k": "series", "n": 2}, "repeat": 1}]})
    out["h_rapid"] = card(
        "Быстрый выстрел", "attack", 1, rapid, {"target": "cell_step", "step": 1, "do": []},
        shot_art["art"], ill_from(cards, "h_shoot_roll", -0.03, 0.01), ["Выстрел", "Комбо", "Повтор"], [
            V("Сильнее", bump(rapid)),
            V("С добором", shot(5, D(3), op("draw", 2),
                                **{"if": [{"when": {"k": "series", "n": 2}, "repeat": 1}]}), "Быстрая рука"),
            V("С меткой", add_op(rapid, op("mark", 2)), "Быстрая метка"),
            V("Дальше", shot(6, D(3), op("draw", 1),
                            **{"if": [{"when": {"k": "series", "n": 2}, "repeat": 1}]}), "Далёкая серия"),
            V("С серией", shot(5, D(3), op("draw", 1),
                              **{"if": [{"when": {"k": "series", "n": 1}, "repeat": 1}]}), "Мгновенная серия"),
        ], vfx="barrage")
    quiver = me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                       "do": [op("damage", 2)]})
    out["h_quiver_echo"] = card(
        "Эхо колчана", "power", 2, quiver, {"target": "cell_step", "step": 1, "do": []},
        arrow_art["art"], ill_from(cards, "h_master_quiver", 0.02, 0.02), ["Выстрел", "Повтор"], [
            V("Сильнее", me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                                   "do": [op("damage", 3)]})),
            V("С меткой", me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                                    "do": [op("damage", 2), op("mark", 1)]}), "Эхо и метка"),
            V("С щитом", me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                                   "do": [op("damage", 2), op("block", 2)]}), "Эхо и щит"),
            V("С уязвимостью", me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                                         "do": [op("damage", 2), op("vulnerable", 1)]}), "Эхо и брешь"),
            V("Всем", me(power={"on": "play", "tag": "Выстрел", "aim": "all",
                                "do": [op("damage", 1)]}), "Эхо по всем"),
        ], vfx="barrage")
    return out


def main():
    cards = json.load(open(P_CARDS, encoding="utf-8"))["cards"]
    new = adds(cards)
    for cid, d in new.items():
        cards[cid] = d
    data = json.load(open(P_CARDS, encoding="utf-8"))
    data["cards"] = cards
    with open(P_CARDS, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    heroes = json.load(open(P_HEROES, encoding="utf-8"))
    h = heroes["heroes"]["hunter"]
    h["starter_by_variant"] = {
        "range": ["h_shot", "h_shot", "h_shot", "h_shot", "h_aimed", "h_long", "h_focus",
                  "h_dodge", "h_dodge", "h_backstep", "h_shoot_roll"],
        "mark": ["h_shot", "h_shot", "h_shot", "h_marking", "h_marking", "h_mark_burst",
                 "h_dodge", "h_dodge", "h_trail", "h_net", "h_aimed"],
        "quiver": ["h_shot", "h_shot", "h_shot", "h_fill", "h_fill", "h_volley",
                   "h_dodge", "h_dodge", "h_shoot_roll", "h_barrage", "h_rapid"],
    }
    # Ядро школы: из него выпадает 2 карты из 3, третья — «свободная» из общего пула.
    h["rewards_by_variant"] = {
        "range": ["h_long", "h_aimed", "h_focus", "h_horn", "h_pierce", "h_deadeye", "h_evade",
                  "h_brush", "h_trail", "h_scope", "h_snipe", "h_steady"],
        "mark": ["h_marking", "h_mark_burst", "h_mark_web", "h_hunt", "h_lure",
                 "h_net", "h_finish", "h_trail", "h_aimed", "h_pierce", "h_deadeye", "h_knife"],
        "quiver": ["h_fill", "h_full_quiver", "h_master_quiver", "h_barrage", "h_volley",
                   "h_echo_shot", "h_rapid", "h_quiver_echo", "h_knife", "h_shoot_roll",
                   "h_evade", "h_rain"],
    }
    for ids in h["rewards_by_variant"].values():
        h["rewards"] = list(dict.fromkeys(h["rewards"] + ids))
    h["rewards"] = list(dict.fromkeys(h["rewards"] + list(new)))
    h["passives"]["range"]["desc"] = ("Дальность: +1 урона за клетку сверх 3 (до +4). "
                                      "Колода: прицел и снайперские выстрелы.")
    h["passives"]["mark"]["desc"] = ("Добыча: +3 по ней, убийство — +1 энергия и карта. "
                                     "Колода: метки и добивание.")
    h["passives"]["quiver"]["desc"] = ("Стрела в руку каждый ход. "
                                       "Колода: стрелы, добор и повторные выстрелы.")
    with open(P_HEROES, "w", encoding="utf-8") as f:
        json.dump(heroes, f, ensure_ascii=False, indent=1)
    print("новых карт:", len(new), "—", ", ".join(new))


if __name__ == "__main__":
    main()
