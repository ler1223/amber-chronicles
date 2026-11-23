"""Вторая волна слияния карт Охотницы: area, движение, точные дубли.

Запускать после tools/consolidate_hunter.py.
"""
import copy
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P_CARDS = os.path.join(ROOT, "data", "deck", "cards.json")
P_HEROES = os.path.join(ROOT, "data", "deck", "heroes.json")
P_CZN = os.path.join(ROOT, "data", "czn", "cards.json")

GROUPS = {
    "h_volley": ["h_area_hunt", "h_rain", "h_dmg_black_volley", "h_rng_vortex"],
    "h_marking": ["h_czn_target_spotted"],
    "h_trail": ["h_evade", "h_shadow_step"],
    "h_chain_draw": ["h_scout", "h_rng_guilty"],
    "h_rng_hunting_time": ["h_rng_max_output", "h_rng_elysium"],
    "h_blood_volley": ["h_rng_ballad"],
    "h_arrow_well": ["h_rng_stealth_reload"],
}


def option(cards, cid):
    c = cards[cid]
    return {"label": c["name"], "name": c["name"], "main": copy.deepcopy(c["main"])}


def main():
    data = json.load(open(P_CARDS, encoding="utf-8"))
    cards = data["cards"]
    removed = {}

    for base, gone in GROUPS.items():
        if base not in cards:
            continue
        opts = cards[base].setdefault("growth", [{"uses": 3, "options": []}])[0].setdefault("options", [])
        new = [option(cards, cid) for cid in gone if cid in cards]
        if not new:
            continue
        if base == "h_marking":
            # Сохранить «Стрелу-маяк» и добавить «Цель замечена».
            opts[3:] = [option(cards, "h_beacon") if "h_beacon" in cards else opts[-1], new[0]]
        elif base == "h_volley":
            opts[-len(new):] = new
        elif len(opts) >= 5:
            opts[-len(new):] = new
        else:
            opts.extend(new)
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
    h["starter"] = ["h_volley" if cid == "h_area_hunt" else cid for cid in h.get("starter", [])]
    for pool in (h.get("starter_by_variant") or {}).values():
        pool[:] = ["h_volley" if cid == "h_area_hunt" else cid for cid in pool]

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
            row.pop("adapted_as", None)

    json.dump(data, open(P_CARDS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(heroes, open(P_HEROES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(czn, open(P_CZN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Вторая волна, объединено:", len(removed))
    for cid, base in removed.items():
        print(f"  {cid} -> {base}")


if __name__ == "__main__":
    main()
