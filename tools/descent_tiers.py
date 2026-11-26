"""Тиры карт, базовые и нейтральные карты «Спуска».

Запускать последним, после всех генераторов карт:
    python tools/descent_epiphanies.py
    python tools/descent_survival.py
    python tools/descent_cards_czn.py
    python tools/descent_priest.py
    python tools/descent_builds.py
    python tools/descent_tactics.py
    python tools/descent_hunter_more.py
    python tools/descent_items.py
    python tools/descent_tiers.py

Поля:
  category: "basic" | "neutral" | "hero" | "token"
  rarity:   0 базовая, 1 обычная, 2 необычная, 3 редкая, 4 легендарная
  basic_role: attack | defense | movement (только basic)
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "deck")
P_CARDS = os.path.join(D, "cards.json")
P_HEROES = os.path.join(D, "heroes.json")

# Базовые карты: по две копии каждой роли в стартовой колоде.
BASIC = {
    "strike": ("attack", "merc"),
    "defend": ("defense", "merc"),
    "m_run": ("movement", "merc"),
    "h_shot": ("attack", "hunter"),
    "h_dodge": ("defense", "hunter"),
    "h_backstep": ("movement", "hunter"),
    "p_bolt": ("attack", "pyro"),
    "p_ward": ("defense", "pyro"),
    "p_stride": ("movement", "pyro"),
    "sc_attack": ("attack", "priest"),
    "sc_defense": ("defense", "priest"),
    "sc_move": ("movement", "priest"),
    "e_basic_attack": ("attack", "elf"),
    "e_basic_defense": ("defense", "elf"),
    "e_basic_move": ("movement", "elf"),
}

BASIC_BY_HERO = {
    "merc": {"attack": "strike", "defense": "defend", "movement": "m_run"},
    "hunter": {"attack": "h_shot", "defense": "h_dodge", "movement": "h_backstep"},
    "pyro": {"attack": "p_bolt", "defense": "p_ward", "movement": "p_stride"},
    "priest": {"attack": "sc_attack", "defense": "sc_defense", "movement": "sc_move"},
    "elf": {"attack": "e_basic_attack", "defense": "e_basic_defense", "movement": "e_basic_move"},
}

NEUTRAL = {
    "lunge": 1, "lunge_rush": 1, "brace": 1, "hook": 1, "n_hand_copy": 1,
    "shield_ram": 2, "sweep": 2, "wall_smash": 2, "riposte": 2,
    "body_slam": 2, "war_cry": 2,
    "blood_sweep": 3, "battle_rage": 3, "charge": 3,
}

T4 = {
    "h_deadeye", "h_mark_burst", "h_chain_finish", "h_hunt_final", "h_blood_volley",
    "h_blood_rite", "h_master_quiver", "h_quiver_echo",
    "m_last_word", "m_blade_storm", "m_blood_trail", "m_quake", "m_rising", "m_butcher",
    "p_meteor", "p_sun", "p_eternal", "p_phoenix", "p_spark_forge", "p_keg",
    "sc_attack_chorus", "sc_curse_chorus", "sc_defense_relay", "sc_move_relay",
    "sc_curse_relay", "sc_gift_relay",
}

T3 = {
    "h_volley", "h_long", "h_rain", "h_pit", "h_patience", "h_toxic", "h_ambush2",
    "h_scope", "h_snipe", "h_marking", "h_mark_web", "h_hunt", "h_echo_shot",
    "h_rapid", "h_chain_2", "h_chain_3", "h_chain_guard", "h_chain_mark", "h_beat",
    "h_stalk", "h_mark_hunt", "h_area_hunt", "h_bloodlust", "h_shadow_quiver",
    "h_dark_reload", "h_smoke_screen", "h_snare_net",
    "m_ram", "m_shieldwall", "m_blade_storm", "m_duelist", "m_meet", "m_crush",
    "m_leader_cry", "m_limit", "m_runner", "m_break", "m_ring", "m_bulldoze",
    "p_flash", "p_wall", "p_lance", "p_ember", "p_blaze", "p_kindle", "p_chain",
    "p_grenade", "p_oil", "p_sparks", "p_ash_eater", "p_heart", "p_fire_rain",
    "p_geyser", "p_flame_armor", "p_burnout",
    "sc_attack", "sc_defense", "sc_move",
}


def has_area(c):
    m = c.get("main", {})
    if m.get("target") == "area":
        return True
    for o in m.get("do", []):
        if o.get("op") in ("aoe_adjacent", "aoe_radius", "detonate"):
            return True
    return False


def assign(cid, c, heroes):
    if (c.get("source") or {}).get("game") == "CZN":
        return
    if c.get("token") or c.get("battle_only") or c.get("status") or c.get("meaning") and cid.startswith("slime_"):
        c["category"] = "token"
        c["rarity"] = 0
        return
    if cid in BASIC:
        role, _ = BASIC[cid]
        c["category"] = "basic"
        c["basic_role"] = role
        c["rarity"] = 0
        return
    if cid in NEUTRAL:
        c["category"] = "neutral"
        c["rarity"] = NEUTRAL[cid]
        return
    if cid == "h_ballista":
        c["category"] = "hero"
        c["rarity"] = 1
        return
    if cid in T4:
        c["category"] = "hero"
        c["rarity"] = 4
        return
    # Токены/служебные карты, которые не выбираются в наградах.
    if c.get("token") or c.get("status"):
        c["category"] = "token"
        c["rarity"] = 0
        return
    c["category"] = "hero"
    main = c.get("main", {})
    ops = list(main.get("do", []))
    sub = [x.get("op") for o in ops for x in o.get("do", [])]
    damage_ops = [o for o in ops if o.get("op") in ("damage", "body_slam")]
    dmg = sum(o.get("n", 0) for o in damage_ops)
    if cid in T3 and (c.get("type") == "power" or has_area(c)):
        c["rarity"] = 3
    elif c.get("type") == "power" or has_area(c) or len(damage_ops) >= 2 or dmg >= 12 or c.get("cost", 0) >= 3 \
            or "chain" in c or "echo" in c:
        c["rarity"] = 3
    elif c.get("cost", 0) >= 2 or main.get("if") or main.get("seal") or c.get("keep") \
            or len(ops) >= 3 or sub:
        c["rarity"] = 2
    else:
        c["rarity"] = 1


def main():
    cards_data = json.load(open(P_CARDS, encoding="utf-8"))
    cards = cards_data["cards"]
    heroes = json.load(open(P_HEROES, encoding="utf-8"))
    for cid, c in cards.items():
        assign(cid, c, heroes)
    cards_data["neutral"] = sorted(set(cards_data.get("neutral", [])) | set(NEUTRAL))
    for hid, h in heroes["heroes"].items():
        if hid in BASIC_BY_HERO:
            h["basic"] = dict(BASIC_BY_HERO[hid])
            # Убираем базовые карты из наград: они должны быть только на старте.
            basics = set(h["basic"].values())
            h["rewards"] = [c for c in h.get("rewards", []) if c not in basics]
            for pool in (h.get("rewards_by_variant") or {}).values():
                pool[:] = [c for c in pool if c not in basics]
            h["reward_guarantee"] = {
                k: [c for c in v if c not in basics] for k, v in (h.get("reward_guarantee") or {}).items()
            }
    json.dump(cards_data, open(P_CARDS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(heroes, open(P_HEROES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    from collections import Counter
    cnt = Counter(c.get("rarity", 0) for c in cards.values() if c.get("category") != "token")
    print("тиры:", dict(sorted(cnt.items())))
    print("нейтральные:", len(NEUTRAL), "базовые:", len(BASIC))
    for hid, h in heroes["heroes"].items():
        if not h.get("basic"):
            continue
        ids = [cid for cid, c in cards.items()
               if c.get("category") == "hero" and c.get("rarity") == 1 and cid.startswith(
                   {"merc": "m_", "hunter": "h_", "pyro": "p_", "priest": "sc_", "elf": "e_"}[hid])]
        print(hid, "тир1 для старта:", len(ids))


if __name__ == "__main__":
    main()
