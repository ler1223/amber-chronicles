"""Кузня v2 (квиз 2026-11-12): тигель → слиток → примитивы (ковка руками или литьё в форму) → вещь, закалка и отпуск.

Сплав (ALLOYS) — смесь материалов в долях (mix) и уголь (углерод стали); плавится в тигле при melt °C (горн должен
его дать), куётся в окне work, закаливается (hardenable) с quench °C в своей жидкости (liquid) и отпускается до
цвета побежалости (temper). Книга сплава (book) открывает точные пропорции и температуры: без неё — наугад.

Слиток: {"uid", "alloy", "mass", "q", "purity"}; примитив: {"uid", "kind", "alloy", "mass", "q", "cast"};
вещь собирается из примитивов (RECIPES). Потолки качества (как диски и линзы у ювелира): горн (температура),
меха (скорость), наковальня и гладилка (чистота ковки), приборы (точность закалки), жидкости, формы, книги.

Шахта (MINE) — простой тайкун: рабочие, кирки, склад, вагонетки, глубина; время идёт, пока игра открыта."""
import math
import random

# ---------- сплавы ----------

TEMPER = {"straw": ("соломенный", 220, (225, 190, 110)), "bronze": ("бронзовый", 240, (190, 130, 70)),
          "purple": ("пурпурный", 270, (140, 70, 130)), "blue": ("синий", 300, (70, 90, 170)),
          "grey": ("серый", 330, (120, 125, 135))}

ALLOYS = {
    "iron": {"name": "Кричное железо", "mix": {"ore": 1.0}, "coal": 0.02, "melt": 1250, "work": (900, 1200),
             "hard": 0.3, "tough": 0.85, "book": None, "color": (150, 150, 158)},
    "copper": {"name": "Медь", "mix": {"copper": 1.0}, "coal": 0.0, "melt": 1085, "work": (600, 900),
               "hard": 0.2, "tough": 0.9, "book": None, "color": (205, 125, 85)},
    "bronze": {"name": "Бронза", "mix": {"copper": 0.88, "tin": 0.12}, "coal": 0.0, "melt": 950, "work": (600, 850),
               "hard": 0.45, "tough": 0.7, "book": "b_bronze", "color": (200, 150, 80)},
    "silver925": {"name": "Серебро 925", "mix": {"silver": 0.925, "copper": 0.075}, "coal": 0.0, "melt": 900,
                  "work": (500, 750), "hard": 0.3, "tough": 0.8, "book": "b_silver", "precious": 1.0,
                  "color": (215, 218, 225)},
    "gold18": {"name": "Золото 18 карат", "mix": {"gold": 0.75, "silver": 0.125, "copper": 0.125}, "coal": 0.0,
               "melt": 950, "work": (550, 800), "hard": 0.35, "tough": 0.75, "book": "b_gold", "precious": 1.12,
               "socket": 1, "color": (235, 195, 80)},
    "steel": {"name": "Сталь", "mix": {"ore": 1.0}, "coal": 0.04, "melt": 1450, "work": (850, 1150),
              "hard": 0.7, "tough": 0.55, "book": "b_steel", "quench": 800, "liquid": "water", "temper": "straw",
              "color": (170, 175, 185)},
    "spring": {"name": "Рессорная сталь", "mix": {"ore": 1.0}, "coal": 0.03, "melt": 1450, "work": (850, 1150),
               "hard": 0.6, "tough": 0.75, "book": "b_spring", "quench": 820, "liquid": "oil", "temper": "blue",
               "color": (160, 170, 185)},
    "hc_steel": {"name": "Высокоуглеродистая сталь", "mix": {"ore": 1.0}, "coal": 0.06, "melt": 1450,
                 "work": (820, 1100), "hard": 0.85, "tough": 0.35, "book": "b_hc", "quench": 780, "liquid": "brine",
                 "temper": "straw", "color": (180, 182, 190)},
    "starsteel": {"name": "Звёздная сталь", "mix": {"meteor": 0.7, "ore": 0.3}, "coal": 0.03, "melt": 1600,
                  "work": (900, 1250), "hard": 0.9, "tough": 0.7, "book": "b_star", "quench": 850,
                  "liquid": "salamander", "temper": "bronze", "color": (150, 170, 210)},
    "embersteel": {"name": "Эмбер-сталь", "mix": {"embersteel": 0.5, "ore": 0.5}, "coal": 0.03, "melt": 1550,
                   "work": (880, 1200), "hard": 0.88, "tough": 0.6, "book": "b_ember", "quench": 830,
                   "liquid": "glacier", "temper": "purple", "color": (220, 120, 70)},
}

