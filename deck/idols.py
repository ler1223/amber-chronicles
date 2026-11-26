"""Жрец идолов «Спуска»: статуи богов на поле, свитки через них, намерения статуй, призванные (прототип).

Механика (docs/descent_heroes2.md, раздел 1; квиз 2026-11-21): Жрец сам только ходит, вся сила — от статуй
его пантеона. Свиток (карта со смыслом: атака, защита, движение, проклятие, дар, призыв) тянут на статую,
и бог исполняет смысл по-своему (таблица 1.6); цель — в досягаемости статуи. Намерение статуи — её
собственный свиток, разыгрывается сам в конце хода. Враги статуи не трогают: это камень-преграда (путь и
выстрелы). Числа — первая прикидка, «потом поправим».

Battle (deck/battle.py) держит self.idols = Idols(self) только у героя с mechanic "idols".
"""
import re

from sim.combat import ENEMY, PLAYER
from sim.grid import DIRS8, cheb, sign

from . import model as M

WAIT = ("wait", 0.0)
IMPACT = ("impact", 0.0)
MEANINGS = ("attack", "defense", "move", "curse", "gift", "summon")
MEANING_NAME = {"attack": "Атака", "defense": "Защита", "move": "Движение", "curse": "Проклятие", "gift": "Дар",
                "summon": "Призыв"}
MEANING_ICON = {"attack": "i_melee", "defense": "i_block", "move": "i_charge", "curse": "i_hex", "gift": "i_rally",
                "summon": "i_summon"}

# бог → смысл → (как выбирается цель, название, коротко, эффект)
# pick: None — без выбора; enemy — враг в досягаемости; cell — клетка; free — свободная клетка; line — клетка на
# линии от статуи (Стрибог); any_free — любая свободная клетка поля
SPEC = {
    "perun": {
        "attack": ("enemy", "Молния", "{6} урона; мокрому ×2 и перескок на соседнего мокрого ({4})", "chain_lightning"),
        "defense": (None, "Священный дуб", "щит {3}; до хода Жреца выстрелы по нему, пока он в 2 от статуи, "
                                          "уходят в статую", "storm_totem"),
        "move": ("cell", "Гром", "враги в 1 от точки удара отлетают на 1; стоящему в ней — {2}", "thunderstorm"),
        "curse": ("enemy", "Громовой знак", "2 хода любая атака статуй по цели — ещё 3 молнией", "chain_lightning"),
        "gift": (None, "Дождь", "все враги на поле мокнут", "thunderstorm"),
        "summon": ("cell", "Грозовая туча", "3 хода над клеткой: в конце хода мочит и бьёт 3", "thunderstorm"),
    },
    "svarog": {
        "attack": ("enemy", "Молот", "{7} урона стоящему рядом со статуей", "e_hammer"),
        "defense": (None, "Наковальня", "щит {6} Жрецу в 2 от статуи, иначе {3}", None),
        "move": (None, "Отдача", "все враги рядом со статуей отлетают на 1", "e_hammer"),
        "curse": ("enemy", "Звон", "оглушить врага рядом со статуей", "e_hammer"),
        "gift": (None, "Закалка", "следующие 2 свитка любой статуи +2", None),
        "summon": ("free", "Сварожич", "огненный дух на 3 хода: жжёт соседей (горение 2)", "fireball"),
    },
    "stribog": {
        "attack": ("line", "Стрела ветра", "{4} урона всем на линии", "whirlwind"),
        "defense": (None, "Встречный ветер", "щит {2}; до хода Жреца выстрелы по нему вдвое слабее", "whirlwind"),
        "move": ("line", "Порыв", "всех на линии — на {2} от статуи (столкновения)", "whirlwind"),
        "curse": ("line", "Вихрь", "оглушить первого врага на линии", "whirlwind"),
        "gift": (None, "Попутный ветер", "Жрецу +{2} шага в этот ход", None),
        "summon": ("line", "Смерч", "3 хода: идёт к врагу, толкает и бьёт 2", "whirlwind"),
    },
    "yarilo": {
        "attack": (None, "Луч", "{3} урона всем врагам в свете (2 клетки)", "judgment"),
        "defense": (None, "Тепло", "лечит Жреца {4} в свете, иначе {2}", "heal"),
        "move": (None, "Зов", "Жрец — к статуе (на соседнюю клетку)", "judgment"),
        "curse": (None, "Ослепление", "слабость {2} всем врагам в свете", "judgment"),
        "gift": (None, "Рост", "статуя крепнет: её числа +1 за каждый следующий ход", None),
        "summon": ("free", "Росток", "куст-укрытие на 4 хода: лечит Жреца рядом на 1", "heal"),
    },
    "veles": {
        "attack": ("enemy", "Удушье", "{2} урона и ещё 2 за каждый стак яда", "e_wither"),
        "defense": (None, "Туман Нави", "до хода Жреца враги дальше 1 клетки его не видят", "poison_cloud"),
        "move": ("cell", "Трясина", "клетка — топь до конца боя: кто в ней, вязнет и мокнет", "poison_cloud"),
        "curse": ("enemy", "Порча", "яд {3}; гибнет — яд переходит на соседей", "e_plague"),
        "gift": (None, "Богатство", "+1 свиток сейчас и +1 к добору следующего хода", None),
        "summon": ("free", "Волк", "зверь 10 HP на 4 хода: сам идёт к врагу, бьёт 3", None),
    },
    "mokosh": {
        "attack": ("enemy", "Нить", "{3} урона цели и ближайшему к ней врагу; связать их на 2 хода", "curse"),
        "defense": (None, "Вплести", "щит {3}; следующий удар по Жрецу уйдёт связанному врагу", "curse"),
        "move": ("enemy", "Подтянуть", "врага — к статуе на {3}", "curse"),
        "curse": ("enemy", "Узел судьбы", "ослабить намерение врага вдвое", "curse"),
        "gift": (None, "Прялка", "следующий свиток этой статуи — дважды", None),
        "summon": ("enemy", "Веретено", "врага держат нити: не ходит {2} хода", "curse"),
    },
    "morana": {
        "attack": ("enemy", "Серп", "{5} урона; раненому (меньше половины HP) ×2", "ice_bolt"),
        "defense": (None, "Ледяная корка", "щит {8}, но следующий ход Жрец не ходит", "frost_guard"),
        "move": ("enemy", "Скольжение", "враг скользит от статуи до упора", "ice_bolt"),
        "curse": ("enemy", "Стужа", "мороз {4} (на 10 — скован; мокрый — сразу)", "frost_needle"),
        "gift": (None, "Мёртвая вода", "следующий свиток, что добьёт врага, вернётся в руку", None),
        "summon": ("free", "Мара", "призрак на 3 хода: морозит соседей (мороз 2)", "frost_needle"),
    },
    "chernobog": {
        "attack": ("enemy_any", "Тёмный удар", "{9} урона любой цели; Жрец −2 HP", "soul_lance"),
        "defense": (None, "Чёрная сделка", "щит {8}; в сброс — «Тина»", "curse"),
        "move": ("any_free", "Тьма", "Жрец переносится на любую свободную клетку", "blink"),
        "curse": ("enemy_any", "Злая доля", "слабость и уязвимость {2}; Жрец −1 HP", "curse"),
        "gift": (None, "Жертва", "сжечь случайный свиток из руки — следующий свиток ×2", None),
        "summon": ("enemy_any", "Тень", "двойник врага на нашей стороне на 2 хода (бьёт 4); Жрец −4 HP",
                   "blink"),
    },
}
# эффекты свитков, у которых метод сам эффекта не играет: (бог, смысл) → (эффект, куда: hero/target/statue/area)
CAST_FX = {
    ("perun", "defense"): ("storm_totem", "statue"), ("perun", "curse"): ("e_chain", "target"),
    ("perun", "gift"): ("e_rain", "statue"), ("perun", "summon"): ("e_thunderstorm", "area"),
    ("svarog", "defense"): ("shield_wall", "hero"), ("svarog", "gift"): ("inspire", "statue"),
    ("svarog", "summon"): ("flashpoint", "area"),
    ("stribog", "defense"): ("purify", "hero"), ("stribog", "gift"): ("haste", "hero"),
    ("stribog", "summon"): ("whirlwind", "area"),
    ("yarilo", "move"): ("blink", "hero"), ("yarilo", "gift"): ("miracle", "statue"),
    ("yarilo", "summon"): ("spirit_tree", "area"),
    ("veles", "gift"): ("e_regrowth", "statue"), ("veles", "summon"): ("hunter_beast", "area"),
    ("mokosh", "defense"): ("spirit_link", "hero"), ("mokosh", "gift"): ("rhythm", "statue"),
    ("morana", "defense"): ("frost_guard", "hero"), ("morana", "gift"): ("e_frost_ward", "statue"),
    ("morana", "summon"): ("e_wail", "area"),
    ("chernobog", "defense"): ("soul_shield", "hero"), ("chernobog", "gift"): ("devour", "statue"),
    ("chernobog", "move"): ("blink", "area"), ("chernobog", "summon"): ("e_mirror", "target"),
}
REACH_TEXT = {"perun": "с неба: любая клетка в 3", "svarog": "рядом (1 клетка)", "stribog": "прямые линии до 5",
              "yarilo": "свет: 2 клетки вокруг", "veles": "2 клетки; топь и вода — дальше",
              "mokosh": "3 клетки", "morana": "2 клетки", "chernobog": "всё поле"}
