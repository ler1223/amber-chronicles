"""Карты и прозрения «Спуска», написанные вручную (docs/descent_tags.md).

Словарь Наёмника (квиз 2026-11-19): теги Удар, Шаг, Толчок, Защита, Шипы, Кровь, Клич; условия хода, позиции,
цели и героя (Разгон N, Под щитом N, Сам ранен, Один на один, Спиной к стене…); Отклик на события (убийство,
получил удар, враг вплотную); карты-реакции (самому не сыграть) и карты без простого применения; результаты —
Усиление, Печать, Отклик, Задел, Дважды, Возврат, «Следующая карта [Тег]», Закалка.

BASE — сами карты (что у них с самого начала), VARIANTS — 5 вариантов прозрения (предлагаются 3).
Принципы прозрений: каждый вариант меняет то, КАК играется карта; хотя бы один — мост в другой билд; первый —
чистое усиление; сила заметная. Цена и простое применение не меняются никогда. Условия и Печать карты
наследуются вариантом (own_if / no_seal — заменить своими). name — новое имя карты после прозрения.

Запуск: python tools/descent_epiphanies.py — пишет карты и прозрения в data/deck/cards.json, награды героя — в
data/deck/heroes.json, печатает таблицу для проверки.
"""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "deck", "cards.json")
PH = os.path.join(ROOT, "data", "deck", "heroes.json")


# ---------- краткая запись ----------

def D(n, **kw):
    return dict(op="damage", n=n, **kw)


def B(n, **kw):
    return dict(op="block", n=n, **kw)


def op(name, n=None, **kw):
    o = {"op": name}
    if n is not None:
        o["n"] = n
    o.update(kw)
    return o


def adj(*ops):
    return {"op": "aoe_adjacent", "do": list(ops)}


def W(k, **kw):
    return dict(k=k, **kw)


def IF(when, **kw):
    return dict(when=when, **kw)


def enemy(*ops, rng=1, los=None, **kw):
    u = {"target": "enemy", "range": rng, "do": list(ops)}
    if los is not None:
        u["los"] = los
    u.update(kw)
    return u


def reach(n, *ops, **kw):
    return dict(target="reach", reach=n, do=list(ops), **kw)


def me(*ops, **kw):
    return dict(target="self", do=list(ops), **kw)


def step(n, *ops, **kw):
    return dict(target="cell_step", step=n, do=list(ops), **kw)


def dash(n, *ops, **kw):
    return dict(target="cell_dash", dash=n, do=list(ops), **kw)


def ifs(*conds):
    return {"if": list(conds)}


def echo(on, *ops, aim="source", when=None, vfx=None):
    e = {"on": on, "do": list(ops), "aim": aim}
    if when:
        e["when"] = when
    if vfx:
        e["vfx"] = vfx
    return e


def V(label, main=None, name=None, **top):
    """Вариант: label — подпись при выборе, main — новое основное применение, top — свойства карты."""
    v = {"label": label}
    if name:
        v["name"] = name
    if main is not None:
        v["main"] = main
    v.update(top)
    return v


def ill(cards, cid, dx, dy, dz=0.15):
    src, fx, fy, z = cards[cid]["ill"]
    return [src, round(min(0.95, max(0.05, fx + dx)), 2), round(min(0.95, max(0.05, fy + dy)), 2), round(z + dz, 2)]


# ======================= Наёмник: база =======================

