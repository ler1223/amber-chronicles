"""Генератор контента героев: классы, навыки, ветки, пути, таланты, призывы, теги, реакции, клетки.

Однократно дописывает data/*.json (существующие записи с теми же id перезаписываются).
python tools/content_heroes.py
"""
import json
import os

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def auto(on=False, *conds):
    return {"on": on, "conds": [{"type": c[0], "value": c[1]} if len(c) > 1 else {"type": c[0]} for c in conds]}


def skill(name, desc, ap, target, effects, rng=0, cast=0.0, cd=0, radius=None, au=None, **kw):
    sk = {"name": name, "ap": ap, "cast": cast, "cooldown": cd, "range": rng, "target": target}
    if radius is not None:
        sk["radius"] = radius
    sk["auto"] = au or auto(False)
    sk["effects"] = effects
    sk["desc"] = desc
    sk.update(kw)
    return sk


def tier(name, desc, *mods):
    return {"name": name, "desc": desc, "mods": list(mods)}


def branch(name, t1, t2):
    return {"name": name, "tiers": [t1, t2]}


def form(name, desc, effects=None, **sets):
    """Мод первой ступени: новое имя, описание, (опционально) новый список эффектов и поля навыка."""
    m = {"set": dict(name=name, desc=desc, **sets)}
    if effects is not None:
        m["effects"] = effects
    return m


def desc(text, **sets):
    return {"set": dict(desc=text, **sets)}


def eff(type_, **kw):
    return {"effect": {"type": type_, **kw}}


def add(e):
    return {"add_effect": e}


def D(amount, kind="spell", radius=None, tag=None, **kw):
    e = {"type": "damage", "amount": amount, "kind": kind}
    if radius:
        e["radius"] = radius
    if tag:
        e["tag"] = tag
    e.update(kw)
    return e


def buff(stat, value, duration, radius=None, affects=None, **kw):
    e = {"type": "buff", "stat": stat, "value": value, "duration": duration}
    if radius:
        e["radius"] = radius
    if affects:
        e["affects"] = affects
    e.update(kw)
    return e


SKILLS, BRANCHES, CLASSES, PATHS, TALENTS = {}, {}, {}, {}, {}


def S(sid, sk, a, b):
    SKILLS[sid] = sk
    BRANCHES[sid] = {"A": a, "B": b}


# ======================= Ассасин =======================
CLASSES["assassin"] = {
    "name": "Ассасин", "label": "А", "color": [86, 84, 112], "role": "melee", "hp": 85, "armor": 1, "move_time": 0.35,
    "attack": {"damage": 13, "range": 1, "cooldown": 0.9}, "ap_max": 6, "ap_regen": 4.5, "pp_max": 2, "pp_regen": 3.5,
    "passive": {"kind": "backstab", "name": "Удар в спину", "pp": 1, "mult": 1.6,
                "desc": "Атака по цели, которая бьёт не ассасина или оглушена: −1 деление шкалы, урон ×1.6"},
    "skills": ["shadow_step", "venom_blade", "vanish"], "unlock": 60,
    "about": "Убийца одиночных целей: заходит за спину, уходит в тень, травит ядом. Хрупкий."}
S("shadow_step", skill("Шаг в тень", "Прыжок к врагу (до 4): 22 урона, ×1.5 в спину.", 3, "enemy",
                       [{"type": "leap_to"}, D(22, "melee", backstab=1.5)], rng=4, cd=4, au=auto(True)),
  branch("Танец клинков",
         tier("Танец клинков", "26 урона, перезарядка 3 сек, затем атаки быстрее.",
              form("Танец клинков", "Прыжок к врагу: 26 урона (×1.6 в спину), 4 сек атаки на 40% быстрее.",
                   [{"type": "leap_to"}, D(26, "melee", backstab=1.6), buff("atk_speed", 0.6, 4, at="caster")],
                   cooldown=3)),
         tier("Вихрь теней", "Ещё 12 урона врагам рядом с целью.",
              desc("Прыжок к врагу: 26 урона (×1.6 в спину), 12 урона врагам рядом, атаки быстрее 4 сек."),
              add(D(12, "melee", radius=1)))),
  branch("Убийца магов",
         tier("Перехват", "Оглушает цель на 1.5 сек — срывает каст.",
              form("Перехват", "Прыжок к врагу: 18 урона и оглушение 1.5 сек.",
                   [{"type": "leap_to"}, D(18, "melee", backstab=1.5), {"type": "stun", "duration": 1.5}],
                   auto=auto(True, ("target_casting",)))),
         tier("Немота", "Цель получает +30% урона 6 сек.",
              desc("Прыжок к врагу: 18 урона, оглушение 1.5 сек, цель получает +30% урона 6 сек."),
              add(buff("dmg_taken", 1.3, 6, affects="enemies")))))
S("venom_blade", skill("Ядовитый клинок", "8 сек атаки накладывают Яд.", 2, "self",
                       [buff("atk_tag", "poison", 8)], cd=10, au=auto(True, ("enemies_adjacent", 1))),
  branch("Смертельный яд",
         tier("Смертельный яд", "Атаки ещё и ×1.25.",
              desc("8 сек атаки накладывают Яд и бьют ×1.25."), add(buff("atk_mult", 1.25, 8))),
         tier("Некроз", "Действует 12 сек, перезарядка 8.",
              desc("12 сек атаки накладывают Яд и бьют ×1.25.", cooldown=8), eff("buff", set={"duration": 12}))),
  branch("Отравленный дротик",
         tier("Отравленный дротик", "Дротик на 4 клетки: 10 урона + Яд, замедление.",
              form("Отравленный дротик", "Дротик (дальность 4): 10 урона + Яд, замедление 4 сек.",
                   [D(10, "ranged", tag="poison", on_hit_buff={"stat": "slow", "value": 1.5, "duration": 4})],
                   target="enemy", range=4, cooldown=3, auto=auto(True))),
         tier("Ядовитые брызги", "Яд перескакивает ещё на 2 врагов.",
              desc("Дротик: 10 урона + Яд, замедление; яд перескакивает на 2 врагов рядом (8 урона)."),
              add({"type": "chain", "jumps": 2, "range": 2, "amount": 8, "tag": "poison", "kind": "ranged"}))))
S("vanish", skill("Исчезновение", "Уходит в тень на 5 сек: враги теряют цель, удар из тени ×1.8.", 3, "self",
                  [{"type": "stealth", "duration": 5, "mult": 1.8}], cd=12, au=auto(True, ("self_hp_below", 50))),
  branch("Засада",
         tier("Засада", "Удар из тени ×2.2, тень 6 сек.",
              desc("Тень на 6 сек: враги теряют цель, удар из тени ×2.2."),
              eff("stealth", set={"duration": 6, "mult": 2.2})),
         tier("Призрак", "В тени двигается на 40% быстрее.",
              desc("Тень на 6 сек, удар из тени ×2.2, движение на 40% быстрее."), add(buff("slow", 0.6, 6)))),
  branch("Отход",
         tier("Отход", "Прыжок на клетку до 3 и тень на 3 сек.",
              form("Отход", "Прыжок на клетку до 3, затем тень 3 сек (удар из тени ×1.8).",
                   [{"type": "teleport"}, {"type": "stealth", "duration": 3, "mult": 1.8, "at": "caster"}],
                   target="cell", range=3, free_cell=True, cooldown=10)),
         tier("Дымная завеса", "На месте прыжка — ядовитое облако.",
              desc("Ядовитое облако на старой клетке, прыжок до 3, тень 3 сек."),
              {"effects": [{"type": "hazard", "hazard": "poison", "duration": 5, "at": "caster"},
                           {"type": "teleport"}, {"type": "stealth", "duration": 3, "mult": 1.8, "at": "caster"}]})))
S("shadow_mark", skill("Метка смерти", "Цель получает +35% урона 6 сек (дальность 5).", 3, "enemy",
                       [buff("dmg_taken", 1.35, 6, affects="enemies")], rng=5, cd=8, au=auto(True)),
  branch("Охота",
         tier("Охота", "Ещё и Яд на цель.", desc("Цель: +35% урона 6 сек и Яд."), add({"type": "status", "tag": "poison"})),
         tier("Приговор тени", "+50% урона вместо +35%.", desc("Цель: +50% урона 6 сек и Яд."),
              eff("buff", set={"value": 1.5}))),
  branch("Слабое место",
         tier("Слабое место", "Цель теряет 4 брони на 6 сек.",
              form("Слабое место", "Цель: −4 брони и +20% урона 6 сек.",
                   [buff("armor", -4, 6, affects="enemies"), buff("dmg_taken", 1.2, 6, affects="enemies")])),
         tier("Разоблачение", "Ещё и оглушение 1 сек.", desc("Цель: −4 брони, +20% урона 6 сек, оглушение 1 сек."),
              add({"type": "stun", "duration": 1.0}))))
