"""Жрец идолов «Спуска» — данные прототипа (docs/descent_heroes2.md, раздел 1; deck/idols.py).

Пишет в data/deck/cards.json свитки (карты-смыслы: атака, защита, движение, проклятие, дар, призыв — исполняет
бог статуи), в data/deck/heroes.json — героя «priest» (наборы пантеона на выбор вместо пассивок), в
data/deck/gods.json — спрайт статуи каждого бога.

Запуск: python tools/descent_priest.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
D = os.path.join(ROOT, "data", "deck")

# свиток: id → (название, смысл, тип рамки, иллюстрация, текст, свойства)
# свойства: plus — сила (+к числам), repeat — ещё раз той же статуей, chorus — смысл исполняют все статуи
# (остальные — сами, по ближайшему), then — следующие смыслы: who same — той же статуей (по той же цели, если
# можно), other — другой статуей, ближе к Жрецу (перекличка); walk — Жрецу шаги, draw — свитки в руку
FRAME = {"attack": "attack", "defense": "skill", "move": "skill", "curse": "power", "gift": "power",
         "summon": "power"}
SCROLLS = {
    # основа: одно действие I
    "sc_attack": ("Свиток атаки", "attack", "priest_wisps", [{"m": "attack"}], {}),
    "sc_defense": ("Свиток защиты", "defense", "amber_altar", [{"m": "defense"}], {}),
    "sc_move": ("Свиток пути", "move", "fog_voices", [{"m": "move"}], {}),
    "sc_curse": ("Свиток проклятия", "curse", "hag_riddle", [{"m": "curse"}], {}),
    "sc_gift": ("Свиток дара", "gift", "sunken_chapel.altar", [{"m": "gift"}], {}),
    "sc_summon": ("Свиток призыва", "summon", "idol", [{"m": "summon"}], {}),
    # редкие: хор (первое действие — ещё и все статуи), перекличка (другой статуей), число раз (×2)
    "sc_attack_chorus": ("Хор гнева", "attack", "cult_initiation", [{"m": "attack"}],
                         {"chorus": True, "say": "*Хор*: *Атака* всеми статуями."}),
    "sc_curse_chorus": ("Хор проклятий", "curse", "fog_doubles", [{"m": "curse"}],
                        {"chorus": True, "say": "*Хор*: *Проклятие* всеми статуями."}),
    "sc_defense_relay": ("Щит и молот", "defense", "hammer_duel", [{"m": "defense"}],
                         {"then": [{"m": "attack", "who": "other"}], "say": "*Защита*, и другая статуя — *Атака*."}),
    "sc_move_relay": ("Перекличка ветров", "move", "smoke_signal", [{"m": "move"}],
                      {"then": [{"m": "curse", "who": "other"}], "say": "*Движение*, и другая статуя — *Проклятие*."}),
    "sc_curse_relay": ("Сглаз и удар", "curse", "witch_envoy", [{"m": "curse"}],
                       {"then": [{"m": "attack", "who": "other"}], "say": "*Проклятие*, и другая статуя — *Атака*."}),
    "sc_gift_relay": ("Подношение", "gift", "village_feast", [{"m": "gift"}],
                      {"then": [{"m": "defense", "who": "other"}], "say": "*Дар*, и другая статуя — *Защита*."}),
    "sc_summon_relay": ("Свита", "summon", "golem_awakening", [{"m": "summon"}],
                        {"then": [{"m": "summon", "who": "other"}], "say": "*Призыв*, и другая статуя — тоже *Призыв*."}),
    "sc_defense_double": ("Двойной оберег", "defense", "sunken_chapel", [{"m": "defense", "n": 2}], {}),
    "sc_gift_double": ("Щедрый дар", "gift", "wisp_hoard", [{"m": "gift", "n": 2}], {}),
}
STATUE = {"perun": "totem_rod", "svarog": "totem_stone_rock", "stribog": "totem_spirit_wise", "yarilo": "totem_heal",
          "veles": "idol", "mokosh": "totem_spirit_might", "morana": "ice_idol", "chernobog": "totem_rage_war"}
PANTHEONS = {
    "storm": {"name": "Гроза и Навь", "gods": ["perun", "veles", "mokosh"],
              "desc": "Перун, Велес, Мокошь: молнии по мокрым, яд и топь, нити судьбы."},
    "forge": {"name": "Кузня и ветер", "gods": ["svarog", "stribog", "yarilo"],
              "desc": "Сварог, Стрибог, Ярило: щиты и молот, ветер толкает, солнце лечит."},
    "winter": {"name": "Зима и тьма", "gods": ["morana", "chernobog", "perun"],
               "desc": "Морана, Чернобог, Перун: мороз по мокрым, тёмные сделки, гроза."},
    "random": {"name": "Случайные боги", "random": 3,
               "desc": "Каждый бой — 3 случайных бога из восьми (проверить всех)."},
}
STARTER = ["sc_attack"] * 3 + ["sc_defense"] * 2 + ["sc_move", "sc_curse", "sc_gift", "sc_summon",
                                                  "sc_defense_relay"]
REWARDS = list(SCROLLS)          # для торговца и проверок; награды Жреца создаются под глубину (deck/idols.py)


def main():
    p = os.path.join(D, "cards.json")
    c = json.load(open(p, encoding="utf-8"))
    cards = c["cards"]
    for k in [k for k in cards if k.startswith("sc_")]:
        del cards[k]
    from deck.idols import scroll_text
    for cid, (name, m, ill, acts, extra) in SCROLLS.items():
        extra = dict(extra)
        say = extra.pop("say", None) or scroll_text(acts)
        cards[cid] = dict({"ill": [ill, 0.5, 0.5, 0.5], "art": cards["strike"].get("art", ""), "name": name, "cost": 0,
                           "type": FRAME[m], "meaning": m, "acts": acts, "main": {"target": "statue", "say": say},
                           "alt": {"target": "none"}}, **extra)
    json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    p = os.path.join(D, "heroes.json")
    h = json.load(open(p, encoding="utf-8"))
    h["heroes"]["priest"] = {
        "name": "Жрец", "sprite": "priest", "hp": 52, "energy": 0, "mechanic": "idols",
        "about": "Сам не бьёт — молится. Статуи его богов падают на поле, свитки исполняет бог статуи.",
        "rule": "Свиток тянут на статую — бог исполняет все его действия по-своему; ступень I–IV — новый эффект. "
                "Свитки бесплатны, +2 за ход (до 5). Ходит на 3. Глубже — свитки толще.",
        "passives": PANTHEONS, "starter": STARTER, "rewards": REWARDS}
    if "priest" not in h["order"]:
        h["order"].append("priest")
    json.dump(h, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    p = os.path.join(D, "gods.json")
    g = json.load(open(p, encoding="utf-8"))
    for gid, spr in STATUE.items():
        if gid in g["gods"]:
            g["gods"][gid]["statue"] = spr
    json.dump(g, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ok: свитков", len(SCROLLS), "· жрец в порядке героев:", h["order"])


if __name__ == "__main__":
    main()
