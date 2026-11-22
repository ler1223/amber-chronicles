"""Карты, колода и забег «Спуска»: данные (data/deck/), текст карты по её операциям, прозрения."""
import copy
import json
import os
import random
import re

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "deck")


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
    return out


# ---------- текст карты ----------

def _op_text(op):
    t = op["op"]
    n = op.get("n")
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
        "burn_card": lambda: f"изгнать {n} карт из руки",
        "strength_x2": lambda: "мощь ×2",
        "chain": lambda: f"молния {n} перескакивает",
        "body_slam": lambda: "урон = вашей защите",
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
    if op.get("per"):                                       # «за каждую…»
        per = op["per"]
        word = {"damage": "урона", "block": "*защиты*", "bleed": "*кровотечения*", "burn": "*горения*",
                "poison": "*яда*", "mark": "*метки*", "heal": "*лечения*", "counter": "*контратаки*"}.get(t, t)
        verb = {"damage": "Нанести", "block": "Получить", "heal": "Восстановить", "counter": "Получить"}.get(t, "Наложить")
        shown = _dmg(dmg) if t == "damage" and dmg is not None else _n(n)
        head = f"{verb} {shown} {word}" if n else f"{verb} {word}"
        return f"{head}: {_n('+' + str(per.get('k', 1)))} {per_text(per)}."
    if t == "damage":
        shown = _dmg(dmg) if dmg is not None else _n(n)
        s = f"Нанести {shown} урона"
        if op.get("mom_k"):
            s += f" {_n('+' + str(op['mom_k']))}×*разгон*"
        if op.get("far"):
            s += f"; цель дальше {_n(op['far']['d'])} — ещё {_n('+' + str(op['far']['bonus']))}"
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
        nm = op.get("cname")
        if nm:
            return f"*Создать* {_n(n)} «{nm}»."
        return f"В руку {_n(n)} " + ("*Стрелу*." if n == 1 else "*Стрелы*.")
    if t == "chain":
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
        "energy": lambda: f"Получить {_n(n)} *энергию*.",
        "heal": lambda: f"*Лечение* {_n(n)}.",
        "lose_hp": lambda: f"Потерять {_n(n)} HP.",
        "strength": lambda: f"Получить {_n(n)} *мощи*.",
        "bleed": lambda: f"*Кровотечение* {_n(n)}.",
        "counter": lambda: f"*Контратака* {_n(n)}.",
        "burn_card": lambda: f"*Изгнать* {_n(n)} " + ("случайную карту из руки." if n == 1 else "случайные карты из руки."),
        "strength_x2": lambda: "Удвоить *мощь*.",
        "body_slam": lambda: (f"Нанести {_dmg(dmg)} урона, равный вашей *защите*." if dmg is not None
                               else "Нанести урон, равный вашей *защите*."),
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
        "empower": lambda: f"Следующая карта [{op['tag']}] в этот ход: ещё {_n('+' + str(n))} урона.",
        "heat_regen": lambda: f"В начале хода {_n('+' + str(n))} *жар*.",
        "keep_momentum": lambda: "*Разгон* больше не гаснет в конце хода.",
        "momentum": lambda: f"{_n('+' + str(n))} *разгона*.",
        "aoe_adjacent": lambda: "Всем соседним врагам: " + _low(" ".join(_op_phrase(o) for o in op["do"])),
        "aoe_radius": lambda: f"Врагам в {_n(op['r'])} клетках: " + _low(" ".join(_op_phrase(o) for o in op["do"])),
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
}


def per_text(per):
    w = per["what"]
    if w.startswith("tag:"):
        return f"за каждую карту [{w[4:]}], сыгранную до неё в этот ход"
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
            head += f" [{pw['tag']}]"
        ops = _low(" ".join(_ops_phrases(pw.get("do", []))))
        out.append(f"{head}: {POWER_AIM.get(pw.get('aim'), '')}{ops}" + (" Раз за ход." if pw.get("once") else ""))
    return " ".join(out)


