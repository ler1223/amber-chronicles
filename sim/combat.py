"""Боевая симуляция: фиксированный тик, приказы, урон, теги и реакции.

Отрисовки здесь нет: всё, что видит игрок, уходит в self.events и забирается UI.
"""
import random

from . import autocast
from . import conditions as C
from . import movement as M
from . import stats as S
from .rules import Rules
from .ai import TeamAI
from . import kit
from . import passives as PS
from . import mutators as MU
from .grid import PERMANENT, Grid, cheb, sign
from .unit import Unit
from .teams import ENEMY, NEUTRAL, PLAYER

DIRECT = ("melee", "ranged", "spell")
DOT_TAGS = ("fire", "poison", "bleed")
# периодические прибавки шкалы: событие -> раз в сколько секунд, пока условие держится
PERIODIC = ("still", "aim", "unseen", "form_time", "near_fire", "structures")
OBJ_TEAMS = {"enemy": ENEMY, "player": PLAYER}


class Combat:
    def __init__(self, data, encounter_index=0, seed=1, ai_teams=(ENEMY,), player_positions=None, squad=None,
                 enemy_scale=None, fx=None, difficulty="normal"):
        """squad — список {"cls", "proto", "hp"} (из забега); по умолчанию базовые классы из squad.json.
        player_positions — желаемая расстановка; если не помещается в зону высадки, берутся точки карты.
        enemy_scale — {"hp", "damage"}: множители врагов по угрозе региона.
        fx — боевые эффекты реликвий отряда: reaction_mult, start_shield, kill_ap.
        difficulty — сложность главы: добавочные враги из пула главы, модификаторы, частота событий поля."""
        self.data = data
        self.cfg = data.config
        self.tags = data.tags
        self.enc = data.encounters[encounter_index]
        self.grid = Grid(self.enc["map"], self.cfg["legend"])
        self.dt = 1.0 / self.cfg["tick_rate"]
        self.time = 0.0
        self.events = []
        self.result = None
        self._skill = None
        self._intercepting = False
        self._actor = None            # кто сейчас применяет эффекты (заслуги: щит, контроль, бафф — ему)
        self._basic = False       # идёт обычная атака (режим героев: скейл от основного атрибута)
        self._flat = False        # идёт эффект навыка героя от его стата (атрибут уже учтён в множителе)
        self.enraged = 0          # ступень ярости затянутого боя
        self.traps = {}           # id ловчего -> клетки его капканов
        self.corpses = []         # трупы врагов: {"cell", "left", "name"} — ресурс некроманта
        self.zones = []           # зоны механик классов (sim/kit.py): эффект раз в every сек
        self.delayed = []         # отложенные эффекты: {"left", "total", "caster", "effects", "center", "tunit"}
        self.hit_timing = self.HIT_TIMING and bool(data.config.get("hit"))   # урон — при попадании, не при касте
        self.rng = random.Random(seed)
        self.fx = fx or {}
        self._reactions = {frozenset(r["tags"]): r for r in data.reactions["unit"]}
        self.rules = Rules(self, data.rules)

        self.units = []
        squad = squad or [{"cls": c, "proto": data.classes[c]} for c in data.squad["units"]]
        spawns = [tuple(p) for p in self.enc["player_spawn"]]
        if len(spawns) < len(squad):           # отряд больше точек высадки карты (сюжет: до 6 героев)
            zone = sorted(self.deploy_cells() - set(spawns), key=lambda q: (-q[0], abs(q[1] - self.grid.h / 2), q))
            spawns += zone[:len(squad) - len(spawns)]
        if player_positions:
            spawns = self._fit_positions([tuple(p) for p in player_positions[:len(squad)]], spawns, len(squad))
        for m, pos in zip(squad, spawns):
            u = self._spawn(PLAYER, m["cls"], m["proto"], pos)
            if m.get("hp") is not None:
                u.hp = max(1, min(u.max_hp, m["hp"]))
            u.autocast = autocast.settings_for(u.skill_defs, m.get("autocast"))
            u.ac_order, u.ac_reserve = autocast.priority_for(u.skills, m.get("ac_order"), m.get("ac_reserve"))
            u.ap = int(round(u.ap_max * m["proto"].get("start_ap", 1.0)))   # экспедиция и сюжет: с половиной AP
            if (u.passive or {}).get("start"):
                u.pp = min(u.pp_max, u.passive["start"])
            if (u.passive or {}).get("no_ap"):        # хрономант: вместо AP — шкала Времени
                u.ap_max = u.ap = 0
            if self.fx.get("start_shield"):
                u.shield, u.shield_time = self.fx["start_shield"], 30.0
        scale = enemy_scale or {}
        self.chapter = data.biomes.get(self.enc.get("chapter", "swamp"), {})
        self.diff = self.cfg["difficulties"][difficulty]
        foes = [(e["type"], tuple(e["pos"])) for e in self.enc["enemies"]]
        foes += self._difficulty_adds(difficulty, {p for _, p in foes})
        for etype, pos in foes:
            u = self._spawn(ENEMY, etype, data.enemies[etype], pos)
            self._scale_enemy(u, scale)
        self._apply_affixes(self.diff.get("affixes", 0))
        for etype in scale.get("extra_adds", []):     # последствия событий: засада, подмога боссу
            if etype in data.enemies:
                MU.spawn_add(self, etype, scale)
        for gtype in scale.get("guests", []):         # союзники-гости из событий
            self._spawn_guest(gtype, scale)
        self.tier = None
        if scale.get("tier"):                  # сложность похода: подкрепление, механики врагов, фазы боссов
            self.enemy_scale = scale
            MU.apply(self, scale["tier"], scale)
        if scale.get("solo"):                  # одиночка: врагов меньше — главари и первые по списку
            self._solo_trim(scale["solo"])
        hideable = [u for u in self.alive(ENEMY) if not u.boss]
        for u in self.rng.sample(hideable, min(len(hideable), self.enc.get("fog", 0))):
            u.hidden = True
        self.enemy_scale = scale
        for o in self.enc.get("objects", []):
            obj = self.spawn_object(o["type"], o["pos"], o.get("spawn"))
            obj.name = o.get("name", obj.name)
        # волны: первая — enemies, дальше — waves; между волнами передышка, в которой время эффектов стоит
        wcfg = self.cfg["waves"]
        self.waves = [list(w) for w in self.enc.get("waves", [])]
        self.wave_total = 1 + len(self.waves)
        self.wave = 1
        self.wave_clock = 0.0
        self.wave_timeout = self.enc.get("wave_timeout", wcfg["timeout"])
        self.intermission = 0.0
        self.objective = self.enc.get("objective")
        self.hold = 0.0
        self.phases = [dict(ph) for ph in self.enc.get("phases", [])]
        self.rising = []          # [юнит, через сколько встанет]
        self.tides = []           # [время отлива, клетки]
        self.arena = []
        order = self.cfg["difficulty_order"]
        scale_ = enemy_scale or {}
        for ev in self.chapter.get("events", []) + scale_.get("arena_extra", []):   # + опасности акта похода
            if order.index(ev.get("min_diff", "normal")) > order.index(difficulty):
                continue
            ev = dict(ev)
            ev["rate"] = self.diff.get("event_rate", 1.0) / scale_.get("arena_rate", 1.0)   # Жар — чаще
            ev["timer"] = ev.get("first", 6.0) * ev["rate"]
            ev["pending"] = None
            self.arena.append(ev)
        self.ais = [TeamAI(self, t) for t in ai_teams]
        self.controllers = []                  # нейросети юнитов: tick(combat, dt) каждый шаг
        # отряд игрока применяет навыки по настройкам автокаста; в демо-режиме — все навыки без условий
        self.autocaster = autocast.AutoCaster(self, PLAYER, force=PLAYER in ai_teams)

    def _scale_enemy(self, u, scale):
        """Сила врага: множители угрозы (основа) или уровень региона с титулом (режим героев)."""
        if scale.get("stats"):
            lvl = scale["level"]
            if u.elite or u.boss:
                lvl += self.data.stats_mode["enemy"]["elite_levels"]
            elif scale.get("titles", True):             # сюжет: в первых вылазках ветеранов и чемпионов нет
                t = S.roll_title(self.data, self.rng)
                if t:
                    lvl += t["levels"]
                    u.title = t["name"]
                    u.name = f"{u.name} ({t['name']})"
            u.level = lvl
            k = S.enemy_mults(self.data, lvl)
            u.power *= k["power"]
            u.armor += int(round(k["armor"]))
        else:
            k = scale
            u.power *= k.get("power", 1.0)          # экспедиция: сила навыков врагов растёт вместе с актом
            if scale.get("level"):
                u.level = scale["level"]
        mod = (scale.get("mods") or {}).get(u.proto_id, {})    # сюжет: отдельные враги слабее (слизни в начале)
        u.max_hp = u.hp = max(1, int(round(u.max_hp * k.get("hp", 1.0) * mod.get("hp", 1.0))))
        u.atk_damage = int(round(u.atk_damage * k.get("damage", 1.0) * mod.get("damage", 1.0)))
        u.base.update(atk_damage=u.atk_damage, armor=u.armor)
        if u.frost_armor:
            u.shield, u.shield_time = u.frost_armor["shield"], 1e9

    def _fit_positions(self, wanted, spawns, n):
        """Расстановка игрока на этой карте: занятая или непроходимая клетка — ближайшая свободная клетка высадки."""
        zone = self.deploy_cells()
        h = self.grid.h
        if h != 6:                         # расстановка хранится в рядах 0..5 — растягиваем под высоту карты
            wanted = [(x, round(y * (h - 1) / 5)) for x, y in wanted]
        out = []
        for i in range(n):
            p = wanted[i] if i < len(wanted) else tuple(spawns[i])
            if p not in zone or p in out:
                free = [q for q in zone if q not in out]
                if not free:
                    return spawns
                p = min(free, key=lambda q: (cheb(q, p), abs(q[1] - p[1]), q))
            out.append(p)
        return out

    def _difficulty_adds(self, difficulty, taken):
        """Сложность добавляет врагов главы (её «героический» и «кошмарный» пул) на свободные клетки врага."""
        n = self.diff.get("adds", 0)
        adds = self.chapter.get("adds", {})
        pool = adds.get("heroic", []) + (adds.get("nightmare", []) if difficulty == "nightmare" else [])
        if not n or not pool:
            return []
        min_x = self.enc.get("deploy_max_x", self.cfg["deploy_max_x"]) + 4
        cells = [p for p, c in sorted(self.grid.cells.items()) if c.passable and p[0] >= min_x and p not in taken
                 and c.terrain not in ("lava", "chasm")]
        out = []
        for _ in range(n):
            if not cells:
                break
            p = cells.pop(self.rng.randrange(len(cells)))
            out.append((self.rng.choice(pool), p))
        return out

    def _spawn_guest(self, etype, scale):
        """Союзник из события: враг этой главы сражается за отряд (сам выбирает цели)."""
        if etype not in self.data.enemies:
            return None
        zone = [p for p, c in sorted(self.grid.cells.items()) if c.passable and self.is_free(p)
                and p[0] <= self.enc.get("deploy_max_x", self.cfg["deploy_max_x"])]
        if not zone:
            return None
        u = self._spawn(PLAYER, etype, self.data.enemies[etype], zone[len(zone) // 2])
        self._scale_enemy(u, scale)
        u.summon = True
        u.name = f"{u.name} (союзник)"
        self.emit("summon", unit=u, owner=None)
        return u

    def _apply_affixes(self, n):
        """Кошмар: часть врагов получает модификатор (свирепый, каменный, вампирский...)."""
        aff = self.cfg.get("affixes", {})
        cand = [u for u in self.alive(ENEMY) if not u.boss]
        for u in self.rng.sample(cand, min(n, len(cand))):
            aid = self.rng.choice(sorted(aff))
            a = aff[aid]
            u.affix = aid
            u.name = f"{a['name']} {u.name.lower()}"
            u.max_hp = u.hp = int(round(u.max_hp * a.get("hp_mult", 1.0)))
            u.armor += a.get("armor_add", 0)
            u.atk_damage = int(round(u.atk_damage * a.get("atk_mult", 1.0)))
            u.atk_cd *= a.get("atk_cd_mult", 1.0)
            u.move_time *= a.get("move_mult", 1.0)
            u.lifesteal = max(u.lifesteal, a.get("lifesteal", 0.0))
            u.atk_tag = a.get("atk_tag", u.atk_tag)
            u.base.update(armor=u.armor, atk_damage=u.atk_damage, atk_cd=u.atk_cd, move_time=u.move_time)

    def reach(self, u):
        """Дальность атаки с учётом песчаной бури."""
        return max(1, u.atk_range + (u.buff("range_add", 0) if u.atk_range > 1 else 0))

    def _spawn(self, team, pid, proto, pos):
        u = Unit(len(self.units), team, pid, proto, pos)
        if not u.skill_defs:
            u.skill_defs = {sid: self.data.skills[sid] for sid in u.skills}
        self.units.append(u)
        return u

    def spawn_object(self, oid, pos, spawn=None):
        """Объект поля: бочка, валун (ничьи), источник врагов (враг), охраняемый обоз (отряд)."""
        d = self.data.objects[oid]
        proto = {"name": d["name"], "label": d["name"][:2], "color": d["color"], "role": "object", "hp": d["hp"],
                 "move_time": 1.0, "attack": {"damage": 0, "range": 0, "cooldown": 99.0}, "static": True,
                 "object": dict(d, id=oid, spawn=list(spawn or []))}
        team = OBJ_TEAMS.get(d.get("team"), NEUTRAL)
        u = self._spawn(team, oid, proto, self.free_near(pos) or tuple(pos))
        if team == ENEMY:
            u.max_hp = u.hp = int(round(u.max_hp * (self.enemy_scale or {}).get("hp", 1.0)))
        return u

    def free_near(self, pos, radius=3):
        """Свободная проходимая клетка: сама pos или ближайшая к ней (без лавы и пропасти)."""
        pos = tuple(pos)
        cells = [p for p in self.grid.in_radius(pos, radius)
                 if self.is_free(p) and self.grid.get(p).terrain not in ("lava", "chasm")]
        return min(cells, key=lambda p: (cheb(p, pos), abs(p[0] - pos[0]) + abs(p[1] - pos[1]), p)) if cells else None

    # ---------- расстановка (до первого тика) ----------

    def deploy_cells(self):
        max_x = self.enc.get("deploy_max_x", self.cfg["deploy_max_x"])
        return {p for p, c in self.grid.cells.items() if c.passable and p[0] <= max_x}

    def redeploy(self, u, pos):
        """Поставить юнита игрока на клетку зоны высадки; если там свой — поменять местами."""
        pos = tuple(pos)
        if self.time > 0 or u.team != PLAYER or pos not in self.deploy_cells():
            return False
        other = self.unit_at(pos)
        if other is u:
            return True
        if other and (other.team != PLAYER or other.obj):
            return False
        if other:
            other.cell = other.prev_cell = u.cell
        u.cell = u.prev_cell = pos
        return True

    def positions(self):
        return [u.cell for u in self.units if u.team == PLAYER]

    # ---------- запросы ----------

    def alive(self, team=None):
        return [u for u in self.units if u.alive and (team is None or u.team == team)]

    def heroes(self, team=PLAYER):
        """Отряд без призванных (тотемов) и объектов."""
        return [u for u in self.units if u.team == team and not u.summon and not u.obj]

    def fighters(self, team):
        """Живые бойцы команды: без объектов (источников, обоза)."""
        return [u for u in self.units if u.alive and u.team == team and not u.obj]

    def guards(self):
        """Охраняемые объекты отряда (цель «Защитить»)."""
        return [u for u in self.units if u.obj and u.obj.get("guard")]

    def in_hold(self, p):
        return self.objective is not None and self.objective["type"] == "hold" and \
                list(p) in self.objective["cells"]

    def visible(self, u):
        """Скрытного (тень ассасина) враги не видят и не выбирают целью."""
        return "stealth" not in u.buffs and u.merged <= 0      # связующий внутри союзника — не цель

    def foes_of(self, u):
        """Видимые враги. Из объектов сами в цель попадают только источники врагов; бочку, валун и обоз бьют
        по приказу (игрока или цели боя — см. TeamAI.objective_order)."""
        return [f for f in self.units if f.alive and u.is_enemy(f) and self.visible(f)
                and not (f.obj and not f.obj.get("source"))]

    def unit_at(self, pos):
        pos = tuple(pos)
        for u in self.units:
            if u.alive and u.cell == pos:
                return u
        return None

    def occupied(self, exclude=None):
        return {u.cell for u in self.units if u.alive and u is not exclude}

    def units_in_radius(self, center, r):
        return [v for v in self.units if v.alive and cheb(v.cell, center) <= r]

    def emit(self, _event, **kw):
        kw["t"] = _event
        self.events.append(kw)

    def log(self, text, color=(200, 200, 200)):
        self.emit("log", text=text, color=color)

    # ---------- приказы ----------

    # ---------- очередь приказов (Shift) ----------

    def queue_order(self, u, o):
        """В конец очереди героя: {"type": "move", "cell"} | {"type": "attack", "target"} |
        {"type": "skill", "skill", "target"}. Пустая очередь и нет приказа — начинается сразу."""
        if not u.alive:
            return False, ""
        if (u.order is None or self._order_done(u)) and u.cast is None and not u.queue:
            return self._start_queued(u, o)
        u.queue.append(o)
        return True, ""

    def _order_done(self, u):
        o = u.order
        if o is None:
            return True
        t = o.get("target")
        return o["type"] in ("attack", "skill") and isinstance(t, Unit) and not t.alive

    def _start_queued(self, u, o):
        if o["type"] == "move":
            return self.order_move(u, o["cell"], keep_queue=True)
        if o["type"] == "attack":
            return self.order_attack(u, o["target"], keep_queue=True)
        sid, target = o["skill"], o["target"]
        sk = u.skill_defs.get(sid)
        if sk is None:
            return False, "Нет такого навыка"
        if sk["target"] == "self":
            target = u
        elif sk["target"] == "cell" and isinstance(target, Unit):
            target = target.cell
        ok, msg = self.check_skill(u, sid, target)
        if not ok and msg not in ("Не хватает AP", "Перезарядка"):
            return False, msg
        self._cancel_cast(u)                  # навык в очереди ждёт AP и перезарядку сам
        u.order = {"type": "skill", "skill": sid, "target": target, "then": None, "auto": False, "queued": True}
        return True, ""

    def _advance_queue(self, u):
        while u.queue and self._order_done(u) and u.cast is None:
            ok, _ = self._start_queued(u, u.queue.pop(0))
            if ok:
                return

    def order_move(self, u, pos, keep_queue=False):
        pos = tuple(pos)
        if not u.alive or u.static or not self.grid.passable(pos):
            return False, "Туда нельзя"
        if not keep_queue:
            u.queue.clear()
        self._cancel_cast(u)
        u.order = {"type": "move", "cell": pos}
        u.last_target = None  # игрок вывел юнита из боя — старую цель забываем
        return True, ""

    def order_path(self, u, points):
        """Маршрут, выбранный игроком: юнит идёт ровно по этим клеткам (промежутки между дальними точками
        достраиваются кратчайшим путём)."""
        if not u.alive or not M.movable(self, u) or u.static:
            return False, "Не может ходить"
        cells = M.fill_path(self, u, points)
        if cells is None:
            return False, "Туда не пройти"
        if not cells:
            return False, "Маршрут пуст"
        self._cancel_cast(u)
        u.order = {"type": "path", "cells": cells, "stuck": 0.0}
        u.last_target = None
        return True, ""

    def order_attack(self, u, target, keep_queue=False):
        if not u.alive or not target.alive or not u.is_enemy(target):
            return False, "Нельзя атаковать"
        if not keep_queue:
            u.queue.clear()
        self._cancel_cast(u)
        u.order = {"type": "attack", "target": target}
        return True, ""

    def assign_initial_targets(self, team=PLAYER):
        """В начале боя сразу выбрать ближайшего врага, чтобы отряд не стоял без приказа.
        Игрок по-прежнему может перехватить управление любым приказом."""
        for u in self.heroes(team):
            if u.alive:
                self._retarget(u)
                if u.order and u.order.get("type") == "attack":
                    u.order["initial"] = True
                    u.last_target = u.order["target"]
        for u in self.units:                   # союзники-гости тоже сразу в бой
            if u.alive and u.team == team and u.summon and u.owner is None and not u.obj:
                self._retarget(u)

    def check_skill(self, u, sid, target):
        sk = u.skill_defs[sid]
        if not u.alive or sid not in u.skills:
            return False, "Нет такого навыка"
        if u.cooldowns.get(sid, 0) > 0:
            return False, "Перезарядка"
        if sk.get("hp_cost") and u.hp <= sk["hp_cost"]:
            return False, "Мало HP"
        # AP тратятся только на старте каста, но с нехваткой лучше сразу сказать
        if u.ap + (u.cast["ap"] if u.cast else 0) < sk["ap"]:
            return False, "Не хватает AP"
        if "silence" in u.buffs:              # безмолвие: навыки недоступны, пока длится
            return False, "Безмолвие"
        why = kit.check(self, u, sk, target)   # шкала класса, облик, тень, метка, тотемы, знамя
        if why:
            return False, why
        kind = sk["target"]
        if kind == "self":
            return True, ""
        if kind in ("enemy", "ally"):
            if not isinstance(target, Unit) or not target.alive:
                return False, "Нужна цель-юнит"
            if (kind == "enemy") != u.is_enemy(target):
                return False, "Не та цель"
            return True, ""
        pos = tuple(target.cell if isinstance(target, Unit) else target)
        if not self.grid.in_bounds(pos):
            return False, "Вне поля"
        if sk.get("free_cell") and (pos == u.cell or not self.is_free(pos)):
            return False, "Клетка занята"
        return True, ""

    def order_skill(self, u, sid, target, auto=False, keep_queue=False):
        sk = u.skill_defs[sid]
        if not auto and not keep_queue:
            u.queue.clear()
        if sk["target"] == "self":
            target = u
        elif sk["target"] == "cell" and isinstance(target, Unit):
            target = target.cell
        ok, msg = self.check_skill(u, sid, target)
        if not ok:
            return False, msg
        then = self._attack_target_after(u, target)
        self._cancel_cast(u)
        u.order = {"type": "skill", "skill": sid, "target": target, "then": then, "auto": auto}
        return True, ""

    def _attack_target_after(self, u, skill_target):
        """Кого бить после навыка: прежнюю цель атаки, иначе врага, на которого применён навык."""
        o = u.order
        if o is None:
            prev = u.last_target
        elif o["type"] == "attack":
            prev = o["target"]
        elif o["type"] == "skill":
            prev = o.get("then")
        else:
            prev = None
        for t in (prev, skill_target):
            if isinstance(t, Unit) and t.alive and u.is_enemy(t):
                return t
        return None

    def _cancel_cast(self, u):
        """Отмена каста игроком: AP и перезарядка возвращаются."""
        if u.cast:
            u.ap = min(u.ap_max, u.ap + u.cast["ap"])
            u.cooldowns.pop(u.cast["skill"], None)
            u.cast = None
            self.emit("cast_cancel", unit=u)

    # ---------- тик ----------

    def step(self):
        if self.result:
            return
        dt = self.dt
        if self.intermission > 0:
            self._intermission_step(dt)
            return
        if self.time == 0.0:                  # первый шаг боя: правила «в начале боя» (предметы, благословения)
            for u in list(self.units):
                if u.alive and u.proto.get("rules"):
                    self.rules.fire("start", {"start", u.team}, unit=u, source=u)
        self.time += dt
        for c in self.grid.cells.values():
            if c.hazard and c.hazard_time != PERMANENT:
                c.hazard_time -= dt
                if c.hazard_time <= 0:
                    c.hazard = None
                    c.blaze = False
        self._oil_t = getattr(self, "_oil_t", 0.0) + dt
        if self._oil_t >= 0.2:                 # огонь рядом с маслом поджигает лужу (как бы его ни поставили)
            self._oil_t = 0.0
            oil = [p for p, c in self.grid.cells.items() if c.hazard == "oil"]
            for p in oil:
                if self.grid.get(p).hazard == "oil" and any(
                        (q := self.grid.get((p[0] + dx, p[1] + dy))) is not None and q.hazard == "fire"
                        for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy):
                    self.ignite_oil(p)
        self._arena_update(dt)
        for item in list(self.rising):
            item[1] -= dt
            if item[1] <= 0:
                self.rising.remove(item)
                self._rise(item[0])
        for item in list(self.tides):
            if self.time >= item[0]:
                self.tides.remove(item)
                for p in item[1]:
                    c = self.grid.get(p)
                    if c.base_terrain:
                        c.terrain, c.base_terrain = c.base_terrain, None
                self.emit("tide_end", cells=item[1])
        for ai in self.ais:
            ai.update(dt)
        self.autocaster.update(dt)
        for ctl in self.controllers:           # нейросети юнитов (sim/neural.py)
            ctl.tick(self, dt)
        for u in self.units:
            if u.alive:
                if u.obj:
                    self._update_object(u, dt)
                else:
                    self._update_unit(u, dt)
        self._delayed_update(dt)
        kit.tick_zones(self, dt)
        if self.tier:
            MU.tick(self, dt)
        self._corpse_update(dt)
        self._enrage_update()
        self._objective_update(dt)
        self._phases_update()
        self._waves_update(dt)
        self._check_end()

    # ---------- волны, передышка, цели боя ----------

    def _intermission_step(self, dt):
        """Передышка: враги не идут, время эффектов стоит (HP, AP, перезарядки, статусы, шкалы не меняются).
        Герои могут перейти на другие клетки и применить навыки, расставляя поле под следующую волну."""
        self.intermission -= dt
        self.autocaster.update(dt)
        for u in self.units:
            if u.alive:
                if u.obj:
                    self._update_object(u, 0.0, dt)
                else:
                    self._act(u, dt, frozen=True)
        if self.intermission <= 0:
            self.intermission = 0.0
            self._next_wave()

    def win_now(self):
        """Мгновенная победа (тесты, отладка): враги и источники гибнут, волн и фаз больше нет, точка удержана."""
        self.waves, self.phases, self.rising, self.intermission = [], [], [], 0.0
        if self.objective and self.objective["type"] == "hold":
            self.hold = self.objective["time"]
        for u in self.alive(ENEMY):
            u.hp = 0
            self._kill(u)
        self._check_end()

    def call_wave(self):
        """Игрок не ждёт конца передышки."""
        if self.intermission > 0:
            self.intermission = min(self.intermission, self.dt)

    def _waves_update(self, dt):
        if not self.waves:
            return
        self.wave_clock += dt
        if not self.fighters(ENEMY) and not self.rising:
            self.intermission = self.cfg["waves"]["intermission"]
            for u in self.units:      # приказы атаки на мёртвых не тянутся в передышку
                if u.alive and u.team == PLAYER and u.order and u.order["type"] == "attack":
                    u.order = None
            self.emit("intermission", wave=self.wave + 1, total=self.wave_total, time=self.intermission)
            self.log(f"Волна {self.wave} отбита. Передышка", (170, 220, 255))
        elif self.wave_clock >= self.wave_timeout:
            self.log("Враги не ждут: следующая волна уже здесь", (255, 190, 120))
            self._next_wave()

    def next_wave_preview(self):
        """Кто и откуда придёт следующей волной: [(тип, клетка)]."""
        return [(e["type"], tuple(e["pos"])) for e in self.waves[0]] if self.waves else []

    def _next_wave(self):
        if not self.waves:
            return
        wave = self.waves.pop(0)
        self.wave += 1
        self.wave_clock = 0.0
        self.emit("wave", wave=self.wave, total=self.wave_total)
        self.log(f"Волна {self.wave} из {self.wave_total}!", (255, 170, 120))
        for e in wave:
            self.spawn_enemy(e["type"], e["pos"])

    def spawn_enemy(self, etype, pos, near=3):
        """Враг посреди боя (волна, источник, фаза босса) — на свободную клетку у pos."""
        cell = self.free_near(pos, near)
        if cell is None:
            return None
        u = self._spawn(ENEMY, etype, self.data.enemies[etype], cell)
        self._scale_enemy(u, self.enemy_scale or {})
        u.ai_timer = 0.3
        self.emit("spawn", unit=u)
        return u

    def _update_object(self, u, dt, move_dt=None):
        """Объект только двигается от толчка; источник выпускает врагов."""
        if u.moving:
            u.move_t = min(1.0, u.move_t + (dt if move_dt is None else move_dt) / u.move_dur)
        if u.life is not None and dt > 0:     # ледяная стена и костяная стена тают
            u.life -= dt
            if u.life <= 0:
                u.alive, u.hp = False, 0
                self.emit("object_break", unit=u, ignite=False, fx=None)
                return
        if u.fuse > 0 and dt > 0:            # горящий фитиль
            u.fuse -= dt
            if u.fuse <= 0:
                self.break_object(u, ignite=True)
                return
        src = u.obj.get("source")
        if not src or not u.obj["spawn"] or dt <= 0:
            return
        u.spawned = [s for s in u.spawned if s.alive]
        u.spawn_timer += dt
        if u.spawn_timer >= src["every"] and len(u.spawned) < src["cap"]:
            u.spawn_timer = 0.0
            v = self.spawn_enemy(self.rng.choice(u.obj["spawn"]), u.cell, 2)
            if v:
                u.spawned.append(v)
                self.emit("source_spawn", unit=v, src=u)

    def _objective_update(self, dt):
        ob = self.objective
        if not ob or ob["type"] != "hold":
            return
        inside = [u for u in self.alive() if not u.obj and not u.summon and self.in_hold(u.cell)]
        mine = any(u.team == PLAYER for u in inside)
        foes = any(u.team == ENEMY for u in inside)
        if mine and not foes:
            self.hold = min(ob["time"], self.hold + dt)

    def _solo_trim(self, s):
        """Бой одного героя: босс и элита остаются, остальных — сколько велено (у босса свита меньше)."""
        foes = [u for u in self.units if u.team == ENEMY and not u.obj]
        leaders = [u for u in foes if u.boss or u.elite]
        rest = [u for u in foes if u not in leaders]
        keep = (s["boss_keep"] if any(u.boss for u in leaders) else max(0, s["keep"] - len(leaders)))
        drop = set(id(u) for u in rest[keep:])
        self.units = [u for u in self.units if id(u) not in drop]

    def _phases_update(self):
        """Фазы босса: на пороге HP — подкрепление и всплеск событий поля."""
        if not self.phases:
            return
        boss = next((u for u in self.units if u.boss and u.team == ENEMY), None)
        if boss is None or not boss.alive:
            return
        while self.phases and boss.hp <= boss.max_hp * self.phases[0]["at"]:
            ph = self.phases.pop(0)
            self.emit("phase", unit=boss, name=ph.get("name", ""))
            self.log(f"{boss.name}: {ph.get('name', 'новая фаза')}!", (255, 150, 90))
            spawns = ph.get("spawn", [])
            if (self.enemy_scale or {}).get("solo"):
                spawns = spawns[:self.enemy_scale["solo"]["phase_max"]]
            for e in spawns:
                self.spawn_enemy(e["type"], e["pos"])
            if ph.get("shield"):
                boss.shield, boss.shield_time = int(boss.max_hp * ph["shield"]), 8.0
                self.emit("shield", unit=boss, amount=boss.shield)
            for ev in self.arena:          # поле отвечает на гнев босса: события приходят сразу
                if ev["pending"] is None:
                    ev["timer"] = min(ev["timer"], 0.5)

    def _update_unit(self, u, dt):
        if u.merged > 0:                       # связующий внутри союзника: ждёт, пока выйдет
            u.merged -= dt
            host = u.merge_host
            if u.merged <= 0 or host is None or not host.alive:
                u.merged = 0.0
                spot = self.free_near(host.cell if host is not None else (0, 0), 2) or self.free_near((0, 0), 6)
                if spot is not None:
                    u.cell = u.prev_cell = spot
                    u.move_t = 1.0
                self.emit("unmerge", unit=u)
            return
        if u.life is not None:
            u.life -= dt
            if u.life <= 0:
                self._kill(u, expire=True)
                return
        if u.airborne > 0:                   # в прыжке: не ходит и не бьёт, пока не приземлится
            u.airborne -= dt
            return
        if u.charm_time > 0:
            u.charm_time -= dt
            if u.charm_time <= 0:
                u.order = None
                u.last_target = None
                self.emit("charm_end", unit=u)
        if u.heat:                       # любит жар: в огне сильнее и восстанавливается
            c = self.grid.get(u.cell)
            if "fire" in u.statuses or c.hazard == "fire" or c.terrain == "lava":
                u.buffs["atk_mult"] = [u.heat.get("atk_mult", 1.3), 0.5]
                u.buffs["regen"] = [u.heat.get("regen", 4), 0.5]
        if u.frost_armor:                # ледяная броня нарастает снова
            u.frost_timer += dt
            fa = u.frost_armor
            if u.frost_timer >= fa["every"] and u.shield < fa["shield"]:
                u.frost_timer = 0.0
                u.shield, u.shield_time = fa["shield"], 1e9
                self.emit("frost_armor", unit=u)
        if u.stasis > 0:
            u.stasis -= dt
        if u.levitate > 0:
            u.levitate -= dt
            if u.levitate <= 0:              # падение после невесомости
                self.emit("land", unit=u)
                self.damage(u, u.levitate_dmg, None, None, "reaction")
                if not u.alive:
                    return
        if u.tether_time > 0:
            u.tether_time -= dt
            b = u.tethered_by
            if u.tether_time <= 0 or b is None or not b.alive:
                u.tethered_by, u.tether_time = None, 0.0
        if not u.summon:                      # история для отката хрономанта: 5 сек, раз в 0.25 сек
            u.hist_acc += dt
            if u.hist_acc >= 0.25:
                u.hist_acc = 0.0
                u.history.append((self.time, u.cell, u.hp))
                if len(u.history) > 20:
                    u.history.pop(0)
        if u.guard_time > 0:
            u.guard_time -= dt
            if u.guard_time <= 0 or u.guarded_by is None or not u.guarded_by.alive:
                u.guard_time, u.guarded_by = 0.0, None
        if u.watch:
            u.watch["left"] -= dt
            if u.watch["left"] <= 0:
                u.watch = None
        if u.song:
            self._song_update(u, dt)
        if u.aura:
            u.aura_timer += dt
            if u.aura_timer >= u.aura["every"]:
                u.aura_timer -= u.aura["every"]
                self.emit("aura", unit=u, radius=u.aura.get("radius", 0))
                self.apply_effects(u, u.aura["effects"], u.cell)
                self.gain(u.owner, "aura")         # заряд шамана: тотем сработал
        self._regen(u, dt)
        cdr = u.buff("cd_rate", 1.0)
        for d in (u.cooldowns, u.reaction_cd):
            for k in list(d):
                d[k] -= dt * (cdr if d is u.cooldowns else 1.0)
                if d[k] <= 0:
                    del d[k]
        u.attack_timer = max(0.0, u.attack_timer - dt)
        u.kite_cd = max(0.0, u.kite_cd - dt)
        self._sync_dots(u)
        for tag in list(u.statuses):
            if tag in u.dots:
                continue                      # доты тикают отдельно: у них свои сила, стаки и длительность
            u.statuses[tag] -= dt
            if u.statuses[tag] <= 0:
                del u.statuses[tag]
        if u.shield:
            u.shield_time -= dt
            if u.shield_time <= 0:
                u.shield = 0
        if u.taunted_by:
            u.taunt_time -= dt
            if u.taunt_time <= 0 or not u.taunted_by.alive:
                u.taunted_by = None
        for stat in list(u.buffs):
            u.buffs[stat][1] -= dt
            if u.buffs[stat][1] <= 0:
                del u.buffs[stat]
        if u.marks:
            kit.tick_marks(self, u, dt)
        if u.passive and u.passive.get("core"):
            PS.tick(self, u, dt)
        if "regen" in u.buffs:
            u.regen_acc += dt
            if u.regen_acc >= 1.0:
                u.regen_acc -= 1.0
                self.heal(u, u.buff("regen", 0))
        else:
            u.regen_acc = 0.0

        self._cell_effects(u, dt)
        self._tick_dots(u, dt)
        if not u.alive:
            return

        if u.gauge:
            self._gauge_tick(u, dt)
        self._act(u, dt)

    def _act(self, u, dt, frozen=False):
        """Шаг, каст, приказ. frozen — передышка: оглушение не проходит, остальное — как обычно."""
        if u.moving:
            u.move_t = min(1.0, u.move_t + dt / u.move_dur)
            return
        if u.stun > 0:
            if frozen:
                return
            u.stun -= dt
            if u.stun <= 0:
                u.asleep = False
            return
        if u.cast:
            u.cast["left"] -= dt / u.slow_mult(self.tags)
            if u.cast["left"] <= 0:
                c, u.cast = u.cast, None
                self._resolve_skill(u, c["skill"], c["target"], c.get("auto", False))
            return
        if u.wait > 0:
            u.wait -= dt
            return
        if frozen and u.order and u.order["type"] == "attack":
            u.order = None
        self._execute_order(u)

    # ---------- личные шкалы ----------

    def gain(self, u, event, n=1):
        """Шкала героя растёт от события его фишки (gauge.gain в classes.json); заодно копится условие ультимейта."""
        if u is not None and u.alive:
            u.ult_count[event] = u.ult_count.get(event, 0) + n
        g = u.gauge if u is not None and u.alive else None
        if not g or u.pp >= u.pp_max:
            return
        k = g["gain"].get(event)
        if k and event not in PERIODIC:
            u.pp = min(u.pp_max, u.pp + k * n)
            self.emit("gauge", unit=u, event=event)

    def _gauge_tick(self, u, dt):
        for event in PERIODIC:
            every = u.gauge["gain"].get(event)
            if not every:
                continue
            if not self._gauge_cond(u, event):
                u.gauge_acc[event] = 0.0
                continue
            acc = u.gauge_acc.get(event, 0.0) + dt
            if acc >= every:
                acc -= every
                if u.pp < u.pp_max:
                    u.pp += 1
                    self.emit("gauge", unit=u, event=event)
            u.gauge_acc[event] = acc

    def _gauge_cond(self, u, event):
        if event == "still":
            return not u.moving and not (u.order and u.order["type"] == "move")
        if event == "aim":                    # прицел снайпера: стоит и рядом нет врага
            return not u.moving and not (u.order and u.order["type"] == "move") and \
                not any(cheb(f.cell, u.cell) <= 1 for f in self.foes_of(u))
        if event == "unseen":
            return "stealth" in u.buffs or not any(
                f.alive and (f.last_target is u or (f.order and f.order.get("target") is u)) for f in self.units)
        if event == "form_time":
            return u.form is not None
        if event == "structures":             # стужа криоманта: пока стоят его постройки
            return any(o.alive and o.obj and o.owner is u for o in self.units)
        if event == "near_fire":
            for p in self.grid.in_radius(u.cell, 2):
                c = self.grid.get(p)
                if c.hazard == "fire" or c.terrain == "lava":
                    return True
            return any(v.alive and "fire" in v.statuses for v in self.units_in_radius(u.cell, 2))
        return False

    def _regen(self, u, dt):
        if u.ap < u.ap_max:
            u.ap_timer += dt
            every = u.ap_regen * u.buff("ap_rate", 1.0)      # песня барда ускоряет восстановление
            if u.ap_timer >= every:
                u.ap_timer -= every
                u.ap += 1
        else:
            u.ap_timer = 0.0
        if u.pp < u.pp_max:
            u.pp_timer += dt
            if u.pp_timer >= u.pp_regen:
                u.pp_timer -= u.pp_regen
                u.pp += 1
        else:
            u.pp_timer = 0.0

    def _cell_effects(self, u, dt):
        if u.flying:
            return
        c = self.grid.get(u.cell)
        terrain = self.cfg["terrain"][c.terrain]
        terrain_status = terrain.get("status")
        if terrain_status and not c.hazard and not self.immune(u, terrain_status):
            self._touch_status(u, terrain_status, hostile=False)     # вода гасит огонь, а не взрывается паром
        if (terrain.get("dps") or terrain.get("dps_pct")) and not c.hazard and not self.immune(u, terrain.get("status")):
            u.hazard_acc += dt                         # лава жжёт всегда
            if u.hazard_acc >= 1.0:
                u.hazard_acc -= 1.0
                self.damage(u, self._env_amount(u, terrain), None, kind="hazard",
                            dtype=terrain.get("damage_type"))
            return
        if c.hazard:
            h = self.cfg["hazards"][c.hazard]
            if h.get("trigger"):                     # мина и капкан: один раз, только по чужим
                if c.hazard_team is not None and c.hazard_team != u.team and not u.obj:
                    tr = h["trigger"]
                    owner = c.hazard_owner
                    ch = c.charge
                    c.hazard, c.hazard_owner, c.charge = None, None, None
                    self.emit("mine", pos=c.pos, unit=u, kind=h.get("look", "mine"))
                    src = owner if owner is not None and owner.alive else None
                    if ch:                             # мина героя: урон от силы навыков, свой радиус и оглушение
                        kit.blow_cell(self, src, c.pos, ch, tr.get("tag"), first=u)
                    else:
                        self.damage(u, tr["damage"] * getattr(c, "mine_mult", 1.0), src, tr.get("tag"), "reaction")
                    stun = (ch or {}).get("stun") or tr.get("stun")
                    if stun and u.alive:
                        self.apply_stun(u, stun, tr.get("look", "trap"))
                    if tr.get("expose") and u.alive:
                        self.add_buff(u, "exposed", tr.get("expose_mult", 1.2), tr["expose"])
                    if owner is not None:
                        self.gain(owner, "caught")
                return
            if h.get("foes_only") and c.hazard_team in (None, u.team):
                u.hazard_acc = 0.0
                return
            if h.get("status") and self.immune(u, h["status"]):
                u.hazard_acc = 0.0
                return
            if h.get("status"):
                self._touch_status(u, h["status"], hostile=c.hazard_team != u.team)
            if h.get("dps") or h.get("dps_pct"):
                u.hazard_acc += dt
                if u.hazard_acc >= 1.0:
                    u.hazard_acc -= 1.0
                    k = self.cfg["blaze"]["mult"] if c.blaze and c.hazard == "fire" else 1.0
                    self.damage(u, self._env_amount(u, h) * k, None, kind="hazard",
                                dtype=h.get("damage_type"))
        else:
            u.hazard_acc = 0.0

    # ---------- доты ----------

    def _dot_cfg(self, tag):
        return self.tags.get(tag, {}).get("dot", {})

    @staticmethod
    def _pct_value(base, pct):
        """Проценты в данных можно писать как 0.04 или как 4 — обе формы дают 4%."""
        pct = float(pct)
        return base * (pct / 100.0 if pct > 1.0 else pct)

    def _env_amount(self, u, cfg):
        """Урон среды: фиксированный процент от максимума HP цели (старый dps — запасной вариант)."""
        if cfg.get("dps_pct") is not None:
            return max(0.0, self._pct_value(u.max_hp, cfg["dps_pct"]))
        return float(cfg.get("dps", 0))

    def _dot_mult(self, tag, attacker):
        if attacker is None:
            return 1.0
        mult = getattr(attacker, "dot_mult", 1.0)
        mult *= getattr(attacker, "dot_%s_mult" % tag, 1.0)
        mult *= attacker.buff("dot_power", 1.0)
        return mult

    def _dot_dps(self, tag, attacker, hit):
        """Сила дот-эффекта: прямой удар — процент от нанесённого урона, чистое наложение — сила навыков."""
        cfg = self._dot_cfg(tag)
        if hit and hit > 0:
            dps = float(hit) * cfg.get("hit_pct", 0.0)
        else:
            power = attacker.power if attacker is not None else 1.0
            atk = attacker.atk_damage if attacker is not None else 0.0
            dps = max(float(cfg.get("spell_base", 0.0)) * power, float(atk) * cfg.get("atk_pct", 0.0))
        return max(float(cfg.get("min", 0.0)), dps)

    def _dot_heal_mult(self, u, tag, dot):
        cfg = self._dot_cfg(tag)
        if tag == "poison":
            per = cfg.get("heal_mult_per_stack", 0.0)
            low = cfg.get("heal_mult_min", 0.0)
            base = cfg.get("heal_mult", self.tags.get(tag, {}).get("heal_mult", 1.0))
            return max(low, base - per * max(0, dot.get("stacks", 1) - 1))
        return cfg.get("heal_mult", self.tags.get(tag, {}).get("heal_mult", 1.0))

    def _mirror_bleed(self, u, dot):
        """Совместимость со старыми проверками/UI: кровотечение остаётся видно и как бафф."""
        if dot is None:
            u.buffs.pop("bleed", None)
            u.buff_total.pop("bleed", None)
            return
        u.buffs["bleed"] = [round(dot["dps"] * dot["stacks"], 3), dot["left"]]
        u.buff_total["bleed"] = dot["total"]

    def _clear_dot(self, u, tag):
        u.dots.pop(tag, None)
        u.statuses.pop(tag, None)
        if tag == "bleed":
            self._mirror_bleed(u, None)

    def _sync_dots(self, u):
        """Подхватить прямые записи в statuses (тесты, старые эффекты) и убрать осиротевшие доты."""
        for tag in list(u.dots):
            if tag not in u.statuses:
                u.dots.pop(tag, None)
                if tag == "bleed":
                    self._mirror_bleed(u, None)
        for tag in DOT_TAGS:
            left = u.statuses.get(tag)
            if left is None or left <= 0 or tag in u.dots:
                continue
            cfg = self._dot_cfg(tag)
            dps = float(cfg.get("env_dps", self.tags.get(tag, {}).get("dps", 0.0)))
            # Прямая запись в statuses — старый/ручной путь: сохраняем прежний dps,
            # процентный урон среды создаётся через apply_status/_touch_status.
            u.dots[tag] = {"tag": tag, "stacks": 1, "dps": dps, "dps_pct": None,
                           "left": float(left), "total": float(left), "src": None,
                           "damage_type": cfg.get("damage_type", tag), "acc": 0.0}
            if tag == "bleed":
                self._mirror_bleed(u, u.dots[tag])

    def _burst_bleed(self, u, dot, attacker):
        cfg = self._dot_cfg("bleed")
        total_dps = dot["dps"] * dot["stacks"]
        burst = total_dps * cfg.get("burst_mult", 2.0)
        if cfg.get("burst_pct"):
            burst = max(burst, self._pct_value(u.max_hp, cfg["burst_pct"]))
        self.emit("bleed_burst", unit=u, amount=burst, stacks=dot["stacks"])
        self._clear_dot(u, "bleed")
        if burst > 0 and u.alive:
            self.damage(u, burst, attacker or dot.get("src"), kind="dot",
                        dtype=cfg.get("damage_type", "physical"))
        self.log(f"{u.name}: кровотечение прорывается ({int(round(burst))})", (220, 70, 80))

    def apply_dot(self, u, tag, dps, duration=None, attacker=None, stacks=1, add_stack=True,
                  damage_type=None, dps_pct=None):
        """Наложить/обновить дот. dps — сила одной единицы (стака) в секунду до множителей владельца.
        dps_pct — для дотов среды: доля максимума HP в секунду (тогда dps не используется)."""
        if not u.alive or u.obj or self.immune(u, tag):
            return 0
        cfg = self._dot_cfg(tag)
        if not cfg:
            return 0
        duration = float(duration if duration is not None else cfg.get("duration", self.cfg["status_duration"]))
        if attacker is not None:
            duration *= getattr(attacker, "dot_duration_mult", 1.0)
        dps = max(0.0, float(dps) * self._dot_mult(tag, attacker) * getattr(u, "dot_taken", 1.0))
        if dps_pct is not None:
            dps = 0.0
        max_stacks = max(1, int(cfg.get("stacks", 1)))
        old = u.dots.get(tag)
        if old is None:
            dot = {"tag": tag, "stacks": min(max_stacks, max(1, stacks)), "dps": dps, "dps_pct": dps_pct,
                   "left": duration, "total": duration, "src": attacker,
                   "damage_type": damage_type or cfg.get("damage_type", tag), "acc": 0.0}
            u.dots[tag] = dot
            u.statuses[tag] = duration
            self.emit("status", unit=u, tag=tag, stacks=dot["stacks"], dps=dot["dps"])
            self.rules.fire("status", {"element", tag, *self.tags.get(tag, {}).get("groups", [])},
                            unit=u, source=attacker)
        else:
            if add_stack:
                old["stacks"] = min(max_stacks, old["stacks"] + max(1, stacks))
            else:
                old["stacks"] = max(old["stacks"], min(max_stacks, max(1, stacks)))
            old["dps"] = max(old["dps"], dps)          # сильнейшее наложение обновляет силу
            if dps_pct is not None:
                old["dps_pct"] = max(old.get("dps_pct") or 0.0, dps_pct)
            old["left"] = max(old["left"], duration)
            old["total"] = max(old["total"], old["left"])
            if attacker is not None:
                old["src"] = attacker
            if damage_type:
                old["damage_type"] = damage_type
            u.statuses[tag] = old["left"]
            self.emit("status_refresh", unit=u, tag=tag, stacks=old["stacks"], dps=old["dps"])
            dot = old
        if tag == "bleed":
            self._mirror_bleed(u, dot)
            if dot["stacks"] >= max_stacks:
                self._burst_bleed(u, dot, attacker)
        return dot["dps"] * dot["stacks"]

    def _refresh_dot(self, u, tag, duration=None):
        dot = u.dots.get(tag)
        if dot is None:
            return False
        duration = float(duration if duration is not None else self.cfg["status_duration"])
        dot["left"] = max(dot["left"], duration)
        dot["total"] = max(dot["total"], dot["left"])
        u.statuses[tag] = dot["left"]
        if tag == "bleed":
            self._mirror_bleed(u, dot)
        return True

    def _tick_dots(self, u, dt):
        self._sync_dots(u)
        for tag, dot in list(u.dots.items()):
            if not u.alive:
                break
            if self.immune(u, tag):
                self._clear_dot(u, tag)
                continue
            dot["left"] -= dt
            dot["acc"] += dt
            while dot["acc"] >= 1.0 and u.alive:
                dot["acc"] -= 1.0
                amount = dot["dps"] * dot["stacks"]
                if dot.get("dps_pct"):
                    amount += self._pct_value(u.max_hp, dot["dps_pct"]) * dot["stacks"]
                self.damage(u, amount, dot.get("src"), kind="dot",
                            dtype=dot.get("damage_type", tag))
            if dot["left"] <= 0:
                self._clear_dot(u, tag)
            else:
                u.statuses[tag] = dot["left"]
                if tag == "bleed":
                    self._mirror_bleed(u, dot)

    # ---------- исполнение приказов ----------

    def _execute_order(self, u):
        if u.queue:                           # приказ выполнен — следующий из очереди
            self._advance_queue(u)
        o = u.order
        if o is None and u.last_target is not None and not u.last_target.alive:
            # юнит дрался сам (без приказа) и добил цель — не стоит, а идёт к следующей
            u.last_target = None
            self._retarget(u)
            o = u.order
        if o is None and not u.static and (u.charmed or self._free_minion(u)):
            self._retarget(u)                 # зачарованный и призванный без приказа — сами к ближайшему врагу
            o = u.order
        if o is None or (u.static and o["type"] != "skill"):
            self._auto_attack(u)
            return
        tgt = o.get("target")
        if isinstance(tgt, Unit) and tgt.alive and u.is_enemy(tgt) and not self.visible(tgt):
            self._retarget(u)                         # цель ушла в тень — ищем другую
            return
        if o["type"] == "path":
            self._walk_path(u, o)
            return
        if o["type"] == "move":
            goal = o["cell"]
            if u.cell == goal or (self.unit_at(goal) and cheb(u.cell, goal) <= 1):
                u.order = None
            elif not self._step_toward(u, goal, 0):
                u.order = None
        elif o["type"] == "attack":
            t = o["target"]
            if not t.alive:
                self._retarget(u)
                t = u.order["target"] if u.order else None
            if t is None:
                return
            if cheb(u.cell, t.cell) <= self.reach(u):
                self._basic_attack(u, t)
            elif not self._step_toward(u, t.cell, self.reach(u)):
                u.wait = 0.3
        elif o["type"] == "skill":
            sid, target = o["skill"], o["target"]
            sk = u.skill_defs[sid]
            if isinstance(target, Unit) and not target.alive:
                then = o.get("then")
                if then and then.alive:
                    u.order = {"type": "attack", "target": then}
                else:
                    self._retarget(u)
                return
            center = target.cell if isinstance(target, Unit) else target
            if cheb(u.cell, center) <= sk["range"]:
                if o.get("auto") and not autocast.cell_safe(self, u, sk, target):
                    then = o.get("then")
                    u.order = {"type": "attack", "target": then} if then and then.alive else None
                elif u.skill_ready(sid, sk):
                    self._start_cast(u, sid, target)
            elif not self._step_toward(u, center, sk["range"]):
                u.wait = 0.3

    def _walk_path(self, u, o):
        """Шаг по маршруту игрока. Занято юнитом — ждём; ждём долго или сбили с пути — обходим до следующей точки."""
        cells = o["cells"]
        while cells and cells[0] == u.cell:
            cells.pop(0)
        if not cells:
            u.order = None
            return
        nxt = cells[0]
        if cheb(u.cell, nxt) > 1 or not self.grid.passable(nxt, u.flying):
            if not self._step_toward(u, nxt, 0):           # сдвинули толчком — возвращаемся на маршрут
                u.order = None
            return
        if self.is_free(nxt, flying=u.flying):
            o["stuck"] = 0.0
            self._step(u, nxt)
            return
        o["stuck"] += 0.25
        u.wait = 0.25
        if o["stuck"] >= 1.5:                              # проход перекрыт надолго — в обход
            o["stuck"] = 0.0
            goal = cells[-1]
            if not self._step_toward(u, goal, 0):
                u.order = None

    def _step(self, u, dest):
        """Один шаг на соседнюю клетку: длительность — по цене клетки (вода, лава, терновник…)."""
        prev = u.cell
        dur = u.move_time * u.slow_mult(self.tags) * u.buff("slow", 1.0) * M.step_cost(self, u, dest)
        self._place(u, dest, dur)
        self._after_step(u, prev)
        self._zone_of_control(u, prev)

    def _step_toward(self, u, target_pos, rng):
        """Один шаг к клетке, с которой target_pos в пределах rng. False — пути нет вообще."""
        occ = self.occupied(exclude=u)
        h = lambda p: max(0, cheb(p, target_pos) - rng)
        if u.static:
            u.order = None
            return False
        fly = u.flying
        pen = None if fly else (lambda p: self._danger(u, p) + M.step_cost(self, u, p) - 1.0)
        path = self.grid.find_path(u.cell, lambda p: h(p) == 0 and p not in occ, h, occ, fly, pen)
        if path is None:
            # проход перекрыт юнитами: идём по пути «сквозь них» и ждём, когда освободится (объекты сами не уйдут)
            walls = {o.cell for o in self.units if o.alive and o.obj}
            path = self.grid.find_path(u.cell, lambda p: h(p) == 0 and p not in walls, h, walls, fly, pen)
            if not path:
                return False
            if path[0] in occ:
                u.wait = 0.25
                return True
        if path:
            self._step(u, path[0])
        return True

    def _place(self, u, dest, dur):
        u.prev_cell = u.cell
        u.cell = tuple(dest)
        u.move_t = 0.0
        u.move_dur = max(dur, 0.01)
        if not u.obj and u.prev_cell != u.cell:
            self._check_watch(u)

    def _check_watch(self, u):
        """Дозор: враг вошёл в зону (шагом, толчком, прыжком) — дозорный стреляет с крит-уроном."""
        for w in self.units:
            wt = w.watch
            if not wt or not w.alive or w.stun > 0 or not w.is_enemy(u) or not self.visible(u):
                continue
            inside = cheb(u.cell, wt["center"]) <= wt["radius"]
            was = cheb(u.prev_cell, wt["center"]) <= wt["radius"]
            if inside and not was:
                wt["shots"] -= 1
                if wt["shots"] <= 0:
                    w.watch = None
                self.emit("watch_fire", unit=w, dst=u)
                self.emit("attack", src=w, dst=u, kind="ranged", tag=wt.get("tag"))
                self.log(f"{w.name}: дозор — выстрел по {u.name}", (255, 220, 140))
                self.damage(u, w.atk_damage * wt["mult"] * w.power, w, wt.get("tag"), "ranged")
                if u.alive and wt.get("stun"):
                    self.apply_stun(u, wt["stun"], "stun")
                return

    def is_free(self, pos, exclude=None, flying=False):
        pos = tuple(pos)
        return self.grid.passable(pos, flying) and self.unit_at(pos) in (None, exclude)

    def immune(self, u, tag):
        """Не горит/не мокнет от клеток и статуса: полное сопротивление или любовь к жару для огня."""
        return tag is not None and (u.resist.get(tag, 1.0) == 0 or (tag == "fire" and bool(u.heat)))

    def _danger(self, u, p):
        """Цена опасной клетки для пути: лава и урон клетки (кроме тех, кому он не страшен)."""
        c = self.grid.cells[p]
        t = self.cfg["terrain"][c.terrain]
        if (t.get("dps") or t.get("dps_pct")) and not self.immune(u, t.get("status")):
            return 5.0
        if c.hazard:
            h = self.cfg["hazards"][c.hazard]
            if h.get("trigger") and c.hazard_team not in (None, u.team) and not h.get("hidden"):
                return 6.0                       # спрятанный капкан враг не видит и не обходит
            if (h.get("dps") or h.get("dps_pct")) and not self.immune(u, h.get("status")) and \
                    not (h.get("foes_only") and c.hazard_team in (None, u.team)):
                return 3.0
        return 0.0

    def _after_step(self, u, prev):
        """Шаг закончился на особой клетке: скользкий лёд тащит дальше, портал переносит."""
        if u.flying:
            return
        c = self.grid.get(u.cell)
        if c.terrain == "ice_floor" and not u.ice_walker:
            d = (u.cell[0] - prev[0], u.cell[1] - prev[1])
            n = (u.cell[0] + d[0], u.cell[1] + d[1])
            if self.is_free(n):
                u.cell = n
                u.move_dur *= 1.7
                self.emit("slide", unit=u)
                c = self.grid.get(u.cell)
        if c.portal:
            exit_ = self.grid.portal_pair.get(u.cell)
            if exit_ and self.is_free(exit_):
                self.emit("portal", unit=u, src=u.cell, dst=exit_)
                u.cell = u.prev_cell = exit_
                u.move_t = 1.0

    def _fall(self, u):
        """Сброшен в пропасть: враг гибнет, герой теряет 40% HP и выкарабкивается, объект пропадает."""
        if u.obj:
            self.emit("fall", unit=u)
            u.igniter = None
            u.alive, u.hp = False, 0
            self.log(f"{u.name} падает в пропасть", (200, 200, 255))
            return
        if u.boss or u.flying or u.static:
            return
        self.emit("fall", unit=u)
        if u.team == ENEMY or u.summon:
            self.log(f"{u.name} падает в пропасть", (200, 200, 255))
            self._kill(u)
        else:
            self.log(f"{u.name} срывается и выкарабкивается", (255, 200, 150))
            self.damage(u, u.max_hp * 0.4, None, kind="reaction")

    def _free_minion(self, u):
        """Призванный боец отряда (скелет, нежить, иллюзия): ходит и бьёт сам, если игрок не дал приказ."""
        return u.summon and u.owner is not None and u.team == PLAYER and not u.obj

    def _retarget(self, u):
        """Цель атаки погибла — переключаемся на ближайшего живого врага (при равенстве — на раненого)."""
        foes = self.foes_of(u)
        if u.taunted_by in foes:
            t = u.taunted_by
        elif foes:
            t = min(foes, key=lambda f: (cheb(u.cell, f.cell), f.hp))
        else:
            t = None
        u.order = {"type": "attack", "target": t} if t else None

    def _auto_attack(self, u):
        foes = [f for f in self.foes_of(u) if cheb(u.cell, f.cell) <= self.reach(u)]
        if not foes:
            return
        if u.taunted_by in foes:
            t = u.taunted_by
        elif u.last_target in foes:
            t = u.last_target
        else:
            t = min(foes, key=lambda f: (cheb(u.cell, f.cell), f.hp))
        self._basic_attack(u, t)

    def _basic_attack(self, u, t):
        if u.attack_timer > 0:
            return
        if PS.kind(u) == "commander":         # тактик сам не бьёт: приказывает союзнику ударить цель
            u.attack_timer = u.atk_cd * u.buff("atk_speed", 1.0)
            u.last_target = t
            kit.command(self, u, t)
            return
        kind = u.atk_kind or ("melee" if u.atk_range <= 1 else "ranged")
        u.attack_timer = u.atk_cd * u.slow_mult(self.tags) * u.buff("atk_speed", 1.0) * PS.atk_cd_mult(self, u)
        u.last_target = t
        tag = u.buff("atk_tag", None) or u.atk_tag          # ядовитый клинок и т.п. — тег на время
        amount = u.atk_damage * u.buff("atk_mult", 1.0) * self._reveal(u) * self.blood_mult(u)
        p = u.passive
        if p and p["kind"] == "backstab" and u.pp >= p["pp"] and self.exposed(t, u):
            self._use_passive(u, f"урон ×{p['mult']:g}", t)
            amount *= p["mult"]
        h = self.cfg.get("hit") if self.hit_timing else None
        flight = 0.0
        if h:
            if kind == "melee":
                flight = h["attack_melee"]
            else:
                sp = h["attack_speed"]
                speed = sp.get(u.proto_id) or sp.get("ranged" if u.role == "ranged" else "spell", 10.0)
                flight = round(min(h["max"], max(0.06, cheb(u.cell, t.cell) / speed)), 2)
        self.emit("attack", src=u, dst=t, kind=kind, tag=tag, hit=flight)

        if flight > 0:                         # снаряд в полёте — данными, не замыканием: бой можно копировать
            self.delayed.append({"left": flight, "total": flight, "basic": (u, t, amount, tag, kind), "tunit": None})
        else:
            self._land_basic(u, t, amount, tag, kind)
        u.ambush = 1.0

    def _land_basic(self, u, t, amount, tag, kind):
        """Обычная атака долетела (или ударила вплотную)."""
        if not t.alive:
            return
        self._basic = True
        try:
            dealt = self.damage(t, amount, u, tag, kind)
        finally:
            self._basic = False
        if dealt and (u.quivers or u.owner is not None or "fletch" in u.buffs):
            kit.basic_rider(self, u, t)
        if u.lifesteal and dealt and u.alive:
            self.heal(u, int(round(dealt * u.lifesteal)))

    def _start_cast(self, u, sid, target):
        sk = u.skill_defs[sid]
        o = u.order if u.order and u.order["type"] == "skill" else {}
        auto = o.get("auto", False)
        u.ap -= sk["ap"]
        if sk.get("hp_cost"):                  # берсерк крови платит здоровьем
            cost = min(sk["hp_cost"], u.hp - 1)
            u.hp -= cost
            self.emit("damage", unit=u, amount=cost, absorbed=0, kind="hp_cost", tag=None, cover=False, blocked=None)
            self.gain(u, "blood")
        if sk["cooldown"]:
            u.cooldowns[sid] = sk["cooldown"]
        then = o.get("then")
        if then and then.alive:
            u.order = {"type": "attack", "target": then}
        elif then:
            self._retarget(u)
        else:
            u.order = None
        if sk["cast"] <= 0:
            self._resolve_skill(u, sid, target, auto)
            return
        u.cast = {"skill": sid, "target": target, "left": sk["cast"], "total": sk["cast"], "ap": sk["ap"],
                  "auto": auto}
        self.emit("cast_start", unit=u, skill=sid)

    HIT_TIMING = True

    # мгновенные навыки: двигают самого героя или ставят что-то на поле — никакого полёта
    INSTANT = {"teleport", "leap_to", "rush", "swap", "form", "stealth", "place_object", "wall", "trap", "watch",
               "song", "toss", "gather", "regroup", "merge", "tether", "terrain_cast", "focus", "rewind", "delay",
               "fuse", "extra_attack", "detonate", "spread_fire", "guard", "summon", "revive", "corpse"}

    def hit_delay(self, u, sid, sk, center, tunit):
        """Через сколько секунд навык попадает (config.hit, tools/hit_timing.py): снаряд летит, метеор падает,
        площадь вспыхивает после метки. 0 — сразу (рывки, призывы, постройки)."""
        h = self.cfg.get("hit")
        if not h or not self.hit_timing:
            return 0.0
        types = {e["type"] for e in sk["effects"]}
        table = h["skills"]
        br = sk.get("branch")
        e = table.get(f"{sid}:{br[0]}") if br else None
        e = e or table.get(sid) or {"mode": "rule"}
        mode = e["mode"]
        if mode == "time" and types & {"teleport", "leap_to"}:      # прыжок: в воздухе до приземления
            u.airborne = e["time"]
            return e["time"]
        if types & self.INSTANT or mode == "instant":
            return 0.0
        dist = cheb(u.cell, tuple(center))
        if sk["target"] in ("enemy", "cell") and any(x.get("arrow") for x in sk["effects"])                 and not types & {"zone", "teleport"}:      # выстрел лучника — со скоростью обычной стрелы
            sp = h["attack_speed"]
            speed = sp.get(u.proto_id) or sp.get("ranged", 13.0)
            return round(min(h["max"], max(0.06, dist / speed)), 2)
        if mode == "fly":
            return round(min(h["max"], max(e.get("min", h["min"]), max(1, dist) / e["speed"])), 2)
        if mode in ("fall", "time"):
            return e["time"]
        if sk["target"] == "self" or dist <= 1:
            hits = types & {"damage", "stun", "knockback", "push", "pull", "line", "chain", "status", "sleep"}
            return h["swing"] if hits else 0.0
        if sk["target"] == "ally":
            return h["ally"]
        return h["area"]

    def _resolve_skill(self, u, sid, target, auto=False):
        sk = u.skill_defs[sid]
        if sk["target"] == "self":
            center, tunit = u.cell, u
        elif isinstance(target, Unit):
            if not target.alive:
                self.emit("fizzle", unit=u, skill=sid)
                return
            center, tunit = target.cell, target
        else:
            center, tunit = tuple(target), None
        hit = self.hit_delay(u, sid, sk, center, tunit)
        spent = kit.spend(self, u, sk)
        u.uses[sid] = u.uses.get(sid, 0) + 1
        if not sk.get("ult"):
            self.gain(u, "skill")
        self.emit("skill", unit=u, skill=sid, center=center, target=tunit, auto=auto, hit=hit)
        for a in self.units:             # ноты барда: навык союзника рядом
            if a is not u and a.alive and a.gauge and a.team == u.team and cheb(a.cell, u.cell) <= 3:
                self.gain(a, "ally_skill")
            if a is not u and a.alive and a.song and a.team == u.team and cheb(a.cell, u.cell) <= a.song["radius"]:
                a.song["notes"] += 1
                self.emit("note", unit=a, src=u)
        self.rules.fire("cast", {"cast", sid} | {e["kind"] for e in sk["effects"] if e.get("kind")}, unit=u, source=u)
        suffix = " (авто)" if auto else ""
        self.log(f"{u.name}: {sk['name']}{suffix}", (230, 230, 160) if u.team == PLAYER else (230, 170, 160))
        if autocast.hits_enemies(sk):
            self._reveal(u)
        effects = sk["effects"]
        pm = PS.powder_mult(self, u, sk)
        if pm is not None:                    # заряд с Порохом — ×2, без — ×0.6
            effects = [dict(e, _powder=pm) for e in effects]
        if spent or u.ambush > 1.0:           # потраченная шкала и удар из тени — в эффекты (урон по прилёте)
            effects = [dict(e, _spent=spent, _shadow=u.ambush) for e in effects]
        if hit > 0:                           # эффекты — по прилёте (_delayed_update)
            self.delayed.append({"left": hit, "total": hit, "caster": u, "effects": effects,
                                 "center": tuple(center), "tunit": tunit, "name": sk["name"], "skill": sid})
        else:
            self._skill = sid                 # вид контроля зависит от навыка (корни, сеть, лёд — config.control_looks)
            self.apply_effects(u, effects, center, tunit)
            self._skill = None
        u.ambush = 1.0
        p = u.passive
        if p and p["kind"] == "encore" and u.pp >= p["pp"] and sk["ap"] >= p.get("min_ap", 3):
            self._use_passive(u, f"+{p['ap']} AP")
            u.ap = min(u.ap_max, u.ap + p["ap"])

    # ---------- эффекты ----------

    def apply_effects(self, caster, effects, center, tunit=None):
        prev = self._actor
        self._actor = self.credit(caster)
        try:
            self._apply_effects(caster, effects, center, tunit)
        finally:
            self._actor = prev

    def stat_k(self, u, of, pct=False):
        """Навык героя растёт от своего стата (sim/stats.py STAT_BASES): множитель вместо силы навыков."""
        ref = u.proto.get("ref") or {"atk": max(1, u.proto["attack"]["damage"]), "hp": max(1, u.proto["hp"])}
        if of == "atk":
            v = u.atk_damage * (u.proto.get("scale") or {}).get("basic", 1.0) * u.buff("atk_mult", 1.0)
            return v if pct else v / ref.get("atk", 1)
        if of == "hp":
            return u.max_hp if pct else u.max_hp / ref.get("hp", 1)
        k = getattr(u, "_pw_base", u.power) * (u.proto.get("scale") or {}).get("spell", 1.0)
        return k * ref.get("atk", 1) if pct else k

    def _apply_effects(self, caster, effects, center, tunit=None):
        for eff in effects:
            of = eff.get("of")
            if of and (caster.proto.get("ref") or eff.get("pct")):   # числа навыка — от стата героя
                outer = hasattr(caster, "_pw_base")
                if not outer:
                    caster._pw_base = caster.power
                flat = self._flat
                caster.power = self.stat_k(caster, of, eff.get("pct")) * caster.buff("skill_mult", 1.0)
                self._flat = True
                try:
                    stop = self._apply_eff(caster, eff, center, tunit)
                finally:
                    self._flat = flat
                    caster.power = caster._pw_base
                    if not outer:
                        del caster._pw_base
            else:
                stop = self._apply_eff(caster, eff, center, tunit)
            if stop:
                return

    def _apply_eff(self, caster, eff, center, tunit):
        """Один эффект навыка. True — навык сорвался (дальше эффекты не применять)."""
        t = eff["type"]
        if eff.get("at") == "caster":
            if t in kit.TYPES:
                kit.special(self, caster, eff, caster.cell, caster)
            elif t == "summon":
                self.summon(caster, eff, caster.cell)
            else:
                self._apply_one(caster, eff, caster.cell, None)
            return
        if t in kit.TYPES:
            kit.special(self, caster, eff, center, tunit)
            return
        if t in ("delay", "rush", "toss", "fuse", "place_object", "watch", "detonate", "song", "trap", "wall",
                 "terrain", "shatter", "corpse", "rewind", "stasis", "spread_fire", "gather", "swap",
                 "levitate", "collapse", "terrain_cast", "reagent", "extra_attack", "regroup", "focus", "tether",
                 "merge", "life_transfer"):
            self._special(caster, eff, center, tunit)
            return
        if t == "teleport":
            if not self.is_free(center, exclude=caster):
                spot = self.free_near(center, 1) if caster.airborne <= 0.05 else None
                if spot is None or spot == caster.cell:      # клетку заняли, пока летел — рядом
                    self.emit("fizzle", unit=caster, skill=None)
                    return True
                center = spot
            self._place(caster, center, 0.12)
            return
        if t == "leap_to":
            if tunit is None or not self._leap_next_to(caster, tunit):
                self.emit("fizzle", unit=caster, skill=None)
                return True
            return
        if t == "line":
            for v in self._line_victims(caster, center, eff["length"]):
                self._hit(caster, v, eff)
                if eff.get("push") and v.alive:      # разлом тарана: каждого задетого — толчком от себя
                    self.knockback(caster.cell, v, eff["push"], caster)
            return
        if t == "chain":
            self._chain(caster, tunit or self.unit_at(center), eff)
            return
        if t == "transfer_statuses":
            if tunit is not None:
                self._transfer_statuses(caster, tunit, eff)
            return
        if t == "summon":
            self.summon(caster, eff, center)
            return
        if t == "form":
            self.set_form(caster, eff.get("form"))
            return
        if t == "revive":
            self.revive(caster, eff, center)
            return
        self._apply_one(caster, eff, center, tunit)

    def _apply_one(self, caster, eff, center, tunit):
        t = eff["type"]
        r = eff.get("radius", 0)
        if t == "cell_tag":
            for p in self.grid.in_radius(center, r):
                self._cell_tag(p, eff["tag"])
            return
        if t == "hazard":
            for p in self.grid.in_radius(center, r):
                c = self.grid.get(p)
                if c.passable and c.terrain != "water":
                    if eff["hazard"] != "fire" or c.hazard != "oil":
                        c.hazard, c.hazard_time = eff["hazard"], eff["duration"]
                    c.hazard_team = caster.team
                    if eff["hazard"] == "mine":
                        c.hazard_owner, c.mine_mult = caster, eff.get("_powder", 1.0)
                        c.charge = None
                        if eff.get("blast"):       # мина героя: урон — % силы навыков на момент установки
                            c.charge = {"dmg": eff["blast"] * self.stat_k(caster, "sp", True) * eff.get("_powder", 1.0),
                                        "r": eff.get("blast_r", 0), "stun": eff.get("stun")}
                    if eff["hazard"] == "fire":
                        self._cell_tag(p, "fire")        # огонь по маслу — вспышка
            return
        if t == "taunt":
            for v in self._select(caster, caster.cell, r, "enemies", None):
                v.taunted_by, v.taunt_time = caster, eff["duration"]
                v.ai_timer = 0.0
                caster.tally["taunts"] += 1
                self.emit("taunt", unit=v, src=caster)
            return
        default = "enemies" if t in ("damage", "stun", "knockback", "status", "sleep", "pull", "charm") else "allies"
        for v in self._select(caster, center, r, eff.get("affects", default), tunit):
            if v.obj and t not in ("damage", "knockback", "heal", "shield", "push", "pull"):
                continue                       # бочку не оглушить и не усилить
            if eff.get("if_mark") and eff["if_mark"] not in v.marks:
                continue                       # только по меченым (вызов, холод, бомба)
            if eff.get("if_held") and not kit.held(v):
                continue
            if t == "damage":
                self._hit(caster, v, eff)
            elif t == "heal":
                if eff.get("pct"):                 # лечение в процентах от HP цели
                    amount = int(round(v.max_hp * eff["pct"] * PS.heal_mult(self, caster)))
                else:
                    hs = 1.0 if self._flat else caster.proto.get("scale", {}).get("heal", 1.0)
                    amount = int(round(eff["amount"] * caster.power * hs * PS.heal_mult(self, caster)))
                real = self.heal(v, amount, caster)
                if real > 0 and v is not caster:
                    self.gain(caster, "heal_given")
                    PS.on_heal_given(self, caster)
                excess = amount - real
                if eff.get("overheal_shield") and excess > 0 and v.alive:
                    v.shield += excess
                    v.shield_time = max(v.shield_time, 6.0)
                    v.shield_src = self.credit(caster)
                    self.emit("shield", unit=v, amount=excess)
            elif t == "shield":
                hs = 1.0 if self._flat else caster.proto.get("scale", {}).get("heal", 1.0)
                amount = int(round(eff["amount"] * caster.power * hs))
                v.shield, v.shield_time = amount, eff["duration"]
                v.shield_src = self.credit(caster)
                self.emit("shield", unit=v, amount=amount)
            elif t == "buff":
                val = eff["value"]
                if self._flat and eff["stat"] in ("regen", "bleed") and isinstance(val, (int, float)):
                    val = round(val * caster.power, 2)        # реген и кровотечение навыка — от стата героя
                self.add_buff(v, eff["stat"], val, eff["duration"])
            elif t == "stun":
                self.apply_stun(v, eff["duration"], eff.get("look") or self.cfg["control_looks"].get(self._skill))
            elif t == "knockback":
                self.knockback(caster.cell, v, eff.get("cells", 1), caster)
            elif t == "push":                  # пинок тарана: свой, чужой или объект — всех толкает
                if v is caster:
                    continue
                if caster.is_enemy(v) and not v.obj and eff.get("amount"):
                    self._hit(caster, v, dict(eff, kind="melee"))
                if v.alive:
                    src = tuple(center) if eff.get("from") == "center" and v.cell != tuple(center) else caster.cell
                    if v.cell == src:
                        src = caster.cell if v.cell != caster.cell else tuple(center)
                    self.knockback(src, v, eff.get("cells", 2), caster)
            elif t == "guard":                 # под защиту: удары по союзнику рядом с воином принимает воин
                if v is not caster:
                    v.guarded_by, v.guard_time = caster, eff["duration"]
                    self.emit("guard", unit=v, src=caster)
            elif t == "cleanse":
                self.cleanse(v, eff.get("tags"), caster)
            elif t == "status":
                self._touch_status(v, eff["tag"], caster)
            elif t == "sleep":
                self.apply_stun(v, eff["duration"], "sleep")
                v.asleep = v.alive
                self.emit("sleep", unit=v)
            elif t == "pull":
                self.pull(caster, v, eff.get("cells", 1))
            elif t == "refresh":
                v.ap = min(v.ap_max, v.ap + eff.get("ap", 0))
                if eff.get("cooldowns") and v is not caster:      # себе перезарядки не сбросить
                    v.cooldowns.clear()
                self.emit("refresh", unit=v, ap=eff.get("ap", 0))
            elif t == "charm":
                if v.boss or v.summon:
                    continue
                self._interrupt(v)
                v.charm_time = eff["duration"]
                v.order = None
                v.last_target = None
                self.emit("charm", unit=v, src=caster)
                self.log(f"{v.name} очарован(а)!", (255, 150, 220))
            elif t == "stealth":
                self.add_buff(v, "stealth", eff.get("mult", 1.5), eff["duration"])
                for f in self.units:                 # кто целился в него — теряет цель
                    if f.alive and f.is_enemy(v) and f.order and f.order.get("target") is v:
                        f.order = None
                    if f.last_target is v:
                        f.last_target = None

    def _hit(self, caster, v, eff):
        """Урон навыка: казнь, удар в спину, вампиризм, бафф/дебафф на цель."""
        amount = eff["amount"] * caster.power * max(caster.ambush, eff.get("_shadow", 1.0)) * self.blood_mult(caster)
        amount *= kit.hit_mult(self, caster, v, eff)
        bs = eff.get("backstab")
        if bs and self.exposed(v, caster):
            amount *= bs
            self.emit("backstab", unit=v, src=caster)
        ex = eff.get("execute")
        if ex and v.hp < v.max_hp * ex["below"]:
            amount *= ex["mult"]
            self.emit("execute", unit=v)
        dealt = self.damage(v, amount, caster, eff.get("tag"), eff.get("kind", "spell"))
        ok = eff.get("on_kill")
        if ok and not v.alive and caster.alive:     # «Охотник за головами»: убил — AP и сброс перезарядки
            caster.ap = min(caster.ap_max, caster.ap + ok.get("ap", 0))
            if ok.get("reset"):
                caster.cooldowns.pop(ok["reset"], None)
            self.emit("refresh", unit=caster, ap=ok.get("ap", 0))
        if eff.get("lifesteal") and dealt and caster.alive:
            self.heal(caster, int(round(dealt * eff["lifesteal"])))
        p = caster.passive
        if p and p["kind"] == "siphon" and dealt and caster.alive and caster.pp >= p["pp"]:
            self._use_passive(caster, f"+{round(dealt * p['pct'])} HP")
            self.heal(caster, int(round(dealt * p["pct"])))
        ob = eff.get("on_hit_buff")
        if ob and v.alive:
            self.add_buff(v, ob["stat"], ob["value"], ob["duration"])
        kit.after_hit(self, caster, v, eff, dealt)
        return dealt

    def blood_mult(self, u):
        """Берсерк крови: до +blood_rage урона при HP у нуля."""
        k = u.proto.get("blood_rage")
        return 1.0 + k * (1 - u.hp / max(1, u.max_hp)) if k else 1.0

    def add_buff(self, u, stat, value, duration, src=None):
        if stat == "bleed":                       # кровотечение — дот со стаками, а не обычный бафф
            return self.apply_dot(u, "bleed", value, duration, attacker=src or self._actor)
        fresh = u.buffs.get(stat, [None])[0] != value     # продление того же баффа (аура знамени) — без надписи
        u.buffs[stat] = [value, duration]
        if stat == "silence" and u.cast is not None:      # безмолвие сбивает каст
            self._interrupt(u)
        u.buff_total[stat] = duration         # для таймера на значке
        a = self._actor
        if fresh and a is not None and a is not u:
            a.tally["buffs" if a.team == u.team else "debuffs"] += 1
        self.emit("buff", unit=u, stat=stat, value=value, fresh=fresh)

    def exposed(self, v, attacker):
        """Цель «открыта для удара в спину»: оглушена или смотрит не на атакующего."""
        if v.stun > 0 or "exposed" in v.buffs:
            return True
        focus = v.order.get("target") if v.order and v.order["type"] in ("attack", "skill") else v.last_target
        return focus is not attacker

    def _reveal(self, u):
        """Атака из тени: скрытность снимается, удар получает множитель засады. Возвращает множитель."""
        if "stealth" in u.buffs:
            u.ambush = u.buff("stealth", 1.5)
            del u.buffs["stealth"]
            self.emit("reveal", unit=u)
        return u.ambush

    def group_limit(self, caster, group):
        """Сколько призванных группы (тотемов) держит герой: по уровню (config.summon_groups) + вещи."""
        lvl = caster.proto.get("level", 1)
        return max(n for lv, n in self.cfg["summon_groups"][group] if lvl >= lv)             + int(caster.proto.get("totem_limit_add", 0))

    def totem_use(self, s):
        """Польза тотема сейчас: сколько целей в его зоне (боевой — врагов, бафающий/лечащий — союзников)."""
        aura = s.aura or {}
        r = aura.get("radius") or s.atk_range or 2
        effs = aura.get("effects", [])
        hostile = s.atk_damage > 0 or any(e["type"] in ("damage", "taunt", "stun") for e in effs)
        n = sum(1 for v in self.units if v.alive and not v.obj and v is not s and not v.summon
                and cheb(v.cell, s.cell) <= r and (s.is_enemy(v) if hostile else v.team == s.team))
        return n

    def worst_totem(self, caster, group):
        """Кого заменить новым тотемом: самый бесполезный сейчас, при равенстве — самый побитый."""
        mine = self.group_members(caster, group)
        return min(mine, key=lambda s: (self.totem_use(s), s.hp / max(1, s.max_hp), s.id)) if mine else None

    def group_members(self, caster, group):
        return [s for s in self.units if s.alive and s.owner is caster and s.proto.get("group") == group
                and not getattr(s, "extra", False)]

    def summon(self, caster, eff, center):
        """Призыв на клетку (или ближайшую свободную рядом). Сила призыва растёт с силой навыков призывателя."""
        proto = self.data.summons[eff["unit"]]
        cells = sorted(self.grid.in_radius(tuple(center), 1), key=lambda p: (cheb(p, center), p))
        cell = next((p for p in cells if self.is_free(p)), None)
        if cell is None:
            self.emit("fizzle", unit=caster, skill=None)
            return None
        limit = eff.get("limit", 1)
        mine = [s for s in self.units if s.alive and s.owner is caster and s.proto_id == eff["unit"]]
        group = proto.get("group")
        if group and not eff.get("extra"):     # тотемы шамана: общий лимит, растёт с уровнем (2 → 3 → 4)
            limit = self.group_limit(caster, group) + eff.get("limit_add", 0)
            mine = self.group_members(caster, group)
        if group and not eff.get("extra"):     # сверх лимита уходит самый бесполезный, а не самый старый
            while len(mine) >= limit and mine:
                old = self.worst_totem(caster, group)
                mine.remove(old)
                self._kill(old, expire=True)
        for old in mine[:max(0, len(mine) - limit + 1)]:
            self._kill(old, expire=True)
        u = self._spawn(caster.team, eff["unit"], proto, cell)
        sm = PS.summon_mult(caster)
        if sm != 1.0:                          # души некроманта: призванные крепче и сильнее
            u.max_hp = u.hp = int(round(u.max_hp * sm))
            u.atk_damage = int(round(u.atk_damage * sm))
        u.owner = caster
        u.life = eff.get("duration", proto.get("life", 10))
        if proto.get("permanent") and not eff.get("timed"):
            u.life = None                      # тотемы, нежить, духи, знамя — без срока, только лимит по числу
        u.extra = bool(eff.get("extra"))       # сверх лимита (Предки, Тотем-пленитель)
        k = caster.power * eff.get("power", 1.0)
        os_ = proto.get("owner_scale")
        if os_:                                # нежить некроманта: доля здоровья, урона и брони хозяина
            if self._flat:                     # навык от стата героя: доля хозяина и так растёт с ним
                k = eff.get("power", 1.0)
            u.max_hp = u.hp = max(u.max_hp, int(round(caster.max_hp * os_.get("hp", 0) * sm
                                                      * (eff.get("power", 1.0) if self._flat else 1.0))))
            dmg = max(caster.atk_damage, 1) * (caster.proto.get("scale") or {}).get("basic", 1.0)                 * os_.get("atk", 0) * k * sm
            u.atk_damage = max(u.atk_damage, int(round(dmg)))
            u.armor = max(u.armor, int(round(caster.total_armor() * os_.get("armor", 0))))
        else:
            u.max_hp = u.hp = int(round(u.max_hp * k))
            u.atk_damage = int(round(u.atk_damage * k))
        u.base.update(atk_damage=u.atk_damage)
        if proto.get("thorns"):                           # колючее чучело
            u.buffs["thorns"] = [proto["thorns"], 1e9]
        if u.aura:
            scaled = [dict(e, amount=int(round(e["amount"] * k))) if "amount" in e else e for e in u.aura["effects"]]
            u.aura = {**u.aura, "effects": scaled}
        if eff.get("taunt"):                   # приманка: враги вокруг бьют призванного
            for v in self.units_in_radius(u.cell, eff.get("taunt_radius", 2)):
                if v.alive and caster.is_enemy(v) and not v.obj and not v.boss:
                    v.taunted_by, v.taunt_time = u, eff["taunt"]
                    v.ai_timer = 0.0
                    self.emit("taunt", unit=v, src=u)
        self.emit("summon", unit=u, owner=caster)
        return u

    def revive(self, caster, eff, center):
        """Поднять павшего героя (не призыв) своей команды, лежащего в радиусе от центра."""
        dead = [u for u in self.units if not u.alive and not u.summon and not u.obj and u.team == caster.team
                and cheb(u.cell, center) <= eff.get("radius", 0)]
        if not dead:
            self.emit("fizzle", unit=caster, skill=None)
            return
        u = min(dead, key=lambda d: cheb(d.cell, center))
        if self.unit_at(u.cell):                 # на его клетке уже кто-то стоит — ищем рядом
            free = [p for p, _ in self.grid.neighbors(u.cell) if self.is_free(p)]
            if not free:
                self.emit("fizzle", unit=caster, skill=None)
                return
            u.cell = u.prev_cell = free[0]
        u.alive = True
        u.hp = max(1, int(u.max_hp * eff["pct"]))
        u.statuses.clear()
        u.dots.clear()
        u.buffs.clear()
        u.buff_total.clear()
        u.stun, u.asleep, u.shield = 0.0, False, 0
        u.ap = min(u.ap_max, 2)
        self.emit("revive", unit=u, src=caster)
        self.log(f"{caster.name} поднимает {u.name}", (255, 240, 170))

    def set_form(self, u, form):
        """Облик (друид): повторное применение того же облика возвращает в человеческий."""
        if form == u.form:
            form = None
        old_hp_add = u.forms.get(u.form, {}).get("hp_add", 0) if u.form else 0
        for k, v in u.base.items():
            setattr(u, k, v)
        u.max_hp -= old_hp_add
        u.form = form
        f = u.forms.get(form, {}) if form else {}
        u.armor += f.get("armor_add", 0)
        u.atk_damage = int(round(u.atk_damage * f.get("atk_mult", 1.0)))
        u.atk_range = f.get("atk_range", u.atk_range)
        u.atk_cd *= f.get("atk_cd_mult", 1.0)
        u.move_time *= f.get("move_mult", 1.0)
        u.atk_kind = f.get("atk_kind", u.atk_kind)
        u.max_hp += f.get("hp_add", 0)
        u.hp = max(1, min(u.max_hp, u.hp + f.get("hp_add", 0) - old_hp_add))
        old_form = getattr(u, "_last_form", None)
        u._last_form = form
        self.emit("form", unit=u, form=form)
        self.gain(u, "form")
        PS.on_form(self, u, old_form, form)
        self.log(f"{u.name}: {f.get('name', 'человеческий облик')}", (200, 230, 160))

    def _zone_of_control(self, u, prev):
        """Копейщик бьёт врага, шагнувшего к нему в соседнюю клетку, и тормозит его."""
        for z in self.units:
            p = z.passive
            free = "zoc_free" in z.buffs     # стойка: удар без траты шкалы
            if (not z.alive or not p or p["kind"] != "zoc" or not z.is_enemy(u) or z.stun > 0 or z.cast
                    or (z.pp < p["pp"] and not free)):
                continue
            reach = p.get("range", 1) + int(z.buff("zoc_range", 0))
            if cheb(u.cell, z.cell) <= reach < cheb(prev, z.cell) or (
                    "zoc_free" in z.buffs and cheb(u.cell, z.cell) <= reach and cheb(prev, z.cell) <= reach
                    and z.buff("zoc_free", 0) >= 2):
                self.gain(z, "zoc_hit")
                if free:
                    self.emit("passive", unit=z, name=p["name"], kind=p["kind"], detail=f"удар по {u.name}", other=u)
                else:
                    self._use_passive(z, f"удар по {u.name}", u)
                if z.buff("zoc_free", 0) >= 3:      # неприступная стена: и оглушает
                    self.apply_stun(u, 1.0)
                self.emit("attack", src=z, dst=u, kind="melee", tag=z.atk_tag)
                zm, zstun = PS.zoc_mult(z)
                self.damage(u, z.atk_damage * p.get("mult", 1.0) * zm, z, z.atk_tag, "melee")
                if zstun and u.alive:                 # окопался до конца — копьё оглушает
                    self.apply_stun(u, 1.0)
                u.wait = max(u.wait, p.get("halt", 0.6))
                return

    def pull(self, caster, u, cells):
        """Притянуть цель на cells клеток к кастеру (до соседней клетки). Мешает преграда — столкновение."""
        M.forced_move(self, u, cells, M.toward(caster.cell, 1), caster, "pull")

    def _leap_next_to(self, caster, target):
        if cheb(caster.cell, target.cell) <= 1:
            return True
        free = [p for p, _ in self.grid.neighbors(target.cell) if self.is_free(p)]
        if not free:
            return False
        # не в лаву и не в огонь, если есть клетка безопаснее
        self._place(caster, min(free, key=lambda p: (self._danger(caster, p), cheb(p, caster.cell))), 0.15)
        return True

    def _line_victims(self, caster, center, length):
        """Враги на прямой от кастера через центр, до length клеток."""
        dx, dy = center[0] - caster.cell[0], center[1] - caster.cell[1]
        n = max(abs(dx), abs(dy))
        if n == 0:
            return []
        out = []
        for k in range(1, length + 1):
            p = (round(caster.cell[0] + dx * k / n), round(caster.cell[1] + dy * k / n))
            if not self.grid.in_bounds(p):
                break
            v = self.unit_at(p)
            if v and caster.is_enemy(v) and v not in out:
                out.append(v)
        if out:
            self.emit("line", src=caster, cells=[v.cell for v in out])
        return out

    def _chain(self, caster, first, eff):
        if first is None:
            return
        hit, cur = {first}, first
        for _ in range(eff["jumps"]):
            nxt = [f for f in self.units if f.alive and caster.is_enemy(f) and f not in hit
                   and cheb(f.cell, cur.cell) <= eff["range"] and not (f.obj and f.team == NEUTRAL)]
            if not nxt:
                return
            v = min(nxt, key=lambda f: cheb(f.cell, cur.cell))
            self.emit("link", src=cur, dst=v, color=self.tags[eff["tag"]]["color"] if eff.get("tag") else None)
            self._hit(caster, v, eff)
            hit.add(v)
            cur = v

    def cleanse(self, u, tags=None, by=None):
        """Снять с юнита состояния с любым из тегов (по умолчанию — стихии, контроль, дебаффы)."""
        gone = C.remove(self, u, tags or C.DEFAULT_CLEANSE)
        if gone:
            self.emit("cleanse", unit=u, names=[g.name for g in gone])
            self.rules.fire("removed", set().union(*(g.tags for g in gone)), unit=u, source=by)
        return gone

    def _transfer_statuses(self, caster, ally, eff):
        tags = list(ally.statuses)
        self.cleanse(ally, ["element"], caster)
        foes = [f for f in self.units if f.alive and caster.is_enemy(f) and cheb(f.cell, ally.cell) <= eff["range"]]
        if not foes:
            return
        foe = min(foes, key=lambda f: cheb(f.cell, ally.cell))
        self.emit("link", src=ally, dst=foe, color=None)
        for tag in tags:
            self._touch_status(foe, tag, caster)
        if eff.get("damage") and foe.alive:
            self.damage(foe, eff["damage"], caster, None, "spell")

    def _select(self, caster, center, r, affects, tunit):
        cand = [tunit] if r == 0 and tunit is not None else self.units_in_radius(center, r)
        if affects == "enemies":
            return [v for v in cand if v.alive and caster.is_enemy(v)]
        if affects == "allies":
            return [v for v in cand if v.alive and not caster.is_enemy(v)]
        return [v for v in cand if v.alive]

    def _cell_tag(self, pos, tag):
        c = self.grid.get(pos)
        if not c.passable:
            return
        for cr in self.data.reactions["cell"]:
            if cr["tag"] != tag:
                continue
            if "terrain" in cr and (c.terrain != cr["terrain"] or c.hazard):
                continue
            if "hazard" in cr and c.hazard != cr["hazard"]:
                continue
            if tag == "fire" and c.hazard == "oil":   # масло: вспыхивает вся лужа, горит сильнее и дольше
                self.ignite_oil(pos)
                return
            if cr.get("clear_hazard"):
                c.hazard = None
                c.blaze = False
            if cr.get("set_hazard"):
                c.hazard, c.hazard_time = cr["set_hazard"], cr["duration"]
                c.blaze = False
            self.emit("cell_reaction", pos=pos, name=cr["name"], tag=tag)
            return

    def ignite_oil(self, pos):
        """Огонь коснулся масла: загорается вся связная лужа (8 соседей) — горящее масло жжёт сильнее и дольше."""
        cfg = self.cfg["blaze"]
        todo, seen = [tuple(pos)], set()
        while todo:
            p = todo.pop()
            if p in seen:
                continue
            seen.add(p)
            cell = self.grid.get(p)
            if cell is None or cell.hazard != "oil":
                continue
            cell.hazard, cell.hazard_time, cell.blaze = "fire", cfg["duration"], True
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (p[0] + dx, p[1] + dy)
                    if q not in seen:
                        todo.append(q)
        burnt = [p for p in seen if self.grid.get(p) is not None and self.grid.get(p).blaze]
        if burnt:
            self.emit("cell_reaction", pos=tuple(pos), name="Масло вспыхнуло", tag="fire")
            self.emit("oil_blaze", cells=burnt)

    # ---------- урон, теги, реакции ----------

    def damage(self, target, amount, attacker=None, tag=None, kind="melee", dtype=None):
        """Полный конвейер удара. kind: melee/ranged/spell — прямой удар; dot/hazard/reaction/collision — без брони
        и пассивок. dtype — тип урона для резистов (physical/magic/стихия), не вешает статус."""
        if not target.alive:
            return 0
        sc = attacker.proto.get("scale") if attacker is not None and not self._intercepting else None
        if sc:                                 # режим героев: урон растёт от атрибута своего вида
            school = "basic" if self._basic else (kind if kind in self.data.stats_mode["schools"] else None)
            if self._flat and not self._basic:
                school = None                  # навык от стата героя: атрибут уже в множителе (stat_k)
            amount *= sc.get(school, 1.0) if school else 1.0
            if kind in DIRECT and attacker.proto.get("crit") and self.rng.random() < attacker.proto["crit"]:
                amount *= attacker.proto.get("crit_mult", 1.75)
                self.emit("crit", unit=target, src=attacker)
                self.rules.fire("crit", {kind, tag} - {None}, unit=target, source=attacker)
        vs = attacker.proto.get("dmg_vs") if attacker is not None and not self._intercepting else None
        if vs:                                 # дар или вещь героя: урон по горящим / мокрым / замёрзшим…
            have = C.unit_tags(self, target)
            for tg, k in vs.items():
                if tg in have:
                    amount *= k
        if attacker is not None and not self._intercepting and not target.obj:
            amount *= PS.out_mult(self, attacker, target, kind, tag, self._basic)
        dg = target.proto.get("dodge")
        if dg and kind in ("melee", "ranged") and attacker is not None and not self._intercepting \
                and self.rng.random() < dg:
            self.emit("dodge", unit=target)
            self.rules.fire("dodge", {kind}, unit=target, source=attacker)
            return 0
        if target.obj:
            return self._hit_object(target, amount, attacker, tag)
        if "reactive" in target.buffs and attacker is not None and kind in DIRECT and attacker.is_enemy(target)                 and not self._intercepting and self.time >= getattr(target, "reactive_t", 0.0):
            kit.reactive_blast(self, target, attacker)
        if attacker is not None and (target.marks or attacker.marks):
            amount *= kit.duel_mult(self, target, attacker)
            if any(m["src"] is attacker for mid, m in target.marks.items() if mid in ("challenge", "duel")):
                self.gain(attacker, "duel_hit")
        b = target.tethered_by
        if b is not None and b.alive and b is not target and b.merged <= 0 and kind not in ("hp_cost",) \
                and not self._intercepting:
            # привязь связующего: половина урона уходит в него
            half = amount * 0.5
            amount -= half
            self._intercepting = True
            try:
                self.damage(b, half, attacker, None, "reaction")
            finally:
                self._intercepting = False
            self.emit("link", src=target, dst=b, color=(255, 170, 170))
            PS.on_tether(self, b, half)
        if target.stasis > 0:                 # вне времени — удары не доходят
            self.emit("damage", unit=target, amount=0, absorbed=0, kind="stasis", tag=None, cover=False, blocked=None)
            return 0
        direct = kind in DIRECT
        g = target.guarded_by
        if direct and g is not None and g.alive and g is not target and attacker is not None \
                and attacker is not g and cheb(g.cell, target.cell) <= 1 and not self._intercepting:
            # телохранитель рядом принимает удар на себя (один раз: перехват перехвата не бывает)
            self.emit("intercept", unit=g, ward=target, src=attacker)
            self.gain(g, "intercept")
            self._intercepting = True
            try:
                return self.damage(g, amount, attacker, tag, kind, dtype=dtype)
            finally:
                self._intercepting = False
        p = target.passive
        blocked = None
        if direct and p and target.pp >= p["pp"]:
            if p["kind"] == "dodge" and kind in p.get("vs", ["melee"]):
                self._use_passive(target, "промах", attacker)
                return 0
            if p["kind"] == "block":
                self._use_passive(target, f"урон ×{p['mult']:g}", attacker)
                amount *= p["mult"]
                blocked = p["name"]
        covered = False
        if kind == "ranged" and attacker is not None:
            cover = self.grid.cover_between(attacker.cell, target.cell) or self._object_cover(attacker, target)
            if cover:
                amount *= self.cfg["cover"][cover]
                covered = True
        amount *= target.buff("dmg_taken", 1.0) * target.buff("exposed", 1.0)
        amount *= PS.in_mult(self, target, attacker, kind)
        if tag == "fire" and target.frost_armor and target.shield > 0:
            target.shield = 0                      # огонь раскалывает ледяную броню
            amount *= 1.5
            self.emit("armor_break", unit=target)
        if dtype and dtype != tag:
            amount *= target.resist.get(dtype, 1.0)
        if tag:
            amount *= target.resist.get(tag, 1.0)
            amount += self.apply_status(target, tag, attacker, amount)
            if not target.alive:
                return 0
        if direct:
            amount = max(1, amount - target.total_armor())
            if target.asleep:
                target.asleep, target.stun = False, 0.0
                self.emit("wake", unit=target)
        amount = int(round(amount))
        hp_before = max(0, target.hp)          # для эффективного урона: overkill не считается заслугой
        absorbed = 0
        if target.shield > 0:
            absorbed = min(target.shield, amount)
            target.shield -= absorbed
            amount -= absorbed
        target.hp -= amount
        if target.hp <= 0 and "undying" in target.buffs:     # неистовая ярость: не умирает, пока длится
            target.hp = 1
        self.emit("damage", unit=target, amount=amount, absorbed=absorbed, kind=kind, tag=tag, cover=covered,
                  blocked=blocked)
        PS.after_damage(self, attacker, target, amount + absorbed, kind, tag, self._basic)
        src = self.credit(attacker)            # статистика боя: призыв и гость считаются за хозяина
        if src is not None and src.team != target.team:
            eff = min(target.max_hp, min(amount, hp_before) + absorbed)
            src.tally["dealt"] += amount + absorbed
            src.tally["dealt_eff"] += eff
            src.tally["dealt_frac"] += eff / max(1, target.max_hp)
            target.last_hit_by = src
            target.hit_by[src] = self.time
        sh = target.shield_src
        if absorbed and sh is not None and sh.team == target.team:
            sh.tally["shielded"] += absorbed
            sh.tally["shielded_frac"] += absorbed / max(1, target.max_hp)
        target.tally["taken"] += amount
        target.tally["absorbed"] += absorbed
        if attacker is not None and attacker.mutator:
            MU.on_hit(self, attacker, target, amount + absorbed, kind)
        thorns = target.buff("thorns", 0)
        if thorns and kind == "melee" and attacker is not None and attacker.alive:
            self.emit("thorns", unit=target, dst=attacker)
            self.damage(attacker, max(1, round((amount + absorbed) * thorns)), target, kind="reaction")
        if direct and target.hp > 0:
            if blocked is None:
                self.gain(target, "hit_taken")
            self._intercede(target)
            self._on_hit_passive(target, attacker, kind)
        if target.alive and amount + absorbed > 0:
            self.rules.fire("hit", {kind, tag} - {None}, unit=target, source=attacker)
        if target.hp <= 0:
            self.rules.fire("kill", ({kind, tag} - {None}) | C.unit_tags(self, target), unit=target, source=attacker)
            if attacker is not None and attacker.team == PLAYER and attacker.alive and self.fx.get("kill_ap"):
                attacker.ap = min(attacker.ap_max, attacker.ap + self.fx["kill_ap"])
            self.gain(attacker, "kill")
            self._kill(target, tag=tag)
            kit.on_kill(self, attacker, target)
        return amount

    # ---------- объекты поля ----------

    def _object_cover(self, shooter, target):
        """Бочка или валун вплотную к цели со стороны стрелка тоже укрывают."""
        dx, dy = sign(shooter.cell[0] - target.cell[0]), sign(shooter.cell[1] - target.cell[1])
        p = (target.cell[0] + dx, target.cell[1] + dy)
        if (dx, dy) == (0, 0) or p == shooter.cell:
            return None
        o = self.unit_at(p)
        return o.obj.get("cover") if o is not None and o.obj else None

    # ---------- особые эффекты героев ----------

    def _special(self, caster, eff, center, tunit):
        t = eff["type"]
        if t == "delay":                   # отложенный эффект (Обет жреца): через time сек на ту же цель
            total = eff["time"]
            self.delayed.append({"left": total, "total": total, "caster": caster, "effects": eff["effects"],
                                 "center": tuple(center), "tunit": tunit, "name": eff.get("name", "")})
            if tunit is not None:
                self.emit("delay_start", unit=tunit, src=caster, time=total, name=eff.get("name", ""))
        elif t == "watch":                 # дозор лучника: зона, первый вошедший враг получает выстрел
            caster.watch = {"center": tuple(center), "radius": eff.get("radius", 1), "left": eff["duration"],
                            "total": eff["duration"], "mult": eff.get("mult", 2.2), "shots": eff.get("shots", 1),
                            "tag": eff.get("tag"), "stun": eff.get("stun")}
            self.emit("watch", unit=caster, center=tuple(center), radius=eff.get("radius", 1))
        elif t == "detonate":              # Вспышка: всё горящее в радиусе взрывается
            self._detonate(caster, eff, center)
        elif t == "place_object":          # бочка подрывника
            mine = [o for o in self.units if o.alive and o.obj and o.owner is caster and o.proto_id == eff["object"]]
            for old in mine[:max(0, len(mine) - eff.get("limit", 3) + 1)]:
                self.break_object(old)
            if not self.is_free(center):
                self.emit("fizzle", unit=caster, skill=None)
                return
            o = self.spawn_object(eff["object"], center)
            o.owner = caster
            o.blast_mult = eff.get("_powder", 1.0)
            if eff.get("blast"):               # заряд героя: урон — % силы навыков, прочность — % его здоровья
                o.blast_dmg = eff["blast"] * self.stat_k(caster, "sp", True) * o.blast_mult
                o.blast_r = eff.get("blast_r")
                o.blast_stun = eff.get("stun")
            if eff.get("hp_pct"):
                o.max_hp = o.hp = max(1, int(round(caster.max_hp * eff["hp_pct"])))
            self.emit("summon", unit=o, owner=caster)
        elif t == "fuse" and eff.get("chain"):     # Фитиль-кнопка: все свои заряды — цепочкой за ~1 сек
            kit.fuse_chain(self, caster, eff)
        elif t == "fuse":                  # фитиль: свои бочки в радиусе взорвутся через delay сек
            for o in self.units:
                if o.alive and o.obj and o.obj.get("volatile") is not None and o.owner is caster \
                        and cheb(o.cell, caster.cell) <= eff.get("radius", 6) and o.fuse <= 0:
                    o.fuse = eff.get("delay", 2.0)
                    o.igniter = caster
                    self.emit("fuse", unit=o)
        elif t == "rush":                  # натиск тарана: бег по линии, первого на пути — толчком дальше
            self._rush(caster, eff, center)
        elif t == "toss":                  # бросок: соседа — в клетку
            self._toss(caster, eff, center)
        elif t in ("gather", "swap", "levitate", "collapse"):
            self._gravity(caster, eff, tuple(center), tunit)
        elif t == "terrain_cast":          # геомант: навык по клетке под целью (родник, жерло, перековка — под врагом)
            cell = tunit.cell if tunit is not None else tuple(center)
            ground = self.grid.get(cell).terrain if self.grid.get(cell) else "grass"
            effects = eff["by"].get(ground) or eff["by"].get("default", [])
            if ground != caster.last_ground:
                caster.last_ground = ground
                self.gain(caster, "new_ground")
            self.emit("terrain_cast", unit=caster, ground=ground)
            self.apply_effects(caster, effects, center, tunit)
        elif t == "reagent":               # зельевар: урон за каждый тег на цели (взрывной вариант снимает теги)
            if tunit is None or not tunit.alive:
                return
            tags = list(tunit.statuses)
            if not tags:
                self.emit("fizzle", unit=caster, skill=None)
                return
            self.emit("reagent", unit=tunit, tags=tags)
            rk, keep = 1.0, False
            if PS.kind(caster) == "recipe":
                rk = 1 + PS.core(caster)["reagent"] * caster.pp
                keep = caster.pp >= caster.pp_max > 0
            eff = dict(eff, per_tag=eff["per_tag"] * rk)
            if eff.get("explode"):
                for tag in tags:
                    if not keep:
                        self._clear_dot(tunit, tag)
                    for v in self.units_in_radius(tunit.cell, eff.get("radius", 1)):
                        if caster.is_enemy(v):
                            self.damage(v, eff["per_tag"] * caster.power, caster, None, "spell")
            else:
                for tag in tags:
                    self._touch_status(tunit, tag, caster, hostile=False)
                self.damage(tunit, eff["per_tag"] * len(tags) * caster.power, caster, None, "spell")
        elif t == "extra_attack":          # приказ «Вперёд!»: союзник сразу бьёт ещё раз
            if tunit is not None and tunit.alive and tunit is not caster:
                foes = [f for f in self.foes_of(tunit) if cheb(f.cell, tunit.cell) <= self.reach(tunit)]
                if foes:
                    t2 = tunit.last_target if tunit.last_target in foes else min(foes, key=lambda f: f.hp)
                    for _ in range(eff.get("count", 1) + (eff.get("banner_count", 1) if kit.banner_near(self, tunit) else 0)):
                        tunit.attack_timer = 0.0
                        self._basic_attack(tunit, t2)
                    self.emit("order", unit=tunit, src=caster, name="Вперёд!")
                    self.gain(caster, "order")
                else:
                    tunit.ap = min(tunit.ap_max, tunit.ap + eff.get("ap", 1))
                    self.emit("order", unit=tunit, src=caster, name=f"+{eff.get('ap', 1)} AP")
        elif t == "regroup":               # «Перестроение»: ближайший к клетке союзник мгновенно встаёт туда
            center = tuple(center)
            if not self.is_free(center):
                self.emit("fizzle", unit=caster, skill=None)
                return
            near = [a for a in self.fighters(caster.team) if a is not caster and not a.static and not a.summon
                    and cheb(a.cell, center) <= eff.get("reach", 2)]
            if not near:
                self.emit("fizzle", unit=caster, skill=None)
                return
            a = min(near, key=lambda a: cheb(a.cell, center))
            self._interrupt(a)
            a.order = None
            src = a.cell
            self._place(a, center, 0.12)
            if eff.get("banner_shield") and kit.banner_near(self, a):
                a.shield, a.shield_time = max(a.shield, int(eff["banner_shield"] * caster.power)), 6.0
                self.emit("shield", unit=a, amount=a.shield)
            self.emit("order", unit=a, src=caster, name="Перестроение")
            self.gain(caster, "order")
            self.emit("rewind", unit=a, src=src, dst=center)
        elif t == "focus":                 # «Фокус»: все бойцы отряда бьют одну цель
            if tunit is None or not tunit.alive:
                return
            for a in self.fighters(caster.team):
                if a is not caster and not a.static and cheb(a.cell, tunit.cell) <= eff.get("reach", 6):
                    self.order_attack(a, tunit)
                    if eff.get("banner_ap") and kit.banner_near(self, a):
                        a.ap = min(a.ap_max, a.ap + eff["banner_ap"])
            self.add_buff(tunit, "dmg_taken", eff.get("mult", 1.2), eff.get("duration", 5))
            self.emit("order", unit=tunit, src=caster, name="Фокус!")
            self.gain(caster, "order")
        elif t == "tether":                # привязь: делит урон союзника пополам
            if tunit is None or tunit is caster:
                return
            mine = [v for v in self.units if v.tethered_by is caster and v is not tunit]
            for v in mine[:max(0, len(mine) - eff.get("limit", 1) + 1)]:
                v.tethered_by = None
            tunit.tethered_by, tunit.tether_time = caster, eff["duration"]
            if eff.get("regen"):
                self.add_buff(tunit, "regen", eff["regen"], eff["duration"])
            self.emit("tether", unit=tunit, src=caster)
        elif t == "merge":                 # «Слияние»: связующий входит в союзника на привязи
            ally = next((v for v in self.units if v.alive and v.tethered_by is caster), None)
            if ally is None or caster.merged > 0:
                self.emit("fizzle", unit=caster, skill=None)
                return
            caster.merged, caster.merge_host = eff["duration"], ally
            caster.order, caster.cast = None, None
            self._place(caster, (-50 - caster.id, -50), 0.01)     # вне поля: не цель, не мешает
            for e2 in eff.get("host", []):
                self.apply_effects(caster, [e2], ally.cell, ally)
            self.emit("merge", unit=caster, host=ally)
        elif t == "life_transfer":         # «Отдать силы»: HP связующего — союзнику
            if tunit is None or not tunit.alive or tunit is caster:
                return
            cost = min(eff["cost"], caster.hp - 1)
            caster.hp -= cost
            self.emit("damage", unit=caster, amount=cost, absorbed=0, kind="hp_cost", tag=None, cover=False,
                      blocked=None)
            self.heal(tunit, int(round(eff["amount"] * caster.power)), caster)
            self.emit("link", src=caster, dst=tunit, color=(255, 170, 170))
        elif t == "spread_fire":           # раздуть: огонь с горящих клеток и врагов перекидывается на соседей
            r = eff.get("radius", 2)
            burning = [p for p in self.grid.in_radius(tuple(center), r) if self.grid.get(p).hazard == "fire"]
            hot = [v for v in self.units_in_radius(tuple(center), r) if v.alive and "fire" in v.statuses]
            if not burning and not hot:
                self.emit("fizzle", unit=caster, skill=None)
                return
            for p in burning + [v.cell for v in hot]:
                for q in self.grid.in_radius(p, 1):
                    c = self.grid.get(q)
                    if c.passable and c.terrain not in ("water", "chasm") and c.hazard != "fire":
                        c.hazard, c.hazard_time, c.hazard_team = "fire", eff.get("duration", 4), caster.team
                        self.emit("cell_reaction", pos=q, name="", tag="fire")
            for v in hot:
                self._touch_status(v, "fire", caster)
                for w in self.units_in_radius(v.cell, 1):
                    if w is not v and caster.is_enemy(w) and not w.obj:
                        self._touch_status(w, "fire", caster)
        elif t == "trap":                  # капкан ловчего: невидим врагу, держит и раскрывает пойманного
            self._place_trap(caster, eff, tuple(center))
        elif t == "wall":                  # ледяная стена криоманта: поперёк направления каста
            self._wall(caster, eff, tuple(center))
        elif t == "terrain":               # каток, лава, родник: клетки на время меняют рельеф
            cells = []
            for p in self.grid.in_radius(tuple(center), eff.get("radius", 1)):
                c = self.grid.get(p)
                want = eff.get("terrain")
                if eff.get("cycle"):           # перековать: следующий рельеф по кругу
                    cyc = eff["cycle"]
                    want = cyc[(cyc.index(c.terrain) + 1) % len(cyc)] if c.terrain in cyc else cyc[0]
                if not c.passable or c.terrain in ("chasm",) or c.terrain == want:
                    continue
                if c.base_terrain and not eff.get("cycle"):
                    continue
                if c.terrain in ("water", "lava") and not eff.get("cycle") and not eff.get("over_liquid"):
                    continue
                if not c.base_terrain:
                    c.base_terrain = c.terrain
                c.terrain = want
                c.hazard = None if want in ("water", "lava") else c.hazard
                cells.append(p)
            if cells:
                self.tides.append([self.time + eff.get("duration", 8), cells])
                self.emit("terrain", cells=cells, terrain=self.grid.get(cells[0]).terrain, src=caster)
        elif t == "shatter":               # раскол: свои ледяные постройки взрываются осколками
            walls = [o for o in self.units if o.alive and o.obj and o.owner is caster
                     and cheb(o.cell, caster.cell) <= eff.get("radius", 6)]
            if not walls:
                self.emit("fizzle", unit=caster, skill=None)
            for o in walls:
                self.emit("shatter", unit=o)
                for v in self.units_in_radius(o.cell, eff.get("blast", 1)):
                    if v is not o and caster.is_enemy(v) and not v.obj:
                        self.damage(v, eff["amount"] * caster.power, caster, eff.get("tag", "ice"), "spell")
                self.break_object(o)
            if eff.get("frozen"):              # и замёрзшие враги раскалываются
                for v in list(self.units):
                    if v.alive and not v.obj and caster.is_enemy(v) and cheb(v.cell, caster.cell) <= eff.get("radius", 6) \
                            and (("cold" in v.marks) or (v.stun > 0 and v.stun_look == "freeze")):
                        n = kit.consume_mark(self, v, "cold") if "cold" in v.marks else 3
                        self.emit("shatter", unit=v)
                        self.damage(v, eff["frozen"] * (1 + 0.35 * n) * caster.power, caster, "ice", "spell")
        elif t == "corpse":                # некромант: труп у точки — взорвать, поднять, пожрать, облако, стена
            self._corpse(caster, eff, tuple(center))
        elif t == "rewind":                # откат хрономанта: клетка и HP, какие были N сек назад
            self._rewind(caster, eff, tunit)
        elif t == "stasis":                # стазис: цель вне времени — неуязвима и не действует
            if tunit is not None and tunit.alive and not tunit.boss and not tunit.obj:
                tunit.stasis = eff["duration"]
                self.apply_stun(tunit, eff["duration"], "stasis")
                self.emit("stasis", unit=tunit, src=caster)
        elif t == "song":                  # песня барда: такты, ноты за навыки союзников, финал
            caster.song = {"beat": 0, "beats": eff.get("beats", 4), "every": eff.get("every", 2.0), "t": 0.0,
                           "notes": 0, "radius": eff.get("radius", 3), "finale": eff.get("finale", []),
                           "per_note": eff.get("per_note", 0.06)}
            self.emit("song_start", unit=caster)

    def _gravity(self, caster, eff, center, tunit):
        t = eff["type"]
        if t == "gather":                  # сингулярность: враги в радиусе стягиваются к точке
            # враги и всё, что можно толкнуть (бочки, валуны, глыбы), — к точке; бочку можно стянуть в толпу
            foes = sorted([v for v in self.units_in_radius(center, eff.get("radius", 2))
                           if v is not caster and M.movable(self, v) and (v.obj or caster.is_enemy(v))],
                          key=lambda v: cheb(v.cell, center))
            self.emit("gather", center=center, src=caster, radius=eff.get("radius", 2))
            for v in foes:
                moved, _ = M.forced_move(self, v, eff.get("cells", 2), M.toward(center, 0), caster, "gather")
                if moved and not v.obj:
                    self.gain(caster, "pulled")
                    PS.on_pulled(self, caster)
                if eff.get("amount") and not v.obj:
                    self.damage(v, eff["amount"] * caster.power, caster, eff.get("tag"), "spell")
        elif t == "swap":                  # обмен: гравитомант и цель меняются местами
            if tunit is None or not M.movable(self, tunit) or not M.movable(self, caster) or M.heavy(self, tunit):
                self.emit("fizzle", unit=caster, skill=None)
                return
            a, b = caster.cell, tunit.cell
            self._interrupt(tunit)
            tunit.order = None
            caster.cell, tunit.cell = b, a          # мгновенно: иначе клетки заняты друг другом
            caster.prev_cell, tunit.prev_cell = a, b
            caster.move_t = tunit.move_t = 0.0
            caster.move_dur = tunit.move_dur = 0.2
            self._check_watch(tunit)
            self.emit("swap", unit=tunit, src=caster)
        elif t == "levitate":              # невесомость: цель в воздухе, толчок по ней — дальше, падение — урон
            if tunit is None or not tunit.alive or tunit.boss:
                self.emit("fizzle", unit=caster, skill=None)
                return
            tunit.levitate = eff["duration"]
            tunit.levitate_dmg = eff.get("fall", 12) * caster.power
            self.apply_stun(tunit, eff["duration"], "levitate")
            self.emit("levitate", unit=tunit, src=caster)
        elif t == "collapse":              # коллапс: урон по куче — чем плотнее, тем больнее
            foes = [v for v in self.units_in_radius(center, eff.get("radius", 2)) if caster.is_enemy(v) and not v.obj]
            self.emit("gather", center=center, src=caster, radius=eff.get("radius", 2))
            for v in foes:
                self.damage(v, (eff["amount"] + eff["per_unit"] * len(foes)) * caster.power
                            * (1 + eff.get("per_gauge", 0) * eff.get("_spent", 0)), caster, None, "spell")

    def _place_trap(self, caster, eff, center):
        off = eff.get("offset")
        if off:                                           # второй капкан — рядом с первым
            center = (center[0] + off[0], center[1] + off[1])
        c = self.grid.get(center)
        if c is None or not c.passable or c.terrain in ("water", "lava", "chasm") or self.unit_at(center):
            self.emit("fizzle", unit=caster, skill=None)
            return
        mine = [p for p in self.traps.get(caster.id, []) if self.grid.get(p).hazard_owner is caster]
        while len(mine) >= eff.get("limit", 3):
            old = self.grid.get(mine.pop(0))
            old.hazard, old.hazard_owner = None, None
        c.hazard, c.hazard_time, c.hazard_team, c.hazard_owner = eff["hazard"], PERMANENT, caster.team, caster
        mine.append(center)
        self.traps[caster.id] = mine
        self.emit("trap_set", pos=center, src=caster)

    def _wall(self, caster, eff, center):
        dx, dy = sign(center[0] - caster.cell[0]), sign(center[1] - caster.cell[1])
        side = (-dy, dx) if (dx, dy) != (0, 0) else (0, 1)
        if side[0] and side[1]:                       # по диагонали — стена вдоль строки
            side = (0, 1)
        half = eff.get("length", 3) // 2
        made = 0
        for k in range(-half, eff.get("length", 3) - half):
            p = (center[0] + side[0] * k, center[1] + side[1] * k)
            c = self.grid.get(p)
            if c is None or not self.is_free(p) or c.terrain in ("lava", "chasm"):
                continue
            o = self.spawn_object(eff["object"], p)
            o.owner, o.life = caster, eff.get("life", 10)
            made += 1
        if made:
            self.emit("wall", src=caster, center=center)
        else:
            self.emit("fizzle", unit=caster, skill=None)

    def _corpse(self, caster, eff, center):
        if eff["do"] == "make":            # создать труп из своей крови
            if self.grid.get(center) is None or not self.grid.get(center).passable:
                self.emit("fizzle", unit=caster, skill=None)
                return
            self.corpses.append({"cell": tuple(center), "left": self.cfg.get("corpse_time", 14.0), "name": "кости"})
            self.emit("corpse_make", pos=tuple(center), src=caster)
            return
        r = eff.get("pick", 1)
        near = [b for b in self.corpses if cheb(b["cell"], center) <= r]
        if eff["do"] == "devour":
            near = [b for b in self.corpses if cheb(b["cell"], caster.cell) <= eff.get("radius", 2)]
        if not near:
            self.emit("fizzle", unit=caster, skill=None)
            return
        if eff["do"] != "devour":
            near = [min(near, key=lambda b: cheb(b["cell"], center))]
        for b in near:
            self.corpses.remove(b)
            self.gain(caster, "corpse")
            PS.on_corpse(self, caster)
            self.emit("corpse_use", pos=b["cell"], src=caster, do=eff["do"])
            p = b["cell"]
            if eff["do"] == "blast":
                for v in self.units_in_radius(p, eff.get("radius", 1)):
                    if caster.is_enemy(v):
                        self.damage(v, eff["amount"] * caster.power, caster, eff.get("tag"), "spell")
            elif eff["do"] == "raise":
                mine = [s for s in self.units if s.alive and s.owner is caster and s.proto_id == eff["unit"]]
                for old in mine[:max(0, len(mine) - eff.get("limit", 2) + 1)]:
                    self._kill(old, expire=True)
                self.summon(caster, {"unit": eff["unit"], "duration": eff.get("duration", 15)}, p)
            elif eff["do"] == "devour":
                caster.shield += int(eff.get("shield", 18) * caster.power)
                caster.shield_time = max(caster.shield_time, 8.0)
                self.emit("shield", unit=caster, amount=caster.shield)
            elif eff["do"] == "cloud":
                for q in self.grid.in_radius(p, eff.get("radius", 1)):
                    c = self.grid.get(q)
                    if c.passable and c.terrain not in ("water", "chasm"):
                        c.hazard, c.hazard_time, c.hazard_team = "poison", eff.get("duration", 6), caster.team
            elif eff["do"] == "wall":
                if self.is_free(p):
                    o = self.spawn_object(eff["object"], p)
                    o.owner, o.life = caster, eff.get("life", 12)

    def _rewind(self, caster, eff, u):
        if u is None or not u.alive or u.obj or not u.history:
            self.emit("fizzle", unit=caster, skill=None)
            return
        want = self.time - eff.get("seconds", 3.0)
        t, cell, hp = min(u.history, key=lambda h: abs(h[0] - want))
        src = u.cell
        if cell != u.cell:
            dest = cell if self.is_free(cell, exclude=u) else self.free_near(cell, 2)
            if dest is not None:
                self._interrupt(u)
                u.order = None
                self._place(u, dest, 0.2)
        if eff.get("hp", True) and not caster.is_enemy(u) and hp > u.hp:
            self.emit("heal", unit=u, amount=hp - u.hp)
            u.hp = min(u.max_hp, hp)
        self.emit("rewind", unit=u, src=src, dst=u.cell)

    def _enrage_update(self):
        """Затянутый бой (тупик: враг лечится или чинит броню быстрее, чем его бьют) не длится вечно: после
        enrage.after сек враги каждые enrage.every сек бьют сильнее."""
        er = self.cfg.get("enrage")
        if not er or self.time < er["after"]:
            return
        stage = int((self.time - er["after"]) // er["every"]) + 1
        if stage <= self.enraged:
            return
        self.enraged = stage
        k = 1 + er["mult"] * stage
        for u in self.fighters(ENEMY):
            u.buffs["atk_mult"] = [max(u.buff("atk_mult", 1.0), k), er["every"] + 1]
        self.emit("enrage", stage=stage, mult=k)
        self.log(f"Враги в ярости: урон ×{k:.2f}", (255, 110, 90))

    def _corpse_update(self, dt):
        for b in list(self.corpses):
            b["left"] -= dt
            if b["left"] <= 0:
                self.corpses.remove(b)

    def _delayed_update(self, dt):
        for d in list(self.delayed):
            d["left"] -= dt
            if d["left"] > 0:
                continue
            self.delayed.remove(d)
            if d.get("basic"):                # выстрел обычной атакой долетел
                self._land_basic(*d["basic"])
                continue
            if d.get("blast"):                # взрыв мутатора «взрывной»
                MU.blast(self, *d["blast"])
                continue
            if d.get("charge"):               # Фитиль дошёл до заряда в клетке или бомбы
                kit.blow_charge(self, *d["charge"])
                continue
            if d.get("ball"):                 # шаровая молния прошла клетку
                kit.ball_step(self, *d["ball"])
                continue
            if d.get("storm_tick"):           # «Грозовой фронт»: удар с неба у шамана и тотемов
                kit.storm_tick(self, *d["storm_tick"])
                continue
            if d.get("rain_barrel"):          # «Дождь бочек»: бочка упала
                kit.rain_barrel_land(self, *d["rain_barrel"])
                continue
            if d.get("shot"):                 # очередная стрела «Шквала»: вылетает, попадает через полёт
                kit.fire_shot(self, *d["shot"])
                continue
            if d.get("shot_hit"):
                kit.land_shot(self, *d["shot_hit"])
                continue
            if d.get("fn"):
                d["fn"]()
                continue
            tu, caster = d["tunit"], d["caster"]
            if d.get("skill"):                # навык долетел: цель-юнит — где она сейчас; погибла — в её клетку
                center = tu.cell if tu is not None else d["center"]
                if tu is not None and not tu.alive:
                    tu = None
                self.emit("skill_hit", unit=caster, skill=d["skill"], center=center, target=tu)
                self._skill = d["skill"]
                try:
                    self.apply_effects(caster, d["effects"], center, tu)
                finally:
                    self._skill = None
                continue
            if tu is not None and not tu.alive:
                continue
            center = tu.cell if tu is not None else d["center"]
            self.emit("delay_hit", unit=tu, src=caster, center=center, name=d["name"])
            self.apply_effects(caster, d["effects"], center, tu)

    def traps_of(self, u):
        """Клетки капканов юнита (их видит только его отряд)."""
        return [p for p in self.traps.get(u.id, []) if self.grid.get(p).hazard_owner is u]

    def pending_on(self, u):
        """Отложенные эффекты, которые придут на юнита: [(имя, осталось, всего)]."""
        return [(d["name"], d["left"], d["total"]) for d in self.delayed
                if d.get("tunit") is u and not d.get("skill") and not d.get("fn")]

    def _detonate(self, caster, eff, center):
        r, amount = eff.get("radius", 6), eff["amount"] * (1 + eff.get("per_gauge", 0) * eff.get("_spent", 0))
        cells = [p for p in self.grid.in_radius(caster.cell, r) if self.grid.get(p).hazard == "fire"]
        hit = set()
        for p in cells:
            self.emit("detonate", pos=p, src=caster)
            if not eff.get("keep_fire") and "inferno" not in caster.buffs:     # инферно: огонь остаётся
                self.grid.get(p).hazard = None
            for v in self.units_in_radius(p, eff.get("blast", 0)):
                if v not in hit and caster.is_enemy(v):
                    hit.add(v)
                    self.damage(v, amount * caster.power, caster, None, "spell")
        for v in self.units_in_radius(caster.cell, r):
            if v.alive and "fire" in v.statuses and caster.is_enemy(v) and v not in hit:
                hit.add(v)
                if not eff.get("keep_fire") and "inferno" not in caster.buffs:
                    self._clear_dot(v, "fire")
                self.emit("detonate", pos=v.cell, src=caster)
                self.damage(v, amount * eff.get("burning_mult", 1.5) * caster.power, caster, None, "spell")
        if not hit and not cells:
            self.emit("fizzle", unit=caster, skill=None)

    def _rush(self, caster, eff, center):
        dx, dy = sign(center[0] - caster.cell[0]), sign(center[1] - caster.cell[1])
        if (dx, dy) == (0, 0):
            return
        dest = caster.cell
        for _ in range(eff.get("length", 4)):
            n = (dest[0] + dx, dest[1] + dy)
            if not self.is_free(n):
                break
            dest = n
        start = caster.cell
        if dest != start:
            self._place(caster, dest, 0.08 * cheb(dest, start) + 0.06)
            self.emit("rush", unit=caster, src=start, dst=dest)
        n = (dest[0] + dx, dest[1] + dy)
        v = self.unit_at(n)
        if v is None:
            return
        if caster.is_enemy(v) and not v.obj and eff.get("amount"):
            self.damage(v, eff["amount"] * caster.power + 3 * cheb(dest, start), caster, None, "melee")
        if v.alive:
            self.knockback(caster.cell, v, eff.get("cells", 2), caster)

    def _toss(self, caster, eff, center):
        center = tuple(center)
        near = [v for v, _ in ((self.unit_at(p), p) for p, _ in self.grid.neighbors(caster.cell, True))
                if v is not None and v is not caster and M.movable(self, v) and not M.heavy(self, v)]
        if not near:
            self.emit("fizzle", unit=caster, skill=None)
            return
        v = min(near, key=lambda w: (not caster.is_enemy(w) if eff.get("prefer") == "enemy" else 0,
                                     cheb(w.cell, center)))
        land = center if self.is_free(center, flying=v.flying) else self.free_near(center, 2)
        occupant = self.unit_at(center)
        if land is None:
            self.emit("fizzle", unit=caster, skill=None)
            return
        self._interrupt(v)
        start = v.cell
        self._place(v, land, 0.32)
        self.emit("toss", unit=v, src=start, dst=land, by=caster)
        if v.obj and v.obj.get("volatile"):
            v.igniter = caster
            self.break_object(v, ignite=True)
            return
        if occupant is not None and occupant is not v:
            self._collide(v, occupant, 2, caster)
        for w in self.units_in_radius(land, 1):
            if w is not v and w.alive and caster.is_enemy(w) and not w.obj:
                self.damage(w, eff.get("splash", 10) * caster.power, caster, None, "melee")
        if caster.is_enemy(v) and v.alive and not v.obj:
            self.damage(v, eff.get("amount", 15) * caster.power, caster, None, "melee")

    def _song_update(self, u, dt):
        s = u.song
        s["t"] += dt
        if s["t"] < s["every"]:
            return
        s["t"] -= s["every"]
        s["beat"] += 1
        self.emit("beat", unit=u, beat=s["beat"], beats=s["beats"], radius=s["radius"])
        if s["beat"] < s["beats"]:
            return
        u.song = None
        notes = s["notes"]
        self.emit("finale", unit=u, notes=notes, radius=s["radius"])
        self.log(f"{u.name}: финал песни — нот {notes}", (255, 190, 230))
        for e in s["finale"]:                   # финал по врагам: урон и сон растут с нотами
            if e["type"] in ("damage", "sleep"):
                for v in self._select(u, u.cell, s["radius"], "enemies", None):
                    if v.obj and e["type"] == "sleep":
                        continue
                    if e["type"] == "damage":
                        self.damage(v, (e.get("amount", 0) + e.get("per_note", 0) * notes) * u.power, u, None, "spell")
                    else:
                        self.apply_stun(v, e.get("duration", 2) + e.get("per_note", 0) * notes, "sleep")
                        v.asleep = v.alive
        for v in self._select(u, u.cell, s["radius"], "allies", None):
            if v.obj:
                continue
            for e in s["finale"]:
                if e["type"] == "heal":
                    self.heal(v, int(round((e.get("amount", 0) + e.get("per_note", 0) * notes) * u.power)))
                elif e["type"] == "buff":
                    val = e["value"] + e.get("per_note", 0) * notes
                    self.add_buff(v, e["stat"], round(val, 3), e["duration"])
                elif e["type"] == "ap":
                    v.ap = min(v.ap_max, v.ap + int(e.get("amount", 0) + e.get("per_note", 0) * notes))

    def _hit_object(self, o, amount, attacker, tag):
        """Объект не горит и не мокнет: тег из ignite сразу его подрывает, остальное — просто урон."""
        if attacker is not None:
            o.igniter = attacker
        if tag and tag in o.obj.get("ignite", []):
            self.break_object(o, ignite=True)
            return 0
        amount = max(1, int(round(amount - o.obj.get("armor", 0))))
        o.hp -= amount
        self.emit("damage", unit=o, amount=amount, absorbed=0, kind="object", tag=tag, cover=False, blocked=None)
        if o.hp <= 0:
            self.break_object(o)
        return amount

    def break_object(self, o, ignite=False):
        """Объект разрушен: бочка взрывается или разливается, источник перестаёт звать врагов."""
        if not o.alive:
            return
        o.alive = False
        o.hp = 0
        d = o.obj
        eff = d.get("on_ignite") if ignite and "on_ignite" in d else d.get("on_break")
        own = getattr(o, "blast_dmg", None)
        fx = eff
        if eff and own is not None:            # заряд героя: свой урон и радиус — и на картинке
            fx = dict(eff, damage=round(own), radius=o.blast_r if getattr(o, "blast_r", None) is not None
                      else eff.get("radius", 0))
        self.emit("object_break", unit=o, ignite=ignite, fx=fx)
        src = o.igniter if o.igniter is not None and o.igniter.alive else None
        if d.get("guard"):
            self.log(f"{o.name} потерян(а)!", (255, 110, 110))
        else:
            self.log(f"{o.name}: {'взрыв' if eff and eff.get('damage') else 'разрушен(а)'}", (255, 190, 120))
        if not eff:
            return
        r = eff.get("radius", 0)
        if eff.get("hazard"):
            for p in self.grid.in_radius(o.cell, r):
                c = self.grid.get(p)
                if c.passable and c.terrain not in ("water", "chasm"):
                    if eff["hazard"] == "fire" and c.hazard == "oil":
                        self.ignite_oil(p)        # взрыв на масле — горит вся лужа
                        continue
                    c.hazard, c.hazard_time = eff["hazard"], eff.get("hazard_time", 5)
                    c.blaze = False
                    c.hazard_team = src.team if src is not None else None
        if own is not None and getattr(o, "owner", None) is not None:
            self.gain(o.owner, "blast")
        if eff.get("damage") or own is not None:
            if own is not None and getattr(o, "blast_r", None) is not None:
                r = o.blast_r
            flat = self._flat
            self._flat = own is not None       # заряд героя: урон уже от его силы навыков
            try:
                for v in self.units_in_radius(o.cell, r):
                    if v is not o:
                        if v.obj:
                            v.igniter = o.igniter
                        dmg = own if own is not None else eff["damage"] * getattr(o, "blast_mult", 1.0)
                        self.damage(v, dmg, src or getattr(o, "owner", None), eff.get("tag"), "reaction")
                        st = getattr(o, "blast_stun", None)
                        if st and v.alive and not v.obj and o.owner is not None and o.owner.is_enemy(v):
                            self.apply_stun(v, st, "stun")
            finally:
                self._flat = flat

    def _collide(self, u, other, left, pusher=None):
        """Удар при толчке о стену, юнит или объект: урон растёт с непройденными клетками, тот, в кого врезались,
        получает половину. Бочка с порохом от удара взрывается."""
        col = self.cfg["collision"]
        dmg = col["base"] + col["per_cell"] * (left - 1)
        if pusher is not None:
            dmg = PS.collision(self, pusher, dmg)
        self.emit("collision", unit=u, other=other, amount=dmg)
        self.gain(pusher, "collision")
        self.rules.fire("collision", {"collision"}, unit=u, other=other, source=pusher)
        if pusher is not None and "collide_stun" in pusher.buffs and u.alive and not u.obj:
            self.apply_stun(u, pusher.buff("collide_stun", 1.0))      # прибит к преграде
        if pusher is not None and "billiard" in pusher.buffs and other is not None and other.alive \
                and not other.obj and not getattr(other, "_billiard", False):
            dmg *= pusher.buff("billiard", 1.5)            # бильярд: тот, в кого врезались, летит дальше
            other._billiard = True
            try:
                self.knockback(u.cell, other, max(1, left), pusher)
            finally:
                other._billiard = False
        for v, k in ((u, 1.0), (other, 0.5)):
            if v is None or not v.alive:
                continue
            if v.obj and v.obj.get("volatile"):
                if pusher is not None:
                    v.igniter = pusher
                self.break_object(v, ignite=True)
            else:
                self.damage(v, max(1, round(dmg * k)), pusher, kind="collision")

    def _on_hit_passive(self, target, attacker, kind):
        """Пассивки, срабатывающие после полученного удара: ярость берсерка, праведный гнев."""
        p = target.passive
        if not p or target.pp < p["pp"]:
            return
        if p["kind"] == "rage":
            self._use_passive(target, f"атаки ×{p['value']:g}")
            self.add_buff(target, p["stat"], p["value"], p["duration"])
        elif p["kind"] == "retaliate" and kind == "melee" and attacker is not None and attacker.alive:
            self._use_passive(target, f"{p['damage']} урона: {attacker.name}", attacker)
            self.damage(attacker, p["damage"], target, p.get("tag"), "reaction")

    def credit(self, u):
        """Кому засчитать урон и лечение: призыв — хозяину, остальное — самому юниту."""
        while u is not None and u.summon and getattr(u, "owner", None) is not None and u.owner is not u:
            u = u.owner
        return u

    def heal(self, u, amount, src=None):
        if not u.alive:
            return 0
        if "trance" in u.buffs and amount > 0:   # кровавый транс: лечение превращается в ярость
            rage = min(2.0, u.buff("atk_mult", 1.0) + amount * u.buff("trance", 0.01))
            self.add_buff(u, "atk_mult", round(rage, 3), u.buffs["trance"][1])
            self.emit("rage", unit=u, value=rage)
            return 0
        for t in list(u.statuses):               # яд режет лечение (сильнее — на большем числе стаков)
            dot = u.dots.get(t)
            mult = self._dot_heal_mult(u, t, dot) if dot else self.tags.get(t, {}).get("heal_mult", 1.0)
            amount = int(round(amount * mult))
        amount = int(round(amount * u.buff("heal_taken", 1.0)))    # проклятие склепа
        real = min(amount, u.max_hp - u.hp)
        u.hp += real
        u.tally["healed_in"] += real
        who = self.credit(src if src is not None else u)
        if who is not None:
            who.tally["healed"] += real
            who.tally["healed_frac"] += real / max(1, u.max_hp)
        self.emit("heal", unit=u, amount=real)
        return real

    def apply_status(self, u, tag, attacker=None, hit=0, hostile=None):
        """Вешает тег-статус. Если на юните есть реагирующий тег — реакция. Возвращает бонус к удару.
        hostile — тег наложил враг юнита (или опасная среда): реакция в полную силу. Союзник или рельеф —
        реакция только нейтрализует теги (вода союзника тушит, а не обваривает паром)."""
        dur = self.cfg["status_duration"]
        if "immune" in u.buffs or u.obj:
            return 0
        if attacker is not None and attacker.is_enemy(u):
            PS.on_status(self, u, tag, attacker)
        if hostile is None:
            hostile = attacker is None or attacker.is_enemy(u)
        if tag == "water":
            return self._apply_water(u, attacker, hit, hostile)
        if tag in DOT_TAGS:
            return self._apply_dot_status(u, tag, attacker, hit, hostile)
        if tag in u.statuses:
            u.statuses[tag] = dur
            return 0
        if "stable" in u.buffs:               # стабилизатор зельевара: теги копятся, не реагируя
            u.statuses[tag] = dur
            self.emit("status", unit=u, tag=tag)
            return 0
        for other in list(u.statuses):
            r = self._reactions.get(frozenset((tag, other)))
            if r and (r["id"] not in u.reaction_cd or not hostile):
                self._clear_dot(u, other)
                return self._react(r, u, attacker, hit, hostile)
        u.statuses[tag] = dur
        self.emit("status", unit=u, tag=tag)
        self.rules.fire("status", {"element", tag, *self.tags[tag].get("groups", [])}, unit=u, source=attacker)
        return 0

    def _apply_water(self, u, attacker, hit, hostile):
        """Вода всегда тушит огонь; союзная/рельефная вода оставляет мокрый тег, вражеская — пар."""
        dur = self.cfg["status_duration"]
        if "fire" in u.statuses:
            self._clear_dot(u, "fire")
            self.emit("extinguish", unit=u, tag="fire")
            r = self._reactions.get(frozenset(("fire", "water")))
            if r and (not hostile or r["id"] not in u.reaction_cd):
                if hostile or attacker is not None:   # вода-навык/вражеская вода расходуется на пар
                    self._clear_dot(u, "water")
                    return self._react(r, u, attacker, hit, hostile)
                self._react(r, u, None, hit, False)   # рельеф: пар нейтрализует огонь, мокрый тег остаётся
        if "water" in u.statuses:
            u.statuses["water"] = dur
            return 0
        if "stable" in u.buffs:
            u.statuses["water"] = dur
            self.emit("status", unit=u, tag="water")
            return 0
        for other in list(u.statuses):
            r = self._reactions.get(frozenset(("water", other)))
            if r and (r["id"] not in u.reaction_cd or not hostile):
                self._clear_dot(u, other)
                return self._react(r, u, attacker, hit, hostile)
        u.statuses["water"] = dur
        self.emit("status", unit=u, tag="water")
        self.rules.fire("status", {"element", "water", *self.tags["water"].get("groups", [])},
                        unit=u, source=attacker)
        return 0

    def _apply_dot_status(self, u, tag, attacker, hit, hostile):
        """Наложение дот-тега с реакциями и правилами стаков."""
        self._sync_dots(u)
        cfg = self._dot_cfg(tag)
        dur = cfg.get("duration", self.cfg["status_duration"])
        if tag == "fire" and ("water" in u.statuses or "wet" in C.unit_tags(self, u)):
            self._clear_dot(u, "fire")             # мокрого поджечь нельзя
            self.emit("extinguish", unit=u, tag="fire")
            r = self._reactions.get(frozenset(("fire", "water")))
            if hostile and r and r["id"] not in u.reaction_cd:
                self._clear_dot(u, "water")
                return self._react(r, u, attacker, hit, hostile)
            return 0
        if tag in u.statuses:
            if tag == "fire":                      # горение не стакается, только сильнейшее обновление
                refresh = dur * getattr(attacker, "dot_duration_mult", 1.0) if attacker is not None else dur
                if not self._refresh_dot(u, tag, refresh):
                    u.statuses[tag] = refresh
                return 0
            dps = self._dot_dps(tag, attacker, hit)
            self.apply_dot(u, tag, dps, dur, attacker=attacker, add_stack=True)
            return 0
        env = attacker is None and not hit
        dps = 0.0 if env else self._dot_dps(tag, attacker, hit)
        dps_pct = cfg.get("env_pct") if env else None
        env_type = cfg.get("env_damage_type") if env else None
        if "stable" in u.buffs:
            self.apply_dot(u, tag, dps, dur, attacker=attacker, dps_pct=dps_pct, damage_type=env_type)
            return 0
        for other in list(u.statuses):
            r = self._reactions.get(frozenset((tag, other)))
            if r and (r["id"] not in u.reaction_cd or not hostile):
                self._clear_dot(u, other)
                return self._react(r, u, attacker, hit, hostile)
        self.apply_dot(u, tag, dps, dur, attacker=attacker, dps_pct=dps_pct, damage_type=env_type)
        return 0

    def _touch_status(self, u, tag, attacker=None, hostile=None):
        """Тег без удара (клетка, эффект «status»): бонусный урон реакции наносится отдельно."""
        self._sync_dots(u)
        if tag in u.statuses:
            if tag in u.dots:
                self._refresh_dot(u, tag)
            else:
                u.statuses[tag] = self.cfg["status_duration"]
            return
        extra = self.apply_status(u, tag, attacker, 0, hostile)
        if extra and u.alive:
            self.damage(u, extra, attacker, kind="reaction")

    def _react(self, r, u, attacker, hit, hostile=True):
        rtags = {"reaction", r["id"], *r["tags"]}
        if not hostile:                     # нейтрализация: теги сняты, вреда нет
            self.emit("reaction", unit=u, id=r["id"], name=r.get("soft", r["name"]), tags=r["tags"], friendly=True)
            self.log(f"{u.name}: {r.get('soft', r['name']).lower()}", (180, 210, 230))
            self.rules.fire("reaction", rtags | {"friendly"}, unit=u, source=attacker)
            return 0
        u.reaction_cd[r["id"]] = self.cfg["reaction_cooldown"]
        mult = self.fx.get("reaction_mult", 1.0) if attacker is not None and attacker.team == PLAYER else 1.0
        if attacker is not None:            # дар героя: его реакции сильнее
            mult *= attacker.proto.get("reaction_mult", 1.0)
        p = attacker.passive if attacker is not None else None
        if p and p["kind"] == "catalyst" and attacker.alive and attacker.pp >= p["pp"]:
            self._use_passive(attacker, f"реакция ×{p['mult']:g}", u)
            mult *= p["mult"]
        self.emit("reaction", unit=u, id=r["id"], name=r["name"], tags=r["tags"])
        if attacker is not None:            # запал подрывника: любая реакция его отряда
            for a in self.heroes(attacker.team):
                self.gain(a, "reaction")
        self.log(f"Реакция «{r['name']}» на {u.name}", tuple(self.tags[r["tags"][0]]["color"]))
        extra = 0
        for eff in r["effects"]:
            t = eff["type"]
            if t in ("aoe_damage", "strip_shields"):
                for v in self.units_in_radius(u.cell, eff["radius"]):
                    if eff["affects"] == "target_side" and v.team != u.team:
                        continue
                    if t == "aoe_damage":
                        self.damage(v, eff["amount"] * mult, attacker, kind="reaction")
                    else:
                        v.shield = 0
            elif t == "bonus_damage":
                extra += max(eff["min"], hit * eff["mult"]) * mult
            elif t == "stun":
                self.apply_stun(u, eff["duration"], {"freeze": "freeze", "shock": "shock"}.get(r["id"]))
            elif t == "spread_status":          # ядовитое облако: тег на всех вокруг
                for v in self.units_in_radius(u.cell, eff["radius"]):
                    if v is not u and v.team == u.team:
                        self._touch_status(v, eff["tag"], attacker)
            elif t == "hazard":                 # пожар: клетки вокруг горят
                for p in self.grid.in_radius(u.cell, eff["radius"]):
                    c = self.grid.get(p)
                    if c.passable and c.terrain != "water":
                        c.hazard, c.hazard_time, c.hazard_team = eff["hazard"], eff["duration"], None
        self.rules.fire("reaction", rtags, unit=u, source=attacker)
        return extra

    def _intercede(self, target):
        for ally in self.units:
            p = ally.passive
            if (ally is target or not ally.alive or ally.team != target.team or not p
                    or p["kind"] != "intercede" or ally.pp < p["pp"]
                    or cheb(ally.cell, target.cell) > p["range"]):
                continue
            self._use_passive(ally, f"+{p['heal']} HP: {target.name}", target)
            self.heal(target, p["heal"])
            return

    def _try_concentration(self, u):
        p = u.passive
        if p and p["kind"] == "concentration" and u.pp >= p["pp"]:
            self._use_passive(u, "каст не сорван")
            return True
        return False

    def _use_passive(self, u, detail, other=None):
        """Тратит PP на пассивку и сообщает об этом UI и журналу."""
        p = u.passive
        u.pp -= p["pp"]
        self.emit("passive", unit=u, name=p["name"], kind=p["kind"], detail=detail, other=other)
        self.log(f"{u.name}: {p['name']} ({detail})", (255, 140, 200))

    def _interrupt(self, u):
        if u.cast and not self._try_concentration(u):
            if self._actor is not None and self._actor.team != u.team:
                self._actor.tally["interrupts"] += 1
            sk = u.skill_defs[u.cast["skill"]]
            u.cast = None
            self.emit("interrupt", unit=u)
            self.log(f"{u.name}: каст «{sk['name']}» сорван", (255, 200, 120))

    def apply_stun(self, u, dur, look=None):
        """Оглушение. look — как оно выглядит: stun (звёзды), root (корни), net (сеть), trap (капкан),
        freeze (лёд), shock (разряд), blind (ослепление), sleep (сон)."""
        if not u.alive:
            return
        self._interrupt(u)
        if self._actor is not None and self._actor.team != u.team:
            self._actor.tally["cc"] += max(0.0, dur - max(0.0, u.stun))
        if dur >= u.stun:
            u.stun_look = look or "stun"
            u.stun_total = dur
        u.stun = max(u.stun, dur)
        self.emit("stun", unit=u, duration=dur, look=u.stun_look)
        look = u.stun_look
        self.rules.fire("status", {"control", look, *self.cfg.get("control_tags", {}).get(look, [])}, unit=u)

    def knockback(self, src_cell, u, cells, pusher=None, kind="knockback"):
        """Толчок от src_cell на cells клеток (sim/movement.py): лёд скользит, пропасть — падение, не дотолкали —
        столкновение. Двигается всё, кроме стен."""
        d = M.push_dir(src_cell, u)
        if d == (0, 0) or not u.alive:
            return
        M.forced_move(self, u, cells, M.straight(d), pusher, kind, slide=True)

    force_push = knockback

    def _kill(self, u, expire=False, tag=None):
        u.alive = False
        u.hp = 0
        if not expire and not u.obj and u.last_hit_by is not None and u.last_hit_by.team != u.team:
            u.last_hit_by.tally["kills"] += 1
            for s, t0 in u.hit_by.items():       # помощь: били его в последние 6 сек, но добил другой
                if s is not u.last_hit_by and s.team != u.team and self.time - t0 <= 6.0:
                    s.tally["assists"] += 1
        if not expire and not u.obj:
            PS.on_death(self, u)
            if u.mutator and not (u.undying and not u.risen):
                MU.on_death(self, u)
        u.cast = None
        u.order = None
        rises = u.undying and not u.risen and tag not in u.undying.get("unless", ["fire"])
        self.emit("death", unit=u, expire=expire, rises=bool(rises))
        if not u.summon and not rises and not expire and u.team == ENEMY:
            self.corpses.append({"cell": u.cell, "left": self.cfg.get("corpse_time", 14.0), "name": u.name})
        if rises:                              # нежить поднимется, если не добить огнём
            u.risen = True
            self.rising.append([u, u.undying.get("delay", 3.0)])
            self.log(f"{u.name} падает… но кости ещё шевелятся", (190, 200, 170))
            return
        if u.summon:
            if not expire:
                self.log(f"{u.name} разрушен", (200, 200, 200))
            return
        self.log(f"{u.name} выбывает", (255, 120, 120) if u.team == PLAYER else (150, 230, 150))
        if u.on_death:
            self.log(f"{u.name}: {u.on_death['name']}", (255, 170, 90))
            self.emit("skill", unit=u, skill=None, center=u.cell, target=None)
            self.apply_effects(u, u.on_death["effects"], u.cell)

    def _rise(self, u):
        cell = u.cell if self.is_free(u.cell) else next(
            (p for p, _ in self.grid.neighbors(u.cell) if self.is_free(p)), None)
        if cell is None:
            return
        u.cell = u.prev_cell = cell
        u.alive = True
        u.hp = max(1, int(u.max_hp * u.undying.get("hp", 0.5)))
        u.statuses.clear()
        u.dots.clear()
        u.buffs.clear()
        u.buff_total.clear()
        u.stun = 0.0
        self.emit("rise", unit=u)
        self.log(f"{u.name} встаёт снова!", (190, 220, 160))

    # ---------- события поля (извержение, лавина, гроза, ветер, буря, прилив) ----------

    def _arena_update(self, dt):
        if self.time < 1.0:
            return
        for ev in self.arena:
            if ev["pending"] is not None:
                ev["pending"] -= dt
                if ev["pending"] <= 0:
                    ev["pending"] = None
                    self._arena_hit(ev)
                continue
            ev["timer"] -= dt
            if ev["timer"] <= 0:
                lo, hi = ev.get("every", [10, 14])
                ev["timer"] = self.rng.uniform(lo, hi) * ev["rate"]
                self._arena_warn(ev)

    def _near_heroes(self, count, spread=1):
        heroes = [u for u in self.alive(PLAYER) if not u.summon] or self.alive(PLAYER)
        cells = []
        for _ in range(count * 4):
            if len(cells) >= count or not heroes:
                break
            h = self.rng.choice(heroes)
            p = (h.cell[0] + self.rng.randint(-spread, spread), h.cell[1] + self.rng.randint(-spread, spread))
            c = self.grid.get(p)
            if c and c.passable and p not in cells:
                cells.append(p)
        return cells

    def _arena_warn(self, ev):
        kind = ev["type"]
        cells, direction = [], None
        if kind in ("eruption", "lightning"):
            cells = self._near_heroes(ev.get("count", 3))
        elif kind == "avalanche":
            heroes = self.alive(PLAYER)
            if heroes:
                hx, hy = self.rng.choice(heroes).cell
                x0, y0 = hx - self.rng.randint(0, 2), hy - self.rng.randint(0, 1)
                cells = [(x, y) for x in range(x0, x0 + 3) for y in range(y0, y0 + 2)
                         if self.grid.get((x, y)) and self.grid.get((x, y)).passable]
        elif kind == "tide":
            rows = self.rng.sample(range(self.grid.h), min(ev.get("rows", 2), self.grid.h))
            cells = [p for p, c in self.grid.cells.items() if p[1] in rows and c.passable
                     and c.terrain not in ("lava", "chasm")]
        elif kind == "wind" or kind == "bellows":
            direction = self.rng.choice([(1, 0), (-1, 0)])
        elif kind == "ladle":                  # ковш: льёт расплав вдоль самого людного ряда (и враги там стоят)
            rows = {}
            for u in self.alive():
                if not u.obj:
                    rows[u.cell[1]] = rows.get(u.cell[1], 0) + 1
            if rows:
                y = max(rows, key=lambda r: (rows[r], self.rng.random()))
                xs = sorted(u.cell[0] for u in self.alive() if u.cell[1] == y and not u.obj)
                mid = xs[len(xs) // 2]
                n = ev.get("length", 5)
                x0 = max(0, min(self.grid.w - n, mid - n // 2))
                cells = [(x, y) for x in range(x0, x0 + n) if self.grid.get((x, y)) and self.grid.get((x, y)).passable]
        ev["cells"], ev["dir"] = cells, direction
        ev["pending"] = ev.get("warn", 1.5)
        self.emit("arena_warn", kind=kind, cells=cells, dir=direction, delay=ev["pending"], name=ev.get("name", kind))

    def _arena_hit(self, ev):
        kind, cells = ev["type"], ev.get("cells", [])
        dmg = ev.get("damage", 0) * self.diff.get("event_dmg", 1.0)
        self.emit("arena_hit", kind=kind, cells=cells, dir=ev.get("dir"))
        if kind == "ladle":                    # расплав: урон всем на ряду и огонь на клетках
            for p in cells:
                v = self.unit_at(p)
                if v and not v.static and v.alive:
                    self.damage(v, dmg, None, "fire", "reaction")
                c = self.grid.get(p)
                if c.terrain not in ("water", "chasm"):
                    c.hazard, c.hazard_time, c.hazard_team = "fire", ev.get("burn", 5), None
            return
        if kind == "bellows":                  # меха: толкают всех и раздувают огонь по ветру
            dx, dy = ev["dir"]
            units = sorted([u for u in self.alive() if M.movable(self, u) and not u.flying],
                           key=lambda u: -u.cell[0] * dx)
            for u in units:
                self.knockback((u.cell[0] - dx, u.cell[1] - dy), u, ev.get("push", 1), kind="wind")
            fires = [p for p, c in self.grid.cells.items() if c.hazard == "fire"]
            for (x, y) in fires:
                q = (x + dx, y + dy)
                c = self.grid.get(q)
                if c and c.passable and c.terrain not in ("water", "chasm") and not c.hazard:
                    c.hazard, c.hazard_time, c.hazard_team = "fire", 4, None
            return
        if kind in ("eruption", "lightning", "avalanche"):
            tag = {"eruption": "fire", "lightning": "storm", "avalanche": "ice"}[kind]
            for p in cells:
                v = self.unit_at(p)
                if v and not v.static and v.alive:
                    self.damage(v, dmg, None, tag, "reaction")
                    if kind == "avalanche" and v.alive:
                        self.apply_stun(v, ev.get("stun", 1.2))
                if kind == "eruption":
                    c = self.grid.get(p)
                    if c.terrain not in ("water", "chasm"):
                        c.hazard, c.hazard_time, c.hazard_team = "fire", ev.get("burn", 4), None
        elif kind == "wind":
            dx, dy = ev["dir"]
            units = sorted([u for u in self.alive() if M.movable(self, u) and not u.flying],
                           key=lambda u: -u.cell[0] * dx)
            for u in units:
                self.knockback((u.cell[0] - dx, u.cell[1] - dy), u, ev.get("push", 1), kind="wind")
        elif kind == "sandstorm":
            for u in self.alive():
                if u.atk_range > 1:
                    u.buffs["range_add"] = [-ev.get("range", 2), ev.get("duration", 6)]
        elif kind == "tide":
            for p in cells:
                c = self.grid.get(p)
                if c.terrain != "water":
                    c.base_terrain, c.terrain = c.terrain, "water"
                c.hazard = None
            self.tides.append([self.time + ev.get("duration", 6), cells])

    def battle_stats(self, team=PLAYER):
        """Итог боя для экрана статистики: по героям (и гостям) — урон, полученный урон, поглощено щитом, лечение,
        убийства, применения навыков; общее — время, убито врагов."""
        rows = []
        for u in self.units:
            if u.team != team or u.obj or (u.summon and u.owner is not None):
                continue
            t = dict(u.tally)
            t.update(name=u.name, cls=u.proto_id, alive=u.alive, hp=u.hp, max_hp=u.max_hp, guest=u.summon,
                     uses={sid: n for sid, n in sorted(u.uses.items(), key=lambda kv: -kv[1])},
                     skill_names={sid: u.skill_defs[sid]["name"] for sid in u.uses if sid in u.skill_defs})
            rows.append(t)
        foes = [u for u in self.units if u.team != team and not u.obj]
        return {"time": round(self.time, 1), "rows": rows, "killed": sum(1 for u in foes if not u.alive),
                "foes": len(foes), "result": self.result}

    def _check_end(self):
        ob = self.objective or {}
        if not any(u.alive for u in self.heroes(PLAYER)) or any(not g.alive for g in self.guards()):
            self.result = "defeat"
        elif ob.get("type") == "hold":
            if self.hold >= ob["time"]:
                self.result = "victory"
        elif not self.alive(ENEMY) and not self.rising and not self.waves and self.intermission <= 0:
            self.result = "victory"
        if self.result:
            self.emit("end", result=self.result)
