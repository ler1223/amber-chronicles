"""Глава 3 «Склеп нежити»: данные похода (acts, events, curses, uniques).

Запуск: python tools/content_expedition_crypt.py
Файл data/expedition_crypt.json перезаписывается; общие data/encounters.json и
data/enemies.json только читаются.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def dump(name, obj):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def event(title, kind, acts, weight, steps, once=True, requires=None):
    e = {"title": title, "kind": kind, "acts": acts, "weight": weight, "steps": steps}
    if once is not None:
        e["once"] = once
    if requires:
        e["requires"] = requires
    return e


def opt(text, do=None, result=None, check=None, success=None, fail=None, requires=None):
    o = {"text": text}
    if requires:
        o["requires"] = requires
    if check:
        o["check"] = check
    if success:
        o["success"] = success
    if fail:
        o["fail"] = fail
    if do is not None:
        o["do"] = do
    if result:
        o["result"] = result
    return o


def main():
    encounters = [e for e in load("encounters.json") if e.get("chapter") == "crypt"]
    enemies = load("enemies.json")
    enemy_keys = ["skeleton", "skeleton_archer", "ghoul", "necromancer", "banshee",
                  "bone_golem", "wraith", "death_knight", "lich", "crypt_abbot", "crypt_warden"]
    # Склеп — глава про подъём нежити: чуть меньше HP/урона, чтобы огонь и добивание
    # оставались главным ответом, а не обязательным условием прохождения.
    crypt_enemies = {}
    for key in enemy_keys:
        if key not in enemies:
            continue
        e = json.loads(json.dumps(enemies[key]))
        e["hp"] = max(1, int(round(e["hp"] * 0.8)))
        e["attack"]["damage"] = round(e["attack"]["damage"] * 0.85, 1)
        if e.get("undying"):
            e["undying"]["hp"] = 0.25
            e["undying"]["delay"] = 4
        crypt_enemies[key] = e

    events = {
        "abandoned_camp": event(
            "Забытый привал", "short", [1, 2, 3], 1,
            {"start": {"text": "Под сводами — старый привал: угли, циновки и чьи-то кости. "
                               "Мёртвые не тронули это место, и это само по себе тревожит.",
                       "options": [
                           opt("Отдохнуть у углей", [{"heal": 0.2}],
                               "Короткий сон без снов. Пока что."),
                           opt("Обыскать тайник", [{"gold": 15}, {"mat": "herbs", "add": 1}],
                               "Под циновкой — завёрнутые в тряпку травы и горсть монет."),
                           opt("Идти дальше", [], "Вы не остаётесь там, где умерли другие."),
                       ]}},
            once=False),

        "hungry_spirit": event(
            "Голодный дух", "short", [1, 2, 3], 8,
            {"start": {"text": "У стены сидит полупрозрачный старик. Он не поднимает глаз: "
                               "«Тепла... хоть немного тепла. Я не помню, когда ел последний раз».",
                       "options": [
                           opt("Отдать свою кровь", [{"hurt": 0.12, "who": "hero"}, {"xp": 45},
                                                      {"rep": "dead", "add": 2}],
                               "Дух жадно ловит капли. В благодарность он шепчет забытое имя."),
                           opt("Оставить травы (2)", [{"mat": "herbs", "add": -2}, {"heal": 0.12},
                                                      {"rep": "dead", "add": 1}],
                               "Старик нюхает травы и улыбается: «Пахнет солнцем».",
                               requires={"mat_at_least": {"herbs": 2}}),
                           opt("Развеять духа", [{"battle": "crypt_0",
                                                  "after": [{"mat": "bonedust", "add": 1}]},
                                                 {"rep": "dead", "add": -2}],
                               "Старик рассыпается пылью. Кости под ним приходят в движение."),
                       ]}}),

        "priest_wisps": event(
            "Огоньки жреца", "short", [1, 2], 8,
            {"start": {"text": "Над могилами пляшут бледные огоньки. Один из них вспыхивает ярче "
                               "и уходит вглубь, оставляя за собой цепочку искр.",
                       "options": [
                           opt("Идти за огоньком",
                               check={"attr": "int", "dc": 13},
                               success={"text": "Огонёк выводит к тайнику, а не в трясину.",
                                        "do": [{"gold": 40}, {"mat": "gems", "add": 2}]},
                               fail={"text": "Огонёк обманывает: под ногами — гнилая доска.",
                                     "do": [{"hurt": 0.15}, {"curse": "grave_chill"}]}),
                           opt("Разогнать огоньки", [{"battle": "crypt_1", "after": [{"xp": 30}]}],
                               "Огоньки гаснут, но из гробов поднимаются те, кому они светили."),
                           opt("Обойти стороной", [], "Вы не доверяете огню в месте, где нет тепла."),
                       ]}}),

        "fog_voices": event(
            "Голоса в тумане", "short", [1, 2, 3], 9,
            {"start": {"text": "Туман сгущается. В нём звучат голоса: одни зовут по имени, другие "
                               "просят не идти дальше. Ни у одного нет лица.",
                       "options": [
                           opt("Слушать и запоминать",
                               check={"attr": "int", "dc": 14},
                               success={"text": "Голоса складываются в историю этого места.",
                                        "do": [{"xp": 50}, {"flag": "fog_heard"}]},
                               fail={"text": "Один голос оказывается слишком близко.",
                                     "do": [{"hurt": 0.2}, {"curse": "soul_rot"}]}),
                           opt("Заткнуть уши и идти", [{"heal": 0.05}],
                               "Вы идёте на звук собственного дыхания."),
                           opt("Крикнуть в туман", [{"battle": "crypt_3", "after": [{"xp": 35}]}],
                               "Туман отвечает лязгом костей."),
                       ]}}),

        "room_cemetery": event(
            "Кладбище под сводами", "short", [1, 2, 3], 8,
            {"start": {"text": "Ряды могил вырублены прямо в камне. На плитах — имена, стёртые "
                               "до неузнаваемости. Одна могила свежая.",
                       "options": [
                           opt("Раскопать свежую могилу",
                               check={"attr": "str", "dc": 13},
                               success={"text": "В гробу — вещь, которую покойный не забрал.",
                                        "do": [{"item": {"slot": "weapon"}}]},
                               fail={"text": "Крышка срывается, и из щели тянется холод.",
                                     "do": [{"hurt": 0.12}, {"curse": "grave_chill"}]}),
                           opt("Почтить память", [{"rep": "order", "add": 2}, {"heal": 0.1}],
                               "Вы читаете имена вслух. Тишина становится чуть добрее."),
                           opt("Сжечь кости", [{"rep": "order", "add": -2}, {"mat": "bonedust", "add": 2}],
                               "Огонь очищает, но Орден не одобрил бы такого погребения."),
                       ]}}),

        "sunken_chapel": event(
            "Затонувшая часовня", "short", [1, 2], 8,
            {"start": {"text": "Часовня ушла под землю вместе с колоколом. Алтарь ещё стоит, "
                               "а на нём — чаша, покрытая зелёной патиной.",
                       "options": [
                           opt("Помолиться", [{"heal": 0.3}, {"rep": "order", "add": 2}],
                               "Тихая молитва в мёртвом месте. Кто-то слушает."),
                           opt("Вскрыть раку", [{"item": {"slot": "armor"}}, {"curse": "grave_chill"}],
                               "Доспех святого тяжёл, а холод не отступает."),
                           opt("Осквернить алтарь", [{"battle": "crypt_6"},
                                                     {"rep": "order", "add": -3},
                                                     {"mat": "bonedust", "add": 2}],
                               "Патина трескается. Часовня отвечает хором мёртвых."),
                           opt("Осмотреть алтарь", [{"add_node": {"event": "sunken_chapel.altar",
                                                                  "label": "Алтарь часовни",
                                                                  "ahead": 2, "in_act": 2}}],
                               "За алтарём — узкий проход, которого не было на плане."),
                       ]}}),

        "sunken_chapel.altar": event(
            "Алтарь часовни", "thread", [], 40,
            {"start": {"text": "Внутри алтаря — ниша с чашей и свечой. Свеча не гаснет, хотя "
                               "воздуха здесь нет уже сотни лет.",
                       "options": [
                           opt("Зажечь свечу", [{"heal": 0.2},
                                                {"boss_mod": {"name": "Освящённый алтарь: Лич слабее",
                                                              "good": True, "hp": 0.9}}],
                               "Свеча горит ровно. Тьма вокруг становится менее плотной."),
                           opt("Забрать чашу", [{"item": {"unique": "crypt_grail"}},
                                                {"curse": "soul_rot"}],
                               "Чаша холодна, как лёд, и не пуста."),
                           opt("Разбить алтарь", [{"battle": "crypt_4"}, {"mat": "bonedust", "add": 3}],
                               "Камень лопается. Из трещин выходят рыцари, которых здесь не хоронили."),
                       ]}}),

        "sunken_library": event(
            "Затонувшая библиотека", "short", [1, 2, 3], 7,
            {"start": {"text": "Стеллажи уходят в темноту. Книги разбухли от сырости, но некоторые "
                               "ещё можно открыть. На столе — свежие заметки.",
                       "options": [
                           opt("Читать заметки", [{"xp": 60}, {"flag": "library_read"}],
                               "Кто-то уже пытался понять, как остановить подъём мёртвых."),
                           opt("Забрать книги", [{"item": {"slot": "weapon"}}, {"curse": "brittle_bone"}],
                               "Переплёты окованы серебром. Серебро здесь не любят."),
                           opt("Сжечь библиотеку", [{"rep": "order", "add": 2},
                                                    {"battle": "crypt_2", "after": [{"mat": "gems", "add": 1}]}],
                               "Огонь съедает страницы. Из дыма поднимаются хозяева книг."),
                       ]}}),

        "old_armory": event(
            "Оружейная склепа", "scene", [1, 2, 3], 7,
            {"start": {"text": "За печатью — оружейная. Стойки истлели, но клинки и доспехи "
                               "ещё держатся на крючьях.",
                       "options": [
                           opt("Взять клинок", [{"item": {"slot": "weapon"}}],
                               "Сталь холодная, но рука её узнаёт."),
                           opt("Взять доспех", [{"item": {"slot": "armor"}}],
                               "Тяжёлый доспех пахнет землёй."),
                           opt("Сгрести всё", [{"item": {"slot": "weapon"}},
                                               {"item": {"slot": "armor"}},
                                               {"curse": "grave_chill"}],
                               "Печать ломается. Холод склепа цепляется за металл."),
                       ]}}),

        "idol": event(
            "Костяной идол", "short", [1, 2, 3], 7,
            {"start": {"text": "В нише сидит идол, сложенный из чужих костей. В глазницах — "
                               "две монеты, и одна из них всё ещё блестит.",
                       "options": [
                           opt("Отдать кровь", [{"hurt": 0.2},
                                                {"perk": {"name": "Дар костяного идола",
                                                          "desc": "+8% урона атак",
                                                          "mods": [{"stat": "atk_damage", "mult": 1.08}]}}],
                               "Идол принимает капли. Рука становится тяжелее и точнее."),
                           opt("Разбить идола", [{"battle": "crypt_4"}, {"mat": "bonedust", "add": 2}],
                               "Кости разлетаются. Пустая ниша смотрит, как вы уходите."),
                           opt("Унести идола", [{"item": {"unique": "crypt_idol"}},
                                                {"curse": "death_mark"}],
                               "Идол не тяжелее ребёнка, но руки немеют."),
                       ]}}),

        "mirror_pool": event(
            "Зеркальный водоём", "short", [2, 3], 7,
            {"start": {"text": "В затопленном зале — чёрная вода. В ней отражается не потолок, "
                               "а вы, но чуть иначе.",
                       "options": [
                           opt("Испить воды", [{"heal": 0.4}, {"curse": "soul_rot"}],
                               "Вода холодная и сладкая. Отражение улыбается первым."),
                           opt("Разбить отражение", [{"battle": "crypt_3"}, {"mat": "gems", "add": 2}],
                               "Вода вспыхивает осколками. Отражение кричит вашим голосом."),
                           opt("Спросить отражение",
                               check={"attr": "int", "dc": 13},
                               success={"text": "Отражение отвечает шёпотом о том, что ждёт впереди.",
                                        "do": [{"xp": 50}]},
                               fail={"text": "Отражение смеётся и не отпускает взгляд.",
                                     "do": [{"hurt": 0.1}, {"curse": "soul_rot"}]}),
                       ]}}),

        "plague_village": event(
            "Чумная деревня", "short", [1, 2], 7,
            {"start": {"text": "Дома стоят нетронутыми, но ни в одном нет живых. На дверях — "
                               "меловые кресты, а в колодце — тела.",
                       "options": [
                           opt("Лечить выживших (травы 3)", [{"mat": "herbs", "add": -3},
                                                              {"rep": "order", "add": 2}, {"xp": 40}],
                               "В подвале церкви — дети. Они ещё дышат.",
                               requires={"mat_at_least": {"herbs": 3}}),
                           opt("Сжечь заражённых", [{"battle": "crypt_5"},
                                                    {"rep": "order", "add": -1},
                                                    {"mat": "bonedust", "add": 2}],
                               "Огонь идёт по улицам. Мёртвые не благодарят."),
                           opt("Уйти", [], "Вы не приносите с собой ни надежды, ни заразы."),
                       ]}}),

        "fog_doubles": event(
            "Двойники в тумане", "short", [2, 3], 7,
            {"start": {"text": "Из тумана выходят точные копии отряда. Они молчат и идут "
                               "ровным шагом, не поднимая оружия.",
                       "options": [
                           opt("Атаковать первыми", [{"battle": "crypt_4", "after": [{"xp": 40}]}],
                               "Копии рассыпаются, но одна из них успевает улыбнуться."),
                           opt("Заговорить с ними",
                               check={"attr": "int", "dc": 14},
                               success={"text": "Двойники отвечают хором: «Мы — то, что вы оставили».",
                                        "do": [{"xp": 50}]},
                               fail={"text": "Они говорят вашими голосами слишком долго.",
                                     "do": [{"curse": "soul_rot"}]}),
                           opt("Отступить", [{"hurt": 0.1}],
                               "Туман провожает вас смехом."),
                       ]}}),

        "sunken_chapel.belfry": event(
            "Колокольня", "short", [1, 2], 7,
            {"start": {"text": "Колокол висит над провалом. Верёвка истлела, но язык колокола "
                               "ещё качается, хотя ветра нет.",
                       "options": [
                           opt("Ударить в колокол", [{"battle_mod": {"name": "Звон колокола: враги слабее",
                                                                     "battles": 2, "dmg": 0.9, "good": True}},
                                                     {"rep": "order", "add": 1}],
                               "Звон идёт по костям. Мёртвые на миг замедляются."),
                           opt("Срезать верёвку", [{"rep": "order", "add": -1}, {"mat": "ore", "add": 2}],
                               "Колокол падает в провал. Металл ещё пригодится."),
                           opt("Слушать звон", [{"xp": 35}, {"heal": 0.1}],
                               "В звоне слышится имя, которое вы уже слышали в тумане."),
                       ]}}),

        "sunken_chest": event(
            "Мокрый сундук", "short", [1, 2, 3], 7,
            {"start": {"text": "Сундук стоит в луже чёрной воды. Замок покрыт солью, а крышка "
                               "приоткрыта на палец.",
                       "options": [
                           opt("Открыть замок",
                               check={"attr": "agi", "dc": 13},
                               success={"text": "Замок поддаётся. Внутри — то, что не успели забрать.",
                                        "do": [{"item": {"slot": "weapon"}}]},
                               fail={"text": "Игла в замке входит под ноготь.",
                                     "do": [{"hurt": 0.1}, {"curse": "death_mark"}]}),
                           opt("Разбить крышку", [{"item": {"slot": "armor"}}, {"hurt": 0.1}],
                               "Крышка ломается. Внутри — доспех, но руки дрожат."),
                           opt("Оставить", [], "Некоторые вещи лучше не будить."),
                       ]}}),

        "order_toll": event(
            "Патруль Ордена", "short", [1, 2, 3], 12,
            {"start": {"text": "Из бокового коридора выходят трое в белых накидках. «Пошлина Ордена. "
                               "Золото, кости или объяснение, почему вы здесь».",
                       "options": [
                           opt("Заплатить (30 золота)", [{"pay": 30}],
                               "Патруль считает монеты и уходит.",
                               requires={"gold": 30}),
                           opt("Отдать кости (2)", [{"mat": "bonedust", "add": -2},
                                                     {"rep": "order", "add": 1}],
                               "Орден забирает кости для освящения.",
                               requires={"mat_at_least": {"bonedust": 2}}),
                           opt("Отказаться", [{"battle": "crypt_5"}, {"rep": "order", "add": -2}],
                               "Накидки падают. Под ними — те же кости, что и у всех здесь."),
                       ]}},
            once=False),

        "final_vigil": event(
            "Последняя ночь", "scene", [3], 10,
            {"start": {"text": "До трона лича — один переход. Кто-то должен не спать и следить "
                               "за туманом, пока остальные отдыхают.",
                       "options": [
                           opt("Провести ночь в молитве", [{"heal": 0.5},
                                                           {"boss_mod": {"name": "Ночная молитва: Лич слабее",
                                                                         "good": True, "hp": 0.9}}],
                               "Свечи горят до утра. Туман не подходит близко."),
                           opt("Смазать оружие (травы 2)", [{"mat": "herbs", "add": -2},
                                                            {"battle_mod": {"name": "Святая мазь: урон выше",
                                                                            "battles": 1, "dmg": 1.15,
                                                                            "good": True}}],
                               "Травы пахнут живым. Сталь становится светлее.",
                               requires={"mat_at_least": {"herbs": 2}}),
                           opt("Пожертвовать золото (60)", [{"gold": -60}, {"xp": 60},
                                                            {"boss_mod": {"name": "Щедрая жертва: Лич слабее",
                                                                          "good": True, "hp": 0.85}}],
                               "Монеты уходят в трещины пола. Кто-то принимает дар.",
                               requires={"gold": 60}),
                       ]}}),

        "lich_phylactery": event(
            "Филактерия", "thread", [3], 9,
            {"start": {"text": "В стене тронного зала — ниша, забранная серебром. За ней бьётся "
                               "что-то маленькое и живое. Лич не был бы личом без такой вещи.",
                       "options": [
                           opt("Найти и вскрыть нишу",
                               check={"attr": "int", "dc": 15},
                               success={"text": "Серебро поддаётся. Филактерия трескается.",
                                        "do": [{"boss_mod": {"name": "Филактерия разбита: Лич слабее",
                                                              "good": True, "hp": 0.8}}]},
                               fail={"text": "Ниша захлопывается, и холод бьёт по рукам.",
                                     "do": [{"hurt": 0.15},
                                            {"boss_mod": {"name": "Филактерия цела: Лич сильнее",
                                                          "good": False, "hp": 1.15}}]}),
                           opt("Оставить нишу", [], "Вы запоминаете место. Возможно, это уже немало."),
                       ]}}),
    }

    uniques = {
        "soulflame_blade": {
            "name": "Клинок души", "base": "blade", "chapter": "crypt",
            "desc": "Удары поджигают врага (30%); +35% урона атак",
            "stats": [{"stat": "atk_damage", "pct": 0.35}],
            "rules": [{"trigger": "hit", "chance": 0.3, "do": ["ignite"]}],
        },
        "grave_ward": {
            "name": "Могильный страж", "base": "plate", "chapter": "crypt",
            "desc": "Когда ранен — щит 15% здоровья (раз в 6 сек); +35% здоровья",
            "stats": [{"stat": "hp", "pct": 0.35}],
            "rules": [{"trigger": "hurt", "chance": 1.0, "icd": 6.0, "do": ["ward"]}],
        },
        "bone_bow": {
            "name": "Костяной лук", "base": "bow", "chapter": "crypt",
            "desc": "Стрелы вызывают кровотечение (35%); +30% урона атак",
            "stats": [{"stat": "atk_damage", "pct": 0.3}],
            "rules": [{"trigger": "hit", "chance": 0.35, "do": ["bleed"]}],
        },
        "lich_crown": {
            "name": "Венец лича", "base": "charm", "chapter": "crypt",
            "desc": "Удары обжигают холодом (25%); +30% силы навыков",
            "stats": [{"stat": "power", "pct": 0.3}],
            "rules": [{"trigger": "hit", "chance": 0.25, "do": ["frostbite"]}],
        },
        "crypt_grail": {
            "name": "Чаша из склепа", "base": "charm", "chapter": "crypt",
            "desc": "Когда ранен — лечит 8% здоровья (раз в 8 сек); +25% силы навыков",
            "stats": [{"stat": "power", "pct": 0.25}, {"stat": "hp", "pct": 0.1}],
            "rules": [{"trigger": "hurt", "chance": 1.0, "icd": 8.0, "do": ["mend"]}],
        },
        "crypt_idol": {
            "name": "Костяной идол", "base": "idol", "chapter": "crypt",
            "desc": "Удары отравляют (25%); +20% силы навыков, +10% урона атак",
            "stats": [{"stat": "power", "pct": 0.2}, {"stat": "atk_damage", "pct": 0.1}],
            "rules": [{"trigger": "hit", "chance": 0.25, "do": ["venom"]}],
        },
    }

    curses = {
        "grave_chill": {"name": "Могильный холод", "desc": "Отряд: −10% здоровья",
                        "mods": [{"stat": "hp", "mult": 0.9}]},
        "soul_rot": {"name": "Гниение души", "desc": "Отряд: −12% силы навыков",
                     "mods": [{"stat": "power", "mult": 0.88}]},
        "brittle_bone": {"name": "Хрупкие кости", "desc": "Отряд: −2 брони",
                         "mods": [{"stat": "armor", "add": -2}]},
        "death_mark": {"name": "Метка смерти", "desc": "Отряд: −10% урона атак",
                       "mods": [{"stat": "atk_damage", "mult": 0.9}]},
    }

    acts = [
        {
            "name": "Акт I. Ограда кладбища",
            "art": "crypt_act_0",
            "difficulty": "normal",
            "intro": "За воротами кладбища воздух становится тяжёлым. Туман прячет ряды могил, "
                     "а под землёй уже кто-то пересчитывает кости.",
            "weights": {"battle": 34, "event": 30, "elite": 9, "shop": 6, "camp": 10},
            "rest": ["camp", "shop"],
            "pools": {"battle": ["crypt_0", "crypt_1"],
                      "elite": ["crypt_4"]},
            "boss": "crypt_7",
            "arena": [],
        },
        {
            "name": "Акт II. Затонувшая часовня",
            "art": "crypt_act_1",
            "difficulty": "heroic",
            "intro": "Часовня ушла под землю вместе с колоколом. Мёртвые ждут, пока их окликнут, "
                     "а туман становится всё гуще.",
            "weights": {"battle": 34, "event": 30, "elite": 9, "shop": 6, "camp": 10},
            "rest": ["camp", "shop"],
            "pools": {"battle": ["crypt_2", "crypt_3", "crypt_6", "crypt_5"],
                      "elite": ["crypt_4"]},
            "boss": "crypt_8",
            "arena": [],
        },
        {
            "name": "Акт III. Трон лича",
            "art": "crypt_act_2",
            "difficulty": "nightmare",
            "intro": "Туман расступается перед тронным залом. На троне сидит тот, кто не умирал, "
                     "и он уже знает ваши имена.",
            "weights": {"battle": 34, "event": 30, "elite": 9, "shop": 6, "camp": 10},
            "rest": ["camp", "shop"],
            "pools": {"battle": ["crypt_2", "crypt_3", "crypt_6", "crypt_5"],
                      "elite": ["crypt_4"]},
            "boss": "crypt_9",
            "arena": [],
        },
    ]

    chapter = {
        "_note": "Глава 3 «Склеп нежити». Данные похода: acts, events, curses, uniques. "
                 "Общие встречи и враги лежат в data/encounters.json и data/enemies.json; "
                 "enemies — ослабленные копии для главы (см. tools/content_expedition_crypt.py).",
        "name": "Склеп нежити",
        "trade_faction": "order",
        "factions": {
            "order": "Орден Света",
            "dead": "Мёртвые",
            "ghouls": "Упыри",
            "cult": "Культ Лича",
        },
        "mats": {
            "ore": {"name": "Железная руда", "color": [170, 150, 140]},
            "herbs": {"name": "Травы", "color": [120, 200, 110]},
            "gems": {"name": "Самоцветная крошка", "color": [170, 140, 255]},
            "bonedust": {"name": "Костяная пыль", "color": [210, 205, 185],
                         "desc": "Редкий материал Склепа: элита и боссы"},
        },
        "mechanics": {},
        "boss_rules": [],
        "curses": curses,
        "acts": acts,
        "enemies": crypt_enemies,
        "encounters": encounters,
        "uniques": uniques,
        "events": events,
    }

    dump("expedition_crypt.json", chapter)
    print(f"expedition_crypt.json: {len(events)} events, {len(uniques)} uniques, "
          f"{len(encounters)} encounters, {len(chapter['enemies'])} enemies")


if __name__ == "__main__":
    main()