S("riposte", skill("Парирование", "4 сек: +4 брони, отражает 80% ближнего урона.", 2, "self",
                   [buff("armor", 4, 4), buff("thorns", 0.8, 4)], cd=7, au=auto(True, ("enemies_adjacent", 1))),
  branch("Дуэль",
         tier("Дуэль", "Ещё и атаки на 40% быстрее.", desc("4 сек: +4 брони, отражение 80%, атаки быстрее."),
              add(buff("atk_speed", 0.6, 4))),
         tier("Мастер клинка", "Длится 6 сек.", desc("6 сек: +4 брони, отражение 80%, атаки быстрее."),
              eff("buff", set={"duration": 6}))),
  branch("Уход в сторону",
         tier("Уход в сторону", "Вместо брони — уклонение: урон по ассасину ×0.4.",
              form("Уход в сторону", "4 сек урон по ассасину ×0.4 и отражение 50%.",
                   [buff("dmg_taken", 0.4, 4), buff("thorns", 0.5, 4)])),
         tier("Тень клинка", "Затем 2 сек тени.", desc("4 сек урон ×0.4, отражение 50%, затем тень (удар ×1.6)."),
              add({"type": "stealth", "duration": 2, "mult": 1.6}))))
PATHS["shadow"] = {"class": "assassin", "name": "Тень", "desc": "Метит цели для всего отряда. Вместо Ядовитого клинка — "
                   "Метка смерти, вместо Удара в спину — Ускользание.", "replace": {"venom_blade": "shadow_mark"},
                   "passive": {"kind": "dodge", "vs": ["melee", "ranged"], "name": "Ускользание", "pp": 1,
                               "desc": "Атака оружием по ассасину: −1 деление шкалы, промах"},
                   "mods": [{"stat": "move_time", "mult": 0.9}]}
PATHS["duelist"] = {"class": "assassin", "name": "Дуэлянт", "desc": "Держит удар в ближнем бою. Вместо Исчезновения — "
                    "Парирование, вместо Удара в спину — Контратака.", "replace": {"vanish": "riposte"},
                    "passive": {"kind": "retaliate", "name": "Контратака", "pp": 1, "damage": 12,
                                "desc": "Ближняя атака по дуэлянту: −1 деление шкалы, 12 урона атакующему"},
                    "mods": [{"stat": "hp", "add": 20}, {"stat": "armor", "add": 1}]}

# ======================= Друид =======================
CLASSES["druid"] = {
    "name": "Друид", "label": "Д", "color": [110, 160, 70], "role": "support", "hp": 85, "armor": 1, "move_time": 0.5,
    "attack": {"damage": 7, "range": 3, "cooldown": 1.2}, "ap_max": 6, "ap_regen": 4.5, "pp_max": 2, "pp_regen": 3.5,
    "passive": {"kind": "rage", "name": "Сила природы", "pp": 1, "stat": "regen", "value": 6, "duration": 3,
                "desc": "Удар по друиду: −1 деление шкалы, восстанавливает 6 HP/сек 3 сек"},
    "forms": {"bear": {"name": "облик медведя", "armor_add": 4, "atk_mult": 1.8, "atk_range": 1, "move_mult": 1.1,
                       "hp_add": 40, "atk_kind": "melee"},
              "wolf": {"name": "облик волка", "armor_add": 1, "atk_mult": 1.5, "atk_range": 1, "atk_cd_mult": 0.6,
                       "move_mult": 0.6, "atk_kind": "melee"}},
    "skills": ["bear_form", "entangle", "rejuvenate"], "unlock": 60,
    "about": "Три роли в одном: лечит издалека, держит удар медведем, связывает врагов корнями."}
S("bear_form", skill("Облик медведя", "Медведь: +4 брони, +40 HP, атака ×1.8 в ближнем бою. Повтор — обратно.", 2, "self",
                     [{"type": "form", "form": "bear"}], cd=3),
  branch("Медведь-страж",
         tier("Медведь-страж", "Превращение провоцирует врагов рядом на 4 сек.",
              desc("Медведь (+4 брони, +40 HP, атака ×1.8); враги рядом атакуют его 4 сек."),
              add({"type": "taunt", "radius": 1, "duration": 4})),
         tier("Шкура", "И щит 30.", desc("Медведь, провокация рядом 4 сек и щит 30."),
              add({"type": "shield", "amount": 30, "duration": 6}))),
  branch("Ярость зверя",
         tier("Ярость зверя", "Превращение даёт атаки на 30% быстрее 5 сек.",
              desc("Медведь (+4 брони, +40 HP, атака ×1.8); 5 сек атаки быстрее."), add(buff("atk_speed", 0.7, 5))),
         tier("Вкус крови", "И лечит на 25.", desc("Медведь, атаки быстрее 5 сек, лечение 25."),
              add({"type": "heal", "amount": 25}))))
S("entangle", skill("Цепкие корни", "Радиус 1: 10 урона, оглушение 1.2 сек, терновник 4 сек.", 3, "cell",
                    [D(10, radius=1), {"type": "stun", "duration": 1.2, "radius": 1},
                     {"type": "hazard", "hazard": "briar", "duration": 4, "radius": 1}],
                    rng=4, cast=0.5, cd=6, radius=1, au=auto(True, ("enemies_in_area", 2))),
  branch("Терновник",
         tier("Терновник", "14 урона, терновник 6 сек.", desc("Радиус 1: 14 урона, оглушение 1.2 сек, терновник 6 сек."),
              eff("damage", set={"amount": 14}), eff("hazard", set={"duration": 6})),
         tier("Дикие заросли", "Радиус 2.", desc("Радиус 2: 14 урона, оглушение 1.2 сек, терновник 6 сек.",
                                                 radius=2), {"radius_add": 1})),
  branch("Удушение",
         tier("Удушение", "Одна цель: оглушение 2.5 сек и Яд.",
              form("Удушение", "Враг (дальность 4): оглушение 2.5 сек и Яд.",
                   [{"type": "stun", "duration": 2.5}, {"type": "status", "tag": "poison"}], target="enemy", radius=0,
                   auto=auto(True, ("target_casting",)))),
         tier("Хватка земли", "И 20 урона.", desc("Враг: 20 урона, оглушение 2.5 сек и Яд."), add(D(20)))))
S("rejuvenate", skill("Омоложение", "Союзник восстанавливает 8 HP/сек 5 сек.", 3, "ally",
                      [buff("regen", 8, 5)], rng=4, au=auto(True, ("target_hp_below", 70))),
  branch("Цветение",
         tier("Цветение", "И союзникам рядом.", desc("Союзник и все рядом: 8 HP/сек 5 сек.", radius=1),
              eff("buff", set={"radius": 1})),
         tier("Очищение росой", "Ещё и снимает теги.", desc("Союзник и все рядом: 8 HP/сек 5 сек, теги сняты."),
              add({"type": "cleanse", "radius": 1}))),
  branch("Живая кора",
         tier("Живая кора", "Ещё +3 брони на 6 сек.", desc("Союзник: 8 HP/сек 5 сек и +3 брони 6 сек."),
              add(buff("armor", 3, 6))),
         tier("Шипы коры", "И отражает 40% ближнего урона.", desc("Союзник: регенерация, +3 брони, отражение 40%."),
              add(buff("thorns", 0.4, 6)))))
S("wolf_form", skill("Облик волка", "Волк: атаки на 40% быстрее и ×1.5, бег вдвое быстрее. Повтор — обратно.", 2, "self",
                     [{"type": "form", "form": "wolf"}], cd=3),
  branch("Вожак",
         tier("Вожак", "Превращение даёт атаки ×1.2 на 6 сек.", desc("Волк; 6 сек атаки ещё ×1.2."),
              add(buff("atk_mult", 1.2, 6))),
         tier("Загонщик", "Враги рядом замедлены.", desc("Волк, атаки ×1.2 6 сек, враги рядом замедлены 4 сек."),
              add(buff("slow", 1.6, 4, radius=1, affects="enemies")))),
  branch("Вой",
         tier("Вой", "Союзники в радиусе 2: атаки ×1.2 на 6 сек.", desc("Волк; союзники в радиусе 2 бьют ×1.2 6 сек."),
              add(buff("atk_mult", 1.2, 6, radius=2))),
         tier("Леденящий вой", "Враги в радиусе 2 получают +20% урона.",
              desc("Волк, союзники бьют ×1.2, враги в радиусе 2 получают +20% урона 6 сек."),
              add(buff("dmg_taken", 1.2, 6, radius=2, affects="enemies")))))
S("spirit_tree", skill("Древо жизни", "Сажает древо (14 сек): лечит союзников в радиусе 2 на 7 каждую секунду.", 4, "cell",
                       [{"type": "summon", "unit": "spirit_tree", "duration": 14}], rng=3, cd=14,
                       au=auto(True, ("ally_hp_below", 70)), place="allies"),
  branch("Роща",
         tier("Роща", "Древо живёт 20 сек.", desc("Древо 20 сек: лечит в радиусе 2 на 7/сек."),
              eff("summon", set={"duration": 20})),
         tier("Могучее древо", "Лечит на 40% сильнее.", desc("Древо 20 сек: лечит в радиусе 2, сила ×1.4."),
              eff("summon", set={"power": 1.4}))),
  branch("Страж-энт",
         tier("Страж-энт", "Вместо древа — энт: бьёт врагов и провоцирует их.",
              form("Страж-энт", "Энт 14 сек: провоцирует врагов в радиусе 2, бьёт рядом.",
                   [{"type": "summon", "unit": "ent", "duration": 14}], place="foes",
                   auto=auto(True, ("enemies_adjacent", 1)))),
         tier("Древний энт", "Энт крепче и сильнее на 50%.", desc("Энт 14 сек, сила ×1.5."),
              eff("summon", set={"power": 1.5}))))
