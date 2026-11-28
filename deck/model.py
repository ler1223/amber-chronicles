"""Карты, колода и забег «Спуска»: данные (data/deck/), текст карты по её операциям, прозрения."""
import copy
import json
import os
import random
import re

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "deck")
BALLISTA_HP = 12
BALLISTA_CHARGES = 10
BALLISTA_CARD = "h_ballista"
BALLISTA_COMMANDS = ("h_ballista_load", "h_ballista_fire")
HAND_COPY_CARD = "n_hand_copy"
SPIRIT_ROMAN = ("I", "II", "III")
BALLISTA_DAMAGE_BUFFS = {"strength", "strength_x2", "ranged_bonus", "focus", "empower", "double_next", "double_attacks"}
FIELD_STANCES = {
    "ready": ("Боевая стойка", "Первое получение защиты за ход даёт ещё 2.", (235, 198, 126)),
    "knight": ("Стойка коня", "Добровольное движение становится прыжком на две клетки по одной оси и на одну "
               "по другой. Первый прыжок за ход даёт 3 защиты.", (165, 211, 255)),
    "guard": ("Глухая оборона", "Получаемая защита ×1.5, с округлением вверх. Карты атаки недоступны.",
              (138, 191, 245)),
}
STANCE_SWITCH = "Тот же приём выводит из стойки. Другая стойка сменяет текущую."


def ballista_buff_op(op):
    kind = op.get("op")
    return kind in BALLISTA_DAMAGE_BUFFS and (kind != "empower" or tag_id(op.get("tag")) == "shot")


def can_buff_ballista(use):
    if use.get("target") != "self":
        return False
    groups = [use, use.get("power") or {}, *use.get("if", [])]
    return any(ballista_buff_op(op) for group in groups for op in group.get("do", []))


def card_ranks(d):
    return d.get("ranks") or d.get("spirit_ranks") or ()


def card_rules(d):
    rules = set(d.get("rules", ()))
    rules.update(rule for rule in ("retain", "exhaust", "unique") if d.get(rule))
    if d.get("deck_unique"):
        rules.add("unique")
    if d.get("spirit_ranks"):
        rules.add("merge")
    return frozenset(rules)


def exhaust_limit(rules):
    """Через сколько основных розыгрышей карта изгоняется: None, 1, 2, 3…"""
    limit = None
    for rule in rules:
        if rule == "exhaust":
            limit = max(limit or 0, 1)
        elif rule.startswith("exhaust_"):
            try:
                limit = max(limit or 0, int(rule.split("_", 1)[1]))
            except ValueError:
                pass
    return limit


def card_reactions(d, event):
    declared = d.get("reactions", {})
    if event in declared:
        return tuple(declared[event])
    if event == "retained":
        return tuple(d.get("retain_do", ()))
    if event == "hand_turn_end" and d.get("grow_end"):
        return ({"op": "temper_card", "n": int(d["grow_end"].get("n", 1))},)
    return ()


def load():
    out = {}
    for name in ("cards", "enemies", "heroes", "gods", "relics"):
        with open(os.path.join(DATA_DIR, f"{name}.json"), encoding="utf-8") as f:
            out[name] = json.load(f)
    ill = os.path.join(os.path.dirname(DATA_DIR), "..", "assets", "illustrations", "hd")
    have = set(os.listdir(ill)) if os.path.isdir(ill) else set()
    for cid, d in out["cards"]["cards"].items():          # своя иллюстрация карты (DC6) — вместо фрагмента события
        if f"card_{cid}.png" in have:
            d["ill"] = [f"card_{cid}", 0.5, 0.5, 1.0]
        if card_ranks(d):
            rank_art = [f"card_{cid}_{rank.lower()}" for rank in SPIRIT_ROMAN]
            d["spirit_ill"] = {i: [name, 0.5, 0.5, 1.0] for i, name in enumerate(rank_art, 1)
                               if f"{name}.png" in have}
    return out


# ---------- текст карты ----------

def _op_text(op):
    t = op["op"]
    n = op.get("n")
    if t in ("temper_card", "temper_spirit", "next_fire_damage", "card_damage_buff", "reduce_burn", "spirit_ignite") or (
            t == "pull" and op.get("burn_on_move")):
        return plain(_op_phrase(op)).rstrip(".")
    return {
        "damage": lambda: f"{n} урона",
        "block": lambda: f"{n} защиты",
        "push": lambda: f"толчок {n}",
        "pull": lambda: f"притянуть {n}",
        "burn": lambda: f"горение {n}",
        "poison": lambda: f"яд {n}",
        "frost": lambda: f"мороз {n}",
        "wet": lambda: "мокрый",
        "weak": lambda: f"слабость {n}",
        "vulnerable": lambda: f"уязвимость {n}",
        "stun": lambda: "оглушение",
        "mark": lambda: f"метка {n}",
        "hunt": lambda: f"преследование {n}",
        "draw": lambda: f"+{n} карта" if n == 1 else f"+{n} карты",
        "energy": lambda: f"+{n} энергия",
        "heal": lambda: f"лечение {n}",
        "lose_hp": lambda: f"потерять {n} HP",
        "strength": lambda: f"+{n} мощи",
        "bleed": lambda: f"кровотечение {n}",
        "counter": lambda: f"контратака {n}",
        "copy_hand": lambda: "копия другой карты из руки до конца боя",
        "burn_card": lambda: f"изгнать {n} карт из руки",
        "strength_x2": lambda: "мощь ×2",
        "chain": lambda: f"молния {n} перескакивает",
        "body_slam": lambda: f"урон = ваша защита + {n}" if n else "урон = вашей защите",
        "collide_x2": lambda: "столкновения ×2 в этот ход",
        "thorns": lambda: f"шипы {n} (в ответ на удар)",
        "cleanse": lambda: "снять слабость и уязвимость",
        "fort": lambda: "оборона: половина защиты останется",
        "rage": lambda: "каждый ход +1 энергия и −2 HP",
        "aoe_adjacent": lambda: "все соседние враги: " + ", ".join(_op_text(o) for o in op["do"]),
        "aoe_radius": lambda: f"враги в {op['r']} кл.: " + ", ".join(_op_text(o) for o in op["do"]),
    }.get(t, lambda: t)()


def use_text(u):
    """Текст одного применения карты: цель + операции."""
    ops = ", ".join(_op_text(o) for o in u.get("do", []))
    t = u["target"]
    if t == "enemy":
        where = "рядом" if u.get("range", 1) <= 1 else f"до {u['range']} кл." + (", по обзору" if u.get("los") else "")
        return f"{ops} ({where})" if ops else where
    if t == "reach":
        r = u.get("reach", 1)
        return f"подойти до {r} кл. к врагу: {ops}"
    if t == "cell_step":
        return f"шаг {u.get('step', 1)}" + (f", {ops}" if ops else "")
    if t == "cell_dash":
        return f"рывок по прямой до {u.get('dash', 1)}" + (f", {ops}" if ops else "")
    return ops or "—"


# ---------- текст карты с разметкой (лицо карты, журнал боя) ----------

def _n(v):
    return "{" + str(v) + "}"


def _dmg(v):
    """Число урона с учётом текущих баффов: на лице карты — зелёным."""
    return "@{" + str(v) + "}"


def _signed(v):
    return ("+" if v > 0 else "−") + str(abs(v))


def _fae_tok(v):
    """Значок фей в тексте: ^+2 — прибавка, ^-1 — трата; рисуется иконкой."""
    return "^" + (f"+{v}" if v >= 0 else str(v))


def _low(s):
    """Первая буква (после разметки *, ~) — строчная; остальное как есть."""
    for i, ch in enumerate(s):
        if ch.isalpha():
            return s[:i] + ch.lower() + s[i + 1:]
        if ch == "{":
            return s
    return s