def merc_base(cards):
    """Карты Наёмника: правки старых (alt None — без простого) и новые."""
    A = cards
    new = {
        # реакции: самому не сыграть
        "m_counter": dict(name="Контрудар", type="attack", cost=0, react=True, art=A["riposte"]["art"],
                          ill=ill(A, "riposte", 0.15, -0.05), main={"target": "none", "do": []},
                          echo=echo("hit", D(7), vfx="power_strike")),
        "m_ambush": dict(name="Настороже", type="attack", cost=0, react=True, art=A["hook"]["art"],
                         ill=ill(A, "hook", -0.12, 0.05), main={"target": "none", "do": []},
                         echo=echo("near", D(5), op("push", 1), vfx="shield_bash")),
        "m_trophy": dict(name="Трофей", type="skill", cost=0, react=True, tags=["Кровь"],
                         art=A["blood_sweep"]["art"], ill=ill(A, "blood_sweep", 0.12, 0.08),
                         main={"target": "none", "do": []}, echo=echo("kill", op("heal", 4), op("energy", 1),
                                                                         aim="self")),
        # условия цели и позиции
        "m_duel": dict(name="Поединок", type="attack", cost=1, art=A["strike"]["art"], ill=ill(A, "strike", -0.15, 0.0),
                       main=enemy(D(7), vfx="power_strike", **ifs(IF(W("duel"), mult=2))),
                       alt=step(1)),
        "m_shieldbreak": dict(name="Пробить щит", type="attack", cost=1, art=A["body_slam"]["art"],
                              ill=ill(A, "body_slam", 0.15, -0.08),
                              main=enemy(D(5), vfx="shield_bash", **ifs(IF(W("guarded"), plus=7))),
                              alt=enemy(D(2))),
        "m_stomp": dict(name="Добить лежачего", type="attack", cost=1, art=A["charge"]["art"],
                        ill=ill(A, "charge", -0.15, 0.1), main=enemy(D(5), vfx="power_strike",
                                                                    **ifs(IF(W("stunned"), mult=3))),
                        alt=enemy(op("push", 1))),
        # Закалка, Возврат, «Следующая карта»
        "m_temper": dict(name="Закалённый клинок", type="attack", cost=1, art=A["strike"]["art"],
                         ill=ill(A, "strike", 0.12, 0.1), main=enemy(D(5), vfx="power_strike"),
                         temper={"n": 2}, alt=enemy(D(2))),
        "m_drill": dict(name="Отработанный приём", type="attack", cost=1, art=A["lunge"]["art"],
                        ill=ill(A, "lunge", 0.1, -0.1), main=enemy(D(4), vfx="lunge", back=W("after", tag="Шаг")),
                        alt=step(1)),
        "m_rally": dict(name="Подготовка", type="skill", cost=1, art=A["war_cry"]["art"],
                        ill=ill(A, "war_cry", -0.15, 0.05),
                        main=me(op("empower", 6, tag="Удар"), op("draw", 1), vfx="inspire"), alt=step(1)),
        # кровь и щит
        "m_bloodpact": dict(name="Кровавая клятва", type="skill", cost=0, art=A["blood_sweep"]["art"],
                            ill=ill(A, "blood_sweep", -0.12, -0.08),
                            main=me(op("lose_hp", 4), op("energy", 2), vfx="bloodlet",
                                    **ifs(IF(W("hurt"), do=[op("draw", 2)])))),
        "m_shieldwall": dict(name="Стена щитов", type="skill", cost=2, art=A["brace"]["art"],
                             ill=ill(A, "brace", 0.15, 0.05),
                             main=me(B(10), vfx="shield_wall", **ifs(IF(W("shielded", n=15), do=[op("thorns", 5)]))),
                             alt=me(B(2))),
    }
    upd = {
        "defend": {"alt": step(2)},                   # больше движения на стартовых: простое — шаг
        "lunge": {"alt": step(2)},
        "sweep": {"main": me(adj(D(4), op("push", 1)), vfx="whirlwind", **ifs(IF(W("surrounded"), plus=3)))},
        "body_slam": {"main": enemy(op("body_slam", 4), vfx="shield_bash",
                                    **ifs(IF(W("shielded", n=10), do=[op("push", 1)]))), "tags": ["Защита"]},
        "blood_sweep": {"main": me(op("lose_hp", 3), adj(D(9)), vfx="bloodlet", **ifs(IF(W("hurt"), plus=4))),
                        "alt": None},
        "battle_rage": {"alt": None},
        "war_cry": {"alt": None},
        "m_inertia": {"alt": None},
        "charge": {"main": reach(4, D(10), op("push", 1), vfx="charge", **ifs(IF(W("momentum", n=4), do=[op("stun")])))},
        "brace": {"main": me(B(4), op("cleanse"), vfx="brace", **ifs(IF(W("back_wall"), do=[B(4)])))},
    }
    return new, upd


# ======================= Наёмник: прозрения =======================

