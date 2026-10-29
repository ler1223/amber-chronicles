"""Переработка героев, партии 3–4 (design_characters.md, раздел 13).

  Гравитомант  стягивает врагов в кучу, меняется местами с целью, поднимает врага в воздух (толчок — дальше)
  Геомант      «Сила земли» зависит от клетки под ногами; перековывает клетку; поднимает валун для Тарана
  Зельевар     сам почти не бьёт: смазывает оружие союзников тегами, кидает склянки, «Реактив» — урон за теги
  Берсерк      навыки стоят HP, чем меньше HP — тем сильнее; в трансе лечение превращается в ярость
  Тактик       приказы: «Вперёд!» (ещё атака), «Перестроение», «Фокус»; знамя — аура брони
  Связующий    привязь делит урон союзника пополам, «Слияние» — входит в союзника, «Отдать силы»

Порядок генераторов: content_rework1 → content_rework2 → content_rework3 (перезапускаемые).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from content_heroes import DATA, D, add, auto, branch, buff, desc, eff, form, skill, tier, upsert, write  # noqa
from content_rework1 import load  # noqa: E402

SKILLS, BRANCHES, CLASSES, PATHS, TALENTS, GAUGES = {}, {}, {}, {}, {}, {}


def S(sid, sk, a, b):
    SKILLS[sid] = sk
    BRANCHES[sid] = {"A": a, "B": b}


def hero(cid, name, label, color, role, hp, armor, move, atk, ap, ap_regen, passive, skills, look, about, **kw):
    CLASSES[cid] = {"name": name, "label": label, "color": color, "role": role, "hp": hp, "armor": armor,
                    "move_time": move, "attack": atk, "ap_max": ap, "ap_regen": ap_regen, "pp_max": 2,
                    "pp_regen": 8.0, "passive": passive, "skills": skills, "unlock": 80, "look": look,
                    "about": about, **kw}


def talents(cid, *items):
    for tid, name, cost, d, mods in items:
        TALENTS[tid] = {"class": cid, "name": name, "cost": cost, "desc": d, "mods": mods}


def ap1(text, **sets):
    return [desc(text, **sets), {"add": {"ap": -1}}]


# ======================= Гравитомант =======================
hero("gravity", "Гравитомант", "Гр", [110, 90, 170], "caster", 65, 0, 0.5, {"damage": 6, "range": 4, "cooldown": 1.3},
     7, 4.2, {"kind": "concentration", "name": "Тяжёлый взгляд", "pp": 1,
              "desc": "Каст прерывают: −1 деление шкалы, каст продолжается"},
     ["singularity", "swap", "levitate"],
     {"body": "robe", "color": [70, 56, 120], "accent": [190, 160, 255], "head": "hood", "weapon": "staff"},
     "Гравитомант: стягивает врагов в кучу под чужой удар (Подрывник, Пиромант), меняется местами с целью, "
     "поднимает врага в воздух — толчок по нему летит дальше. Почти без урона; обмен может подставить своих.")
S("singularity", skill("Сингулярность", "Враги в радиусе 2 стягиваются к точке на 2 клетки.", 4, "cell",
                       [{"type": "gather", "radius": 2, "cells": 2}], rng=5, cd=6, radius=2,
                       au=auto(True, ("enemies_in_area", 2))),
  branch("Чёрная дыра",
         tier("Глубокая воронка", "Тянет на 3 клетки.", desc("Враги в радиусе 2 стягиваются к точке на 3 клетки."),
              eff("gather", set={"cells": 3})),
         tier("Горизонт", "Радиус 3.", desc("Враги в радиусе 3 стягиваются к точке на 3 клетки.", radius=3),
              eff("gather", set={"radius": 3}))),
  branch("Сжатие",
         tier("Сжатие", "И 10 урона каждому.", desc("Враги в радиусе 2 стягиваются к точке и получают 10 урона."),
              eff("gather", set={"amount": 10})),
         tier("Лёгкая воронка", "3 AP.", *ap1("Враги в радиусе 2 стягиваются к точке, 10 урона. 3 AP."))))
S("swap", skill("Обмен", "Гравитомант и враг меняются местами (до 5 клеток).", 2, "enemy", [{"type": "swap"}], rng=5,
                cd=5, au=auto(False)),
  branch("Подмена",
         tier("Ловушка", "Враг на новом месте оглушён на 1 сек.", desc(
             "Гравитомант и враг меняются местами, враг оглушён 1 сек."), add({"type": "stun", "duration": 1.0})),
         tier("Короткий обмен", "Перезарядка 3.", desc("Меняются местами, враг оглушён 1 сек.", cooldown=3))),
  branch("Спасение",
         tier("Спасти своего", "Обмен с союзником: вытащить его из окружения.", form(
             "Обмен с союзником", "Гравитомант и союзник меняются местами (до 5).", [{"type": "swap"}],
             target="ally", auto=auto(True, ("ally_hp_below", 30)))),
         tier("Щит при обмене", "Союзнику щит 25.", desc("Меняются местами, союзнику щит 25."),
              add({"type": "shield", "amount": 25, "duration": 5}))))
S("levitate", skill("Невесомость", "Враг 3 сек в воздухе: не действует, толчок по нему на 2 клетки дальше, падая — "
                                    "12 урона.", 3, "enemy", [{"type": "levitate", "duration": 3, "fall": 12}], rng=5,
                    cd=6, au=auto(True, ("target_casting",))),
  branch("Высота",
         tier("Высоко", "Падение — 24 урона.", desc("Враг 3 сек в воздухе, падая — 24 урона."),
              eff("levitate", set={"fall": 24})),
         tier("Долгий полёт", "4.5 сек.", desc("Враг 4.5 сек в воздухе, падая — 24 урона."),
              eff("levitate", set={"duration": 4.5}))),
  branch("Подъём",
         tier("Подъём толпы", "Поднимает и врагов рядом.", desc("Враг и соседи 3 сек в воздухе.", radius=1),
              {"effects": [{"type": "levitate", "duration": 3, "fall": 12}]}),
         tier("Лёгкость", "2 AP.", *ap1("Враг 3 сек в воздухе. 2 AP."))))
S("collapse", skill("Коллапс", "Враги в радиусе 2: 6 урона + 6 за каждого врага в радиусе.", 4, "cell",
                    [{"type": "collapse", "radius": 2, "amount": 6, "per_unit": 6}], rng=5, cd=5, radius=2,
                    au=auto(True, ("enemies_in_area", 2))),
  branch("Масса", tier("Плотность", "8 за каждого.", desc("Враги в радиусе 2: 6 + 8 за каждого."),
                       eff("collapse", set={"per_unit": 8})),
         tier("Звезда", "Радиус 3.", desc("Враги в радиусе 3: 6 + 8 за каждого.", radius=3),
              eff("collapse", set={"radius": 3}))),
  branch("Быстро", tier("3 AP", "3 AP.", *ap1("Враги в радиусе 2: 6 + 6 за каждого. 3 AP.")),
         tier("Без отката", "Перезарядка 2.", desc("Враги в радиусе 2: 6 + 6 за каждого.", cooldown=2))))
S("repulse", skill("Отталкивание", "Враги в радиусе 2 от точки разлетаются на 2 клетки.", 3, "cell",
                   [{"type": "push", "cells": 2, "radius": 2, "affects": "enemies", "from": "center"}], rng=5, cd=5,
                   radius=2, au=auto(True, ("enemies_in_area", 2))),
  branch("Волна", tier("Сильная волна", "На 3 клетки.", desc("Враги в радиусе 2 разлетаются на 3 клетки."),
                       eff("push", set={"cells": 3})),
         tier("И урон", "10 урона.", desc("Враги разлетаются на 3 клетки, 10 урона."),
              eff("push", set={"amount": 10}))),
  branch("Импульс", tier("2 AP", "2 AP.", *ap1("Враги в радиусе 2 разлетаются на 2 клетки. 2 AP.")),
         tier("Частые импульсы", "Перезарядка 3.", desc("Враги разлетаются на 2 клетки.", cooldown=3))))
PATHS["collapser"] = {"class": "gravity", "name": "Коллапсар", "desc": "«Обмен» → «Коллапс»: урон по куче.",
                      "replace": {"swap": "collapse"}, "passive": {"kind": "siphon", "name": "Поглощение", "pp": 1,
                                                                   "pct": 0.25, "desc": "Урон навыком: −1 деление "
                                                                   "шкалы, лечится на 25%"},
                      "mods": [{"stat": "power", "mult": 1.05}]}
PATHS["orbiter"] = {"class": "gravity", "name": "Орбита", "desc": "«Невесомость» → «Отталкивание»: разбрасывает "
                    "врагов о стены и бочки.", "replace": {"levitate": "repulse"},
                    "passive": {"kind": "dodge", "vs": ["ranged"], "name": "Искривление", "pp": 1,
                                "desc": "Дальняя атака: −1 деление шкалы, промах"}, "mods": [{"stat": "hp", "add": 15}]}
talents("gravity", ("gr_mass", "Плотная мантия", 1, "+15 HP", [{"stat": "hp", "add": 15}]),
        ("gr_pull", "Сильное притяжение", 1, "Сингулярность тянет на клетку дальше",
         [{"skill": "singularity", "effect": {"type": "gather", "add": {"cells": 1}}}]),
        ("gr_core", "Ядро", 2, "+1 деление шкалы", [{"stat": "pp_max", "add": 1}]))
GAUGES["gravity"] = {"name": "Масса", "color": [180, 150, 255], "trickle": 8.0, "gain": {"pulled": 1},
                     "desc": "+1 за каждого стянутого врага"}

# ======================= Геомант =======================
EARTH = {
    "grass": [D(14, "spell"), {"type": "stun", "duration": 1.4, "look": "root"}],
    "water": [D(20, "spell", tag="water"), {"type": "knockback", "cells": 1}],
    "stone": [D(34, "ranged")],
    "lava": [D(24, "spell", radius=1, tag="fire")],
    "ice_floor": [D(22, "spell", radius=1, tag="ice")],
    "default": [D(18, "spell")],
}
hero("geomancer", "Геомант", "Гм", [150, 120, 80], "caster", 85, 1, 0.5, {"damage": 7, "range": 4, "cooldown": 1.3},
     7, 4.2, {"kind": "block", "name": "Каменная кожа", "pp": 1, "mult": 0.65,
              "desc": "Любой удар: −1 деление шкалы, урон ×0.65"},
     ["earth_power", "reshape", "rockfall"],
     {"body": "humanoid", "color": [150, 120, 80], "accent": [120, 200, 120], "head": "hood", "weapon": "staff"},
     "Геомант: один навык — разный по клетке под ногами: трава — корни, вода — волна, камень — валун, лава — "
     "извержение, лёд — шипы. Перековывает клетку под собой и поднимает валуны (Тарану — снаряды). На однородной "
     "карте слабее; пока выбирает землю — нужен прикрывающий.")
S("earth_power", skill("Сила земли", "По клетке под ногами: трава — 14 урона и корни 1.4 сек; вода — 20 + Вода и "
                                      "толчок; камень — 34 урона; лава — 24 + Огонь рядом; лёд — 22 + Лёд рядом.", 3,
                       "enemy", [{"type": "terrain_cast", "by": EARTH}], rng=4, cd=1.5, au=auto(True)),
  branch("Родство",
         tier("Глубокая связь", "Всё сильнее на треть.", desc("Сила земли по клетке под ногами — на треть сильнее."),
              {"effects": [{"type": "terrain_cast", "by": {
                  k: [dict(e, amount=int(e["amount"] * 1.33)) if e["type"] == "damage" else e for e in v]
                  for k, v in EARTH.items()}}]}),
         tier("Дальше", "Дальность 6.", desc("Сила земли (на треть сильнее), дальность 6.", range=6))),
  branch("Ритм земли",
         tier("Без отката", "Перезарядка 0.", desc("Сила земли по клетке под ногами.", cooldown=0)),
         tier("2 AP", "2 AP.", *ap1("Сила земли по клетке под ногами. 2 AP."))))
S("reshape", skill("Перековать", "Клетка под геомантом на 20 сек: трава → вода → камень → трава.", 1, "self",
                   [{"type": "terrain", "cycle": ["grass", "water", "stone"], "radius": 0, "duration": 20}], cd=2,
                   au=auto(False)),
  branch("Широкий шаг",
         tier("Вокруг себя", "И клетки рядом.", desc("Клетки в радиусе 1 перековываются на 20 сек.", radius=1),
              eff("terrain", set={"radius": 1})),
         tier("Навсегда почти", "60 сек.", desc("Клетки в радиусе 1 перековываются на 60 сек."),
              eff("terrain", set={"duration": 60}))),
  branch("Огненный путь",
         tier("Жар земли", "В цикле есть лава (стоять на ней больно).", desc(
             "Клетка под геомантом: трава → вода → камень → лава → трава (20 сек)."),
             eff("terrain", set={"cycle": ["grass", "water", "stone", "lava"]})),
         tier("Мгновенно", "Без перезарядки.", desc("Клетка: трава → вода → камень → лава.", cooldown=0))))
S("rockfall", skill("Обвал", "Валун падает на свободную клетку (до 2): 14 урона врагам рядом. Валун — укрытие и снаряд "
                              "для Тарана.", 3, "cell",
                    [{"type": "place_object", "object": "boulder", "limit": 2}, D(14, "spell", radius=1)], rng=5, cd=4,
                    radius=1, free_cell=True, au=auto(True, ("enemies_in_area", 1))),
  branch("Камнепад", tier("Тяжёлый", "20 урона.", desc("Валун (до 2): 20 урона врагам рядом."),
                          eff("damage", set={"amount": 20})),
         tier("Три валуна", "До 3.", desc("Валун (до 3): 20 урона врагам рядом."),
              eff("place_object", set={"limit": 3}))),
  branch("Россыпь", tier("2 AP", "2 AP.", *ap1("Валун (до 2): 10 урона рядом. 2 AP.")),
         tier("Оглушение", "Задетые оглушены 0.8 сек.", desc("Валун: 10 урона и оглушение рядом."),
              add({"type": "stun", "duration": 0.8, "radius": 1}))))
S("lava_vent", skill("Жерло", "Радиус 1: клетки 8 сек становятся лавой (жжёт всех, кроме любящих жар).", 4, "cell",
                     [{"type": "terrain", "terrain": "lava", "radius": 1, "duration": 8}], rng=5, cd=8, radius=1,
                     au=auto(True, ("enemies_in_area", 2))),
  branch("Извержение", tier("Долгое", "12 сек.", desc("Радиус 1: лава 12 сек."),
                            eff("terrain", set={"duration": 12})),
         tier("Выброс", "И 16 урона + Огонь.", desc("Радиус 1: лава 12 сек, 16 урона + Огонь."),
              add(D(16, "spell", radius=1, tag="fire")))),
  branch("Точечное", tier("Одна клетка, 2 AP", "Радиус 0, 2 AP.", desc("Клетка 8 сек — лава. 2 AP.", radius=0),
                          eff("terrain", set={"radius": 0}), {"add": {"ap": -2}}),
         tier("Часто", "Перезарядка 3.", desc("Клетка 8 сек — лава.", cooldown=3))))
S("spring", skill("Родник", "Радиус 1: клетки 8 сек — вода; врагам Вода (для Грозы и Льда).", 3, "cell",
                  [{"type": "terrain", "terrain": "water", "radius": 1, "duration": 8},
                   {"type": "status", "tag": "water", "radius": 1}], rng=5, cd=6, radius=1,
                  au=auto(True, ("enemies_in_area", 2))),
  branch("Разлив", tier("Широкий разлив", "Радиус 2.", desc("Радиус 2: вода 8 сек, врагам Вода.", radius=2),
                        {"radius_add": 1}),
         tier("Половодье", "14 сек.", desc("Радиус 2: вода 14 сек, врагам Вода."),
              eff("terrain", set={"duration": 14}))),
  branch("Ключ", tier("2 AP", "2 AP.", *ap1("Радиус 1: вода 8 сек, врагам Вода. 2 AP.")),
         tier("Целебный ключ", "Союзникам рядом +15 HP.", desc("Радиус 1: вода, врагам Вода, союзникам +15 HP."),
              add({"type": "heal", "amount": 15, "radius": 1}))))
PATHS["lavalord"] = {"class": "geomancer", "name": "Повелитель лавы", "desc": "«Перековать» → «Жерло».",
                     "replace": {"reshape": "lava_vent"},
                     "passive": {"kind": "retaliate", "name": "Магма", "pp": 1, "damage": 8, "tag": "fire",
                                 "desc": "Ближняя атака: −1 деление шкалы, 8 урона + Огонь"},
                     "mods": [{"resist": "fire", "mult": 0.5}]}
PATHS["springkeeper"] = {"class": "geomancer", "name": "Хранитель источников", "desc": "«Обвал» → «Родник».",
                         "replace": {"rockfall": "spring"},
                         "passive": {"kind": "block", "name": "Каменная кожа", "pp": 1, "mult": 0.65,
                                     "desc": "Любой удар: −1 деление шкалы, урон ×0.65"},
                         "mods": [{"stat": "hp", "add": 15}]}
talents("geomancer", ("ge_stone", "Гранит", 1, "+1 к броне", [{"stat": "armor", "add": 1}]),
        ("ge_root", "Корни земли", 1, "+20 HP", [{"stat": "hp", "add": 20}]),
        ("ge_harmony", "Созвучие", 2, "+1 деление шкалы", [{"stat": "pp_max", "add": 1}]))
GAUGES["geomancer"] = {"name": "Созвучие", "color": [170, 200, 120], "trickle": 8.0, "gain": {"new_ground": 1},
                       "desc": "+1 за Силу земли на другой клетке, чем в прошлый раз"}

# ======================= Зельевар =======================
hero("brewer", "Зельевар", "Зв", [120, 170, 110], "support", 72, 0, 0.45, {"damage": 6, "range": 3, "cooldown": 1.2},
     7, 4.2, {"kind": "catalyst", "name": "Реакция", "pp": 1, "mult": 1.4,
              "desc": "Реакция от удара зельевара: −1 деление шкалы, сильнее в 1.4 раза"},
     ["coat", "flask", "reagent"],
     {"body": "robe", "color": [90, 120, 80], "accent": [200, 160, 255], "head": "hat", "weapon": "staff"},
     "Зельевар: вооружает других — смазывает оружие союзника тегом (Масло, Огонь, Яд), кидает склянки с тегами "
     "во врагов, «Реактив» бьёт тем сильнее, чем больше тегов на цели. Весь урон — через чужие атаки; сам беззащитен.")
S("coat", skill("Смазка", "Атаки союзника 10 сек поджигают (Огонь) и бьют ×1.2.", 2, "ally",
                [buff("atk_tag", "fire", 10), buff("atk_mult", 1.2, 10)], rng=4, cd=3, au=auto(True)),
  branch("Масляная смазка",
         tier("Масляная смазка", "Атаки накладывают Масло — для Пироманта.", desc(
             "Атаки союзника 10 сек накладывают Масло и бьют ×1.1."),
             {"effects": [buff("atk_tag", "oil", 10), buff("atk_mult", 1.1, 10)]}),
         tier("Горючая смесь", "×1.25.", desc("Атаки союзника 10 сек: Масло и урон ×1.25."),
              {"effects": [buff("atk_tag", "oil", 10), buff("atk_mult", 1.25, 10)]})),
  branch("Ядовитая смазка",
         tier("Ядовитая смазка", "Атаки отравляют.", desc("Атаки союзника 10 сек накладывают Яд и бьют ×1.1."),
              {"effects": [buff("atk_tag", "poison", 10), buff("atk_mult", 1.1, 10)]}),
         tier("Долгая смазка", "16 сек.", desc("Атаки союзника 16 сек накладывают Яд."),
              eff("buff", set={"duration": 16}))))
S("flask", skill("Склянка", "Радиус 1: 8 урона, враги мокнут (Вода) — для Грозы, Льда, Огня.", 2, "cell",
                 [D(8, "ranged", radius=1), {"type": "status", "tag": "water", "radius": 1}], rng=5, cd=2, radius=1,
                 au=auto(True, ("enemies_in_area", 2))),
  branch("Масляная склянка", tier("Масло", "Тег Масло.", desc("Радиус 1: враги в Масле."),
                                  eff("status", set={"tag": "oil"})),
         tier("Лужа", "И масляная лужа 8 сек.", desc("Радиус 1: враги в Масле, лужа масла 8 сек."),
              add({"type": "hazard", "hazard": "oil", "duration": 8, "radius": 1}))),
  branch("Ледяная склянка", tier("Лёд", "Тег Лёд.", desc("Радиус 1: враги во Льду (замедлены)."),
                                 eff("status", set={"tag": "ice"})),
         tier("1 AP", "1 AP.", *ap1("Радиус 1: враги во Льду. 1 AP."))))
S("reagent", skill("Реактив", "14 урона за каждый тег на враге, теги обновляются.", 3, "enemy",
                   [{"type": "reagent", "per_tag": 14}], rng=5, cd=4, au=auto(True, ("target_has_tag", "water"))),
  branch("Концентрат", tier("Концентрат", "20 за тег.", desc("20 урона за каждый тег на враге."),
                            eff("reagent", set={"per_tag": 20})),
         tier("Дальний бросок", "Дальность 7.", desc("20 урона за тег, дальность 7.", range=7))),
  branch("Быстрый реактив", tier("2 AP", "2 AP.", *ap1("10 урона за тег. 2 AP.")),
         tier("Без отката", "Перезарядка 1.", desc("10 урона за тег.", cooldown=1))))
S("toxic_flask", skill("Ядовитая склянка", "Радиус 1: Яд и ядовитое облако 6 сек (только по врагам).", 3, "cell",
                       [{"type": "status", "tag": "poison", "radius": 1},
                        {"type": "hazard", "hazard": "poison", "duration": 6, "radius": 1}], rng=5, cd=4, radius=1,
                       au=auto(True, ("enemies_in_area", 2))),
  branch("Мор", tier("Широкое облако", "Радиус 2.", desc("Радиус 2: Яд и облако 6 сек.", radius=2),
                     {"radius_add": 1}),
         tier("Долгое облако", "10 сек.", desc("Радиус 2: Яд и облако 10 сек."), eff("hazard", set={"duration": 10}))),
  branch("Быстро", tier("2 AP", "2 AP.", *ap1("Радиус 1: Яд и облако 6 сек. 2 AP.")),
         tier("Часто", "Перезарядка 2.", desc("Радиус 1: Яд и облако 6 сек.", cooldown=2))))
S("volatile_mix", skill("Гремучая смесь", "Каждый тег на враге взрывается: 14 урона врагам рядом, теги исчезают.", 3,
                        "enemy", [{"type": "reagent", "per_tag": 14, "explode": True, "radius": 1}], rng=5, cd=4,
                        au=auto(True, ("target_has_tag", "oil"))),
  branch("Детонация", tier("Мощнее", "20 за тег.", desc("Каждый тег взрывается: 20 урона рядом."),
                           eff("reagent", set={"per_tag": 20})),
         tier("Шире", "Радиус 2.", desc("Каждый тег взрывается: 20 урона в радиусе 2."),
              eff("reagent", set={"radius": 2}))),
  branch("Быстро", tier("2 AP", "2 AP.", *ap1("Каждый тег взрывается: 14 урона рядом. 2 AP.")),
         tier("Часто", "Перезарядка 2.", desc("Каждый тег взрывается.", cooldown=2))))
PATHS["toxicologist"] = {"class": "brewer", "name": "Ядовар", "desc": "«Склянка» → «Ядовитая склянка».",
                         "replace": {"flask": "toxic_flask"},
                         "passive": {"kind": "retaliate", "name": "Пары", "pp": 1, "damage": 6, "tag": "poison",
                                     "desc": "Ближняя атака: −1 деление шкалы, 6 урона + Яд"},
                         "mods": [{"stat": "hp", "add": 10}]}
PATHS["blaster"] = {"class": "brewer", "name": "Взрывотехник", "desc": "«Реактив» → «Гремучая смесь».",
                    "replace": {"reagent": "volatile_mix"},
                    "passive": {"kind": "catalyst", "name": "Цепная реакция", "pp": 1, "mult": 1.7,
                                "desc": "Реакция от удара: −1 деление шкалы, сильнее в 1.7 раза"},
                    "mods": [{"stat": "power", "mult": 1.05}]}
talents("brewer", ("br_bag", "Бездонная сумка", 1, "+1 AP", [{"stat": "ap_max", "add": 1}]),
        ("br_apron", "Фартук", 1, "+15 HP", [{"stat": "hp", "add": 15}]),
        ("br_mix", "Смеси", 2, "+1 деление шкалы", [{"stat": "pp_max", "add": 1}]))
GAUGES["brewer"] = {"name": "Реагенты", "color": [190, 230, 140], "trickle": 8.0, "gain": {"reaction": 1},
                    "desc": "+1 за реакцию тегов от удара отряда"}

# ======================= Берсерк крови =======================
hero("bloodrager", "Берсерк крови", "Бк", [180, 50, 50], "melee", 140, 2, 0.42,
     {"damage": 12, "range": 1, "cooldown": 1.0}, 4, 5.0,
     {"kind": "rage", "name": "Боль — топливо", "pp": 1, "stat": "atk_speed", "value": 0.7, "duration": 3,
      "desc": "Удар по берсерку: −1 деление шкалы, атаки на 30% быстрее 3 сек"},
     ["blood_strike", "bloodlet", "trance"],
     {"body": "humanoid", "color": [160, 60, 50], "accent": [230, 200, 190], "head": "horns", "weapon": "axe"},
     "Берсерк крови: навыки стоят HP, а не AP; чем меньше HP — тем сильнее удары (до +80%). В «Кровавом трансе» "
     "лечение превращается в ярость. Нужны щиты и отложенное лечение; легко умирает, если отряд не держит его на грани.",
     blood_rage=0.8)
S("blood_strike", skill("Кровавый удар", "Стоит 10 HP: 38 урона, лечит на 30% нанесённого.", 0, "enemy",
                        [D(38, "melee", lifesteal=0.3)], rng=1, cd=2.5, au=auto(True), hp_cost=10),
  branch("Рассечь", tier("Глубокая рана", "48 урона.", desc("Стоит 10 HP: 48 урона, лечит на 30%."),
                         eff("damage", set={"amount": 48})),
         tier("Кровотечение", "Ещё Яд цели.", desc("Стоит 10 HP: 48 урона, лечит на 30%, Яд."),
              add({"type": "status", "tag": "poison"}))),
  branch("Пить кровь", tier("Пить кровь", "Лечит на 60%.", desc("Стоит 10 HP: 38 урона, лечит на 60%."),
                            eff("damage", set={"lifesteal": 0.6})),
         tier("Дешевле", "Стоит 6 HP.", desc("Стоит 6 HP: 38 урона, лечит на 60%.", hp_cost=6))))
S("bloodlet", skill("Кровопускание", "Стоит 16 HP: 6 сек атаки на 40% быстрее и ×1.2.", 0, "self",
                    [buff("atk_speed", 0.6, 6), buff("atk_mult", 1.2, 6)], cd=8, au=auto(True, ("enemies_adjacent", 1)),
                    hp_cost=16),
  branch("Безумие", tier("Безумие", "×1.35.", desc("Стоит 16 HP: атаки быстрее и ×1.35 на 6 сек."),
                         {"effects": [buff("atk_speed", 0.6, 6), buff("atk_mult", 1.35, 6)]}),
         tier("Дольше", "9 сек.", desc("Стоит 16 HP: атаки быстрее и ×1.35 на 9 сек."), eff("buff", set={"duration": 9}))),
  branch("Холодная кровь", tier("Дешевле", "Стоит 10 HP.", desc("Стоит 10 HP: атаки быстрее и ×1.2.", hp_cost=10)),
         tier("Частое", "Перезарядка 5.", desc("Стоит 10 HP: атаки быстрее и ×1.2.", cooldown=5))))
S("trance", skill("Кровавый транс", "8 сек: любое лечение берсерка вместо HP даёт +1% урона за 1 HP (до ×2), "
                                     "урон по нему −15%.", 2, "self",
                  [buff("trance", 0.01, 8), buff("dmg_taken", 0.85, 8)], cd=14, au=auto(True, ("self_hp_below", 50))),
  branch("Пламя крови", tier("Жарче", "+1.5% за 1 HP.", desc("8 сек: лечение → +1.5% урона за 1 HP."),
                             {"effects": [buff("trance", 0.015, 8), buff("dmg_taken", 0.85, 8)]}),
         tier("Дольше", "12 сек.", desc("12 сек: лечение → ярость."), eff("buff", set={"duration": 12}))),
  branch("Стойкость", tier("Стойкость", "Урон по нему −30%.", desc("8 сек: лечение → ярость, урон по нему −30%."),
                           {"effects": [buff("trance", 0.01, 8), buff("dmg_taken", 0.7, 8)]}),
         tier("Чаще", "Перезарядка 9.", desc("8 сек: лечение → ярость.", cooldown=9))))
S("cleave", skill("Размах", "Стоит 12 HP: 26 урона всем врагам рядом.", 0, "self", [D(26, "melee", radius=1)], cd=3,
                  radius=1, au=auto(True, ("enemies_adjacent", 2)), hp_cost=12),
  branch("Мясорубка", tier("Мясорубка", "34 урона.", desc("Стоит 12 HP: 34 урона всем рядом."),
                           eff("damage", set={"amount": 34})),
         tier("Вампиризм", "Лечит на 25%.", desc("Стоит 12 HP: 34 урона рядом, лечит на 25%."),
              eff("damage", set={"lifesteal": 0.25}))),
  branch("Раскрутка", tier("Без отката", "Перезарядка 1.", desc("Стоит 12 HP: 26 урона всем рядом.", cooldown=1)),
         tier("Дешевле", "Стоит 8 HP.", desc("Стоит 8 HP: 26 урона всем рядом.", hp_cost=8))))
S("undying_rage", skill("Неистовая ярость", "4 сек берсерк не умирает (HP не ниже 1), атаки ×1.3.", 2, "self",
                        [buff("undying", 1, 4), buff("atk_mult", 1.3, 4)], cd=20,
                        au=auto(True, ("self_hp_below", 20))),
  branch("Бессмертие", tier("Дольше", "6 сек.", desc("6 сек берсерк не умирает, атаки ×1.3."),
                            eff("buff", set={"duration": 6})),
         tier("Ярость", "Атаки ×1.6.", desc("6 сек не умирает, атаки ×1.6."),
              {"effects": [buff("undying", 1, 6), buff("atk_mult", 1.6, 6)]})),
  branch("Чаще", tier("Чаще", "Перезарядка 14.", desc("4 сек не умирает, атаки ×1.3.", cooldown=14)),
         tier("Без AP", "0 AP.", desc("4 сек не умирает, атаки ×1.3. 0 AP."), {"add": {"ap": -2}})))
PATHS["butcher"] = {"class": "bloodrager", "name": "Мясник", "desc": "«Кровопускание» → «Размах».",
                    "replace": {"bloodlet": "cleave"},
                    "passive": {"kind": "rage", "name": "Запах крови", "pp": 1, "stat": "atk_mult", "value": 1.3,
                                "duration": 3, "desc": "Удар по берсерку: −1 деление шкалы, атаки ×1.3 на 3 сек"},
                    "mods": [{"stat": "hp", "add": 15}]}
PATHS["frenzied"] = {"class": "bloodrager", "name": "Неистовый", "desc": "«Кровавый транс» → «Неистовая ярость».",
                     "replace": {"trance": "undying_rage"},
                     "passive": {"kind": "rage", "name": "Боль — топливо", "pp": 1, "stat": "atk_speed", "value": 0.7,
                                 "duration": 3, "desc": "Удар: −1 деление шкалы, атаки быстрее 3 сек"},
                     "mods": [{"stat": "atk_damage", "add": 2}]}
talents("bloodrager", ("bl_hide", "Толстая шкура", 1, "+25 HP", [{"stat": "hp", "add": 25}]),
        ("bl_edge", "Зазубренный топор", 1, "+3 к урону атаки", [{"stat": "atk_damage", "add": 3}]),
        ("bl_rage", "Ярость", 2, "+1 деление шкалы", [{"stat": "pp_max", "add": 1}]))
GAUGES["bloodrager"] = {"name": "Ярость", "color": [230, 80, 70], "trickle": 8.0, "gain": {"hit_taken": 1, "blood": 1},
                        "desc": "+1 за пропущенный удар и за навык ценой HP"}

# ======================= Тактик =======================
hero("tactician", "Тактик", "Тк", [200, 160, 70], "support", 95, 2, 0.45,
     {"damage": 9, "range": 2, "cooldown": 1.3, "kind": "melee"}, 7, 4.5,
     {"kind": "block", "name": "Знамя-щит", "pp": 1, "mult": 0.7, "desc": "Любой удар: −1 деление шкалы, урон ×0.7"},
     ["forward", "regroup", "focus"],
     {"body": "humanoid", "color": [180, 140, 60], "accent": [220, 60, 60], "head": "helm", "weapon": "spear"},
     "Тактик-знаменосец: приказы — «Вперёд!» (союзник сразу бьёт ещё раз), «Перестроение» (союзник мгновенно "
     "встаёт на клетку), «Фокус» (весь отряд бьёт одну цель, она уязвима). Знамя: союзники рядом +1 брони. Сильные "
     "союзники — сильные приказы; сам почти не бьёт.",
     aura={"every": 1.0, "radius": 2,
           "effects": [{"type": "buff", "stat": "armor", "value": 1, "duration": 1.5, "radius": 2,
                        "affects": "allies"}]})
S("forward", skill("Вперёд!", "Союзник сразу атакует ещё раз (если некого бить — +1 AP).", 2, "ally",
                   [{"type": "extra_attack", "count": 1, "ap": 1}], rng=5, cd=3, au=auto(True)),
  branch("Натиск", tier("Двойной удар", "Две атаки.", desc("Союзник сразу атакует дважды."),
                        eff("extra_attack", set={"count": 2})),
         tier("Ярость приказа", "И +20% урона на 4 сек.", desc("Союзник атакует дважды, +20% урона 4 сек."),
              add(buff("atk_mult", 1.2, 4)))),
  branch("Чёткий приказ", tier("1 AP", "1 AP.", *ap1("Союзник сразу атакует ещё раз. 1 AP.")),
         tier("Без отката", "Перезарядка 1.", desc("Союзник сразу атакует ещё раз.", cooldown=1))))
S("regroup", skill("Перестроение", "Ближайший к клетке союзник (до 2 клеток) мгновенно встаёт на неё.", 2, "cell",
                   [{"type": "regroup", "reach": 2}], rng=6, cd=4, free_cell=True, au=auto(False)),
  branch("Манёвр", tier("Широкий манёвр", "Союзник до 3 клеток.", desc("Союзник до 3 клеток встаёт на клетку."),
                        eff("regroup", set={"reach": 3})),
         tier("Под прикрытием", "Ему щит 20.", desc("Союзник до 3 клеток встаёт на клетку, щит 20."),
              add({"type": "shield", "amount": 20, "duration": 4, "radius": 0}))),
  branch("Быстро", tier("1 AP", "1 AP.", *ap1("Союзник встаёт на клетку. 1 AP.")),
         tier("Часто", "Перезарядка 2.", desc("Союзник встаёт на клетку.", cooldown=2))))
S("focus", skill("Фокус", "Весь отряд атакует цель, она получает +20% урона 5 сек.", 3, "enemy",
                 [{"type": "focus", "mult": 1.2, "duration": 5}], rng=7, cd=8, au=auto(True, ("target_hp_below", 50))),
  branch("Охота", tier("Беспощадно", "+30%.", desc("Весь отряд атакует цель, +30% урона 5 сек."),
                       eff("focus", set={"mult": 1.3})),
         tier("Долго", "8 сек.", desc("Весь отряд атакует цель, +30% урона 8 сек."), eff("focus", set={"duration": 8}))),
  branch("Слаженность", tier("2 AP", "2 AP.", *ap1("Отряд атакует цель, +20% урона. 2 AP.")),
         tier("Часто", "Перезарядка 5.", desc("Отряд атакует цель, +20% урона.", cooldown=5))))
S("all_out", skill("Общий натиск", "Союзники в радиусе 3: атаки на 25% быстрее и шаги быстрее 5 сек.", 3, "self",
                   [buff("atk_speed", 0.75, 5, radius=3, affects="allies"), buff("slow", 0.8, 5, radius=3,
                                                                                    affects="allies")],
                   cd=10, radius=3, au=auto(True)),
  branch("Атака", tier("Дольше", "8 сек.", desc("Союзники в радиусе 3: быстрее 8 сек."), eff("buff", set={"duration": 8})),
         tier("Шире", "Радиус 4.", desc("Союзники в радиусе 4: быстрее 8 сек.", radius=4), {"radius_add": 1})),
  branch("Порядок", tier("2 AP", "2 AP.", *ap1("Союзники в радиусе 3: быстрее 5 сек. 2 AP.")),
         tier("Часто", "Перезарядка 6.", desc("Союзники в радиусе 3: быстрее 5 сек.", cooldown=6))))
S("ambush_order", skill("Засада", "Враг раскрыт 5 сек (удар в спину от всех, +25% урона), отряд атакует его.", 3,
                        "enemy", [buff("exposed", 1.25, 5, affects="enemies"),
                                  {"type": "focus", "mult": 1.0, "duration": 0.1}], rng=7, cd=8, au=auto(True)),
  branch("Западня", tier("Долго", "8 сек.", desc("Враг раскрыт 8 сек, отряд атакует его."),
                         eff("buff", set={"duration": 8})),
         tier("Беспощадно", "+35%.", desc("Враг раскрыт 8 сек (+35%), отряд атакует."), eff("buff", set={"value": 1.35}))),
  branch("Быстро", tier("2 AP", "2 AP.", *ap1("Враг раскрыт 5 сек. 2 AP.")),
         tier("Часто", "Перезарядка 5.", desc("Враг раскрыт 5 сек.", cooldown=5))))
PATHS["warlord"] = {"class": "tactician", "name": "Полководец", "desc": "«Перестроение» → «Общий натиск».",
                    "replace": {"regroup": "all_out"},
                    "passive": {"kind": "block", "name": "Знамя-щит", "pp": 1, "mult": 0.6,
                                "desc": "Любой удар: −1 деление шкалы, урон ×0.6"}, "mods": [{"stat": "hp", "add": 15}]}
PATHS["strategist"] = {"class": "tactician", "name": "Стратег", "desc": "«Фокус» → «Засада».",
                       "replace": {"focus": "ambush_order"},
                       "passive": {"kind": "dodge", "vs": ["ranged"], "name": "Предусмотрительность", "pp": 1,
                                   "desc": "Дальняя атака: −1 деление шкалы, промах"},
                       "mods": [{"stat": "ap_max", "add": 1}]}
talents("tactician", ("tc_banner", "Тяжёлое знамя", 1, "+1 к броне", [{"stat": "armor", "add": 1}]),
        ("tc_voice", "Командный голос", 1, "+1 AP", [{"stat": "ap_max", "add": 1}]),
        ("tc_command", "Командование", 2, "+1 деление шкалы", [{"stat": "pp_max", "add": 1}]))
GAUGES["tactician"] = {"name": "Командование", "color": [240, 200, 100], "trickle": 6.0, "gain": {"order": 1, "kill": 1},
                       "desc": "+1 за отданный приказ и за добивание"}

# ======================= Связующий =======================
hero("binder", "Связующий", "Св", [210, 140, 170], "support", 80, 0, 0.45, {"damage": 6, "range": 3, "cooldown": 1.3},
     6, 4.5, {"kind": "intercede", "name": "Опека", "pp": 1, "range": 1, "heal": 8,
              "desc": "Соседа-союзника бьют: −1 деление шкалы, лечит его на 8"},
     ["tether", "merge", "life_transfer"],
     {"body": "spirit", "color": [210, 140, 170], "accent": [255, 230, 240]},
     "Связующий: привязывается к союзнику — половина урона по нему уходит в связующего, союзник восстанавливается. "
     "«Слияние»: входит в союзника (не цель для врагов), тот сильнее. «Отдать силы»: своё HP — союзнику. Без "
     "партнёра почти ничего не умеет; гибель партнёра бьёт по нему.")
S("tether", skill("Привязь", "15 сек: половина урона по союзнику — в связующего, союзнику +3 HP/сек.", 2, "ally",
                  [{"type": "tether", "duration": 15, "regen": 3}], rng=5, cd=2, au=auto(True)),
  branch("Крепкая нить", tier("Крепкая нить", "+6 HP/сек.", desc("15 сек: половина урона — в связующего, +6 HP/сек."),
                              eff("tether", set={"regen": 6})),
         tier("Долгая нить", "25 сек.", desc("25 сек: половина урона — в связующего, +6 HP/сек."),
              eff("tether", set={"duration": 25}))),
  branch("Дальняя нить", tier("Дальность 7", "Дальность 7.", desc("Привязь на дальность 7.", range=7)),
         tier("1 AP", "1 AP.", *ap1("Привязь: половина урона — в связующего. 1 AP."))))
S("merge", skill("Слияние", "Входит в союзника на привязи на 6 сек: не цель для врагов; союзнику +3 брони и урон ×1.25.",
                 3, "self", [{"type": "merge", "duration": 6,
                              "host": [buff("armor", 3, 6), buff("atk_mult", 1.25, 6)]}], cd=14,
                 au=auto(True, ("self_hp_below", 40))),
  branch("Единство", tier("Единство", "Урон ×1.4.", desc("6 сек внутри союзника: +3 брони, урон ×1.4."),
                          eff("merge", set={"host": [buff("armor", 3, 6), buff("atk_mult", 1.4, 6)]})),
         tier("Дольше", "9 сек.", desc("9 сек внутри союзника: +3 брони, урон ×1.4."),
              eff("merge", set={"duration": 9}))),
  branch("Убежище", tier("Целитель внутри", "Союзнику +6 HP/сек.", desc("6 сек внутри: +3 брони, урон ×1.25, +6 HP/сек."),
                         eff("merge", set={"host": [buff("armor", 3, 6), buff("atk_mult", 1.25, 6),
                                                    buff("regen", 6, 6)]})),
         tier("Часто", "Перезарядка 9.", desc("6 сек внутри союзника.", cooldown=9))))
S("life_transfer", skill("Отдать силы", "Связующий теряет 20 HP, союзник получает 32.", 1, "ally",
                         [{"type": "life_transfer", "cost": 20, "amount": 32}], rng=5, cd=2,
                         au=auto(True, ("ally_hp_below", 40))),
  branch("Щедрость", tier("Щедрость", "Союзнику 44.", desc("−20 HP себе, +44 союзнику."),
                          eff("life_transfer", set={"amount": 44})),
         tier("Даром", "Себе −12.", desc("−12 HP себе, +44 союзнику."), eff("life_transfer", set={"cost": 12}))),
  branch("Поток", tier("Без отката", "Перезарядка 0.", desc("−20 HP себе, +32 союзнику.", cooldown=0)),
         tier("Дальше", "Дальность 7.", desc("−20 HP себе, +32 союзнику, дальность 7.", range=7))))
S("soul_shield", skill("Щит души", "Союзнику щит 50 на 6 сек.", 3, "ally", [{"type": "shield", "amount": 50,
                                                                              "duration": 6}], rng=5, cd=6,
                       au=auto(True, ("ally_hp_below", 50))),
  branch("Броня души", tier("Толще", "Щит 70.", desc("Союзнику щит 70."), eff("shield", set={"amount": 70})),
         tier("Дольше", "10 сек.", desc("Союзнику щит 70 на 10 сек."), eff("shield", set={"duration": 10}))),
  branch("Быстро", tier("2 AP", "2 AP.", *ap1("Союзнику щит 50. 2 AP.")),
         tier("Часто", "Перезарядка 3.", desc("Союзнику щит 50.", cooldown=3))))
S("share_pain", skill("Разделить боль", "Враг: 16 урона и −30% к его урону на 6 сек.", 2, "enemy",
                      [D(16, "spell"), buff("atk_mult", 0.7, 6, affects="enemies")], rng=5, cd=4, au=auto(True)),
  branch("Тяжесть", tier("Тяжесть", "−45%.", desc("16 урона, −45% к урону врага 6 сек."),
                         eff("buff", set={"value": 0.55})),
         tier("Дольше", "9 сек.", desc("16 урона, −45% к урону 9 сек."), eff("buff", set={"duration": 9}))),
  branch("Боль", tier("Сильнее", "26 урона.", desc("26 урона, −30% к урону врага."), eff("damage", set={"amount": 26})),
         tier("1 AP", "1 AP.", *ap1("26 урона, −30% к урону. 1 AP."))))
PATHS["soulguard"] = {"class": "binder", "name": "Страж души", "desc": "«Слияние» → «Щит души».",
                      "replace": {"merge": "soul_shield"},
                      "passive": {"kind": "intercede", "name": "Опека", "pp": 1, "range": 2, "heal": 10,
                                  "desc": "Союзника рядом (2) бьют: −1 деление шкалы, лечит на 10"},
                      "mods": [{"stat": "hp", "add": 15}]}
PATHS["empath"] = {"class": "binder", "name": "Сопереживающий", "desc": "«Отдать силы» → «Разделить боль».",
                   "replace": {"life_transfer": "share_pain"},
                   "passive": {"kind": "retaliate", "name": "Отражение боли", "pp": 1, "damage": 10,
                               "desc": "Ближняя атака: −1 деление шкалы, 10 урона атакующему"},
                   "mods": [{"stat": "armor", "add": 1}]}
talents("binder", ("bd_soul", "Широкая душа", 1, "+20 HP", [{"stat": "hp", "add": 20}]),
        ("bd_thread", "Шёлковая нить", 1, "+1 AP", [{"stat": "ap_max", "add": 1}]),
        ("bd_bond", "Узы", 2, "+1 деление шкалы", [{"stat": "pp_max", "add": 1}]))
GAUGES["binder"] = {"name": "Связь", "color": [255, 170, 200], "trickle": 5.0, "gain": {"heal_given": 1},
                    "desc": "сама копится раз в 5 сек, +1 за лечение союзника"}


def main():
    upsert("skills.json", SKILLS, "fields")
    upsert("branches.json", BRANCHES, "branches")
    upsert("classes.json", CLASSES, "fields")
    upsert("paths.json", PATHS, "fields")
    upsert("talents.json", TALENTS, "line")
    gauges = load("gauges.json")
    gauges.update(GAUGES)
    j = lambda v: json.dumps(v, ensure_ascii=False)  # noqa: E731
    write(os.path.join(DATA, "gauges.json"), "{\n" + ",\n".join(f"  {j(k)}: {j(v)}" for k, v in gauges.items()) + "\n}\n")
    print(f"навыков {len(SKILLS)}, классов {len(CLASSES)}, путей {len(PATHS)}, талантов {len(TALENTS)}")


if __name__ == "__main__":
    main()