ALLOYS["damascus"] = {"name": "Дамаск", "mix": {}, "coal": 0.0, "melt": 9999, "work": (850, 1150), "hard": 0.8,
                      "tough": 0.72, "book": "b_damascus", "quench": 810, "liquid": "oil", "temper": "straw",
                      "nocrucible": True, "color": (165, 170, 178)}

LIQUIDS = {"water": ("Вода", 0.8), "oil": ("Масло", 0.55), "brine": ("Рассол", 1.0),
           "salamander": ("Кровь саламандры", 0.92), "glacier": ("Талая вода ледника", 0.86)}
# жёсткость закалки; у каждой стали — своя лучшая; слишком резкая — риск трещины, мягкая — меньше твёрдости

PRIMS = {"rod": {"name": "Прут", "mass": 100, "thick": 10.0, "len": 160},
         "strip": {"name": "Полоса", "mass": 100, "thick": 5.0, "len": 260},
         "sheet": {"name": "Лист", "mass": 150, "thick": 2.5, "len": 300},
         "wire": {"name": "Проволока", "mass": 40, "thick": 4.4, "len": 340}}

RECIPES = {"bracers": {"sheet": 2, "strip": 1}, "belt": {"strip": 2, "rod": 1},
           "ring": {"wire": 1}, "amulet": {"sheet": 1, "wire": 1}}

FORGE_TEMP = {0: 1150, 1: 1300, 2: 1500, 3: 1650, 4: 1800}       # уровень горна → наибольшая температура

# из каких металлов куются вещи сета данной редкости (тиры пересекаются: железо годно и редким)
SET_ALLOYS = {
    "ws_forge": {"common": ["iron", "bronze", "copper"], "rare": ["iron", "bronze", "steel"],
                 "epic": ["steel", "spring", "hc_steel"], "legendary": ["hc_steel", "starsteel", "embersteel"]},
    "ws_jewel": {"common": ["copper", "bronze", "silver925"], "rare": ["bronze", "silver925", "gold18"],
                 "epic": ["silver925", "gold18"], "legendary": ["gold18", "starsteel"]},
}

# свой эффект у каждого металла (как у камней): простые металлы — слабые статы (твёрдость, вязкость), но
# сильный эффект; дорогие сплавы — крепче сами, эффект скромнее. (свойство из items.stat_affixes, множитель)
ALLOY_AFFIX = {"iron": ("stout", 1.5), "copper": ("focus", 1.0), "bronze": ("swift", 0.9),
               "silver925": ("haste", 0.9), "gold18": ("reactor", 1.0), "steel": ("keen", 0.6),
               "spring": ("elusive", 0.8), "hc_steel": ("deadly", 0.8), "starsteel": ("wisdom", 1.0),
               "embersteel": ("kindling", 1.0), "damascus": ("keen", 0.7)}


# ---------- торговля с бродячими мастерами ----------

INGOT_VALUE = {"iron": 30, "copper": 40, "bronze": 60, "silver925": 120, "gold18": 260, "steel": 80, "spring": 110,
               "hc_steel": 150, "starsteel": 420, "embersteel": 330, "damascus": 300}      # золота за 100 г
MAT_VALUE = {"ore": 3, "coal": 2, "copper": 5, "tin": 7, "silver": 14, "gold": 30, "meteor": 40,
             "embersteel": 60}                                                           # за единицу (10 г)
MAT_LOT = 10                                       # руду продают пачкой по 10 единиц
TRADE = {"sell_k": 0.5, "buy_k": 1.6, "asks": (1.0, 1.15, 1.3, 1.5)}


