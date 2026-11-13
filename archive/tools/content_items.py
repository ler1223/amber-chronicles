"""Генератор предметов: дописывает новые предметы в data/items.json (существующие id не трогает).
python tools/content_items.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from content_heroes import append  # noqa: E402


def item(name, slot, rarity, price, desc, *mods):
    return {"name": name, "slot": slot, "rarity": rarity, "price": price, "desc": desc, "mods": list(mods)}


def st(stat, add=None, mult=None):
    m = {"stat": stat}
    if add is not None:
        m["add"] = add
    if mult is not None:
        m["mult"] = mult
    return m


W, A, T = "weapon", "armor", "trinket"
ITEMS = {
    # оружие
    "storm_spear": item("Копьё грозы", W, "common", 55, "Атаки с тегом Гроза", {"attack_tag": "storm"}),
    "venom_dagger": item("Отравленный кинжал", W, "common", 50, "Атаки с тегом Яд", {"attack_tag": "poison"}),
    "smith_hammer": item("Кузнечный молот", W, "common", 45, "+3 к урону атаки, +1 броня",
                         st("atk_damage", 3), st("armor", 1)),
    "rapier": item("Рапира", W, "common", 50, "Атаки на 20% чаще", st("atk_cooldown", mult=0.8)),
    "long_spear": item("Длинная пика", W, "rare", 85, "+1 дальность атаки, +2 к урону атаки",
                       st("atk_range", 1), st("atk_damage", 2)),
    "thunder_rod": item("Громовой жезл", W, "rare", 85, "Атаки с тегом Гроза, +15% сила навыков",
                        {"attack_tag": "storm"}, st("power", mult=1.15)),
    "bone_flute": item("Костяная флейта", W, "rare", 80, "+15% сила навыков, AP на 0.4 сек быстрее",
                       st("power", mult=1.15), st("ap_regen", -0.4)),
    "shadow_blade": item("Клинок тени", W, "rare", 90, "+5 к урону атаки, +1 деление шкалы", st("atk_damage", 5), st("pp_max", 1)),
    "seasons_staff": item("Посох времён года", W, "epic", 140, "+20% сила навыков, +2 AP",
                          st("power", mult=1.2), st("ap_max", 2)),
    "storm_axe": item("Топор бури", W, "epic", 135, "Атаки с тегом Гроза, +8 к урону атаки, атаки на 10% чаще",
                      {"attack_tag": "storm"}, st("atk_damage", 8), st("atk_cooldown", mult=0.9)),
    # броня
    "leather_vest": item("Кожаный жилет", A, "common", 40, "+1 броня, движение на 10% быстрее",
                         st("armor", 1), st("move_time", mult=0.9)),
    "storm_cloak": item("Плащ громовержца", A, "common", 50, "Урон с тегом Гроза ×0.5, +15 HP",
                        {"resist": "storm", "mult": 0.5}, st("hp", 15)),
    "herbalist_robe": item("Мантия знахаря", A, "common", 50, "Урон с тегом Яд ×0.4, +1 броня",
                           {"resist": "poison", "mult": 0.4}, st("armor", 1)),
    "pilgrim_robe": item("Ряса пилигрима", A, "common", 45, "+1 деление шкалы, +10 HP", st("pp_max", 1), st("hp", 10)),
    "fireproof_apron": item("Огнеупорный фартук", A, "common", 50, "Урон Огнём ×0.6 и Маслом ×0.5",
                            {"resist": "fire", "mult": 0.6}, {"resist": "oil", "mult": 0.5}),
    "scale_mail": item("Чешуйчатый доспех", A, "rare", 85, "+3 брони, движение на 10% медленнее",
                       st("armor", 3), st("move_time", mult=1.1)),
    "bark_armor": item("Доспех из коры", A, "rare", 85, "+35 HP, шкала сама растёт на 0.5 сек быстрее", st("hp", 35), st("pp_regen", -0.5)),
    "shadow_cloak": item("Плащ теней", A, "rare", 90, "Движение на 15% быстрее, +1 деление шкалы",
                         st("move_time", mult=0.85), st("pp_max", 1)),
    "giant_belt": item("Пояс великана", A, "epic", 135, "+60 HP, +2 брони", st("hp", 60), st("armor", 2)),
    "elemental_plate": item("Доспех стихий", A, "epic", 140, "Урон Огнём, Льдом и Грозой ×0.6, +2 брони",
                            {"resist": "fire", "mult": 0.6}, {"resist": "ice", "mult": 0.6},
                            {"resist": "storm", "mult": 0.6}, st("armor", 2)),
    # амулеты: чужие навыки и превращения тегов
    "oil_pouch": item("Сумка масла", T, "common", 55, "Навык: Масляная склянка", {"new_skill": "oil_flask"}),
    "venom_vial": item("Склянка яда", T, "common", 55, "Навык: Ядовитый клинок", {"new_skill": "venom_blade"}),
    "grappling_hook": item("Абордажный крюк", T, "common", 55, "Навык: Крюк", {"new_skill": "hook"}),
    "thunder_charm": item("Оберег грозы", T, "common", 50, "Весь огонь героя становится Грозой",
                          {"convert_tag": ["fire", "storm"]}),
    "bog_ring": item("Кольцо болота", T, "common", 50, "Вся вода героя становится Ядом", {"convert_tag": ["water", "poison"]}),
    "totem_carving": item("Резной тотем", T, "rare", 85, "Навык: Тотем исцеления", {"new_skill": "healing_totem"}),
    "travel_lute": item("Походная лютня", T, "rare", 80, "Навык: Боевая песнь", {"new_skill": "war_song"}),
    "smoke_pellets": item("Дымовые шарики", T, "rare", 80, "Навык: Исчезновение", {"new_skill": "vanish"}),
    "seer_eye": item("Око провидца", T, "rare", 80, "шкала сама растёт на 0.8 сек быстрее", st("pp_regen", -0.8)),
    "phoenix_feather": item("Перо феникса", T, "epic", 150, "Навык: Воскрешение, +20 HP",
                            {"new_skill": "revive"}, st("hp", 20)),
    "hourglass": item("Песочные часы", T, "epic", 140, "Все касты ×0.6, перезарядки ×0.7",
                      {"skill": "*", "cast_mult": 0.6, "cooldown_mult": 0.7}),
}

if __name__ == "__main__":
    append("items.json", ITEMS, "line")