PATHS["wild"] = {"class": "druid", "name": "Дикий оборотень", "desc": "Ближний бой в облике волка. Вместо Омоложения — "
                 "Облик волка, вместо Силы природы — Звериная ярость.", "replace": {"rejuvenate": "wolf_form"},
                 "passive": {"kind": "rage", "name": "Звериная ярость", "pp": 1, "stat": "atk_mult", "value": 1.4,
                             "duration": 3, "desc": "Удар по друиду: −1 деление шкалы, его атаки ×1.4 на 3 сек"},
                 "mods": [{"stat": "atk_damage", "add": 2}]}
PATHS["grove"] = {"class": "druid", "name": "Хранитель рощи", "desc": "Лечит отряд через древо. Вместо Облика медведя — "
                  "Древо жизни, вместо Силы природы — Покров рощи.", "replace": {"bear_form": "spirit_tree"},
                  "passive": {"kind": "intercede", "name": "Покров рощи", "pp": 1, "range": 1, "heal": 8,
                              "desc": "Соседа-союзника бьют: −1 деление шкалы, лечит его на 8"},
                  "mods": [{"stat": "ap_max", "add": 1}]}

# ======================= Страж-копейщик =======================
CLASSES["guardian"] = {
    "name": "Страж", "label": "С", "color": [160, 140, 100], "role": "melee", "hp": 125, "armor": 4, "move_time": 0.5,
    "attack": {"damage": 10, "range": 2, "cooldown": 1.3, "kind": "melee"}, "ap_max": 6, "ap_regen": 5.0,
    "pp_max": 2, "pp_regen": 3.0,
    "passive": {"kind": "zoc", "name": "Стойка", "pp": 1, "mult": 1.0, "halt": 0.8,
                "desc": "Враг шагнул в соседнюю клетку: −1 деление шкалы, удар копьём, враг замешкался"},
    "skills": ["lunge", "hook", "shield_wall"], "unlock": 60,
    "about": "Держит линию: копьё бьёт на 2 клетки, каждого подошедшего встречает ударом, притягивает крюком."}
S("lunge", skill("Выпад", "Копьё пробивает 3 клетки по линии: 24 урона каждому.", 3, "enemy",
                 [{"type": "line", "amount": 24, "length": 3, "kind": "melee"}], rng=2, cd=3, au=auto(True)),
  branch("Пронзатель",
         tier("Пронзатель", "4 клетки, 30 урона.", desc("Копьё пробивает 4 клетки: 30 урона каждому."),
              eff("line", set={"length": 4, "amount": 30})),
         tier("Бронебой", "Пробитые теряют 3 брони на 6 сек.", desc("4 клетки: 30 урона, −3 брони 6 сек."),
              eff("line", set={"on_hit_buff": {"stat": "armor", "value": -3, "duration": 6}}))),
  branch("Сокрушитель строя",
         tier("Сокрушитель строя", "Одна цель: 28 урона и отталкивание на 1.",
              form("Сокрушитель строя", "Враг (дальность 2): 28 урона и отталкивание на 1.",
                   [D(28, "melee"), {"type": "knockback", "cells": 1}])),
         tier("Опрокинуть", "И оглушение 1 сек.", desc("Враг: 28 урона, отталкивание и оглушение 1 сек."),
              add({"type": "stun", "duration": 1.0}))))
S("hook", skill("Крюк", "Притягивает врага (до 4 клеток) на 3 клетки: 10 урона, замедление.", 3, "enemy",
                [{"type": "pull", "cells": 3}, D(10, "melee", on_hit_buff={"stat": "slow", "value": 1.5, "duration": 3})],
                rng=4, cd=6, au=auto(True, ("target_casting",))),
  branch("Цепь",
         tier("Цепь", "Притянутый оглушён на 1.2 сек.", desc("Притягивает врага на 3 клетки: 10 урона и оглушение 1.2 сек."),
              add({"type": "stun", "duration": 1.2})),
         tier("Длинная цепь", "Дальность 5.", desc("Дальность 5: притягивает, 10 урона, оглушение 1.2 сек.", range=5))),
  branch("Подсечка",
         tier("Подсечка", "Без притягивания: 16 урона и оглушение 1.5 сек (дальность 2).",
              form("Подсечка", "Враг (дальность 2): 16 урона и оглушение 1.5 сек.",
                   [D(16, "melee"), {"type": "stun", "duration": 1.5}], range=2)),
         tier("Круговая подсечка", "По всем врагам рядом с целью.",
              desc("Враг и все рядом: 16 урона и оглушение 1.5 сек.", radius=1),
              eff("damage", set={"radius": 1}), eff("stun", set={"radius": 1}))))
S("shield_wall", skill("Стена щитов", "+5 брони себе 6 сек, союзникам рядом — щит 20.", 4, "self",
                       [buff("armor", 5, 6), {"type": "shield", "amount": 20, "duration": 6, "radius": 1}],
                       cd=10, radius=1, au=auto(True, ("enemies_adjacent", 2))),
  branch("Фаланга",
         tier("Фаланга", "Щит 25 союзникам в радиусе 2.", desc("+5 брони себе, щит 25 союзникам в радиусе 2.", radius=2),
              eff("shield", set={"radius": 2, "amount": 25})),
         tier("Строй", "Союзникам рядом ещё +3 брони.", desc("+5 брони себе, щит 25 и +3 брони союзникам в радиусе 2."),
              add(buff("armor", 3, 6, radius=2)))),
  branch("Ёж",
         tier("Ёж", "Отражает 60% ближнего урона 6 сек.", desc("+5 брони и отражение 60% ближнего урона 6 сек."),
              add(buff("thorns", 0.6, 6))),
         tier("Вызов", "Враги в радиусе 2 атакуют стража 4 сек.", desc("+5 брони, отражение 60%, провокация в радиусе 2."),
              add({"type": "taunt", "radius": 2, "duration": 4}))))
S("brace", skill("Упор", "5 сек: +3 брони и атаки на 40% быстрее.", 2, "self",
                 [buff("armor", 3, 5), buff("atk_speed", 0.6, 5)], cd=8, au=auto(True, ("enemies_adjacent", 1))),
  branch("Несокрушимый",
         tier("Несокрушимый", "+6 брони вместо +3.", desc("5 сек: +6 брони и атаки быстрее."),
              {"effects": [buff("armor", 6, 5), buff("atk_speed", 0.6, 5)]}),
         tier("Скала", "Иммунитет к тегам.", desc("5 сек: +6 брони, атаки быстрее, иммунитет к тегам."),
              add(buff("immune", 1, 5)))),
  branch("Шквал копий",
         tier("Шквал копий", "Атаки ×1.3.", desc("5 сек: +3 брони, атаки быстрее и ×1.3."), add(buff("atk_mult", 1.3, 5))),
         tier("Буря стали", "Длится 8 сек.", desc("8 сек: +3 брони, атаки быстрее и ×1.3."),
              eff("buff", set={"duration": 8}))))
S("jump_strike", skill("Прыжок драгуна", "Прыжок на клетку до 4: 28 урона врагам рядом, оглушение 0.8 сек.", 4, "cell",
                       [{"type": "teleport"}, D(28, "melee", radius=1), {"type": "stun", "duration": 0.8, "radius": 1}],
                       rng=4, cd=6, radius=1, free_cell=True, au=auto(True, ("enemies_in_area", 2))),
  branch("Пикирование",
         tier("Пикирование", "36 урона.", desc("Прыжок до 4: 36 урона рядом, оглушение 0.8 сек."),
              eff("damage", set={"amount": 36})),
         tier("Падение с небес", "Дальность 6.", desc("Прыжок до 6: 36 урона рядом, оглушение 0.8 сек.", range=6))),
  branch("Удар хвостом",
         tier("Удар хвостом", "Отбрасывает врагов на 2.", desc("Прыжок до 4: 28 урона, отбрасывание на 2."),
              {"effects": [{"type": "teleport"}, D(28, "melee", radius=1), {"type": "knockback", "cells": 2, "radius": 1}]}),
         tier("Боевой порыв", "Затем атаки быстрее 4 сек.", desc("Прыжок, 28 урона, отбрасывание, атаки быстрее 4 сек."),
              add(buff("atk_speed", 0.6, 4, at="caster")))))
PATHS["sentinel"] = {"class": "guardian", "name": "Часовой", "desc": "Неприступная стойка. Вместо Крюка — Упор, "
                     "стойка бьёт на 2 клетки и сильнее.", "replace": {"hook": "brace"},
                     "passive": {"kind": "zoc", "name": "Длинная стойка", "pp": 1, "mult": 1.3, "halt": 1.0, "range": 2,
                                 "desc": "Враг подошёл на 2 клетки: −1 деление шкалы, удар ×1.3, враг замешкался"},
                     "mods": [{"stat": "armor", "add": 1}]}
