"""Автокаст: навык применяется сам, когда выполнены условия игрока (до 2, через «И»).

Ручной приказ главнее: пока у юнита есть ручной приказ навыка или идёт каст, автокаст молчит.
Автокаст не подводит юнита к цели — только то, что уже в досягаемости.
"""
import copy

from . import conditions as C
from .grid import cheb

MAX_CONDS = 2
PCT = list(range(10, 100, 10))

# scope: "global" — про самого юнита/отряд; "target" — про выбранную цель (или врагов в зоне навыка)
CONDS = {
    "ap_at_least": {"label": "AP ≥ {v}", "values": list(range(1, 13)), "scope": "global"},
    "self_hp_below": {"label": "своё HP < {v}%", "values": PCT, "scope": "global"},
    "ally_hp_below": {"label": "союзник HP < {v}%", "values": PCT, "scope": "global"},
    "enemies_adjacent": {"label": "врагов рядом ≥ {v}", "values": [1, 2, 3, 4], "scope": "global"},
    "target_hp_below": {"label": "HP цели < {v}%", "values": PCT, "scope": "target"},
    "target_casting": {"label": "цель кастует", "values": None, "scope": "target"},
    "target_has_tag": {"label": "на цели: {v}", "values": ["fire", "water", "ice", "storm", "poison", "oil",
                                                          "control", "debuff"],
                       "scope": "target"},
    "enemies_in_area": {"label": "врагов в зоне ≥ {v}", "values": [1, 2, 3, 4, 5], "scope": "target"},
}


def flat_effects(sk):
    """Эффекты навыка вместе с вложенными в отложенный (Обет жреца — это лечение)."""
    out = []
    for e in sk["effects"]:
        out.append(e)
        if e["type"] == "delay":
            out += e["effects"]
    return out


def is_teleport(sk):
    return any(e["type"] == "teleport" for e in sk["effects"])


def hits_enemies(sk):
    return any(e["type"] in ("damage", "stun", "knockback", "taunt", "line", "chain", "sleep", "pull", "push", "rush",
                             "toss", "detonate", "watch", "gather", "swap", "levitate", "collapse", "terrain_cast",
                             "reagent", "focus")
               and e.get("affects", "enemies") == "enemies" for e in sk["effects"])


def summons(sk):
    return any(e["type"] == "summon" for e in sk["effects"])


def ally_danger_radius(sk, tags):
    """Радиус, в котором навык вредит своим (огненная лужа, горящая клетка); -1 — безопасен."""
    r = -1
    for e in sk["effects"]:
        if e["type"] == "hazard" or (e["type"] == "cell_tag" and tags.get(e["tag"], {}).get("dps")):
            r = max(r, e.get("radius", 0))
        if e["type"] == "spread_fire":
            r = max(r, e.get("radius", 2) + 1)
    return r


def cell_safe(combat, u, sk, target):
    """Авто-навык по клетке не начинается, если за время подхода под удар встал союзник."""
    if sk["target"] != "cell" or not isinstance(target, tuple):
        return True
    danger = ally_danger_radius(sk, combat.tags)
    return not any(cheb(a.cell, target) <= danger for a in combat.alive(u.team))


def allowed_conds(sk):
    kind = sk["target"]
    out = ["ap_at_least", "self_hp_below", "ally_hp_below", "enemies_adjacent"]
    if kind in ("enemy", "ally", "cell"):
        out.append("target_hp_below")
    if kind in ("enemy", "cell"):
        out.append("target_casting")
    if kind in ("enemy", "ally", "cell"):
        out.append("target_has_tag")
    if kind in ("cell", "self") or sk.get("radius", 0) > 0:
        out.append("enemies_in_area")
    return out


def sanitize(setting, sk):
    allowed = allowed_conds(sk)
    conds = []
    for c in setting.get("conds", []):
        spec = CONDS.get(c.get("type"))
        if c.get("type") in allowed and (spec["values"] is None or c.get("value") in spec["values"]):
            conds.append(dict(c))
    return {"on": bool(setting.get("on")), "conds": conds[:MAX_CONDS]}


