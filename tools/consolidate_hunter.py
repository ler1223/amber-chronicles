"""Первая волна слияния похожих карт Охотницы.

Малые отличия убираются из отдельных карт и становятся вариантами прозрений
базовой карты. Запускать последним после всех генераторов и balance policy.
"""
import copy
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P_CARDS = os.path.join(ROOT, "data", "deck", "cards.json")
P_HEROES = os.path.join(ROOT, "data", "deck", "heroes.json")
P_CZN = os.path.join(ROOT, "data", "czn", "cards.json")

# база -> карты, чьи основные эффекты переносятся в прозрения
GROUPS = {
    "h_fill": ["h_full_quiver"],
    "h_poison": ["h_venom_tip"],
    "h_jagged": ["h_dmg_rupture"],
    "h_tendon": ["h_dmg_cripple"],
    "h_focus": ["h_steady", "h_ambush2"],
    "h_marking": ["h_beacon"],
    "h_arrow_well": ["h_shadow_quiver", "h_czn_quiver_reload"],
}


def main():
    data = json.load(open(P_CARDS, encoding="utf-8"))
    cards = data["cards"]
    removed = {}

    def option(cid):
        c = cards[cid]
        return {"label": c["name"], "name": c["name"], "main": copy.deepcopy(c["main"])}

    for base, gone in GROUPS.items():
        if base not in cards:
            continue
        opts = cards[base].setdefault("growth", [{"uses": 3, "options": []}])[0].setdefault("options", [])
        if base == "h_fill":
            # У h_fill уже есть вариант «3 стрелы», отдельная копия не нужна.
            for cid in gone:
                removed[cid] = base
            continue
        new_opts = [option(cid) for cid in gone if cid in cards]
        if not new_opts:
            continue
        if len(opts) >= 5:
            opts[-len(new_opts):] = new_opts
        else:
            opts.extend(new_opts)
        for cid in gone:
            removed[cid] = base

    for cid in removed:
        cards.pop(cid, None)

    heroes = json.load(open(P_HEROES, encoding="utf-8"))
    h = heroes["heroes"]["hunter"]
    h["rewards"] = [cid for cid in h.get("rewards", []) if cid not in removed]
    for pool in h.get("rewards_by_variant", {}).values():
        pool[:] = [cid for cid in pool if cid not in removed]
    for pool in (h.get("reward_guarantee") or {}).values():
        pool[:] = [cid for cid in pool if cid not in removed]
    for key in ("starter",):
        h[key] = [cid for cid in h.get(key, []) if cid not in removed]
    for pool in (h.get("starter_by_variant") or {}).values():
        pool[:] = [cid for cid in pool if cid not in removed]

    # Источники CZN: адаптация переносится на базовую карту.
    czn = json.load(open(P_CZN, encoding="utf-8"))
    for row in czn["cards"]:
        mapped = []
        for cid in row.get("adapted_as", []):
            cid = removed.get(cid, cid)
            if cid not in mapped:
                mapped.append(cid)
        if mapped:
            row["adapted_as"] = mapped
        else:
            row.pop("adapted_as", None)          # не раздуваем каталог пустыми полями

    json.dump(data, open(P_CARDS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(heroes, open(P_HEROES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(czn, open(P_CZN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Объединено карт:", len(removed))
    for cid, base in removed.items():
        print(f"  {cid} -> {base}")


if __name__ == "__main__":
    main()