def ingot_value(ing):
    return INGOT_VALUE.get(ing["alloy"], 50) * ing["mass"] / 100 * (0.6 + 0.6 * ing.get("q", 0.8))


def prim_value(p):
    """Примитив дороже металла в нём: работа кузнеца (×1.35)."""
    return INGOT_VALUE.get(p["alloy"], 50) * p["mass"] / 100 * 1.35 * (0.6 + 0.6 * p.get("q", 0.8))


def haggle_chance(ask, patience):
    """Согласится ли торговец на цену ×ask: без торга — всегда; выше — реже, и тем реже, чем меньше терпения."""
    if ask <= 1.0001:
        return 1.0
    return max(0.0, min(1.0, (1 - (ask - 1) * 1.5) * (0.45 + 0.55 * patience)))


def roll_ingots(rng, known, n):
    """Слитки у бродячего кузнеца: в основном знакомые сплавы, иногда — ещё не изученный (раньше книги)."""
    plain = [a for a in known if a in INGOT_VALUE and a != "damascus"] or ["iron"]
    rare = [a for a in INGOT_VALUE if a not in known and a != "damascus"]
    out = []
    for _ in range(n):
        aid = rng.choice(rare) if rare and rng.random() < 0.25 else rng.choice(plain)
        out.append({"alloy": aid, "mass": rng.choice((200, 300, 400, 600)), "q": round(rng.uniform(0.7, 0.98), 2),
                    "purity": round(rng.uniform(0.8, 0.97), 2)})
    return out


def set_alloys(ws, rarity):
    return SET_ALLOYS.get(ws, {}).get(rarity, [])


def metal_affixes(prims, q=1.0):
    """Эффекты металлов вещи: по доле массы каждого сплава × качество вещи."""
    total = sum(p["mass"] for p in prims) or 1
    out = {}
    for p in prims:
        out[p["alloy"]] = out.get(p["alloy"], 0) + p["mass"] / total
    return [{"alloy": a, "id": ALLOY_AFFIX[a][0], "k": round(ALLOY_AFFIX[a][1] * share * q, 3)}
            for a, share in sorted(out.items(), key=lambda kv: -kv[1]) if a in ALLOY_AFFIX]

