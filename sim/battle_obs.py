"""Сборщик состояния боя для нейросетей: из боя — набор токенов переменной длины для каждого юнита-наблюдателя.

Наблюдение юнита u (observe):
  units  [n, UF]  все бойцы на поле (до MAX_U, ближние первыми; u — первый): кто это относительно u, где, куда идёт,
                  здоровье и щит, броня и урон, все баффы и дебаффы (величина и остаток), стихийные статусы со
                  временем, метки и стаки, каст (что, сколько осталось, на кого/куда), приказ (кого бьёт), контроль
                  (оглушён, сон, стазис, насмешка), опасная ли клетка, как быстро теряет здоровье;
  kinds  [n]      номер вида юнита (класс героя или вид врага) — сеть учит «характер» каждого вида;
  skills [s, SF]  навыки u: готовность, цена, перезарядка, дальность, радиус, тип цели, набор эффектов (группы и
                  каждый тип), сумма урона/лечения/щита, длительность контроля;
  sids   [s]      номер навыка — для своего вектора навыка;
  map    [MC,11,11] карта вокруг u: проходимость, опасные клетки (урон местности, ловушки, чужие и свои),
                  вода, лава, лёд, пропасть, укрытия, свои и чужие (с их здоровьем), трупы, зоны, места, куда
                  летят чужие и свои касты, и куда уже летят отложенные снаряды;
  glob   [GF]     общее: время, силы сторон, прошлое действие u.

Действие — два шага: тип (ждать / атака / шаг / навык k) и цель: юнит из units (указатель), клетка карты 11×11
или без цели (навык на себя). Маски закрывают невозможное: tmask [T], umask [T, n], cmask [T, 121].

Признаки описаны по именам (SCHEMA): сеть хранит имена, с которыми обучалась, и при новом составе признаков веса
переносятся по именам (новые начинают с нуля) — вход можно расширять, не теряя обученного.
Признаки, не зависящие от наблюдателя, считаются один раз за тик боя (View) и общие для всех наблюдателей.
"""
import math
from collections import deque

import numpy as np

from .grid import cheb

MAX_U = 20
MAX_S = 8
R = 5
SIDE = 2 * R + 1
NCELL = SIDE * SIDE
T_HOLD, T_ATK, T_MOVE, T_SKILL = 0, 1, 2, 3
N_TYPES = T_SKILL + MAX_S
TGT_NONE, TGT_UNIT, TGT_CELL = 0, 1, 2

ROLES = ("melee", "ranged", "caster", "support")
MULT_STATS = {"atk_mult", "atk_speed", "dmg_taken", "heal_taken", "ap_rate", "slow"}
BUFF_STATS = ("atk_mult", "armor", "atk_speed", "regen", "slow", "dmg_taken", "exposed", "silence", "atk_tag", "thorns",
              "ap_rate", "undying", "zoc_free", "zoc_range", "collide_stun", "heal_taken", "trance", "all_arrows",
              "billiard", "stable")
EFFECT_GROUPS = {
    "damage": {"damage", "line", "chain", "detonate", "detonate_charges", "shatter", "collapse", "spread_fire",
               "extra_attack", "rush", "toss", "fuse"},
    "heal": {"heal", "revive"},
    "shield": {"shield", "guard"},
    "buff": {"buff", "focus", "form", "refresh", "stealth"},
    "control": {"stun", "knockback", "push", "pull", "sleep", "charm", "stasis", "taunt", "tether", "tether_all",
                "levitate", "gather"},
    "mobility": {"leap_to", "teleport", "swap", "rush", "regroup"},
    "summon": {"summon", "corpse", "place_object", "totem_pulse", "totem_move", "revive"},
    "area": {"hazard", "zone", "terrain", "terrain_wave", "terrain_cast", "cell_tag", "wall", "trap", "delay",
             "watch", "spread_fire"},
    "status": {"status", "mark"},
    "cleanse": {"cleanse"},
    "music": {"note", "song"},
}
TGT_KINDS = ("enemy", "ally", "self", "cell")
CELL_NEEDS = ("needs_corpse", "needs_totem", "needs_mark", "needs_shadow", "needs_banner", "place", "powder")

_SCHEMA = {}


# ---------- схема признаков ----------