MERC = {
    # --- стартовые ---
    "strike": [
        V("Острее", enemy(D(9))),
        V("Добить", enemy(D(7), **ifs(IF(W("wounded"), mult=2))), "Добивающий удар"),
        V("С разбега", enemy(D(6, mom_k=2)), "Удар с разбега"),
        V("По слабому", enemy(D(6), **ifs(IF(W("weakened"), mult=2))), "Удар по слабому"),
        V("Ударить и отойти", enemy(D(6), op("retreat", 1)), "Удар с отходом"),
    ],
    "defend": [
        V("Крепче", me(B(8))),
        V("Оборона в кольце", me(B(5), **ifs(IF(W("surrounded"), do=[B(5)]))), "Глухая оборона"),
        V("Шаг и щит", step(1, B(5)), "Щит на ходу"),
        V("С шипами", me(B(4), op("thorns", 3)), "Шипастый щит"),
        V("Разгон в щит", me(B(4, mom_k=2)), "Защита с разбега"),
    ],
    "lunge_rush": [
        V("Острее", reach(3, D(6))),
        V("Дальше", reach(5, D(3)), "Дальний рывок"),
        V("С толчком", reach(3, D(3), op("push", 2)), "Сшибающий рывок"),
        V("Под щитом", reach(3, B(4), D(3)), "Рывок под щитом"),
        V("Не сбавляя хода", reach(3, D(3), **ifs(IF(W("run", n=3), do=[op("draw", 1)]))), "Пробежка"),
    ],
    "lunge": [
        V("Острее", reach(1, D(8))),
        V("Ударить и отойти", reach(1, D(5), op("retreat", 2)), "Выпад с отходом"),
        V("Вскрыть защиту", reach(1, D(5), op("vulnerable", 1)), "Колющий выпад"),
        V("Длиннее", reach(2, D(5)), "Длинный выпад"),
        V("Первым делом", reach(1, D(5), **ifs(IF(W("first"), mult=2))), "Первый выпад"),
    ],
    "shield_ram": [
        V("Острее", enemy(D(12), op("push", 2))),
        V("В стену", enemy(op("collide_x2"), D(8), op("push", 2)), "Таран в стену"),
        V("С подходом", reach(2, D(8), op("push", 2)), "Щитовой натиск"),
        V("Укрыться щитом", enemy(B(6), D(8), op("push", 2)), "Таран под щитом"),
        V("Оглушить у стены", enemy(D(8), op("push", 3), **ifs(IF(W("wall"), do=[op("stun")]))),
          "Сокрушающий таран"),
    ],
    # --- награды ---
    "sweep": [
        V("Острее", me(adj(D(6), op("push", 1)))),
        V("Круговая оборона", me(adj(D(4), op("push", 1)), **ifs(IF(W("surrounded"), do=[B(6)]))), "Круговая сшибка"),
        V("Разметать", me(adj(D(3), op("push", 2))), "Разметать"),
        V("Подсечка", me(adj(D(4), op("push", 1), op("weak", 1))), "Подсечка"),
        V("Ворваться", step(1, adj(D(4), op("push", 1))), "Ворваться в строй"),
    ],
    "wall_smash": [
        V("Сильнее", me(op("collide_x2", 3), op("draw", 1)), "Ломать о стены"),
        V("Больше карт", me(op("collide_x2"), op("draw", 2))),
        V("Плечом", enemy(op("collide_x2"), op("push", 1)), "Плечом в стену"),
        V("С опорой", me(op("collide_x2"), op("draw", 1), B(4)), "Упор у стены"),
        V("После толчков", me(op("collide_x2"), op("draw", 1),
                              **ifs(IF(W("resonance", tag="Толчок", n=1), do=[op("energy", 1)]))), "Тяжёлые стены"),
    ],
    "riposte": [
        V("Крепче", me(B(9), op("thorns", 4))),
        V("Колючая стена", me(B(4), op("thorns", 6)), "Колючая стена"),
        V("Встречный удар", enemy(B(6), op("thorns", 3), D(3)), "Встречный удар"),
        V("Против толпы", me(B(6), op("thorns", 3), **ifs(IF(W("surrounded"), do=[op("thorns", 3)]))), "Ёж"),
        V("Ответить на удар", None, "Ответ", echo=echo("hit", D(4), vfx="riposte")),
    ],
    "body_slam": [
        V("Сильнее", enemy(B(3), op("body_slam", 4))),
        V("С подходом", reach(2, op("body_slam", 4)), "Бросок телом"),
        V("Добить", enemy(op("body_slam", 4), **ifs(IF(W("wounded"), mult=2))), "Раздавить"),
        V("Дважды в серии", enemy(op("body_slam", 4), **ifs(IF(W("series", n=2), repeat=1))), "Град ударов"),
        V("Сквозь щит", enemy(op("body_slam", 4), **ifs(IF(W("guarded"), plus=5))), "Пробой"),
    ],
    "blood_sweep": [
        V("Острее", me(op("lose_hp", 3), adj(D(13)))),
        V("Пить кровь", me(op("lose_hp", 3), adj(D(9)), **ifs(IF(W("surrounded"), do=[op("heal", 6)]))), "Кровопийца"),
        V("Ярость", me(op("lose_hp", 3), adj(D(9)), op("strength", 1)), "Кровавая ярость"),
        V("С шагом", step(1, op("lose_hp", 3), adj(D(9))), "Кровавый рывок"),
        V("Добить раненых", me(op("lose_hp", 3), adj(D(9)), **ifs(IF(W("wounded"), plus=6))), "Резня"),
    ],
    "battle_rage": [
        V("Сильнее", me(op("rage"), op("strength", 1))),
        V("Вспышка", me(op("rage"), op("lose_hp", 4), op("energy", 2)), "Вспышка ярости"),
        V("Холодная голова", me(op("rage"), B(8)), "Холодный раж"),
        V("Разгон не гаснет", me(op("rage"), op("keep_momentum")), "Неудержимость"),
        V("Больше карт", me(op("rage"), op("draw", 2)), "Неистовство"),
    ],
    "charge": [
        V("Острее", reach(4, D(15), op("push", 1))),
        V("С разбега", reach(4, D(8, mom_k=2), op("push", 1)), "Натиск с разбега"),
        V("В стену", reach(4, D(10), op("push", 2), **ifs(IF(W("wall"), mult=2))), "Натиск в стену"),
        V("Под щитом", reach(4, B(5), D(10), op("push", 1)), "Таранный натиск"),
        V("Дальше", reach(6, D(10), op("push", 1)), "Прорыв"),
    ],
    "brace": [
        V("Крепче", me(B(7), op("cleanse"))),
        V("За укрытием", me(B(4), op("cleanse"), **ifs(IF(W("cover"), do=[B(5)]))), "Не сдвинуть"),
        V("Собраться", me(B(4), op("cleanse"), op("draw", 1)), "Собраться"),
        V("Разгон в упор", me(B(2, mom_k=2), op("cleanse")), "Упор с разбега"),
        V("С шипами", me(B(4), op("cleanse"), op("thorns", 2)), "Стальной хребет"),
    ],
    "hook": [
        V("Острее", enemy(op("pull", 3), D(7), rng=4, los=True)),
        V("Подсечь", enemy(op("pull", 3), D(4), op("weak", 1), rng=4, los=True), "Подсекающий крюк"),
        V("Дальше", enemy(op("pull", 4), D(4), rng=6, los=True), "Длинная цепь"),
        V("Подтянуть и врезать", enemy(op("pull", 3), D(4), rng=4, los=True, **ifs(IF(W("adjacent"), plus=5))),
          "Крюк и кулак"),
        V("Приковать", enemy(op("pull", 3), op("root", 1), D(4), rng=4, los=True), "Цепь"),
    ],
    "war_cry": [
        V("Сильнее", me(op("strength", 3), op("aoe_radius", r=3, do=[op("weak", 1)]))),
        V("Устрашить", me(op("strength", 1), op("aoe_radius", r=3, do=[op("weak", 2), op("vulnerable", 1)])),
          "Устрашение"),
        V("Не сгорает", me(op("strength", 1), op("aoe_radius", r=3, do=[op("weak", 1)])), "Боевая песня",
          exhaust=False),
        V("Клич натиска", me(op("strength", 2), op("momentum", 2), op("aoe_radius", r=3, do=[op("weak", 1)])),
          "Клич натиска"),
        V("Призыв к бою", me(op("strength", 2), op("aoe_radius", r=3, do=[op("weak", 1)]),
                             op("empower", 4, tag="Удар")), "Призыв к бою"),
    ],
    "m_ram": [
        V("Острее", reach(2, D(9, mom_k=2), op("push", 1))),
        V("Дальше и тяжелее", reach(3, D(6, mom_k=3), op("push", 1)), "Таран с разгона"),
        V("В стену", reach(2, D(6, mom_k=2), op("push", 2), **ifs(IF(W("wall"), mult=2))), "Таран в стену"),
        V("Под щитом", reach(2, D(6, mom_k=2), op("push", 1), B(5)), "Таран под щитом"),
        V("Не останавливаясь", reach(2, D(6, mom_k=2), op("push", 1), op("momentum", 2)), "Неудержимый"),
    ],
    "m_inertia": [
        V("Сильнее", me(op("keep_momentum"), op("momentum", 2))),
        V("Тяжёлая поступь", me(op("keep_momentum"), B(5)), "Тяжёлая поступь"),
        V("Вечное движение", me(op("keep_momentum"), op("draw", 1)), "Вечное движение"),
        V("Сразу в путь", step(2, op("keep_momentum")), "Сорваться с места"),
        V("Инерция удара", me(op("keep_momentum"), op("strength", 1)), "Инерция удара"),
    ],
    "m_halt": [
        V("Крепче", me(B(6, mom_k=3))),
        V("Встать в шипы", me(B(4, mom_k=2), op("thorns", 3)), "Стоп-шипы"),
        V("Перевести дух", me(B(4, mom_k=2), op("draw", 1)), "Перевести дух"),
        V("Тормозной путь", me(B(4, mom_k=2), adj(op("push", 1))), "Тормозной путь"),
        V("У укрытия", me(B(4, mom_k=2), **ifs(IF(W("cover"), do=[B(5)]))), "Врасти в землю"),
    ],
    "m_run": [
        V("Дальше", step(4)),
        V("Под щитом", step(3, B(3)), "Бег под щитом"),
        V("По прямой", dash(5), "Бросок"),
        V("На одном дыхании", step(3, **ifs(IF(W("run", n=3), do=[op("draw", 1)]))), "На одном дыхании"),
        V("Разбег к удару", step(3, op("empower", 3, tag="Удар")), "Разбег к удару"),
    ],
    "m_flurry": [
        V("Острее", enemy(D(5), D(5), D(5))),
        V("С разбега", enemy(D(4, mom_k=2), D(4), D(4)), "Шквал с разбега"),
        V("Бешеный", enemy(D(5), D(5), D(5), D(5), seal=W("series", n=3)), "Бешеный шквал"),
        V("Без печати", enemy(D(3), D(3), D(3)), "Град", no_seal=True),
        V("Шквал и отход", enemy(D(4), D(4), D(4), op("retreat", 2)), "Шквал с отходом"),
    ],
    "m_wallbash": [
        V("Острее", enemy(D(9), op("push", 1))),
        V("Размазать", enemy(D(6), op("push", 1), **ifs(IF(W("wall"), do=[op("stun")]))), "Размазать"),
        V("С подходом", reach(2, D(6), op("push", 1)), "Прижать к стене"),
        V("Добить раненого", enemy(D(6), op("push", 1), **ifs(IF(W("wounded"), plus=4))), "Додавить"),
        V("Вдавить", enemy(op("collide_x2"), D(6), op("push", 1)), "Вдавить"),
    ],
    # --- новые ---
    "m_counter": [
        V("Острее", echo=echo("hit", D(10), vfx="power_strike")),
        V("Отбросить", None, "Отпор", echo=echo("hit", D(6), op("push", 2), vfx="shield_bash")),
        V("Ответ щитом", None, "Щитовой отпор", echo=echo("hit", D(5), B(5), vfx="shield_bash")),
        V("Кровь за кровь", None, "Кровь за кровь", echo=echo("hit", D(7), op("strength", 1), vfx="power_strike")),
        V("Дважды", None, "Двойной отпор", echo=echo("hit", D(4), D(4), vfx="power_strike")),
    ],
    "m_ambush": [
        V("Острее", echo=echo("near", D(8), op("push", 1), vfx="shield_bash")),
        V("Отшвырнуть", None, "Отшвырнуть", echo=echo("near", D(4), op("push", 3), vfx="shield_bash")),
        V("Оглушить", None, "Встретить ударом", echo=echo("near", D(4), op("stun"), vfx="shield_bash")),
        V("Встать в щит", None, "Стойка", echo=echo("near", D(5), op("push", 1), B(4), vfx="shield_bash")),
        V("Подсечь", None, "Подсечка", echo=echo("near", D(5), op("weak", 2), vfx="shield_bash")),
    ],
    "m_trophy": [
        V("Сильнее", echo=echo("kill", op("heal", 6), op("energy", 1), aim="self")),
        V("Трофейный клинок", None, "Трофейный клинок", echo=echo("kill", op("strength", 1), op("energy", 1),
                                                                    aim="self")),
        V("Добыча", None, "Добыча", echo=echo("kill", op("draw", 2), op("energy", 1), aim="self")),
        V("Кровавый трофей", None, "Кровавый трофей", echo=echo("kill", op("heal", 8), aim="self")),
        V("Не останавливаться", None, "Разгон победителя", echo=echo("kill", op("momentum", 3), op("energy", 1),
                                                                      aim="self")),
    ],
    "m_duel": [
        V("Острее", enemy(D(10))),
        V("Насмерть", enemy(D(7), **ifs(IF(W("wounded"), plus=4))), "Дуэль насмерть"),
        V("Вызов", enemy(D(7), op("weak", 1)), "Вызов"),
        V("Ударить и отойти", enemy(D(7), op("retreat", 1)), "Поединок с отходом"),
        V("Закалка в поединках", enemy(D(7)), "Мастер поединка", temper={"when": W("duel"), "n": 2}),
    ],
    "m_shieldbreak": [
        V("Острее", enemy(D(8))),
        V("Расколоть", enemy(D(5), op("vulnerable", 1)), "Расколоть"),
        V("Сбить с ног", enemy(D(5), **ifs(IF(W("guarded"), do=[op("stun")]))), "Сбить щитом"),
        V("С разбега", enemy(D(5, mom_k=2)), "Пробить с разбега"),
        V("Дважды в серии", enemy(D(5), **ifs(IF(W("series", n=2), repeat=1))), "Серия пробоев"),
    ],
    "m_stomp": [
        V("Острее", enemy(D(7))),
        V("По слабому", enemy(D(5), **ifs(IF(W("weakened"), mult=2))), "Добить слабого"),
        V("Пинок", enemy(D(5), op("push", 2)), "Пинок лежачего"),
        V("Добить раненого", enemy(D(5), **ifs(IF(W("wounded"), plus=5))), "Без пощады"),
        V("Оглушить у стены", enemy(D(5), **ifs(IF(W("wall"), do=[op("stun")]))), "Прибить к стене"),
    ],
    "m_temper": [
        V("Острее", enemy(D(7))),
        V("Быстрая закалка", None, "Горячая ковка", temper={"n": 3}),
        V("И щит", enemy(D(5), B(3)), "Закалённая сталь"),
        V("Закалка в серии", None, "Ковка в бою", temper={"when": W("series", n=2), "n": 4}),
        V("Размах", me(adj(D(4)), vfx="whirlwind"), "Закалённый размах"),
    ],
    "m_drill": [
        V("Острее", enemy(D(6))),
        V("С подходом", reach(1, D(4)), "Отработанный выпад"),
        V("Толчок", enemy(D(4), op("push", 1), back=W("after", tag="Толчок")), "Отработанный толчок"),
        V("В ритме", enemy(D(4), back=W("series", n=2)), "В ритме"),
        V("Со щитом", enemy(D(4), B(3), back=W("after", tag="Защита")), "Отработанная защита"),
    ],
    "m_rally": [
        V("Сильнее", me(op("empower", 9, tag="Удар"), op("draw", 1))),
        V("К бою", me(op("empower", 6, tag="Удар"), op("energy", 1)), "К бою!"),
        V("Подготовить таран", me(op("empower", 6, tag="Толчок"), op("draw", 1)), "Подготовить таран"),
        V("Вдохновить", me(op("strength", 1), op("draw", 1)), "Вдохновение"),
        V("Собраться", me(op("empower", 6, tag="Удар"), B(4)), "Собраться с силами"),
    ],
    "m_bloodpact": [
        V("Сильнее", me(op("lose_hp", 4), op("energy", 2), **ifs(IF(W("hurt"), do=[op("draw", 3)])), own_if=True)),
        V("Кровь за силу", me(op("lose_hp", 4), op("energy", 1), op("strength", 1)), "Кровь за силу"),
        V("Кровавый щит", me(op("lose_hp", 4), op("energy", 2), B(6)), "Кровавый щит"),
        V("Жажда", me(op("lose_hp", 4), op("energy", 2), op("empower", 5, tag="Удар")), "Жажда"),
        V("Клятва мести", None, "Клятва мести", keep=W("hurt")),
    ],
    "m_shieldwall": [
        V("Крепче", me(B(14))),
        V("С шипами", me(B(8), op("thorns", 3)), "Стена с шипами"),
        V("Спиной к стене", me(B(10), **ifs(IF(W("back_wall"), do=[B(6)]))), "Опора"),
        V("Стена-таран", me(B(10), adj(op("push", 1))), "Стена-таран"),
        V("Не опускать щит", None, "Глухая стена", keep=W("shielded", n=10)),
    ],
}