def _op_phrase(op, dmg=None):
    t = op["op"]
    n = op.get("n")
    if t == "body_slam":
        if n:
            if dmg is not None:
                return f"Нанести {_dmg(dmg)} урона (*защита* + {_n(n)})."
            return f"Нанести урон в размере вашей *защиты* + {_n(n)}."
        if dmg is not None:
            return f"Нанести {_dmg(dmg)} урона, равного вашей *защите*."
        return "Нанести урон, равный вашей *защите*."
    if t == "stance":
        name, effect, _ = FIELD_STANCES[op["id"]]
        return f"*{name}*. {effect} Повтор карты снимает стойку."
    if t == "ballista_place":
        return (f"Поставить *баллисту* с {_n(op.get('hp', BALLISTA_HP))} прочности."
                + (f" Начальный заряд {_n(op['charge'])}." if op.get("charge") else "")
                + " Положить зарядку и залп наверх колоды.")
    if t == "ballista_load":
        return f"При выборе *баллисты* дать ей {_n(n)} заряда."
    if t == "ballista_fire":
        return (f"*Баллиста* стреляет по первому врагу на линии. {_n(n or 5)} урона, ещё "
                f"{_n(op.get('per_charge', 3))} за каждый заряд сверх первого. Тратит все заряды.")
    if t == "copy_hand":
        return "Превратиться в *копию* другой карты из руки до конца боя."
    if t == "trigger_retain":
        return ("Дважды активировать эффект *сохранения* выбранной карты." if n == 2
                else "Активировать эффект *сохранения* выбранных карт.")
    if t == "grant_retain":
        return ("Дать выбранным картам *сохранение* до конца хода."
                + (f" Если карта сохранится, её первый розыгрыш в следующем ходу дешевле на {_n(n)}." if n else ""))
    if t == "retain_rewards":
        rewards = []
        if n:
            rewards.append(f"{_n('+' + str(n))} урона к первой огненной атаке следующего хода")
        if op.get("block"):
            rewards.append(f"{_n(op['block'])} защиты перед ходом врагов")
        return "За каждую карту, сохранённую в конце хода: " + " и ".join(rewards) + "."
    if t == "create_retain":
        return (f"*Создать* {_n(n)} случайную карту с *Сохранением*. Карты с рангами создаются на I ранге. "
                "У Пиромантки созданные карты за энергию стоят столько же *жара*.")
    if t in ("temper_card", "temper_spirit"):
        return f"Урон этой карты {_n('+' + str(n))} до конца боя."
    if t == "next_fire_damage":
        return f"Первая атака [Огонь] в следующий ход получает {_n('+' + str(n))} к урону."
    if t == "card_damage_buff":
        kind = "атака" if op.get("type") == "attack" else "карта"
        tag = f" [{tag_label(op['tag'])}]" if op.get("tag") else ""
        delay = op.get("delay", 1)
        when = "в этот ход" if delay == 0 else "в следующий ход" if delay == 1 else f"через {delay} хода"
        return f"Первая {kind}{tag} {when} получает {_n('+' + str(n))} к урону."
    if t == "reduce_burn":
        return f"Снять {_n(n)} *горения* с героя."
    if t == "spirit_ignite":
        return ("*Поджечь* клетку цели и четыре соседние по сторонам."
                if n else "*Поджечь* клетку цели.")
    if t == "pull" and op.get("burn_on_move"):
        return f"*Притянуть* {_n(n)}. При сдвиге наложить {_n(op['burn_on_move'])} *горения*."
    if t == "note":
        return op.get("text", "")
    if t == "plant":
        grow = op.get("grow_text")
        return "Семя" + (f" (рост {_n(grow)})" if grow else "") + "."
    if t == "beast":
        return "Зверь."
    if t == "attach":
        return "Привить."
    if t == "fae_ring":
        return f"Кольцо на {_n(n or 3)} хода."
    if t == "blueprint":
        return "Части — в колоду и сброс."
    if t == "execute_below":
        return f"*Казнь*: цель ниже {_n(n)}% HP погибает."
    if t == "discard_hand":
        return "Сбросить выбранную карту."
    if t == "damage_nearest":
        return f"Нанести {_n(n)} урона ближайшему врагу."
    if t in ("aoe_target", "aoe_center"):
        return f"Врагам в {_n(op.get('r', 1))} кл.: " + _low(" ".join(_op_phrase(o) for o in op["do"]))
    if op.get("per"):                                       # «за каждую…»
        per = op["per"]
        if t == "pull":
            return f"*Притянуть* на {_n(n)}, ещё {_n(per.get('k', 1))} {per_text(per)}."
        if per.get("what") != "fae":
            word = {"damage": "урона", "block": "*защиты*", "bleed": "*кровотечения*", "burn": "*горения*",
                    "poison": "*яда*", "mark": "*метки*", "heal": "*лечения*",
                    "counter": "*контратаки*"}.get(t, t)
            verb = {"damage": "Нанести", "block": "Получить", "heal": "Восстановить",
                    "counter": "Получить"}.get(t, "Наложить")
            shown = _dmg(dmg) if t == "damage" and dmg is not None else _n(n)
            head = f"{verb} {shown} {word}" if n else f"{verb} {word}"
            return f"{head}: {_n('+' + str(per.get('k', 1)))} {per_text(per)}."
        word = {"damage": "урона", "block": "защиты", "bleed": "кровотечения", "burn": "горения",
                "poison": "яда", "mark": "метки", "heal": "лечения", "counter": "контратаки",
                "fae": "фея"}.get(t, t)
        verb = {"damage": "Нанести", "block": "Получить", "heal": "Восстановить", "counter": "Получить",
                "fae": "Получить"}.get(t, "Наложить")
        shown = _dmg(dmg) if t == "damage" and dmg is not None else (f"^{n:+d}" if t == "fae" else _n(n))
        head = f"{verb} {shown} {word}" if n else ""
        k = per.get("k", 1)
        add = ("^" + f"+{k}") if t == "fae" else _n("+" + str(k))
        tail = (f"За каждые {_n(per['div'])} фей" if per.get("div") else "За фею") + f": {add} {word}."
        return f"{head}. {tail}" if head else tail
    if t == "damage":
        shown = _dmg(dmg) if dmg is not None else _n(n)
        s = f"Нанести {shown} урона"
        if op.get("x"):
            s += f" +{_n(op['x'])}×X"
        if op.get("mom_k"):
            s += f" {_n('+' + str(op['mom_k']))}×*разгон*"
        if op.get("far"):
            s += f"; цель дальше {_n(op['far']['d'])} — ещё {_n('+' + str(op['far']['bonus']))}"
        if op.get("ignore_shield"):
            s += " (*щит* цели не спасает)"
        return s + "."
    if t == "block":
        s = f"Получить {_n(n)} *защиты*"
        if op.get("mom_k"):
            s += f" {_n('+' + str(op['mom_k']))}×*разгон*"
        return s + "."
    if t == "heat":
        return f"{_n(_signed(n))} *жара*."
    if t == "ignite":
        r = op.get("n", 0)
        return "*Поджечь* клетку." if not r else f"*Поджечь* клетки в радиусе {_n(r)}."
    if t == "detonate":
        s = f"Горящие враги в {_n(op.get('r', 4))} кл. получают урон = *горение* ×{_n(n)}."
        return s + (" *Горение* гаснет." if op.get("clear") else "")
    if t == "add_card":
        if op.get("pool"):
            if op.get("same"):
                return f"*Создать* {_n(n)} копии одной случайной карты из набора «{op['pool_name']}»."
            if op.get("distinct"):
                first = f" «{op['cname']}» среди них." if op.get("cname") else ""
                return f"*Создать* {_n(n)} разные карты из набора «{op['pool_name']}»." + first
            return f"*Создать* {_n(n)} из набора «{op.get('pool_name', 'Случайные карты')}»."
        nm = op.get("cname")
        if nm:
            return f"*Создать* {_n(n)} «{nm}»."
        return f"В руку {_n(n)} " + ("*Стрелу*." if n == 1 else "*Стрелы*.")
    if t == "chain":
        if not n and op.get("stun"):
            return f"*Оглушение* {_n(op.get('jumps', 2))} соседних врагов."
        return f"*Молния*: ещё {_n(op.get('jumps', 2))} врагам рядом по {_n(n)} урона."
    if t == "hunt":
        return f"Получить {_n(n)} *преследования*."
    return {
        "push": lambda: f"*Толчок* {_n(n)}.",
        "pull": lambda: f"*Притянуть* {_n(n)}.",
        "burn": lambda: f"*Горение* {_n(n)}.",
        "poison": lambda: f"*Яд* {_n(n)}.",
        "frost": lambda: f"*Мороз* {_n(n)}.",
        "wet": lambda: "Цель *мокрая*.",
        "weak": lambda: f"*Слабость* {_n(n)}.",
        "vulnerable": lambda: f"*Уязвимость* {_n(n)}.",
        "stun": lambda: "*Оглушение*.",
        "mark": lambda: f"*Метка* {_n(n)}.",
        "draw": lambda: f"Взять {_n(n)} " + ("карту." if n == 1 else "карты."),
        "discard_choose": lambda: f"Сбросить {_n(n)} " + ("карту (выберите)." if n == 1 else "карты (выберите)."),
        "energy": lambda: f"Получить {_n(n)} *энергию*.",
        "heal": lambda: f"*Лечение* {_n(n)}.",
        "lose_hp": lambda: f"Потерять {_n(n)} HP.",
        "strength": lambda: f"Получить {_n(n)} *мощи*.",
        "bleed": lambda: f"*Кровотечение* {_n(n)}.",
        "counter": lambda: f"*Контратака* {_n(n)}.",
        "burn_card": lambda: f"*Изгнать* {_n(n)} " + ("случайную карту из руки." if n == 1 else "случайные карты из руки."),
        "strength_x2": lambda: "Удвоить *мощь*.",
        "double_attacks": lambda: f"Следующие {_n(n)} карты атаки: урон ×2.",
        "collide_x2": lambda: f"*Столкновения* в этот ход {_n('×' + str(n or 2))}.",
        "thorns": lambda: f"*Шипы* {_n(n)} до конца хода.",
        "cleanse": lambda: "Снять *слабость* и *уязвимость*.",
        "fort": lambda: "*Оборона*: половина защиты останется на следующий ход.",
        "rage": lambda: "В начале хода: {+1} *энергия*, {−2} HP.",
        "retreat": lambda: f"*Отскок* на {_n(n)} от цели.",
        "root": lambda: f"*Корни* {_n(n)}: цель не двигается.",
        "ranged_bonus": lambda: f"Дальние атаки {_n('+' + str(n))} до конца боя.",
        "trap": lambda: f"*Капкан*: враг, наступивший сюда, получит {_n(n)} урона и встанет.",
        "focus": lambda: "Следующая дальняя атака {×2}.",
        "burn_all": lambda: f"Всем горящим врагам: ещё {_n('+' + str(n))} *горения*.",
        "scrape": lambda: "Отскрести *тину* — мусор от врагов.",
        "empower": lambda: ("Следующая карта [" + tag_label(op["tag"]) + "] в этот ход: ещё "
                            if op.get("tag") else "Следующая атака в этот ход: ещё ") +
                           f"{_n('+' + str(n))} урона.",
        "heat_regen": lambda: f"В начале хода {_n('+' + str(n))} *жар*.",
        "keep_momentum": lambda: "*Разгон* больше не гаснет в конце хода.",
        "momentum": lambda: f"{_n('+' + str(n))} *разгона*.",
        "fae": lambda: f"Получить {_fae_tok(n)}.",
        "spend_fae": lambda: f"Потратить {_fae_tok(-n)}.",
        "plant": lambda: "*Посадить растение*.",
        "attach": lambda: "*Привить* к карте.",
        "aoe_adjacent": lambda: "Всем соседним врагам: " + _low(" ".join(_op_phrase(o) for o in op["do"])),
        "aoe_radius": lambda: (f"Врагам в {_n(op['r'])} клетках"
                               + (f" (с порогом — в {_n(op['r_fae']['r'])})" if op.get("r_fae") else "")
                               + ": " + _low(" ".join(_op_phrase(o) for o in op["do"]))),
    }.get(t, lambda: t)()


PER_TEXT = {
    "played": "за каждую карту, сыгранную до неё в этот ход", "strength": "за каждую *мощь*",
    "bleed": "за каждое *кровотечение* цели", "burn": "за каждое *горение* цели", "poison": "за каждый *яд* цели",
    "mark": "за каждую *метку* цели",
    "vulnerable": "за каждую *уязвимость* цели", "weak": "за каждую *слабость* цели",
    "exhausted": "за каждую *изгнанную* в этом бою карту", "hand": "за каждую карту в руке",
    "counter": "за каждую *контратаку*", "shield": "за каждую *защиту*", "heat": "за каждый *жар*",
    "hunt": "за каждую единицу *преследования*",
    "walked": "за каждую клетку, пройденную в этот ход", "foes_burning": "за каждого горящего врага",
    "foes_bleeding": "за каждого кровоточащего врага", "foes": "за каждого врага",
    "powers": "за каждую сыгранную *Силу*",
    "fae": "за каждую *фею*",
}


def per_text(per):
    w = per["what"]
    if w.startswith("tag:"):
        return f"за каждую карту [{tag_label(w[4:])}], сыгранную до неё в этот ход"
    if per.get("div"):
        return f"за каждые {_n(per['div'])} " + {"fae": "фей"}.get(w, PER_TEXT.get(w, w))
    return PER_TEXT.get(w, w)