# ветки богов: на каждом уровне после боя — аура статуи, 1 из 2 (квиз 2026-11-21: «только ауры» — переделки
# смыслов теперь делают ступени действий на картах, TIERS; поле «m» ниже — прежние переделки, не используются). Переделка — модификаторы поверх смысла:
# plus — к числам, twice — ещё раз, after — цели (юнит или враг на клетке), near — врагам у статуи (r, ops),
# hero — Жрецу (shield, heal, walk, draw). Аура: (название, описание, вид, число, радиус).
BRANCHES = {
    "perun": {"m": {
        "attack": ("Раскат", "Молния +2, цель мокнет", {"plus": 2, "after": [("wet",)]}),
        "defense": ("Дубовая кора", "ещё щит 3 и лечение 2", {"hero": [("shield", 3), ("heal", 2)]}),
        "move": ("Громовой удар", "Гром дважды", {"twice": True}),
        "curse": ("Клеймо грозы", "Знак — ещё и слабость 2", {"after": [("weak", 2)]}),
        "gift": ("Ливень", "Дождь — и +1 свиток", {"hero": [("draw", 1)]}),
        "summon": ("Две тучи", "Туча дважды", {"twice": True})},
        "a": [("Сырой воздух", "в конце хода враги в 2 от статуи мокнут", "wet_near", 0, 2),
              ("Громоотвод", "Жрец в 2 от статуи: щит 2 в начале хода", "shield_hero", 2, 2),
              ("Гнев небес", "намерение статуи +2", "intent", 2, 0),
              ("Удар с неба", "досягаемость статуи +1", "reach", 1, 0),
              ("Перунов гнев", "в конце хода враги рядом со статуей — 3 урона", "dmg_near", 3, 1)]},
    "svarog": {"m": {
        "attack": ("Тяжкий молот", "Молот +3 и оглушение", {"plus": 3, "after": [("stun",)]}),
        "defense": ("Кованый щит", "Наковальня дважды", {"twice": True}),
        "move": ("Ударная волна", "Отдача — и 3 урона всем рядом", {"near": (1, [("damage", 3)])}),
        "curse": ("Набат", "Звон — и уязвимость 2", {"after": [("vulnerable", 2)]}),
        "gift": ("Горн", "Закалка — и +1 свиток", {"hero": [("draw", 1)]}),
        "summon": ("Двое сварожичей", "призыв дважды", {"twice": True})},
        "a": [("Жар горна", "в конце хода враги рядом со статуей горят (1)", "burn_near", 1, 1),
              ("Кольчуга", "Жрец в 2 от статуи: щит 3 в начале хода", "shield_hero", 3, 2),
              ("Подмастерья", "намерение статуи +2", "intent", 2, 0),
              ("Длинная рукоять", "досягаемость статуи +1", "reach", 1, 0),
              ("Наковальня земли", "в конце хода враги рядом со статуей — 3 урона", "dmg_near", 3, 1)]},
    "stribog": {"m": {
        "attack": ("Буря", "Стрела ветра +2 и слабость 1", {"plus": 2, "after": [("weak", 1)]}),
        "defense": ("Вихрь-щит", "ещё щит 3 и +1 шаг", {"hero": [("shield", 3), ("walk", 1)]}),
        "move": ("Ураган", "Порыв на 1 дальше", {"plus": 1}),
        "curse": ("Сбивающий шквал", "Вихрь — и 3 урона всем на линии", {"after": [("damage", 3)]}),
        "gift": ("Крылья", "Попутный ветер — и +1 свиток", {"hero": [("draw", 1)]}),
        "summon": ("Два смерча", "призыв дважды", {"twice": True})},
        "a": [("Попутный", "Жрецу +1 шаг каждый ход", "walk", 1, 0),
              ("Ветер в спину", "Жрец в 2 от статуи: щит 2 в начале хода", "shield_hero", 2, 2),
              ("Шторм", "намерение статуи +1", "intent", 1, 0),
              ("Дальний ветер", "досягаемость статуи +1 (линии длиннее)", "reach", 1, 0),
              ("Сквозняк", "в конце хода враги рядом со статуей: слабость 1", "weak_near", 1, 1)]},
    "yarilo": {"m": {
        "attack": ("Полдень", "Луч +2", {"plus": 2}),
        "defense": ("Солнечный венец", "Тепло — и щит 4", {"hero": [("shield", 4)]}),
        "move": ("Солнечный путь", "Зов — и +2 шага", {"hero": [("walk", 2)]}),
        "curse": ("Ослепительный", "Ослепление — и 2 урона всем в свете", {"near": (2, [("damage", 2)])}),
        "gift": ("Весна", "Рост — и лечение 3", {"hero": [("heal", 3)]}),
        "summon": ("Роща", "призыв дважды", {"twice": True})},
        "a": [("Тёплый свет", "Жрец в 2 от статуи: лечение 1 в конце хода", "heal_hero", 1, 2),
              ("Зной", "в конце хода враги в свете горят (1)", "burn_near", 1, 2),
              ("Ярь", "намерение статуи +2", "intent", 2, 0),
              ("Длинный день", "досягаемость статуи +1", "reach", 1, 0),
              ("Солнцестояние", "Жрецу +1 свиток каждый ход", "draw", 1, 0)]},
    "veles": {"m": {
        "attack": ("Змеиный яд", "Удушье — и яд 2", {"after": [("poison", 2)]}),
        "defense": ("Шкура", "Туман — и щит 4", {"hero": [("shield", 4)]}),
        "move": ("Болотина", "Трясина — и яд 2 тому, кто в ней", {"after": [("poison", 2)]}),
        "curse": ("Мор", "Порча +2", {"plus": 2}),
        "gift": ("Клад", "Богатство — и ещё +1 свиток", {"hero": [("draw", 1)]}),
        "summon": ("Стая", "призыв дважды", {"twice": True})},
        "a": [("Миазмы", "в конце хода враги рядом со статуей: яд 1", "poison_near", 1, 1),
              ("Хозяин Нави", "досягаемость статуи +1", "reach", 1, 0),
              ("Пастух", "намерение статуи +2", "intent", 2, 0),
              ("Сырость", "в конце хода враги в 2 от статуи мокнут", "wet_near", 0, 2),
              ("Изобилие", "Жрецу +1 свиток каждый ход", "draw", 1, 0)]},
    "mokosh": {"m": {
        "attack": ("Острая нить", "Нить +2", {"plus": 2}),
        "defense": ("Кокон", "Вплести дважды", {"twice": True}),
        "move": ("Тугая нить", "Подтянуть — и оглушить", {"after": [("stun",)]}),
        "curse": ("Злая пряжа", "Узел — и слабость 2", {"after": [("weak", 2)]}),
        "gift": ("Веретено судьбы", "Прялка — и +1 свиток", {"hero": [("draw", 1)]}),
        "summon": ("Сеть", "Веретено — и 3 урона", {"after": [("damage", 3)]})},
        "a": [("Нити вокруг", "в конце хода враги рядом со статуей не ходят (1 ход)", "root_near", 1, 1),
              ("Защита пряхи", "Жрец в 2 от статуи: щит 2 в начале хода", "shield_hero", 2, 2),
              ("Длинные нити", "досягаемость статуи +1", "reach", 1, 0),
              ("Узелок на память", "Жрецу +1 свиток каждый ход", "draw", 1, 0),
              ("Доля", "в конце хода враги рядом со статуей: уязвимость 1", "vuln_near", 1, 1)]},
    "morana": {"m": {
        "attack": ("Коса", "Серп +3", {"plus": 3}),
        "defense": ("Ледяной панцирь", "Корка — и лечение 3", {"hero": [("heal", 3)]}),
        "move": ("Наледь", "Скольжение — и мороз 3", {"after": [("frost", 3)]}),
        "curse": ("Смертный холод", "Стужа +2", {"plus": 2}),
        "gift": ("Живая и мёртвая", "Мёртвая вода — и +1 свиток", {"hero": [("draw", 1)]}),
        "summon": ("Хоровод мар", "призыв дважды", {"twice": True})},
        "a": [("Иней", "в конце хода враги рядом со статуей: мороз 2", "frost_near", 2, 1),
              ("Студёный покров", "Жрец в 2 от статуи: щит 2 в начале хода", "shield_hero", 2, 2),
              ("Лютая", "намерение статуи +2", "intent", 2, 0),
              ("Долгая зима", "досягаемость статуи +1", "reach", 1, 0),
              ("Сон смерти", "в конце хода враги в 2 от статуи: слабость 1", "weak_near", 1, 2)]},
    "chernobog": {"m": {
        "attack": ("Чёрная кара", "Тёмный удар +3", {"plus": 3}),
        "defense": ("Тёмный щит", "Сделка — и лечение 3", {"hero": [("heal", 3)]}),
        "move": ("Шаг во тьму", "Тьма — и щит 4", {"hero": [("shield", 4)]}),
        "curse": ("Проклятие рода", "Злая доля +1 и оглушение", {"plus": 1, "after": [("stun",)]}),
        "gift": ("Великая жертва", "Жертва — и +1 свиток", {"hero": [("draw", 1)]}),
        "summon": ("Тени", "призыв дважды", {"twice": True})},
        "a": [("Ужас", "в конце хода враги рядом со статуей: слабость 1", "weak_near", 1, 1),
              ("Сытость", "Чернобог не голодает", "nohunger", 0, 0),
              ("Тёмная жатва", "намерение статуи +3", "intent", 3, 0),
              ("Кровь за кровь", "в конце хода враги рядом со статуей — 3 урона", "dmg_near", 3, 1),
              ("Злая сила", "Жрецу +1 свиток каждый ход", "draw", 1, 0)]},
}

# ступени действий (квиз 2026-11-21): качество действия на карте — I (основа, SPEC) … IV; у каждого бога на каждый
# смысл свои II, III, IV — (название, что добавляет, модификаторы). Модификаторы: plus — к числам; twice — ещё раз;
# times — ещё N раз; after — цели; chain (r, ops) — врагам в r от цели; near (r, ops) — врагам у статуи;
# all — всем врагам; hero — Жрецу (shield, heal, walk, draw).
D_, W_, P_, F_, B_, K_, V_, S_, R_, T_ = ("damage",), ("wet",), ("poison",), ("frost",), ("burn",), ("weak",), \
    ("vulnerable",), ("stun",), ("root",), ("thunder",)


def d(n):
    return ("damage", n)


