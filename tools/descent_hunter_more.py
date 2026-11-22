"""Расширение Охотницы: карты Tressa-стиля, области, добор и энергия.

Запускать после tools/descent_tactics.py:
    python tools/descent_hunter_more.py

Механики Tressa перенесены на существующие ресурсы «Спуска»:
- Shadow Dagger → временные «Кровавые стрелы» (0 стоимости, bleeding);
- Agony → кровотечение;
- Curse → сила «кровавый навет» (при выстреле вешает кровотечение);
- Vital Attack → многократный залп с бонусом по кровоточащей цели;
- Shadow Reload → добор/энергия/создание стрел.
"""
import copy
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "deck")
P_CARDS = os.path.join(D, "cards.json")
P_HEROES = os.path.join(D, "heroes.json")

SCALE = {"damage", "block", "draw", "mark", "bleed", "burn", "poison", "weak", "vulnerable", "ranged_bonus",
         "heal", "energy", "hunt", "push", "pull", "strength"}


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


def options(main, self_target=False):
    """Пять простых веток, чтобы у каждой новой карты было прозрение."""
    extra = op("strength", 1) if self_target else op("bleed", 1)
    return [
        V("Сильнее", bump(main)),
        V("С добором", add_op(main, op("draw", 1)), "Дыхание"),
        V("С защитой", add_op(main, B(3))),
        V("С кровью", add_op(main, extra), "Кровь"),
        V("С энергией", add_op(main, op("energy", 1)), "Второе дыхание"),
    ]


def add_new(cards, cid, src, name, main, tags, *, alt=None, typ=None, dx=0.03, dy=0.01, opts=None, **extra):
    c = copy.deepcopy(cards[src])
    c["name"] = name
    c["main"] = main
    c["tags"] = list(tags)
    if alt is not None:
        c["alt"] = alt
    if typ:
        c["type"] = typ
    if opts is not None:
        c["growth"][0]["options"] = opts
    elif "growth" in c:
        c["growth"][0]["options"] = options(main, main.get("target") == "self")
    c["ill"] = ill_from(cards, src, dx, dy)
    c.pop("levels", None)
    for field in ("chain", "echo", "keep"):
        c.pop(field, None)
    c.update(extra)
    cards[cid] = c
    return c