POWER_ON = {"turn": "В начале хода", "play": "Когда играете карту", "step": "За каждую пройденную клетку",
            "kill": "Когда убиваете врага", "hit": "Когда враг бьёт вас", "exhaust": "Когда карта *изгнана*",
            "end": "В конце хода"}
POWER_AIM = {"nearest": "ближайшему врагу — ", "source": "ему — ", "adjacent": "соседним врагам — ",
             "all": "всем врагам — "}
POWER_MOD = {"burn_keep": "*Горение* врагов не спадает.", "bleed_keep": "*Кровотечение* врагов не убывает.",
             "retain": "Карты в руке не сбрасываются в конце хода.",
             "counter_plus": "*Контратака* бьёт на {n} сильнее.",
             "counter_bleed": "*Контратака* ещё и пускает кровь: *кровотечение* {2}."}


def power_text(pw):
    """Сила до конца боя: «В начале хода: …» или постоянное правило."""
    out = ["*Сила до конца боя*."]
    if pw.get("mod"):
        out.append(POWER_MOD[pw["mod"]].replace("{n}", _n("+" + str(pw.get("n", 0)))))
    if pw.get("on"):
        head = POWER_ON[pw["on"]]
        if pw.get("tag"):
            head += f" [{tag_label(pw['tag'])}]"
        ops = _low(" ".join(_ops_phrases(pw.get("do", []))))
        out.append(f"{head}: {POWER_AIM.get(pw.get('aim'), '')}{ops}" + (" Раз за ход." if pw.get("once") else ""))
    return " ".join(out)


COND_NAMES = {"series": "Серия", "after": "Вслед за", "resonance": "Резонанс", "first": "Первая",
              "allin": "Ва-банк", "adjacent": "Вплотную", "far": "Издалека", "run": "С разбега",
              "not_walked": "Без шага", "wall": "У стены",
              "surrounded": "В окружении", "cover": "Из укрытия", "burning": "По горящему", "wet": "По мокрому",
              "poisoned": "По отравленному", "marked": "По помеченному", "wounded": "По раненому",
              "momentum": "Разгон", "shielded": "Под щитом", "hurt": "Сам ранен", "duel": "Один на один",
              "back_wall": "Спиной к стене", "stunned": "По оглушённому", "weakened": "По ослабленному",
              "guarded": "Цель со щитом", "vulnerable": "По уязвимому", "bleeding": "По кровоточащему",
              "fae": "Феи", "fae_min": "Феи", "linked_hand": "Связь в руке", "had_lead": "Была скидка",
              "fae_before": "Феи до карты", "second_fae": "Второе применение"}
# условия, которым нужна цель (проверяются по цели удара)
TARGET_CONDS = {"adjacent", "far", "wall", "burning", "wet", "poisoned", "marked", "wounded", "stunned", "weakened",
                "guarded", "vulnerable", "bleeding"}
# события для Отклика: карта в руке срабатывает сама
EVENT_NAMES = {"kill": "убийство", "hit": "получил удар", "near": "враг вплотную"}
NOALT = {"target": "none", "do": []}           # у карты нет простого применения


def cond_text(c, lit=False):
    """Условие разметкой: имя — золотом (выполнено — зелёным), [Тег] — голубым, число — крупно."""
    k = c["k"]
    mark = "~" if lit else "*"
    if k in ("fae", "fae_min", "fae_before"):
        return f"{mark}Порог{mark} {_n(c.get('n', 6))}"
    name = " ".join(f"{mark}{w}{mark}" for w in COND_NAMES[k].split())
    if k == "after":
        return f"{name} [{tag_label(c['tag'])}]"
    if k == "resonance":
        return f"{name} {tag_label(c['tag'])} {_n(c['n'])}"
    if k in ("series", "far", "run", "momentum", "shielded", "second_fae", "linked_hand"):
        return f"{name} {_n(c['n'])}"
    return name


def _if_phrase(c, lit=False):
    head = cond_text(c["when"], lit)
    if c["when"].get("k") == "resonance":
        return head + "."                                   # тег «Резонанс» уже всё объясняет
    bits = []
    if c.get("plus"):
        bits.append(f"ещё {_n('+' + str(c['plus']))} урона.")
    if c.get("mult"):
        bits.append(f"урон {_n('×' + str(c['mult']))}.")
    if c.get("repeat"):
        bits.append("срабатывает дважды.")
    bits += [_op_phrase(o) for o in c.get("do", [])]
    return f"{head}: " + _low(" ".join(bits))


def _ops_phrases(do, preview=None):
    """Фразы действий; одинаковые подряд — одной фразой «×N».
    preview — реальные числа урона по порядку для лицевой стороны в бою."""
    out, k, pi = [], 0, 0
    preview = list(preview or ())
    while k < len(do):
        r = 1
        while k + r < len(do) and do[k + r] == do[k]:
            r += 1
        hit = do[k]["op"] in ("damage", "body_slam")
        dmg = preview[pi] if hit and pi < len(preview) else None
        if hit:
            pi += 1
        ph = _op_phrase(do[k], dmg)
        out.append(ph if r == 1 else ph.rstrip(".") + f" {_n('×' + str(r))}.")
        k += r
    return out


def phrase(u, exhaust=False, lit=(), preview=None):
    """Текст применения с разметкой: {число} — крупно белым, @{число} — реальный урон зелёным
    (в бою, с баффами героя), *слово* — золотом, ~слово~ — выполненное условие, [Тег] — голубым.
    lit — какие условия сейчас выполнены: "seal" и ("if", i)."""
    if u.get("target") == "statue":                       # свиток Жреца: смысл, исполняет бог статуи
        return u.get("say", "")
    do = u.get("do", [])
    preview = list(preview or ())
    buff_choice = "Усиление герою или *баллисте*. " if can_buff_ballista(u) else ""
    if u.get("power"):                                    # Сила: правило до конца боя
        return buff_choice + (" ".join(_ops_phrases(do)) + " " if do else "") + power_text(u["power"])
    if [o["op"] for o in do] == ["heat"] and do[0].get("n", 0) > 0 and u["target"] == "self" and not u.get("if"):
        return f"*Раздуть*: {_n(_signed(do[0]['n']))} *жар*."
    parts = [buff_choice.strip()] if buff_choice else []
    if u.get("seal"):
        parts.append(f"*Печать* ({cond_text(u['seal'], 'seal' in lit)}).")
    t = u["target"]
    if t == "none" and not do:
        return ""
    if t == "cell_step":
        extra = (f" (+1 за каждые {_n(u['step_fae'])} фей)" if u.get("step_fae") else "")
        if u.get("step_thr"):
            extra += f"; с порогом — {_n(u['step_thr'].get('n', 1))}"
        parts.append((f"Можете сделать *шаг* {_n(u.get('step', 1))}{extra}." if u.get("allow_stay")
                      else f"*Шаг* {_n(u.get('step', 1))}{extra}."))
    elif t == "cell_dash":
        parts.append(f"*Рывок* по прямой {_n(u.get('dash', 1))}.")
    elif t == "reach":
        parts.append(f"Подойти к врагу на {_n(u.get('reach', 1))}, затем:")
    elif t == "enemy" and u.get("range", 1) > 1:
        parts.append(f"*Дальность* {_n(u['range'])}.")
    elif t == "area":
        rad = f"Область радиус {_n(u.get('radius', 1))}"
        if u.get("radius_fae"):
            rad += f" (с порогом — {_n(u['radius_fae'].get('r', 1))})"
        parts.append(f"{rad}, дальность {_n(u.get('range', 5))}:")
    elif t == "cell_any":
        parts.append(f"Клетка в {_n(u.get('range', 4))}:")
    elif t == "plant":
        parts.append(f"Клетка в {_n(u.get('range', 4))}:")
    elif t == "ballista_place":
        parts.append(f"Свободная клетка в {_n(u.get('range', 2))} кл.")
    elif t == "ballista_load":
        parts.append(f"Герой или баллиста в {_n(u.get('range', 2))} кл.")
    elif t == "ballista_fire":
        parts.append(f"Дальность от баллисты {_n(u.get('range', 6))}.")
    elif t == "hand_attach":
        pass                                      # [Прививка] уже объясняет, что карта крепится к карте в руке
    elif t in ("hand_retain", "hand_other", "hand_link"):
        count = u.get("count", 1)
        cards = "другую карту" if count == 1 else f"{_n(count)} другие карты"
        what = " с *Сохранением*" if t == "hand_retain" else " со *Связью*" if t == "hand_link" else ""
        parts.append(f"Выберите {cards}{what} в руке.")
    if u.get("line"):
        parts.append("*Только по прямой*.")
    if u.get("pierce") and not u.get("line_fae"):
        parts.append("*Пробивает всех на линии*.")
    parts += _ops_phrases(do, preview)
    for i, c in enumerate(u.get("if", [])):
        parts.append(_if_phrase(c, ("if", i) in lit))
    if u.get("back"):
        parts.append(f"*Возврат* ({cond_text(u['back'], 'back' in lit)}): карта снова в руке.")
    if exhaust:
        parts.append("*Изгнание*.")
    return " ".join(parts) or "—"


def retain_phrase(d):
    """Эффект при сохранении карты в конце хода."""
    return " ".join(_ops_phrases(card_reactions(d, "retained")))


def _has_op(x, names):
    """Есть ли в ветке описания действие с одним из имён."""
    if isinstance(x, dict):
        if x.get("op") in names:
            return True
        return any(_has_op(v, names) for v in x.values())
    if isinstance(x, list):
        return any(_has_op(v, names) for v in x)
    return False


def fae_generates(u):
    """Карта-генератор: в основной части даёт фей и не бьёт/защищает/сажает/призывает."""
    chunks = [u.get("do", [])]
    power = u.get("power")
    if isinstance(power, dict):
        chunks.append(power.get("do", []))
    gain = any(op.get("op") == "fae" and isinstance(op.get("n"), int) and op["n"] > 0
               for do in chunks for op in do)
    if not gain:
        return False
    martial = {"block", "heal", "plant", "beast", "attach", "blueprint"}
    for do in chunks:
        for op in do:
            kind = op.get("op", "")
            if kind in martial or kind.startswith("damage"):
                return False
    return True


def fae_burn_value(u, card_type=None):
    """Сколько фей сжигает усиленная карта: генераторы не тратят, атаки — 3+, защита — 2+."""
    if fae_generates(u):
        return 0
    burn = u.get("fae_burn")
    if burn == "all":
        return burn
    if burn == 0:
        return 0
    base = burn if isinstance(burn, int) else (3 if card_type == "attack" else 1)
    if card_type == "attack":
        return max(base, 3)
    if _has_op(u.get("do", []), {"block"}) or _has_op(u.get("if", []), {"block"}):
        return max(base, 2)
    return base


