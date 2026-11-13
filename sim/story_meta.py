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
    """Открытые навыки для слотов (ультимейт — отдельно, см. battle_skills)."""
    always = set(cfg(data)["classes"].get(cls, {}).get("always", []))
    return [sid for sid in all_skills(data, cls)
            if is_unlocked(data, cls, sid, lvl) and not is_ult(data, cls, sid) and sid not in always]


# ---------- ультимейт, обязательные навыки и зависимости ----------

def ults_of(data, cls):
    """Ультимейты класса (до трёх — на разные способы игры). У героя — один, случайный (как набор навыков)."""
    return [e["id"] for e in entries(data, cls) if e.get("ult")]


def ult_of(data, cls, skills=None):
    """Ультимейт героя: не занимает слот, в бою всегда четвёртый (клавиша R). skills — набор героя: его ультимейт
    из них; без набора (или в наборе его нет) — первый ультимейт класса."""
    ults = ults_of(data, cls)
    if skills:
        own = next((s for s in skills if s in ults), None)
        if own:
            return own
    return ults[0] if ults else None


def is_ult(data, cls, sid):
    return sid is not None and sid in ults_of(data, cls)


def mech_of(data, cls):
    """Кнопка механики класса (Фитиль подрывника): всегда в бою, вне слотов, клавиша F, без AP и перезарядки."""
    return cfg(data)["classes"].get(cls, {}).get("mech")


def notes_of(data, cls):
    """Бард: вместо слотов — три ноты (Q, W, E); пул класса — мелодии."""
    return list(cfg(data)["classes"][cls].get("notes", []))


def melodies(data, cls, lvl):
    """Мелодии, которые бард знает на этом уровне."""
    return [s for s in unlocked_skills(data, cls, lvl) if data.skills.get(s, {}).get("melody")]


def battle_skills(data, cls, hero):
    """Навыки героя в бой: слоты и, когда открыт, ультимейт четвёртым (у барда — три ноты и финал)."""
    notes = notes_of(data, cls)
    load = notes if notes else [s for s in hero.get("skill_loadout", []) if not is_ult(data, cls, s)][:slots(data)]
    always = [s for s in cfg(data)["classes"][cls].get("always", []) if s in data.skills]
    if always:
        load = always + [s for s in load if s not in always]
    ult = hero.get("ult") if is_ult(data, cls, hero.get("ult")) else ult_of(data, cls)
    if ult and is_unlocked(data, cls, ult, level(hero)):
        load.append(ult)
    mech = mech_of(data, cls)
    if mech and mech in data.skills:
        load.append(mech)
    return load


def core_group(data, cls):
    """Обязательная группа: хотя бы один из этих навыков держит механику класса."""
    return list(cfg(data)["classes"][cls].get("core", []))


def requires(data, cls, sid):
    """Навык работает, только если в наборе есть один из этих (облик, тотем, песня, огонь…)."""
    return list(cfg(data)["classes"][cls].get("requires", {}).get(sid, []))


def kit_ok(data, cls, skills):
    """Набор цельный: есть навык из обязательной группы, у каждого навыка есть то, на чём он работает."""
    have = set(skills) | set(cfg(data)["classes"].get(cls, {}).get("always", []))
    if notes_of(data, cls):
        return True
    core = core_group(data, cls)
    if core and not have & set(core):
        return False
    return all(not requires(data, cls, s) or have & set(requires(data, cls, s)) for s in skills)


def random_kit(data, cls, rng, n=None):
    """Случайный цельный набор для таверны: навык из обязательной группы + совместимые + ультимейт."""
    n = n or slots(data)
    if notes_of(data, cls):                   # бард: ноты и финал
        ults = ults_of(data, cls)
        return notes_of(data, cls) + ([rng.choice(ults)] if ults else [])
    always = set(cfg(data)["classes"].get(cls, {}).get("always", []))
    pool = [s for s in all_skills(data, cls) if not is_ult(data, cls, s) and s not in always]
    core = [s for s in core_group(data, cls) if s in pool] or pool[:1]
    kit = [rng.choice(core)]
    rest = [s for s in pool if s not in kit]
    rng.shuffle(rest)
    for _ in range(3):                        # зависимый навык может стать доступным после другого
        for s in list(rest):
            if len(kit) >= n:
                break
            need = requires(data, cls, s)
            if not need or set(need) & set(kit):
                kit.append(s)
                rest.remove(s)
    for s in rest:                            # если всё ещё мало — добрать «самостоятельные»
        if len(kit) >= n:
            break
        if not requires(data, cls, s):
            kit.append(s)
    ults = ults_of(data, cls)
    return kit[:n] + ([rng.choice(ults)] if ults else [])


def default_loadout(data, cls, lvl):
    return unlocked_skills(data, cls, lvl)[:slots(data)]


def one_skill_choices(data, cls, lvl, hero=None):
    """Навыки, которые герой может взять единственной способностью в бесконечном забеге.
    В отличие от обычного набора, ультимейт здесь — такой же выбор, а не отдельная кнопка R.
    Если передан герой, выбор ограничен его текущим набором (ветки и ранги продолжают работать)."""
    if notes_of(data, cls):
        pool = notes_of(data, cls)
    else:
        pool = all_skills(data, cls)
    out = [sid for sid in pool if sid in data.skills and is_unlocked(data, cls, sid, lvl)]
    if hero is not None:
        always = cfg(data)["classes"].get(cls, {}).get("always", [])
        own = list(getattr(hero, "skills", [])) + list(always)
        extra = [s for s in own if s in data.skills and s not in out
                 and (s in always or not is_ult(data, cls, s) or is_unlocked(data, cls, s, lvl))]
        if extra:
            out += extra
        own = [s for s in out if s in own]
        if own:
            out = own
    return out


def default_one_skill(data, cls, lvl, hero=None):
    """Разумный стартовый выбор: открытый ультимейт, иначе первый доступный навык."""
    choices = one_skill_choices(data, cls, lvl, hero)
    if not choices:
        return None
    ults = set(ults_of(data, cls))
    return next((s for s in choices if s in ults), choices[0])


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
                        if sid in load and sid in data.branches and v[0] in data.branches[sid]}


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
        if sid in pool and sid not in load and is_unlocked(data, cls, sid, lvl) and not is_ult(data, cls, sid):
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
    """Поставить навык в выбранный слот. False — навык ещё закрыт, это ультимейт (он всегда на R) или слота нет."""
    if not is_unlocked(data, cls, sid, level(hero)) or not 0 <= slot < slots(data) or is_ult(data, cls, sid)             or notes_of(data, cls):
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