def default_setting(sk):
    """Умолчание — автокаст выключен у всех навыков; условия из данных остаются готовой подсказкой."""
    st = copy.deepcopy(sk.get("auto", {"on": False, "conds": []}))
    st["on"] = False
    return sanitize(st, sk)


def settings_for(skill_defs, given=None):
    given = given or {}
    return {sid: sanitize(given[sid], sk) if sid in given else default_setting(sk) for sid, sk in skill_defs.items()}


TAG_NAMES = {"control": "контроль", "debuff": "ослабление"}


def cond_label(c, tags=None):
    spec = CONDS[c["type"]]
    v = c.get("value")
    if c["type"] == "target_has_tag" and tags:
        v = tags[v]["name"] if v in tags else TAG_NAMES.get(v, v)
    return spec["label"].format(v=v)


def setting_label(st, tags=None):
    if not st["on"]:
        return "авто выкл"
    if not st["conds"]:
        return "авто: всегда"
    return "авто: " + " и ".join(cond_label(c, tags) for c in st["conds"])


class AutoCaster:
    TICK = 0.25

    def __init__(self, combat, team, force=False):
        self.c = combat
        self.team = team
        self.force = force   # демо/тесты: все навыки включены, условия — по умолчанию

    def update(self, dt):
        for u in self.c.fighters(self.team):
            if u.cast or u.stun > 0 or u.moving or u.charmed:
                continue
            if u.order and u.order["type"] == "skill":
                continue  # ручной приказ главнее
            u.auto_timer -= dt
            if u.auto_timer > 0:
                continue
            u.auto_timer = self.TICK
            choice = self.choose(u)
            if choice:
                self.c.order_skill(u, choice[0], choice[1], auto=True)

    def choose(self, u):
        for sid in u.skills:
            sk = u.skill_defs[sid]
            st = dict(default_setting(sk), on=True) if self.force else u.autocast.get(sid)
            if not st or not st["on"] or not u.skill_ready(sid, sk):
                continue
            if any(e["type"] == "form" and e.get("form") == u.form for e in sk["effects"]):
                continue   # уже в этом облике — повтор вернул бы обратно
            conds = st["conds"]
            if not all(self._global_ok(u, c) for c in conds if CONDS[c["type"]]["scope"] == "global"):
                continue
            target = self._pick_target(u, sk, [c for c in conds if CONDS[c["type"]]["scope"] == "target"])
            if target is not None:
                return sid, target
        return None

    # ---------- условия ----------

    def _foes(self, u):
        return self.c.foes_of(u)

    def _global_ok(self, u, c):
        t, v = c["type"], c.get("value")
        if t == "ap_at_least":
            return u.ap >= v
        if t == "self_hp_below":
            return u.hp < u.max_hp * v / 100
        if t == "ally_hp_below":
            return any(a.hp < a.max_hp * v / 100 for a in self.c.alive(u.team))
        if t == "enemies_adjacent":
            return sum(1 for f in self._foes(u) if cheb(f.cell, u.cell) <= 1) >= v
        return True

    def _area_ok(self, group, conds, area_count):
        """Условия цели для навыков по области: «в зоне есть враг, который…»."""
        for c in conds:
            t, v = c["type"], c.get("value")
            if t == "enemies_in_area" and area_count < v:
                return False
            if t == "target_hp_below" and not any(f.hp < f.max_hp * v / 100 for f in group):
                return False
            if t == "target_casting" and not any(f.cast for f in group):
                return False
            if t == "target_has_tag" and not any(v in f.statuses for f in group):
                return False
        return True

    def _unit_ok(self, u, sk, target, conds):
        r = sk.get("radius", 0)
        for c in conds:
            t, v = c["type"], c.get("value")
            if t == "target_hp_below" and not target.hp < target.max_hp * v / 100:
                return False
            if t == "target_casting" and not target.cast:
                return False
            if t == "target_has_tag" and v not in C.unit_tags(self.c, target):
                return False
            if t == "enemies_in_area":
                n = sum(1 for f in self._foes(u) if cheb(f.cell, target.cell) <= r)
                if n < v:
                    return False
        return True

    # ---------- выбор цели ----------

    def _pick_target(self, u, sk, conds):
        kind, rng = sk["target"], sk["range"]
        foes = self._foes(u)
        if kind == "enemy":
            cand = [f for f in foes if cheb(u.cell, f.cell) <= rng and self._unit_ok(u, sk, f, conds)]
            if not cand:
                return None
            cur = u.order["target"] if u.order and u.order["type"] == "attack" else u.last_target
            return cur if cur in cand else min(cand, key=lambda f: (f.hp, cheb(u.cell, f.cell)))
        if kind == "ally":
            flat = flat_effects(sk)
            effects = {e["type"] for e in flat}
            stat_buffs = {e.get("stat") for e in flat if e["type"] == "buff"}
            leap = "leap_to" in effects
            cand = []
            for a in self.c.alive(u.team):
                if cheb(u.cell, a.cell) > rng or ((leap or "refresh" in effects) and a is u) or a.summon or a.obj:
                    continue
                cl_tags = [t for e in flat if e["type"] == "cleanse" for t in (e.get("tags") or C.DEFAULT_CLEANSE)]
                need_cleanse = bool(cl_tags and C.removable(self.c, a, cl_tags)) or \
                    bool("transfer_statuses" in effects and a.statuses)
                if effects & {"cleanse", "transfer_statuses"} and "heal" not in effects and not need_cleanse:
                    continue
                if (effects & {"heal"} or "regen" in stat_buffs) and a.hp >= a.max_hp and not need_cleanse:
                    continue
                if not effects & {"heal", "cleanse", "transfer_statuses"} and "regen" not in stat_buffs:
                    if not any(cheb(f.cell, a.cell) <= 3 for f in foes):   # щиты и баффы — только в гуще боя
                        continue
                if self._unit_ok(u, sk, a, conds):
                    cand.append(a)
            return min(cand, key=lambda a: a.hp / a.max_hp) if cand else None
        types = {e["type"] for e in sk["effects"]}
        if "detonate" in types:                 # Вспышка — только если есть что взрывать
            r = max(e.get("radius", 6) for e in sk["effects"] if e["type"] == "detonate")
            burning = any(self.c.grid.get(p).hazard == "fire" for p in self.c.grid.in_radius(u.cell, r)) or \
                any("fire" in f.statuses for f in foes if cheb(f.cell, u.cell) <= r)
            return u if burning and self._area_ok([f for f in foes if cheb(f.cell, u.cell) <= r], conds, 1) else None
        if "corpse" in types:                   # некромант: только туда, где есть труп
            return self._corpse_target(u, sk, foes)
        if "spread_fire" in types:              # раздуть — туда, где горит и рядом враги, но не свои
            r = next(e.get("radius", 2) for e in sk["effects"] if e["type"] == "spread_fire")
            allies = self.c.fighters(u.team)
            best, best_n = None, 0
            for p in self.c.grid.in_radius(u.cell, rng):
                if any(cheb(a.cell, p) <= r + 1 for a in allies):
                    continue
                fire = any(self.c.grid.get(q).hazard == "fire" for q in self.c.grid.in_radius(p, r)) or \
                    any("fire" in f.statuses and cheb(f.cell, p) <= r for f in foes)
                n = sum(1 for f in foes if cheb(f.cell, p) <= r + 1)
                if fire and n > best_n:
                    best, best_n = p, n
            return best
        if "watch" in types:                    # дозор — на клетку на пути ближайшего врага к лучнику
            if u.watch or not foes:
                return None
            f = min(foes, key=lambda f: cheb(f.cell, u.cell))
            if cheb(f.cell, u.cell) > rng + 2:
                return None
            cells = [p for p in self.c.grid.in_radius(f.cell, 2) if cheb(p, u.cell) <= rng and p != f.cell]
            if not cells:
                return None
            return min(cells, key=lambda p: (abs(cheb(p, u.cell) - cheb(f.cell, u.cell) + 2), cheb(p, f.cell)))
        if kind == "self":
            r = sk.get("radius", 0)
            area = [f for f in foes if cheb(f.cell, u.cell) <= r]
            if hits_enemies(sk):
                if not area:
                    return None
            elif not any(cheb(f.cell, u.cell) <= 4 for f in foes):
                return None
            return u if self._area_ok(area, conds, len(area)) else None
        # клетка
        if is_teleport(sk):
            return self._teleport_cell(u, sk, foes, conds)
        if summons(sk):
            return self._summon_cell(u, sk, foes, conds)
        if any(e["type"] == "revive" for e in sk["effects"]):
            dead = [a for a in self.c.heroes(u.team) if not a.alive and cheb(a.cell, u.cell) <= rng]
            return dead[0].cell if dead else None
        r = sk.get("radius", 0)
        danger = ally_danger_radius(sk, self.c.tags)
        allies = self.c.alive(u.team)
        best, best_n = None, 0
        for p in self.c.grid.in_radius(u.cell, rng):
            if any(cheb(a.cell, p) <= danger for a in allies):
                continue   # не поджигать клетки под своими
            if sk.get("free_cell") and not self.c.is_free(p):
                continue
            group = [f for f in foes if cheb(f.cell, p) <= r]
            if len(group) > best_n and self._area_ok(group, conds, len(group)):
                best, best_n = p, len(group)
        return best

    def _corpse_target(self, u, sk, foes):
        e = next(e for e in sk["effects"] if e["type"] == "corpse")
        if e["do"] == "devour":
            near = [b for b in self.c.corpses if cheb(b["cell"], u.cell) <= e.get("radius", 2)]
            return u if near and any(cheb(f.cell, u.cell) <= 4 for f in foes) else None
        cand = [b["cell"] for b in self.c.corpses if cheb(b["cell"], u.cell) <= sk["range"]]
        if not cand or not foes:
            return None
        if e["do"] in ("blast", "cloud"):
            r = e.get("radius", 1)
            best = max(cand, key=lambda p: sum(1 for f in foes if cheb(f.cell, p) <= r))
            return best if any(cheb(f.cell, best) <= r for f in foes) else None
        return min(cand, key=lambda p: min(cheb(p, f.cell) for f in foes))

    def _summon_cell(self, u, sk, foes, conds):
        """Тотем: свободная клетка в досягаемости — у врагов (боевой) или среди своих (лечащий)."""
        if not foes or not any(cheb(f.cell, u.cell) <= sk["range"] + 3 for f in foes):
            return None
        cells = [p for p in self.c.grid.in_radius(u.cell, sk["range"]) if self.c.is_free(p)]
        if not cells:
            return None
        if sk.get("place") == "allies":
            allies = self.c.heroes(u.team)
            return max(cells, key=lambda p: (sum(1 for a in allies if a.alive and cheb(a.cell, p) <= 2),
                                             -cheb(p, u.cell)))
        near = [f for f in foes if self._area_ok([f], conds, 1)]
        if not near:
            return None
        return min(cells, key=lambda p: (min(cheb(p, f.cell) for f in near), cheb(p, u.cell)))

    def _teleport_cell(self, u, sk, foes, conds):
        cells = [p for p in self.c.grid.in_radius(u.cell, sk["range"]) if p != u.cell and self.c.is_free(p)]
        if not cells or not foes:
            return None
        landing = [e for e in sk["effects"] if e.get("at") != "caster" and e["type"] in ("damage", "stun")]
        if landing:   # прыжок в гущу: туда, где рядом больше врагов
            r = max(e.get("radius", 0) for e in landing)
            best, best_n = None, 0
            for p in cells:
                group = [f for f in foes if cheb(f.cell, p) <= r]
                if len(group) > best_n and self._area_ok(group, conds, len(group)):
                    best, best_n = p, len(group)
            return best
        # прыжок назад: дальше от врагов, если стало безопаснее
        def safety(p):
            return min(cheb(p, f.cell) for f in foes)
        best = max(cells, key=safety)
        if safety(best) <= safety(u.cell):
            return None
        near = [f for f in foes if cheb(f.cell, u.cell) <= 1]
        return best if self._area_ok(near, conds, len(near)) else None