def fae_threshold(u):
    """Порог усиленной версии карты: минимальный N среди условий/полей фей."""
    nums = []
    for c in u.get("if", []):
        w = c.get("when", {}) if isinstance(c, dict) else {}
        if w.get("k") in ("fae", "fae_min", "fae_before") and w.get("n"):
            nums.append(int(w["n"]))
    for key in ("radius_fae", "line_fae"):
        val = u.get(key)
        if isinstance(val, dict) and val.get("fae"):
            nums.append(int(val["fae"]))
        elif isinstance(val, int) and val:
            nums.append(int(val))
    if (u.get("step_thr") or {}).get("fae"):
        nums.append(int(u["step_thr"]["fae"]))
    if u.get("fae_thr"):
        nums.append(int(u["fae_thr"]))
    return min(nums) if nums else None


def fae_empower_text(d):
    """Строка усиления эльфа: сколько фей сжечь и что это даст."""
    u = d.get("main") or {}
    bonus = u.get("fae_bonus") or {}
    threshold = fae_threshold(u)
    burn = fae_burn_value(u, d.get("type"))
    if not burn or not bonus or threshold is None:
        return ""
    spent = "^все" if burn == "all" else "^" + f"-{burn}"
    words = {
        "damage": "урона/фея", "block": "защиты/фея", "heal": "лечения/фея", "draw": "карта/фея",
        "stack": "стак/фея", "growth": "рост/фея", "beast": "HP зверя/фея",
        "duration": "ход кольца/фея", "fae": "фея/фея", "self_block": "защиты/фея",
    }
    parts = [f"+{rate} {words.get(kind, kind)}" for kind, rate in bonus.items()]
    head = f"*Усиление*: порог {_n(threshold)}, " if u.get("fae_thr") else "*Усиление*: "
    return head + f"сжечь {spent}: " + ", ".join(parts) + "."


def card_extras(d, lit=()):
    """Свойства карты целиком (не применения): Отклик и Задел — строкой под основным текстом."""
    out = []
    if d.get("auto_end"):
        out.append("*Авто в конце хода*: не играется вручную.")
    if d.get("grow_end"):
        out.append(f"*Растёт в руке*: +{_n(d['grow_end'].get('n', 1))} урона в конце хода.")
    if d.get("unique") and not d.get("deck_unique"):
        out.append("*Единственная*.")
    if "retain" in card_rules(d):
        retained = retain_phrase(d)
        out.append(f"*Сохранение*: {_low(retained)}" if retained else "*Сохранение*.")
    empower = fae_empower_text(d)
    if empower:
        out.append(empower)
    if d.get("react"):
        out.append("*Реакция*.")
    if d.get("echo"):
        e = d["echo"]
        if e.get("when", {}).get("k") == "resonance":
            out.append(cond_text(e["when"], "echo" in lit) + ".")
        else:
            ops = " ".join(_ops_phrases(e["do"]))
            aim = e.get("aim", "nearest")
            who = {"nearest": "ближайшему врагу — ", "source": "ему — "}.get(aim, "") if e.get("on") != "kill" or \
                aim != "source" else ""
            if e.get("on"):
                head = " ".join(f"*{w}*" for w in EVENT_NAMES[e["on"]].split())
                if e.get("when"):
                    head += f", {cond_text(e['when'], 'echo' in lit)}"
            else:
                head = cond_text(e["when"], "echo" in lit)
            out.append(f"*Отклик* ({head}): {who}{_low(ops)}")
    if d.get("temper"):
        tp = d["temper"]
        head = f" ({cond_text(tp['when'], 'temper' in lit)})" if tp.get("when") else ""
        out.append(f"*Закалка*{head}: после розыгрыша урон и защита карты {_n('+' + str(tp.get('n', 1)))} "
                   "до конца боя.")
    if d.get("keep"):
        out.append(f"*Задел* ({cond_text(d['keep'], 'keep' in lit)}).")
    if d.get("chain"):
        out.append(f"*Цепочка*: {cond_text(d['chain']['when'], 'chain' in lit)}.")
    return " ".join(out)


# ---------- теги: из того, что карта делает ----------

TAG_LABELS = {
    "quietus": "Квиетус",
    "blessing": "Благословение",
    "linked": "Связь",
    "lead": "Наведение",
    "fae": "Фея",
    "spell": "Чары",
    "plant": "Растение",
    "beast": "Зверь",
    "attachment": "Прививка",
    "field": "Поле",
    "assembly": "Сборка",
    "fire": "Огонь",
    "strike": "Удар",
    "shot": "Выстрел",
    "area": "Область",
    "step": "Шаг",
    "block": "Защита",
    "retain": "Сохранение",
    "merge": "Слияние",
    "push": "Толчок",
    "thorns": "Шипы",
    "blood": "Кровь",
    "shout": "Клич",
    "mark": "Метка",
    "pursuit": "Преследование",
    "poison": "Яд",
    "trap": "Ловушка",
    "create": "Создание",
    "spirit": "Дух",
    "exhaust": "Изгнание",
    "combo": "Комбо",
    "resonance": "Резонанс",
    "repeat": "Повтор",
    "chain": "Цепочка",
    "scroll": "Свиток",
    "attack": "Атака",
    "defense": "Оборона",
    "move": "Движение",
    "curse": "Проклятие",
    "gift": "Дар",
    "summon": "Призыв",
    "chorus": "Хор",
    "unique": "Уникальная",
    "initiation": "Инициация",
    "exhaust_2": "Изгнание 2",
    "exhaust_3": "Изгнание 3",
    "ephemeral": "Мимолётная",
    "pulverize": "Дробление",
    "bullet": "Пуля",
    "finale": "Финал",
    "unactivatable": "Неактивируемая",
}
TAG_IDS_BY_LABEL = {label: key for key, label in TAG_LABELS.items()}


def tag_id(value):
    """Читать стабильный ID и старую локализованную ссылку на тег."""
    return TAG_IDS_BY_LABEL.get(value, value)


def tag_label(value):
    return TAG_LABELS.get(value, value)


HAND_TARGETS = ("copy_hand", "hand_retain", "hand_other", "hand_attach", "hand_link")


def use_tags(u):
    ops = [o["op"] for o in u.get("do", [])]
    for o in u.get("do", []):
        ops += [x["op"] for x in o.get("do", [])]          # aoe_adjacent и т.п.
    for c in u.get("if", []):                              # условные усиления тоже часть карты
        ops += [o["op"] for o in c.get("do", [])]
    for o in u.get("do", []):
        for c in o.get("if", []):
            ops += [x["op"] for x in c.get("do", [])]
    t = u.get("target")
    tags = set()
    dmg = {"damage", "body_slam"} & set(ops)
    if dmg and u.get("ranged"):
        tags.add("shot")
    elif dmg and (t in ("reach",) or (t == "enemy" and u.get("range", 1) <= 1) or "aoe_adjacent" in ops):
        tags.add("strike")
    if t == "area" or {"aoe_adjacent", "aoe_radius", "detonate"} & set(ops):
        tags.add("area")
    if "hunt" in ops:
        tags.add("pursuit")
    if {"burn", "ignite", "detonate", "heat", "burn_all", "spirit_ignite", "reduce_burn"} & set(ops) or any(
            o.get("burn_on_move") for o in u.get("do", [])):
        tags.add("fire")
    if t in ("cell_step", "cell_dash", "reach") or "retreat" in ops:
        tags.add("step")
    if "block" in ops:
        tags.add("block")
    if {"push", "pull", "collide_x2"} & set(ops):
        tags.add("push")
    if {"thorns", "counter"} & set(ops):
        tags.add("thorns")
    if {"lose_hp", "rage", "bleed"} & set(ops):
        tags.add("blood")
    if "add_card" in ops or "create_retain" in ops:
        tags.add("create")
    if "burn_card" in ops:
        tags.add("exhaust")
    if {"strength", "empower", "strength_x2"} & set(ops) or any(o["op"] == "aoe_radius" and {x["op"] for x in o["do"]} &
                                                  {"weak", "vulnerable"} for o in u.get("do", [])):
        tags.add("shout")
    if "mark" in ops:
        tags.add("mark")
    if "poison" in ops:
        tags.add("poison")
    if {"trap", "root"} & set(ops):
        tags.add("trap")
    if {"weak", "vulnerable"} & set(ops):
        tags.add("shout")
    if {"ranged_bonus", "focus"} & set(ops):
        tags.add("shot")
    if "heat_regen" in ops:
        tags.add("fire")
    if "summon" in ops:
        tags.add("summon")
    conds = [c.get("when", {}) for c in u.get("if", []) if isinstance(c, dict)]
    if any(c.get("k") in ("fae", "fae_min") for c in conds) or {"fae", "spend_fae"} & set(ops):
        tags.add("fae")
    if any(c.get("repeat") for c in u.get("if", []) if isinstance(c, dict)) or any(
            c.get("k") in ("series", "first", "allin") for c in conds):
        tags.add("combo")
    if any(c.get("k") == "resonance" for c in conds) or (u.get("seal") or {}).get("k") == "resonance":
        tags.add("resonance")
    if any(c.get("repeat") for c in u.get("if", []) if isinstance(c, dict)):
        tags.add("repeat")
    return tags


MEANING_TAGS = {"attack": "Атака", "defense": "Оборона", "move": "Движение", "curse": "Проклятие",
                "gift": "Дар", "summon": "Призыв"}


def card_tag_ids(d):
    """Теги карты: по основному применению (у карт с уровнями — по всем уровням) + заданные вручную."""
    tags = {tag_id(t) for t in d.get("tags", [])}
    if d.get("deck_unique"):
        tags.add("unique")
    if d.get("meaning"):
        tags.add("scroll")
        tags.add(d["meaning"])
        if d["meaning"] == "summon":
            tags.add("summon")
    for a in d.get("acts", []):
        if a.get("m") in MEANING_TAGS:
            tags.add(a["m"])
    if d.get("chorus") or d.get("then") or d.get("double"):
        tags.add("chorus")
    uses = [L["main"] for L in d.get("levels", [])] or [d["main"]]
    uses = uses + [{"target": "enemy", "range": 1, "do": u["power"].get("do", [])} for u in uses if u.get("power")]
    if (d.get("echo") or {}).get("do"):                     # реакция: теги — по тому, что делает отклик
        uses = uses + [{"target": "enemy", "range": 1, "do": d["echo"]["do"]}]
    for u in uses:
        tags |= use_tags(u)
    if d.get("element") == "fire":
        tags.add("fire")
    tags.update(card_rules(d))
    if d.get("exhaust") or any(u.get("exhaust") for u in uses):
        tags.add("exhaust")
    if (d.get("echo") or {}).get("when", {}).get("k") == "resonance":
        tags.add("resonance")
    if d.get("chain"):
        tags.add("chain")
        if (d["chain"].get("when") or {}).get("k") == "resonance":
            tags.add("resonance")
    return tuple(t for t in TAG_LABELS if t in tags) + tuple(sorted(tags - TAG_LABELS.keys()))