TIERS = {
    "perun": {
        "attack": [("Цепная молния", "+2; перескок 4 на всех в 1 от цели", {"plus": 2, "chain": (1, [d(4)])}),
                   ("Гроза", "+3; по всем в 2 от цели 5, мокнут", {"plus": 3, "chain": (2, [d(5), W_])}),
                   ("Перунов гнев", "+5; молния 6 по всем врагам, все мокнут", {"plus": 5, "all": [d(6), W_]})],
        "defense": [("Дубрава", "+2 к щиту, лечение 2", {"plus": 2, "hero": [("heal", 2)]}),
                    ("Дуб-громоотвод", "+4 к щиту; врагам в 2 от статуи — 3", {"plus": 4, "near": (2, [d(3)])}),
                    ("Небесный щит", "+8 к щиту, лечение 5; врагам в 2 — 5 и оглушение",
                     {"plus": 8, "hero": [("heal", 5)], "near": (2, [d(5), S_])})],
        "move": [("Раскат", "Гром дважды, +2", {"plus": 2, "twice": True}),
                 ("Громовой удар", "дважды, +3; соседи цели оглушены", {"plus": 3, "twice": True, "chain": (1, [S_])}),
                 ("Сотрясение небес", "дважды, +4; все враги — слабость 1", {"plus": 4, "twice": True, "all": [("weak", 1)]})],
        "curse": [("Клеймо", "знак и слабость 2", {"after": [("weak", 2)]}),
                  ("Двойной знак", "знак и соседям цели, уязвимость 1", {"after": [("vulnerable", 1)], "chain": (1, [T_])}),
                  ("Знак громовержца", "знак на всех врагов, все мокнут", {"all": [T_, W_]})],
        "gift": [("Ливень", "дождь и +1 свиток", {"hero": [("draw", 1)]}),
                 ("Ливень и град", "+1 свиток; всем врагам 2", {"hero": [("draw", 1)], "all": [d(2)]}),
                 ("Потоп", "+2 свитка; всем врагам 4 и слабость 1", {"hero": [("draw", 2)], "all": [d(4), ("weak", 1)]})],
        "summon": [("Две тучи", "туча дважды", {"twice": True}),
                   ("Грозовой фронт", "две тучи; враги в 2 от статуи мокнут", {"twice": True, "near": (2, [W_])}),
                   ("Небесная рать", "две тучи; все враги мокнут; щит 5", {"twice": True, "all": [W_], "hero": [("shield", 5)]})],
    },
    "svarog": {
        "attack": [("Тяжкий молот", "+3", {"plus": 3}),
                   ("Молот и наковальня", "+4 и оглушение", {"plus": 4, "after": [S_]}),
                   ("Кузнечный гром", "+6, оглушение; всем у статуи 6", {"plus": 6, "after": [S_], "near": (1, [d(6)])})],
        "defense": [("Кольчуга", "+3 к щиту", {"plus": 3}),
                    ("Броня", "+5 к щиту, лечение 3", {"plus": 5, "hero": [("heal", 3)]}),
                    ("Небесная кузня", "+9 к щиту, лечение 5; у статуи горят", {"plus": 9, "hero": [("heal", 5)], "near": (1, [("burn", 2)])})],
        "move": [("Ударная волна", "и 3 урона всем у статуи", {"near": (1, [d(3)])}),
                 ("Удар оземь", "и 4 с оглушением всем у статуи", {"near": (1, [d(4), S_])}),
                 ("Разлом", "дважды; всем в 2 от статуи 5", {"twice": True, "near": (2, [d(5)])})],
        "curse": [("Набат", "и уязвимость 2", {"after": [("vulnerable", 2)]}),
                  ("Колокол", "уязвимость 2; у статуи — слабость 1", {"after": [("vulnerable", 2)], "near": (1, [("weak", 1)])}),
                  ("Звон наковальни", "оглушение; все враги — слабость 2", {"all": [("weak", 2)]})],
        "gift": [("Горн", "и +1 свиток", {"hero": [("draw", 1)]}),
                 ("Жар горна", "+1 свиток, щит 4", {"hero": [("draw", 1), ("shield", 4)]}),
                 ("Закалённый дух", "+2 свитка, щит 8", {"hero": [("draw", 2), ("shield", 8)]})],
        "summon": [("Двое сварожичей", "призыв дважды", {"twice": True}),
                   ("Огненный круг", "дважды; у статуи горят 2", {"twice": True, "near": (1, [("burn", 2)])}),
                   ("Кузнечная рать", "дважды; в 2 горят 3; щит 4", {"twice": True, "near": (2, [("burn", 3)]), "hero": [("shield", 4)]})],
    },
    "stribog": {
        "attack": [("Буря", "+2 и слабость 1", {"plus": 2, "after": [("weak", 1)]}),
                   ("Шквал", "дважды, +3", {"plus": 3, "twice": True}),
                   ("Ураган", "дважды, +4; все враги — слабость 1", {"plus": 4, "twice": True, "all": [("weak", 1)]})],
        "defense": [("Вихрь-щит", "+3 к щиту, +1 шаг", {"plus": 3, "hero": [("walk", 1)]}),
                    ("Ветреный покров", "+4 к щиту, +2 шага", {"plus": 4, "hero": [("walk", 2)]}),
                    ("Око бури", "+8 к щиту, +2 шага; в 2 — слабость 2", {"plus": 8, "hero": [("walk", 2)], "near": (2, [("weak", 2)])})],
        "move": [("Ураган", "на 1 дальше", {"plus": 1}),
                 ("Буря на линии", "на 2 дальше и 3 урона", {"plus": 2, "after": [d(3)]}),
                 ("Смерч", "дважды, на 3 дальше", {"plus": 3, "twice": True})],
        "curse": [("Шквал", "и 3 урона", {"after": [d(3)]}),
                  ("Сбивающий шквал", "4 урона; соседи цели оглушены", {"after": [d(4)], "chain": (1, [S_])}),
                  ("Буран", "6 урона; все враги — слабость 2", {"after": [d(6)], "all": [("weak", 2)]})],
        "gift": [("Крылья", "и +1 свиток", {"hero": [("draw", 1)]}),
                 ("Ветер перемен", "+1 свиток, +2 шага", {"hero": [("draw", 1), ("walk", 2)]}),
                 ("Вихрь", "+2 свитка, +3 шага", {"hero": [("draw", 2), ("walk", 3)]})],
        "summon": [("Два смерча", "призыв дважды", {"twice": True}),
                   ("Вихри", "дважды; в 2 от статуи — слабость 1", {"twice": True, "near": (2, [("weak", 1)])}),
                   ("Буря", "дважды; все враги — слабость 1; +2 шага", {"twice": True, "all": [("weak", 1)], "hero": [("walk", 2)]})],
    },
    "yarilo": {
        "attack": [("Полдень", "+2", {"plus": 2}),
                   ("Зной", "+3; в свете горят 2", {"plus": 3, "near": (2, [("burn", 2)])}),
                   ("Солнцеворот", "+5; всем врагам 3 и горение 2", {"plus": 5, "all": [d(3), ("burn", 2)]})],
        "defense": [("Солнечный венец", "и щит 4", {"hero": [("shield", 4)]}),
                    ("Живительный свет", "+3, щит 5", {"plus": 3, "hero": [("shield", 5)]}),
                    ("Воскрешающее солнце", "+8, щит 8", {"plus": 8, "hero": [("shield", 8)]})],
        "move": [("Солнечный путь", "и +2 шага", {"hero": [("walk", 2)]}),
                 ("Тропа света", "+2 шага, лечение 3", {"hero": [("walk", 2), ("heal", 3)]}),
                 ("Восход", "+3 шага, лечение 5; в свете — слабость 2", {"hero": [("walk", 3), ("heal", 5)], "near": (2, [("weak", 2)])})],
        "curse": [("Ослепительный", "и 2 урона в свете", {"near": (2, [d(2)])}),
                  ("Слепящий полдень", "+1; в свете 3 и уязвимость 1", {"plus": 1, "near": (2, [d(3), ("vulnerable", 1)])}),
                  ("Огненное око", "+2; все враги — слабость 2, горение 2", {"plus": 2, "all": [("weak", 2), ("burn", 2)]})],
        "gift": [("Весна", "и лечение 3", {"hero": [("heal", 3)]}),
                 ("Цветение", "лечение 4, +1 свиток", {"hero": [("heal", 4), ("draw", 1)]}),
                 ("Купала", "лечение 6, +2 свитка", {"hero": [("heal", 6), ("draw", 2)]})],
        "summon": [("Роща", "призыв дважды", {"twice": True}),
                   ("Священная роща", "дважды, лечение 3", {"twice": True, "hero": [("heal", 3)]}),
                   ("Ярилин сад", "дважды, лечение 5, щит 5", {"twice": True, "hero": [("heal", 5), ("shield", 5)]})],
    },
    "veles": {
        "attack": [("Змеиный яд", "и яд 2", {"after": [("poison", 2)]}),
                   ("Удав", "+2, яд 3, не ходит", {"plus": 2, "after": [("poison", 3), ("root", 1)]}),
                   ("Змей Нави", "+4, яд 4; соседям цели яд 3", {"plus": 4, "after": [("poison", 4)], "chain": (1, [("poison", 3)])})],
        "defense": [("Шкура", "и щит 4", {"hero": [("shield", 4)]}),
                    ("Мохнатая шкура", "щит 6, лечение 2", {"hero": [("shield", 6), ("heal", 2)]}),
                    ("Покров Нави", "щит 10; в 2 от статуи яд 2", {"hero": [("shield", 10)], "near": (2, [("poison", 2)])})],
        "move": [("Болотина", "и яд 2 тому, кто в топи", {"after": [("poison", 2)]}),
                 ("Топь", "яд 2; соседи тоже вязнут и мокнут", {"after": [("poison", 2)], "chain": (1, [("root", 1), W_])}),
                 ("Навья трясина", "дважды; в 2 от цели вязнут, яд 2", {"twice": True, "chain": (2, [("root", 1), ("poison", 2)])})],
        "curse": [("Мор", "+2", {"plus": 2}),
                  ("Чёрный мор", "+2; соседям цели яд 2", {"plus": 2, "chain": (1, [("poison", 2)])}),
                  ("Поветрие", "+3; всем врагам яд 3", {"plus": 3, "all": [("poison", 3)]})],
        "gift": [("Клад", "и +1 свиток", {"hero": [("draw", 1)]}),
                 ("Богатство Нави", "+2 свитка", {"hero": [("draw", 2)]}),
                 ("Скотий бог", "+2 свитка, щит 5", {"hero": [("draw", 2), ("shield", 5)]})],
        "summon": [("Стая", "призыв дважды", {"twice": True}),
                   ("Волчья стая", "дважды; в 2 от статуи — слабость 1", {"twice": True, "near": (2, [("weak", 1)])}),
                   ("Велесово стадо", "трижды; все враги — слабость 1", {"times": 2, "all": [("weak", 1)]})],
    },
    "mokosh": {
        "attack": [("Острая нить", "+2", {"plus": 2}),
                   ("Удавка", "+3, не ходит", {"plus": 3, "after": [("root", 1)]}),
                   ("Нить судьбы", "+5, не ходит 2; в 2 от цели 4", {"plus": 5, "after": [("root", 2)], "chain": (2, [d(4)])})],
        "defense": [("Кокон", "дважды", {"twice": True}),
                    ("Плотный кокон", "дважды, лечение 2", {"twice": True, "hero": [("heal", 2)]}),
                    ("Пелена судьбы", "дважды, лечение 4; в 2 — слабость 2", {"twice": True, "hero": [("heal", 4)], "near": (2, [("weak", 2)])})],
        "move": [("Тугая нить", "и оглушение", {"after": [S_]}),
                 ("Петля", "оглушение и 4 урона", {"after": [S_, d(4)]}),
                 ("Сеть судьбы", "дважды и оглушение", {"twice": True, "after": [S_]})],
        "curse": [("Злая пряжа", "и слабость 2", {"after": [("weak", 2)]}),
                  ("Порванная нить", "слабость 2, уязвимость 2", {"after": [("weak", 2), ("vulnerable", 2)]}),
                  ("Обрыв нити", "слабость 3, уязвимость 3; соседям слабость 2",
                   {"after": [("weak", 3), ("vulnerable", 3)], "chain": (1, [("weak", 2)])})],
        "gift": [("Веретено судьбы", "и +1 свиток", {"hero": [("draw", 1)]}),
                 ("Пряжа", "+1 свиток, щит 3", {"hero": [("draw", 1), ("shield", 3)]}),
                 ("Доля и недоля", "+2 свитка; все враги — слабость 1", {"hero": [("draw", 2)], "all": [("weak", 1)]})],
        "summon": [("Сеть", "и 3 урона", {"after": [d(3)]}),
                   ("Тенёта", "+1, 4 урона; соседи вязнут", {"plus": 1, "after": [d(4)], "chain": (1, [("root", 1)])}),
                   ("Паутина судьбы", "+2; все враги вязнут", {"plus": 2, "all": [("root", 1)]})],
    },
    "morana": {
        "attack": [("Коса", "+3", {"plus": 3}),
                   ("Ледяная коса", "+4, мороз 3", {"plus": 4, "after": [("frost", 3)]}),
                   ("Смертный серп", "+7, мороз 4; соседям мороз 4", {"plus": 7, "after": [("frost", 4)], "chain": (1, [("frost", 4)])})],
        "defense": [("Ледяной панцирь", "и лечение 3", {"hero": [("heal", 3)]}),
                    ("Вечная мерзлота", "+3, лечение 3", {"plus": 3, "hero": [("heal", 3)]}),
                    ("Ледяной гроб", "+8, лечение 5; у статуи мороз 4", {"plus": 8, "hero": [("heal", 5)], "near": (1, [("frost", 4)])})],
        "move": [("Наледь", "и мороз 3", {"after": [("frost", 3)]}),
                 ("Каток", "мороз 3; соседям мороз 2", {"after": [("frost", 3)], "chain": (1, [("frost", 2)])}),
                 ("Вьюга", "дважды; всем врагам мороз 2", {"twice": True, "all": [("frost", 2)]})],
        "curse": [("Смертный холод", "+2", {"plus": 2}),
                  ("Стужа", "+3; соседям мороз 3", {"plus": 3, "chain": (1, [("frost", 3)])}),
                  ("Лютая зима", "+4; всем врагам мороз 4", {"plus": 4, "all": [("frost", 4)]})],
        "gift": [("Живая и мёртвая", "и +1 свиток", {"hero": [("draw", 1)]}),
                 ("Мёртвая вода", "+1 свиток, лечение 4", {"hero": [("draw", 1), ("heal", 4)]}),
                 ("Живая вода", "+2 свитка, лечение 8", {"hero": [("draw", 2), ("heal", 8)]})],
        "summon": [("Хоровод мар", "призыв дважды", {"twice": True}),
                   ("Мары", "дважды; в 2 от статуи мороз 2", {"twice": True, "near": (2, [("frost", 2)])}),
                   ("Зимний хоровод", "трижды; всем врагам мороз 2", {"times": 2, "all": [("frost", 2)]})],
    },
    "chernobog": {
        "attack": [("Чёрная кара", "+3", {"plus": 3}),
                   ("Тёмная жатва", "+5; соседям цели 4", {"plus": 5, "chain": (1, [d(4)])}),
                   ("Конец света", "+7; всем врагам 5", {"plus": 7, "all": [d(5)]})],
        "defense": [("Тёмный щит", "и лечение 3", {"hero": [("heal", 3)]}),
                    ("Сделка с тьмой", "+4, лечение 3", {"plus": 4, "hero": [("heal", 3)]}),
                    ("Чёрная броня", "+10, лечение 5", {"plus": 10, "hero": [("heal", 5)]})],
        "move": [("Шаг во тьму", "и щит 4", {"hero": [("shield", 4)]}),
                 ("Тень за спиной", "щит 6, +2 шага", {"hero": [("shield", 6), ("walk", 2)]}),
                 ("Царство тьмы", "щит 8; все враги — слабость 2", {"hero": [("shield", 8)], "all": [("weak", 2)]})],
        "curse": [("Проклятие рода", "+1 и оглушение", {"plus": 1, "after": [S_]}),
                  ("Родовое проклятие", "+2, оглушение; соседям слабость 2", {"plus": 2, "after": [S_], "chain": (1, [("weak", 2)])}),
                  ("Чёрная доля", "+3; все враги — слабость и уязвимость 2", {"plus": 3, "all": [("weak", 2), ("vulnerable", 2)]})],
        "gift": [("Великая жертва", "и +1 свиток", {"hero": [("draw", 1)]}),
                 ("Сделка", "+2 свитка", {"hero": [("draw", 2)]}),
                 ("Тёмный завет", "+3 свитка, лечение 3", {"hero": [("draw", 3), ("heal", 3)]})],
        "summon": [("Тени", "призыв дважды", {"twice": True}),
                   ("Тени теней", "дважды; в 2 от статуи — слабость 1", {"twice": True, "near": (2, [("weak", 1)])}),
                   ("Войско тьмы", "трижды; все враги — слабость 1", {"times": 2, "all": [("weak", 1)]})],
    },
}
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}