# прокачки (бродячий кузнец, походы): (название, цена, вид, описание)
TOOLS = {
    "bellows": ("Кузнечные меха", 900, "forge", "горн греет вдвое быстрее"),
    "pyrometer": ("Пирометр", 3000, "gauge", "температура цифрой — закалка точнее (+12% потолка)"),
    "magnet": ("Магнит на ручке", 1200, "gauge", "точка Кюри: сталь перестаёт магнититься — пора в закалку (+5%)"),
    "hourglass": ("Песочные часы", 800, "gauge", "выдержка в жидкости по часам (+4%)"),
    "calipers": ("Штангенциркуль", 1500, "gauge", "ширина и толщина под молотом цифрами (без него — на глаз)"),
    "hardness": ("Твердомер", 4000, "gauge", "твёрдость после закалки — видно, где отпускать (+4%)"),
    "hammer_sledge": ("Кувалда", 900, "hammer", "тянет металл быстрее, но грубее"),
    "flatter": ("Гладилка", 1500, "hammer", "выравнивает поверхность — чистота ковки выше"),
    "power_hammer": ("Автомолот", 6000, "hammer", "держите ЛКМ — бьёт сам по точке под курсором (протяжка, разгонка)"),
    "punch": ("Пробойник", 1200, "hammer", "ровные отверстия точно по меткам (без него — бородок, грубее)"),
    "swage": ("Обжимка", 1400, "hammer", "скругляет сечение быстро и ровно (без неё — удары «на угол»)"),
    "anvil_steel": ("Стальная наковальня", 3500, "anvil", "меньше теряется удар, чище поверхность (потолок 95%)"),
    "anvil_master": ("Наковальня мастера", 12000, "anvil", "идеальная поверхность (потолок 100%)"),
    "oil": ("Закалочное масло", 600, "liquid", "мягкая закалка: рессорные стали"),
    "brine": ("Рассол", 400, "liquid", "самая резкая закалка: высокоуглеродистые стали"),
    "salamander": ("Кровь саламандры", 8000, "liquid", "для звёздной стали"),
    "glacier": ("Талая вода ледника", 7000, "liquid", "для эмбер-стали"),
    "mold_rod": ("Форма для прутьев", 1500, "mold", "лить прут сразу из тигля"),
    "mold_strip": ("Форма для полос", 1500, "mold", "лить полосу сразу из тигля"),
    "mold_sheet": ("Форма для листов", 2500, "mold", "лить лист сразу из тигля"),
    "mold_wire": ("Волока для проволоки", 2000, "mold", "тянуть проволоку из прутка без ковки"),
}
BOOKS = {
    "b_bronze": ("Книга «Бронзы и колокола»", 1200, "бронза: медь 88%, олово 12%, 950 °C"),
    "b_silver": ("Книга «Серебро монетное»", 1500, "серебро 925: серебро и немного меди"),
    "b_steel": ("Книга «Сталь из кричного железа»", 3000, "сталь: уголь 4%, закалка в воде с 800 °C"),
    "b_spring": ("Книга «Рессоры и пружины»", 3500, "рессорная сталь: уголь 3%, масло, синий отпуск"),
    "b_gold": ("Книга «Червонное золото»", 4000, "золото 18 карат: оправы на камень больше"),
    "b_hc": ("Книга «Клинки высокой стали»", 6000, "уголь 6%, рассол с 780 °C, соломенный отпуск"),
    "b_star": ("Книга «Звёздная сталь»", 12000, "метеоритное железо, кровь саламандры"),
    "b_ember": ("Книга «Огонь в металле»", 10000, "эмбер-сталь, талая вода ледника"),
    "b_quench": ("Книга «Закалка и отпуск»", 2500, "показывает температуру закалки и цвет отпуска"),
    "b_damascus": ("Книга «Тайны дамаска»", 9000, "пакет и сварка двух сталей — узорчатый слиток"),
    "c_bracers": ("Техкарта мастера: наручи", 3500, "лишний этап доводки — наручи до 130% и свойство"),
    "c_belt": ("Техкарта мастера: пояс", 3500, "лишний этап доводки — пояс до 130% и свойство"),
    "c_ring": ("Техкарта мастера: кольцо", 4000, "лишний этап доводки — кольцо до 130% и свойство"),
    "c_amulet": ("Техкарта мастера: амулет", 4500, "лишний этап доводки — амулет до 130% и свойство"),
}
START_TOOLS = ["water"]                                     # вода и шкала цветов каления — с самого начала


def alloy(aid):
    return ALLOYS[aid]


def known_alloys(tools):
    return [a for a, v in ALLOYS.items() if (v["book"] is None or v["book"] in tools) and not v.get("nocrucible")]


def max_temp(forge_level):
    return FORGE_TEMP.get(max(0, min(4, forge_level)), 1150)


def can_melt(aid, forge_level):
    return ALLOYS[aid]["melt"] + 30 <= max_temp(forge_level)


# ---------- тигель ----------

def charge_need(aid, mass):
    """Сколько материалов на слиток массой mass (г): {материал: единиц} (1 единица = 10 г, уголь — по доле)."""
    a = ALLOYS[aid]
    need = {m: max(1, round(mass * s / 10)) for m, s in a["mix"].items()}
    if a["coal"]:
        need["coal"] = max(1, round(mass * a["coal"] * 2.5 / 10))
    return need


def mix_accuracy(aid, charge):
    """Насколько смесь в тигле совпала с рецептом: 1 — точно; углерод (уголь) важнее всего у сталей."""
    a = ALLOYS[aid]
    metal = sum(v for m, v in charge.items() if m in a["mix"])
    if metal <= 0:
        return 0.0
    err = sum(abs(charge.get(m, 0) / metal - s) for m, s in a["mix"].items())
    err += sum(charge.get(m, 0) / metal for m in charge if m not in a["mix"] and m != "coal")
    if a["coal"]:
        want = a["coal"] * 2.5
        err += abs(charge.get("coal", 0) / metal - want) / max(want, 1e-6) * 0.5
    elif charge.get("coal"):
        err += 0.2
    return round(max(0.0, 1 - max(0.0, err - 0.03) * 2.2), 3)          # 3% — погрешность весов (по 10 г)


