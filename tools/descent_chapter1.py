"""Глава 1 «Спуска» — Болото (квиз 2026-11-19, docs/descent_chapter1.md): враги, элиты, боссы с фазами, три этажа,
реликвии, карта «Тина». Пишет в data/deck/enemies.json, relics.json, cards.json.

Намерения врагов (deck/battle.py): melee, shot, zone (+hazard), block, aim, heal, roar, summon и новые —
charge (рывок по линии), pull (утягивание), guard (щит своим), rally (сила своим), veil (туман), curse («Тина»
в колоду), hex (сглаз: меньше карт на ход), drown (утащить карту из колоды до конца боя).
Свойства: cap (рой — урон от удара не больше), drain у удара (кража жизни), on_death: split, fire_cell, explode.
Фазы босса: phases [{at — доля HP, name, enter — что делает сразу, cycle — новые намерения}].

Запуск: python tools/descent_chapter1.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "deck")


def M(name, dmg, **kw):
    return dict(kind="melee", name=name, dmg=dmg, **kw)


def S(name, dmg, rng=5, **kw):
    return dict(kind="shot", name=name, dmg=dmg, range=rng, **kw)


def Z(name, dmg, r=1, shape="target", **kw):
    return dict(kind="zone", name=name, dmg=dmg, r=r, shape=shape, **kw)


def K(kind, name, **kw):
    return dict(kind=kind, name=name, **kw)


ENEMIES = {
    # ---------- этаж 1: Камышовые топи ----------
    "slime": dict(name="Болотный слизень", sprite="slime", hp=24, speed=2,
                  cycle=[M("Шлепок", 7), M("Обволочь", 5, add=[{"op": "block", "n": 5}])],
                  on_death={"split": "slime_small", "n": 2}, about="При смерти распадается на два малых слизня."),
    "slime_small": dict(name="Малый слизень", sprite="slime", hp=8, speed=2, small=True, cycle=[M("Шлепок", 4)]),
    "toxic_slime": dict(name="Ядовитый слизень", sprite="toxic_slime", hp=22, speed=2,
                        cycle=[M("Едкий шлепок", 5, add=[{"op": "poison", "n": 2}]), M("Обволочь", 4, add=[{"op": "block", "n": 4}])],
                        on_death={"explode": {"dmg": 0, "r": 1, "hazard": "poison"}},
                        about="Отравляет ударом. При смерти оставляет ядовитую лужу."),
    "bog_archer": dict(name="Болотный стрелок", sprite="bog_archer", hp=18, speed=3, keep_range=4,
                       cycle=[K("aim", "Прицел", mult=2, vfx="hunter_mark"), S("Выстрел", 6), S("Выстрел", 6)],
                       about="Стоит и стреляет на 5 клеток по линии обзора. Начинает с прицела."),
    "beetle": dict(name="Огненный жук", sprite="beetle", hp=14, speed=3,
                   cycle=[M("Укус", 5, add=[{"op": "burn", "n": 2}])], on_death={"fire_cell": True},
                   about="Быстрый, поджигает. При смерти оставляет горящую клетку."),
    "mosquito_swarm": dict(name="Комариный рой", sprite="mosquito_swarm", hp=12, speed=4, cap=3,
                           cycle=[M("Жалит", 3, add=[{"op": "poison", "n": 1}]), M("Жалит", 3)],
                           about="Рой: от одного удара теряет не больше 3 HP — бейте часто или по площади."),
    "poacher": dict(name="Браконьер", sprite="poacher", hp=16, speed=3, keep_range=3,
                    cycle=[S("Выстрел из камышей", 5, 5), K("veil", "Залечь в камыши"), S("Выстрел", 7, 5)],
                    about="Стреляет и прячется в камышах: в тумане его не достать картами издали — только вплотную."),
    "will_wisp": dict(name="Блуждающий огонёк", sprite="will_wisp", hp=9, speed=4, keep_range=3,
                      cycle=[S("Обжигающий свет", 4, 4, add=[{"op": "burn", "n": 1}]), K("veil", "Мерцание")],
                      on_death={"explode": {"dmg": 6, "r": 1}},
                      about="Мерцает (туман). При смерти вспыхивает — 6 урона всем рядом."),
    # ---------- этаж 2: Жабьи дворы ----------
    "frog_shaman": dict(name="Жаба-шаман", sprite="frog_shaman", hp=20, speed=2, keep_range=3, smart="shaman",
                        moves={"heal": K("heal", "Болотное исцеление", n=8, vfx="frog_heal"),
                               "splash": Z("Брызги трясины", 4, 1, add=[{"op": "wet"}], range=6, vfx="mud_splash")},
                        about="Лечит раненых союзников, иначе брызгает трясиной по зоне вокруг героя."),
    "toad_spearman": dict(name="Жаба-копейщик", sprite="toad_spearman", hp=24, speed=2,
                          cycle=[K("guard", "Сомкнуть щиты", n=6, r=2, vfx="shield_wall"),
                                 M("Удар копьём", 8, add=[{"op": "push", "n": 1}])],
                          about="Прикрывает щитом соседей (защита всем рядом), колет копьём с толчком."),
    "bog_hag": dict(name="Болотная ведьма", sprite="bog_hag", hp=16, speed=2, keep_range=4,
                    cycle=[K("veil", "Морок"), K("curse", "Тина в колоду", n=2), K("hex", "Сглаз", n=1)],
                    about="Прячется в мороке, подкладывает «Тину» в колоду и сглазом отнимает карту на следующий ход."),
    "toad_guard": dict(name="Жаба-стражник", sprite="toad_spearman", hp=14, speed=2,
                       cycle=[K("guard", "Прикрыть", n=4, r=2, vfx="shield_wall"), M("Укол", 6)],
                       about="Свита короля и королевы: прикрывает щитом и колет."),
    "elder_leech": dict(name="Старая пиявка", sprite="elder_leech", hp=16, speed=3,
                        cycle=[M("Присосаться", 6, drain=True), M("Присосаться", 6, drain=True),
                               M("Раздуться", 4, add=[{"op": "block", "n": 5}])],
                        about="Пьёт кровь: лечится на нанесённый урон."),
    "leechling": dict(name="Пиявчонок", sprite="elder_leech", hp=7, speed=3, small=True,
                      cycle=[M("Присосаться", 3, drain=True)]),
    "bog_croc": dict(name="Болотный крокодил", sprite="bog_croc", hp=34, speed=2,
                     cycle=[K("charge", "Бросок из воды", dmg=10, range=4, push=1), M("Челюсти", 9),
                            M("Панцирь", 6, add=[{"op": "block", "n": 8}])],
                     about="Бросок по линии — клетки отмечены заранее, уйди с линии. Потом рвёт челюстями."),
    "spore_shroom": dict(name="Гриб-споровик", sprite="spore_shroom", hp=14, speed=1, keep_range=3,
                         cycle=[Z("Облако спор", 2, 1, add=[{"op": "poison", "n": 2}], range=5, vfx="mud_splash"),
                                K("block", "Шляпка", n=4)],
                         on_death={"explode": {"dmg": 0, "r": 1, "poison": 3, "hazard": "poison"}},
                         about="Облако спор травит по зоне. При смерти лопается: яд всем рядом и ядовитые лужи."),
    # ---------- этаж 3: Сердце трясины ----------
    "drowned": dict(name="Утопленник", sprite="drowned", hp=26, speed=2,
                    cycle=[K("pull", "Утянуть", dmg=4, range=4, n=3), M("Мёртвая хватка", 9),
                           M("Мёртвая хватка", 9, add=[{"op": "weak", "n": 1}])],
                    about="Утягивает героя к себе с 4 клеток (по линии обзора) и бьёт вплотную."),
    "fog_double": dict(name="Туманный двойник", sprite="fog_double", hp=18, speed=3,
                       cycle=[K("veil", "Раствориться"), M("Удар из тумана", 9), M("Удар из тумана", 9)],
                       on_death={"hex": 1}, about="Растворяется в тумане. Умирая, оставляет сглаз: −1 карта на ход."),
    "rust_merc": dict(name="Наёмник Ржавых", sprite="rust_merc", hp=20, speed=3,
                      cycle=[M("Рубка", 7), M("Удар щитом", 5, add=[{"op": "block", "n": 5}]), M("Рубка", 8)],
                      about="Наёмник соперников: рубит и прикрывается щитом."),
    # ---------- элиты ----------
    "bog_horror": dict(name="Болотный ужас", sprite="bog_horror", hp=60, speed=2, elite=True,
                       cycle=[M("Удар", 10), Z("Размах", 14, 1, "self", vfx="whirlwind"),
                              K("roar", "Рёв", weak=2, r=3, vfx="e_war_cry")],
                       about="Элита. Размах бьёт все соседние клетки — отойди. Рёв — слабость."),
    "rust_captain": dict(name="Капитан Ржавых", sprite="rust_captain", hp=52, speed=3, elite=True,
                         cycle=[K("rally", "За мной!", n=1, r=4, vfx="e_war_cry"), M("Клинок капитана", 10),
                                K("guard", "Строй", n=7, r=3, vfx="shield_wall"), M("Клинок капитана", 11)],
                         about="Элита. Командует отрядом: сила и щиты всем своим. Начни с наёмников или с него?"),
    "old_tooth": dict(name="Старый Зуб", sprite="old_tooth", hp=72, speed=2, elite=True, cap=12,
                      cycle=[K("charge", "Бросок из глубины", dmg=14, range=6, push=2),
                             K("pull", "Утащить на дно", dmg=6, range=3, n=2), M("Челюсти", 12),
                             K("block", "Каменная чешуя", n=12)],
                      about="Элита. Бросок по длинной линии, утягивает к себе. Чешуя: от удара — не больше 12."),
    "leech_mother": dict(name="Матка пиявок", sprite="leech_mother", hp=56, speed=1, elite=True,
                         cycle=[K("summon", "Выводок", unit="leechling", n=1), M("Жадный укус", 9, drain=True),
                                Z("Кровавая лужа", 6, 1, add=[{"op": "poison", "n": 2}], hazard="poison", range=5),
                                M("Жадный укус", 9, drain=True)],
                         about="Элита. Плодит пиявчат, пьёт кровь, разливает ядовитые лужи."),
    "bell_ringer": dict(name="Звонарь-утопленник", sprite="bell_ringer", hp=78, speed=2, elite=True,
                        cycle=[K("hex", "Погребальный звон", n=1, weak=1, r=6, vfx="e_war_cry"),
                               K("pull", "Колокольная цепь", dmg=6, range=5, n=3), M("Удар колоколом", 13),
                               K("drown", "Утащить на дно", n=2)],
                        about="Элита. Звон — сглаз и слабость, цепь утягивает, «на дно» уносит карты из колоды."),
    # ---------- стражи ----------
    "slime_king": dict(name="Король слизней", sprite="slime_king", hp=76, speed=2, elite=True, boss=True,
                       cycle=[M("Удар туши", 12), Z("Волна слизи", 9, 1, add=[{"op": "wet"}], vfx="mud_splash"),
                              K("summon", "Отпочкование", unit="slime_small", n=2), K("block", "Студень", n=12)],
                       phases=[{"at": 0.5, "name": "Распад",
                                "enter": [K("summon", "Распад", unit="slime_small", n=2)],
                                "cycle": [Z("Тяжёлая волна", 12, 2, add=[{"op": "wet"}], vfx="mud_splash"),
                                          M("Удар туши", 13), K("curse", "Слизь в колоду", n=2),
                                          K("block", "Студень", n=10)]}],
                       about="Страж топей. На половине HP распадается: два слизня и новые удары."),
    "toad_queen": dict(name="Королева жаб", sprite="toad_queen", hp=64, speed=2, elite=True, boss=True,
                       keep_range=2,
                       cycle=[Z("Королевская волна", 9, 1, add=[{"op": "wet"}], range=7, vfx="mud_splash"),
                              K("curse", "Тина", n=2), K("heal", "Целебная слизь", n=8, vfx="frog_heal"),
                              K("hex", "Королевский сглаз", n=1)],
                       phases=[{"at": 0.5, "name": "Королевский гнев",
                                "enter": [K("rally", "Гнев", n=1, r=9), K("summon", "Стража!", unit="toad_guard", n=2)],
                                "cycle": [Z("Потоп", 10, 2, add=[{"op": "wet"}], hazard="water", range=7,
                                            vfx="mud_splash"),
                                          K("curse", "Тина", n=2), M("Королевский удар", 11)]}],
                       about="Страж дворов. Лечит и зовёт копейщиков. В гневе — сила и щиты свите, потоп."),
    "kvaks": dict(name="Квакс, король Сердца", sprite="kvaks", hp=84, speed=2, elite=True, boss=True, final=True,
                  cycle=[M("Скипетр", 11), Z("Янтарная волна", 9, 1, add=[{"op": "wet"}], range=7, vfx="mud_splash"),
                         K("curse", "Тина", n=2), K("summon", "Ко мне!", unit="toad_guard", n=1)],
                  phases=[{"at": 0.6, "name": "Трон треснул",
                           "enter": [K("rally", "Ярость двора", n=2, r=9)],
                           "cycle": [K("charge", "Бросок с трона", dmg=12, range=6, push=2),
                                     Z("Ядовитое сердце", 10, 2, hazard="poison", add=[{"op": "poison", "n": 2}],
                                       range=7, vfx="mud_splash"),
                                     K("drown", "Трясина забирает", n=2), M("Скипетр", 14)]},
                          {"at": 0.3, "name": "Последний король",
                           "enter": [K("rally", "Последняя ярость", n=2, r=0), K("summon", "Свита", unit="drowned", n=1)],
                           "cycle": [M("Скипетр", 13), K("pull", "Зов трясины", dmg=5, range=6, n=3),
                                     Z("Обвал трона", 14, 1, shape="self", vfx="whirlwind"),
                                     K("hex", "Проклятие короля", n=1, weak=2, r=9)]}],
                  about="Босс главы. Три фазы: двор, треснувший трон (рывки, ядовитое сердце), последняя ярость."),
}

FLOORS = [
    {"name": "Камышовые топи", "pools": {
        "battle": [
            {"name": "Камыши", "maps": ["reeds", "st_reedbed"], "enemies": ["slime", "bog_archer", "mosquito_swarm"]},
            {"name": "Комариная топь", "maps": ["ex_mosquito_bog"], "enemies": ["mosquito_swarm", "mosquito_swarm", "slime"]},
            {"name": "Огненное гнездо", "maps": ["nest", "st_ford"], "enemies": ["beetle", "beetle", "bog_archer", "slime_small"]},
            {"name": "Ядовитая топь", "maps": ["ex_toxic_marsh", "bog"], "enemies": ["toxic_slime", "beetle", "beetle"]},
            {"name": "Браконьеры", "maps": ["ex_village_mob", "st_reedbed"], "enemies": ["poacher", "poacher", "slime_small", "mosquito_swarm"]},
            {"name": "Огни над топью", "maps": ["ex_wisp_marsh", "st_causeway"], "enemies": ["will_wisp", "will_wisp", "toxic_slime", "slime_small"]},
        ],
        "elite": [
            {"name": "Логово ужаса", "maps": ["ex_horror_den"], "enemies": ["bog_horror", "beetle", "beetle"]},
            {"name": "Отряд Ржавых", "maps": ["ex_rivals", "ex_hunters"], "enemies": ["rust_captain", "rust_merc", "rust_merc"]},
        ],
        "boss": [{"name": "Трон короля слизней", "maps": ["ex_slime_throne", "slime_court"], "enemies": ["slime_king", "slime_small"]}],
    }},
    {"name": "Жабьи дворы", "pools": {
        "battle": [
            {"name": "Жабья фаланга", "maps": ["ex_toad_phalanx", "ex_toad_patrol"], "enemies": ["toad_spearman", "toad_spearman", "frog_shaman", "toad_guard"]},
            {"name": "Грибная роща", "maps": ["ex_spore_grove"], "enemies": ["spore_shroom", "spore_shroom", "bog_hag", "elder_leech"]},
            {"name": "Пиявочные заводи", "maps": ["ex_leech_pools"], "enemies": ["elder_leech", "elder_leech", "frog_shaman", "leechling"]},
            {"name": "Крокодилий брод", "maps": ["ex_croc_ford"], "enemies": ["bog_croc", "mosquito_swarm", "mosquito_swarm"]},
            {"name": "Лагерь жаб", "maps": ["camp", "st_frogs"], "enemies": ["toad_spearman", "frog_shaman", "toxic_slime", "toad_guard"]},
            {"name": "Ведьмин круг", "maps": ["st_chapel", "ex_spore_grove"], "enemies": ["bog_hag", "elder_leech", "slime", "leechling"]},
        ],
        "elite": [
            {"name": "Логово Старого Зуба", "maps": ["ex_old_tooth"], "enemies": ["old_tooth", "mosquito_swarm", "mosquito_swarm"]},
            {"name": "Гнездо матки", "maps": ["ex_leech_mother"], "enemies": ["leech_mother", "elder_leech", "leechling"]},
        ],
        "boss": [{"name": "Двор Королевы жаб", "maps": ["ex_toad_court"], "enemies": ["toad_queen", "toad_guard"]}],
    }},
    {"name": "Сердце трясины", "pools": {
        "battle": [
            {"name": "Чёрная переправа", "maps": ["ex_ferry", "ex_drowned_path"], "enemies": ["drowned", "drowned", "will_wisp", "elder_leech"]},
            {"name": "Двойники", "maps": ["ex_fog_doubles"], "enemies": ["fog_double", "fog_double", "bog_hag", "drowned"]},
            {"name": "Край трясины", "maps": ["ex_mire_edge"], "enemies": ["bog_croc", "spore_shroom", "toxic_slime", "mosquito_swarm"]},
            {"name": "Серебряные клинки", "maps": ["ex_hunters"], "enemies": ["rust_merc", "poacher", "fog_double", "rust_merc"]},
            {"name": "Тропа утопленников", "maps": ["ex_drowned_path"], "enemies": ["drowned", "elder_leech", "spore_shroom", "will_wisp"]},
        ],
        "elite": [
            {"name": "Звонница утопленника", "maps": ["ex_bell_ringer"], "enemies": ["bell_ringer", "drowned", "drowned"]},
            {"name": "Логово Старого Зуба", "maps": ["ex_old_tooth"], "enemies": ["old_tooth", "will_wisp", "mosquito_swarm"]},
            {"name": "Отряд Ржавых", "maps": ["ex_rivals"], "enemies": ["rust_captain", "rust_merc", "poacher", "rust_merc"]},
        ],
        "boss": [{"name": "Трон Квакса", "maps": ["ex_kvaks_throne"], "enemies": ["kvaks", "toad_guard"]}],
    }},
]

RELICS = {
    "whetstone": {"name": "Точило", "icon": "relic_whetstone", "about": "В начале хода: следующая карта [Удар] — ещё +3 урона.",
                  "on": "turn", "do": [{"op": "empower", "tag": "Удар", "n": 3}]},
    "iron_lid": {"name": "Щит-крышка", "icon": "relic_iron_vow", "about": "В начале боя: 10 защиты.",
                 "on": "battle", "do": [{"op": "block", "n": 10}]},
    "horseshoe": {"name": "Подкова", "icon": "item_loop", "about": "В начале боя: взять 2 карты.",
                  "on": "battle", "do": [{"op": "draw", "n": 2}]},
    "blood_stone": {"name": "Кровавый камень", "icon": "gift_blood_thirst", "about": "Убийство: лечение 3.",
                    "on": "kill", "do": [{"op": "heal", "n": 3}]},
    "war_horn": {"name": "Трофейный рог", "icon": "relic_war_drum", "about": "Первое убийство за ход: +1 энергия.",
                 "on": "kill", "once": True, "do": [{"op": "energy", "n": 1}]},
    "hourglass": {"name": "Песочные часы", "icon": "gift_spare_time", "about": "Серия 3 (третья карта за ход): взять карту.",
                  "on": "series", "n": 3, "do": [{"op": "draw", "n": 1}]},
    "light_boots": {"name": "Лёгкие сапоги", "icon": "gift_elusive_step", "about": "Первая карта [Шаг] за ход: 3 защиты.",
                    "on": "play", "tag": "Шаг", "once": True, "do": [{"op": "block", "n": 3}]},
    "ember_jar": {"name": "Банка углей", "icon": "relic_boiling_pot", "about": "В начале хода: ближайшему врагу горение 2.",
                  "on": "turn", "aim": "nearest", "do": [{"op": "burn", "n": 2}]},
    "thorn_mantle": {"name": "Шипастый наплечник", "icon": "gift_thorn_skin", "about": "В начале хода: шипы 2.",
                     "on": "turn", "do": [{"op": "thorns", "n": 2}]},
    "strength_flask": {"name": "Склянка силы", "icon": "gift_strong_brew", "about": "В начале боя: 1 сила.",
                       "on": "battle", "do": [{"op": "strength", "n": 1}]},
    "amber_eye": {"name": "Янтарный глаз", "icon": "relic_amber_charm", "about": "Первая карта [Выстрел] или [Огонь] за ход: метка 2 ближайшему.",
                  "on": "play", "tag": ["Выстрел", "Огонь"], "once": True, "aim": "nearest", "do": [{"op": "mark", "n": 2}]},
    "reed_charm": {"name": "Камышовый оберег", "icon": "relic_bog_moss", "about": "«Тина» и сглаз: первая «Тина» за ход сгорает сама.",
                   "on": "passive", "key": "cleanse_rot"},
}

ROT = {"name": "Тина", "type": "skill", "cost": 1, "status": True, "exhaust": True, "art": "gift_steel_shell",
       "ill": ["drowning", 0.3, 0.75, 0.35], "main": {"target": "self", "do": [{"op": "scrape"}]},
       "growth": [], "about": "Мусор от врагов: занимает руку. Основное (1 энергия) — отскрести, карта сгорает."}


def main():
    p = os.path.join(D, "enemies.json")
    e = json.load(open(p, encoding="utf-8"))
    e["enemies"].update(ENEMIES)
    e["chapter"] = {"_doc": "Глава 1 — Болото: три этажа, на каждом свой состав и страж; после стража 3-го этажа — "
                            "победа (tools/descent_chapter1.py).", "name": "Болото", "floors": FLOORS}
    e["floor"]["pools"] = FLOORS[0]["pools"]
    e["floor"]["weights"]["elite"] = 14
    e["floor"]["hp_per_depth"] = 0.15                      # глава из трёх этажей — рост мягче
    e["floor"]["dmg_per_depth"] = 0.10
    e["shop"]["relic_price"] = [110, 140]
    json.dump(e, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"_doc": "Реликвии «Спуска»: on — когда срабатывает (battle — начало боя, turn — начало хода, kill — "
                       "убийство, series — n-я карта за ход, play — карта с тегом, passive — особое); do — действия; "
                       "aim nearest — ближайшему врагу; once — раз за ход. Источники: элита (1 из 2), страж (1 из 3), "
                       "торговец.", "relics": RELICS},
              open(os.path.join(D, "relics.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    p = os.path.join(D, "cards.json")
    c = json.load(open(p, encoding="utf-8"))
    c["cards"]["slime_rot"] = ROT
    json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ok:", len(ENEMIES), "врагов,", len(RELICS), "реликвий")


if __name__ == "__main__":
    main()