# зрелищность ступеней: свой эффект бога на II, III, IV (поверх обычного), подпись над статуей, тряска экрана
TIER_FX = {"perun": ["e_chain", "thunderstorm", "e_thunderstorm"],
           "svarog": ["quake_strike", "e_slam", "earthquake"],
           "stribog": ["repulse", "sonic_blast", "whirlwind"],
           "yarilo": ["consecrate", "judgment", "miracle"],
           "veles": ["e_plague", "soul_harvest", "e_entangle"],
           "mokosh": ["spirit_link", "e_entangle", "stasis"],
           "morana": ["ice_shard", "frost_storm", "eternal_winter"],
           "chernobog": ["shadow_mark", "soul_lance", "world_fracture"]}
TIER_COLOR = {2: (200, 215, 235), 3: (255, 210, 110), 4: (255, 140, 230)}
LEVELS = [4, 12, 24, 40, 60]        # опыт бога (свитков через его статую за поход) → уровень; уровень — +1 к числам
SKIP = object()                     # для свитка-сочетания: эта статуя смысл не исполнит (некуда)
SUMMON_SPRITE = {"wolf": "druid_wolf", "imp": "fire_imp", "whirl": "thunder_elemental", "sprout": "spirit_tree",
                 "mara": "smith_ghost"}


class IdolCast:
    """Цель свитка Жреца: через какую статую и в кого (юнит, клетку или ничего)."""

    def __init__(self, statue, tgt=None):
        self.statue, self.tgt = statue, tgt

    @property
    def cell(self):                                         # для анимации полёта карты — к статуе
        return self.statue.cell