def ingot_q(accuracy, purity, heat):
    """Качество слитка: точность смеси, чистота (снятый шлак), удержание жара в окне плавки."""
    return round(max(0.0, min(1.0, accuracy * 0.5 + purity * 0.25 + heat * 0.25)), 3)


def charge_mass(charge):
    return sum(v for m, v in charge.items() if m != "coal") * 10


# ---------- примитивы ----------

def anvil_cap(tools):
    return 1.0 if "anvil_master" in tools else 0.95 if "anvil_steel" in tools else 0.85


def forged_q(score, tools):
    """Кованый примитив: оценка ковки (ровность, длина, трещины, окалина) × наковальня (+ гладилка)."""
    cap = anvil_cap(tools) + (0.03 if "flatter" in tools else 0.0)
    return round(max(0.0, min(1.0, score)) * min(1.0, cap), 3)


def cast_q(pour_acc, tools):
    """Литой примитив: точность температуры разлива; литьё уступает ковке (потолок 85%)."""
    return round(max(0.0, min(1.0, pour_acc)) * 0.85, 3)


# ---------- закалка и отпуск ----------

def gauge_cap(tools):
    """Потолок точности термообработки — от приборов (без них — на глаз по цвету)."""
    return 0.75 + 0.12 * ("pyrometer" in tools) + 0.05 * ("magnet" in tools) + 0.04 * ("hourglass" in tools) + \
        0.04 * ("hardness" in tools)


# ванна: лучшая температура жидкости (°C), с какой начинает (°C); деталь вынимают, остыв до out (°C)
BATH = {"water": 40, "oil": 80, "brine": 30, "salamander": 140, "glacier": 8}
BATH_START = {"glacier": 2}
QUENCH_OUT = {"steel": 150, "spring": 220, "hc_steel": 120, "starsteel": 180, "embersteel": 160, "damascus": 160}


def bath_start(liquid):
    return BATH_START.get(liquid, 15)


def quench_out(aid):
    return QUENCH_OUT.get(aid, 150)


def bath_rate(liquid, bath_t):
    """Как быстро жидкость снимает жар (1/с): резкость жидкости, горячая ванна — мягче."""
    sev = LIQUIDS.get(liquid, ("", 0.6))[1]
    return 1.25 * sev * max(0.45, 1 - max(0.0, bath_t - BATH.get(liquid, 40)) / 200)


def quench_eval(aid, t_in, liquid, bath_t, t_out, rng=None):
    """Закалка клещами: (доля твёрдости 0–1, трещина ли, разбор по частям).
    t_in — жар детали при погружении, bath_t — жидкость, t_out — жар детали, когда вынули из ванны."""
    a = ALLOYS[aid]
    if not a.get("quench"):
        return 1.0, False, {}
    t_acc = max(0.0, 1 - abs(t_in - a["quench"]) / 120)
    best = LIQUIDS[a["liquid"]][1]
    sev = LIQUIDS.get(liquid, ("", 0.5))[1]
    fit = max(0.2, 1 - abs(sev - best) * 1.6)
    if liquid != a["liquid"] and a["liquid"] in ("salamander", "glacier"):
        fit = min(fit, 0.7)
    want = BATH.get(liquid, 40)
    bath = max(0.3, 1 - max(0.0, abs(bath_t - want) - 10) / 70)
    out = quench_out(aid)
    if t_out > out + 50:                                    # вынули горячей — не прокалилась
        o_acc = max(0.0, 1 - (t_out - out - 50) / 300)
    else:
        o_acc = 1.0
    risk = 0.0                                              # трещина: резкая жидкость, холодная ванна, передержка
    risk += max(0.0, sev - best - 0.12) * 2.5
    risk += max(0.0, want - 15 - bath_t) / 60
    risk += max(0.0, out - 60 - t_out) / 150
    crack = (rng or random).random() < min(0.9, risk)
    hard = round(t_acc * fit * bath * o_acc, 3)
    return hard, crack, {"t_in": round(t_acc, 3), "liquid": round(fit, 3), "bath": round(bath, 3),
                         "out": round(o_acc, 3), "risk": round(min(0.9, risk), 3)}