VARIANTS = {**MERC}
HERO_NEW = {"merc": ["m_counter", "m_ambush", "m_trophy", "m_duel", "m_shieldbreak", "m_stomp", "m_temper",
                     "m_drill", "m_rally", "m_bloodpact", "m_shieldwall"]}


def write_base(cards, heroes):
    new, upd = merc_base(cards)
    for cid, c in new.items():
        prev = cards.get(cid, {})
        cards[cid] = dict(c, growth=prev.get("growth", [{"uses": 3, "options": []}]))
    for cid, u in upd.items():
        for k, v in u.items():
            if v is None:
                cards[cid].pop(k, None)
            else:
                cards[cid][k] = v
    for hero, cids in HERO_NEW.items():
        r = heroes["heroes"][hero]["rewards"]
        for cid in cids:
            if cid not in r:
                r.append(cid)


def apply(cards):
    for cid, vs in VARIANTS.items():
        c = cards[cid]
        assert len(vs) == 5, cid
        base = c["main"]
        out = []
        for v in vs:
            v = copy.deepcopy(v)
            own_if = v["main"].pop("own_if", False) if "main" in v else False
            no_seal = v.pop("no_seal", False)
            if "main" in v:
                m = v["main"]
                m.setdefault("vfx", base.get("vfx"))
                if m["vfx"] is None:
                    m.pop("vfx")
                if base.get("if") and not own_if:                          # условия карты — и после прозрения
                    m["if"] = copy.deepcopy(base["if"]) + m.get("if", [])
                if base.get("seal") and "seal" not in m and not no_seal:
                    m["seal"] = copy.deepcopy(base["seal"])
                for k in ("back",):
                    if base.get(k) and k not in m:
                        m[k] = copy.deepcopy(base[k])
            elif no_seal:
                v["main"] = {k: x for k, x in copy.deepcopy(base).items() if k != "seal"}
            assert "cost" not in v and "alt" not in v, cid                       # цена и простое — никогда
            out.append(v)
        uses = c["growth"][0]["uses"] if c.get("growth") else 3
        c["growth"] = [{"uses": uses, "options": out}]