PATHS["dragoon"] = {"class": "guardian", "name": "Драгун", "desc": "Врывается в строй. Вместо Стены щитов — Прыжок драгуна, "
                    "вместо Стойки — Натиск.", "replace": {"shield_wall": "jump_strike"},
                    "passive": {"kind": "rage", "name": "Натиск", "pp": 1, "stat": "atk_mult", "value": 1.3, "duration": 4,
                                "desc": "Удар по драгуну: −1 деление шкалы, его атаки ×1.3 на 4 сек"},
                    "mods": [{"stat": "armor", "add": -1}, {"stat": "move_time", "mult": 0.85}]}

# ======================= Шаман бури =======================
CLASSES["shaman"] = {
    "name": "Шаман", "label": "Ш", "color": [80, 130, 220], "role": "caster", "hp": 70, "armor": 1, "move_time": 0.5,
    "attack": {"damage": 8, "range": 4, "cooldown": 1.3}, "ap_max": 7, "ap_regen": 4.2, "pp_max": 2, "pp_regen": 3.5,
    "passive": {"kind": "retaliate", "name": "Статический заряд", "pp": 1, "damage": 8, "tag": "storm",
                "desc": "Ближняя атака по шаману: −1 деление шкалы, 8 урона + Гроза атакующему"},
    "skills": ["chain_lightning", "storm_totem", "healing_totem"], "unlock": 60,
    "about": "Гроза и тотемы. Молния по мокрым — электрошок, по льду — раскол, по огню — перегрузка."}
S("chain_lightning", skill("Цепная молния", "22 урона + Гроза, перескакивает на 2 врагов (14).", 4, "enemy",
                           [D(22, tag="storm"), {"type": "chain", "jumps": 2, "range": 3, "amount": 14, "tag": "storm"}],
                           rng=5, cast=0.6, au=auto(True)),
  branch("Буря",
         tier("Буря", "Перескакивает на 4.", desc("22 урона + Гроза, перескакивает на 4 врагов (14)."),
              eff("chain", set={"jumps": 4})),
         tier("Сверхпроводник", "Прыжки на 4 клетки, 18 урона.", desc("22 урона + Гроза, 4 прыжка по 18 до 4 клеток."),
              eff("chain", set={"range": 4, "amount": 18}))),
  branch("Удар грома",
         tier("Удар грома", "По клетке: 30 урона + Гроза в радиусе 1, оглушение 1 сек.",
              form("Удар грома", "Радиус 1: 30 урона + Гроза, оглушение 1 сек.",
                   [D(30, radius=1, tag="storm"), {"type": "stun", "duration": 1.0, "radius": 1}], target="cell",
                   radius=1, cast=1.0, cooldown=5, auto=auto(True, ("enemies_in_area", 2)))),
         tier("Раскат", "Радиус 2.", desc("Радиус 2: 30 урона + Гроза, оглушение 1 сек.", radius=2), {"radius_add": 1})))
S("storm_totem", skill("Тотем грозы", "Тотем (12 сек) бьёт молнией врагов в радиусе 3.", 4, "cell",
                       [{"type": "summon", "unit": "totem_storm", "duration": 12}], rng=3, cd=10, au=auto(True)),
  branch("Громовой тотем",
         tier("Громовой тотем", "Живёт 16 сек.", desc("Тотем 16 сек бьёт молнией в радиусе 3."),
              eff("summon", set={"duration": 16})),
         tier("Пара тотемов", "Можно держать два тотема, сила ×1.3.", desc("До двух тотемов по 16 сек, сила ×1.3."),
              eff("summon", set={"limit": 2, "power": 1.3}))),
  branch("Тотем бури",
         tier("Тотем бури", "Тотем раз в 2 сек бьёт всех врагов в радиусе 2 (10 + Гроза).",
              form("Тотем бури", "Тотем 12 сек: раз в 2 сек 10 урона + Гроза всем врагам в радиусе 2.",
                   [{"type": "summon", "unit": "totem_thunder", "duration": 12}])),
         tier("Око бури", "Живёт 16 сек, сила ×1.3.", desc("Тотем бури 16 сек, сила ×1.3."),
              eff("summon", set={"duration": 16, "power": 1.3}))))
S("healing_totem", skill("Тотем исцеления", "Тотем (12 сек) лечит союзников в радиусе 2 на 5 в секунду.", 3, "cell",
                         [{"type": "summon", "unit": "totem_heal", "duration": 12}], rng=3, cd=12,
                         au=auto(True, ("ally_hp_below", 70)), place="allies"),
  branch("Родник",
         tier("Родник", "Лечит на 40% сильнее.", desc("Тотем 12 сек лечит в радиусе 2, сила ×1.4."),
              eff("summon", set={"power": 1.4})),
         tier("Источник жизни", "Живёт 18 сек.", desc("Тотем 18 сек лечит в радиусе 2, сила ×1.4."),
              eff("summon", set={"duration": 18}))),
  branch("Тотем-страж",
         tier("Тотем-страж", "Тотем провоцирует врагов в радиусе 2.",
              form("Тотем-страж", "Тотем 12 сек: крепкий, раз в 3 сек провоцирует врагов в радиусе 2.",
                   [{"type": "summon", "unit": "totem_ward", "duration": 12}], place="foes",
                   auto=auto(True, ("ally_hp_below", 60)))),
         tier("Каменный идол", "Сила ×1.5.", desc("Тотем-страж 12 сек, сила ×1.5."), eff("summon", set={"power": 1.5}))))
S("thunderstorm", skill("Гроза", "Каст 1.5 сек, радиус 2: 26 урона + Гроза, оглушение 0.6 сек.", 5, "cell",
                        [D(26, radius=2, tag="storm"), {"type": "stun", "duration": 0.6, "radius": 2}],
                        rng=5, cast=1.5, cd=8, radius=2, au=auto(True, ("enemies_in_area", 2))),
  branch("Ураган",
         tier("Ураган", "34 урона.", desc("Радиус 2: 34 урона + Гроза, оглушение 0.6 сек."), eff("damage", set={"amount": 34})),
         tier("Небесный гнев", "Каст 1 сек.", desc("Каст 1 сек, радиус 2: 34 урона + Гроза, оглушение.", cast=1.0))),
  branch("Ливень",
         tier("Ливень", "Ещё и Вода: сразу готовит электрошок.",
              desc("Радиус 2: Вода, затем 26 урона + Гроза (электрошок!), оглушение 0.6 сек."),
              {"effects": [{"type": "status", "tag": "water", "radius": 2}, D(26, radius=2, tag="storm"),
                           {"type": "stun", "duration": 0.6, "radius": 2}]}),
         tier("Потоп", "Клетки становятся лужами (Вода 6 сек).", desc("Ливень по радиусу 2, клетки мокрые."),
              add({"type": "cell_tag", "tag": "water", "radius": 2}))))
S("spirit_link", skill("Связь духов", "Союзнику: щит 30 и 5 HP/сек 5 сек.", 3, "ally",
                       [{"type": "shield", "amount": 30, "duration": 6}, buff("regen", 5, 5)], rng=4, cd=4,
                       au=auto(True, ("target_hp_below", 60))),
  branch("Предки",
         tier("Предки", "Щит 45.", desc("Союзнику: щит 45 и 5 HP/сек."), eff("shield", set={"amount": 45})),
         tier("Хор духов", "И всем рядом с ним.", desc("Союзнику и всем рядом: щит 45 и 5 HP/сек.", radius=1),
              eff("shield", set={"radius": 1}), eff("buff", set={"radius": 1}))),
  branch("Дух-проводник",
         tier("Дух-проводник", "Союзник получает +2 AP.", desc("Союзнику: щит 30, регенерация и +2 AP."),
              add({"type": "refresh", "ap": 2})),
         tier("Одержимость", "И атаки ×1.25 на 6 сек.", desc("Союзнику: щит 30, регенерация, +2 AP, атаки ×1.25."),
              add(buff("atk_mult", 1.25, 6)))))
PATHS["thunderlord"] = {"class": "shaman", "name": "Громовержец", "desc": "Чистая гроза. Вместо Тотема исцеления — Гроза, "
                        "вместо Статического заряда — Сосредоточение.", "replace": {"healing_totem": "thunderstorm"},
                        "passive": {"kind": "concentration", "name": "Сосредоточение", "pp": 1,
                                    "desc": "Каст прерывают: −1 деление шкалы, каст продолжается"},
                        "mods": [{"stat": "power", "mult": 1.08}]}
PATHS["spiritwalker"] = {"class": "shaman", "name": "Хранитель духов", "desc": "Поддержка через духов. Вместо Цепной молнии — "
                         "Связь духов, вместо Статического заряда — Духи предков.",
                         "replace": {"chain_lightning": "spirit_link"},
                         "passive": {"kind": "rage", "name": "Духи предков", "pp": 1, "stat": "armor", "value": 4,
                                     "duration": 3, "desc": "Удар по шаману: −1 деление шкалы, +4 брони на 3 сек"},
                         "mods": [{"stat": "hp", "add": 15}]}

