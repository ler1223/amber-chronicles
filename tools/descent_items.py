"""Предметы «Спуска» (квиз 2026-11-21): как реликвии Slay the Spire — срабатывают при редком условии.

Старые 12 реликвий убраны. Дары богов на карты убраны: алтари стали сундуками. Редкость: обычные, необычные,
редкие (сундук, элита, торговец), «предметы стража» — сильные, но с минусом, и товары торговца. Общие + классовые
(hero). Формат — deck/items.py.

Пишет data/deck/relics.json. Запуск: python tools/descent_items.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def op(name, n=None, **kw):
    o = {"op": name}
    if n is not None:
        o["n"] = n
    o.update(kw)
    return o


def W(k, n=None):
    w = {"k": k}
    if n is not None:
        w["n"] = n
    return w


def item(name, icon, rarity, about, on=None, *do, hero=None, **kw):
    r = {"name": name, "icon": icon, "rarity": rarity, "about": about}
    if on:
        r["on"] = on
        r["do"] = list(do)
    if hero:
        r["hero"] = hero
    r.update(kw)
    return r


RES, RES2 = "{res}", "{res2}"        # энергия / жар / свиток — подставляет deck/items.about по герою
ITEMS = {
    # ---------- обычные ----------
    "pen_nib": item("Перо-наконечник", "relic_whetstone", "common",
                    "Каждая 10-я сыгранная атака (счёт идёт через все бои): следующая атака — двойной урон.",
                    "play", op("double_next"), type="attack", count=10, scope="run"),
    "horn_cleat": item("Боевой рог", "necro_c_banner", "common", "Каждый 5-й ход боя: 16 защиты.",
                       "turn", op("block", 16), every=5),
    "wheel": item("Штурвал", "art_belt_common", "common", "На 3-м ходу, если врагов всё ещё 3+: 18 защиты.",
                  "turn", op("block", 18), turn=3, when=[W("foes_min", 3)]),
    "bog_flower": item("Болотный цветок", "mat_herbs", "common", f"Каждый 6-й ход боя: +3 {RES2}.",
                       "turn", op("resource", 3), every=6),
    "puzzle": item("Старая головоломка", "gem_topaz", "common",
                   "HP впервые за бой падает ниже половины: взять 3 карты.", "hp_low", op("draw", 3)),
    "inkwell": item("Чернильница", "item_seal", "common",
                    "Каждая 15-я сыгранная карта (через все бои): взять 2 карты.",
                    "play", op("draw", 2), count=15, scope="run"),
    "spin_top": item("Волчок", "item_charm", "common", "Сыграли последнюю карту из руки: взять карту.",
                     "play", op("draw", 1), when=[W("hand_empty")]),
    "war_treatise": item("Трактат о войне", "gift_word_power", "common",
                         f"Ход без единой атаки, но с 3+ сыгранными картами: в следующий ход +1 {RES}.",
                         "end", op("next_energy", 1), when=[W("no_attack"), W("played_min", 3)]),
    "pocketwatch": item("Карманные часы", "art_amulet_common", "common",
                        "Сыграли за ход 1 карту или ни одной: в следующий ход +3 карты.",
                        "end", op("next_draw", 3), when=[W("played_max", 1)]),
    "fan": item("Резной веер", "relic_wanderer_cloak", "common", "Каждое 3-е умение за ход: 4 защиты.",
                "play", op("block", 4), type="skill", count=3, scope="turn"),
    "letter_knife": item("Нож для писем", "item_dagger", "common",
                         "Каждое 3-е умение за ход: 5 урона всем врагам.",
                         "play", op("damage", 5), type="skill", count=3, scope="turn", aim="all"),
    "shuriken": item("Звёздочка", "necro_s_backstab", "common", "Каждая 4-я атака за ход: +1 мощь до конца боя.",
                     "play", op("strength", 1), type="attack", count=4, scope="turn"),
    "kunai": item("Кунай", "necro_s_shadow", "common", "Каждая 4-я атака за ход: контратака 3.",
                  "play", op("counter", 3), type="attack", count=4, scope="turn"),
    "sundial": item("Солнечные часы", "gift_spare_time", "common",
                    f"Каждая 3-я перетасовка колоды за бой: +2 {RES2}.",
                    "shuffle", op("resource", 2), count=3, scope="battle"),
    # ---------- необычные ----------
    "red_skull": item("Красный череп", "necro_r_death_blast", "uncommon",
                      "HP впервые за бой падает ниже половины: +3 мощи.", "hp_low", op("strength", 3)),
    "gremlin_horn": item("Рог гремлина", "gift_pack_call", "uncommon",
                         f"Двое убиты за один ход: +1 {RES} и 2 карты.",
                         "kill", op("resource", 1), op("draw", 2), when=[W("kills_turn", 2)], once="turn"),
    "charon_ash": item("Пепел Харона", "mat_bonedust", "uncommon", "Карта изгнана: 3 урона всем врагам.",
                       "exhaust", op("damage", 3), aim="all"),
    "dry_branch": item("Сухая ветвь", "gift_bog_roots", "uncommon",
                       "Карта изгнана: в руку случайная карта вашего класса (до конца боя).",
                       "exhaust", op("add_random", 1)),
    "herb_pills": item("Пилюли травника", "fx_heal_taken", "uncommon",
                       f"Сыграли за ход атаку, умение и Силу: снять слабость и уязвимость, +1 {RES}, карта.",
                       "play", op("cleanse"), op("resource", 1), op("draw", 1), when=[W("trio")], once="turn"),
    "last_stand": item("Знамя последнего", "gift_last_stand", "uncommon",
                       "Остался последний враг, а у вас HP ниже половины: +3 мощи и 12 защиты.",
                       "last_foe", op("strength", 3), op("block", 12), when=[W("hp_below", 50)], once="battle"),
    "bandage": item("Тугая повязка", "fx_tough", "uncommon",
                    "Конец хода, в руке 2+ карты с Сохранением: 8 защиты.",
                    "end", op("block", 8), when=[W("retained", 2)]),
    "boots": item("Сапоги скорохода", "gift_elusive_step", "uncommon",
                  f"Каждая 12-я клетка, пройденная за бой: +1 {RES}.",
                  "step", op("resource", 1), count=12, scope="battle"),
    "still_pool": item("Тихий омут", "gift_reed_shadow", "uncommon",
                       "Ход, в котором вы не двигались и не атаковали: 10 защиты.",
                       "end", op("block", 10), when=[W("not_walked"), W("no_attack")]),
    "fort_stone": item("Крепостной камень", "fx_sanctuary", "uncommon",
                       "Конец хода с 15+ защиты: половина защиты останется на следующий ход.",
                       "end", op("fort", 1), when=[W("shield_min", 15)]),
    "blood_vial": item("Склянка крови", "gift_amber_blood", "uncommon",
                       "Бой начинается при HP ниже половины: лечение 6 и +2 мощи.",
                       "battle", op("heal", 6), op("strength", 2), when=[W("hp_below", 50)]),
    "fate_thread": item("Нить судьбы", "gift_fate_threads", "uncommon",
                        "Колода перетасована, когда у вас HP ниже половины: 8 защиты и 2 карты.",
                        "shuffle", op("block", 8), op("draw", 2), when=[W("hp_below", 50)]),
    # ---------- редкие ----------
    "lizard_tail": item("Хвост ящерицы", "gift_second_wind", "rare",
                        "Раз за забег: смертельный удар оставляет вас с половиной HP.", mods={"revive": 1}),
    "censer": item("Курильница", "fx_prayer", "rare", f"Каждый 6-й ход боя: 25 защиты и +1 {RES}.",
                   "turn", op("block", 25), op("resource", 1), every=6),
    "nunchaku": item("Нунчаки", "item_staff", "rare",
                     f"Каждая 10-я сыгранная атака (через все бои): +1 {RES}.",
                     "play", op("resource", 1), type="attack", count=10, scope="run"),
    "two_faced": item("Двуликий идол", "item_idol", "rare", f"Сыграли 6 карт за ход: +1 {RES} и 6 защиты.",
                      "play", op("resource", 1), op("block", 6), when=[W("played_min", 6)], once="turn"),
    "bells": item("Колокольцы", "gift_perfect_pitch", "rare",
                  "Каждая 5-я созданная за бой карта: 6 урона ближайшему врагу и карта.",
                  "create", op("damage", 6), op("draw", 1), count=5, scope="battle", aim="nearest"),
    "snake_skull": item("Змеиный череп", "necro_m_souls", "rare",
                        "Бой начинается против 4+ врагов: все враги уязвимы 3 хода.",
                        "battle", op("vulnerable", 3), when=[W("foes_min", 4)], aim="all"),
    "calendar": item("Каменный календарь", "relic_soul_catcher", "rare", "На 7-м ходу боя: 40 урона всем врагам.",
                     "turn", op("damage", 40), turn=7, aim="all"),
    # ---------- предметы стража: сильные, с минусом ----------
    "black_crown": item("Чёрная корона", "art_amulet_legendary", "boss",
                        f"+1 {RES} каждый ход. Минус: в начале боя в колоду замешаны 2 «Тины».",
                        mods={"energy": 1, "slime": 2}),
    "velvet_collar": item("Бархатный ошейник", "art_ring_legendary", "boss",
                          f"+1 {RES} каждый ход. Минус: за ход можно сыграть основным не больше 6 карт.",
                          mods={"energy": 1, "play_limit": 6}),
    "kettle": item("Котелок бодрости", "relic_boiling_pot", "boss",
                   f"+1 {RES} каждый ход. Минус: у костра нельзя отдохнуть.", mods={"energy": 1, "no_camp_heal": 1}),
    "cursed_key": item("Проклятый ключ", "art_talisman_legendary", "boss",
                       f"+1 {RES} каждый ход. Минус: враги начинают бой с +1 мощью.",
                       mods={"energy": 1, "foe_strength": 1}),
    "rune_pyramid": item("Руническая пирамида", "gem_amethyst", "boss",
                         "Карты не сбрасываются в конце хода. Минус: в начале хода на 1 карту меньше.",
                         mods={"retain_all": 1, "hand": -1}),
    "phylactery": item("Филактерия", "relic_iron_vow", "boss",
                       f"+1 {RES} каждый ход. Минус: в начале каждого боя −6 HP.", mods={"energy": 1, "start_hp": 6}),
    "greed_eye": item("Око жадности", "gem_ruby", "boss",
                      f"+1 {RES} каждый ход. Минус: в награду за бой — на 1 карту меньше на выбор.",
                      mods={"energy": 1, "fewer_rewards": 1}),
    # ---------- Наёмник ----------
    "m_whet": item("Точило разгона", "relic_whetstone", "uncommon", "Удар с Разгоном 5: цель оглушена.",
                   "play", op("stun"), hero="merc", tag="Удар", when=[W("momentum_min", 5)], aim="target"),
    "m_gutter": item("Кровосток", "gift_blood_thirst", "uncommon",
                     "Враг гибнет с кровотечением 6+: его кровотечение переходит соседям.",
                     "kill", op("spread", what="bleed"), hero="merc", when=[W("victim_bleed", 6)], aim="around"),
    "m_mirror": item("Зерцало дуэлянта", "gift_duel_honor", "rare",
                     "3 контратаки за один ход врагов: +1 мощь до конца боя.",
                     "counter", op("strength", 1), hero="merc", count=3, scope="turn"),
    "m_heavy_shield": item("Тяжёлый щит", "necro_g_shield", "common", "Конец хода с 20+ защиты: контратака 3.",
                           "end", op("counter", 3), hero="merc", when=[W("shield_min", 20)]),
    "m_trophy": item("Трофейный пояс", "art_belt_epic", "rare", "Трое убиты за один ход: +2 мощи до конца боя.",
                     "kill", op("strength", 2), hero="merc", when=[W("kills_turn", 3)], once="turn"),
    "m_spurs": item("Шпоры", "gift_battering", "common",
                    "Каждая 20-я клетка, пройденная за бой: следующая атака — двойной урон.",
                    "step", op("double_next"), hero="merc", count=20, scope="battle"),
    # ---------- Охотница ----------
    "h_raven": item("Вороново оперение", "arrow_piercing", "uncommon",
                    "Каждая 6-я сыгранная Стрела (через все бои): следующая атака — двойной урон.",
                    "play", op("double_next"), hero="hunter", card="arrow", count=6, scope="run"),
    "h_horn": item("Охотничий рог", "relic_war_drum", "uncommon", f"Враг попал в капкан: 2 карты и +1 {RES}.",
                   "trap", op("draw", 2), op("resource", 1), hero="hunter"),
    "h_owl": item("Глаз совы", "gift_far_sight", "common", "Выстрел с 7+ клеток: метка 6 на цель (раз за ход).",
                  "play", op("mark", 6), hero="hunter", tag="Выстрел", when=[W("far", 7)], aim="target", once="turn"),
    "h_hide": item("Засидка", "item_leather", "common",
                   "Ход без движения: в следующий ход +1 карта, следующий выстрел ×2.",
                   "end", op("next_draw", 1), op("focus"), hero="hunter", when=[W("not_walked")]),
    "h_fang": item("Ядовитый клык", "item_fang", "uncommon", "Враг гибнет отравленным 5+: его яд переходит соседям.",
                   "kill", op("spread", what="poison"), hero="hunter", when=[W("victim_poison", 5)], aim="around"),
    "h_quiver": item("Бездонный колчан", "arrow_storm", "rare", f"Каждая 8-я созданная за бой карта: +2 {RES2}.",
                     "create", op("resource", 2), hero="hunter", count=8, scope="battle"),
    # ---------- Пиромантка ----------
    "p_crucible": item("Горнило", "mat_emberheart", "uncommon",
                       "Перегрев не ранит: лишний жар уходит горением ×2 всем врагам.", hero="pyro",
                       mods={"overheat_burn": 1}),
    "p_flint": item("Кремень", "mat_ember", "common", "Каждая 5-я Искра за бой: +2 жара.",
                    "play", op("resource", 2), hero="pyro", card="t_spark", count=5, scope="battle"),
    "p_urn": item("Пепельная урна", "gift_ash_heart", "rare",
                  "Каждая 3-я изгнанная за бой карта: +1 жар в начале каждого хода до конца боя.",
                  "exhaust", op("heat_regen", 1), hero="pyro", count=3, scope="battle"),
    "p_salamander": item("Саламандра в банке", "gift_fire_soul", "uncommon",
                         "Враг гибнет с горением 6+: его горение переходит соседям.",
                         "kill", op("spread", what="burn"), hero="pyro", when=[W("victim_burn", 6)], aim="around"),
    "p_melt": item("Плавильный тигель", "art_talisman_rare", "uncommon", "Карта за 4+ жара: взять 2 карты.",
                   "play", op("draw", 2), hero="pyro", when=[W("heat_min", 4)]),
    "p_cold_heart": item("Остывшее сердце", "gift_frost_soul", "common",
                         "Конец хода с 0 жара после 4+ сыгранных карт: в следующий ход +2 карты и +1 жар.",
                         "end", op("next_draw", 2), op("next_energy", 1), hero="pyro",
                         when=[W("heat_zero"), W("played_min", 4)]),
    # ---------- Жрец ----------
    "i_beads": item("Чётки", "item_band", "uncommon", "Четвёртый свиток в одну статую за ход: 2 свитка и 8 защиты.",
                    "scroll", op("draw", 2), op("block", 8), hero="priest", when=[W("same_statue", 4)], once="turn"),
    "i_bear": item("Медвежий оберег", "gift_warden", "common",
                   "Осквернена третья статуя за бой: 15 защиты и 2 свитка.",
                   "desecrated", op("block", 15), op("draw", 2), hero="priest", count=3, scope="battle"),
    "i_candle": item("Свеча бдения", "fx_vow", "common",
                     "Ход, в котором свитки получили все статуи: в следующий ход +1 свиток.",
                     "end", op("next_draw", 1), hero="priest", when=[W("all_fed")]),

    # ---------- предметы под теги: пассивная прибавка и свойства ----------
    "shot_eye": item("Меткий глаз", "gift_sharp_eye", "common",
                     "Карты [Выстрел]: +2 урона.", hero="hunter",
                     tag_bonus=[{"tag": "Выстрел", "damage": 2}]),
    "melee_whet": item("Точильный камень", "relic_whetstone", "common",
                       "Карты [Удар]: +2 урона.", hero="merc",
                       tag_bonus=[{"tag": "Удар", "damage": 2}]),
    "fire_ember": item("Пепельный уголёк", "mat_ember", "common",
                       "Карты [Огонь]: +2 урона.", hero="pyro",
                       tag_bonus=[{"tag": "Огонь", "damage": 2}]),
    "block_buckle": item("Крепкая пряжка", "art_belt_common", "common",
                         "Карты [Защита]: +2 защиты.",
                         tag_bonus=[{"tag": "Защита", "block": 2}]),
    "blood_edge": item("Алый клинок", "item_dagger", "uncommon",
                       "Карты [Кровь]: +3 урона.", hero="merc",
                       tag_bonus=[{"tag": "Кровь", "damage": 3}]),
    "mark_scope": item("Метка охотника", "gift_prey", "uncommon",
                       "Карты [Метка]: +3 урона; первая [Метка] за ход кладёт ещё 2 метки.",
                       "play", op("mark", 2), hero="hunter", tag="Метка", once="turn", aim="target",
                       tag_bonus=[{"tag": "Метка", "damage": 3}]),
    "combo_drum": item("Барабан цепи", "relic_war_drum", "uncommon",
                       "Карты [Комбо]: +2 урона; первая [Комбо] за ход даёт +1 {res}.",
                       "play", op("resource", 1), tag="Комбо", once="turn",
                       tag_bonus=[{"tag": "Комбо", "damage": 2}]),
    "script_seal": item("Печать писца", "item_seal", "common",
                        "Первый [Свиток] за ход: взять карту.", "scroll", op("draw", 1),
                        hero="priest", tag="Свиток", once="turn"),
    "resonance_bell": item("Колокол резонанса", "gift_perfect_pitch", "rare",
                           "Карты [Резонанс] и [Цепочка]: +3 урона; первая [Цепочка] за ход даёт +1 {res}.",
                           "play", op("resource", 1), tag="Цепочка", once="turn",
                           tag_bonus=[{"tags": ["Резонанс", "Цепочка"], "damage": 3}]),
    "shot_focus": item("Оптика следопыта", "gift_far_sight", "rare",
                       "Первый [Выстрел] за ход: следующий выстрел ×2.", "play", op("focus"),
                       hero="hunter", tag="Выстрел", once="turn"),
    "fire_heart": item("Тлеющее сердце", "gift_fire_soul", "rare",
                       "Карты [Огонь]: +2 урона; первая [Огонь] за ход поджигает цель на 1.",
                       "play", op("burn", 1), hero="pyro", tag="Огонь", once="turn", aim="target",
                       tag_bonus=[{"tag": "Огонь", "damage": 2}]),
    "combo_echo": item("Раковина эха", "item_charm", "rare",
                       "Первая [Комбо] за ход: следующая атака — двойной урон.",
                       "play", op("double_next"), tag="Комбо", once="turn"),
    "weak_point": item("Слабое место", "gift_far_sight", "rare",
                       "Карты [Клич]: +2 урона; первая [Клич] за ход накладывает 2 уязвимости.",
                       "play", op("vulnerable", 2), hero="hunter", tag="Клич", once="turn", aim="target",
                       tag_bonus=[{"tag": "Клич", "damage": 2}]),
    "chain_quiver": item("Колчан эха", "arrow_storm", "rare",
                         "Карты [Цепочка]: +2 урона; первая цепочка за ход берёт карту.",
                         "chain", op("draw", 1), hero="hunter", tag="Цепочка", once="turn",
                         tag_bonus=[{"tag": "Цепочка", "damage": 2}]),
    "hunt_horn": item("Рог преследования", "gift_prey", "rare",
                      "Карты [Преследование]: +2 урона; первая [Преследование] за ход даёт +1 преследование.",
                      "play", op("hunt", 1), tag="Преследование", once="turn",
                      tag_bonus=[{"tag": "Преследование", "damage": 2}]),
    "area_seal": item("Печать области", "item_charm", "rare",
                      "Карты [Область]: +2 урона; первая [Область] за ход даёт +1 {res}.",
                      "play", op("resource", 1), tag="Область", once="turn",
                      tag_bonus=[{"tag": "Область", "damage": 2}]),
    "retain_box": item("Ларец сохранения", "item_seal", "uncommon",
                       "Карты [Сохранение]: +3 защиты; первая [Сохранение] за ход берёт карту.",
                       "play", op("draw", 1), tag="Сохранение", once="turn",
                       tag_bonus=[{"tag": "Сохранение", "block": 3}]),
}


def main():
    p = os.path.join(ROOT, "data", "deck", "relics.json")
    data = {"_doc": "Предметы забега (как реликвии StS): срабатывают только при редком условии. Формат — "
                    "deck/items.py; пишет tools/descent_items.py.",
            "relics": ITEMS}
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    print("предметов:", len(ITEMS), dict(Counter(r["rarity"] for r in ITEMS.values())),
          dict(Counter(r.get("hero", "все") for r in ITEMS.values())))


if __name__ == "__main__":
    main()
