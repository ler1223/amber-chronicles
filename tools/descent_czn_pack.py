"""Пакет карт CZN, которые переносятся в движок «Спуска».

Полный каталог CZN лежит в data/czn/cards.json (импорт: tools/import_czn_catalog.py).
Этот файл добавляет только те карты, которые можно выразить существующими операциями:
урон, защита, лечение, добор, энергия, метки, кровотечение, области, толчки, силы и временные карты.

Запускать ПОСЛЕ tools/descent_tiers.py:
    python tools/descent_tiers.py
    python tools/descent_czn_pack.py

CZN-карты помечены source.game == "CZN"; tier-скрипт их не переклассифицирует.
"""
import copy
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "deck")
P_CARDS = os.path.join(D, "cards.json")
P_HEROES = os.path.join(D, "heroes.json")

RARITY = {"Normal": 1, "Rare": 2, "Legendary": 3, "Mythic": 4}
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
                               "vulnerable", "weak", "strength"} and o.get("n") is not None:
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
    src = list(cards[cid]["ill"])
    # Каждой перенесённой карте — свой фрагмент иллюстрации (тест на уникальные лица).
    global SEQ
    SEQ += 1
    i = SEQ
    x = src[1] + dx + (i % 13) * 0.007
    y = src[2] + dy + (i // 13) * 0.011
    return [src[0], round(min(0.98, max(0.02, x)), 4),
            round(min(0.98, max(0.02, y)), 4), src[3]]


def add(cards, cid, source_cid, name, main, tags, *, typ="attack", cost=None, owner=None,
        rarity="Rare", source=None, dx=0.02, dy=0.01, alt=None, **extra):
    c = copy.deepcopy(cards[source_cid])
    c["name"] = name
    c["main"] = main
    c["type"] = typ
    if cost is not None:
        c["cost"] = cost
    c["tags"] = list(tags)
    if alt is not None:
        c["alt"] = alt
    c["rarity"] = RARITY.get(rarity, 2)
    c["category"] = "neutral" if owner is None else "hero"
    if owner:
        c["owner"] = owner
    c["source"] = dict(source or {}, game="CZN")
    c.update(extra)
    c["ill"] = ill_from(cards, source_cid, dx, dy)
    c.pop("levels", None)
    for f in ("chain", "echo", "keep"):
        c.pop(f, None)
    if "growth" in c:
        c["growth"][0]["options"] = opts(main)
    cards[cid] = c


def main():
    data = json.load(open(P_CARDS, encoding="utf-8"))
    cards = data["cards"]
    added = []

    # ---------- Охотница: Hilde / Selena ----------
    add(cards, "h_czn_multishot", "h_volley", "Мультивыстрел",
        {"target": "area", "range": 5, "radius": 1, "do": [D(3)], "ranged": True, "vfx": "rain_of_arrows"},
        ["Выстрел", "Область"], cost=1, owner="hunter", source={
            "character": "Hilde", "name": "Multishot", "effect": "60% Damage to all enemies"})
    add(cards, "h_czn_quiver_reload", "h_arrow_well", "Перезарядка колчана",
        me(op("add_card", 3, card="arrow"), op("draw", 1)),
        ["Создание", "Выстрел"], typ="skill", cost=1, owner="hunter", source={
            "character": "Hilde", "name": "Quiver Reload", "effect": "Create 3 Homing Arrow in Draw Pile"})
    add(cards, "h_czn_plasma_rain", "h_rain", "Плазменный дождь",
        {"target": "area", "range": 5, "radius": 1, "do": [D(4), op("burn", 2)],
         "ranged": True, "vfx": "rain_of_arrows"},
        ["Выстрел", "Область", "Огонь"], cost=2, owner="hunter", source={
            "character": "Hilde", "name": "Plasma Rain", "effect": "60% Damage and 2 Ionization to all enemies"})
    add(cards, "h_czn_draw_release", "h_focus", "Натянуть и отпустить",
        me(op("draw", 2), op("ranged_bonus", 1)),
        ["Комбо", "Выстрел"], typ="skill", cost=1, owner="hunter", source={
            "character": "Hilde", "name": "Draw & Release", "effect": "Draw 2 Attack Cards; +50% Damage"})
    add(cards, "h_czn_high_scope", "h_marking", "Мощная оптика",
        {"target": "enemy", "range": 6, "los": True, "do": [op("mark", 3), op("draw", 1)]},
        ["Метка", "Выстрел"], typ="skill", cost=1, owner="hunter", source={
            "character": "Selena", "name": "High-Power Scope", "effect": "2 Mark"})
    add(cards, "h_czn_target_spotted", "h_shot", "Цель замечена",
        shot(6, D(5), op("mark", 2)),
        ["Выстрел", "Метка"], cost=1, owner="hunter", source={
            "character": "Selena", "name": "Target Spotted", "effect": "150% Damage; 1 Mark"})
    add(cards, "h_czn_drone_bomb", "h_volley", "Бомбардировка дронами",
        {"target": "area", "range": 5, "radius": 1, "do": [D(4), op("weak", 2)],
         "ranged": True, "vfx": "grenade"},
        ["Выстрел", "Область", "Клич"], cost=2, owner="hunter", source={
            "character": "Selena", "name": "Drone Bombing", "effect": "120% Damage to all enemies, 1 Weakness"})
    add(cards, "h_czn_sniper_domain", "h_hunt", "Владения снайпера",
        me(power={"on": "play", "tag": "Метка", "aim": "nearest", "do": [D(3)]}),
        ["Метка", "Выстрел"], typ="power", cost=2, owner="hunter", source={
            "character": "Selena", "name": "Sniper's Domain", "effect": "+80% Mark Damage"})
    added += ["h_czn_multishot", "h_czn_quiver_reload", "h_czn_plasma_rain", "h_czn_draw_release",
              "h_czn_high_scope", "h_czn_target_spotted", "h_czn_drone_bomb", "h_czn_sniper_domain"]

    # ---------- Наёмник: Maribell / Khalipe / Magna ----------
    add(cards, "m_czn_shelter_kick", "m_hit_back", "Удар из укрытия",
        {"target": "enemy", "range": 1, "do": [D(5), B(4)]},
        ["Удар", "Защита"], cost=1, owner="merc", source={
            "character": "Maribell", "name": "Shelter Kick", "effect": "Defense-based damage"})
    add(cards, "m_czn_shelter_mk2", "m_hit_back", "Укрытие MK.II",
        {"target": "enemy", "range": 1, "do": [D(6), B(6)]},
        ["Удар", "Защита"], cost=2, owner="merc", source={
            "character": "Maribell", "name": "Shelter MK.II", "effect": "120% Defense Damage; 100% Shield"})
    add(cards, "m_czn_wolves_dome", "m_shieldwall", "Волчий купол",
        me(power={"on": "turn", "do": [op("counter", 1), B(4)]}),
        ["Защита", "Шипы"], typ="power", cost=1, owner="merc", source={
            "character": "Maribell", "name": "Wolves' Dome", "effect": "Counterattack each turn"})
    add(cards, "m_czn_shelter_strike", "body_slam", "Удар щитом",
        {"target": "enemy", "range": 1, "do": [op("body_slam"), B(3)]},
        ["Удар", "Защита"], cost=1, owner="merc", source={
            "character": "Maribell", "name": "Shelter Strike", "effect": "Fixed Damage equal to Shield"})
    add(cards, "m_czn_overpower", "m_ring", "Пересилить",
        {"target": "self", "do": [B(8), op("aoe_adjacent", do=[op("push", 1)])]},
        ["Защита", "Толчок", "Область"], cost=2, owner="merc", source={
            "character": "Khalipe", "name": "Overpower", "effect": "250% Shield; Tenacity damage"})
    add(cards, "m_czn_rally", "m_hit_back", "Сплочение",
        me(B(6), op("draw", 1)),
        ["Защита", "Комбо"], typ="skill", cost=1, owner="merc", source={
            "character": "Khalipe", "name": "Rally", "effect": "120% Shield; Draw highest-cost"})
    add(cards, "m_czn_frost_charge", "m_ring", "Морозный заряд",
        {"target": "area", "range": 4, "radius": 1, "do": [B(7), op("vulnerable", 2)]},
        ["Защита", "Область", "Клич"], typ="skill", cost=2, owner="merc", source={
            "character": "Magna", "name": "Frost Charge", "effect": "140% Shield; 3 Vulnerable"})
    add(cards, "m_czn_ice_wall", "m_shieldwall", "Ледяная стена",
        me(B(8), op("counter", 2)),
        ["Защита", "Шипы"], typ="skill", cost=2, owner="merc", source={
            "character": "Magna", "name": "Ice Wall", "effect": "200% Shield; 2 Counterattack"})
    added += ["m_czn_shelter_kick", "m_czn_shelter_mk2", "m_czn_wolves_dome", "m_czn_shelter_strike",
              "m_czn_overpower", "m_czn_rally", "m_czn_frost_charge", "m_czn_ice_wall"]

    # ---------- Пиромантка: Fei / Kayron / Mei Lin / Tenebria ----------
    add(cards, "p_czn_soulfire", "p_lance", "Танец души",
        shot(5, D(3), op("draw", 1)),
        ["Огонь", "Комбо"], cost=1, owner="pyro", source={
            "character": "Fei", "name": "Soulfire Dance", "effect": "100% Damage x X+1; Draw X"})
    add(cards, "p_czn_soliloquy", "h_focus", "Монолог",
        me(op("draw", 2)),
        ["Комбо"], typ="skill", cost=1, owner="pyro", source={
            "character": "Fei", "name": "Soliloquy", "effect": "Draw 2; discard high-cost"})
    add(cards, "p_czn_black_hole", "p_meteor", "Чёрная дыра",
        shot(5, D(8, per={"what": "exhausted", "k": 1})),
        ["Огонь", "Комбо"], cost=2, owner="pyro", source={
            "character": "Kayron", "name": "Black Hole", "effect": "240% Damage; +40% per Futility"})
    add(cards, "p_czn_brand", "p_meteor", "Клеймо уничтожения",
        {"target": "area", "range": 5, "radius": 1, "do": [D(7)], "vfx": "e_meteor"},
        ["Огонь", "Область"], cost=3, owner="pyro", source={
            "character": "Kayron", "name": "Brand of Annihilation", "effect": "400% Damage to all enemies"})
    add(cards, "p_czn_echo_abyss", "p_geyser", "Эхо бездны",
        {"target": "area", "range": 4, "radius": 1, "do": [D(6), op("draw", 1)], "vfx": "geyser"},
        ["Огонь", "Область"], cost=2, owner="pyro", source={
            "character": "Kayron", "name": "Echoes of True Abyss", "effect": "240% Damage; create Futility"})
    add(cards, "p_czn_rising_dragon", "p_geyser", "Восходящий дракон",
        shot(4, D(3), D(3), D(3)),
        ["Огонь", "Комбо"], cost=1, owner="pyro", source={
            "character": "Mei Lin", "name": "Rising Dragon Spire", "effect": "100% Damage; Streak: +1 Hit"})
    add(cards, "p_czn_unity", "p_ashstep", "Единство атаки и защиты",
        me(op("draw", 2), op("energy", 1)),
        ["Комбо"], typ="skill", cost=0, owner="pyro", source={
            "character": "Mei Lin", "name": "Unity of Attack and Defense", "effect": "Draw 2; reduce cost"})
    add(cards, "p_czn_call_response", "p_lance", "Зов и ответ",
        shot(5, D(5), op("draw", 1)),
        ["Огонь", "Комбо"], cost=1, owner="pyro", source={
            "character": "Tenebria", "name": "Call & Response", "effect": "200% Damage; draw Rhythm"})
    add(cards, "p_czn_encore", "p_geyser", "На бис",
        shot(5, D(4), **{"if": [{"when": {"k": "series", "n": 2}, "repeat": 1}]}),
        ["Огонь", "Комбо"], cost=1, owner="pyro", source={
            "character": "Tenebria", "name": "Encore", "effect": "120% Damage; repeat Rhythm"})
    added += ["p_czn_soulfire", "p_czn_soliloquy", "p_czn_black_hole", "p_czn_brand",
              "p_czn_echo_abyss", "p_czn_rising_dragon", "p_czn_unity", "p_czn_call_response",
              "p_czn_encore"]

    # ---------- Нейтральные: общие карты CZN ----------
    neutral = [
        ("n_czn_quick_shell", "Быстрый обстрел", "Quick Shelling", shot(5, D(4), op("draw", 1)),
         ["Выстрел", "Комбо"], "attack", 1, {"character": "Neutral", "name": "Quick Shelling",
                                               "effect": "80% Damage; Draw 1"}),
        ("n_czn_reorganize", "Реорганизация", "Reorganize", me(op("draw", 3)), ["Комбо", "Изгнание"],
         "skill", 1, {"character": "Neutral", "name": "Reorganize", "effect": "Draw 3; Exhaust"}),
        ("n_czn_rally", "Сплочение", "Rally", me(op("draw", 1), op("energy", 1)), ["Комбо"],
         "skill", 1, {"character": "Neutral", "name": "Rally", "effect": "Draw 1; +Action Count"}),
        ("n_czn_protective", "Защитный клич", "Protective Shout", me(B(7)), ["Защита"],
         "skill", 1, {"character": "Neutral", "name": "Protective Shout", "effect": "130% Shield"}),
        ("n_czn_precision", "Точный прицел", "Precision Aim", shot(6, D(5), op("draw", 1)),
         ["Выстрел", "Комбо"], "attack", 1, {"character": "Neutral", "name": "Precision Aim",
                                               "effect": "120% Damage; top of Draw Pile"}),
        ("n_czn_pulverize", "Дробить", "Pulverize", shot(4, D(4), D(4), op("draw", 1)),
         ["Удар", "Комбо"], "attack", 2, {"character": "Neutral", "name": "Pulverize",
                                            "effect": "150% Damage x2; Draw 1"}),
        ("n_czn_pierce", "Пронизать", "Pierce",
         shot(6, D(8), op("vulnerable", 1), op("weak", 1), op("bleed", 2)),
         ["Выстрел", "Клич", "Кровь"], "attack", 2, {"character": "Neutral", "name": "Pierce",
                                                     "effect": "200% Damage; Vulnerable, Weaken, Agony"}),
        ("n_czn_adagio", "Адажио", "Adagio", me(op("draw", 2)), ["Комбо", "Изгнание"],
         "skill", 0, {"character": "Nia", "name": "Adagio", "effect": "Draw 1; Discard 1"}),
        ("n_czn_soul_riff", "Душевный рифф", "Soul Riff", me(op("heal", 5), op("draw", 1)),
         ["Комбо"], "skill", 1, {"character": "Nia", "name": "Soul Riff",
                                  "effect": "Heal 150%; Retain"}),
    ]
    for cid, name, en, main, tags, typ, cost, src in neutral:
        add(cards, cid, "h_focus" if typ == "skill" else "h_shot", name, main, tags,
            typ=typ, cost=cost, owner=None, source=src, dx=0.03 + 0.01 * len(added), dy=0.02,
            exhaust=True if cid in ("n_czn_reorganize", "n_czn_adagio") else None)
        added.append(cid)

    data.setdefault("neutral", [])
    data["neutral"] = sorted(set(data["neutral"]) | {c for c in added if c.startswith("n_czn_")})
    heroes = json.load(open(P_HEROES, encoding="utf-8"))
    for cid in added:
        if cid.startswith("h_czn_"):
            heroes["heroes"]["hunter"]["rewards"] = list(dict.fromkeys(heroes["heroes"]["hunter"]["rewards"] + [cid]))
        elif cid.startswith("m_czn_"):
            heroes["heroes"]["merc"]["rewards"] = list(dict.fromkeys(heroes["heroes"]["merc"]["rewards"] + [cid]))
        elif cid.startswith("p_czn_"):
            heroes["heroes"]["pyro"]["rewards"] = list(dict.fromkeys(heroes["heroes"]["pyro"]["rewards"] + [cid]))

    json.dump(data, open(P_CARDS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(heroes, open(P_HEROES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # Отметить в полном каталоге, какие CZN-строки уже получили игровую версию.
    catalog_path = os.path.join(ROOT, "data", "czn", "cards.json")
    if os.path.exists(catalog_path):
        catalog = json.load(open(catalog_path, encoding="utf-8"))
        by_source = {}
        for cid in added:
            src = cards[cid].get("source", {})
            by_source.setdefault((src.get("character"), src.get("name")), []).append(cid)
        for row in catalog.get("cards", []):
            if row.get("variant") == "Base":
                row["adapted_as"] = by_source.get((row.get("character"), row.get("name")), [])
        json.dump(catalog, open(catalog_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("CZN-карт добавлено:", len(added))
    print(", ".join(added))


if __name__ == "__main__":
    main()