# ======================= Бард =======================
CLASSES["bard"] = {
    "name": "Бард", "label": "Б", "color": [210, 110, 170], "role": "support", "hp": 75, "armor": 1, "move_time": 0.45,
    "attack": {"damage": 7, "range": 3, "cooldown": 1.1}, "ap_max": 6, "ap_regen": 4.0, "pp_max": 2, "pp_regen": 3.5,
    "passive": {"kind": "encore", "name": "Импровизация", "pp": 1, "ap": 1, "min_ap": 3,
                "desc": "После навыка от 3 AP: −1 деление шкалы, +1 AP"},
    "skills": ["war_song", "lullaby", "inspire"], "unlock": 60,
    "about": "Темп боя: песни ускоряют AP и усиливают атаки, колыбельная усыпляет, «На бис» перезаряжает союзника."}
S("war_song", skill("Боевая песнь", "Союзники в радиусе 3: атаки ×1.25 и AP на 25% быстрее 8 сек.", 4, "self",
                    [buff("atk_mult", 1.25, 8, radius=3), buff("ap_rate", 0.75, 8, radius=3)], cd=12, radius=3,
                    au=auto(True)),
  branch("Марш",
         tier("Марш", "И движение на 25% быстрее, 10 сек.", desc("Союзники в радиусе 3: атаки ×1.25, AP быстрее, бег быстрее 10 сек."),
              eff("buff", set={"duration": 10}), add(buff("slow", 0.75, 10, radius=3))),
         tier("Барабаны войны", "И атаки на 20% чаще.", desc("Марш: ещё и атаки на 20% чаще."),
              add(buff("atk_speed", 0.8, 10, radius=3)))),
  branch("Гимн стойкости",
         tier("Гимн стойкости", "Вместо урона: +3 брони и 4 HP/сек.",
              form("Гимн стойкости", "Союзники в радиусе 3: +3 брони, 4 HP/сек, AP на 25% быстрее 8 сек.",
                   [buff("armor", 3, 8, radius=3), buff("regen", 4, 8, radius=3), buff("ap_rate", 0.75, 8, radius=3)])),
         tier("Щит песни", "И щит 20.", desc("Гимн стойкости и щит 20 всем в радиусе 3."),
              add({"type": "shield", "amount": 20, "duration": 8, "radius": 3}))))
S("lullaby", skill("Колыбельная", "Радиус 1: враги засыпают на 4 сек (удар будит).", 4, "cell",
                   [{"type": "sleep", "duration": 4, "radius": 1}], rng=4, cast=0.6, cd=10, radius=1,
                   au=auto(True, ("enemies_in_area", 2))),
  branch("Глубокий сон",
         tier("Глубокий сон", "Сон 6 сек.", desc("Радиус 1: сон 6 сек."), eff("sleep", set={"duration": 6})),
         tier("Сонное царство", "Радиус 2.", desc("Радиус 2: сон 6 сек.", radius=2), {"radius_add": 1})),
  branch("Диссонанс",
         tier("Диссонанс", "Не усыпляет: 14 урона и +25% урона по целям 6 сек.",
              form("Диссонанс", "Радиус 1: 14 урона, враги получают +25% урона 6 сек.",
                   [D(14, radius=1), buff("dmg_taken", 1.25, 6, radius=1, affects="enemies")])),
         tier("Какофония", "И оглушение 0.8 сек.", desc("Радиус 1: 14 урона, +25% урона по ним, оглушение 0.8 сек."),
              add({"type": "stun", "duration": 0.8, "radius": 1}))))
S("inspire", skill("На бис", "Союзник получает 3 AP и сбрасывает перезарядки.", 2, "ally",
                   [{"type": "refresh", "ap": 3, "cooldowns": True}], rng=4, cd=8),
  branch("Вдохновение",
         tier("Вдохновение", "4 AP и атаки ×1.2 на 5 сек.", desc("Союзник: +4 AP, перезарядки сброшены, атаки ×1.2 5 сек."),
              eff("refresh", set={"ap": 4}), add(buff("atk_mult", 1.2, 5))),
         tier("Овация", "Перезарядка 5 сек.", desc("Союзник: +4 AP, перезарядки сброшены, атаки ×1.2.", cooldown=5))),
  branch("Баллада о подвигах",
         tier("Баллада о подвигах", "Всем рядом с целью: +2 AP.", desc("Союзник и все рядом: +2 AP, перезарядки сброшены.",
                                                                    radius=1),
              eff("refresh", set={"ap": 2, "radius": 1})),
         tier("Песнь исцеления", "И лечит на 20.", desc("Союзник и все рядом: +2 AP, сброс перезарядок, лечение 20."),
              add({"type": "heal", "amount": 20, "radius": 1}))))
S("sonic_blast", skill("Звуковая волна", "Враги в радиусе 2: 18 урона и отбрасывание на 1.", 4, "self",
                       [D(18, radius=2), {"type": "knockback", "cells": 1, "radius": 2}], cd=6, radius=2,
                       au=auto(True, ("enemies_in_area", 2))),
  branch("Рёв скальда",
         tier("Рёв скальда", "26 урона.", desc("Радиус 2: 26 урона и отбрасывание."), eff("damage", set={"amount": 26})),
         tier("Оглушительный рёв", "И оглушение 1 сек.", desc("Радиус 2: 26 урона, отбрасывание, оглушение 1 сек."),
              add({"type": "stun", "duration": 1.0, "radius": 2}))),
  branch("Боевой клич",
         tier("Боевой клич", "Союзники в радиусе 2: атаки ×1.3 на 5 сек.",
              desc("Радиус 2: 18 урона врагам, отбрасывание; союзники бьют ×1.3 5 сек."),
              add(buff("atk_mult", 1.3, 5, radius=2))),
         tier("Песнь берсерков", "И атаки на 30% чаще.", desc("Клич: ещё и атаки союзников на 30% чаще."),
              add(buff("atk_speed", 0.7, 5, radius=2)))))
S("serenade", skill("Серенада", "Союзники в радиусе 3: 6 HP/сек 6 сек и теги сняты.", 4, "self",
                    [buff("regen", 6, 6, radius=3), {"type": "cleanse", "radius": 3}], cd=12, radius=3,
                    au=auto(True, ("ally_hp_below", 60))),
  branch("Колыбель жизни",
         tier("Колыбель жизни", "9 HP/сек.", desc("Радиус 3: 9 HP/сек 6 сек, теги сняты."), eff("buff", set={"value": 9})),
         tier("Иммунитет", "Иммунитет к тегам на 5 сек.", desc("Радиус 3: 9 HP/сек, теги сняты, иммунитет 5 сек."),
              add(buff("immune", 1, 5, radius=3)))),
  branch("Мелодия ветра",
         tier("Мелодия ветра", "И AP на 30% быстрее 6 сек.", desc("Радиус 3: 6 HP/сек, теги сняты, AP быстрее 6 сек."),
              add(buff("ap_rate", 0.7, 6, radius=3))),
         tier("Попутный ветер", "И бег быстрее.", desc("Радиус 3: регенерация, AP и бег быстрее, теги сняты."),
              add(buff("slow", 0.7, 6, radius=3)))))
PATHS["skald"] = {"class": "bard", "name": "Скальд", "desc": "Боевой бард в гуще схватки. Вместо Колыбельной — "
                  "Звуковая волна, вместо Импровизации — Боевой раж.", "replace": {"lullaby": "sonic_blast"},
                  "passive": {"kind": "rage", "name": "Боевой раж", "pp": 1, "stat": "atk_mult", "value": 1.4,
                              "duration": 3, "desc": "Удар по скальду: −1 деление шкалы, его атаки ×1.4 на 3 сек"},
                  "mods": [{"stat": "hp", "add": 25}, {"stat": "armor", "add": 1}]}
PATHS["minstrel"] = {"class": "bard", "name": "Менестрель", "desc": "Целитель песней. Вместо Боевой песни — Серенада, "
                     "вместо Импровизации — Утешение.", "replace": {"war_song": "serenade"},
                     "passive": {"kind": "intercede", "name": "Утешение", "pp": 1, "range": 1, "heal": 6,
                                 "desc": "Соседа-союзника бьют: −1 деление шкалы, лечит его на 6"},
                     "mods": [{"stat": "ap_max", "add": 1}]}

# ======================= Алхимик =======================
CLASSES["alchemist"] = {
    "name": "Алхимик", "label": "Х", "color": [200, 150, 60], "role": "ranged", "hp": 75, "armor": 1, "move_time": 0.45,
    "attack": {"damage": 8, "range": 4, "cooldown": 1.2}, "ap_max": 7, "ap_regen": 4.3, "pp_max": 2, "pp_regen": 3.5,
    "passive": {"kind": "catalyst", "name": "Катализатор", "pp": 1, "mult": 1.5,
                "desc": "Реакция от удара алхимика: −1 деление шкалы, она сильнее в 1.5 раза"},
    "skills": ["fire_bomb", "oil_flask", "healing_potion"], "unlock": 60,
    "about": "Бомбы и склянки: сам готовит реакции. Масло + огонь — пожар, яд + огонь — ядовитое облако."}
