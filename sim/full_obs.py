"""Полное наблюдение боя для новой сети (рядом со старой battle_obs, не заменяя её).

Отличия от battle_obs.View:
  * видны ВСЕ живые юниты, включая охраняемые объекты, источники подмоги и нейтральные объекты;
  * карта не вырезается вокруг юнита: это всё поле, дополненное до SIDE × SIDE;
  * в карте и общем векторе есть цель боя (hold / destroy / defend), клетки удержания, охрана и источники;
  * клетка описана по типам: рельеф (лава, вода, камень, лёд, пропасть, трава), опасность (огонь, масло, яд,
    капкан, мина и т.д.), таймер, владелец, укрытие, портал, временная смена рельефа;
  * в общем векторе — волны, фазы, зоны, отложенные снаряды, трупы, приливы, события поля (извержение, молния,
    лавина, ветер, меха, ковш расплава, песчаная буря), число объектов и т.п.;
  * маски шага/навыков строятся по полной карте, а не по окну 11 × 11.

Действие остаётся прежним: тип (ждать / атака / шаг / навык k) и цель (юнит / клетка / без цели).
Старые sim/battle_obs.py, sim/entity_net.py и сохранённые сети не меняются: full_obs передаёт в ту же сеть
другие размеры через arch (max_u, max_s, side, n_types). Сеть может быть новой, но её формулы — те же.
"""
import math

import numpy as np

from . import battle_obs as B
from .grid import PERMANENT, cheb
from .teams import ENEMY, NEUTRAL, PLAYER

MAX_U = 64                 # все живые юниты; в обычном бою их 6–12, запас на волны и призывы
MAX_S = 12                 # все навыки юнита (в игре обычно не больше 8)
SIDE = 24                  # полное поле: 14×8 тоже помещается; остальное — маска in_bounds
NCELL = SIDE * SIDE
T_HOLD, T_ATK, T_MOVE, T_SKILL = B.T_HOLD, B.T_ATK, B.T_MOVE, B.T_SKILL
N_TYPES = T_SKILL + MAX_S
TGT_NONE, TGT_UNIT, TGT_CELL = B.TGT_NONE, B.TGT_UNIT, B.TGT_CELL

# События поля: извержение, молния, лавина, прилив, ветер, меха, ковш расплава, песчаная буря.
# Это не «маски действий», а часть описания боя: где сейчас предупреждение и куда/когда ударит.
ARENA_KINDS = ("eruption", "lightning", "avalanche", "tide", "wind", "bellows", "ladle", "sandstorm")
ARENA_FIELDS = ("on", "timer", "pending", "dir_x", "dir_y", "damage", "burn", "push", "duration", "range")

# Архитектура новой сети. Те же формулы entity_net, но другие пределы и чуть больше ёмкости.
ARCH = {"d": 96, "heads": 4, "layers": 2, "ff": 192, "conv": 32, "kind_dim": 16, "skill_dim": 16,
        "gelu": "tanh", "max_u": MAX_U, "max_s": MAX_S, "side": SIDE, "n_types": N_TYPES}

