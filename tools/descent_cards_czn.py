"""Новые карты Наёмника, Охотницы и Пиромантки (квиз 2026-11-21): сильнее стартовых, часть — билдостроительные.

Ключевые слова из CZN: Изгнание (exhaust), Сохранение (retain), Создать карту (add_card — временные карты),
Единственная (unique). Состояния: Уязвимость / Слабость, Кровотечение (bleed), Контратака (counter), Мощь
(strength). Билды: Силы до конца боя (main.power: on/tag/aim/do или mod) и двигатели «за каждую…» (op.per).
Анимации — только готовые навыки из data/vfx.json. У каждой карты 5 прозрений (предлагаются 3).

Пишет в data/deck/cards.json и награды героев в data/deck/heroes.json.
Запуск: python tools/descent_cards_czn.py (после descent_epiphanies.py и descent_survival.py).
"""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from descent_epiphanies import IF, B, D, V, W, adj, enemy, ifs, me, op, reach, step  # noqa: E402

D_ = os.path.join(ROOT, "data", "deck")
SCALE = {"damage", "block", "bleed", "burn", "poison", "heal", "counter", "trap", "weak", "vulnerable", "mark",
         "thorns", "chain"}


# ---------- краткая запись ----------

def shot(rng, *ops, **kw):
    return enemy(*ops, rng=rng, los=True, ranged=True, **kw)


def per(what, k):
    return {"what": what, "k": k}


def area(rng, r, *ops, **kw):
    return dict(target="area", range=rng, radius=r, do=list(ops), **kw)


def cell(rng, *ops, **kw):
    return dict(target="cell_any", range=rng, do=list(ops), **kw)


def make(cid, n, name):
    return op("add_card", n, card=cid, cname=name)


def power(on=None, *do, tag=None, aim=None, mod=None, n=None, once=False, cost_do=(), **kw):
    """Сила до конца боя. cost_do — что карта делает сразу при розыгрыше."""
    pw = {}
    if on:
        pw["on"] = on
        pw["do"] = list(do)
    if tag:
        pw["tag"] = tag
    if aim:
        pw["aim"] = aim
    if mod:
        pw["mod"] = mod
    if n is not None:
        pw["n"] = n
    if once:
        pw["once"] = True
    return dict({"target": "self", "do": list(cost_do), "power": pw}, **kw)


def up(u, frac=0.4):
    """Сильнее: числа действий (урон, защита, состояния…) — примерно на 40%."""
    u = copy.deepcopy(u)

    def delta(v):
        d = round(v * frac)
        return max(1, d) if frac > 0 else min(-1, d)

    def bump(ops):
        for o in ops:
            if o["op"] in SCALE and o.get("n"):
                o["n"] = max(1, o["n"] + delta(o["n"]))
            if o.get("per") and frac > 0:
                o["per"]["k"] += 1 if o["per"]["k"] < 4 else 2
            if o.get("do"):
                bump(o["do"])
    bump(u.get("do", []))
    if u.get("power"):
        bump(u["power"].get("do", []))
        if u["power"].get("n"):
            u["power"]["n"] = max(1, u["power"]["n"] + delta(u["power"]["n"]))
    return u


def plus(u, *ops):
    u = copy.deepcopy(u)
    u["do"] = list(u.get("do", [])) + list(ops)
    return u


def lv(*levels):
    return [{"heat": h, "main": m} for h, m in levels]


def uplv(levels, frac=0.4):
    return [dict(L, main=up(L["main"], frac)) for L in levels]


def pluslv(levels, *ops):
    return [dict(L, main=plus(L["main"], *ops)) for L in levels]


def LV(label, name, levels, **top):
    v = {"label": label, "levels": levels}
    if name:
        v["name"] = name
    v.update(top)
    return v


ILLS = iter([
    "deserter", "anvil", "bell_ringer", "bellows_hall", "brass_oracle", "broken_automaton", "camp", "cold_anvil",
    "contract_due", "drowned_bell", "frog_gambler", "golem_parts", "greedy_find", "guild_contract", "guild_feast",
    "guild_toll", "leech_egg", "leech_hatch", "leech_master", "lich_phylactery", "mage_gas", "market_gems",
    "market_night", "master_contest", "moon_frog", "obsidian_mirror", "overseer_bribe", "plague_village",
    "quench_bath", "slag_merchant", "slave_cache", "slave_revolt", "smith_debt", "smith_rescue", "spore_mushroom",
    "starsteel_vein", "sunken_caravan", "sunken_chest", "sunken_library", "trapped_miner", "tribute_cart",
    "witch_price", "act_1", "act_2", "forge_act_0", "forge_act_1", "forge_act_2", "crypt_act_0", "crypt_act_1",
    "crypt_act_2", "steppe_act_0", "pass_act_0", "tomb_act_0", "citadel_act_0", "fae_act_0", "sunken_act_0",
    "final_vigil", "market_goods",
])


def card(name, typ, art, main=None, alt=None, cost=1, levels=None, variants=(), **kw):
    c = {"ill": [next(ILLS), 0.5, 0.5, 0.7], "art": art, "name": name, "cost": cost, "type": typ, "alt": alt}
    if levels:
        c["levels"] = levels
        c["main"] = levels[0]["main"]
        c["cost"] = levels[0]["heat"]
    else:
        c["main"] = main
    c.update(kw)
    vs = list(variants)
    assert len(vs) == 5, name
    for v in vs:
        if "main" in v and main is not None and main.get("vfx"):
            v["main"].setdefault("vfx", main["vfx"])
    c["growth"] = [{"uses": 3, "options": vs}]
    return c


def token(name, art, main, ill):
    return {"ill": [ill, 0.45, 0.45, 0.4], "art": art, "name": name, "cost": 0, "type": "attack", "token": True,
            "exhaust": True, "main": main, "alt": None}


# ======================= Наёмник =======================
# Кровотечение (порезы и «вскрыть»), Контратака (стойки), Мощь (накопить и вложить), Разгон (бег), Ножи.