S("fire_bomb", skill("Огненная бомба", "Радиус 1: 20 урона + Огонь, центр горит 3 сек.", 4, "cell",
                     [D(20, radius=1, tag="fire"), {"type": "hazard", "hazard": "fire", "duration": 3}],
                     rng=5, cast=0.4, radius=1, au=auto(True, ("enemies_in_area", 2))),
  branch("Напалм",
         tier("Напалм", "Горит весь радиус 4 сек.", desc("Радиус 1: 20 урона + Огонь, клетки горят 4 сек."),
              eff("hazard", set={"radius": 1, "duration": 4})),
         tier("Жидкий огонь", "26 урона.", desc("Радиус 1: 26 урона + Огонь, клетки горят 4 сек."),
              eff("damage", set={"amount": 26}))),
  branch("Осколочная",
         tier("Осколочная", "Без огня: 28 урона и отбрасывание.",
              form("Осколочная бомба", "Радиус 1: 28 урона и отбрасывание на 1.",
                   [D(28, "ranged", radius=1), {"type": "knockback", "cells": 1, "radius": 1}])),
         tier("Картечь", "Радиус 2.", desc("Радиус 2: 28 урона и отбрасывание.", radius=2), {"radius_add": 1})))
S("oil_flask", skill("Масляная склянка", "Радиус 1: Масло на врагов и лужа масла 8 сек (огонь её поджигает).", 2, "cell",
                     [{"type": "status", "tag": "oil", "radius": 1},
                      {"type": "hazard", "hazard": "oil", "duration": 8, "radius": 1}],
                     rng=5, cd=4, radius=1, au=auto(True, ("enemies_in_area", 2))),
  branch("Горючая смесь",
         tier("Горючая смесь", "Радиус 2.", desc("Радиус 2: Масло на врагов и масляные лужи 8 сек.", radius=2),
              {"radius_add": 1}),
         tier("Липкая смесь", "Враги замедлены 4 сек.", desc("Радиус 2: Масло, лужи, замедление 4 сек."),
              add(buff("slow", 1.5, 4, radius=2, affects="enemies")))),
  branch("Кислота",
         tier("Кислота", "Вместо масла: 6 урона + Яд, −3 брони, ядовитая лужа.",
              form("Кислотная склянка", "Радиус 1: 6 урона + Яд, −3 брони 6 сек, ядовитая лужа 6 сек.",
                   [D(6, radius=1, tag="poison"), buff("armor", -3, 6, radius=1, affects="enemies"),
                    {"type": "hazard", "hazard": "poison", "duration": 6, "radius": 1}])),
         tier("Царская водка", "Радиус 2.", desc("Радиус 2: Яд, −3 брони, ядовитые лужи.", radius=2),
              {"radius_add": 1})))
S("healing_potion", skill("Лечебное зелье", "Бросок в союзника: лечит его и всех рядом на 35.", 3, "ally",
                          [{"type": "heal", "amount": 35, "radius": 1}], rng=4, cd=3, radius=1,
                          au=auto(True, ("target_hp_below", 60))),
  branch("Эликсир",
         tier("Эликсир", "Лечит на 40 и снимает теги.", desc("Союзник и все рядом: лечение 40, теги сняты."),
              eff("heal", set={"amount": 40}), add({"type": "cleanse", "radius": 1})),
         tier("Панацея", "И 5 HP/сек 4 сек.", desc("Лечение 40, теги сняты, затем 5 HP/сек 4 сек."),
              add(buff("regen", 5, 4, radius=1)))),
  branch("Зелье силы",
         tier("Зелье силы", "Лечит на 15, атаки ×1.3 и быстрее 6 сек.",
              form("Зелье силы", "Союзник и все рядом: лечение 15, атаки ×1.3 и на 20% чаще 6 сек.",
                   [{"type": "heal", "amount": 15, "radius": 1}, buff("atk_mult", 1.3, 6, radius=1),
                    buff("atk_speed", 0.8, 6, radius=1)], auto=auto(True))),
         tier("Эликсир гиганта", "И +3 брони.", desc("Зелье силы и +3 брони 6 сек."), add(buff("armor", 3, 6, radius=1)))))
S("mine", skill("Мина", "Мина на клетке (30 сек): первый враг получает 30 урона + Огонь и оглушение 1 сек.", 2, "cell",
                [{"type": "hazard", "hazard": "mine", "duration": 30}], rng=3, cd=3, au=auto(False)),
  branch("Минное поле",
         tier("Минное поле", "Мины в радиусе 1 (5 сек перезарядка).", desc("Мины на всех клетках радиуса 1 (30 сек).",
                                                                        radius=1, cooldown=5),
              eff("hazard", set={"radius": 1})),
         tier("Растяжки", "Дальность 5.", desc("Мины в радиусе 1, дальность 5.", range=5))),
  branch("Бочка с порохом",
         tier("Бочка с порохом", "Взрыв сразу: радиус 1, 34 урона + Огонь.",
              form("Бочка с порохом", "Радиус 1: 34 урона + Огонь, отбрасывание.",
                   [D(34, radius=1, tag="fire"), {"type": "knockback", "cells": 1, "radius": 1}], radius=1, cast=0.8,
                   cooldown=6, auto=auto(True, ("enemies_in_area", 2)))),
         tier("Пороховой склад", "Радиус 2.", desc("Радиус 2: 34 урона + Огонь, отбрасывание.", radius=2),
              {"radius_add": 1})))
S("poison_cloud", skill("Ядовитое облако", "Радиус 1: 8 урона + Яд, облако 6 сек (Яд всем внутри).", 3, "cell",
                        [D(8, radius=1, tag="poison"), {"type": "hazard", "hazard": "poison", "duration": 6, "radius": 1}],
                        rng=5, cast=0.4, cd=2, radius=1, au=auto(True, ("enemies_in_area", 2))),
  branch("Чума",
         tier("Чума", "Облако 10 сек.", desc("Радиус 1: 8 урона + Яд, облако 10 сек."), eff("hazard", set={"duration": 10})),
         tier("Мор", "Радиус 2.", desc("Радиус 2: 8 урона + Яд, облако 10 сек.", radius=2), {"radius_add": 1})),
  branch("Нервный газ",
         tier("Нервный газ", "Ещё и замедление 4 сек.", desc("Радиус 1: Яд, облако, замедление 4 сек."),
              add(buff("slow", 1.6, 4, radius=1, affects="enemies"))),
         tier("Паралич", "И враги бьют слабее (×0.7) 5 сек.", desc("Радиус 1: Яд, облако, замедление, атаки ×0.7."),
              add(buff("atk_mult", 0.7, 5, radius=1, affects="enemies")))))
PATHS["demolitionist"] = {"class": "alchemist", "name": "Подрывник", "desc": "Мины и взрывы. Вместо Лечебного зелья — Мина.",
                          "replace": {"healing_potion": "mine"},
                          "passive": {"kind": "catalyst", "name": "Детонатор", "pp": 1, "mult": 2.0,
                                      "desc": "Реакция от удара подрывника: −1 деление шкалы, она сильнее вдвое"},
                          "mods": [{"stat": "power", "mult": 1.08}]}
PATHS["poisoner"] = {"class": "alchemist", "name": "Отравитель", "desc": "Яды и облака. Вместо Огненной бомбы — "
                     "Ядовитое облако, вместо Катализатора — Миазмы.", "replace": {"fire_bomb": "poison_cloud"},
                     "passive": {"kind": "retaliate", "name": "Миазмы", "pp": 1, "damage": 6, "tag": "poison",
                                 "desc": "Ближняя атака по отравителю: −1 деление шкалы, 6 урона + Яд атакующему"},
                     "mods": [{"attack_tag": "poison"}]}

# ======================= новые пути старых героев =======================
S("consecrate", skill("Освящение", "Радиус 2: союзники +20 HP, враги 14 урона.", 4, "self",
                      [{"type": "heal", "amount": 20, "radius": 2}, D(14, radius=2)], cd=8, radius=2,
                      au=auto(True, ("ally_hp_below", 70))),
  branch("Святая земля",
         tier("Святая земля", "Союзникам ещё 4 HP/сек 5 сек.", desc("Радиус 2: +20 HP и 4 HP/сек союзникам, 14 урона врагам."),
              add(buff("regen", 4, 5, radius=2))),
         tier("Благословение", "И +2 брони союзникам.", desc("Святая земля и +2 брони союзникам на 5 сек."),
              add(buff("armor", 2, 5, radius=2)))),
  branch("Кара небес",
         tier("Кара небес", "Врагам 24 урона + Огонь.", desc("Радиус 2: +20 HP союзникам, 24 урона + Огонь врагам."),
              eff("damage", set={"amount": 24, "tag": "fire"})),
         tier("Испепеление", "Враги оглушены на 1 сек.", desc("Кара небес и оглушение врагов 1 сек."),
              add({"type": "stun", "duration": 1.0, "radius": 2}))))