def schema(data):
    """Имена признаков и словари видов и навыков для этих данных игры (один раз на процесс)."""
    key = id(data)
    if key in _SCHEMA:
        return _SCHEMA[key]
    tags = sorted(getattr(data, "tags", {}) or {"fire": 1, "water": 1, "ice": 1, "storm": 1, "poison": 1})
    eff_types = set()
    skill_ids = set(data.skills)
    for sk in data.skills.values():
        eff_types |= {e.get("type") for e in sk.get("effects", [])}
    kinds = set(data.classes) | set(data.enemies) | set(getattr(data, "summons", {}) or {})
    for proto in list(data.classes.values()) + list(data.enemies.values()):
        for sid, sk in (proto.get("skill_defs") or {}).items():
            skill_ids.add(sid)
            eff_types |= {e.get("type") for e in sk.get("effects", [])}
    eff_types.discard(None)
    unit_rel = ["me", "ally", "enemy", "dx", "dy", "dist", "targets_me", "targets_my_side", "targets_their_side",
                "my_target", "me_in_its_range", "it_in_my_range", "cast_on_me", "cast_on_my_side", "cast_near_me",
                "taunted_by_me", "goal_toward_me"]
    unit_abs = ["summon", "boss", "elite", "static", "flying", "charmed", "object",
                "x", "y", "step_dx", "step_dy", "moving", "goal_dx", "goal_dy", "has_goal",
                "hp_frac", "hp_log", "max_hp_log", "shield", "armor", "atk_log", "atk_range", "atk_cd", "move_time",
                "power", "lifesteal", "ap_frac", "ap_max", "pp_frac",
                "casting", "cast_left", "cast_progress", "cast_radius",
                "attacking", "skill_order", "moving_order",
                "stun", "asleep", "taunted", "stasis", "levitate", "airborne", "hidden", "tethered", "guarded",
                "on_hazard", "on_danger", "danger_adjacent", "hp_loss_5s", "hp_gain_5s", "marks", "mark_stacks",
                "skills_ready", "level"]
    unit_abs += ["role:" + r for r in ROLES] + ["status:" + t for t in tags] + ["atk_tag:" + t for t in tags]
    unit_abs += ["resist:" + t for t in tags]
    unit_abs += [f"buff:{s}" for s in BUFF_STATS] + [f"buff_t:{s}" for s in BUFF_STATS] + ["buff:other"]
    skill_f = ["present", "ready", "usable", "ap_cost", "can_afford", "cd_left", "cd_total", "range", "radius",
               "cast_time", "ult", "hp_cost", "uses", "free_cell", "min_targets", "n_targets",
               "dmg_amount", "heal_amount", "shield_amount", "control_time", "buff_time", "n_effects"]
    skill_f += ["tgt:" + k for k in TGT_KINDS] + ["grp:" + g for g in EFFECT_GROUPS]
    skill_f += ["eff:" + e for e in sorted(eff_types)] + ["tag:" + t for t in tags]
    map_c = ["in_bounds", "passable", "free", "hazard_foe", "hazard_own", "terrain_dps", "hazard_dps", "danger",
             "water", "lava", "ice", "chasm", "cover",
             "ally", "enemy", "me", "ally_hp", "enemy_hp", "corpse", "zone_foe", "zone_own", "cast_foe", "cast_own",
             "delay_foe", "delay_own", "coord_x", "coord_y", "my_range"]
    glob = ["time", "n_allies", "n_foes", "ally_hp", "foe_hp", "ally_hp_frac", "foe_hp_frac", "foes_adjacent",
            "allies_adjacent", "ap_frac", "hp_frac"] + [f"last:{k}" for k in range(N_TYPES)]
    s = {"unit": unit_rel + unit_abs, "unit_abs": unit_abs, "unit_rel": unit_rel, "skill": skill_f, "map": map_c,
         "glob": glob, "kinds": ["?"] + sorted(kinds), "skills": ["?"] + sorted(skill_ids), "tags": tags}
    s["kind_ix"] = {k: i for i, k in enumerate(s["kinds"])}
    s["skill_ix"] = {k: i for i, k in enumerate(s["skills"])}
    s["dims"] = {"unit": len(s["unit"]), "skill": len(skill_f), "map": len(map_c), "glob": len(glob),
                 "kinds": len(s["kinds"]), "skills": len(s["skills"])}
    _SCHEMA[key] = s
    return s


def names(sc):
    """Только имена (для сохранения вместе с сетью)."""
    return {k: sc[k] for k in ("unit", "skill", "map", "glob", "kinds", "skills")}


# ---------- признаки навыка (по описанию, не зависят от боя) ----------

_SKILL_STATIC = {}


