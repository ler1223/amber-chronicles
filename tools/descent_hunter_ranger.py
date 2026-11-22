"""Охотница: дополнительные карты CZN Ranger/Hunter.

Расширяет пул до полного набора ролей: одиночный урон, серии, области, добор,
энергия, защита, сохранение, дебаффы и пейоффы. Механики CZN с неподдерживаемыми
ресурсами (Bullet, Quietus, Tenacity) сведены к существующим операциям; источник
сохранён в поле source.

Запускать после tools/descent_hunter_damage.py.
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
RARITY = {"Normal": 1, "Rare": 2, "Legendary": 3, "Mythic": 4}
CZ_NAMES = {
    "h_rng_vortex": "Vortex Arrow", "h_rng_big_game": "Big Game Ranger",
    "h_rng_matrix": "Matrix Overlay", "h_rng_tactical": "Tactical Maneuver",
    "h_rng_final_shot": "Final Shot", "h_rng_stealth_reload": "Stealth Reload",
    "h_rng_demon_dance": "Dance of the Demon", "h_rng_lethal_design": "Lethal Design",
    "h_rng_finisher": "Finisher Round", "h_rng_blooming": "Blooming Love",
    "h_rng_liberated": "Liberated Feelings", "h_rng_instant": "Instant Judgment",
    "h_rng_ballad": "Ballad of Pitch Black", "h_rng_last_ditch": "Last-Ditch Assault",
    "h_rng_plasma_missile": "Plasma Missile", "h_rng_cobalt": "Cobalt Light",
    "h_rng_pale_star": "Pale Shooting Star", "h_rng_charged": "Charged Shot",
    "h_rng_guilty": "Guilty Pleasure", "h_rng_unlimited": "Unlimited Firepower",
    "h_rng_max_output": "Max Output Charged Shot", "h_rng_hero": "Hero to All",
    "h_rng_thread": "Thread of Light", "h_rng_elysium": "Elysium of Blades",
    "h_rng_repose": "Repose", "h_rng_kowalski": "Sir Kowalski",
    "h_rng_hunting_time": "Hunting Time", "h_rng_flamethrower": "Flame Thrower",
    "h_rng_flashbang": "Flashbang", "h_rng_full_burst": "Full Burst",
}


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


def options(main):
    return [V("Сильнее", bump(main)),
            V("С добором", add_op(main, op("draw", 1)), "Дыхание"),
            V("С защитой", add_op(main, B(3))),
            V("С меткой", add_op(main, op("mark", 1)), "Метка"),
            V("С энергией", add_op(main, op("energy", 1)), "Второе дыхание")]


def ill_from(cards, cid, dx, dy):
    global SEQ
    SEQ += 1
    i = SEQ
    src = list(cards[cid]["ill"])
    return [src[0], round(min(0.98, max(0.02, src[1] + dx + (i % 11) * 0.006)), 4),
            round(min(0.98, max(0.02, src[2] + dy + (i // 11) * 0.009)), 4), src[3]]


def add(cards, cid, src, name, main, tags, *, typ="attack", cost=1, src_rarity="Rare",
        source, alt=None, **extra):
    c = copy.deepcopy(cards[src])
    c.update({
        "name": name, "main": main, "type": typ, "cost": cost, "tags": list(tags),
        "category": "hero", "owner": "hunter", "rarity": RARITY.get(src_rarity, 2),
        "source": dict(source, game="CZN"),
        "ill": ill_from(cards, src, 0.03, 0.02),
    })
    if alt is not None:
        c["alt"] = alt
    c.pop("levels", None)
    for f in ("chain", "echo", "keep"):
        c.pop(f, None)
    c.update(extra)
    if "growth" in c:
        c["growth"][0]["options"] = options(main)
    cards[cid] = c


def main():
    data = json.load(open(P_CARDS, encoding="utf-8"))
    cards = data["cards"]
    new = []

    def card(cid, name, src, main, tags, typ="attack", cost=1, rarity="Rare", character="", effect="", **extra):
        add(cards, cid, src, name, main, tags, typ=typ, cost=cost, src_rarity=rarity,
            source={"character": character, "name": CZ_NAMES.get(cid, name), "effect": effect}, **extra)
        new.append(cid)

    # Hilde
    card("h_rng_vortex", "Вихревая стрела", "h_volley",
         {"target": "area", "range": 6, "radius": 1, "do": [D(5)], "ranged": True, "vfx": "rain_of_arrows"},
         ["Выстрел", "Область", "Комбо"], cost=2, rarity="Legendary", character="Hilde",
         effect="Draw 3; 120% Damage to all enemies; +60% per Attack drawn")
    card("h_rng_big_game", "Большая дичь", "h_hunt",
         me(power={"on": "play", "tag": "Выстрел", "aim": "nearest",
                   "do": [op("mark", 1), op("hunt", 1)]}),
         ["Метка", "Выстрел", "Преследование"], typ="power", cost=2, rarity="Legendary",
         character="Hilde", effect="On Hit: 2 Zero In")
    card("h_rng_matrix", "Матричное наложение", "h_smoke_screen",
         {"target": "area", "range": 6, "radius": 1,
          "do": [op("weak", 2), op("vulnerable", 1)], "vfx": "poison_cloud"},
         ["Область", "Клич", "Комбо"], typ="skill", cost=2, rarity="Legendary",
         character="Hilde", effect="+15% Weakness Damage; Draw 3 Attack cards")
    # Selena
    card("h_rng_tactical", "Тактический манёвр", "h_dodge",
         me(B(6), op("counter", 2)), ["Защита", "Клич"], typ="skill", cost=1, rarity="Legendary",
         character="Selena", effect="150% Shield; 2 Tenacity damage")
    card("h_rng_final_shot", "Финальный выстрел", "h_deadeye",
         shot(6, D(10), op("mark", 3)), ["Выстрел", "Метка"], cost=3, rarity="Mythic",
         character="Selena", effect="300% Damage; 3 Mark")
    # Luke
    card("h_rng_stealth_reload", "Теневая перезарядка", "h_arrow_well",
         me(op("add_card", 3, card="arrow"), op("draw", 1)), ["Создание", "Выстрел"],
         typ="skill", cost=1, rarity="Rare", character="Luke", effect="Create 3 Handgun Bullets")
    card("h_rng_demon_dance", "Танец демона", "h_barrage", shot(5, D(2), D(2), D(2)),
         ["Выстрел", "Комбо"], cost=1, rarity="Legendary", character="Luke",
         effect="50% Damage; add 1 Hit per Bullet")
    card("h_rng_lethal_design", "Смертельный замысел", "h_barrage",
         shot(5, D(4, per={"what": "hand", "k": 1})), ["Выстрел", "Комбо"], cost=2,
         rarity="Mythic", character="Luke", effect="450% Damage; +25% per card in hand")
    card("h_rng_finisher", "Последний патрон", "h_deadeye",
         shot(6, D(12)), ["Выстрел"], cost=3, rarity="Mythic", character="Luke",
         effect="500% Damage when 5 Bullets activated", unique=True)
    # Diana / Renoa
    card("h_rng_blooming", "Цветущая любовь", "h_focus",
         me(op("draw", 2), op("energy", 1)), ["Комбо"], typ="skill", cost=1, rarity="Legendary",
         character="Diana", effect="Draw Quietus; Discard 2")
    card("h_rng_liberated", "Освобождённые чувства", "h_shot",
         shot(6, D(8), op("draw", 2)), ["Выстрел", "Комбо"], cost=2, rarity="Mythic",
         character="Diana", effect="Draw 2 Exhaust Bullet; 300% Damage")
    card("h_rng_instant", "Мгновенный приговор", "h_shot",
         shot(6, D(7, per={"what": "hand", "k": 1})), ["Выстрел", "Комбо"], cost=2, rarity="Rare",
         character="Renoa", effect="220% Damage; +100% if Dirge Bullet in hand")
    card("h_rng_ballad", "Баллада тьмы", "h_barrage", shot(6, D(2), D(2), D(2)),
         ["Выстрел", "Комбо"], cost=1, rarity="Rare", character="Renoa",
         effect="60% Damage x3; +20% per Dirge Bullet")
    card("h_rng_last_ditch", "Последний штурм", "h_shot",
         shot(6, D(9)), ["Выстрел"], cost=2, rarity="Legendary", character="Renoa",
         effect="300% Damage; discard Dirge Bullets for +50%")
    # Sereniel
    card("h_rng_plasma_missile", "Плазменная ракета", "h_shot",
         shot(6, D(5), op("weak", 1)), ["Выстрел", "Клич"], cost=1, rarity="Rare",
         character="Sereniel", effect="120% Damage; proc again if not Ravaged")
    card("h_rng_cobalt", "Кобальтовый свет", "h_volley",
         {"target": "area", "range": 5, "radius": 1, "do": [D(5), D(5)], "ranged": True,
          "vfx": "rain_of_arrows"}, ["Выстрел", "Область"], cost=3, rarity="Mythic",
         character="Sereniel", effect="140% Damage x4 to random enemies")
    card("h_rng_pale_star", "Бледная звезда", "h_shot",
         shot(6, D(9), op("draw", 1)), ["Выстрел", "Комбо"], cost=2, rarity="Legendary",
         character="Sereniel", effect="150% Damage; proc Homing Lasers")
    # Beryl / Heidemarie / Veronica / Lucas
    card("h_rng_charged", "Заряженный выстрел", "h_shot", shot(6, D(7)),
         ["Выстрел", "Сохранение"], cost=2, rarity="Rare", character="Beryl",
         effect="270% Damage; Retain", retain=True)
    card("h_rng_guilty", "Порочное удовольствие", "h_focus", me(op("draw", 3)),
         ["Комбо", "Изгнание"], typ="skill", cost=0, rarity="Rare", character="Beryl",
         effect="Draw 3; Exhaust", exhaust=True)
    card("h_rng_unlimited", "Неограниченная мощь", "h_shot",
         me(B(5), op("ranged_bonus", 1)), ["Защита", "Выстрел"], typ="skill", cost=1,
         rarity="Rare", character="Beryl", effect="100% Shield; next Attack +80%")
    card("h_rng_max_output", "Максимальная мощность", "h_volley",
         {"target": "area", "range": 6, "radius": 1, "do": [D(8)], "ranged": True,
          "vfx": "rain_of_arrows"}, ["Выстрел", "Область"], cost=3, rarity="Legendary",
         character="Beryl", effect="350% Damage to all enemies")
    card("h_rng_hero", "Герой для всех", "h_focus", me(op("draw", 3)),
         ["Комбо"], typ="skill", cost=1, rarity="Legendary", character="Heidemarie",
         effect="Draw 3; apply Linked")
    card("h_rng_thread", "Нить света", "h_shot",
         shot(6, D(6, per={"what": "hand", "k": 1})), ["Выстрел", "Комбо"], cost=1,
         rarity="Rare", character="Heidemarie", effect="120% Damage; +120% per Linked card")
    card("h_rng_elysium", "Элизиум клинков", "h_rain",
         {"target": "area", "range": 6, "radius": 1, "do": [D(8)], "ranged": True,
          "vfx": "rain_of_arrows"}, ["Выстрел", "Область"], cost=3, rarity="Mythic",
         character="Heidemarie", effect="400% Damage; +80% per discarded card")
    card("h_rng_repose", "Покой", "h_dodge", me(B(6), op("draw", 2)),
         ["Защита", "Комбо"], typ="skill", cost=1, rarity="Rare", character="Veronica",
         effect="100% Shield; Draw 2")
    card("h_rng_kowalski", "Сэр Ковальски", "h_focus",
         me(op("draw", 1), op("ranged_bonus", 2)), ["Комбо", "Выстрел"], typ="skill",
         cost=1, rarity="Legendary", character="Veronica", effect="Select Ballista; +100%; Draw 1")
    card("h_rng_hunting_time", "Время охоты", "h_rain",
         {"target": "area", "range": 6, "radius": 1, "do": [D(8)], "ranged": True,
          "vfx": "rain_of_arrows"}, ["Выстрел", "Область"], cost=3, rarity="Legendary",
         character="Veronica", effect="250% Piercing Damage to all enemies")
    card("h_rng_flamethrower", "Огнемёт", "h_rain",
         {"target": "area", "range": 5, "radius": 1, "do": [D(5), op("burn", 2)],
          "ranged": True, "vfx": "rain_of_arrows"}, ["Выстрел", "Область", "Огонь"],
         cost=2, rarity="Legendary", character="Lucas", effect="180% Damage to all; Draw 1")
    card("h_rng_flashbang", "Светошумовая", "h_volley",
         {"target": "area", "range": 5, "radius": 1, "do": [D(3), op("weak", 2)],
          "ranged": True, "vfx": "rain_of_arrows"}, ["Выстрел", "Область", "Клич"],
         cost=1, rarity="Rare", character="Lucas", effect="120% Damage to all; 2 Weaken")
    card("h_rng_full_burst", "Полный залп", "h_rain",
         {"target": "area", "range": 6, "radius": 1, "do": [D(7), op("weak", 1)],
          "ranged": True, "vfx": "rain_of_arrows"}, ["Выстрел", "Область", "Комбо"],
         cost=3, rarity="Mythic", character="Lucas", effect="Draw 2; 250% Damage to all enemies")

    heroes = json.load(open(P_HEROES, encoding="utf-8"))
    h = heroes["heroes"]["hunter"]
    h["rewards"] = list(dict.fromkeys(h.get("rewards", []) + new))
    for variant in ("mark", "quiver", "range", "chain"):
        pool = h.setdefault("rewards_by_variant", {}).setdefault(variant, [])
        pool[:] = list(dict.fromkeys(pool + new))
    json.dump(data, open(P_CARDS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(heroes, open(P_HEROES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    czn = json.load(open(P_CZN, encoding="utf-8"))
    marked = 0
    for cid in new:
        src = cards[cid]["source"]
        for row in czn["cards"]:
            if row["variant"] == "Base" and row["character"] == src["character"] and row["name"] == src["name"]:
                row["adapted_as"] = list(dict.fromkeys(row.get("adapted_as", []) + [cid]))
                marked += 1
                break
    json.dump(czn, open(P_CZN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("новых ranger/hunter карт:", len(new), "| отмечено в каталоге:", marked)
    print(", ".join(new))


if __name__ == "__main__":
    main()