COND_NAMES = {"series": "Серия", "after": "Вслед за", "resonance": "Резонанс", "first": "Первая",
              "allin": "Ва-банк", "adjacent": "Вплотную", "far": "Издалека", "run": "С разбега", "wall": "У стены",
              "surrounded": "В окружении", "cover": "Из укрытия", "burning": "По горящему", "wet": "По мокрому",
              "poisoned": "По отравленному", "marked": "По помеченному", "wounded": "По раненому",
              "momentum": "Разгон", "shielded": "Под щитом", "hurt": "Сам ранен", "duel": "Один на один",
              "back_wall": "Спиной к стене", "stunned": "По оглушённому", "weakened": "По ослабленному",
              "guarded": "Цель со щитом", "vulnerable": "По уязвимому", "bleeding": "По кровоточащему"}
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
    name = " ".join(f"{mark}{w}{mark}" for w in COND_NAMES[k].split())
    if k == "after":
        return f"{name} [{c['tag']}]"
    if k == "resonance":
        return f"{name} {c['tag']} {_n(c['n'])}"
    if k in ("series", "far", "run", "momentum", "shielded"):
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
    if u.get("power"):                                    # Сила: правило до конца боя
        return (" ".join(_ops_phrases(do)) + " " if do else "") + power_text(u["power"])
    if [o["op"] for o in do] == ["heat"] and do[0].get("n", 0) > 0 and u["target"] == "self" and not u.get("if"):
        return f"*Раздуть*: {_n(_signed(do[0]['n']))} *жар*."
    parts = []
    if u.get("seal"):
        parts.append(f"*Печать* ({cond_text(u['seal'], 'seal' in lit)}).")
    t = u["target"]
    if t == "none" and not do:
        return ""
    if t == "cell_step":
        parts.append(f"*Шаг* {_n(u.get('step', 1))}.")
    elif t == "cell_dash":
        parts.append(f"*Рывок* по прямой {_n(u.get('dash', 1))}.")
    elif t == "reach":
        parts.append(f"Подойти к врагу на {_n(u.get('reach', 1))}, затем:")
    elif t == "enemy" and u.get("range", 1) > 1:
        parts.append(f"*Дальность* {_n(u['range'])}.")
    elif t == "area":
        parts.append(f"Область радиус {_n(u.get('radius', 1))}, дальность {_n(u.get('range', 5))}:")
    elif t == "cell_any":
        parts.append(f"Клетка в {_n(u.get('range', 4))}:")
    parts += _ops_phrases(do, preview)
    for i, c in enumerate(u.get("if", [])):
        parts.append(_if_phrase(c, ("if", i) in lit))
    if u.get("back"):
        parts.append(f"*Возврат* ({cond_text(u['back'], 'back' in lit)}): карта снова в руке.")
    if exhaust:
        parts.append("*Изгнание*.")
    return " ".join(parts) or "—"


def card_extras(d, lit=()):
    """Свойства карты целиком (не применения): Отклик и Задел — строкой под основным текстом."""
    out = []
    if d.get("unique"):
        out.append("*Единственная*.")
    if d.get("retain"):
        out.append("*Сохранение*.")
    if d.get("react"):
        out.append("*Реакция*: самому не сыграть.")
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