def card_tags(d):
    return [tag_label(t) for t in card_tag_ids(d)]


# основа слова → (название, пояснение); порядок важен: первое совпадение по началу слова
GLOSSARY = [(name.lower(), name, effect + " " + STANCE_SWITCH) for name, effect, _ in FIELD_STANCES.values()] + [
    ("баллист", "Баллиста", f"Получает заряд в начале каждого хода игрока, максимум {BALLISTA_CHARGES}. "
                            "Занимает клетку и принимает урон от вражеских зон. Пока она стоит, карта установки "
                            "ждёт в сбросе, а бесплатные зарядка и залп ходят по стопкам. При разрушении команды исчезают."),
    ("кровотеч", "Кровотечение", "В начале хода носителя: урон по числу стаков мимо защиты, затем стаков вдвое "
                                 "меньше. Копите и вскрывайте картами «за каждое кровотечение»."),
    ("контратак", "Контратака", "Стаки: враг ударил вас вплотную — вы сразу отвечаете ударом 4 (+Мощь), стак "
                                "тратится. Держатся, пока не потрачены."),
    ("мощ", "Мощь", "+N к урону каждого удара до конца боя. Копится."),
    ("изгна", "Изгнание", "После розыгрыша карта уходит до конца боя. Изгнанные карты считают некоторые Силы."),
    ("сохранени", "Сохранение", "Карта не сбрасывается в конце хода — остаётся в руке."),
    ("уникальн", "Уникальная", "Один экземпляр в колоде забега."),
    ("копи", "Копия карты", "Слепок принимает свойства выбранной карты из руки на весь бой, включая прозрение и дар. "
                            "Для превращения подходят карты другого вида."),
    ("единственн", "Единственная", "В руке может быть только одна такая карта: вторая при доборе уходит под низ "
                                   "колоды."),
    ("созда", "Создать", "Временные карты в руку: играются как обычные, после розыгрыша — Изгнание; в колоду не "
                         "попадают."),
    ("молни", "Молния", "Перескакивает с цели на ближайших врагов (до 3 клеток между ними)."),
    ("сила до", "Сила", "Карта-Сила: после розыгрыша не уходит в сброс, а действует до конца боя."),
    ("оборон", "Оборона", "Половина защиты, что осталась к концу хода, переходит на следующий ход."),
    ("скован", "Скован", "Жрец: если в начале хода враг стоит вплотную, за ход можно отойти только на 1 клетку."),
    ("с ходу", "С ходу", "Враг, прошедший к герою больше половины своего хода, бьёт вполсилы."),
    ("хор", "Хор", "Смысл свитка исполняет выбранная статуя, а потом все остальные — каждая сама, по ближайшей цели."),
    ("переклич", "Перекличка", "Второй смысл свитка исполняет другая статуя — та, что ближе к Жрецу; цель — сама."),
    ("атак", "Атака", "Смысл свитка Жреца: статуя бьёт врага. Как и куда — решает её бог."),
    ("движен", "Движение", "Смысл свитка Жреца: бог двигает врагов или Жреца."),
    ("проклят", "Проклятие", "Смысл свитка Жреца: бог ослабляет врага — мороз, яд, слабость, оглушение."),
    ("призыв", "Призыв", "Смысл свитка Жреца: слуга бога появляется рядом со статуей на несколько ходов."),
    ("горени", "Горение", "В начале хода носителя: урон по числу стаков мимо защиты, затем −1 стак. Вода гасит "
                          "горение; огонь по мокрому — пар (мокрый просто высыхает)."),
    ("яд", "Яд", "В начале хода носителя: урон по числу стаков мимо защиты, затем −1 стак."),
    ("мороз", "Мороз", "Копится; на 10 цель сковывает льдом — пропускает ход. Холод по мокрому — сразу лёд."),
    ("мокр", "Мокрый", "2 хода. Молния по мокрому — урон ×2; холод — сразу лёд; гасит горение."),
    ("слабост", "Слабость", "Удары носителя слабее на 25%. −1 в конце его хода."),
    ("уязвим", "Уязвимость", "Носитель получает от ударов на 50% больше. −1 в конце его хода."),
    ("оглуш", "Оглушение", "Враг пропускает своё следующее намерение."),
    ("метк", "Метка", "Следующий удар по цели наносит +N урона, затем метка снимается."),
    ("толч", "Толчок", "Сдвинуть цель от себя на N клеток. Упёрлась в стену или в другого — столкновение."),
    ("притян", "Притянуть", "Подтянуть цель к себе на N клеток. Упёрлась — столкновение."),
    ("столкнов", "Столкновение", "Толкнутый упёрся: 3 урона за каждую клетку, которую он не прошёл, — ему и тому, в "
                                 "кого врезался. Пропасть — падение."),
    ("шип", "Шипы", "До конца хода: кто ударит вас вплотную, получит N урона."),
    ("отскок", "Отскок", "Отпрыгнуть от цели на N клеток по прямой."),
    ("корни", "Корни", "Цель не может двигаться N ходов (бить, если достаёт, может)."),
    ("капкан", "Капкан", "Ловушка на клетке: враг, наступивший на неё, получает урон и останавливается."),
    ("разгон", "Разгон", "Наёмник: каждая пройденная клетка даёт +1 (до 5). Следующий удар получает бонус и тратит "
                         "разгон; от 3 — толкает на клетку дальше. Гаснет в конце хода. Условие «Разгон N» — у вас "
                         "не меньше N разгона."),
    ("раздут", "Раздуть", "Простое действие Пиромантки: прибавить жар бесплатно."),
    ("жар", "Жар", "Пиромантка платит жаром, а не энергией: +1 в начале хода. Уровень карты (колесо) — сколько "
                   "жара потратить. Выше порога в конце хода — перегрев: 2 урона за каждый лишний жар."),
    ("подж", "Поджечь", "Клетки горят: кто стоит или входит — получает горение 2. Пиромантка на своём огне не горит."),
    ("сгора", "Сгорает", "После основного применения карта уходит до конца боя."),
    ("защит", "Защита", "Поглощает урон от ударов (не от горения и яда). Спадает в начале вашего следующего хода."),
    ("сил", "Сила", "+N к урону каждого удара до конца боя."),
    ("энерги", "Энергия", "Плата за основное применение карты; восполняется каждый ход."),
    ("шаг", "Шаг", "Пройти до N клеток, обходя препятствия (по диагонали — тоже одна клетка)."),
    ("рывок", "Рывок", "Пройти по прямой до N клеток."),
    ("дальност", "Дальность", "Насколько далеко цель, в клетках (по диагонали — тоже одна клетка)."),
    ("стрел", "Стрела", "Охотница: временная карта за 0 энергии — выстрел. В колоду не уходит."),
    ("лечени", "Лечение", "Восстановить N HP."),
    ("реакци", "Реакция", "Карту нельзя сыграть самому — она срабатывает только Откликом. Пока она в руке, "
                          "отклик на ход врага ждёт до вашего следующего хода; сработала — в сброс."),
    ("возврат", "Возврат", "Условие выполнено — после розыгрыша карта возвращается в руку (можно сыграть снова)."),
    ("закалк", "Закалка", "После розыгрыша урон и защита этой карты растут до конца боя."),
    ("следующ", "Следующая карта", "Бонус к урону следующей карты с этим тегом в этот ход; тратится."),
    ("убийств", "Убийство", "Отклик: срабатывает, когда вы убили врага."),
    ("получил", "Получил удар", "Отклик: срабатывает, когда враг ударил вас. Карта ждёт в руке весь ход врага."),
    ("щитом", "Под щитом", "У вас не меньше N защиты. (Цель со щитом — у цели есть защита.)"),
    ("сам", "Сам ранен", "У вас меньше половины HP."),
    ("один", "Один на один", "Рядом с вами ровно один враг."),
    ("спиной", "Спиной к стене", "Рядом с вами стена, препятствие или край поля."),
    ("оглушённ", "По оглушённому", "Цель оглушена (пропустит намерение)."),
    ("ослабленн", "По ослабленному", "На цели слабость."),
    ("уязвимом", "По уязвимому", "На цели уязвимость."),
    ("кровоточ", "По кровоточащему", "На цели кровотечение."),
    ("тин", "Тина", "Мусорная карта от врагов: занимает руку. Основное (1 энергия) — отскрести, карта сгорает."),
    ("печать", "Печать", "Карту нельзя сыграть основным, пока условие не выполнено. Простое применение — всегда можно."),
    ("отклик", "Отклик", "Карта в руке срабатывает сама и бесплатно, когда условие выполнено (раз за ход); "
                         "остаётся в руке."),
    ("задел", "Задел", "Если к концу хода условие выполнено, карта остаётся в руке на следующий ход."),
    ("сери", "Серия", "За этот ход уже сыграно N карт основным (простое применение не считается)."),
    ("вслед", "Вслед за", "Предыдущая карта, сыгранная основным в этот ход, — с этим тегом."),
    ("резонанс", "Резонанс", "За этот ход сыграно основным N карт с этим тегом."),
    ("перв", "Первая", "Это первая карта хода, сыгранная основным."),
    ("ва-банк", "Ва-банк", "После розыгрыша у вас не осталось энергии (у Пиромантки — жара)."),
    ("вплотную", "Вплотную", "Цель стоит рядом с вами."),
    ("издалека", "Издалека", "Цель не ближе N клеток."),
    ("разбег", "С разбега", "За этот ход вы прошли не меньше N клеток (любыми картами)."),
    ("вплотную", "Враг вплотную", "Отклик: враг подошёл к вам вплотную в свой ход — карта бьёт первой."),
    ("стен", "У стены", "За целью (по направлению от вас) стена, препятствие, край или другой юнит."),
    ("окружени", "В окружении", "Рядом с вами двое врагов или больше."),
    ("укрыти", "Из укрытия", "Вы стоите рядом с укрытием (камень, дерево, стена)."),
    ("горящ", "По горящему", "На цели горение."),
    ("отравленн", "По отравленному", "На цели яд."),
    ("помеченн", "По помеченному", "На цели метка."),
    ("ранен", "По раненому", "У цели меньше половины HP."),
    ("дар", "Дар", "Дар бога на карте — особое свойство (алтарь, награда стража), одно на карту. У свитка Жреца "
                        "Дар — смысл: бог усиливает Жреца или следующие свитки."),
    ("добыч", "Добыча", "Охотница (метка): по добыче +3 урона; добыча пала — +1 энергия, +1 карта, метка переходит."),
    ("фе", "Феи", "0–10 стаков, не гаснут в конце хода. Избыток сверх 10 даёт защиту. ^+N — прибавка фей, ^-N — трата."),
    ("порог", "Порог", "С какого количества фей включается усиленная версия карты. Ниже порога — базовый эффект, феи не тратятся."),
    ("усилен", "Усиление", "На пороге карта сжигает фей: атаки — до 2, остальные — 1, особые — 3/4/всех. Атака получает +3 урона за каждую фею, остальные — свой бонус."),
    ("прививк", "Прививка", "Карта крепится к другой карте в руке. Хозяин получает Сохранение, после его основной карты срабатывает прививка. На карте — только одна прививка или растение."),
    ("сборк", "Сборка", "Части оружия рассыпаны по колоде и сбросу и приходят в руку при доборе. Когда все части собраны, они заменяются оружием; после розыгрыша оружие изгоняется."),
    ("растен", "Растение", "Семя занимает клетку, имеет 2 HP и растёт в конце хода. При созревании срабатывает и исчезает; порог фей ускоряет рост."),
    ("звер", "Зверь", "Призванный зверь занимает клетку и действует сам. Один живой зверь каждого вида; HP и сила фиксируются при призыве."),
    ("поле", "Поле", "Карта создаёт объект или зону на поле: кольцо, семя, стену."),
    ("чары", "Чары", "Школа заклинаний эльфа. Тег для условий и фильтров."),
    ("наведен", "Наведение", "В начале хода 50% шанс скидки 1. При 6 феях скидка всегда."),
    ("инициац", "Инициация", "В начале боя карта лежит на верху колоды."),
    ("квиетус", "Квиетус", "При сбросе карта срабатывает и остаётся в Used до конца хода."),
    ("благослов", "Благословение", "При сбросе даёт защиту, если текущая защита ниже 30% максимального HP."),
    ("мимолёт", "Мимолётная", "Если карта осталась в руке в конце хода, она изгоняется."),
    ("финал", "Финал", "После розыгрыша карта заканчивает ход."),
    ("изгнание 2", "Изгнание 2", "После второго основного розыгрыша карта изгоняется."),
    ("неактивир", "Неактивируемая", "Карту нельзя разыграть вручную: её эффекты срабатывают по событию."),
    ("дроблен", "Дробление", "Урон по цели со щитом увеличен на 20%."),

]