# Дополнительные признаки (имена стабильны: по ним переносятся веса при дообучении).
UNIT_ABS_EXTRA = [
    "team_player", "team_enemy", "team_neutral", "is_guard", "is_source", "is_neutral_object",
    "objective_holder", "on_objective", "obj_dx", "obj_dy", "dist_obj",
    "n_buffs", "n_statuses", "n_marks", "n_skills", "n_skills_ready", "ult_ready",
    "summon_owner", "source_every", "source_spawns",
]
MAP_EXTRA = [
    "objective", "hold", "guard", "source", "object", "neutral",
    "ally_guard", "enemy_guard", "ally_source", "enemy_source",
    # описание клетки: рельеф, ловушки/эффекты, укрытия, порталы, временные изменения
    "terrain_changed", "terrain_move", "base_terrain_id", "terrain_other",
    "portal", "cover_half", "cover_full",
    "hazard_time", "hazard_permanent", "hazard_move", "hazard_trigger",
    "hazard_trigger_damage", "hazard_trigger_stun", "hazard_hidden", "hazard_foes_only",
    "hazard_covers", "hazard_mine_mult", "hazard_team_none", "hazard_other",
    "hazard_owner_own", "hazard_owner_foe",
    # трупы, которые вот-вот встанут, и активный прилив
    "rising", "rising_time", "tide", "tide_left",
    # события поля: предупреждение, остаток времени и тип события
    "arena_warn", "arena_pending",
] + [f"arena_{kind}" for kind in ARENA_KINDS]
GLOB_EXTRA = [
    "objective_none", "objective_hold", "objective_destroy", "objective_defend",
    "hold_progress", "hold_time", "n_guards", "n_sources", "n_neutral", "n_objects",
    "n_units", "n_waves", "wave", "intermission", "n_zones", "n_delayed", "n_corpses",
    "n_phases", "n_rising", "rising_next", "n_tides", "tide_next",
    "arena_n", "arena_pending_n", "arena_next", "arena_pending",
] + [f"arena_{kind}_{field}" for kind in ARENA_KINDS for field in ARENA_FIELDS]

_SCHEMA = {}


def schema(data):
    """Имена признаков полного наблюдения. Старые имена сохраняются, новые добавляются в конец."""
    key = id(data)
    if key in _SCHEMA:
        return _SCHEMA[key]
    base = B.schema(data)
    cfg = getattr(data, "config", {}) or {}
    terrains = sorted((cfg.get("terrain") or {}).keys())
    hazards = sorted((cfg.get("hazards") or {}).keys())
    unit_abs = list(base["unit_abs"]) + UNIT_ABS_EXTRA
    unit_rel = list(base["unit_rel"])
    skill = list(base["skill"])
    map_c = list(base["map"]) + MAP_EXTRA
    # Типы рельефа и опасностей — отдельными каналами, чтобы свёртка видела не «опасно/неопасно»,
    # а конкретную клетку: лава, вода, камень, лёд, пропасть, огонь, масло, яд, капкан и т.д.
    map_c += [f"terrain_{t}" for t in terrains]
    map_c += [f"hazard_{h}" for h in hazards]
    glob = [n for n in base["glob"] if not n.startswith("last:")]
    glob += [f"last:{k}" for k in range(N_TYPES)] + GLOB_EXTRA
    kinds = list(base["kinds"])
    for name in sorted(getattr(data, "objects", {}) or {}):   # охрана, источники и нейтральные объекты — свои виды
        if name not in kinds:
            kinds.append(name)
    s = {"unit": unit_rel + unit_abs, "unit_abs": unit_abs, "unit_rel": unit_rel, "skill": skill, "map": map_c,
         "glob": glob, "kinds": kinds, "skills": list(base["skills"]), "tags": list(base["tags"]),
         "terrains": terrains, "hazards": hazards}
    s["kind_ix"] = {k: i for i, k in enumerate(s["kinds"])}
    s["skill_ix"] = {k: i for i, k in enumerate(s["skills"])}
    s["dims"] = {"unit": len(s["unit"]), "skill": len(skill), "map": len(map_c), "glob": len(glob),
                 "kinds": len(s["kinds"]), "skills": len(s["skills"])}
    _SCHEMA[key] = s
    return s


def names(sc):
    """Только имена (для сохранения вместе с сетью)."""
    return {k: sc[k] for k in ("unit", "skill", "map", "glob", "kinds", "skills")}


