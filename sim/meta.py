"""Подготовка героя между вылазками: мастерство, путь (подкласс), ветки навыков, таланты.

Герой в профиле — словарь {"xp", "path", "branches": {skill: [ветка, ступень]}, "talents", "autocast", "loadout"}.
Мастерство открывает варианты навсегда; сам выбор свободно меняется между вылазками в пределах очков мастерства.
Без pygame — проверяется тестами.
"""
from .build import class_skills


def new_hero():
    return {"xp": 0, "path": None, "branches": {}, "talents": [], "autocast": {}, "loadout": [], "bonus_points": 0,
            "rpg": {"level": 1, "xp": 0, "points": {"str": 0, "agi": 0, "int": 0}}}    # режим героев


def mastery_level(data, xp):
    return sum(1 for need in data.config["mastery"]["xp_levels"] if xp >= need)


def mastery_progress(data, xp):
    """(набрано на этом уровне, нужно до следующего) или None на максимуме."""
    levels = data.config["mastery"]["xp_levels"]
    lvl = mastery_level(data, xp)
    if lvl >= len(levels):
        return None
    return xp - levels[lvl - 1], levels[lvl] - levels[lvl - 1]


def points_total(data, hero):
    return data.config["mastery"]["points_base"] + mastery_level(data, hero["xp"]) + hero.get("bonus_points", 0)


def talent_cost(data, tid):
    return data.talents[tid].get("cost", 1)


def build_cost(data, hero):
    return sum(t for _, t in hero["branches"].values()) + sum(talent_cost(data, t) for t in hero["talents"])


def points_free(data, hero):
    return points_total(data, hero) - build_cost(data, hero)


# ---------- путь ----------

def path_unlock_level(data):
    return data.config["mastery"]["path_unlock"]


def paths_for(data, cls):
    return [pid for pid, p in data.paths.items() if p["class"] == cls]


def can_take_path(data, hero, path):
    return path is None or mastery_level(data, hero["xp"]) >= path_unlock_level(data)


def hero_skills(data, cls, hero):
    """Три навыка героя с учётом пути — у них и есть ветки."""
    return class_skills(data, cls, hero["path"])


def passive_kind(data, cls, hero):
    return (data.paths[hero["path"]]["passive"] if hero["path"] else data.classes[cls]["passive"])["kind"]


def set_path(data, cls, hero, path):
    """Смена пути: ветки заменённых навыков и несовместимые таланты снимаются (очки возвращаются)."""
    if not can_take_path(data, hero, path):
        return False
    hero["path"] = path
    skills = hero_skills(data, cls, hero)
    hero["branches"] = {sid: v for sid, v in hero["branches"].items() if sid in skills}
    hero["talents"] = [t for t in hero["talents"] if talent_fits(data, cls, hero, t)]
    return True


# ---------- ветки ----------

def click_branch(data, hero, sid, branch, tier):
    """Клик по ступени: взять ветку до этой ступени (другая ветка навыка снимается) или, если она уже взята,
    откатить до ступени ниже. False — не хватает очков."""
    cur = hero["branches"].get(sid)
    if cur and cur[0] == branch and cur[1] >= tier:
        new = tier - 1
    else:
        new = tier
    old_cost = cur[1] if cur else 0
    if new - old_cost > points_free(data, hero):
        return False
    if new <= 0:
        hero["branches"].pop(sid, None)
    else:
        hero["branches"][sid] = [branch, new]
    if (cur[0] if cur else None) != (branch if new > 0 else None):
        hero["autocast"].pop(sid, None)   # навык сменил форму — автокаст с умолчаний новой формы
    return True


# ---------- таланты ----------

def talent_fits(data, cls, hero, tid):
    """Талант своего класса (или общий); модификатор пассивки — только для пассивки того же вида."""
    t = data.talents[tid]
    if t["class"] not in (cls, "any"):
        return False
    kind = passive_kind(data, cls, hero)
    return all(m.get("kind", kind) == kind for m in t["mods"] if "passive" in m)


def talent_options(data, cls, hero):
    return [tid for tid in data.talents if talent_fits(data, cls, hero, tid)]


def toggle_talent(data, cls, hero, tid):
    if tid in hero["talents"]:
        hero["talents"].remove(tid)
        return True
    if not talent_fits(data, cls, hero, tid) or talent_cost(data, tid) > points_free(data, hero):
        return False
    hero["talents"].append(tid)
    return True


def trim_to_points(data, hero):
    """Если очков стало меньше (не должно, но на всякий случай) — снимаем таланты, потом ступени веток."""
    while points_free(data, hero) < 0 and hero["talents"]:
        hero["talents"].pop()
    while points_free(data, hero) < 0 and hero["branches"]:
        sid = next(iter(hero["branches"]))
        b, t = hero["branches"][sid]
        if t > 1:
            hero["branches"][sid] = [b, t - 1]
        else:
            del hero["branches"][sid]