def merc():
    C = {}
    rend = enemy(D(5), op("bleed", 3), vfx="blood_strike")
    C["m_rend"] = card("Рваная рана", "attack", "item_dagger", rend, step(1), variants=[
        V("Сильнее", up(rend)),
        V("Глубже", enemy(D(3), op("bleed", 6)), "Глубокий порез"),
        V("Два пореза", enemy(D(3), op("bleed", 2), D(3), op("bleed", 2)), "Двойной порез"),
        V("С отходом", enemy(D(5), op("bleed", 3), op("retreat", 2)), "Порез и отход"),
        V("По кровоточащему", enemy(D(5), op("bleed", 3), **ifs(IF(W("bleeding"), plus=5))), "Добавить крови")])
    opn = enemy(D(3, per=per("bleed", 2)), vfx="bone_grip")
    C["m_open"] = card("Вскрыть раны", "attack", "gift_blood_thirst", opn, step(1), variants=[
        V("Сильнее", up(opn)),
        V("Всем соседям", me(adj(D(2, per=per("bleed", 2)))), "Кровавая жатва"),
        V("Изгнание: глубже", enemy(D(3, per=per("bleed", 4))), "Вскрыть до кости", exhaust=True),
        V("Удвоить кровь", enemy(D(3), op("bleed", 0, per=per("bleed", 1))), "Разбередить"),
        V("Испить", enemy(D(3, per=per("bleed", 2)), op("heal", 0, per=per("bleed", 1))), "Кровопийца")])
    wh = me(adj(D(4), op("bleed", 2)), vfx="whirlwind")
    C["m_blade_storm"] = card("Вихрь клинков", "attack", "item_axe", wh, me(B(2)), cost=2, variants=[
        V("Сильнее", up(wh)),
        V("С разбега", step(2, adj(D(4), op("bleed", 2))), "Налёт"),
        V("Под щитом", me(adj(D(4), op("bleed", 2)), B(6)), "Стальной вихрь"),
        V("Ответный", me(adj(D(3), op("bleed", 2)), op("counter", 2)), "Вихрь и стойка"),
        V("Всем вокруг", me(op("aoe_radius", r=2, do=[D(3), op("bleed", 2)])), "Буря клинков")])
    sta = me(B(5), op("counter", 2), vfx="riposte")
    C["m_duelist"] = card("Стойка дуэлянта", "skill", "gift_duel_honor", sta, me(B(2)), retain=True, variants=[
        V("Сильнее", up(sta)),
        V("Глухая", me(B(9), op("counter", 1)), "Глухая стойка"),
        V("Острая", me(B(3), op("counter", 4)), "Острая стойка"),
        V("Оборона", me(B(5), op("counter", 2), op("fort", 1)), "Стойка с обороной"),
        V("Мощь", me(B(4), op("counter", 2), op("strength", 1)), "Стойка мастера")])
    lunge = reach(2, D(4, per=per("counter", 3)), vfx="lunge")
    C["m_riposte"] = card("Ответный выпад", "attack", "gift_knife_back", lunge, step(1), variants=[
        V("Сильнее", up(lunge)),
        V("Дальше", reach(3, D(4, per=per("counter", 3))), "Длинный выпад"),
        V("Не тратить", reach(2, D(4, per=per("counter", 3)), op("counter", 1)), "Выпад и стойка"),
        V("Кровью", reach(2, D(4, per=per("counter", 3)), op("bleed", 3)), "Кровавый выпад"),
        V("Под щитом", reach(2, D(4, per=per("counter", 3)), B(5)), "Выпад под щитом")])
    meet = power("turn", op("counter", 2), vfx="last_stand")
    C["m_meet"] = card("Встречный бой", "power", "gift_spear_wall", meet, me(B(2)), cost=2, variants=[
        V("Сильнее", power("turn", op("counter", 3), vfx="last_stand")),
        V("Со щитом", power("turn", op("counter", 2), B(3), vfx="last_stand"), "Стена клинков"),
        V("Острее", power(mod="counter_plus", n=4, vfx="last_stand"), "Острый ответ"),
        V("Кровью", power(mod="counter_bleed", vfx="last_stand"), "Ответ кровью"),
        V("Когда бьют", power("hit", op("counter", 1), vfx="last_stand"), "Злой ответ")])
    rage = power("turn", op("strength", 1), vfx="undying_rage")
    C["m_rising"] = card("Растущая ярость", "power", "gift_berserk_blood", rage, me(B(2)), cost=3, variants=[
        V("Кровью", power("turn", op("strength", 2), op("lose_hp", 2), vfx="undying_rage"), "Ярость в крови"),
        V("С защитой", power("turn", op("strength", 1), B(3), vfx="undying_rage"), "Стальная ярость"),
        V("От ран", power("hit", op("strength", 1), once=True, vfx="undying_rage"), "Боль даёт силу"),
        V("От убийств", power("kill", op("strength", 2), vfx="undying_rage"), "Жажда битвы"),
        V("Сейчас", power("turn", op("strength", 1), cost_do=[op("strength", 2)], vfx="undying_rage"),
          "Ярость сразу")])
    crush = enemy(D(9, per=per("strength", 2)), vfx="quake_strike", shake=1)
    C["m_crush"] = card("Сокрушить", "attack", "item_hammer", crush, enemy(D(2)), cost=2, variants=[
        V("Сильнее", up(crush)),
        V("Тройная мощь", enemy(D(6, per=per("strength", 3))), "Удар исполина"),
        V("Отбросить", enemy(D(9, per=per("strength", 2)), op("push", 2)), "Сокрушить и отбросить"),
        V("Уязвить", enemy(D(8, per=per("strength", 2)), op("vulnerable", 2)), "Пробить защиту"),
        V("Оглушить", enemy(D(7, per=per("strength", 2)), op("stun")), "Оглушающий удар")])
    cry = me(op("strength", 2), op("aoe_radius", r=2, do=[op("weak", 1)]), vfx="war_song")
    C["m_leader_cry"] = card("Клич вожака", "skill", "gift_marshal", cry, me(B(2)), exhaust=True, variants=[
        V("Сильнее", up(cry, 0.5)),
        V("Без изгнания", me(op("strength", 1), op("aoe_radius", r=2, do=[op("weak", 1)])), "Боевой клич",
          exhaust=False),
        V("Устрашить", me(op("strength", 2), op("aoe_radius", r=3, do=[op("weak", 2), op("vulnerable", 1)])),
          "Устрашение"),
        V("Добрать", me(op("strength", 2), op("draw", 2)), "Клич и рывок"),
        V("Щит", me(op("strength", 2), B(6)), "Клич со щитом")])
    lim = me(op("strength_x2"), vfx="trance")
    C["m_limit"] = card("Предел", "skill", "gift_bloodlust", lim, me(B(2)), exhaust=True, unique=True, variants=[
        V("Плюс мощь", me(op("strength", 2), op("strength_x2"))),
        V("Сохранение", me(op("strength_x2")), retain=True),
        V("Добрать", me(op("strength_x2"), op("draw", 2)), "Предел и рывок"),
        V("Кровью", me(op("lose_hp", 4), op("strength", 3), op("strength_x2")), "Кровавый предел"),
        V("Без изгнания", me(op("strength", 1), op("strength_x2"), op("lose_hp", 6)), "Вечный предел",
          exhaust=False)])
    knives = me(make("t_knife", 2, "Метательный нож"), vfx="fletching")
    C["m_knives"] = card("Метательные ножи", "skill", "item_dagger", knives, step(1), variants=[
        V("Больше", me(make("t_knife", 3, "Метательный нож"))),
        V("Ядовитые", me(make("t_knife", 2, "Метательный нож"), op("aoe_radius", r=4, do=[op("bleed", 1)])),
          "Ножи и кровь"),
        V("Мощь", me(make("t_knife", 2, "Метательный нож"), op("strength", 1)), "Ножи мастера"),
        V("Шаг", step(2, make("t_knife", 2, "Метательный нож")), "Ножи на бегу"),
        V("Сохранение", me(make("t_knife", 2, "Метательный нож")), retain=True)])
    trail = power("step", op("bleed", 1), aim="adjacent", vfx="rush")
    C["m_blood_trail"] = card("Кровавый след", "power", "gift_mire_fury", trail, step(1), cost=2, variants=[
        V("Сильнее", power("step", op("bleed", 2), aim="adjacent", vfx="rush")),
        V("И щит", power("step", op("bleed", 1), aim="adjacent", vfx="rush", cost_do=[B(6)]), "След под щитом"),
        V("Разгон", power("step", B(1), vfx="rush"), "Бег в броне"),
        V("Не тает", power(mod="bleed_keep", vfx="rush"), "Открытые раны"),
        V("Убийство", power("kill", op("draw", 1), op("energy", 1), vfx="rush"), "Мясник")])
    fr = enemy(D(3, per=per("played", 2)), vfx="jump_strike")
    C["m_frenzy"] = card("Неистовство", "attack", "item_blade", fr, step(1), variants=[
        V("Сильнее", up(fr)),
        V("По [Удар]", enemy(D(3, per=per("tag:Удар", 3))), "Цепь ударов"),
        V("Кровью", enemy(D(3, per=per("played", 2)), op("bleed", 2)), "Кровавое неистовство"),
        V("Подход", reach(2, D(3, per=per("played", 2))), "Неистовый натиск"),
        V("Возврат", enemy(D(3, per=per("played", 2)), back=W("series", n=3)), "Нескончаемое неистовство")])
    ram = reach(4, D(4, per=per("walked", 2)), op("push", 1), vfx="charge")
    C["m_runner"] = card("Таранный бег", "attack", "gift_battering", ram, step(1), cost=2, variants=[
        V("Сильнее", up(ram)),
        V("Дальше", reach(5, D(4, per=per("walked", 2)), op("push", 1)), "Долгий разбег"),
        V("Сбить", reach(4, D(4, per=per("walked", 2)), op("push", 2), op("weak", 1)), "Сбить с ног"),
        V("Со щитом", reach(4, D(4, per=per("walked", 2)), B(5)), "Щитом вперёд"),
        V("Кровью", reach(4, D(3, per=per("walked", 2)), op("bleed", 3)), "Рваный натиск")])
    last = enemy(D(16), op("vulnerable", 1), **ifs(IF(W("wounded"), mult=2)), vfx="power_strike", shake=1)
    C["m_last_word"] = card("Последний довод", "attack", "gift_giant_slayer", last, enemy(D(3)), cost=3,
                            unique=True, retain=True, variants=[
        V("Сильнее", up(last)),
        V("Дешевле силой", enemy(D(12, per=per("strength", 3)), **ifs(IF(W("wounded"), mult=2))), "Довод силы"),
        V("Кровью", enemy(D(14), op("bleed", 6), **ifs(IF(W("wounded"), mult=2))), "Кровавый довод"),
        V("Подойти", reach(3, D(16), **ifs(IF(W("wounded"), mult=2))), "Довод с разбега"),
        V("Оглушить", enemy(D(14), op("stun"), **ifs(IF(W("wounded"), mult=2))), "Сокрушительный довод")])
    bul = me(B(10), op("counter", 2), op("fort", 1), vfx="shield_wall")
    C["m_unbreak"] = card("Несокрушимый", "skill", "gift_steel_shell", bul, me(B(3)), cost=2, variants=[
        V("Сильнее", up(bul)),
        V("Колючий", me(B(10), op("counter", 2), op("thorns", 4)), "Колючая крепость"),
        V("Мощь", me(B(9), op("counter", 2), op("strength", 1)), "Несокрушимая воля"),
        V("Сохранение", me(B(10), op("counter", 2), op("fort", 1)), retain=True),
        V("Удар щитом", me(B(10), adj(D(0, per=per("counter", 3)))), "Ответ щитом")])
    hunt = power("kill", op("energy", 1), op("draw", 1), vfx="all_out")
    C["m_butcher"] = card("Азарт резни", "power", "gift_bloodlust", hunt, me(B(2)), cost=2, variants=[
        V("Больше", power("kill", op("energy", 1), op("draw", 2), vfx="all_out")),
        V("Мощь", power("kill", op("strength", 1), op("draw", 1), vfx="all_out"), "Растущая резня"),
        V("Лечение", power("kill", op("heal", 4), op("energy", 1), vfx="all_out"), "Пир победителя"),
        V("Кровь", power("kill", op("bleed", 3), aim="all", vfx="all_out"), "Кровавый урок"),
        V("Ножи", power("kill", make("t_knife", 2, "Метательный нож"), vfx="all_out"), "Трофейные ножи")])
    tk = token("Метательный нож", "item_dagger", shot(4, D(3), op("bleed", 1), vfx="_d_quick_arrow"), "rival_finale")
    return C, {"t_knife": tk}