TAG_INFO = {
    "Удар": "Урон вплотную: дальность 1, подход к врагу или удар по соседям.",
    "Выстрел": "Дальний урон (стрелы, болты).",
    "Область": "Урон или эффект по области: несколько клеток или соседние враги.",
    "Сохранение": "Карта остаётся в руке в конце хода.",
    "Слияние": "Два одинаковых духа одного ранга в руке сливаются в духа следующего ранга. Предел — III.",
    "Преследование": "Запас преследования: карта [Преследование] после удара делает дополнительный выстрел по той же цели.",
    "Огонь": "Горение, поджог, жар Пиромантки.",
    "Шаг": "Карта двигает героя: шаг, рывок, подход, отскок.",
    "Защита": "Карта даёт защиту.",
    "Толчок": "Толчок, притягивание, столкновения.",
    "Шипы": "Ответный урон тем, кто бьёт вплотную: шипы и контратака.",
    "Кровь": "Кровотечение врагов, плата здоровьем, сила от ран.",
    "Создание": "Карта создаёт временные карты в руку.",
    "Дух": "Созданный в бою дух или элементаль. Карты Пиромантки могут учитывать разыгранных духов.",
    "Изгнание": "Карта изгоняет карты из руки (Силы «при изгнании» это ценят).",
    "Клич": "Сила себе, слабость и уязвимость врагам.",
    "Метка": "Метка: следующий удар по цели сильнее.",
    "Яд": "Яд: урон в начале хода цели мимо защиты.",
    "Ловушка": "Капканы и корни.",
    "Комбо": "Карта считает или строит серию розыгрышей за ход.",
    "Резонанс": "Когда условие выполнено, карта разыгрывается ещё раз. Своего эффекта у резонанса нет.",
    "Повтор": "Карта повторяется или даёт дополнительный удар при условии.",
    "Цепочка": "Когда условие выполнено, карта сама играется из руки раз за ход, без оплаты.",
    "Свиток": "Карта Жреца: её смысл исполняет статуя бога.",
    "Атака": "Смысл свитка: статуя наносит урон.",
    "Оборона": "Смысл свитка: статуя даёт щит или защиту.",
    "Движение": "Смысл свитка: статуя двигает героя, врагов или статую.",
    "Проклятие": "Смысл свитка: статуя ослабляет или оглушает врага.",
    "Дар": "Смысл свитка: статуя усиливает героя или следующий свиток.",
    "Призыв": "Смысл свитка: статуя зовёт слугу бога.",
    "Хор": "Свиток, который исполняют несколько статуй или который повторяется.",
    "Фея": "Феи 0–10; карта усиливается на пороге и сжигает фей. ^+N — прибавка, ^-N — трата.",
    "Чары": "Школа заклинаний эльфа.",
    "Растение": "Семя на поле/карте; растёт и созревает.",
    "Зверь": "Призванный помощник; один живой зверь каждого вида.",
    "Связь": "Парная карта: пока в руке есть другая [Связь], обе получают бонус.",
    "Прививка": "Крепится к карте в руке; срабатывает после её основной карты.",
    "Поле": "Создаёт объект или зону на поле.",
    "Сборка": "Части оружия собираются в руке в одно оружие.",
}


def lookup(word, style="k"):
    """Описание выделенного слова на карте: (название, текст) или None. style «g» — тег."""
    w = word.lower().strip(" .,:;()!")
    if style == "g":
        for tag, info in TAG_INFO.items():
            if w == tag.lower():
                return f"Тег: {tag}", info + " Условия вроде «Вслед за [" + tag + "]» и «Резонанс " + tag +                     " N» считают такие карты."
    for stem, name, expl in GLOSSARY:
        if w.startswith(stem):
            return name, expl
    return None


def keywords(card):
    """Ключевые слова карты (все стороны и уровни) с пояснениями: [(название, текст)]."""
    d = card.d
    texts = [phrase(d["main"], d.get("exhaust")), phrase(d["alt"]), card_extras(d)] + \
        [phrase(L["main"]) for L in card.levels]
    if card.divine:
        texts.append("*Дар*")
    out, seen = [], set()
    for t in texts:
        for w in re.findall(r"\*([^*]+)\*", t.replace("~", "*")):
            w = w.lower().strip(" .,:")
            for stem, name, expl in GLOSSARY:
                if w.startswith(stem) or any(x.startswith(stem) for x in w.split()):
                    if name not in seen:
                        seen.add(name)
                        out.append((name, expl))
                    break
    return out


def plain(s):
    """Разметка → обычный текст (журнал боя)."""
    s = re.sub(r"\^([+-]?\d+|все)", lambda m: "феи " + m.group(1), s)
    return s.replace("{", "").replace("}", "").replace("*", "")


# ---------- карта ----------

OFFER = 3          # сколько вариантов прозрения предлагается
INSIGHT_CHANCE = 0.05   # шанс прозрения за основное применение карты
INSIGHT_PITY = 20       # после стольких неудач — гарантированное прозрение

CARD_RARITY_NAME = {0: "Базовая", 1: "Обычная", 2: "Необычная", 3: "Редкая", 4: "Легендарная"}
CARD_RARITY_COLOR = {0: (170, 170, 170), 1: (190, 190, 170), 2: (120, 210, 170),
                     3: (120, 170, 255), 4: (235, 160, 255)}
CARD_TIER_WEIGHTS = {1: 55, 2: 28, 3: 13, 4: 4}


def _bless_use(u, god):
    u = copy.deepcopy(u)
    if god.get("add_do"):
        u["do"] = list(u.get("do", [])) + copy.deepcopy(god["add_do"])
    if god.get("add_if"):
        u["if"] = list(u.get("if", [])) + copy.deepcopy(god["add_if"])
    if god.get("plus_reach"):
        for key in ("step", "dash", "reach", "range"):
            if key in u:
                u[key] += god["plus_reach"]
    if god.get("plus_damage"):                          # прибавка к удару карты (нет удара — свой удар)
        hit = next((o for o in u.get("do", []) if o["op"] == "damage"), None)
        if hit is not None:
            hit["n"] += god["plus_damage"]
        else:
            u["do"] = list(u.get("do", [])) + [{"op": "damage", "n": god["plus_damage"]}]
    return u


def bless(d, god):
    """Карта с даром бога: его действия и условия добавляются к основному применению (и ко всем уровням)."""
    d = dict(d, divine=god["id"], divine_name=god["name"])
    d["main"] = _bless_use(d["main"], god)
    if d.get("levels"):
        d["levels"] = [dict(L, main=_bless_use(L["main"], god)) for L in d["levels"]]
    return d


def god_fits(god, card):
    """Подходит ли дар карте: «needs» — цель (удар/выстрел), перемещение или дальность."""
    if card.divine:
        return False
    need = god.get("needs")
    u = card.d["main"]
    if need == "target":
        return u["target"] in ("enemy", "reach", "area")
    if need == "reach":
        return any(k in u for k in ("step", "dash", "reach", "range"))
    return True


def _merge(base, patch):
    out = copy.deepcopy(base)
    for k, v in patch.items():
        if k == "label":
            continue
        out[k] = copy.deepcopy(v)
    return out


_ALL_DEFS = None


def card_def(cid):
    """Описание карты по id из data/deck/cards.json (для созданных карт — их видно при чтении)."""
    global _ALL_DEFS
    if _ALL_DEFS is None:
        _ALL_DEFS = load()["cards"]["cards"]
    return _ALL_DEFS.get(cid)


def created_ids(d):
    """Какие карты создаёт карта (add_card во всех применениях, уровнях, Силе, Отклике) — по порядку, без повторов."""
    out = []

    def scan(x):
        if isinstance(x, dict):
            if x.get("op") == "add_card":
                for cid in x.get("pool") or (x.get("card"),):
                    if cid and cid not in out:
                        out.append(cid)
            for v in x.values():
                scan(v)
        elif isinstance(x, list):
            for v in x:
                scan(v)
    scan({k: d.get(k) for k in ("main", "alt", "levels", "echo")})
    return out