class View(B.View):
    """Общие для всех наблюдателей признаки полного боя: все юниты и всё поле."""

    def __init__(self, c):
        self.c = c
        self.sc = sc = schema(c.data)
        self.t = c.time
        self.units = [u for u in c.units if u.alive]
        self.index = {u: i for i, u in enumerate(self.units)}
        ab = sc["unit_abs"]
        self.ax = {n: i for i, n in enumerate(ab)}
        A = np.zeros((len(self.units), len(ab)), np.float32)
        for i, u in enumerate(self.units):
            self._abs(A[i], u)
        self.A = A
        self.cells = np.array([u.cell for u in self.units], np.int32).reshape(-1, 2)
        self.teams = [u.team for u in self.units]
        self.kinds = np.array([sc["kind_ix"].get(u.proto_id, 0) for u in self.units], np.int64)
        self.occ = np.zeros((c.grid.h + 2 * B.R, c.grid.w + 2 * B.R), bool)
        for x, y in self.cells:
            if 0 <= x < c.grid.w and 0 <= y < c.grid.h:
                self.occ[y + B.R, x + B.R] = True
        self._map_static()

    def _abs(self, f, u):
        B.View._abs(self, f, u)                       # все старые признаки
        ix, c, sc = self.ax, self.c, self.sc
        w, h = max(1, c.grid.w), max(1, c.grid.h)
        f[ix["team_player"]] = 1.0 if u.team == PLAYER else 0.0
        f[ix["team_enemy"]] = 1.0 if u.team == ENEMY else 0.0
        f[ix["team_neutral"]] = 1.0 if u.team == NEUTRAL else 0.0
        obj = u.obj or {}
        f[ix["is_guard"]] = 1.0 if obj.get("guard") else 0.0
        f[ix["is_source"]] = 1.0 if obj.get("source") else 0.0
        f[ix["is_neutral_object"]] = 1.0 if u.obj and u.team == NEUTRAL else 0.0
        f[ix["n_buffs"]] = len(u.buffs) / 8
        f[ix["n_statuses"]] = len(u.statuses) / 5
        f[ix["n_marks"]] = len(u.marks) / 3
        skills = [s for s in u.skills if s in u.skill_defs]
        f[ix["n_skills"]] = len(skills) / MAX_S
        ready = sum(1 for s in skills if u.skill_ready(s, u.skill_defs[s]))
        f[ix["n_skills_ready"]] = ready / MAX_S
        f[ix["ult_ready"]] = 1.0 if any(u.skill_defs[s].get("ult") and u.skill_ready(s, u.skill_defs[s])
                                        for s in skills) else 0.0
        f[ix["summon_owner"]] = 1.0 if u.summon and getattr(u, "owner", None) is not None else 0.0
        src = obj.get("source") or {}
        f[ix["source_every"]] = min(3.0, (src.get("every") or 0) / 10)
        f[ix["source_spawns"]] = len(obj.get("spawn") or []) / 4
        objective = c.objective or {}
        cells = objective.get("cells") or []
        on = tuple(u.cell) in {tuple(p) for p in cells}
        f[ix["on_objective"]] = 1.0 if on else 0.0
        f[ix["objective_holder"]] = 1.0 if on and not u.obj and not u.summon else 0.0
        if cells:
            cx = sum(p[0] for p in cells) / len(cells)
            cy = sum(p[1] for p in cells) / len(cells)
            f[ix["obj_dx"]] = (cx - u.cell[0]) / max(w, h)
            f[ix["obj_dy"]] = (cy - u.cell[1]) / max(w, h)
            f[ix["dist_obj"]] = cheb((cx, cy), u.cell) / max(w, h)

    def _map_static(self):
        B.View._map_static(self)                      # старые слои + поля R
        c, sc, mi = self.c, self.sc, self.mi
        w, h = c.grid.w, c.grid.h
        M = self.M
        terrains = sc.get("terrains") or []
        tix = {t: i for i, t in enumerate(terrains)}
        cfg = c.cfg or {}
        tcfg = cfg.get("terrain") or {}
        hcfg = cfg.get("hazards") or {}

        # Подробное описание каждой клетки: конкретный рельеф и конкретная опасность, а не только «опасно».
        for (x, y), cell in c.grid.cells.items():
            X, Y = x + B.R, y + B.R
            t = cell.terrain
            layer = mi.get(f"terrain_{t}")
            if layer is not None:
                M[layer, Y, X] = 1
            else:
                M[mi["terrain_other"], Y, X] = 1
            base = cell.base_terrain or t
            if base in tix:
                M[mi["base_terrain_id"], Y, X] = (tix[base] + 1) / max(1, len(terrains))
            if cell.base_terrain and cell.base_terrain != t:
                M[mi["terrain_changed"], Y, X] = 1
            td = tcfg.get(t) or {}
            M[mi["terrain_move"], Y, X] = min(2.0, float(td.get("move", 1.0) or 1.0)) / 2
            if cell.portal:
                M[mi["portal"], Y, X] = 1
            if cell.cover == "half":
                M[mi["cover_half"], Y, X] = 1
            elif cell.cover == "full":
                M[mi["cover_full"], Y, X] = 1
            hz_name = cell.hazard
            if hz_name:
                layer = mi.get(f"hazard_{hz_name}")
                if layer is not None:
                    M[layer, Y, X] = 1
                else:
                    M[mi["hazard_other"], Y, X] = 1
                hz = hcfg.get(hz_name) or {}
                left = float(cell.hazard_time)
                permanent = left < 0 or left == PERMANENT
                M[mi["hazard_permanent"], Y, X] = 1.0 if permanent else 0.0
                M[mi["hazard_time"], Y, X] = 1.0 if permanent else min(1.0, max(0.0, left) / 20)
                M[mi["hazard_move"], Y, X] = min(2.0, float(hz.get("move", 1.0) or 1.0)) / 2
                tr = hz.get("trigger") or {}
                M[mi["hazard_trigger"], Y, X] = 1.0 if tr else 0.0
                M[mi["hazard_trigger_damage"], Y, X] = min(1.0, float(tr.get("damage", 0) or 0) / 30)
                M[mi["hazard_trigger_stun"], Y, X] = min(1.0, float(tr.get("stun", 0) or 0) / 5)
                M[mi["hazard_hidden"], Y, X] = 1.0 if hz.get("hidden") else 0.0
                M[mi["hazard_foes_only"], Y, X] = 1.0 if hz.get("foes_only") else 0.0
                M[mi["hazard_covers"], Y, X] = 1.0 if hz.get("covers") else 0.0
                M[mi["hazard_team_none"], Y, X] = 1.0 if cell.hazard_team is None else 0.0
                M[mi["hazard_mine_mult"], Y, X] = min(2.0, float(cell.mine_mult or 1.0)) / 2

        # Трупы, которые встанут через несколько секунд: где и когда.
        for item in getattr(c, "rising", []) or []:
            try:
                u, left = item[0], float(item[1])
            except (TypeError, ValueError, IndexError):
                continue
            x, y = u.cell
            if 0 <= x < w and 0 <= y < h:
                X, Y = x + B.R, y + B.R
                M[mi["rising"], Y, X] = 1
                M[mi["rising_time"], Y, X] = max(M[mi["rising_time"], Y, X], min(1.0, max(0.0, left) / 5))

        # Активный прилив: временная вода и сколько ей ещё осталось.
        for item in getattr(c, "tides", []) or []:
            try:
                end, cells = float(item[0]), item[1]
            except (TypeError, ValueError, IndexError):
                continue
            left = max(0.0, end - c.time)
            for x, y in cells:
                if 0 <= x < w and 0 <= y < h:
                    X, Y = x + B.R, y + B.R
                    M[mi["tide"], Y, X] = 1
                    M[mi["tide_left"], Y, X] = max(M[mi["tide_left"], Y, X], min(1.0, left / 10))

        # Предупреждения событий поля (ковш, извержение, лавина, прилив): где именно сейчас опасно.
        for ev in getattr(c, "arena", []) or []:
            if ev.get("pending") is None:
                continue
            left = max(0.0, float(ev.get("pending") or 0))
            layer = mi.get(f"arena_{ev.get('type')}")
            for p in ev.get("cells") or []:
                x, y = int(p[0]), int(p[1])
                if not (0 <= x < w and 0 <= y < h):
                    continue
                X, Y = x + B.R, y + B.R
                if layer is not None:
                    M[layer, Y, X] = 1
                M[mi["arena_warn"], Y, X] = 1
                M[mi["arena_pending"], Y, X] = max(M[mi["arena_pending"], Y, X], min(1.0, left / 5))

        # Чей именно капкан/мина: команда ставит их для чужих, но сеть должна видеть владельца.
        for team, S in self.side.items():
            for (x, y), cell in c.grid.cells.items():
                owner = cell.hazard_owner
                if owner is None or getattr(owner, "team", None) is None:
                    continue
                X, Y = x + B.R, y + B.R
                own = owner.team == team
                S[mi["hazard_owner_own" if own else "hazard_owner_foe"], Y, X] = 1

        objective = c.objective or {}
        cells = objective.get("cells") or []
        for x, y in cells:
            if 0 <= x < w and 0 <= y < h:
                self.M[mi["hold"], y + B.R, x + B.R] = 1
                self.M[mi["objective"], y + B.R, x + B.R] = 1
        for u in self.units:
            if not u.obj:
                continue
            x, y = u.cell
            if not (0 <= x < w and 0 <= y < h):
                continue
            X, Y = x + B.R, y + B.R
            self.M[mi["object"], Y, X] = 1
            if u.obj.get("guard"):
                self.M[mi["guard"], Y, X] = 1
                if objective.get("type") == "defend":
                    self.M[mi["objective"], Y, X] = 1
            if u.obj.get("source"):
                self.M[mi["source"], Y, X] = 1
                if objective.get("type") == "destroy":
                    self.M[mi["objective"], Y, X] = 1
            if u.team == NEUTRAL:
                self.M[mi["neutral"], Y, X] = 1
        # Командные слои: super() считает нейтральные объекты «чужими» для обеих команд — исправляем.
        for team, S in self.side.items():
            for name in ("ally", "enemy", "ally_hp", "enemy_hp"):
                S[mi[name]] = 0
            for u in self.units:
                x, y = u.cell
                if not (0 <= x < w and 0 <= y < h):
                    continue
                X, Y = x + B.R, y + B.R
                if u.team == NEUTRAL:
                    continue                              # нейтральные уже в общем слое M, не в командном
                own = u.team == team
                S[mi["ally" if own else "enemy"], Y, X] = 1
                S[mi["ally_hp" if own else "enemy_hp"], Y, X] = u.hp / max(1, u.max_hp)
                if u.obj and u.obj.get("guard"):
                    S[mi["ally_guard" if own else "enemy_guard"], Y, X] = 1
                if u.obj and u.obj.get("source"):
                    S[mi["ally_source" if own else "enemy_source"], Y, X] = 1

    # ---------- наблюдение одного юнита ----------

    def observe(self, u, last_type=0, caster=None):
        c, sc = self.c, self.sc
        me = self.index.get(u)
        order = sorted(range(len(self.units)), key=lambda i: (i != me, cheb(tuple(self.cells[i]), u.cell), i))[:MAX_U]
        units = [self.units[i] for i in order]
        n = len(units)
        w, h = max(1, c.grid.w), max(1, c.grid.h)
        scale = max(w, h)
        rel = np.zeros((n, len(sc["unit_rel"])), np.float32)
        ux, uy = u.cell
        uo = u.order or {}
        my_tgt = uo.get("target") if uo.get("type") == "attack" else None
        for k, i in enumerate(order):
            v = self.units[i]
            x, y = self.cells[i]
            d = cheb((x, y), (ux, uy))
            mine = v.team == u.team
            r = rel[k]
            r[0] = 1.0 if v is u else 0.0
            r[1] = 1.0 if mine and v is not u else 0.0
            r[2] = 1.0 if u.is_enemy(v) else 0.0
            r[3] = (x - ux) / scale
            r[4] = (y - uy) / scale
            r[5] = d / scale
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
                gdx = self.A[i, self.ax["goal_dx"]] * scale
                gdy = self.A[i, self.ax["goal_dy"]] * scale
                r[16] = 1.0 if (gdx * (ux - x) + gdy * (uy - y)) > 0 else 0.0
        U = np.concatenate([rel, self.A[order]], 1) if n else np.zeros((0, len(sc["unit"])), np.float32)
        kinds = self.kinds[order] if n else np.zeros(0, np.int64)

        # Полная карта: реальное поле лежит в self.M/self.side с полями B.R; переносим в SIDE×SIDE.
        S = self.side.get(u.team)
        if S is None:
            S = np.zeros_like(self.M)
        Mp = np.zeros((len(sc["map"]), SIDE, SIDE), np.float32)
        occ_full = np.zeros((SIDE, SIDE), bool)
        a, b = min(h, SIDE), min(w, SIDE)
        Mp[:, :a, :b] = self.M[:, B.R:B.R + a, B.R:B.R + b] + S[:, B.R:B.R + a, B.R:B.R + b]
        occ_full[:a, :b] = self.occ[B.R:B.R + a, B.R:B.R + b]
        mi = self.mi
        if 0 <= ux < b and 0 <= uy < a:
            Mp[mi["me"], uy, ux] = 1
        xs = np.arange(SIDE, dtype=np.float32)
        ys = np.arange(SIDE, dtype=np.float32)
        Mp[mi["coord_x"]] = ((xs / max(1, w - 1)) * 2 - 1)[None, :]
        Mp[mi["coord_y"]] = ((ys / max(1, h - 1)) * 2 - 1)[:, None]
        dd = np.maximum(np.abs(xs[None, :] - ux), np.abs(ys[:, None] - uy))
        Mp[mi["my_range"]] = (dd <= u.atk_range).astype(np.float32)

        # Навыки наблюдателя (полный набор, до MAX_S).
        skills = [s for s in u.skills if s in u.skill_defs][:MAX_S]
        SK = np.zeros((len(skills), len(sc["skill"])), np.float32)
        sids = np.array([sc["skill_ix"].get(s, 0) for s in skills], np.int64)
        si = {nm: i for i, nm in enumerate(sc["skill"])}
        general = []
        for k, sid in enumerate(skills):
            sk = u.skill_defs[sid]
            SK[k] = B._skill_static(sc, sid, sk)
            cd = u.cooldowns.get(sid, 0)
            ok = c.check_skill(u, sid, u if sk["target"] in ("self", "ally") else u.cell)
            usable = ok[0] or ok[1] in ("Нужна цель-юнит", "Не та цель", "Клетка занята")
            general.append(usable)
            SK[k, si["ready"]] = 1.0 if u.skill_ready(sid, sk) else 0.0
            SK[k, si["usable"]] = 1.0 if usable else 0.0
            SK[k, si["can_afford"]] = 1.0 if u.ap >= sk.get("ap", 0) else 0.0
            SK[k, si["cd_left"]] = min(3.0, cd / 20)
            SK[k, si["uses"]] = min(3.0, u.uses.get(sid, 0) / 20)

        tmask = np.zeros(N_TYPES, bool)
        umask = np.zeros((N_TYPES, MAX_U), bool)
        cmask = np.zeros((N_TYPES, NCELL), bool)
        ttype = np.zeros(N_TYPES, np.int64)
        tmask[T_HOLD] = True
        ttype[T_ATK] = TGT_UNIT
        for k, v in enumerate(units):
            if v.alive and u.is_enemy(v):
                umask[T_ATK, k] = True
        tmask[T_ATK] = umask[T_ATK].any()
        cells = [(x, y) for y in range(SIDE) for x in range(SIDE)]
        inb = Mp[mi["in_bounds"]].reshape(-1) > 0
        pas = Mp[mi["passable"]].reshape(-1) > 0
        occw = occ_full.reshape(-1)
        ttype[T_MOVE] = TGT_CELL
        if not u.static:
            can = inb & (pas | bool(u.flying)) & ~occw
            reach = self._reachable(u)
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
                    if (kind == "enemy") == u.is_enemy(v) and c.check_skill(u, sid, v)[0]:
                        umask[t, j] = True
                tmask[t] = umask[t].any()
            else:
                ttype[t] = TGT_CELL
                if any(sk.get(k2) for k2 in B.CELL_NEEDS):
                    for j in np.flatnonzero(inb):
                        cmask[t, j] = c.check_skill(u, sid, cells[j])[0]
                elif sk.get("free_cell"):
                    cmask[t] = inb & pas & ~occw
                else:
                    cmask[t] = inb
                tmask[t] = cmask[t].any()

        gi = {nm: i for i, nm in enumerate(sc["glob"])}
        g = np.zeros(len(sc["glob"]), np.float32)
        allies = [v for v in self.units if v.team == u.team]
        foes = [v for v in self.units if u.is_enemy(v)]
        neutral = [v for v in self.units if v.team == NEUTRAL]
        g[gi["time"]] = min(3.0, c.time / 90)
        g[gi["n_allies"]] = len(allies) / 12
        g[gi["n_foes"]] = len(foes) / 12
        ah = sum(v.hp for v in allies)
        fh = sum(v.hp for v in foes)
        g[gi["ally_hp"]] = math.log1p(ah) / 8
        g[gi["foe_hp"]] = math.log1p(fh) / 8
        g[gi["ally_hp_frac"]] = ah / max(1, sum(v.max_hp for v in allies))
        g[gi["foe_hp_frac"]] = fh / max(1, sum(v.max_hp for v in foes))
        g[gi["foes_adjacent"]] = sum(1 for v in foes if cheb(v.cell, u.cell) <= 1) / 4
        g[gi["allies_adjacent"]] = sum(1 for v in allies if v is not u and cheb(v.cell, u.cell) <= 1) / 4
        g[gi["ap_frac"]] = u.ap / max(1, u.ap_max) if u.ap_max else 0.0
        g[gi["hp_frac"]] = u.hp / max(1, u.max_hp)
        g[gi["last:%d" % min(N_TYPES - 1, int(last_type))]] = 1
        objective = c.objective or {}
        typ = objective.get("type") or "none"
        g[gi["objective_none"]] = 1.0 if typ not in ("hold", "destroy", "defend") else 0.0
        g[gi["objective_hold"]] = 1.0 if typ == "hold" else 0.0
        g[gi["objective_destroy"]] = 1.0 if typ == "destroy" else 0.0
        g[gi["objective_defend"]] = 1.0 if typ == "defend" else 0.0
        if typ == "hold":
            total = max(1e-6, objective.get("time", 0.0))
            g[gi["hold_progress"]] = min(1.0, c.hold / total)
            g[gi["hold_time"]] = min(3.0, total / 30.0)
        g[gi["n_guards"]] = len(c.guards()) / 4
        g[gi["n_sources"]] = sum(1 for v in self.units if v.obj and v.obj.get("source")) / 4
        g[gi["n_neutral"]] = len(neutral) / 8
        g[gi["n_objects"]] = sum(1 for v in self.units if v.obj) / 8
        g[gi["n_units"]] = len(self.units) / 12
        g[gi["n_waves"]] = len(getattr(c, "waves", []) or []) / 3
        g[gi["wave"]] = getattr(c, "wave", 0) / max(1, getattr(c, "wave_total", 1))
        g[gi["intermission"]] = min(3.0, getattr(c, "intermission", 0.0) / 10)
        g[gi["n_zones"]] = len(getattr(c, "zones", []) or []) / 8
        g[gi["n_delayed"]] = len(getattr(c, "delayed", []) or []) / 8
        g[gi["n_corpses"]] = len(getattr(c, "corpses", []) or []) / 8
        g[gi["n_phases"]] = len(getattr(c, "phases", []) or []) / 4
        rising = list(getattr(c, "rising", []) or [])
        g[gi["n_rising"]] = len(rising) / 4
        g[gi["rising_next"]] = min([max(0.0, float(item[1])) for item in rising] or [0.0]) / 5
        tides = list(getattr(c, "tides", []) or [])
        g[gi["n_tides"]] = len(tides) / 4
        g[gi["tide_next"]] = min([max(0.0, float(item[0]) - c.time) for item in tides] or [0.0]) / 10

        # События поля: не только «сколько их», но и тип, фаза, таймер, направление и сила.
        arena = list(getattr(c, "arena", []) or [])
        g[gi["arena_n"]] = len(arena) / 4
        g[gi["arena_pending_n"]] = sum(1 for ev in arena if ev.get("pending") is not None) / 4
        g[gi["arena_next"]] = min([max(0.0, float(ev.get("timer") or 0)) for ev in arena] or [0.0]) / 20
        g[gi["arena_pending"]] = min([max(0.0, float(ev["pending"])) for ev in arena
                                      if ev.get("pending") is not None] or [0.0]) / 5
        for kind in ARENA_KINDS:
            evs = [ev for ev in arena if ev.get("type") == kind]
            if not evs:
                continue
            g[gi[f"arena_{kind}_on"]] = 1.0
            g[gi[f"arena_{kind}_timer"]] = min(max(0.0, float(ev.get("timer") or 0)) for ev in evs) / 20
            pending = [max(0.0, float(ev["pending"])) for ev in evs if ev.get("pending") is not None]
            g[gi[f"arena_{kind}_pending"]] = min(pending) / 5 if pending else 0.0
            dirs = [ev.get("dir") for ev in evs if ev.get("dir") is not None]
            if dirs:
                g[gi[f"arena_{kind}_dir_x"]] = float(dirs[0][0])
                g[gi[f"arena_{kind}_dir_y"]] = float(dirs[0][1])
            g[gi[f"arena_{kind}_damage"]] = min(1.0, max(float(ev.get("damage") or 0) for ev in evs) / 30)
            g[gi[f"arena_{kind}_burn"]] = min(1.0, max(float(ev.get("burn") or 0) for ev in evs) / 10)
            g[gi[f"arena_{kind}_push"]] = min(1.0, max(float(ev.get("push") or 0) for ev in evs) / 3)
            g[gi[f"arena_{kind}_duration"]] = min(1.0, max(float(ev.get("duration") or 0) for ev in evs) / 10)
            g[gi[f"arena_{kind}_range"]] = min(1.0, max(float(ev.get("range") or 0) for ev in evs) / 6)
        obs = {"units": U, "kinds": kinds, "skills": SK, "sids": sids, "map": Mp, "glob": g,
               "tmask": tmask, "umask": umask, "cmask": cmask, "ttype": ttype}
        cands = {"units": units, "cells": cells, "skills": skills}
        return obs, cands


# ---------- действие ↔ приказ ----------

decode = B.decode
describe = B.describe


def encode(u, order, obs, cands):
    """Приказ → (тип, цель) по полной карте; None, если приказ не переводится."""
    tm, um, cm = obs["tmask"], obs["umask"], obs["cmask"]
    ux, uy = u.cell

    def cell_ix(p, t):
        x, y = int(p[0]), int(p[1])
        if 0 <= x < SIDE and 0 <= y < SIDE:
            j = y * SIDE + x
            if cm[t, j]:
                return j
        ok = np.flatnonzero(cm[t])
        if not len(ok):
            return None
        cx, cy = ok % SIDE, ok // SIDE
        return int(ok[np.argmin(np.maximum(np.abs(cx - x), np.abs(cy - y)))])

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