def _skill_static(sc, sid, sk):
    key = (id(sc), sid, id(sk))
    if key in _SKILL_STATIC:
        return _SKILL_STATIC[key]
    ix = {n: i for i, n in enumerate(sc["skill"])}
    f = np.zeros(len(sc["skill"]), np.float32)
    effs = list(_walk(sk.get("effects", [])))
    f[ix["present"]] = 1
    f[ix["ap_cost"]] = sk.get("ap", 0) / 10
    f[ix["cd_total"]] = min(3.0, sk.get("cooldown", 0) / 20)
    f[ix["range"]] = sk.get("range", 0) / 6
    f[ix["radius"]] = sk.get("radius", 0) / 3
    f[ix["cast_time"]] = min(3.0, sk.get("cast", 0) / 2)
    f[ix["ult"]] = 1.0 if sk.get("ult") else 0.0
    f[ix["hp_cost"]] = sk.get("hp_cost", 0) / 100
    f[ix["free_cell"]] = 1.0 if sk.get("free_cell") else 0.0
    f[ix["min_targets"]] = sk.get("min_targets", 0) / 4
    f[ix["n_effects"]] = len(effs) / 5
    if sk.get("target") in TGT_KINDS:
        f[ix["tgt:" + sk["target"]]] = 1
    for e in effs:
        t = e.get("type")
        if "eff:" + str(t) in ix:
            f[ix["eff:" + t]] += 1
        for g, members in EFFECT_GROUPS.items():
            if t in members:
                f[ix["grp:" + g]] = 1
        amt = e.get("amount", 0) if isinstance(e.get("amount", 0), (int, float)) else 0
        if t in EFFECT_GROUPS["damage"]:
            f[ix["dmg_amount"]] += amt / 100
        elif t == "heal":
            f[ix["heal_amount"]] += amt / 100
        elif t == "shield":
            f[ix["shield_amount"]] += amt / 100
        dur = e.get("duration", 0) if isinstance(e.get("duration", 0), (int, float)) else 0
        if t in EFFECT_GROUPS["control"]:
            f[ix["control_time"]] += dur / 5
        elif t in ("buff", "status", "mark", "zone", "hazard"):
            f[ix["buff_time"]] += dur / 10
        if e.get("tag") and "tag:" + str(e["tag"]) in ix:
            f[ix["tag:" + e["tag"]]] = 1
    np.clip(f, -5, 5, out=f)
    _SKILL_STATIC[key] = f
    return f


def _walk(effects):
    for e in effects:
        if isinstance(e, dict):
            yield e
            for k in ("effects", "do"):
                sub = e.get(k)
                if isinstance(sub, list):
                    yield from _walk(sub)


# ---------- кадр боя ----------

