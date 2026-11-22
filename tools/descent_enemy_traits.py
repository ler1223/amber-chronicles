"""Враги «Спуска» сложнее (квиз 2026-11-21): HP всех врагов ×2, свойства-механики, новые мобы и +1 моб с механикой
в каждый бой и элиту. Запускать ПОСЛЕ tools/descent_chapter1.py и descent_chapter2.py (они пишут базу) — повторный
запуск не удваивает HP второй раз (метка hp_x2 на враге).

Свойства врага (deck/battle.py):
  armor N   — броня: каждый удар по нему слабее на N;          spikes N  — колючий: бьёшь вплотную — получаешь N;
  share     — стая: половину удара берёт соседний союзник;      regen N   — в начале хода лечится на N;
  grow N    — крепнет: +N силы каждый ход;                      merge     — сливается с соседом того же вида;
  mend N    — лечит соседей на N;                               protect N — щит N соседям каждый ход;
  retaliate N — отвечает ударом N на удар вплотную (раз за ход); enrage N — +N силы за каждое умение героя;
  steal     — удар крадёт карту из колоды, вернётся при его смерти;
  on_death: avenge N (соседи +N силы), curse N («Тина» в сброс), rise id (встаёт в другой форме — эволюция),
            split, explode, fire_cell, hex (были).

Запуск: python tools/descent_enemy_traits.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "deck", "enemies.json")


def M(name, dmg, **kw):
    return dict(kind="melee", name=name, dmg=dmg, **kw)


def S(name, dmg, rng=5, **kw):
    return dict(kind="shot", name=name, dmg=dmg, range=rng, **kw)


def K(kind, name, **kw):
    return dict(kind=kind, name=name, **kw)


TRAIT_TEXT = {
    "armor": "Броня {n}: каждый удар по нему слабее на {n}.",
    "spikes": "Колючий: ударивший вплотную получает {n}.",
    "share": "Стая: половину удара берёт соседний союзник.",
    "regen": "Регенерация: +{n} HP в начале хода.",
    "grow": "Крепнет: +{n} силы каждый ход.",
    "merge": "Сливается с соседом того же вида — один, но вдвое крепче.",
    "mend": "Лечит соседей на {n} в начале хода.",
    "protect": "Даёт соседям {n} защиты каждый ход.",
    "retaliate": "Отвечает ударом {n} на удар вплотную (раз за ход).",
    "enrage": "Злится: +{n} силы за каждое сыгранное вами умение.",
    "steal": "Удар крадёт карту из колоды — вернётся, когда он умрёт.",
}
DEATH_TEXT = {
    "avenge": "Умирая, ярит соседей: +{n} силы.",
    "curse": "Умирая, подкладывает «Тину» ×{n} в сброс.",
    "rise": "Умирая, встаёт снова: {name}.",
}

# новые враги (HP — уже итоговые, после удвоения)
NEW = {
    # ---------- болото ----------
    "acid_drop": dict(name="Едкая капля", sprite="toxic_slime", hp=14, speed=3, small=True, merge=True,
                      cycle=[M("Брызг", 3, add=[{"op": "poison", "n": 1}])],
                      on_death={"explode": {"dmg": 0, "r": 0, "hazard": "poison"}}, about="Мелкая и едкая."),
    "sticky_slime": dict(name="Липкий слизень", sprite="slime", hp=34, speed=2, merge=True, grow=1,
                         cycle=[M("Шлепок", 6), M("Обволочь", 4, add=[{"op": "block", "n": 6}])],
                         on_death={"split": "acid_drop", "n": 2}, about="Распадается на едкие капли."),
    "reed_militia": dict(name="Камышовый ополченец", sprite="reed_militia", hp=28, speed=3, protect=4,
                         cycle=[M("Удар вилами", 6), K("guard", "Сомкнуть ряды", n=5, r=2)],
                         about="Прикрывает своих."),
    "thorn_boar": dict(name="Колючий кабан", sprite="thorn_beast", hp=36, speed=3, spikes=3,
                       cycle=[M("Таран клыками", 8), M("Таран клыками", 8)], about="Весь в колючках."),
    "shell_crab": dict(name="Панцирник", sprite="crab_knight", hp=30, speed=2, armor=3,
                       cycle=[M("Клешня", 6), K("block", "Втянуться", n=8)], about="Слабые удары отскакивают."),
    "bog_eel": dict(name="Болотный угорь", sprite="eel", hp=22, speed=4, retaliate=4,
                    cycle=[M("Хлёст", 5), M("Укус", 6)], about="Скользкий и злой."),
    "sundew": dict(name="Росянка", sprite="maneater", hp=34, speed=0, regen=3,
                   cycle=[K("pull", "Липкий ус", dmg=3, range=4, n=3), M("Пасть", 10)],
                   about="Не ходит — подтягивает к себе."),
    "ghoul": dict(name="Трупоед", sprite="ghoul", hp=26, speed=3, steal=True,
                  cycle=[M("Рвать", 6), M("Рвать", 6)], on_death={"rise": "ghoul_hungry"},
                  about="Ворует и не умирает с первого раза."),
    "ghoul_hungry": dict(name="Голодный трупоед", sprite="ghoul", hp=24, speed=4, grow=2,
                         cycle=[M("Грызть", 7)], about="Восставший: голоден и крепнет."),
    "drowned_bones": dict(name="Костяк утопленника", sprite="skeleton", hp=14, speed=2,
                          cycle=[M("Костлявый удар", 4)], about="Что осталось от утопленника."),
    "bog_nymph": dict(name="Болотная нимфа", sprite="dryad", hp=24, speed=2, keep_range=3, mend=4,
                      cycle=[S("Шип", 4, 4), K("heal", "Целебный туман", n=6, r=3)],
                      on_death={"rise": "will_wisp"}, about="Лечит своих; умирая, становится огоньком."),
    "bog_ogre": dict(name="Болотный огр", sprite="steppe_ogre", hp=70, speed=2, enrage=2,
                     cycle=[M("Дубина", 11), M("Дубина", 11), K("roar", "Рёв", weak=1, r=3)],
                     about="Ненавидит хитрости."),
    # ---------- кузни ----------
    "slag_crawler": dict(name="Шлаковый ползун", sprite="scarab", hp=20, speed=3, armor=2, merge=True,
                         cycle=[M("Жвалы", 5, add=[{"op": "burn", "n": 1}])], on_death={"fire_cell": True},
                         about="Панцирь из шлака."),
    "forge_sentinel": dict(name="Страж горна", sprite="sentinel", hp=44, speed=2, armor=4, protect=4,
                           cycle=[M("Алебарда", 9), K("guard", "Строй", n=6, r=2)], about="Стоит стеной."),
    "ash_cocoon": dict(name="Пепельный кокон", sprite="volcano_heart", hp=26, speed=0, grow=1,
                       cycle=[K("block", "Твердеть", n=8), K("block", "Твердеть", n=8)],
                       on_death={"rise": "ash_wraith"}, about="Не бьёт — зреет. Разбейте — выйдет дух."),
    "apprentice": dict(name="Подмастерье", sprite="forge_overseer", hp=32, speed=3, enrage=2,
                       cycle=[M("Молот", 8), M("Клещи", 6, add=[{"op": "weak", "n": 1}])], about="Горяч и обидчив."),
    "sparkling": dict(name="Искряк", sprite="sprite", hp=14, speed=4, retaliate=3,
                      cycle=[M("Искра", 4, add=[{"op": "burn", "n": 1}])],
                      on_death={"explode": {"dmg": 6, "r": 1}}, about="Взрывается."),
    "slag_thief": dict(name="Вор шлака", sprite="raider", hp=26, speed=4, steal=True,
                       cycle=[M("Подрезать", 6), M("Подрезать", 6)], on_death={"curse": 1},
                       about="Тащит всё, что плохо лежит."),
    "cooled_lava": dict(name="Остывшая лава", sprite="living_lava", hp=18, speed=1, armor=3,
                        cycle=[M("Тяжёлый ком", 6)], about="Застывшая корка."),
}

# свойства существующим врагам
TRAITS = {
    "slime": dict(merge=True), "toxic_slime": dict(merge=True), "bog_croc": dict(armor=2),
    "old_tooth": dict(armor=3, retaliate=5), "bog_horror": dict(grow=1), "leech_mother": dict(mend=4),
    "mosquito_swarm": dict(share=True), "toad_guard": dict(protect=3),
    "kvaks": dict(enrage=1), "magma_golem": dict(regen=3), "obsidian_guard": dict(armor=3),
    "flame_priest": dict(mend=4), "chain_smith": dict(retaliate=4), "crucible_golem": dict(armor=4),
    "slag_slave": dict(share=True), "ember_hound": dict(retaliate=3),
}
DEATHS = {
    "drowned": {"rise": "drowned_bones"}, "rust_merc": {"avenge": 2}, "cult_zealot": {"avenge": 2},
    "living_lava": {"rise": "cooled_lava"}, "spore_shroom": {"curse": 1},
}
# по мобу с механикой в каждый бой главы (по кругу) и в элиту
ADD = {0: ["sticky_slime", "reed_militia", "shell_crab", "bog_eel", "ghoul", "acid_drop", "bog_nymph", "sundew",
           "thorn_boar"],
       1: ["slag_crawler", "apprentice", "sparkling", "slag_thief", "ash_cocoon", "forge_sentinel"]}
ELITE_ADD = {0: ["bog_ogre", "ghoul", "thorn_boar"], 1: ["forge_sentinel", "apprentice", "ash_cocoon"]}


def describe(d):
    """Текст свойств — к описанию врага (подсказка в бою)."""
    bits = [TRAIT_TEXT[k].format(n=d[k]) for k in TRAIT_TEXT if d.get(k)]
    od = d.get("on_death") or {}
    for k, t in DEATH_TEXT.items():
        if od.get(k):
            bits.append(t.format(n=od[k], name=od[k] if k != "rise" else ""))
    return bits


def main():
    data = json.load(open(P, encoding="utf-8"))
    E = data["enemies"]
    data.pop("doubled", None)
    for d in E.values():                                        # HP ×2 — один раз (метка на самом враге)
        if not d.get("hp_x2"):
            d["hp"] = d["hp"] * 2
            d["hp_x2"] = True
    for eid, d in NEW.items():
        E[eid] = dict(d, hp_x2=True)
    for eid, t in TRAITS.items():
        if eid in E:
            E[eid].update(t)
    for eid, od in DEATHS.items():
        if eid in E:
            E[eid]["on_death"] = dict(E[eid].get("on_death") or {}, **od)
    for eid, d in E.items():                                    # описание свойств
        base = d.get("about_base", d.get("about", ""))
        d["about_base"] = base
        bits = describe(d)
        rise = (d.get("on_death") or {}).get("rise")
        if rise:
            bits = [b if not b.startswith("Умирая, встаёт") else f"Умирая, встаёт снова: {E[rise]['name']}." for b in bits]
        d["about"] = " ".join([base] + bits).strip()
    for ci, ch in enumerate(data.get("chapters", [])):
        k = 0
        for fi, fl in enumerate(ch["floors"]):
            for kind, pools in fl["pools"].items():
                for p in pools:
                    base = p.get("base_enemies", p["enemies"])
                    p["base_enemies"] = list(base)
                    if ci == 0 and fi == 0:                     # первый этаж — без добавки: втягивание
                        p["enemies"] = list(base)
                    elif kind == "battle":
                        add = ADD[min(ci, 1)][k % len(ADD[min(ci, 1)])]
                        k += 1
                        p["enemies"] = list(base) + [add]
                    elif kind == "elite":
                        add = ELITE_ADD[min(ci, 1)][k % len(ELITE_ADD[min(ci, 1)])]
                        k += 1
                        p["enemies"] = list(base) + [add]
                    else:
                        p["enemies"] = list(base)
    json.dump(data, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("врагов:", len(E), "новых:", len(NEW), "со свойствами:",
          sum(1 for d in E.values() if any(d.get(k) for k in TRAIT_TEXT) or d.get("on_death")))


if __name__ == "__main__":
    main()