class Idols:
    def __init__(self, b):
        self.b = b
        gods = b.run.data["gods"]["gods"]
        self.pantheon = [gods[g] for g in self.pantheon_ids(b) if g in gods]
        self.statues = []
        self.summons = []            # [юнит]: у юнита .kind, .turns
        self.clouds = []             # [[клетка, ходов]]
        self.mud = set()             # клетки-топи Велеса
        self.temper = 0              # Сварог «Закалка»: сколько следующих свитков +2
        self.double = False          # Чернобог «Жертва»: следующий свиток ×2
        self.dead_water = False      # Морана: свиток, что добьёт, вернётся в руку
        self.extra_draw = 0          # Велес «Богатство»: +1 к добору следующего хода
        self.walk_bonus = 0          # ауры: +шаги в этот ход
        self.boost = 0
        self.plus = 0
        self.mult = 1
        self.killed = False
        self.place()

    @staticmethod
    def pantheon_ids(b):
        """Пантеон: из выбранного набора героя; «случайные» — 3 разных бога каждый бой."""
        p = (b.hero_def.get("passives") or {}).get(b.variant) or {}
        if p.get("random"):
            ids = sorted(b.run.data["gods"]["gods"])
            return b.rng.sample(ids, p.get("random", 3))
        return p.get("gods", ["perun", "veles", "mokosh"])

    # ---------- статуи ----------

    def place(self):
        """Статуи падают с неба на случайные клетки (не вплотную к Жрецу, не друг на друга); кто рядом с местом
        падения — получает удар 3."""
        b = self.b
        h = b.hero
        cells = [p for p, c in b.c.grid.cells.items() if b.free(p) and 2 <= cheb(p, h.cell) <= 6]
        b.rng.shuffle(cells)
        chosen = []
        for p in cells:
            if all(cheb(p, q) >= 2 for q in chosen):
                chosen.append(p)
            if len(chosen) == len(self.pantheon):
                break
        for god, p in zip(self.pantheon, chosen):
            sprite = god.get("statue", "idol")
            proto = {"name": god["name"], "label": god["name"][:2], "color": god["color"], "role": "object",
                     "hp": 999, "move_time": 1.0, "attack": {"damage": 0, "range": 0, "cooldown": 99.0},
                     "static": True, "object": {"id": "statue", "name": god["name"], "hp": 999,
                                                "color": god["color"], "art": sprite}}
            u = b.c._spawn(PLAYER, sprite, proto, p)
            b._setup(u, {"name": god["name"], "hp": 999})
            u.statue = god["id"]
            u.god = god
            u.repeat = 0
            u.grow = 0
            u.rod = False
            u.fed = False
            u.intent = None
            self.statues.append(u)
            for f in [f for f in b.foes() if cheb(f.cell, p) <= 1]:
                b.hurt(f, 3, h, "collision")
        if self.statues:
            b.say("С неба падают статуи: " + ", ".join(s.god["name"] for s in self.statues), (255, 220, 160))

    def god(self, st):
        return st.statue

    def reach(self, st):
        """Клетки, до которых бог достаёт со своей статуи."""
        b = self.b
        g = st.statue
        cells = b.c.grid.cells
        if g == "chernobog":
            return set(cells)
        if g == "stribog":
            return set(self.line_cells(st))
        r = {"perun": 3, "svarog": 1, "yarilo": 2, "veles": 2, "mokosh": 3, "morana": 2}.get(g, 2) + \
            self.aura_sum(st, "reach")
        out = {p for p in cells if cheb(p, st.cell) <= r and p != st.cell}
        if g == "veles":                                     # по воде и топи — дальше
            out |= {p for p in cells if any(cheb(p, m) <= 1 for m in self.mud)}
            out |= {p for p, c in cells.items() if c.terrain == "water" and cheb(p, st.cell) <= 4}
        return out

    def line_cells(self, st, d=None):
        """Стрибог: клетки по 8 прямым от статуи до 5 (ветер идёт над фигурками, стену не пробивает)."""
        out = []
        for dd in ([d] if d else DIRS8):
            p = st.cell
            for _ in range(5 + self.aura_sum(st, "reach")):
                p = (p[0] + dd[0], p[1] + dd[1])
                cell = self.b.c.grid.get(p)
                if cell is None or not cell.passable or any(s.cell == p for s in self.statues):
                    break
                out.append(p)
        return out

    def on_line(self, st, cell):
        d = (sign(cell[0] - st.cell[0]), sign(cell[1] - st.cell[1]))
        return d, [p for p in self.line_cells(st, d)]

    def choices(self, st, meaning):
        """Из чего выбирать цель свитка: None — без выбора; список (юниты или клетки); [] — некуда."""
        pick = SPEC[st.statue][meaning][0]
        b = self.b
        if pick is None:
            return None
        if pick == "enemy":
            reach = self.reach(st)
            return [f for f in b.foes() if f.cell in reach]
        if pick == "enemy_any":
            return list(b.foes())
        if pick == "cell":
            return sorted(self.reach(st))
        if pick == "free":
            return sorted(p for p in self.reach(st) if b.free(p))
        if pick == "line":
            return sorted(set(self.line_cells(st)))
        if pick == "any_free":
            return sorted(p for p in b.c.grid.cells if b.free(p))
        return []

    def silenced(self, st):
        """Статуя осквернена врагом: на ход Жреца молчит (свитки — только Движение, сама не действует)."""
        return getattr(st, "silence", 0) > 0

    def can_cast(self, st, meaning):
        ch = self.choices(st, meaning)
        return ch is None or bool(ch)

    # ---------- свиток ----------

    def n(self, st, base):
        """Число эффекта: + уровень бога, + сила свитка, + Закалка Сварога, + Рост Ярило; × Жертва Чернобога."""
        v = base + self.boost + self.plus + self.level(st) + (st.grow if st.statue == "yarilo" else 0)
        return v * self.mult

    # ---------- рост богов ----------

    def xp(self, st):
        return getattr(self.b.run, "god_xp", {}).get(st.statue, 0)

    def level(self, st):
        x = self.xp(st)
        return sum(1 for t in LEVELS if x >= t)

    def next_level(self, st):
        """(сколько опыта до следующего уровня, порог) или None — максимум."""
        lv = self.level(st)
        return (LEVELS[lv] - self.xp(st), LEVELS[lv]) if lv < len(LEVELS) else None

    def picks(self, st):
        return getattr(self.b.run, "god_picks", {}).get(st.statue, [])

    @staticmethod
    def tier_mods(god, meaning, q):
        """Модификаторы ступени q (I — основа: пусто)."""
        if q <= 1:
            return {}
        return TIERS[god][meaning][min(q, 4) - 2][2]

    def auras(self, st):
        a = BRANCHES[st.statue]["a"]
        return [a[i] for k, i in self.picks(st) if k == "a"]

    def aura_sum(self, st, kind):
        return sum(x[3] for x in self.auras(st) if x[2] == kind)

    def ib(self, st):
        """Прибавка к числам намерения: уровень + аура «намерение»."""
        return self.level(st) + self.aura_sum(st, "intent")

    @staticmethod
    def branch_offer(run, god, level):
        """Выбор на новом уровне: 2 случайные ещё не взятые ауры бога (последняя — одна)."""
        auras = BRANCHES[god]["a"]
        took = [i for k, i in run.god_picks.get(god, []) if k == "a"]
        free = [i for i in range(len(auras)) if i not in took]
        pick = run.rng.sample(free, min(2, len(free)))
        return [(("a", i), f"Аура: {auras[i][0]}", auras[i][1]) for i in sorted(pick)]

    def gain(self, st, n=1):
        """Свиток через статую — опыт её богу (на весь поход); новый уровень — объявление."""
        run = self.b.run
        if not hasattr(run, "god_xp"):
            run.god_xp = {}
        before = self.level(st)
        run.god_xp[st.statue] = run.god_xp.get(st.statue, 0) + n
        lv = self.level(st)
        if lv > before:
            if not hasattr(run, "god_pending"):
                run.god_pending = []
            for L in range(before + 1, lv + 1):
                run.god_pending.append((st.statue, L))             # ветка — после боя
            self.b.say(f"{st.god['name']} — уровень {lv}: числа +{lv}, после боя — ветка", (255, 230, 150))
            self.b.fx("phase", unit=st, name=f"{st.god['name']}: уровень {lv}")

    # ---------- свиток-сочетание ----------

    def auto(self, st, meaning):
        """Цель для статуи без выбора игрока (хор, перекличка): ближайший враг; клетка — где враг или рядом с
        ним; Тьма Чернобога (перенос Жреца куда угодно) — не сама. SKIP — некуда."""
        ch = self.choices(st, meaning)
        if ch is None:
            return None
        if not ch:
            return SKIP
        if SPEC[st.statue][meaning][0] == "any_free":
            return SKIP
        units = [c for c in ch if hasattr(c, "cell")]
        if units:
            return min(units, key=lambda f: (cheb(f.cell, st.cell), f.hp))
        foes = self.b.foes()
        if not foes:
            return ch[0]
        foe_cells = {f.cell for f in foes}
        on = [c for c in ch if c in foe_cells]
        if on:
            return min(on, key=lambda c: cheb(c, st.cell))
        return min(ch, key=lambda c: min(cheb(c, f.cell) for f in foes))

    def other(self, st, meaning):
        """Перекличка: другая статуя (ближе к Жрецу), что может исполнить смысл."""
        h = self.b.hero
        cand = [s for s in self.statues if s is not st and self.can_cast(s, meaning)
                and self.auto(s, meaning) is not SKIP]
        return min(cand, key=lambda s: cheb(s.cell, h.cell)) if cand else None

    @staticmethod
    def acts(card):
        """Действия свитка: [{"m": смысл, "q": ступень, "n": сколько раз}] (старый формат — один смысл)."""
        d = card.d
        return d.get("acts") or [{"m": d["meaning"], "q": 1 + (1 if d.get("plus") else 0), "n": 1 + d.get("repeat", 0)}]

    def target_for(self, st, meaning, tgt):
        """Цель действия статуи: выбранная игроком, если годится этому смыслу, иначе — сама (ближайшая)."""
        ch = self.choices(st, meaning)
        if ch is None:
            return None
        if tgt is not None and tgt in ch and (not hasattr(tgt, "alive") or tgt.alive):
            return tgt
        return self.auto(st, meaning)

    def cast_card(self, st, card, tgt):
        """Свиток целиком: все действия — выбранной статуей, по порядку (у каждого своя ступень и число раз);
        хор — первое действие ещё и всеми статуями; перекличка — следующие смыслы другой статуей."""
        b = self.b
        d = card.d
        before = len(b.foes())
        acts = self.acts(card)
        for i, act in enumerate(acts):
            if b.result:
                break
            m = act["m"]
            if m != "move" and self.silenced(st):          # осквернитель рядом — бог не слышит (кроме Движения)
                b.say(f"{st.god['name']} молчит: статуя осквернена", (190, 160, 160))
                continue
            t = tgt if i == 0 else self.target_for(st, m, tgt)
            if t is SKIP:
                b.say(f"{st.god['name']}: {MEANING_NAME[m]} — некуда", (190, 190, 190))
                continue
            yield from self.cast(st, m, t, q=act.get("q", 1), extra=act.get("n", 1) - 1)
        if d.get("chorus") and acts:
            m, q = acts[0]["m"], acts[0].get("q", 1)
            for o in [x for x in self.statues if x is not st]:
                if b.result:
                    break
                t2 = self.auto(o, m)
                if t2 is not SKIP:
                    yield from self.cast(o, m, t2, q=q)
        for step in d.get("then", []):
            if b.result:
                break
            m2 = step["m"]
            who = st if step.get("who", "same") == "same" else self.other(st, m2)
            if who is None:
                b.say("Перекличка: другой статуе некуда", (190, 190, 190))
                continue
            t2 = self.target_for(who, m2, tgt if who is st else None)
            if t2 is SKIP:
                continue
            yield from self.cast(who, m2, t2, q=step.get("q", 1))
        if d.get("walk"):
            b.walk_left += d["walk"]
            b.say(f"Жрецу +{d['walk']} шага", (190, 230, 200))
        if d.get("draw"):
            b.draw(d["draw"])
        self.killed = len(b.foes()) < before

    def cast(self, st, meaning, tgt, card=None, plus=0, extra=0, q=1):
        """Действие через статую: бог исполняет смысл ступени q (с повтором Прялки и свитка, Закалкой, Жертвой)."""
        b = self.b
        g = st.statue
        name = SPEC[g][meaning][1]
        boost_used = self.temper > 0 and meaning != "gift"
        double_used = self.double and meaning != "gift"
        mods = self.tier_mods(g, meaning, q)
        reps = 1 + st.repeat + extra + (1 if mods.get("twice") else 0) + mods.get("times", 0)
        st.repeat = 0
        self.boost = 2 if boost_used else 0
        self.mult = 2 if double_used else 1
        self.plus = plus + mods.get("plus", 0)
        self.killed = False
        before = len(b.foes())
        if q > 1:
            name = TIERS[g][meaning][min(q, 4) - 2][0]
        b.say(f"{st.god['name']}: {name}" + (f" {ROMAN[min(q, 4)]}" if q > 1 else "") +
              (f" ×{reps}" if reps > 1 else ""), tuple(st.god["color"]))
        if q > 1:                                           # ступень: подпись, свой эффект бога, тряска
            qq = min(q, 4)
            b.fx("tier", unit=st, name=f"{MEANING_NAME[meaning]} {ROMAN[qq]} — {name}", q=qq)
            sid = TIER_FX[g][qq - 2]
            unit = tgt if hasattr(tgt, "cell") else None
            ctr = tgt if isinstance(tgt, tuple) else (unit.cell if unit is not None else st.cell)
            yield from self.look(st, sid, name, target=unit if qq < 4 else None, center=ctr,
                                 radius={2: 0, 3: 1, 4: 2}[qq])
        fx = CAST_FX.get((g, meaning))
        if fx:                                              # смысл без своего эффекта в методе — эффект здесь
            sid, where = fx
            who = b.hero if where == "hero" else tgt if hasattr(tgt, "cell") else None
            ctr = tgt if isinstance(tgt, tuple) else st.cell if where in ("statue", "area") else None
            yield from self.look(st, sid, name, target=who, center=ctr, radius=1 if where == "area" else 0)
        for _ in range(reps):
            if b.result:
                break
            yield from getattr(self, f"{g}_{meaning}")(st, tgt)
        if mods and not b.result:
            yield from self.apply_mods(st, mods, tgt)
        if boost_used:
            self.temper -= 1
        if double_used:
            self.double = False
        self.boost, self.mult, self.plus = 0, 1, 0
        st.fed = True
        self.gain(st)
        self.killed = len(b.foes()) < before

    def apply_mods(self, st, mods, tgt):
        """Ветка-переделка: что ещё делает смысл — цели, врагам рядом со статуей, Жрецу."""
        b = self.b
        unit = tgt if hasattr(tgt, "cell") else next((f for f in b.foes() if f.cell == tgt), None) \
            if isinstance(tgt, tuple) else None
        if unit is not None and unit.alive and getattr(unit, "team", None) == ENEMY:
            for op in mods.get("after", []):
                yield from self.op_on(st, unit, op)
        if mods.get("chain") and unit is not None:
            r, ops = mods["chain"]
            for f in [f for f in b.foes() if f is not unit and cheb(f.cell, unit.cell) <= r]:
                for op in ops:
                    yield from self.op_on(st, f, op)
        if mods.get("near"):
            r, ops = mods["near"]
            for f in [f for f in b.foes() if cheb(f.cell, st.cell) <= r]:
                for op in ops:
                    yield from self.op_on(st, f, op)
        for f in list(b.foes()) if mods.get("all") else []:
            for op in mods["all"]:
                yield from self.op_on(st, f, op)
        h = b.hero
        for k, n in mods.get("hero", []):
            if k == "shield":
                self.shield(n)
            elif k == "heal":
                h.hp = min(h.max_hp, h.hp + n)
                b.c.emit("heal", unit=h, amount=n)
            elif k == "walk":
                b.walk_left += n
            elif k == "draw":
                b.draw(n)
        yield WAIT

    def op_on(self, st, f, op):
        b = self.b
        k = op[0]
        n = op[1] if len(op) > 1 else 0
        if not f.alive:
            return
        if k == "damage":
            yield from self.hit(st, f, n)
            return
        if k == "wet":
            b.wet(f)
        elif k == "poison":
            b.add_poison(f, n)
        elif k == "frost":
            b.add_frost(f, n)
        elif k == "burn":
            b.add_burn(f, n)
        elif k in ("weak", "vulnerable"):
            f.ds[k] += n
            b.fx("status", unit=f, el=k)
        elif k == "stun":
            f.ds["stun"] = True
        elif k == "root":
            f.ds["root"] = max(f.ds["root"], n)
        elif k == "thunder":
            f.ds["thunder"] = 2
        b._icons(f)

    def hit(self, st, tgt, n, vfx=None, el=None, name=""):
        """Удар статуи (генератор): эффект от статуи к цели, затем урон — Громовой знак, мокрый + молния,
        уязвимость и метка."""
        b = self.b
        if tgt is None or not tgt.alive:
            return
        if vfx and b.vfx(st, vfx, name or st.god["name"], target=tgt):
            yield IMPACT
        if not tgt.alive:
            return
        if tgt.ds.get("thunder"):
            n += 3
        if el == "lightning" and tgt.ds["wet"]:
            n *= 2
            b.fx("react", unit=tgt, what="shock")
            b.say("Мокрый + молния: урон ×2", (255, 240, 140))
        if tgt.ds["vulnerable"]:
            n = int(n * 1.5)
        if tgt.ds["mark"]:
            n += tgt.ds["mark"]
            tgt.ds["mark"] = 0
        b.hurt(tgt, n, b.hero, "spell")
        b._icons(tgt)
        yield WAIT

    def shield(self, n):
        self.b.gain_shield(self.b.hero, n)

    def look(self, st, sid, name, target=None, center=None, radius=0):
        if sid and self.b.vfx(st, sid, name, target=target, center=center, radius=radius):
            yield IMPACT

    def summon(self, kind, cell, name, hp, turns, dmg=0, color=(200, 220, 255), sprite=None):
        """Союзник на клетке: свой ход в конце хода Жреца (врагов не притягивает, они его обходят)."""
        b = self.b
        if cell is None or not b.free(cell):
            return None
        pid = sprite or SUMMON_SPRITE.get(kind, "druid_wolf")
        proto = {"name": name, "label": name[:2], "color": color, "role": "summon", "hp": hp, "move_time": 0.5,
                 "attack": {"damage": dmg, "range": 1, "cooldown": 1.0}}
        u = b.c._spawn(PLAYER, pid, proto, cell)
        b._setup(u, {"name": name, "hp": hp})
        u.summon = True
        u.kind = kind
        u.turns = turns
        u.dmg = dmg
        u.speed = 3
        self.summons.append(u)
        b.fx("portal", cell=cell)
        b.c.emit("summon", unit=u, owner=b.hero)
        return u

    def free_near(self, cell):
        b = self.b
        spots = [p for p in b.c.grid.in_radius(cell, 1) if b.free(p)]
        return min(spots, key=lambda p: cheb(p, b.hero.cell)) if spots else None

    def nearest_foe(self, cell, r=99):
        fs = [f for f in self.b.foes() if cheb(f.cell, cell) <= r]
        return min(fs, key=lambda f: (cheb(f.cell, cell), f.hp)) if fs else None

    # ---------- Перун: с неба в 3 ----------

    def perun_attack(self, st, tgt):
        b = self.b
        yield from self.hit(st, tgt, self.n(st, 6), "chain_lightning", "lightning", "Молния")
        if tgt.alive or True:                               # перескок по мокрым — от цели к соседу
            nxt = next((f for f in b.foes() if f is not tgt and f.ds["wet"] and cheb(f.cell, tgt.cell) <= 1), None)
            if nxt is not None:
                yield from self.hit(st, nxt, self.n(st, 4), "chain_lightning", "lightning", "Цепь")

    def perun_defense(self, st, tgt):
        self.shield(self.n(st, 3))
        st.rod = True
        self.b.say("Священный дуб: статуя — громоотвод до хода Жреца", (190, 220, 255))
        yield WAIT

    def perun_move(self, st, cell):
        b = self.b
        yield from self.look(st, "thunderstorm", "Гром", center=cell, radius=1)
        anchor = _Point(cell)
        for f in [f for f in b.foes() if cheb(f.cell, cell) <= 1 and f.cell != cell]:
            yield from b.push(anchor, f, 1)
        f0 = next((f for f in b.foes() if f.cell == cell), None)
        if f0 is not None:
            yield from self.hit(st, f0, self.n(st, 2), None, "lightning")

    def perun_curse(self, st, tgt):
        tgt.ds["thunder"] = 2
        self.b.fx("status", unit=tgt, el="rally")
        self.b.say(f"Громовой знак на {tgt.name}: удары статуй +3 молнией (2 хода)", (190, 220, 255))
        yield WAIT

    def perun_gift(self, st, tgt):
        b = self.b
        for f in b.foes():
            b.wet(f)
            b._icons(f)
        b.fx("roar", unit=st, r=6)
        b.say("Дождь: все враги мокнут", (150, 200, 255))
        yield WAIT

    def perun_summon(self, st, cell):
        self.clouds.append([cell, 3])
        self.b.say("Грозовая туча нависла (3 хода)", (190, 210, 255))
        yield WAIT

    def perun_intent(self, st):
        t = self.nearest_foe(st.cell, 3)
        if t is not None:
            yield from self.hit(st, t, 4 + self.ib(st), "chain_lightning", "lightning", "Молния")
        else:
            yield from self.look(st, "e_rain", "Гроза", center=st.cell, radius=2)
            for f in [f for f in self.b.foes() if cheb(f.cell, st.cell) <= 4]:
                self.b.wet(f)
            yield WAIT

    # ---------- Сварог: рядом ----------

    def svarog_attack(self, st, tgt):
        yield from self.hit(st, tgt, self.n(st, 7), "e_hammer", None, "Молот")

    def svarog_defense(self, st, tgt):
        near = cheb(self.b.hero.cell, st.cell) <= 2
        self.shield(self.n(st, 6 if near else 3))
        yield WAIT

    def svarog_move(self, st, tgt):
        b = self.b
        yield from self.look(st, "e_hammer", "Отдача", center=st.cell, radius=1)
        for f in [f for f in b.foes() if cheb(f.cell, st.cell) <= 1]:
            yield from b.push(st, f, 1 + (1 if self.mult > 1 else 0))

    def svarog_curse(self, st, tgt):
        yield from self.look(st, "e_hammer", "Звон", target=tgt)
        tgt.ds["stun"] = True
        self.b._icons(tgt)
        self.b.say(f"{tgt.name} оглушён звоном наковальни", (255, 230, 140))

    def svarog_gift(self, st, tgt):
        self.temper += 2
        self.b.say("Закалка: следующие 2 свитка +2", (255, 190, 120))
        yield WAIT

    def svarog_summon(self, st, cell):
        self.summon("imp", cell, "Сварожич", 8, 3, dmg=2, color=(255, 140, 60))
        yield WAIT

    def svarog_intent(self, st):
        b = self.b
        t = self.nearest_foe(st.cell, 1)
        if cheb(b.hero.cell, st.cell) <= 2 or t is None:
            yield from self.look(st, "shield_wall", "Щит", target=b.hero)
            self.shield(3 + self.ib(st))
            yield WAIT
        else:
            yield from self.hit(st, t, 4 + self.ib(st), "e_hammer", None, "Молот")

    # ---------- Стрибог: линии ----------

    def _line_units(self, st, cell):
        d, cells = self.on_line(st, cell)
        units = [f for p in cells for f in self.b.foes() if f.cell == p]
        return d, units

    def stribog_attack(self, st, cell):
        d, units = self._line_units(st, cell)
        yield from self.look(st, "whirlwind", "Стрела ветра", center=cell)
        for f in units:
            yield from self.hit(st, f, self.n(st, 4), "sonic_blast", None, "Стрела ветра")

    def stribog_defense(self, st, tgt):
        self.shield(self.n(st, 2))
        self.b.hero.ds["windward"] = 1
        self.b.say("Встречный ветер: выстрелы по Жрецу вдвое слабее", (190, 230, 240))
        yield WAIT

    def stribog_move(self, st, cell):
        b = self.b
        d, units = self._line_units(st, cell)
        yield from self.look(st, "repulse", "Порыв", center=cell)
        for f in sorted(units, key=lambda f: -cheb(f.cell, st.cell)):      # дальние первыми — не мешают ближним
            yield from b.push(st, f, self.n(st, 2))

    def stribog_curse(self, st, cell):
        d, units = self._line_units(st, cell)
        if units:
            f = min(units, key=lambda f: cheb(f.cell, st.cell))
            yield from self.look(st, "whirlwind", "Вихрь", target=f)
            f.ds["stun"] = True
            self.b._icons(f)
            self.b.say(f"{f.name}: сбит вихрем — пропустит намерение", (255, 230, 140))
        yield WAIT

    def stribog_gift(self, st, tgt):
        self.b.walk_left += self.n(st, 2)
        self.b.say("Попутный ветер: +2 шага", (190, 230, 240))
        yield WAIT

    def stribog_summon(self, st, cell):
        d, cells = self.on_line(st, cell)
        spot = next((p for p in cells if self.b.free(p)), None)
        self.summon("whirl", spot, "Смерч", 6, 3, dmg=2, color=(190, 230, 240))
        yield WAIT

    def stribog_intent(self, st):
        b = self.b
        cand = [f for f in b.foes() if f.cell in set(self.line_cells(st))]
        if cand:
            f = min(cand, key=lambda f: cheb(f.cell, b.hero.cell))
            yield from self.look(st, "whirlwind", "Порыв", target=f)
            yield from b.push(st, f, 2 + self.ib(st) // 2)
        else:
            yield WAIT

    # ---------- Ярило: свет 2 ----------

    def _lit(self, st):
        return [f for f in self.b.foes() if cheb(f.cell, st.cell) <= 2]

    def yarilo_attack(self, st, tgt):
        for f in self._lit(st):
            yield from self.hit(st, f, self.n(st, 3), "judgment", None, "Луч")

    def yarilo_defense(self, st, tgt):
        b = self.b
        h = b.hero
        amt = self.n(st, 4 if cheb(h.cell, st.cell) <= 2 else 2)
        yield from self.look(st, "blessing", "Тепло", target=h)
        h.hp = min(h.max_hp, h.hp + amt)
        b.c.emit("heal", unit=h, amount=amt)

    def yarilo_move(self, st, tgt):
        b = self.b
        spot = self.free_near(st.cell)
        if spot is not None and spot != b.hero.cell:
            b.fx("portal", cell=spot)
            b.c._place(b.hero, spot, 0.3)
            yield ("wait", 0.0)
        yield WAIT

    def yarilo_curse(self, st, tgt):
        yield from self.look(st, "consecrate", "Ослепление", center=st.cell, radius=2)
        for f in self._lit(st):
            f.ds["weak"] += self.n(st, 2)
            self.b._icons(f)

    def yarilo_gift(self, st, tgt):
        st.grow = max(1, st.grow + 1)
        self.b.say("Рост: числа Ярило растут каждый ход", (255, 220, 120))
        yield WAIT

    def yarilo_summon(self, st, cell):
        self.summon("sprout", cell, "Росток", 10, 4, color=(160, 230, 120))
        yield WAIT

    def yarilo_intent(self, st):
        b = self.b
        h = b.hero
        if cheb(h.cell, st.cell) <= 2 and h.hp < h.max_hp:
            amt = 2 + st.grow + self.ib(st)
            yield from self.look(st, "blessing", "Тепло", target=h)
            h.hp = min(h.max_hp, h.hp + amt)
            b.c.emit("heal", unit=h, amount=amt)
            yield WAIT
        else:
            for f in self._lit(st):
                yield from self.hit(st, f, 2 + st.grow + self.ib(st), "judgment", None, "Луч")
            yield WAIT

    # ---------- Велес: 2, по воде и топи — дальше ----------

    def veles_attack(self, st, tgt):
        n = self.n(st, 2 + 2 * tgt.ds["poison"])
        yield from self.hit(st, tgt, n, "e_wither", None, "Удушье")

    def veles_defense(self, st, tgt):
        self.b.hero.ds["navfog"] = 1
        self.b.say("Туман Нави: враги дальше 1 клетки не видят Жреца", (170, 210, 170))
        yield from self.look(st, "vanish", "Туман Нави", target=self.b.hero)

    def veles_move(self, st, cell):
        b = self.b
        self.mud.add(tuple(cell))
        yield from self.look(st, "mud_splash", "Трясина", center=cell)
        for f in [f for f in b.foes() if f.cell == cell]:
            f.ds["root"] = max(f.ds["root"], 1)
            b.wet(f)
            b._icons(f)
        b.say("Трясина: клетка стала топью", (170, 200, 140))

    def veles_curse(self, st, tgt):
        yield from self.look(st, "e_plague", "Порча", target=tgt)
        self.b.add_poison(tgt, self.n(st, 3))
        tgt.ds["rot"] = True
        self.b._icons(tgt)

    def veles_gift(self, st, tgt):
        self.b.draw(1 + (1 if self.mult > 1 else 0))
        self.extra_draw += 1
        self.b.say("Богатство: +1 свиток и +1 к следующему добору", (200, 230, 150))
        yield WAIT

    def veles_summon(self, st, cell):
        self.summon("wolf", cell, "Волк Велеса", 10, 4, dmg=3, color=(150, 190, 110))
        yield WAIT

    def veles_intent(self, st):
        b = self.b
        if b.turn % 3 == 0:
            yield from self.look(st, "hunter_beast", "Уж", center=st.cell)
            self.summon("wolf", self.free_near(st.cell), "Уж", 4, 2, dmg=2, color=(130, 170, 90))
            yield WAIT
            return
        t = self.nearest_foe(st.cell, 2)
        if t is not None:
            yield from self.look(st, "e_plague", "Яд", target=t)
            b.add_poison(t, 2 + self.ib(st))
            b._icons(t)
        yield WAIT

    # ---------- Мокошь: 3 клетки, нити ----------

    def bind(self, a, c, turns=2):
        if a is None or c is None or a is c:
            return
        a.ds["bound"], c.ds["bound"] = turns, turns
        a.bound_to, c.bound_to = c, a
        self.b.say(f"Нить судьбы связала: {a.name} и {c.name}", (210, 180, 240))

    def mokosh_attack(self, st, tgt):
        b = self.b
        other = min((f for f in b.foes() if f is not tgt), key=lambda f: cheb(f.cell, tgt.cell), default=None)
        self.bind(tgt, other)
        yield from self.hit(st, tgt, self.n(st, 3), "tether", None, "Нить")
        if other is not None and other.alive:
            yield from self.hit(st, other, self.n(st, 3))

    def mokosh_defense(self, st, tgt):
        self.shield(self.n(st, 3))
        self.b.hero.ds["weave"] = 1
        self.b.say("Вплести: следующий удар по Жрецу уйдёт связанному врагу", (210, 180, 240))
        yield WAIT

    def mokosh_move(self, st, tgt):
        yield from self.look(st, "e_drag", "Подтянуть", target=tgt)
        yield from self.b.push(st, tgt, self.n(st, 3), toward=True)

    def mokosh_curse(self, st, tgt):
        it = tgt.intent or {}
        if "dmg" in it:
            it["dmg"] = max(0, it["dmg"] // 2)
            self.b.say(f"Узел судьбы: {tgt.name} — намерение вдвое слабее", (210, 180, 240))
        else:
            tgt.ds["weak"] += 2
            self.b.say(f"Узел судьбы: {tgt.name} ослаблен", (210, 180, 240))
        self.b._icons(tgt)
        yield from self.look(st, "curse", "Узел судьбы", target=tgt)

    def mokosh_gift(self, st, tgt):
        st.repeat += 1
        self.b.say("Прялка: следующий свиток Мокоши — дважды", (210, 180, 240))
        yield WAIT

    def mokosh_summon(self, st, tgt):
        tgt.ds["root"] = max(tgt.ds["root"], self.n(st, 2))
        self.b._icons(tgt)
        self.b.say(f"Веретено: {tgt.name} опутан нитями", (210, 180, 240))
        yield from self.look(st, "net", "Веретено", target=tgt)

    def mokosh_intent(self, st):
        fs = sorted((f for f in self.b.foes() if cheb(f.cell, st.cell) <= 3), key=lambda f: cheb(f.cell, st.cell))
        if len(fs) >= 2:
            yield from self.look(st, "spirit_link", "Нить судьбы", target=fs[0])
            self.bind(fs[0], fs[1])
        yield WAIT

    # ---------- Морана: 2 клетки, холод ----------

    def morana_attack(self, st, tgt):
        n = self.n(st, 5)
        if tgt.hp * 2 < tgt.max_hp:
            n *= 2
        yield from self.hit(st, tgt, n, "ice_bolt", None, "Серп")

    def morana_defense(self, st, tgt):
        self.shield(self.n(st, 8))
        self.b.hero.ds["iced"] = 1
        self.b.say("Ледяная корка: следующий ход Жрец не ходит", (180, 220, 255))
        yield WAIT

    def morana_move(self, st, tgt):
        yield from self.look(st, "ice_bolt", "Скольжение", target=tgt)
        yield from self.b.push(st, tgt, 8)

    def morana_curse(self, st, tgt):
        yield from self.look(st, "frost_needle", "Стужа", target=tgt)
        self.b.add_frost(tgt, self.n(st, 4))
        self.b._icons(tgt)

    def morana_gift(self, st, tgt):
        self.dead_water = True
        self.b.say("Мёртвая вода: свиток, что добьёт, вернётся в руку", (180, 220, 255))
        yield WAIT

    def morana_summon(self, st, cell):
        self.summon("mara", cell, "Мара", 6, 3, color=(190, 220, 255))
        yield WAIT

    def morana_intent(self, st):
        b = self.b
        yield from self.look(st, "e_frost_breath", "Мороз", center=st.cell, radius=1)
        for u in [u for u in b.c.units if u.alive and not u.obj and not getattr(u, "summon", False)
                  and cheb(u.cell, st.cell) <= 1]:
            b.add_frost(u, 2 + self.ib(st))
            b._icons(u)
        yield WAIT

    # ---------- Чернобог: всё поле, за кровь ----------

    def chernobog_attack(self, st, tgt):
        yield from self.hit(st, tgt, self.n(st, 9), "soul_lance", None, "Тёмный удар")
        self.b.hurt(self.b.hero, 2, None, "hp_cost")

    def chernobog_defense(self, st, tgt):
        b = self.b
        self.shield(self.n(st, 8))
        b.discard.append(M.Card("slime_rot", b.run.defs))
        b.fx("curse", unit=st, n=1)
        b.say("Чёрная сделка: +8 защиты, «Тина» в сброс", (180, 150, 200))
        yield WAIT

    def chernobog_move(self, st, cell):
        b = self.b
        b.fx("portal", cell=cell)
        b.c._place(b.hero, cell, 0.25)
        yield ("wait", 0.0)
        yield WAIT

    def chernobog_curse(self, st, tgt):
        yield from self.look(st, "curse", "Злая доля", target=tgt)
        tgt.ds["weak"] += self.n(st, 2)
        tgt.ds["vulnerable"] += self.n(st, 2)
        self.b._icons(tgt)
        self.b.hurt(self.b.hero, 1, None, "hp_cost")

    def chernobog_gift(self, st, tgt):
        b = self.b
        pool = [c for c in b.hand if c.d.get("meaning")]
        if pool:
            c = b.rng.choice(pool)
            b.hand.remove(c)
            b.exhaust.append(c)
            b.say(f"Жертва: «{c.name}» сгорает — следующий свиток ×2", (200, 150, 220))
        self.double = True
        yield WAIT

    def chernobog_summon(self, st, tgt):
        b = self.b
        spot = self.free_near(tgt.cell) or self.free_near(st.cell)
        u = self.summon("shade", spot, f"Тень: {tgt.name}", max(4, tgt.max_hp // 2), 2, dmg=4,
                        color=(120, 90, 140), sprite=tgt.proto_id)
        if u is not None:
            b.hurt(b.hero, 4, None, "hp_cost")
        yield WAIT

    def chernobog_intent(self, st):
        b = self.b
        if not st.fed and not self.aura_sum(st, "nohunger") and not any(a[2] == "nohunger" for a in self.auras(st)):
            b.say("Чернобог голоден: −2 HP Жрецу", (200, 120, 160))
            yield from self.look(st, "curse", "Голод", target=b.hero)
            b.hurt(b.hero, 2, None, "hp_cost")
            yield WAIT
        else:
            t = self.nearest_foe(st.cell)
            if t is not None:
                yield from self.hit(st, t, 5 + self.ib(st), "soul_lance", None, "Тёмный удар")
            yield WAIT

    # ---------- намерения ----------

    INTENT = {"perun": ("attack", "Молния", 4), "svarog": ("defense", "Щит или молот", 3),
              "stribog": ("move", "Порыв", 2), "yarilo": ("defense", "Тепло или луч", 2),
              "veles": ("curse", "Яд", 2), "mokosh": ("curse", "Связать двоих", 0),
              "morana": ("curse", "Мороз рядом", 2), "chernobog": ("attack", "Голод", 5)}

    def intent_of(self, st):
        """Намерение статуи на этот ход — для медальона: (смысл, название, число)."""
        g = st.statue
        m, name, n = self._intent(st)
        L = self.ib(st)
        if self.silenced(st):
            return (m, "Осквернена: молчит этот ход", 0)
        if not st.fed and g != "chernobog":
            return (m, f"Ответит на свиток: {name}", 0)
        hungry = g == "chernobog" and not st.fed and not any(a[2] == "nohunger" for a in self.auras(st))
        if n and g != "stribog" and not hungry:                              # голод Чернобога — всегда 2
            n += L
        elif g == "stribog":
            n += L // 2
        return (m, name, n)

    def _intent(self, st):
        g = st.statue
        m, name, n = self.INTENT[g]
        b = self.b
        if g == "perun" and self.nearest_foe(st.cell, 3) is None:
            return ("curse", "Гроза: мочит рядом", 0)
        if g == "svarog":
            if cheb(b.hero.cell, st.cell) <= 2 or self.nearest_foe(st.cell, 1) is None:
                return ("defense", "Щит Жрецу", 3)
            return ("attack", "Молот", 4)
        if g == "yarilo":
            h = b.hero
            if cheb(h.cell, st.cell) <= 2 and h.hp < h.max_hp:
                return ("defense", "Тепло", 2 + st.grow)
            return ("attack", "Луч", 2 + st.grow)
        if g == "veles" and b.turn % 3 == 0:
            return ("summon", "Уж", 0)
        if g == "chernobog":
            fed = st.fed or any(a[2] == "nohunger" for a in self.auras(st))
            return ("attack", "Голод: сыт — бьёт врага, голоден — Жреца", 5 if fed else 2)
        return (m, name, n)

    def start_turn(self):
        b = self.b
        h = b.hero
        for k in ("navfog", "windward", "weave"):
            h.ds[k] = 0
        self.walk_bonus = 0
        for st in self.statues:
            st.rod = False
            st.fed = False
            for name, _d, kind, n, r in self.auras(st):              # ауры начала хода
                if kind == "shield_hero" and cheb(h.cell, st.cell) <= r:
                    self.shield(n)
                elif kind == "walk":
                    self.walk_bonus += n
                elif kind == "draw":
                    self.extra_draw += n
            if st.grow:
                st.grow += 1
        b._icons(h)

    def end_of_turn(self):
        """Конец хода Жреца: статуи играют свои свитки, тучи бьют, призванные действуют, таймеры тикают."""
        b = self.b
        for st in self.statues:                                 # статуи отвечают на молитву: свиток в этот ход
            if b.result:
                return
            if self.silenced(st):
                b.say(f"{st.god['name']} молчит: статуя осквернена", (190, 160, 160))
                continue
            if not st.fed and st.statue != "chernobog":         # Чернобог голоден и без свитка — бьёт Жреца
                continue
            yield from getattr(self, f"{st.statue}_intent")(st)
        for st in self.statues:                                 # ауры конца хода
            for name, _d, kind, n, r in self.auras(st):
                if b.result:
                    return
                near = [f for f in b.foes() if cheb(f.cell, st.cell) <= r]
                if kind == "heal_hero" and cheb(b.hero.cell, st.cell) <= r and b.hero.hp < b.hero.max_hp:
                    b.hero.hp = min(b.hero.max_hp, b.hero.hp + n)
                    b.c.emit("heal", unit=b.hero, amount=n)
                    continue
                op = {"wet_near": ("wet",), "poison_near": ("poison", n), "frost_near": ("frost", n),
                      "burn_near": ("burn", n), "weak_near": ("weak", n), "vuln_near": ("vulnerable", n),
                      "root_near": ("root", n), "dmg_near": ("damage", n)}.get(kind)
                if op and near:
                    b.say(f"{st.god['name']}: {name}", tuple(st.god["color"]))
                    for f in near:
                        yield from self.op_on(st, f, op)
        for st in self.statues:                                 # осквернение — на один ход
            st.silence = max(0, getattr(st, "silence", 0) - 1)
        for c in list(self.clouds):                             # Грозовая туча
            if b.result:
                return
            cell = c[0]
            for f in [f for f in b.foes() if cheb(f.cell, cell) <= 0]:
                b.wet(f)
                st = next((s for s in self.statues if s.statue == "perun"), None) or b.hero
                yield from self.hit(st, f, 3, "chain_lightning", "lightning", "Туча")
            c[1] -= 1
            if c[1] <= 0:
                self.clouds.remove(c)
        for u in list(self.summons):
            if b.result:
                return
            if u.alive:
                yield from self.summon_act(u)
            u.turns -= 1
            if u.turns <= 0 and u.alive:
                u.alive = False
                u.hp = 0
                b.c.emit("death", unit=u, expire=True, rises=False)
                b.say(f"{u.name} уходит", (180, 180, 200))
            if not u.alive:
                self.summons.remove(u)
        for f in b.foes():                                      # таймеры знаков и нитей
            for k in ("thunder", "bound"):
                if f.ds.get(k):
                    f.ds[k] -= 1
            b._icons(f)

    def summon_act(self, u):
        """Ход призванного: волк, уж и тень — к ближайшему врагу и укус; дух и мара — по соседям; смерч толкает;
        росток лечит Жреца рядом."""
        b = self.b
        k = u.kind
        if k == "sprout":
            if cheb(u.cell, b.hero.cell) <= 1 and b.hero.hp < b.hero.max_hp:
                b.hero.hp += 1
                b.c.emit("heal", unit=b.hero, amount=1)
            yield WAIT
            return
        if k in ("imp", "mara"):
            for f in [f for f in b.foes() if cheb(f.cell, u.cell) <= 1]:
                if k == "imp":
                    b.add_burn(f, 2)
                else:
                    b.add_frost(f, 2)
                b._icons(f)
            yield WAIT
            return
        t = self.nearest_foe(u.cell)
        if t is None:
            yield WAIT
            return
        if cheb(u.cell, t.cell) > 1:
            reach = b.paths(u, 2 if k == "whirl" else u.speed)
            near = [p for p in reach if cheb(p, t.cell) <= 1]
            dest = min(near, key=lambda p: len(reach[p])) if near else min(reach, key=lambda p: cheb(p, t.cell))
            yield from b.walk(u, reach[dest])
        if u.alive and t.alive and cheb(u.cell, t.cell) <= 1:
            if not b.vfx(u, "e_claw", u.name, target=t):           # укус — когти
                b.c.emit("attack", src=u, dst=t, kind="melee", tag=None)
            yield IMPACT
            if t.alive:
                b.hurt(t, u.dmg, b.hero, "melee")
                if k == "whirl" and t.alive:
                    yield from b.push(u, t, 1)
        yield WAIT

    # ---------- подсказки ----------

    def describe(self, st):
        """Подсказка статуи без свитка: бог, уровень, досягаемость, намерение, взятые ветки. [(текст, заголовок?)]"""
        g = st.statue
        god = st.god
        m, name, n = self.intent_of(st)
        lv = self.level(st)
        nx = self.next_level(st)
        lines = [(f"{god['name']} — {god.get('title', '')}", True),
                 (f"Уровень {lv}" + (f" (числа +{lv})" if lv else "") +
                  (f" · до следующего — {nx[0]} свитк." if nx else " · наивысший"), False),
                 (f"Досягаемость: {REACH_TEXT.get(g, '')}" +
                  (f" +{self.aura_sum(st, 'reach')}" if self.aura_sum(st, "reach") else ""), False),
                 (f"Намерение: {name}" + (f" {n}" if n else ""), False)]
        for k, v in self.picks(st):
            if k == "a":
                a_ = BRANCHES[g]["a"][v]
                lines.append((f"Аура — {a_[0]}: {a_[1]}", False))
        lines.append(("Тяните свиток на статую — увидите, что сделает бог.", False))
        return lines

    def fill(self, st, meaning, plus=0, q=1):
        """Описание действия с посчитанными числами: {k} → k + уровень + ступень + Закалка (+ Рост), × Жертва."""
        mods = self.tier_mods(st.statue, meaning, q)
        bonus = self.level(st) + plus + mods.get("plus", 0) + (st.grow if st.statue == "yarilo" else 0) + \
            (2 if self.temper > 0 and meaning != "gift" else 0)
        mult = 2 if self.double and meaning != "gift" else 1
        desc = SPEC[st.statue][meaning][2]
        return re.sub(r"\{(\d+)\}", lambda m_: str((int(m_.group(1)) + bonus) * mult), desc)

    def act_line(self, s_, mm, q=1, n=1, first=False):
        """Одна строка: «Атака II — Цепная молния: 9 урона…; ступень: …» с числом раз."""
        g = s_.statue
        mods = self.tier_mods(g, mm, q)
        times = n + (1 if mods.get("twice") else 0) + mods.get("times", 0) + (s_.repeat if first else 0)
        nm = TIERS[g][mm][min(q, 4) - 2][0] if q > 1 else SPEC[g][mm][1]
        txt = self.fill(s_, mm, 0, q)
        out = f"{MEANING_NAME[mm]} {ROMAN[min(q, 4)]} — {nm}: {txt}"
        if q > 1:                                        # прибавки уже в числах — в тексте только новое
            extra = re.sub(r"(^|[,;] ?)\+\d+( к щиту)?", "", TIERS[g][mm][min(q, 4) - 2][1]).strip(" ,;")
            if extra:
                out += f"; {extra}"
        if times > 1:
            out += f" — ×{times}"
        return out

    def cast_lines(self, st, card):
        """Что сделает свиток через эту статую — только это: [(текст, заголовок?)]."""
        d = card.d
        acts = self.acts(card)
        lines = [(f"{st.god['name']} · {card.name}", True)]
        if self.silenced(st) and acts[0]["m"] != "move":
            lines.append(("Осквернена врагом: в этот ход бог слышит только Движение", False))
            return lines
        if not self.can_cast(st, acts[0]["m"]):
            lines.append(("Некуда: нет цели в досягаемости статуи", False))
            return lines
        for i, act in enumerate(acts):
            m = act["m"]
            if i and self.target_for(st, m, None) is SKIP:
                lines.append((f"{MEANING_NAME[m]} — некуда", False))
                continue
            lines.append((self.act_line(st, m, act.get("q", 1), act.get("n", 1), first=i == 0), False))
        if d.get("chorus"):
            m, q = acts[0]["m"], acts[0].get("q", 1)
            for o in [x for x in self.statues if x is not st]:
                if self.auto(o, m) is SKIP:
                    lines.append((f"Хор — {o.god['name']}: некуда", False))
                else:
                    lines.append((f"Хор — {o.god['name']}: {self.act_line(o, m, q)}", False))
        for step in d.get("then", []):
            m2 = step["m"]
            who = st if step.get("who", "same") == "same" else self.other(st, m2)
            if who is None:
                lines.append((f"Затем {MEANING_NAME[m2]} — другой статуе некуда", False))
            else:
                lines.append((f"Затем {who.god['name']}: {self.act_line(who, m2, step.get('q', 1))}", False))
        if d.get("walk"):
            lines.append((f"Жрецу +{d['walk']} шага", False))
        if d.get("draw"):
            lines.append((f"+{d['draw']} свиток в руку", False))
        return lines


class _Point:
    """Точка поля как «источник» толчка (Гром Перуна: от места удара)."""

    def __init__(self, cell):
        self.cell = tuple(cell)
        self.alive = True
        self.obj = None


# ---------- свитки-награды: чем глубже, тем «толще» (квиз 2026-11-21) ----------

SHORT = {"attack": "Атака", "defense": "Защита", "move": "Путь", "curse": "Проклятие", "gift": "Дар",
         "summon": "Призыв"}
FRAME = {"attack": "attack", "defense": "skill", "move": "skill", "curse": "power", "gift": "power",
         "summon": "power"}
ILL = {"attack": ["priest_wisps", "final_vigil", "cult_initiation"], "defense": ["amber_altar", "sunken_chapel"],
       "move": ["fog_voices", "smoke_signal", "tribute_cart"], "curse": ["hag_riddle", "plague_village", "witch_envoy"],
       "gift": ["sunken_chapel.altar", "wisp_hoard", "village_feast"], "summon": ["idol", "golem_awakening"]}
RARE = ["sc_attack_chorus", "sc_curse_chorus", "sc_defense_relay", "sc_move_relay", "sc_curse_relay",
        "sc_gift_relay", "sc_summon_relay", "sc_defense_double", "sc_gift_double"]


def scroll_text(acts):
    """Текст свитка: «*Атака* II, затем *Проклятие*»; число раз — ×N."""
    parts = []
    for a in acts:
        q = a.get("q", 1)
        parts.append(f"*{MEANING_NAME[a['m']]}*" + (f" {ROMAN[min(q, 4)]}" if q > 1 else "") +
                     (f" ×{a['n']}" if a.get("n", 1) > 1 else ""))
    return ", затем ".join(parts) + "."


def make_scroll(run, acts):
    """Новый свиток с этими действиями — в словарь карт забега; возвращает id."""
    i = 1
    while f"sc_g{i}" in run.defs:
        i += 1
    cid = f"sc_g{i}"
    m0 = acts[0]["m"]
    name = " · ".join(SHORT[a["m"]] + (f" {ROMAN[min(a.get('q', 1), 4)]}" if a.get("q", 1) > 1 else "") for a in acts)
    ill = ILL[m0][i % len(ILL[m0])]
    run.defs[cid] = {"ill": [ill, 0.5, 0.5, 0.5], "art": run.defs["strike"].get("art", ""), "name": name, "cost": 0,
                     "type": FRAME[m0], "meaning": m0, "acts": acts,
                     "main": {"target": "statue", "say": scroll_text(acts)}, "alt": {"target": "none"}}
    return cid


def gen_acts(rng, depth):
    """Действия свитка под глубину: 1 этаж — 1–2 действия до II, 2 — 2–3 до III, 3+ — 3–4 до IV (IV — редко)."""
    lo, hi, qmax = {1: (1, 2, 2), 2: (2, 3, 3)}.get(depth, (3, 4, 4))
    n = rng.randint(lo, hi)
    ms = rng.sample(MEANINGS, n)
    out = []
    for k, m in enumerate(ms):
        q = 1
        roll = rng.random()
        if qmax >= 2 and roll < (0.55 if k == 0 else 0.3):
            q = 2
        if qmax >= 3 and roll < (0.25 if k == 0 else 0.1):
            q = 3
        if qmax >= 4 and roll < (0.08 if k == 0 else 0.02):
            q = 4
        out.append({"m": m, "q": q})
    return out


def offer_scrolls(run, n=3):
    """Награда Жреца: n−1 созданных под глубину свитков + 1 редкий (хор, перекличка, двойной)."""
    out = [make_scroll(run, gen_acts(run.rng, max(1, run.depth))) for _ in range(max(1, n - 1))]
    rare = [c for c in RARE if c in run.defs]
    if rare and n > 1:
        out.append(run.rng.choice(rare))
    run.rng.shuffle(out)
    return out[:n]