class View:
    """Признаки, общие для всех наблюдателей в этот тик: юниты (без отношения к наблюдателю) и слои карты."""

    def __init__(self, c):
        self.c = c
        self.sc = sc = schema(c.data)
        self.t = c.time
        units = [u for u in c.units if u.alive and (not u.obj or u.obj.get("source"))]
        self.units = units
        self.index = {u: i for i, u in enumerate(units)}
        ab = sc["unit_abs"]
        self.ax = {n: i for i, n in enumerate(ab)}
        A = np.zeros((len(units), len(ab)), np.float32)
        for i, u in enumerate(units):
            self._abs(A[i], u)
        self.A = A
        self.cells = np.array([u.cell for u in units], np.int32).reshape(-1, 2)
        self.teams = [u.team for u in units]
        self.kinds = np.array([sc["kind_ix"].get(u.proto_id, 0) for u in units], np.int64)
        self.occ = np.zeros((c.grid.h + 2 * R, c.grid.w + 2 * R), bool)   # занятые клетки (с полями R)
        for x, y in self.cells:
            if 0 <= x < c.grid.w and 0 <= y < c.grid.h:
                self.occ[y + R, x + R] = True
        self._map_static()

    def _abs(self, f, u):
        ix, c, sc = self.ax, self.c, self.sc
        w, h = c.grid.w, c.grid.h
        f[ix["summon"]] = 1.0 if u.summon else 0.0
        f[ix["boss"]] = 1.0 if u.boss else 0.0
        f[ix["elite"]] = 1.0 if u.elite else 0.0
        f[ix["static"]] = 1.0 if u.static else 0.0
        f[ix["flying"]] = 1.0 if u.flying else 0.0
        f[ix["charmed"]] = 1.0 if u.charm_time > 0 else 0.0
        f[ix["object"]] = 1.0 if u.obj else 0.0
        f[ix["x"]] = u.cell[0] / w
        f[ix["y"]] = u.cell[1] / h
        if u.prev_cell != u.cell:
            f[ix["step_dx"]] = u.cell[0] - u.prev_cell[0]
            f[ix["step_dy"]] = u.cell[1] - u.prev_cell[1]
        f[ix["moving"]] = 1.0 if u.move_t < 1.0 else 0.0
        o = u.order or {}
        goal = o.get("cell") if o.get("type") == "move" else (o.get("cells") or [None])[-1] if o.get("type") == "path" \
            else None
        if o.get("type") in ("attack", "skill"):
            tg = o.get("target")
            goal = tg.cell if hasattr(tg, "cell") else tuple(tg) if tg is not None and not isinstance(tg, str) else None
        if goal is not None:
            f[ix["goal_dx"]] = (goal[0] - u.cell[0]) / R
            f[ix["goal_dy"]] = (goal[1] - u.cell[1]) / R
            f[ix["has_goal"]] = 1
        f[ix["hp_frac"]] = u.hp / max(1, u.max_hp)
        f[ix["hp_log"]] = math.log1p(max(0, u.hp)) / 7
        f[ix["max_hp_log"]] = math.log1p(u.max_hp) / 7
        f[ix["shield"]] = min(2.0, u.shield / max(1, u.max_hp))
        f[ix["armor"]] = u.total_armor() / 20
        f[ix["atk_log"]] = math.log1p(max(0, u.atk_damage)) / 5
        f[ix["atk_range"]] = u.atk_range / 6
        f[ix["atk_cd"]] = min(3.0, u.atk_cd / 2)
        f[ix["move_time"]] = min(3.0, u.move_time)
        f[ix["power"]] = min(3.0, u.power)
        f[ix["lifesteal"]] = u.lifesteal
        f[ix["ap_frac"]] = u.ap / max(1, u.ap_max) if u.ap_max else 0.0
        f[ix["ap_max"]] = u.ap_max / 10
        f[ix["pp_frac"]] = (u.pp / u.pp_max) if u.pp_max else 0.0
        if u.cast:
            f[ix["casting"]] = 1
            f[ix["cast_left"]] = min(3.0, u.cast["left"])
            f[ix["cast_progress"]] = 1 - u.cast["left"] / max(1e-3, u.cast["total"])
            sk = u.skill_defs.get(u.cast["skill"], {})
            f[ix["cast_radius"]] = sk.get("radius", 0) / 3
        f[ix["attacking"]] = 1.0 if o.get("type") == "attack" else 0.0
        f[ix["skill_order"]] = 1.0 if o.get("type") == "skill" else 0.0
        f[ix["moving_order"]] = 1.0 if o.get("type") in ("move", "path") else 0.0
        f[ix["stun"]] = min(3.0, u.stun)
        f[ix["asleep"]] = 1.0 if u.asleep else 0.0
        f[ix["taunted"]] = 1.0 if u.taunted_by is not None else 0.0
        f[ix["stasis"]] = min(3.0, u.stasis)
        f[ix["levitate"]] = min(3.0, u.levitate)
        f[ix["airborne"]] = 1.0 if u.airborne > 0 else 0.0
        f[ix["hidden"]] = 1.0 if u.hidden or "stealth" in u.buffs else 0.0
        f[ix["tethered"]] = 1.0 if u.tethered_by is not None else 0.0
        f[ix["guarded"]] = 1.0 if u.guarded_by is not None else 0.0
        cell = self.c.grid.get(u.cell)
        f[ix["on_hazard"]] = 1.0 if cell is not None and cell.hazard and cell.hazard_team != u.team else 0.0
        f[ix["on_danger"]] = 1.0 if u.cell in self.c.grid.cells and self.c._danger(u, u.cell) > 0 else 0.0
        near = 0
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                p = (u.cell[0] + dx, u.cell[1] + dy)
                if p in self.c.grid.cells and self.c._danger(u, p) > 0:
                    near += 1
        f[ix["danger_adjacent"]] = near / 8.0
        if u.history:
            old = u.history[0][2]
            f[ix["hp_loss_5s"]] = max(0, old - u.hp) / max(1, u.max_hp)
            f[ix["hp_gain_5s"]] = max(0, u.hp - old) / max(1, u.max_hp)
        f[ix["marks"]] = len(u.marks) / 3
        f[ix["mark_stacks"]] = sum(m.get("n", 1) for m in u.marks.values()) / 5
        f[ix["skills_ready"]] = sum(1 for s in u.skills if s in u.skill_defs and u.skill_ready(s, u.skill_defs[s])) / 4
        f[ix["level"]] = (u.level or 0) / 20
        if "role:" + str(u.role) in ix:
            f[ix["role:" + u.role]] = 1
        sd = self.c.cfg.get("status_duration", 4.0)
        for t, left in u.statuses.items():
            if "status:" + t in ix:
                f[ix["status:" + t]] = min(3.0, left / sd)
        if u.atk_tag and "atk_tag:" + str(u.atk_tag) in ix:
            f[ix["atk_tag:" + u.atk_tag]] = 1
        for t, v in (u.resist or {}).items():
            if "resist:" + t in ix and isinstance(v, (int, float)):
                f[ix["resist:" + t]] = max(-2.0, min(2.0, v))
        for stat, b in u.buffs.items():
            val, left = (b[0], b[1]) if isinstance(b, (list, tuple)) and len(b) > 1 else (b, 0)
            if not isinstance(val, (int, float)):
                val = 1.0
            v = val - 1 if stat in MULT_STATS else (val / 10 if abs(val) > 3 else val)
            if "buff:" + stat in ix:
                f[ix["buff:" + stat]] = max(-3.0, min(3.0, v))
                f[ix["buff_t:" + stat]] = min(3.0, (left or 0) / 10)
            else:
                f[ix["buff:other"]] += 1

    def _map_static(self):
        """Слои всего поля [MC, H, W]; свои/чужие — с точки зрения команды игрока (для врагов меняются местами)."""
        c, sc = self.c, self.sc
        w, h = c.grid.w, c.grid.h
        mi = {n: i for i, n in enumerate(sc["map"])}
        self.mi = mi
        M = np.zeros((len(sc["map"]), h + 2 * R, w + 2 * R), np.float32)   # поле с полями по R для вырезки
        self.team_layers = {}
        occupied = {v.cell for v in c.units if v.alive}
        for (x, y), cell in c.grid.cells.items():
            X, Y = x + R, y + R
            M[mi["in_bounds"], Y, X] = 1
            M[mi["passable"], Y, X] = 1.0 if cell.passable else 0.0
            M[mi["free"], Y, X] = 1.0 if cell.passable and (x, y) not in occupied else 0.0
            t = cell.terrain
            if t == "water":
                M[mi["water"], Y, X] = 1
            elif t == "lava":
                M[mi["lava"], Y, X] = 1
            elif t in ("ice", "ice_floor"):
                M[mi["ice"], Y, X] = 1
            elif t == "chasm":
                M[mi["chasm"], Y, X] = 1
            tdps = c.cfg.get("terrain", {}).get(t, {}).get("dps", 0) or 0
            if tdps:
                M[mi["terrain_dps"], Y, X] = min(1.0, tdps / 10.0)
            if cell.hazard:
                hz = c.cfg.get("hazards", {}).get(cell.hazard, {})
                hdps = hz.get("dps", 0) or 0
                if hz.get("trigger"):
                    hdps = max(hdps, 10)
                M[mi["hazard_dps"], Y, X] = min(1.0, hdps / 10.0)
            if cell.cover:
                M[mi["cover"], Y, X] = 1
        M[mi["danger"]] = np.maximum(M[mi["terrain_dps"]], M[mi["hazard_dps"]])
        for b in c.corpses:
            x, y = b["cell"]
            if 0 <= x < w and 0 <= y < h:
                M[mi["corpse"], y + R, x + R] = 1
        self.M = M
        # слои, зависящие от команды: опасности, юниты, зоны, касты — по командам
        self.side = {}
        teams = set(self.teams) | {getattr(u, "team", None) for u in c.units}
        for team in teams:
            S = np.zeros((len(sc["map"]), h + 2 * R, w + 2 * R), np.float32)
            for (x, y), cell in c.grid.cells.items():
                if cell.hazard:
                    S[mi["hazard_own" if cell.hazard_team == team else "hazard_foe"], y + R, x + R] = 1
            for u, (x, y) in zip(self.units, self.cells):
                if not (0 <= x < w and 0 <= y < h):
                    continue
                own = u.team == team
                S[mi["ally" if own else "enemy"], y + R, x + R] = 1
                S[mi["ally_hp" if own else "enemy_hp"], y + R, x + R] = u.hp / max(1, u.max_hp)
                if u.cast:
                    tg = u.cast.get("target")
                    p = tg.cell if hasattr(tg, "cell") else tuple(tg) if tg is not None else None
                    if p is not None:
                        rad = u.skill_defs.get(u.cast["skill"], {}).get("radius", 0)
                        self._disc(S[mi["cast_own" if own else "cast_foe"]], p, rad)
            for z in c.zones:
                cst = z.get("caster")
                own = cst is not None and cst.team == team
                self._disc(S[mi["zone_own" if own else "zone_foe"]], z["center"], z.get("radius", 1))
            for d in c.delayed:                    # снаряды/метеоры уже в полёте: куда они прилетят
                cst, center = d.get("caster"), d.get("center")
                if cst is None or center is None:
                    continue
                own = cst.team == team
                rad = max([e.get("radius", 0) for e in d.get("effects", [])] + [0])
                self._disc(S[mi["delay_own" if own else "delay_foe"]], center, rad)
            self.side[team] = S

    @staticmethod
    def _disc(layer, p, rad):
        x, y = int(p[0]) + R, int(p[1]) + R
        r = int(rad)
        layer[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1] = 1

    def _reachable(self, u):
        """Клетки, куда u реально дойдёт, не проходя сквозь союзников и врагов (все живые юниты блокируют)."""
        c = self.c
        if u.static or u.cell not in c.grid.cells:
            return set()
        blocked = {v.cell for v in c.units if v.alive and v is not u}
        seen = {u.cell}
        q = deque([u.cell])
        while q:
            p = q.popleft()
            for n, _ in c.grid.neighbors(p, u.flying):
                if n in blocked or n in seen:
                    continue
                if n[0] != p[0] and n[1] != p[1] and \
                        ((n[0], p[1]) in blocked or (p[0], n[1]) in blocked):
                    continue                          # не срезать угол между двумя юнитами
                seen.add(n)
                q.append(n)
        return seen

    # ---------- наблюдение одного юнита ----------

    def observe(self, u, last_type=0, caster=None):
        """→ (obs: dict массивов, cands: варианты для перевода действия в приказ)."""
        c, sc = self.c, self.sc
        me = self.index.get(u)
        order = sorted(range(len(self.units)), key=lambda i: (i != me, cheb(tuple(self.cells[i]), u.cell)))[:MAX_U]
        units = [self.units[i] for i in order]
        n = len(units)
        rel = np.zeros((n, len(sc["unit_rel"])), np.float32)
        ux, uy = u.cell
        uo = u.order or {}
        my_tgt = uo.get("target") if uo.get("type") == "attack" else None
        for k, i in enumerate(order):
            v = self.units[i]
            x, y = self.cells[i]
            d = max(abs(x - ux), abs(y - uy))
            mine = v.team == u.team
            r = rel[k]
            r[0] = 1.0 if v is u else 0.0
            r[1] = 1.0 if mine and v is not u else 0.0
            r[2] = 1.0 if u.is_enemy(v) else 0.0
            r[3] = (x - ux) / R
            r[4] = (y - uy) / R
            r[5] = d / 10
            vo = v.order or {}
            t = vo.get("target") if vo.get("type") in ("attack", "skill") else None
            if t is u:
                r[6] = 1
            elif hasattr(t, "team"):
                r[7 if t.team == u.team else 8] = 1
            r[9] = 1.0 if v is my_tgt else 0.0
            r[10] = 1.0 if d <= v.atk_range else 0.0
            r[11] = 1.0 if d <= u.atk_range else 0.0
            if v.cast:
                ct = v.cast.get("target")
                if ct is u:
                    r[12] = 1
                elif hasattr(ct, "team") and ct.team == u.team:
                    r[13] = 1
                p = ct.cell if hasattr(ct, "cell") else tuple(ct) if ct is not None else None
                if p is not None and cheb(p, u.cell) <= v.skill_defs.get(v.cast["skill"], {}).get("radius", 0) + 1:
                    r[14] = 1
            r[15] = 1.0 if v.taunted_by is u else 0.0
            if vo.get("type") in ("move", "path") or t is not None:
                gdx = self.A[i, self.ax["goal_dx"]] * R
                gdy = self.A[i, self.ax["goal_dy"]] * R
                r[16] = 1.0 if (gdx * (ux - x) + gdy * (uy - y)) > 0 else 0.0
        U = np.concatenate([rel, self.A[order]], 1) if n else np.zeros((0, len(sc["unit"])), np.float32)
        kinds = self.kinds[order] if n else np.zeros(0, np.int64)
        # карта вокруг
        S = self.side.get(u.team)
        if S is None:
            S = np.zeros_like(self.M)
        x0 = max(0, min(c.grid.w - 1, ux))           # в поле с полями R: окно [y, y+2R]; юнит за краем — у края
        y0 = max(0, min(c.grid.h - 1, uy))
        Mp = self.M[:, y0:y0 + SIDE, x0:x0 + SIDE] + S[:, y0:y0 + SIDE, x0:x0 + SIDE]
        Mp = np.ascontiguousarray(Mp)
        mi = self.mi
        Mp[mi["me"], R, R] = 1
        Mp[mi["coord_x"]] = (np.arange(SIDE)[None, :] - R) / R
        Mp[mi["coord_y"]] = (np.arange(SIDE)[:, None] - R) / R
        dd = np.maximum(np.abs(np.arange(SIDE)[None, :] - R), np.abs(np.arange(SIDE)[:, None] - R))
        Mp[mi["my_range"]] = (dd <= u.atk_range).astype(np.float32)
        # навыки
        skills = [s for s in u.skills if s in u.skill_defs][:MAX_S]
        SK = np.zeros((len(skills), len(sc["skill"])), np.float32)
        sids = np.array([sc["skill_ix"].get(s, 0) for s in skills], np.int64)
        si = {nm: i for i, nm in enumerate(sc["skill"])}
        general = []
        for k, sid in enumerate(skills):
            sk = u.skill_defs[sid]
            SK[k] = _skill_static(sc, sid, sk)
            cd = u.cooldowns.get(sid, 0)
            ok = c.check_skill(u, sid, u if sk["target"] in ("self", "ally") else u.cell)
            usable = ok[0] or ok[1] in ("Нужна цель-юнит", "Не та цель", "Клетка занята")
            general.append(usable)
            SK[k, si["ready"]] = 1.0 if u.skill_ready(sid, sk) else 0.0
            SK[k, si["usable"]] = 1.0 if usable else 0.0
            SK[k, si["can_afford"]] = 1.0 if u.ap >= sk.get("ap", 0) else 0.0
            SK[k, si["cd_left"]] = min(3.0, cd / 20)
            SK[k, si["uses"]] = min(3.0, u.uses.get(sid, 0) / 20)
        # маски действий
        tmask = np.zeros(N_TYPES, bool)
        umask = np.zeros((N_TYPES, MAX_U), bool)
        cmask = np.zeros((N_TYPES, NCELL), bool)
        ttype = np.zeros(N_TYPES, np.int64)
        tmask[T_HOLD] = True
        ttype[T_ATK] = TGT_UNIT
        for k, v in enumerate(units):
            if u.is_enemy(v) and (not v.obj or v.obj.get("source")):
                umask[T_ATK, k] = True
        tmask[T_ATK] = umask[T_ATK].any()
        cells = [(x0 + dx - R, y0 + dy - R) for dy in range(SIDE) for dx in range(SIDE)]
        inb = Mp[mi["in_bounds"]].reshape(-1) > 0
        pas = Mp[mi["passable"]].reshape(-1) > 0
        occw = self.occ[y0:y0 + SIDE, x0:x0 + SIDE].reshape(-1)     # клетки окна, где кто-то стоит (и я)
        ttype[T_MOVE] = TGT_CELL
        if not u.static:
            can = inb & (pas | bool(u.flying)) & ~occw
            reach = self._reachable(u)               # не только цель свободна: нужен путь в обход юнитов
            can &= np.fromiter((p in reach for p in cells), bool, count=len(cells))
            cmask[T_MOVE] = can
            tmask[T_MOVE] = can.any()
        for k, sid in enumerate(skills):
            if not general[k]:
                continue
            sk = u.skill_defs[sid]
            t = T_SKILL + k
            kind = sk["target"]
            if kind == "self":
                ttype[t] = TGT_NONE
                tmask[t] = c.check_skill(u, sid, u)[0]
            elif kind in ("enemy", "ally"):
                ttype[t] = TGT_UNIT
                for j, v in enumerate(units):
                    if (kind == "enemy") == u.is_enemy(v) and not v.obj and c.check_skill(u, sid, v)[0]:
                        umask[t, j] = True
                tmask[t] = umask[t].any()
            else:
                ttype[t] = TGT_CELL
                if any(sk.get(k2) for k2 in CELL_NEEDS):   # труп, тотем, метка… — проверка по каждой клетке
                    for j in np.flatnonzero(inb):
                        cmask[t, j] = c.check_skill(u, sid, cells[j])[0]
                elif sk.get("free_cell"):
                    cmask[t] = inb & pas & ~occw
                else:
                    cmask[t] = inb
                tmask[t] = cmask[t].any()
        g = np.zeros(len(sc["glob"]), np.float32)
        allies = [v for v in self.units if v.team == u.team and not v.obj]
        foes = [v for v in self.units if u.is_enemy(v) and not v.obj]
        g[0] = min(3.0, c.time / 90)
        g[1] = len(allies) / 8
        g[2] = len(foes) / 8
        ah = sum(v.hp for v in allies)
        fh = sum(v.hp for v in foes)
        g[3] = math.log1p(ah) / 8
        g[4] = math.log1p(fh) / 8
        g[5] = ah / max(1, sum(v.max_hp for v in allies))
        g[6] = fh / max(1, sum(v.max_hp for v in foes))
        g[7] = sum(1 for v in foes if cheb(v.cell, u.cell) <= 1) / 4
        g[8] = sum(1 for v in allies if v is not u and cheb(v.cell, u.cell) <= 1) / 4
        g[9] = u.ap / max(1, u.ap_max) if u.ap_max else 0.0
        g[10] = u.hp / max(1, u.max_hp)
        g[11 + int(last_type)] = 1
        obs = {"units": U, "kinds": kinds, "skills": SK, "sids": sids, "map": Mp, "glob": g,
               "tmask": tmask, "umask": umask, "cmask": cmask, "ttype": ttype}
        cands = {"units": units, "cells": cells, "skills": skills}
        return obs, cands