S("headshot", skill("В голову", "Каст 1.2 сек, дальность 8: 45 урона, ×1.5 по целям с HP < 30%.", 4, "enemy",
                    [D(45, "ranged", execute={"below": 0.3, "mult": 1.5})], rng=8, cast=1.2, cd=6, au=auto(True)),
  branch("Охотник за головами",
         tier("Охотник за головами", "55 урона.", desc("Дальность 8: 55 урона, ×1.5 по раненым."), eff("damage", set={"amount": 55})),
         tier("Контрольный", "Добивание ×2.", desc("Дальность 8: 55 урона, ×2 по целям с HP < 30%."),
              eff("damage", set={"execute": {"below": 0.3, "mult": 2.0}}))),
  branch("Подавление",
         tier("Подавление", "Быстрый выстрел (каст 0.4): 30 урона и оглушение 1.2 сек.",
              form("Подавление", "Каст 0.4 сек: 30 урона и оглушение 1.2 сек.",
                   [D(30, "ranged"), {"type": "stun", "duration": 1.2}], cast=0.4,
                   auto=auto(True, ("target_casting",)))),
         tier("Прибить к земле", "И замедление 4 сек.", desc("30 урона, оглушение 1.2 сек, замедление 4 сек."),
              eff("damage", set={"on_hit_buff": {"stat": "slow", "value": 1.6, "duration": 4}}))))
S("blizzard", skill("Буран", "Каст 1.2 сек, радиус 1: 20 урона + Лёд, ледяные клетки 5 сек.", 5, "cell",
                    [D(20, radius=1, tag="ice"), {"type": "cell_tag", "tag": "ice", "radius": 1},
                     {"type": "hazard", "hazard": "ice", "duration": 5, "radius": 1}],
                    rng=5, cast=1.2, cd=4, radius=1, au=auto(True, ("enemies_in_area", 2))),
  branch("Вечная мерзлота",
         tier("Вечная мерзлота", "Ледяные клетки 8 сек.", desc("Радиус 1: 20 урона + Лёд, ледяные клетки 8 сек."),
              eff("hazard", set={"duration": 8})),
         tier("Ледник", "Радиус 2.", desc("Радиус 2: 20 урона + Лёд, ледяные клетки 8 сек.", radius=2), {"radius_add": 1})),
  branch("Ледяная игла",
         tier("Ледяная игла", "Одна цель: 40 урона + Лёд, каст 0.8.",
              form("Ледяная игла", "Враг (дальность 5): каст 0.8, 40 урона + Лёд.", [D(40, tag="ice")],
                   target="enemy", radius=0, cast=0.8, auto=auto(True))),
         tier("Абсолютный ноль", "×2 по замороженным/оглушённым — оглушение 1 сек.",
              desc("Враг: 40 урона + Лёд и оглушение 1 сек."), add({"type": "stun", "duration": 1.0}))))
S("revive", skill("Воскрешение", "Каст 2 сек: поднимает павшего союзника (до 3 клеток) с 35% HP. Перезарядка 40.", 6, "cell",
                  [{"type": "revive", "pct": 0.35, "radius": 1}], rng=3, cast=2.0, cd=40, au=auto(True)),
  branch("Второе дыхание",
         tier("Второе дыхание", "С 55% HP.", desc("Каст 2 сек: павший союзник встаёт с 55% HP."),
              eff("revive", set={"pct": 0.55})),
         tier("Чудо", "Перезарядка 25.", desc("Каст 2 сек: павший союзник встаёт с 55% HP. Перезарядка 25.", cooldown=25))),
  branch("Быстрая молитва",
         tier("Быстрая молитва", "Каст 0.8 сек, 30% HP.", desc("Каст 0.8 сек: павший союзник встаёт с 30% HP.", cast=0.8),
              eff("revive", set={"pct": 0.3})),
         tier("Ангел-хранитель", "Воскрешённый получает щит 40.", desc("Каст 0.8 сек: встаёт с 30% HP и щитом 40."),
              add({"type": "shield", "amount": 40, "duration": 6, "radius": 1}))))
PATHS["paladin"] = {"class": "warrior", "name": "Паладин", "desc": "Танк-целитель. Вместо Рывка — Освящение, "
                    "вместо Блока — Святая защита.", "replace": {"charge": "consecrate"},
                    "passive": {"kind": "intercede", "name": "Святая защита", "pp": 1, "range": 1, "heal": 8,
                                "desc": "Соседа-союзника бьют: −1 деление шкалы, лечит его на 8"},
                    "mods": [{"stat": "power", "mult": 1.05}]}
PATHS["sniper"] = {"class": "archer", "name": "Снайпер", "desc": "Дальний выстрел. Вместо Отскока — В голову, "
                   "вместо Уворота — Хладнокровие, +1 дальность.", "replace": {"leap_back": "headshot"},
                   "passive": {"kind": "concentration", "name": "Хладнокровие", "pp": 1,
                               "desc": "Каст прерывают: −1 деление шкалы, каст продолжается"},
                   "mods": [{"stat": "atk_range", "add": 1}, {"stat": "move_time", "mult": 1.1}]}
PATHS["cryomancer"] = {"class": "mage", "name": "Криомант", "desc": "Мастер льда. Вместо Огненного шара — Буран, "
                       "+20 HP.", "replace": {"fireball": "blizzard"},
                       "passive": {"kind": "concentration", "name": "Ледяное спокойствие", "pp": 1,
                                   "desc": "Каст прерывают: −1 деление шкалы, каст продолжается"},
                       "mods": [{"stat": "hp", "add": 20}]}
PATHS["lifekeeper"] = {"class": "priest", "name": "Хранитель жизни", "desc": "Возвращает павших. Вместо Очищения — "
                       "Воскрешение.", "replace": {"purify": "revive"},
                       "passive": {"kind": "intercede", "name": "Заступничество", "pp": 1, "range": 1, "heal": 8,
                                   "desc": "Соседа-союзника бьют: −1 деление шкалы, лечит его на 8"},
                       "mods": [{"stat": "ap_max", "add": 1}]}

# ======================= таланты =======================
for cid, items in {
    "assassin": [("as_blades", "Острые клинки", 1, "+3 к урону атаки", [{"stat": "atk_damage", "add": 3}]),
                 ("as_poise", "Хладнокровие убийцы", 1, "Удар в спину ×1.9 вместо ×1.6",
                  [{"passive": "mult", "set": 1.9, "kind": "backstab"}]),
                 ("as_reflex", "Рефлексы", 1, "+1 деление шкалы", [{"stat": "pp_max", "add": 1}]),
                 ("as_venom", "Ядовитые клинки", 1, "Атаки с тегом Яд", [{"attack_tag": "poison"}])],
    "druid": [("dr_bark", "Дубовая кора", 1, "+2 брони", [{"stat": "armor", "add": 2}]),
              ("dr_wild", "Дикая сила", 1, "+15% сила навыков", [{"stat": "power", "mult": 1.15}]),
              ("dr_roots", "Корни", 1, "+25 HP", [{"stat": "hp", "add": 25}]),
              ("dr_spirit", "Дух леса", 1, "+1 деление шкалы", [{"stat": "pp_max", "add": 1}])],
    "guardian": [("gu_tower", "Башенный щит", 1, "+2 брони", [{"stat": "armor", "add": 2}]),
                 ("gu_long", "Длинное древко", 1, "+3 к урону атаки", [{"stat": "atk_damage", "add": 3}]),
                 ("gu_stance", "Стойкость", 1, "+1 деление шкалы", [{"stat": "pp_max", "add": 1}]),
                 ("gu_brawn", "Крепость", 1, "+30 HP", [{"stat": "hp", "add": 30}])],
    "shaman": [("sh_storm", "Грозовые атаки", 1, "Атаки с тегом Гроза", [{"attack_tag": "storm"}]),
               ("sh_focus", "Транс", 1, "+2 AP", [{"stat": "ap_max", "add": 2}]),
               ("sh_flow", "Поток стихий", 1, "AP восстанавливается на 0.8 сек быстрее", [{"stat": "ap_regen", "add": -0.8}]),
               ("sh_power", "Глас грома", 1, "+15% сила навыков", [{"stat": "power", "mult": 1.15}])],
    "bard": [("ba_voice", "Сильный голос", 1, "+15% сила навыков", [{"stat": "power", "mult": 1.15}]),
             ("ba_tempo", "Темп", 1, "AP восстанавливается на 0.7 сек быстрее", [{"stat": "ap_regen", "add": -0.7}]),
             ("ba_lute", "Лютня-кистень", 1, "+4 к урону атаки", [{"stat": "atk_damage", "add": 4}]),
             ("ba_encore", "Бис", 1, "+1 деление шкалы", [{"stat": "pp_max", "add": 1}])],
    "alchemist": [("al_pouch", "Большая сумка", 1, "+2 AP", [{"stat": "ap_max", "add": 2}]),
                  ("al_potent", "Крепкие смеси", 1, "+15% сила навыков", [{"stat": "power", "mult": 1.15}]),
                  ("al_fire", "Зажигательные снаряды", 1, "Атаки с тегом Огонь", [{"attack_tag": "fire"}]),
                  ("al_apron", "Кожаный фартук", 1, "+1 броня, +15 HP",
                   [{"stat": "armor", "add": 1}, {"stat": "hp", "add": 15}])],
}.items():
    for tid, name, cost, d, mods in items:
        TALENTS[tid] = {"class": cid, "name": name, "cost": cost, "desc": d, "mods": mods}