TAG_ORDER = ["Огонь", "Удар", "Выстрел", "Область", "Шаг", "Защита", "Сохранение", "Толчок", "Шипы", "Кровь",
             "Клич", "Метка", "Преследование", "Яд", "Ловушка", "Создание", "Изгнание", "Комбо", "Резонанс", "Повтор",
             "Цепочка", "Свиток", "Атака", "Оборона", "Движение", "Проклятие", "Дар", "Призыв", "Хор"]


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
        tags.add("Выстрел")
    elif dmg and (t in ("reach",) or (t == "enemy" and u.get("range", 1) <= 1) or "aoe_adjacent" in ops):
        tags.add("Удар")
    if t == "area" or {"aoe_adjacent", "aoe_radius", "detonate"} & set(ops):
        tags.add("Область")
    if "hunt" in ops:
        tags.add("Преследование")
    if {"burn", "ignite", "detonate", "heat", "burn_all"} & set(ops):
        tags.add("Огонь")
    if t in ("cell_step", "cell_dash", "reach") or "retreat" in ops:
        tags.add("Шаг")
    if "block" in ops:
        tags.add("Защита")
    if {"push", "pull", "collide_x2"} & set(ops):
        tags.add("Толчок")
    if {"thorns", "counter"} & set(ops):
        tags.add("Шипы")
    if {"lose_hp", "rage", "bleed"} & set(ops):
        tags.add("Кровь")
    if "add_card" in ops:
        tags.add("Создание")
    if "burn_card" in ops:
        tags.add("Изгнание")
    if {"strength", "empower", "strength_x2"} & set(ops) or any(o["op"] == "aoe_radius" and {x["op"] for x in o["do"]} &
                                                  {"weak", "vulnerable"} for o in u.get("do", [])):
        tags.add("Клич")
    if "mark" in ops:
        tags.add("Метка")
    if "poison" in ops:
        tags.add("Яд")
    if {"trap", "root"} & set(ops):
        tags.add("Ловушка")
    if {"weak", "vulnerable"} & set(ops):
        tags.add("Клич")
    if {"ranged_bonus", "focus"} & set(ops):
        tags.add("Выстрел")
    if "heat_regen" in ops:
        tags.add("Огонь")
    if "summon" in ops:
        tags.add("Призыв")
    conds = [c.get("when", {}) for c in u.get("if", []) if isinstance(c, dict)]
    if any(c.get("repeat") for c in u.get("if", []) if isinstance(c, dict)) or any(
            c.get("k") in ("series", "first", "allin") for c in conds):
        tags.add("Комбо")
    if any(c.get("k") == "resonance" for c in conds) or (u.get("seal") or {}).get("k") == "resonance":
        tags.add("Резонанс")
    if any(c.get("repeat") for c in u.get("if", []) if isinstance(c, dict)):
        tags.add("Повтор")
    return tags


MEANING_TAGS = {"attack": "Атака", "defense": "Оборона", "move": "Движение", "curse": "Проклятие",
                "gift": "Дар", "summon": "Призыв"}


def card_tags(d):
    """Теги карты: по основному применению (у карт с уровнями — по всем уровням) + заданные вручную."""
    tags = set(d.get("tags", []))
    if d.get("meaning"):
        tags.add("Свиток")
        tags.add(MEANING_TAGS.get(d["meaning"], d["meaning"]))
        if d["meaning"] == "summon":
            tags.add("Призыв")
    for a in d.get("acts", []):
        if a.get("m") in MEANING_TAGS:
            tags.add(MEANING_TAGS[a["m"]])
    if d.get("chorus") or d.get("then") or d.get("double"):
        tags.add("Хор")
    uses = [L["main"] for L in d.get("levels", [])] or [d["main"]]
    uses = uses + [{"target": "enemy", "range": 1, "do": u["power"].get("do", [])} for u in uses if u.get("power")]
    if (d.get("echo") or {}).get("do"):                     # реакция: теги — по тому, что делает отклик
        uses = uses + [{"target": "enemy", "range": 1, "do": d["echo"]["do"]}]
    for u in uses:
        tags |= use_tags(u)
    if d.get("element") == "fire" or any("Огонь" in use_tags(u) for u in uses):
        tags.add("Огонь")
    if d.get("retain"):
        tags.add("Сохранение")
    if d.get("exhaust") or any(u.get("exhaust") for u in uses):
        tags.add("Изгнание")
    if (d.get("echo") or {}).get("when", {}).get("k") == "resonance":
        tags.add("Резонанс")
    if d.get("chain"):
        tags.add("Цепочка")
        if (d["chain"].get("when") or {}).get("k") == "resonance":
            tags.add("Резонанс")
    return [t for t in TAG_ORDER if t in tags] + sorted(tags - set(TAG_ORDER))


# основа слова → (название, пояснение); порядок важен: первое совпадение по началу слова
GLOSSARY = [
    ("кровотеч", "Кровотечение", "В начале хода носителя: урон по числу стаков мимо защиты, затем стаков вдвое "
                                 "меньше. Копите и вскрывайте картами «за каждое кровотечение»."),
    ("контратак", "Контратака", "Стаки: враг ударил вас вплотную — вы сразу отвечаете ударом 4 (+Мощь), стак "
                                "тратится. Держатся, пока не потрачены."),
    ("мощ", "Мощь", "+N к урону каждого удара до конца боя. Копится."),
    ("изгна", "Изгнание", "После розыгрыша карта уходит до конца боя. Изгнанные карты считают некоторые Силы."),
    ("сохранени", "Сохранение", "Карта не сбрасывается в конце хода — остаётся в руке."),
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
]


