"""Сборка прототипа юнита: класс + путь + таланты + ветки + руны + предметы → словарь, который понимает Unit.

Таланты, ветки, предметы и реликвии описываются одним языком модификаторов
(см. data/talents.json, branches.json, items.json, relics.json).
"""
import copy

ATTACK_STATS = {"atk_damage": "damage", "atk_range": "range", "atk_cooldown": "cooldown"}
MIN_VALUES = {"ap": 0, "cast": 0, "cooldown": 0, "range": 0, "ap_regen": 0.3, "move_time": 0.15}
AMOUNT_EFFECTS = ("damage", "heal", "shield", "chain", "line")


def branch_tiers(data, sid, branch, tier):
    """Ступени ветки, взятые до tier включительно."""
    return data.branches[sid][branch]["tiers"][:tier]


def skill_in_branch(data, sid, branch, tier):
    """Навык в форме ветки без остального героя (галерея эффектов, тесты)."""
    sk = copy.deepcopy(data.skills[sid])
    for t in branch_tiers(data, sid, branch, tier):
        for m in t["mods"]:
            apply_skill_mod(sk, m)
    sk["branch"] = (branch, tier)
    radii = [e.get("radius", 0) for e in sk["effects"] if e.get("at") != "caster"]
    if "radius" in sk or any(radii):
        sk["radius"] = max(radii or [0])
    return sk


def class_skills(data, cls_id, path=None):
    """Три базовых навыка героя с учётом замен пути."""
    repl = data.paths[path]["replace"] if path else {}
    return [repl.get(sid, sid) for sid in data.classes[cls_id]["skills"]]


def build_proto(data, cls_id, talents=(), items=(), branches=None, extra_mods=(), path=None, runes=None,
                skills=None, doctrine=None):
    """branches: {skill_id: (ветка "A"|"B", ступень 1|2)}; runes: {skill_id: [rune_id, ...]};
    items — список id надетых предметов; extra_mods — проценты уровня, мастерства, лагеря, реликвий
    (применяются последними, поэтому умножают уже итоговые значения).

    path — старый режим: подкласс заменяет навыки. skills — сюжетный режим: явный набор навыков из пула.
    doctrine — сюжетный режим: пассивная доктрина вместо подкласса (её replace не применяется)."""
    p = copy.deepcopy(data.classes[cls_id])
    p.setdefault("power", 1.0)
    mods = []
    if path:
        pd = data.paths[path]
        p["skills"] = class_skills(data, cls_id, path)
        p["passive"] = copy.deepcopy(pd["passive"])
        p["path"] = path
        mods += pd["mods"]
    elif skills is not None:
        p["skills"] = [sid for sid in skills if sid in data.skills]
    if doctrine:
        pd = data.paths[doctrine]
        p["passive"] = copy.deepcopy(pd["passive"])
        p["doctrine"] = doctrine
        mods += pd["mods"]
    p["skill_defs"] = {sid: copy.deepcopy(data.skills[sid]) for sid in p["skills"]}
    mods += [m for tid in talents for m in data.talents[tid]["mods"]]
    for iid in items:
        mods += data.items[iid]["mods"]
    mods += list(extra_mods)
    # сначала новые навыки, чтобы остальные модификаторы могли их задеть
    for m in mods:
        sid = m.get("new_skill")
        if sid and sid not in p["skills"]:
            p["skills"].append(sid)
            p["skill_defs"][sid] = copy.deepcopy(data.skills[sid])
    # ветки переделывают навык первыми: руны и «+X к урону» применятся уже к новой форме
    for sid, (branch, tier) in (branches or {}).items():
        if sid in p["skill_defs"]:
            sk = p["skill_defs"][sid]
            for t in branch_tiers(data, sid, branch, tier):
                for m in t["mods"]:
                    apply_skill_mod(sk, m)
            sk["branch"] = (branch, tier)
    for sid, ids in (runes or {}).items():
        if sid in p["skill_defs"]:
            sk = p["skill_defs"][sid]
            for rid in ids:
                apply_skill_mod(sk, data.runes[rid]["mod"])
            sk["runes"] = list(ids)
    for m in mods:
        _apply(p, m)
    for sk in p["skill_defs"].values():
        radii = [e.get("radius", 0) for e in sk["effects"] if e.get("at") != "caster"]
        if "radius" in sk or any(radii):
            sk["radius"] = max(radii or [0])
    p["hp"] = int(round(p["hp"]))
    p["attack"]["damage"] = int(round(p["attack"]["damage"]))
    p["talents"] = list(talents)
    p["items"] = list(items)
    return p