def main():
    data = json.load(open(P_CARDS, encoding="utf-8"))
    cards = data["cards"]
    out = {}

    # Токен Tressa-style: Shadow Dagger → Кровавая стрела.
    add_new(cards, "arrow_blood", "arrow", "Кровавая стрела",
            shot(6, D(3), op("bleed", 2)),
            ["Выстрел", "Кровь"], typ="attack", dx=0.10, dy=0.08,
            opts=None, token=True, exhaust=True)
    out["arrow_blood"] = "arrow_blood"

    # +урон при розыгрыше (не копия «Охотничьего азарта»: мощи на все атаки, ценой HP).
    bloodlust = me(op("strength", 2), op("lose_hp", 2), op("draw", 1))
    add_new(cards, "h_bloodlust", "h_focus", "Кровавый азарт", bloodlust,
            ["Клич", "Кровь"], typ="skill", dx=0.12, dy=0.02,
            opts=options(bloodlust, self_target=True))

    # Tressa Curse: при игре выстрела вешает кровотечение.
    curse_power = {"on": "play", "tag": "Выстрел", "aim": "nearest", "do": [op("bleed", 1)]}
    add_new(cards, "h_blood_rite", "h_hunt", "Кровавый навет",
            me(power=curse_power), ["Кровь", "Выстрел"], typ="power", dx=0.13, dy=0.03,
            opts=[V("Сильнее", me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                                         "do": [op("bleed", 2)]})),
                  V("Дольше", me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                                        "do": [op("bleed", 1)], "once": True}), "Навет раз за ход"),
                  V("С меткой", me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                                          "do": [op("bleed", 1), op("mark", 1)]})),
                  V("По площади", me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                                            "do": [op("bleed", 1), op("weak", 1)]})),
                  V("С добором", me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                                           "do": [op("bleed", 1), op("draw", 1)]}))])

    # Tressa Vital Attack: три удара, бонус по кровоточащей цели.
    volley = shot(6, D(3), D(3), D(3), **{"if": [{"when": {"k": "bleeding"}, "plus": 2}]})
    add_new(cards, "h_blood_volley", "h_barrage", "Кровавый залп", volley,
            ["Выстрел", "Кровь"], cost=2, dx=0.14, dy=0.04,
            opts=[V("Сильнее", shot(6, D(4), D(4), D(4), **{"if": [{"when": {"k": "bleeding"}, "plus": 2}]})),
                  V("Четыре удара", shot(6, D(3), D(3), D(3), D(3),
                                         **{"if": [{"when": {"k": "bleeding"}, "plus": 2}]}), "Кровавый залп"),
                  V("С добором", shot(6, D(3), D(3), D(3),
                                       **{"if": [{"when": {"k": "bleeding"}, "plus": 2}], "do": [D(3), D(3), D(3), op("draw", 1)]}),
                    "Залп и дыхание"),
                  V("Глубже", shot(6, D(3), D(3), D(3),
                                    **{"if": [{"when": {"k": "bleeding"}, "plus": 4}]}), "Кровавый залп"),
                  V("Дальше", shot(8, D(3), D(3), D(3),
                                    **{"if": [{"when": {"k": "bleeding"}, "plus": 2}]}), "Далёкий залп")])

    # Tressa Shadow Dagger: создаёт временные кровавые стрелы.
    add_new(cards, "h_shadow_quiver", "h_arrow_well", "Теневой колчан",
            me(op("add_card", 2, card="arrow_blood", cname="Кровавая стрела"), op("draw", 1)),
            ["Создание", "Выстрел"], typ="skill", dx=0.15, dy=0.05,
            opts=[V("Больше стрел", me(op("add_card", 3, card="arrow_blood", cname="Кровавая стрела"),
                                        op("draw", 1))),
                  V("С добором", me(op("add_card", 2, card="arrow_blood", cname="Кровавая стрела"),
                                     op("draw", 2)), "Тень и дыхание"),
                  V("С энергией", me(op("add_card", 2, card="arrow_blood", cname="Кровавая стрела"),
                                      op("energy", 1)), "Тень и дыхание"),
                  V("С меткой", me(op("add_card", 2, card="arrow_blood", cname="Кровавая стрела"),
                                    op("mark", 2)), "Тень и метка"),
                  V("С защитой", me(op("add_card", 2, card="arrow_blood", cname="Кровавая стрела"),
                                     B(4)), "Тень и щит")])

    # Tressa Shadow Reload: добор, энергия и стрелы.
    add_new(cards, "h_dark_reload", "h_chain_draw", "Перезарядка тьмы",
            me(op("draw", 2), op("energy", 1), op("add_card", 1, card="arrow_blood", cname="Кровавая стрела")),
            ["Создание", "Комбо"], typ="skill", cost=1, dx=0.16, dy=0.06,
            opts=[V("Больше карт", me(op("draw", 3), op("energy", 1),
                                       op("add_card", 1, card="arrow_blood", cname="Кровавая стрела"))),
                  V("Больше энергии", me(op("draw", 2), op("energy", 2),
                                          op("add_card", 1, card="arrow_blood", cname="Кровавая стрела"))),
                  V("Две стрелы", me(op("draw", 2), op("energy", 1),
                                      op("add_card", 2, card="arrow_blood", cname="Кровавая стрела"))),
                  V("С защитой", me(op("draw", 2), op("energy", 1), B(4),
                                     op("add_card", 1, card="arrow_blood", cname="Кровавая стрела"))),
                  V("С меткой", me(op("draw", 2), op("energy", 1), op("mark", 1),
                                    op("add_card", 1, card="arrow_blood", cname="Кровавая стрела")))])

    # Простая карта добора/энергии — почти без прямого урона.
    add_new(cards, "h_second_wind", "h_focus", "Второе дыхание",
            me(op("energy", 1), op("draw", 1)), ["Комбо"], typ="skill", cost=0, dx=0.17, dy=0.07,
            opts=options(me(op("energy", 1), op("draw", 1)), self_target=True), exhaust=True)
    out["h_second_wind"] = "h_second_wind"

    add_new(cards, "h_scout", "h_focus", "Разведка",
            me(op("draw", 2)), ["Комбо"], typ="skill", dx=0.18, dy=0.08,
            opts=[V("Больше карт", me(op("draw", 3))),
                  V("С энергией", me(op("draw", 1), op("energy", 1)), "Разведка и дыхание"),
                  V("С защитой", me(op("draw", 2), B(3)), "Разведка и щит"),
                  V("С меткой", me(op("draw", 2), op("mark", 1)), "Разведка и метка"),
                  V("С кровью", me(op("draw", 2), op("bleed", 2)), "Разведка и кровь")])

    # Областные умения: ослабление и контроль, не просто ещё один урон.
    add_new(cards, "h_smoke_screen", "h_toxic", "Дымовая завеса",
            {"target": "area", "range": 5, "radius": 1, "do": [op("weak", 2), op("draw", 1)],
             "vfx": "poison_cloud"},
            ["Область", "Клич"], typ="skill", dx=0.19, dy=0.09,
            opts=[V("Шире", {"target": "area", "range": 5, "radius": 2,
                              "do": [op("weak", 2), op("draw", 1)], "vfx": "poison_cloud"}),
                  V("Сильнее", {"target": "area", "range": 5, "radius": 1,
                                 "do": [op("weak", 3), op("draw", 1)], "vfx": "poison_cloud"}),
                  V("С меткой", {"target": "area", "range": 5, "radius": 1,
                                  "do": [op("weak", 2), op("draw", 1), op("mark", 1)], "vfx": "poison_cloud"}),
                  V("С уязвимостью", {"target": "area", "range": 5, "radius": 1,
                                       "do": [op("weak", 2), op("draw", 1), op("vulnerable", 1)], "vfx": "poison_cloud"}),
                  V("С защитой", {"target": "area", "range": 5, "radius": 1,
                                   "do": [op("weak", 2), op("draw", 1), B(3)], "vfx": "poison_cloud"})])

    add_new(cards, "h_snare_net", "h_mark_web", "Облава",
            {"target": "area", "range": 5, "radius": 1, "do": [op("root", 1), op("mark", 1)],
             "vfx": "hunter_mark"},
            ["Область", "Ловушка", "Метка"], typ="skill", dx=0.20, dy=0.10,
            opts=[V("Шире", {"target": "area", "range": 5, "radius": 2,
                              "do": [op("root", 1), op("mark", 1)], "vfx": "hunter_mark"}),
                  V("Дольше", {"target": "area", "range": 5, "radius": 1,
                                "do": [op("root", 2), op("mark", 1)], "vfx": "hunter_mark"}),
                  V("С добором", {"target": "area", "range": 5, "radius": 1,
                                   "do": [op("root", 1), op("mark", 1), op("draw", 1)], "vfx": "hunter_mark"}),
                  V("С уязвимостью", {"target": "area", "range": 5, "radius": 1,
                                       "do": [op("root", 1), op("mark", 1), op("vulnerable", 1)], "vfx": "hunter_mark"}),
                  V("С кровью", {"target": "area", "range": 5, "radius": 1,
                                  "do": [op("root", 1), op("mark", 1), op("bleed", 2)], "vfx": "hunter_mark"})])

    # Retain-карта: не сбрасывается в конце хода.
    add_new(cards, "h_patient_shot", "h_shot", "Терпеливый выстрел",
            shot(6, D(6)), ["Выстрел", "Сохранение"], dx=0.21, dy=0.11, retain=True)

    out.update({k: k for k in ("h_bloodlust", "h_blood_rite", "h_blood_volley", "h_shadow_quiver",
                               "h_dark_reload", "h_scout", "h_smoke_screen", "h_snare_net",
                               "h_patient_shot")})

    heroes = json.load(open(P_HEROES, encoding="utf-8"))
    h = heroes["heroes"]["hunter"]
    all_new = [k for k in out if k != "arrow_blood"]
    h["rewards"] = list(dict.fromkeys(h.get("rewards", []) + all_new))
    for variant, ids in {
        "mark": ["h_bloodlust", "h_blood_rite", "h_blood_volley", "h_shadow_quiver", "h_patient_shot"],
        "quiver": ["h_shadow_quiver", "h_dark_reload", "h_second_wind", "h_scout", "h_smoke_screen",
                   "h_snare_net", "h_blood_volley", "h_patient_shot"],
        "range": ["h_bloodlust", "h_smoke_screen", "h_snare_net", "h_scout"],
        "chain": ["h_second_wind", "h_dark_reload", "h_scout", "h_smoke_screen"],
    }.items():
        pool = h.setdefault("rewards_by_variant", {}).setdefault(variant, [])
        pool[:] = list(dict.fromkeys(pool + ids))
    h.setdefault("reward_guarantee", {})["quiver"] = list(dict.fromkeys(
        h["reward_guarantee"].get("quiver", []) + ["h_shadow_quiver"]))

    with open(P_CARDS, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    with open(P_HEROES, "w", encoding="utf-8") as f:
        json.dump(heroes, f, ensure_ascii=False, indent=1)
    print("новых карт Охотницы:", len(out), "—", ", ".join(out))


if __name__ == "__main__":
    main()
