"""Враги давят на позицию (квиз 2026-11-25, docs/descent_field.md §3): метка на клетку и линии + умеренная
природа (ветер в болоте, лавовый дождь в кузнях). Запускать ПОСЛЕ descent_chapter1/2 и descent_enemy_traits.

Формы зон (deck/battle.py zone_cells): cell — клетка героя (снайпер: уйди или получи); row / col / cross —
ряд, столбец, крест через героя; beam — луч от врага через героя до края или укрытия.
Природа боя (fight["env"]): gust — ветер сдувает героя на n клеток, если рядом нет укрытия; lava_rain — лава
падает на клетку героя и ещё n клеток рядом. Предупреждение — в начале хода, удар — в начале хода врагов.

Запуск: python tools/descent_field_pressure.py (повторный запуск ничего не удваивает).
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "deck", "enemies.json")


def Z(name, dmg, shape, **kw):
    return dict(kind="zone", name=name, dmg=dmg, shape=shape, **kw)


def S(name, dmg, rng=5, **kw):
    return dict(kind="shot", name=name, dmg=dmg, range=rng, **kw)


def M(name, dmg, **kw):
    return dict(kind="melee", name=name, dmg=dmg, **kw)


# новые циклы: метка на клетку и линии (старые удары частью остаются)
CYCLES = {
    # болото
    "bog_archer": [Z("Выстрел в клетку", 12, "cell", vfx="aimed_shot"), S("Выстрел", 6), S("Выстрел", 6)],
    "poacher": [Z("Залп вдоль ряда", 6, "row", vfx="volley"), dict(kind="veil", name="Залечь в камыши"),
                S("Выстрел", 7, 5)],
    "bell_ringer": None,                                      # элита: добавим крест в цикл (ниже)
    # кузни
    "hammer_thrower": [S("Бросок молота", 7), Z("Молот навылет", 9, "beam", vfx="toss"), S("Бросок молота", 8)],
    "flame_priest": [dict(kind="heal", name="Пламя очищения", n=8, vfx="e_heal"),
                     Z("Огненный крест", 7, "cross", hazard="fire", vfx="e_fireball"),
                     dict(kind="hex", name="Сглаз пламени", n=1)],
    "cinder_caster": [Z("Пепельная волна", 7, "row", hazard="fire", vfx="cinder_field"), S("Пепельный выстрел", 6)],
}
APPEND = {"bell_ringer": Z("Звон по линиям", 8, "cross", vfx="e_wail"),
          "rust_captain": Z("Прицельный приказ", 10, "cell", vfx="ambush_order")}
ABOUT = {
    "cell": "Метит в клетку героя: уйди — промахнётся.",
    "row": "Бьёт по всему ряду героя.", "col": "Бьёт по всему столбцу героя.",
    "cross": "Бьёт крестом — по ряду и столбцу героя.", "beam": "Бьёт лучом через героя до края.",
}
# природа: болото — ветер, кузни — лавовый дождь; не на первом этаже и не в каждом бою
ENV = {0: {"kind": "gust", "every": 4, "start": 3, "n": 2},
       1: {"kind": "lava_rain", "every": 3, "start": 2, "n": 4, "dmg": 6}}


def main():
    data = json.load(open(P, encoding="utf-8"))
    E = data["enemies"]
    for eid, cyc in CYCLES.items():
        if eid in E and cyc:
            E[eid]["cycle"] = cyc
    for eid, it in APPEND.items():
        if eid in E:
            cyc = E[eid].get("cycle", [])
            if not any(x.get("name") == it["name"] for x in cyc):
                cyc.append(it)
    for eid, d in E.items():                                   # подсказка над врагом: как он давит
        shapes = {x.get("shape") for x in d.get("cycle", []) if x.get("kind") == "zone"}
        extra = " ".join(ABOUT[s] for s in ("cell", "row", "col", "cross", "beam") if s in shapes)
        base = d.get("about", "")
        for t in ABOUT.values():
            base = base.replace(" " + t, "").replace(t, "")
        d["about"] = (base.strip() + " " + extra).strip()
    n_env = 0
    for ci, ch in enumerate(data.get("chapters", [])):
        env = ENV[min(ci, 1)]
        for fi, fl in enumerate(ch["floors"]):
            for kind, pools in fl["pools"].items():
                for k, p in enumerate(pools):
                    p.pop("env", None)
                    if ci == 0 and fi == 0:                    # первый этаж — без природы
                        continue
                    if kind == "boss" or k % 2:                # через бой: не переборщить
                        continue
                    p["env"] = dict(env)
                    n_env += 1
    json.dump(data, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("враги с давлением:", sum(1 for d in E.values() if any(x.get("shape") in ABOUT for x in d.get("cycle", []))),
          "· боёв с природой:", n_env)


if __name__ == "__main__":
    main()