def cast_fill_q(fill, over):
    """Литьё в форму: недолив — деталь короче и хуже, перелив — облой (заусенец), чем больше — тем хуже."""
    f = max(0.0, min(1.0, fill))
    return round(max(0.0, (f ** 1.5) * (1 - min(0.6, over * 1.5))), 3)


def quench_result(aid, temp, liquid, rng=None):
    """Закалка: (доля твёрдости 0–1, трещина ли). Не та температура — мягче; слишком резкая жидкость — трещина."""
    a = ALLOYS[aid]
    if not a.get("quench"):
        return 1.0, False
    t_acc = max(0.0, 1 - abs(temp - a["quench"]) / 120)
    best = LIQUIDS[a["liquid"]][1]
    sev = LIQUIDS.get(liquid, ("", 0.5))[1]
    fit = max(0.2, 1 - abs(sev - best) * 1.6)
    if liquid != a["liquid"] and a["liquid"] in ("salamander", "glacier"):
        fit = min(fit, 0.7)                                   # волшебной стали нужна своя жидкость
    crack = sev - best > 0.18 and (rng or random).random() < 0.5
    return round(t_acc * fit, 3), crack


def temper_result(aid, temp):
    """Отпуск: точность попадания в цвет побежалости (по температуре)."""
    a = ALLOYS[aid]
    if not a.get("temper"):
        return 1.0
    want = TEMPER[a["temper"]][1]
    return round(max(0.0, 1 - abs(temp - want) / 60), 3)


def temper_color(temp):
    """Цвет побежалости на металле при нагреве до temp °C (непрерывно)."""
    stops = [(150, (175, 178, 186)), (220, TEMPER["straw"][2]), (240, TEMPER["bronze"][2]),
             (270, TEMPER["purple"][2]), (300, TEMPER["blue"][2]), (340, TEMPER["grey"][2])]
    if temp <= stops[0][0]:
        return stops[0][1]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if temp <= t1:
            k = (temp - t0) / (t1 - t0)
            return tuple(int(a + (b - a) * k) for a, b in zip(c0, c1))
    return stops[-1][1]


def item_quality(prims, heat, tools):
    """Качество вещи 0.7–1.3: материал (слитки) + примитивы + термообработка (с потолком приборов)."""
    pq = sum(p["q"] for p in prims) / max(1, len(prims))
    heat = min(heat, gauge_cap(tools))
    score = 0.55 * pq + 0.45 * heat
    return round(0.7 + 0.6 * max(0.0, min(1.0, score)), 3)


def item_metal(prims, quench_hard, temper_acc):
    """Металл вещи (для статов: artifacts.metal_mods): твёрдость — от закалки, вязкость — от отпуска; литьё — хрупче."""
    m = sum(p["mass"] for p in prims) or 1
    hard = tough = 0.0
    for p in prims:
        a = ALLOYS[p["alloy"]]
        w = p["mass"] / m
        hk = (0.6 + 0.4 * quench_hard) if a.get("quench") else 1.0
        tk = (0.75 + 0.25 * temper_acc) if a.get("temper") else 1.0
        tk *= 0.85 if p.get("cast") else 1.0
        hard += a["hard"] * hk * w
        tough += a["tough"] * tk * w
    pattern = max((p.get("pattern", 0.0) for p in prims), default=0.0)       # дамаск: узор → крит
    return {"hard": round(hard, 3), "tough": round(tough, 3), "layers": 1 + int(pattern * 200), "pattern": pattern,
            "mass": int(m), "heavy": 0.0}


ASSEMBLY_CAP = 1.0          # вещь, собранная из примитивов, — не выше 100%; 130% и свойство — у цельной ковки


