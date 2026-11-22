"""Глава 2 «Спуска» — Огненные кузни (перенос из экспедиции: data/expedition_forge.json — враги, карты полей,
три акта). Квиз 2026-11-21: главы берём из экспедиции; враги агрессивнее (ближние наступают в любой ход, щит —
вместе с ударом), разнообразнее.

Пишет в data/deck/enemies.json: врагов кузни, главу «Огненные кузни» в список глав (chapters: болото, кузни);
спуск идёт подряд — этажи 4–6 после Квакса. Сначала — tools/descent_chapter1.py (глава 1), затем этот.

Запуск: python tools/descent_chapter2.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from descent_chapter1 import K, M, S, Z  # noqa: E402

D = os.path.join(ROOT, "data", "deck")


def B(name, dmg, n, **kw):
    """Удар и щит себе (вместо пустого «щита на себя»)."""
    return M(name, dmg, add=[{"op": "block", "n": n}], **kw)


BURN = [{"op": "burn", "n": 2}]

ENEMIES = {
    # ---------- этаж 4: Шлаковые отвалы ----------
    "slag_slave": dict(name="Раб-шлаковщик", sprite="slag_slave", hp=16, speed=3,
                       cycle=[M("Удар киркой", 6), M("Бросок шлака", 5, add=BURN)],
                       about="Измождённый, но идёт напролом. Шлак обжигает."),
    "ember_hound": dict(name="Угольный пёс", sprite="ember_hound", hp=18, speed=4,
                        cycle=[M("Огненная пасть", 6, add=BURN), K("charge", "Прыжок", dmg=8, range=5, push=1)],
                        about="Быстрый: кусает с горением, прыгает по линии."),
    "hammer_thrower": dict(name="Метатель молотов", sprite="hammer_thrower", hp=20, speed=3, keep_range=3,
                           cycle=[S("Бросок молота", 7, 5, add=[{"op": "push", "n": 1}]), K("aim", "Замах", mult=2),
                                  S("Тяжёлый бросок", 8, 5)],
                           about="Стоит и мечет молоты на 5 клеток: толчок, после замаха — вдвое."),
    "fire_imp": dict(name="Огненный бес", sprite="fire_imp", hp=10, speed=4, small=True,
                     cycle=[M("Когти", 4, add=BURN), M("Подпалить", 3, add=[{"op": "burn", "n": 3}])],
                     on_death={"fire_cell": True}, about="Мелкий и злой: поджигает, при смерти — горящая клетка."),
    "bellows_keeper": dict(name="Мехоносец", sprite="bellows_keeper", hp=24, speed=2,
                           cycle=[K("rally", "Раздуть жар", n=1, r=3, vfx="e_war_cry"),
                                  Z("Горячий поток", 6, 1, hazard="fire", range=5, vfx="e_flame_breath"),
                                  B("Удар мехами", 5, 5)],
                           about="Раздувает жар: сила соседям, огненный поток оставляет пламя на клетках."),
    "chain_smith": dict(name="Цепной кузнец", sprite="chain_smith", hp=40, speed=3,
                        cycle=[K("pull", "Цепь", dmg=6, range=4, n=2, vfx="e_lash"), M("Молот", 10),
                               B("Цепная рубаха", 6, 6)],
                        about="Притягивает цепью и бьёт молотом. Цепная рубаха — щит после удара."),
    # ---------- этаж 5: Литейные цеха ----------
    "cinder_caster": dict(name="Литейщица", sprite="cinder_caster", hp=20, speed=2, keep_range=3,
                          cycle=[Z("Плеск расплава", 7, 1, hazard="fire", range=6, vfx="fire_bomb"),
                                 S("Капля металла", 6, 5, add=BURN)],
                          about="Плещет расплав по зоне — клетки горят; капли металла жгут."),
    "magma_golem": dict(name="Магмовый голем", sprite="magma_golem", hp=34, speed=2,
                        cycle=[M("Магмовый кулак", 9, add=BURN), B("Остывшая корка", 6, 7)],
                        on_death={"fire_cell": True}, about="Медленный и тяжёлый, бьёт расплавом."),
    "obsidian_guard": dict(name="Обсидиановый страж", sprite="obsidian_guard", hp=30, speed=2,
                           cycle=[K("guard", "Обсидиановая стена", n=6, r=2, vfx="shield_wall"), M("Стеклянный клинок", 9)],
                           about="Прикрывает своих щитом и режет обсидианом."),
    "salamander": dict(name="Саламандра", sprite="salamander", hp=22, speed=4,
                       cycle=[K("charge", "Огненный рывок", dmg=8, range=5, push=1), M("Хвост", 6, add=BURN)],
                       about="Рывок по линии, хвост поджигает."),
    "crucible_golem": dict(name="Тигельный голем", sprite="crucible_golem", hp=74, speed=2, elite=True,
                           cycle=[M("Тигельный удар", 12), Z("Опрокинуть тигель", 10, 1, hazard="fire", range=4,
                                                             vfx="lava_vent"), B("Кованый корпус", 8, 10)],
                           on_death={"explode": {"dmg": 8, "r": 1}},
                           about="Элита. Опрокидывает тигель — расплав на клетках. При гибели взрывается."),
    "free_golem": dict(name="Вольный голем", sprite="free_golem", hp=60, speed=2, elite=True, cap=10,
                       cycle=[M("Каменный кулак", 11), K("charge", "Таран", dmg=10, range=4, push=2), M("Сокрушить", 13)],
                       about="Элита. Каменная шкура: от удара — не больше 10. Таранит по линии."),
    # ---------- этаж 6: Сердце горна ----------
    "cult_zealot": dict(name="Фанатик пламени", sprite="cult_zealot", hp=22, speed=3,
                        cycle=[M("Огненный кинжал", 7, add=BURN), K("rally", "Экстаз", n=1, r=0), M("Самосожжение", 10)],
                        about="Распаляет себя (сила) и режет огнём."),
    "flame_priest": dict(name="Жрец пламени", sprite="flame_priest", hp=22, speed=2, keep_range=4,
                         cycle=[K("heal", "Пламя очищения", n=8, vfx="e_heal"),
                                Z("Огненный круг", 7, 1, hazard="fire", range=6, vfx="flame_wall"),
                                K("hex", "Клеймо культа", n=1)],
                         about="Лечит своих, ставит огненный круг, клеймом отнимает карту на ход."),
    "ash_wraith": dict(name="Пепельный дух", sprite="ash_wraith", hp=18, speed=4, keep_range=3,
                       cycle=[K("roar", "Вой пепла", weak=1, r=4, vfx="e_wail"), S("Пепельный сгусток", 6, 5),
                              K("veil", "Раствориться в пепле")],
                       about="Воет (слабость), швыряет пепел, растворяется — издали не достать."),
    "living_lava": dict(name="Живая лава", sprite="living_lava", hp=26, speed=2,
                        cycle=[M("Обжечь", 7, add=[{"op": "burn", "n": 3}]), M("Растечься", 6, add=BURN)],
                        on_death={"explode": {"dmg": 6, "r": 1}, "fire_cell": True},
                        about="Жжёт. При гибели взрывается и оставляет пламя."),
    "smith_ghost": dict(name="Безымянный кузнец", sprite="smith_ghost", hp=80, speed=3, elite=True,
                        cycle=[M("Призрачный молот", 13), K("hex", "Забытая клятва", n=1, weak=1, r=5, vfx="e_wail"),
                               K("charge", "Шаг сквозь горн", dmg=11, range=5, push=1), K("veil", "Остывший горн")],
                        about="Элита. Сквозь горн — рывок, клятва отнимает карту и силу."),
    "ash_wyrm": dict(name="Пепельный змей", sprite="ash_wyrm", hp=84, speed=3, elite=True,
                     cycle=[Z("Пепельное дыхание", 10, 1, shape="self", hazard="fire", vfx="e_flame_breath"),
                            M("Укус", 12, add=BURN), K("summon", "Гнездо", unit="fire_imp", n=2)],
                     about="Элита. Дышит пеплом вокруг себя, будит бесов из гнезда."),
    # ---------- стражи ----------
    "overseer_groh": dict(name="Надсмотрщик Грох", sprite="overseer_groh", hp=96, speed=3, elite=True, boss=True,
                          cycle=[K("pull", "Хлыст", dmg=7, range=5, n=3, vfx="e_lash"), M("Дубина", 13),
                                 K("summon", "Пошевеливайтесь!", unit="slag_slave", n=2), K("rally", "Кнут", n=1, r=4)],
                          phases=[{"at": 0.5, "name": "Бешенство надсмотрщика",
                                   "enter": [K("rally", "Ярость", n=2, r=0), K("summon", "Все сюда!", unit="ember_hound", n=1)],
                                   "cycle": [M("Дубина", 15), K("charge", "Растоптать", dmg=13, range=6, push=2),
                                             K("pull", "Хлыст", dmg=8, range=5, n=3, vfx="e_lash")]}],
                          about="Страж отвалов. Хлыстом тянет к себе, гонит рабов в бой. На половине HP — бешенство."),
    "crucible_titan": dict(name="Литейный титан", sprite="crucible_titan", hp=118, speed=2, elite=True, boss=True,
                           cycle=[M("Чугунный кулак", 14), Z("Литьё", 11, 1, hazard="fire", range=6, vfx="lava_vent"),
                                  K("summon", "Живая лава", unit="living_lava", n=1),
                                  K("charge", "Шаг титана", dmg=12, range=5, push=2)],
                           phases=[{"at": 0.5, "name": "Расплавленное сердце",
                                    "enter": [K("summon", "Брызги", unit="fire_imp", n=2)],
                                    "cycle": [Z("Волна расплава", 13, 2, hazard="fire", range=6, vfx="e_meteor"),
                                              M("Чугунный кулак", 16), B("Остывший чугун", 10, 12)]}],
                           about="Страж цехов. Льёт расплав, зовёт живую лаву, топчет по линии."),
    "forge_lord": dict(name="Владыка кузни", sprite="forge_lord", hp=130, speed=2, elite=True, boss=True, final=True,
                       keep_range=2,
                       cycle=[Z("Огненный дождь", 10, 1, hazard="fire", range=7, vfx="e_meteor"),
                              K("summon", "Фанатики", unit="cult_zealot", n=1), K("hex", "Клеймо Владыки", n=1, weak=1, r=7),
                              S("Копьё пламени", 11, 6, add=BURN)],
                       phases=[{"at": 0.6, "name": "Горн пробуждается",
                                "enter": [K("rally", "Жар горна", n=2, r=9), K("summon", "Жрецы", unit="flame_priest", n=1)],
                                "cycle": [Z("Извержение", 13, 2, hazard="fire", range=7, vfx="e_meteor"),
                                          K("pull", "Цепи горна", dmg=8, range=6, n=3, vfx="e_lash"),
                                          S("Копьё пламени", 13, 6, add=BURN)]},
                               {"at": 0.3, "name": "Владыка расплава",
                                "enter": [K("summon", "Живая лава", unit="living_lava", n=2)],
                                "cycle": [M("Молот Владыки", 17), Z("Сердце вулкана", 15, 1, shape="self", hazard="fire",
                                                                    vfx="e_flame_breath"),
                                          K("drown", "Переплавить", n=2), K("charge", "Шаг из пламени", dmg=14, range=6, push=2)]}],
                       about="Босс главы. Огненный дождь, клеймо, фанатики; три фазы — до сердца вулкана."),
}

FLOORS = [
    {"name": "Шлаковые отвалы", "pools": {
        "battle": [
            {"name": "Шлаковая яма", "maps": ["ex_f_slag_pit"], "enemies": ["slag_slave", "slag_slave", "hammer_thrower", "ember_hound"]},
            {"name": "Бунт рабов", "maps": ["ex_f_slave_mob"], "enemies": ["slag_slave", "slag_slave", "slag_slave", "fire_imp"]},
            {"name": "Надсмотрщики", "maps": ["ex_f_revolt"], "enemies": ["chain_smith", "hammer_thrower", "fire_imp"]},
            {"name": "Зал мехов", "maps": ["ex_f_bellows"], "enemies": ["bellows_keeper", "fire_imp", "fire_imp", "slag_slave"]},
            {"name": "Псарня", "maps": ["ex_f_slag_pit", "ex_f_revolt"], "enemies": ["ember_hound", "ember_hound", "hammer_thrower"]},
        ],
        "elite": [
            {"name": "Цепная бригада", "maps": ["ex_f_chain_gang"], "enemies": ["chain_smith", "chain_smith", "slag_slave"]},
            {"name": "Вольный голем", "maps": ["ex_f_golem_pit"], "enemies": ["free_golem", "fire_imp", "fire_imp"]},
        ],
        "boss": [{"name": "Двор надсмотрщика", "maps": ["ex_f_groh"], "enemies": ["overseer_groh", "slag_slave", "hammer_thrower"]}],
    }},
    {"name": "Литейные цеха", "pools": {
        "battle": [
            {"name": "Тигельный зал", "maps": ["ex_f_crucible"], "enemies": ["magma_golem", "cinder_caster", "cinder_caster", "ember_hound"]},
            {"name": "Мост над расплавом", "maps": ["ex_f_lava_bridge"], "enemies": ["salamander", "salamander", "cinder_caster"]},
            {"name": "Обсидиановый пост", "maps": ["ex_f_bellows", "ex_f_crucible"], "enemies": ["obsidian_guard", "magma_golem", "hammer_thrower"]},
            {"name": "Литейный пролёт", "maps": ["ex_f_crucible"], "enemies": ["cinder_caster", "obsidian_guard", "salamander", "fire_imp"]},
            {"name": "Горячий цех", "maps": ["ex_f_bellows"], "enemies": ["bellows_keeper", "magma_golem", "ember_hound"]},
        ],
        "elite": [
            {"name": "Яма големов", "maps": ["ex_f_golem_pit"], "enemies": ["crucible_golem", "obsidian_guard", "cinder_caster"]},
            {"name": "Вольные големы", "maps": ["ex_f_golem_pit"], "enemies": ["free_golem", "magma_golem", "fire_imp"]},
        ],
        "boss": [{"name": "Литейная яма", "maps": ["ex_f_titan"], "enemies": ["crucible_titan", "cinder_caster", "ember_hound"]}],
    }},
    {"name": "Сердце горна", "pools": {
        "battle": [
            {"name": "Зал пепла", "maps": ["ex_f_ash_hall"], "enemies": ["ash_wraith", "ash_wraith", "cult_zealot", "cult_zealot"]},
            {"name": "Алтарь культа", "maps": ["ex_f_cult_altar"], "enemies": ["cult_zealot", "cult_zealot", "flame_priest", "fire_imp"]},
            {"name": "Хор пламени", "maps": ["ex_f_cult_choir"], "enemies": ["flame_priest", "flame_priest", "cult_zealot", "living_lava"]},
            {"name": "Лавовые протоки", "maps": ["ex_f_lava_bridge"], "enemies": ["living_lava", "salamander", "ash_wraith"]},
            {"name": "Пепельный караул", "maps": ["ex_f_ash_hall"], "enemies": ["obsidian_guard", "ash_wraith", "cinder_caster", "cult_zealot"]},
        ],
        "elite": [
            {"name": "Призрачная кузня", "maps": ["ex_f_smith_ghost"], "enemies": ["smith_ghost", "hammer_thrower", "hammer_thrower"]},
            {"name": "Пепельное гнездо", "maps": ["ex_f_ash_wyrm"], "enemies": ["ash_wyrm", "ember_hound"]},
        ],
        "boss": [{"name": "Вознесение Владыки", "maps": ["ex_f_cult_ascension"],
                  "enemies": ["forge_lord", "cult_zealot", "flame_priest"]}],
    }},
]


def main():
    p = os.path.join(D, "enemies.json")
    e = json.load(open(p, encoding="utf-8"))
    e["enemies"].update(ENEMIES)
    ch1 = e["chapter"]
    e["enemies"]["kvaks"]["final"] = False                # Квакс — страж главы, но не конец спуска
    e["chapters"] = [ch1, {"_doc": "Глава 2 — Огненные кузни (перенос из экспедиции, tools/descent_chapter2.py): "
                                   "этажи 4–6 после болота.", "name": "Огненные кузни", "id": "forge",
                           "floors": FLOORS}]
    json.dump(e, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ok:", len(ENEMIES), "врагов кузни ·", sum(len(f["pools"]["battle"]) for f in FLOORS), "боёв")


if __name__ == "__main__":
    main()