# ======================= Охотница =======================
# Выстрел-цепочки, Кровотечение (зазубрины), Слабость/Уязвимость, ловушки, стрелы-токены, Сохранение (выжидать).

def hunter():
    C = {}
    jag = shot(5, D(5), op("bleed", 3), vfx="mirror_arrow")
    C["h_jagged"] = card("Зазубренная стрела", "attack", "arrow_bleed", jag, step(1), variants=[
        V("Сильнее", up(jag)),
        V("Глубже", shot(5, D(3), op("bleed", 6)), "Крюк-наконечник"),
        V("Дальше", shot(7, D(5), op("bleed", 3)), "Дальняя зазубрина"),
        V("Отход", shot(5, D(5), op("bleed", 3), op("retreat", 1)), "Зазубрина с отходом"),
        V("По уязвимому", shot(5, D(5), op("bleed", 3), **ifs(IF(W("vulnerable"), plus=5))), "Точная зазубрина")])
    ten = shot(5, D(4), op("weak", 2), op("root", 1), vfx="shackle_shot")
    C["h_tendon"] = card("В сухожилие", "attack", "arrow_blunt", ten, step(1), variants=[
        V("Сильнее", up(ten)),
        V("Обездвижить", shot(5, D(3), op("weak", 1), op("root", 2)), "Пригвоздить"),
        V("Уязвить", shot(5, D(4), op("weak", 1), op("vulnerable", 2)), "Под рёбра"),
        V("Кровью", shot(5, D(4), op("weak", 2), op("bleed", 3)), "Рваное сухожилие"),
        V("Добрать", shot(5, D(4), op("weak", 2), op("draw", 1)), "Быстрый подрез")])
    prc = shot(6, D(9), op("vulnerable", 2), vfx="aimed_shot")
    C["h_pierce"] = card("Бронебойная", "attack", "arrow_piercing", prc, step(1), cost=2, variants=[
        V("Сильнее", up(prc)),
        V("Издалека", shot(7, D(9), op("vulnerable", 2), **ifs(IF(W("far", n=4), plus=6))), "Дальний пробой"),
        V("Насквозь", shot(6, D(7), op("vulnerable", 2), op("aoe_radius", r=1, do=[op("vulnerable", 1)])),
          "Сквозная стрела"),
        V("Метка", shot(6, D(8), op("vulnerable", 2), op("mark", 4)), "Пробой и метка"),
        V("Сохранение", shot(6, D(9), op("vulnerable", 2)), retain=True)])
    bar = shot(5, D(2, per=per("tag:Выстрел", 3)), vfx="barrage")
    C["h_barrage"] = card("Шквал стрел", "attack", "arrow_storm", bar, step(1), variants=[
        V("Сильнее", up(bar)),
        V("За каждую", shot(5, D(2, per=per("played", 3))), "Сплошной шквал"),
        V("Кровью", shot(5, D(2, per=per("tag:Выстрел", 2)), op("bleed", 2)), "Рваный шквал"),
        V("Возврат", shot(5, D(2, per=per("tag:Выстрел", 3)), back=W("resonance", tag="Выстрел", n=3)),
          "Нескончаемый шквал"),
        V("Отход", shot(5, D(2, per=per("tag:Выстрел", 3)), op("retreat", 2)), "Шквал на отходе")])
    qv = me(make("arrow", 3, "Стрела"), vfx="fletching")
    C["h_full_quiver"] = card("Полный колчан", "skill", "arrow_piercing", qv, step(1), variants=[
        V("Больше", me(make("arrow", 4, "Стрела"))),
        V("Дальше", me(make("arrow", 2, "Стрела"), op("ranged_bonus", 1)), "Колчан и тетива"),
        V("Шаг", step(2, make("arrow", 3, "Стрела")), "Колчан на бегу"),
        V("Фокус", me(make("arrow", 2, "Стрела"), op("focus")), "Колчан и прицел"),
        V("Защита", me(make("arrow", 3, "Стрела"), B(4)), "Колчан за щитом")])
    rain = area(6, 1, D(5), op("bleed", 1), ranged=True, vfx="arrow_storm")
    C["h_rain"] = card("Ливень стрел", "attack", "arrow_storm", rain, step(1), cost=2, variants=[
        V("Сильнее", up(rain)),
        V("Шире", area(6, 2, D(4), ranged=True), "Стрелы до горизонта"),
        V("Яд", area(6, 1, D(4), op("poison", 3), ranged=True), "Ядовитый ливень"),
        V("Ослабить", area(6, 1, D(4), op("weak", 2), ranged=True), "Ливень с неба"),
        V("Изгнание: мощнее", area(6, 2, D(8), op("bleed", 2), ranged=True), "Последний ливень", exhaust=True)])
    sp = cell(4, op("trap", 10), vfx="spike_trap")
    C["h_spikes"] = card("Шипастая ловушка", "skill", "gift_bog_roots", sp, step(1), variants=[
        V("Сильнее", up(sp)),
        V("Дальше", cell(6, op("trap", 10)), "Дальний капкан"),
        V("С защитой", cell(4, op("trap", 9), B(4)), "Засада у капкана"),
        V("Добрать", cell(4, op("trap", 8), op("draw", 1)), "Быстрый капкан"),
        V("Сохранение", cell(4, op("trap", 10)), retain=True)])
    pit = cell(4, op("trap", 18), vfx="wolf_pit")
    C["h_pit"] = card("Волчья яма", "skill", "gift_bog_roots", pit, step(1), cost=2, exhaust=True, variants=[
        V("Глубже", up(pit)),
        V("Без изгнания", cell(4, op("trap", 12)), "Яма-ловушка", exhaust=False),
        V("Дальше", cell(6, op("trap", 18)), "Дальняя яма"),
        V("Добрать", cell(4, op("trap", 16), op("draw", 2)), "Яма и отход"),
        V("Сохранение", cell(4, op("trap", 18)), retain=True)])
    net = enemy(op("root", 2), op("weak", 2), op("vulnerable", 1), rng=4, vfx="net")
    C["h_net"] = card("Ловчая сеть", "skill", "item_loop", net, step(1), variants=[
        V("Сильнее", up(net, 0.5)),
        V("Широкая", area(4, 1, op("root", 1), op("weak", 1)), "Широкая сеть"),
        V("Тянуть", enemy(op("root", 1), op("vulnerable", 2), op("pull", 2), rng=5), "Сеть с крюком"),
        V("Кровью", enemy(op("root", 2), op("weak", 2), op("bleed", 3), rng=4), "Сеть с крючьями"),
        V("Добрать", enemy(op("root", 2), op("weak", 2), op("draw", 1), rng=4), "Быстрая сеть")])
    fin = shot(5, D(4, per=per("bleed", 2)), vfx="headshot")
    C["h_finish"] = card("Добить подранка", "attack", "gift_prey", fin, step(1), variants=[
        V("Сильнее", up(fin)),
        V("По яду", shot(5, D(4, per=per("poison", 2))), "Добить отравленного"),
        V("По уязвимому", shot(5, D(4, per=per("bleed", 2)), **ifs(IF(W("vulnerable"), mult=2))), "Решающий"),
        V("Возврат", shot(5, D(4, per=per("bleed", 2)), back=W("bleeding")), "Охота по следу"),
        V("Испить", shot(5, D(4, per=per("bleed", 2)), op("heal", 3)), "Добыча кормит")])
    pat = power(mod="retain", vfx="focus")
    C["h_patience"] = card("Затаить дыхание", "power", "gift_deep_focus", pat, step(1), cost=2, variants=[
        V("С добором", power(mod="retain", vfx="focus", cost_do=[op("draw", 2)]), "Терпение охотника"),
        V("С фокусом", power(mod="retain", vfx="focus", cost_do=[op("focus")]), "Выжидать цель"),
        V("Защита", power("turn", B(4), vfx="focus"), "Засидка"),
        V("Стрелы", power("turn", make("arrow", 1, "Стрела"), vfx="focus"), "Колчан мастера"),
        V("Метка", power("turn", op("mark", 3), aim="nearest", vfx="focus"), "Глаз охотника")])
    mq = power("turn", make("arrow", 1, "Стрела"), vfx="hunter_ambush")
    C["h_master_quiver"] = card("Колчан мастера", "power", "item_bow", mq, step(1), cost=2, variants=[
        V("Больше", power("turn", make("arrow", 2, "Стрела"), vfx="hunter_ambush")),
        V("Дальность", power("turn", make("arrow", 1, "Стрела"), vfx="hunter_ambush",
                             cost_do=[op("ranged_bonus", 2)]), "Тугая тетива"),
        V("Кровь", power("play", op("bleed", 1), tag="Выстрел", aim="nearest", vfx="hunter_ambush"),
          "Зазубренные наконечники"),
        V("Метка", power("play", op("mark", 2), tag="Выстрел", aim="nearest", vfx="hunter_ambush"),
          "Охотничий азарт"),
        V("Яд", power("play", op("poison", 1), tag="Выстрел", aim="nearest", vfx="hunter_ambush"),
          "Отравленные наконечники")])
    pc = area(5, 1, op("poison", 4), vfx="poison_cloud")
    C["h_toxic"] = card("Ядовитое облако", "skill", "gift_ghoul_kiss", pc, step(1), variants=[
        V("Сильнее", up(pc)),
        V("Шире", area(5, 2, op("poison", 3)), "Ядовитый туман"),
        V("Ослабить", area(5, 1, op("poison", 3), op("weak", 1)), "Удушливое облако"),
        V("Кровь", area(5, 1, op("poison", 3), op("bleed", 2)), "Едкое облако"),
        V("Отход", area(5, 1, op("poison", 4), op("draw", 1)), "Облако и отход")])
    dead = shot(7, D(14), **ifs(IF(W("vulnerable"), mult=2)), vfx="headshot", shake=1)
    C["h_deadeye"] = card("Смертельный выстрел", "attack", "gift_sharp_eye", dead, step(1), cost=2, unique=True,
                          retain=True, variants=[
        V("Сильнее", up(dead)),
        V("По кровоточащему", shot(7, D(14), **ifs(IF(W("bleeding"), mult=2))), "Выстрел по следу"),
        V("Издалека", shot(8, D(12), **ifs(IF(W("far", n=5), mult=2))), "Выстрел за горизонт"),
        V("Уязвить", shot(7, D(10), op("vulnerable", 2), **ifs(IF(W("vulnerable"), mult=2))), "Двойной выстрел"),
        V("Изгнание: мощь", shot(7, D(24), **ifs(IF(W("vulnerable"), mult=2))), "Выстрел жизни", exhaust=True)])
    kn = enemy(D(4), op("bleed", 1), op("retreat", 1), vfx="lunge")
    C["h_knife"] = card("Охотничий нож", "attack", "item_dagger", kn, step(1), cost=0, variants=[
        V("Сильнее", up(kn)),
        V("Глубже", enemy(D(3), op("bleed", 3), op("retreat", 1)), "Свежевание"),
        V("Отход", enemy(D(4), op("bleed", 1), op("retreat", 3)), "Удар и прыжок"),
        V("Добрать", enemy(D(4), op("bleed", 1), op("draw", 1)), "Быстрый нож"),
        V("Ослабить", enemy(D(4), op("weak", 2), op("retreat", 1)), "Подрезать")])
    amb = me(op("focus"), op("draw", 2), vfx="hunter_ambush")
    C["h_ambush2"] = card("Засада", "skill", "gift_reed_shadow", amb, step(1), variants=[
        V("Больше", me(op("focus"), op("draw", 3))),
        V("Защита", me(op("focus"), op("draw", 1), B(6)), "Засада в камышах"),
        V("Стрелы", me(op("focus"), make("arrow", 2, "Стрела")), "Засада с колчаном"),
        V("Энергия", me(op("draw", 1), op("energy", 1)), "Внезапная засада"),
        V("Сохранение", me(op("focus"), op("draw", 2)), retain=True)])
    lure = enemy(op("pull", 2), op("vulnerable", 2), rng=5, vfx="tether")
    C["h_lure"] = card("Приманка", "skill", "gift_pack_call", lure, step(1), variants=[
        V("Сильнее", up(lure, 0.5)),
        V("В капкан", enemy(op("pull", 3), op("vulnerable", 1), rng=6), "Затянуть в капкан"),
        V("Кровью", enemy(op("pull", 2), op("bleed", 3), rng=5), "Крюк на верёвке"),
        V("Ослабить", enemy(op("pull", 2), op("weak", 2), rng=5), "Вымотать"),
        V("Добрать", enemy(op("pull", 2), op("vulnerable", 1), op("draw", 1), rng=5), "Быстрая приманка")])
    return C, {}