# ---------- Мастерская: улучшение простого применения (квиз 2026-11-21) ----------

def _bump(ops, k=1):
    out = copy.deepcopy(ops)
    for o in out:
        if o.get("n"):
            o["n"] += k
    return out


def alt_options(d, hero=None):
    """Три улучшения простого применения карты: [(подпись, новое простое)]. Пусто — улучшать нечего (свитки
    Жреца, временные карты). Карте без простого Мастерская его даёт."""
    if d.get("meaning") or d.get("token") or d.get("status") or (d.get("main") or {}).get("target") == "copy_hand":
        return []
    a = d.get("alt") or NOALT
    t = a.get("target", "none")
    ops = list(a.get("do", []))
    names = [o["op"] for o in ops]
    B = {"op": "block", "n": 3}

    def me(*o):
        return {"target": "self", "do": list(o)}

    if t == "none":
        rider = {"merc": ("Простое: разгон 2", me({"op": "momentum", "n": 2})),
                 "hunter": ("Простое: метка 3", {"target": "enemy", "range": 5, "los": True,
                                                 "do": [{"op": "mark", "n": 3}]}),
                 "pyro": ("Простое: раздуть", me({"op": "heat", "n": 1}))}.get(
            hero, ("Простое: контратака 1", me({"op": "counter", "n": 1})))
        return [("Простое: шаг 1", {"target": "cell_step", "step": 1, "do": []}), ("Простое: защита 3", me(B)), rider]
    if t in ("cell_step", "cell_dash"):
        key = "step" if t == "cell_step" else "dash"
        return [("Дальше: шаг +1", dict(a, **{key: a.get(key, 1) + 1})),
                ("Под щитом: +3 защиты", dict(a, do=ops + [B])),
                ("С отпором: контратака 1", dict(a, do=ops + [{"op": "counter", "n": 1}]))]
    if t == "self" and names == ["heat"]:
        n = ops[0].get("n", 1)
        return [("Раздуть сильнее: +1 жар", me({"op": "heat", "n": n + 1})),
                ("Жар и щит: +3 защиты", me({"op": "heat", "n": n}, B)),
                ("Жар и пламя: горящим +1", me({"op": "heat", "n": n}, {"op": "burn_all", "n": 1}))]
    if t == "self" and "block" in names:
        return [("Крепче: +3 защиты", dict(a, do=_bump(ops, 3))),
                ("С шипами: шипы 3", dict(a, do=ops + [{"op": "thorns", "n": 3}])),
                ("С обороной", dict(a, do=ops + [{"op": "fort", "n": 1}]))]
    if t == "self":
        return [("Сильнее: числа +1", dict(a, do=_bump(ops, 1))),
                ("И щит: +3 защиты", dict(a, do=ops + [B])),
                ("И отпор: контратака 1", dict(a, do=ops + [{"op": "counter", "n": 1}]))]
    if t == "enemy" and "damage" in names:
        return [("Сильнее: +2 урона", dict(a, do=[dict(o, n=o["n"] + 2) if o["op"] == "damage" else o for o in ops])),
                ("С толчком: толчок 1", dict(a, do=ops + [{"op": "push", "n": 1}])),
                ("Пустить кровь: кровотечение 2", dict(a, do=ops + [{"op": "bleed", "n": 2}]))]
    if t == "enemy":
        return [("Сильнее: числа +1", dict(a, do=_bump(ops, 1))),
                ("Дальше: дальность +2", dict(a, range=a.get("range", 1) + 2)),
                ("Ослабить: слабость 1", dict(a, do=ops + [{"op": "weak", "n": 1}]))]
    return []


class Card:
    _n = 0

    def __init__(self, cid, defs, tier=0, uses=0, picks=None, insight_ready=False, insight_misses=0):
        Card._n += 1
        self.uid = Card._n
        self.cid = cid
        self.base = defs[cid]
        self.uses = uses                 # основные применения за забег (история карты)
        self.picks = list(picks or [])   # выбранные ветки прозрений по ступеням
        self.ready = bool(insight_ready) # прозрение выпало и ждёт выбора
        self.insight_misses = int(insight_misses)  # неудачи после прошлого прозрения
        self._lvl = None                 # Пиромантка: выбранный уровень карты (за сколько жара); None — сам
        self._spirit_rank = 1            # духи начинают бой с ранга I
        self._d = None
        self.divine = None               # дар бога (data/deck/gods.json) — поверх прозрения
        self._offer = None               # какие 3 варианта прозрения из 5 предложены (выбираются один раз)
        self.alt_up = None               # Мастерская: улучшенное простое применение (одно на карту)
        self.preview = None              # бой: {"main": [реальный урон…], "alt": […]}; вне боя — None
        self.preview_cost = None
        self.heat_payment = False
        self._linked_spent = False
        self._temporary_rules = frozenset()

    def preview_key(self):
        """Хэшируемый снимок preview для кэшей лиц карт."""
        p = self.preview or {}
        return self.preview_cost, self.heat_payment, self.linked_spent, self.temporary_rules, tuple(
            (mode, tuple(v or ())) for mode, v in sorted(p.items()))

    @property
    def temporary_rules(self):
        return self._temporary_rules

    @temporary_rules.setter
    def temporary_rules(self, value):
        self._temporary_rules = frozenset(value)
        self._d = None

    @property
    def linked_spent(self):
        return self._linked_spent

    @linked_spent.setter
    def linked_spent(self, value):
        if self._linked_spent != value:
            self._linked_spent = value
            self._d = None

    @property
    def d(self):
        """Карта с прозрениями; у карты с уровнями main и cost — выбранного уровня."""
        if self._d is None:
            d = self.base
            for tier, k in enumerate(self.picks):
                d = _merge(d, self.base["growth"][tier]["options"][k])
            if ranks := card_ranks(d):
                rank = ranks[self.rank - 1]
                ill = d.get("spirit_ill", {}).get(self.spirit_rank, d.get("ill"))
                reactions = {**d.get("reactions", {}), **rank.get("reactions", {})}
                d = dict(d, main=rank.get("main", d["main"]), reactions=reactions, ill=ill)
                if "retain_do" in rank:
                    d["retain_do"] = rank["retain_do"]
            if self.divine:
                d = bless(d, self.divine)
            if d.get("levels"):
                lv = d["levels"][min(self.lvl, len(d["levels"]) - 1)]
                d = dict(d, main=lv["main"], cost=lv["heat"])
            if not d.get("alt"):
                d = dict(d, alt=NOALT)
            if self.alt_up is not None:
                d = dict(d, alt=self.alt_up)
            if self.linked_spent:
                d = dict(d, rules=[rule for rule in d.get("rules", ()) if rule != "linked"])
            if self.temporary_rules:
                d = dict(d, rules=[*d.get("rules", ()), *sorted(self.temporary_rules)])
            self._d = d
        return self._d

    @property
    def tags(self):
        return [tag_label(t) for t in self.tag_ids]

    @property
    def tag_ids(self):
        return card_tag_ids(self.d)

    @property
    def levels(self):
        """Уровни карты (Пиромантка) — с учётом прозрений; пусто — обычная карта."""
        d = self.base
        for tier, k in enumerate(self.picks):
            d = _merge(d, self.base["growth"][tier]["options"][k])
        if self.divine:
            d = bless(d, self.divine)
        return d.get("levels") or []

    @property
    def lvl(self):
        return 0 if self._lvl is None else self._lvl

    @lvl.setter
    def lvl(self, v):
        if v != self._lvl:
            self._lvl = v
            self._d = None

    @property
    def rank(self):
        return self._spirit_rank

    @rank.setter
    def rank(self, value):
        rank = max(1, min(value, len(card_ranks(self.base))))
        if rank != self._spirit_rank:
            self._spirit_rank = rank
            self._d = None

    spirit_rank = rank

    @property
    def spirit_rank_name(self):
        if not card_ranks(self.base):
            return ""
        return SPIRIT_ROMAN[self.rank - 1] if self.rank <= len(SPIRIT_ROMAN) else str(self.rank)

    @property
    def tier(self):
        return len(self.picks)

    @property
    def name(self):
        name = self.d["name"] + ("+" * self.tier if self.d["name"] == self.base["name"] else "")
        return f"{name} {self.spirit_rank_name}" if self.spirit_rank_name else name

    @property
    def cost(self):
        return self.d["cost"]

    @property
    def uses_heat(self):
        return self.heat_payment or bool(self.levels)

    @property
    def cost_label(self):
        if self.d.get("x_cost"):
            return "X"
        return self.cost if self.preview_cost is None else self.preview_cost

    @property
    def rarity(self):
        return int(self.d.get("rarity", 1))

    @property
    def rarity_name(self):
        return CARD_RARITY_NAME.get(self.rarity, CARD_RARITY_NAME[1])

    @property
    def category(self):
        return self.d.get("category", "hero")

    def text(self, mode):
        return plain(phrase(self.d[mode]))

    def growth_next(self):
        g = self.base.get("growth", [])
        return g[self.tier] if self.tier < len(g) else None

    def insight_ready(self):
        return self.growth_next() is not None and self.ready

    def insight_progress(self):
        """Заполнение полоски до гарантии (сам шанс — 5% за использование)."""
        if self.insight_ready():
            return 1.0
        return min(1.0, self.insight_misses / INSIGHT_PITY)

    def offer(self):
        """Какие варианты прозрения предложены: 3 случайных из 5 (как эпифании CZN), один раз на карту."""
        g = self.growth_next()
        if g is None:
            return []
        if self._offer is None:
            n = len(g["options"])
            rng = random.Random(f"{self.cid}:{self.uid}:{self.tier}")
            self._offer = sorted(rng.sample(range(n), min(OFFER, n)))
        return self._offer

    def options(self):
        """Предложенные варианты ближайшего прозрения: [(подпись, карта после выбора)]."""
        g = self.growth_next()
        if g is None:
            return []
        out = []
        for k in self.offer():
            opt = g["options"][k]
            c = Card(self.cid, {self.cid: self.base}, uses=self.uses, picks=self.picks + [k])
            c.divine = self.divine
            out.append((opt.get("label", f"Ветка {k + 1}"), c))
        return out

    def alt_options(self, hero=None):
        """Мастерская: варианты простого — [(подпись, карта после улучшения)]; уже улучшено — пусто."""
        if self.alt_up is not None:
            return []
        out = []
        for label, alt in alt_options(self.d, hero):
            c = Card(self.cid, {self.cid: self.base}, uses=self.uses, picks=self.picks)
            c.divine = self.divine
            c.alt_up = alt
            out.append((label, c))
        return out

    def upgrade_alt(self, alt):
        self.alt_up = alt
        self._d = None

    def choose(self, i):
        """Выбрать i-й из предложенных вариантов."""
        self.pick(self.offer()[i])

    def pick(self, k):
        self.picks.append(k)
        self.ready = False
        self.insight_misses = 0
        self._offer = None
        self._d = None

    def bless(self, god):
        """Дар бога: одно на карту."""
        self.divine = god
        self._d = None