# ---------- действие ↔ приказ ----------

def decode(cands, ttype, a_type, a_tgt):
    """(тип, цель) → вариант: ("hold",) / ("attack", v) / ("move", клетка) / ("skill", sid, цель)."""
    if a_type == T_HOLD:
        return ("hold",)
    if a_type == T_ATK:
        return ("attack", cands["units"][a_tgt])
    if a_type == T_MOVE:
        return ("move", cands["cells"][a_tgt])
    sid = cands["skills"][a_type - T_SKILL]
    tt = ttype[a_type]
    if tt == TGT_NONE:
        return ("skill", sid, None)
    if tt == TGT_UNIT:
        return ("skill", sid, cands["units"][a_tgt])
    return ("skill", sid, cands["cells"][a_tgt])


def encode(u, order, obs, cands):
    """Приказ (игрока, автопилота) → (тип, цель), допустимые масками, или None (не переводится)."""
    tm, um, cm = obs["tmask"], obs["umask"], obs["cmask"]
    ux, uy = u.cell

    def cell_ix(p, t):
        """Клетка → номер в окне 11×11; вне окна — ближайшая допустимая клетка окна по направлению."""
        dx, dy = p[0] - ux, p[1] - uy
        if max(abs(dx), abs(dy)) > R:
            k = R / max(abs(dx), abs(dy))
            dx, dy = round(dx * k), round(dy * k)
        j = (dy + R) * SIDE + (dx + R)
        if cm[t, j]:
            return j
        ok = np.flatnonzero(cm[t])
        if not len(ok):
            return None
        cx, cy = ok % SIDE - R, ok // SIDE - R
        return int(ok[np.argmin(np.maximum(np.abs(cx - dx), np.abs(cy - dy)))])

    if not order:
        return (T_HOLD, 0)
    t = order.get("type")
    units = cands["units"]
    if t == "attack":
        v = order.get("target")
        if v in units and um[T_ATK, units.index(v)]:
            return (T_ATK, units.index(v))
        return None
    if t in ("move", "path"):
        goal = order.get("cell") or (order.get("cells") or [None])[-1]
        if goal is None or not tm[T_MOVE]:
            return None
        j = cell_ix(goal, T_MOVE)
        return (T_MOVE, j) if j is not None else None
    if t == "skill":
        sid = order.get("skill")
        if sid not in cands["skills"]:
            return None
        a = T_SKILL + cands["skills"].index(sid)
        if not tm[a]:
            return None
        tt = obs["ttype"][a]
        if tt == TGT_NONE:
            return (a, 0)
        tg = order.get("target")
        if tt == TGT_UNIT:
            if tg in units and um[a, units.index(tg)]:
                return (a, units.index(tg))
            return None
        p = tg.cell if hasattr(tg, "cell") else tuple(tg) if tg is not None else u.cell
        j = cell_ix(p, a)
        return (a, j) if j is not None else None
    return None


def describe(c, u, cand):
    """Вариант → короткий текст для панели «что думает сеть»."""
    k = cand[0]
    if k == "hold":
        return "ждать / продолжать"
    if k == "attack":
        return f"атака → {cand[1].name}"
    if k == "move":
        dx, dy = cand[1][0] - u.cell[0], cand[1][1] - u.cell[1]
        return f"шаг ({dx:+d}, {dy:+d})"
    name = u.skill_defs[cand[1]]["name"]
    t = cand[2]
    if t is None:
        return name
    if hasattr(t, "name"):
        return f"{name} → {t.name}"
    return f"{name} → клетка ({t[0] - u.cell[0]:+d}, {t[1] - u.cell[1]:+d})"
