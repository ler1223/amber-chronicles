"""Переработка героев, партия 2 (design_characters.md, раздел 13): Ловчий, Криомант-зодчий, Некромант, Хрономант.
Пиромант отдаёт «Ледяную стрелу» Криоманту и получает «Раздуть»; путь «Криомант» у мага → «Поджигатель».

  Ловчий      невидимые капканы (держат и раскрывают пойманного — удар в спину для всех), приманка, метка
  Криомант    строит рельеф: ледяные стены (огонь их растапливает), каток, раскол построек осколками
  Некромант   трупы врагов — ресурс: взорвать, поднять мертвеца, пожрать ради щита
  Хрономант   откат союзника на 3 сек назад (клетка и HP), ускорение, стазис (цель вне времени)

Перезапускаемый: python tools/content_rework2.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from content_heroes import DATA, D, add, auto, branch, buff, desc, eff, fmt_entry, form, skill, tier, upsert, write  # noqa
from content_rework1 import load  # noqa: E402

SKILLS, BRANCHES, CLASSES, PATHS, TALENTS, OBJECTS, SUMMONS, GAUGES = {}, {}, {}, {}, {}, {}, {}, {}


def S(sid, sk, a, b):
    SKILLS[sid] = sk
    BRANCHES[sid] = {"A": a, "B": b}


def corpse(do, **kw):
    return {"type": "corpse", "do": do, **kw}


# ======================= Пиромант: «Раздуть» вместо «Ледяной стрелы» =======================
classes = load("classes.json")
mage = dict(classes["mage"])
mage["skills"] = ["fireball", "fan_flames", "flashpoint"]
CLASSES["mage"] = mage
S("fan_flames", skill("Раздуть", "Огонь в радиусе 2 от точки перекидывается на соседние клетки, горящие враги "
                                 "поджигают соседей. Без огня не работает.", 2, "cell",
                      [{"type": "spread_fire", "radius": 2, "duration": 4}], rng=5, cd=3, radius=2, au=auto(True)),
  branch("Пожар",
         tier("Долгий пожар", "Клетки горят 6 сек.", desc(
             "Огонь в радиусе 2 перекидывается на соседей и горит 6 сек."), eff("spread_fire", set={"duration": 6})),
         tier("Раздутый очаг", "Радиус 3.", desc("Огонь в радиусе 3 перекидывается на соседей и горит 6 сек.",
                                                   radius=3), eff("spread_fire", set={"radius": 3}))),
  branch("Жар",
         tier("Жар", "Ещё 10 урона врагам в радиусе.", desc(
             "Огонь в радиусе 2 перекидывается на соседей, врагам в радиусе 10 урона."),
             add(D(10, "spell", radius=2))),
         tier("Лёгкое дыхание", "1 AP.", desc(
             "Огонь в радиусе 2 перекидывается на соседей, врагам 10 урона. 1 AP."), {"add": {"ap": -1}})))
S("cinder_field", skill("Тлеющее поле", "Радиус 1: 8 урона + Огонь, клетки горят 6 сек.", 4, "cell",
                        [D(8, "spell", radius=1, tag="fire"),
                         {"type": "hazard", "hazard": "fire", "duration": 6, "radius": 1}], rng=5, radius=1,
                        au=auto(True, ("enemies_in_area", 2))),
  branch("Пламя",
         tier("Широкое поле", "Радиус 2.", desc("Радиус 2: 8 урона + Огонь, клетки горят 6 сек.", radius=2),
              {"radius_add": 1}),
         tier("Пекло", "Клетки горят 9 сек.", desc("Радиус 2: 8 урона + Огонь, клетки горят 9 сек."),
              eff("hazard", set={"duration": 9}))),
  branch("Искры",
         tier("Искры", "3 AP.", desc("Радиус 1: 8 урона + Огонь, клетки горят 6 сек. 3 AP."), {"add": {"ap": -1}}),
         tier("Россыпь", "Дальность 7.", desc("Радиус 1: 8 урона + Огонь, горит 6 сек, дальность 7.", range=7))))
paths = load("paths.json")
PATHS["igniter"] = {"class": "mage", "name": "Поджигатель", "desc": "«Огненный шар» → «Тлеющее поле»: сам зажигает "
                    "клетки надолго — топливо для Вспышки.", "replace": {"fireball": "cinder_field"},
                    "passive": paths["cryomancer"]["passive"] | {"name": "Тление"} if "cryomancer" in paths else
                    {"kind": "concentration", "name": "Тление", "pp": 1, "desc": "Каст прерывают: −1 деление шкалы, "
                     "каст продолжается"}, "mods": [{"stat": "hp", "add": 10}]}
warlock = dict(paths["warlock"])
warlock["replace"] = {"fan_flames": "curse"}
PATHS["warlock"] = warlock

# ======================= Ловчий =======================
CLASSES["trapper"] = {
    "name": "Ловчий", "label": "Лв", "color": [118, 140, 76], "role": "ranged", "hp": 75, "armor": 1,
    "move_time": 0.42, "attack": {"damage": 8, "range": 4, "cooldown": 1.2}, "ap_max": 6, "ap_regen": 4.5,
    "pp_max": 2, "pp_regen": 8.0,
    "passive": {"kind": "backstab", "name": "Добивание", "pp": 1, "mult": 1.5,
                "desc": "Атака по цели, которая держит другого или поймана: −1 деление шкалы, урон ×1.5"},
    "skills": ["snare", "lure", "hunter_mark"], "unlock": 80,
    "look": {"body": "humanoid", "color": [118, 140, 76], "accent": [190, 160, 100], "head": "hood", "weapon": "bow"},
    "about": "Ловчий: ставит капканы, невидимые для врага. Пойманный держится и открыт для удара в спину всем. "
             "Враги должны прийти к капканам — приманка, Таран, Страж. Слабый прямой урон, летающим капканы не страшны."}
S("snare", skill("Капкан", "Невидимый для врага капкан (до 3): 12 урона, держит 2.5 сек, пойманный раскрыт 5 сек "
                           "(удар в спину от всех, +20% урона).", 2, "cell",
                 [{"type": "trap", "hazard": "snare", "limit": 3}], rng=4, cd=2, radius=0, au=auto(True)),
  branch("Сеть капканов",
         tier("Четыре капкана", "До 4 капканов.", desc("Невидимый капкан (до 4): 12 урона, держит 2.5 сек, раскрывает."),
              eff("trap", set={"limit": 4})),
         tier("Быстрые руки", "1 AP, без перезарядки.", desc(
             "Невидимый капкан (до 4): 12 урона, держит 2.5 сек, раскрывает. 1 AP.", cooldown=0), {"add": {"ap": -1}})),
  branch("Дальний бросок",
         tier("Дальний бросок", "Дальность 6.", desc(
             "Невидимый капкан (до 3) на дальность 6: держит 2.5 сек, раскрывает.", range=6)),
         tier("Двойной капкан", "Ставит сразу два: в точку и соседнюю.", desc(
             "Два невидимых капкана рядом (до 4): держат 2.5 сек, раскрывают."),
             {"effects": [{"type": "trap", "hazard": "snare", "limit": 4}]},
             add({"type": "trap", "hazard": "snare", "limit": 4, "offset": [1, 0]}))))
S("lure", skill("Приманка", "Чучело на клетку (6 сек): враги в радиусе 3 бросаются на него.", 3, "cell",
                [{"type": "summon", "unit": "decoy", "duration": 6}], rng=4, cd=8, radius=3, free_cell=True,
                au=auto(True, ("enemies_in_area", 2))),
  branch("Крепкое чучело",
         tier("Набитое чучело", "Живёт 9 сек, прочнее.", desc("Чучело на 9 сек: враги в радиусе 3 бросаются на него."),
              eff("summon", set={"duration": 9, "power": 1.6})),
         tier("Колючее чучело", "Бьющих его ранит шипами.", desc(
             "Чучело на 9 сек: враги в радиусе 3 бросаются на него, шипы ранят бьющих."),
             eff("summon", set={"unit": "decoy_thorns"}))),
  branch("Хитрая приманка",
         tier("Дальний манок", "Дальность 6.", desc("Чучело на 6 сек на дальность 6: враги бросаются на него.",
                                                     range=6)),
         tier("Манок", "Перезарядка 5 сек.", desc("Чучело на 6 сек на дальность 6.", cooldown=5))))
S("hunter_mark", skill("Метка охотника", "Враг раскрыт 6 сек: получает +25% урона и удар в спину от всех.", 2,
                       "enemy", [buff("exposed", 1.25, 6, affects="enemies")], rng=6, cd=6, au=auto(True)),
  branch("Охота",
         tier("Долгая охота", "8 сек.", desc("Враг раскрыт 8 сек: +25% урона, удар в спину от всех."),
              eff("buff", set={"duration": 8})),
         tier("Загнанный", "+35% урона и замедление.", desc(
             "Враг раскрыт 8 сек: +35% урона, удар в спину от всех, замедлен."),
             eff("buff", set={"value": 1.35}), add(buff("slow", 1.4, 8, affects="enemies")))),
  branch("Стая",
         tier("Метка стаи", "Метка и на врагов рядом с целью.", desc(
             "Враг и соседи раскрыты 6 сек: +25% урона, удар в спину от всех.", radius=1),
             eff("buff", set={"radius": 1})),
         tier("Выстрел по метке", "Ещё и стрела: 14 урона.", desc(
             "Стрела 14 урона, враг и соседи раскрыты 6 сек."), add(D(14, "ranged")))))
S("bear_trap", skill("Медвежий капкан", "Невидимый капкан (до 2): 30 урона, держит 3.5 сек, раскрывает 6 сек.", 3,
                     "cell", [{"type": "trap", "hazard": "bear_trap", "limit": 2}], rng=4, cd=3, radius=0,
                     au=auto(True)),
  branch("Железо",
         tier("Три капкана", "До 3.", desc("Невидимый медвежий капкан (до 3): 30 урона, держит 3.5 сек."),
              eff("trap", set={"limit": 3})),
         tier("Лёгкая установка", "2 AP.", desc("Медвежий капкан (до 3), 2 AP."), {"add": {"ap": -1}})),
  branch("Дальше",
         tier("Дальний бросок", "Дальность 6.", desc("Медвежий капкан (до 2) на дальность 6.", range=6)),
         tier("Без перезарядки", "Перезарядка 0.", desc("Медвежий капкан (до 2) на дальность 6.", cooldown=0))))
S("hunting_horn", skill("Рог загонщика", "Враги в радиусе 3 отбегают на 2 клетки от ловчего — на капканы.", 3, "self",
                        [{"type": "push", "cells": 2, "radius": 3, "affects": "enemies"}], cd=8, radius=3,
                        au=auto(True, ("enemies_adjacent", 1))),
  branch("Громкий рог",
         tier("Громкий рог", "Отбегают на 3.", desc("Враги в радиусе 3 отбегают на 3 клетки."),
              eff("push", set={"cells": 3})),
         tier("Паника", "И замедлены.", desc("Враги в радиусе 3 отбегают на 3 клетки и замедлены 3 сек."),
              add(buff("slow", 1.4, 3, radius=3, affects="enemies")))),
  branch("Охотничий клич",
         tier("Перезарядка", "Перезарядка 5.", desc("Враги в радиусе 3 отбегают на 2 клетки.", cooldown=5)),
         tier("Клич", "Отряду рядом +15% урона на 5 сек.", desc(
             "Враги в радиусе 3 отбегают на 2, союзникам рядом +15% урона 5 сек."),
             add(buff("atk_mult", 1.15, 5, radius=3, affects="allies")))))
PATHS["trapmaster"] = {"class": "trapper", "name": "Капканщик", "desc": "«Приманка» → «Медвежий капкан»: меньше, "
                       "но страшнее.", "replace": {"lure": "bear_trap"},
                       "passive": {"kind": "backstab", "name": "Добивание", "pp": 1, "mult": 1.7,
                                   "desc": "Атака по пойманной цели: −1 деление шкалы, урон ×1.7"},
                       "mods": [{"stat": "atk_damage", "add": 2}]}
PATHS["beater"] = {"class": "trapper", "name": "Загонщик", "desc": "«Метка охотника» → «Рог загонщика»: гонит врагов "
                   "на капканы.", "replace": {"hunter_mark": "hunting_horn"},
                   "passive": {"kind": "dodge", "vs": ["melee"], "name": "Отскок", "pp": 1,
                               "desc": "Ближняя атака по загонщику: −1 деление шкалы, промах"},
                   "mods": [{"stat": "move_time", "mult": 0.9}]}
SUMMONS["decoy"] = {"name": "Чучело", "label": "Ч", "color": [190, 160, 100], "role": "support", "hp": 45, "armor": 2,
                    "move_time": 1.0, "attack": {"damage": 0, "range": 0, "cooldown": 9},
                    "aura": {"every": 1.0, "radius": 3, "effects": [{"type": "taunt", "radius": 3, "duration": 1.5}]},
                    "summon": True, "static": True}
SUMMONS["decoy_thorns"] = dict(SUMMONS["decoy"], name="Колючее чучело", thorns=0.6)
TALENTS.update({
    "tr_steel": {"class": "trapper", "name": "Стальные зубья", "cost": 1, "desc": "+1 к броне", "mods": [
        {"stat": "armor", "add": 1}]},
    "tr_eye": {"class": "trapper", "name": "Глаз охотника", "cost": 1, "desc": "+1 к дальности атаки",
               "mods": [{"stat": "atk_range", "add": 1}]},
    "tr_bag": {"class": "trapper", "name": "Набитая сумка", "cost": 2, "desc": "+1 деление шкалы",
               "mods": [{"stat": "pp_max", "add": 1}]},
})
GAUGES["trapper"] = {"name": "Добыча", "color": [200, 190, 120], "trickle": 8.0, "gain": {"caught": 1, "kill": 1},
                     "desc": "+1 за пойманного в капкан и за добивание"}

# ======================= Криомант-зодчий =======================
CLASSES["cryo"] = {
    "name": "Криомант", "label": "Кр", "color": [120, 176, 226], "role": "caster", "hp": 65, "armor": 0,
    "move_time": 0.48, "attack": {"damage": 6, "range": 4, "cooldown": 1.3, "tag": "ice"}, "ap_max": 7,
    "ap_regen": 4.2, "pp_max": 2, "pp_regen": 8.0,
    "passive": {"kind": "retaliate", "name": "Морозная корка", "pp": 1, "damage": 6, "tag": "ice",
                "desc": "Ближняя атака по криоманту: −1 деление шкалы, 6 урона + Лёд атакующему"},
    "skills": ["ice_wall", "rink", "shatter"], "unlock": 80,
    "look": {"body": "robe", "color": [120, 176, 226], "accent": [235, 248, 255], "head": "hood", "weapon": "staff"},
    "about": "Криомант-зодчий: строит рельеф — ледяные стены перекрывают проход, каток протаскивает толчки дальше, "
             "раскол взрывает постройки осколками. Урон наносят другие: Таран бьёт врагов о стены, Страж держит "
             "коридор. Огонь (свой Пиромант!) растапливает стены."}
OBJECTS["ice_wall"] = {"name": "Ледяная стена", "hp": 40, "color": [170, 220, 250], "art": "ice_block",
                       "cover": "full", "ignite": ["fire"], "on_break": {"radius": 0, "hazard": "ice", "hazard_time": 4},
                       "desc": "Перекрывает путь и укрывает. Тает со временем, огонь растапливает сразу"}
OBJECTS["bone_wall"] = {"name": "Костяная стена", "hp": 50, "color": [220, 210, 190], "art": "bones",
                        "cover": "full", "desc": "Перекрывает путь и укрывает. Рассыпается со временем"}
S("ice_wall", skill("Ледяная стена", "Стена из 3 глыб поперёк направления (10 сек): перекрывает путь, укрывает.", 3,
                    "cell", [{"type": "wall", "object": "ice_wall", "length": 3, "life": 10}], rng=4, cd=5, radius=1,
                    au=auto(True, ("enemies_in_area", 1))),
  branch("Крепость",
         tier("Длинная стена", "5 глыб.", desc("Стена из 5 глыб поперёк направления (10 сек)."),
              eff("wall", set={"length": 5})),
         tier("Вечный лёд", "Стоит 16 сек.", desc("Стена из 5 глыб поперёк направления (16 сек)."),
              eff("wall", set={"life": 16}))),
  branch("Ловушка изо льда",
         tier("Быстрая кладка", "2 AP.", desc("Стена из 3 глыб поперёк направления (10 сек). 2 AP."),
              {"add": {"ap": -1}}),
         tier("Морозный выдох", "Врагам у стены Лёд.", desc(
             "Стена из 3 глыб (10 сек), врагам рядом Лёд."), add({"type": "status", "tag": "ice", "radius": 1}))))
S("rink", skill("Каток", "Радиус 1: клетки 8 сек скользкий лёд — шаги и толчки проезжают дальше.", 2, "cell",
                [{"type": "terrain", "terrain": "ice_floor", "radius": 1, "duration": 8}], rng=5, cd=6, radius=1,
                au=auto(True, ("enemies_in_area", 2))),
  branch("Большой каток",
         tier("Большой каток", "Радиус 2.", desc("Радиус 2: клетки 8 сек скользкий лёд.", radius=2),
              eff("terrain", set={"radius": 2})),
         tier("Долгий каток", "12 сек.", desc("Радиус 2: клетки 12 сек скользкий лёд."),
              eff("terrain", set={"duration": 12}))),
  branch("Гололёд",
         tier("Гололёд", "Врагам Лёд (замедление).", desc("Радиус 1: скользкий лёд 8 сек, врагам Лёд."),
              add({"type": "status", "tag": "ice", "radius": 1})),
         tier("Хрусткий лёд", "И 12 урона.", desc("Радиус 1: скользкий лёд 8 сек, врагам Лёд и 12 урона."),
              add(D(12, "spell", radius=1)))))
S("shatter", skill("Раскол", "Свои ледяные постройки в радиусе 6 взрываются: врагам рядом с каждой 18 урона + Лёд.",
                   3, "self", [{"type": "shatter", "radius": 6, "amount": 18, "blast": 1, "tag": "ice"}], cd=4,
                   au=auto(True)),
  branch("Шрапнель",
         tier("Острые осколки", "26 урона.", desc("Свои постройки взрываются: врагам рядом 26 урона + Лёд."),
              eff("shatter", set={"amount": 26})),
         tier("Широкий разлёт", "Радиус осколков 2.", desc("Свои постройки взрываются: 26 урона + Лёд в радиусе 2."),
              eff("shatter", set={"blast": 2}))),
  branch("Хрупкость",
         tier("Хрупкость", "2 AP.", desc("Свои постройки взрываются: 18 урона + Лёд. 2 AP."), {"add": {"ap": -1}}),
         tier("Иней", "Задетые замедлены сильнее.", desc("Свои постройки взрываются: 18 урона + Лёд, замедление."),
              add(buff("slow", 1.5, 4, radius=6, affects="enemies")))))
S("frost_guard", skill("Ледяная броня", "Союзнику щит 40 и +3 брони на 6 сек.", 3, "ally",
                       [{"type": "shield", "amount": 40, "duration": 6}, buff("armor", 3, 6)], rng=4, cd=5,
                       au=auto(True, ("ally_hp_below", 60))),
  branch("Панцирь",
         tier("Толстый панцирь", "Щит 60.", desc("Союзнику щит 60 и +3 брони на 6 сек."),
              eff("shield", set={"amount": 60})),
         tier("Отражение", "Бьющих его — Лёд.", desc("Союзнику щит 60, +3 брони и шипы изо льда 6 сек."),
              add(buff("thorns", 0.3, 6)))),
  branch("Ледяной кокон",
         tier("Кокон", "Ещё стена-глыба рядом с союзником.", desc(
             "Союзнику щит 40, +3 брони; рядом встаёт ледяная глыба."),
             add({"type": "wall", "object": "ice_wall", "length": 1, "life": 8})),
         tier("Быстрый лёд", "2 AP.", desc("Союзнику щит 40, +3 брони, глыба рядом. 2 AP."), {"add": {"ap": -1}})))
PATHS["iceguard"] = {"class": "cryo", "name": "Ледяной страж", "desc": "«Каток» → «Ледяная броня»: защищает союзников.",
                     "replace": {"rink": "frost_guard"},
                     "passive": {"kind": "block", "name": "Ледяной панцирь", "pp": 1, "mult": 0.6,
                                 "desc": "Любой удар: −1 деление шкалы, урон ×0.6"}, "mods": [{"stat": "hp", "add": 20}]}
PATHS["stormfrost"] = {"class": "cryo", "name": "Повелитель метели", "desc": "«Раскол» → «Буран»: ледяная буря по "
                       "площади.", "replace": {"shatter": "blizzard"},
                       "passive": {"kind": "concentration", "name": "Холодный ум", "pp": 1,
                                   "desc": "Каст прерывают: −1 деление шкалы, каст продолжается"},
                       "mods": [{"stat": "power", "mult": 1.05}]}
TALENTS.update({
    "cr_glacier": {"class": "cryo", "name": "Ледник", "cost": 1, "desc": "+20 HP", "mods": [{"stat": "hp", "add": 20}]},
    "cr_wall": {"class": "cryo", "name": "Толстые стены", "cost": 1, "desc": "Ледяная стена стоит на 4 сек дольше",
                "mods": [{"skill": "ice_wall", "effect": {"type": "wall", "add": {"life": 4}}}]},
    "cr_frost": {"class": "cryo", "name": "Стужа", "cost": 2, "desc": "+1 деление шкалы",
                 "mods": [{"stat": "pp_max", "add": 1}]},
})
GAUGES["cryo"] = {"name": "Стужа", "color": [170, 225, 255], "trickle": 8.0, "gain": {"structures": 2.0},
                  "desc": "+1 за 2 сек, пока стоят его постройки"}

# ======================= Некромант =======================
CLASSES["necro"] = {
    "name": "Некромант", "label": "Нк", "color": [96, 80, 120], "role": "caster", "hp": 70, "armor": 0,
    "move_time": 0.5, "attack": {"damage": 7, "range": 4, "cooldown": 1.3, "tag": "poison"}, "ap_max": 7,
    "ap_regen": 4.2, "pp_max": 2, "pp_regen": 8.0,
    "passive": {"kind": "siphon", "name": "Жатва", "pp": 1, "pct": 0.3,
                "desc": "Урон навыком: −1 деление шкалы, некромант лечится на 30% нанесённого"},
    "skills": ["corpse_blast", "raise_dead", "devour"], "unlock": 80,
    "look": {"body": "robe", "color": [70, 60, 90], "accent": [150, 230, 120], "head": "hood", "weapon": "staff"},
    "about": "Некромант-могильщик: павшие враги оставляют трупы на 14 сек — его ресурс: взорвать, поднять мертвеца, "
             "пожрать ради щита. Пока никто не умер, почти бесполезен: нужны убийцы (Ассасин, Снайпер)."}
S("corpse_blast", skill("Взрыв трупа", "Труп у точки взрывается: 24 урона + Яд в радиусе 1.", 2, "cell",
                        [corpse("blast", amount=24, radius=1, tag="poison")], rng=5, radius=1, au=auto(True),
                        needs_corpse=True),
  branch("Гниль",
         tier("Тухлый взрыв", "32 урона.", desc("Труп взрывается: 32 урона + Яд в радиусе 1."),
              eff("corpse", set={"amount": 32})),
         tier("Широкий взрыв", "Радиус 2.", desc("Труп взрывается: 32 урона + Яд в радиусе 2.", radius=2),
              eff("corpse", set={"radius": 2}))),
  branch("Цепь трупов",
         tier("Дальний взрыв", "Дальность 7.", desc("Труп взрывается: 24 урона + Яд в радиусе 1.", range=7)),
         tier("Лёгкая рука", "1 AP.", desc("Труп взрывается: 24 урона + Яд. 1 AP."), {"add": {"ap": -1}})))
S("raise_dead", skill("Поднять мертвеца", "Труп встаёт скелетом на 15 сек (до 2).", 3, "cell",
                      [corpse("raise", unit="risen", limit=2, duration=15)], rng=5, cd=3, radius=1, au=auto(True),
                      needs_corpse=True),
  branch("Армия",
         tier("Трое", "До 3 мертвецов.", desc("Труп встаёт скелетом на 15 сек (до 3)."),
              eff("corpse", set={"limit": 3})),
         tier("Долгая нежизнь", "25 сек.", desc("Труп встаёт скелетом на 25 сек (до 3)."),
              eff("corpse", set={"duration": 25}))),
  branch("Рыцарь смерти",
         tier("Костяной рыцарь", "Поднимает крепкого рыцаря (до 1).", form(
             "Костяной рыцарь", "Труп встаёт рыцарем на 15 сек (до 1).",
             [corpse("raise", unit="risen_knight", limit=1, duration=15)])),
         tier("Клятва", "Рыцарь стоит 25 сек.", desc("Труп встаёт рыцарем на 25 сек (до 1)."),
              eff("corpse", set={"duration": 25}))))
S("devour", skill("Пожрать", "Трупы в радиусе 2 исчезают: некроманту щит 18 за каждый.", 2, "self",
                  [corpse("devour", radius=2, shield=18)], cd=4, radius=2, au=auto(True), needs_corpse=True),
  branch("Ненасытность",
         tier("Ненасытность", "Щит 26 за труп.", desc("Трупы в радиусе 2: щит 26 за каждый."),
              eff("corpse", set={"shield": 26})),
         tier("Длинные руки", "Радиус 3.", desc("Трупы в радиусе 3: щит 26 за каждый.", radius=3),
              eff("corpse", set={"radius": 3}))),
  branch("Пир",
         tier("Пир", "И лечение 10 за труп.", desc("Трупы в радиусе 2: щит 18 и +10 HP за каждый."),
              add({"type": "heal", "amount": 20, "at": "caster"})),
         tier("Без перезарядки", "Перезарядка 0.", desc("Трупы в радиусе 2: щит 18 и HP.", cooldown=0))))
S("corpse_cloud", skill("Чумной труп", "Труп у точки становится облаком яда (радиус 1, 6 сек, только по врагам).", 2,
                        "cell", [corpse("cloud", radius=1, duration=6)], rng=5, radius=1, au=auto(True),
                        needs_corpse=True),
  branch("Мор", tier("Мор", "Радиус 2.", desc("Труп — облако яда радиусом 2 на 6 сек.", radius=2),
                     eff("corpse", set={"radius": 2})),
         tier("Долгий мор", "10 сек.", desc("Труп — облако яда радиусом 2 на 10 сек."),
              eff("corpse", set={"duration": 10}))),
  branch("Зараза", tier("Дальше", "Дальность 7.", desc("Труп — облако яда на 6 сек, дальность 7.", range=7)),
         tier("1 AP", "1 AP.", desc("Труп — облако яда на 6 сек. 1 AP."), {"add": {"ap": -1}})))
S("bone_wall", skill("Костяная стена", "Труп у точки становится костяной стеной (12 сек): перекрывает путь.", 2,
                     "cell", [corpse("wall", object="bone_wall", life=12)], rng=5, radius=1, au=auto(False),
                     needs_corpse=True),
  branch("Ограда", tier("Прочная", "Стоит 18 сек.", desc("Труп — костяная стена на 18 сек."),
                        eff("corpse", set={"life": 18})),
         tier("Дальше", "Дальность 7.", desc("Труп — костяная стена на 18 сек, дальность 7.", range=7))),
  branch("Склеп", tier("1 AP", "1 AP.", desc("Труп — костяная стена на 12 сек. 1 AP."), {"add": {"ap": -1}}),
         tier("Склеп", "Ещё и щит некроманту 15.", desc("Труп — стена, некроманту щит 15."),
              add({"type": "shield", "amount": 15, "duration": 6, "at": "caster"}))))
PATHS["plaguebearer"] = {"class": "necro", "name": "Чумной", "desc": "«Поднять мертвеца» → «Чумной труп»: облака яда.",
                         "replace": {"raise_dead": "corpse_cloud"},
                         "passive": {"kind": "retaliate", "name": "Миазмы", "pp": 1, "damage": 6, "tag": "poison",
                                     "desc": "Ближняя атака по некроманту: −1 деление шкалы, 6 урона + Яд"},
                         "mods": [{"stat": "hp", "add": 10}]}
PATHS["bonelord"] = {"class": "necro", "name": "Костяной лорд", "desc": "«Пожрать» → «Костяная стена»: строит из "
                     "трупов.", "replace": {"devour": "bone_wall"},
                     "passive": {"kind": "block", "name": "Костяной доспех", "pp": 1, "mult": 0.6,
                                 "desc": "Любой удар: −1 деление шкалы, урон ×0.6"}, "mods": [{"stat": "armor", "add": 1}]}
SUMMONS["risen"] = {"name": "Поднятый мертвец", "label": "М", "color": [200, 196, 170], "role": "melee", "hp": 40,
                    "armor": 1, "move_time": 0.6, "attack": {"damage": 8, "range": 1, "cooldown": 1.2}, "summon": True,
                    "look": {"body": "skeleton", "color": [210, 205, 180], "accent": [140, 230, 120]}}
SUMMONS["risen_knight"] = {"name": "Костяной рыцарь", "label": "Р", "color": [190, 186, 170], "role": "melee",
                           "hp": 90, "armor": 3, "move_time": 0.6, "attack": {"damage": 14, "range": 1, "cooldown": 1.3},
                           "summon": True,
                           "look": {"body": "skeleton", "color": [190, 186, 170], "accent": [140, 230, 120],
                                    "head": "helm", "weapon": "sword"}}
TALENTS.update({
    "nc_grave": {"class": "necro", "name": "Могильный холод", "cost": 1, "desc": "+15 HP",
                 "mods": [{"stat": "hp", "add": 15}]},
    "nc_rot": {"class": "necro", "name": "Гниение", "cost": 1, "desc": "Взрыв трупа: +8 урона",
               "mods": [{"skill": "corpse_blast", "effect": {"type": "corpse", "add": {"amount": 8}}}]},
    "nc_souls": {"class": "necro", "name": "Сосуд душ", "cost": 2, "desc": "+1 деление шкалы",
                 "mods": [{"stat": "pp_max", "add": 1}]},
})
GAUGES["necro"] = {"name": "Души", "color": [150, 230, 120], "trickle": 8.0, "gain": {"corpse": 1},
                   "desc": "+1 за использованный труп"}

# ======================= Хрономант =======================
CLASSES["chrono"] = {
    "name": "Хрономант", "label": "Хр", "color": [206, 176, 96], "role": "support", "hp": 70, "armor": 0,
    "move_time": 0.48, "attack": {"damage": 6, "range": 4, "cooldown": 1.3}, "ap_max": 7, "ap_regen": 4.0,
    "pp_max": 2, "pp_regen": 5.0,
    "passive": {"kind": "dodge", "vs": ["melee", "ranged", "spell"], "name": "Предвидение", "pp": 1,
                "desc": "Любая атака по хрономанту: −1 деление шкалы, промах"},
    "skills": ["rewind", "haste", "stasis"], "unlock": 80,
    "look": {"body": "robe", "color": [206, 176, 96], "accent": [120, 210, 240], "head": "hat", "weapon": "staff"},
    "about": "Хрономант: время. Откат возвращает союзника на клетку и к HP трёхсекундной давности, ускорение "
             "разгоняет AP и атаки, стазис выключает цель из времени (неуязвима и не действует). Сам почти не бьёт; "
             "стазис может спасти врага, если ошибиться."}
S("rewind", skill("Откат", "Союзник возвращается на клетку и к HP, какие были 3 сек назад (HP — только если было "
                           "больше).", 3, "ally", [{"type": "rewind", "seconds": 3.0}], rng=5, cd=6,
                  au=auto(True, ("ally_hp_below", 40))),
  branch("Глубокий откат",
         tier("Пять секунд", "Откат на 4.5 сек.", desc("Союзник возвращается на 4.5 сек назад (клетка и HP)."),
              eff("rewind", set={"seconds": 4.5})),
         tier("Чистое прошлое", "Ещё и снимает теги.", desc("Откат на 4.5 сек и очищение от тегов."),
              add({"type": "cleanse"}))),
  branch("Скорый откат",
         tier("Скорый откат", "Перезарядка 3 сек.", desc("Союзник возвращается на 3 сек назад.", cooldown=3)),
         tier("Дальний откат", "Дальность 7.", desc("Союзник возвращается на 3 сек назад, дальность 7.", range=7))))
S("haste", skill("Ускорение", "Союзник 6 сек: AP копятся вдвое быстрее, атаки на 30% быстрее.", 3, "ally",
                 [buff("ap_rate", 0.5, 6), buff("atk_speed", 0.7, 6)], rng=5, cd=8, au=auto(True)),
  branch("Разгон",
         tier("Долгий разгон", "9 сек.", desc("Союзник 9 сек: AP вдвое быстрее, атаки быстрее."),
              eff("buff", set={"duration": 9})),
         tier("Вихрь времени", "И +2 AP сразу.", desc("Союзник 9 сек: AP вдвое быстрее, атаки быстрее, +2 AP."),
              add({"type": "refresh", "ap": 2}))),
  branch("Поток",
         tier("Поток", "И движение быстрее.", desc("Союзник 6 сек: AP, атаки и шаги быстрее."),
              add(buff("slow", 0.7, 6))),
         tier("Общий поток", "И союзникам рядом.", desc("Союзник и соседи 6 сек: AP, атаки и шаги быстрее.",
                                                         radius=1), {"radius_add": 1})))
S("stasis", skill("Стазис", "Цель (враг или союзник) 3 сек вне времени: неуязвима и не действует.", 3, "enemy",
                  [{"type": "stasis", "duration": 3}], rng=5, cd=8, au=auto(True, ("target_casting",))),
  branch("Остановка",
         tier("Долгий стазис", "4.5 сек.", desc("Цель 4.5 сек вне времени: неуязвима и не действует."),
              eff("stasis", set={"duration": 4.5})),
         tier("Мгновение", "2 AP.", desc("Цель 4.5 сек вне времени. 2 AP."), {"add": {"ap": -1}})),
  branch("Спасение",
         tier("Спасти своего", "Стазис на союзника: спасает от смерти.", form(
             "Стазис союзника", "Союзник 3 сек вне времени: неуязвим, не действует.",
             [{"type": "stasis", "duration": 3}], target="ally", auto=auto(True, ("ally_hp_below", 20)))),
         tier("Короткий стазис", "Перезарядка 5.", desc("Союзник 3 сек вне времени.", cooldown=5))))
S("slow_field", skill("Вязкое время", "Радиус 1: враги 5 сек ходят вдвое медленнее и бьют на 40% реже.", 3, "cell",
                      [buff("slow", 2.0, 5, radius=1, affects="enemies"),
                       buff("atk_speed", 1.4, 5, radius=1, affects="enemies")], rng=5, cd=6, radius=1,
                      au=auto(True, ("enemies_in_area", 2))),
  branch("Трясина времени", tier("Шире", "Радиус 2.", desc("Радиус 2: враги 5 сек медленнее.", radius=2),
                                 {"radius_add": 1}),
         tier("Дольше", "8 сек.", desc("Радиус 2: враги 8 сек медленнее."), eff("buff", set={"duration": 8}))),
  branch("Застывший миг", tier("2 AP", "2 AP.", desc("Радиус 1: враги 5 сек медленнее. 2 AP."), {"add": {"ap": -1}}),
         tier("Хрупкий миг", "Задетые получают +15% урона.", desc("Радиус 1: враги медленнее и уязвимее."),
              add(buff("dmg_taken", 1.15, 5, radius=1, affects="enemies")))))
S("rewind_foe", skill("Вспять", "Враг возвращается на клетку, где был 3 сек назад.", 2, "enemy",
                      [{"type": "rewind", "seconds": 3.0, "hp": False}], rng=6, cd=4, au=auto(True)),
  branch("Дальше назад", tier("Пять секунд", "4.5 сек назад.", desc("Враг возвращается на 4.5 сек назад."),
                              eff("rewind", set={"seconds": 4.5})),
         tier("Сбить с толку", "И оглушение 1 сек.", desc("Враг на 4.5 сек назад и оглушён 1 сек."),
              add({"type": "stun", "duration": 1.0}))),
  branch("Петля", tier("Петля", "Перезарядка 2.", desc("Враг возвращается на 3 сек назад.", cooldown=2)),
         tier("1 AP", "1 AP.", desc("Враг возвращается на 3 сек назад. 1 AP."), {"add": {"ap": -1}})))
PATHS["momentkeeper"] = {"class": "chrono", "name": "Хранитель мгновения", "desc": "«Стазис» → «Вязкое время»: "
                         "замедляет врагов по площади.", "replace": {"stasis": "slow_field"},
                         "passive": {"kind": "concentration", "name": "Безвременье", "pp": 1,
                                     "desc": "Каст прерывают: −1 деление шкалы, каст продолжается"},
                         "mods": [{"stat": "hp", "add": 15}]}
PATHS["fateweaver"] = {"class": "chrono", "name": "Ткач судьбы", "desc": "«Ускорение» → «Вспять»: отбрасывает врага "
                       "назад во времени.", "replace": {"haste": "rewind_foe"},
                       "passive": {"kind": "dodge", "vs": ["melee", "ranged", "spell"], "name": "Предвидение", "pp": 1,
                                   "desc": "Любая атака: −1 деление шкалы, промах"},
                       "mods": [{"stat": "ap_max", "add": 1}]}
TALENTS.update({
    "ch_sand": {"class": "chrono", "name": "Песочные часы", "cost": 2, "desc": "+1 деление шкалы",
                "mods": [{"stat": "pp_max", "add": 1}]},
    "ch_tempo": {"class": "chrono", "name": "Темп", "cost": 1, "desc": "+1 AP", "mods": [{"stat": "ap_max", "add": 1}]},
    "ch_robe": {"class": "chrono", "name": "Ткань времён", "cost": 1, "desc": "+15 HP", "mods": [{"stat": "hp", "add": 15}]},
})
GAUGES["chrono"] = {"name": "Песок", "color": [230, 200, 120], "trickle": 4.0, "gain": {},
                    "desc": "сам копится раз в 4 сек"}


def main():
    upsert("skills.json", SKILLS, "fields")
    upsert("branches.json", BRANCHES, "branches")
    upsert("classes.json", CLASSES, "fields")
    upsert("talents.json", TALENTS, "line")
    upsert("objects.json", OBJECTS, "line")
    upsert("summons.json", SUMMONS, "fields")
    paths = load("paths.json")
    paths.pop("cryomancer", None)                     # путь мага «Криомант» стал отдельным героем
    paths.update(PATHS)
    write(os.path.join(DATA, "paths.json"),
          "{\n" + ",\n".join(fmt_entry(k, v, "fields") for k, v in paths.items()) + "\n}\n")
    gauges = load("gauges.json")
    gauges.update(GAUGES)
    j = lambda v: json.dumps(v, ensure_ascii=False)  # noqa: E731
    write(os.path.join(DATA, "gauges.json"), "{\n" + ",\n".join(f"  {j(k)}: {j(v)}" for k, v in gauges.items()) + "\n}\n")
    print(f"навыков {len(SKILLS)}, классов {len(CLASSES)}, путей {len(PATHS)}, талантов {len(TALENTS)}")


if __name__ == "__main__":
    main()