# ======================= призывы =======================
SUMMONS = {
    "totem_storm": {"name": "Тотем грозы", "label": "Т", "color": [110, 140, 230], "role": "ranged", "hp": 40, "armor": 1,
                    "move_time": 1.0, "attack": {"damage": 9, "range": 3, "cooldown": 1.0, "tag": "storm", "kind": "ranged"},
                    "summon": True, "static": True},
    "totem_thunder": {"name": "Тотем бури", "label": "Т", "color": [140, 120, 240], "role": "caster", "hp": 40, "armor": 1,
                      "move_time": 1.0, "attack": {"damage": 0, "range": 0, "cooldown": 9},
                      "aura": {"every": 2.0, "radius": 2, "effects": [D(10, radius=2, tag="storm")]},
                      "summon": True, "static": True},
    "totem_heal": {"name": "Тотем исцеления", "label": "Т", "color": [110, 210, 140], "role": "support", "hp": 40,
                   "armor": 1, "move_time": 1.0, "attack": {"damage": 0, "range": 0, "cooldown": 9},
                   "aura": {"every": 1.0, "radius": 2, "effects": [{"type": "heal", "amount": 5, "radius": 2}]},
                   "summon": True, "static": True},
    "totem_ward": {"name": "Тотем-страж", "label": "Т", "color": [170, 150, 120], "role": "melee", "hp": 90, "armor": 3,
                   "move_time": 1.0, "attack": {"damage": 0, "range": 0, "cooldown": 9},
                   "aura": {"every": 3.0, "radius": 2, "effects": [{"type": "taunt", "radius": 2, "duration": 3}]},
                   "summon": True, "static": True},
    "spirit_tree": {"name": "Древо жизни", "label": "Д", "color": [90, 170, 80], "role": "support", "hp": 60, "armor": 2,
                    "move_time": 1.0, "attack": {"damage": 0, "range": 0, "cooldown": 9},
                    "aura": {"every": 1.0, "radius": 2, "effects": [{"type": "heal", "amount": 7, "radius": 2}]},
                    "summon": True, "static": True},
    "ent": {"name": "Энт", "label": "Э", "color": [120, 100, 60], "role": "melee", "hp": 110, "armor": 4, "move_time": 1.0,
            "attack": {"damage": 12, "range": 1, "cooldown": 1.4},
            "aura": {"every": 3.0, "radius": 2, "effects": [{"type": "taunt", "radius": 2, "duration": 3}]},
            "summon": True, "static": True},
}

TAGS = {
    "storm": {"name": "Гроза", "short": "Г", "color": [150, 165, 255], "status": "Наэлектризован"},
    "poison": {"name": "Яд", "short": "Я", "color": [130, 210, 80], "status": "Яд: 2 урона/сек, лечение ×0.5", "dps": 2,
               "heal_mult": 0.5},
    "oil": {"name": "Масло", "short": "М", "color": [170, 130, 60], "status": "Вязкий: замедление ×1.3", "slow": 1.3},
}
REACTIONS = [
    {"id": "shock", "name": "Электрошок", "tags": ["storm", "water"], "desc": "Урон рядом и оглушение",
     "effects": [{"type": "aoe_damage", "amount": 12, "radius": 1, "affects": "target_side"},
                 {"type": "stun", "duration": 1.2}]},
    {"id": "shatter", "name": "Раскол", "tags": ["storm", "ice"], "desc": "Двойной урон",
     "effects": [{"type": "bonus_damage", "mult": 1.0, "min": 12}]},
    {"id": "overload", "name": "Перегрузка", "tags": ["storm", "fire"], "desc": "Взрыв по площади",
     "effects": [{"type": "aoe_damage", "amount": 18, "radius": 1, "affects": "target_side"}]},
    {"id": "toxic", "name": "Ядовитый дым", "tags": ["poison", "fire"], "desc": "Урон и Яд всем рядом",
     "effects": [{"type": "aoe_damage", "amount": 8, "radius": 1, "affects": "target_side"},
                 {"type": "spread_status", "tag": "poison", "radius": 1}]},
    {"id": "blaze", "name": "Пожар", "tags": ["oil", "fire"], "desc": "Двойной урон, земля горит",
     "effects": [{"type": "bonus_damage", "mult": 1.0, "min": 15},
                 {"type": "hazard", "hazard": "fire", "duration": 5, "radius": 0}]},
]
CELL_REACTIONS = [{"tag": "fire", "hazard": "oil", "name": "Масло вспыхнуло", "set_hazard": "fire", "duration": 6}]
HAZARDS = {
    "oil": {"name": "Масляная лужа", "color": [120, 92, 46], "status": "oil", "dps": 0, "foes_only": True},
    "poison": {"name": "Ядовитое облако", "color": [110, 190, 70], "status": "poison", "dps": 0, "foes_only": True},
    "briar": {"name": "Терновник", "color": [80, 120, 50], "dps": 3, "foes_only": True},
    "mine": {"name": "Мина", "color": [200, 80, 60], "trigger": {"damage": 30, "tag": "fire", "stun": 1.0}},
}


def j(v):
    return json.dumps(v, ensure_ascii=False)


def fmt_entry(key, val, kind):
    """Новая запись в стиле файла: поле — строка (навыки, классы, пути) или ступень — строка (ветки)."""
    if kind == "line":
        return f"  {j(key)}: {j(val)}"
    if kind == "branches":
        parts = []
        for b, br in val.items():
            tiers = ",\n".join(f"      {j(t)}" for t in br["tiers"])
            parts.append(f'    {j(b)}: {{"name": {j(br["name"])}, "tiers": [\n{tiers}]}}')
        return f"  {j(key)}: {{\n" + ",\n".join(parts) + "\n  }"
    rows = ",\n".join(f"    {j(k)}: {j(v)}" for k, v in val.items())
    return f"  {j(key)}: {{\n{rows}\n  }}"


def write(path, text):
    json.loads(text)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def upsert(name, entries, kind):
    """Как append, но записи с теми же id заменяются (генератор можно перезапускать после правок)."""
    path = os.path.join(DATA, name)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    have = json.loads(text)
    for k, v in entries.items():
        if k not in have:
            continue
        head = f"\n  {j(k)}: "
        i = text.index(head) + 1
        if text[i + len(head) - 1:].startswith("{\n"):     # многострочная запись — до закрывающей «  }»
            end = text.index("\n  }", i) + 4
        else:
            end = text.index("\n", i)
            if text[end - 1] == ",":
                end -= 1
        text = text[:i] + fmt_entry(k, v, kind) + text[end:]
    write(path, text)
    append(name, entries, kind)


def append(name, entries, kind):
    """Дописывает записи перед закрывающей скобкой файла, не трогая остальное оформление."""
    path = os.path.join(DATA, name)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    have = json.loads(text)
    new = [fmt_entry(k, v, kind) for k, v in entries.items() if k not in have]
    if not new:
        return
    body = text.rstrip()
    assert body.endswith("}")
    body = body[:-1].rstrip()
    sep = "," if body != "{" else ""
    write(path, body + sep + "\n" + ",\n".join(new) + "\n}\n")


def main():
    append("skills.json", SKILLS, "fields")
    append("branches.json", BRANCHES, "branches")
    append("classes.json", CLASSES, "fields")
    append("paths.json", PATHS, "fields")
    append("talents.json", TALENTS, "line")
    if not os.path.exists(os.path.join(DATA, "summons.json")):
        write(os.path.join(DATA, "summons.json"), "{}\n")
    append("summons.json", SUMMONS, "fields")
    append("tags.json", TAGS, "line")
    path = os.path.join(DATA, "reactions.json")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if '"shock"' not in text:
        i = text.index('"cell"')
        head = text[:i].rstrip()
        assert head.endswith("],")
        head = head[:-2].rstrip()
        rx = "".join(",\n    " + j(r) for r in REACTIONS)
        text = head + rx + "\n  ],\n  " + text[i:]
        k = text.index("[", text.index('"cell"')) + 1
        text = text[:k] + "\n    " + j(CELL_REACTIONS[0]) + "," + text[k:]
        write(path, text)
    path = os.path.join(DATA, "config.json")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if '"briar"' not in text:
        anchor = '"ice": {"name": "Лёд", "color": [170, 225, 245], "status": "ice", "dps": 0}'
        assert text.count(anchor) == 1
        hz = "".join(f",\n    {j(k)}: {j(v)}" for k, v in HAZARDS.items())
        write(path, text.replace(anchor, anchor + hz))


if __name__ == "__main__":
    main()