def rune_fits(data, sk, rid):
    """Подходит ли руна к навыку (в его текущей форме)."""
    req = data.runes[rid]["req"]
    if req.get("has_amount") and not any(e["type"] in AMOUNT_EFFECTS and "amount" in e for e in sk["effects"]):
        return False
    if req.get("ap_min") and sk["ap"] < req["ap_min"]:
        return False
    if req.get("cast_or_cooldown") and not (sk["cast"] or sk["cooldown"]):
        return False
    if req.get("range_min") and sk["range"] < req["range_min"]:
        return False
    if req.get("radius_min") and sk.get("radius", 0) < req["radius_min"]:
        return False
    return True


def _num(target, key, m):
    v = target.get(key, 0)
    if "add" in m:
        v += m["add"]
    if "mult" in m:
        v *= m["mult"]
    if "set" in m:
        v = m["set"]
    if key in MIN_VALUES:
        v = max(MIN_VALUES[key], v)
    target[key] = round(v, 3)


def apply_skill_mod(sk, m):
    """Модификатор одного навыка: set / effects / add / cast_mult / effect / add_effect / remove_effect."""
    for key, val in m.get("set", {}).items():
        sk[key] = copy.deepcopy(val)
    if "effects" in m:
        sk["effects"] = copy.deepcopy(m["effects"])
    for key, delta in m.get("add", {}).items():
        sk[key] = max(MIN_VALUES.get(key, 0), round(sk.get(key, 0) + delta, 3))
    if "cast_mult" in m:
        sk["cast"] = round(sk["cast"] * m["cast_mult"], 2)
    if "cooldown_mult" in m:
        sk["cooldown"] = round(sk["cooldown"] * m["cooldown_mult"], 2)
    if "amount_mult" in m:
        for eff in sk["effects"]:
            if eff["type"] in AMOUNT_EFFECTS and "amount" in eff:
                eff["amount"] = int(round(eff["amount"] * m["amount_mult"]))
    if "radius_add" in m:
        for eff in sk["effects"]:
            if eff.get("radius", 0) > 0 and eff.get("at") != "caster":
                eff["radius"] += m["radius_add"]
    if "effect" in m:
        em = m["effect"]
        for eff in sk["effects"]:
            if eff["type"] == em["type"]:
                for key, delta in em.get("add", {}).items():
                    eff[key] = eff.get(key, 0) + delta
                for key, val in em.get("set", {}).items():
                    eff[key] = copy.deepcopy(val)
    if "add_effect" in m:
        sk["effects"].append(copy.deepcopy(m["add_effect"]))
    if "remove_effect" in m:
        sk["effects"] = [e for e in sk["effects"] if e["type"] != m["remove_effect"]]


def _apply(p, m):
    if "stat" in m:
        key = m["stat"]
        if key in ATTACK_STATS:
            _num(p["attack"], ATTACK_STATS[key], m)
        else:
            _num(p, key, m)
    elif "passive" in m:
        # модификатор пассивки действует, только если пассивка того вида (путь мог её сменить)
        if p.get("passive") and m.get("kind", p["passive"]["kind"]) == p["passive"]["kind"]:
            _num(p["passive"], m["passive"], m)
    elif "skill" in m:
        targets = p["skill_defs"].values() if m["skill"] == "*" else (
            [p["skill_defs"][m["skill"]]] if m["skill"] in p["skill_defs"] else [])
        for sk in targets:
            apply_skill_mod(sk, m)
    elif "attack_tag" in m:
        p["attack"]["tag"] = m["attack_tag"]
    elif "convert_tag" in m:
        src, dst = m["convert_tag"]
        if p["attack"].get("tag") == src:
            p["attack"]["tag"] = dst
        for sk in p["skill_defs"].values():
            for eff in sk["effects"]:
                if eff.get("tag") == src:
                    eff["tag"] = dst
    elif "resist" in m:
        p.setdefault("resist", {})[m["resist"]] = m["mult"]
