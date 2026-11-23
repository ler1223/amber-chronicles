"""Общий балансный пакет по итогам квиза.

- 0-стоимость только у созданных/свитков/редких и явно утверждённых исключений;
- альтернативное применение — только у базовых карт (кроме h_backstep/m_run)
  и трёх сигнатур: charge, body_slam, riposte;
- «Адажио» получает выбор сброса 2 карт;
- «Порочное удовольствие» — цена 1 и добор 2.

Запускать вручную после согласования; это не генератор контента.
"""
import copy
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "deck", "cards.json")
NOALT = {"target": "none", "do": []}

COST = {
    "m_run": 1,
    "brace": 1,
    "h_chain_draw": 1,
    "h_rng_guilty": 1,
    "m_bloodpact": 1,
}

# Базовые карты, которые действительно сохраняют альтернативу.
# h_backstep и m_run тоже базовые, но по отдельному решению alt у них убран.
BASE_ALT = {"strike", "defend", "h_shot", "h_dodge", "p_bolt", "p_ward", "p_stride",
            "sc_attack", "sc_defense", "sc_move"}
SIGNATURE_ALT = {"charge", "body_slam", "riposte"}
KEEP_ALT = BASE_ALT | SIGNATURE_ALT


def find_op(use, kind):
    return next((o for o in use.get("do", []) if o.get("op") == kind), None)


def ensure_adagio(use):
    """В любом прозрении Адажио должны остаться и добор, и выбор сброса."""
    use = copy.deepcopy(use)
    do = use.setdefault("do", [])
    if not find_op(use, "draw"):
        do.insert(0, {"op": "draw", "n": 2})
    if not find_op(use, "discard_choose"):
        do.append({"op": "discard_choose", "n": 2})
    return use


def main():
    data = json.load(open(P, encoding="utf-8"))
    cards = data["cards"]

    for cid, cost in COST.items():
        cards[cid]["cost"] = cost

    guilty = cards["h_rng_guilty"]
    draw = find_op(guilty["main"], "draw")
    if draw:
        draw["n"] = 2
    guilty["cost"] = 1

    adagio = cards["n_czn_adagio"]
    adagio["main"] = ensure_adagio(adagio["main"])
    for growth in adagio.get("growth", []):
        for opt in growth.get("options", []):
            if opt.get("main"):
                opt["main"] = ensure_adagio(opt["main"])

    for cid, c in cards.items():
        if cid not in KEEP_ALT:
            c["alt"] = copy.deepcopy(NOALT)

    # Контроль: всё, что осталось за 0, должно быть созданным/свитком/редким
    # или явно утверждённым исключением.
    allowed_zero = {
        "arrow", "arrow_blood", "t_knife", "t_spark",       # created tokens
        "m_ambush", "m_counter", "m_trophy",                  # rare reactions
        "h_backstep", "h_knife", "h_second_wind", "p_cool", "p_czn_unity",
        "p_stoke", "m_battle_plan", "n_czn_adagio",           # approved exceptions
    }
    for cid, c in cards.items():
        if cid.startswith("sc_"):
            allowed_zero.add(cid)                             # priest scrolls
        if c.get("cost") == 0:
            assert cid in allowed_zero or c.get("token"), f"непроверенная 0-стоимость: {cid}"
        if cid not in KEEP_ALT:
            assert c["alt"].get("target") == "none", f"alt остался у {cid}"

    json.dump(data, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Балансный пакет применён.")
    print("0-стоимость:", len([c for c in cards.values() if c.get("cost") == 0]))
    print("С альтернативой:", len([c for c in cards.values()
                                    if c.get("alt", {}).get("target") != "none"]))


if __name__ == "__main__":
    main()