# ---------- стартовая колода ----------

def hero_prefix(hero_id):
    return {"merc": "m_", "hunter": "h_", "pyro": "p_", "priest": "sc_", "elf": "e_"}.get(hero_id, "")


def basic_starter(data, hero_id):
    """6 базовых карт: 2 атаки, 2 защиты, 2 перемещения."""
    h = data["heroes"]["heroes"][hero_id]
    basic = h.get("basic") or {}
    out = []
    for role in ("attack", "defense", "movement"):
        cid = basic.get(role)
        if cid:
            out += [cid, cid]
    return out


def tier1_pool(data, hero_id):
    """Карты 1 тира, из которых игрок добирает 4 в стартовую колоду."""
    cards = data["cards"]["cards"]
    neutral = set(data["cards"].get("neutral", []))
    pref = hero_prefix(hero_id)
    out = []
    for cid, c in cards.items():
        if c.get("category") == "basic" or c.get("category") == "token":
            continue
        if c.get("rarity") != 1:
            continue
        if cid in neutral or cid.startswith(pref):
            out.append(cid)
    return out


def deck_limit_reached(cid, defs, deck_ids):
    return bool(defs.get(cid, {}).get("deck_unique") and cid in deck_ids)


# ---------- забег ----------

class Run:
    """Забег прототипа: герой, его HP и колода, номер боя."""

    def __init__(self, data=None, seed=None, hero="merc", variant=None, starter=None):
        """hero — герой, variant — пассивка, starter — своя стартовая колода (10 карт)."""
        self.data = data or load()
        self.rng = random.Random(seed)
        self.defs = dict(self.data["cards"]["cards"])   # свой словарь: Жрецу в него пишутся созданные свитки
        h = self.data["heroes"]["heroes"][hero]
        self.hero_id = hero
        self.hero = h
        self.hero_name = h["name"]
        self.sprite = h["sprite"]
        self.max_hp = h["hp"]
        self.hp = h["hp"]
        self.variant = variant or (next(iter(h["passives"])) if h.get("passives") else None)
        chosen = list(starter) if starter else None
        if not chosen:
            chosen = (h.get("starter_by_variant") or {}).get(self.variant) or h["starter"]
        self.deck = [Card(cid, self.defs) for cid in chosen]
        self.normalize_ballista_deck()
        self.fight = 0                   # сколько боёв выиграно
        self.result = None
        fl = self.data["enemies"]["floor"]
        self.gold = fl["start_gold"]
        self.depth = 0
        self.floor = None
        self.remove_price = self.data["enemies"]["shop"]["remove_price"]
        self.kills = 0
        self.god_xp = {}                 # Жрец: опыт богов за поход (свитки через их статуи) → уровни
        self.god_picks = {}              # Жрец: ветки богов — {бог: [("m", смысл) | ("a", № ауры)]}
        self.god_pending = []            # Жрец: новые уровни, ветка выбирается после боя — [(бог, уровень)]
        self.relics = []                 # реликвии (data/deck/relics.json) — словари с id
        self.next_floor()

    def normalize_ballista_deck(self):
        """Старые карты команд заменяет установка, повторные установки убирает."""
        replace = (self.hero_id == "hunter" and BALLISTA_CARD in self.defs
                   and not any(c.cid == BALLISTA_CARD for c in self.deck))
        deck = []
        seen = set()
        for card in self.deck:
            if card.cid in BALLISTA_COMMANDS:
                if not replace:
                    continue
                card = Card(BALLISTA_CARD, self.defs)
                replace = False
            if not deck_limit_reached(card.cid, self.defs, seen):
                deck.append(card)
                seen.add(card.cid)
        self.deck = deck

    @property
    def fights(self):
        """Готовые бои из данных (тесты и примеры)."""
        return self.data["enemies"]["fights"]

    @property
    def chapters(self):
        """Главы спуска подряд: болото, кузни… (data/deck/enemies.json: chapters; старое — одна chapter)."""
        e = self.data["enemies"]
        return e.get("chapters") or ([e["chapter"]] if e.get("chapter") else [])

    def chapter_at(self, depth=None):
        """(№ главы с 0, глава, № этажа в главе с 0) для глубины (этажи глав — подряд)."""
        d = (self.depth if depth is None else depth) - 1
        for i, ch in enumerate(self.chapters):
            if d < len(ch["floors"]):
                return i, ch, d
            d -= len(ch["floors"])
        return None

    @property
    def chapter_name(self):
        at = self.chapter_at()
        return at[1]["name"] if at else ""

    @property
    def floor_cfg(self):
        """Настройки этажа: общие + состав врагов этого этажа его главы."""
        fl = self.data["enemies"]["floor"]
        at = self.chapter_at() if self.depth >= 1 else None
        if at:
            f = at[1]["floors"][at[2]]
            return dict(fl, pools=f["pools"], name=f["name"])
        return fl

    @property
    def floor_name(self):
        return self.floor_cfg.get("name", "")

    @property
    def last_floor(self):
        """Этот этаж — последний во всём спуске (его страж — последний босс)."""
        return bool(self.chapters) and self.depth >= sum(len(c["floors"]) for c in self.chapters)

    @property
    def chapter_end(self):
        """Этот этаж — последний в своей главе (страж — босс главы, дальше — новая глава)."""
        at = self.chapter_at()
        return bool(at) and at[2] == len(at[1]["floors"]) - 1

    def relic_offer(self, n, source="chest"):
        """n предметов, которых ещё нет: редкость — по источнику (сундук, элита, торговец, страж), только общие и
        своего класса (deck/items.py)."""
        from .items import OFFER_WEIGHTS, fits
        have = {r["id"] for r in self.relics}
        weights = OFFER_WEIGHTS.get(source, OFFER_WEIGHTS["chest"])
        pool = [dict(r, id=rid) for rid, r in self.data["relics"]["relics"].items()
                if rid not in have and fits(r, self.hero_id) and r.get("rarity", "common") in weights]
        required = {r["needs_tag"] for r in pool if r.get("needs_tag")}
        if required:
            available = required.intersection(tag for c in self.deck for tag in c.tag_ids)
            available.update(required.intersection(tag for d in self.defs.values() for tag in card_tag_ids(d)))
            pool = [r for r in pool if not r.get("needs_tag") or r["needs_tag"] in available
                    or r.get("alternative_relic") in have]
        out = []
        while pool and len(out) < n:
            rar = self.rng.choices(list(weights), list(weights.values()))[0]
            group = [r for r in pool if r.get("rarity", "common") == rar] or pool
            r = self.rng.choice(group)
            pool.remove(r)
            out.append(r)
        return out

    def next_floor(self):
        from .floor import Floor
        self.depth += 1
        self.floor = Floor(self.floor_cfg, self.rng, self.depth)

    def scale(self):
        """Сила врагов на этой глубине: (×HP, ×урон)."""
        fl = self.floor_cfg
        d = max(0, self.depth - 1)
        curve = fl.get("difficulty_by_depth", ())
        if d < len(curve):
            return tuple(curve[d])
        if curve:
            hp, dmg = curve[-1]
            extra = d - len(curve) + 1
            return hp + fl["hp_per_depth"] * extra, dmg + fl["dmg_per_depth"] * extra
        return 1 + fl["hp_per_depth"] * d, 1 + fl["dmg_per_depth"] * d

    def gold_for(self, kind):
        lo, hi = self.floor_cfg["gold"].get(kind, [10, 15])
        return self.rng.randint(lo, hi)

    def shop_stock(self):
        sh = self.data["enemies"]["shop"]
        return [(c, self.rng.randint(*sh["card_price"])) for c in self.reward_offer(sh["cards"])]

    def rewardable(self, cid):
        d = self.defs.get(cid)
        return (bool(d) and d.get("category") not in ("basic", "token") and d.get("rarity", 1) > 0
                and not deck_limit_reached(cid, self.defs, (c.cid for c in self.deck)))

    def weighted_pick(self, pool):
        pool = [cid for cid in pool if self.rewardable(cid)]
        if not pool:
            return None
        weights = [CARD_TIER_WEIGHTS.get(self.defs[cid].get("rarity", 1), 1) for cid in pool]
        return self.rng.choices(pool, weights=weights, k=1)[0]

    def reward_offer(self, n=3):
        from .items import mod
        count = max(1, n - mod(self, "fewer_rewards"))
        neutral = list(self.data["cards"].get("neutral", []))
        if self.hero.get("mechanic") == "idols":           # Жрец: только свитки, без обычных карт
            from .idols import offer_scrolls
            scrolls = [cid for cid in offer_scrolls(self, count) if self.rewardable(cid)]
            return [Card(cid, self.defs) for cid in scrolls]
        core = [cid for cid in ((self.hero.get("rewards_by_variant") or {}).get(self.variant) or [])
                if self.rewardable(cid)]
        if core:                                      # школа: 2 карты направления + 1 свобода
            picks = []
            must = [cid for cid in (self.hero.get("reward_guarantee") or {}).get(self.variant, [])
                    if cid in core]
            if must:
                picks.append(self.rng.choice(must))
            room = min(2, count)                      # ядро: до двух карт, включая гарантию
            while len(picks) < room:
                pick = self.weighted_pick([cid for cid in core if cid not in picks])
                if pick is None:
                    break
                picks.append(pick)
            rest = [cid for cid in self.hero.get("rewards", []) if cid not in core and cid not in picks]
            rest += [cid for cid in neutral if cid not in picks]
            while len(picks) < count and rest:
                pick = self.weighted_pick(rest)
                if pick is None:
                    break
                picks.append(pick)
                rest.remove(pick)
            self.rng.shuffle(picks)
            return [Card(cid, self.defs) for cid in picks]
        pool = [cid for cid in self.hero.get("rewards", []) if self.rewardable(cid)] + \
               [cid for cid in neutral if self.rewardable(cid)]
        picks = []
        while len(picks) < count and pool:
            pick = self.weighted_pick(pool)
            if pick is None:
                break
            picks.append(pick)
            pool.remove(pick)
        return [Card(cid, self.defs) for cid in picks]

    def take(self, card):
        if deck_limit_reached(card.cid, self.defs, (c.cid for c in self.deck)):
            return False
        self.deck.append(card)
        return True

    def insights(self):
        return [c for c in self.deck if c.insight_ready()]
