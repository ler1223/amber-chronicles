"""Сюжетная прогрессия героя: пул навыков, слоты и пассивные доктрины.

Отдельно от sim/meta.py, чтобы не менять основную игру и режим героев. Данные — data/story_progression.json:
у класса есть 5 навыков (3 базовых и 2 бывших навыка подклассов) и 2 доктрины (бывшие подклассы, только пассивка).
Навыки открываются уровнем героя, в бой берётся ограниченное число слотов. Число слотов задаётся данными,
код нигде не считает его равным трём.
"""
from . import meta


def cfg(data):
    return data.story_progression


def slots(data):
    return max(1, int(cfg(data).get("slots", 3)))


def level(hero):
    return int((hero.get("rpg") or {}).get("level", 1))


def entries(data, cls):
    return cfg(data)["classes"][cls]["skills"]


def all_skills(data, cls):
    return [e["id"] for e in entries(data, cls)]


def skill_level(data, cls, sid):
    return next((int(e["level"]) for e in entries(data, cls) if e["id"] == sid), 99)


def is_unlocked(data, cls, sid, lvl):
    return sid in all_skills(data, cls) and lvl >= skill_level(data, cls, sid)


def unlocked_skills(data, cls, lvl):
    return [sid for sid in all_skills(data, cls) if is_unlocked(data, cls, sid, lvl)]


def default_loadout(data, cls, lvl):
    return unlocked_skills(data, cls, lvl)[:slots(data)]


def doctrine_entries(data, cls):
    return cfg(data)["classes"][cls].get("doctrines", [])


def doctrine_ids(data, cls):
    return [d["id"] for d in doctrine_entries(data, cls)]


def doctrine_level(data, cls, did):
    return next((int(d["level"]) for d in doctrine_entries(data, cls) if d["id"] == did), 99)


def doctrine_available(data, cls, did, lvl):
    return did in doctrine_ids(data, cls) and lvl >= doctrine_level(data, cls, did)


def doctrine_unlock_level(data, cls):
    levels = [int(d["level"]) for d in doctrine_entries(data, cls)]
    return min(levels) if levels else 1


def _trim_branches(data, cls, hero):
    load = set(hero.get("skill_loadout", []))
    hero["branches"] = {sid: list(v) for sid, v in hero.get("branches", {}).items()
                        if sid in load and sid in data.branches and v[0] in ("A", "B")}


def _trim_talents(data, cls, hero):
    hero["talents"] = [t for t in hero.get("talents", []) if t in data.talents
                       and meta.talent_fits(data, cls, hero, t)
                       and not any("new_skill" in m for m in data.talents[t]["mods"])]


def sanitize_hero(data, cls, hero):
    """Привести сюжетного героя к данным: валидный пул, слоты, доктрина, ветки и таланты."""
    hero.setdefault("skill_loadout", [])
    hero.setdefault("doctrine", None)
    hero["path"] = None
    lvl = level(hero)
    pool = all_skills(data, cls)
    load = []
    for sid in hero.get("skill_loadout", []):
        if sid in pool and sid not in load and is_unlocked(data, cls, sid, lvl):
            load.append(sid)
    if not load:
        load = default_loadout(data, cls, lvl)
    hero["skill_loadout"] = load[:slots(data)]
    did = hero.get("doctrine")
    if did not in doctrine_ids(data, cls) or not doctrine_available(data, cls, did, lvl):
        hero["doctrine"] = None
    _trim_branches(data, cls, hero)
    _trim_talents(data, cls, hero)
    hero["loadout"] = [i for i in hero.get("loadout", []) if i in data.items]
    meta.trim_to_points(data, hero)


def auto_fill(data, cls, hero):
    """После уровня открыть новые навыки в свободные слоты; занятые слоты игрок меняет сам."""
    sanitize_hero(data, cls, hero)
    load = list(hero["skill_loadout"])
    for sid in unlocked_skills(data, cls, level(hero)):
        if len(load) >= slots(data):
            break
        if sid not in load:
            load.append(sid)
    hero["skill_loadout"] = load[:slots(data)]
    _trim_branches(data, cls, hero)
    return hero["skill_loadout"]


def equip(data, cls, hero, sid, slot):
    """Поставить навык в выбранный слот. False — навык ещё закрыт или слота нет."""
    if not is_unlocked(data, cls, sid, level(hero)) or not 0 <= slot < slots(data):
        return False
    load = list(hero.get("skill_loadout", []))
    if sid in load:
        old = load.index(sid)
        if old == slot:
            return True
        load.pop(old)
        if old < slot:
            slot -= 1
    if slot < len(load):
        load[slot] = sid
    else:
        load.append(sid)
    hero["skill_loadout"] = load[:slots(data)]
    _trim_branches(data, cls, hero)
    return True


def unequip(data, cls, hero, slot):
    """Убрать навык из слота. False — слот пуст или это последний навык."""
    load = list(hero.get("skill_loadout", []))
    if not 0 <= slot < len(load) or len(load) <= 1:
        return False
    load.pop(slot)
    hero["skill_loadout"] = load
    _trim_branches(data, cls, hero)
    return True


def set_doctrine(data, cls, hero, did):
    """Выбрать пассивную доктрину (None — классовая пассивка). False — ещё не открыта."""
    if did is not None and not doctrine_available(data, cls, did, level(hero)):
        return False
    hero["doctrine"] = did
    _trim_talents(data, cls, hero)
    return True


def talent_options(data, cls, hero):
    """Таланты сюжета: новые навыки не даём — пул фиксирован, поэтому такие таланты скрыты."""
    return [tid for tid in meta.talent_options(data, cls, hero)
            if not any("new_skill" in m for m in data.talents[tid]["mods"])]