# ======================= Пиромантка (уровни за жар) =======================
# Горение-двигатель, Изгнание (кормит жаром), Искры (создать), Уязвимость (расплавить), молния, взрывы.

def pyro():
    C = {}
    heat1 = me(op("heat", 1))
    ch = lv((1, enemy(D(4), op("chain", 3, jumps=1), rng=5, vfx="chain_lightning")),
            (2, enemy(D(6), op("chain", 4, jumps=2), rng=5, vfx="chain_lightning")),
            (3, enemy(D(8), op("chain", 6, jumps=3), rng=5, vfx="thunderstorm")))
    C["p_chain"] = card("Цепная молния", "attack", "gift_storm_soul", levels=ch, alt=heat1, variants=[
        LV("Сильнее", None, uplv(ch)),
        LV("Поджечь", "Огненная молния", pluslv(ch, op("burn", 2))),
        LV("Уязвить", "Разряд", pluslv(ch, op("vulnerable", 1))),
        LV("Добрать", "Молния знания", pluslv(ch, op("draw", 1))),
        LV("Оглушить", "Гром", [dict(ch[0]), dict(ch[1]), dict(ch[2], main=plus(ch[2]["main"], op("stun")))])])
    gr = lv((1, area(5, 1, D(3), op("burn", 1), vfx="grenade")), (2, area(5, 1, D(5), op("burn", 2), vfx="grenade")),
            (3, area(5, 1, D(8), op("burn", 3), vfx="grenade", shake=1)))
    C["p_grenade"] = card("Граната", "attack", "gift_reactor", levels=gr, alt=heat1, variants=[
        LV("Сильнее", None, uplv(gr)),
        LV("Шире", "Осколочная", [dict(L, main=dict(L["main"], radius=2)) for L in gr]),
        LV("Ослабить", "Дымовая граната", pluslv(gr, op("weak", 1))),
        LV("Поджечь", "Зажигательная", pluslv(gr, op("ignite", 0))),
        LV("Уязвить", "Кислотная граната", pluslv(gr, op("vulnerable", 1)))])
    oil = lv((1, area(5, 1, op("vulnerable", 1), op("burn", 1), vfx="oil_flask")),
             (2, area(5, 1, op("vulnerable", 2), op("burn", 2), vfx="oil_flask")),
             (3, area(5, 1, op("vulnerable", 3), op("burn", 4), vfx="oil_flask")))
    C["p_oil"] = card("Масляная склянка", "skill", "mat_amber", levels=oil, alt=heat1, variants=[
        LV("Сильнее", None, uplv(oil)),
        LV("Ослабить", "Едкое масло", pluslv(oil, op("weak", 1))),
        LV("Шире", "Масляный дождь", [dict(L, main=dict(L["main"], radius=2)) for L in oil]),
        LV("Урон", "Горящее масло", pluslv(oil, D(3))),
        LV("Добрать", "Склянка в запасе", pluslv(oil, op("draw", 1)))])
    sp = lv((1, me(make("t_spark", 1, "Искра"), vfx="fuse")), (2, me(make("t_spark", 2, "Искра"), vfx="fuse")),
            (3, me(make("t_spark", 3, "Искра"), op("heat", 1), vfx="fuse")))
    C["p_sparks"] = card("Сноп искр", "skill", "mat_ember", levels=sp, alt=heat1, variants=[
        LV("Больше", None, [dict(L, main=plus(L["main"], make("t_spark", 1, "Искра"))) for L in sp]),
        LV("Защита", "Искры и щит", pluslv(sp, B(3))),
        LV("Добрать", "Искры и пепел", pluslv(sp, op("draw", 1))),
        LV("Горение", "Жгучие искры", pluslv(sp, op("burn_all", 1))),
        LV("Сохранение", None, sp, retain=True)])
    et = lv((2, power(mod="burn_keep", vfx="flashover")))
    C["p_eternal"] = card("Вечный огонь", "power", "gift_flame_heart", levels=et, alt=heat1, variants=[
        LV("И жар", "Вечный горн", lv((2, power(mod="burn_keep", vfx="flashover", cost_do=[op("heat_regen", 1)])))),
        LV("Пожар", "Вечный пожар", lv((2, power("turn", op("burn", 1), aim="all", vfx="flashover")))),
        LV("Защита", "Огненный кокон", lv((2, power("turn", B(0, per=per("foes_burning", 3)), vfx="flashover")))),
        LV("Всем горящим", "Раздувать", lv((2, power("turn", op("burn_all", 1), vfx="flashover")))),
        LV("Уязвить", "Плавящий жар", lv((2, power("turn", op("vulnerable", 1), aim="all", vfx="flashover"))))])
    ash = lv((2, power("exhaust", op("heat", 1), op("draw", 1), vfx="phoenix")))
    C["p_ash_eater"] = card("Пожиратель пепла", "power", "gift_ash_heart", levels=ash, alt=heat1, variants=[
        LV("Больше", None, lv((2, power("exhaust", op("heat", 2), op("draw", 1), vfx="phoenix")))),
        LV("Защита", "Пепельная броня", lv((2, power("exhaust", B(4), op("heat", 1), vfx="phoenix")))),
        LV("Урон", "Пепельный вихрь", lv((2, power("exhaust", op("burn", 2), aim="all", vfx="phoenix")))),
        LV("Искры", "Пепел в искры", lv((2, power("exhaust", make("t_spark", 1, "Искра"), vfx="phoenix")))),
        LV("Мощь", "Сила пепла", lv((2, power("exhaust", op("strength", 1), vfx="phoenix"))))])
    fo = lv((2, power("turn", make("t_spark", 1, "Искра"), vfx="flame_wall")),
            (3, power("turn", make("t_spark", 2, "Искра"), vfx="flame_wall")))
    C["p_spark_forge"] = card("Кузня искр", "power", "mat_emberheart", levels=fo, alt=heat1, variants=[
        LV("И жар", "Горн искр", pluslv(fo, op("heat", 1))),
        LV("Защита", "Искры-стражи", [dict(L, main=power("turn", make("t_spark", i + 1, "Искра"), B(2),
                                                       vfx="flame_wall")) for i, L in enumerate(fo)]),
        LV("Сразу", "Кузня в ладонях", pluslv(fo, make("t_spark", 2, "Искра"))),
        LV("Жгучие", "Жгучая кузня", lv((2, power("play", op("burn", 1), tag="Огонь", aim="nearest", vfx="flame_wall")),
                                          (3, power("play", op("burn", 2), tag="Огонь", aim="nearest", vfx="flame_wall")))),
        LV("Добор", "Кузня мыслей", lv((2, power("turn", op("draw", 1), vfx="flame_wall")),
                                        (3, power("turn", op("draw", 1), op("heat", 1), vfx="flame_wall"))))])
    ht = lv((1, power("play", B(2), tag="Огонь", vfx="phoenix")), (3, power("play", B(4), tag="Огонь", vfx="phoenix")))
    C["p_heart"] = card("Сердце пламени", "power", "gift_fire_soul", levels=ht, alt=heat1, variants=[
        LV("Сильнее", None, lv((1, power("play", B(3), tag="Огонь", vfx="phoenix")),
                                (3, power("play", B(5), tag="Огонь", vfx="phoenix")))),
        LV("Лечение", "Целебное пламя", lv((1, power("play", op("heal", 1), tag="Огонь", vfx="phoenix")),
                                            (3, power("play", op("heal", 2), tag="Огонь", vfx="phoenix")))),
        LV("Контратака", "Огненный ответ", lv((1, power("play", op("counter", 1), tag="Огонь", once=True, vfx="phoenix")),
                                               (3, power("play", op("counter", 1), tag="Огонь", vfx="phoenix")))),
        LV("Урон", "Пылающее сердце", lv((1, power("play", D(2), tag="Огонь", aim="nearest", vfx="phoenix")),
                                          (3, power("play", D(4), tag="Огонь", aim="nearest", vfx="phoenix")))),
        LV("Мощь", "Жар в крови", lv((1, power("play", op("strength", 1), tag="Огонь", once=True, vfx="phoenix")),
                                      (3, power("turn", op("strength", 1), B(3), vfx="phoenix"))))])
    sac = lv((1, me(op("burn_card", 1), op("heat", 2), vfx="flashpoint")),
             (2, me(op("burn_card", 1), op("heat", 3), op("draw", 1), vfx="flashpoint")),
             (3, me(op("burn_card", 2), op("heat", 5), op("draw", 2), vfx="flashpoint")))
    C["p_sacrifice"] = card("Жертвенный огонь", "skill", "gift_witch_gift", levels=sac, alt=heat1, variants=[
        LV("Больше жара", None, [dict(L, main=plus(L["main"], op("heat", 1))) for L in sac]),
        LV("Защита", "Огненная жертва", pluslv(sac, B(4))),
        LV("Искры", "Пепел в искры", pluslv(sac, make("t_spark", 1, "Искра"))),
        LV("Горение", "Жертва пламени", pluslv(sac, op("burn_all", 2))),
        LV("Лечение", "Очищающий огонь", pluslv(sac, op("heal", 3)))])
    wh = lv((1, enemy(D(2, per=per("foes_burning", 2)), rng=3, vfx="fan_flames")),
            (2, enemy(D(3, per=per("foes_burning", 3)), rng=4, vfx="fan_flames")),
            (3, enemy(D(4, per=per("foes_burning", 4)), op("burn_all", 1), rng=4, vfx="e_flame_breath")))
    C["p_whip"] = card("Огненная плеть", "attack", "fx_fire_wall", levels=wh, alt=heat1, variants=[
        LV("Сильнее", None, uplv(wh)),
        LV("По горению", "Плеть-жало", [dict(L, main=enemy(D(2, per=per("burn", i + 2)), rng=4, vfx="fan_flames"))
                                        for i, L in enumerate(wh)]),
        LV("Поджечь", "Плеть с искрами", pluslv(wh, op("burn", 2))),
        LV("Притянуть", "Плеть-аркан", pluslv(wh, op("pull", 2))),
        LV("Отход", "Хлёсткий отход", pluslv(wh, op("retreat", 2)))])
    keg = lv((2, area(4, 2, D(6), op("burn", 1), vfx="powder_keg")), (3, area(4, 2, D(10), op("burn", 2), vfx="powder_keg")),
             (4, area(4, 2, D(14), op("ignite", 1), vfx="powder_keg", shake=1)))
    C["p_keg"] = card("Пороховая бочка", "attack", "gift_reactor", levels=keg, alt=heat1, exhaust=True, variants=[
        LV("Сильнее", None, uplv(keg)),
        LV("Без изгнания", "Бочонок", [dict(L, main=up(L["main"], -0.3)) for L in keg], exhaust=False),
        LV("Уязвить", "Шрапнель", pluslv(keg, op("vulnerable", 2))),
        LV("Оглушить", "Контузия", pluslv(keg, op("weak", 2))),
        LV("Дальше", "Бросок бочки", [dict(L, main=dict(L["main"], range=6)) for L in keg])])
    rn = lv((2, area(6, 3, op("burn", 2), vfx="barrel_rain")), (3, area(6, 3, op("burn", 3), D(3), vfx="barrel_rain")))
    C["p_fire_rain"] = card("Огненный ливень", "attack", "fx_meteor", levels=rn, alt=heat1, exhaust=True, variants=[
        LV("Сильнее", None, uplv(rn)),
        LV("Без изгнания", "Огненный дождь", [dict(L, main=dict(up(L["main"], -0.4), radius=2)) for L in rn],
           exhaust=False),
        LV("Уязвить", "Плавящий ливень", pluslv(rn, op("vulnerable", 1))),
        LV("Поджечь", "Ливень-пожар", pluslv(rn, op("ignite", 0))),
        LV("Ослабить", "Пепельный ливень", pluslv(rn, op("weak", 1)))])
    melt = lv((1, enemy(op("vulnerable", 1), op("burn", 1), rng=4, vfx="volatile_mix")),
              (2, enemy(op("vulnerable", 2), op("burn", 2), rng=4, vfx="volatile_mix")),
              (3, enemy(op("vulnerable", 3), op("burn", 3), rng=5, vfx="volatile_mix",
                        **ifs(IF(W("burning"), do=[op("burn", 3)])))))
    C["p_melt"] = card("Расплавить броню", "skill", "gift_reactor", levels=melt, alt=heat1, variants=[
        LV("Сильнее", None, uplv(melt, 0.5)),
        LV("Урон", "Расплавить и ударить", pluslv(melt, D(4))),
        LV("Слабость", "Расплавить волю", pluslv(melt, op("weak", 1))),
        LV("Добрать", "Знание металла", pluslv(melt, op("draw", 1))),
        LV("Всем вокруг", "Плавильня", [dict(L, main=area(5, 1, *L["main"]["do"], vfx="volatile_mix")) for L in melt])])
    smk = lv((1, me(B(4), adj(op("weak", 1)), vfx="ash_veil")), (2, me(B(6), adj(op("weak", 2)), vfx="ash_veil")),
             (3, me(B(9), adj(op("weak", 2)), op("fort", 1), vfx="ash_veil")))
    C["p_smoke"] = card("Дымовая завеса", "skill", "fx_fog", levels=smk, alt=heat1, variants=[
        LV("Сильнее", None, uplv(smk)),
        LV("Отход", "Уйти в дым", [dict(L, main=step(2, *L["main"]["do"], vfx="ash_veil")) for L in smk]),
        LV("Добрать", "Дым и пепел", pluslv(smk, op("draw", 1))),
        LV("Жгучий", "Едкий дым", pluslv(smk, adj(op("burn", 2)))),
        LV("Сохранение", None, smk, retain=True)])
    sun = lv((2, area(5, 1, D(10), vfx="meteor", shake=1)), (3, area(5, 1, D(18), op("burn", 3), vfx="meteor", shake=1)),
             (4, area(5, 2, D(24), op("burn", 4), op("ignite", 1), vfx="meteor", shake=1)))
    C["p_sun"] = card("Солнечное ядро", "attack", "fx_meteor", levels=sun, alt=heat1, unique=True, exhaust=True,
                      variants=[
        LV("Сильнее", None, uplv(sun, 0.3)),
        LV("Без изгнания", "Малое солнце", [dict(L, main=up(L["main"], -0.35)) for L in sun], exhaust=False),
        LV("Уязвить", "Плавящее солнце", pluslv(sun, op("vulnerable", 2))),
        LV("Сохранение", None, sun, retain=True),
        LV("Жар", "Солнце в ладонях", pluslv(sun, op("heat", 2)))])
    gy = lv((1, area(5, 1, D(3), op("push", 1), vfx="geyser")), (2, area(5, 1, D(5), op("push", 1), op("burn", 1), vfx="geyser")),
            (3, area(5, 1, D(8), op("push", 2), op("burn", 2), vfx="geyser")))
    C["p_geyser"] = card("Огненный гейзер", "attack", "fx_fire_wall", levels=gy, alt=heat1, variants=[
        LV("Сильнее", None, uplv(gy)),
        LV("Столкновения", "Взрывной гейзер", pluslv(gy, op("collide_x2", 2))),
        LV("Ослабить", "Паровой гейзер", pluslv(gy, op("weak", 1))),
        LV("Уязвить", "Кипящий гейзер", pluslv(gy, op("vulnerable", 1))),
        LV("Поджечь", "Гейзер лавы", pluslv(gy, op("ignite", 0)))])
    arm = lv((1, me(B(4), op("counter", 1), vfx="powder_plate")), (2, me(B(6), op("counter", 2), vfx="powder_plate")),
             (3, me(B(8), op("counter", 3), op("thorns", 3), vfx="powder_plate")))
    C["p_flame_armor"] = card("Пламенный доспех", "skill", "fx_phoenix_shield", levels=arm, alt=heat1, variants=[
        LV("Сильнее", None, uplv(arm)),
        LV("Оборона", "Тлеющий доспех", pluslv(arm, op("fort", 1))),
        LV("Жгучий", "Жгучий доспех", pluslv(arm, adj(op("burn", 2)))),
        LV("Мощь", "Доспех ярости", pluslv(arm, op("strength", 1))),
        LV("Сохранение", None, arm, retain=True)])
    bo = lv((1, me(op("burn_card", 1), op("draw", 2), vfx="flashover")), (2, me(op("burn_card", 2), op("draw", 3), vfx="flashover")),
            (3, me(op("burn_card", 2), op("draw", 3), op("heat", 2), vfx="flashover")))
    C["p_burnout"] = card("Выгорание", "skill", "gift_spellsurge", levels=bo, alt=heat1, variants=[
        LV("Больше", None, pluslv(bo, op("draw", 1))),
        LV("Защита", "Пепельный щит", pluslv(bo, B(0, per=per("exhausted", 2)))),
        LV("Урон", "Вспышка пепла", pluslv(bo, op("aoe_radius", r=2, do=[D(0, per=per("exhausted", 2))]))),
        LV("Искры", "Искры из пепла", pluslv(bo, make("t_spark", 2, "Искра"))),
        LV("Жар", "Жаркое выгорание", pluslv(bo, op("heat", 1)))])
    for cid in ("p_eternal", "p_spark_forge", "p_oil", "p_melt", "p_smoke", "p_flame_armor", "p_sun", "p_ash_eater"):
        C[cid]["element"] = "fire"                     # огонь Пиромантки: [Огонь] для Резонанса и Сердца пламени
    tk = token("Искра", "mat_ember", enemy(D(2), op("burn", 1), rng=4, vfx="_d_quick_arrow"), "lava_raft")
    return C, {"t_spark": tk}


def main():
    p = os.path.join(D_, "cards.json")
    data = json.load(open(p, encoding="utf-8"))
    cards = data["cards"]
    ph = os.path.join(D_, "heroes.json")
    heroes = json.load(open(ph, encoding="utf-8"))
    for hid, fn in (("merc", merc), ("hunter", hunter), ("pyro", pyro)):
        new, tokens = fn()
        cards.update(new)
        cards.update(tokens)
        hd = heroes["heroes"][hid]
        for cid in new:
            if cid not in hd["rewards"]:
                hd["rewards"].append(cid)
        print(f"{hid}: {len(new)} карт" + (f", токены: {', '.join(tokens)}" if tokens else ""))
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(heroes, open(ph, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