def item_mass(kind):
    """Сколько металла в вещи (по рецепту из примитивов) — столько нужно слитка для цельной ковки."""
    return sum(PRIMS[k]["mass"] * n for k, n in RECIPES[kind].items())


def frame_bonus(prims):
    """Оправа ювелира: металл — множитель силы и лишнее гнездо (золото)."""
    best = max((ALLOYS[p["alloy"]].get("precious", 0.85) for p in prims), default=0.85)
    sock = max((ALLOYS[p["alloy"]].get("socket", 0) for p in prims), default=0)
    return best, sock


# ---------- шахта ----------

MINE = {
    "depths": [
        {"name": "Штольня", "cost": 0, "mats": {"ore": 1.0, "coal": 0.9, "copper": 0.5}},
        {"name": "Второй горизонт", "cost": 4000, "mats": {"tin": 0.45, "silver": 0.25}},
        {"name": "Глубокая жила", "cost": 15000, "mats": {"gold": 0.12, "gems": 0.35}, "rough": 0.004},
        {"name": "Звёздный пласт", "cost": 45000, "mats": {"meteor": 0.06}, "rough": 0.008},
    ],
    "workers": [300, 500, 900, 1500, 2400, 3600, 5200, 7500],   # цена следующего рабочего (до 8)
    "pick": [(1.0, 0), (1.5, 1200), (2.2, 4000), (3.2, 12000), (4.5, 30000)],     # (выработка ×, цена)
    "store": [(80, 0), (200, 1000), (500, 3500), (1200, 10000), (3000, 28000)],  # (вместимость, цена)
    "cart": [(8, 0), (20, 1500), (50, 5000), (120, 14000), (300, 36000)],         # (подъём в минуту, цена)
    "per_worker": 1.2,                                         # (замедлено в 5 раз, квиз 2026-11-12)
    "max_workers": 8,                                          # единиц в минуту на рабочего с простой киркой
}


def new_mine():
    return {"workers": 1, "pick": 0, "store": 0, "cart": 0, "depth": 0, "stock": {}, "acc": {}, "rough": 0,
            "racc": 0.0, "t": 0.0}


def mine_rate(m):
    """Добыча в минуту (до склада): рабочие × кирка, но не больше, чем поднимут вагонетки."""
    dig = m["workers"] * MINE["per_worker"] * MINE["pick"][m["pick"]][0]
    return min(dig, MINE["cart"][m["cart"]][0])


def mine_cap(m):
    return MINE["store"][m["store"]][0]


def mine_weights(m):
    w = {}
    for d in MINE["depths"][:m["depth"] + 1]:
        for k, v in d["mats"].items():
            w[k] = w.get(k, 0) + v
    return w


def mine_tick(m, dt, rng=None):
    """dt секунд работы шахты: добыча по долям жил, пока склад не полон; глубокие жилы — шанс сырого самоцвета."""
    total = sum(m["stock"].values())
    cap = mine_cap(m)
    if total >= cap or dt <= 0:
        return 0.0
    units = min(mine_rate(m) * dt / 60.0, cap - total)
    w = mine_weights(m)
    s = sum(w.values())
    for k, v in w.items():
        m["acc"][k] = m["acc"].get(k, 0.0) + units * v / s
        whole = int(m["acc"][k])
        if whole:
            m["stock"][k] = m["stock"].get(k, 0) + whole
            m["acc"][k] -= whole
    chance = sum(d.get("rough", 0) for d in MINE["depths"][:m["depth"] + 1])
    if chance:
        m["racc"] = m.get("racc", 0.0) + units * chance
        while m["racc"] >= 1:
            m["rough"] = m.get("rough", 0) + 1
            m["racc"] -= 1
    return units


def mine_next_cost(m, what):
    if what == "workers":                              # до 8 рабочих: цена каждого следующего
        i = m["workers"] - 1
        return MINE["workers"][i] if m["workers"] < MINE["max_workers"] else None
    if what == "depth":
        i = m["depth"] + 1
        return MINE["depths"][i]["cost"] if i < len(MINE["depths"]) else None
    i = m[what] + 1
    table = MINE[what]
    return table[i][1] if i < len(table) else None