TAG_INFO = {
    "Удар": "Урон вплотную: дальность 1, подход к врагу или удар по соседям.",
    "Выстрел": "Дальний урон (стрелы, болты).",
    "Область": "Урон или эффект по области: несколько клеток или соседние враги.",
    "Сохранение": "Карта остаётся в руке в конце хода.",
    "Преследование": "Запас преследования: карта [Преследование] после удара делает дополнительный выстрел по той же цели.",
    "Огонь": "Горение, поджог, жар Пиромантки.",
    "Шаг": "Карта двигает героя: шаг, рывок, подход, отскок.",
    "Защита": "Карта даёт защиту.",
    "Толчок": "Толчок, притягивание, столкновения.",
    "Шипы": "Ответный урон тем, кто бьёт вплотную: шипы и контратака.",
    "Кровь": "Кровотечение врагов, плата здоровьем, сила от ран.",
    "Создание": "Карта создаёт временные карты в руку.",
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
            if x.get("op") == "add_card" and x.get("card") and x["card"] not in out:
                out.append(x["card"])
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
    if d.get("meaning") or d.get("token") or d.get("status"):
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
        self._d = None
        self.divine = None               # дар бога (data/deck/gods.json) — поверх прозрения
        self._offer = None               # какие 3 варианта прозрения из 5 предложены (выбираются один раз)
        self.alt_up = None               # Мастерская: улучшенное простое применение (одно на карту)
        self.preview = None              # бой: {"main": [реальный урон…], "alt": […]}; вне боя — None

    def preview_key(self):
        """Хэшируемый снимок preview для кэшей лиц карт."""
        p = self.preview or {}
        return tuple((mode, tuple(v or ())) for mode, v in sorted(p.items()))

    @property
    def d(self):
        """Карта с прозрениями; у карты с уровнями main и cost — выбранного уровня."""
        if self._d is None:
            d = self.base
            for tier, k in enumerate(self.picks):
                d = _merge(d, self.base["growth"][tier]["options"][k])
            if self.divine:
                d = bless(d, self.divine)
            if d.get("levels"):
                lv = d["levels"][min(self.lvl, len(d["levels"]) - 1)]
                d = dict(d, main=lv["main"], cost=lv["heat"])
            if not d.get("alt"):
                d = dict(d, alt=NOALT)
            if self.alt_up is not None:
                d = dict(d, alt=self.alt_up)
            self._d = d
        return self._d

    @property
    def tags(self):
        return card_tags(self.d if not self.levels else dict(self.d, levels=self.levels))

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
    def tier(self):
        return len(self.picks)

    @property
    def name(self):
        return self.d["name"] + ("+" * self.tier if self.d["name"] == self.base["name"] else "")

    @property
    def cost(self):
        return self.d["cost"]

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
    return {"merc": "m_", "hunter": "h_", "pyro": "p_", "priest": "sc_"}.get(hero_id, "")


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
        d = self.depth - 1
        return 1 + fl["hp_per_depth"] * d, 1 + fl["dmg_per_depth"] * d

    def gold_for(self, kind):
        lo, hi = self.floor_cfg["gold"].get(kind, [10, 15])
        return self.rng.randint(lo, hi)

    def shop_stock(self):
        sh = self.data["enemies"]["shop"]
        return [(c, self.rng.randint(*sh["card_price"])) for c in self.reward_offer(sh["cards"])]

    def rewardable(self, cid):
        d = self.defs.get(cid)
        return bool(d) and d.get("category") not in ("basic", "token") and d.get("rarity", 1) > 0

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
        if self.hero.get("mechanic") == "idols":           # Жрец: свитки + нейтральная карта
            from .idols import offer_scrolls
            scrolls = [cid for cid in offer_scrolls(self, count) if self.rewardable(cid)]
            ids = scrolls[:max(1, count - 1)]
            free = [cid for cid in neutral if self.rewardable(cid)]
            while len(ids) < count and free:
                pick = self.weighted_pick(free)
                if pick is None:
                    break
                ids.append(pick)
                free.remove(pick)
            return [Card(cid, self.defs) for cid in ids]
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
        self.deck.append(card)

    def insights(self):
        return [c for c in self.deck if c.insight_ready()]