def table(cards, cids):
    sys.path.insert(0, ROOT)
    from deck import model as M
    from deck.ui import _changes
    lines = []
    for cid in cids:
        c = M.Card(cid, cards)
        alt = M.plain(M.phrase(c.d["alt"])) or "нет"
        lines.append(f"\n**{c.name}** [{', '.join(c.tags)}] {c.d.get('cost')}: "
                     f"{M.plain(M.phrase(c.d['main'], c.d.get('exhaust')))} {M.plain(M.card_extras(c.d))}"
                     f" | простое: {alt}")
        for k, o in enumerate(cards[cid]["growth"][0]["options"]):
            c2 = M.Card(cid, cards, picks=[k])
            ch = "; ".join(M.plain(t) for _, t in _changes(c, c2)) or "—"
            lines.append(f"{k + 1}. *{o['label']}* → «{c2.name}»: {ch}")
    return "\n".join(lines)


# эффекты ударов: свои у каждой карты (не одни и те же у всех), карта → (было, стало); None — любой/пусто
VFX_OVERRIDE = {"h_shot": (None, "aimed_shot"), "h_poison": (None, "_d_poison_arrow"), "arrow": (None, "_d_quick_arrow"),
                "h_long": ("aimed_shot", "mirror_arrow"), "m_duel": ("power_strike", "jump_strike"),
                "m_flurry": ("power_strike", "cleave"), "m_stomp": ("power_strike", "quake_strike"),
                "m_temper": ("power_strike", "e_club")}


def vfx_override(cards):
    for cid, (old, new) in VFX_OVERRIDE.items():
        cd = cards.get(cid)
        if cd is None:
            continue
        for m in [cd["main"]] + [o["main"] for g in cd.get("growth", []) for o in g.get("options", []) if "main" in o]:
            if old is None or m.get("vfx") == old:
                m["vfx"] = new


if __name__ == "__main__":
    data = json.load(open(P, encoding="utf-8"))
    heroes = json.load(open(PH, encoding="utf-8"))
    write_base(data["cards"], heroes)
    apply(data["cards"])
    vfx_override(data["cards"])
    json.dump(data, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(heroes, open(PH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(table(data["cards"], list(VARIANTS)))
