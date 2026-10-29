"""Генератор глав: враги (с обликом для заглушек спрайтов), навыки врагов, призывы, столкновения с картами,
регионы глав, сложности и модификаторы. Дописывает data/*.json (существующие id не трогает).

python tools/content_chapters.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from content_heroes import upsert, write  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def look(body, color, accent=None, head="none", weapon="none", **kw):
    return dict(body=body, color=color, accent=accent or color, head=head, weapon=weapon, **kw)


def E(name, label, role, hp, atk, lk, rng=1, cd=1.3, armor=0, move=0.55, tag=None, skills=(), **kw):
    a = {"damage": atk, "range": rng, "cooldown": cd}
    if tag:
        a["tag"] = tag
    if kw.pop("reach", False):
        a["kind"] = "melee"
    p = {"name": name, "label": label, "color": lk["color"], "role": role, "hp": hp, "armor": armor, "move_time": move,
         "attack": a, "ap_max": 6, "ap_regen": 5.0, "skills": list(skills), "look": lk}
    p.update(kw)
    return p


def sk(name, desc, ap, target, effects, ai, rng=0, cast=0.0, cd=0, radius=None, **kw):
    s = {"name": name, "ap": ap, "cast": cast, "cooldown": cd, "range": rng, "target": target, "ai": ai}
    if radius is not None:
        s["radius"] = radius
    s["auto"] = {"on": False, "conds": []}
    s["effects"] = effects
    s["desc"] = desc
    s.update(kw)
    return s


def D(amount, kind="spell", radius=None, tag=None, **kw):
    e = {"type": "damage", "amount": amount, "kind": kind}
    if radius:
        e["radius"] = radius
    if tag:
        e["tag"] = tag
    e.update(kw)
    return e


ENEMY_SKILLS = {
    "e_fireball": sk("Огненный шар", "Радиус 1: 18 урона + Огонь, центр горит.", 4, "cell",
                     [D(18, radius=1, tag="fire"), {"type": "hazard", "hazard": "fire", "duration": 3}], "cluster",
                     rng=5, cast=1.5, cd=8, radius=1, min_targets=1),
    "e_hammer": sk("Бросок молота", "12 урона и оглушение 0.8 сек.", 3, "enemy",
                   [D(12, "ranged"), {"type": "stun", "duration": 0.8}], "enemy_in_range", rng=4, cd=10),
    "e_flame_breath": sk("Огненное дыхание", "Радиус 1 у цели: 12 урона + Огонь.", 3, "enemy",
                         [D(12, radius=1, tag="fire")], "enemy_in_range", rng=2, cd=6),
    "e_lash": sk("Цепной хлыст", "Притягивает на 2 клетки, 12 урона.", 3, "enemy",
                 [{"type": "pull", "cells": 2}, D(12, "melee")], "enemy_in_range", rng=3, cd=7),
    "e_meteor": sk("Метеоритный дождь", "Каст 2 сек, радиус 2: 30 урона + Огонь, земля горит.", 5, "cell",
                   [D(30, radius=2, tag="fire"), {"type": "hazard", "hazard": "fire", "duration": 4, "radius": 1}],
                   "cluster", rng=5, cast=2.0, cd=10, radius=2, min_targets=1),
    "e_raise": sk("Поднять мертвецов", "Поднимает скелета (до 2).", 3, "self",
                  [{"type": "summon", "unit": "skeleton_minion", "duration": 25, "limit": 2}], "summon_self", cd=10),
    "e_raise_lich": sk("Армия костей", "Поднимает скелета (до 3).", 3, "self",
                       [{"type": "summon", "unit": "skeleton_minion", "duration": 30, "limit": 3}], "summon_self", cd=8),
    "e_wither": sk("Иссушающее проклятие", "10 урона, лечение цели вдвое слабее 6 сек.", 3, "enemy",
                   [D(10), {"type": "buff", "stat": "heal_taken", "value": 0.5, "duration": 6, "affects": "enemies"}],
                   "enemy_in_range", rng=4, cd=6),
    "e_wail": sk("Вопль", "Радиус 2: 8 урона и оглушение 1 сек.", 3, "self",
                 [D(8, radius=2), {"type": "stun", "duration": 1.0, "radius": 2}], "adjacent_foes", cd=9, radius=2),
    "e_slam": sk("Удар о землю", "Враги рядом: 18 урона и оглушение 0.8 сек.", 3, "self",
                 [D(18, "melee", radius=1), {"type": "stun", "duration": 0.8, "radius": 1}], "adjacent_foes", cd=8,
                 radius=1),
    "e_frost_ward": sk("Ледяной оберег", "Союзнику щит 30 на 8 сек.", 3, "ally",
                       [{"type": "shield", "amount": 30, "duration": 8}], "shield_ally", rng=4, cd=7),
    "e_frost_breath": sk("Ледяное дыхание", "Радиус 1: 16 урона + Лёд.", 3, "cell",
                         [D(16, radius=1, tag="ice")], "cluster", rng=3, cd=6, radius=1, min_targets=1),
    "e_avalanche": sk("Сход лавины", "Каст 1.5 сек, радиус 1: 26 урона + Лёд, оглушение 1.2 сек.", 4, "cell",
                      [D(26, radius=1, tag="ice"), {"type": "stun", "duration": 1.2, "radius": 1}], "cluster",
                      rng=5, cast=1.5, cd=9, radius=1, min_targets=1),
    "e_charge": sk("Набег", "Прыжок к врагу (до 4): 16 урона.", 3, "enemy",
                   [{"type": "leap_to"}, D(16, "melee")], "enemy_in_range", rng=4, cd=6),
    "e_rain": sk("Ливень", "Радиус 1: Вода на героев (молния по мокрым — электрошок).", 2, "cell",
                 [{"type": "status", "tag": "water", "radius": 1}], "cluster", rng=5, cd=7, radius=1, min_targets=1),
    "e_chain": sk("Цепная молния", "16 урона + Гроза, перескакивает на 2 (12).", 3, "enemy",
                  [D(16, tag="storm"), {"type": "chain", "jumps": 2, "range": 3, "amount": 12, "tag": "storm"}],
                  "enemy_in_range", rng=5, cast=0.6, cd=4),
    "e_war_cry": sk("Клич орды", "Союзники в радиусе 3: атаки ×1.3 на 8 сек.", 3, "self",
                    [{"type": "buff", "stat": "atk_mult", "value": 1.3, "duration": 8, "radius": 3}], "self_buff",
                    cd=14, radius=3),
    "e_thunderstorm": sk("Буря", "Каст 1.6 сек, радиус 2: 24 урона + Гроза, оглушение 0.5 сек.", 5, "cell",
                         [D(24, radius=2, tag="storm"), {"type": "stun", "duration": 0.5, "radius": 2}], "cluster",
                         rng=5, cast=1.6, cd=10, radius=2, min_targets=1),
    "e_club": sk("Дубина", "22 урона и отбрасывание на 2.", 3, "enemy",
                 [D(22, "melee"), {"type": "knockback", "cells": 2}], "enemy_in_range", rng=1, cd=7),
    "e_heal": sk("Исцеление", "Лечит союзника на 40.", 3, "ally", [{"type": "heal", "amount": 40}], "heal_ally",
                 rng=4, cast=0.8, cd=4),
    "e_plague": sk("Чумное облако", "Радиус 1: 10 урона + Яд, ядовитое облако 5 сек.", 3, "cell",
                   [D(10, radius=1, tag="poison"), {"type": "hazard", "hazard": "poison", "duration": 5, "radius": 1}],
                   "cluster", rng=4, cd=8, radius=1, min_targets=1),
    "e_raise_mummy": sk("Восстание мумий", "Поднимает мумию (до 2).", 3, "self",
                        [{"type": "summon", "unit": "mummy_risen", "duration": 30, "limit": 2}], "summon_self", cd=12),
    "e_charm": sk("Очарование", "Герой 3 сек сражается за врага.", 3, "enemy",
                  [{"type": "charm", "duration": 3}], "enemy_in_range", rng=4, cd=14),
    "e_mirror": sk("Зеркальный образ", "Создаёт двойника-иллюзию (до 2).", 2, "self",
                   [{"type": "summon", "unit": "illusion", "duration": 10, "limit": 2}], "summon_self", cd=9),
    "e_regrowth": sk("Рост", "Союзник: 8 HP/сек 5 сек.", 3, "ally",
                     [{"type": "buff", "stat": "regen", "value": 8, "duration": 5}], "heal_ally", rng=4, cd=5),
    "e_entangle": sk("Оплетание", "Радиус 1: 8 урона и оглушение 1.2 сек.", 3, "cell",
                     [D(8, radius=1), {"type": "stun", "duration": 1.2, "radius": 1}], "cluster", rng=4, cd=9, radius=1,
                     min_targets=1),
    "e_sleep": sk("Песнь сирены", "Радиус 1: сон 3 сек.", 3, "cell", [{"type": "sleep", "duration": 3, "radius": 1}],
                  "cluster", rng=4, cast=0.6, cd=11, radius=1, min_targets=1),
    "e_drag": sk("Утащить на дно", "Притягивает на 3 клетки и оглушает 1 сек.", 3, "enemy",
                 [{"type": "pull", "cells": 3}, {"type": "stun", "duration": 1.0}], "enemy_in_range", rng=4, cd=9),
    "e_claw": sk("Клешня", "20 урона и отбрасывание.", 3, "enemy", [D(20, "melee"), {"type": "knockback", "cells": 1}],
                 "enemy_in_range", rng=1, cd=6),
    "e_tidal": sk("Волна", "Каст 1.5 сек, радиус 2: 20 урона + Вода, отбрасывание.", 4, "cell",
                  [D(20, radius=2, tag="water"), {"type": "knockback", "cells": 1, "radius": 2}], "cluster",
                  rng=5, cast=1.5, cd=10, radius=2, min_targets=1),
    "e_shield_push": sk("Таран щитом", "16 урона и отбрасывание на 2 — к краю пропасти.", 3, "enemy",
                        [D(16, "melee"), {"type": "knockback", "cells": 2}], "enemy_in_range", rng=1, cd=6),
    "e_star_bolt": sk("Звёздная стрела", "18 урона, перескакивает на 1 (14).", 3, "enemy",
                      [D(18), {"type": "chain", "jumps": 1, "range": 3, "amount": 14}], "enemy_in_range", rng=5,
                      cast=0.5, cd=3),
    "e_gravity": sk("Притяжение бездны", "Притягивает на 2 и 12 урона.", 3, "enemy",
                    [{"type": "pull", "cells": 2}, D(12)], "enemy_in_range", rng=5, cd=8),
    "e_archon_wave": sk("Небесная волна", "Радиус 2: 22 урона и отбрасывание на 2.", 4, "self",
                        [D(22, radius=2), {"type": "knockback", "cells": 2, "radius": 2}], "adjacent_foes", cd=9,
                        radius=2),
}

SUMMONS = {
    "skeleton_minion": E("Поднятый скелет", "Ск", "melee", 60, 9, look("skeleton", [210, 205, 190], head="skull",
                                                                      weapon="sword"), move=0.6, summon=True),
    "mummy_risen": E("Восставшая мумия", "Мм", "melee", 90, 10, look("humanoid", [190, 175, 140], [120, 100, 70],
                                                                     head="wrap"), tag="poison", move=0.75, summon=True),
    "illusion": E("Иллюзия", "Ил", "melee", 30, 6, look("fairy", [200, 160, 255], [255, 220, 255]), move=0.4,
                  summon=True, flying=True),
}

FIRE0 = {"fire": 0.4}      # враги кузни: огонь по ним слабее, гореть они не горят (любовь к жару)
CH = []        # главы по порядку (Болото уже есть)
ENEMIES = {}


def chapter(cid, name, desc, mechanics, palette, enemies, adds, events, maps, encounters, regions, bonuses, power):
    CH.append(dict(id=cid, name=name, desc=desc, mechanics=mechanics, palette=palette, enemies=enemies, adds=adds,
                   events=events, maps=maps, encounters=encounters, regions=regions, bonuses=bonuses, power=power))
    ENEMIES.update(enemies)


# ======================= Болото: добавки сложности =======================
SWAMP_ADDS = {
    "toxic_slime": E("Ядовитый слизень", "Яс", "melee", 130, 11, look("blob", [120, 190, 70]), tag="poison", move=0.7,
                     on_death={"name": "Ядовитая лужа", "effects": [{"type": "hazard", "hazard": "poison", "duration": 5,
                                                                    "radius": 1}]}),
    "bog_horror": E("Болотный ужас", "Уж", "melee", 260, 18, look("golem", [70, 100, 70], [140, 180, 110]), armor=2,
                    move=0.75, cd=1.6, lifesteal=0.25),
}
ENEMIES.update(SWAMP_ADDS)

# ======================= Огненные кузни =======================
chapter(
    "forge", "Огненные кузни",
    "Подземные горны, реки лавы и рабы огня. Владыка кузни куёт армию из магмы.",
    ["Лава: клетки лавы жгут всегда (6 урона/сек + Огонь)",
     "Извержения: отмеченные клетки через 1.5 сек вспыхивают огнём",
     "Перегрев: враги кузни в огне и на лаве бьют сильнее и восстанавливаются — гасите их Водой и Льдом"],
    {"grass": [58, 48, 44], "stone": [84, 72, 66], "water": [40, 60, 90]},
    {
        "fire_imp": E("Огненный бес", "Бс", "melee", 65, 9, look("imp", [230, 90, 40], [255, 200, 80], head="horns"),
                      cd=0.8, move=0.35, tag="fire", heat={"atk_mult": 1.25, "regen": 3}, resist=FIRE0),
        "magma_golem": E("Магмовый голем", "Гл", "melee", 200, 15, look("golem", [90, 60, 50], [255, 120, 40]), armor=3,
                         cd=1.6, move=0.8, heat={"atk_mult": 1.3, "regen": 6}, resist=FIRE0, skills=["e_slam"]),
        "hammer_thrower": E("Метатель молотов", "Мм", "ranged", 90, 11, look("humanoid", [150, 110, 80], [200, 200, 210],
                                                                             head="helm", weapon="hammer"),
                            rng=4, cd=1.4, skills=["e_hammer"]),
        "flame_priest": E("Жрец пламени", "Жп", "caster", 85, 7, look("robe", [180, 60, 40], [255, 180, 60], head="hood",
                                                                      weapon="staff"),
                          rng=4, skills=["e_fireball"], resist=FIRE0),
        "salamander": E("Саламандра", "Сл", "melee", 110, 11, look("lizard", [220, 120, 40], [255, 220, 90]), tag="fire",
                        move=0.45, skills=["e_flame_breath"], heat={"atk_mult": 1.3, "regen": 5}, resist=FIRE0),
        "obsidian_guard": E("Обсидиановый страж", "Об", "melee", 220, 14, look("golem", [40, 36, 50], [180, 90, 255]),
                            armor=4, cd=1.5, move=0.75, heat={"atk_mult": 1.25, "regen": 4}, resist=FIRE0),
        "living_lava": E("Живая лава", "Лв", "melee", 110, 13, look("blob", [255, 110, 30], [255, 220, 120]), tag="fire",
                         move=0.6, resist=FIRE0, heat={"atk_mult": 1.3, "regen": 4},
                         on_death={"name": "Разлив лавы", "effects": [D(14, radius=1, tag="fire", affects="enemies"),
                                                                      {"type": "hazard", "hazard": "fire",
                                                                       "duration": 5, "radius": 1}]}),
        "forge_overseer": E("Надсмотрщик кузни", "Нд", "melee", 360, 18, look("humanoid", [120, 80, 60], [255, 150, 60],
                                                                             head="horns", weapon="whip"),
                            armor=3, elite=True, cd=1.4, skills=["e_lash", "e_slam"], resist=FIRE0),
        "forge_lord": E("Владыка кузни", "Вл", "caster", 640, 18, look("golem", [70, 50, 50], [255, 140, 40], head="crown"),
                        armor=4, boss=True, rng=2, reach=True, cd=1.5, move=0.7, ap_max=8, ap_regen=3.5,
                        skills=["e_meteor", "e_slam", "e_fireball"], resist=FIRE0, heat={"atk_mult": 1.25, "regen": 8},
                        pp_max=2, pp_regen=3.0,
                        passive={"kind": "block", "name": "Броня горна", "pp": 1, "mult": 0.5,
                                 "desc": "Любой удар: −1 деление шкалы, урон ×0.5"}),
    },
    {"heroic": ["obsidian_guard", "fire_imp"], "nightmare": ["living_lava"]},
    [{"type": "eruption", "name": "Извержение", "every": [10, 14], "first": 6, "count": 3, "warn": 1.6, "damage": 14,
      "burn": 3}],
    {
        "a": ["..........", "....LL..#.", "...#LL....", "....LL....", "...#..LL..", "......LL.."],
        "b": ["...L......", "...L..#...", "......LLL.", "..........", "...##..LL.", "........L."],
        "c": ["......LL..", "...=..LL..", "...=......", "....L...#.", "...LLL....", ".........."],
        "d": ["..........", "....L..L..", "...LL.#LL.", "....L..L..", "...#......", ".........."],
    },
    [("Шлаковые отвалы", "normal", 1, "a", ["fire_imp", "fire_imp", "hammer_thrower", "salamander"]),
     ("Литейный цех", "normal", 1, "b", ["magma_golem", "fire_imp", "hammer_thrower", "flame_priest"]),
     ("Плавильня", "normal", 2, "c", ["magma_golem", "salamander", "fire_imp", "hammer_thrower", "flame_priest"]),
     ("Огненный мост", "normal", 2, "d", ["salamander", "salamander", "fire_imp", "hammer_thrower", "flame_priest"]),
     ("Зал надсмотрщика", "elite", 2, "c", ["forge_overseer", "fire_imp", "hammer_thrower", "flame_priest"]),
     ("Ворота кузни", "guard", 1, "a", ["magma_golem", "fire_imp", "fire_imp", "hammer_thrower", "flame_priest"]),
     ("Угольные шахты", "guard", 1, "b", ["salamander", "fire_imp", "hammer_thrower", "hammer_thrower", "flame_priest"]),
     ("Кипящий канал", "guard", 2, "d", ["magma_golem", "salamander", "fire_imp", "hammer_thrower", "flame_priest"]),
     ("Арсенал", "guard", 2, "c", ["magma_golem", "magma_golem", "hammer_thrower", "flame_priest", "fire_imp"]),
     ("Сердце горна", "boss", 3, "d", ["forge_lord", "fire_imp", "salamander", "flame_priest"])],
    ["Ворота кузни", "Угольные шахты", "Кипящий канал", "Арсенал", "Зал надсмотрщика", "Сердце горна"],
    [("power_pct", 0.04, "Горн", "+4% урона атак и силы навыков"),
     ("start_gold", 15, "Казна рабов", "+15 золота в начале вылазки"),
     ("shop_items", 1, "Склад оружия", "+1 предмет у торговца"),
     ("hp_pct", 0.04, "Закалённая сталь", "+4% макс. HP отряду"),
     ("rare_chance", 0.05, "Мастерская", "Редкие предметы чаще на 5%")],
    {"hp": 1.12, "damage": 1.05})

# ======================= Склеп нежити =======================
chapter(
    "crypt", "Склеп нежити",
    "Катакомбы под заброшенным монастырём. Лич поднимает мёртвых снова и снова.",
    ["Нежить встаёт: скелеты и рыцари смерти поднимаются через 3 сек с половиной HP — добивайте Огнём",
     "Проклятие: некроманты делают лечение героя вдвое слабее",
     "Туман: на разведке видны не все враги — часть появится только в бою"],
    {"grass": [46, 46, 56], "stone": [70, 70, 82], "water": [40, 50, 70]},
    {
        "skeleton": E("Скелет-воин", "Ск", "melee", 110, 12, look("skeleton", [215, 210, 195], [150, 150, 160],
                                                                  head="skull", weapon="sword"),
                      armor=1, move=0.6, undying={"delay": 3, "hp": 0.4, "unless": ["fire"]}),
        "skeleton_archer": E("Скелет-лучник", "Сл", "ranged", 80, 11, look("skeleton", [215, 210, 195], [120, 90, 60],
                                                                          head="skull", weapon="bow"),
                             rng=5, undying={"delay": 3, "hp": 0.4, "unless": ["fire"]}),
        "ghoul": E("Упырь", "Уп", "melee", 100, 11, look("ghoul", [120, 140, 110], [200, 60, 60]), tag="poison",
                   move=0.4, cd=1.0, lifesteal=0.25),
        "necromancer": E("Некромант", "Нк", "caster", 95, 8, look("robe", [70, 40, 90], [180, 255, 160], head="hood",
                                                                  weapon="staff"),
                         rng=4, skills=["e_raise", "e_wither"]),
        "banshee": E("Банши", "Бн", "caster", 85, 9, look("spirit", [190, 210, 230], [120, 160, 200]), rng=3,
                     flying=True, skills=["e_wail"]),
        "bone_golem": E("Костяной голем", "Кг", "melee", 280, 16, look("golem", [200, 195, 180], [120, 110, 100]),
                        armor=3, cd=1.6, move=0.8, undying={"delay": 4, "hp": 0.4, "unless": ["fire"]}),
        "wraith": E("Призрак", "Пз", "melee", 100, 14, look("spirit", [90, 80, 120], [200, 150, 255]), flying=True,
                    move=0.4, lifesteal=0.3),
        "death_knight": E("Рыцарь смерти", "Рс", "melee", 380, 18, look("skeleton", [60, 60, 80], [120, 220, 160],
                                                                        head="helm", weapon="sword"),
                          armor=4, elite=True, cd=1.4, skills=["e_slam", "e_wither"],
                          undying={"delay": 4, "hp": 0.5, "unless": ["fire"]}),
        "lich": E("Лич", "Лч", "caster", 600, 15, look("skeleton", [90, 60, 120], [150, 255, 200], head="crown",
                                                       weapon="staff"),
                  armor=2, boss=True, rng=4, ap_max=8, ap_regen=3.5, skills=["e_raise_lich", "e_wither", "frost_storm"],
                  pp_max=2, pp_regen=3.0,
                  passive={"kind": "block", "name": "Филактерия", "pp": 1, "mult": 0.5,
                           "desc": "Любой удар: −1 деление шкалы, урон ×0.5"}),
    },
    {"heroic": ["bone_golem", "skeleton"], "nightmare": ["wraith"]},
    [],
    {
        "a": ["..........", "...=...#..", "....#.....", "...=..=...", ".....#..=.", ".........."],
        "b": ["...#......", "...#..=...", "......##..", "...=......", "...#..=...", "...#......"],
        "c": ["..........", "....##....", "...=..=...", "...=..=...", "....##....", ".........."],
        "d": ["..........", "...#....#.", "..........", ".....=....", "...#....#.", ".........."],
    },
    [("Оссуарий", "normal", 1, "a", ["skeleton", "skeleton", "skeleton_archer", "ghoul"], 1),
     ("Галерея гробов", "normal", 1, "b", ["skeleton", "ghoul", "skeleton_archer", "necromancer"], 1),
     ("Зал плача", "normal", 2, "c", ["skeleton", "skeleton", "ghoul", "banshee", "necromancer"], 1),
     ("Нижние катакомбы", "normal", 2, "d", ["skeleton", "ghoul", "ghoul", "skeleton_archer", "necromancer"], 2),
     ("Чертог рыцаря", "elite", 2, "c", ["death_knight", "skeleton", "skeleton_archer", "necromancer"], 1),
     ("Ограда кладбища", "guard", 1, "a", ["skeleton", "skeleton", "ghoul", "skeleton_archer", "necromancer"], 2),
     ("Часовня", "guard", 1, "b", ["skeleton", "ghoul", "banshee", "skeleton_archer", "skeleton_archer"], 2),
     ("Склеп аббата", "guard", 2, "d", ["skeleton", "skeleton", "ghoul", "banshee", "necromancer"], 2),
     ("Колодец душ", "guard", 2, "c", ["ghoul", "ghoul", "banshee", "necromancer", "skeleton_archer"], 2),
     ("Трон лича", "boss", 3, "d", ["lich", "skeleton", "skeleton", "banshee"], 0)],
    ["Ограда кладбища", "Часовня", "Склеп аббата", "Колодец душ", "Чертог рыцаря", "Трон лича"],
    [("post_battle_heal", 0.05, "Святая вода", "Лечение после победы +5%"),
     ("rerolls", 1, "Чётки", "+1 переброс наград"),
     ("hp_pct", 0.05, "Мощи", "+5% макс. HP отряду"),
     ("start_gold", 15, "Подношения", "+15 золота в начале вылазки"),
     ("power_pct", 0.04, "Реликварий", "+4% урона атак и силы навыков")],
    {"hp": 1.36, "damage": 1.2})

# ======================= Ледяные перевалы =======================
chapter(
    "pass", "Ледяные перевалы",
    "Горные тропы над пропастью снега. Йети и ледяной великан не пускают дальше.",
    ["Скользкий лёд: шаг на лёд протаскивает ещё на клетку (звери перевала не скользят)",
     "Лавины: отмеченный участок через 2 сек накрывает — урон, Лёд и оглушение",
     "Ледяная броня: щит врага нарастает снова каждые 8 сек; Огонь колет его и бьёт ×1.5"],
    {"grass": [112, 126, 140], "stone": [88, 98, 112], "water": [60, 90, 130]},
    {
        "frost_wolf": E("Снежный волк", "Вк", "melee", 85, 11, look("beast", [220, 225, 235], [140, 170, 210]),
                        tag="ice", move=0.35, cd=1.0, ice_walker=True),
        "yeti": E("Йети", "Йт", "melee", 220, 17, look("yeti", [230, 235, 240], [120, 150, 200]), armor=2, cd=1.6,
                  move=0.7, ice_walker=True, frost_armor={"shield": 30, "every": 8}, skills=["e_slam"]),
        "ice_archer": E("Стрелок перевала", "Ст", "ranged", 85, 12, look("humanoid", [120, 150, 190], [230, 240, 255],
                                                                         head="hood", weapon="bow"),
                        rng=5, frost_armor={"shield": 20, "every": 10}, skills=["ice_dart"]),
        "frost_shaman": E("Шаман инея", "Ши", "support", 95, 7, look("robe", [140, 190, 230], [240, 250, 255],
                                                                        head="horns", weapon="staff"),
                          rng=4, skills=["e_frost_ward", "e_frost_breath"]),
        "ice_golem": E("Ледяной голем", "Лг", "melee", 260, 16, look("golem", [170, 210, 240], [240, 250, 255]),
                       armor=3, cd=1.6, move=0.8, ice_walker=True, frost_armor={"shield": 50, "every": 7}),
        "frost_wyrmling": E("Ледяной змеёныш", "Зм", "ranged", 130, 12, look("wyrm", [150, 200, 240], [230, 245, 255]),
                            rng=3, tag="ice", flying=True, move=0.45, skills=["e_frost_breath"]),
        "yeti_alpha": E("Вожак йети", "Вй", "melee", 400, 19, look("yeti", [250, 250, 255], [90, 130, 200], head="crown"),
                        armor=3, elite=True, cd=1.5, move=0.65, ice_walker=True,
                        frost_armor={"shield": 50, "every": 8}, skills=["e_slam"]),
        "frost_giant": E("Ледяной великан", "Вл", "melee", 700, 22, look("yeti", [160, 200, 235], [255, 255, 255],
                                                                         head="helm"),
                         armor=3, boss=True, cd=1.8, move=0.75, ap_max=8, ap_regen=3.5, ice_walker=True,
                         frost_armor={"shield": 80, "every": 10}, skills=["e_avalanche", "e_slam"]),
    },
    {"heroic": ["ice_golem", "frost_wolf"], "nightmare": ["frost_wyrmling"]},
    [{"type": "avalanche", "name": "Лавина", "every": [11, 15], "first": 6, "warn": 2.0, "damage": 20, "stun": 1.2}],
    {
        "a": ["..........", "...IIII...", "...IIII.#.", "....II....", "...#..II..", ".........."],
        "b": ["...#....#.", "....III...", "...IIIII..", "....III...", "...#......", ".......#.."],
        "c": ["..........", "...##..I..", "....IIII..", "...IIII...", "...#......", ".........."],
        "d": ["..........", "...IIIIII.", "...I#..I..", "...I..#I..", "...IIIIII.", ".........."],
    },
    [("Снежная тропа", "normal", 1, "a", ["frost_wolf", "frost_wolf", "ice_archer", "yeti"]),
     ("Обледенелый мост", "normal", 1, "b", ["frost_wolf", "yeti", "ice_archer", "frost_shaman"]),
     ("Ледник", "normal", 2, "c", ["yeti", "frost_wolf", "frost_wolf", "ice_archer", "frost_shaman"]),
     ("Пещера инея", "normal", 2, "d", ["yeti", "yeti", "ice_archer", "ice_archer", "frost_shaman"]),
     ("Логово вожака", "elite", 2, "c", ["yeti_alpha", "frost_wolf", "frost_wolf", "frost_shaman"]),
     ("Застава", "guard", 1, "a", ["yeti", "frost_wolf", "frost_wolf", "ice_archer", "frost_shaman"]),
     ("Тропа волков", "guard", 1, "b", ["frost_wolf", "frost_wolf", "frost_wolf", "ice_archer", "frost_shaman"]),
     ("Перевал бурь", "guard", 2, "d", ["yeti", "yeti", "frost_wolf", "ice_archer", "frost_shaman"]),
     ("Ледяной водопад", "guard", 2, "c", ["yeti", "ice_archer", "ice_archer", "frost_shaman", "frost_wolf"]),
     ("Вершина великана", "boss", 3, "d", ["frost_giant", "frost_wolf", "frost_wolf", "frost_shaman"])],
    ["Застава", "Тропа волков", "Перевал бурь", "Ледяной водопад", "Логово вожака", "Вершина великана"],
    [("hp_pct", 0.05, "Тёплые меха", "+5% макс. HP отряду"),
     ("discount", 0.05, "Горные торговцы", "Цены у торговца −5%"),
     ("power_pct", 0.04, "Закалка морозом", "+4% урона атак и силы навыков"),
     ("start_gold", 15, "Пошлина", "+15 золота в начале вылазки"),
     ("post_battle_heal", 0.05, "Горячие источники", "Лечение после победы +5%")],
    {"hp": 1.54, "damage": 1.3})

# ======================= Грозовая степь =======================
chapter(
    "steppe", "Грозовая степь",
    "Бескрайние травы под вечной грозой. Орды налётчиков служат Хану бури.",
    ["Гроза: молнии бьют в отмеченные клетки — мокрым героям грозит электрошок",
     "Ветер: порыв сдвигает всех на клетку (в стену — урон)",
     "Налётчики: быстрые всадники врываются в тыл прыжком"],
    {"grass": [88, 94, 56], "stone": [96, 90, 78], "water": [50, 80, 110]},
    {
        "raider": E("Степной налётчик", "Нл", "melee", 95, 12, look("rider", [150, 110, 70], [200, 60, 50],
                                                                    weapon="spear"),
                    move=0.3, cd=1.1, skills=["e_charge"]),
        "storm_hawk": E("Грозовой ястреб", "Яс", "ranged", 60, 10, look("bird", [110, 110, 140], [190, 200, 255]),
                        rng=3, tag="storm", move=0.3, flying=True, cd=1.0),
        "stormcaller": E("Заклинатель бури", "Зб", "caster", 90, 8, look("robe", [70, 80, 140], [190, 200, 255],
                                                                         head="hood", weapon="staff"),
                         rng=4, skills=["e_rain", "e_chain"]),
        "steppe_ogre": E("Степной огр", "Ог", "melee", 240, 18, look("ogre", [150, 130, 90], [110, 80, 50],
                                                                     weapon="club"),
                         armor=2, cd=1.7, move=0.65, skills=["e_club"]),
        "thunder_elemental": E("Элементаль грома", "Эг", "caster", 180, 12, look("elemental", [120, 140, 255],
                                                                                 [240, 245, 255]),
                               rng=3, tag="storm", flying=True,
                               aura={"every": 2.0, "radius": 1, "effects": [D(8, radius=1, tag="storm")]}),
        "wind_rider": E("Всадник ветра", "Вв", "melee", 160, 15, look("rider", [200, 210, 220], [90, 160, 230],
                                                                      weapon="spear"),
                        move=0.28, cd=1.0, lifesteal=0.2, skills=["e_charge"]),
        "warchief": E("Вождь налётчиков", "Вж", "melee", 380, 18, look("rider", [120, 80, 50], [255, 200, 60],
                                                                       head="horns", weapon="axe"),
                      armor=3, elite=True, move=0.4, skills=["e_charge", "e_war_cry"]),
        "storm_khan": E("Хан бури", "Хн", "caster", 680, 18, look("rider", [60, 60, 100], [180, 200, 255],
                                                                  head="crown", weapon="spear"),
                        armor=3, boss=True, rng=2, reach=True, move=0.45, ap_max=8, ap_regen=3.5,
                        skills=["e_thunderstorm", "e_charge", "e_war_cry"], pp_max=2, pp_regen=3.0,
                        passive={"kind": "dodge", "vs": ["ranged"], "name": "Вихрь копыт", "pp": 1,
                                 "desc": "Дальняя атака: −1 деление шкалы, промах"}),
    },
    {"heroic": ["thunder_elemental", "raider"], "nightmare": ["wind_rider"]},
    [{"type": "lightning", "name": "Удар молнии", "every": [7, 10], "first": 4, "count": 3, "warn": 1.2, "damage": 16},
     {"type": "wind", "name": "Порыв ветра", "every": [13, 17], "first": 9, "warn": 1.5, "push": 1}],
    {
        "a": ["..........", "...~~..=..", "...~~.....", ".......~~.", "...=...~~.", ".........."],
        "b": ["..........", "....=.....", "...~~~....", "....~~~...", "......=...", ".........."],
        "c": [".....~....", "...=.~....", "......~~..", "...~......", "...~..=...", ".........."],
        "d": ["..........", "...~~..~~.", "....#.....", ".....#....", "...~~..~~.", ".........."],
    },
    [("Высокие травы", "normal", 1, "a", ["raider", "raider", "storm_hawk", "stormcaller"]),
     ("Курганы", "normal", 1, "b", ["steppe_ogre", "raider", "storm_hawk", "storm_hawk"]),
     ("Солёное озеро", "normal", 2, "c", ["raider", "raider", "steppe_ogre", "stormcaller", "storm_hawk"]),
     ("Грозовой холм", "normal", 2, "d", ["steppe_ogre", "raider", "stormcaller", "stormcaller", "storm_hawk"]),
     ("Шатёр вождя", "elite", 2, "c", ["warchief", "raider", "storm_hawk", "stormcaller"]),
     ("Кочевье", "guard", 1, "a", ["raider", "raider", "steppe_ogre", "storm_hawk", "stormcaller"]),
     ("Каменные бабы", "guard", 1, "b", ["steppe_ogre", "raider", "storm_hawk", "storm_hawk", "stormcaller"]),
     ("Брод", "guard", 2, "c", ["steppe_ogre", "steppe_ogre", "raider", "stormcaller", "storm_hawk"]),
     ("Становище орды", "guard", 2, "d", ["raider", "raider", "raider", "stormcaller", "storm_hawk"]),
     ("Ставка хана", "boss", 3, "d", ["storm_khan", "raider", "storm_hawk", "stormcaller"])],
    ["Кочевье", "Каменные бабы", "Брод", "Становище орды", "Шатёр вождя", "Ставка хана"],
    [("rerolls", 1, "Гадалка", "+1 переброс наград"),
     ("power_pct", 0.05, "Табун", "+5% урона атак и силы навыков"),
     ("start_gold", 20, "Дань", "+20 золота в начале вылазки"),
     ("hp_pct", 0.05, "Кумыс", "+5% макс. HP отряду"),
     ("ap", 1, "Боевой рог", "+1 AP всем героям")],
    {"hp": 1.72, "damage": 1.4})

# ======================= Пустынные гробницы =======================
chapter(
    "tomb", "Пустынные гробницы",
    "Пески скрывают усыпальницы древних царей. Фараон не желает покоя.",
    ["Песчаная буря: на 6 сек дальность всех стрелков и магов −2",
     "Саркофаги: каменные гробы поднимают мумий, пока их не разбить",
     "Скарабеи: рои мелких жуков с ядом — Яд режет лечение"],
    {"grass": [150, 128, 88], "stone": [128, 110, 82], "water": [60, 110, 130]},
    {
        "mummy": E("Мумия", "Мм", "melee", 160, 13, look("humanoid", [200, 185, 150], [120, 100, 70], head="wrap"),
                   armor=1, tag="poison", move=0.7),
        "scarab": E("Скарабей", "Ск", "melee", 38, 6, look("insect", [60, 110, 120], [230, 200, 80]), tag="poison",
                    move=0.35, cd=0.9),
        "tomb_archer": E("Лучник гробниц", "Лг", "ranged", 85, 12, look("humanoid", [170, 140, 90], [60, 90, 150],
                                                                       head="nemes", weapon="bow"), rng=5),
        "sand_priest": E("Жрец песков", "Жп", "support", 95, 7, look("robe", [200, 170, 90], [80, 120, 200],
                                                                     head="nemes", weapon="staff"),
                         rng=4, skills=["e_heal", "e_wither"]),
        "sarcophagus": E("Саркофаг", "Сф", "melee", 140, 0, look("sarcophagus", [180, 150, 90], [230, 200, 80]),
                         rng=0, armor=3, static=True,
                         aura={"every": 7.0, "radius": 0, "effects": [{"type": "summon", "unit": "mummy_risen",
                                                                      "duration": 30, "limit": 2}]}),
        "sand_golem": E("Песчаный голем", "Пг", "melee", 260, 16, look("golem", [190, 160, 100], [230, 200, 140]),
                        armor=2, cd=1.6, move=0.8, skills=["e_slam"]),
        "anubis_guard": E("Страж Анубиса", "Ан", "melee", 220, 17, look("jackal", [40, 40, 50], [230, 190, 60],
                                                                         weapon="spear"),
                          armor=4, cd=1.4, lifesteal=0.2),
        "tomb_guardian": E("Хранитель гробницы", "Хг", "melee", 380, 18, look("golem", [170, 140, 80], [80, 140, 220],
                                                                               head="nemes"),
                           armor=4, elite=True, cd=1.5, skills=["e_slam", "e_plague"]),
        "pharaoh": E("Фараон", "Фр", "caster", 650, 16, look("humanoid", [220, 190, 120], [60, 110, 200], head="nemes",
                                                             weapon="staff"),
                     armor=3, boss=True, rng=4, ap_max=8, ap_regen=3.5, skills=["e_raise_mummy", "e_plague", "e_wither"],
                     pp_max=2, pp_regen=3.0,
                     passive={"kind": "block", "name": "Божественная плоть", "pp": 1, "mult": 0.5,
                              "desc": "Любой удар: −1 деление шкалы, урон ×0.5"}),
    },
    {"heroic": ["sand_golem", "scarab"], "nightmare": ["anubis_guard"]},
    [{"type": "sandstorm", "name": "Песчаная буря", "every": [14, 18], "first": 7, "warn": 1.5, "range": 2,
      "duration": 6}],
    {
        "a": ["..........", "...#...#..", "..........", "...=...=..", "..........", "...#...#.."],
        "b": ["...=......", "....#..#..", "..........", "....#..#..", "...=......", ".........."],
        "c": ["..........", "...##.....", "......=...", "...=......", ".....##...", ".........."],
        "d": ["...#....#.", "..........", "...#....#.", "..........", "...#....#.", ".........."],
    },
    [("Дюны", "normal", 1, "a", ["mummy", "scarab", "scarab", "scarab", "tomb_archer"]),
     ("Аллея сфинксов", "normal", 1, "b", ["mummy", "mummy", "tomb_archer", "sand_priest"]),
     ("Погребальный зал", "normal", 2, "c", ["sarcophagus", "mummy", "scarab", "scarab", "tomb_archer"]),
     ("Сокровищница", "normal", 2, "d", ["mummy", "scarab", "scarab", "tomb_archer", "sand_priest"]),
     ("Зал хранителя", "elite", 2, "c", ["tomb_guardian", "scarab", "scarab", "sand_priest"]),
     ("Оазис", "guard", 1, "a", ["mummy", "mummy", "scarab", "scarab", "tomb_archer"]),
     ("Некрополь", "guard", 1, "b", ["sarcophagus", "mummy", "tomb_archer", "sand_priest"]),
     ("Лабиринт", "guard", 2, "d", ["sarcophagus", "sarcophagus", "mummy", "scarab", "tomb_archer"]),
     ("Храм солнца", "guard", 2, "c", ["mummy", "mummy", "scarab", "sand_priest", "tomb_archer", "tomb_archer"]),
     ("Усыпальница фараона", "boss", 3, "d", ["pharaoh", "sarcophagus", "scarab", "scarab", "tomb_archer"])],
    ["Оазис", "Некрополь", "Лабиринт", "Храм солнца", "Зал хранителя", "Усыпальница фараона"],
    [("rare_chance", 0.05, "Карта сокровищ", "Редкие предметы чаще на 5%"),
     ("start_gold", 20, "Золото гробниц", "+20 золота в начале вылазки"),
     ("hp_pct", 0.05, "Бальзам", "+5% макс. HP отряду"),
     ("power_pct", 0.05, "Скарабей удачи", "+5% урона атак и силы навыков"),
     ("start_relics", 1, "Погребальный дар", "Вылазка начинается со случайной реликвией")],
    {"hp": 1.9, "damage": 1.5})

# ======================= Тёмный лес фей =======================
chapter(
    "fae", "Тёмный лес фей",
    "Лес, где тропы меняются, а феи играют с разумом путников. Королева ждёт в сердце чащи.",
    ["Очарование: феи заставляют героя 4 сек сражаться против своих",
     "Иллюзии: иллюзионисты создают двойников-приманок",
     "Хищные растения: стоят на месте, хватают героев рядом и лечат фей"],
    {"grass": [48, 52, 66], "stone": [72, 66, 84], "water": [40, 60, 100], "tree": [86, 70, 130]},
    {
        "sprite": E("Фея-проказница", "Фп", "caster", 65, 7, look("fairy", [230, 150, 230], [255, 240, 150]), rng=4,
                    move=0.35, flying=True, skills=["e_charm"]),
        "thorn_beast": E("Терновый зверь", "Тз", "melee", 150, 14, look("beast", [70, 100, 60], [180, 90, 140]),
                         armor=2, move=0.45, cd=1.2),
        "illusionist": E("Иллюзионист", "Ил", "caster", 80, 8, look("robe", [120, 80, 180], [255, 220, 255],
                                                                    head="hat", weapon="staff"),
                         rng=4, skills=["e_mirror"]),
        "maneater": E("Росянка-людоед", "Рс", "melee", 130, 14, look("plant", [90, 150, 70], [230, 80, 110]), armor=1,
                      static=True, rng=1,
                      aura={"every": 4.0, "radius": 2, "effects": [{"type": "stun", "duration": 0.8, "radius": 1},
                                                                   {"type": "heal", "amount": 8, "radius": 2}]}),
        "dryad": E("Дриада", "Др", "support", 100, 7, look("dryad", [120, 170, 90], [230, 200, 255]), rng=4,
                   skills=["e_regrowth", "e_entangle"]),
        "treant": E("Древень", "Дв", "melee", 250, 16, look("treant", [100, 80, 55], [110, 170, 80]), armor=3, cd=1.7,
                    move=0.85, skills=["e_slam"]),
        "shade_fae": E("Теневая фея", "Тф", "caster", 95, 12, look("fairy", [70, 50, 110], [200, 120, 255]), rng=3,
                       flying=True, move=0.35, lifesteal=0.3, skills=["e_charm"]),
        "fae_knight": E("Рыцарь шипов", "Рш", "melee", 360, 17, look("humanoid", [80, 110, 70], [230, 120, 200],
                                                                     head="helm", weapon="spear"),
                        armor=3, elite=True, reach=True, rng=2, skills=["e_lash", "e_entangle"]),
        "fae_queen": E("Королева фей", "Кф", "caster", 600, 15, look("fairy", [200, 120, 255], [255, 230, 120],
                                                                     head="crown"),
                       armor=2, boss=True, rng=4, flying=True, ap_max=8, ap_regen=3.5,
                       skills=["e_charm", "e_mirror", "e_sleep"], pp_max=2, pp_regen=3.0,
                       passive={"kind": "block", "name": "Мерцание", "pp": 1, "mult": 0.6,
                                "desc": "Любой удар: −1 деление шкалы, урон ×0.6"}),
    },
    {"heroic": ["treant", "thorn_beast"], "nightmare": ["shade_fae"]},
    [],
    {
        "a": ["....T.....", "...T...T..", "......~~..", "...T..~~..", ".....T....", "......T..."],
        "b": ["..........", "...TT.....", "......T...", "...~~...T.", "...~~.....", "......TT.."],
        "c": ["...T...T..", "..........", "....TT....", "..........", "...T...T..", ".........."],
        "d": ["..........", "...T....T.", ".....~~...", ".....~~...", "...T....T.", ".........."],
    },
    [("Светящиеся грибы", "normal", 1, "a", ["thorn_beast", "thorn_beast", "sprite", "dryad"]),
     ("Кольцо фей", "normal", 1, "b", ["thorn_beast", "maneater", "sprite", "illusionist"]),
     ("Шепчущая роща", "normal", 2, "c", ["thorn_beast", "thorn_beast", "maneater", "sprite", "dryad"]),
     ("Зеркальное озеро", "normal", 2, "d", ["thorn_beast", "illusionist", "illusionist", "sprite", "dryad"]),
     ("Шипастый двор", "elite", 2, "c", ["fae_knight", "maneater", "sprite", "dryad"]),
     ("Опушка", "guard", 1, "a", ["thorn_beast", "thorn_beast", "sprite", "dryad", "maneater"]),
     ("Туманная лощина", "guard", 1, "b", ["thorn_beast", "illusionist", "sprite", "sprite", "dryad"]),
     ("Сад росянок", "guard", 2, "c", ["maneater", "maneater", "thorn_beast", "sprite", "dryad"]),
     ("Лунная поляна", "guard", 2, "d", ["thorn_beast", "thorn_beast", "illusionist", "sprite", "dryad"]),
     ("Чертог королевы", "boss", 3, "d", ["fae_queen", "thorn_beast", "maneater", "dryad"])],
    ["Опушка", "Туманная лощина", "Сад росянок", "Лунная поляна", "Шипастый двор", "Чертог королевы"],
    [("post_battle_heal", 0.05, "Родник", "Лечение после победы +5%"),
     ("rerolls", 1, "Клевер", "+1 переброс наград"),
     ("power_pct", 0.05, "Пыльца фей", "+5% урона атак и силы навыков"),
     ("hp_pct", 0.05, "Сердце дуба", "+5% макс. HP отряду"),
     ("discount", 0.05, "Торговцы-гномы", "Цены у торговца −5%")],
    {"hp": 2.08, "damage": 1.6})

# ======================= Затонувший город =======================
chapter(
    "sunken", "Затонувший город",
    "Город, ушедший под воду. В отлив открываются улицы, в прилив — пасть глубин.",
    ["Приливы: волна затапливает два ряда клеток на 6 сек — Вода на всех, кто там стоит",
     "Утаскивание: утопленники притягивают героев и оглушают",
     "Угри: электрические твари бьют Грозой — по мокрым будет электрошок"],
    {"grass": [62, 74, 80], "stone": [84, 96, 102], "water": [34, 70, 110]},
    {
        "drowned": E("Утопленник", "Ут", "melee", 150, 13, look("ghoul", [90, 130, 130], [40, 80, 90]), tag="water",
                     move=0.65, skills=["e_drag"]),
        "eel": E("Электрический угорь", "Уг", "ranged", 75, 11, look("serpent", [60, 90, 140], [230, 240, 120]), rng=4,
                 tag="storm", move=0.4),
        "siren": E("Сирена", "Ср", "caster", 90, 8, look("siren", [120, 190, 200], [255, 200, 220]), rng=4,
                   skills=["e_sleep"]),
        "crab_knight": E("Краб-рыцарь", "Кр", "melee", 200, 15, look("crab", [200, 90, 60], [240, 200, 160]), armor=4,
                         move=0.6, skills=["e_claw"]),
        "deep_priest": E("Жрец глубин", "Жг", "support", 110, 8, look("robe", [40, 90, 100], [160, 240, 230],
                                                                         head="fin", weapon="staff"),
                         rng=4, skills=["e_heal", "e_tidal"]),
        "kraken_arm": E("Щупальце кракена", "Щк", "melee", 150, 14, look("tentacle", [130, 60, 110], [220, 140, 200]),
                        armor=2, rng=2, reach=True, static=True, skills=["e_drag"]),
        "drowned_captain": E("Утонувший капитан", "Кп", "melee", 380, 19, look("ghoul", [70, 100, 110], [220, 190, 80],
                                                                               head="hat", weapon="sword"),
                             armor=3, elite=True, skills=["e_drag", "e_slam"]),
        "deep_lord": E("Владыка глубин", "Вг", "caster", 680, 18, look("siren", [40, 80, 120], [120, 255, 220],
                                                                       head="crown"),
                       armor=3, boss=True, rng=3, ap_max=8, ap_regen=3.5, skills=["e_tidal", "e_drag", "e_chain"],
                       pp_max=2, pp_regen=3.0,
                       passive={"kind": "block", "name": "Чешуя", "pp": 1, "mult": 0.5,
                                "desc": "Любой удар: −1 деление шкалы, урон ×0.5"}),
    },
    {"heroic": ["deep_priest", "crab_knight"], "nightmare": ["kraken_arm"]},
    [{"type": "tide", "name": "Прилив", "every": [12, 16], "first": 6, "warn": 2.0, "rows": 2, "duration": 6}],
    {
        "a": ["..........", "...~~~~...", "...~#~~...", "...~~~~.#.", "....~~....", ".........."],
        "b": ["...~~.....", "...~~..#..", "......~~~.", "...#..~~~.", "...~~.....", "...~~....."],
        "c": ["..........", "....~~~~..", "...#~~~~#.", "....~~~~..", "..........", ".........."],
        "d": ["..........", "...~~..~~.", "...~~##~~.", "...~~..~~.", "...~~..~~.", ".........."],
    },
    [("Пристань", "normal", 1, "a", ["drowned", "drowned", "eel", "siren"]),
     ("Площадь фонтанов", "normal", 1, "b", ["crab_knight", "drowned", "eel", "eel"]),
     ("Затопленный рынок", "normal", 2, "c", ["drowned", "crab_knight", "eel", "eel", "siren"]),
     ("Подводный храм", "normal", 2, "d", ["crab_knight", "drowned", "drowned", "siren", "eel"]),
     ("Палуба капитана", "elite", 2, "c", ["drowned_captain", "drowned", "eel", "siren"]),
     ("Маяк", "guard", 1, "a", ["drowned", "drowned", "crab_knight", "eel", "siren"]),
     ("Каналы", "guard", 1, "b", ["eel", "eel", "drowned", "crab_knight", "siren"]),
     ("Затопленный дворец", "guard", 2, "d", ["crab_knight", "crab_knight", "drowned", "eel", "siren"]),
     ("Кладбище кораблей", "guard", 2, "c", ["drowned", "drowned", "eel", "eel", "siren", "crab_knight"]),
     ("Бездна", "boss", 3, "d", ["deep_lord", "drowned", "eel", "siren"])],
    ["Маяк", "Каналы", "Затопленный дворец", "Кладбище кораблей", "Палуба капитана", "Бездна"],
    [("shop_items", 1, "Контрабанда", "+1 предмет у торговца"),
     ("hp_pct", 0.05, "Жемчуг", "+5% макс. HP отряду"),
     ("power_pct", 0.05, "Трезубец", "+5% урона атак и силы навыков"),
     ("start_gold", 20, "Сундук утопленника", "+20 золота в начале вылазки"),
     ("rare_chance", 0.05, "Затонувшие сокровища", "Редкие предметы чаще на 5%")],
    {"hp": 2.26, "damage": 1.7})

# ======================= Небесная цитадель =======================
chapter(
    "citadel", "Небесная цитадель",
    "Парящая крепость над облаками. Небесный архонт сбрасывает непрошеных гостей в пропасть.",
    ["Пропасти: сброшенный в пропасть враг гибнет, герой теряет 40% HP — отталкивания решают",
     "Порталы: шаг в портал переносит к парному порталу",
     "Летающие: крылатые враги парят над пропастями; на героической и выше дует ветер"],
    {"grass": [150, 150, 166], "stone": [118, 118, 138], "water": [70, 110, 160]},
    {
        "sky_knight": E("Небесный рыцарь", "Нр", "melee", 190, 15, look("humanoid", [220, 220, 235], [255, 210, 90],
                                                                        head="helm", weapon="sword", wings=True),
                        armor=4, skills=["e_shield_push"]),
        "harpy": E("Гарпия", "Гп", "melee", 80, 11, look("bird", [170, 120, 90], [240, 220, 200]), flying=True,
                   move=0.3, cd=0.9),
        "sentinel": E("Часовой-голем", "Чг", "ranged", 140, 14, look("construct", [150, 160, 190], [120, 220, 255]),
                      armor=3, rng=5, move=0.8),
        "seraph": E("Серафим", "Сф", "support", 100, 8, look("angel", [250, 245, 230], [255, 220, 120]), rng=4,
                    flying=True, skills=["e_heal", "e_frost_ward"]),
        "arcanist": E("Звёздный маг", "Зм", "caster", 90, 9, look("robe", [60, 60, 130], [200, 210, 255], head="hat",
                                                                  weapon="staff"),
                      rng=5, skills=["e_star_bolt"]),
        "griffin": E("Грифон", "Гр", "melee", 170, 16, look("griffin", [200, 160, 90], [250, 245, 230]), flying=True,
                     move=0.3, cd=1.1),
        "void_watcher": E("Наблюдатель бездны", "Нб", "caster", 130, 11, look("eye", [60, 30, 90], [200, 120, 255]),
                          rng=5, flying=True, skills=["e_gravity", "e_star_bolt"]),
        "storm_paladin": E("Паладин шпиля", "Пш", "melee", 400, 18, look("humanoid", [230, 230, 250], [120, 200, 255],
                                                                         head="crown", weapon="hammer", wings=True),
                           armor=5, elite=True, skills=["e_shield_push", "e_heal"]),
        "archon": E("Небесный архонт", "Ар", "caster", 720, 18, look("angel", [255, 250, 230], [120, 200, 255],
                                                                     head="crown"),
                    armor=3, boss=True, rng=4, flying=True, ap_max=8, ap_regen=3.5,
                    skills=["e_archon_wave", "e_star_bolt", "e_gravity"], pp_max=2, pp_regen=3.0,
                    passive={"kind": "block", "name": "Сияние", "pp": 1, "mult": 0.5,
                             "desc": "Любой удар: −1 деление шкалы, урон ×0.5"}),
    },
    {"heroic": ["griffin", "sky_knight"], "nightmare": ["void_watcher"]},
    [{"type": "wind", "name": "Порыв ветра", "every": [14, 18], "first": 10, "warn": 1.5, "push": 1,
      "min_diff": "heroic"}],
    {
        "a": ["..........", "...__.....", "...__..O..", "...O...__.", ".......__.", ".........."],
        "b": ["....___...", "..........", "...O..#...", ".......O..", "..........", "....___..."],
        "c": ["..........", "...__..__.", "....O..O..", "...__..__.", "..........", ".........."],
        "d": ["..........", "..._....._", "...O....O.", "...#....#.", "..._....._", ".........."],
    },
    [("Облачный причал", "normal", 1, "a", ["sky_knight", "harpy", "harpy", "sentinel"]),
     ("Звёздная лестница", "normal", 1, "b", ["sky_knight", "harpy", "arcanist", "seraph"]),
     ("Висячие сады", "normal", 2, "c", ["sky_knight", "sky_knight", "harpy", "sentinel", "arcanist"]),
     ("Обсерватория", "normal", 2, "d", ["harpy", "harpy", "sentinel", "arcanist", "seraph"]),
     ("Зал паладина", "elite", 2, "c", ["storm_paladin", "harpy", "sentinel", "seraph"]),
     ("Внешняя стена", "guard", 1, "a", ["sky_knight", "sky_knight", "harpy", "sentinel", "arcanist"]),
     ("Гнёзда гарпий", "guard", 1, "b", ["harpy", "harpy", "harpy", "sentinel", "seraph"]),
     ("Мост ветров", "guard", 2, "d", ["sky_knight", "sky_knight", "sentinel", "arcanist", "seraph"]),
     ("Шпиль часовых", "guard", 2, "c", ["sentinel", "sentinel", "sky_knight", "harpy", "arcanist"]),
     ("Тронный зал небес", "boss", 3, "d", ["archon", "sky_knight", "harpy", "seraph"])],
    ["Внешняя стена", "Гнёзда гарпий", "Мост ветров", "Шпиль часовых", "Зал паладина", "Тронный зал небес"],
    [("power_pct", 0.06, "Звёздная сталь", "+6% урона атак и силы навыков"),
     ("hp_pct", 0.06, "Благословение небес", "+6% макс. HP отряду"),
     ("start_relics", 1, "Сокровищница", "Вылазка начинается со случайной реликвией"),
     ("rerolls", 1, "Оракул", "+1 переброс наград"),
     ("ap", 1, "Небесный горн", "+1 AP всем героям")],
    {"hp": 2.44, "damage": 1.8})

# ---------- сборка: столкновения, регионы ----------

SPAWN = [[2, 2], [0, 1], [0, 3], [1, 4]]
BACK = [(9, 2), (9, 3), (8, 1), (8, 4), (9, 1), (9, 4), (9, 0), (9, 5), (8, 2), (8, 3)]
FRONT = [(7, 2), (7, 3), (6, 2), (6, 3), (7, 1), (7, 4), (6, 1), (6, 4), (7, 0), (7, 5), (8, 2), (8, 3)]
BLOCK = set("#=_LTO")


def place(rows, types, enemies):
    """Расставить врагов: дальние и поддержка — сзади, ближние — спереди; только на проходимые обычные клетки."""
    taken, out = set(), []

    def free(p):
        x, y = p
        return p not in taken and rows[y][x] not in BLOCK

    for t in sorted(types, key=lambda t: enemies[t]["role"] in ("melee",)):
        pref = FRONT + BACK if enemies[t]["role"] == "melee" else BACK + FRONT
        if enemies[t].get("boss"):
            pref = [(9, 2), (9, 3), (8, 2), (8, 3)] + BACK
        p = next(p for p in pref if free(p))
        taken.add(p)
        out.append({"type": t, "pos": list(p)})
    return out


# расположение регионов на карте главы — как в Болоте
POS = [[0.10, 0.28], [0.14, 0.76], [0.42, 0.22], [0.46, 0.72], [0.70, 0.48], [0.92, 0.48]]
LINKS = [[1, 2], [0, 3], [0, 3, 4], [1, 2, 4], [2, 3, 5], [4, 2, 3]]


def build():
    encounters, biomes = [], {}
    for order, ch in enumerate(CH, start=1):
        cid = ch["id"]
        all_enemies = {**ENEMIES, **SUMMONS}
        enc_ids = []
        for i, e in enumerate(ch["encounters"]):
            name, kind, tier, m, types = e[:5]
            fog = e[5] if len(e) > 5 else 0
            eid = f"{cid}_{i}"
            rows = ch["maps"][m]
            enc = {"id": eid, "name": name, "kind": kind, "tier": tier, "chapter": cid, "map": rows,
                   "player_spawn": SPAWN, "enemies": place(rows, types, all_enemies)}
            if fog:
                enc["fog"] = fog
            encounters.append(enc)
            enc_ids.append(eid)
        guards = enc_ids[5:9] + [enc_ids[4], enc_ids[9]]     # 4 стража, элита — глубина, босс
        regions = []
        for k in range(6):
            rid = f"{cid}_r{k}"
            threat = (1, 1, 2, 2, 3, 3)[k]
            r = {"id": rid, "name": ch["regions"][k], "pos": POS[k], "threat": threat,
                 "links": [f"{cid}_r{j}" for j in LINKS[k]], "guard": guards[k]}
            if k < 2:
                r["start"] = True
            if k == 5:
                r["boss"] = True
                r["layers"], r["tiers"] = [1, 2, 3, 2, 3, 2, 1], [1, 1, 2, 2, 2]
            elif k < 2:
                r["layers"], r["tiers"] = [1, 2, 2, 1], [1, 1, 1]
            else:
                r["layers"], r["tiers"], r["force_elite"] = [1, 2, 3, 2, 1], [1, 2, 2], False
            if k < 5:
                t, v, n, d = ch["bonuses"][k]
                r["bonus"] = {"type": t, "value": v, "name": n, "desc": d}
            regions.append(r)
        biomes[cid] = {"name": ch["name"], "desc": ch["desc"], "order": order, "boss_after": 3,
                       "mechanics": ch["mechanics"], "palette": ch["palette"], "events": ch["events"],
                       "adds": ch["adds"], "power": ch["power"], "regions": regions}
    return encounters, biomes


SWAMP_EXTRA = {"order": 0,
               "mechanics": ["Вода: стоящие в воде мокнут — Лёд по мокрым замораживает, Огонь даёт пар",
                             "Реакции тегов: жабы и стрелки смешивают Воду и Лёд",
                             "Взрывы при смерти: огненные жуки взрываются рядом с героями"],
               "palette": {}, "events": [], "adds": {"heroic": ["toxic_slime"], "nightmare": ["bog_horror"]},
               "power": {"hp": 1.0, "damage": 1.0}}

CONFIG_ADD = {
    "difficulties": {
        "normal": {"name": "Обычная", "hp": 1.0, "damage": 1.0, "adds": 0, "affixes": 0, "event_rate": 1.0,
                   "event_dmg": 1.0, "amber": 1.0, "xp": 1.0, "epic": 0.0},
        "heroic": {"name": "Героическая", "hp": 1.2, "damage": 1.1, "adds": 1, "affixes": 0, "event_rate": 0.85,
                   "event_dmg": 1.15, "amber": 1.6, "xp": 1.3, "epic": 0.3},
        "nightmare": {"name": "Кошмар", "hp": 1.45, "damage": 1.2, "adds": 2, "affixes": 1, "event_rate": 0.7,
                      "event_dmg": 1.3, "amber": 2.3, "xp": 1.6, "epic": 0.6}},
    "difficulty_order": ["normal", "heroic", "nightmare"],
    "affixes": {
        "fierce": {"name": "Свирепый", "atk_mult": 1.4},
        "stone": {"name": "Каменный", "armor_add": 4, "hp_mult": 1.3},
        "vampiric": {"name": "Вампирский", "lifesteal": 0.4},
        "swift": {"name": "Стремительный", "move_mult": 0.6, "atk_cd_mult": 0.75},
        "burning": {"name": "Пылающий", "atk_tag": "fire", "atk_mult": 1.15}},
}
TERRAIN_ADD = {
    "lava": {"name": "Лава", "color": [190, 70, 24], "status": "fire", "dps": 6},
    "ice_floor": {"name": "Скользкий лёд", "color": [168, 204, 228]},
    "chasm": {"name": "Пропасть", "color": [14, 12, 28]},
}
LEGEND_ADD = {
    "L": {"terrain": "lava"},
    "I": {"terrain": "ice_floor"},
    "_": {"terrain": "chasm", "passable": False},
    "O": {"terrain": "stone", "portal": True},
    "T": {"terrain": "grass", "passable": False, "cover": "full", "deco": "tree"},
}


def main():
    encounters, biomes = build()
    j = lambda v: json.dumps(v, ensure_ascii=False)  # noqa: E731
    upsert("enemies.json", ENEMIES, "fields")
    upsert("skills.json", ENEMY_SKILLS, "fields")
    upsert("summons.json", SUMMONS, "fields")
    # столкновения — список: дописываем в конец
    p = os.path.join(DATA, "encounters.json")
    with open(p, encoding="utf-8") as f:
        text = f.read()
    ours = {e["id"] for e in encounters}
    keep = [line for line in text.rstrip().rstrip("]").rstrip().split("\n")
            if not any(line.strip().startswith('{"id": ' + j(i)) for i in ours)]
    body = "\n".join(keep).rstrip().rstrip(",")
    write(p, body + ",\n" + ",\n".join("  " + j(e) for e in encounters) + "\n]\n")
    # главы: Болото дополняется полями главы, новые — целиком
    p = os.path.join(DATA, "biomes.json")
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if "order" not in data["swamp"]:
        data["swamp"].update(SWAMP_EXTRA)
    data.update(biomes)
    out = "{\n" + ",\n".join(
        f'  {j(cid)}: {{\n' + ",\n".join(
            ('    "regions": [\n' + ",\n".join(f"      {j(r)}" for r in b["regions"]) + "\n    ]")
            if k == "regions" else f"    {j(k)}: {j(v)}" for k, v in b.items()) + "\n  }"
        for cid, b in data.items()) + "\n}\n"
    write(p, out)
    # настройки: сложности, модификаторы, рельеф, легенда
    p = os.path.join(DATA, "config.json")
    with open(p, encoding="utf-8") as f:
        text = f.read()
    if '"difficulties"' not in text:
        body = text.rstrip()[:-1].rstrip()
        add = ",\n".join(f'  {j(k)}: {j(v)}' for k, v in CONFIG_ADD.items())
        text = body + ",\n" + add + "\n}\n"
    have = json.loads(text)
    for name, block in (("terrain", TERRAIN_ADD), ("legend", LEGEND_ADD)):
        for k, v in block.items():
            if k not in have[name]:
                anchor = f'"{name}": ' + "{"
                i = text.index(anchor) + len(anchor)
                text = text[:i] + f"\n    {j(k)}: {j(v)}," + text[i:]
    write(p, text)


if __name__ == "__main__":
    main()
